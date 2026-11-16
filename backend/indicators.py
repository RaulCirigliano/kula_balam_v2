"""
Módulo: backend/indicators.py
Proyecto: Kula Balam
Funciones deterministas de cálculo de indicadores de volatilidad y compresión de canal.
"""

import pandas as pd


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
