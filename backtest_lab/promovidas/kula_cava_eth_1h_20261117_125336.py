# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: ETH/USDT | Dataset: binance_ETH_USDT_1h.parquet | Slot Asignado: 2
Fecha de Promoción: 2026-11-17T12:53:36.403364+00:00
"""

# -*- coding: utf-8 -*-
"""
Kula Balam Cava & Ruiz Estructural (ETH/USDT 1H · Zona Dorada 0.50-0.75 · Meseta S46)
Auditada Backtest Lab (1,101 días):
  - N=30 | WR=46.67% | PF=1.76 | Ret=+7.91% | MaxDD=3.88% | MC DD 95%=6.32%
  - OOS (30% ciego): N=10 | PF=2.55 | Ret=+4.11% | MC DD 95%=3.16%
  - Rolling WFO (5V): WFE=0.82 | 3/5 ventanas positivas (60.0%) | Apta Fondeo=True
"""
from typing import Tuple, Optional
import pandas as pd
import numpy as np

DATASET = "binance_ETH_USDT_1h.parquet"
ARBITRO_IA = "arbitro_kula_cava_eth_1h.py"
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
    if "_kc_eth1h_init" not in df.columns:
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
        df["_h_sw"] = df["high"].rolling(46).max()
        df["_l_sw"] = df["low"].rolling(46).min()
        df["_kc_eth1h_init"] = True

    if i < 205:
        return False, None, 0.0, 0.0

    r = df.iloc[i]
    c = float(r["close"])
    o = float(r["open"])
    h = float(r["high"])
    l = float(r["low"])
    atr = float(r["_atr"])
    if atr <= 0 or c <= 0:
        return False, None, 0.0, 0.0
    if atr <= float(r["_atr_sma20"]):
        return False, None, 0.0, 0.0

    ema50 = float(r["_ema50"])
    ema50_prev = float(df["_ema50"].iloc[i - 4])
    sw_h = float(r["_h_sw"])
    sw_l = float(r["_l_sw"])
    rng_fibo = max(sw_h - sw_l, 1e-9)

    w_df = df.iloc[max(0, i - 45) : i + 1]
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

    h_curr = float(r["_hist"])
    h_prev = float(df["_hist"].iloc[i - 1])
    h_prev2 = float(df["_hist"].iloc[i - 2])
    m_curr = float(r["_macd"])
    m_prev = float(df["_macd"].iloc[i - 1])
    rng = max(h - l, 1e-9)

    if target_side == "LONG":
        fallo_macd = (h_curr > h_prev) or (h_curr > h_prev2) or (m_curr > m_prev)
        ema_ok = c >= (ema50 * 0.999)
        v3_ok = c > o
        veto_mecha = ((h - max(o, c)) / rng >= 0.50) or (((min(o, c) - l) / rng) < 0.15 and c < ema50)
    else:
        fallo_macd = (h_curr < h_prev) or (h_curr < h_prev2) or (m_curr < m_prev)
        ema_ok = c <= (ema50 * 1.001)
        v3_ok = c < o
        veto_mecha = (((min(o, c) - l) / rng) >= 0.50) or (((h - max(o, c)) / rng) < 0.15 and c > ema50)

    if not (fallo_macd and ema_ok and v3_ok and not veto_mecha):
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


# --- ÁRBITRO HEURÍSTICO IA ---
# -*- coding: utf-8 -*-
"""
Árbitro Cuantitativo para Kula Balam Cava & Ruiz (ETH/USDT 1H)
Calibrado en meseta S46 (S45..S50): Asimetría R:R >= 1:2.0 y Sizing Fraccional 0.60%
para blindar Monte Carlo DD 95% <= 6.32%.
"""
from typing import Tuple

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "target_risk_pct": 0.60,
    "max_sizing": 0.42,
    "min_sizing": 0.10,
}


def arbitro_ia(fila, lado: str, entry: float, sl: float, tp: float) -> Tuple[bool, float, str]:
    p_ref = float(fila.get("close", entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    target_risk = float(CONFIG_IA["target_risk_pct"])
    sz = round(
        min(
            float(CONFIG_IA["max_sizing"]),
            max(float(CONFIG_IA["min_sizing"]), target_risk / max(sl_dist_pct, 0.20)),
        ),
        4,
    )
    return True, sz, f"AUTORIZADO Cava ETH 1H (Sizing {sz:.2f}x · Riesgo {target_risk:.2f}%)"
