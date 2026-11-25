"""Modelos de datos (sin dependencias externas). Montos en COP enteros; ``None`` = desconocido."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse

CHANNELS = ("mercadolibre", "facebook")
CHANNEL_LABELS = {"mercadolibre": "Mercado Libre", "facebook": "Facebook Marketplace"}

AMOUNT_FIELDS = {
    "suggested_price_cop": "precio sugerido",
    "stock": "stock",
    "weight_g": "peso",
    "shipping_cost_cop": "flete Dropi",
}


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def valid_image_url(url) -> bool:
    """Solo URLs http(s) con dominio. Rechaza rutas locales, file:, data: y otros esquemas
    (auditoría P2-03: Streamlit abriría una ruta local como imagen)."""
    if not isinstance(url, str) or len(url) > 2048:
        return False
    try:
        parsed = urlparse(url.strip())
        host = parsed.hostname  # valida también el host (p. ej. "[" sin cerrar)
    except ValueError:  # URL mal formada: inválida, nunca una excepción (RA-P2-01)
        return False
    return parsed.scheme in ("http", "https") and bool(host) and " " not in url.strip()


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
    has_variants: bool | None = None  # None = el archivo no lo indica
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    # Valores del origen que no se pudieron interpretar (no se guardan; bloquean el producto).
    parse_errors: list[str] = field(default_factory=list, repr=False)
    id: int | None = None  # asignado por la base de datos

    def invalid_values(self) -> list[str]:
        """Errores que impiden guardar el producto. Regla única para TODAS las entradas
        (CSV, JSON, mapeo del MCP, formulario manual y base de datos) — auditoría P0-02.
        Un dato vacío (desconocido) no es error; un dato con valor inválido sí."""
        out = list(self.parse_errors)
        if not (self.name or "").strip():
            out.append("sin nombre")
        if not (self.source_id or "").strip():
            out.append("sin identificador (dropi_id/sku)")
        if self.supplier_cost_cop is not None and not (_finite(self.supplier_cost_cop) and self.supplier_cost_cop > 0):
            out.append("costo de proveedor inválido (debe ser mayor que 0)")
        for attr, label in AMOUNT_FIELDS.items():
            v = getattr(self, attr)
            if v is not None and not (_finite(v) and v >= 0):
                out.append(f"{label} inválido (negativo)")
        bad = [u for u in self.images if not valid_image_url(u)]
        if bad:
            out.append(f"imagen con dirección no permitida (solo http/https): {bad[0][:80]}")
        return out

    def problems(self) -> list[str]:
        """Datos que faltan o son inválidos para valorar el producto."""
        out = self.invalid_values()
        if self.supplier_cost_cop is None:
            out.append("sin costo de proveedor")
        return out

    def to_dict(self, include_raw: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_raw:
            data.pop("raw", None)
            data.pop("parse_errors", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Product":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})
