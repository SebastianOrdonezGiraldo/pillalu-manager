"""Prueba funcional de la interfaz: cada página carga sin errores con datos reales del flujo."""

import pytest
from streamlit.testing.v1 import AppTest

from conftest import ROOT, SAMPLES
from pillalu.adapters.dropi import file_import
from pillalu.catalog import build_rows
from pillalu.core.listings import build_listing
from pillalu.storage import db

PAGES = ["📊 Resumen", "📥 Importar productos", "🛒 Catálogo", "📝 Fichas para publicar", "⚙️ Costos por canal"]


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("PILLALU_DB", str(tmp_path / "app.db"))
    import streamlit as st

    st.cache_resource.clear()
    return tmp_path / "app.db"


def run(page):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.session_state["page"] = page
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@pytest.mark.parametrize("page", PAGES)
def test_pages_empty_db(app, page):
    run(page)


def test_full_flow(app):
    conn = db.connect(app)
    report = file_import.read_file("p.csv", (SAMPLES / "productos_ficticios.csv").read_bytes())
    db.upsert_products(conn, report.products, "p.csv", len(report.rejected))

    # Configurar Facebook desde el formulario de la interfaz
    at = run(PAGES[4])
    at.text_input(key="facebook_c").set_value("0")
    at.text_input(key="facebook_o").set_value("0")
    at.text_input(key="facebook_p").set_value("1000")
    at.text_area(key="facebook_f").set_value("0")
    at.text_input(key="facebook_rr").set_value("20")
    at.text_input(key="facebook_rc").set_value("28000")
    at.button[1].click()  # botón Guardar del segundo formulario (Facebook)
    at.run()
    assert not at.exception
    cfg = db.get_channel_config(conn, "facebook")
    assert cfg.return_rate == pytest.approx(0.20) and cfg.packaging_cop == 1000 and cfg.use_product_shipping

    configs = db.all_configs(conn)
    rows = build_rows(db.list_products(conn), configs)
    lamp = next(r for r in rows if r.product.source_id == "DEMO-001")
    assert lamp.results["facebook"].complete and not lamp.results["mercadolibre"].complete
    listing = build_listing(lamp.product, "facebook", lamp.results["facebook"].recommended_price)
    db.upsert_draft(conn, lamp.product.id, "facebook", listing["title"], listing["description"], listing["price"])

    for page in PAGES:
        at = run(page)
    at = run(PAGES[2])
    assert any("DEMO-001" in str(df.value.to_dict()) for df in at.dataframe)
    at = run(PAGES[3])
    at.selectbox[0].set_value("facebook").run()
    assert not at.exception
    assert any("Lámpara" in e.label for e in at.expander)
