# -*- coding: utf-8 -*-
"""
ESTRATEGIA HEREDADA EN CONTENEDOR DE AUDITORÍA: Trailing Dinámico (Tendencia sin Techo)
Doctrina: Seguidor de microtendencia sobre EMA 200 y SMA 20 con RSI saludable (40-72) y acompañamiento libre de riesgo.
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_SOL_USDT_4h.parquet"
MAX_BARS_HOLD = 64

def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_ttr_init" not in df.columns:
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
        df["_ttr_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    c = float(row["close"])
    o = float(row["open"])
    ema200 = float(row["_ema200"])
    sma20 = float(row["_sma20"])
    rsi = float(row["_rsi14"])
    atr = float(row["_atr14"])

    # Tendencia alcista: Precio sobre EMA 200 y SMA 20, con RSI entre 40 y 72 (sin euforia extrema)
    if (c > ema200) and (c > sma20) and (40.0 <= rsi <= 72.0) and (c > o):
        sl_dist = 1.50 * atr
        tp_dist = 3.60 * atr  # R:R Teórico 1:2.40 con trailing de fondo
        return True, "LONG", c - sl_dist, c + tp_dist

    return False, None, 0.0, 0.0


def arbitro_ia(fila, lado, entry, sl, tp) -> Tuple[bool, float, str]:
    dist_sl = abs(float(entry) - float(sl))
    dist_tp = abs(float(tp) - float(entry))
    rr = dist_tp / (dist_sl + 1e-9)

    if rr < 2.0:
        return False, 0.0, f"VETO R:R insuficiente ({rr:.2f} < 2.0)"

    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > 3.0:
        return False, 0.0, f"VETO Sobreextensión tendencial ({dist_ema:.2f} ATR > 3.0)"

    return True, 1.0, "AUTORIZADO: Tendencia saludable alineada con medias macro"
