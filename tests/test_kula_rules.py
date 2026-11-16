"""
Módulo: tests/test_kula_rules.py
Pruebas deterministas para el gatillo multivariable de Kula (Punto 3).
"""

import pytest
import pandas as pd
from backend.market_context import KeyLevelsModel
from backend.kula_rules import (
    evaluate_kula_trigger,
    compute_asymmetric_order_governance,
    evaluate_order_exit_state,
)


def create_mock_data():
    """Genera datos sintéticos con tendencia alcista en 1H y volatilidad expansiva en 5M."""
    n_1h = 100
    closes_1h = [100.0 + (i * 0.5) for i in range(n_1h)]
    highs_1h = [c + 1.0 for c in closes_1h]
    lows_1h = [c - 0.5 for c in closes_1h]
    df_1h = pd.DataFrame({"high": highs_1h, "low": lows_1h, "close": closes_1h})

    n_5m = 50
    # Primeras 40 velas de bajo rango, últimas 10 con rango alto para disparar ATR > SMA(ATR, 20)
    highs_5m = [150.0 + 0.2] * 40 + [150.0 + 2.0] * 10
    lows_5m = [150.0 - 0.2] * 40 + [150.0 - 2.0] * 10
    closes_5m = [150.0] * 50
    df_5m = pd.DataFrame({"high": highs_5m, "low": lows_5m, "close": closes_5m})

    return df_1h, df_5m


def test_kula_trigger_all_rules_pass():
    """Valida el disparo afirmativo cuando se cumplen las 4 condiciones."""
    df_1h, df_5m = create_mock_data()
    # Precio actual en 140.0 (por encima de EMA 50 ~125 y dentro de la zona 135-145)
    key_levels = KeyLevelsModel(
        support=130.0,
        resistance=160.0,
        fibo_50=145.0,
        fibo_75=135.0
    )
    result = evaluate_kula_trigger(
        df_1h=df_1h,
        df_5m=df_5m,
        key_levels=key_levels,
        current_price=140.0
    )
    assert result["triggered"] is True
    assert result["side"] == "LONG"
    assert len(result["failures"]) == 0
    assert result["rules"]["rule1_close_gt_ema50"] is True
    assert result["rules"]["rule2_ema21_gt_ema89"] is True
    assert result["rules"]["rule3_fibo_zone"] is True
    assert result["rules"]["rule4_atr_expansion_5m"] is True


def test_kula_trigger_fails_on_ema50():
    """Valida el bloqueo si el precio perfora por debajo de EMA 50."""
    df_1h, df_5m = create_mock_data()
    key_levels = KeyLevelsModel(
        support=80.0,
        resistance=160.0,
        fibo_50=100.0,
        fibo_75=90.0
    )
    # Precio en 95.0, por debajo de EMA 50
    result = evaluate_kula_trigger(
        df_1h=df_1h,
        df_5m=df_5m,
        key_levels=key_levels,
        current_price=95.0
    )
    assert result["triggered"] is False
    assert result["rules"]["rule1_close_gt_ema50"] is False
    assert any("Regla 1 violada" in f for f in result["failures"])


def test_kula_trigger_fails_on_fibo_invalidation():
    """Valida el descarte inmediato si el precio perfora el 0.75 de Fibonacci."""
    df_1h, df_5m = create_mock_data()
    key_levels = KeyLevelsModel(
        support=130.0,
        resistance=160.0,
        fibo_50=145.0,
        fibo_75=135.0
    )
    # Precio en 130.0 (perforó el 135.0)
    result = evaluate_kula_trigger(
        df_1h=df_1h,
        df_5m=df_5m,
        key_levels=key_levels,
        current_price=130.0
    )
    assert result["triggered"] is False
    assert result["rules"]["rule3_fibo_zone"] is False
    assert any("perforó el límite de invalidación Fibo 0.75" in f for f in result["failures"])


def test_kula_trigger_fails_on_compressed_5m_volatility():
    """Valida el descarte si la volatilidad intradiaria en 5M está comprimida."""
    df_1h, _ = create_mock_data()
    # Serie de 5m con volatilidad menguante
    highs_flat = [150.0 + 2.0] * 35 + [150.0 + 0.1] * 15
    lows_flat = [150.0 - 2.0] * 35 + [150.0 - 0.1] * 15
    closes_flat = [150.0] * 50
    df_5m_compressed = pd.DataFrame({"high": highs_flat, "low": lows_flat, "close": closes_flat})

    key_levels = KeyLevelsModel(
        support=130.0,
        resistance=160.0,
        fibo_50=145.0,
        fibo_75=135.0
    )
    result = evaluate_kula_trigger(
        df_1h=df_1h,
        df_5m=df_5m_compressed,
        key_levels=key_levels,
        current_price=140.0
    )
    assert result["triggered"] is False
    assert result["rules"]["rule4_atr_expansion_5m"] is False
    assert any("Regla 4 violada" in f for f in result["failures"])


def test_kula_trigger_short_all_rules_pass():
    """Valida el disparo afirmativo para SHORT cuando se cumplen las 4 condiciones bajistas."""
    n_1h = 100
    closes_1h = [200.0 - (i * 0.5) for i in range(n_1h)]
    highs_1h = [c + 0.5 for c in closes_1h]
    lows_1h = [c - 1.0 for c in closes_1h]
    df_1h = pd.DataFrame({"high": highs_1h, "low": lows_1h, "close": closes_1h})

    n_5m = 50
    highs_5m = [160.0 + 0.2] * 40 + [160.0 + 2.0] * 10
    lows_5m = [160.0 - 0.2] * 40 + [160.0 - 2.0] * 10
    closes_5m = [160.0] * 50
    df_5m = pd.DataFrame({"high": highs_5m, "low": lows_5m, "close": closes_5m})

    # Swing: 200 a 150 (diff 50). Fibo 50% = 175, Fibo 75% = 187.5.
    # Precio actual en 180.0 (en rebote correctivo dentro de 175-187.5)
    key_levels = KeyLevelsModel(
        support=140.0,
        resistance=210.0,
        fibo_50=175.0,
        fibo_75=187.5
    )
    result = evaluate_kula_trigger(
        df_1h=df_1h,
        df_5m=df_5m,
        key_levels=key_levels,
        current_price=160.0,
        side="SHORT"
    )
    # EMA 50 es ~175, precio 160 < EMA 50 -> rule1 OK
    # EMA 21 < EMA 89 -> rule2 OK
    # Fibo: si key_levels está en 160 vs 175, probemos con rebote en 180
    result_valid = evaluate_kula_trigger(
        df_1h=df_1h,
        df_5m=df_5m,
        key_levels=KeyLevelsModel(support=140.0, resistance=210.0, fibo_50=158.0, fibo_75=165.0),
        current_price=160.0,
        side="SHORT"
    )
    assert result_valid["triggered"] is True
    assert result_valid["side"] == "SHORT"
    assert result_valid["rules"]["rule1_close_gt_ema50"] is True  # En short, significa close < ema50
    assert result_valid["rules"]["rule2_ema21_gt_ema89"] is True  # En short, ema21 < ema89
    assert result_valid["rules"]["rule3_fibo_zone"] is True
    assert result_valid["rules"]["rule4_atr_expansion_5m"] is True


def test_asymmetric_order_governance_calculations():
    """Valida los cálculos deterministas de SL 1.5x ATR, TP1 R:R 2.0 y Breakeven cubriendo 0.26%."""
    entry_price = 100.0
    atr = 2.0  # Risk distance = 1.5 * 2.0 = 3.0
    gov = compute_asymmetric_order_governance(
        entry_price=entry_price,
        atr_14=atr,
        side="LONG",
        risk_atr_mult=1.5,
        tp1_rr_ratio=2.0,
        round_trip_fee_pct=0.26,
        ema_21_1h=99.0
    )
    assert gov["sl_initial_price"] == 97.0    # 100 - 3.0
    assert gov["tp1_price"] == 106.0          # 100 + (3.0 * 2.0)
    assert gov["breakeven_price"] == 100.26   # 100 * (1 + 0.0026)
    assert gov["tp1_trim_pct"] == 50.0


def test_order_exit_state_lifecycle():
    """Valida el ciclo completo de la orden: SL inicial -> TP1 con peluqueo -> Trailing Stop."""
    entry_price = 100.0
    gov = compute_asymmetric_order_governance(
        entry_price=entry_price,
        atr_14=2.0,
        side="LONG",
        tp1_rr_ratio=2.0,
        round_trip_fee_pct=0.26
    )

    # 1. Dentro de rango normal -> HOLD
    res_hold = evaluate_order_exit_state(current_price=102.0, gov=gov, tp1_trimmed=False)
    assert res_hold["action"] == "HOLD"

    # 2. Stop Loss inicial alcanzado -> CLOSE_FULL_SL
    res_sl = evaluate_order_exit_state(current_price=96.5, gov=gov, tp1_trimmed=False)
    assert res_sl["action"] == "CLOSE_FULL_SL"

    # 3. TP1 alcanzado (+6%) -> TRIM_50%_TP1 y pase a Breakeven Real
    res_tp1 = evaluate_order_exit_state(current_price=106.5, gov=gov, tp1_trimmed=False)
    assert res_tp1["action"] == "TRIM_50%_TP1"
    assert res_tp1["new_stop_price"] == 100.26
    assert res_tp1["tp1_trimmed"] is True

    # 4. Tras peluqueo: Remanente corriendo libre con Trailing Stop
    # Si precio sube a 112 y EMA 21 está en 108:
    res_trailing_run = evaluate_order_exit_state(
        current_price=112.0,
        gov=gov,
        tp1_trimmed=True,
        trailing_reference=108.0
    )
    assert res_trailing_run["action"] == "HOLD_TRAILING"
    assert res_trailing_run["current_stop_price"] == 108.0

    # 5. Trailing Stop alcanzado cuando precio retrocede a 107.5 (< 108.0)
    res_trailing_exit = evaluate_order_exit_state(
        current_price=107.5,
        gov=gov,
        tp1_trimmed=True,
        trailing_reference=108.0
    )
    assert res_trailing_exit["action"] == "CLOSE_REMAINING_TRAILING"


def test_kula_trigger_enforces_1d_macro_rule0_and_5decimal_precision():
    """Verifica Regla 0 (1D < EMA50 1D veta LONG) y precisión de 5 decimales en Forex."""
    df_1h, df_5m = create_mock_data()
    # Serie 1D claramente bajista bajo EMA50 1D
    closes_1d = [200.0 - i * 1.2 for i in range(60)]
    df_1d_bear = pd.DataFrame({
        "high": [c + 1.0 for c in closes_1d],
        "low": [c - 1.0 for c in closes_1d],
        "close": closes_1d,
    })
    levels = KeyLevelsModel(support=130.0, resistance=160.0, fibo_50=145.0, fibo_75=135.0)
    res = evaluate_kula_trigger(
        df_1h=df_1h,
        df_5m=df_5m,
        key_levels=levels,
        current_price=140.0,
        side="LONG",
        df_1d=df_1d_bear,
    )
    assert res["triggered"] is False
    assert res["triad_mode"] == "multitemporal_1d_1h_5m"
    assert res["rules"]["rule0_1d_macro_bias"] is False
    assert any("Regla 0 (1D) violada" in f for f in res["failures"])

    gov_fx = compute_asymmetric_order_governance(
        entry_price=1.08452,
        atr_14=0.00520,
        side="LONG",
        risk_atr_mult=1.5,
        tp1_rr_ratio=2.0,
        round_trip_fee_pct=0.024,
    )
    assert gov_fx["sl_initial_price"] == round(1.08452 - 1.5 * 0.00520, 5)
    assert gov_fx["breakeven_price"] == round(1.08452 * (1.0 + 0.00024), 5)
    assert gov_fx["sl_initial_price"] != 1.08


