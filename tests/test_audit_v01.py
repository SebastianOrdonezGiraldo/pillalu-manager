"""Regresiones de la auditoría independiente de v0.1 (commit d4697da, 25-nov-2026).

Cada prueba reproduce el caso del informe docs/audits/money-engine-v0.1-2026-11-25-d4697da.md.
"""

import json
import sqlite3
import threading

import pytest

from conftest import ROOT
from pillalu import drafts as draft_rules
from pillalu.adapters.dropi import file_import
from pillalu.adapters.dropi.mapping import MappingError, parse_mapping
from pillalu.catalog import build_rows
from pillalu.core.models import Product, valid_image_url
from pillalu.core.pricing import (
    ChannelConfig, UncoveredTierError, analyze, break_even_units, evaluate, expected_deliveries, parse_tiers,
    solve_min_price, tier_value,
)
from pillalu.export import drafts_to_fb_zip, drafts_to_ml_csv
from pillalu.storage import db


def cfg(**kw):
    base = dict(channel="facebook", commission_pct=0.0, fixed_fee_tiers=[(None, 0)], other_pct=0.0,
                shipping_tiers=[(None, 0)], packaging_cop=0, return_rate=0.0, return_cost_cop=0,
                target_margin=0.25, min_margin=0.10, min_profit_cop=5000)
    base.update(kw)
    return ChannelConfig(**base)


# --- P0-01 · tramo sin tarifa ------------------------------------------------------

def test_p0_01_audit_case_uncovered_tier_is_incomplete_not_zero():
    r = analyze(47000, cfg(shipping_tiers=[(50000, 12000)]))
    assert not r.complete and r.recommended_price is None
    assert any("tramo final" in m for m in r.missing)


def test_p0_01_parse_requires_final_tier():
    with pytest.raises(ValueError, match="tramo final"):
        parse_tiers("hasta 50000: 12000")
    assert parse_tiers("hasta 50000: 12000\nresto: 18000") == [(50000, 12000), (None, 18000)]


def test_p0_01_audit_case_with_full_table_charges_the_real_freight():
    c = cfg(shipping_tiers=[(50000, 12000), (None, 18000)])
    r = analyze(47000, c)
    b = r.at_recommended
    assert b.shipping == 18000  # el precio recomendado cae en el tramo superior
    assert b.expected_profit >= 5000 and b.margin >= 0.25 - 1e-9
    assert evaluate(62900, 47000, c).expected_profit == pytest.approx(-2100)  # el caso del informe


@pytest.mark.parametrize("which", ["shipping_tiers", "fixed_fee_tiers"])
def test_p0_01_both_tables_below_at_above_boundary(which):
    tiers = [(50000, 1000), (None, 3000)]
    assert [tier_value(tiers, p) for p in (49999, 50000, 50001)] == [1000, 1000, 3000]
    with pytest.raises(UncoveredTierError):
        tier_value([(50000, 1000)], 50001)
    c = cfg(**{which: tiers})
    for price in (49999, 50000, 50001):
        b = evaluate(price, 20000, c)
        got = b.shipping if which == "shipping_tiers" else b.fixed_fee
        assert got == (1000 if price <= 50000 else 3000)
    assert not analyze(20000, cfg(**{which: [(50000, 1000)]})).complete


def test_p0_01_explicit_zero_is_allowed():
    assert analyze(20000, cfg(shipping_tiers=parse_tiers("0"))).complete


# --- P0-02 · costos negativos en todas las entradas --------------------------------

def test_p0_02_mapping_rejects_negative_freight():
    raw = {"items": [{"id": "N1", "name": "Ficticio", "cost": 25000, "freight": -12000}]}
    mapping = parse_mapping({"items_path": "items", "fields": {
        "source_id": "id", "name": "name", "supplier_cost_cop": "cost", "shipping_cost_cop": "freight"}})
    report = file_import.read_json_text(json.dumps(raw), mapping)
    assert not report.products and "flete" in report.rejected[0][1]


def test_p0_02_persistence_layer_rejects_negative_values(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    bad = Product(source="manual", source_id="N1", name="X", supplier_cost_cop=25000, shipping_cost_cop=-12000)
    with pytest.raises(ValueError):
        db.upsert_products(conn, [bad])
    assert db.list_products(conn) == []


def test_p0_02_negative_config_tier_rejected():
    with pytest.raises(ValueError, match="negativ"):
        parse_tiers("-2000")
    assert not analyze(25000, cfg(fixed_fee_tiers=[(None, -2000)])).complete
    assert not analyze(25000, cfg(packaging_cop=-1)).complete
    assert not analyze(25000, cfg(commission_pct=1.2)).complete


def test_p0_02_audit_case_negative_product_freight_blocks_calculation():
    c = cfg(use_product_shipping=True, shipping_tiers=None)
    r = analyze(25000, c, product_shipping=-12000)
    assert not r.complete and r.recommended_price is None
    assert evaluate(18900, 25000, c, 12000).expected_profit == pytest.approx(-18100)


def test_p0_02_previously_stored_invalid_rows_are_blocked(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.upsert_products(conn, [Product(source="csv", source_id="OLD", name="Viejo", supplier_cost_cop=25000)])
    conn.execute("UPDATE products SET shipping_cost_cop = -12000")  # dato heredado de v0.1
    conn.commit()
    c = cfg(use_product_shipping=True, shipping_tiers=None)
    rows = build_rows(db.list_products(conn), {"facebook": c, "mercadolibre": cfg(channel="mercadolibre")})
    assert all(not r.complete for r in rows[0].results.values())
    assert rows[0].results["facebook"].selling is None


# --- P1-01 · aviso del precio manual en su propio tramo ----------------------------

def test_p1_01_audit_case_custom_price_in_expensive_tier_warns_loss():
    c = cfg(shipping_tiers=[(40000, 0), (None, 30000)])
    r = analyze(20000, c, custom_price=41000)
    assert r.min_profitable_price == 25000
    assert r.at_custom.expected_profit == pytest.approx(-9000)
    assert any("PÉRDIDA" in w for w in r.warnings)


# --- P1-02 · fichas listas sin precio / producto excluido --------------------------

def test_p1_02_draft_rules_block_export(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.upsert_products(conn, [Product(source="csv", source_id="A", name="Sin stock", supplier_cost_cop=25000,
                                      stock=0, shipping_cost_cop=12000)])
    pid = db.list_products(conn)[0].id
    c = cfg(use_product_shipping=True, shipping_tiers=None)
    db.upsert_draft(conn, pid, "facebook", "Título", "Desc", None)
    db.set_excluded(conn, [pid], True)
    d = db.list_drafts(conn)[0]
    d["status"] = "lista"
    blockers, _ = draft_rules.check(d, db.get_product(conn, pid), c)
    assert {"sin precio", "producto excluido del catálogo", "sin stock en Dropi"} <= set(blockers)
    assert draft_rules.expected_profit(d, db.get_product(conn, pid), c) is None  # no suma al potencial


def test_p1_02_valid_draft_profit_uses_draft_price_and_unknown_stock_warns():
    p = Product(source="csv", source_id="A", name="P", supplier_cost_cop=25000, shipping_cost_cop=12000, stock=None)
    c = cfg(use_product_shipping=True, shipping_tiers=None)
    d = {"title": "T", "price_cop": 49900, "excluded": 0, "status": "lista"}
    blockers, warns = draft_rules.check(d, p, c)
    assert not blockers and any("stock desconocido" in w for w in warns)
    assert draft_rules.expected_profit(d, p, c) == pytest.approx(49900 - 25000 - 12000)
    loss = dict(d, price_cop=30000)
    assert "el precio deja pérdida esperada" in draft_rules.check(loss, p, c)[0]


def test_p1_02_exports_mark_drafts():
    drafts = [{"title": "A", "description": "d", "price_cop": 1000, "images": [], "status": "borrador"},
              {"title": "B", "description": "d", "price_cop": 1000, "images": [], "status": "lista"}]
    csv_text = drafts_to_ml_csv(drafts).decode("utf-8-sig")
    assert csv_text.splitlines()[0].startswith("estado;") and "borrador;" in csv_text
    import io
    import zipfile
    names = zipfile.ZipFile(io.BytesIO(drafts_to_fb_zip(drafts))).namelist()
    assert any(n.startswith("BORRADOR-") for n in names) and any(n.startswith("002-") for n in names)


# --- P1-03 · atomicidad con varias sesiones ----------------------------------------

def test_p1_03_failed_batch_rolls_back_everything_with_concurrent_session(tmp_path):
    path = tmp_path / "t.db"
    conn_a = db.connect(path)
    conn_a.execute("CREATE TRIGGER boom BEFORE INSERT ON products WHEN NEW.source_id = 'BOOM' "
                   "BEGIN SELECT RAISE(ABORT, 'falla forzada'); END")
    conn_a.commit()
    batch = [Product(source="csv", source_id=f"P{i}", name=f"P{i}", supplier_cost_cop=1000) for i in range(3)]
    batch.append(Product(source="csv", source_id="BOOM", name="Boom", supplier_cost_cop=1000))
    errors = []

    def other_session():
        conn_b = db.connect(path)  # otra sesión, su propia conexión
        db.save_channel_config(conn_b, cfg())
        conn_b.close()

    t = threading.Thread(target=other_session)
    try:
        t.start()
        db.upsert_products(conn_a, batch, "lote.csv")
    except sqlite3.DatabaseError as exc:
        errors.append(exc)
    t.join()
    assert errors
    fresh = db.connect(path)
    assert fresh.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
    assert fresh.execute("SELECT COUNT(*) FROM price_history").fetchone()[0] == 0
    assert fresh.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0] == 0
    assert db.get_channel_config(fresh, "facebook").commission_pct == 0.0  # la otra sesión sí guardó


def test_p1_03_app_does_not_share_a_cached_connection():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "cache_resource" not in source and "check_same_thread=False" not in (
        ROOT / "src/pillalu/storage/db.py").read_text(encoding="utf-8")


# --- P1-04 · versión de Python ----------------------------------------------------

def test_p1_04_python_requirement_is_consistent():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    bat = (ROOT / "iniciar.bat").read_text(encoding="utf-8")
    assert "3.10" not in readme and "3.12" in readme
    assert "-3.12" in bat and "errorlevel" in bat.lower()
    assert "version_info[:2] == (3, 12)" in bat and ">= (3, 11)" not in bat  # RA-P3-01


# --- P2 / P3 -----------------------------------------------------------------------

def test_p2_01_break_even_counts_started_orders():
    assert break_even_units(40000, 4000) == 10
    assert expected_deliveries(10, 0.5) == 5
    with pytest.raises(ValueError):
        break_even_units(-1, 4000)


def test_p2_02_break_even_has_no_fractional_loss():
    c = cfg(commission_pct=0.51)
    p = solve_min_price(100, c, 0, 0)
    assert p == 205
    assert evaluate(p, 100, c).expected_profit >= 0
    assert evaluate(204, 100, c).expected_profit < 0


@pytest.mark.parametrize("url,ok", [
    ("https://cdn.example.com/a.jpg", True), ("http://example.com/a.png", True),
    ("C:\\Users\\sebas\\secreto.png", False), ("/etc/passwd", False), ("file:///etc/passwd", False),
    ("data:image/png;base64,AAAA", False), ("https://", False), ("javascript:alert(1)", False),
])
def test_p2_03_image_urls(url, ok):
    assert valid_image_url(url) is ok


def test_p2_03_mapping_rejects_local_image_paths():
    raw = [{"id": "I1", "name": "Img", "img": "C:\\Users\\sebas\\privado.png"}]
    mapping = parse_mapping({"fields": {"source_id": "id", "name": "name", "images": "img"}})
    report = file_import.read_json_text(json.dumps(raw), mapping)
    assert not report.products and "imagen" in report.rejected[0][1]


def test_p2_04_raw_rows_not_persisted_and_old_ones_purged(tmp_path):
    path = tmp_path / "t.db"
    report = file_import.read_csv_text("dropi_id;nombre;costo_proveedor;telefono_cliente\nA;P;1000;3001234567\n")
    conn = db.connect(path)
    db.upsert_products(conn, report.products)
    assert conn.execute("SELECT raw_json FROM products").fetchone()[0] is None
    # Base heredada de v0.1 con filas crudas: la migración las borra al abrir.
    conn.execute("UPDATE products SET raw_json = '{\"telefono_cliente\": \"3001234567\"}'")
    conn.execute("UPDATE meta SET value = '1' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()
    conn = db.connect(path)
    assert conn.execute("SELECT raw_json FROM products").fetchone()[0] is None


def test_p3_01_mapping_validated_in_memory():
    with pytest.raises(MappingError):
        parse_mapping({"fields": {"name": "name"}})
    with pytest.raises(MappingError):
        parse_mapping(["no es objeto"])
