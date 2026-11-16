# -*- coding: utf-8 -*-
"""Tests del filtro de derivados (Funding H1) y su integración en donchian_breakout_1h."""
from pathlib import Path

import pandas as pd
import pytest

from backend import derivatives_flow as dflow
from backend.estrategias.donchian_breakout_1h import DonchianBreakout1H

DATA = Path(__file__).resolve().parent.parent / "backtest_lab" / "data" / "datos_historicos" / "binance_SOL_USDT_4h.parquet"


def test_symbol_mapping():
    assert dflow.to_futures_symbol("SOL/USDT") == "SOLUSDT"
    assert dflow.to_futures_symbol("ETH/USDT:USDT") == "ETHUSDT"
    assert dflow.to_futures_symbol("BTCUSDT") == "BTCUSDT"
    for sym in ("AAPL", "EURUSD=X", "MES=F", "GGAL.BA", ""):
        assert dflow.to_futures_symbol(sym) is None


def test_gate_rules_and_fail_open():
    ok, _ = dflow.evaluate_short_funding_gate({"available": True, "funding_last": 0.0001})
    assert ok is True
    ok, reason = dflow.evaluate_short_funding_gate({"available": True, "funding_last": 0.0})
    assert ok is False and "squeeze" in reason
    ok, _ = dflow.evaluate_short_funding_gate({"available": True, "funding_last": -0.00005})
    assert ok is False
    ok, reason = dflow.evaluate_short_funding_gate({"available": False, "error": "timeout"})
    assert ok is True and "fail-open" in reason
    assert dflow.evaluate_short_funding_gate(None)[0] is True


def test_snapshot_never_raises_and_caches(monkeypatch):
    calls = {"n": 0}

    def boom(_sym):
        calls["n"] += 1
        raise RuntimeError("red caída")

    dflow._cache.clear()
    monkeypatch.setattr(dflow, "_fetch", boom)
    snap = dflow.get_derivatives_snapshot("SOL/USDT")
    assert snap["available"] is False and "red caída" in snap["error"]
    dflow.get_derivatives_snapshot("SOL/USDT")
    assert calls["n"] == 1  # segunda llamada servida desde caché TTL
    assert dflow.get_derivatives_snapshot("AAPL")["available"] is False
    dflow._cache.clear()


def _short_setup():
    if not DATA.exists():
        pytest.skip("Dataset histórico SOL 4H no disponible")
    df = pd.read_parquet(DATA)
    sub = df.loc[:"2025-10-30 12:00"].tail(400).copy()
    return sub


def _eval(sub, funding):
    ind = {
        "symbol": "SOL/USDT", "timeframe": "4h",
        "latest": {"close": float(sub["close"].iloc[-1])},
        "derivatives": {"available": True, "funding_last": funding, "oi_change_pct_24h": 1.5},
    }
    return DonchianBreakout1H().evaluar(ind, 2.0, 1.0, 0.1, 0.05, 0.5, 0.3, 1.0, df=sub)


def test_shadow_mode_does_not_block_short(monkeypatch):
    from backend.estrategias.config_manager import StrategyConfigManager
    monkeypatch.setattr(StrategyConfigManager, "get_strategy_config", lambda self, sid: {})
    sub = _short_setup()
    m, _, eligible, failures, _ = _eval(sub, -0.0001)
    assert eligible is True and m["side"] == "SHORT"
    assert m["funding_gate"]["mode"] == "SOMBRA"
    assert m["funding_gate"]["shadow_veto"] is True
    assert not any("Funding" in f for f in failures)


def test_blocking_mode_vetoes_short_with_non_positive_funding(monkeypatch):
    from backend.estrategias.config_manager import StrategyConfigManager
    monkeypatch.setattr(
        StrategyConfigManager, "get_strategy_config",
        lambda self, sid: {"sub_strategies": {"filtro_funding_short": True}},
    )
    sub = _short_setup()
    m, _, eligible, failures, _ = _eval(sub, -0.0001)
    assert eligible is False and m["side"] == "MANTENER"
    assert any("Filtro Funding (H1)" in f for f in failures)

    m2, _, eligible2, _, _ = _eval(sub, 0.0001)
    assert eligible2 is True and m2["side"] == "SHORT" and m2["funding_gate"]["ok"] is True
