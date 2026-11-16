# -*- coding: utf-8 -*-
"""
ESTRATEGIA HEREDADA EN CONTENEDOR DE AUDITORÍA: Alex Ruiz Tríada 3 Velas
Doctrina: Fractal de impulso con retroceso a Zona Dorada Fibonacci (0.50 - 0.75), filtro EMA 50 y confirmación por quiebre de vela precedente.
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_BTC_USDT_4h.parquet"
MAX_BARS_HOLD = 48

def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_alex_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
        df["_atr14"] = tr.rolling(14).mean().shift(1).bfill()
        df["_ema50"] = df["close"].ewm(span=50, adjust=False).mean().shift(1)
        df["_ema200"] = df["close"].ewm(span=200, adjust=False).mean().shift(1)
        df["_h35"] = df["high"].shift(1).rolling(35).max().bfill()
        df["_l35"] = df["low"].shift(1).rolling(35).min().bfill()
        df["_alex_init"] = True

    if i < 55:
        return False, None, 0.0, 0.0

    curr = df.iloc[i]
    prev = df.iloc[i - 1]

    c = float(curr["close"])
    h = float(curr["high"])
    l = float(curr["low"])
    h_prev = float(prev["high"])
    l_prev = float(prev["low"])

    ema50 = float(curr["_ema50"])
    ema200 = float(curr["_ema200"])
    atr = float(curr["_atr14"])

    h_swing = float(curr["_h35"])
    l_swing = float(curr["_l35"])
    rng = max(h_swing - l_swing, 1e-9)

    fibo_50 = h_swing - (0.50 * rng)
    fibo_75 = h_swing - (0.75 * rng)

    # LONG: Macro alcista (EMA 50 > EMA 200) + Zona Dorada (0.50 - 0.75) + Quiebre de vela previa
    if (ema50 > ema200) and (fibo_75 <= c <= fibo_50) and (c > ema50) and (c > h_prev):
        sl_dist = max(c - fibo_75 + (0.5 * atr), 1.5 * atr)
        tp_dist = 2.2 * sl_dist  # R:R 1:2.20
        return True, "LONG", c - sl_dist, c + tp_dist

    # SHORT: Macro bajista (EMA 50 < EMA 200) + Rebote Zona Dorada + Perforación de vela previa
    fibo_short_50 = l_swing + (0.50 * rng)
    fibo_short_75 = l_swing + (0.75 * rng)
    if (ema50 < ema200) and (fibo_short_50 <= c <= fibo_short_75) and (c < ema50) and (c < l_prev):
        sl_dist = max(fibo_short_75 - c + (0.5 * atr), 1.5 * atr)
        tp_dist = 2.2 * sl_dist
        return True, "SHORT", c + sl_dist, c - tp_dist

    return False, None, 0.0, 0.0


def arbitro_ia(fila, lado, entry, sl, tp) -> Tuple[bool, float, str]:
    dist_sl = abs(float(entry) - float(sl))
    dist_tp = abs(float(tp) - float(entry))
    rr = dist_tp / (dist_sl + 1e-9)

    if rr < 2.0:
        return False, 0.0, f"VETO Asimetría insuficiente ({rr:.2f} < 2.0)"

    return True, 1.0, "AUTORIZADO: Alex Ruiz Tríada validada con asimetría"
