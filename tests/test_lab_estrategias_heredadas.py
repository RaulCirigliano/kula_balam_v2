# -*- coding: utf-8 -*-
"""
Pruebas para el contenedor de estrategias heredadas y recuperación en Backtest Lab.
"""
from fastapi.testclient import TestClient
from backtest_lab.server import app

client = TestClient(app)

def test_listar_estrategias_heredadas():
    res = client.get("/api/estrategias_heredadas")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 7

    nombres = [item["archivo"] for item in data]
    assert "cava_ruiz_fractal.py" in nombres
    assert "tres_velas_wyckoff.py" in nombres
    assert "trailing_trend_runner.py" in nombres
    assert "triple_confluencia_4h.py" in nombres
    assert "alex_ruiz_triada.py" in nombres
    assert "nasdaq_araujo_vwap.py" in nombres
    assert "hyenuk_chu_multibagger.py" in nombres

def test_obtener_estrategia_heredada_individual():
    res = client.get("/api/estrategias_heredadas/cava_ruiz_fractal.py")
    assert res.status_code == 200
    data = res.json()
    assert data["archivo"] == "cava_ruiz_fractal.py"
    assert "formula_matematica" in data["code_math"]
    assert "arbitro_ia" in data["code_ia"]
    assert data["dataset_sugerido"] == "binance_BTC_USDT_4h.parquet"

def test_estrategia_heredada_no_existente():
    res = client.get("/api/estrategias_heredadas/inexistente.py")
    assert res.status_code == 404
