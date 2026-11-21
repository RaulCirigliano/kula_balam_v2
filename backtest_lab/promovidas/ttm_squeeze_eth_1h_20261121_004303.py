# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: ETH/USDT | Dataset: binance_ETH_USDT_1h.parquet | Slot Asignado: 2
Fecha de Promoción: 2026-11-21T00:43:03.726604+00:00
"""

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


# --- ÁRBITRO HEURÍSTICO IA ---
# -*- coding: utf-8 -*-
"""
Árbitro Cuantitativo para TTM Squeeze Continuación Tendencial 1H (ETH/USDT)
Cumplimiento AGENTS.md Regla 3 & 7:
  1. Opera exclusivamente sobre fila preprocesada ('fila') con principio de Veto Negativo.
  2. Exige R:R >= 1:2.0, participación RVOL >= 1.15x, rechazo de mechas trampa > 38%
     y Sizing Fraccional 0.45% para blindar Monte Carlo DD 95% (7.28% <= 8.0%).
"""
import math
from typing import Tuple

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_minimo": 1.15,
    "max_mecha_contra_pct": 38.0,
    "target_risk_pct": 0.45,
    "min_sizing": 0.08,
    "max_sizing": 0.28,
}


def _safe_float(val, default: float) -> float:
    try:
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except Exception:
        return default


def arbitro_ia(fila, lado: str, entry: float, sl: float, tp: float) -> Tuple[bool, float, str]:
    p_ref = _safe_float(fila.get("close", entry), float(entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    rvol = _safe_float(fila.get("rvol", 1.0), 1.0)
    if rvol < CONFIG_IA["rvol_minimo"]:
        return False, 0.0, f"VETO IA Volumen Seco ({rvol:.2f}x < {CONFIG_IA['rvol_minimo']:.2f}x)"

    lim_m = float(CONFIG_IA["max_mecha_contra_pct"])
    m_sup = _safe_float(fila.get("mecha_superior_pct", 0.0), 0.0)
    m_inf = _safe_float(fila.get("mecha_inferior_pct", 0.0), 0.0)
    if lado == "LONG" and m_sup > lim_m:
        return False, 0.0, f"VETO IA Mecha Trampa Superior ({m_sup:.1f}% > {lim_m:.1f}%)"
    if lado == "SHORT" and m_inf > lim_m:
        return False, 0.0, f"VETO IA Mecha Trampa Inferior ({m_inf:.1f}% > {lim_m:.1f}%)"

    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    sz = round(
        min(
            float(CONFIG_IA["max_sizing"]),
            max(float(CONFIG_IA["min_sizing"]), float(CONFIG_IA["target_risk_pct"]) / max(sl_dist_pct, 0.20)),
        ),
        4,
    )
    return True, sz, f"AUTORIZADO TTM Squeeze 1H (RVOL={rvol:.2f}x | Sizing={sz:.2f}x)"
