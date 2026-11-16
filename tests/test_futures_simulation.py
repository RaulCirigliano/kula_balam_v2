import math
import time
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.daemon import TraderDaemon
from backend.estrategias.kula_balam_cava_ruiz import KulaBalamCavaRuiz
from backend.execution.paper_broker import PaperBrokerAdapter
from backend.quant_risk import (
    ASSET_CLASS_FUTURES_MICRO,
    calculate_futures_pnl,
    get_asset_friction_costs,
    get_micro_futures_spec,
    is_micro_futures_symbol,
)


def test_micro_futures_specs_and_tick_point_pnl_mes_and_mnq():
    assert is_micro_futures_symbol("MES=F") is True
    assert is_micro_futures_symbol("MNQ=F") is True
    assert is_micro_futures_symbol("SPY") is False
    assert is_micro_futures_symbol("GC=F") is False

    mes_costs = get_asset_friction_costs("MES=F", price=6000.0)
    assert mes_costs["asset_type"] == ASSET_CLASS_FUTURES_MICRO
    assert mes_costs["multiplier"] == 5.0
    assert mes_costs["tick_size"] == 0.25
    assert mes_costs["tick_value"] == 1.25
    assert mes_costs["commission_per_contract_side"] == 1.25
    assert mes_costs["commission_round_trip_per_contract"] == 2.50
    assert mes_costs["default_contracts"] == 2

    mnq_costs = get_asset_friction_costs("MNQ=F", price=21000.0)
    assert mnq_costs["asset_type"] == ASSET_CLASS_FUTURES_MICRO
    assert mnq_costs["multiplier"] == 2.0
    assert mnq_costs["tick_size"] == 0.25
    assert mnq_costs["tick_value"] == 0.50
    assert mnq_costs["commission_per_contract_side"] == 1.25
    assert mnq_costs["default_contracts"] == 2

    # MES LONG: +10.25 pts (+41 ticks) x $5/pt x 2 contratos = +$102.50 bruto - $5.00 comisión = +$97.50 neto
    pnl_mes_long = calculate_futures_pnl("MES=F", entry_price=6000.00, exit_price=6010.25, contracts=2, side="LONG")
    assert pnl_mes_long["ticks_diff"] == pytest.approx(41.0)
    assert pnl_mes_long["gross_pnl"] == pytest.approx(102.50)
    assert pnl_mes_long["total_commission"] == pytest.approx(5.00)
    assert pnl_mes_long["net_pnl"] == pytest.approx(97.50)

    # MES SHORT: -4.50 pts a favor (+18 ticks) x $5/pt x 1 contrato = +$22.50 bruto - $2.50 comisión = +$20.00 neto
    pnl_mes_short = calculate_futures_pnl("MES=F", entry_price=6000.00, exit_price=5995.50, contracts=1, side="SHORT")
    assert pnl_mes_short["ticks_diff"] == pytest.approx(18.0)
    assert pnl_mes_short["gross_pnl"] == pytest.approx(22.50)
    assert pnl_mes_short["net_pnl"] == pytest.approx(20.00)

    # MNQ LONG: +25.75 pts (+103 ticks) x $2/pt x 2 contratos = +$103.00 bruto - $5.00 comisión = +$98.00 neto
    pnl_mnq_long = calculate_futures_pnl("MNQ=F", entry_price=21000.00, exit_price=21025.75, contracts=2, side="LONG")
    assert pnl_mnq_long["ticks_diff"] == pytest.approx(103.0)
    assert pnl_mnq_long["gross_pnl"] == pytest.approx(103.00)
    assert pnl_mnq_long["total_commission"] == pytest.approx(5.00)
    assert pnl_mnq_long["net_pnl"] == pytest.approx(98.00)

    # MNQ SHORT perdedor: +10.00 pts en contra x $2/pt x 2 contratos = -$40.00 bruto - $5.00 comisión = -$45.00 neto
    pnl_mnq_loss = calculate_futures_pnl("MNQ=F", entry_price=21000.00, exit_price=21010.00, contracts=2, side="SHORT")
    assert pnl_mnq_loss["gross_pnl"] == pytest.approx(-40.00)
    assert pnl_mnq_loss["net_pnl"] == pytest.approx(-45.00)


def test_micro_futures_execution_isolated_from_real_spot_vaults(tmp_path):
    db_path = str(tmp_path / "futures_isolated.sqlite3")
    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=db_path, fee_pct=0.10)

    vaults_before = dict(broker.vault_balances)
    ops_before = dict(broker.balances)
    op_cap_before = dict(broker.operating_capital_balances)
    cb_usd_before = dict(broker.ledger.check_circuit_breaker("USD"))
    fut_initial = broker.get_futures_balance()
    assert fut_initial == pytest.approx(2500.0)

    # 1. Abrir exactamente 2 contratos micro MES=F @ 6000.00 (comisión entrada: $2.50)
    entry_res = broker.place_entry(
        symbol="MES=F",
        side="BUY",
        qty=2,
        price=6000.0,
        initial_tp_pct=0.25,
        initial_sl_pct=0.12,
        strategy="kula_balam_cava_ruiz",
    )
    assert entry_res["status"] == "FILLED"
    assert entry_res["asset_class"] == ASSET_CLASS_FUTURES_MICRO
    assert entry_res["contracts"] == 2.0
    assert entry_res["fee_amount"] == pytest.approx(2.50)
    assert broker.get_futures_balance() == pytest.approx(2497.50)

    # 2. Peluqueo TP1: cerrar 1 contrato @ 6010.00 (+$50.00 bruto, -$1.25 salida => +$47.50 neto del 1er contrato)
    trim_res = broker.trim_position("MES=F", trim_qty=1, current_price=6010.0, reason="PELUQUEO_TP1_50%")
    assert trim_res["trimmed"] is True
    assert trim_res["trimmed_qty"] == 1.0
    assert trim_res["remaining_qty"] == 1.0
    assert trim_res["gross_pnl"] == pytest.approx(50.00)
    assert trim_res["net_pnl"] == pytest.approx(47.50)
    assert broker.get_futures_balance() == pytest.approx(2546.25)

    # Verificar estado Break-Even armado en el contrato remanente
    open_fut = [p for p in broker.fetch_positions() if p["symbol"] == "MES=F"][0]
    assert open_fut["be_armed"] == 1
    assert open_fut["contracts"] == 1.0

    # 3. Cierre 2do contrato @ 6020.00 (+$100.00 bruto, -$1.25 salida => +$97.50 neto del 2do contrato; +$145.00 acumulado)
    close_res = broker.flatten("MES=F", current_price=6020.0, exit_reason="Trailing Stop")
    assert close_res["closed"] is True
    assert close_res["gross_pnl"] == pytest.approx(100.00)
    assert close_res["net_pnl"] == pytest.approx(145.00)
    assert close_res["total_fees"] == pytest.approx(5.00)
    assert broker.get_futures_balance() == pytest.approx(2645.00)

    # 4. Operación SHORT perdedora en MNQ=F (2 contratos @ 21000 -> 21015 => -$60 bruto - $5 fee = -$65 neto)
    broker.place_entry("MNQ=F", "SHORT", qty=2, price=21000.0, initial_tp_pct=0.30, initial_sl_pct=0.15, strategy="kula_balam_cava_ruiz")
    mnq_close = broker.flatten("MNQ=F", current_price=21015.0, exit_reason="Stop Loss")
    assert mnq_close["net_pnl"] == pytest.approx(-65.00)
    assert broker.get_futures_balance() == pytest.approx(2580.00)

    # Invariante absoluto: Bóvedas reales Spot (USDT, USD, ARS) y su Circuit Breaker permanecen 100% intactos
    assert broker.vault_balances == vaults_before
    assert broker.balances == ops_before
    assert broker.operating_capital_balances == op_cap_before
    assert broker.ledger.check_circuit_breaker("USD") == cb_usd_before
    assert broker.ledger.verify_double_entry_integrity()["valid"] is True


def _build_kula_futures_triad(base_price: float, step_pt: float):
    # 1D alcista sobre EMA50
    df_1d = pd.DataFrame([
        {
            "open": base_price - (60 - i) * step_pt,
            "high": base_price - (60 - i) * step_pt + step_pt * 2,
            "low": base_price - (60 - i) * step_pt - step_pt * 2,
            "close": base_price - (60 - i) * step_pt + step_pt,
            "volume": 5000.0,
        }
        for i in range(60)
    ])
    # 1H retroceso a Zona Dorada Fibonacci (~55% del impulso [low=base-20*step, high=base+10*step])
    impulse_low = base_price - 20.0 * step_pt
    impulse_high = base_price + 10.0 * step_pt
    golden_px = impulse_high - 0.58 * (impulse_high - impulse_low)
    rows_1h = []
    for i in range(45):
        p = impulse_low + (i / 44.0) * (impulse_high - impulse_low)
        rows_1h.append({"open": p - step_pt * 0.2, "high": p + step_pt * 0.5, "low": p - step_pt * 0.5, "close": p, "volume": 2500.0})
    for j in range(15):
        p = impulse_high - (j / 14.0) * (impulse_high - golden_px)
        rows_1h.append({"open": p + step_pt * 0.2, "high": p + step_pt * 0.3, "low": p - step_pt * 0.3, "close": p, "volume": 1200.0})
    df_1h = pd.DataFrame(rows_1h)

    # 5M agotamiento con fallo de MACD, secado previo y cierre rompiendo EMA50
    rows_5m = []
    for k in range(55):
        p = golden_px + step_pt * 1.5 - (k * 0.04 * step_pt)
        rows_5m.append({"open": p + 0.1, "high": p + 0.3, "low": p - 0.3, "close": p, "volume": 900.0})
    for k in range(4):
        p = rows_5m[-1]["close"] - (0.05 * step_pt)
        rows_5m.append({"open": p + 0.1, "high": p + 0.2, "low": p - 0.5, "close": p, "volume": 400.0})
    last_close = golden_px + step_pt * 3.0
    rows_5m.append({"open": golden_px - step_pt * 0.2, "high": last_close + step_pt * 0.2, "low": golden_px - step_pt * 0.6, "close": last_close, "volume": 1800.0})
    df_5m = pd.DataFrame(rows_5m)
    return df_1d, df_1h, df_5m, last_close


def test_kula_triad_and_daemon_2_contract_peluqueo_on_mes_and_mnq(tmp_path, monkeypatch):
    monkeypatch.setenv("KULA_MARKET_CONTEXT_PATH", str(tmp_path / "no_ctx.json"))
    strat = KulaBalamCavaRuiz()
    assert "MES=F" in strat.activos_recomendados
    assert "MNQ=F" in strat.activos_recomendados

    for sym, base_px, step_pt, exp_mult in [("MES=F", 6000.0, 2.5, 5.0), ("MNQ=F", 21000.0, 10.0, 2.0)]:
        df_1d, df_1h, df_5m, c_px = _build_kula_futures_triad(base_px, step_pt)
        costs = get_asset_friction_costs(sym, price=c_px)
        ind = {
            "symbol": sym,
            "live_price": c_px,
            "atr_14": step_pt * 0.8,
            "relative_volume": 0.70,
            "lower_wick_ratio": 0.28,
            "rsi": 48.0,
            "df_1d": df_1d,
            "df_1h": df_1h,
            "latest": {"close": c_px, "atr_14": step_pt * 0.8},
        }
        metrics, _, _, _, _ = strat.evaluar(
            ind=ind,
            tp=1.5,
            sl=0.5,
            fee=costs["fee_pct"],
            spread=costs["spread_pct"],
            min_profit_pct=0.10,
            round_trip_cost=round((costs["fee_pct"] + costs["spread_pct"]) * 2.0, 4),
            net_tp_manual=1.4,
            df=df_5m,
        )
        assert metrics["asset_class"] == ASSET_CLASS_FUTURES_MICRO
        assert metrics["lot_mode"] == "CONTRACTS"
        assert metrics["contracts"] == 2
        assert metrics["point_multiplier"] == exp_mult
        assert metrics["tick_size"] == 0.25
        assert metrics["triad_mode"] == "multitemporal_1d_1h_5m"

    # Ciclo autónomo completo en TraderDaemon: abre 2 contratos, corta 1 en TP1 y cierra el 2do con Trailing
    monkeypatch.setenv("TRADING_OLLAMA_CSV_PATH", str(tmp_path / "fut_daemon.csv"))
    db_file = str(tmp_path / "daemon_fut.sqlite3")
    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=db_file)
    # El guardián respeta horarios CME (pausa 18:00-19:00 ART); se fija el mercado abierto para evitar dependencia del reloj real
    monkeypatch.setattr("backend.estrategias.registry.is_asset_market_open", lambda sym, now_dt=None: True)
    td = TraderDaemon(broker=broker)
    assert td.enable_futures_simulation is False
    assert td.get_status()["enable_futures_simulation"] is False
    td.symbol = "MES=F"
    td.timeframe = "5m"
    td.strategy = "kula_balam_cava_ruiz"
    td.mode = "fixed"

    fake_analysis = {
        "signal": "COMPRAR",
        "reason": "Tríada Kula 1D-1H-5M confirmada en MES=F",
        "strategy": "kula_balam_cava_ruiz",
        "strategy_metrics": {
            "asset_class": ASSET_CLASS_FUTURES_MICRO,
            "contracts": 2,
            "tp_gross_pct": 0.20,
            "sl_gross_pct": 0.10,
            "atr_14": 3.0,
            "relative_volume": 1.1,
            "sub_strategy": "cava_ruiz_long",
        },
        "candlestick_audit": {},
    }
    with patch("backend.main.get_analysis", return_value=fake_analysis), \
         patch("backend.main.get_price", return_value={"symbol": "MES=F", "price": 6000.0}), \
         patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch("backend.entry_gate.entry_gate_failures", return_value=[]), \
         patch("backend.macro_bias_buffer.MacroBiasBuffer.get_all_active", return_value=[]), \
         patch.object(td, "_check_radar_for_autorouting", return_value=None):
        td._execute_cycle()

    pos = broker.fetch_positions()
    assert len(pos) == 1
    assert pos[0]["symbol"] == "MES=F"
    assert pos[0]["contracts"] == 2.0
    assert broker.vault_balances == {"USDT": 500.0, "USD": 500.0, "ARS": 500000.0}

    # TP1 (+0.20% = 6012.0): Peluqueo cierra exactamente 1 contrato (+$60 bruto, $1.25+$1.25=$2.50 fee -> +$57.50 neto)
    with patch("backend.main.get_price", return_value={"symbol": "MES=F", "price": 6012.0}):
        liq1 = td._check_open_positions_protections()
    assert len(liq1) == 1
    assert liq1[0]["action"] == "PELUQUEO_TP1"
    pos_after = broker.fetch_positions()
    assert len(pos_after) == 1
    assert pos_after[0]["contracts"] == 1.0
    assert pos_after[0]["be_armed"] == 1

    # El 2do contrato avanza a 6036.0 (+0.60%) activando Trailing Stop y luego retrocede a 6022.0 (< 6023.93 stop)
    with patch("backend.main.get_price", return_value={"symbol": "MES=F", "price": 6036.0}):
        td._check_open_positions_protections()
    pos_trail = broker.fetch_positions()[0]
    assert pos_trail["trail_active"] == 1

    with patch("backend.main.get_price", return_value={"symbol": "MES=F", "price": 6022.0}):
        liq2 = td._check_open_positions_protections()
    assert len(liq2) == 1
    assert liq2[0]["action"] == "TRAILING_STOP"
    assert broker.fetch_positions() == []
    assert broker.get_futures_balance() > 2500.0
    # Spot vaults intactas de principio a fin
    assert broker.vault_balances == {"USDT": 500.0, "USD": 500.0, "ARS": 500000.0}


def test_yfinance_datafeed_mapping_and_triad_endpoint_for_mes_and_mnq(tmp_path, monkeypatch):
    assert "MES=F" in main.SUPPORTED_SYMBOLS
    assert "MNQ=F" in main.SUPPORTED_SYMBOLS

    monkeypatch.setenv("KULA_MARKET_CONTEXT_PATH", str(tmp_path / "no_ctx2.json"))
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", str(tmp_path / "no_bias.json"))

    def _make_yf_df(step_s: int, count: int, base: float):
        now_s = int(time.time()) // step_s * step_s
        idx = pd.to_datetime([(now_s - (count - i) * step_s) * 1000 for i in range(count)], unit="ms", utc=True)
        closes = [base + i * 0.25 for i in range(count)]
        return pd.DataFrame({
            "Open": [c - 0.25 for c in closes],
            "High": [c + 0.50 for c in closes],
            "Low": [c - 0.50 for c in closes],
            "Close": closes,
            "Volume": [1000.0] * count,
        }, index=idx)

    calls = []

    class FakeTicker:
        def __init__(self, sym):
            self.sym = sym

        def history(self, period="5d", interval="5m", timeout=10):
            calls.append((self.sym, period, interval))
            base = 6000.0 if self.sym == "MES=F" else 21000.0
            if interval == "1d":
                return _make_yf_df(86400, 70, base)
            if interval == "1h":
                return _make_yf_df(3600, 80, base)
            return _make_yf_df(300, 230, base)

    import yfinance as yf
    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    monkeypatch.setattr("backend.estrategias.registry.is_asset_market_open", lambda sym: True)
    main._CACHE_DATA.clear()

    client = TestClient(main.app)
    for sym in ("MES=F", "MNQ=F"):
        res = client.get(f"/api/market/analysis?symbol={sym}&timeframe=5m&engine=antigravity_operador&strategy=kula_balam_cava_ruiz")
        assert res.status_code == 200
        data = res.json()
        assert data["strategy_metrics"]["triad_mode"] == "multitemporal_1d_1h_5m"
        assert data["strategy_metrics"]["asset_class"] == ASSET_CLASS_FUTURES_MICRO
        assert data["strategy_metrics"]["contracts"] == 2

    assert ("MES=F", "5d", "5m") in calls
    assert ("MES=F", "60d", "1h") in calls
    assert ("MES=F", "2y", "1d") in calls
    assert ("MNQ=F", "5d", "5m") in calls
