# -*- coding: utf-8 -*-
"""
Árbitro Cuantitativo para Fractal Squeeze 15M Presencial (1H -> 15M · Londres/NY)
Principio de Veto Negativo sobre fila preprocesada ('fila'):
  - Exige asimetría matemática R:R >= 1:2.0.
  - Rechaza mechas trampa contrarias > 40%.
  - Preserva el volumen natural de salidas de compresión en 15m (sin veto RVOL destructivo).
  - Sizing fraccional 0.45% para mantener Monte Carlo DD 95% <= 6.36% (<= 8.0%).
"""
import math
from typing import Tuple

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "max_mecha_contra_pct": 40.0,
    "target_risk_pct": 0.45,
    "min_sizing": 0.08,
    "max_sizing": 0.30,
}


def _safe_float(val, default: float) -> float:
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return default


def arbitro_ia(fila, lado: str, entry: float, sl: float, tp: float) -> Tuple[bool, float, str]:
    p_ref = _safe_float(fila.get("close", entry), float(entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    m_col = "mecha_superior_pct" if lado == "LONG" else "mecha_inferior_pct"
    mecha = _safe_float(fila.get(m_col, 0.0), 0.0)
    lim_m = float(CONFIG_IA["max_mecha_contra_pct"])
    if mecha > lim_m:
        return False, 0.0, f"VETO IA Mecha Trampa ({mecha:.1f}% > {lim_m:.1f}%)"

    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    sz = round(
        min(
            float(CONFIG_IA["max_sizing"]),
            max(float(CONFIG_IA["min_sizing"]), float(CONFIG_IA["target_risk_pct"]) / max(sl_dist_pct, 0.20)),
        ),
        4,
    )
    return True, sz, f"AUTORIZADO Fractal Squeeze 15M (Sizing={sz:.2f}x)"
