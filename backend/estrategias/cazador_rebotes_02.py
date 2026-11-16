"""
Estrategia 02: Cazador de Rebotes ATR 15m (Fase 4)
Estrategia cuantitativa de reversión a la media buscando rebotes tras caídas extremas con absorción.
Basada en Z-Score (Pánico o Pullback), RSI/Mecha de absorción, RVOL y asimetría matemática R:R.
Carga parámetros y directivas desde estrategia_02.json.
"""

import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd
from backend.estrategias.base import EstrategiaBase
from backend.quant_risk import (
    MIN_NET_RR,
    SL_ATR_NOISE_MULTIPLIER,
    net_return_after_costs,
    net_rr_metrics,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ESTRATEGIA_JSON_PATH = os.path.join(PROJECT_ROOT, "estrategia_02.json")


def evaluar_estrategia(datos: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Evalúa las condiciones deterministas para la estrategia 'Cazador de Rebotes ATR'.
    Retorna: (bool viable, str motivo)
    """
    z_score = float(datos.get("z_score", 0.0) or 0.0)
    rsi = float(datos.get("rsi", 50.0) or 50.0)
    rvol = float(datos.get("rvol", 0.0) or 0.0)
    lower_wick = float(datos.get("lower_wick_ratio", 0.0) or 0.0)
    rr_neto = float(datos.get("rr_neto", 0.0) or 0.0)

    # 1. Pánico Extremo o Pullback Sano
    cond_z_score = (z_score <= -2.0) or (-1.2 <= z_score <= -0.4)

    # 2. Sobreventa o Absorción Institucional
    cond_rsi_wick = (rsi <= 35.0) or (lower_wick >= 0.25)

    # 3. Interés Institucional (Volumen)
    cond_volumen = rvol >= 0.8

    # 4. Asimetría Matemática (Riesgo/Beneficio real)
    cond_rr = rr_neto >= 1.0

    if not cond_z_score:
        return False, f"Z-Score ({z_score:.2f}) fuera de zona de pánico (<= -2.0) o pullback ([-1.2, -0.4])."
    if not cond_rsi_wick:
        return False, f"Falta sobreventa (RSI: {rsi:.1f} > 35) o mecha de absorción ({lower_wick:.2f} < 0.25)."
    if not cond_volumen:
        return False, f"Volumen insuficiente (RVOL: {rvol:.2f} < 0.80)."
    if not cond_rr:
        return False, f"R:R neto ({rr_neto:.2f}) menor a 1.0 tras comisiones."

    return True, "Confluencia de pánico/pullback, absorción y asimetría confirmada. Listo para ejecución."


class CazadorRebotes02(EstrategiaBase):
    id: str = "02_cazador_rebotes_atr_15m"
    long_entries_suspended: bool = True  # Medida Inmediata 1: Suspensión preventiva de entradas Long
    nombre: str = "🧲🧪 Cazador de Rebotes ATR 15m"
    descripcion: str = "Estrategia de reversión a la media buscando rebotes tras caídas extremas con absorción institucional."
    autor: str = "Raúl Cirigliano / Auditoría Gemini"
    activos_recomendados: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "SPY", "QQQ"]
    temporalidades_permitidas: Set[str] = {"15m", "1h"}
    horario_operativo: str = "24/7 (Cripto) / Horario Bursátil Regular"
    parametros_por_defecto: Dict[str, Any] = {
        "timeframe": "15m",
        "sl_atr_multiplier": 1.5,
        "tp_atr_multiplier": 3.0,
        "z_panic_threshold": -2.0,
        "z_pullback_min": -1.2,
        "z_pullback_max": -0.4,
        "rsi_oversold_threshold": 35.0,
        "lower_wick_min": 0.25,
        "min_rvol": 0.80,
    }

    def __init__(self):
        super().__init__()
        if os.path.isfile(ESTRATEGIA_JSON_PATH):
            try:
                with open(ESTRATEGIA_JSON_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if cfg.get("descripcion"):
                        self.descripcion = cfg["descripcion"]
            except Exception:
                pass

    def evaluar(
        self,
        ind: Dict[str, Any],
        tp: float,
        sl: float,
        fee: float,
        spread: float,
        min_profit_pct: float,
        round_trip_cost: float,
        net_tp_manual: float,
        df: Optional[Any] = None,
    ) -> Tuple[Dict[str, Any], float, bool, List[str], float]:
        latest_raw = ind.get("latest")
        latest = latest_raw if latest_raw is not None else {}
        current_price = float(latest.get("close") or ind.get("price") or 0.0)
        atr_14 = float(ind.get("atr_14") or 0.0)
        z_score = float(ind.get("z_score") if ind.get("z_score") is not None else 0.0)
        rsi_val = float(latest.get("rsi") if "rsi" in latest and not pd.isna(latest.get("rsi")) else 50.0)
        lower_wick = float(ind.get("lower_wick_ratio") or 0.0)
        rvol = float(ind.get("relative_volume") or 1.0)
        tf_label = ind.get("timeframe") or "15m"
        live_px = ind.get("live_price")
        live_txt = f" [Tick vivo: ${live_px:.2f}]" if (live_px is not None and live_px > 0) else ""

        # SL adaptativo fuera del ruido ATR (+0.1% de margen de seguridad)
        if atr_14 > 0 and current_price > 0:
            atr_pct = (atr_14 / current_price) * 100.0
            sl_calc = round(max(1.0, SL_ATR_NOISE_MULTIPLIER * atr_pct + 0.10), 2)
            tp_calc = round(max(3.0, sl_calc * 2.0), 2)
        else:
            sl_calc = 1.5
            tp_calc = 3.0

        net_tp = round(net_return_after_costs(tp_calc, fee, spread), 4)
        net_sl = round(net_return_after_costs(-sl_calc, fee, spread), 4)
        minimum_strategy_net_tp = max(0.50, min_profit_pct)

        # Cálculo R:R neto
        rr_info = net_rr_metrics(tp_calc, sl_calc, fee, spread)
        rr_neto = rr_info.get("net_rr", 0.0)

        # Evaluar lógica determinista con la función pura
        datos_eval = {
            "z_score": z_score,
            "rsi": rsi_val,
            "rvol": rvol,
            "lower_wick_ratio": lower_wick,
            "rr_neto": rr_neto,
        }
        viable, motivo = evaluar_estrategia(datos_eval)

        filter_failures: List[str] = []
        if self.long_entries_suspended:
            viable = False
            filter_failures.append(
                "Entradas en LONG suspendidas de inmediato en '02_cazador_rebotes_atr_15m': "
                "Protección de capital contra cuchillos cayendo en temporalidades de 15m durante tendencias bajistas (Medida Inmediata 1)."
            )
        elif not viable:
            filter_failures.append(motivo)

        candidate_eligible = viable and (rr_neto >= 1.0) and not self.long_entries_suspended
        signal = "COMPRAR" if candidate_eligible else "MANTENER"
        effective_net_tp = net_tp if candidate_eligible else 0.0

        setup_name = "Rebote de Pánico Extremo" if z_score <= -2.0 else "Pullback en Tendencia"

        strategy_metrics = {
            "mode": self.id,
            "setup": setup_name,
            "current_price": round(current_price, 2),
            "z_score": round(z_score, 2),
            "rsi": round(rsi_val, 2),
            "lower_wick_ratio": round(lower_wick, 3),
            "relative_volume": round(rvol, 2),
            "atr_14": round(atr_14, 4),
            "tp_gross_pct": tp_calc,
            "sl_gross_pct": sl_calc,
            "tp_net_pct": net_tp,
            "sl_net_pct": net_sl,
            "minimum_net_tp_pct": round(minimum_strategy_net_tp, 4),
            "candidate_eligible": candidate_eligible,
            "suggested_signal": signal,
            "filter_failures": filter_failures,
            "policy": (
                "Cazador de Rebotes ATR 15m (Estrategia 02): Compra si Z-Score <= -2.0 o [-1.2, -0.4], "
                "con RSI <= 35 o absorción >= 0.25, RVOL >= 0.8 y R:R neto >= 1.0 tras comisiones."
            ),
        }

        return (
            strategy_metrics,
            effective_net_tp,
            candidate_eligible,
            filter_failures,
            minimum_strategy_net_tp,
        )
