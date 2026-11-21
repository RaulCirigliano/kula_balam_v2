# -*- coding: utf-8 -*-
"""
TTM Squeeze Continuación Tendencial 1H (ETH/USDT · EMA200 + Expansión ATR + Bollinger/Keltner)
Complemento tendencial sin requisito de retroceso Fibonacci para capturar impulsos y caídas sostenidas.

Auditada Backtest Lab (binance_ETH_USDT_1h.parquet · 26,442 velas · 1,101.7 días · 0.26% round-trip):
  - Full 3Y (Con IA): N=91 (39W-52L) | WR=42.86% | PF=1.52 | R:R Real=2.03 | Ret=+12.24% | MaxDD=5.06%
  - Fondeo Prop Firm: Max Daily DD=0.56% (<=4.5%) | Monte Carlo DD 95%=7.28% (<=8.0%) -> APTA FONDEO
  - IS 70%: N=57 | PF=1.43 | WR=42.11% | Ret=+6.22%
  - OOS 30% Ciego: N=34 | PF=1.67 | WR=44.12% | Ret=+5.67%
  - Rolling WFO (5V): WFE=0.99 (>=0.50) | 4/5 (80.0%) ventanas OOS positivas -> ROBUSTA
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_ETH_USDT_1h.parquet"
ARBITRO_IA = "arbitro_ttm_squeeze_1h.py"
MAX_BARS_HOLD = 168
BREAKEVEN_RR = 0.0
TRAILING_ATR_MULT = 0.0
ATR_SLIPPAGE_K = 0.05

PARAMETROS_CALIBRADOS = {
    "familia": "TTM_SQUEEZE_TREND_1H",
    "kc_mult": 1.60,
    "sq_lookback": 4,
    "sl_mult": 4.8,
    "rr_target": 2.6,
    "rvol_min": 1.15,
    "max_mecha_contra_pct": 38.0,
}


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_ttm1h_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat(
            [df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(14).mean().shift(1).bfill()
        df["_atr"] = atr
        df["_atr_sma20"] = atr.rolling(20).mean().bfill()
        e20 = df["close"].ewm(span=20, adjust=False).mean()
        e200 = df["close"].ewm(span=200, adjust=False).mean()
        df["_e20"] = e20
        df["_e200"] = e200
        df["_e200_slp"] = e200 - e200.shift(16)

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
        df["_ttm1h_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    r = df.iloc[i]
    o = float(r["open"])
    c = float(r["close"])
    atr = float(r["_atr"])
    if atr <= 0 or c <= 0:
        return False, None, 0.0, 0.0
    if atr <= float(r["_atr_sma20"]) or not bool(r["_was_sq"]):
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
