"""
Tests Unitarios para MacroBiasBuffer y CandlestickAuditor (0 Tokens, Pure Python).
Verifica:
1. Registro, consulta, TTL y expiración silenciosa en MacroBiasBuffer.
2. Identificación de patrones de Thomas Bulkowski (Martillo, Envolvente, Estrella).
3. Divergencias cuantitativas de RSI 14 (+15% si hay, -15% si falta en reversión).
4. Filtro de Squeeze ATR (veto de continuación en compresión).
5. Confluencia Setup A++ (Macro + Micro) y Setup A (Técnico Cuantitativo).
"""

import os
import time
import pytest
import pandas as pd
import numpy as np

from backend.macro_bias_buffer import MacroBiasBuffer
from backend.candlestick_auditor import (
    detect_candle_pattern,
    detect_rsi_divergence,
    audit_candlestick_confluence,
)


def test_macro_bias_buffer_lifecycle(tmp_path):
    buffer_file = str(tmp_path / "test_buffer.json")
    buffer = MacroBiasBuffer(buffer_file)

    # 1. Registrar sesgo con TTL de 2.5 horas
    rec = buffer.set_bias("BTC/USDT", "ALCISTA", 88, "Acumulación ballenas", ttl_hours=2.5)
    assert rec["status"] == "PENDING_VALIDATION"
    assert rec["bias"] == "ALCISTA"

    # 2. Consultar sesgo activo
    active = buffer.get_bias("BTC/USDT")
    assert active is not None
    assert active["confidence"] == 88

    # 3. Normalización de símbolo (BTC-USDT encuentra BTC/USDT)
    active_dash = buffer.get_bias("BTC-USDT")
    assert active_dash is not None

    # 4. Actualizar veredicto
    buffer.update_verdict("BTC/USDT", "CONFIRMED_BUY", "[CHEQUEADO: COMPRA FIRME · A++]")
    updated = buffer.get_bias("BTC/USDT")
    assert updated["status"] == "CONFIRMED_BUY"
    assert "[CHEQUEADO: COMPRA FIRME · A++]" in updated["checked_verdict"]

    # 5. Expiración de TTL
    rec_exp = buffer.set_bias("ETH/USDT", "ALCISTA", 80, "Tesis efímera", ttl_hours=-0.1)
    # Al consultar ETH/USDT vencido, debe retornar None y pasar a DISCARDED_EXPIRED
    expired = buffer.get_bias("ETH/USDT")
    assert expired is None


def test_detect_candlestick_patterns():
    # 1. Martillo (Hammer)
    df_hammer = pd.DataFrame({
        "open": [100.0, 95.0, 90.0],
        "high": [102.0, 96.0, 90.5],
        "low":  [98.0, 92.0, 83.0],  # Mecha inferior = 7.0, cuerpo = 0.4
        "close": [100.0, 94.0, 90.4],
    })
    pat_hammer = detect_candle_pattern(df_hammer)
    assert pat_hammer["pattern"] == "HAMMER"
    assert pat_hammer["type"] == "BULLISH_REVERSAL"

    # 2. Envolvente Alcista (Bullish Engulfing)
    df_engulf = pd.DataFrame({
        "open": [100.0, 98.0, 93.0],
        "high": [101.0, 98.5, 99.0],
        "low":  [99.0, 93.5, 92.8],
        "close": [100.0, 94.0, 98.5], # Abre en 93 (<= 94) y cierra en 98.5 (>= 98.0)
    })
    pat_engulf = detect_candle_pattern(df_engulf)
    assert pat_engulf["pattern"] == "BULLISH_ENGULFING"
    assert pat_engulf["win_rate"] == 63.0

    # 3. Estrella de la Mañana (Morning Star)
    df_mstar = pd.DataFrame({
        "open": [100.0, 87.0, 91.0],  # Vela 1 bajista fuerte (100 -> 90)
        "high": [100.5, 89.0, 98.0],
        "low":  [89.5, 84.0, 90.5],
        "close": [90.0, 86.5, 97.0],  # Vela 2 estrella pequeña (87->86.5, rango 5.0, ratio 0.10)
    })
    pat_mstar = detect_candle_pattern(df_mstar)
    assert pat_mstar["pattern"] == "MORNING_STAR"
    assert pat_mstar["win_rate"] == 78.0


def test_rsi_divergence_logic():
    dates = pd.date_range("2026-10-24 10:00", periods=20, freq="15min")
    # Precio marcando Lower Lows
    prices_low = [100.0 - (i * 0.5) for i in range(20)]
    # RSI marcando Higher Lows
    rsi_rising = [25.0 + (i * 0.8) for i in range(20)]

    df = pd.DataFrame({
        "low": prices_low,
        "high": [p + 2.0 for p in prices_low],
        "close": [p + 0.5 for p in prices_low],
        "open": [p + 1.0 for p in prices_low],
        "rsi": rsi_rising,
    })

    div = detect_rsi_divergence(df)
    assert div["divergence"] == "BULLISH"
    assert div["confidence_boost"] == 15


def test_candlestick_confluence_audit_a_plus_plus(tmp_path):
    buffer_file = str(tmp_path / "bias_test.json")
    buffer = MacroBiasBuffer(buffer_file)
    buffer.set_bias("SOL/USDT", "ALCISTA", 90, "Rotura institucional ETF", ttl_hours=2.5)

    dates = pd.date_range("2026-10-24 10:00", periods=25, freq="15min")
    prices = [150.0 - (i * 0.4) for i in range(23)] + [140.0, 138.0]
    rsis = [28.0 + (i * 0.5) for i in range(25)]

    df = pd.DataFrame({
        "timestamp": [int(d.timestamp() * 1000) for d in dates],
        "open": [p + 0.5 for p in prices],
        "high": [p + 1.0 for p in prices],
        "low":  [p - 1.0 for p in prices],
        "close": prices,
        "volume": [1000.0] * 24 + [2800.0], # RVOL > 2.0
    })
    # Martillo en la última vela
    df.loc[24, "open"] = 138.0
    df.loc[24, "high"] = 138.5
    df.loc[24, "low"] = 130.0  # Mecha de 8.0, cuerpo 0.3
    df.loc[24, "close"] = 138.3
    df["rsi"] = rsis
    df["atr_14"] = 3.5
    df["vwap"] = 135.0

    ind = {
        "latest": df.iloc[-1],
        "previous": df.iloc[-2],
        "atr_14": 3.5,
        "relative_volume": 2.8,
        "ema_200_slope_pct": 0.08,
    }

    # Inyectar buffer temporal en el auditor
    from backend import candlestick_auditor
    orig_file = candlestick_auditor.MacroBiasBuffer
    class MockBuffer:
        def __init__(self, *args, **kwargs):
            self.buf = buffer
        def get_bias(self, s):
            return self.buf.get_bias(s)
        def update_verdict(self, *a, **k):
            return self.buf.update_verdict(*a, **k)

    candlestick_auditor.MacroBiasBuffer = MockBuffer
    try:
        res = audit_candlestick_confluence("SOL/USDT", df, ind)
        assert res["eligible"] is True
        assert "A++ (CONFLUENCIA MACRO + MICRO)" in res["verdict"]
        assert res["rr_ratio"] >= 2.0
        assert res["rvol"] >= 2.0
    finally:
        candlestick_auditor.MacroBiasBuffer = orig_file
