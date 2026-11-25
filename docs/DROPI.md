# Conexión con Dropi — estado en v0.1

Fecha: 25 de noviembre de 2026. Base: investigación de la Fase 0 (`FEASIBILITY.md` §1).

## Qué está disponible

| Mecanismo | Estado | Uso en v0.1 |
|---|---|---|
| API REST pública de Dropi | **[NO ENCONTRADO]** No hay documentación oficial (`dev.dropi.co` vacío) | No se usa. No se construye nada sobre endpoints no documentados. |
| MCP oficial `https://mcp.dropi.co/mcp` | **[VERIFICADO]** Existe, con OAuth en `oauth.dropi.co` (búsqueda de productos, categorías, pedidos, cotización de envíos) | Indirecto: el fundador lo conecta en Claude y exporta resultados a JSON. |
| Campos que devuelve la búsqueda del MCP (costo proveedor, imágenes, proveedor) | **[NO ENCONTRADO]** No documentados públicamente | El importador usa un **archivo de mapeo** que se ajusta con una respuesta real. |
| CSV/JSON propio con datos de la cuenta del fundador | Disponible | Ruta principal de v0.1. |

Desde el entorno de desarrollo en la nube no hay acceso de red a `mcp.dropi.co`, y conectarse requiere el usuario
y la contraseña de Dropi del fundador (que nunca deben compartirse). Por eso la integración directa queda para la
siguiente fase, cuando se confirme el formato real de las respuestas.

## Cómo traer productos hoy (sin scraping)

**A. Plantilla CSV.** En la app: *Importar productos → Descargar plantilla CSV*. Llénala con los productos que
te interesan de tu panel de Dropi y cárgala. Columnas obligatorias: `dropi_id`, `nombre`. Recomendadas:
`costo_proveedor`, `precio_sugerido`, `stock`, `costo_envio` (flete Dropi), `imagenes` (URLs separadas por `|`).

**B. MCP oficial de Dropi conectado en Claude.**
1. En Claude: *Configuración → Conectores → Agregar conector personalizado* → `https://mcp.dropi.co/mcp`.
2. Inicia sesión en la ventana de `oauth.dropi.co` (tu contraseña solo se escribe ahí).
3. No marques "Permitir siempre" para la herramienta de **crear orden**.
4. Pide: *"Busca productos de [categoría] en Dropi y devuélveme la respuesta completa en JSON"*.
5. Guarda la respuesta como `productos.json` y cárgala en la app.
   - Si trae columnas reconocibles (`id`, `name`, `precio_proveedor`…), se importa directo.
   - Si es la respuesta cruda, la app muestra un **mapeo sugerido**. Revísalo, guárdalo como `mapeo.json`
     (ejemplo: `samples/mapeo_mcp_ejemplo.json`, con nombres **hipotéticos**) y cárgalo junto al JSON.

## Lo que necesito del fundador para la integración directa (bloqueo B-1)

1. Un JSON real de la búsqueda de productos del MCP (puede ser de 2–3 productos), para fijar el mapeo verdadero
   y confirmar si incluye costo de proveedor, imágenes, proveedor y stock.
2. Respuesta de Dropi (soporte o `comercial@dropi.co`) a: ¿hay API documentada para dropshippers? ¿está permitido
   usar el MCP desde una aplicación propia? ¿límites de uso?
