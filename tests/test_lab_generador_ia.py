# -*- coding: utf-8 -*-
"""
Pruebas Unitarias para el Sintetizador de Estrategias con IA (Prompt-to-Backtest) en Backtest Lab.
Kula Balam / Backtest Lab
"""

import pytest
from fastapi.testclient import TestClient
from backtest_lab.server import app, DATA_DIR
from backtest_lab.generador_ia import (
    sintetizar_estrategia,
    _generar_template_donchian_squeeze,
    _generar_template_vwap_reversion,
    _generar_template_pullback_fibo
)


def test_sintetizador_donchian_squeeze_sol():
    prompt = "Ruptura de Canal Donchian de 30 periodos en SOL/USDT 4H con compresión de volatilidad (Squeeze)"
    res = sintetizar_estrategia(prompt, motor="auto", ticker_hint="AUTO")
    assert "code_math" in res
    assert "code_ia" in res
    assert "binance_SOL_USDT_4h.parquet" in res["code_math"]
    assert "shift(1)" in res["code_math"]  # Causalidad estricta
    assert "tp_dist = 4.16 * atr" in res["code_math"]  # R:R >= 2.60


def test_sintetizador_vwap_reversion():
    prompt = "Reversión estadística a la media en bandas extremas de VWAP +-1.5 sigma en ETH/USDT 15m"
    res = sintetizar_estrategia(prompt, motor="auto", ticker_hint="AUTO")
    assert "code_math" in res
    assert "code_ia" in res
    assert "binance_ETH_USDT_15m.parquet" in res["code_math"]
    assert "tp_dist = 2.6 * atr" in res["code_math"]  # R:R 1:2.16


def test_sintetizador_fibo_pullback():
    prompt = "Pullback tendencial a EMA 50 en zona dorada fibonacci 0.50 a 0.618 en BTC"
    res = sintetizar_estrategia(prompt, motor="auto", ticker_hint="AUTO")
    assert "code_math" in res
    assert "code_ia" in res
    assert "binance_BTC_USDT_4h.parquet" in res["code_math"]
    assert "tp_dist = 2.86 * atr" in res["code_math"]  # R:R 1:2.20


def test_sintetizador_momentum_qqq_1d():
    prompt = "Estrategia de momentum diario en acciones e indices QQQ 1D con filtro de tendencia EMA 200"
    res = sintetizar_estrategia(prompt, motor="auto", ticker_hint="AUTO")
    assert "code_math" in res
    assert "yf_QQQ_1d.parquet" in res["code_math"]


def test_api_generar_estrategia_ia():
    client = TestClient(app)
    resp = client.post("/api/generar_estrategia_ia", json={
        "prompt": "Estrategia Donchian Squeeze en BTC 4H",
        "motor": "auto",
        "api_key": "",
        "ticker": "AUTO"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "code_math" in data
    assert "code_ia" in data
    assert "def formula_matematica" in data["code_math"]
    assert "def arbitro_ia" in data["code_ia"]
    assert "binance_BTC_USDT_4h.parquet" in data["code_math"]


def test_api_generar_y_ejecutar_en_lab():
    """
    Prueba de integración de extremo a extremo:
    1. Generar estrategia a través del endpoint.
    2. Enviar el código generado al endpoint /api/run.
    3. Verificar que se ejecuta sin errores de compilación ni runtime y produce métricas.
    """
    client = TestClient(app)
    resp_gen = client.post("/api/generar_estrategia_ia", json={
        "prompt": "Donchian Squeeze en ETH 4H",
        "motor": "auto",
        "api_key": "",
        "ticker": "AUTO"
    })
    assert resp_gen.status_code == 200
    data_gen = resp_gen.json()

    code_math = data_gen["code_math"]
    code_ia = data_gen["code_ia"]

    resp_run = client.post("/api/run", json={
        "category": "datos_historicos",
        "ticker": "AUTO",
        "code_math": code_math,
        "code_ia": code_ia
    })
    assert resp_run.status_code == 200
    data_run = resp_run.json()
    assert data_run.get("error") == "" or data_run.get("error") is None
    out = data_run.get("output", "")
    assert "LAB: FÓRMULA MATEMÁTICA PURA vs. FÓRMULA ARBITRADA POR IA ANTIGRAVITY" in out
    assert "MÉTRICA CUANTITATIVA" in out
    assert "AUDITORÍA ANTI-SOBREAJUSTE WALK-FORWARD" in out


def test_adaptar_codigo_existente_a_forex():
    """Prueba que el sintetizador adapte código existente cuando se le solicita conversión a Forex."""
    code_math = """
DATASET = "binance_SOL_USDT_4h.parquet"

def formula_matematica(df):
    df['condicion_compra'] = df['close'] > df['close'].shift(1)
    df['sl_precio'] = df['close'] - 10
    df['tp_precio'] = df['close'] + 20
    return df
"""
    code_ia = """
CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_minimo": 1.15,
    "rvol_4h": 1.15
}

def arbitro_ia(fila, lado, entry, sl, tp):
    return True, "OK", 0
"""
    client = TestClient(app)
    resp = client.post("/api/generar_estrategia_ia", json={
        "prompt": "convierte la estrategia en la ia y el cuadro matematico en una formula para correr en los mercados de fores",
        "motor": "auto",
        "api_key": "",
        "ticker": "AUTO",
        "code_math_existente": code_math,
        "code_ia_existente": code_ia
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "yf_EURUSD_1h.parquet" in data["code_math"]
    assert "yf_EURUSD_1h.parquet" == data["dataset_recomendado"]
    assert '"rvol_minimo": 0.0' in data["code_ia"]
    assert "FOREX" in data["comentario"]

