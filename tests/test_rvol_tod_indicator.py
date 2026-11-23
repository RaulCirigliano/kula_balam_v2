# -*- coding: utf-8 -*-
"""
Pruebas Unitarias y de Integración para el indicador visual RVOL por Hora del Día (`rvol_tod`):
  1. Cálculo estrictamente causal por misma hora:minuto en sesiones previas (sin look-ahead).
  2. Fallback causal SMA20 en `1d` o con < 3 muestras previas en la misma franja horaria.
  3. Manejo seguro de volumen 0 (Forex `EURUSD=X`) sin NaN/Inf en JSON de `/api/market/history`.
"""

import math
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.indicators import compute_rvol_tod


def test_compute_rvol_tod_compares_same_hour_across_prior_sessions_causally():
    # 6 días consecutivos de velas 1H (144 velas) con patrón intradiario fuerte:
    # Hora 14:00 UTC (apertura NY) siempre tiene volumen 1000 en días 0..4 y 2500 en día 5 (RVOL exacto = 2.50x).
    # Otras horas tienen volumen bajo (100), para probar que NO se distorsiona con SMA20 corrido.
    start_ts = int(pd.Timestamp("2026-11-01 00:00:00", tz="UTC").timestamp() * 1000)
    rows = []
    for day in range(6):
        for hour in range(24):
            ts_ms = start_ts + ((day * 24 + hour) * 3600 * 1000)
            if hour == 14:
                vol = 2500.0 if day == 5 else 1000.0
            else:
                vol = 100.0
            rows.append([ts_ms, 100.0, 101.0, 99.0, 100.5, vol])

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    rvol = compute_rvol_tod(df, timeframe="1h", max_sessions=10, min_tod_samples=3)

    # Día 5 hora 14:00 -> índice 5*24 + 14 = 134
    # Promedio de los 5 días previos a las 14:00 UTC es exactamente 1000.0 -> 2500 / 1000 = 2.50
    idx_d5_h14 = 5 * 24 + 14
    assert rvol.iloc[idx_d5_h14] == pytest.approx(2.50, abs=1e-6)

    # Día 4 hora 14:00 -> índice 4*24 + 14 = 110 (4 muestras previas de 1000 -> RVOL = 1.00, sin look-ahead del pico de día 5!)
    idx_d4_h14 = 4 * 24 + 14
    assert rvol.iloc[idx_d4_h14] == pytest.approx(1.00, abs=1e-6)

    # Día 5 hora 15:00 -> 100 / 100 = 1.00 (no penalizado por el pico de las 14:00)
    assert rvol.iloc[idx_d5_h14 + 1] == pytest.approx(1.00, abs=1e-6)


def test_compute_rvol_tod_daily_fallback_and_zero_volume_forex_safe():
    # 1) Diario (1d): usa fallback causal SMA20
    start_ts = int(pd.Timestamp("2026-10-01 00:00:00", tz="UTC").timestamp() * 1000)
    rows_1d = [
        [start_ts + i * 86400 * 1000, 100.0, 102.0, 98.0, 101.0, 400.0 if i == 25 else 200.0]
        for i in range(30)
    ]
    df_1d = pd.DataFrame(rows_1d, columns=["timestamp", "open", "high", "low", "close", "volume"])
    rvol_1d = compute_rvol_tod(df_1d, timeframe="1d")
    assert rvol_1d.iloc[25] == pytest.approx(2.00, abs=1e-6)
    assert pd.isna(rvol_1d.iloc[0])  # primera vela sin historial previo

    # 2) Forex (volumen 0): sin NaN/Inf en división ni crash
    rows_fx = [
        [start_ts + i * 3600 * 1000, 1.09, 1.092, 1.088, 1.091, 0.0]
        for i in range(40)
    ]
    df_fx = pd.DataFrame(rows_fx, columns=["timestamp", "open", "high", "low", "close", "volume"])
    rvol_fx = compute_rvol_tod(df_fx, timeframe="1h")
    assert rvol_fx.isna().all()
    assert not np.isinf(rvol_fx.fillna(0.0)).any()


def test_market_history_endpoint_exposes_rvol_tod_and_handles_forex_zero_volume():
    start_ts = int(pd.Timestamp("2026-11-01 00:00:00", tz="UTC").timestamp() * 1000)
    ohlcv_crypto = [
        [start_ts + i * 3600 * 1000, 100.0 + i * 0.1, 101.0 + i * 0.1, 99.0 + i * 0.1, 100.5 + i * 0.1, 250.0 if i == 119 else 100.0]
        for i in range(120)
    ]
    ohlcv_fx = [
        [start_ts + i * 3600 * 1000, 1.09, 1.092, 1.088, 1.091, 0.0]
        for i in range(40)
    ]

    client = TestClient(main.app)
    with patch.object(main, "get_ohlcv", return_value=ohlcv_crypto):
        r_c = client.get("/api/market/history?symbol=ETH/USDT&timeframe=1h&limit=30")
        assert r_c.status_code == 200
        data_c = r_c.json()
        assert len(data_c) == 30
        assert data_c[-1]["rvol_tod"] == pytest.approx(2.5, abs=0.05)
        assert all(
            (it["rvol_tod"] is None) or (isinstance(it["rvol_tod"], (int, float)) and math.isfinite(it["rvol_tod"]))
            for it in data_c
        )

    with patch.object(main, "get_ohlcv", return_value=ohlcv_fx):
        r_fx = client.get("/api/market/history?symbol=EURUSD=X&timeframe=1h&limit=20")
        assert r_fx.status_code == 200
        data_fx = r_fx.json()
        assert len(data_fx) == 20
        assert all(it["rvol_tod"] is None for it in data_fx)
