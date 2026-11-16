"""
Auditor Cuantitativo Determinista de Velas Japonesas y Flujo Institucional (0 Tokens).
Implementa la taxonomía de Thomas Bulkowski, análisis de volumen VPA (Wyckoff),
divergencias RSI 14, compresión ATR 14 y confluencia con el Buffer de Sesgo Macro del CIO.
"""

import math
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from backend.macro_bias_buffer import MacroBiasBuffer


def detect_candle_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analiza las últimas 3 velas del DataFrame para identificar patrones según
    la geometría estricta de Thomas Bulkowski.
    """
    if len(df) < 3:
        return {"pattern": "INSUFFICIENT_DATA", "type": "NEUTRAL", "win_rate": 0.0, "desc": "Datos insuficientes"}

    c0 = df.iloc[-1]  # Vela actual (última cerrada)
    c1 = df.iloc[-2]  # Vela anterior
    c2 = df.iloc[-3]  # Vela previa

    o0, h0, l0, cl0 = float(c0["open"]), float(c0["high"]), float(c0["low"]), float(c0["close"])
    o1, h1, l1, cl1 = float(c1["open"]), float(c1["high"]), float(c1["low"]), float(c1["close"])
    o2, h2, l2, cl2 = float(c2["open"]), float(c2["high"]), float(c2["low"]), float(c2["close"])

    r0 = max(1e-9, h0 - l0)
    body0 = abs(cl0 - o0)
    upper_wick0 = h0 - max(o0, cl0)
    lower_wick0 = min(o0, cl0) - l0

    r1 = max(1e-9, h1 - l1)
    body1 = abs(cl1 - o1)

    r2 = max(1e-9, h2 - l2)
    body2 = abs(cl2 - o2)

    is_green0 = cl0 >= o0
    is_red0 = cl0 < o0
    is_green1 = cl1 >= o1
    is_red1 = cl1 < o1
    is_green2 = cl2 >= o2
    is_red2 = cl2 < o2

    # 1. Estrella de la Mañana (Morning Star) - 3 velas (Win Rate 78%)
    if is_red2 and r2 > 0 and (body2 / r2) > 0.4:
        if (body1 / r1) < 0.35 and max(o1, cl1) < cl2:  # Vela 2: cuerpo pequeño / estrella por debajo
            if is_green0 and cl0 > (o2 + cl2) / 2.0:  # Vela 3: alcista cerrando > 50% de vela 1
                return {
                    "pattern": "MORNING_STAR",
                    "type": "BULLISH_REVERSAL",
                    "win_rate": 78.0,
                    "desc": "Estrella de la Mañana (Morning Star) validada institucionalmente (78% efectividad Bulkowski)",
                }

    # 2. Estrella del Atardecer (Evening Star) - 3 velas (Win Rate 72%)
    if is_green2 and r2 > 0 and (body2 / r2) > 0.4:
        if (body1 / r1) < 0.35 and min(o1, cl1) > cl2:
            if is_red0 and cl0 < (o2 + cl2) / 2.0:
                return {
                    "pattern": "EVENING_STAR",
                    "type": "BEARISH_REVERSAL",
                    "win_rate": 72.0,
                    "desc": "Estrella del Atardecer (Evening Star) confirmada (72% efectividad bajista)",
                }

    # 3. Tres Soldados Blancos (Three White Soldiers) - 3 velas (Win Rate 82%)
    if (
        cl0 > o0 and cl1 > o1 and cl2 > o2
        and cl0 > cl1 > cl2
        and o0 > o1 and o1 > o2
        and upper_wick0 / r0 < 0.25
    ):
        return {
            "pattern": "THREE_WHITE_SOLDIERS",
            "type": "BULLISH_CONTINUATION",
            "win_rate": 82.0,
            "desc": "Tres Soldados Blancos (Three White Soldiers) en expansión (82% efectividad)",
        }

    # 4. Tres Cuervos Negros (Three Black Crows) - 3 velas (Win Rate 79%)
    if (
        cl0 < o0 and cl1 < o1 and cl2 < o2
        and cl0 < cl1 < cl2
        and o0 < o1 and o1 < o2
        and lower_wick0 / r0 < 0.25
    ):
        return {
            "pattern": "THREE_BLACK_CROWS",
            "type": "BEARISH_CONTINUATION",
            "win_rate": 79.0,
            "desc": "Tres Cuervos Negros (Three Black Crows) en cascada bajista (79% efectividad)",
        }

    # 5. Envolvente Alcista (Bullish Engulfing) - 2 velas (Win Rate 63%)
    if is_red1 and is_green0 and cl0 >= o1 and o0 <= cl1 and body0 > body1 * 1.05:
        return {
            "pattern": "BULLISH_ENGULFING",
            "type": "BULLISH_REVERSAL",
            "win_rate": 63.0,
            "desc": "Envolvente Alcista (Bullish Engulfing) que devora la oferta previa (63% efectividad)",
        }

    # 6. Envolvente Bajista (Bearish Engulfing) - 2 velas (Win Rate 65%)
    if is_green1 and is_red0 and cl0 <= o1 and o0 >= cl1 and body0 > body1 * 1.05:
        return {
            "pattern": "BEARISH_ENGULFING",
            "type": "BEARISH_REVERSAL",
            "win_rate": 65.0,
            "desc": "Envolvente Bajista (Bearish Engulfing) absorbiendo la demanda previa (65% efectividad)",
        }

    # 7. Martillo (Hammer) - 1 vela (Win Rate 60%)
    if (
        lower_wick0 >= 2.0 * max(1e-9, body0)
        and upper_wick0 <= 0.25 * r0
        and (lower_wick0 / r0) >= 0.55
    ):
        return {
            "pattern": "HAMMER",
            "type": "BULLISH_REVERSAL",
            "win_rate": 60.0,
            "desc": "Martillo (Hammer) con rechazo contundente de mínimos institucionales (60% efectividad)",
        }

    # 8. Estrella Fugaz (Shooting Star) - 1 vela (Win Rate 59%)
    if (
        upper_wick0 >= 2.0 * max(1e-9, body0)
        and lower_wick0 <= 0.25 * r0
        and (upper_wick0 / r0) >= 0.55
    ):
        return {
            "pattern": "SHOOTING_STAR",
            "type": "BEARISH_REVERSAL",
            "win_rate": 59.0,
            "desc": "Estrella Fugaz (Shooting Star) con barrida de liquidez superior y rechazo (59% efectividad)",
        }

    # 9. Doji Libélula (Dragonfly Doji) - 1 vela (Win Rate 64%)
    if body0 / r0 <= 0.10 and lower_wick0 / r0 >= 0.70 and upper_wick0 / r0 <= 0.10:
        return {
            "pattern": "DRAGONFLY_DOJI",
            "type": "BULLISH_REVERSAL",
            "win_rate": 64.0,
            "desc": "Doji Libélula (Dragonfly Doji) con absorción total en soporte (64% efectividad)",
        }

    # 10. Doji Lápida (Gravestone Doji) - 1 vela (Win Rate 61%)
    if body0 / r0 <= 0.10 and upper_wick0 / r0 >= 0.70 and lower_wick0 / r0 <= 0.10:
        return {
            "pattern": "GRAVESTONE_DOJI",
            "type": "BEARISH_REVERSAL",
            "win_rate": 61.0,
            "desc": "Doji Lápida (Gravestone Doji) con capitulación de compradores (61% efectividad)",
        }

    # 11. Martillo Invertido (Inverted Hammer) - 1 vela (Win Rate 57%)
    if (
        upper_wick0 >= 2.0 * max(1e-9, body0)
        and lower_wick0 <= 0.20 * r0
        and is_red1  # viene de caída
    ):
        return {
            "pattern": "INVERTED_HAMMER",
            "type": "BULLISH_REVERSAL",
            "win_rate": 57.0,
            "desc": "Martillo Invertido (Inverted Hammer) testeando liquidez superior tras soporte (57% efectividad)",
        }

    # 12. Hombre Colgado (Hanging Man) - 1 vela (Win Rate 59%)
    if (
        lower_wick0 >= 2.0 * max(1e-9, body0)
        and upper_wick0 <= 0.20 * r0
        and is_green1  # viene de subida
    ):
        return {
            "pattern": "HANGING_MAN",
            "type": "BEARISH_REVERSAL",
            "win_rate": 59.0,
            "desc": "Hombre Colgado (Hanging Man) advirtiendo debilidad en techo (59% efectividad bajista)",
        }

    # 13. Marubozu Alcista (Win Rate 56%)
    if is_green0 and (body0 / r0) >= 0.85:
        return {
            "pattern": "MARUBOZU_BULL",
            "type": "BULLISH_CONTINUATION",
            "win_rate": 56.0,
            "desc": "Marubozu Alcista de impulso sin mechas (56% efectividad)",
        }

    # 14. Marubozu Bajista (Win Rate 57%)
    if is_red0 and (body0 / r0) >= 0.85:
        return {
            "pattern": "MARUBOZU_BEAR",
            "type": "BEARISH_CONTINUATION",
            "win_rate": 57.0,
            "desc": "Marubozu Bajista de liquidación plena (57% efectividad)",
        }

    # 15. Impulso Alcista (Bullish Impulse) - Vela de Expansión (Win Rate 62%)
    if is_green0 and (body0 / r0) >= 0.60 and body0 > (body1 * 1.15) and upper_wick0 <= (0.20 * r0):
        return {
            "pattern": "BULLISH_IMPULSE",
            "type": "BULLISH_CONTINUATION",
            "win_rate": 62.0,
            "desc": "Impulso Alcista Institucional con cuerpo expansivo y absorción de oferta (62% efectividad)",
        }

    return {
        "pattern": "NONE",
        "type": "NEUTRAL",
        "win_rate": 50.0,
        "desc": "Sin patrón de velas destacado de Bulkowski",
    }


def detect_rsi_divergence(df: pd.DataFrame, window: int = 14) -> Dict[str, Any]:
    """
    Audita divergencias cuantitativas entre el precio y el oscilador RSI 14.
    - Divergencia Alcista: Precio marca Lower Low (mínimo más bajo) y RSI marca Higher Low (mínimo más alto).
    - Divergencia Bajista: Precio marca Higher High (máximo más alto) y RSI marca Lower High (máximo más bajo).
    """
    if len(df) < window + 5 or "rsi" not in df.columns:
        return {"divergence": "NONE", "confidence_boost": 0}

    recent_df = df.iloc[-(window + 2):].copy()
    price_lows = recent_df["low"].values
    rsi_vals = recent_df["rsi"].values

    # Buscar dos valles de precio y RSI
    mid = len(recent_df) // 2
    p_min1, p_min2 = np.min(price_lows[:mid]), np.min(price_lows[mid:])
    idx1, idx2 = np.argmin(price_lows[:mid]), mid + np.argmin(price_lows[mid:])

    rsi1, rsi2 = rsi_vals[idx1], rsi_vals[idx2]

    # Bullish Divergence: Precio hizo nuevo mínimo, pero RSI no lo acompañó
    if p_min2 < p_min1 and rsi2 > rsi1 and rsi2 < 45.0:
        return {
            "divergence": "BULLISH",
            "confidence_boost": 15,
            "desc": f"Divergencia Alcista RSI confirmada (Precio: {p_min1:.2f} -> {p_min2:.2f}, RSI: {rsi1:.1f} -> {rsi2:.1f})",
        }

    # Bearish Divergence
    price_highs = recent_df["high"].values
    p_max1, p_max2 = np.max(price_highs[:mid]), np.max(price_highs[mid:])
    h_idx1, h_idx2 = np.argmax(price_highs[:mid]), mid + np.argmax(price_highs[mid:])
    rsi_h1, rsi_h2 = rsi_vals[h_idx1], rsi_vals[h_idx2]

    if p_max2 > p_max1 and rsi_h2 < rsi_h1 and rsi_h2 > 55.0:
        return {
            "divergence": "BEARISH",
            "confidence_boost": -15,
            "desc": f"Divergencia Bajista RSI detectada (Agotamiento de compradores)",
        }

    return {"divergence": "NONE", "confidence_boost": 0, "desc": "Sin divergencia RSI significativa"}


def audit_candlestick_confluence(
    symbol: str,
    df: pd.DataFrame,
    ind: Dict[str, Any],
    fee: float = 0.1,
    spread: float = 0.05,
    min_profit_pct: float = 0.5,
) -> Dict[str, Any]:
    """
    Auditor central cuantitativo de velas y flujo institucional.
    Calcula en Python puro (0 tokens):
    1. Geometría de velas Bulkowski
    2. Volumen relativo institucional RVOL (Wyckoff)
    3. Divergencias RSI 14 (+15% si hay, -15% si falta en reversión)
    4. Compresión ATR 14 (filtro squeeze)
    5. Posición vs VWAP y EMA 200
    6. Asimetría matemática R:R >= 1:2.0
    7. Confluencia con MacroBiasBuffer
    """
    buffer = MacroBiasBuffer()
    active_bias = buffer.get_bias(symbol)

    candle_info = detect_candle_pattern(df)
    rsi_div = detect_rsi_divergence(df)

    latest = ind["latest"]
    price = float(latest["close"])
    atr = float(ind.get("atr_14") or 0.0)
    rvol = float(ind.get("relative_volume") or 1.0)
    rsi_val = float(latest.get("rsi", 50.0))
    vwap_val = float(latest.get("vwap", price))
    ema200_slope = ind.get("ema_200_slope_pct")

    # Filtro de compresión de volatilidad ATR (Percentil inferior / Squeeze)
    atr_series = df["atr_14"].dropna() if "atr_14" in df.columns else pd.Series([atr])
    sma_atr = float(atr_series.rolling(20).mean().iloc[-1]) if len(atr_series) >= 20 else atr
    is_atr_squeeze = atr < (0.70 * sma_atr) if sma_atr > 0 else False

    # Base de confianza inicial basada en la efectividad histórica de Bulkowski
    base_conf = int(candle_info["win_rate"])

    # Ajuste por divergencia RSI
    if candle_info["type"] == "BULLISH_REVERSAL":
        if rsi_div["divergence"] == "BULLISH":
            base_conf = min(95, base_conf + 15)
        elif rsi_div["divergence"] == "BEARISH":
            base_conf = max(35, base_conf - 15)
        # Si divergence == "NONE", se preserva la fiabilidad base estadística de Bulkowski

    # Ajuste por RVOL institucional (Wyckoff VPA)
    if rvol >= 1.8:
        base_conf = min(98, base_conf + 10)
    elif rvol < 0.65:
        base_conf = max(35, base_conf - 10)

    # Cálculo de SL y TP asimétrico con filtro ATR (calibrado por clase de activo: Cripto vs Forex =X vs TradFi)
    min_sl_floor = 0.0012 if "=X" in str(symbol).upper() else (0.015 if "/" in str(symbol) else 0.008)
    sl_dist = max(price * min_sl_floor, 1.5 * atr) if atr > 0 else price * min_sl_floor
    sl_pct = (sl_dist / price) * 100.0
    # Asimetría obligatoria R:R >= 1:2.0
    round_trip_cost = (fee * 2.0) + spread
    tp_pct = max(sl_pct * 2.333, round_trip_cost + min_profit_pct + (sl_pct * 2.0))
    rr_ratio = round(tp_pct / sl_pct, 2) if sl_pct > 0 else 2.0

    # Veredicto de Confluencia
    is_bullish_pattern = candle_info["type"] in ("BULLISH_REVERSAL", "BULLISH_CONTINUATION")
    has_macro_bull = active_bias and active_bias.get("bias") in ("ALCISTA", "OPORTUNIDAD")
    has_macro_veto = active_bias and active_bias.get("bias") in ("BAJISTA", "PELIGRO", "VETO")

    eligible = False
    verdict = "[CHEQUEADO: ABSTENCIÓN]"
    reason = "Sin confluencia suficiente."

    if has_macro_veto:
        verdict = "[CHEQUEADO: ABSTENCIÓN · VETO MACRO ACTIVO]"
        reason = f"Alerta macro activa del CIO ({active_bias.get('thesis', '')[:80]}). Compras bloqueadas."
        buffer.update_verdict(symbol, "VETOED", verdict, {"reason": reason})

    elif rsi_val < 25.0:
        verdict = "[CHEQUEADO: ABSTENCIÓN · CAÍDA VERTICAL SIN ABSORCIÓN]"
        reason = f"RSI extremo en {rsi_val:.1f} (<25). Esperando freno y absorción institucional."

    elif price < vwap_val and ema200_slope is not None and ema200_slope < -0.04:
        verdict = "[CHEQUEADO: ABSTENCIÓN · BAJO VWAP CON TENDENCIA BAJISTA]"
        reason = f"Precio bajo VWAP diario institucional con EMA200 descendente ({ema200_slope:.2f}%)."

    elif is_atr_squeeze and candle_info["type"] == "BULLISH_CONTINUATION":
        verdict = "[CHEQUEADO: ABSTENCIÓN · MERCADO EN COMPRESIÓN]"
        reason = "ATR en squeeze de volatilidad. Patrón de continuación vetado para evitar trampa de ruptura (whipsaw)."

    elif is_bullish_pattern and base_conf >= 55 and rr_ratio >= 2.0:
        eligible = True
        if has_macro_bull:
            setup_grade = "A++ (CONFLUENCIA MACRO + MICRO)"
            verdict = f"[CHEQUEADO: COMPRA FIRME · {setup_grade}]"
            reason = (
                f"{candle_info['desc']}. RVOL {rvol:.1f}x. {rsi_div['desc']}. "
                f"Sesgo Macro CIO favorable ({active_bias.get('confidence', 80)}% conf). R:R neto {rr_ratio}x."
            )
            buffer.update_verdict(symbol, "CONFIRMED_BUY", verdict, {
                "pattern": candle_info["pattern"],
                "rvol": rvol,
                "rsi_div": rsi_div["divergence"],
                "rr_ratio": rr_ratio,
            })
        else:
            setup_grade = "A (TÉCNICO CUANTITATIVO)"
            verdict = f"[CHEQUEADO: COMPRA FIRME · {setup_grade}]"
            reason = (
                f"{candle_info['desc']}. RVOL {rvol:.1f}x. {rsi_div['desc']}. "
                f"Estructura asimétrica R:R {rr_ratio}x. SL {sl_pct:.2f}% fuera de ruido ATR."
            )
    else:
        verdict = "[CHEQUEADO: DESCARTADO · SIN PATRÓN VÁLIDO]"
        reason = f"Sin confluencia geométrica (Patrón: {candle_info['pattern']}, Conf: {base_conf}%, R:R: {rr_ratio}x)."

    return {
        "symbol": symbol,
        "eligible": eligible,
        "verdict": verdict,
        "reason": reason,
        "pattern_name": candle_info["pattern"],
        "pattern_desc": candle_info["desc"],
        "win_rate": candle_info["win_rate"],
        "confidence": base_conf,
        "rvol": round(rvol, 2),
        "rsi_divergence": rsi_div["divergence"],
        "rsi_divergence_desc": rsi_div["desc"],
        "is_atr_squeeze": is_atr_squeeze,
        "sl_pct": round(sl_pct, 2),
        "tp_pct": round(tp_pct, 2),
        "rr_ratio": rr_ratio,
        "active_macro_bias": active_bias,
    }
