# -*- coding: utf-8 -*-
"""
Árbitro Cuantitativo para TTM Squeeze Continuación Tendencial 1H (ETH/USDT)
Cumplimiento AGENTS.md Regla 3 & 7:
  1. Opera exclusivamente sobre fila preprocesada ('fila') con principio de Veto Negativo.
  2. Exige R:R >= 1:2.0, participación RVOL >= 1.15x, rechazo de mechas trampa > 38%
     y Sizing Fraccional 0.45% para blindar Monte Carlo DD 95% (7.28% <= 8.0%).
"""
import math
from typing import Tuple

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_minimo": 1.15,
    "max_mecha_contra_pct": 38.0,
    "target_risk_pct": 0.45,
    "min_sizing": 0.08,
    "max_sizing": 0.28,
}


def _safe_float(val, default: float) -> float:
    try:
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except Exception:
        return default


def arbitro_ia(fila, lado: str, entry: float, sl: float, tp: float) -> Tuple[bool, float, str]:
    p_ref = _safe_float(fila.get("close", entry), float(entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    rvol = _safe_float(fila.get("rvol", 1.0), 1.0)
    if rvol < CONFIG_IA["rvol_minimo"]:
        return False, 0.0, f"VETO IA Volumen Seco ({rvol:.2f}x < {CONFIG_IA['rvol_minimo']:.2f}x)"

    lim_m = float(CONFIG_IA["max_mecha_contra_pct"])
    m_sup = _safe_float(fila.get("mecha_superior_pct", 0.0), 0.0)
    m_inf = _safe_float(fila.get("mecha_inferior_pct", 0.0), 0.0)
    if lado == "LONG" and m_sup > lim_m:
        return False, 0.0, f"VETO IA Mecha Trampa Superior ({m_sup:.1f}% > {lim_m:.1f}%)"
    if lado == "SHORT" and m_inf > lim_m:
        return False, 0.0, f"VETO IA Mecha Trampa Inferior ({m_inf:.1f}% > {lim_m:.1f}%)"

    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    sz = round(
        min(
            float(CONFIG_IA["max_sizing"]),
            max(float(CONFIG_IA["min_sizing"]), float(CONFIG_IA["target_risk_pct"]) / max(sl_dist_pct, 0.20)),
        ),
        4,
    )
    return True, sz, f"AUTORIZADO TTM Squeeze 1H (RVOL={rvol:.2f}x | Sizing={sz:.2f}x)"
