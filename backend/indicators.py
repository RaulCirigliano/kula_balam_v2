"""
Módulo: backend/indicators.py
Proyecto: Kula Balam
Funciones deterministas de cálculo de indicadores de volatilidad, compresión de canal
y Volumen Relativo por Hora del Día (RVOL-TOD) estrictamente causal.
"""

from collections import defaultdict, deque
import math
from typing import Deque, Dict, Optional, Tuple

import numpy as np
import pandas as pd


_INTRADAY_TFS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h"}


def _extract_utc_hm(ts_val) -> Optional[Tuple[int, int]]:
    """Extrae (hora, minuto) UTC a partir de timestamp (ms, s o Timestamp pandas)."""
    if ts_val is None or pd.isna(ts_val):
        return None
    try:
        if isinstance(ts_val, pd.Timestamp):
            dt = ts_val.tz_convert("UTC") if ts_val.tzinfo is not None else ts_val
            return int(dt.hour), int(dt.minute)
        num = float(ts_val)
        if not math.isfinite(num) or num <= 0:
            return None
        sec = num / 1000.0 if num > 1e11 else num
        dt = pd.to_datetime(sec, unit="s", utc=True)
        return int(dt.hour), int(dt.minute)
    except Exception:
        return None


def compute_rvol_tod(
    df: pd.DataFrame,
    timeframe: str = "1h",
    max_sessions: int = 10,
    min_tod_samples: int = 3,
    fallback_window: int = 20,
) -> pd.Series:
    """
    Calcula RVOL (Volumen Relativo por Hora del Día) estrictamente causal (0 look-ahead):
      - En temporalidades intradía (1m..4h): divide el volumen de cada vela entre el promedio
        de las últimas `max_sessions` (5–10) sesiones previas en esa misma hora:minuto exacta
        (excluyendo la vela actual), siempre que existan al menos `min_tod_samples` muestras previas.
      - En `1d` o cuando haya < `min_tod_samples` muestras previas en esa franja horaria:
        usa el fallback causal `volume / volume.shift(1).rolling(fallback_window).mean()`.
      - Si el activo no tiene volumen real (ej. Forex con volumen 0) o el dato no es finito,
        retorna NaN de forma segura (sin Inf ni divisiones por cero).
    """
    if df is None or len(df) == 0 or "volume" not in df.columns:
        return pd.Series(dtype="float64", index=df.index if df is not None else None)

    vols = pd.to_numeric(df["volume"], errors="coerce").astype(float)
    tf_norm = str(timeframe or "1h").strip().lower()
    use_tod = tf_norm in _INTRADAY_TFS

    has_ts_col = "timestamp" in df.columns
    ts_source = df["timestamp"].tolist() if has_ts_col else list(df.index)

    rolling_base = vols.where(vols > 0.0).shift(1).rolling(window=max(1, int(fallback_window)), min_periods=1).mean()
    tod_history: Dict[Tuple[int, int], Deque[float]] = defaultdict(lambda: deque(maxlen=max(1, int(max_sessions))))

    out = np.full(len(df), np.nan, dtype="float64")
    vol_vals = vols.to_numpy(dtype="float64")
    roll_vals = rolling_base.to_numpy(dtype="float64")

    for i in range(len(df)):
        v = vol_vals[i]
        hm = _extract_utc_hm(ts_source[i]) if use_tod else None

        if not math.isfinite(v) or v <= 0.0:
            continue

        denom = np.nan
        if use_tod and hm is not None:
            hist = tod_history[hm]
            if len(hist) >= int(min_tod_samples):
                denom = float(sum(hist)) / float(len(hist))

        if (not math.isfinite(denom) or denom <= 0.0) and math.isfinite(roll_vals[i]) and roll_vals[i] > 0.0:
            denom = float(roll_vals[i])

        if math.isfinite(denom) and denom > 0.0:
            val = v / denom
            if math.isfinite(val):
                out[i] = val

        # Actualizar historial estrictamente DESPUÉS de calcular la barra actual (causalidad)
        if use_tod and hm is not None:
            tod_history[hm].append(float(v))

    return pd.Series(out, index=df.index, dtype="float64")


def compute_bandwidth(df: pd.DataFrame, period_entry: int = 24) -> pd.Series:
    """
    Calcula el ancho relativo normalizado del canal Donchian respecto a la EMA del precio de cierre.
    Bandwidth = (Donchian_High_N - Donchian_Low_N) / EMA(Close, N)
    """
    high_n = df['high'].rolling(window=period_entry).max()
    low_n = df['low'].rolling(window=period_entry).min()
    ema_close = df['close'].ewm(span=period_entry, adjust=False).mean()
    return (high_n - low_n) / ema_close


def check_bandwidth_expansion_filter(
    df: pd.DataFrame,
    period_entry: int = 24,
    sma_period: int = 48
) -> bool:
    """
    Filtro de expansión de volatilidad:
    Exige que el ancho actual del canal supere su media móvil de 48 períodos:
    Bandwidth[-1] > SMA(Bandwidth, 48)[-1]
    
    Si el historial es insuficiente o hay NaNs, devuelve False de forma segura.
    """
    if df is None or len(df) < (period_entry + sma_period):
        return False

    bw = compute_bandwidth(df, period_entry=period_entry)
    bw_sma = bw.rolling(window=sma_period).mean()
    
    if pd.isna(bw.iloc[-1]) or pd.isna(bw_sma.iloc[-1]):
        return False
        
    return bool(bw.iloc[-1] > bw_sma.iloc[-1])
