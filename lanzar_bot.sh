#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$PROJECT_DIR"
PYTHON="${TARGET_DIR}/venv/bin/python"
LOG_FILE="${TARGET_DIR}/multimercado.log"

cd "$TARGET_DIR"

if [[ ! -x "$PYTHON" ]]; then
    notify-send "Error Kula Balam" "No se encontró el entorno virtual en $TARGET_DIR" || true
    echo "No se encontró el entorno virtual: $PYTHON" >&2
    exit 1
fi

# Verificar si ya está corriendo para evitar instancias duplicadas
if pgrep -f "main_multimercado.py" > /dev/null; then
    notify-send "Kula Balam Multimercado" "El bot ya está en ejecución activa." || true
else
    nohup "$PYTHON" main_multimercado.py > "$LOG_FILE" 2>&1 &
    sleep 1
    notify-send "Kula Balam Multimercado" "Bot iniciado correctamente (ETH 1H + NVDA 1D)." || true
fi

# Si se llama desde interfaz gráfica o terminal, abrir ventana de monitoreo
if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal --title="Kula Balam Multimercado - Monitor" -- bash -c "cd '$TARGET_DIR' && ./venv/bin/python main_multimercado.py --status; echo ''; echo '--- Presiona Ctrl+C para salir de los logs en vivo ---'; tail -f '$LOG_FILE'"
fi
