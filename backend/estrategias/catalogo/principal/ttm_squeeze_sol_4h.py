# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: SOL/USDT | Dataset: binance_SOL_USDT_4h.parquet | Slot Asignado: 1
Fecha de Promoción: 2026-11-21T00:43:03.876189+00:00
"""

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


# --- ÁRBITRO HEURÍSTICO IA ---
# -*- coding: utf-8 -*-
"""
Árbitro Cuantitativo para TTM Squeeze Direccional 4H (SOL/USDT)
Cumplimiento AGENTS.md Regla 3 & 7:
  1. Opera exclusivamente sobre fila preprocesada ('fila') con principio de Veto Negativo.
  2. Exige R:R >= 1:2.0, participación RVOL >= 0.80x, mechas <= 40%, distancia a EMA50 <= 4.2 ATRs
     y Sizing Fraccional 0.60% para blindar Monte Carlo DD 95% (7.61% <= 8.0%).
"""
import math
from typing import Tuple

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_minimo": 0.80,
    "max_mecha_contra_pct": 40.0,
    "max_dist_ema50_atrs": 4.2,
    "target_risk_pct": 0.60,
    "min_sizing": 0.12,
    "max_sizing": 0.30,
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

    dist_ema = _safe_float(fila.get("dist_ema_atrs", 0.0), 0.0)
    if dist_ema > float(CONFIG_IA["max_dist_ema50_atrs"]):
        return False, 0.0, f"VETO IA Sobreextensión EMA50 ({dist_ema:.2f} ATR > {CONFIG_IA['max_dist_ema50_atrs']:.1f})"

    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    sz = round(
        min(
            float(CONFIG_IA["max_sizing"]),
            max(float(CONFIG_IA["min_sizing"]), float(CONFIG_IA["target_risk_pct"]) / max(sl_dist_pct, 0.20)),
        ),
        4,
    )
    return True, sz, f"AUTORIZADO TTM Squeeze 4H (RVOL={rvol:.2f}x | Sizing={sz:.2f}x)"
