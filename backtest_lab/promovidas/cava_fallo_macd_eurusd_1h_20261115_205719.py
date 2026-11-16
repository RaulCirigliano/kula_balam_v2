# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: EURUSD=X | Dataset: yf_EURUSD_1h.parquet | Slot Asignado: 1
Fecha de Promoción: 2026-11-15T20:57:19.646407+00:00
"""

# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN
Activo: EURUSD=X | Dataset: yf_EURUSD_1h.parquet | Slot Asignado: 1
Fecha de Promoción: 2026-11-09T21:19:14.445966+00:00
"""

# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA EN BACKTEST LAB PARA MERCADO FOREX (EUR/USD)
Guía III: Acción del Precio, Geometría y Axiomas de Reacción (Cava / Trullás)
Tesis: Fallo de MACD en agotamiento de Onda C + Mechas de Absorción Institucional + Trailing ATR
Dataset: yf_EURUSD_1h.parquet | Velas: 17,264 (2024 a 2026, ~2.8 años)
Métricas: N=56 | PF=1.96 | Win Rate=55.36% | R:R=1.58 | Max DD=0.63% | Retorno=2.39%
Walk-Forward: In-Sample (70%) PF=1.56 (N=46) | Out-of-Sample Ciego (30%) PF=8.25 (N=10, Ret=+1.08%)
Dictamen: ✅ POSITIVA CERTIFICADA (Walk-Forward Aprobado)
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "yf_EURUSD_1h.parquet"
ARBITRO_IA = "arbitro_cava_forex_1h.py"
BREAKEVEN_RR = 0.0
TRAILING_ATR_MULT = 1.8
MAX_BARS_HOLD = 36


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    """
    Gatillo Determinista de Fallo de MACD + Mecha de Barrido en Horario Londres/NY.
    """
    if "_c1h_opt_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
        df["_atr"] = tr.rolling(14).mean().shift(1).bfill()

        # MACD Clásico (12, 26, 9)
        e12 = df["close"].ewm(span=12, adjust=False).mean()
        e26 = df["close"].ewm(span=26, adjust=False).mean()
        df["_macd"] = e12 - e26
        df["_sig"] = df["_macd"].ewm(span=9, adjust=False).mean()
        df["_hist"] = df["_macd"] - df["_sig"]

        # Tendencia Direccional
        df["_ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["_ema200"] = df["close"].ewm(span=200, adjust=False).mean()

        # Ventana de swing para detección de fallo (8 periodos)
        df["_l_sw"] = df["low"].shift(2).rolling(8).min().bfill()
        df["_h_sw"] = df["high"].shift(2).rolling(8).max().bfill()
        df["_hm_sw"] = df["_hist"].shift(2).rolling(8).min().bfill()
        df["_hx_sw"] = df["_hist"].shift(2).rolling(8).max().bfill()

        df["_c1h_opt_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    c = float(row["close"])
    atr = float(row["_atr"])
    hist = float(row["_hist"])
    hist_p = float(df["_hist"].iloc[i - 1])

    # Horario Bursátil Europeo y Americano (07:00 a 18:00 UTC)
    hora = row.name.hour if hasattr(row.name, "hour") else 12
    if hora < 7 or hora > 18:
        return False, None, 0.0, 0.0

    rango = max(h - l, 1e-5)
    mecha_inf = ((min(o, c) - l) / rango) * 100.0
    mecha_sup = ((h - max(o, c)) / rango) * 100.0

    # 1. SETUP LONG: Fallo de MACD Alcista
    # Precio marca nuevo mínimo pero el histograma de MACD marca suelo creciente
    # Confirmación: Cierre sobre EMA 50 y Mecha de absorción inferior >= 25%
    if (l < float(row["_l_sw"])) and (hist > float(row["_hm_sw"])) and (hist > hist_p) and (c > o) and (mecha_inf >= 25.0) and (c > float(row["_ema50"])):
        dsl = 1.4 * atr
        return True, "LONG", c - dsl, c + (3.0 * dsl)

    # 2. SETUP SHORT: Fallo de MACD Bajista
    # Precio marca nuevo máximo pero el histograma de MACD marca techo decreciente
    # Confirmación: Cierre bajo EMA 50 y Mecha de rechazo superior >= 25%
    if (h > float(row["_h_sw"])) and (hist < float(row["_hx_sw"])) and (hist < hist_p) and (c < o) and (mecha_sup >= 25.0) and (c < float(row["_ema50"])):
        dsl = 1.4 * atr
        return True, "SHORT", c + dsl, c - (3.0 * dsl)

    return False, None, 0.0, 0.0

# --- ÁRBITRO HEURÍSTICO IA ---
# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/estrategias_ia/arbitro_cava_forex_1h.py
Proyecto: Kula Balam / Backtest Lab (Rol ANTIGRAVITY CIO - Árbitro Heurístico de Forex)
Especializado en la Escuela de Acción del Precio, Geometría y Axiomas de Reacción (Cava / Trullás):
  1. Cero cálculo de indicadores: opera sobre la fila preprocesada ('fila').
  2. Principio de Veto Negativo Puro:
     - Exige asimetría teórica R:R >= 1:2.0.
     - Veta mechas de rechazo opuestas > 32% (absorción contraria en parqué).
     - Veta sobreextensión dinámica respecto a EMA 50 > 3.5 ATR (agotamiento por estiramiento).
     - Desactiva el umbral de volumen centralizado (rvol_minimo = 0.0) por tratarse de Forex spot.
"""

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "max_mecha_contra": 32.0,
    "max_dist_ema50_atrs": 3.5,
    "rvol_minimo": 0.0,
}


def arbitro_ia(fila, lado, entry, sl, tp):
    """
    Evalúa las compuertas institucionales para Forex EUR/USD 1H.
    Devuelve: (autorizado: bool, multiplicador_riesgo: float, motivo: str)
    """
    p_ref = float(fila.get("close", entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    # 1. Asimetría mínima exigida por protocolo CIO
    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R insuficiente ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    # 2. Veto por mecha en contra (presión pasiva opuesta en subasta)
    m_sup = float(fila.get("mecha_superior_pct", 0.0))
    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    lim_m = float(CONFIG_IA["max_mecha_contra"])

    if lado == "LONG" and m_sup > lim_m:
        return False, 0.0, f"VETO Mecha superior excesiva ({m_sup:.1f}% > {lim_m:.1f}%): Presión vendedora activa"
    if lado == "SHORT" and m_inf > lim_m:
        return False, 0.0, f"VETO Mecha inferior excesiva ({m_inf:.1f}% > {lim_m}%): Absorción compradora activa"

    # 3. Sobreextensión dinámica respecto a la media de equilibrio (EMA 50)
    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > float(CONFIG_IA["max_dist_ema50_atrs"]):
        return False, 0.0, f"VETO Sobreextensión dinámica ({dist_ema:.2f} ATR > {CONFIG_IA['max_dist_ema50_atrs']} ATR)"

    return True, 1.0, "AUTORIZADO por Árbitro CIO Forex"
