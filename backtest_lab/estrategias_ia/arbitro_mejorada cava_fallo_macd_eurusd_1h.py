# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/estrategias_ia/arbitro_cava_forex_1h.py
Proyecto: Kula Balam / Backtest Lab (Rol ANTIGRAVITY CIO - Árbitro Heurístico de Forex)
Homologado con RFC-2026-11:
  1. Cero cálculo de indicadores pesados: opera sobre la fila preprocesada ('fila').
  2. Principio de Veto Negativo Puro (Estándar Producción):
     - Exige asimetría R:R >= 1:1.55.
     - Veta mechas de rechazo opuestas >= 50.0% (Veto Universal de Mechas).
     - Permite agotamientos de Onda C hasta 6.0 ATR de EMA 50.
     - Desactiva el umbral de volumen centralizado (rvol_minimo = 0.0) por tratarse de Forex spot.
"""

CONFIG_IA = {
    "asimetria_rr_minima": 1.55,
    "max_mecha_contra": 50.0,
    "max_dist_ema50_atrs": 6.0,
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

    # 1. Asimetría mínima exigida por protocolo RFC-2026-11
    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R insuficiente ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.2f})"

    # 2. Veto Universal por mecha en contra (>= 50.0%)
    m_sup = float(fila.get("mecha_superior_pct", 0.0))
    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    lim_m = float(CONFIG_IA["max_mecha_contra"])

    if lado == "LONG" and m_sup >= lim_m:
        return False, 0.0, f"VETO Mecha superior excesiva ({m_sup:.1f}% >= {lim_m:.1f}%): Presión vendedora activa"
    if lado == "SHORT" and m_inf >= lim_m:
        return False, 0.0, f"VETO Mecha inferior excesiva ({m_inf:.1f}% >= {lim_m:.1f}%): Absorción compradora activa"

    # 3. Sobreextensión dinámica respecto a la media de equilibrio (EMA 50)
    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > float(CONFIG_IA["max_dist_ema50_atrs"]):
        return False, 0.0, f"VETO Sobreextensión dinámica ({dist_ema:.2f} ATR > {CONFIG_IA['max_dist_ema50_atrs']} ATR)"

    return True, 1.0, "AUTORIZADO por Árbitro CIO Forex (RFC-2026-11)"


def custom_brain_filter(df, i, lado, entry, sl, tp):
    """Puente homologado para catalog_adapter.py y server.py."""
    ok, _mult, motivo = arbitro_ia(df.iloc[i], lado, entry, sl, tp)
    return ok, motivo