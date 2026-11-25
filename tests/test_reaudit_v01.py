"""Regresiones de la reauditoría de v0.1 (commit 72a8c27, 25-nov-2026).

Casos de docs/audits/money-engine-v0.1-2026-11-25-72a8c27.md, incluidas bases SQLite con
datos que la versión anterior permitía guardar, probadas desde la interfaz (AppTest).
"""

import json

import pytest
from streamlit.testing.v1 import AppTest

from conftest import ROOT
from pillalu import drafts as draft_rules
from pillalu.adapters.dropi import file_import
from pillalu.adapters.dropi.mapping import parse_mapping
from pillalu.core.models import Product, valid_image_url
from pillalu.core.money import parse_cop, parse_pct, parse_percent_field
from pillalu.core.pricing import ChannelConfig, analyze, evaluate, parse_tiers
from pillalu.storage import db


def fb_cfg(**kw):
    base = dict(channel="facebook", commission_pct=0.0, fixed_fee_tiers=[(None, 0)], other_pct=0.0,
                shipping_tiers=None, use_product_shipping=True, packaging_cop=0, return_rate=0.0,
                return_cost_cop=0, target_margin=0.25, min_margin=0.10, min_profit_cop=5000)
    base.update(kw)
    return ChannelConfig(**base)


# --- RA-P0-01 · el importe completo se valida antes de convertir ---------------------

@pytest.mark.parametrize("raw", ["1,20E+04", "1.2e4", "12 mil", "12k", "45.9.00", "1.234,567.8", "12,34,567",
                                 "$$12.000", "12.000-", "0x10", "١٢٠٠٠"])
def test_ra_p0_01_unaccepted_formats_are_rejected(raw):
    assert parse_cop(raw) is None


@pytest.mark.parametrize("raw,value", [("12.000", 12000), ("12,000", 12000), ("$ 12.000", 12000),
                                       ("COP 12.000", 12000), ("12.000 COP", 12000), ("12000", 12000),
                                       ("12.000,50", 12001), ("-12.000", -12000), (12000.0, 12000)])
def test_ra_p0_01_accepted_formats_keep_their_value(raw, value):
    assert parse_cop(raw) == value


def test_ra_p0_01_audit_case_csv_scientific_freight_is_rejected():
    text = "dropi_id;nombre;costo_proveedor;costo_envio\nS1;Ficticio;25000;1,20E+04\n"
    report = file_import.read_csv_text(text)
    assert not report.products
    assert "costo_envio" in report.rejected[0][1] and "1,20E+04" in report.rejected[0][1]


def test_ra_p0_01_same_rule_in_json_mapping_tiers_and_percent():
    flat = [{"id": "S1", "name": "F", "costo": 25000, "costo_envio": "1,20E+04"}]
    assert not file_import.read_json_text(json.dumps(flat)).products
    mapping = parse_mapping({"fields": {"source_id": "id", "name": "name", "supplier_cost_cop": "costo",
                                        "shipping_cost_cop": "costo_envio"}})
    report = file_import.read_json_text(json.dumps(flat), mapping)
    assert not report.products  # el mapeo tampoco acepta el importe reinterpretado
    assert file_import.read_json_text(json.dumps([dict(flat[0], costo_envio=1.2e4)])).products[0] \
        .shipping_cost_cop == 12000  # un número JSON real conserva su valor
    with pytest.raises(ValueError):
        parse_tiers("hasta 50000: 1,2E+04\nresto: 0")
    assert parse_percent_field("1e1") is None and parse_pct("1E2") is None


def test_ra_p0_01_value_preserved_from_import_to_price_and_margin(tmp_path):
    report = file_import.read_csv_text("dropi_id;nombre;costo_proveedor;costo_envio\nS1;F;25.000;12.000\n")
    conn = db.connect(tmp_path / "t.db")
    db.upsert_products(conn, report.products)
    p = db.list_products(conn)[0]
    assert (p.supplier_cost_cop, p.shipping_cost_cop) == (25000, 12000)
    r = analyze(p.supplier_cost_cop, fb_cfg(), product_shipping=p.shipping_cost_cop)
    b = r.at_recommended
    assert b.shipping == 12000
    assert b.expected_profit == pytest.approx(b.price - 37000)
    assert b.margin >= 0.25 - 1e-9
    assert evaluate(33900, 25000, fb_cfg(), 12000).expected_profit == pytest.approx(-3100)  # caso del informe


# --- Bases heredadas (datos que 72a8c27 o anteriores permitían guardar) --------------

def legacy_db(path, stock=-1, draft_price=49900, status="borrador"):
    conn = db.connect(path)
    db.save_channel_config(conn, fb_cfg())
    db.upsert_products(conn, [Product(source="csv", source_id="L1", name="Producto heredado",
                                      supplier_cost_cop=25000, shipping_cost_cop=12000, stock=5)])
    pid = db.list_products(conn)[0].id
    db.upsert_draft(conn, pid, "facebook", "Producto heredado", "Desc", 49900)
    # Escritura directa, como la dejaba la versión anterior.
    conn.execute("UPDATE products SET stock = ?", (stock,))
    conn.execute("UPDATE listing_drafts SET price_cop = ?, status = ?", (draft_price, status))
    conn.commit()
    conn.close()
    return pid


def run_page(path, monkeypatch, page, channel="facebook"):
    monkeypatch.setenv("PILLALU_DB", str(path))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.session_state["page"] = page
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    if page.startswith("📝"):
        at.selectbox[0].set_value(channel).run()
        assert not at.exception, [e.value for e in at.exception]
    return at


def download_disabled(at) -> bool:
    buttons = at.get("download_button")
    assert buttons, "no se encontró el botón de descarga"
    return all(b.proto.disabled for b in buttons)


def test_ra_p1_01_legacy_negative_stock_blocks_draft(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    legacy_db(path, stock=-1, status="lista")
    conn = db.connect(path)
    d = db.list_drafts(conn)[0]
    blockers, _ = draft_rules.check(d, db.get_product(conn, d["product_id"]), fb_cfg())
    assert any("stock" in b and "negativo" in b for b in blockers)
    assert draft_rules.expected_profit(d, db.get_product(conn, d["product_id"]), fb_cfg()) is None

    at = run_page(path, monkeypatch, "📝 Fichas para publicar")
    assert download_disabled(at)
    assert any("stock inválido" in e.value for e in at.error)
    at = run_page(path, monkeypatch, "📊 Resumen")
    potential = next(m for m in at.metric if "POTENCIAL" in m.label)
    assert potential.value == "$ 0"


def test_ra_p1_02_legacy_negative_price_does_not_break_drafts_page(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    legacy_db(path, stock=5, draft_price=-1000, status="lista")
    at = run_page(path, monkeypatch, "📝 Fichas para publicar")
    assert any("Precio guardado inválido" in e.value for e in at.error)
    assert download_disabled(at)
    price_input = next(n for n in at.number_input if n.label == "Precio (COP)")
    assert price_input.value == 0  # el formulario abre editable dentro del rango
    at = run_page(path, monkeypatch, "📊 Resumen")
    assert next(m for m in at.metric if "POTENCIAL" in m.label).value == "$ 0"
    at = run_page(path, monkeypatch, "🛒 Catálogo")  # el precio heredado no se usa como precio elegido
    conn = db.connect(path)
    assert db.custom_prices(conn) == {}
    with pytest.raises(ValueError):
        db.update_draft(conn, db.list_drafts(conn)[0]["id"], price_cop=-5)


def test_ra_p1_02_fixing_the_legacy_price_reenables_export(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    legacy_db(path, stock=5, draft_price=-1000, status="borrador")
    conn = db.connect(path)
    db.update_draft(conn, db.list_drafts(conn)[0]["id"], price_cop=49900, status="lista")
    conn.close()
    at = run_page(path, monkeypatch, "📝 Fichas para publicar")
    assert not download_disabled(at)
    at = run_page(path, monkeypatch, "📊 Resumen")
    assert next(m for m in at.metric if "POTENCIAL" in m.label).value == "$ 12.900"


# --- RA-P2-01 · URL mal formada -------------------------------------------------------

def test_ra_p2_01_malformed_url_is_invalid_not_an_exception():
    assert valid_image_url("https://[abc/x.jpg") is False
    report = file_import.read_csv_text(
        "dropi_id;nombre;costo_proveedor;imagenes\nU1;P;1000;https://[abc/x.jpg|https://ok.example.com/a.jpg\n")
    assert report.products[0].images == ["https://ok.example.com/a.jpg"]
    mapping = parse_mapping({"fields": {"source_id": "id", "name": "name", "images": "img"}})
    rep = file_import.read_json_text(json.dumps([{"id": "U2", "name": "P", "img": "https://[abc/x.jpg"}]), mapping)
    assert not rep.products and rep.rejected


def test_ra_p2_01_legacy_malformed_image_does_not_break_pages(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    legacy_db(path, stock=5)
    conn = db.connect(path)
    conn.execute("UPDATE products SET images_json = ?", (json.dumps(["https://[abc/x.jpg"]),))
    conn.commit()
    run_page(path, monkeypatch, "📝 Fichas para publicar")
    run_page(path, monkeypatch, "🛒 Catálogo")
