"""Importación manual de productos desde un CSV propio (plan de contingencia).

Sirve mientras no haya acceso programático confirmado a los datos de Dropi:
el fundador copia del panel de Dropi los datos de los productos que le
interesan a una hoja de cálculo con estas columnas. No es scraping: es
información que el usuario consulta con su propia cuenta.

Columnas (``samples/plantilla_productos.csv``)::

    dropi_id, nombre, costo_proveedor, precio_sugerido, stock, categoria,
    proveedor_id, proveedor, imagenes, peso_g, descripcion, tiene_variantes

``imagenes`` admite varias URLs separadas por ``|``.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..models import Product
from .mapping import _to_int

COLUMNS = (
    "dropi_id",
    "nombre",
    "costo_proveedor",
    "precio_sugerido",
    "stock",
    "categoria",
    "proveedor_id",
    "proveedor",
    "imagenes",
    "peso_g",
    "descripcion",
    "tiene_variantes",
)

_TRUE = {"si", "sí", "true", "1", "x", "yes"}


def read_csv(path: str | Path) -> list[Product]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        reader = csv.DictReader(fh, dialect=dialect)
        missing = {"dropi_id", "nombre"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Faltan columnas obligatorias: {sorted(missing)}")
        products = []
        for row in reader:
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            if not row.get("dropi_id") and not row.get("nombre"):
                continue
            products.append(
                Product(
                    source="csv",
                    source_id=row.get("dropi_id", ""),
                    name=row.get("nombre", ""),
                    supplier_cost_cop=_to_int(row.get("costo_proveedor")),
                    suggested_price_cop=_to_int(row.get("precio_sugerido")),
                    stock=_to_int(row.get("stock")),
                    category=row.get("categoria") or None,
                    supplier_id=row.get("proveedor_id") or None,
                    supplier_name=row.get("proveedor") or None,
                    images=[u.strip() for u in row.get("imagenes", "").split("|") if u.strip()],
                    weight_g=_to_int(row.get("peso_g")),
                    description=row.get("descripcion") or None,
                    has_variants=row.get("tiene_variantes", "").lower() in _TRUE,
                )
            )
    return products
