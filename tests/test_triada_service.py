# -*- coding: utf-8 -*-
"""
Pruebas Unitarias e Integración para la Terminal de la Tríada Multitemporal:
  1. Los 5 puntos de overlay reales (evaluate_kula_trigger + check_universal_wick_veto + audit_candlestick_confluence).
  2. Plan de ejecución asistida protegida (quant_risk.py, riesgo 0.5%, R:R >= 2.0 neto).
  3. Bloqueos de seguridad: veto de mecha >= 50%, posición OPEN en auto (one_open_trade_per_symbol), gatillo sin luz verde.
  4. Ejecución virtual aislada (`MANUAL_TRIADA` en `shadow_trades`) y 0% contaminación en Campaign Audit / auditar_sqlite / VAULT_USDT.
"""

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from auditar_sqlite import auditar
from backend import main
from backend.campaign_audit import build_campaign_report
from backend.execution.paper_broker import PaperBrokerAdapter
from backend.triada_service import evaluate_triada_snapshot, execute_triada_simulation


def _make_ohlcv_df(closes, step_sec=3600, base_ts=1795000000, spread_pct=0.008, last_upper_wick_ratio=0.05):
    rows = []
    for i, c in enumerate(closes):
        ts_ms = (base_ts + i * step_sec) * 1000
        o = closes[i - 1] if i > 0 else c * 0.998
        body_hi = max(o, c)
        body_lo = min(o, c)
        hi = body_hi * (1.0 + spread_pct * 0.4)
        lo = body_lo * (1.0 - spread_pct * 0.4)
        if i == len(closes) - 1 and last_upper_wick_ratio >= 0.5:
            # Forzar mecha superior >= 50% del rango total
            rng = max(abs(c - o) * 4.0, c * 0.02)
            lo = body_lo
            hi = body_hi + rng * 0.75
        rows.append([ts_ms, float(o), float(hi), float(lo), float(c), 1200.0 + i * 10.0])
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


def _build_green_triada_frames(wick_veto=False):
    """Construye 3 DataFrames sintéticos deterministas donde las 5 reglas LONG pasan."""
    # 1D alcista sobre EMA50
    closes_1d = np.linspace(1500.0, 2100.0, 65)
    df_1d = _make_ohlcv_df(closes_1d, step_sec=86400)

    # 1H: base en 1700->1860 (55 velas), impulso fuerte 1860->2145 (18 velas) y retroceso a 1955 (7 velas)
    # -> EMA50 ~1944 (< 1955 OK), EMA21 > EMA89 OK, Zona Dorada ~[1875, 1966] OK
    base_1h = list(np.linspace(1700.0, 1860.0, 55)) + list(np.linspace(1865.0, 2145.0, 18)) + list(np.linspace(2135.0, 1955.0, 7))
    df_1h = _make_ohlcv_df(base_1h, step_sec=3600, spread_pct=0.004)
    df_1h.loc[df_1h.index[-25], "low"] = 1850.0
    df_1h.loc[df_1h.index[-8], "high"] = 2150.0
    df_1h.loc[df_1h.index[-1], "close"] = 1955.0
    df_1h.loc[df_1h.index[-1], "open"] = 1948.0
    df_1h.loc[df_1h.index[-1], "high"] = 1960.0
    df_1h.loc[df_1h.index[-1], "low"] = 1946.0

    # 5M táctico con ATR expandido en las últimas 12 velas (ATR(14) > SMA(ATR, 20))
    closes_5m = list(np.linspace(1940.0, 1955.0, 50))
    df_5m = _make_ohlcv_df(closes_5m, step_sec=300, spread_pct=0.002, last_upper_wick_ratio=0.70 if wick_veto else 0.05)
    for k in range(1, 13):
        idx = df_5m.index[-k]
        c_val = float(df_5m.loc[idx, "close"])
        if k == 1 and wick_veto:
            df_5m.loc[idx, "open"] = 1950.0
            df_5m.loc[idx, "close"] = 1955.0
            df_5m.loc[idx, "low"] = 1948.0
            df_5m.loc[idx, "high"] = 2000.0  # mecha superior > 80%
            df_5m.loc[idx, "volume"] = 2400.0
        elif k == 1:
            # Vela alcista limpia con mecha superior pequeña (< 20%) y RVOL >= 1.4x
            df_5m.loc[idx, "open"] = 1942.0
            df_5m.loc[idx, "close"] = 1955.0
            df_5m.loc[idx, "low"] = 1938.0
            df_5m.loc[idx, "high"] = 1958.0
            df_5m.loc[idx, "volume"] = 2400.0
        else:
            df_5m.loc[idx, "high"] = c_val + 14.0
            df_5m.loc[idx, "low"] = c_val - 14.0
    return df_1d, df_1h, df_5m


def test_triada_evaluate_all_five_overlays_and_guarded_execution_plan(tmp_path):
    db_file = str(tmp_path / "triada_eval.sqlite3")
    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=db_file, fee_pct=0.10)
    df_1d, df_1h, df_5m = _build_green_triada_frames(wick_veto=False)
    now_ok = datetime(2026, 11, 23, 14, 0, 0, tzinfo=timezone.utc)  # 11:00 ART (Londres/NY AM)

    snap = evaluate_triada_snapshot(
        symbol="ETHUSDT",
        timeframe="5m",
        direction_mode="long_only",
        risk_pct=0.5,
        target_rr=2.0,
        df_1d=df_1d,
        df_1h=df_1h,
        df_tactical=df_5m,
        broker=broker,
        now_utc=now_ok,
    )

    assert snap["status"] == "ok"
    assert snap["symbol"] == "ETH/USDT"
    assert snap["triggered"] is True

    ov = snap["overlays"]
    assert ov["rule0_macro_1d"]["ok"] is True
    assert ov["rule0_macro_1d"]["ema50_1d"] is not None
    assert "EMA50 1D (✅)" == ov["rule0_macro_1d"]["label"]

    assert ov["rules12_structure_1h"]["rule1_ok"] is True
    assert ov["rules12_structure_1h"]["rule2_ok"] is True
    assert len(ov["rules12_structure_1h"]["series_ema50"]) > 20
    assert len(ov["rules12_structure_1h"]["series_ema21"]) > 20
    assert len(ov["rules12_structure_1h"]["series_ema89"]) > 20

    fibo = ov["rule3_fibo_golden_zone"]
    assert fibo["ok"] is True
    assert fibo["swing_high"] > fibo["fibo_50"] > fibo["fibo_75"] > fibo["swing_low"]
    assert fibo["invalidation_price"] == fibo["fibo_75"]

    atr_sw = ov["rule4_atr_switch"]
    assert atr_sw["ok"] is True
    assert atr_sw["regime"] == "EXPANSION"
    assert atr_sw["badge_text"] == "EXPANSION (Retroceso)"

    r5 = ov["rule5_wick_and_candlestick"]
    assert r5["wick_veto_active"] is False
    assert r5["last_candle_ts"] > 0

    plan = snap["execution_plan"]
    assert plan["can_execute"] is True
    assert plan["block_reasons"] == []
    assert plan["side"] == "LONG"
    assert plan["net_rr"] >= 2.0
    assert plan["risk_pct"] == pytest.approx(0.5)
    assert plan["risk_budget_usd"] == pytest.approx(2.5)
    assert plan["qty"] > 0
    assert plan["sl_price"] < plan["entry_price"] < plan["tp_price"]
    assert plan["strategy"] == "manual_triada"
    assert plan["arbiter_verdict"] == "MANUAL_TRIADA"


def test_triada_blocks_wick_veto_and_open_auto_position(tmp_path):
    db_file = str(tmp_path / "triada_blocks.sqlite3")
    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=db_file, fee_pct=0.10)

    # 1. Veto de mecha >= 50% debe bloquear ejecución incluso si las 5 reglas pasan
    df_1d, df_1h, df_5m_wick = _build_green_triada_frames(wick_veto=True)
    snap_wick = evaluate_triada_snapshot(
        symbol="ETH/USDT",
        timeframe="5m",
        direction_mode="long_only",
        df_1d=df_1d,
        df_1h=df_1h,
        df_tactical=df_5m_wick,
        broker=broker,
    )
    assert snap_wick["overlays"]["rule5_wick_and_candlestick"]["wick_veto_active"] is True
    assert snap_wick["overlays"]["rule5_wick_and_candlestick"]["marker_text"] == "⚠️ VETO MECHA >= 50%"
    assert snap_wick["execution_plan"]["can_execute"] is False
    assert any("Mecha" in r for r in snap_wick["execution_plan"]["block_reasons"])

    res_blocked = execute_triada_simulation(
        symbol="ETH/USDT",
        timeframe="5m",
        direction_mode="long_only",
        df_1d=df_1d,
        df_1h=df_1h,
        df_tactical=df_5m_wick,
        broker=broker,
    )
    assert res_blocked["executed"] is False

    # 2. Posición OPEN en auto sobre ETH/USDT debe bloquear ejecución para proteger one_open_trade_per_symbol
    broker.place_entry(
        symbol="ETH/USDT",
        side="BUY",
        qty=0.05,
        price=1970.0,
        initial_sl_pct=1.5,
        initial_tp_pct=3.5,
        strategy="ttm_squeeze_eth_1h",
    )
    df_1d_ok, df_1h_ok, df_5m_ok = _build_green_triada_frames(wick_veto=False)
    snap_open = evaluate_triada_snapshot(
        symbol="ETH/USDT",
        timeframe="5m",
        direction_mode="long_only",
        df_1d=df_1d_ok,
        df_1h=df_1h_ok,
        df_tactical=df_5m_ok,
        broker=broker,
    )
    assert snap_open["execution_plan"]["can_execute"] is False
    assert any("one_open_trade_per_symbol" in r for r in snap_open["execution_plan"]["block_reasons"])


def test_triada_execute_sim_isolated_from_vault_and_campaign_audit(tmp_path, monkeypatch):
    db_file = str(tmp_path / "triada_iso.sqlite3")
    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=db_file, fee_pct=0.10)
    state_file = tmp_path / "daemon_state.json"
    state_file.write_text(
        json.dumps({"symbol": "ETH/USDT", "timeframe": "4h", "strategy": "auto", "allowed_strategies": ["ttm_squeeze_eth_1h"]}),
        encoding="utf-8",
    )
    cfg_file = tmp_path / "campaign_config.json"
    cfg_file.write_text(
        json.dumps({"campaign_name": "Campaña Iso", "since_iso": "2026-11-21T00:00:00Z", "min_resolved_events": 15}),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRADING_LEDGER_DB_PATH", db_file)
    monkeypatch.setenv("DAEMON_STATE_PATH", str(state_file))
    monkeypatch.setenv("CAMPAIGN_CONFIG_PATH", str(cfg_file))

    df_1d, df_1h, df_5m = _build_green_triada_frames(wick_veto=False)
    now_ok = datetime(2026, 11, 23, 14, 0, 0, tzinfo=timezone.utc)  # 11:00 ART
    res = execute_triada_simulation(
        symbol="ETH/USDT",
        timeframe="5m",
        direction_mode="long_only",
        risk_pct=0.5,
        target_rr=2.0,
        df_1d=df_1d,
        df_1h=df_1h,
        df_tactical=df_5m,
        broker=broker,
        now_utc=now_ok,
    )
    assert res["status"] == "ok"
    assert res["executed"] is True
    assert res["strategy"] == "manual_triada"
    assert res["arbiter_verdict"] == "MANUAL_TRIADA"
    assert broker.fetch_positions() == []
    assert broker.vault_balances["USDT"] == pytest.approx(500.0)

    # Cerrar virtualmente por TP y verificar 0% contaminación en Campaign Audit y auditar_sqlite
    tp_hit = float(res["simulation"]["tp_price"]) + 5.0
    closed = broker.ledger.update_and_close_shadow_trades(
        symbol="ETH/USDT", current_price=tp_hit, high_price=tp_hit, low_price=1965.0
    )
    assert len(closed) == 1

    rep = build_campaign_report(
        db_path=db_file,
        since_iso="2026-11-21T00:00:00Z",
        daemon_state_path=str(state_file),
        config_path=str(cfg_file),
        now_utc=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    assert rep["summary"]["trades_closed"] == 0
    assert rep["summary"]["net_pnl_usd"] == 0.0
    assert rep["summary"]["shadow"]["vetoed_total"] == 0
    assert rep["summary"]["shadow"]["net_arbiter_edge_usd"] == 0.0
    assert rep["summary"]["parallel_shadow"]["closed"] == 0
    assert rep["summary"]["manual_triada"]["closed"] == 1
    assert rep["summary"]["manual_triada"]["wins"] == 1
    assert rep["other_strategies"] == []

    txt = auditar(db_path=db_file, since_iso="2026-11-21")
    assert "0 operaciones vetadas por el Árbitro IA" in txt


def test_triada_fastapi_endpoints_smoke(tmp_path):
    db_file = str(tmp_path / "triada_api.sqlite3")
    broker_iso = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=db_file, fee_pct=0.10)
    df_1d, df_1h, df_5m = _build_green_triada_frames(wick_veto=False)

    def _fake_fetch(symbol, tf, limit):
        if tf == "1d":
            return df_1d
        if tf == "1h":
            return df_1h
        return df_5m

    class _FakeDaemon:
        broker = broker_iso

    now_ok_guard = {
        "art_time": "11:00",
        "window_code": "LONDRES_NY_AM",
        "window_label": "Londres / NY AM (09:30–13:30 ART)",
        "is_primary_window": True,
        "is_blackout": False,
        "blackout_reason": None,
        "tf_norm": "5m",
        "tf_floor_ok": True,
        "tf_recommended": "15m",
        "tf_warning": None,
    }

    client = TestClient(main.app)
    with patch("backend.triada_service._fetch_closed_df", side_effect=_fake_fetch), \
         patch("backend.triada_service._evaluate_session_and_tf_guard", return_value=now_ok_guard), \
         patch("backend.daemon.get_trader_daemon", return_value=_FakeDaemon()):
        r_eval = client.get("/api/triada/evaluate?symbol=ETHUSDT&timeframe=5m&direction_mode=long_only&risk_pct=0.5&target_rr=2.0")
        assert r_eval.status_code == 200
        d_eval = r_eval.json()
        assert d_eval["status"] == "ok"
        assert d_eval["execution_plan"]["can_execute"] is True

        r_exec = client.post(
            "/api/triada/execute-sim",
            json={"symbol": "ETH/USDT", "timeframe": "5m", "direction_mode": "long_only", "risk_pct": 0.5, "target_rr": 2.0},
        )
        assert r_exec.status_code == 200
        d_exec = r_exec.json()
        assert d_exec["executed"] is True
        assert d_exec["arbiter_verdict"] == "MANUAL_TRIADA"
        assert d_exec["simulation"]["entry_price"] > 0
        assert d_exec["simulation"]["sl_price"] > 0
        assert d_exec["simulation"]["tp_price"] > 0


def test_triada_presencial_5_step_protocol_setup_a_rvol_session_and_daily_caps(tmp_path):
    """
    Verifica los 5 pasos del Protocolo Presencial en backend/triada_service.py:
      - Paso 1: Bloqueo en Lunch Lull (14:30 ART) y en escala 1m cripto; habilitado en Londres/NY (11:00 ART, 15m).
      - Paso 2 y 3: Setup A (Ruptura post-compresión 1H -> 15M) dispara luz verde aunque el precio esté fuera de la Zona Dorada Fibo.
      - Paso 4: RVOL-TOD bipolar bloquea si < 1.8x en Setup A (o < 1.1x en Setup B) y habilita si >= 1.8x.
      - Paso 5: SL cripto >= 1.2% y cupo duro diario bloquea al llegar a 2 operaciones MANUAL_TRIADA o 2 SL en el día.
    """
    db_file = str(tmp_path / "triada_presencial_5steps.sqlite3")
    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=db_file, fee_pct=0.10)

    # 1D y 1H en tendencia alcista clara (Precio = 2145, arriba de Fibo 0.50-0.75 -> Setup B Fibo es False)
    closes_1d = np.linspace(1500.0, 2145.0, 65)
    df_1d = _make_ohlcv_df(closes_1d, step_sec=86400)
    closes_1h = np.linspace(1700.0, 2145.0, 80)
    df_1h = _make_ohlcv_df(closes_1h, step_sec=3600, spread_pct=0.004)

    # 15M táctico: 35 velas muy comprimidas en [2138, 2140] con rango alto (ATR alto, STD de cierres casi 0 -> BB dentro de KC)
    # y última vela rompe con fuerza a 2168 con volumen RVOL >= 2.2x
    rows_15m = []
    base_ts = 1795000000
    for i in range(40):
        ts_ms = (base_ts + i * 900) * 1000
        if i < 39:
            c = 2139.0 + (0.15 if i % 2 == 0 else -0.15)
            o = 2139.0
            hi = 2152.0
            lo = 2126.0
            vol = 1000.0
        else:
            # Vela de ruptura fuera de Keltner (kcu ~ 2183) con volumen institucional (2500 vs media 1000 -> 2.5x)
            o = 2140.0
            c = 2195.0
            hi = 2198.0
            lo = 2139.0
            vol = 2500.0
        rows_15m.append([ts_ms, o, hi, lo, c, vol])
    df_15m = pd.DataFrame(rows_15m, columns=["timestamp", "open", "high", "low", "close", "volume"])

    # Hora válida: Lunes 11:00 ART = 14:00 UTC
    now_london_ny = datetime(2026, 11, 23, 14, 0, 0, tzinfo=timezone.utc)

    snap_a = evaluate_triada_snapshot(
        symbol="ETH/USDT",
        timeframe="15m",
        direction_mode="long_only",
        df_1d=df_1d,
        df_1h=df_1h,
        df_tactical=df_15m,
        broker=broker,
        now_utc=now_london_ny,
    )
    proto = snap_a["presencial_protocol"]
    assert proto["setup_b_fibo_pullback"]["triggered"] is False
    assert proto["setup_a_squeeze"]["triggered"] is True
    assert proto["active_setup"] == "SETUP_A_SQUEEZE"
    assert proto["rvol_gate"]["ok"] is True
    assert proto["rvol_gate"]["rvol_tod"] >= 1.8
    assert snap_a["execution_plan"]["can_execute"] is True
    assert snap_a["execution_plan"]["sl_gross_pct"] >= 1.2

    # Si el volumen de la ruptura es seco (RVOL < 1.8x, ej. vol=800 -> 0.8x), Paso 4 debe bloquear
    df_15m_low_vol = df_15m.copy()
    df_15m_low_vol.loc[df_15m_low_vol.index[-1], "volume"] = 800.0
    snap_low_rvol = evaluate_triada_snapshot(
        symbol="ETH/USDT",
        timeframe="15m",
        direction_mode="long_only",
        df_1d=df_1d,
        df_1h=df_1h,
        df_tactical=df_15m_low_vol,
        broker=broker,
        now_utc=now_london_ny,
    )
    assert snap_low_rvol["presencial_protocol"]["rvol_gate"]["ok"] is False
    assert snap_low_rvol["execution_plan"]["can_execute"] is False
    assert any("RVOL bipolar insuficiente" in r for r in snap_low_rvol["execution_plan"]["block_reasons"])

    # Si estamos en Lunch Lull (14:30 ART = 17:30 UTC), Paso 1 debe bloquear
    now_lunch_lull = datetime(2026, 11, 23, 17, 30, 0, tzinfo=timezone.utc)
    snap_lunch = evaluate_triada_snapshot(
        symbol="ETH/USDT",
        timeframe="15m",
        direction_mode="long_only",
        df_1d=df_1d,
        df_1h=df_1h,
        df_tactical=df_15m,
        broker=broker,
        now_utc=now_lunch_lull,
    )
    assert snap_lunch["presencial_protocol"]["session_guard"]["is_blackout"] is True
    assert snap_lunch["execution_plan"]["can_execute"] is False
    assert any("Lunch Lull" in r for r in snap_lunch["execution_plan"]["block_reasons"])

    # Si el operador ya ejecutó 2 operaciones MANUAL_TRIADA hoy, Paso 5 (cupo diario) debe bloquear la 3ra
    for idx_t in range(2):
        broker.ledger.open_shadow_trade(
            symbol=f"SYM{idx_t}/USDT",
            side="LONG",
            qty=0.1,
            entry_price=2000.0,
            sl_price=1970.0,
            tp_price=2065.0,
            initial_sl_pct=1.5,
            initial_tp_pct=3.25,
            strategy="manual_triada",
            arbiter_verdict="MANUAL_TRIADA",
            arbiter_reason="Test cupo diario",
            deduplicate=False,
        )

    snap_quota = evaluate_triada_snapshot(
        symbol="ETH/USDT",
        timeframe="15m",
        direction_mode="long_only",
        df_1d=df_1d,
        df_1h=df_1h,
        df_tactical=df_15m,
        broker=broker,
        now_utc=datetime.now(timezone.utc),
    )
    assert snap_quota["presencial_protocol"]["daily_limits"]["daily_trades_count"] == 2
    assert snap_quota["presencial_protocol"]["daily_limits"]["ok"] is False
    assert snap_quota["execution_plan"]["can_execute"] is False
    assert any("Cupo diario presencial alcanzado" in r for r in snap_quota["execution_plan"]["block_reasons"])
