"""
Módulo: backend/kula_rules.py
Proyecto: Kula Balam
Gatillo Multivariable de Kula (Punto 3):
Función determinista en Python puro con 4 reglas simultáneas:
1. Cierre > EMA 50 en 1H
2. EMA 21 > EMA 89 en 1H (alineación tendencial)
3. Retroceso en zona 0.50 - 0.75 de Fibonacci (invalida si rompe el 0.75)
4. Gatillo en 5m con filtro de volatilidad: ATR(14) > SMA(ATR, 20)
"""

from typing import Any, Dict, List, Optional
import pandas as pd
from backend.market_context import KeyLevelsModel


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    """Calcula la media móvil exponencial de forma determinista."""
    return series.ewm(span=span, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calcula el Rango Verdadero Medio (ATR)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def evaluate_kula_trigger(
    df_1h: pd.DataFrame,
    df_5m: Optional[pd.DataFrame] = None,
    key_levels: Optional[KeyLevelsModel] = None,
    current_price: Optional[float] = None,
    df_tactical: Optional[pd.DataFrame] = None,
    side: str = "LONG",
    target_side: Optional[str] = None,
    df_1d: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Evalúa la tríada multitemporal completa del gatillo multivariable de Kula (1D -> 1H -> 5M/Táctico):
    0. Filtro Macro 1D (opcional si se provee df_1d >= 25 velas): Cierre 1D vs EMA 50 1D.
    1. Filtro Direccional (1H):
       - LONG: Cierre > EMA 50
       - SHORT: Cierre < EMA 50
    2. Alineación Tendencial (1H):
       - LONG: EMA 21 > EMA 89
       - SHORT: EMA 21 < EMA 89
    3. Retroceso en Zona Dorada de Fibonacci [0.50, 0.75]:
       - LONG: Retroceso entre 0.50 y 0.75 del impulso previo (invalida si < 0.75)
       - SHORT: Rebote correctivo entre 0.50 y 0.75 (invalida si > 0.75)
    4. Expansión de volatilidad táctica: ATR(14) > SMA(ATR, 20) en 5M/15M (o marco táctico)
    """
    failures: List[str] = []
    effective_side = (target_side or side or "LONG").upper()
    is_long = effective_side in ("LONG", "BUY")

    # Determinar marco táctico de ejecución (prioridad: df_tactical -> df_5m -> df_1h)
    tactical_df = df_tactical if df_tactical is not None else (df_5m if df_5m is not None else df_1h)

    if df_1h is None or len(df_1h) < 25:
        return {
            "triggered": False,
            "side": "NONE",
            "triad_mode": "multitemporal_1d_1h_5m" if df_1d is not None else "2tf_1h_5m",
            "volatility_regime": "COMPRESSION",
            "failures": ["Historial insuficiente en 1H (se requieren al menos 25 velas para cálculo de medias)."],
            "rules": {
                "rule0_1d_macro_bias": False,
                "rule1_close_gt_ema50": False,
                "rule2_ema21_gt_ema89": False,
                "rule3_fibo_zone": False,
                "rule4_atr_expansion_5m": False,
                "rule4_atr_expansion_tactical": False,
            }
        }

    close_1h_series = df_1h["close"]
    cur_price = current_price if current_price is not None else float(close_1h_series.iloc[-1])
    px_dec = 5 if cur_price < 10.0 else 2

    # 0. Regla 0: Contexto Macro Diario (1D vs EMA 50 1D) cuando está disponible
    rule0_ok = True
    ema50_1d_val: Optional[float] = None
    triad_mode = "2tf_1h_5m"
    if df_1d is not None and isinstance(df_1d, pd.DataFrame) and len(df_1d) >= 25:
        triad_mode = "multitemporal_1d_1h_5m"
        close_1d_series = df_1d["close"]
        ema50_1d_val = float(compute_ema(close_1d_series, min(50, len(close_1d_series))).iloc[-1])
        close_1d_val = float(close_1d_series.iloc[-1])
        if is_long:
            rule0_ok = close_1d_val >= (ema50_1d_val * 0.998)
            if not rule0_ok:
                failures.append(
                    f"Regla 0 (1D) violada: Cierre diario (${close_1d_val:.{px_dec}f}) bajo EMA 50 1D (${ema50_1d_val:.{px_dec}f})."
                )
        else:
            rule0_ok = close_1d_val <= (ema50_1d_val * 1.002)
            if not rule0_ok:
                failures.append(
                    f"Regla 0 (1D) violada: Cierre diario (${close_1d_val:.{px_dec}f}) sobre EMA 50 1D (${ema50_1d_val:.{px_dec}f})."
                )

    # 1. Regla 1: Filtro Direccional con EMA 50 en 1H
    ema50_series = compute_ema(close_1h_series, 50)
    ema50_val = float(ema50_series.iloc[-1])
    if is_long:
        rule1_ok = cur_price > ema50_val
        if not rule1_ok:
            failures.append(f"Regla 1 violada: Precio (${cur_price:.{px_dec}f}) <= EMA 50 1H (${ema50_val:.{px_dec}f}).")
    else:
        rule1_ok = cur_price < ema50_val
        if not rule1_ok:
            failures.append(f"Regla 1 violada: Precio (${cur_price:.{px_dec}f}) >= EMA 50 1H (${ema50_val:.{px_dec}f}).")

    # 2. Regla 2: Alineación Tendencial EMA 21 vs EMA 89 en 1H
    ema21_series = compute_ema(close_1h_series, 21)
    ema89_series = compute_ema(close_1h_series, min(89, max(10, len(close_1h_series))))
    ema21_val = float(ema21_series.iloc[-1])
    ema89_val = float(ema89_series.iloc[-1])
    if is_long:
        rule2_ok = ema21_val > ema89_val
        if not rule2_ok:
            failures.append(f"Regla 2 violada: EMA 21 1H (${ema21_val:.{px_dec}f}) <= EMA 89 1H (${ema89_val:.{px_dec}f}). Sin alineación alcista.")
    else:
        rule2_ok = ema21_val < ema89_val
        if not rule2_ok:
            failures.append(f"Regla 2 violada: EMA 21 1H (${ema21_val:.{px_dec}f}) >= EMA 89 1H (${ema89_val:.{px_dec}f}). Sin alineación bajista.")

    # 3. Regla 3: Retroceso en zona 0.50 - 0.75 de Fibonacci
    rule3_ok = False
    fibo_min = 0.0
    fibo_max = 0.0
    if key_levels is not None:
        fibo_min = min(key_levels.fibo_50, key_levels.fibo_75)
        fibo_max = max(key_levels.fibo_50, key_levels.fibo_75)
    else:
        lookback = min(50, len(df_1h))
        swing_high = float(df_1h["high"].tail(lookback).max())
        swing_low = float(df_1h["low"].tail(lookback).min())
        diff = swing_high - swing_low
        if diff > 0:
            if is_long:
                fibo_min = swing_high - (0.75 * diff)
                fibo_max = swing_high - (0.50 * diff)
            else:
                fibo_min = swing_low + (0.50 * diff)
                fibo_max = swing_low + (0.75 * diff)

    if fibo_min > 0 and fibo_max > 0:
        if is_long:
            if cur_price < fibo_min:
                failures.append(f"Regla 3 violada: Precio (${cur_price:.{px_dec}f}) perforó el límite de invalidación Fibo 0.75 (${fibo_min:.{px_dec}f}).")
            elif cur_price > fibo_max:
                failures.append(f"Regla 3 violada: Precio (${cur_price:.{px_dec}f}) por encima de la Zona Dorada Fibo 0.50 (${fibo_max:.{px_dec}f}). Sin retroceso suficiente.")
            else:
                rule3_ok = True
        else:
            if cur_price > fibo_max:
                failures.append(f"Regla 3 violada: Rebote en corto (${cur_price:.{px_dec}f}) superó el límite de invalidación Fibo 0.75 (${fibo_max:.{px_dec}f}).")
            elif cur_price < fibo_min:
                failures.append(f"Regla 3 violada: Rebote en corto (${cur_price:.{px_dec}f}) no alcanzó la Zona Dorada Fibo 0.50 (${fibo_min:.{px_dec}f}).")
            else:
                rule3_ok = True
    else:
        failures.append("Regla 3 violada: No fue posible calcular la Zona Dorada de Fibonacci.")

    # 4. Regla 4: Gatillo táctico con filtro de volatilidad: ATR(14) > SMA(ATR, 20)
    rule4_ok = False
    atr_tactical_val = 0.0
    atr_sma_tactical_val = 0.0

    if tactical_df is not None and len(tactical_df) >= 20:
        atr_series = compute_atr(tactical_df, min(14, len(tactical_df) // 2))
        atr_sma_series = atr_series.rolling(min(20, len(tactical_df)), min_periods=5).mean().bfill()
        atr_tactical_val = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else 0.0
        atr_sma_tactical_val = float(atr_sma_series.iloc[-1]) if not pd.isna(atr_sma_series.iloc[-1]) else 0.0
        rule4_ok = (atr_tactical_val > atr_sma_tactical_val) and (atr_tactical_val > 0)
        if not rule4_ok:
            failures.append(f"Regla 4 violada: Volatilidad táctica comprimida (ATR: {atr_tactical_val:.5f} <= SMA: {atr_sma_tactical_val:.5f}).")
    else:
        failures.append("Regla 4 violada: Historial insuficiente en marco táctico para calcular ATR y su SMA 20 (mínimo 20 velas).")

    all_passed = rule0_ok and rule1_ok and rule2_ok and rule3_ok and rule4_ok

    return {
        "triggered": all_passed,
        "side": effective_side if all_passed else "NONE",
        "triad_mode": triad_mode,
        "volatility_regime": "EXPANSION" if rule4_ok else "COMPRESSION",
        "current_price": cur_price,
        "failures": failures,
        "rules": {
            "rule0_1d_macro_bias": rule0_ok,
            "rule1_close_gt_ema50": rule1_ok,
            "rule2_ema21_gt_ema89": rule2_ok,
            "rule3_fibo_zone": rule3_ok,
            "rule4_atr_expansion_5m": rule4_ok,
            "rule4_atr_expansion_tactical": rule4_ok,
        },
        "metrics": {
            "ema50_1d": round(ema50_1d_val, px_dec) if ema50_1d_val is not None else None,
            "ema50_1h": round(ema50_val, px_dec),
            "ema21_1h": round(ema21_val, px_dec),
            "ema89_1h": round(ema89_val, px_dec),
            "fibo_zone_min": round(fibo_min, px_dec),
            "fibo_zone_max": round(fibo_max, px_dec),
            "atr_5m": round(atr_tactical_val, 5),
            "atr_sma_5m": round(atr_sma_tactical_val, 5),
            "atr_tactical": round(atr_tactical_val, 5),
            "atr_sma_tactical": round(atr_sma_tactical_val, 5),
        }
    }


def check_universal_wick_veto(df: pd.DataFrame, side: str, max_wick_ratio: float = 0.50) -> Optional[str]:
    """
    Veto Universal Antitrampas:
    Verifica en la última vela cerrada (df.iloc[-1]) si la mecha contraria
    (upper_wick para LONG, lower_wick para SHORT) es >= max_wick_ratio * (high - low).
    Retorna mensaje de veto si se viola, o None si pasa la validación.
    """
    if df is None or len(df) == 0:
        return None
    candle = df.iloc[-1]
    try:
        high = float(candle["high"])
        low = float(candle["low"])
        open_px = float(candle["open"])
        close_px = float(candle["close"])
    except (KeyError, ValueError, TypeError):
        return None

    candle_range = high - low
    if candle_range <= 0:
        return None

    norm_side = str(side or "").upper()
    is_long = norm_side in ("LONG", "BUY")

    if is_long:
        upper_wick = high - max(open_px, close_px)
        wick_ratio = upper_wick / candle_range
        if wick_ratio >= max_wick_ratio:
            return (
                f"Veto Universal de Mechas: Mecha superior contraria ({wick_ratio * 100:.1f}%) "
                f">= {max_wick_ratio * 100:.0f}% en vela cerrada (LONG rechazado)."
            )
    else:
        lower_wick = min(open_px, close_px) - low
        wick_ratio = lower_wick / candle_range
        if wick_ratio >= max_wick_ratio:
            return (
                f"Veto Universal de Mechas: Mecha inferior contraria ({wick_ratio * 100:.1f}%) "
                f">= {max_wick_ratio * 100:.0f}% en vela cerrada (SHORT rechazado)."
            )

    return None


def compute_asymmetric_order_governance(
    entry_price: float,
    atr_14: float,
    side: str = "LONG",
    risk_atr_mult: float = 1.5,
    tp1_rr_ratio: float = 2.0,
    round_trip_fee_pct: float = 0.26,
    ema_21_1h: Optional[float] = None,
    donchian_mid_10: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Gobernanza del Ledger y Salidas Asimétricas (Punto 4):
    1. Entrada: Riesgo fijado a 1.5 x ATR(14).
    2. TP1: Salida parcial del 50% al ratio R:R >= 1:1.5 o 1:2.0.
    3. Pase a Breakeven: Stop en Precio_Entrada + Comisiones (0.26%).
    4. Trailing Stop: 50% remanente siguiendo EMA 21 o Mediana Donchian (10).
    """
    is_long = side.upper() in ("LONG", "BUY")
    risk_distance = max(risk_atr_mult * atr_14, entry_price * 0.005)

    # 1. Stop Loss Inicial
    sl_initial_price = entry_price - risk_distance if is_long else entry_price + risk_distance

    # 2. TP1 (Salida parcial 50% con ratio R:R)
    tp1_distance = risk_distance * tp1_rr_ratio
    tp1_price = entry_price + tp1_distance if is_long else entry_price - tp1_distance

    # 3. Precio Breakeven Real (cubre 100% de comisiones ida y vuelta)
    fee_factor = round_trip_fee_pct / 100.0
    be_price = entry_price * (1.0 + fee_factor) if is_long else entry_price * (1.0 - fee_factor)

    # 4. Referencia de Trailing Stop para el 50% remanente
    trailing_ref = ema_21_1h if ema_21_1h is not None else donchian_mid_10

    px_dec = 5 if entry_price < 10.0 else 4
    return {
        "side": "LONG" if is_long else "SHORT",
        "entry_price": round(entry_price, px_dec),
        "risk_distance": round(risk_distance, px_dec),
        "sl_initial_price": round(sl_initial_price, px_dec),
        "tp1_price": round(tp1_price, px_dec),
        "tp1_trim_pct": 50.0,
        "breakeven_price": round(be_price, px_dec),
        "trailing_reference": round(trailing_ref, px_dec) if trailing_ref is not None else None,
        "round_trip_fee_pct": round_trip_fee_pct,
    }


def evaluate_order_exit_state(
    current_price: float,
    gov: Dict[str, Any],
    tp1_trimmed: bool = False,
    trailing_reference: Optional[float] = None
) -> Dict[str, Any]:
    """
    Evalúa la salida determinista de una posición activa:
    - Antes de TP1: Monitorea SL inicial y TP1.
    - Al tocar TP1: Gatilla toma parcial (50%), desplaza SL a Breakeven Real y activa Trailing.
    - Tras TP1: El 50% remanente corre con Trailing Stop siguiendo la EMA 21 o Mediana Donchian.
    """
    is_long = gov["side"] == "LONG"
    sl_initial = gov["sl_initial_price"]
    tp1_price = gov["tp1_price"]
    be_price = gov["breakeven_price"]

    # Caso 1: Posición previa a TP1
    if not tp1_trimmed:
        # Stop Loss alcanzado
        if (is_long and current_price <= sl_initial) or (not is_long and current_price >= sl_initial):
            return {
                "action": "CLOSE_FULL_SL",
                "exit_price": current_price,
                "reason": "Stop Loss Inicial ejecutado a 1.5x ATR.",
                "tp1_trimmed": False,
            }
        # TP1 alcanzado: Peluqueo del 50%
        if (is_long and current_price >= tp1_price) or (not is_long and current_price <= tp1_price):
            return {
                "action": "TRIM_50%_TP1",
                "exit_price": current_price,
                "reason": f"TP1 alcanzado ({tp1_price:.2f}). Peluqueo 50% a bóveda y Stop a Breakeven Real.",
                "tp1_trimmed": True,
                "new_stop_price": be_price,
            }
        return {"action": "HOLD", "reason": "Posición en seguimiento dentro de los límites."}

    # Caso 2: Posición remanente (50%) con Trailing Stop activo
    effective_stop = be_price
    if trailing_reference is not None:
        if is_long:
            effective_stop = max(be_price, trailing_reference)
        else:
            effective_stop = min(be_price, trailing_reference)

    if (is_long and current_price <= effective_stop) or (not is_long and current_price >= effective_stop):
        return {
            "action": "CLOSE_REMAINING_TRAILING",
            "exit_price": current_price,
            "reason": f"Trailing Stop alcanzado en ${effective_stop:.2f} (50% remanente liquidado sin riesgo).",
            "tp1_trimmed": True,
        }

    return {
        "action": "HOLD_TRAILING",
        "current_stop_price": effective_stop,
        "reason": f"50% remanente corriendo libre con Trailing Stop en ${effective_stop:.2f}."
    }

