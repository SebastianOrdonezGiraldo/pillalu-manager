import zipfile
import io

from pillalu.catalog import build_rows, to_records
from pillalu.core.listings import build_listing, clean_title
from pillalu.core.models import Product
from pillalu.core.pricing import ChannelConfig
from pillalu.export import drafts_to_fb_zip, drafts_to_ml_csv
from pillalu.storage import db


def mk(sid="D1", cost=20000, **kw):
    return Product(source="csv", source_id=sid, name=kw.pop("name", "Producto demo"), supplier_cost_cop=cost, **kw)


def test_upsert_history_and_no_blank_overwrite(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    c = db.upsert_products(conn, [mk(stock=10, category="Hogar")])
    assert c["inserted"] == 1
    c = db.upsert_products(conn, [mk(stock=10, category="Hogar")])
    assert c["unchanged"] == 1
    c = db.upsert_products(conn, [mk(cost=22000, stock=None, category=None)])
    assert c["updated"] == 1
    p = db.list_products(conn)[0]
    assert p.supplier_cost_cop == 22000 and p.stock == 10 and p.category == "Hogar"
    assert [h["supplier_cost_cop"] for h in db.price_history(conn, p.id)] == [20000, 22000]
    assert db.last_imports(conn)[0]["updated"] == 1


def test_persistence_across_connections(tmp_path):
    path = tmp_path / "t.db"
    conn = db.connect(path)
    db.upsert_products(conn, [mk()])
    cfg = ChannelConfig(channel="facebook", commission_pct=0.0, fixed_fee_tiers=[(None, 0)], other_pct=0.0,
                        shipping_tiers=[(None, 15000)], packaging_cop=0, return_rate=0.2, return_cost_cop=28000)
    db.save_channel_config(conn, cfg, "Garantía 30 días")
    conn.close()
    conn2 = db.connect(path)
    assert len(db.list_products(conn2)) == 1
    assert db.get_channel_config(conn2, "facebook") == cfg
    assert db.get_footer(conn2, "facebook") == "Garantía 30 días"
    # Canal sin configurar: todo desconocido
    assert db.get_channel_config(conn2, "mercadolibre").commission_pct is None


def test_drafts_do_not_overwrite_edits(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.upsert_products(conn, [mk()])
    pid = db.list_products(conn)[0].id
    assert db.upsert_draft(conn, pid, "facebook", "T1", "D1", 50000)
    d = db.list_drafts(conn)[0]
    db.update_draft(conn, d["id"], title="Editado", status="lista")
    assert not db.upsert_draft(conn, pid, "facebook", "T2", "D2", 60000)
    assert db.list_drafts(conn)[0]["title"] == "Editado"
    assert db.custom_prices(conn) == {(pid, "facebook"): 50000}
    db.upsert_draft(conn, pid, "facebook", "T2", "D2", 60000, overwrite=True)
    assert db.list_drafts(conn)[0]["title"] == "T2"


def test_catalog_rows_and_custom_price(tmp_path):
    cfg_fb = ChannelConfig(channel="facebook", commission_pct=0.0, fixed_fee_tiers=[(None, 0)], other_pct=0.0,
                           use_product_shipping=True, packaging_cop=0, return_rate=0.2, return_cost_cop=28000)
    configs = {"mercadolibre": ChannelConfig(channel="mercadolibre"), "facebook": cfg_fb}
    p = mk(shipping_cost_cop=14000)
    p.id = 1
    rows = build_rows([p], configs, {(1, "facebook"): 59900})
    rec = to_records(rows)[0]
    assert rec["ml_ganancia"] is None and rec["ml_completo"] is False  # desconocido ≠ 0
    assert rec["fb_precio"] == 59900
    assert rec["fb_ganancia"] == round(0.8 * (59900 - 20000 - 14000) - 0.2 * 28000)
    assert rec["mejor_canal"] == "FB"


def test_clean_title_rules():
    t = clean_title("Audífonos inalámbricos TWS ¡ENVÍO GRATIS! stock disponible 🔥", 60)
    assert "gratis" not in t.lower() and "stock" not in t.lower() and "🔥" not in t
    assert t.startswith("Audífonos Inalámbricos TWS")
    long = clean_title("Organizador de maquillaje giratorio 360 grados con seis niveles ajustables de acrílico", 40)
    assert len(long) <= 40 and not long.endswith(" de")


def test_listing_and_exports():
    p = mk(name="Lámpara LED recargable", description="Luz LED de 3 tonos. Batería USB.", images=[
        "https://example.com/1.jpg"])
    listing = build_listing(p, "facebook", 59900, 60, "Garantía 30 días")
    assert "- Luz LED de 3 tonos." in listing["description"] and "Garantía 30 días" in listing["description"]
    drafts = [{"title": listing["title"], "description": listing["description"], "price_cop": 59900,
               "images": p.images, "source_id": "D1", "stock": 5, "category": "Hogar"}]
    csv_bytes = drafts_to_ml_csv(drafts)
    assert csv_bytes.startswith(b"\xef\xbb\xbf") and b"59900" in csv_bytes
    zf = zipfile.ZipFile(io.BytesIO(drafts_to_fb_zip(drafts)))
    names = zf.namelist()
    assert "LEEME.txt" in names and any(n.endswith("anuncio.txt") for n in names)
    txt = zf.read([n for n in names if n.endswith("anuncio.txt")][0]).decode()
    assert "$ 59.900" in txt
