# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: ETH/USDT | Dataset: binance_ETH_USDT_4h.parquet | Slot Asignado: 1
Fecha de Promoción: 2026-11-15T23:49:05.274676+00:00
"""

# -*- coding: utf-8 -*-
"""
ESTRATEGIA ENSAMBLE MULTI-SENSOR CAMPEÓN (KULA BALAM & BACKTEST LAB)
Generada automáticamente por Torneo de Poda Iterativa Walk-Forward (IS 70% / OOS 30%).
Criterio: Máxima Rentabilidad Neta con Resolución de Conflictos por Prioridad al Mejor.
Dataset Base: binance_ETH_USDT_4h.parquet

MÉTRICAS CONSOLIDADAS DEL ENSAMBLE:
- Retorno Neto Total : +60.47% (Fricción institucional descontada)
- Profit Factor Neto : 1.78
- Win Rate Neto      : 44.4%
- Drawdown Máximo    : 10.38%
- Trades Totales     : 45

NÚCLEO DE SUB-SENSORES CAMPEONES:
- Prioridad 1: ⚡👑 2. Squeeze Dual ETH 4H (Slot 2) (2_squeeze_dual_eth_4h)
"""
from typing import Tuple, Optional
import pandas as pd
import numpy as np

DATASET = "binance_ETH_USDT_4h.parquet"
MAX_BARS_HOLD = 84

# ==============================================================================
# 1. SUB-SENSORES MATEMÁTICOS AUDITADOS Y CERTIFICADOS
# ==============================================================================
# --- SUB-SENSOR 1: ⚡👑 2. Squeeze Dual ETH 4H (Slot 2) (Prioridad 1) ---
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
_PARAMS_CALIBRADOS_1 = {'familia': 'BB_SQUEEZE_DUAL', 'ema_macro': 200, 'donchian_n': 20, 'bos_short': 8, 'squeeze_mult': 1.2, 'sl_mult': 1.4, 'rr_target': 2.6, 'rvol_min': 1.15, 'max_dist_atr': 2.8, 'descripcion': 'BB_Squeeze_Dual(EMA200, D20/BOS8, SQ<=1.2x, SL=1.4x, RR=2.6, RVOL>=1.15)'}


def _sensor_1_2_squeeze_dual_eth_4h(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_wf_auto_init_1" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat(
            [df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()],
            axis=1,
        ).max(axis=1)
        df["_atr"] = tr.rolling(14).mean().shift(1).bfill()
        df["_ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        em_sp = int(_PARAMS_CALIBRADOS_1["ema_macro"])
        df["_ema_m"] = df["close"].ewm(span=em_sp, adjust=False).mean()
        df["_ema_slp"] = df["_ema_m"] - df["_ema_m"].shift(8)

        dn = int(_PARAMS_CALIBRADOS_1["donchian_n"])
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

        bos_sh = int(_PARAMS_CALIBRADOS_1.get("bos_short", 8))
        df["_dl_sh"] = df["low"].shift(1).rolling(bos_sh).min().bfill()
        df["_high_8"] = df["high"].shift(1).rolling(8).max().bfill()
        df["_wf_auto_init_1"] = True

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

    fam = _PARAMS_CALIBRADOS_1["familia"]
    sq_m = float(_PARAMS_CALIBRADOS_1["squeeze_mult"])
    sl_m = float(_PARAMS_CALIBRADOS_1["sl_mult"])
    rr = float(_PARAMS_CALIBRADOS_1["rr_target"])
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
        ("2_squeeze_dual_eth_4h", _sensor_1_2_squeeze_dual_eth_4h, 1, "⚡👑 2. Squeeze Dual ETH 4H (Slot 2)")
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
ÁRBITRO HEURÍSTICO IA CENTRAL (GATEKEEPER ÚNICO DEL ENSAMBLE RFC-2026-11)
Audita la microestructura de mercado previa a la entrada de cualquier sub-sensor:
- Asimetría matemática mínima R:R >= 1:2.0
- Expansión de volumen institucional RVOL >= 1.15
- Veto por mechas trampa de absorción en contra > 32% (y tope universal >= 50%)
- Veto por sobreextensión dinámica respecto a EMA 50 > 2.8 ATR
- Filtro de piso de ruido ATR (SL >= 1.35 * ATR)
- Escudo anti-cuchillo cayendo en compras LONG
"""
CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_minimo": 1.15,
    "max_mecha_contra_pct": 32.0,
    "max_distancia_ema50_atrs": 2.8,
    "sl_atr_noise_multiplier": 1.35,
}

def arbitro_ia(fila, lado, entry, sl, tp):
    p_ref = float(fila.get("close", entry))
    riesgo = max(abs(p_ref - float(sl)), abs(entry - float(sl)))
    recompensa = max(abs(float(tp) - p_ref), abs(float(tp) - entry))
    rr_teorico = recompensa / (riesgo + 1e-9)

    # 1. Compuerta de Asimetría R:R
    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.2f})"

    # 2. Piso de Ruido ATR
    atr_val = float(fila.get("atr", 0.0))
    if atr_val > 0 and riesgo < (CONFIG_IA["sl_atr_noise_multiplier"] * atr_val):
        return False, 0.0, f"VETO Ruido ATR: SL ({riesgo:.4f}) < {CONFIG_IA['sl_atr_noise_multiplier']} ATR"

    # 3. Compuerta de Volumen Institucional
    rvol = float(fila.get("rvol", 1.0))
    if rvol < CONFIG_IA["rvol_minimo"]:
        return False, 0.0, f"VETO RVOL Insuficiente ({rvol:.2f}x < {CONFIG_IA['rvol_minimo']:.2f}x)"

    # 4. Compuerta de Mechas de Absorción
    m_sup = float(fila.get("mecha_superior_pct", 0.0))
    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    lim_mecha = CONFIG_IA["max_mecha_contra_pct"]
    if lado == "LONG" and m_sup > lim_mecha:
        return False, 0.0, f"VETO Mecha Trampa Superior ({m_sup:.1f}% > {lim_mecha:.1f}%)"
    if lado == "SHORT" and m_inf > lim_mecha:
        return False, 0.0, f"VETO Mecha Trampa Inferior ({m_inf:.1f}% > {lim_mecha:.1f}%)"

    # 5. Compuerta de Sobreextensión EMA 50
    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > CONFIG_IA["max_distancia_ema50_atrs"]:
        return False, 0.0, f"VETO Sobreextensión EMA50 ({dist_ema:.2f} ATR > {CONFIG_IA['max_distancia_ema50_atrs']:.1f})"

    # 6. Escudo Anti-Cuchillo Cayendo en LONG
    o_c = float(fila.get("open", p_ref))
    c_c = float(fila.get("close", p_ref))
    if lado == "LONG" and atr_val > 0 and (o_c - c_c) > (1.2 * atr_val):
        return False, 0.0, "VETO Cuchillo Cayendo (Caída violenta > 1.2 ATR)"

    return True, 1.0, "AUTORIZADO por Antigravity CIO Central"


def custom_brain_filter(df_eval, idx, side_norm, entry_px, sl_px, tp_px):
    """Gancho estándar RFC-2026-11 para integración directa con Kula Balam."""
    fila = df_eval.iloc[idx]
    return arbitro_ia(fila, side_norm, entry_px, sl_px, tp_px)
