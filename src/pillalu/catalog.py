"""Une catálogo + motor de rentabilidad: una fila por producto con métricas por canal."""

from __future__ import annotations

from dataclasses import dataclass

from .core.models import CHANNELS, Product
from .core.pricing import ChannelConfig, ProfitResult, analyze


@dataclass
class CatalogRow:
    product: Product
    results: dict[str, ProfitResult]
    excluded: bool = False

    def best_channel(self) -> str | None:
        best, best_profit = None, None
        for ch, r in self.results.items():
            b = r.selling
            if b and (best_profit is None or b.expected_profit > best_profit):
                best, best_profit = ch, b.expected_profit
        return best


def analyze_product(p: Product, configs: dict[str, ChannelConfig],
                    custom: dict[tuple[int, str], int] | None = None) -> dict[str, ProfitResult]:
    custom = custom or {}
    return {
        ch: analyze(
            p.supplier_cost_cop,
            configs[ch],
            product_shipping=p.shipping_cost_cop,
            suggested_price=p.suggested_price_cop,
            custom_price=custom.get((p.id, ch)) if p.id is not None else None,
        )
        for ch in CHANNELS
    }


def build_rows(products: list[Product], configs: dict[str, ChannelConfig],
               custom: dict[tuple[int, str], int] | None = None,
               excluded: set[int] | None = None) -> list[CatalogRow]:
    excluded = excluded or set()
    return [CatalogRow(p, analyze_product(p, configs, custom), p.id in excluded) for p in products]


def to_records(rows: list[CatalogRow]) -> list[dict]:
    """Registros planos para la tabla de la interfaz (montos en COP)."""
    out = []
    for row in rows:
        p = row.product
        rec = {
            "id": p.id,
            "dropi_id": p.source_id,
            "producto": p.name,
            "categoria": p.category or "",
            "proveedor": p.supplier_name or "",
            "stock": p.stock,
            "costo": p.supplier_cost_cop,
            "sugerido_dropi": p.suggested_price_cop,
            "fotos": len(p.images),
            "excluido": row.excluded,
        }
        for ch, prefix in (("mercadolibre", "ml"), ("facebook", "fb")):
            r = row.results[ch]
            b = r.selling
            rec[f"{prefix}_precio"] = b.price if b else None
            rec[f"{prefix}_ganancia"] = round(b.expected_profit) if b else None
            rec[f"{prefix}_margen"] = round(b.margin * 100, 1) if b else None
            rec[f"{prefix}_minimo"] = r.min_profitable_price
            rec[f"{prefix}_completo"] = r.complete
        best = row.best_channel()
        rec["mejor_canal"] = {"mercadolibre": "ML", "facebook": "FB"}.get(best or "", "")
        profits = [rec["ml_ganancia"], rec["fb_ganancia"]]
        known = [x for x in profits if x is not None]
        rec["mejor_ganancia"] = max(known) if known else None
        out.append(rec)
    return out
