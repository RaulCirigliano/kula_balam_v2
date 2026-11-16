"""
Estrategia Cero: Tendencia Institucional 15m (Fase 1 / Fase 3)
Basada en cruce de medias (EMA200, SMA20), RSI y validación de volumen (RVOL).
Carga los parámetros y directivas desde estrategia_01.json.
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
ESTRATEGIA_JSON_PATH = os.path.join(PROJECT_ROOT, "estrategia_01.json")


class TendenciaInstitucional01(EstrategiaBase):
    id: str = "01_tendencia_institucional_15m"
    nombre: str = "🏃🧪 Tendencia Institucional 15m (EMA 21)"
    descripcion: str = "Estrategia cuantitativa auditada basada en cruce de medias (EMA200, SMA20), RSI y validación de volumen (RVOL)."
    autor: str = "Raúl Cirigliano / Auditoría Gemini"
    activos_recomendados: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    temporalidades_permitidas: Set[str] = {"15m", "1h"}
    horario_operativo: str = "24/7 (Cripto) / Horario Bursátil Regular"
    parametros_por_defecto: Dict[str, Any] = {
        "timeframe": "15m",
        "sl_pct": 2.0,
        "tp_pct": 3.0,
        "min_rsi": 40.0,
        "min_rvol": 0.80,
    }

    def __init__(self):
        super().__init__()
        # Cargar metadatos si estrategia_01.json existe
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
        ema_200_val = ind.get("ema_200_value")
        sma_20_val = float(latest.get("sma_20")) if "sma_20" in latest and not pd.isna(latest.get("sma_20")) else current_price
        rsi_val = float(latest.get("rsi")) if "rsi" in latest and not pd.isna(latest.get("rsi")) else 50.0
        rvol = float(ind.get("relative_volume") or 1.0)
        atr_14 = float(ind.get("atr_14") or 0.0)
        tf_label = ind.get("timeframe") or "15m"
        live_px = ind.get("live_price")
        live_txt = f" [Tick vivo: ${live_px:.2f}]" if (live_px is not None and live_px > 0) else ""

        min_rsi = float(self.parametros_por_defecto.get("min_rsi", 40.0))
        min_rvol = float(self.parametros_por_defecto.get("min_rvol", 0.80))

        # SL adaptativo fuera del ruido ATR
        base_sl = float(self.parametros_por_defecto.get("sl_pct", 2.0))
        if atr_14 > 0 and current_price > 0:
            atr_pct = (atr_14 / current_price) * 100.0
            sl_calc = round(max(base_sl, SL_ATR_NOISE_MULTIPLIER * atr_pct), 2)
        else:
            sl_calc = base_sl

        tp_calc = round(max(3.0, sl_calc * 1.5), 2)
        net_tp = round(net_return_after_costs(tp_calc, fee, spread), 4)
        net_sl = round(net_return_after_costs(-sl_calc, fee, spread), 4)
        minimum_strategy_net_tp = max(0.50, min_profit_pct)

        filter_failures: List[str] = []

        # Regla 1: Precio > EMA200
        if ema_200_val is not None and current_price <= ema_200_val:
            filter_failures.append(
                f"Cierre vela {tf_label} (${current_price:.2f}) cotiza bajo la EMA200 (${ema_200_val:.2f}){live_txt}"
            )

        # Regla 2: Precio > SMA20
        if current_price <= sma_20_val:
            filter_failures.append(
                f"Cierre vela {tf_label} (${current_price:.2f}) cotiza bajo la SMA20 (${sma_20_val:.2f}){live_txt}"
            )

        # Regla 3: RSI > 40
        if rsi_val <= min_rsi:
            filter_failures.append(f"RSI={rsi_val:.1f} <= {min_rsi:.1f} (falta impulso alcista)")

        # Regla 4: RVOL > 0.8
        if rvol <= min_rvol:
            filter_failures.append(f"RVOL={rvol:.2f} <= {min_rvol:.2f} (volumen insuficiente)")

        # Regla 5: R:R neto >= 1.0 tras comisiones
        rr_info = net_rr_metrics(tp_calc, sl_calc, fee, spread)
        if not rr_info["valid"] or rr_info["net_rr"] < MIN_NET_RR:
            filter_failures.append(f"R:R neto {rr_info['net_rr']:.2f} < {MIN_NET_RR:.2f} tras costos")

        candidate_eligible = len(filter_failures) == 0
        signal = "COMPRAR" if candidate_eligible else "MANTENER"
        effective_net_tp = net_tp if candidate_eligible else 0.0

        strategy_metrics = {
            "mode": self.id,
            "current_price": round(current_price, 2),
            "sma_20": round(sma_20_val, 2),
            "ema_200": round(ema_200_val, 2) if ema_200_val is not None else None,
            "rsi": round(rsi_val, 2),
            "relative_volume": round(rvol, 2),
            "tp_gross_pct": tp_calc,
            "sl_gross_pct": sl_calc,
            "tp_net_pct": net_tp,
            "sl_net_pct": net_sl,
            "minimum_net_tp_pct": round(minimum_strategy_net_tp, 4),
            "candidate_eligible": candidate_eligible,
            "suggested_signal": signal,
            "filter_failures": filter_failures,
            "policy": (
                "Tendencia Institucional 15m (Estrategia Cero): Compra si Precio > EMA200 y SMA20, "
                "RSI > 40 y RVOL > 0.8. Venta si precio cruza bajo SMA20."
            ),
        }

        return (
            strategy_metrics,
            effective_net_tp,
            candidate_eligible,
            filter_failures,
            minimum_strategy_net_tp,
        )
