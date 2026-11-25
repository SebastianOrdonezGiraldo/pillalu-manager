"""Importación de productos desde CSV o JSON (alternativa mientras no haya API de Dropi).

Fuentes válidas (todas autorizadas, sin scraping):
- Una hoja de cálculo que el fundador llena con datos de su propia cuenta de Dropi
  (plantilla: ``samples/plantilla_productos.csv``).
- Un JSON exportado desde una conversación con el MCP oficial de Dropi conectado
  en Claude (ver docs/DROPI.md), ya sea con nuestras columnas o con la respuesta
  cruda del MCP más un archivo de mapeo (``mapping.py``).

Los encabezados se reconocen con alias en español e inglés, sin importar
mayúsculas ni tildes. Cada fila inválida se rechaza con su motivo; nunca se
rellenan datos inventados.
"""

from __future__ import annotations

import csv
import io
import json
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from ...core.models import Product
from ...core.money import parse_cop

ALIASES: dict[str, tuple[str, ...]] = {
    "source_id": ("dropi_id", "id", "id_producto", "product_id", "sku", "codigo", "referencia"),
    "name": ("nombre", "name", "titulo", "title", "producto"),
    "supplier_cost_cop": (
        "costo_proveedor", "precio_proveedor", "costo", "precio_dropshipper", "sale_price", "cost", "supplier_cost",
    ),
    "suggested_price_cop": ("precio_sugerido", "suggested_price", "precio_venta_sugerido", "pvp"),
    "stock": ("stock", "inventario", "existencias", "cantidad", "quantity"),
    "category": ("categoria", "category"),
    "supplier_id": ("proveedor_id", "supplier_id", "id_proveedor"),
    "supplier_name": ("proveedor", "supplier", "supplier_name", "bodega"),
    "images": ("imagenes", "images", "fotos", "imagen", "image", "url_imagen"),
    "weight_g": ("peso_g", "peso", "weight", "weight_g"),
    "shipping_cost_cop": ("costo_envio", "flete", "shipping_cost", "envio"),
    "description": ("descripcion", "description", "detalle"),
    "has_variants": ("tiene_variantes", "variantes", "has_variants"),
}

TRUE_VALUES = {"si", "sí", "true", "1", "x", "yes", "y"}
INT_FIELDS = {"supplier_cost_cop", "suggested_price_cop", "stock", "weight_g", "shipping_cost_cop"}


def _norm(key: str) -> str:
    key = unicodedata.normalize("NFKD", str(key)).encode("ascii", "ignore").decode()
    return key.strip().lower().replace(" ", "_").replace("-", "_")


_LOOKUP = {alias: canonical for canonical, aliases in ALIASES.items() for alias in aliases}


@dataclass
class ImportReport:
    products: list[Product] = field(default_factory=list)
    rejected: list[tuple[int, str]] = field(default_factory=list)  # (fila, motivo)
    unknown_columns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _images(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        text = str(value).strip()
        if text.startswith("["):
            try:
                items = json.loads(text)
            except json.JSONDecodeError:
                items = [text]
        else:
            items = text.replace(";", "|").replace(",", "|").split("|") if "http" in text else []
    out = []
    for item in items:
        url = item.get("url") if isinstance(item, dict) else item
        url = str(url or "").strip()
        if url.startswith(("http://", "https://")) and url not in out:
            out.append(url)
    return out


def row_to_product(row: dict[str, Any], source: str, line: int, report: ImportReport) -> Product | None:
    data: dict[str, Any] = {}
    for key, value in row.items():
        if key is None:
            continue
        canonical = _LOOKUP.get(_norm(key))
        if canonical and canonical not in data:
            data[canonical] = value.strip() if isinstance(value, str) else value
    if not any(v not in (None, "") for v in data.values()):
        return None  # fila vacía

    values: dict[str, Any] = {}
    for f, v in data.items():
        if f in INT_FIELDS:
            parsed = parse_cop(v)
            if v not in (None, "") and parsed is None:
                report.rejected.append((line, f"valor no numérico en '{ALIASES[f][0]}': {v!r}"))
                return None
            values[f] = parsed
        elif f == "images":
            values[f] = _images(v)
        elif f == "has_variants":
            values[f] = str(v).strip().lower() in TRUE_VALUES if not isinstance(v, bool) else v
        else:
            values[f] = str(v).strip() if v not in (None, "") else None

    name = values.pop("name", None) or ""
    source_id = values.pop("source_id", None) or ""
    product = Product(source=source, source_id=source_id, name=name, raw=dict(row), **values)
    if not name:
        report.rejected.append((line, "sin nombre"))
        return None
    if not source_id:
        report.rejected.append((line, f"'{name}': sin identificador (dropi_id/sku)"))
        return None
    if product.supplier_cost_cop is not None and product.supplier_cost_cop <= 0:
        report.rejected.append((line, f"'{name}': costo de proveedor inválido"))
        return None
    if product.supplier_cost_cop is None:
        report.warnings.append(f"Fila {line} '{name}': sin costo de proveedor; se importa pero no se puede valorar.")
    return product


def _unknown(headers: list[str]) -> list[str]:
    return [h for h in headers if h and _norm(h) not in _LOOKUP]


def read_csv_text(text: str) -> ImportReport:
    report = ImportReport()
    text = text.lstrip("﻿")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = reader.fieldnames or []
    canon = {_LOOKUP.get(_norm(h)) for h in headers}
    if "name" not in canon:
        raise ValueError("El archivo no tiene columna de nombre (nombre/name/titulo).")
    report.unknown_columns = _unknown(headers)
    for i, row in enumerate(reader, start=2):
        p = row_to_product(row, "csv", i, report)
        if p:
            report.products.append(p)
    return report


def read_json_text(text: str, mapping: dict | None = None) -> ImportReport:
    """JSON con lista de productos (nuestras columnas o alias) o respuesta cruda del MCP + mapeo."""
    raw = json.loads(text)
    if mapping:
        from .mapping import normalize

        report = ImportReport()
        for i, p in enumerate(normalize(raw, mapping), start=1):
            if not p.name or not p.source_id:
                report.rejected.append((i, "sin nombre o identificador tras aplicar el mapeo"))
            else:
                report.products.append(p)
        return report

    items = raw
    if isinstance(raw, dict):
        lists = [v for v in raw.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
        items = raw.get("productos") or raw.get("products") or (lists[0] if len(lists) == 1 else None)
    if not isinstance(items, list):
        raise ValueError(
            "No encontré una lista de productos. Usa una lista JSON o {\"productos\": [...]}; "
            "para respuestas crudas del MCP de Dropi, carga también un archivo de mapeo."
        )
    report = ImportReport()
    headers: list[str] = []
    for item in items:
        if isinstance(item, dict):
            headers += [k for k in item if k not in headers]
    if "name" not in {_LOOKUP.get(_norm(h)) for h in headers}:
        raise ValueError("Los productos no tienen campo de nombre reconocible; usa un archivo de mapeo.")
    report.unknown_columns = _unknown(headers)
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            report.rejected.append((i, "elemento no es un objeto"))
            continue
        p = row_to_product(item, "json", i, report)
        if p:
            report.products.append(p)
    return report


def read_file(filename: str, content: bytes, mapping: dict | None = None) -> ImportReport:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")  # Excel en Windows suele guardar CSV en ANSI
    if filename.lower().endswith(".json"):
        return read_json_text(text, mapping)
    return read_csv_text(text)


TEMPLATE_HEADERS = [
    "dropi_id", "nombre", "costo_proveedor", "precio_sugerido", "stock", "categoria", "proveedor_id",
    "proveedor", "imagenes", "peso_g", "costo_envio", "descripcion", "tiene_variantes",
]
