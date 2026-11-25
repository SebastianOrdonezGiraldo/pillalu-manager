"""Modelos de datos (sin dependencias externas). Montos en COP enteros; ``None`` = desconocido."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CHANNELS = ("mercadolibre", "facebook")
CHANNEL_LABELS = {"mercadolibre": "Mercado Libre", "facebook": "Facebook Marketplace"}


@dataclass
class Product:
    """Producto normalizado, venga de Dropi (MCP), de un CSV o de un JSON."""

    source: str  # "dropi_mcp" | "csv" | "json" | "manual"
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
    shipping_cost_cop: int | None = None  # cotización de flete Dropi para este producto, si existe
    description: str | None = None
    has_variants: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    id: int | None = None  # asignado por la base de datos

    def problems(self) -> list[str]:
        """Datos que faltan o son inválidos para valorar el producto."""
        out = []
        if not self.name:
            out.append("sin nombre")
        if self.supplier_cost_cop is None:
            out.append("sin costo de proveedor")
        elif self.supplier_cost_cop <= 0:
            out.append("costo de proveedor inválido")
        if self.stock is not None and self.stock < 0:
            out.append("stock negativo")
        return out

    def to_dict(self, include_raw: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_raw:
            data.pop("raw", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Product":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})
