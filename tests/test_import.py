import json

import pytest

from conftest import SAMPLES
from pillalu.adapters.dropi import file_import
from pillalu.adapters.dropi.mapping import load_mapping, normalize, suggest_mapping


def test_sample_csv():
    report = file_import.read_file("x.csv", (SAMPLES / "productos_ficticios.csv").read_bytes())
    ids = [p.source_id for p in report.products]
    assert ids == ["DEMO-001", "DEMO-002", "DEMO-003", "DEMO-004", "DEMO-005", "DEMO-006"]
    assert report.rejected and report.rejected[0][0] == 8 and "costo_proveedor" in report.rejected[0][1]
    p1 = report.products[0]
    assert p1.supplier_cost_cop == 28500 and p1.suggested_price_cop == 59900 and p1.shipping_cost_cop == 14000
    assert p1.images == ["https://example.com/demo/lampara-1.jpg", "https://example.com/demo/lampara-2.jpg"]
    assert report.products[3].has_variants is True
    # Sin costo: se importa pero queda advertido (no se inventa el dato)
    assert report.products[5].supplier_cost_cop is None
    assert any("DEMO-006" in w or "Audífonos" in w for w in report.warnings)
    # Precio sugerido vacío queda desconocido
    assert report.products[4].suggested_price_cop is None


def test_sample_json_with_aliases():
    report = file_import.read_file("x.json", (SAMPLES / "productos_ficticios.json").read_bytes())
    assert [p.source_id for p in report.products] == ["DEMO-101", "DEMO-102"]
    assert report.products[1].supplier_cost_cop == 39500
    assert report.products[1].images == ["https://example.com/demo/cepillo-1.jpg"]


def test_csv_comma_delimited_latin1_and_accented_headers():
    text = "Código,Nombre,Costo,Stock\nA1,Producto uno,\"12.500\",3\n"
    report = file_import.read_file("x.csv", text.encode("latin-1"))
    assert report.products[0].supplier_cost_cop == 12500 and report.products[0].source_id == "A1"


def test_missing_id_and_invalid_cost_rejected():
    text = "dropi_id;nombre;costo_proveedor\n;Sin id;1000\nB2;Costo cero;0\n"
    report = file_import.read_csv_text(text)
    assert not report.products
    assert len(report.rejected) == 2


def test_no_name_column_raises():
    with pytest.raises(ValueError):
        file_import.read_csv_text("a;b\n1;2\n")


def test_raw_mcp_json_requires_mapping_and_mapping_works(tmp_path):
    raw = {"data": {"products": [
        {"id": 77, "name": "Producto MCP", "sale_price": "25.000", "suggested_price": 55000, "stock": 9,
         "categories": [{"name": "Hogar"}], "user": {"name": "Prov X"},
         "gallery": [{"url": "https://example.com/a.jpg"}, {"url": "https://example.com/b.jpg"}]},
    ]}}
    with pytest.raises(ValueError):
        file_import.read_json_text(json.dumps(raw))
    mapping = load_mapping(SAMPLES / "mapeo_mcp_ejemplo.json")
    report = file_import.read_json_text(json.dumps(raw), mapping)
    p = report.products[0]
    assert (p.source_id, p.supplier_cost_cop, p.category, p.supplier_name) == ("77", 25000, "Hogar", "Prov X")
    assert p.images == ["https://example.com/a.jpg", "https://example.com/b.jpg"]
    suggestion = suggest_mapping(raw)
    assert suggestion["items_path"] == "data.products"
    assert suggestion["fields"]["source_id"] == "id"
    assert normalize(raw, mapping)[0].name == "Producto MCP"
