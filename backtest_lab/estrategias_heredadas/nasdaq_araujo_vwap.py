# -*- coding: utf-8 -*-
"""
ESTRATEGIA HEREDADA EN CONTENEDOR DE AUDITORÍA: Nasdaq Araujo VWAP
Doctrina: Francotirador de apertura en Wall Street con VWAP diario, absorción por mechas (>= 25%) y RVOL >= 1.15.
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "yf_QQQ_1d.parquet"
MAX_BARS_HOLD = 20

def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_araujo_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
        df["_atr14"] = tr.rolling(14).mean().shift(1).bfill()
        
        typ_p = (df["high"] + df["low"] + df["close"]) / 3.0
        vol = df["volume"].replace(0, 1.0) if "volume" in df.columns else pd.Series(1.0, index=df.index)
        cum_pv = (typ_p * vol).rolling(20, min_periods=5).sum()
        cum_v = vol.rolling(20, min_periods=5).sum()
        df["_vwap"] = (cum_pv / (cum_v + 1e-9)).shift(1).bfill()
        vol_sma = vol.rolling(20).mean().shift(1).bfill()
        df["_rvol"] = (vol / (vol_sma + 1e-9)).shift(1)
        df["_araujo_init"] = True

    if i < 25:
        return False, None, 0.0, 0.0

    curr = df.iloc[i]
    c = float(curr["close"])
    o = float(curr["open"])
    h = float(curr["high"])
    l = float(curr["low"])
    vwap = float(curr["_vwap"])
    atr = float(curr["_atr14"])
    rvol = float(curr["_rvol"])

    rng = max(h - l, 1e-9)
    mecha_inf = ((min(o, c) - l) / rng) * 100.0
    mecha_sup = ((h - max(o, c)) / rng) * 100.0

    # LONG: Rechazo en VWAP con mecha inferior y RVOL institucional
    if (c > vwap) and (l <= vwap * 1.002) and (mecha_inf >= 25.0) and (rvol >= 1.15):
        sl_dist = max(c - vwap + (0.3 * atr), 1.2 * atr)
        tp_dist = 2.4 * sl_dist  # R:R 1:2.40
        return True, "LONG", c - sl_dist, c + tp_dist

    # SHORT: Rechazo bajo VWAP con mecha superior y RVOL
    if (c < vwap) and (h >= vwap * 0.998) and (mecha_sup >= 25.0) and (rvol >= 1.15):
        sl_dist = max(vwap - c + (0.3 * atr), 1.2 * atr)
        tp_dist = 2.4 * sl_dist
        return True, "SHORT", c + sl_dist, c - tp_dist

    return False, None, 0.0, 0.0


def arbitro_ia(fila, lado, entry, sl, tp) -> Tuple[bool, float, str]:
    dist_sl = abs(float(entry) - float(sl))
    dist_tp = abs(float(tp) - float(entry))
    rr = dist_tp / (dist_sl + 1e-9)

    if rr < 2.0:
        return False, 0.0, f"VETO Asimetría insuficiente ({rr:.2f} < 2.0)"

    return True, 1.0, "AUTORIZADO: Rechazo en VWAP validado institucionalmente"
