# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: ETH/USDT | Dataset: binance_ETH_USDT_4h.parquet | Slot Asignado: 1
Fecha de Promoción: 2026-11-09T18:06:00.477617+00:00
"""

# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/estrategias_math/squeeze_dual_eth_4h.py
Proyecto: Kula Balam / Backtest Lab (Rol BALAM - Músculo Matemático Determinista)
Activo / Temporalidad: ETH/USDT 4H (3 Años: 6,570 velas | 2023-11 -> 2026-11)
Arquitectura Estructural (Walk-Forward 70% IS / 30% OOS Ciego - Cero Sesgo):
  1. Régimen Alcista Macro (Close > EMA 200 y Pendiente EMA 200 > 0):
     Compresión previa de Bandas de Bollinger respecto a ATR (Squeeze <= 1.25x mediana 60p)
     + Ruptura simultánea de Banda Superior Bollinger y Canal Donchian de 20 velas.
  2. Régimen Bajista Macro (Close < EMA 200, EMA 50 < EMA 200 y Pendiente EMA 200 < 0):
     Rebote correctivo previo hacia zona dinámica de oferta (High_8 >= 0.985 * EMA 50)
     + Quiebre estructural bajista del soporte de 8 velas (BOS < Donchian Low 8).
  3. Gestión Asimétrica Pura: SL = 1.4x ATR(14) | TP = 3.64x ATR(14) (R:R Teórico 1:2.60).
"""

from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_ETH_USDT_4h.parquet"
ARBITRO_IA = "arbitro_squeeze_dual_4h.py"
MAX_BARS_HOLD = 84

VELA_TESTIGO = {
    "fecha_historica": "2026-09-29 08:00:00",
    "close_offset_pct": -1.35,
    "rvol": 1.85,
    "mecha_sup_pct": 8.0,
    "mecha_inf_pct": 8.0,
    "cuerpo_pct": 75.0,
}


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    """
    Motor determinista Balam para ETH/USDT 4H.
    Calcula estructuras de volatilidad y tendencia de forma estrictamente causal (shift(1)).
    """
    if "_eth4h_sq_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev_c).abs(),
                (df["low"] - prev_c).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["_atr14"] = tr.rolling(14).mean().shift(1).bfill()
        df["_ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["_ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["_slp200"] = df["_ema200"] - df["_ema200"].shift(8)

        sma20 = df["close"].shift(1).rolling(20).mean().bfill()
        std20 = df["close"].shift(1).rolling(20).std().bfill()
        df["_bb_up"] = sma20 + (2.0 * std20)
        bb_w = (4.0 * std20) / (df["_atr14"] + 1e-9)
        df["_bb_w"] = bb_w
        df["_bb_w_med"] = bb_w.rolling(60, min_periods=20).median().bfill()

        df["_dh20"] = df["high"].shift(1).rolling(20).max().bfill()
        df["_dl8"] = df["low"].shift(1).rolling(8).min().bfill()
        df["_high8"] = df["high"].shift(1).rolling(8).max().bfill()
        df["_eth4h_sq_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    c = float(row["close"])
    atr = float(row["_atr14"])

    # Filtro determinista contra velas climáticas anómalas (> 2.6 ATR)
    if (h - l) > (2.6 * atr):
        return False, None, 0.0, 0.0

    e50 = float(row["_ema50"])
    e200 = float(row["_ema200"])
    slp200 = float(row["_slp200"]) if pd.notna(row["_slp200"]) else 0.0

    # Pata LONG: Expansión alcista desde compresión Bollinger + ruptura Donchian 20
    squeeze_activo = float(row["_bb_w"]) <= (float(row["_bb_w_med"]) * 1.25)
    es_long = (
        (c > e200)
        and (slp200 > 0.0)
        and squeeze_activo
        and (c > float(row["_bb_up"]))
        and (c > float(row["_dh20"]))
        and (c > o)
    )
    if es_long:
        dist_sl = 1.4 * atr
        return True, "LONG", c - dist_sl, c + (2.6 * dist_sl)

    # Pata SHORT: Rechazo en EMA 50 dentro de tendencia bajista + quiebre suelo 8 velas
    es_short = (
        (c < e200)
        and (e50 < e200)
        and (slp200 < 0.0)
        and (float(row["_high8"]) >= (e50 * 0.985))
        and (c < float(row["_dl8"]))
        and (c < o)
    )
    if es_short:
        dist_sl = 1.4 * atr
        return True, "SHORT", c + dist_sl, c - (2.6 * dist_sl)

    return False, None, 0.0, 0.0

# =====================================================================
# ÁRBITRO DE IA HEURÍSTICO (ANTIGRAVITY CIO)
# =====================================================================
# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/estrategias_ia/arbitro_squeeze_dual_4h.py
Proyecto: Kula Balam / Backtest Lab (Rol ANTIGRAVITY CIO - Árbitro Heurístico de Veto)
Cumplimiento AGENTS.md Regla 7:
  1. Cero cálculo de indicadores ni medias: opera exclusivamente sobre la fila preprocesada ('fila').
  2. Principio de Veto Negativo puro: rechaza rupturas sin volumen institucional, con mechas
     de absorción/trampa en contra (> 32%) o sobreextendidas respecto a la EMA 50 (> 2.8 ATRs).
"""

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_4h": 0.70,
    "rvol_1d": 1.15,
    "rvol_minimo": 0.70,
    "max_mecha_4h": 32.0,
    "max_mecha_1d": 38.0,
    "max_mecha_contra_pct": 32.0,
    "max_dist_ema50_4h": 2.8,
    "max_dist_ema50_1d": 3.8,
    "max_distancia_ema50_atrs": 2.8,
}

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

    # 5. Sizing Dinámico Cuantitativo para Fondeo (Riesgo Objetivo ~0.58% de la cuenta)
    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    target_risk_pct = 0.58
    sz = round(min(0.24, max(0.12, target_risk_pct / max(sl_dist_pct, 0.20))), 4)

    return True, sz, f"AUTORIZADO por Antigravity CIO (Squeeze + Flujo Institucional Validado | Sizing sz={sz:.2f})"
