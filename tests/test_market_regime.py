"""
Módulo: tests/test_market_regime.py
Pruebas unitarias para el clasificador determinista de régimen de mercado (Punto 2).
"""

import pytest
import numpy as np
import pandas as pd
from backend.market_regime import (
    compute_adx,
    compute_ema_slope,
    compute_atr_ratio,
    classify_market_regime,
)


def test_adx_computation():
    """Valida el cálculo de ADX en datos sintéticos con tendencia clara."""
    # 60 velas alcistas continuas (de 100 a 160)
    n = 60
    closes = [100.0 + i for i in range(n)]
    highs = [c + 1.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    df_trend = pd.DataFrame({"high": highs, "low": lows, "close": closes})

    adx = compute_adx(df_trend, period=14)
    assert len(adx) == n
    # En tendencia lineal fuerte, el ADX debe terminar elevado (> 40)
    assert float(adx.iloc[-1]) > 40.0


def test_classify_crisis_on_volatility_spike():
    """Valida que una expansión brusca de ATR gatille 'Crisis'."""
    # 50 velas tranquilas (rango 1) seguidas de velas con rango 10
    n = 60
    highs = [101.0] * 50 + [110.0] * 10
    lows = [100.0] * 50 + [90.0] * 10
    closes = [100.5] * 50 + [95.0] * 10
    df_spike = pd.DataFrame({"high": highs, "low": lows, "close": closes})

    result = classify_market_regime(df_spike)
    assert result["regime"] == "Crisis"
    assert result["atr_ratio"] >= 1.75


def test_classify_tendencia_on_clean_trend():
    """Valida que una serie tendencial limpia clasifique como 'Tendencia'."""
    n = 80
    closes = [100.0 + (i * 0.8) for i in range(n)]
    highs = [c + 0.8 for c in closes]
    lows = [c - 0.4 for c in closes]
    df_trend = pd.DataFrame({"high": highs, "low": lows, "close": closes})

    result = classify_market_regime(df_trend, adx_trend_threshold=25.0)
    assert result["regime"] == "Tendencia"
    assert result["adx"] >= 25.0
    assert result["ema_slope_pct"] > 0


def test_classify_calma_on_flat_market():
    """Valida que un mercado plano/lateral clasifique como 'Calma'."""
    n = 60
    # Oscilaciones muy estrechas [100.0, 100.5]
    closes = [100.0 + (0.5 if i % 2 == 0 else 0.0) for i in range(n)]
    highs = [c + 0.2 for c in closes]
    lows = [c - 0.2 for c in closes]
    df_flat = pd.DataFrame({"high": highs, "low": lows, "close": closes})

    result = classify_market_regime(df_flat, adx_trend_threshold=25.0)
    assert result["regime"] == "Calma"
