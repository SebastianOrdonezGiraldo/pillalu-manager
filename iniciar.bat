@echo off
REM Pillalu Money Engine - inicio en Windows (doble clic)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual por primera vez...
  py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat
if not exist ".venv\Scripts\streamlit.exe" (
  echo Instalando dependencias, solo la primera vez...
  python -m pip install -r requirements.txt
)
streamlit run app.py
pause
