# Plan de implementación por fases

Principio: cada fase debe **ahorrar tiempo o generar dinero por sí sola**. Ninguna fase depende de que la
siguiente exista. Cada fase termina con un pull request auditado por ChatGPT y aprobado por el fundador.

Leyenda de dependencias: **B-1…B-4** son los bloqueos descritos en `FEASIBILITY.md` §6.

---

## Fase 0 — Viabilidad técnica ✅ (este PR)
- Investigación de Dropi, Mercado Libre, Facebook y logística.
- Documentos: FEASIBILITY, ARCHITECTURE, ROADMAP, SECURITY, CLAUDE.md.
- **Salida:** decisión del fundador sobre el alcance del MVP y gestiones B-1, B-2, B-3.

## Fase 1 — Núcleo de rentabilidad (sin integraciones externas)
**Valor:** saber en segundos si un producto deja ganancia antes de publicarlo.
- Esqueleto del proyecto (Python, SQLite, Streamlit, pruebas).
- Modelo de datos y carga **manual/asistida** de productos (formulario + importación de CSV propio).
- Calculadora de precio y margen con parámetros configurables (comisión, costo fijo, envío, devoluciones).
- Puntaje simple de potencial comercial (margen, precio, stock, categoría).
- Generador de títulos/descripciones **sin costo** (plantillas + reglas de ML).
- Paquete de anuncio para **Facebook Marketplace** (texto + fotos listos para publicar a mano).
- **Depende de:** nada. **Costo:** $0.

## Fase 2 — Conexión con Dropi
**Valor:** dejar de copiar datos de Dropi a mano.
- Cliente MCP para `mcp.dropi.co`: buscar productos, categorías, cotizar envíos.
- Mapeo de los campos que realmente devuelva el MCP; lo que falte se completa a mano.
- Si Dropi entrega API oficial (B-1): adaptador de API con sincronización de stock y precio.
- Creación de pedidos en Dropi **solo en modo simulación** hasta autorización.
- **Depende de:** B-1 (parcialmente; el MCP ya está disponible).

## Fase 3 — Mercado Libre con usuario de prueba
**Valor:** publicar en lote en minutos, con margen real calculado.
- Aplicación de ML (B-3), OAuth con renovación segura del refresh token.
- Usuarios de prueba en `MCO`.
- Predictor de categorías + atributos obligatorios + validación previa.
- Comisiones reales vía `/sites/MCO/listing_prices` integradas a la calculadora.
- Publicación de **ítems de prueba** y actualización de stock/precio (`PUT /items`, API de precios).
- Revisión del modelo **User Products** antes de implementar la creación.
- **Depende de:** B-3. **No publica nada real.**

## Fase 4 — Pedidos y salida a producción controlada
**Valor:** vender de verdad con poco trabajo manual.
- Sondeo de pedidos de ML (`orders/search`), registro de pedidos de Facebook manual.
- Flujo de pedido ML → Dropi según el escenario logístico confirmado (B-2).
- Sincronización periódica de stock Dropi → ML (pausar si stock = 0).
- **Piloto real con 5–10 productos**, solo con autorización escrita del fundador.
- **Depende de:** B-2 y autorización del fundador.

## Fase 5 — Dashboard y devoluciones
- Ventas, ganancia neta, margen por producto/canal, tasa de devoluciones, productos sin rotación.
- Registro de devoluciones y reclamos (API oficial de ML).

## Fase 6 — Mejoras opcionales (solo si el negocio lo justifica)
- Generación de textos con API de IA de pago (B-4).
- Webhooks de ML con un servidor mínimo.
- Catálogo de Meta + tienda propia con checkout para anuncios de catálogo.
- Hosting en la nube para operar sin el computador encendido.

---

## Orden recomendado de trabajo inmediato
1. Fundador: aprobar este PR o pedir cambios.
2. Fundador: gestionar B-2 (logística) — es lo que decide si Mercado Libre es viable.
3. Fundador: gestionar B-1 y B-3 (son gratuitos).
4. Claude: iniciar la Fase 1, que no depende de nadie.
