# Pillalú Money Engine

Software propio de **Pillalú** (dropshipping, Colombia, COP) para encontrar productos rentables de **Dropi**,
preparar sus publicaciones para **Mercado Libre** y **Facebook Marketplace** y gestionar la operación.

> Estado: **MVP v0.1** — importador, catálogo local, motor de rentabilidad por canal y fichas para publicación
> manual. Nada se publica, compra ni paga automáticamente.

## Qué hace la v0.1

| Módulo | Función |
|---|---|
| 📥 Importar productos | CSV (plantilla o export de Excel) y JSON. JSON crudo del MCP oficial de Dropi con archivo de mapeo. Actualiza por `dropi_id` y guarda historial de costo/stock. |
| 🛒 Catálogo | Tabla con ganancia, margen, precio recomendado y mínimo por canal. Filtros (texto, categoría, proveedor, ganancia, margen, stock) y orden. Desglose de costos por producto. |
| ⚙️ Costos por canal | Comisión, cargo fijo por tramos, retenciones, envío (o flete Dropi por producto), empaque, devoluciones y metas de margen. **Un dato vacío nunca se toma como cero.** |
| 📝 Fichas para publicar | Título y descripción generados sin costo, precio recomendado, edición, estados y exportación (CSV para ML, ZIP para Facebook). |
| 📊 Resumen | Indicadores básicos. Ganancia **potencial** y **realizada** siempre separadas. |

## Cómo ejecutarla en Windows

Requisito: **Python 3.12** ([python.org](https://www.python.org/downloads/), marca *Add python.exe to PATH*).
Streamlit 1.67 exige Python 3.11 o superior; la versión probada en Windows y en CI es la 3.12.

**Opción fácil:** doble clic en `iniciar.bat`. La primera vez crea el entorno con Python 3.12 e instala
dependencias (unos minutos); si algo falla, se detiene y muestra el error. Después abre la app en el navegador
(`http://localhost:8501`).

**Opción manual (PowerShell, en la carpeta del proyecto):**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1          # si PowerShell lo bloquea: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
streamlit run app.py
```

Primeros pasos dentro de la app:
1. **⚙️ Costos por canal**: escribe tus costos reales (los de Mercado Libre salen de su calculadora oficial de costos).
2. **📥 Importar productos**: prueba con `samples/productos_ficticios.csv` o descarga la plantilla y llénala con tus productos de Dropi.
3. **🛒 Catálogo**: filtra, ordena, selecciona productos y pulsa **Preparar fichas**.
4. **📝 Fichas para publicar**: revisa, copia el texto o descarga el paquete y publica a mano.

Los datos se guardan en `data/pillalu.db` (no se sube a GitHub). Para usar otra ubicación: variable `PILLALU_DB`.

## Pruebas

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

Las pruebas también corren en GitHub Actions (Windows y Linux, Python 3.12) en cada push y pull request.
`tests/test_audit_v01.py` reproduce los casos de la auditoría de v0.1.

## Estructura

```
app.py                       interfaz (Streamlit)
src/pillalu/core/            reglas de negocio puras: dinero, rentabilidad, fichas
src/pillalu/adapters/dropi/  importación CSV/JSON y mapeo de respuestas del MCP de Dropi
src/pillalu/storage/db.py    catálogo SQLite
src/pillalu/catalog.py       une catálogo + rentabilidad
src/pillalu/export.py        exportación de fichas
samples/                     datos FICTICIOS para pruebas
tests/                       pruebas financieras, de importación, almacenamiento e interfaz
docs/                        viabilidad, arquitectura, seguridad, Dropi
```

## Reglas del proyecto

- Solo APIs oficiales y mecanismos autorizados. Nada de scraping ni evasión de restricciones.
- Ninguna publicación, pedido real o gasto sin autorización explícita del fundador.
- Ningún secreto en el repositorio (ver `docs/SECURITY.md`).
- Trabajo por ramas y pull requests; cada PR pasa auditoría antes de fusionarse.
- Rentabilidad por encima de complejidad tecnológica.

Documentación: [FEASIBILITY](docs/FEASIBILITY.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) ·
[ROADMAP](docs/ROADMAP.md) · [SECURITY](docs/SECURITY.md) · [DROPI](docs/DROPI.md) · [CLAUDE.md](CLAUDE.md)
