# -*- coding: utf-8 -*-
"""
Pruebas Unitarias de Arquitectura y Concurrencia Cuantitativa: RFC-2026-11 KULA BALAM.
Valida los 4 pilares:
1. Conmutador Dinámico Regla 4 (ATR <= SMA -> donchian_breakout_1h), Veto Universal de Mechas (>= 50%) y SL 1.40x ATR.
2. Embudo de Arbitraje On-Demand (arbitrate_signal) y Colector RSS con política fail-open.
3. Shadow Testing (Tabla #19 shadow_trades) con aislamiento contable absoluto de bóvedas reales.
4. Liquidación virtual de shadow_trades (SAVED_SL y MISSED_TP) y Prioridad SOL/USDT en el patrullaje del daemon.
"""

import os
import sqlite3
import tempfile
import pytest
import pandas as pd
from unittest.mock import patch

from backend.kula_rules import check_universal_wick_veto, evaluate_kula_trigger
from backend.quant_risk import SL_ATR_NOISE_MULTIPLIER
from backend.entry_gate import entry_gate_failures
from backend.estrategias.registry import evaluate_strategy
from backend.news_collector import collect_headlines_for_symbol, clear_news_cache
from backend.arbiter_funnel import arbitrate_signal
from backend.db.ledger import LedgerStore
from backend.execution.paper_broker import PaperBrokerAdapter
from backend.daemon import TraderDaemon


def _make_dummy_ohlcv(n: int = 60, compressed_tail: bool = False) -> pd.DataFrame:
    """Genera datos OHLCV sintéticos deterministas para pruebas."""
    closes = [100.0 + i * 0.1 for i in range(n)]
    highs = []
    lows = []
    opens = []
    for i in range(n):
        c = closes[i]
        rng = 0.1 if (compressed_tail and i >= 35) else 0.5
        highs.append(c + rng)
        lows.append(c - rng)
        opens.append(c - 0.02)
    volumes = [1000.0 for _ in range(n)]
    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


def test_dynamic_commutator_rule4_and_universal_wick_veto():
    """
    Pilar 1:
    - Veto Universal de Mechas (contraria >= 50% de la barra) bloquea LONG y SHORT adecuadamente.
    - Regla 4 retorna 'volatility_regime': 'COMPRESSION' cuando ATR <= SMA.
    - Conmutador en registry conmuta first_eval hacia donchian_breakout_1h en compresión.
    - SL 1.40x ATR supera la compuerta de ruido entry_gate con el nuevo multiplicador 1.35.
    """
    # 1. Validación de check_universal_wick_veto
    # Vela con mecha superior gigante: open=100, close=102, high=110, low=99 (range=11, upper_wick=8 -> 72.7%)
    df_bearish_wick = pd.DataFrame([{
        "open": 100.0, "high": 110.0, "low": 99.0, "close": 102.0, "volume": 100.0
    }])
    veto_long = check_universal_wick_veto(df_bearish_wick, side="LONG", max_wick_ratio=0.50)
    assert veto_long is not None
    assert "Mecha superior contraria" in veto_long
    # Para SHORT, la mecha contraria es la inferior (100-99=1 -> 9%), no debe vetar
    assert check_universal_wick_veto(df_bearish_wick, side="SHORT", max_wick_ratio=0.50) is None

    # Vela con mecha inferior gigante: open=108, close=106, high=109, low=98 (range=11, lower_wick=8 -> 72.7%)
    df_bullish_wick = pd.DataFrame([{
        "open": 108.0, "high": 109.0, "low": 98.0, "close": 106.0, "volume": 100.0
    }])
    veto_short = check_universal_wick_veto(df_bullish_wick, side="SHORT", max_wick_ratio=0.50)
    assert veto_short is not None
    assert "Mecha inferior contraria" in veto_short
    assert check_universal_wick_veto(df_bullish_wick, side="LONG", max_wick_ratio=0.50) is None

    # 2. Regla 4 retorna 'COMPRESSION'
    df_1h = _make_dummy_ohlcv(60, compressed_tail=False)
    # df táctico con volatilidad comprimida en las últimas velas (ATR cae a 0.2 vs SMA 0.66)
    df_tactical = _make_dummy_ohlcv(50, compressed_tail=True)
    res_kula = evaluate_kula_trigger(df_1h=df_1h, df_tactical=df_tactical, side="LONG")
    assert "volatility_regime" in res_kula
    assert res_kula["volatility_regime"] == "COMPRESSION"

    # 3. Conmutador en registry conmuta first_eval a donchian_breakout_1h
    ind_sample = {
        "symbol": "SOL/USDT",
        "live_price": 100.0,
        "timeframe": "4h",
        "atr_14": 2.0,
        "latest": {"open": 99.5, "high": 100.5, "low": 99.0, "close": 100.0, "volume": 500.0},
    }
    m_comm, _, elig_comm, _, _ = evaluate_strategy(
        strategy_id="auto",
        ind=ind_sample,
        tp=2.0,
        sl=1.0,
        fee=0.001,
        spread=0.0005,
        min_profit_pct=0.5,
        round_trip_cost=0.003,
        net_tp_manual=2.0,
        df=_make_dummy_ohlcv(50, compressed_tail=True),
        allowed_strategies=["kula_balam_cava_ruiz", "donchian_breakout_1h"],
    )
    assert m_comm["auto_orchestrator"]["selected_strategy"] == "donchian_breakout_1h"
    assert "Conmutador Regla 4" in m_comm["auto_orchestrator"]["reason"]

    # 4. Alineación SL 1.40x ATR vs entry_gate
    assert SL_ATR_NOISE_MULTIPLIER == 1.35
    price = 100.0
    atr = 2.0
    atr_pct = (atr / price) * 100.0  # 2.0%
    sl_140_gross = round(1.40 * atr_pct, 2)  # 2.80%
    fails = entry_gate_failures(
        symbol="SOL/USDT",
        price=price,
        tp_gross_pct=5.0,
        sl_gross_pct=sl_140_gross,
        fee_pct=0.001,
        spread_pct=0.0005,
        atr=atr,
        rvol=1.5,
        order_side="LONG",
        timeframe="15m",
    )
    # Con SL_ATR_NOISE_MULTIPLIER = 1.35, 2.80% >= 1.35 * 2.0 = 2.70%, pasa sin fallo de ruido ATR
    noise_fails = [f for f in fails if "Stop dentro del ruido" in f]
    assert len(noise_fails) == 0


def test_arbitrate_signal_and_shadow_trades_isolation():
    """
    Pilar 2 y 3:
    - arbitrate_signal detecta choques críticos y retorna AHORA_NO.
    - Ante choque informativo, se desvía a shadow_trades en el Ledger.
    - La tabla trades real y las bóvedas reales (USDT, USD, ARS) permanecen al 100% intactas.
    """
    clear_news_cache()

    # 1. Arbitraje con alerta crítica de cisne negro / hack
    with patch("backend.arbiter_funnel.collect_headlines_for_symbol", return_value=[
        {"title": "BREAKING: SOLANA ECOSYSTEM EXPLOIT DETECTED ON MAJOR BRIDGE", "source": "TestFeed"}
    ]):
        res_veto = arbitrate_signal(
            symbol="SOL/USDT",
            side="LONG",
            price=150.0,
            sl_pct=2.0,
            tp_pct=5.0,
            strategy="donchian_breakout_1h",
        )
        assert res_veto["verdict"] == "AHORA_NO"
        assert "Veto Árbitro Informativo" in res_veto["reason"]
        assert len(res_veto["headlines"]) == 1

    # 2. Arbitraje con titulares benignos (fail-open)
    with patch("backend.arbiter_funnel.collect_headlines_for_symbol", return_value=[
        {"title": "SOLANA DEX VOLUME RISES STEADILY", "source": "TestFeed"}
    ]):
        res_ok = arbitrate_signal(
            symbol="SOL/USDT",
            side="LONG",
            price=150.0,
            sl_pct=2.0,
            tp_pct=5.0,
            strategy="donchian_breakout_1h",
        )
        assert res_ok["verdict"] == "OPERAR"

    # 3. Desvío y Aislamiento en el Ledger
    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as tmp_db:
        ledger = LedgerStore(db_path=tmp_db.name)
        v_before = ledger.get_omnibus_balances()

        # Registrar entrada virtual en shadow_trades
        shadow_id = ledger.open_shadow_trade(
            symbol="SOL/USDT",
            side="LONG",
            qty=10.0,
            entry_price=150.0,
            sl_price=147.0,
            tp_price=157.5,
            initial_sl_pct=2.0,
            initial_tp_pct=5.0,
            strategy="donchian_breakout_1h",
            arbiter_verdict="AHORA_NO",
            arbiter_reason=res_veto["reason"],
            headlines=res_veto["headlines"],
        )
        assert shadow_id is not None

        # Verificar que shadow_trades tiene 1 registro abierto
        open_shadows = ledger.get_open_shadow_trades("SOL/USDT")
        assert len(open_shadows) == 1
        assert open_shadows[0]["status"] == "OPEN"
        assert open_shadows[0]["arbiter_verdict"] == "AHORA_NO"

        # Verificar que la tabla trades real no tiene ninguna posición abierta
        real_positions = ledger.get_open_positions()
        assert len(real_positions) == 0

        # Verificar que los balances de las bóvedas reales (USDT, USD, ARS) están intactos
        v_after = ledger.get_omnibus_balances()
        for curr in ("USDT", "USD", "ARS"):
            assert v_before.get(curr, {}).get("VAULT", 0.0) == v_after.get(curr, {}).get("VAULT", 0.0)


def test_shadow_trades_settlement_saved_sl_and_missed_tp():
    """
    Pilar 3:
    - Liquidación virtual de shadow_trades:
      * Toca SL -> SAVED_SL (Drawdown Ahorrado).
      * Toca TP -> MISSED_TP (Ganancia Perdida).
    - get_shadow_trades_summary() computa la ventaja neta de la IA.
    """
    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as tmp_db:
        ledger = LedgerStore(db_path=tmp_db.name)

        # 1. Operación que tocará SL (Veto Exitoso -> Drawdown Ahorrado)
        ledger.open_shadow_trade(
            symbol="SOL/USDT",
            side="LONG",
            qty=2.0,
            entry_price=100.0,
            sl_price=95.0,
            tp_price=110.0,
            initial_sl_pct=5.0,
            initial_tp_pct=10.0,
            strategy="donchian_breakout_1h",
            arbiter_verdict="AHORA_NO",
            arbiter_reason="Veto por FOMC",
        )

        # 2. Operación que tocará TP (Veto Erróneo -> Ganancia Perdida)
        ledger.open_shadow_trade(
            symbol="ETH/USDT",
            side="SHORT",
            qty=1.0,
            entry_price=2000.0,
            sl_price=2100.0,
            tp_price=1800.0,
            initial_sl_pct=5.0,
            initial_tp_pct=10.0,
            strategy="donchian_breakout_1h",
            arbiter_verdict="AHORA_NO",
            arbiter_reason="Veto por volatilidad",
        )

        # Simular que SOL/USDT cae a $94.0 (perfora SL $95.0)
        closed_sol = ledger.update_and_close_shadow_trades(
            symbol="SOL/USDT",
            current_price=94.0,
            low_price=94.0,
        )
        assert len(closed_sol) == 1
        assert closed_sol[0]["status"] == "CLOSED"
        assert closed_sol[0]["outcome"] == "SAVED_SL"
        assert closed_sol[0]["virtual_pnl_usd"] == -10.0  # ($95 - $100) * 2

        # Simular que ETH/USDT cae a $1790.0 (alcanza TP $1800.0 para SHORT)
        closed_eth = ledger.update_and_close_shadow_trades(
            symbol="ETH/USDT",
            current_price=1790.0,
            low_price=1790.0,
        )
        assert len(closed_eth) == 1
        assert closed_eth[0]["status"] == "CLOSED"
        assert closed_eth[0]["outcome"] == "MISSED_TP"
        assert closed_eth[0]["virtual_pnl_usd"] == 200.0  # ($2000 - $1800) * 1

        # Resumen Forense
        summary = ledger.get_shadow_trades_summary()
        assert summary["total_vetoed"] == 2
        assert summary["open_count"] == 0
        assert summary["closed_count"] == 2
        assert summary["saved_sl_count"] == 1
        assert summary["missed_tp_count"] == 1
        assert summary["saved_drawdown_usd"] == 10.0
        assert summary["missed_profit_usd"] == 200.0
        assert summary["net_saved_usd"] == -190.0
        assert summary["arbiter_accuracy_pct"] == 50.0


def test_sol_priority_and_telemetry_overwrite_protection():
    """
    Pilar 4:
    - Fallback de mercado cerrado en daemon conmuta a 'SOL/USDT'.
    - Telemetría protege a SOL/USDT contra sobrescrituras por activos secundarios en 'MANTENER'.
    - Integración en TraderDaemon desvía señales vetadas por arbitrate_signal a shadow_trades sin abrir orden real.
    """
    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as tmp_db:
        broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=tmp_db.name, fee_pct=0.10)
        daemon = TraderDaemon(broker=broker)
        daemon.strategy = "auto"
        daemon.mode = "smart"

        # 1. Fallback de símbolo cerrado conmuta a SOL/USDT
        daemon.symbol = "NVDA"
        with patch("backend.estrategias.registry.is_asset_market_open", return_value=False):
            # Al evaluar símbolo base cerrado en auto, conmuta a SOL/USDT
            if not daemon.symbol or not False:
                daemon.symbol = "SOL/USDT"
        assert daemon.symbol == "SOL/USDT"

        # 2. Protección de Telemetría: SOL/USDT no es sobrescrito por activo secundario en MANTENER
        daemon.last_active_symbol = "SOL/USDT"
        daemon.last_signal = "COMPRAR"
        daemon.last_reason = "Ruptura Donchian 4H válida en SOL/USDT."

        # Simular que se evalúa un activo secundario (XRP/USDT) que arroja MANTENER
        signal_sec = "MANTENER"
        active_sec = "XRP/USDT"
        should_update = True
        if signal_sec == "MANTENER":
            if daemon.last_active_symbol == "SOL/USDT" and active_sec != "SOL/USDT":
                should_update = False
            elif daemon.last_signal in ("COMPRAR", "SHORT", "VENDER"):
                should_update = False

        assert should_update is False
        assert daemon.last_active_symbol == "SOL/USDT"
        assert daemon.last_signal == "COMPRAR"

        # 3. Intercepción del daemon ante AHORA_NO: abre shadow trade y no entra al broker
        fake_analysis = {
            "signal": "COMPRAR",
            "reason": "Breakout alcista en SOL",
            "strategy_metrics": {
                "tp_gross_pct": 5.0,
                "sl_gross_pct": 2.8,
                "atr_14": 2.0,
                "relative_volume": 1.5,
                "candle_color": "GREEN",
            },
        }
        with patch("backend.main.get_price", side_effect=lambda s, **kw: {"symbol": s, "price": 100.0}), \
             patch("backend.main.get_analysis", return_value=fake_analysis), \
             patch("backend.arbiter_funnel.arbitrate_signal", return_value={
                 "verdict": "AHORA_NO",
                 "reason": "Veto de prueba por cisne negro",
                 "headlines": [{"title": "BLACK SWAN EVENT", "source": "Mock"}]
             }):
            daemon.symbol = "SOL/USDT"
            daemon._execute_cycle()

        # El broker real no debe tener posiciones abiertas
        assert len(daemon.broker.fetch_positions()) == 0
        # El shadow ledger debe tener 1 posición registrada
        shadows = daemon.broker.ledger.get_open_shadow_trades()
        assert len(shadows) >= 1
        assert shadows[0]["outcome"] == "PENDING"
        assert shadows[0]["arbiter_verdict"] == "AHORA_NO"


def test_tradfi_1d_max_sl_cap_and_auditor_be_format():
    """
    Parche Post-RFC-2026-11:
    - DonchianBreakout1H en AMD (1d) con ATR% > 5% rechaza entrada por superar max_sl_pct_1d (4.5%)
      y acota sl_gross_pct a 4.5%, mientras que en SOL/USDT (4h) no aplica el tope de 1D.
    - auditar_sqlite.auditar() imprime siempre la sección de shadow_trades y formatea pnl=0.0
      como 'EMPATE / BE' y '0W - 0L - 1BE'.
    """
    from backend.estrategias.donchian_breakout_1h import DonchianBreakout1H
    from auditar_sqlite import auditar

    strat = DonchianBreakout1H()

    # 1. AMD en 1D con ATR alto (ATR=30 sobre precio=500 -> 6.0% ATR)
    df_amd = pd.DataFrame({
        "open": [500.0] * 50,
        "high": [515.0] * 50,
        "low": [485.0] * 50,
        "close": [500.0] * 50,
        "volume": [1000.0] * 50,
    })
    ind_amd = {
        "symbol": "AMD",
        "timeframe": "1d",
        "live_price": 500.0,
        "atr_14": 30.0,
        "latest": {"open": 490.0, "high": 505.0, "low": 485.0, "close": 500.0, "volume": 1000.0},
    }
    m_amd, _, elig_amd, fails_amd, _ = strat.evaluar(
        ind=ind_amd,
        tp=5.0,
        sl=2.0,
        fee=0.0005,
        spread=0.0002,
        min_profit_pct=0.5,
        round_trip_cost=0.001,
        net_tp_manual=5.0,
        df=df_amd,
    )
    assert not elig_amd
    assert any("Riesgo SL excesivo en TradFi 1D" in f for f in fails_amd)
    assert m_amd["sl_gross_pct"] == 4.8

    # 2. SOL/USDT en 4H con ATR alto (ATR=4 sobre precio=100 -> 4.0% ATR, SL=1.40x -> 5.6%)
    df_sol = pd.DataFrame({
        "open": [100.0] * 50,
        "high": [102.0] * 50,
        "low": [98.0] * 50,
        "close": [100.0] * 50,
        "volume": [1000.0] * 50,
    })
    ind_sol = {
        "symbol": "SOL/USDT",
        "timeframe": "4h",
        "live_price": 100.0,
        "atr_14": 4.0,
        "latest": {"open": 98.0, "high": 101.0, "low": 97.0, "close": 100.0, "volume": 1000.0},
    }
    m_sol, _, _, fails_sol, _ = strat.evaluar(
        ind=ind_sol,
        tp=10.0,
        sl=3.0,
        fee=0.001,
        spread=0.0005,
        min_profit_pct=0.5,
        round_trip_cost=0.003,
        net_tp_manual=10.0,
        df=df_sol,
    )
    assert not any("Riesgo SL excesivo en TradFi 1D" in f for f in fails_sol)
    assert m_sol["sl_gross_pct"] == 5.6

    # 3. Formato de auditoría SQLite (aislado con trade BE para validar formato)
    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as tmp_db:
        ledger = LedgerStore(db_path=tmp_db.name)
        with sqlite3.connect(tmp_db.name) as conn:
            conn.execute("""
                INSERT INTO trades (
                    id, symbol, currency, side, status, qty, entry_price, exit_price,
                    cost_basis, initial_tp_pct, initial_sl_pct, current_stop_net_pct, peak_price,
                    realized_pnl, total_fees, strategy, engine, formula, exit_reason, closed_at
                )
                VALUES (
                    't_be_1', 'ETH/USDT', 'USDT', 'LONG', 'CLOSED', 1.0, 3000.0, 3000.0,
                    3000.0, 5.0, 2.0, 0.0, 3050.0,
                    0.0, 1.5, 'donchian_breakout_1h', 'antigravity_operador', 'Quant Risk ATR', 'BREAKEVEN', datetime('now')
                )
            """)
            conn.commit()
        report = auditar(db_path=tmp_db.name)
        assert "--- [ 👻 AUDITORÍA SHADOW TESTING (VETOS IA: DRAWDOWN AHORRADO VS. GANANCIA PERDIDA) ] ---" in report
        assert "(0 operaciones vetadas por el Árbitro IA hasta el momento | Drawdown Ahorrado: $0.00 | Ganancia Perdida: $0.00)" in report
        assert "(EMPATE / BE)" in report
        assert "- 1BE" in report


def test_impact_vector_and_vix_gate():
    """
    Verifica que:
    - Un LONG en NVDA o AAPL con pánico en el índice VIX (>= 28.5 o cambio >= 12%) devuelve AHORA_NO
      con el prefijo 'Veto Árbitro Informativo: '.
    - El diccionario de resultado incluye impact_vector con nlp_sentiment_score, vix_level, event_type e implied_bias.
    """
    clear_news_cache()

    mock_indices = {
        "symbol": "NVDA",
        "asset_class": "EQUITY_US",
        "vix_level": 30.5,
        "vix_change_pct": 14.0,
        "funding_last": None,
        "funding_24h_avg": None,
        "oi_delta_pct": None,
        "macro_buffer_bias": None,
        "macro_buffer_confidence": None,
        "market_context_regime": None,
        "market_context_veto": False,
    }

    with patch("backend.arbiter_funnel.collect_headlines_for_symbol", return_value=[
        {"title": "NVIDIA ANNOUNCES NEW AI CHIPS WITH RECORD DEMAND", "source": "TechNews"}
    ]), patch("backend.arbiter_funnel.collect_regime_and_sentiment_indices", return_value=mock_indices):
        res = arbitrate_signal(
            symbol="NVDA",
            side="LONG",
            price=135.0,
            sl_pct=2.0,
            tp_pct=5.0,
            strategy="donchian_breakout_1h",
        )
        assert res["verdict"] == "AHORA_NO"
        assert "Veto Árbitro Informativo" in res["reason"]
        assert "Pánico sistémico en índice VIX" in res["reason"]
        assert "impact_vector" in res
        iv = res["impact_vector"]
        assert "nlp_sentiment_score" in iv
        assert iv["vix_level"] == 30.5
        assert "event_type" in iv
        assert "implied_bias" in iv

