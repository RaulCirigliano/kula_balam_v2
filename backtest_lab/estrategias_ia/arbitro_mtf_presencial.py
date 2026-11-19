# -*- coding: utf-8 -*-
"""
Árbitro IA Multitemporal Presencial (1H -> 15M -> 5M)
Supervisa ADX 1H >= 18, sobreextensión respecto a EMA50 <= 2.6 ATR, RVOL >= 0.60
y asimetría neta R:R >= 1:2.0 con sizing fraccional de riesgo (0.60%, tope 0.42x).
"""
from typing import Tuple

CONFIG_IA = {
    "adx_1h_min": 18.0,
    "rvol_minimo": 0.60,
    "max_dist_ema50_atrs": 2.6,
    "asimetria_rr_minima": 2.0,
    "target_risk_pct": 0.60,
    "max_sizing": 0.42,
    "min_sizing": 0.10,
}


def arbitro_ia(fila, lado: str, entry: float, sl: float, tp: float) -> Tuple[bool, float, str]:
    p_ref = float(fila.get("close", entry))
    atr_trig = float(fila.get("_atr_trig", fila.get("_atr_5m", fila.get("atr", 0.0))) or 0.0)
    adx1h = float(fila.get("_adx_1h", 25.0) or 25.0)
    rvol = float(fila.get("_rvol_trig", fila.get("_rvol_5m", fila.get("rvol", 1.0))) or 1.0)
    ema_trig = float(fila.get("_ema_trig", fila.get("_ema50_5m", fila.get("ema_50", p_ref))) or p_ref)

    if adx1h < CONFIG_IA["adx_1h_min"]:
        return False, 0.0, f"VETO IA 1H Lateral (ADX {adx1h:.1f} < {CONFIG_IA['adx_1h_min']:.0f})"

    if rvol < CONFIG_IA["rvol_minimo"]:
        return False, 0.0, f"VETO IA Volumen Seco (RVOL {rvol:.2f} < {CONFIG_IA['rvol_minimo']:.2f})"

    if atr_trig > 0:
        dist_atrs = abs(p_ref - ema_trig) / atr_trig
        if dist_atrs > CONFIG_IA["max_dist_ema50_atrs"]:
            return False, 0.0, f"VETO IA Sobreextensión EMA ({dist_atrs:.2f} ATR > {CONFIG_IA['max_dist_ema50_atrs']:.1f})"

    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr = recompensa / (riesgo + 1e-9)
    if rr < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO IA Asimetría R:R ({rr:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    sz = round(
        min(
            CONFIG_IA["max_sizing"],
            max(CONFIG_IA["min_sizing"], CONFIG_IA["target_risk_pct"] / max(sl_dist_pct, 0.20)),
        ),
        4,
    )
    return True, sz, f"AUTORIZADO MTF Presencial (ADX1H={adx1h:.1f} · Sizing={sz:.2f}x)"
