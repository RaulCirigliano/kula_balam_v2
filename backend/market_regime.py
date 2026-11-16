"""
Módulo: backend/market_regime.py
Proyecto: Kula Balam
Clasificador determinista de régimen de mercado (Punto 2):
Heurística numérica basada en ADX (fuerza), pendiente de EMA 200 (10 velas) y ratio/percentil de ATR 14 vs SMA(ATR, 20).
"""

from typing import Any, Dict, Literal, Tuple
import numpy as np
import pandas as pd

RegimeType = Literal["Calma", "Tendencia", "Crisis"]


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calcula el Average Directional Index (ADX) con suavizado exponencial estándar de Wilder.
    """
    if len(df) < period * 2:
        return pd.Series(index=df.index, dtype=float)

    high = df["high"]
    low = df["low"]
    close = df["close"]

    # Rango Verdadero (TR)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Movimiento Direccional (+DM, -DM)
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm_series = pd.Series(plus_dm, index=df.index)
    minus_dm_series = pd.Series(minus_dm, index=df.index)

    # Suavizado de Wilder (alpha = 1 / period)
    alpha = 1.0 / period
    tr_smooth = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_dm_smooth = plus_dm_series.ewm(alpha=alpha, adjust=False).mean()
    minus_dm_smooth = minus_dm_series.ewm(alpha=alpha, adjust=False).mean()

    # Indicadores Direccionales (+DI, -DI)
    plus_di = 100.0 * (plus_dm_smooth / (tr_smooth + 1e-9))
    minus_di = 100.0 * (minus_dm_smooth / (tr_smooth + 1e-9))

    # Índice Direccional (DX) y ADX
    dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9))
    adx = dx.ewm(alpha=alpha, adjust=False).mean()
    return adx


def compute_ema_slope(df: pd.DataFrame, ema_period: int = 200, lookback_bars: int = 10) -> float:
    """
    Calcula la pendiente porcentual de la EMA a N velas de retroceso:
    slope = ((EMA[-1] - EMA[-10]) / EMA[-10]) * 100
    """
    if len(df) < (ema_period + lookback_bars):
        # Fallback a EMA más corta si la serie es intermedia
        span = max(20, min(ema_period, len(df) // 2))
    else:
        span = ema_period

    ema = df["close"].ewm(span=span, adjust=False).mean()
    if len(ema) <= lookback_bars:
        return 0.0
    
    prev_val = float(ema.iloc[-lookback_bars - 1])
    curr_val = float(ema.iloc[-1])
    if prev_val <= 0:
        return 0.0
    return ((curr_val - prev_val) / prev_val) * 100.0


def compute_atr_ratio(df: pd.DataFrame, atr_period: int = 14, sma_period: int = 20) -> Tuple[float, float]:
    """
    Calcula el ATR(14) actual y el ratio frente a su media de 20 períodos:
    ratio = ATR(14)[-1] / SMA(ATR(14), 20)[-1]
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(atr_period).mean()
    atr_sma = atr.rolling(sma_period).mean()

    curr_atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
    curr_sma = float(atr_sma.iloc[-1]) if not pd.isna(atr_sma.iloc[-1]) else 0.0

    ratio = (curr_atr / curr_sma) if curr_sma > 0 else 1.0
    return curr_atr, ratio


def compute_atr_percentile_100(df: pd.DataFrame, atr_period: int = 14, window: int = 100) -> float:
    """Calcula el percentil del ATR(14) en una ventana histórica de 100 velas."""
    if len(df) < atr_period + 5:
        return 50.0
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(atr_period).mean().dropna()
    if len(atr) == 0:
        return 50.0
    atr_window = atr.tail(window)
    curr_atr = float(atr_window.iloc[-1])
    # Si la serie de ATR es prácticamente plana sin dispersión, el percentil es neutro (50%)
    if (atr_window.max() - atr_window.min()) < 1e-6:
        return 50.0
    pct = float((atr_window <= curr_atr).mean() * 100.0)
    return pct


def classify_market_regime(
    df: pd.DataFrame,
    adx_trend_threshold: float = 25.0,
    crisis_atr_ratio_threshold: float = 1.75
) -> Dict[str, Any]:
    """
    Clasificador determinista de régimen de mercado:
    - 'Crisis': Percentil ATR(14) > 90% (en 100 velas) o ratio ATR >= 1.75 -> veto_active = True.
    - 'Tendencia': ADX >= 25 con |delta EMA 200| > 0 y sin shock de volatilidad.
    - 'Calma': ADX < 20 (o < 25) y volatilidad en percentiles normales.
    """
    if df is None or len(df) < 25:
        return {
            "regime": "Calma",
            "veto_active": False,
            "adx": 0.0,
            "ema_slope_pct": 0.0,
            "atr_ratio": 1.0,
            "atr_percentile": 50.0,
            "reason": "Historial insuficiente de velas para clasificar régimen (default: Calma)"
        }

    adx_series = compute_adx(df, period=14)
    adx_val = float(adx_series.iloc[-1]) if (len(adx_series) > 0 and not pd.isna(adx_series.iloc[-1])) else 15.0

    slope = compute_ema_slope(df, ema_period=200, lookback_bars=10)
    atr_val, atr_ratio = compute_atr_ratio(df, atr_period=14, sma_period=20)
    atr_pctile = compute_atr_percentile_100(df, atr_period=14, window=100)

    # Regla 1: Shock de volatilidad / Crisis (Percentil ATR > 90% con expansión o ratio extremo)
    is_crisis = (atr_pctile > 90.0 and atr_ratio >= 1.30) or (atr_ratio >= crisis_atr_ratio_threshold)
    if is_crisis:
        return {
            "regime": "Crisis",
            "veto_active": True,
            "adx": round(adx_val, 2),
            "ema_slope_pct": round(slope, 3),
            "atr_ratio": round(atr_ratio, 2),
            "atr_percentile": round(atr_pctile, 1),
            "reason": f"Alerta de volatilidad extrema / Crisis: Percentil ATR ({atr_pctile:.1f}% > 90%) y ratio ATR ({atr_ratio:.2f}x). Veto total activado."
        }

    # Regla 2: Tendencia (ADX fuerte >= 25 y pendiente alineada)
    if adx_val >= adx_trend_threshold and abs(slope) > 0.0:
        direction = "Alcista" if slope > 0 else "Bajista"
        return {
            "regime": "Tendencia",
            "veto_active": False,
            "adx": round(adx_val, 2),
            "ema_slope_pct": round(slope, 3),
            "atr_ratio": round(atr_ratio, 2),
            "atr_percentile": round(atr_pctile, 1),
            "reason": f"Tendencia {direction} confirmada: ADX ({adx_val:.1f} >= {adx_trend_threshold:.1f}) y pendiente EMA ({slope:+.3f}%)."
        }

    # Regla 3: Calma (Rango, consolidación, baja direccionalidad)
    return {
        "regime": "Calma",
        "veto_active": False,
        "adx": round(adx_val, 2),
        "ema_slope_pct": round(slope, 3),
        "atr_ratio": round(atr_ratio, 2),
        "atr_percentile": round(atr_pctile, 1),
        "reason": f"Mercado sin dirección / Calma: ADX ({adx_val:.1f} < {adx_trend_threshold:.1f}) con volatilidad controlada."
    }
