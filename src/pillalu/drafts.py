"""Reglas para que una ficha pueda marcarse como lista y exportarse (auditoría P1-02).

Se aplican al guardar el estado, al exportar y al calcular la ganancia potencial, para
que catálogo, exportación y resumen digan lo mismo sobre una ficha.
"""

from __future__ import annotations

from .core.models import Product
from .core.pricing import ChannelConfig, evaluate, missing_inputs

READY_STATUSES = ("lista", "publicada_manual")


def check(draft: dict, product: Product | None, cfg: ChannelConfig) -> tuple[list[str], list[str]]:
    """Devuelve (bloqueos, avisos). Con bloqueos, la ficha no puede estar lista ni exportarse."""
    blockers: list[str] = []
    warnings: list[str] = []
    if product is None:
        return ["el producto ya no existe"], []
    price = draft.get("price_cop")
    if not draft.get("title", "").strip():
        blockers.append("sin título")
    if not price or price <= 0:
        blockers.append("sin precio")
    if draft.get("excluded"):
        blockers.append("producto excluido del catálogo")
    if product.stock == 0:
        blockers.append("sin stock en Dropi")
    elif product.stock is None:
        warnings.append("stock desconocido: confírmalo en Dropi antes de publicar")
    miss = missing_inputs(cfg, product.supplier_cost_cop, product.shipping_cost_cop)
    if miss:
        blockers.append("no se puede calcular la ganancia: " + ", ".join(miss))
    elif price and price > 0:
        b = evaluate(price, product.supplier_cost_cop, cfg, product.shipping_cost_cop)
        if b.expected_profit < 0:
            blockers.append("el precio deja pérdida esperada")
        elif b.expected_profit < cfg.min_profit_cop or b.margin < cfg.min_margin:
            warnings.append("el precio no cumple tu ganancia o margen mínimo")
    return blockers, warnings


def expected_profit(draft: dict, product: Product | None, cfg: ChannelConfig) -> float | None:
    """Ganancia esperada AL PRECIO DE LA FICHA (nunca al recomendado), o None si no aplica."""
    blockers, _ = check(draft, product, cfg)
    if blockers:
        return None
    return evaluate(draft["price_cop"], product.supplier_cost_cop, cfg, product.shipping_cost_cop).expected_profit
