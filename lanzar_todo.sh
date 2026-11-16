#!/usr/bin/env bash
set -u

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PROJECT_DIR}/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "❌ Error: No se encontró el entorno virtual de Kula Balam en:" >&2
    echo "   $PYTHON" >&2
    echo ""
    read -rp "Presione [Enter] para salir..." || true
    exit 1
fi

echo "=========================================================="
echo "  🚀 INICIANDO KULA BALAM, MONITOR DEL MERCADO & BACKTEST LAB"
echo "=========================================================="

"$PYTHON" "$PROJECT_DIR/lanzar_todo.py" "$@"
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
    echo ""
    echo "⚠️ El lanzador finalizó con código de error: $EXIT_CODE"
    read -rp "Presione [Enter] para cerrar esta ventana..." || true
fi

exit $EXIT_CODE


