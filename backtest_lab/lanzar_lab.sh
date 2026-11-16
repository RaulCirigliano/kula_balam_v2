#!/usr/bin/env bash
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Buscar intérprete Python en entornos virtuales locales o superiores
PYTHON=""
if [[ -x "$DIR/.venv/bin/python" ]]; then
    PYTHON="$DIR/.venv/bin/python"
elif [[ -x "$DIR/venv/bin/python" ]]; then
    PYTHON="$DIR/venv/bin/python"
elif [[ -x "$DIR/../venv/bin/python" ]]; then
    PYTHON="$DIR/../venv/bin/python"
elif [[ -x "$DIR/../../trading_ollama/venv/bin/python" ]]; then
    PYTHON="$DIR/../../trading_ollama/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
fi

if [[ -z "$PYTHON" ]]; then
    echo "❌ Error: No se encontró intérprete Python para Backtest Lab." >&2
    exit 1
fi

echo "=========================================================="
echo "  🧪 INICIANDO BACKTEST LAB CUANTITATIVO (PUERTO 8000)"
echo "=========================================================="
echo "Directorio: $DIR"
echo "Python:     $PYTHON"
echo ""

# Abrir el navegador en segundo plano tras breve pausa
(sleep 1.5 && (xdg-open "http://127.0.0.1:8000" 2>/dev/null || sensible-browser "http://127.0.0.1:8000" 2>/dev/null || true)) &

exec "$PYTHON" -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
