# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/estrategias_ia/arbitro_eth_fondeo_4h.py
Proyecto: Kula Balam / Backtest Lab (Rol ANTIGRAVITY CIO - Árbitro Heurístico de Veto)
Certificación Fondeo (Prop Firm Compliance - RFC-2026-11):
  1. Cero cálculo de indicadores redundantes: opera sobre la fila preprocesada o sobre df_eval.
  2. Principio de Veto Negativo puro: rechaza rupturas sin volumen institucional (< 1.15x),
     con mechas de absorción/trampa en contra (> 32%), sobreextendidas respecto a EMA 50 (> 2.8 ATR)
     o con riesgo unitario de Stop Loss que exceda el 2.9% del precio de entrada.
"""

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_minimo": 1.15,
    "max_mecha_contra_pct": 32.0,
    "max_distancia_ema50_atrs": 2.8,
    "max_sl_pct_fondeo": 2.90,
}


def arbitro_ia(fila, lado, entry, sl, tp):
    """
    Evalúa la calidad microestructural de la señal generada por Balam en 4H para Cuentas de Fondeo.
    Devuelve: (autorizado: bool, multiplicador_riesgo: float, motivo: str)
    """
    p_ref = float(fila.get("close", entry)) if hasattr(fila, "get") else float(entry)
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    # 1. Veto por Asimetría Matemática Insuficiente (Regla 3: R:R >= 1:2.0)
    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    # 2. Veto por Riesgo Unitario Máximo de Fondeo (SL <= 2.90% spot)
    sl_pct = (riesgo / (p_ref + 1e-9)) * 100.0
    if sl_pct > (CONFIG_IA["max_sl_pct_fondeo"] + 0.01):
        return False, 0.0, f"VETO Riesgo Excesivo Fondeo ({sl_pct:.2f}% > {CONFIG_IA['max_sl_pct_fondeo']:.2f}%)"

    # 3. Veto por Falta de Participación Institucional (RVOL)
    rvol = float(fila.get("rvol", 1.0)) if hasattr(fila, "get") else 1.0
    if rvol < CONFIG_IA["rvol_minimo"]:
        return False, 0.0, f"VETO Secado de Volumen ({rvol:.2f}x < {CONFIG_IA['rvol_minimo']:.2f}x)"

    # 4. Veto por Mecha de Absorción / Trampa de Liquidez en Contra
    m_sup = float(fila.get("mecha_superior_pct", 0.0)) if hasattr(fila, "get") else 0.0
    m_inf = float(fila.get("mecha_inferior_pct", 0.0)) if hasattr(fila, "get") else 0.0
    lim_mecha = CONFIG_IA["max_mecha_contra_pct"]
    if lado == "LONG" and m_sup > lim_mecha:
        return False, 0.0, f"VETO Absorción Oferta Superior ({m_sup:.1f}% > {lim_mecha:.1f}%)"
    if lado == "SHORT" and m_inf > lim_mecha:
        return False, 0.0, f"VETO Absorción Demanda Inferior ({m_inf:.1f}% > {lim_mecha:.1f}%)"

    # 5. Veto por Sobreextensión respecto al Valor Dinámico EMA 50
    dist_ema = float(fila.get("dist_ema_atrs", 0.0)) if hasattr(fila, "get") else 0.0
    if dist_ema > CONFIG_IA["max_distancia_ema50_atrs"]:
        return False, 0.0, f"VETO Sobreextensión EMA50 ({dist_ema:.2f} ATR > {CONFIG_IA['max_distancia_ema50_atrs']:.1f})"

    return True, 1.0, "AUTORIZADO por Antigravity CIO (Squeeze Fondeo + Flujo Institucional Validado)"


def custom_brain_filter(df_eval, idx, side, entry_px, sl_px, tp_px):
    """
    Gancho estándar RFC-2026-11 para integración con CatalogFormulaStrategy en Kula Balam.
    Devuelve: (autorizado: bool, motivo: str) o (autorizado: bool, mult: float, motivo: str)
    """
    fila = df_eval.iloc[idx]
    aut, mult, motivo = arbitro_ia(fila, side, entry_px, sl_px, tp_px)
    return aut, mult, motivo
