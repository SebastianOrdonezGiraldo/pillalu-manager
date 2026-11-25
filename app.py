"""Pillalú Money Engine — interfaz local (Streamlit).

Ejecutar:  streamlit run app.py   (o doble clic en iniciar.bat en Windows)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from pillalu import __version__  # noqa: E402
from pillalu.adapters.dropi import file_import  # noqa: E402
from pillalu.adapters.dropi.mapping import MappingError, suggest_mapping  # noqa: E402
from pillalu.catalog import analyze_product, build_rows, to_records  # noqa: E402
from pillalu.core.listings import build_listing  # noqa: E402
from pillalu.core.models import CHANNEL_LABELS, CHANNELS, Product  # noqa: E402
from pillalu.core.money import fmt_cop, fmt_pct, parse_cop, parse_percent_field  # noqa: E402
from pillalu.core.pricing import ChannelConfig, break_even_units, evaluate, format_tiers, parse_tiers  # noqa: E402
from pillalu.export import ad_text, drafts_to_fb_zip, drafts_to_ml_csv  # noqa: E402
from pillalu.storage import db  # noqa: E402

st.set_page_config(page_title="Pillalú Money Engine", page_icon="💸", layout="wide")

st.markdown(
    """
    <style>
      [data-testid="stSidebar"] { background-color: #0B1424; }
      [data-testid="stMetricValue"] { color: #BAFA71; }
      .pill-brand { font-size: 1.6rem; font-weight: 800; color: #FFFFFF; }
      .pill-brand span { color: #BAFA71; }
      .pill-note { color: #9FB0CC; font-size: 0.85rem; }
      button[kind="primary"], button[kind="primaryFormSubmit"] { color: #101C32 !important; font-weight: 700; }
      [data-baseweb="tag"] span { color: #101C32 !important; font-weight: 600; }
      button[kind="primary"] p, button[kind="primaryFormSubmit"] p { color: #101C32 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_conn():
    return db.connect()


conn = get_conn()

PAGES = ["📊 Resumen", "📥 Importar productos", "🛒 Catálogo", "📝 Fichas para publicar", "⚙️ Costos por canal"]
with st.sidebar:
    st.markdown('<div class="pill-brand">Pillalú <span>Money Engine</span></div>', unsafe_allow_html=True)
    st.caption(f"v{__version__} · local · sin publicaciones automáticas")
    page = st.radio("Menú", PAGES, label_visibility="collapsed", key="page")
    st.divider()
    st.markdown(
        '<div class="pill-note">Todo corre en tu computador. Nada se publica ni se compra '
        "automáticamente.</div>",
        unsafe_allow_html=True,
    )


def load_rows():
    configs = db.all_configs(conn)
    products = db.list_products(conn)
    rows = build_rows(products, configs, db.custom_prices(conn), db.excluded_ids(conn))
    return configs, rows


def missing_config_banner(configs: dict[str, ChannelConfig]) -> None:
    from pillalu.core.pricing import missing_inputs

    for ch, cfg in configs.items():
        miss = [m for m in missing_inputs(cfg, 1, 1) if m != "costo del proveedor"]
        if miss:
            st.warning(
                f"**{CHANNEL_LABELS[ch]}**: faltan costos ({', '.join(miss)}). "
                "Mientras falten, ese canal no muestra ganancias (un costo desconocido no se toma como cero). "
                "Complétalos en ⚙️ Costos por canal."
            )


# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------
def page_summary():
    st.title("Resumen")
    configs, rows = load_rows()
    missing_config_banner(configs)
    active = [r for r in rows if not r.excluded]
    drafts = db.list_drafts(conn)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Productos en catálogo", len(active))
    valuable = [r for r in active if any(res.complete for res in r.results.values())]
    c2.metric("Con datos para calcular", len(valuable))
    profitable = [
        r for r in active
        if any(res.at_suggested and res.at_suggested.expected_profit >= configs[ch].min_profit_cop
               and res.at_suggested.margin >= configs[ch].min_margin for ch, res in r.results.items())
    ]
    c3.metric("Oportunidades al precio sugerido Dropi", len(profitable),
              help="Productos que cumplen tu ganancia y margen mínimos si se venden al precio sugerido por Dropi.")
    c4.metric("Fichas preparadas", len(drafts))

    st.subheader("Ganancias")
    g1, g2 = st.columns(2)
    ready = [d for d in drafts if d["status"] in ("lista", "publicada_manual")]
    potential = 0.0
    for d in ready:
        p = db.get_product(conn, d["product_id"])
        res = analyze_product(p, configs, {(p.id, d["channel"]): d["price_cop"]})[d["channel"]] if p else None
        if res and res.selling:
            potential += res.selling.expected_profit
    g1.metric("Ganancia POTENCIAL (1 venta por ficha lista/publicada)", fmt_cop(potential),
              help="Estimación, no es dinero real. Suma la ganancia esperada de vender una unidad de cada ficha.")
    g2.metric("Ganancia REALIZADA", fmt_cop(0),
              help="Aún no hay registro de pedidos (llega en una versión posterior). Nunca se mezcla con la potencial.")
    st.caption("La ganancia realizada solo contará pedidos entregados y pagados. En v0.1 no hay pedidos registrados.")

    st.subheader("Fichas por estado")
    counts = {db.STATUS_LABELS[s]: sum(1 for d in drafts if d["status"] == s) for s in db.DRAFT_STATUSES}
    st.dataframe(pd.DataFrame([counts]), hide_index=True)

    st.subheader("Últimas importaciones")
    imports = db.last_imports(conn)
    if imports:
        st.dataframe(pd.DataFrame(imports).rename(columns={
            "filename": "archivo", "created_at": "fecha", "inserted": "nuevos", "updated": "actualizados",
            "unchanged": "sin cambios", "rejected": "rechazados"}), hide_index=True)
    else:
        st.info("Todavía no has importado productos. Ve a 📥 Importar productos.")


# ---------------------------------------------------------------------------
# Importar
# ---------------------------------------------------------------------------
def page_import():
    st.title("Importar productos")
    st.markdown(
        "Carga un **CSV** (Excel → Guardar como CSV) o un **JSON** con productos de Dropi. "
        "Si importas un producto que ya existe (mismo `dropi_id`), se actualizan costo, stock y precio sugerido "
        "y se guarda el historial."
    )
    template = ";".join(file_import.TEMPLATE_HEADERS) + "\n"
    st.download_button("⬇️ Descargar plantilla CSV", template.encode("utf-8-sig"), "plantilla_productos.csv",
                       "text/csv")
    with st.expander("¿De dónde saco los datos de Dropi?"):
        st.markdown(
            "- **Opción 1 (hoy):** copia de tu panel de Dropi los productos que te interesan en la plantilla.\n"
            "- **Opción 2 (MCP oficial de Dropi):** conecta `https://mcp.dropi.co/mcp` como conector "
            "personalizado en Claude, pide la búsqueda de productos y guarda la respuesta como `.json`. "
            "Si el JSON no trae nuestras columnas, carga también un archivo de mapeo (ver `docs/DROPI.md`).\n"
            "- No se usa scraping."
        )

    uploaded = st.file_uploader("Archivo de productos", type=["csv", "json"])
    mapping_file = st.file_uploader("Archivo de mapeo del MCP (opcional, solo JSON crudo)", type=["json"])
    if uploaded:
        mapping = None
        try:
            if mapping_file:
                from pillalu.adapters.dropi.mapping import load_mapping
                import tempfile, os

                with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as tmp:
                    tmp.write(mapping_file.getvalue())
                mapping = load_mapping(tmp.name)
                os.unlink(tmp.name)
            report = file_import.read_file(uploaded.name, uploaded.getvalue(), mapping)
        except (ValueError, MappingError, json.JSONDecodeError) as exc:
            st.error(f"No se pudo leer el archivo: {exc}")
            if uploaded.name.lower().endswith(".json") and not mapping_file:
                try:
                    suggestion = suggest_mapping(json.loads(uploaded.getvalue().decode("utf-8-sig")))
                    st.info("Parece una respuesta cruda. Este es un mapeo **sugerido**; revísalo, guárdalo como "
                            "`mapeo.json` y cárgalo arriba.")
                    st.code(json.dumps(suggestion, indent=2, ensure_ascii=False), language="json")
                except Exception:  # noqa: BLE001
                    pass
            return

        st.success(f"{len(report.products)} productos válidos · {len(report.rejected)} filas rechazadas")
        if report.unknown_columns:
            st.caption("Columnas ignoradas: " + ", ".join(report.unknown_columns))
        for w in report.warnings[:20]:
            st.warning(w)
        if report.rejected:
            st.dataframe(pd.DataFrame(report.rejected, columns=["fila", "motivo"]), hide_index=True)
        if report.products:
            preview = pd.DataFrame([p.to_dict() for p in report.products])
            st.dataframe(preview.drop(columns=["id"], errors="ignore"), hide_index=True, use_container_width=True)
            if st.button("💾 Guardar en el catálogo", type="primary"):
                counts = db.upsert_products(conn, report.products, uploaded.name, len(report.rejected),
                                            {"rechazadas": report.rejected[:200]})
                st.success(f"Listo: {counts['inserted']} nuevos, {counts['updated']} actualizados, "
                           f"{counts['unchanged']} sin cambios.")

    st.divider()
    st.subheader("Agregar un producto a mano")
    with st.form("manual", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        sid = c1.text_input("ID de Dropi *")
        name = c2.text_input("Nombre *")
        category = c3.text_input("Categoría")
        cost = c1.text_input("Costo proveedor (COP) *")
        sugg = c2.text_input("Precio sugerido Dropi (COP)")
        stock = c3.text_input("Stock")
        supplier = c1.text_input("Proveedor")
        ship = c2.text_input("Flete Dropi (COP)")
        imgs = c3.text_input("URLs de imágenes (separadas por |)")
        desc = st.text_area("Descripción")
        if st.form_submit_button("Agregar"):
            c = parse_cop(cost)
            if not sid or not name or not c or c <= 0:
                st.error("ID, nombre y un costo de proveedor mayor que cero son obligatorios.")
            else:
                p = Product(source="manual", source_id=sid.strip(), name=name.strip(), supplier_cost_cop=c,
                            suggested_price_cop=parse_cop(sugg), stock=parse_cop(stock), category=category or None,
                            supplier_name=supplier or None, shipping_cost_cop=parse_cop(ship),
                            images=[u.strip() for u in imgs.split("|") if u.strip().startswith("http")],
                            description=desc or None)
                counts = db.upsert_products(conn, [p], "manual")
                st.success("Producto guardado." if counts["inserted"] else "Producto actualizado.")


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------
SORTS = {
    "Mayor ganancia (mejor canal)": ("mejor_ganancia", False),
    "Mayor ganancia Mercado Libre": ("ml_ganancia", False),
    "Mayor ganancia Facebook": ("fb_ganancia", False),
    "Mayor ganancia FB al precio sugerido Dropi": ("fb_ganancia_sugerido", False),
    "Mayor ganancia ML al precio sugerido Dropi": ("ml_ganancia_sugerido", False),
    "Mayor margen Mercado Libre": ("ml_margen", False),
    "Mayor margen Facebook": ("fb_margen", False),
    "Menor costo": ("costo", True),
    "Mayor stock": ("stock", False),
    "Nombre": ("producto", True),
}


def breakdown_table(results, configs) -> pd.DataFrame:
    lines = [
        ("Precio de venta", lambda b: b.price),
        ("− Costo proveedor (Dropi)", lambda b: -b.supplier_cost),
        ("− Comisión del canal", lambda b: -b.commission),
        ("− Cargo fijo por venta", lambda b: -b.fixed_fee),
        ("− Retenciones / otros", lambda b: -b.other),
        ("− Envío", lambda b: -b.shipping),
        ("− Empaque / otros", lambda b: -b.packaging),
        ("= Ganancia si se entrega", lambda b: b.profit_if_delivered),
        ("− Pérdida esperada por devoluciones", lambda b: -b.expected_return_loss),
        ("= GANANCIA ESPERADA", lambda b: b.expected_profit),
    ]
    data = {"Concepto": [l[0] for l in lines] + ["Margen esperado", "Precio recomendado", "Precio mínimo rentable",
                                                  "Precio de equilibrio (ganancia 0)"]}
    for ch, r in results.items():
        b = r.selling
        col = []
        for _, fn in lines:
            col.append(fmt_cop(fn(b)) if b else "—")
        col += [fmt_pct(b.margin) if b else "—", fmt_cop(r.recommended_price), fmt_cop(r.min_profitable_price),
                fmt_cop(r.break_even_price)]
        data[CHANNEL_LABELS[ch]] = col
    return pd.DataFrame(data)


def page_catalog():
    st.title("Catálogo")
    configs, rows = load_rows()
    missing_config_banner(configs)
    if not rows:
        st.info("El catálogo está vacío. Importa productos primero.")
        return
    df = pd.DataFrame(to_records(rows))

    with st.container(border=True):
        f1, f2, f3, f4 = st.columns([2, 2, 2, 2])
        text = f1.text_input("Buscar", placeholder="nombre o ID")
        cats = f2.multiselect("Categoría", sorted(c for c in df["categoria"].unique() if c), placeholder="Todas")
        sups = f3.multiselect("Proveedor", sorted(s for s in df["proveedor"].unique() if s), placeholder="Todos")
        sort_label = f4.selectbox("Ordenar por", list(SORTS))
        g1, g2, g3, g4, g5 = st.columns(5)
        channel = g1.selectbox("Canal para filtros", ["Cualquiera", "Mercado Libre", "Facebook"])
        min_profit = g2.number_input("Ganancia mínima (COP)", value=0, step=1000)
        min_margin = g3.number_input("Margen mínimo (%)", value=0.0, step=1.0)
        only_complete = g4.checkbox("Solo con cálculo completo", value=False)
        only_stock = g5.checkbox("Solo con stock", value=False)
        show_excluded = g5.checkbox("Ver excluidos", value=False)

    view = df.copy()
    if text:
        t = text.lower()
        view = view[view["producto"].str.lower().str.contains(t, regex=False) | view["dropi_id"].astype(str).str.contains(t, regex=False)]
    if cats:
        view = view[view["categoria"].isin(cats)]
    if sups:
        view = view[view["proveedor"].isin(sups)]
    if not show_excluded:
        view = view[~view["excluido"]]
    if only_stock:
        view = view[view["stock"].fillna(0) > 0]
    prefixes = {"Cualquiera": ["ml", "fb"], "Mercado Libre": ["ml"], "Facebook": ["fb"]}[channel]

    def cond(prefix):
        c = pd.Series(True, index=view.index)
        if only_complete:
            c &= view[f"{prefix}_completo"]
        if min_profit:
            c &= view[f"{prefix}_ganancia"].fillna(-1e18) >= min_profit
        if min_margin:
            c &= view[f"{prefix}_margen"].fillna(-1e18) >= min_margin
        return c

    mask = cond(prefixes[0])
    for pr in prefixes[1:]:
        mask |= cond(pr)
    view = view[mask]
    col, asc = SORTS[sort_label]
    view = view.sort_values(col, ascending=asc, na_position="last").reset_index(drop=True)

    st.caption(f"{len(view)} de {len(df)} productos · montos por unidad en COP. «Ganancia» = ganancia esperada "
               "(descuenta devoluciones) al precio de tu ficha o, si no hay ficha, al precio recomendado. "
               "«Ganancia a sugerido» usa el precio sugerido por Dropi: es la mejor referencia para comparar productos. "
               "Vacío = faltan datos (nunca se asume cero).")
    event = st.dataframe(
        view.drop(columns=["ml_completo", "fb_completo", "mejor_ganancia"]),
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="multi-row",
        column_config={
            "id": None,
            "excluido": None,
            "dropi_id": "ID Dropi",
            "producto": st.column_config.TextColumn("Producto", width="medium"),
            "stock": "Stock",
            "fotos": "Fotos",
            "categoria": "Categoría",
            "proveedor": "Proveedor",
            "costo": st.column_config.NumberColumn("Costo", format="localized"),
            "sugerido_dropi": st.column_config.NumberColumn("Sugerido Dropi", format="localized"),
            "ml_precio": st.column_config.NumberColumn("ML precio venta", format="localized"),
            "ml_ganancia": st.column_config.NumberColumn("ML ganancia", format="localized"),
            "ml_margen": st.column_config.NumberColumn("ML margen", format="%.1f %%"),
            "ml_minimo": st.column_config.NumberColumn("ML mínimo", format="localized"),
            "fb_precio": st.column_config.NumberColumn("FB precio venta", format="localized"),
            "fb_ganancia": st.column_config.NumberColumn("FB ganancia", format="localized"),
            "fb_margen": st.column_config.NumberColumn("FB margen", format="%.1f %%"),
            "fb_minimo": st.column_config.NumberColumn("FB mínimo", format="localized"),
            "ml_ganancia_sugerido": st.column_config.NumberColumn(
                "ML ganancia a sugerido", format="localized",
                help="Ganancia esperada si vendes al precio sugerido por Dropi"),
            "fb_ganancia_sugerido": st.column_config.NumberColumn(
                "FB ganancia a sugerido", format="localized",
                help="Ganancia esperada si vendes al precio sugerido por Dropi"),
            "mejor_canal": "Mejor canal",
        },
        column_order=["dropi_id", "producto", "mejor_canal", "ml_ganancia", "ml_margen", "ml_precio", "fb_ganancia",
                      "fb_margen", "fb_precio", "costo", "sugerido_dropi", "ml_ganancia_sugerido", "fb_ganancia_sugerido", "stock", "ml_minimo", "fb_minimo",
                      "categoria", "proveedor", "fotos"],
        key="catalog_table",
    )
    selected = view.iloc[event.selection.rows] if event and event.selection.rows else view.iloc[0:0]
    ids = [int(i) for i in selected["id"].tolist()]

    st.markdown(f"**{len(ids)} seleccionados**")
    a1, a2, a3, a4 = st.columns([3, 2, 2, 2])
    chans = a1.multiselect("Canales de las fichas", list(CHANNELS), default=list(CHANNELS),
                           format_func=lambda c: CHANNEL_LABELS[c])
    overwrite = a2.checkbox("Regenerar fichas existentes", value=False,
                            help="Si no se marca, no se tocan fichas que ya editaste.")
    if a3.button("📝 Preparar fichas", type="primary", disabled=not ids):
        by_id = {r.product.id: r for r in rows}
        created = skipped = 0
        no_price: list[str] = []
        for pid in ids:
            row = by_id[pid]
            for ch in chans:
                cfg = configs[ch]
                price = row.results[ch].recommended_price
                if price is None:  # canal incompleto o sin precio que cumpla la meta: no se crea ficha
                    no_price.append(f"{row.product.name} ({CHANNEL_LABELS[ch]})")
                    continue
                listing = build_listing(row.product, ch, price, cfg.title_max_len, db.get_footer(conn, ch))
                if db.upsert_draft(conn, pid, ch, listing["title"], listing["description"], listing["price"],
                                   overwrite):
                    created += 1
                else:
                    skipped += 1
        st.success(f"{created} fichas preparadas, {skipped} ya existían. Revísalas en 📝 Fichas para publicar.")
        if no_price:
            st.warning("Sin ficha por falta de costos o de un precio rentable: " + "; ".join(no_price[:20]))
    if a4.button("🚫 Excluir / restaurar", disabled=not ids):
        currently = db.excluded_ids(conn)
        db.set_excluded(conn, ids, not all(i in currently for i in ids))
        st.rerun()

    if ids:
        st.divider()
        by_id = {r.product.id: r for r in rows}
        pid = st.selectbox("Detalle de rentabilidad", ids, format_func=lambda i: by_id[i].product.name)
        row = by_id[pid]
        p = row.product
        d1, d2 = st.columns([3, 1])
        with d1:
            st.dataframe(breakdown_table(row.results, configs), hide_index=True, use_container_width=True)
            for ch, r in row.results.items():
                if r.missing:
                    st.warning(f"{CHANNEL_LABELS[ch]}: faltan datos → {', '.join(r.missing)}")
                for w in r.warnings:
                    st.info(f"{CHANNEL_LABELS[ch]}: {w}")
            inv = st.number_input("Inversión fija a recuperar (muestras, fotos…) en COP", value=0, step=10000)
            if inv:
                for ch, r in row.results.items():
                    b = r.selling
                    units = break_even_units(inv, b.expected_profit) if b else None
                    st.write(f"**{CHANNEL_LABELS[ch]}**: punto de equilibrio = "
                             f"{units if units else '—'} pedidos entregados")
        with d2:
            if p.images:
                st.image(p.images[0], use_container_width=True)
            st.caption(f"Stock: {p.stock if p.stock is not None else '—'} · Proveedor: {p.supplier_name or '—'}")
            hist = db.price_history(conn, pid)
            if len(hist) > 1:
                st.caption("Historial de costo/stock")
                st.dataframe(pd.DataFrame(hist), hide_index=True)


# ---------------------------------------------------------------------------
# Fichas
# ---------------------------------------------------------------------------
def page_drafts():
    st.title("Fichas para publicar")
    st.caption("Publicación **manual**: copia el texto o descarga el paquete. Nada se publica automáticamente.")
    configs = db.all_configs(conn)
    f1, f2 = st.columns(2)
    ch = f1.selectbox("Canal", list(CHANNELS), format_func=lambda c: CHANNEL_LABELS[c])
    statuses = f2.multiselect("Estado", list(db.DRAFT_STATUSES), default=["borrador", "lista"],
                              format_func=lambda s: db.STATUS_LABELS[s])
    drafts = [d for d in db.list_drafts(conn, ch) if d["status"] in statuses]
    if not drafts:
        st.info("No hay fichas con ese filtro. Selecciona productos en 🛒 Catálogo y pulsa «Preparar fichas».")
        return

    e1, e2 = st.columns(2)
    if ch == "mercadolibre":
        e1.download_button("⬇️ Exportar CSV de trabajo (Mercado Libre)", drafts_to_ml_csv(drafts),
                           "fichas_mercadolibre.csv", "text/csv")
        e2.caption("No es la plantilla oficial de carga masiva de ML (se descarga desde tu cuenta y depende de "
                   "la categoría). Úsalo para copiar los datos.")
    else:
        e1.download_button("⬇️ Descargar paquetes Facebook (.zip)", drafts_to_fb_zip(drafts),
                           "fichas_facebook.zip", "application/zip")

    cfg = configs[ch]
    for d in drafts:
        p = db.get_product(conn, d["product_id"])
        label = f"{db.STATUS_LABELS[d['status']]} · {d['title']} · {fmt_cop(d['price_cop'])}"
        with st.expander(label):
            c1, c2 = st.columns([3, 1])
            with c1:
                with st.form(f"draft_{d['id']}"):
                    title = st.text_input(f"Título ({len(d['title'])}/{cfg.title_max_len})", d["title"],
                                          max_chars=max(cfg.title_max_len, len(d["title"])))
                    price = st.number_input("Precio (COP)", value=int(d["price_cop"] or 0), step=1000)
                    desc = st.text_area("Descripción", d["description"], height=220)
                    status = st.selectbox("Estado", list(db.DRAFT_STATUSES),
                                          index=list(db.DRAFT_STATUSES).index(d["status"]),
                                          format_func=lambda s: db.STATUS_LABELS[s])
                    url = st.text_input("Enlace de la publicación (cuando la publiques)", d.get("external_url") or "")
                    s1, s2 = st.columns(2)
                    if s1.form_submit_button("💾 Guardar", type="primary"):
                        db.update_draft(conn, d["id"], title=title.strip(), price_cop=int(price) or None,
                                        description=desc, status=status, external_url=url.strip() or None)
                        st.rerun()
                    if s2.form_submit_button("🗑️ Eliminar ficha"):
                        db.delete_draft(conn, d["id"])
                        st.rerun()
            with c2:
                if p and p.supplier_cost_cop and d["price_cop"]:
                    from pillalu.core.pricing import missing_inputs

                    if not missing_inputs(cfg, p.supplier_cost_cop, p.shipping_cost_cop):
                        b = evaluate(d["price_cop"], p.supplier_cost_cop, cfg, p.shipping_cost_cop)
                        st.metric("Ganancia esperada", fmt_cop(b.expected_profit), f"margen {fmt_pct(b.margin)}", delta_color="off")
                    else:
                        st.caption("Faltan costos del canal para calcular la ganancia.")
                if d["images"]:
                    st.image(d["images"][0], use_container_width=True)
                    st.caption(f"{len(d['images'])} fotos de Dropi")
            st.caption("Texto para copiar:")
            st.code(ad_text(d), language=None)


# ---------------------------------------------------------------------------
# Costos por canal
# ---------------------------------------------------------------------------
HELP = {
    "mercadolibre": (
        "Toma los valores de la **calculadora oficial de costos de Mercado Libre** o de la sección "
        "*Costos por vender* de tu cuenta (dependen de categoría, tipo de publicación y logística). "
        "En la Fase 3 se leerán automáticamente de la API oficial `/sites/MCO/listing_prices`."
    ),
    "facebook": (
        "Facebook Marketplace con pago contra entrega por Dropi: normalmente lo que importa es el **flete** "
        "que cobra Dropi y la **tasa de devoluciones** (pedidos rechazados). Confirma en tu cuenta de Dropi si "
        "hay comisión por recaudo y escríbela en *retenciones/otros*."
    ),
}


def _txt(v) -> str:
    return "" if v is None else str(v)


def _pct_txt(v) -> str:
    return "" if v is None else f"{v * 100:g}"


def page_settings():
    st.title("Costos por canal")
    st.markdown(
        "Deja un campo **vacío** si no conoces el dato: el sistema no lo tomará como cero y te avisará. "
        "Escribe **0** solo si estás seguro de que ese costo no existe."
    )
    tabs = st.tabs([CHANNEL_LABELS[c] for c in CHANNELS])
    for tab, ch in zip(tabs, CHANNELS):
        with tab:
            cfg = db.get_channel_config(conn, ch)
            st.info(HELP[ch])
            with st.form(f"cfg_{ch}"):
                c1, c2, c3 = st.columns(3)
                commission = c1.text_input("Comisión del canal (%)", _pct_txt(cfg.commission_pct), key=f"{ch}_c")
                other = c2.text_input("Retenciones / impuestos / recaudo (%)", _pct_txt(cfg.other_pct), key=f"{ch}_o")
                packaging = c3.text_input("Empaque u otros por pedido (COP)", _txt(cfg.packaging_cop), key=f"{ch}_p")
                t1, t2 = st.columns(2)
                fixed = t1.text_area("Cargo fijo por venta (COP)", format_tiers(cfg.fixed_fee_tiers), key=f"{ch}_f",
                                     help="Un valor (p. ej. 0) o tramos, una línea por tramo:\n"
                                          "hasta 50000: 2000\nresto: 0")
                shipping = t2.text_area("Envío que pagas tú (COP)", format_tiers(cfg.shipping_tiers), key=f"{ch}_s",
                                        help="Un valor o tramos por precio (mismo formato que el cargo fijo).")
                use_ps = st.checkbox("Usar el flete Dropi de cada producto cuando exista (columna costo_envio)",
                                     cfg.use_product_shipping, key=f"{ch}_ups")
                r1, r2 = st.columns(2)
                rrate = r1.text_input("Tasa de devoluciones / rechazos (%)", _pct_txt(cfg.return_rate), key=f"{ch}_rr")
                rcost = r2.text_input("Pérdida por cada devolución (COP)", _txt(cfg.return_cost_cop), key=f"{ch}_rc",
                                      help="P. ej. flete de ida + flete de regreso que te cobran si el pedido vuelve.")
                st.markdown("**Tus metas**")
                m1, m2, m3, m4 = st.columns(4)
                target = m1.number_input("Margen objetivo (%)", 0.0, 90.0, cfg.target_margin * 100, 1.0, key=f"{ch}_t")
                minm = m2.number_input("Margen mínimo (%)", 0.0, 90.0, cfg.min_margin * 100, 1.0, key=f"{ch}_mm")
                minp = m3.number_input("Ganancia mínima por pedido (COP)", 0, None, cfg.min_profit_cop, 1000,
                                       key=f"{ch}_mp")
                tlen = m4.number_input("Largo máximo del título", 20, 200, cfg.title_max_len, 1, key=f"{ch}_tl")
                footer = st.text_area("Texto final de las descripciones (garantía, horarios…)",
                                      db.get_footer(conn, ch), key=f"{ch}_footer")
                if st.form_submit_button("💾 Guardar", type="primary"):
                    errors = []

                    def pct(label, value):
                        if not value.strip():
                            return None
                        v = parse_percent_field(value)
                        if v is None or v < 0 or v >= 1:
                            errors.append(f"{label}: valor inválido")
                        return v

                    def cop(label, value):
                        if not value.strip():
                            return None
                        v = parse_cop(value)
                        if v is None or v < 0:
                            errors.append(f"{label}: valor inválido")
                        return v

                    def tiers(label, value):
                        if not value.strip():
                            return None
                        try:
                            return parse_tiers(value)
                        except ValueError as exc:
                            errors.append(f"{label}: {exc}")

                    if minm > target:
                        errors.append("El margen mínimo no puede ser mayor que el objetivo.")
                    new = ChannelConfig(
                        channel=ch,
                        commission_pct=pct("Comisión", commission),
                        other_pct=pct("Retenciones", other),
                        packaging_cop=cop("Empaque", packaging),
                        fixed_fee_tiers=tiers("Cargo fijo", fixed),
                        shipping_tiers=tiers("Envío", shipping),
                        use_product_shipping=use_ps,
                        return_rate=pct("Tasa de devoluciones", rrate),
                        return_cost_cop=cop("Pérdida por devolución", rcost),
                        target_margin=target / 100,
                        min_margin=minm / 100,
                        min_profit_cop=int(minp),
                        title_max_len=int(tlen),
                    )
                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        db.save_channel_config(conn, new, footer)
                        st.success("Guardado. Los cálculos del catálogo ya usan estos valores.")


{
    PAGES[0]: page_summary,
    PAGES[1]: page_import,
    PAGES[2]: page_catalog,
    PAGES[3]: page_drafts,
    PAGES[4]: page_settings,
}[page]()
