# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: ETH/USDT | Dataset: binance_ETH_USDT_4h.parquet | Slot Asignado: 1
Fecha de Promoción: 2026-11-09T16:24:54.784412+00:00
"""

# -*- coding: utf-8 -*-
"""
Fórmula Estructural Certificada por Walk-Forward Autónomo (70% IS / 30% OOS Ciego)
Dataset Base: binance_ETH_USDT_4h.parquet
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


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
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

# --- ÁRBITRO HEURÍSTICO IA ---
# -*- coding: utf-8 -*-
'''
Árbitro IA
'''
def arbitro_ia(fila, lado, entry, sl, tp):
    """
    Evalúa la calidad microestructural de la señal generada por Balam en 4H.
    Devuelve: (autorizado: bool, multiplicador_riesgo: float, motivo: str)
    """
    p_ref = float(fila.get("close", entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    # 1. Veto por Asimetría Matemática Insuficiente (Regla 3: R:R >= 1:2.0)
    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    # 2. Veto por Falta de Participación Institucional (RVOL)
    rvol = float(fila.get("rvol", 1.0))
    if rvol < CONFIG_IA["rvol_minimo"]:
        return False, 0.0, f"VETO Secado de Volumen ({rvol:.2f}x < {CONFIG_IA['rvol_minimo']:.2f}x)"

    # 3. Veto por Mecha de Absorción / Trampa de Liquidez en Contra
    m_sup = float(fila.get("mecha_superior_pct", 0.0))
    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    lim_mecha = CONFIG_IA["max_mecha_contra_pct"]
    if lado == "LONG" and m_sup > lim_mecha:
        return False, 0.0, f"VETO Absorción Oferta Superior ({m_sup:.1f}% > {lim_mecha:.1f}%)"
    if lado == "SHORT" and m_inf > lim_mecha:
        return False, 0.0, f"VETO Absorción Demanda Inferior ({m_inf:.1f}% > {lim_mecha:.1f}%)"

    # 4. Veto por Sobreextensión respecto al Valor Dinámico EMA 50
    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > CONFIG_IA["max_distancia_ema50_atrs"]:
        return False, 0.0, f"VETO Sobreextensión EMA50 ({dist_ema:.2f} ATR > {CONFIG_IA['max_distancia_ema50_atrs']:.1f})"

    return True, 1.0, "AUTORIZADO por Antigravity CIO (Squeeze + Flujo Institucional Validado)"
