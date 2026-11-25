"""Regresiones de los hallazgos de la revisión automática del PR #2."""

import pytest

from pillalu.adapters.dropi import file_import
from pillalu.core.money import parse_percent_field
from pillalu.core.models import Product
from pillalu.core.pricing import ChannelConfig, _meets, analyze, evaluate
from pillalu.export import drafts_to_ml_csv
from pillalu.storage import db


def test_negative_numbers_rejected_on_import():
    text = "dropi_id;nombre;costo_proveedor;costo_envio;stock\nA;Uno;1000;-5000;3\nB;Dos;1000;100;-1\n"
    report = file_import.read_csv_text(text)
    assert not report.products
    assert [r[0] for r in report.rejected] == [2, 3]


def test_percent_field_is_unambiguous():
    assert parse_percent_field("0,5") == pytest.approx(0.005)
    assert parse_percent_field("1") == pytest.approx(0.01)
    assert parse_percent_field("12 %") == pytest.approx(0.12)
    assert parse_percent_field("") is None


def test_recommended_price_always_meets_target_even_with_big_tier_jump():
    # Un salto de envío enorme justo encima del precio exacto: el redondeo no puede recuperarlo.
    cfg = ChannelConfig(channel="mercadolibre", commission_pct=0.10, fixed_fee_tiers=[], other_pct=0.0,
                        shipping_tiers=[(60000, 0), (None, 200000)], packaging_cop=0, return_rate=0.0,
                        return_cost_cop=0, target_margin=0.25, min_margin=0.10, min_profit_cop=5000)
    for cost in range(38000, 41000, 250):
        r = analyze(cost, cfg)
        if r.recommended_price is not None:
            assert _meets(evaluate(r.recommended_price, cost, cfg), 5000, 0.25), cost


def test_explicit_false_variants_clears_flag(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.upsert_products(conn, [Product(source="csv", source_id="X", name="P", supplier_cost_cop=1, has_variants=True)])
    db.upsert_products(conn, [Product(source="csv", source_id="X", name="P", supplier_cost_cop=1, has_variants=None)])
    assert db.list_products(conn)[0].has_variants is True  # no indicado: se conserva
    report = file_import.read_csv_text("dropi_id;nombre;tiene_variantes\nX;P;no\n")
    db.upsert_products(conn, report.products)
    assert db.list_products(conn)[0].has_variants is False


def test_regenerating_resets_status_and_discarded_price_ignored(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.upsert_products(conn, [Product(source="csv", source_id="X", name="P", supplier_cost_cop=1000)])
    pid = db.list_products(conn)[0].id
    db.upsert_draft(conn, pid, "facebook", "T", "D", 50000)
    did = db.list_drafts(conn)[0]["id"]
    db.update_draft(conn, did, status="publicada_manual", external_url="https://example.com/x")
    db.upsert_draft(conn, pid, "facebook", "T2", "D2", 60000, overwrite=True)
    d = db.list_drafts(conn)[0]
    assert d["status"] == "borrador" and d["external_url"] is None
    db.update_draft(conn, did, status="descartada")
    assert db.custom_prices(conn) == {}


def test_csv_export_neutralizes_formulas():
    out = drafts_to_ml_csv([{"title": "=HYPERLINK(\"http://x\")", "description": "@cmd", "price_cop": 1000,
                             "images": [], "source_id": "+1", "stock": None, "category": "-x"}]).decode("utf-8-sig")
    assert "'=HYPERLINK" in out and ";'@cmd" in out and "'+1" in out and "'-x" in out
