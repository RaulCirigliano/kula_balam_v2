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
    "rvol_minimo": 0.70,
    "max_mecha_contra_pct": 32.0,
    "max_distancia_ema50_atrs": 2.8,
}


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

    # Sizing dinámico compensado con riesgo objetivo al 0.60% por operación:
    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    target_risk_pct = 0.60
    sz = round(min(0.22, max(0.12, target_risk_pct / max(sl_dist_pct, 0.20))), 4)
    return True, sz, f"AUTORIZADO por Antigravity CIO (Squeeze Óptimo Grid Search | Sizing sz={sz:.2f})"
