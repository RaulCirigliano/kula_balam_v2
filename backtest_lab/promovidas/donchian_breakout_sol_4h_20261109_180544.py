# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: SOL/USDT | Dataset: binance_SOL_USDT_4h.parquet | Slot Asignado: 1
Fecha de Promoción: 2026-11-09T18:05:44.661047+00:00
"""

# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/estrategias_math/donchian_breakout_1h.py
Proyecto: Kula Balam / Backtest Lab (Rol BALAM - Músculo Matemático Determinista)
Espejo Exacto de Producción: backend/estrategias/donchian_breakout_1h.py
Adaptación Automática Multi-Marco (Cero Lookahead - Walk-Forward 70% IS / 30% OOS):
  • Marco Intradía/Swing (< 1D, ej. SOL/USDT 4H, ETH/USDT 4H):
      - Canal Donchian 30 causal (shift 1), Bidireccional (LONG / SHORT).
      - Régimen EMA 200 + Pendiente estructural de 8 velas.
      - Compresión Dual: Ancho/ATR <= 6.0x y <= 1.15x mediana rodante causal de 60 velas.
      - Vela no climática (Rango <= 2.6x ATR) | SL = 1.60x ATR | TP = 4.16x ATR (R:R Bruto 1:2.60).
  • Marco Diario (1D, ej. AAPL, AMD, AVGO, META, MSFT, BTC/USDT 1D):
      - Canal Donchian 20 causal (shift 1), Solo Largo (LONG).
      - Régimen EMA 100 + Pendiente estructural de 5 velas.
      - Compresión Dual: Ancho/ATR <= 4.4x y <= 1.35x mediana rodante causal de 60 velas.
      - Vela no climática (Rango <= 3.2x ATR) | SL = 1.10x ATR | TP = 2.42x ATR (R:R Bruto 1:2.20).
"""

from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_SOL_USDT_4h.parquet"
ARBITRO_IA = "arbitro_donchian_breakout_1h.py"
MAX_BARS_HOLD = 84

VELA_TESTIGO = {
    "fecha_historica": "2026-09-18 04:00:00",
    "close_offset_pct": 1.80,
    "rvol": 1.85,
    "mecha_sup_pct": 8.0,
    "mecha_inf_pct": 8.0,
    "cuerpo_pct": 75.0,
}


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    """
    Motor determinista Balam para DonchianBreakout1H (4H Cripto / 1D Acciones & Swing).
    """
    if "_dc_auditada_init" not in df.columns:
        es_1d = False
        if isinstance(df.index, pd.DatetimeIndex) and len(df.index) >= 3:
            dt_sec = float((df.index[-1] - df.index[-2]).total_seconds())
            es_1d = dt_sec >= 80000.0

        dc_p = 20 if es_1d else 30
        ema_p = 100 if es_1d else 200
        slp_b = 5 if es_1d else 8

        prev_c = df["close"].shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev_c).abs(),
                (df["low"] - prev_c).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["_dc_atr14"] = tr.rolling(14).mean().shift(1).bfill()
        df["_dc_ema"] = df["close"].ewm(span=ema_p, adjust=False).mean()
        df["_dc_slp"] = df["_dc_ema"] - df["_dc_ema"].shift(slp_b)

        df["_dc_hi"] = df["high"].shift(1).rolling(dc_p).max().bfill()
        df["_dc_lo"] = df["low"].shift(1).rolling(dc_p).min().bfill()
        bw = (df["_dc_hi"] - df["_dc_lo"]) / (df["_dc_atr14"] + 1e-9)
        df["_dc_bw"] = bw
        df["_dc_bw_med"] = bw.shift(1).rolling(60, min_periods=20).median().bfill()
        df["_es_1d"] = es_1d
        df["_dc_auditada_init"] = True

    es_1d_row = bool(df["_es_1d"].iloc[i])
    warmup = 110 if es_1d_row else 210
    if i < warmup:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    c = float(row["close"])
    atr = float(row["_dc_atr14"])
    if atr <= 0:
        return False, None, 0.0, 0.0

    max_bar_atr = 3.2 if es_1d_row else 2.6
    if (h - l) > (max_bar_atr * atr):
        return False, None, 0.0, 0.0

    cap_atr = 4.4 if es_1d_row else 6.0
    rel_sq = 1.35 if es_1d_row else 1.15
    bw_val = float(row["_dc_bw"])
    if (bw_val > cap_atr) or (bw_val > float(row["_dc_bw_med"]) * rel_sq):
        return False, None, 0.0, 0.0

    ema_v = float(row["_dc_ema"])
    slp_v = float(row["_dc_slp"]) if pd.notna(row["_dc_slp"]) else 0.0
    dh = float(row["_dc_hi"])
    dl = float(row["_dc_lo"])

    sl_mult = 1.10 if es_1d_row else 1.60
    tp_mult = 2.42 if es_1d_row else 4.16
    dist_sl = sl_mult * atr
    dist_tp = tp_mult * atr

    if (c > dh) and (c > ema_v) and (slp_v > 0.0) and (c >= o):
        return True, "LONG", c - dist_sl, c + dist_tp

    if (not es_1d_row) and (c < dl) and (c < ema_v) and (slp_v < 0.0) and (c <= o):
        return True, "SHORT", c + dist_sl, c - dist_tp

    return False, None, 0.0, 0.0

# =====================================================================
# ÁRBITRO DE IA HEURÍSTICO (ANTIGRAVITY CIO)
# =====================================================================
# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/estrategias_ia/arbitro_donchian_breakout_1h.py
Proyecto: Kula Balam / Backtest Lab (Rol ANTIGRAVITY CIO - Árbitro Heurístico de Veto)
Espejo de Subfórmulas de Calidad de DonchianBreakout1H (Cumplimiento AGENTS.md Regla 7):
  1. Cero cálculo de indicadores ni medias: lee únicamente 'fila' preprocesada por Balam/Lab.
  2. Principio de Veto Negativo puro:
     - Exige asimetría teórica >= 1:2.0.
     - Exige expansión de volumen causal RVOL >= 1.15x (<1D) / >= 1.25x (1D).
     - Veta mechas de absorción en contra > 32% (<1D) / > 38% (1D).
     - Veta sobreextensión respecto al equilibrio dinámico EMA 50 > 3.2 ATR (<1D) / > 4.2 ATR (1D).
"""

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_4h": 1.15,
    "rvol_1d": 1.25,
    "max_mecha_4h": 32.0,
    "max_mecha_1d": 38.0,
    "max_dist_ema50_4h": 3.2,
    "max_dist_ema50_1d": 4.2,
}

# --- ÁRBITRO HEURÍSTICO IA ---
# -*- coding: utf-8 -*-
CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_4h": 1.15,
    "rvol_1d": 1.25,
    "rvol_minimo": 1.15,
    "max_mecha_4h": 32.0,
    "max_mecha_1d": 38.0,
    "max_mecha_contra_pct": 32.0,
    "max_dist_ema50_4h": 3.2,
    "max_dist_ema50_1d": 4.2,
    "max_distancia_ema50_atrs": 3.2,
}

# -*- coding: utf-8 -*-
'''
Árbitro IA
'''
def arbitro_ia(fila, lado, entry, sl, tp):
    """
    Evalúa las compuertas institucionales de volumen, anatomía de mecha y sobreextensión EMA 50.
    Devuelve: (autorizado: bool, multiplicador_riesgo: float, motivo: str)
    """
    es_1d = bool(fila.get("_es_1d", False))

    p_ref = float(fila.get("close", entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    rvol_min = CONFIG_IA["rvol_1d"] if es_1d else CONFIG_IA["rvol_4h"]
    rvol = float(fila.get("rvol", 1.0))
    if rvol < rvol_min:
        return False, 0.0, f"VETO Volumen Insuficiente ({rvol:.2f}x < {rvol_min:.2f}x)"

    lim_mecha = CONFIG_IA["max_mecha_1d"] if es_1d else CONFIG_IA["max_mecha_4h"]
    m_sup = float(fila.get("mecha_superior_pct", 0.0))
    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    if lado == "LONG" and m_sup > lim_mecha:
        return False, 0.0, f"VETO Mecha Trampa Superior ({m_sup:.1f}% > {lim_mecha:.1f}%)"
    if lado == "SHORT" and m_inf > lim_mecha:
        return False, 0.0, f"VETO Mecha Trampa Inferior ({m_inf:.1f}% > {lim_mecha:.1f}%)"

    lim_dist = CONFIG_IA["max_dist_ema50_1d"] if es_1d else CONFIG_IA["max_dist_ema50_4h"]
    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > lim_dist:
        return False, 0.0, f"VETO Sobreextensión EMA50 ({dist_ema:.2f} ATR > {lim_dist:.1f})"

    marco_lbl = "1D" if es_1d else "4H"
    return True, 1.0, f"AUTORIZADO por Antigravity CIO (Donchian Estructural {marco_lbl} + RVOL + Squeeze)"
