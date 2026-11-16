# -*- coding: utf-8 -*-
"""
Pruebas Unitarias para el Módulo Adaptador de Estrategias Freqtrade / Lab.
Valida la extracción sintáctica, los shims de compatibilidad (TA-Lib / QtPyLib),
el blindaje de asimetría R:R >= 1:2.0 (Regla 3 de AGENTS.md) y los endpoints API.
"""

import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from backtest_lab.server import app
from backtest_lab.adaptador_freqtrade import (
    extraer_atributos_freqtrade,
    adaptar_codigo_freqtrade,
    listar_biblioteca_freqtrade,
    BIBLIOTECA_DIR,
    COMPATIBILIDAD_SHIM
)


def test_extraer_atributos_freqtrade():
    sample_code = '''
    class AlphaTrendStrategy(IStrategy):
        timeframe = "1h"
        can_short = True
        stoploss = -0.025
        minimal_roi = {
            "0": 0.075,
            "30": 0.05
        }
    '''
    attrs = extraer_atributos_freqtrade(sample_code)
    assert attrs["class_name"] == "AlphaTrendStrategy"
    assert attrs["timeframe"] == "1h"
    assert attrs["can_short"] is True
    assert attrs["stoploss"] == -0.025
    assert attrs["minimal_roi"] == {"0": 0.075, "30": 0.05}


def test_blindaje_asimetria_regla_3():
    # Estrategia con R:R negativo (TP 1% vs SL 2% -> R:R 0.5)
    bad_rr_code = '''
    class ScalperLoss(IStrategy):
        timeframe = "15m"
        stoploss = -0.02
        minimal_roi = {"0": 0.01}
    '''
    res = adaptar_codigo_freqtrade(bad_rr_code)
    assert res["asimetria_ajustada"] is True
    assert res["rr_calculado"] >= 2.0
    assert "formula_matematica" in res["code_math"]
    assert "arbitro_ia" in res["code_ia"]

    # Estrategia que ya cumple R:R >= 2.0 (TP 6% vs SL 2% -> R:R 3.0)
    good_rr_code = '''
    class TrendWinner(IStrategy):
        timeframe = "4h"
        stoploss = -0.02
        minimal_roi = {"0": 0.06}
    '''
    res_good = adaptar_codigo_freqtrade(good_rr_code)
    assert res_good["asimetria_ajustada"] is False
    assert res_good["rr_calculado"] == 3.0


def test_shims_compatibilidad():
    # Crear un DataFrame sintético para probar shims
    np.random.seed(42)
    n = 60
    prices = 100 + np.cumsum(np.random.randn(n))
    df = pd.DataFrame({
        "open": prices,
        "high": prices + 1.5,
        "low": prices - 1.5,
        "close": prices + 0.2,
        "volume": np.random.uniform(100, 500, n)
    })

    # Ejecutar shims en un namespace local
    ns = {"pd": pd, "np": np}
    exec(COMPATIBILIDAD_SHIM, ns)
    ta = ns["ta"]
    qtpylib = ns["qtpylib"]

    ema20 = ta.EMA(df, timeperiod=20)
    assert len(ema20) == n
    assert not ema20.isna().all()

    rsi14 = ta.RSI(df, timeperiod=14)
    assert len(rsi14) == n

    atr14 = ta.ATR(df, timeperiod=14)
    assert len(atr14) == n

    upper, mid, lower = ta.BBANDS(df, timeperiod=20)
    assert (upper.dropna() >= mid.dropna()).all()
    assert (mid.dropna() >= lower.dropna()).all()

    # QtPyLib shims
    tp = qtpylib.typical_price(df)
    assert len(tp) == n

    bb = qtpylib.bollinger_bands(tp, window=20, stds=2)
    assert "lower" in bb.columns and "mid" in bb.columns and "upper" in bb.columns

    cross = qtpylib.crossed_above(df["close"], df["open"])
    assert len(cross) == n


def test_biblioteca_freqtrade_archivos():
    biblioteca = listar_biblioteca_freqtrade()
    assert len(biblioteca) >= 3

    for item in biblioteca:
        archivo = item["archivo"]
        path = BIBLIOTECA_DIR / archivo
        assert path.exists(), f"El archivo {archivo} declarado en biblioteca no existe en disco."
        raw_code = path.read_text(encoding="utf-8")
        assert "class " in raw_code
        assert "IStrategy" in raw_code


def test_api_freqtrade_endpoints():
    client = TestClient(app)

    # 1. GET /api/freqtrade/biblioteca
    r_bib = client.get("/api/freqtrade/biblioteca")
    assert r_bib.status_code == 200
    data_bib = r_bib.json()
    assert isinstance(data_bib, list)
    assert len(data_bib) >= 3

    # 2. GET /api/freqtrade/cargar/{archivo}
    r_load = client.get("/api/freqtrade/cargar/asymmetric_bench_strategy.py")
    assert r_load.status_code == 200
    data_load = r_load.json()
    assert "code_math" in data_load
    assert "code_ia" in data_load
    assert data_load["clase_origen"] == "AsymmetricBenchStrategy"

    # 3. GET /api/freqtrade/cargar/{archivo_inexistente} -> 404
    r_404 = client.get("/api/freqtrade/cargar/no_existe.py")
    assert r_404.status_code == 404

    # 4. POST /api/freqtrade/adaptar
    custom_code = '''
    class UserCommunityStrategy(IStrategy):
        timeframe = "1h"
        stoploss = -0.03
        minimal_roi = {"0": 0.08}
    '''
    r_adapt = client.post("/api/freqtrade/adaptar", json={"codigo": custom_code, "activo": "AUTO"})
    assert r_adapt.status_code == 200
    data_adapt = r_adapt.json()
    assert data_adapt["clase_origen"] == "UserCommunityStrategy"
    assert data_adapt["rr_calculado"] >= 2.0

    # 5. POST /api/freqtrade/adaptar con código vacío -> 400
    r_empty = client.post("/api/freqtrade/adaptar", json={"codigo": ""})
    assert r_empty.status_code == 400
