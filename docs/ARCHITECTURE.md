# Arquitectura propuesta — MVP de uso individual

Objetivo: lo más **simple, barato y mantenible** posible para una sola persona. Costo de infraestructura
objetivo: **$0 COP/mes** en el MVP.

## 1. Decisiones principales

| Decisión | Elección | Por qué |
|---|---|---|
| Dónde corre | **En el computador del fundador** (local) | Sin servidores ni costos; los datos personales no salen del equipo |
| Lenguaje | **Python 3.12** | Buen soporte de HTTP, datos, IA y MCP; fácil de auditar |
| Base de datos | **SQLite** (un archivo) | Cero administración; suficiente para miles de productos |
| Interfaz | **Streamlit** (panel web local) | Formularios y dashboard sin escribir frontend |
| Tareas programadas | Comando `pillalu sync` ejecutado a mano o con el programador de tareas del sistema | Sin colas ni workers |
| Pedidos de Mercado Libre | **Sondeo** de `orders/search` cada X minutos | Evita exponer un servidor público para webhooks |
| Secretos | Archivo `.env` local (no versionado) + llavero del sistema para tokens | Ver `SECURITY.md` |
| Dependencias | `httpx`, `pydantic`, `sqlmodel`/`sqlite3`, `streamlit`, `python-dotenv`, `keyring`, `mcp` (SDK oficial) | Pocas y conocidas |

Descartado por ahora (más costo o complejidad sin retorno inmediato): microservicios, Docker obligatorio,
Postgres, nube, colas de mensajes, frontend en React, webhooks públicos.

## 2. Vista general

```
                ┌───────────────────────────────────────────────┐
                │          Panel local (Streamlit)              │
                │  Catálogo · Calculadora · Anuncios · Pedidos  │
                │                 · Dashboard                   │
                └──────────────────────┬────────────────────────┘
                                       │
                ┌──────────────────────▼────────────────────────┐
                │               Núcleo (Python)                 │
                │  pricing   scoring   listings   orders        │
                │  (reglas de negocio puras, 100% testeables)   │
                └───┬──────────────┬──────────────┬─────────────┘
                    │              │              │
         ┌──────────▼───┐   ┌──────▼──────┐  ┌────▼────────────┐
         │ Adaptador    │   │ Adaptador   │  │ Adaptador       │
         │ Dropi        │   │ Mercado     │  │ Facebook        │
         │ (MCP / API / │   │ Libre (API  │  │ (exporta        │
         │  manual)     │   │ REST OAuth) │  │  paquete manual)│
         └──────┬───────┘   └──────┬──────┘  └────┬────────────┘
                │                  │              │
          mcp.dropi.co     api.mercadolibre.com   archivos locales
                                                  (texto + fotos)
                    ┌──────────────────────────┐
                    │   SQLite (data/pillalu.db)│
                    └──────────────────────────┘
```

Cada canal vive detrás de un **adaptador** con una interfaz común. Si Dropi entrega una API oficial, solo
se cambia el adaptador de Dropi; el núcleo no se toca.

## 3. Estructura de carpetas (propuesta)

```
pillalu-manager/
├── src/pillalu/
│   ├── core/            # reglas de negocio puras
│   │   ├── pricing.py   # costo, comisión, envío, IVA, margen, precio objetivo
│   │   ├── scoring.py   # puntaje de potencial comercial
│   │   └── models.py    # Product, Listing, Order, Supplier…
│   ├── adapters/
│   │   ├── dropi/       # mcp_client.py, manual_import.py (api.py solo si Dropi la autoriza)
│   │   ├── mercadolibre/# auth.py, items.py, fees.py, orders.py
│   │   └── facebook/    # export.py (paquete para publicación asistida)
│   ├── ai/              # generación de títulos/descripciones (proveedor intercambiable)
│   ├── storage/         # SQLite, migraciones simples
│   ├── ui/              # páginas de Streamlit
│   └── cli.py           # comandos: sync, publish --dry-run, orders pull…
├── tests/               # pruebas unitarias con datos de ejemplo (sin red)
├── samples/             # datos ficticios para pruebas
├── docs/
├── .env.example         # nombres de variables, sin valores
└── pyproject.toml
```

## 4. Modelo de datos mínimo

| Tabla | Campos clave |
|---|---|
| `suppliers` | id, dropi_id, nombre, ciudad, notas de calidad |
| `products` | id, dropi_id, supplier_id, nombre, categoría, costo_proveedor, precio_sugerido, stock, imágenes (URLs), peso, dimensiones, actualizado_en |
| `pricing_snapshots` | product_id, canal, precio_venta, comisión, costo_fijo, envío, margen_cop, margen_pct, fuente_de_comisión, fecha |
| `listings` | id, product_id, canal (`ml`/`fb`), id_externo, título, descripción, precio, estado, es_prueba |
| `orders` | id, canal, id_externo, product_id, cantidad, precio, estado, dropi_order_id, costo_real, ganancia |
| `audit_log` | fecha, acción, objetivo, modo (`simulación`/`real`), resultado |

Los datos personales del comprador **no** se guardan en `orders` más allá de lo necesario para crear el
pedido en Dropi (ver `SECURITY.md`).

## 5. Cálculo de rentabilidad (núcleo)

```
ganancia = precio_venta
         − costo_proveedor_dropi
         − comisión_canal         (ML: sale_fee_amount de /sites/MCO/listing_prices)
         − costo_fijo_canal       (ML: fixed_fee, depende de logística)
         − costo_envío            (según escenario logístico; Dropi: cotización MCP)
         − otros (empaque, devoluciones esperadas, pauta)
margen_pct = ganancia / precio_venta
```

Reglas: nunca usar porcentajes de comisión escritos a mano si la API está disponible; guardar de dónde salió
cada valor; si falta un dato, el producto queda **"no publicable"**, nunca se adivina.

## 6. Seguridad por diseño

- **Modo simulación por defecto.** Toda acción de escritura externa (publicar, actualizar, crear pedido en
  Dropi) tiene `--dry-run` por defecto y exige confirmación explícita para el modo real.
- Mercado Libre: desarrollo solo con **usuarios de prueba** hasta que el fundador autorice publicar.
- Registro de auditoría de cada acción externa.
- Backoff exponencial ante errores 429.

## 7. Generación de textos con IA

Interfaz `TextGenerator` con dos implementaciones:
1. **Sin costo (por defecto):** plantillas + reglas de títulos de Mercado Libre; el fundador puede pegar el
   texto generado por un asistente de IA que ya usa.
2. **API de IA (opcional, requiere autorización B-4):** proveedor configurable. Se calcula y muestra el
   costo estimado antes de habilitarlo.

## 8. Qué queda fuera del MVP

Multiusuario, hosting en la nube, webhooks, tienda web propia, catálogo de Meta por API, Mercado Libre Full,
facturación electrónica. Se reevalúan en fases posteriores si el negocio lo justifica.
