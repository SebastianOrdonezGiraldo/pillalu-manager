# CLAUDE.md — reglas para Claude Code en Pillalú Manager

Idioma: toda la documentación, commits y PRs en **español**. Moneda: **COP**. País: **Colombia** (Mercado Libre `MCO`).

## Roles
- Fundador: decide lo comercial y aprueba cada merge.
- Claude Code: implementa, prueba y documenta.
- ChatGPT: arquitecto y auditor independiente; revisa cada PR antes de que el fundador lo apruebe.

## Reglas obligatorias
1. **No inventar** endpoints, campos, credenciales ni funcionalidades. Todo endpoint usado debe tener su fuente oficial citada en `docs/FEASIBILITY.md` o en el código.
2. Marcar siempre lo **verificado** frente a lo que es **hipótesis**.
3. Solo APIs oficiales y mecanismos autorizados. **Prohibido** el scraping no autorizado y la automatización de navegador para Facebook.
4. **Nunca** publicar, modificar publicaciones reales, crear pedidos reales ni contratar servicios de pago sin autorización explícita del fundador. Modo simulación (`--dry-run`) por defecto.
5. Mercado Libre: desarrollo y pruebas **solo con usuarios de prueba**.
6. **Ningún secreto** en el repositorio. Usar `.env` (ignorado) y `.env.example` solo con nombres. Ver `docs/SECURITY.md`.
7. Nunca usar datos reales de compradores en pruebas o en el repo.
8. Preferir la solución más simple y barata (ver `docs/ARCHITECTURE.md`). No añadir infraestructura sin justificar su retorno.

## Flujo de trabajo
- Ramas: `phase-N/descripcion-corta`. Nunca trabajar directo en `main`.
- Commits pequeños y descriptivos.
- Cada fase termina en un PR con: resumen, cómo probar, riesgos, fuentes consultadas.
- **No hacer merge** sin aprobación del fundador.

## Técnica (a partir de la Fase 1)
- Python 3.12, SQLite, Streamlit. Código en `src/pillalu/`, pruebas en `tests/`.
- Reglas de negocio en `core/` sin acceso a red; integraciones en `adapters/`.
- Pruebas sin red, con datos ficticios en `samples/`.
- Errores 429: backoff exponencial con jitter.
- Comisiones de ML: obtenerlas de `/sites/MCO/listing_prices`, no escribir porcentajes a mano.

## Documentos de referencia
- `docs/FEASIBILITY.md` — qué está verificado y qué no.
- `docs/ARCHITECTURE.md` — diseño del MVP.
- `docs/ROADMAP.md` — fases y dependencias.
- `docs/SECURITY.md` — credenciales, datos personales, acciones irreversibles.
