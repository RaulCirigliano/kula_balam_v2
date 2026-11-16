# -*- coding: utf-8 -*-
"""
Kula Balam: Fórmula Matemática SMR (Synthetic Mean Reversion Index)
Temporalidad declarada: 4h | Dataset objetivo: binance_SOL_USDT_4h.parquet
Filtros: EMA 200 (Régimen Macro) + BBW Squeeze (Percentil 10%)
Gestión: R:R Asimétrico 1:2.07 (SL 1.5x ATR, TP 3.1x ATR)
"""
from typing import Tuple, Optional
import pandas as pd
import numpy as np

DATASET = "binance_SOL_USDT_4h.parquet"
MAX_BARS_HOLD = 60


# -----------------------------------------------------------------------------
# SHIMS DE COMPATIBILIDAD (Pure Pandas / NumPy sin dependencias externas)
# -----------------------------------------------------------------------------
class _TALibShim:
    @staticmethod
    def EMA(series: pd.Series, timeperiod: int = 200) -> pd.Series:
        return series.ewm(span=timeperiod, adjust=False).mean()

    @staticmethod
    def RSI(series: pd.Series, timeperiod: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1.0 / timeperiod, min_periods=timeperiod, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / timeperiod, min_periods=timeperiod, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def ATR(df: pd.DataFrame, timeperiod: int = 14) -> pd.Series:
        prev_c = df["close"].shift(1)
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - prev_c).abs(),
            (df["low"] - prev_c).abs()
        ], axis=1).max(axis=1)
        return tr.rolling(timeperiod).mean()

ta = _TALibShim()


# -----------------------------------------------------------------------------
# MOTOR MATEMÁTICO PRINCIPAL (Kula Balam SMR)
# -----------------------------------------------------------------------------
def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_smr_init" not in df.columns:
        d = df.copy()

        # 1. Bandas de Bollinger y %B Normalizado al espacio [-1.0, 1.0]
        mid = d["close"].rolling(20).mean()
        std = d["close"].rolling(20).std()
        upper = mid + (2.0 * std)
        lower = mid - (2.0 * std)
        pct_b = (d["close"] - lower) / (upper - lower + 1e-9)
        b_norm = (pct_b - 0.5) * 2.0

        # 2. RSI (14) Normalizado al espacio [-1.0, 1.0]
        rsi = ta.RSI(d["close"], timeperiod=14)
        rsi_norm = (rsi - 50.0) / 50.0

        # 3. Estocástico (14, 3) Normalizado al espacio [-1.0, 1.0]
        low14 = d["low"].rolling(14).min()
        high14 = d["high"].rolling(14).max()
        stoch_k = 100.0 * (d["close"] - low14) / (high14 - low14 + 1e-9)
        stoch_norm = (stoch_k - 50.0) / 50.0

        # 4. Índice SMR Compuesto (Ponderación Kula Balam: 0.45, 0.35, 0.20)
        d["smr"] = (0.45 * b_norm) + (0.35 * rsi_norm) + (0.20 * stoch_norm)
        d["smr_slope"] = d["smr"].diff()

        # 5. Filtro de Régimen Macro: EMA 200
        d["ema_200"] = ta.EMA(d["close"], timeperiod=200)

        # 6. Detección de Fugas (BBW Squeeze en percentil 10%)
        bbw = (upper - lower) / (mid + 1e-9)
        bbw_q10 = bbw.rolling(120, min_periods=30).quantile(0.10)
        is_squeeze = (bbw < bbw_q10).fillna(False).astype(bool)
        not_squeeze = (~is_squeeze).shift(1).fillna(True).astype(bool)

        # 7. ATR Adaptativo para Stops Dinámicos
        d["atr"] = ta.ATR(d, timeperiod=14).bfill()

        # GATILLOS SMR BIDIRECCIONALES:
        # LONG: SMR en sobreventa (< -0.55), giro alcista, sobre EMA200 y fuera de squeeze
        cond_long = (
            (d["close"].shift(1) >= d["ema_200"].shift(1)) &
            (d["smr"].shift(1) < -0.55) &
            (d["smr_slope"].shift(1) > 0) &
            not_squeeze
        )

        # SHORT: SMR en sobrecompra (> +0.55), giro bajista, bajo EMA200 y fuera de squeeze
        cond_short = (
            (d["close"].shift(1) < d["ema_200"].shift(1)) &
            (d["smr"].shift(1) > 0.55) &
            (d["smr_slope"].shift(1) < 0) &
            not_squeeze
        )

        df["_smr_enter_long"] = cond_long.fillna(False).astype(bool)
        df["_smr_enter_short"] = cond_short.fillna(False).astype(bool)
        df["_smr_atr"] = d["atr"].fillna(d["close"] * 0.02)
        df["_smr_init"] = True

    # Período de calentamiento mínimo
    if i < 60:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    c = float(row["close"])
    atr = float(row.get("_smr_atr", c * 0.02))

    # Asimetría matemática: R:R = 3.1 / 1.5 = 1:2.07 (supera el 1:1.95 del Árbitro IA)
    sl_dist = 1.5 * atr
    tp_dist = 3.1 * atr

    if bool(row.get("_smr_enter_long", False)):
        return True, "LONG", c - sl_dist, c + tp_dist

    if bool(row.get("_smr_enter_short", False)):
        return True, "SHORT", c + sl_dist, c - tp_dist

    return False, None, 0.0, 0.0