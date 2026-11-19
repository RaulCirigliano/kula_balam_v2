# -*- coding: utf-8 -*-
"""
Árbitro Cuantitativo para Kula Balam Cava & Ruiz (ETH/USDT 1H)
Calibrado en meseta S46 (S45..S50): Asimetría R:R >= 1:2.0 y Sizing Fraccional 0.60%
para blindar Monte Carlo DD 95% <= 6.32%.
"""
from typing import Tuple

CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "target_risk_pct": 0.60,
    "max_sizing": 0.42,
    "min_sizing": 0.10,
}


def arbitro_ia(fila, lado: str, entry: float, sl: float, tp: float) -> Tuple[bool, float, str]:
    p_ref = float(fila.get("close", entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    target_risk = float(CONFIG_IA["target_risk_pct"])
    sz = round(
        min(
            float(CONFIG_IA["max_sizing"]),
            max(float(CONFIG_IA["min_sizing"]), target_risk / max(sl_dist_pct, 0.20)),
        ),
        4,
    )
    return True, sz, f"AUTORIZADO Cava ETH 1H (Sizing {sz:.2f}x · Riesgo {target_risk:.2f}%)"
