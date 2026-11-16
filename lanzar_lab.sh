#!/usr/bin/env bash
set -u

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="${PROJECT_DIR}/backtest_lab"

if [[ ! -d "$LAB_DIR" ]]; then
    echo "❌ Error: No se encontró el directorio backtest_lab en:" >&2
    echo "   $LAB_DIR" >&2
    exit 1
fi

exec bash "${LAB_DIR}/lanzar_lab.sh" "$@"
