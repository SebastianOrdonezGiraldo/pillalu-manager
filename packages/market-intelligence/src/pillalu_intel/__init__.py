"""Pillalú Money Engine — módulo de inteligencia comercial (responsable: Claude).

Componentes:
- ``dropi``: importación autorizada de productos de Dropi (MCP oficial o CSV).
- ``market``: señales de mercado de Mercado Libre (API oficial, solo lectura).
- ``scoring``: estimación de ganancia y clasificación de oportunidades.
- ``listings``: generación de publicaciones (Mercado Libre y paquete para Facebook).

El módulo no escribe en la base de datos ni tiene interfaz gráfica: eso lo
construye Codex. Todo se intercambia como JSON/CSV o como objetos Python.
"""

__version__ = "0.1.0"
