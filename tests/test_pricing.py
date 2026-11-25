"""Pruebas financieras del motor de rentabilidad (valores calculados a mano)."""

import pytest

from pillalu.core.pricing import (
    ChannelConfig, analyze, break_even_units, evaluate, format_tiers, parse_tiers, solve_min_price, tier_value,
)


def ml_cfg(**kw):
    base = dict(
        channel="mercadolibre", commission_pct=0.15, fixed_fee_tiers=[(60000, 3000), (None, 0)], other_pct=0.02,
        shipping_tiers=[(100000, 0), (None, 9000)], packaging_cop=1000, return_rate=0.05, return_cost_cop=10000,
        target_margin=0.25, min_margin=0.10, min_profit_cop=5000,
    )
    base.update(kw)
    return ChannelConfig(**base)


def fb_cfg(**kw):
    base = dict(
        channel="facebook", commission_pct=0.0, fixed_fee_tiers=[], other_pct=0.0, shipping_tiers=None,
        use_product_shipping=True, packaging_cop=0, return_rate=0.20, return_cost_cop=28000,
        target_margin=0.25, min_margin=0.10, min_profit_cop=5000,
    )
    base.update(kw)
    return ChannelConfig(**base)


def test_evaluate_hand_computed_ml():
    b = evaluate(59900, 28500, ml_cfg())
    assert b.commission == pytest.approx(8985)
    assert b.fixed_fee == 3000
    assert b.other == pytest.approx(1198)
    assert b.shipping == 0
    assert b.profit_if_delivered == pytest.approx(17217)
    assert b.expected_profit == pytest.approx(0.95 * 17217 - 0.05 * 10000)  # 15.856,15
    assert b.expected_return_loss == pytest.approx(17217 - 15856.15)
    assert b.margin == pytest.approx(15856.15 / 59900)


def test_fixed_fee_not_subtracted_twice_above_threshold():
    # Por encima de 60.000 el cargo fijo es 0; el envío pasa a 9.000 sobre 100.000.
    b = evaluate(120000, 50000, ml_cfg())
    assert b.fixed_fee == 0 and b.shipping == 9000
    assert b.profit_if_delivered == pytest.approx(120000 - 50000 - 18000 - 2400 - 9000 - 1000)


def test_evaluate_facebook_cod_uses_product_freight():
    b = evaluate(59900, 28500, fb_cfg(), product_shipping=14000)
    assert b.shipping == 14000
    assert b.profit_if_delivered == 17400
    # 20 % de rechazos con pérdida de 28.000 cada uno
    assert b.expected_profit == pytest.approx(0.8 * 17400 - 0.2 * 28000)  # 8.320


def test_break_even_hand_computed():
    # Tramo ≤ 60.000: k = 28.500 + 3.000 + 0 + 1.000; P = (0,95·32.500 + 500) / (0,95·0,83) = 39.790,74
    p = solve_min_price(28500, ml_cfg(), 0, 0)
    assert p == 39791
    assert evaluate(p, 28500, ml_cfg()).expected_profit >= 0
    assert evaluate(p - 1, 28500, ml_cfg()).expected_profit < 0


def _brute(cost, cfg, min_profit, min_margin, ship=None, top=400000):
    for p in range(1, top):
        b = evaluate(p, cost, cfg, ship)
        if b.expected_profit + 0.5 >= min_profit and b.expected_profit + 0.5 >= min_margin * p:
            return p
    return None


@pytest.mark.parametrize("cost", [5000, 19999, 28500, 41000, 49000, 70000])
@pytest.mark.parametrize("goal", [(0, 0), (5000, 0.10), (5000, 0.25)])
def test_solver_matches_brute_force(cost, goal):
    cfg = ml_cfg()
    assert solve_min_price(cost, cfg, *goal) == _brute(cost, cfg, *goal)


def test_solver_handles_step_down_tier():
    # Cargo fijo alto bajo 50.000 y nulo encima: el mínimo puede saltar al siguiente tramo.
    cfg = ml_cfg(fixed_fee_tiers=[(50000, 15000), (None, 0)], shipping_tiers=[(None, 0)])
    for cost in (20000, 25000, 30000):
        assert solve_min_price(cost, cfg, 5000, 0.25) == _brute(cost, cfg, 5000, 0.25)


def test_analyze_complete_ml():
    r = analyze(28500, ml_cfg(), suggested_price=59900)
    assert r.complete
    assert r.break_even_price <= r.min_profitable_price <= r.recommended_price
    assert str(r.recommended_price).endswith("900")
    b = r.at_recommended
    assert b.margin >= 0.25 - 1e-9 and b.expected_profit >= 5000
    assert r.at_suggested.price == 59900


@pytest.mark.parametrize("cost", range(5000, 200000, 7919))
def test_recommended_always_meets_target(cost):
    for cfg in (ml_cfg(), fb_cfg()):
        r = analyze(cost, cfg, product_shipping=15000)
        assert r.recommended_price is not None
        assert r.at_recommended.margin >= cfg.target_margin - 1e-6
        assert r.at_recommended.expected_profit >= cfg.min_profit_cop - 0.5


def test_unknown_costs_are_not_zero():
    cfg = ChannelConfig(channel="mercadolibre")  # todo desconocido
    r = analyze(28500, cfg)
    assert not r.complete
    assert r.recommended_price is None and r.at_recommended is None
    assert "comisión del canal (%)" in r.missing
    assert "costo de envío" in r.missing


def test_missing_supplier_cost():
    r = analyze(None, ml_cfg())
    assert r.missing == ["costo del proveedor"]


def test_facebook_without_product_freight_or_channel_shipping_is_incomplete():
    r = analyze(28500, fb_cfg(), product_shipping=None)
    assert any("flete" in m for m in r.missing)
    r2 = analyze(28500, fb_cfg(shipping_tiers=[(None, 15000)]), product_shipping=None)
    assert r2.complete


def test_explicit_zero_is_accepted():
    cfg = fb_cfg(return_rate=0.0, return_cost_cop=0)
    r = analyze(10000, cfg, product_shipping=0)
    assert r.complete
    assert r.break_even_price == 10000


def test_impossible_margin_returns_none_with_warning():
    r = analyze(28500, ml_cfg(commission_pct=0.80))
    assert r.recommended_price is None
    assert r.warnings


def test_custom_price_below_minimum_warns():
    r = analyze(28500, ml_cfg(), custom_price=40000)
    assert r.selling.price == 40000
    assert any("mínimo rentable" in w for w in r.warnings)


def test_recommended_above_dropi_suggested_warns():
    r = analyze(50000, ml_cfg(), suggested_price=59900)
    assert any("sugerido por Dropi" in w for w in r.warnings)


def test_break_even_units():
    assert break_even_units(100000, 15856.15) == 7
    assert break_even_units(100000, 0) is None


def test_tiers_parse_and_format_roundtrip():
    tiers = parse_tiers("hasta 60.000: 3.000\nresto: 0")
    assert tiers == [(60000, 3000), (None, 0)]
    assert parse_tiers(format_tiers(tiers)) == tiers
    assert parse_tiers("2500") == [(None, 2500)]
    assert tier_value(tiers, 60000) == 3000 and tier_value(tiers, 60001) == 0
    with pytest.raises(ValueError):
        parse_tiers("hasta xx: 3000")
