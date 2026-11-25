"""Catálogo local persistente en SQLite (un archivo, sin servidor).

Ubicación por defecto: ``data/pillalu.db`` dentro del proyecto (ignorado por Git).
Se puede cambiar con la variable de entorno ``PILLALU_DB``.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from ..core.models import CHANNELS, Product
from ..core.pricing import ChannelConfig

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = PROJECT_ROOT / "data" / "pillalu.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    supplier_id TEXT,
    supplier_name TEXT,
    supplier_cost_cop INTEGER,
    suggested_price_cop INTEGER,
    stock INTEGER,
    images_json TEXT NOT NULL DEFAULT '[]',
    weight_g INTEGER,
    shipping_cost_cop INTEGER,
    has_variants INTEGER NOT NULL DEFAULT 0,
    excluded INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (source_id)
);
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    supplier_cost_cop INTEGER,
    suggested_price_cop INTEGER,
    stock INTEGER,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    created_at TEXT NOT NULL,
    inserted INTEGER NOT NULL,
    updated INTEGER NOT NULL,
    unchanged INTEGER NOT NULL,
    rejected INTEGER NOT NULL,
    details_json TEXT
);
CREATE TABLE IF NOT EXISTS channel_settings (
    channel TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    footer TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS listing_drafts (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    price_cop INTEGER,
    status TEXT NOT NULL DEFAULT 'borrador',
    external_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (product_id, channel)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

DRAFT_STATUSES = ("borrador", "lista", "publicada_manual", "descartada")
STATUS_LABELS = {
    "borrador": "Borrador",
    "lista": "Lista para publicar",
    "publicada_manual": "Publicada (manual)",
    "descartada": "Descartada",
}
TRACKED = ("supplier_cost_cop", "suggested_price_cop", "stock")
UPDATABLE = (
    "name", "description", "category", "supplier_id", "supplier_name", "supplier_cost_cop",
    "suggested_price_cop", "stock", "weight_g", "shipping_cost_cop", "has_variants",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(path or os.environ.get("PILLALU_DB") or DEFAULT_DB)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    # Una conexión por unidad de trabajo / hilo (auditoría P1-03): no se comparte entre
    # sesiones de Streamlit; SQLite serializa a los escritores con su propio bloqueo.
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1')")
    version = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0]
    if version == "1":
        # v2: no se conservan filas crudas importadas (auditoría P2-04); se borran las históricas.
        conn.execute("UPDATE products SET raw_json = NULL WHERE raw_json IS NOT NULL")
        conn.execute("UPDATE meta SET value = '2' WHERE key = 'schema_version'")
    conn.commit()
    return conn


def _row_to_product(row: sqlite3.Row) -> Product:
    return Product(
        id=row["id"],
        source=row["source"],
        source_id=row["source_id"],
        name=row["name"],
        description=row["description"],
        category=row["category"],
        supplier_id=row["supplier_id"],
        supplier_name=row["supplier_name"],
        supplier_cost_cop=row["supplier_cost_cop"],
        suggested_price_cop=row["suggested_price_cop"],
        stock=row["stock"],
        images=json.loads(row["images_json"] or "[]"),
        weight_g=row["weight_g"],
        shipping_cost_cop=row["shipping_cost_cop"],
        has_variants=bool(row["has_variants"]),
    )


def upsert_products(conn: sqlite3.Connection, products: Iterable[Product], filename: str = "", rejected: int = 0,
                    details: dict | None = None) -> dict[str, int]:
    """Inserta o actualiza por ``source_id`` (id de Dropi). Guarda historial de costo/stock.

    Un campo vacío en el archivo **no borra** un dato ya conocido.
    """
    products = list(products)
    # Validación en la capa de persistencia: ningún origen puede guardar valores inválidos.
    invalid = [(p.source_id or p.name, e) for p in products for e in p.invalid_values()]
    if invalid:
        raise ValueError("Productos inválidos, no se guardó nada: "
                         + "; ".join(f"{who}: {e}" for who, e in invalid[:10]))
    counts = {"inserted": 0, "updated": 0, "unchanged": 0}
    now = _now()
    # Lote atómico: productos, historial y registro del lote se confirman juntos o nada.
    with _transaction(conn):
        for p in products:
            existing = conn.execute("SELECT * FROM products WHERE source_id = ?", (p.source_id,)).fetchone()
            if existing is None:
                cur = conn.execute(
                    """INSERT INTO products (source, source_id, name, description, category, supplier_id,
                       supplier_name, supplier_cost_cop, suggested_price_cop, stock, images_json, weight_g,
                       shipping_cost_cop, has_variants, raw_json, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (p.source, p.source_id, p.name, p.description, p.category, p.supplier_id, p.supplier_name,
                     p.supplier_cost_cop, p.suggested_price_cop, p.stock, json.dumps(p.images), p.weight_g,
                     p.shipping_cost_cop, int(bool(p.has_variants)), None,
                     now, now),
                )
                conn.execute(
                    "INSERT INTO price_history (product_id, supplier_cost_cop, suggested_price_cop, stock, recorded_at)"
                    " VALUES (?,?,?,?,?)",
                    (cur.lastrowid, p.supplier_cost_cop, p.suggested_price_cop, p.stock, now),
                )
                counts["inserted"] += 1
                continue
            changes: dict[str, Any] = {}
            for f in UPDATABLE:
                new = getattr(p, f)
                if f == "has_variants" and new is not None:
                    new = int(new)  # un "no" explícito sí limpia el dato anterior
                if new is None or new == "":
                    continue
                if existing[f] != new:
                    changes[f] = new
            if p.images and json.loads(existing["images_json"] or "[]") != p.images:
                changes["images_json"] = json.dumps(p.images)
            if not changes:
                counts["unchanged"] += 1
                continue
            sets = ", ".join(f"{k} = ?" for k in changes)
            conn.execute(
                f"UPDATE products SET {sets}, updated_at = ? WHERE id = ?",
                (*changes.values(), now, existing["id"]),
            )
            if any(f in changes for f in TRACKED):
                conn.execute(
                    "INSERT INTO price_history (product_id, supplier_cost_cop, suggested_price_cop, stock, recorded_at)"
                    " VALUES (?,?,?,?,?)",
                    (existing["id"], changes.get("supplier_cost_cop", existing["supplier_cost_cop"]),
                     changes.get("suggested_price_cop", existing["suggested_price_cop"]),
                     changes.get("stock", existing["stock"]), now),
                )
            counts["updated"] += 1
        conn.execute(
            "INSERT INTO import_batches (filename, created_at, inserted, updated, unchanged, rejected, details_json)"
            " VALUES (?,?,?,?,?,?,?)",
            (filename, now, counts["inserted"], counts["updated"], counts["unchanged"], rejected,
             json.dumps(details or {}, ensure_ascii=False)),
        )
    return counts


class _transaction:
    """``BEGIN IMMEDIATE`` … ``COMMIT``/``ROLLBACK`` explícitos sobre una conexión."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self):
        if self.conn.in_transaction:
            self.conn.commit()
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        return False


def list_products(conn: sqlite3.Connection, include_excluded: bool = True) -> list[Product]:
    sql = "SELECT * FROM products" + ("" if include_excluded else " WHERE excluded = 0") + " ORDER BY id"
    return [_row_to_product(r) for r in conn.execute(sql)]


def get_product(conn: sqlite3.Connection, product_id: int) -> Product | None:
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _row_to_product(row) if row else None


def excluded_ids(conn: sqlite3.Connection) -> set[int]:
    return {r[0] for r in conn.execute("SELECT id FROM products WHERE excluded = 1")}


def set_excluded(conn: sqlite3.Connection, product_ids: Iterable[int], excluded: bool) -> None:
    with _transaction(conn):
        conn.executemany("UPDATE products SET excluded = ? WHERE id = ?", [(int(excluded), i) for i in product_ids])


def price_history(conn: sqlite3.Connection, product_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT supplier_cost_cop, suggested_price_cop, stock, recorded_at FROM price_history"
        " WHERE product_id = ? ORDER BY id", (product_id,))]


def last_imports(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT filename, created_at, inserted, updated, unchanged, rejected FROM import_batches"
        " ORDER BY id DESC LIMIT ?", (limit,))]


# --- Configuración por canal -------------------------------------------------

def get_channel_config(conn: sqlite3.Connection, channel: str) -> ChannelConfig:
    row = conn.execute("SELECT config_json FROM channel_settings WHERE channel = ?", (channel,)).fetchone()
    if row:
        return ChannelConfig.from_dict(json.loads(row["config_json"]))
    # Sin datos inventados: todo desconocido salvo preferencias de margen.
    return ChannelConfig(channel=channel, use_product_shipping=(channel == "facebook"))


def get_footer(conn: sqlite3.Connection, channel: str) -> str:
    row = conn.execute("SELECT footer FROM channel_settings WHERE channel = ?", (channel,)).fetchone()
    return row["footer"] if row else ""


def save_channel_config(conn: sqlite3.Connection, cfg: ChannelConfig, footer: str = "") -> None:
    with _transaction(conn):
        conn.execute(
            "INSERT INTO channel_settings (channel, config_json, footer, updated_at) VALUES (?,?,?,?)"
            " ON CONFLICT(channel) DO UPDATE SET config_json = excluded.config_json, footer = excluded.footer,"
            " updated_at = excluded.updated_at",
            (cfg.channel, json.dumps(cfg.to_dict()), footer, _now()),
        )


def all_configs(conn: sqlite3.Connection) -> dict[str, ChannelConfig]:
    return {c: get_channel_config(conn, c) for c in CHANNELS}


# --- Fichas comerciales -------------------------------------------------------

def upsert_draft(conn: sqlite3.Connection, product_id: int, channel: str, title: str, description: str,
                 price_cop: int | None, overwrite: bool = False) -> bool:
    """Crea la ficha. Si ya existe, solo la reemplaza con ``overwrite`` (no pisa ediciones)."""
    if price_cop is not None and price_cop <= 0:
        raise ValueError("El precio de la ficha debe ser mayor que 0.")
    now = _now()
    with _transaction(conn):
        existing = conn.execute(
            "SELECT id FROM listing_drafts WHERE product_id = ? AND channel = ?", (product_id, channel)
        ).fetchone()
        if existing and not overwrite:
            return False
        if existing:
            conn.execute(
                "UPDATE listing_drafts SET title = ?, description = ?, price_cop = ?, status = 'borrador',"
                " external_url = NULL, updated_at = ? WHERE id = ?",
                (title, description, price_cop, now, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO listing_drafts (product_id, channel, title, description, price_cop, created_at,"
                " updated_at) VALUES (?,?,?,?,?,?,?)",
                (product_id, channel, title, description, price_cop, now, now),
            )
    return True


def update_draft(conn: sqlite3.Connection, draft_id: int, **fields: Any) -> None:
    allowed = {"title", "description", "price_cop", "status", "external_url"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if "status" in fields and fields["status"] not in DRAFT_STATUSES:
        raise ValueError(f"Estado inválido: {fields['status']}")
    if fields.get("price_cop") is not None and fields["price_cop"] <= 0:
        raise ValueError("El precio de la ficha debe ser mayor que 0.")
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _transaction(conn):
        conn.execute(f"UPDATE listing_drafts SET {sets}, updated_at = ? WHERE id = ?",
                     (*fields.values(), _now(), draft_id))


def list_drafts(conn: sqlite3.Connection, channel: str | None = None) -> list[dict]:
    sql = ("SELECT d.*, p.name AS product_name, p.images_json, p.source_id, p.stock, p.supplier_cost_cop, p.excluded,"
           " p.category FROM listing_drafts d JOIN products p ON p.id = d.product_id")
    args: tuple = ()
    if channel:
        sql += " WHERE d.channel = ?"
        args = (channel,)
    sql += " ORDER BY d.updated_at DESC, d.id DESC"
    out = []
    for r in conn.execute(sql, args):
        d = dict(r)
        d["images"] = json.loads(d.pop("images_json") or "[]")
        out.append(d)
    return out


def custom_prices(conn: sqlite3.Connection) -> dict[tuple[int, str], int]:
    """Precio elegido en la ficha (si existe) por (producto, canal)."""
    return {(r["product_id"], r["channel"]): r["price_cop"] for r in conn.execute(
        "SELECT product_id, channel, price_cop FROM listing_drafts"
        " WHERE price_cop > 0 AND status != 'descartada'")}


def delete_draft(conn: sqlite3.Connection, draft_id: int) -> None:
    with _transaction(conn):
        conn.execute("DELETE FROM listing_drafts WHERE id = ?", (draft_id,))
