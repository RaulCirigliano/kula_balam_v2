# -*- coding: utf-8 -*-
"""
ESTRATEGIA HEREDADA EN CONTENEDOR DE AUDITORÍA: Triple Confluencia Swing 4H
Doctrina: Cruce tendencial EMA 21 / EMA 89, confirmación con expansión de volatilidad ATR(14) > SMA20(ATR) y R:R >= 1:2.0.
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_ETH_USDT_4h.parquet"
MAX_BARS_HOLD = 60

def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_tc4h_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
        df["_atr14"] = tr.rolling(14).mean().shift(1).bfill()
        df["_atr_sma20"] = df["_atr14"].rolling(20).mean().shift(1).bfill()
        df["_ema21"] = df["close"].ewm(span=21, adjust=False).mean().shift(1)
        df["_ema89"] = df["close"].ewm(span=89, adjust=False).mean().shift(1)
        df["_tc4h_init"] = True

    if i < 95:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    c = float(row["close"])
    o = float(row["open"])
    e21 = float(row["_ema21"])
    e89 = float(row["_ema89"])
    atr14 = float(row["_atr14"])
    atr_sma = float(row["_atr_sma20"])

    # Filtro de expansión de volatilidad activa
    expansion_atr = atr14 > atr_sma

    # LONG Swing: EMA 21 > EMA 89 con precio superando la EMA rápida y expansión ATR
    if (e21 > e89) and (c > e21) and expansion_atr and (c > o):
        sl_dist = 1.50 * atr14
        tp_dist = 3.30 * atr14  # Asimetría R:R 1:2.20
        return True, "LONG", c - sl_dist, c + tp_dist

    # SHORT Swing: EMA 21 < EMA 89 con precio bajo EMA rápida y expansión ATR
    if (e21 < e89) and (c < e21) and expansion_atr and (c < o):
        sl_dist = 1.50 * atr14
        tp_dist = 3.30 * atr14
        return True, "SHORT", c + sl_dist, c - tp_dist

    return False, None, 0.0, 0.0


def arbitro_ia(fila, lado, entry, sl, tp) -> Tuple[bool, float, str]:
    dist_sl = abs(float(entry) - float(sl))
    dist_tp = abs(float(tp) - float(entry))
    rr = dist_tp / (dist_sl + 1e-9)

    if rr < 2.0:
        return False, 0.0, f"VETO Asimetría insuficiente ({rr:.2f} < 2.0)"

    return True, 1.0, "AUTORIZADO: Triple confluencia de medias y volatilidad confirmada"
