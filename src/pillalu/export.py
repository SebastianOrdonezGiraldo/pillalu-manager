"""Exportación de fichas para publicación manual.

- Mercado Libre: CSV de trabajo con los datos de cada ficha. **No es** la plantilla
  oficial de carga masiva de Mercado Libre: esa plantilla se descarga desde la cuenta
  del vendedor y sus columnas dependen de la categoría, así que no se inventa aquí.
  Este CSV sirve para copiar/pegar en esa plantilla (pendiente para v0.2).
- Facebook Marketplace: un ZIP con una carpeta por producto (``anuncio.txt`` listo
  para copiar y ``fotos.txt`` con los enlaces de imágenes de Dropi). La
  publicación la hace el fundador a mano (no hay API autorizada).
"""

from __future__ import annotations

import csv
import io
import re
import zipfile

from .core.money import fmt_cop

ML_COLUMNS = ["estado", "dropi_id", "titulo", "precio_cop", "stock_proveedor", "categoria_dropi", "condicion",
              "descripcion", "imagen_1", "imagen_2", "imagen_3", "imagen_4", "imagen_5", "imagen_6"]


def _safe(value):
    """Evita que Excel interprete como fórmula un texto que empieza por = + - @ (inyección CSV)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def drafts_to_ml_csv(drafts: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")  # Excel en español usa ';'
    writer.writerow(ML_COLUMNS)
    for d in drafts:
        imgs = (d.get("images") or [])[:6]
        writer.writerow([_safe(v) for v in (
            d.get("status", ""), d.get("source_id", ""), d["title"], d.get("price_cop") or "", d.get("stock") if d.get("stock") is not None else "",
            d.get("category") or "", "Nuevo", d["description"], *imgs, *[""] * (6 - len(imgs)),
        )])
    return buf.getvalue().encode("utf-8-sig")  # BOM para que Excel lea las tildes


def _slug(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_]+", "-", text)[:50] or "producto"


def ad_text(d: dict) -> str:
    return f"{d['title']}\n\nPrecio: {fmt_cop(d.get('price_cop'))}\n\n{d['description']}\n"


def drafts_to_fb_zip(drafts: list[dict]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, d in enumerate(drafts, start=1):
            prefix = "" if d.get("status") in ("lista", "publicada_manual") else "BORRADOR-"
            folder = f"{prefix}{i:03d}-{_slug(d['title'])}"
            zf.writestr(f"{folder}/anuncio.txt", ad_text(d))
            zf.writestr(f"{folder}/fotos.txt", "\n".join(d.get("images") or []) + "\n")
        zf.writestr(
            "LEEME.txt",
            "Paquetes para publicar a mano en Facebook Marketplace.\n"
            "1. Abre la carpeta del producto.\n2. Copia título, precio y descripción de anuncio.txt.\n"
            "3. Descarga las fotos de los enlaces de fotos.txt (imágenes del proveedor en Dropi).\n"
            "4. Publica desde tu cuenta y marca la ficha como 'Publicada (manual)' en Pillalú.\n",
        )
    return buf.getvalue()
