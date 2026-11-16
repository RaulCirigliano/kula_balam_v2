# -*- coding: utf-8 -*-
"""
Pruebas Unitarias para la Auditoría de Escalado Cuantitativo por Slots en Backtest Lab.
Kula Balam / Backtest Lab
"""

import pytest
from fastapi.testclient import TestClient
from backtest_lab.server import app, generar_script_ejecucion, DATA_DIR


def test_generar_script_ejecucion_con_modo_escalado():
    code_math = """
def formula_matematica(df, i):
    return False, "LONG", 0.0, 0.0
"""
    script = generar_script_ejecucion(
        code_math=code_math,
        code_ia="",
        modo_escalado=True,
        slot_capital=25.0,
        riesgo_base=0.50,
        riesgo_escalado=1.00,
        umbral_escalado=35.0,
        umbral_desescalado=30.0,
    )
    assert "MODO_ESCALADO = True" in script
    assert "SLOT_CAPITAL = float(25.0)" in script
    assert "RIESGO_BASE = float(0.5)" in script
    assert "RIESGO_ESCALADO = float(1.0)" in script
    assert "UMBRAL_ESCALADO = float(35.0)" in script
    assert "AUDITORÍA CUANTITATIVA DE ESCALADO DE RIESGO EN SLOT" in script


def test_api_auditar_escalado_sin_codigo():
    client = TestClient(app)
    resp = client.post("/api/auditar_escalado", json={
        "category": "datos_historicos",
        "ticker": "AUTO",
        "code_math": "",
        "slot_capital": 25.0,
        "riesgo_base": 0.50,
        "riesgo_escalado": 1.00
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "No se recibió código de fórmula matemática" in data.get("error", "")


def test_api_auditar_escalado_ejecucion_real():
    from backtest_lab.server import BASE_DIR
    client = TestClient(app)
    # Usar fórmula real de prueba sobre ETH 4H
    math_path = BASE_DIR / "estrategias_math" / "squeeze_dual_eth_4h.py"
    if not math_path.exists():
        pytest.skip("Fórmula squeeze_dual_eth_4h.py no encontrada en disco")

    code_math = math_path.read_text(encoding="utf-8")
    resp = client.post("/api/auditar_escalado", json={
        "category": "datos_historicos",
        "ticker": "binance_ETH_USDT_4h.parquet",
        "code_math": code_math,
        "code_ia": "",
        "slot_capital": 25.0,
        "riesgo_base": 0.50,
        "riesgo_escalado": 1.00,
        "umbral_escalado": 35.0,
        "umbral_desescalado": 30.0
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("error") == "" or data.get("error") is None
    out = data.get("output", "")
    assert "AUDITORÍA CUANTITATIVA DE ESCALADO DE RIESGO EN SLOT" in out
    assert "COMPUERTA 1: SUPERVIVENCIA & DD" in out
    assert "COMPUERTA 2: ROBUSTEZ OOS CIEGA" in out
    assert "COMPUERTA 3: CAPACIDAD DE TRACCIÓN" in out
    assert "DICTAMEN DE AUDITORÍA" in out
