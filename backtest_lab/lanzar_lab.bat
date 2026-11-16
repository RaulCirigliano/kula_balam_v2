@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   LAB: INICIANDO BACKTEST LAB CUANTITATIVO (PUERTO 8000)
echo ==========================================================

:: Buscar interprete Python en entornos virtuales
set "PYTHON="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
) else if exist "..\venv\Scripts\python.exe" (
    set "PYTHON=..\venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

:: Abrir navegador en segundo plano
start "" http://127.0.0.1:8000/

:: Iniciar servidor uvicorn
"%PYTHON%" -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
pause
