"""Modelos de datos compartidos (sin dependencias externas).

Todos los montos están en pesos colombianos (COP) enteros.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Campos mínimos para poder valorar un producto.
REQUIRED_FOR_SCORING = ("name", "supplier_cost_cop", "stock", "images")


@dataclass
class Product:
    """Producto normalizado, venga de Dropi (MCP) o de un CSV."""

    source: str  # "dropi_mcp" | "csv"
    source_id: str
    name: str
    supplier_cost_cop: int | None = None
    suggested_price_cop: int | None = None
    stock: int | None = None
    category: str | None = None
    supplier_id: str | None = None
    supplier_name: str | None = None
    images: list[str] = field(default_factory=list)
    weight_g: int | None = None
    description: str | None = None
    has_variants: bool = False
    # Respuesta original, para auditoría. No se exporta a CSV.
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def missing_fields(self) -> list[str]:
        missing = []
        for name in REQUIRED_FOR_SCORING:
            value = getattr(self, name)
            if value is None or value == "" or value == []:
                missing.append(name)
        return missing

    def to_dict(self, include_raw: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_raw:
            data.pop("raw", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Product":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class MarketSignals:
    """Señales de Mercado Libre para un producto. ``None`` = desconocido."""

    category_id: str | None = None
    domain_id: str | None = None
    trend_keyword: str | None = None  # palabra de /trends que coincide con el producto
    catalog_matches: int | None = None  # resultados en /products/search
    fee_pct: float | None = None  # 0.0–1.0, de /sites/MCO/listing_prices
    fixed_fee_cop: int | None = None
    max_title_length: int | None = None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MarketSignals":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})
