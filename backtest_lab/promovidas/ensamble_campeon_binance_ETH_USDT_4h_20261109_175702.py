# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: ETH/USDT | Dataset: binance_ETH_USDT_4h.parquet | Slot Asignado: 1
Fecha de Promoción: 2026-11-09T17:57:02.383985+00:00
"""

# -*- coding: utf-8 -*-
"""
ESTRATEGIA ENSAMBLE MULTI-SENSOR CAMPEÓN (KULA BALAM & BACKTEST LAB)
Generada automáticamente por Torneo de Poda Iterativa (Challenger Ladder).
Criterio: Máxima Rentabilidad Neta con Resolución de Conflictos por Prioridad al Mejor.
Dataset Base: binance_ETH_USDT_4h.parquet

MÉTRICAS CONSOLIDADAS DEL ENSAMBLE:
- Retorno Neto Total : +21.73% (Fricción institucional descontada)
- Profit Factor Neto : 1.29
- Win Rate Neto      : 56.1%
- Drawdown Máximo    : 14.04%
- Trades Totales     : 66

NÚCLEO DE SUB-SENSORES CAMPEONES:
- Prioridad 1: 🚀 2. Squeeze Dual ETH 4H (Slot 2) (2_squeeze_dual_eth_4h)
- Prioridad 4: 🛡️ Donchian Breakout 1H (donchian_breakout_1h)
"""
from typing import Tuple, Optional
import pandas as pd
import numpy as np

DATASET = "binance_ETH_USDT_4h.parquet"
MAX_BARS_HOLD = 84

# ==============================================================================
# 1. SUB-SENSORES MATEMÁTICOS AUDITADOS Y CERTIFICADOS
# ==============================================================================
# --- SUB-SENSOR 1: 🚀 2. Squeeze Dual ETH 4H (Slot 2) (Prioridad 1) ---
# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: ETH/USDT | Dataset: binance_ETH_USDT_4h.parquet | Slot Asignado: 2
Fecha de Promoción: 2026-11-09T16:24:54+00:00
Fórmula Estructural Certificada por Walk-Forward Autónomo (70% IS / 30% OOS Ciego)
Métricas 3Y : N=45 | PF=1.78 | WR=44.44% | R:R=2.23 | Max DD=10.38%
Walk-Forward: IS PF=1.93 (N=31) | OOS Ciego PF=1.41 (N=14, Ret=7.29%)
Configuración: BB_Squeeze_Dual(EMA200, D20/BOS8, SQ<=1.2x, SL=1.4x, RR=2.6, RVOL>=1.15)
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = 'binance_ETH_USDT_4h.parquet'
ARBITRO_IA = 'arbitro_squeeze_dual_4h.py'
MAX_BARS_HOLD = 84
PARAMETROS_CALIBRADOS = {'familia': 'BB_SQUEEZE_DUAL', 'ema_macro': 200, 'donchian_n': 20, 'bos_short': 8, 'squeeze_mult': 1.2, 'sl_mult': 1.4, 'rr_target': 2.6, 'rvol_min': 1.15, 'max_dist_atr': 2.8, 'descripcion': 'BB_Squeeze_Dual(EMA200, D20/BOS8, SQ<=1.2x, SL=1.4x, RR=2.6, RVOL>=1.15)'}


def _sensor_1_2_squeeze_dual_eth_4h(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_wf_auto_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat(
            [df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()],
            axis=1,
        ).max(axis=1)
        df["_atr"] = tr.rolling(14).mean().shift(1).bfill()
        df["_ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        em_sp = int(PARAMETROS_CALIBRADOS["ema_macro"])
        df["_ema_m"] = df["close"].ewm(span=em_sp, adjust=False).mean()
        df["_ema_slp"] = df["_ema_m"] - df["_ema_m"].shift(8)

        dn = int(PARAMETROS_CALIBRADOS["donchian_n"])
        df["_dh"] = df["high"].shift(1).rolling(dn).max().bfill()
        df["_dl"] = df["low"].shift(1).rolling(dn).min().bfill()
        df["_bw"] = (df["_dh"] - df["_dl"]) / (df["_atr"] + 1e-9)
        df["_bw_med"] = df["_bw"].shift(1).rolling(60, min_periods=20).median().bfill()

        sma20 = df["close"].shift(1).rolling(20).mean().bfill()
        std20 = df["close"].shift(1).rolling(20).std().bfill()
        df["_bb_up"] = sma20 + 2.0 * std20
        bb_w = (4.0 * std20) / (df["_atr"] + 1e-9)
        df["_bb_w"] = bb_w
        df["_bb_w_med"] = bb_w.rolling(60, min_periods=20).median().bfill()

        bos_sh = int(PARAMETROS_CALIBRADOS.get("bos_short", 8))
        df["_dl_sh"] = df["low"].shift(1).rolling(bos_sh).min().bfill()
        df["_high_8"] = df["high"].shift(1).rolling(8).max().bfill()
        df["_wf_auto_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    c = float(row["close"])
    atr = float(row["_atr"])
    e50 = float(row["_ema_50"])
    em = float(row["_ema_m"])
    slp = float(row["_ema_slp"]) if pd.notna(row["_ema_slp"]) else 0.0

    if (h - l) > (2.6 * atr):
        return False, None, 0.0, 0.0

    fam = PARAMETROS_CALIBRADOS["familia"]
    sq_m = float(PARAMETROS_CALIBRADOS["squeeze_mult"])
    sl_m = float(PARAMETROS_CALIBRADOS["sl_mult"])
    rr = float(PARAMETROS_CALIBRADOS["rr_target"])
    dsl = sl_m * atr

    if fam == "BB_SQUEEZE_DUAL":
        es_long = (c > em) and (slp > 0) and (float(row["_bb_w"]) <= float(row["_bb_w_med"]) * sq_m) and (c > float(row["_bb_up"])) and (c > float(row["_dh"])) and (c > o)
        es_short = (c < em) and (e50 < em) and (slp < 0) and (float(row["_high_8"]) >= e50 * 0.985) and (c < float(row["_dl_sh"])) and (c < o)
    else:
        comp = float(row["_bw"]) <= (float(row["_bw_med"]) * sq_m)
        es_long = comp and (c > float(row["_dh"])) and (c > em) and (slp > 0) and (c > o)
        es_short = comp and (c < float(row["_dl"])) and (c < em) and (slp < 0) and (c < o)

    if es_long:
        return True, "LONG", c - dsl, c + (rr * dsl)
    if es_short:
        return True, "SHORT", c + dsl, c - (rr * dsl)
    return False, None, 0.0, 0.0

# --- SUB-SENSOR 2: 🛡️ Donchian Breakout 1H (Prioridad 4) ---
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


def _sensor_2_donchian_breakout_1h(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
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


# ==============================================================================
# 2. ORQUESTADOR CENTRAL DE PRIORIDADES DE RENTABILIDAD
# ==============================================================================
def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    """
    Evalúa todos los sensores del núcleo campeón.
    Ante discrepancias de señal, aplica la Regla Institucional de Prioridad al Mejor:
    la subfórmula con mayor expectativa matemática individual ejecuta su orden.
    """
    sensores = [
        ("2_squeeze_dual_eth_4h", _sensor_1_2_squeeze_dual_eth_4h, 1, "🚀 2. Squeeze Dual ETH 4H (Slot 2)"),
        ("donchian_breakout_1h", _sensor_2_donchian_breakout_1h, 4, "🛡️ Donchian Breakout 1H")
    ]

    disparos = []
    for s_id, s_fn, s_rank, s_tit in sensores:
        try:
            cand, lado, sl, tp = s_fn(df, i)
            if cand and lado in ("LONG", "SHORT") and sl > 0 and tp > 0:
                disparos.append((s_rank, lado, sl, tp, s_id))
        except Exception:
            continue

    if not disparos:
        return False, None, 0.0, 0.0

    # Ordenar por rango de rentabilidad: menor número = mayor prioridad
    disparos.sort(key=lambda x: x[0])
    mejor = disparos[0]

    return True, mejor[1], mejor[2], mejor[3]

# --- ÁRBITRO HEURÍSTICO IA ---
# -*- coding: utf-8 -*-
"""
ÁRBITRO HEURÍSTICO IA CENTRAL (GATEKEEPER ÚNICO DEL ENSAMBLE)
Audita la microestructura de mercado previa a la entrada de cualquier sub-sensor:
- Asimetría matemática mínima R:R >= 1:2.0
- Expansión de volumen institucional RVOL >= 1.15
- Veto por mechas trampa de absorción en contra > 32%
- Veto por sobreextensión dinámica respecto a EMA 50 > 3.2 ATR
"""
CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_minimo": 1.15,
    "max_mecha_contra_pct": 32.0,
    "max_distancia_ema50_atrs": 3.2,
}

def arbitro_ia(fila, lado, entry, sl, tp):
    p_ref = float(fila.get("close", entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    # 1. Compuerta de Asimetría R:R
    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    # 2. Compuerta de Volumen Institucional
    rvol = float(fila.get("rvol", 1.0))
    if rvol < CONFIG_IA["rvol_minimo"]:
        return False, 0.0, f"VETO RVOL Insuficiente ({rvol:.2f}x < {CONFIG_IA['rvol_minimo']:.2f}x)"

    # 3. Compuerta de Mecha de Rechazo
    m_sup = float(fila.get("mecha_superior_pct", 0.0))
    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    lim_mecha = CONFIG_IA["max_mecha_contra_pct"]
    if lado == "LONG" and m_sup > lim_mecha:
        return False, 0.0, f"VETO Mecha Trampa Superior ({m_sup:.1f}% > {lim_mecha:.1f}%)"
    if lado == "SHORT" and m_inf > lim_mecha:
        return False, 0.0, f"VETO Mecha Trampa Inferior ({m_inf:.1f}% > {lim_mecha:.1f}%)"

    # 4. Compuerta de Sobreextensión EMA 50
    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > CONFIG_IA["max_distancia_ema50_atrs"]:
        return False, 0.0, f"VETO Sobreextensión EMA50 ({dist_ema:.2f} ATR > {CONFIG_IA['max_distancia_ema50_atrs']:.1f})"

    return True, 1.0, "AUTORIZADO por Antigravity CIO Central"
