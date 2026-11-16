# -*- coding: utf-8 -*-
"""
ESTRATEGIA HEREDADA EN CONTENEDOR DE AUDITORÍA: Tres Velas & Wyckoff VPA
Doctrina: Acción del precio cuantitativa de Thomas Bulkowski (Three White Soldiers, Bullish Engulfing) + RVOL y VWAP.
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_ETH_USDT_4h.parquet"
MAX_BARS_HOLD = 36

def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_wyck_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
        df["_atr14"] = tr.rolling(14).mean().shift(1).bfill()
        df["_ema50"] = df["close"].ewm(span=50, adjust=False).mean().shift(1)
        vol = df["volume"] if "volume" in df.columns else pd.Series(1.0, index=df.index)
        vol_sma = vol.rolling(20).mean().shift(1).bfill()
        df["_rvol"] = (vol / (vol_sma + 1e-9)).shift(1)
        df["_wyck_init"] = True

    if i < 30:
        return False, None, 0.0, 0.0

    curr = df.iloc[i]
    prev1 = df.iloc[i - 1]
    prev2 = df.iloc[i - 2]

    c = float(curr["close"])
    o = float(curr["open"])
    c1 = float(prev1["close"])
    o1 = float(prev1["open"])
    c2 = float(prev2["close"])
    o2 = float(prev2["open"])
    ema50 = float(curr["_ema50"])
    atr = float(curr["_atr14"])
    rvol = float(curr["_rvol"])

    if c <= ema50:
        return False, None, 0.0, 0.0

    # Patrón 1: Bullish Engulfing con volumen
    engulfing = (c1 < o1) and (c > o) and (c >= o1) and (o <= c1)
    # Patrón 2: Three White Soldiers (3 velas alcistas consecutivas con máximos crecientes)
    soldiers = (c > o) and (c1 > o1) and (c2 > o2) and (c > c1 > c2)

    if (engulfing or soldiers) and (rvol >= 1.15):
        sl_dist = 1.50 * atr
        tp_dist = 3.30 * atr  # Asimetría R:R 1:2.20
        return True, "LONG", c - sl_dist, c + tp_dist

    return False, None, 0.0, 0.0


def arbitro_ia(fila, lado, entry, sl, tp) -> Tuple[bool, float, str]:
    dist_sl = abs(float(entry) - float(sl))
    dist_tp = abs(float(tp) - float(entry))
    rr = dist_tp / (dist_sl + 1e-9)

    if rr < 2.0:
        return False, 0.0, f"VETO R:R insuficiente ({rr:.2f} < 2.0)"

    rvol = float(fila.get("rvol", 1.0))
    if rvol < 1.10:
        return False, 0.0, f"VETO Falta volumen institucional (RVOL {rvol:.2f} < 1.10)"

    return True, 1.0, "AUTORIZADO: Patrón Wyckoff confirmado con RVOL"
