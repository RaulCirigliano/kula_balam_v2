# -*- coding: utf-8 -*-
"""
ESTRATEGIA HEREDADA EN CONTENEDOR DE AUDITORÍA: Hyenuk Chu Swing Multibagger
Doctrina: Seguidor tendencial con Vela Elefante, precio sobre EMA 200 y SMA 20, y filtro anti-euforia (RSI <= 70).
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "yf_QQQ_1d.parquet"
MAX_BARS_HOLD = 40

def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_chu_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
        df["_atr14"] = tr.rolling(14).mean().shift(1).bfill()
        df["_ema200"] = df["close"].ewm(span=200, adjust=False).mean().shift(1)
        df["_sma20"] = df["close"].rolling(20).mean().shift(1).bfill()
        
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        df["_rsi14"] = (100.0 - (100.0 / (1.0 + rs))).shift(1).fillna(50.0)
        df["_chu_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    curr = df.iloc[i]
    c = float(curr["close"])
    o = float(curr["open"])
    h = float(curr["high"])
    l = float(curr["low"])
    ema200 = float(curr["_ema200"])
    sma20 = float(curr["_sma20"])
    rsi = float(curr["_rsi14"])
    atr = float(curr["_atr14"])

    # Vela elefante: rango de la vela > 1.8 veces el ATR
    vela_elefante = (h - l) >= (1.8 * atr)
    cuerpo_fuerte = (c - o) >= (0.65 * (h - l))

    if (c > ema200) and (c > sma20) and (rsi <= 70.0) and vela_elefante and cuerpo_fuerte and (c > o):
        sl_dist = 1.50 * atr
        tp_dist = 3.60 * atr  # R:R 1:2.40
        return True, "LONG", c - sl_dist, c + tp_dist

    return False, None, 0.0, 0.0


def arbitro_ia(fila, lado, entry, sl, tp) -> Tuple[bool, float, str]:
    dist_sl = abs(float(entry) - float(sl))
    dist_tp = abs(float(tp) - float(entry))
    rr = dist_tp / (dist_sl + 1e-9)

    if rr < 2.0:
        return False, 0.0, f"VETO Asimetría insuficiente ({rr:.2f} < 2.0)"

    return True, 1.0, "AUTORIZADO: Vela elefante institucional sobre medias macro"
