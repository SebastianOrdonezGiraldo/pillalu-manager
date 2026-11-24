# Fase 0 — Investigación de viabilidad técnica

Fecha de la investigación: **24 de noviembre de 2026**. Autor: Claude Code. Auditor: ChatGPT.

## Cómo leer este documento

Cada afirmación lleva una etiqueta:

| Etiqueta | Significado |
|---|---|
| **[VERIFICADO]** | Leído en la documentación oficial citada, en la fecha de la investigación. |
| **[PARCIAL]** | La fuente oficial lo menciona, pero sin detalle técnico suficiente para implementar. |
| **[HIPÓTESIS]** | Inferencia razonable o dato de fuentes no oficiales. Debe confirmarse antes de construir sobre ello. |
| **[NO ENCONTRADO]** | Se buscó y no hay fuente oficial que lo respalde. |

No se probó ningún endpoint con credenciales reales ni se hizo ninguna publicación o pedido.
Los endpoints de Mercado Libre se citan tal como aparecen en su documentación; ninguno fue inventado.

---

## Resumen ejecutivo

| Área | Viabilidad | Conclusión corta |
|---|---|---|
| Dropi → catálogo (productos, precios, stock, imágenes, proveedores) | 🟡 **Media, con bloqueo** | Dropi tiene un **MCP oficial** con búsqueda de productos, pero no hay documentación pública de una API REST. Precio de proveedor, imágenes y proveedor **no están confirmados** en el MCP. |
| Dropi → crear pedidos | 🟢 **Alta** (vía MCP) | El MCP oficial permite crear y consultar órdenes, cotizar envíos y ver transportadoras. |
| Mercado Libre Colombia (publicar, stock, precio, pedidos, comisiones) | 🟢 **Alta** | API oficial completa, OAuth 2.0, usuarios de prueba, calculadora de comisiones por API, notificaciones. |
| Facebook Marketplace | 🔴 **Baja para automatizar** | No hay API pública verificada para que un vendedor individual publique en Marketplace. Se recomienda **publicación asistida** (la herramienta prepara el anuncio; la persona lo publica). |
| Logística Dropi ↔ Mercado Libre | 🟡 **Incierta — principal riesgo del negocio** | Mercado Libre empuja a Mercado Envíos 2 (etiqueta de Mercado Libre). Falta confirmar si los proveedores de Dropi pueden despachar con esa etiqueta o si se puede publicar con envío propio. |

**Recomendación:** construir primero el núcleo que ya es viable y da dinero sin depender de lo incierto:
**calculadora de rentabilidad + catálogo local + generador de anuncios con IA + publicación en Mercado Libre
con usuario de prueba**. En paralelo, el fundador resuelve con Dropi y con Mercado Libre las dos preguntas
bloqueantes (acceso a datos de catálogo y logística). Ver `ROADMAP.md`.

---

## 1. Dropi

### 1.1 Fuentes consultadas

| Fuente | Tipo | Resultado |
|---|---|---|
| https://dropi.co/blog/mcp-de-dropi-guia-oficial | Oficial (blog Dropi, 6 nov 2026) | Leída |
| https://dropi.co/mcp-claude | Oficial (landing del MCP) | Leída |
| https://dropi.co/integraciones | Oficial | Leída |
| https://dropi.co/herramientas | Oficial | Leída (calculadoras, no API) |
| https://dev.dropi.co/ | Dominio de Dropi | Responde, pero **sin contenido** (página vacía) |
| Copias en Scribd de "Documentación API de Dropi" | **No oficial** (subidas por terceros) | No se pudo leer el contenido; no se usan como fuente |

### 1.2 Servidor MCP oficial de Dropi

- **[VERIFICADO]** URL del servidor: `https://mcp.dropi.co/mcp`. Se agrega como conector personalizado en el cliente de IA (Claude: Configuración → Conectores → Agregar conector personalizado).
- **[VERIFICADO]** Autenticación: inicio de sesión en `oauth.dropi.co` con el correo y la contraseña de Dropi, más código 2FA si está activo. La contraseña solo se introduce en `oauth.dropi.co`. No hay token de API ni llave de integración.
- **[VERIFICADO]** Una cuenta solo puede tener **una sesión abierta** a la vez.
- **[VERIFICADO]** Disponible en los países donde opera Dropi, incluida Colombia.
- **[VERIFICADO]** Capacidades anunciadas (nombres comerciales, no identificadores técnicos):

| Área | Capacidad | Lectura / escritura |
|---|---|---|
| Pedidos | Crear orden | **Escritura** |
| Pedidos | Listar órdenes (filtros por fecha, cliente, zona), detalle de orden, estados de orden | Lectura |
| Envíos | Cotizar envío, transportadoras, departamentos y ciudades | Lectura |
| Catálogo | Buscar productos ("para identificar artículos y stock disponible"), listar categorías | Lectura |
| Comprador | "Huella digital" del comprador por teléfono (historial de entregas efectivas) | Lectura |

- **[NO ENCONTRADO]** Los nombres técnicos de las herramientas y sus esquemas. Se obtienen al conectar el MCP (`tools/list`); no se documentan públicamente.
- **[NO ENCONTRADO]** Confirmación de que la búsqueda de productos devuelve **precio de proveedor, precio sugerido, imágenes, proveedor y variantes**. Es lo más importante para Pillalú y está sin confirmar.
- **[NO ENCONTRADO]** Precio o costo del MCP; límites de uso; duración del token OAuth.
- **[HIPÓTESIS]** Usar el MCP desde un programa propio (no desde un chat) es técnicamente posible con un cliente MCP, pero requiere el flujo OAuth interactivo de Dropi. Hay que confirmar que Dropi lo permite y que la sesión dura lo suficiente.

### 1.3 API REST de Dropi

- **[PARCIAL]** Dropi tiene integraciones oficiales con Shopify, WooCommerce y Tiendanube a través de su plugin **Dropify**, que "sincroniza productos, inventarios y pedidos". Para WooCommerce, el FAQ oficial menciona un **token** creado en Dropi que se pega en Dropify. Esto indica que existe una API interna de integraciones, pero **no está documentada públicamente**.
- **[NO ENCONTRADO]** Documentación pública de endpoints, URL base, cabeceras de autenticación o webhooks. `dev.dropi.co` está vacío.
- **[NO ENCONTRADO]** Integración oficial Dropi ↔ Mercado Libre o Dropi ↔ Facebook. La página de integraciones no la lista.

**Decisión:** no se construirá nada sobre endpoints de Dropi que no estén documentados oficialmente.
Las copias de Scribd no cuentan como fuente.

### 1.4 Métodos autorizados para obtener datos de Dropi (de mejor a peor)

| # | Método | Estado | Comentario |
|---|---|---|---|
| A | API oficial de Dropi con token de integración entregado por Dropi | **Pendiente**: hay que pedirla | Lo ideal para sincronizar stock y precio. Requiere que Dropi entregue documentación y autorización escrita. |
| B | MCP oficial (`mcp.dropi.co`) | **Disponible** | Sirve para buscar productos, crear pedidos y cotizar envíos. Falta confirmar qué campos devuelve. |
| C | Exportación manual desde el panel de Dropi (si existe) o captura manual asistida | **[HIPÓTESIS]** | Plan de contingencia: el fundador elige productos y la herramienta los completa y valora. |
| ✗ | Scraping del panel o de la tienda de Dropi | **Descartado** | Prohibido por las reglas del proyecto. |

**Acción para el fundador (bloqueo B-1):** escribir a Dropi (soporte o `comercial@dropi.co`) y preguntar:
1. ¿Existe API para dropshippers con documentación oficial? ¿Cómo se obtiene el token?
2. ¿La búsqueda de productos del MCP devuelve precio de proveedor, precio sugerido, imágenes, proveedor, variantes y stock?
3. ¿Está permitido usar el MCP desde una aplicación propia (no solo desde un chat)?
4. ¿Hay límites de uso?

---

## 2. Mercado Libre Colombia (site `MCO`, moneda COP)

### 2.1 Fuentes consultadas (todas oficiales, `developers.mercadolibre.com.co/es_ar/…`)

| Página | Última actualización indicada |
|---|---|
| `autenticacion-y-autorizacion` | 15/07/2026 |
| `publica-productos` | 09/01/2026 |
| `producto-sincroniza-modifica-publicaciones` | 21/10/2026 |
| `comision-por-vender` (Costos por vender) | 03/09/2026 |
| `tipos-de-publicacion-y-actualizaciones-de-articulos` | 01/06/2026 |
| `mercadoenvios-modo-1` | 06/02/2026 |
| `mercadoenvios-modo-2` | 06/07/2026 |
| `envios-flex` | 15/10/2026 |
| `envios-personalizados` | 13/03/2026 |
| `productos-recibe-notificaciones` | 03/11/2026 |
| `gestiona-ventas` (Órdenes) | 21/09/2026 |
| `user-products` | 17/06/2026 |
| `realiza-pruebas` | 30/12/2025 |
| `rate-limit-error-429` | 05/05/2026 |
| `mcp-server` | 10/09/2026 |

Las páginas de ayuda para vendedores (`mercadolibre.com.co/ayuda`) bloquean lectores automáticos, por lo
que **los porcentajes de comisión no se leyeron ahí**. Se obtendrán por API (ver 2.5).

### 2.2 Autenticación — [VERIFICADO]

- OAuth 2.0, flujo **Authorization Code (server side)**, con PKCE opcional.
- URL de autorización (el ejemplo oficial es de Argentina; para Colombia se cambia el dominio por el del país):
  `https://auth.mercadolibre.com.ar/authorization?response_type=code&client_id=$APP_ID&redirect_uri=$YOUR_URL`
  → **[HIPÓTESIS]** para Colombia: `https://auth.mercadolibre.com.co/authorization?...` (la documentación dice "cambiar el .com.ar por el dominio del país").
- Canje y renovación: `POST https://api.mercadolibre.com/oauth/token` con `grant_type=authorization_code` o `grant_type=refresh_token`.
- El **access token dura 6 horas**. El **refresh token es de un solo uso**, cada renovación entrega uno nuevo, y caduca a los **6 meses**.
- El `redirect_uri` debe coincidir **exactamente** con el registrado en la aplicación.
- El usuario que autoriza debe ser el **administrador** de la cuenta (no un colaborador).
- El token se invalida si cambia la contraseña, si se regenera el Client Secret, si se revocan permisos o tras **4 meses sin uso**.
- El token se envía siempre por cabecera: `Authorization: Bearer …`.

### 2.3 Pruebas sin riesgo — [VERIFICADO]

- **No existe sandbox.** Se prueba en producción con **usuarios de prueba** (`POST https://api.mercadolibre.com/users/test_user` con `{"site_id": "MCO"}`).
- Máximo 10 usuarios de prueba por cuenta; se borran tras 60 días sin actividad.
- Los artículos de prueba deben titularse "Item de Prueba - Por favor, NO OFERTAR" y no usar `gold`/`gold_premium`.
- Las cuentas personales **no** deben usarse para pruebas.
- El MCP oficial de Mercado Libre **no funciona con usuarios de prueba**.

👉 Esto encaja con la regla "no publicar nada real": todo el desarrollo de publicación se hará con usuarios de prueba.

### 2.4 Publicación — [VERIFICADO]

- Crear: `POST https://api.mercadolibre.com/items`. Consultar: `GET https://api.mercadolibre.com/items/$ITEM_ID`.
- Campos usados en los ejemplos oficiales: `title`, `category_id`, `price`, `currency_id`, `available_quantity`, `buying_mode` (`buy_it_now`), `listing_type_id`, `condition`/atributo `ITEM_CONDITION`, `pictures` (lista de URLs `source`), `attributes`, `sale_terms` (garantía), `shipping`.
- La **categoría** se debe elegir con el predictor de categorías; si se publica en otra categoría distinta a la recomendada, la publicación "será moderada". Para publicación masiva, Mercado Libre recomienda validar categorías antes.
- **Título**: sin stock, sin envío gratis, sin color si hay variantes, sin marcas de terceros salvo compatibilidad. Límite por categoría (`max_title_length`). En Colombia el título se complementa con precio por unidad de medida.
- La **descripción** se crea después del ítem.
- **Imágenes**: hasta 6 URLs públicas en `pictures`.
- **Atención — cambio en curso:** Mercado Libre está migrando al modelo **User Products** ("para nuevos desarrollos de flujos de publicación, es necesario llevar en consideración la nueva manera de publicar"). En ese modelo el título "cambiará de función" y no deberá enviarse. **[PARCIAL]** Las fechas de activación por país deben revisarse en la documentación de User Products antes de implementar.
- `condition` será reemplazado por el atributo `ITEM_CONDITION`.
- **Publicación masiva:** **[NO ENCONTRADO]** endpoint de carga por lotes para crear ítems. La masividad se logra con llamadas individuales a `POST /items` respetando el límite de peticiones.

### 2.5 Comisiones y costos — [VERIFICADO el mecanismo, no los valores]

- Calculadora oficial por API, de solo lectura:
  `GET https://api.mercadolibre.com/sites/$SITE/listing_prices?category_id=…&price=…&currency_id=…&logistic_type=…&shipping_modes=…&listing_type_id=…`
- Devuelve `sale_fee_amount`, `sale_fee_details` (`percentage_fee`, `fixed_fee`, `financing_add_on_fee`) y costos por publicar.
- `sale_fee_amount` **ya incluye** el `fixed_fee`. En el ejemplo oficial: precio 5.000, `percentage_fee` 36 % (1.800) + `fixed_fee` 200 = `sale_fee_amount` 2.000. No se debe restar el costo fijo dos veces.
- Desde el **23/03 en Colombia**, el `fixed_fee` depende del **tipo de logística**; si no se envían `logistic_type` y `shipping_mode`, el valor calculado **no coincidirá** con lo cobrado.
- Tipos de publicación para marketplace: `free`, `gold_special`, `gold_pro` (puede variar por sitio). Listado por sitio: `GET /sites/$SITE_ID/listing_types`.

👉 La herramienta **no tendrá porcentajes escritos a mano**: consultará esta API para cada producto y categoría.

### 2.6 Actualizar precio e inventario — [VERIFICADO]

- `PUT https://api.mercadolibre.com/items/$ITEM_ID` con `available_quantity`, precio, imágenes, envío.
- La **descripción** no va en ese PUT: se edita con `PUT https://api.mercadolibre.com/items/$ITEM_ID/description?api_version=2` y cuerpo `plain_text` (página oficial `descripcion-de-articulos`).
- `available_quantity = 0` pausa la publicación (`paused` / `out_of_stock`); volver a > 0 la reactiva. **Solo** funciona si el ítem es `condition = new` y no es `listing_type = free`; en otro caso hay que pausar cambiando el `status`.
- Con ventas no se puede cambiar el título.
- **[PARCIAL — ambigüedad a resolver]** La documentación dice: "A partir del 18 de marzo de 2026, las solicitudes que actualicen únicamente el campo price serán rechazadas con un 400", dentro de un aviso sobre la automatización de precios. Para precio debe usarse la **API de precios** (`api-de-precios`). Hay que leer esa página antes de implementar la sincronización de precios.
- Con User Products y stock multi-origen, el stock se gestiona por `user-products/$ID/stock`.

### 2.7 Pedidos, notificaciones, devoluciones — [VERIFICADO]

- `GET /orders/$ORDER_ID`, `GET /orders/search?seller=$SELLER_ID&order.status=paid`, `GET /orders/$ORDER_ID/shipments`.
- **Packs:** toda compra está asociada a un `pack_id`, y un pack puede tener **varias órdenes** (relación 1 a N) con un solo envío. Un checkout con varios productos debe convertirse en **un** pedido en Dropi, no en varios (`GET /packs/$PACK_ID`).
- **Contrato de envíos en migración:** la vista actual de `orders/$ORDER_ID/shipments` se depreca desde finales de septiembre de 2026. La "Hosted View" **siempre devuelve un arreglo** (la vista actual devuelve un objeto) y los datos del destinatario (`receiver_name`, `receiver_phone`) requieren la cabecera `X-Api-Version: 2`. Implementar directamente contra el contrato nuevo.
- Notificaciones por **webhook (HTTP POST a una URL pública)** configurada en la aplicación, con tópicos como `orders_v2`, `items`, `shipments`, `questions`, `messages`, `items_prices`, `stock-location`, `post_purchase`.
- Existen secciones oficiales de **reclamos**, **devoluciones** y **mensajería posventa**.
- **Límite de peticiones**: error 429; el control es principalmente por Client ID y por endpoint; se recomienda backoff exponencial con jitter. No se publica un número general (Flex: 1000 rpm).

**Decisión para el MVP:** consultar pedidos por **sondeo periódico** (`orders/search`) en lugar de webhooks, para no necesitar un servidor público.

### 2.8 Envíos en Colombia — [VERIFICADO]

| Modalidad | Disponible en Colombia | Quién entrega | Implicación para Dropi |
|---|---|---|---|
| ME2 `drop_off` / `xd_drop_off` / `cross_docking` | Sí | Mercado Libre (el vendedor entrega el paquete con **etiqueta de ML**) | El proveedor de Dropi tendría que despachar con la etiqueta de ML |
| ME2 Flex (`self_service`) | Sí | El vendedor, con la **app Flex de ML** (no integrable) | No compatible con transportadoras de Dropi |
| ME2 Full (`fulfillment`) | No se confirmó para Colombia | Bodega de ML | Requiere stock propio en bodega; no es dropshipping |
| ME1 | Sí, para productos **pesados/voluminosos** no elegibles a ME2; requiere asesor comercial | El vendedor o un tercero | Solo aplica a una franja pequeña de productos |
| Personalizado (`custom` / `not_specified`) | Existe en la API | El vendedor | Ver nota |

Notas oficiales relevantes:
- "Si el usuario tiene configurada la opción Mercado Envíos por defecto, todas sus publicaciones se crearán bajo esa modalidad, con excepción de aquellas que tengan una categoría que no la soporte."
- "En países donde Mercado Envíos se encuentra activo, solo puedes agregar envíos custom gratis en categorías que no acepten Mercado Envíos."
- Etiquetas descargables por API: `GET /shipment_labels?shipment_ids=…&response_type=pdf`.

### 2.9 MCP de Mercado Libre — [VERIFICADO]

Existe un servidor MCP oficial (OAuth desde el cliente). No funciona con usuarios de prueba, así que **no sirve para desarrollar sin riesgo**; la integración del MVP usará la API REST.

---

## 3. Facebook Marketplace

### 3.1 Fuentes consultadas

| Fuente | Tipo | Resultado |
|---|---|---|
| https://developers.facebook.com/devpolicy/ | Oficial (actualizada 3 feb 2026) | Leída |
| https://developers.facebook.com/documentation/ads-commerce/commerce-platform | Oficial (29 jun 2026) | Leída |
| …/commerce-platform/catalog y …/setup-checkout-url | Oficial | Leídas |
| Páginas de ayuda y términos en `facebook.com` | Oficial | **Bloqueadas** para lectura automática |
| spottableapp.com, autolander.ai | **No oficiales** | Leídas solo como contexto |

### 3.2 Hallazgos

- **[VERIFICADO]** La política de desarrolladores menciona una "Marketplace Platform" para **socios tecnológicos** (Tech Providers) y la Lead Generation API de Marketplace. No describe una API de publicación abierta para vendedores individuales.
- **[HIPÓTESIS, fuentes no oficiales]** Las APIs de socios de Marketplace están limitadas a inventario de **vehículos e inmuebles** de socios aprobados.
- **[NO ENCONTRADO]** Ninguna API oficial que permita a una persona o pequeña empresa publicar artículos de consumo en Marketplace de forma automática.
- **[VERIFICADO]** La política exige respetar "los límites que hemos establecido en la funcionalidad del producto" y obtener consentimiento antes de actuar en nombre de alguien. Bots, extensiones o automatización del navegador para publicar en Marketplace **no son mecanismos autorizados** y ponen en riesgo la cuenta.
- **[VERIFICADO]** Existe el **Commerce Platform** (Graph API) con **catálogos** y su API por lotes, que alimentan Shops, Marketplace e Instagram Shopping. Los anuncios de Shops usan **checkout externo**: el comprador termina la compra en **tu sitio web** (`checkout URL`).
- **[NO ENCONTRADO]** Confirmación de que Shops o el catálogo aparezcan en Marketplace **en Colombia**.

### 3.3 Conclusión para Facebook

La automatización completa **no es viable** por medios autorizados. La opción realista es:

1. **Publicación asistida (MVP):** la herramienta genera un "paquete de anuncio" por producto (título, precio, descripción, fotos listas para subir, categoría sugerida). El fundador lo publica manualmente en 1–2 minutos. Ahorra la mayor parte del trabajo sin riesgo de bloqueo.
2. **Futuro (opcional):** catálogo de Meta vía API + tienda web propia con checkout, para anuncios de catálogo e Instagram. Implica costos (dominio, hosting, pauta) y solo se evalúa si el canal demuestra rentabilidad.

Los pedidos de Facebook se registrarán manualmente en la herramienta y se crearán en Dropi (vía MCP, con confirmación).

---

## 4. Compatibilidad logística Dropi ↔ Mercado Libre

Este es el **punto crítico del negocio**.

| Pregunta | Estado |
|---|---|
| ¿Mercado Libre Colombia empuja a ME2 en las categorías que lo soportan? | **[VERIFICADO]** Sí, si la cuenta tiene ME2 por defecto. |
| ¿ME2 requiere la etiqueta de Mercado Libre y entregar en punto o colecta de ML? | **[VERIFICADO]** Sí (`drop_off`, `xd_drop_off`, `cross_docking`). |
| ¿Puede un proveedor de Dropi despachar un paquete con etiqueta de Mercado Libre (en vez de la guía de Dropi)? | **[NO ENCONTRADO]** Debe preguntarse a Dropi. |
| ¿Puede una cuenta nueva en Colombia publicar con envío personalizado en categorías que aceptan ME2? | **[NO ENCONTRADO]** La documentación sugiere que es restringido. Debe confirmarse con Mercado Libre. |
| ¿Los tiempos de despacho de Dropi cumplen lo que exige ME2 para no dañar la reputación? | **[HIPÓTESIS]** Riesgo alto; depende del proveedor. |
| Dropi trabaja mucho con **pago contra entrega**; Mercado Libre cobra **por adelantado**. | **[HIPÓTESIS]** Esto es favorable (no hay rechazos de pago contra entrega), pero el flujo de pedido en Dropi debe ser "con recaudo" o "sin recaudo" según corresponda. Confirmar con Dropi. |

**Escenarios:**

- **Escenario A (ideal):** Dropi permite despachar con etiqueta de ML. Flujo: venta en ML → crear pedido en Dropi "sin recaudo" con la etiqueta de ML → proveedor despacha → ML entrega.
- **Escenario B:** Mercado Libre permite envío personalizado en las categorías elegidas. Flujo: venta en ML → pedido en Dropi con transportadora de Dropi → se informa el seguimiento al comprador. Riesgo de reputación por tiempos.
- **Escenario C:** ninguno es posible. Mercado Libre queda limitado a productos ME1 (voluminosos) o se descarta, y el foco pasa a Facebook.

**Acción para el fundador (bloqueo B-2):** confirmar con Dropi y con Mercado Libre (asesor o soporte de vendedores) cuál escenario aplica. **Ningún pedido real debe tomarse en Mercado Libre antes de esta confirmación.**

---

## 5. Riesgos

### Técnicos
| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Dropi no ofrece API documentada ni datos de precio en el MCP | Media | Alto | Contingencia C (ingreso asistido); pedir acceso formal |
| Sesión única del MCP de Dropi: el programa y el panel web se cierran sesión mutuamente | Media | Medio | Ejecuciones cortas y programadas; confirmar con Dropi |
| Cambios de Mercado Libre (User Products, API de precios) rompen la integración | Alta | Medio | Capa de adaptadores; revisar "Novedades" del portal en cada fase |
| Límites de peticiones (429) en publicación masiva | Media | Bajo | Backoff exponencial, colas, lotes pequeños |
| Refresh token de un solo uso perdido → hay que reautorizar | Media | Bajo | Guardar el nuevo token de forma atómica antes de usarlo |

### Comerciales
| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Logística incompatible Dropi ↔ ML (sección 4) | **Alta** | **Alto** | Bloqueo B-2 antes de vender |
| Reputación en ML dañada por demoras de proveedores | Media | Alto | Elegir proveedores con buen historial; empezar con pocos productos |
| Margen comido por comisiones y costo fijo | Media | Alto | Calculadora con datos reales de `listing_prices` antes de publicar |
| Productos con marca de terceros o restringidos → moderación | Media | Medio | Validación de títulos y categorías antes de publicar |
| Stock desactualizado → venta sin inventario | Media | Alto | Sincronización frecuente; margen de seguridad de stock |

### Seguridad y cumplimiento
| Riesgo | Mitigación |
|---|---|
| Fuga de credenciales (Client Secret de ML, tokens, sesión de Dropi) | Ver `SECURITY.md`: `.env` local, nada en Git, permisos mínimos |
| Datos personales de compradores (nombre, teléfono, dirección) | Ley 1581 de 2012 (Habeas Data, Colombia): guardar lo mínimo, local y cifrado en disco |
| Automatización no autorizada en Facebook → bloqueo de cuenta | Solo publicación asistida |
| Acción irreversible por error (pedido real en Dropi, publicación real) | Modo "simulación" por defecto y confirmación explícita |

---

## 6. Bloqueos que requieren al fundador

| ID | Bloqueo | Con quién | Bloquea |
|---|---|---|---|
| **B-1** | Acceso y campos de datos de catálogo de Dropi (API, MCP, precios, imágenes) | Dropi | Importación automática (Fase 2) |
| **B-2** | Logística Dropi ↔ Mercado Libre (etiqueta ML o envío propio) | Dropi + Mercado Libre | Ventas reales en ML |
| **B-3** | Crear aplicación en el portal de desarrolladores de ML (gratis) y entregar App ID / Secret de forma segura | Fundador | Integración ML (Fase 3) |
| **B-4** | Autorizar (o no) el uso de una API de IA de pago para generar textos | Fundador | Generación automática con IA (Fase 1 usa alternativa sin costo) |
