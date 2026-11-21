# -*- coding: utf-8 -*-
"""
TTM Squeeze Direccional 4H (SOL/USDT · Compresión Bollinger/Keltner + Tendencia EMA200)
Complemento estructural en 4H orientado a continuaciones direccionales y caídas sostenidas sin filtro Fibonacci.

Auditada Backtest Lab (binance_SOL_USDT_4h.parquet · 6,610 velas · 1,101.5 días · 0.26% round-trip):
  - Full 3Y (Con IA): N=43 (20W-23L) | WR=46.51% | PF=1.89 | R:R Real=2.17 | Ret=+14.97% | MaxDD=2.90%
  - Fondeo Prop Firm: Max Daily DD=1.10% (<=4.5%) | Monte Carlo DD 95%=7.61% (<=8.0%) -> APTA FONDEO
  - IS 70%: N=33 | PF=1.85 | WR=45.45% | Ret=+11.65%
  - OOS 30% Ciego: N=10 | PF=2.10 | WR=50.00% | Ret=+2.98%
  - Rolling WFO (5V): WFE=0.83 (>=0.50) | 5/5 (100.0%) ventanas OOS positivas -> ROBUSTA
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_SOL_USDT_4h.parquet"
ARBITRO_IA = "arbitro_ttm_squeeze_4h.py"
MAX_BARS_HOLD = 84
BREAKEVEN_RR = 0.0
TRAILING_ATR_MULT = 0.0
ATR_SLIPPAGE_K = 0.05

PARAMETROS_CALIBRADOS = {
    "familia": "TTM_SQUEEZE_4H",
    "kc_mult": 1.80,
    "sq_lookback": 3,
    "sl_mult": 2.5,
    "rr_target": 2.5,
    "rvol_min": 0.80,
    "max_mecha_contra_pct": 40.0,
    "max_dist_ema50_atrs": 4.2,
}


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_ttm4h_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat(
            [df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(14).mean().shift(1).bfill()
        df["_atr"] = atr
        e20 = df["close"].ewm(span=20, adjust=False).mean()
        e200 = df["close"].ewm(span=200, adjust=False).mean()
        df["_e20"] = e20
        df["_e200"] = e200
        df["_e200_slp"] = e200 - e200.shift(8)

        sma20 = df["close"].shift(1).rolling(20).mean().bfill()
        std20 = df["close"].shift(1).rolling(20).std().bfill()
        bbu = sma20 + 2.0 * std20
        bbd = sma20 - 2.0 * std20
        kc_m = float(PARAMETROS_CALIBRADOS["kc_mult"])
        kcu = e20 + kc_m * atr
        kcd = e20 - kc_m * atr
        df["_kcu"] = kcu
        df["_kcd"] = kcd
        in_sq = (bbu < kcu) & (bbd > kcd)
        sq_lb = int(PARAMETROS_CALIBRADOS["sq_lookback"])
        df["_was_sq"] = in_sq.shift(1).rolling(sq_lb).max().fillna(0).astype(bool)
        df["_ttm4h_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    r = df.iloc[i]
    o = float(r["open"])
    c = float(r["close"])
    atr = float(r["_atr"])
    if atr <= 0 or c <= 0 or not bool(r["_was_sq"]):
        return False, None, 0.0, 0.0

    e200 = float(r["_e200"])
    e200_slp = float(r["_e200_slp"]) if pd.notna(r["_e200_slp"]) else 0.0
    sl_m = float(PARAMETROS_CALIBRADOS["sl_mult"])
    rr = float(PARAMETROS_CALIBRADOS["rr_target"])
    dsl = max(sl_m * atr, 0.007 * c)

    if (c > float(r["_kcu"])) and (c > e200) and (e200_slp > 0.0) and (c > o):
        return True, "LONG", c - dsl, c + (rr * dsl)
    if (c < float(r["_kcd"])) and (c < e200) and (e200_slp < 0.0) and (c < o):
        return True, "SHORT", c + dsl, c - (rr * dsl)
    return False, None, 0.0, 0.0
