# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: ETH/USDT | Dataset: binance_ETH_USDT_15m.parquet | Slot Asignado: 2
Fecha de Promoción: 2026-11-21T12:24:39.789022+00:00
"""

# -*- coding: utf-8 -*-
"""
Fractal Squeeze Presencial 15M (1H -> 15M · Londres/NY excluyendo Lunch Lull · ETH/USDT)
Continuación direccional sin filtro Fibonacci: tendencia causal 1H (EMA50/EMA200 + pendiente EMA50)
combinada con ruptura de compresión Bollinger/Keltner en 15M y piso de SL >= 1.2% para absorber
la fricción taker cripto (0.26% round-trip) preservando R:R neto >= 1:2.0.

Auditada Backtest Lab (binance_ETH_USDT_15m.parquet · 35,040 velas · 365.0 días · 0.26% round-trip):
  - Full 1Y (Con IA): N=53 (22W-31L) | WR=41.51% | PF=1.45 | R:R Real=2.04 | Ret=+5.95% | MaxDD=3.96%
  - Fondeo Prop Firm: Monte Carlo DD 95%=6.36% (<=8.0%) -> APTO FONDEO
  - IS 70%: N=36 | PF=1.06 | WR=36.11% | Ret=+0.50%
  - OOS 30% Ciego: N=17 | PF=2.89 | WR=52.94% | Ret=+5.42%
  - Rolling WFO (5V): WFE=2.06 (>=0.50) | 2/5 (40.0%) ventanas OOS positivas (Ventana #4: -0.04%, PF 0.98)
  - Clasificación: Operador Presente (Supervisión Humana Obligatoria; no habilitada en daemon autónomo).
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_ETH_USDT_15m.parquet"
ARBITRO_IA = "arbitro_fractal_squeeze_15m.py"
MAX_BARS_HOLD = 192
BREAKEVEN_RR = 0.0
TRAILING_ATR_MULT = 0.0
ATR_SLIPPAGE_K = 0.05

PARAMETROS_CALIBRADOS = {
    "familia": "FRACTAL_SQUEEZE_1H_15M",
    "kc_mult": 1.60,
    "sq_lookback": 4,
    "sl_mult": 4.2,
    "min_sl_pct": 0.012,
    "rr_target": 2.8,
}


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_fs15_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat(
            [df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(14).mean().shift(1).bfill()
        df["_atr"] = atr
        df["_atr_sma20"] = atr.rolling(20).mean().bfill()

        e20 = df["close"].ewm(span=20, adjust=False).mean()
        sma20 = df["close"].shift(1).rolling(20).mean().bfill()
        std20 = df["close"].shift(1).rolling(20).std().bfill()
        bbu, bbd = sma20 + 2.0 * std20, sma20 - 2.0 * std20
        kc_m = float(PARAMETROS_CALIBRADOS["kc_mult"])
        kcu, kcd = e20 + kc_m * atr, e20 - kc_m * atr
        df["_kcu"], df["_kcd"] = kcu, kcd
        in_sq = (bbu < kcu) & (bbd > kcd)
        sq_lb = int(PARAMETROS_CALIBRADOS["sq_lookback"])
        df["_was_sq"] = in_sq.shift(1).rolling(sq_lb).max().fillna(0).astype(bool)

        if isinstance(df.index, pd.DatetimeIndex):
            df_1h = df.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            e50_1h = df_1h["close"].ewm(span=50, adjust=False).mean()
            e200_1h = df_1h["close"].ewm(span=200, adjust=False).mean()
            b1h = pd.Series(0, index=df_1h.index)
            b1h[(df_1h["close"] > e50_1h) & (e50_1h > e200_1h) & (e50_1h > e50_1h.shift(4))] = 1
            b1h[(df_1h["close"] < e50_1h) & (e50_1h < e200_1h) & (e50_1h < e50_1h.shift(4))] = -1
            df["_b1h"] = b1h.shift(1).reindex(df.index, method="ffill").fillna(0).astype(int)

            idx_utc = df.index.tz_convert("UTC") if df.index.tz is not None else df.index
            mins = idx_utc.hour * 60 + idx_utc.minute
            # Sesión Londres + NY (07:00-21:00 UTC) excluyendo Lunch Lull NY (17:00-18:30 UTC)
            df["_sess_ok"] = ((mins >= 420) & (mins < 1020)) | ((mins >= 1110) & (mins < 1260))
        else:
            df["_b1h"] = 0
            df["_sess_ok"] = True
        df["_fs15_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    r = df.iloc[i]
    if not bool(r["_sess_ok"]):
        return False, None, 0.0, 0.0

    c, o, atr = float(r["close"]), float(r["open"]), float(r["_atr"])
    if atr <= 0 or c <= 0 or atr <= float(r["_atr_sma20"]) or not bool(r["_was_sq"]):
        return False, None, 0.0, 0.0

    b1h = int(r["_b1h"])
    if b1h == 0:
        return False, None, 0.0, 0.0

    dsl = max(float(PARAMETROS_CALIBRADOS["sl_mult"]) * atr, float(PARAMETROS_CALIBRADOS["min_sl_pct"]) * c)
    rr = float(PARAMETROS_CALIBRADOS["rr_target"])

    if b1h == 1 and c > float(r["_kcu"]) and c > o:
        return True, "LONG", c - dsl, c + (rr * dsl)
    if b1h == -1 and c < float(r["_kcd"]) and c < o:
        return True, "SHORT", c + dsl, c - (rr * dsl)
    return False, None, 0.0, 0.0


# --- ÁRBITRO HEURÍSTICO IA ---
# -*- coding: utf-8 -*-
"""
Árbitro Cuantitativo para Fractal Squeeze 15M Presencial (1H -> 15M · Londres/NY)
Principio de Veto Negativo sobre fila preprocesada ('fila'):
  - Exige asimetría matemática R:R >= 1:2.0.
  - Rechaza mechas trampa contrarias > 40%.
  - Preserva el volumen natural de salidas de compresión en 15m (sin veto RVOL destructivo).
  - Sizing fraccional 0.45% para mantener Monte Carlo DD 95% <= 6.36% (<= 8.0%).
"""
import math
from typing import Tuple

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "max_mecha_contra_pct": 40.0,
    "target_risk_pct": 0.45,
    "min_sizing": 0.08,
    "max_sizing": 0.30,
}


def _safe_float(val, default: float) -> float:
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return default


def arbitro_ia(fila, lado: str, entry: float, sl: float, tp: float) -> Tuple[bool, float, str]:
    p_ref = _safe_float(fila.get("close", entry), float(entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    m_col = "mecha_superior_pct" if lado == "LONG" else "mecha_inferior_pct"
    mecha = _safe_float(fila.get(m_col, 0.0), 0.0)
    lim_m = float(CONFIG_IA["max_mecha_contra_pct"])
    if mecha > lim_m:
        return False, 0.0, f"VETO IA Mecha Trampa ({mecha:.1f}% > {lim_m:.1f}%)"

    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    sz = round(
        min(
            float(CONFIG_IA["max_sizing"]),
            max(float(CONFIG_IA["min_sizing"]), float(CONFIG_IA["target_risk_pct"]) / max(sl_dist_pct, 0.20)),
        ),
        4,
    )
    return True, sz, f"AUTORIZADO Fractal Squeeze 15M (Sizing={sz:.2f}x)"
