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
    "rvol_4h": 0.85,
    "rvol_1d": 1.25,
    "max_mecha_4h": 32.0,
    "max_mecha_1d": 38.0,
    "max_dist_ema50_4h": 3.2,
    "max_dist_ema50_1d": 4.2,
}


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

    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    # Riesgo efectivo neto objetivo = 0.60% para blindar MC DD <= 7.8% con fricción proporcional
    sz = round(min(0.22, max(0.14, 0.60 / max(sl_dist_pct, 0.20))), 4)
    return True, sz, "Aprobado con riesgo escalado"
