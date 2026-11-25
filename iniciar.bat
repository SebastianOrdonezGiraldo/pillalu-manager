@echo off
REM Pillalu Money Engine - inicio en Windows (doble clic). Requiere Python 3.12.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  py -3.12 --version >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] No se encontro Python 3.12.
    echo Instalalo desde https://www.python.org/downloads/ y vuelve a abrir este archivo.
    pause
    exit /b 1
  )
  echo Creando entorno virtual con Python 3.12...
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual.
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)"
if errorlevel 1 (
  echo [ERROR] El entorno .venv no usa Python 3.12, la unica version soportada. Borra la carpeta .venv y vuelve a intentar.
  pause
  exit /b 1
)

if not exist ".venv\installed.ok" (
  echo Instalando dependencias, solo la primera vez...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias. Revisa el mensaje de arriba.
    pause
    exit /b 1
  )
  echo ok> ".venv\installed.ok"
)

".venv\Scripts\python.exe" -m streamlit run app.py
pause
