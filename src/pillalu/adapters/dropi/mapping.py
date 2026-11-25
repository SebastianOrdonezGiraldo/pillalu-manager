"""Normalización de respuestas del MCP de Dropi a ``Product``.

Importante: los nombres de campos que devuelve el MCP de Dropi **no están
documentados públicamente** (ver docs/FEASIBILITY.md §1.2). Por eso este módulo
NO asume nombres: trabaja con un archivo de mapeo (JSON) que se completa
después de ver una respuesta real del MCP (ver docs/DROPI.md).

Origen: borrador de la rama ``feature/market-intelligence`` (commit 4022207),
reutilizado y corregido (parseo de montos con coma de miles).

``suggest_mapping`` propone un mapeo a partir de una respuesta real comparando
nombres de claves; cada sugerencia debe confirmarse a mano.

Formato del mapeo::

    {
      "items_path": "data.products",          # dónde está la lista de productos
      "fields": {
        "source_id": "id",
        "name": "name",
        "supplier_cost_cop": "sale_price",
        "images": "gallery[].url",              # [] recorre listas
        ...
      }
    }
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from ...core.models import Product
from ...core.money import parse_cop

MAPPABLE_FIELDS = (
    "source_id",
    "name",
    "supplier_cost_cop",
    "suggested_price_cop",
    "stock",
    "category",
    "supplier_id",
    "supplier_name",
    "images",
    "weight_g",
    "shipping_cost_cop",
    "description",
    "has_variants",
)

INT_FIELDS = {"supplier_cost_cop", "suggested_price_cop", "stock", "weight_g", "shipping_cost_cop"}

# Palabras clave para *sugerir* (no asumir) qué clave real corresponde a cada campo.
_HINTS: dict[str, tuple[str, ...]] = {
    "source_id": ("id", "product_id", "sku"),
    "name": ("name", "nombre", "title", "titulo"),
    "supplier_cost_cop": ("sale_price", "precio_proveedor", "price", "precio", "cost", "costo"),
    "suggested_price_cop": ("suggested", "sugerido", "retail"),
    "stock": ("stock", "inventory", "inventario", "quantity", "cantidad"),
    "category": ("category", "categoria"),
    "supplier_id": ("supplier_id", "user_id", "proveedor_id", "provider_id"),
    "supplier_name": ("supplier", "proveedor", "provider", "store", "tienda"),
    "images": ("image", "imagen", "gallery", "photo", "foto", "url"),
    "weight_g": ("weight", "peso"),
    "shipping_cost_cop": ("shipping_cost", "flete", "envio"),
    "description": ("description", "descripcion"),
    "has_variants": ("variation", "variacion", "variant"),
}


class MappingError(ValueError):
    pass


def resolve(obj: Any, path: str) -> Any:
    """Resuelve rutas tipo ``a.b``, ``a[0].b`` y ``a[].b`` (todas las posiciones)."""
    if not path:
        return obj
    head, _, rest = path.partition(".")
    m = re.fullmatch(r"([^\[\]]*)(\[(\d*)\])?", head)
    if not m:
        raise MappingError(f"Ruta inválida: {path!r}")
    key, has_index, index = m.group(1), m.group(2), m.group(3)
    current = obj
    if key:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    if has_index is not None:
        if not isinstance(current, list):
            return None
        if index == "":
            values = [resolve(item, rest) for item in current]
            flat: list[Any] = []
            for v in values:
                if isinstance(v, list):
                    flat.extend(v)
                elif v is not None:
                    flat.append(v)
            return flat
        i = int(index)
        current = current[i] if i < len(current) else None
    return resolve(current, rest) if rest else current


def load_mapping(path: str | Path) -> dict[str, Any]:
    return parse_mapping(json.loads(Path(path).read_text(encoding="utf-8")))


def parse_mapping(mapping: Any) -> dict[str, Any]:
    """Valida un mapeo ya cargado en memoria (sin archivos temporales — auditoría P3-01)."""
    if not isinstance(mapping, dict) or not isinstance(mapping.get("fields", {}), dict):
        raise MappingError("El mapeo debe ser un objeto JSON con 'fields'.")
    fields = mapping.get("fields", {})
    unknown = set(fields) - set(MAPPABLE_FIELDS)
    if unknown:
        raise MappingError(f"Campos desconocidos en el mapeo: {sorted(unknown)}")
    for required in ("source_id", "name"):
        if not fields.get(required):
            raise MappingError(f"El mapeo debe indicar la ruta de '{required}'")
    return mapping


def normalize(raw: Any, mapping: dict[str, Any]) -> list[Product]:
    """Convierte una respuesta cruda del MCP en productos normalizados."""
    items = resolve(raw, mapping.get("items_path", "")) if mapping.get("items_path") else raw
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        raise MappingError("La ruta 'items_path' no apunta a una lista de productos")
    products: list[Product] = []
    for item in items:
        values: dict[str, Any] = {}
        for field_name, path in mapping["fields"].items():
            if not path:
                continue
            value = resolve(item, path)
            if field_name in INT_FIELDS:
                value = parse_cop(value)
            elif field_name == "images":
                if isinstance(value, str):
                    value = [value]
                value = [str(v) for v in (value or []) if v]
            elif field_name == "has_variants":
                value = None if value is None else bool(value)
            elif value is not None:
                value = str(value)
            values[field_name] = value
        products.append(
            Product(
                source="dropi_mcp",
                source_id=values.pop("source_id") or "",
                name=values.pop("name") or "",
                **{k: v for k, v in values.items() if v is not None},
            )
        )
    return products


def _walk_keys(obj: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            yield p, v
            yield from _walk_keys(v, p)
    elif isinstance(obj, list) and obj:
        p = f"{prefix}[]"
        yield from _walk_keys(obj[0], p)


def suggest_mapping(raw: Any) -> dict[str, Any]:
    """Sugiere un mapeo a partir de una respuesta real. **Debe revisarse a mano.**"""
    # 1) Buscar la lista de productos más grande con objetos dentro.
    best_path, best_len = "", -1
    if isinstance(raw, list):
        best_path, best_len = "", len(raw)
    for path, value in _walk_keys(raw):
        if isinstance(value, list) and value and isinstance(value[0], dict) and "[]" not in path:
            if len(value) > best_len:
                best_path, best_len = path, len(value)
    items = resolve(raw, best_path) if best_path else raw
    sample = items[0] if isinstance(items, list) and items else items
    keys = [p for p, v in _walk_keys(sample) if not isinstance(v, dict)]

    fields: dict[str, str | None] = {}
    for field_name, hints in _HINTS.items():
        match = None
        for hint in hints:
            for key in keys:
                leaf = key.split(".")[-1].replace("[]", "").lower()
                if leaf == hint or (len(hint) > 3 and hint in leaf):
                    match = key
                    break
            if match:
                break
        fields[field_name] = match
    return {
        "_aviso": "Sugerencia automática por nombre de claves. Confirmar cada ruta antes de usar.",
        "items_path": best_path,
        "fields": fields,
        "_claves_disponibles": keys,
    }
