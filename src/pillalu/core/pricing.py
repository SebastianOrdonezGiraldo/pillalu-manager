"""Motor de rentabilidad por canal.

Principio: **un costo desconocido nunca vale cero**. Si falta un parámetro, el
resultado queda incompleto y se listan los datos que faltan. El fundador puede
escribir 0 de forma explícita cuando un costo realmente no existe.

Modelo por pedido (todos los montos en COP):

    cargos(P)          = comisión_% · P + cargo_fijo(P) + otros_% · P
    ganancia_entregado = P − costo_proveedor − cargos(P) − envío(P) − empaque
    ganancia_esperada  = (1 − tasa_dev) · ganancia_entregado − tasa_dev · costo_por_devolución
    pérdida_por_dev    = ganancia_entregado − ganancia_esperada
    margen             = ganancia_esperada / P

En una devolución se asume que el producto vuelve al proveedor (no se paga su
costo), no se cobra la venta y se pierde ``costo_por_devolución`` (p. ej. flete de
ida y vuelta). Ese costo lo define el fundador por canal.

Mercado Libre: ``comisión_%`` y ``cargo_fijo`` deben venir de
``/sites/MCO/listing_prices`` (``sale_fee_amount`` ya incluye el ``fixed_fee``;
no restar dos veces). Mientras no exista la integración (Fase 3), los ingresa el
fundador a mano desde la calculadora oficial de Mercado Libre.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from .money import round_commercial

# Tramo: (precio_hasta_inclusive | None = sin límite, valor_cop)
Tier = tuple[int | None, int]


def tier_value(tiers: list[Tier], price: float) -> int:
    """Valor del primer tramo cuyo límite cubre el precio. Lista vacía = 0 (explícito)."""
    for upto, value in sorted(tiers, key=lambda t: math.inf if t[0] is None else t[0]):
        if upto is None or price <= upto:
            return value
    return 0  # por encima del último límite y sin tramo abierto: no aplica


def parse_tiers(text: str) -> list[Tier]:
    """Convierte líneas ``hasta 60000: 3000`` / ``resto: 0`` en tramos.

    Una sola cifra (``3000``) significa el mismo valor para cualquier precio.
    Lanza ``ValueError`` con un mensaje en español si una línea no es válida.
    """
    from .money import parse_cop

    tiers: list[Tier] = []
    for raw_line in text.strip().splitlines():
        line = raw_line.strip().lower()
        if not line:
            continue
        if ":" in line:
            left, right = line.split(":", 1)
            value = parse_cop(right)
            left = left.replace("hasta", "").strip()
            upto = None if left in ("resto", "", "*", "mas", "más") else parse_cop(left)
            if value is None or (upto is None and left not in ("resto", "", "*", "mas", "más")):
                raise ValueError(f"Línea no válida: '{raw_line}'")
        else:
            value = parse_cop(line)
            upto = None
            if value is None:
                raise ValueError(f"Línea no válida: '{raw_line}'")
        tiers.append((upto, value))
    return tiers


def format_tiers(tiers: list[Tier] | None) -> str:
    if tiers is None:
        return ""
    if len(tiers) == 1 and tiers[0][0] is None:
        return str(tiers[0][1])
    return "\n".join(
        f"resto: {v}" if u is None else f"hasta {u}: {v}"
        for u, v in sorted(tiers, key=lambda t: math.inf if t[0] is None else t[0])
    )


@dataclass
class ChannelConfig:
    """Parámetros de costo de un canal. ``None`` = desconocido (bloquea el cálculo)."""

    channel: str
    commission_pct: float | None = None  # comisión porcentual del canal sobre el precio
    fixed_fee_tiers: list[Tier] | None = None  # cargo fijo por venta según precio
    other_pct: float | None = None  # retenciones / impuestos / recaudo, % sobre el precio
    shipping_tiers: list[Tier] | None = None  # envío que paga el vendedor según precio
    use_product_shipping: bool = False  # usar la cotización de flete Dropi del producto
    packaging_cop: int | None = None  # empaque u otros costos fijos por pedido
    return_rate: float | None = None  # fracción de pedidos devueltos/rechazados
    return_cost_cop: int | None = None  # pérdida por cada devolución
    target_margin: float = 0.25  # margen objetivo para el precio recomendado
    min_margin: float = 0.10  # margen mínimo aceptable
    min_profit_cop: int = 5000  # ganancia mínima aceptable por pedido
    title_max_len: int = 60

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelConfig":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in known}
        for key in ("fixed_fee_tiers", "shipping_tiers"):
            if clean.get(key) is not None:
                clean[key] = [(None if u is None else int(u), int(v)) for u, v in clean[key]]
        return cls(**clean)


FIELD_LABELS = {
    "commission_pct": "comisión del canal (%)",
    "fixed_fee_tiers": "cargo fijo por venta",
    "other_pct": "retenciones/otros (%)",
    "shipping_tiers": "costo de envío",
    "packaging_cop": "empaque/otros por pedido",
    "return_rate": "tasa de devolución",
    "return_cost_cop": "costo por devolución",
}


@dataclass
class Breakdown:
    """Desglose de rentabilidad para un precio dado."""

    price: int
    supplier_cost: int
    commission: float
    fixed_fee: int
    other: float
    shipping: int
    packaging: int
    profit_if_delivered: float
    expected_return_loss: float
    expected_profit: float
    margin: float


@dataclass
class ProfitResult:
    """Resultado completo de un producto en un canal."""

    channel: str
    missing: list[str] = field(default_factory=list)
    recommended_price: int | None = None
    min_profitable_price: int | None = None
    break_even_price: int | None = None
    at_recommended: Breakdown | None = None
    at_suggested: Breakdown | None = None  # al precio sugerido por Dropi, si existe
    at_custom: Breakdown | None = None  # al precio elegido por el fundador, si existe
    warnings: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def selling(self) -> Breakdown | None:
        """Desglose al precio con el que se piensa vender (elegido > recomendado)."""
        return self.at_custom or self.at_recommended


def missing_inputs(cfg: ChannelConfig, supplier_cost: int | None, product_shipping: int | None) -> list[str]:
    missing = []
    if supplier_cost is None or supplier_cost <= 0:
        missing.append("costo del proveedor")
    for key in ("commission_pct", "fixed_fee_tiers", "other_pct", "packaging_cop", "return_rate", "return_cost_cop"):
        if getattr(cfg, key) is None:
            missing.append(FIELD_LABELS[key])
    if cfg.use_product_shipping:
        if product_shipping is None and cfg.shipping_tiers is None:
            missing.append("flete Dropi del producto (o envío del canal)")
    elif cfg.shipping_tiers is None:
        missing.append(FIELD_LABELS["shipping_tiers"])
    return missing


def _shipping(cfg: ChannelConfig, price: float, product_shipping: int | None) -> int:
    if cfg.use_product_shipping and product_shipping is not None:
        return product_shipping
    return tier_value(cfg.shipping_tiers or [], price)


def evaluate(price: int, supplier_cost: int, cfg: ChannelConfig, product_shipping: int | None = None) -> Breakdown:
    """Desglose a un precio. Requiere configuración completa (ver ``missing_inputs``)."""
    assert cfg.commission_pct is not None and cfg.other_pct is not None
    assert cfg.return_rate is not None and cfg.return_cost_cop is not None and cfg.packaging_cop is not None
    commission = cfg.commission_pct * price
    fixed = tier_value(cfg.fixed_fee_tiers or [], price)
    other = cfg.other_pct * price
    shipping = _shipping(cfg, price, product_shipping)
    delivered = price - supplier_cost - commission - fixed - other - shipping - cfg.packaging_cop
    r = cfg.return_rate
    expected = (1 - r) * delivered - r * cfg.return_cost_cop
    return Breakdown(
        price=int(price),
        supplier_cost=supplier_cost,
        commission=commission,
        fixed_fee=fixed,
        other=other,
        shipping=shipping,
        packaging=cfg.packaging_cop,
        profit_if_delivered=delivered,
        expected_return_loss=delivered - expected,
        expected_profit=expected,
        margin=expected / price if price else 0.0,
    )


def _meets(b: Breakdown, min_profit: float, min_margin: float) -> bool:
    # Tolerancia de 0,5 COP por redondeo.
    return b.expected_profit + 0.5 >= min_profit and b.expected_profit + 0.5 >= min_margin * b.price


def solve_min_price(
    supplier_cost: int,
    cfg: ChannelConfig,
    min_profit: float,
    min_margin: float,
    product_shipping: int | None = None,
) -> int | None:
    """Precio entero mínimo con ganancia esperada ≥ ``min_profit`` y margen ≥ ``min_margin``.

    La ganancia es lineal en el precio dentro de cada tramo de cargos/envío, así que
    se resuelve por tramos de forma exacta. Devuelve ``None`` si es imposible
    (p. ej. comisiones + margen ≥ 100 %).
    """
    r = cfg.return_rate or 0.0
    pct = (cfg.commission_pct or 0.0) + (cfg.other_pct or 0.0)
    bounds = sorted(
        {u for u, _ in (cfg.fixed_fee_tiers or []) if u is not None}
        | ({u for u, _ in (cfg.shipping_tiers or []) if u is not None} if not (cfg.use_product_shipping and product_shipping is not None) else set())
    )
    segments: list[tuple[int, float]] = []
    lo = 1
    for b in bounds:
        if b >= lo:
            segments.append((lo, b))
            lo = b + 1
    segments.append((lo, math.inf))

    for seg_lo, seg_hi in segments:
        fixed = tier_value(cfg.fixed_fee_tiers or [], seg_lo)
        ship = _shipping(cfg, seg_lo, product_shipping)
        k = supplier_cost + fixed + ship + (cfg.packaging_cop or 0)
        base = (1 - r) * k + r * (cfg.return_cost_cop or 0)
        # Condición A: (1-r)(1-pct)P − base ≥ min_profit
        # Condición B: ((1-r)(1-pct) − m)P ≥ base
        coef_a = (1 - r) * (1 - pct)
        coef_b = coef_a - min_margin
        if coef_a <= 0 or coef_b <= 0:
            return None
        p = max((min_profit + base) / coef_a, base / coef_b, seg_lo)
        p = math.ceil(p - 1e-9)
        if p <= seg_hi:
            # Verificación exacta (protege contra errores de redondeo).
            while p <= seg_hi and not _meets(evaluate(p, supplier_cost, cfg, product_shipping), min_profit, min_margin):
                p += 1
            while p - 1 >= seg_lo and _meets(evaluate(p - 1, supplier_cost, cfg, product_shipping), min_profit, min_margin):
                p -= 1
            if p <= seg_hi:
                return int(p)
    return None


def analyze(
    supplier_cost: int | None,
    cfg: ChannelConfig,
    product_shipping: int | None = None,
    suggested_price: int | None = None,
    custom_price: int | None = None,
) -> ProfitResult:
    """Calcula precio recomendado, mínimo rentable, de equilibrio y desgloses."""
    result = ProfitResult(channel=cfg.channel)
    result.missing = missing_inputs(cfg, supplier_cost, product_shipping)
    if result.missing:
        return result
    assert supplier_cost is not None

    result.break_even_price = solve_min_price(supplier_cost, cfg, 0, 0, product_shipping)
    result.min_profitable_price = solve_min_price(
        supplier_cost, cfg, cfg.min_profit_cop, cfg.min_margin, product_shipping
    )
    exact = solve_min_price(supplier_cost, cfg, cfg.min_profit_cop, cfg.target_margin, product_shipping)
    if exact is None:
        result.warnings.append("No existe un precio que cumpla el margen objetivo con estos costos.")
    else:
        rec = round_commercial(exact)
        # Subir de a 1.000 si el redondeo cae en un tramo con más cargos.
        for _ in range(50):
            if _meets(evaluate(rec, supplier_cost, cfg, product_shipping), cfg.min_profit_cop, cfg.target_margin):
                break
            rec += 1000
        else:
            # Ningún precio redondeado cercano cumple: se usa el precio exacto, que sí cumple.
            rec = exact
            result.warnings.append("El precio recomendado no se pudo redondear a …900 sin perder margen.")
        result.recommended_price = rec
        result.at_recommended = evaluate(rec, supplier_cost, cfg, product_shipping)

    if suggested_price:
        result.at_suggested = evaluate(suggested_price, supplier_cost, cfg, product_shipping)
        if result.recommended_price and result.recommended_price > suggested_price:
            result.warnings.append("El precio recomendado supera el precio sugerido por Dropi.")
    if custom_price:
        result.at_custom = evaluate(custom_price, supplier_cost, cfg, product_shipping)
        if result.min_profitable_price and custom_price < result.min_profitable_price:
            result.warnings.append("El precio elegido está por debajo del precio mínimo rentable.")
    return result


def break_even_units(fixed_investment_cop: int, profit_per_order: float) -> int | None:
    """Pedidos necesarios para recuperar una inversión fija (muestras, fotos, etc.)."""
    if profit_per_order <= 0:
        return None
    return math.ceil(fixed_investment_cop / profit_per_order)
