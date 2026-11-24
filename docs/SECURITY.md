# Seguridad, credenciales y datos personales

## 1. Credenciales que tendrá el sistema

| Credencial | Dónde vive | Nunca |
|---|---|---|
| Mercado Libre `APP_ID` y `CLIENT_SECRET` | `.env` local | En Git, en issues, en chats, en capturas |
| Mercado Libre access token (6 h) y refresh token (un solo uso, 6 meses) | Llavero del sistema (`keyring`) o archivo cifrado fuera del repo | En Git o en logs |
| Sesión OAuth del MCP de Dropi | La gestiona el cliente MCP; el programa **nunca** pide ni guarda la contraseña de Dropi | Guardar la contraseña de Dropi |
| Llave de API de IA (si se autoriza) | `.env` local | En Git |

Reglas:
1. El repositorio solo contiene `.env.example` con **nombres** de variables, sin valores.
2. `.gitignore` excluye `.env*`, bases de datos, exportaciones y CSV.
3. Las credenciales nunca se escriben en logs; los logs enmascaran cualquier valor que empiece por `APP_USR-` o `TG-`.
4. El refresh token de ML se guarda **antes** de usar el nuevo access token (es de un solo uso; perderlo obliga a reautorizar).
5. Si un secreto se filtra: regenerar el Client Secret en el portal de ML (invalida los tokens), cambiar la contraseña de Dropi, revisar el historial de Git y reescribirlo si hace falta.
6. Antes de cada PR se revisa el diff buscando secretos (y se puede activar el escaneo de secretos de GitHub).

## 2. Permisos mínimos

- Mercado Libre: solicitar solo los permisos funcionales necesarios en cada fase (lectura en fases tempranas).
- La cuenta que autoriza en ML debe ser la del administrador, pero el desarrollo usa **usuarios de prueba**.
- Dropi: confirmar en la pantalla de permisos del MCP qué podrá hacer la IA; no elegir "Permitir siempre" para la herramienta **Crear orden**.

## 3. Datos personales (Ley 1581 de 2012 — Habeas Data, Colombia)

Los pedidos contienen nombre, teléfono y dirección de compradores.
- Guardar solo lo necesario para despachar, y solo el tiempo necesario.
- La base de datos vive en el equipo del fundador, fuera del repositorio; disco cifrado recomendado (BitLocker/FileVault).
- Nunca usar datos reales de compradores en pruebas ni en el repositorio: usar `samples/` con datos ficticios.
- La función "huella digital del comprador" del MCP de Dropi trata datos personales: usarla solo para validar pedidos propios.

## 4. Acciones irreversibles

| Acción | Protección |
|---|---|
| Publicar o modificar en Mercado Libre | Modo simulación por defecto; usuarios de prueba hasta autorización |
| Crear pedido en Dropi | Simulación por defecto; confirmación manual por pedido |
| Gastos (APIs de pago, hosting, pauta) | Solo con autorización escrita del fundador |
| Facebook | No se automatiza; publicación manual |

Todas las acciones externas quedan en `audit_log` (fecha, acción, modo, resultado).

## 5. Mecanismos prohibidos

- Scraping de Dropi, Mercado Libre o Facebook fuera de sus APIs oficiales.
- Bots, extensiones o automatización del navegador para publicar en Facebook Marketplace.
- Evadir límites de peticiones, captchas o controles de las plataformas.
- Usar endpoints no documentados (por ejemplo, copias no oficiales de documentación de Dropi).
