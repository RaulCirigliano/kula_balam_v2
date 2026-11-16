from datetime import datetime, timedelta, timezone

from backend.entry_gate import (
    check_btc_macro_veto,
    churn_block_reason,
    cio_directive_failures,
    entry_gate_failures,
    get_btc_macro_status,
    in_opening_blackout,
    in_pre_close_blackout,
    is_btc,
    is_crypto_altcoin,
    parse_entry_range,
    should_auto_flatten_intraday,
)



def test_gate_blocks_negative_edge_levels_and_passes_good_ones():
    bad = entry_gate_failures("BTC/USDT", 82000.0, 0.8, 0.5, 0.1, 0.05)
    assert any("R:R neto" in f for f in bad)
    good = entry_gate_failures("BTC/USDT", 82000.0, 2.1, 0.6, 0.1, 0.05, atr=100.0, rvol=1.0)
    assert good == []


def test_gate_blocks_stop_inside_atr_noise_and_low_volume():
    failures = entry_gate_failures("BTC/USDT", 100.0, 4.0, 0.6, 0.1, 0.05, atr=1.0, rvol=0.3)
    assert any("ruido" in f for f in failures)
    assert any("Volumen relativo" in f for f in failures)


def test_opening_blackout_only_first_15_minutes_for_us_equities():
    # 2026-10-19 13:35 UTC = 09:35 NY (EDT)
    assert in_opening_blackout("QQQ", datetime(2026, 10, 19, 13, 35, tzinfo=timezone.utc)) is True
    assert in_opening_blackout("QQQ", datetime(2026, 10, 19, 13, 50, tzinfo=timezone.utc)) is False
    assert in_opening_blackout("BTC/USDT", datetime(2026, 10, 19, 13, 35, tzinfo=timezone.utc)) is False


def test_churn_blocks_reentry_after_breakeven_at_same_price():
    now = datetime(2026, 10, 19, 17, 0, 0, tzinfo=timezone.utc)
    history = [{
        "symbol": "QQQ", "status": "CLOSED", "closed_at": "2026-10-19 16:02:44",
        "exit_price": 722.25, "exit_reason": "Breakeven",
    }]
    assert "cooldown" in churn_block_reason(history, "QQQ", 720.87, now=now)
    later = now + timedelta(hours=3)
    assert "del último cierre" in churn_block_reason(history, "QQQ", 720.87, now=later)
    assert churn_block_reason(history, "QQQ", 720.87, z_score=-2.3, now=later) is None
    assert churn_block_reason(history, "QQQ", 700.0, now=later) is None
    assert churn_block_reason(history, "BTC/USDT", 82000.0, now=now) is None


def test_cio_directive_revalidation_range_and_ttl():
    assert parse_entry_range("Entrada: 706.00 - 712.00 USD | SL: 693") == (706.0, 712.0)
    now = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=1)).isoformat()
    stale = (now - timedelta(hours=9)).isoformat()
    text = "Tesis | Entrada: 706.00 - 712.00 USD"
    assert cio_directive_failures(text, fresh, 709.0, now=now) == []
    assert any("por encima del rango" in f for f in cio_directive_failures(text, fresh, 720.8, now=now))
    assert any("caducada" in f for f in cio_directive_failures(text, stale, 709.0, now=now))


def test_pre_close_blackout_blocks_late_us_equities():
    # 2026-10-19 19:35 UTC = 15:35 NY (EDT), a 25 min del cierre (16:00 NY)
    late = datetime(2026, 10, 19, 19, 35, tzinfo=timezone.utc)
    midday = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc)  # 14:00 NY
    assert in_pre_close_blackout("QQQ", late) is True
    assert in_pre_close_blackout("QQQ", midday) is False
    assert in_pre_close_blackout("BTC/USDT", late) is False  # Cripto nunca bloquea por pre-cierre

    failures = entry_gate_failures("QQQ", 718.0, 2.0, 0.6, 0.1, 0.05, atr=5.0, rvol=1.0, now_dt=late)
    assert any("Ventana Pre-Cierre" in f for f in failures)


def test_auto_flatten_window_triggers_15m_before_close():
    # 2026-10-19 19:50 UTC = 15:50 NY (EDT), dentro de los 15 min de pre-cierre
    pre_close = datetime(2026, 10, 19, 19, 50, tzinfo=timezone.utc)
    midday = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc)
    assert should_auto_flatten_intraday("QQQ", pre_close) is True
    assert should_auto_flatten_intraday("QQQ", midday) is False
    assert should_auto_flatten_intraday("BTC/USDT", pre_close) is False


def test_btc_macro_veto_blocks_altcoins_when_btc_bearish():
    # 1. Identificación de símbolos
    assert is_btc("BTC/USDT") is True
    assert is_btc("BTC-USD") is True
    assert is_crypto_altcoin("XRP/USDT") is True
    assert is_crypto_altcoin("SOL/USDT") is True
    assert is_crypto_altcoin("ETH/USDT") is True
    assert is_crypto_altcoin("BNB/USDT") is True
    assert is_crypto_altcoin("BTC/USDT") is False
    assert is_crypto_altcoin("AAPL") is False

    # 2. Veto activo si BTC cotiza bajo EMA200 1H o bajo VWAP diario
    btc_bearish_override = {
        "btc_close": 79000.0,
        "btc_ema_200_1h": 81000.0,
        "btc_vwap_daily": 80500.0,
        "below_ema200": True,
        "below_vwap": True,
        "veto_active": True,
        "reason": "BTC cotiza bajo EMA200 1H y bajo VWAP diario",
    }

    # Bloqueo estricto de compras LONG en altcoins (XRP, SOL, ETH, BNB)
    for alt in ("XRP/USDT", "SOL/USDT", "ETH/USDT", "BNB/USDT"):
        veto_msg = check_btc_macro_veto(alt, order_side="BUY", btc_macro_override=btc_bearish_override)
        assert veto_msg is not None
        assert "Veto Macro Bitcoin" in veto_msg
        assert "Bloqueo estricto" in veto_msg

        # entry_gate_failures debe incluir el veto
        fails = entry_gate_failures(
            alt, 1.25, 3.0, 1.0, 0.1, 0.05, atr=0.05, rvol=1.5,
            order_side="BUY", btc_macro_override=btc_bearish_override
        )
        assert any("Veto Macro Bitcoin" in f for f in fails)

    # 3. NO debe bloquear a BTC/USDT directamente
    assert check_btc_macro_veto("BTC/USDT", order_side="BUY", btc_macro_override=btc_bearish_override) is None

    # 4. NO debe bloquear órdenes SHORT en altcoins (en caídas los shorts son bienvenidos)
    assert check_btc_macro_veto("XRP/USDT", order_side="SHORT", btc_macro_override=btc_bearish_override) is None
    fails_short = entry_gate_failures(
        "XRP/USDT", 1.25, 3.0, 1.0, 0.1, 0.05, atr=0.05, rvol=1.5,
        order_side="SHORT", btc_macro_override=btc_bearish_override
    )
    assert not any("Veto Macro Bitcoin" in f for f in fails_short)

    # 5. Si BTC es alcista (sobre EMA200 1H y sobre VWAP), no hay veto
    btc_bullish_override = {
        "btc_close": 85000.0,
        "btc_ema_200_1h": 81000.0,
        "btc_vwap_daily": 82000.0,
        "below_ema200": False,
        "below_vwap": False,
        "veto_active": False,
        "reason": "BTC sobre EMA200 1H y sobre VWAP diario",
    }
    assert check_btc_macro_veto("XRP/USDT", order_side="BUY", btc_macro_override=btc_bullish_override) is None


def test_centinela_falling_knife_and_guarded_sl():
    """Verifica el funcionamiento del Escudo Centinela No Bloqueante (Veto Cuchillo y SL Blindado)."""
    from backend.quant_risk import calculate_guarded_stop_loss, detect_institutional_sweep_bonus

    # 1. Blindaje de Stop Loss (fuera del ruido y bajo soporte con margen)
    guarded = calculate_guarded_stop_loss(
        price=100.0,
        support_price=98.0,
        atr=1.5,
        base_sl_pct=1.0,
        tick_size=0.01,
    )
    assert guarded["is_guarded"] is True
    # Soporte a 2.0% de distancia + margen de 0.30% (0.20*1.5) = 2.30%
    # Fuera del ruido 1.5 * (1.5 / 100 * 100) = 2.25%
    assert guarded["sl_pct"] >= 2.25
    assert guarded["sl_price"] < 98.0  # El SL queda estrictamente POR DEBAJO del soporte

    # 2. Veto Cuchillo Cayendo (vela roja sólida sin mecha inferior)
    fails_knife = entry_gate_failures(
        symbol="BTC/USDT",
        price=70000.0,
        tp_gross_pct=4.0,
        sl_gross_pct=1.5,
        fee_pct=0.1,
        spread_pct=0.05,
        atr=500.0,
        rvol=1.0,
        order_side="BUY",
        lower_wick_ratio=0.08,  # < 15%
        candle_color="RED",     # Vela bajista
    )
    assert any("Veto Centinela Cuchillo Cayendo" in f for f in fails_knife)

    # 3. No debe vetar si la vela tiene rechazo/mecha de absorción (no es cuchillo)
    fails_normal = entry_gate_failures(
        symbol="BTC/USDT",
        price=70000.0,
        tp_gross_pct=4.0,
        sl_gross_pct=1.5,
        fee_pct=0.1,
        spread_pct=0.05,
        atr=500.0,
        rvol=1.0,
        order_side="BUY",
        lower_wick_ratio=0.35,  # >= 15%
        candle_color="GREEN",
    )
    assert not any("Veto Centinela Cuchillo Cayendo" in f for f in fails_normal)

    # 4. Detector de Barrido Institucional (Bonus 2X, no peaje)
    # Sin barrido extremo: 1X estándar
    normal_sweep = detect_institutional_sweep_bonus(rvol=1.0, lower_wick_ratio=0.20)
    assert normal_sweep["sweep_detected"] is False
    assert normal_sweep["conviction_multiplier"] == 1.0
    assert normal_sweep["risk_budget_pct"] == 0.25

    # Con barrido institucional: 2X acelerador
    boost_sweep = detect_institutional_sweep_bonus(rvol=1.8, lower_wick_ratio=0.45)
    assert boost_sweep["sweep_detected"] is True
    assert boost_sweep["conviction_multiplier"] == 2.0
    assert boost_sweep["risk_budget_pct"] == 0.50


