# -*- coding: utf-8 -*-
"""
Kula Balam Cava & Ruiz Estructural (SOL/USDT 1H · Zona Dorada 0.50-0.75)
Auditada Backtest Lab (1,101 días):
  - N=31 | WR=51.61% | PF=2.66 | Ret=+19.39% | MaxDD=2.15% | Sortino=6.40 | MC DD 95%=5.51%
  - OOS (30% ciego): N=10 | PF=3.11 | WR=50.0% | Ret=+7.50% | MC DD 95%=3.99%
  - Rolling WFO (5V): WFE=1.32 | 5/5 ventanas positivas (100.0%) | Apta Fondeo=True
"""
from typing import Tuple, Optional
import pandas as pd
import numpy as np

DATASET = "binance_SOL_USDT_1h.parquet"
ARBITRO_IA = "arbitro_kula_cava_sol_1h.py"
MAX_BARS_HOLD = 48
BREAKEVEN_RR = 0.0
TRAILING_ATR_MULT = 0.0
ATR_SLIPPAGE_K = 0.05


def _net_ret(gross_pct: float, fee: float, spread: float) -> float:
    e = (1.0 + fee / 100.0) * (1.0 + spread / 100.0)
    x = (1.0 - fee / 100.0) * (1.0 - spread / 100.0)
    return ((1.0 + gross_pct / 100.0) * x / e - 1.0) * 100.0


def _net_rr(tp_gross_pct: float, sl_gross_pct: float, fee: float = 0.10, spread: float = 0.05) -> float:
    tp_n = _net_ret(tp_gross_pct, fee, spread)
    sl_n = _net_ret(-abs(sl_gross_pct), fee, spread)
    if sl_n >= 0 or tp_n <= 0:
        return 0.0
    return tp_n / abs(sl_n)


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_kc_sol1h_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - prev_c).abs(),
            (df["low"] - prev_c).abs(),
        ], axis=1).max(axis=1)
        df["_atr"] = tr.rolling(14).mean().shift(1).bfill()
        df["_atr_sma20"] = df["_atr"].rolling(20).mean().bfill()
        df["_ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        e12 = df["close"].ewm(span=12, adjust=False).mean()
        e26 = df["close"].ewm(span=26, adjust=False).mean()
        df["_macd"] = e12 - e26
        df["_sig"] = df["_macd"].ewm(span=9, adjust=False).mean()
        df["_hist"] = df["_macd"] - df["_sig"]
        df["_h60"] = df["high"].rolling(60).max()
        df["_l60"] = df["low"].rolling(60).min()
        df["_kc_sol1h_init"] = True

    if i < 205:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    c = float(row["close"])
    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    atr = float(row["_atr"])
    if atr <= 0 or c <= 0:
        return False, None, 0.0, 0.0

    ema50 = float(row["_ema50"])
    ema50_prev = float(df["_ema50"].iloc[i - 4])
    sw_h = float(row["_h60"])
    sw_l = float(row["_l60"])
    rng_fibo = max(sw_h - sw_l, 1e-9)

    w_df = df.iloc[i - 59 : i + 1]
    high_pos = int(np.argmax(w_df["high"].values))
    low_pos = int(np.argmin(w_df["low"].values))
    swing_bias_long = (high_pos >= low_pos)
    is_ema_falling = (ema50 < ema50_prev * 0.995)

    if is_ema_falling and not swing_bias_long and c < (ema50 * 0.998):
        target_side = "SHORT"
    elif swing_bias_long:
        target_side = "LONG"
    else:
        target_side = "SHORT" if c < ema50 else "LONG"

    retr = ((sw_h - c) / rng_fibo) if target_side == "LONG" else ((c - sw_l) / rng_fibo)
    if not (0.50 <= retr <= 0.75):
        return False, None, 0.0, 0.0

    h_curr = float(row["_hist"])
    h_prev = float(df["_hist"].iloc[i - 1])
    h_prev2 = float(df["_hist"].iloc[i - 2])
    m_curr = float(row["_macd"])
    m_prev = float(df["_macd"].iloc[i - 1])
    v2 = df.iloc[i - 1]
    rng = max(h - l, 1e-9)

    if target_side == "LONG":
        fallo_macd = (h_curr > h_prev) or (h_curr > h_prev2) or (m_curr > m_prev)
        ema_ok = c >= (ema50 * 0.999)
        v3_ok = c > float(v2["high"])
        upper_wick_pct = (h - max(o, c)) / rng
        lower_wick_pct = (min(o, c) - l) / rng
        veto_mecha = (upper_wick_pct >= 0.50) or (lower_wick_pct < 0.15 and c < ema50)
    else:
        fallo_macd = (h_curr < h_prev) or (h_curr < h_prev2) or (m_curr < m_prev)
        ema_ok = c <= (ema50 * 1.001)
        v3_ok = c < float(v2["low"])
        lower_wick_pct = (min(o, c) - l) / rng
        upper_wick_pct = (h - max(o, c)) / rng
        veto_mecha = (lower_wick_pct >= 0.50) or (upper_wick_pct < 0.15 and c > ema50)

    if not (fallo_macd and ema_ok and v3_ok and not veto_mecha):
        return False, None, 0.0, 0.0

    if atr <= float(row["_atr_sma20"]):
        return False, None, 0.0, 0.0

    if target_side == "LONG":
        loc_low = float(df.iloc[max(0, i - 6) : i + 1]["low"].min())
        sl_dist = min(3.0 * atr, max(c - loc_low + 0.2 * atr, 1.0 * atr, 0.007 * c))
        sl_px = c - sl_dist
        tp_px = sw_h
    else:
        loc_high = float(df.iloc[max(0, i - 6) : i + 1]["high"].max())
        sl_dist = min(3.0 * atr, max(loc_high - c + 0.2 * atr, 1.0 * atr, 0.007 * c))
        sl_px = c + sl_dist
        tp_px = sw_l

    sl_pct = abs(c - sl_px) / c * 100.0
    tp_pct = (tp_px - c) / c * 100.0 if target_side == "LONG" else (c - tp_px) / c * 100.0
    if tp_pct <= 0 or sl_pct <= 0 or _net_rr(tp_pct, sl_pct, 0.10, 0.05) < 2.0:
        return False, None, 0.0, 0.0

    return True, target_side, sl_px, tp_px
