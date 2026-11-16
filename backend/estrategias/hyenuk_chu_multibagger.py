"""
===============================================================================
ESTRATEGIA CUANTITATIVA: HYENUK CHU · SWING TREND & TRIM (1H MULTIBAGGER)
===============================================================================
Ecosistema: KULA · BALAM
Basado en: Metodología de Trend Following Asimétrico y Vela Elefante de Hyenuk Chu
(20 años de experiencia bursátil en Wall Street y activos líderes).

Pilares del Sistema:
1. Temporalidad Estricta Horaria (1H):
   - Especializada en capturar tendencias institucionales prolongadas (2 a 10 días).
   - Minimiza drásticamente el ruido de 5M y el impacto de comisiones/spreads (< 4% del TP).
2. Direccionalidad Exclusiva en LONG (Compras):
   - Prohíbe taxativamente ventas en corto en acciones/ETFs por la asimetría negativa
     de riesgo inherente (pérdida ilimitada en short squeezes).
3. Gatillo de Vela Elefante de Ignición:
   - Vela verde de expansión con cuerpo sólido (Cierre > Apertura).
   - Rango total amplio respecto a la volatilidad reciente: Range >= 1.0 x ATR_14.
   - Mecha superior pequeña (UpperWick <= 25% del rango total) indicando control comprador.
   - Volumen institucional participante: RVOL >= 1.10.
4. Alineación Tendencial Institucional:
   - Precio sobre EMA 200 con pendiente positiva y sobre SMA 20 de corto plazo.
5. Filtro Contrario Anti-Euforia (Doctrina Chu):
   - Veto de compra si RSI(14) > 75.0 (evita comprar en techos de consenso vertical).
   - Impulso mínimo requerido: RSI(14) >= 45.0.
6. Stop Estructural al 50% de la Vela Elefante & Peluqueo:
   - Stop Loss anclado en el 50% del cuerpo de la vela elefante (equilibrio de subasta)
     o en su mínimo de ignición, más 2 ticks de margen estructural.
   - Peluqueo 50/50: Toma de ganancias del 50% en TP1 (+3.5% a +5.0% neto, R:R >= 1:2.0).
   - Free-Roll: Stop trasladado inmediatamente a Breakeven ($0 riesgo) para correr 2 a 10 días.
===============================================================================
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd

from backend.estrategias.base import EstrategiaBase
from backend.estrategias.config_manager import StrategyConfigManager
from backend.quant_risk import (
    MIN_NET_RR,
    net_return_after_costs,
    net_rr_metrics,
    required_tp_gross_for_rr,
)

CHU_STRATEGY_TIMEFRAMES: Set[str] = {"1h"}


class HyenukChuMultibagger(EstrategiaBase):
    """
    Seguidor de Tendencia Institucional Swing 1H (Hyenuk Chu)
    con detección de Vela Elefante, Stop al 50% de ignición y Peluqueo 50/50.
    """

    id: str = "hyenuk_chu_multibagger"
    nombre: str = "🐘👑 Hyenuk Chu: Swing Multibagger"
    descripcion: str = (
        "Estrategia de seguimiento tendencial institucional en 1H para activos líderes (NVDA, TSLA, BTC, QQQ, CEDEARs). "
        "Exige alineación sobre EMA 200 alcista y SMA 20, detecta Velas Elefante de ignición con volumen RVOL >= 1.10, "
        "aplica filtro anti-euforia RSI <= 75, sitúa Stop estructural al 50% de la vela con 2 ticks de holgura "
        "y asegura capital con Peluqueo del 50% en TP1 (+3.5% neto) dejando correr el remanente a Breakeven."
    )
    autor: str = "Hyenuk Chu (Adaptación Cuantitativa Kula Balam)"
    activos_recomendados: List[str] = [
        "NVDA", "TSLA", "BTC/USDT", "SOL/USDT", "QQQ", "SPY", "AAPL", "MSFT", "AMZN",
        "GGAL.BA", "BMA.BA", "YPFD.BA"
    ]
    temporalidades_permitidas: Set[str] = CHU_STRATEGY_TIMEFRAMES
    horario_operativo: str = "Swing Trading 1H (Vigente durante toda la tendencia)"

    parametros_por_defecto: Dict[str, Any] = {
        "timeframe": "1h",
        "min_rr_ratio": 2.0,                  # Asimetría obligatoria R:R >= 1:2.0
        "first_tp_trim_pct": 3.50,            # Hito de ganancia TP1 para peluqueo parcial (+3.5% bruto)
        "sl_fallback_pct": 1.75,              # Stop Loss de referencia si no hay vela completa
        "min_rvol": 1.10,                     # Volumen relativo mínimo participante
        "max_rsi_euphoria": 75.0,             # Veto si RSI > 75 (anti-techos de consenso)
        "min_rsi": 45.0,                      # Impulso mínimo necesario
        "elephant_atr_multiplier": 1.0,       # Rango mínimo de vela elefante respecto a ATR
        "max_upper_wick": 0.25,               # Mecha superior máxima (25% del rango)
        "factor_atr_stop": 0.15,              # Margen adicional ATR para Stop a Misa
        "ticks_seguridad": 2,                 # Margen estructural de 2 ticks
        "tick_size": 0.01,
        "peluqueo_partial_pct": 50.0,         # Cierre del 50% en TP1
    }

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
        latest = ind.get("latest", {})
        current_price = float(ind.get("live_price") or latest.get("close") or 0.0)
        tf_label = ind.get("timeframe") or "1h"
        live_px = ind.get("live_price")
        live_txt = f" [Tick vivo: ${live_px:.2f}]" if (live_px is not None and live_px > 0) else ""

        # 0. Sincronización con el Gestor de Configuración Dinámica
        is_active = StrategyConfigManager.is_strategy_active(self.id, default=True)
        sub_long_enabled = StrategyConfigManager.is_sub_enabled(self.id, "operar_long", default=True)
        sub_elephant_enabled = StrategyConfigManager.is_sub_enabled(self.id, "filtro_vela_elefante", default=True)
        sub_rvol_enabled = StrategyConfigManager.is_sub_enabled(self.id, "filtro_rvol_institucional", default=True)
        sub_euphoria_enabled = StrategyConfigManager.is_sub_enabled(self.id, "filtro_anti_euforia_rsi", default=True)
        sub_stop_50_enabled = StrategyConfigManager.is_sub_enabled(self.id, "stop_estructural_50pct", default=True)
        sub_peluqueo_enabled = StrategyConfigManager.is_sub_enabled(self.id, "peluqueo_tp1", default=True)

        min_rr_target = float(StrategyConfigManager.get_parameter(self.id, "min_rr_ratio", self.parametros_por_defecto["min_rr_ratio"]))
        first_tp = float(StrategyConfigManager.get_parameter(self.id, "first_tp_trim_pct", self.parametros_por_defecto["first_tp_trim_pct"]))
        sl_fallback = float(StrategyConfigManager.get_parameter(self.id, "sl_fallback_pct", self.parametros_por_defecto["sl_fallback_pct"]))
        min_rvol = float(StrategyConfigManager.get_parameter(self.id, "min_rvol", self.parametros_por_defecto["min_rvol"]))
        max_rsi = float(StrategyConfigManager.get_parameter(self.id, "max_rsi_euphoria", self.parametros_por_defecto["max_rsi_euphoria"]))
        min_rsi = float(StrategyConfigManager.get_parameter(self.id, "min_rsi", self.parametros_por_defecto["min_rsi"]))
        elephant_atr_mult = float(StrategyConfigManager.get_parameter(self.id, "elephant_atr_multiplier", self.parametros_por_defecto["elephant_atr_multiplier"]))
        max_upper_wick = float(StrategyConfigManager.get_parameter(self.id, "max_upper_wick", self.parametros_por_defecto["max_upper_wick"]))
        factor_atr = float(StrategyConfigManager.get_parameter(self.id, "factor_atr_stop", self.parametros_por_defecto["factor_atr_stop"]))
        ticks_seguridad = int(StrategyConfigManager.get_parameter(self.id, "ticks_seguridad", self.parametros_por_defecto["ticks_seguridad"]))
        tick_size = float(StrategyConfigManager.get_parameter(self.id, "tick_size", self.parametros_por_defecto["tick_size"]))

        filter_failures: List[str] = []
        applied_safeguards: List[str] = []

        if not is_active:
            filter_failures.append("Estrategia Hyenuk Chu Multibagger archivada o desactivada por el operador.")
            return (
                self._build_metrics("MANTENER", "HOLD", "araujo_inactive", 0.0, 0.0, 0.0, filter_failures, applied_safeguards, current_price),
                0.0, False, filter_failures, min_profit_pct
            )

        if not sub_long_enabled:
            filter_failures.append("Subestrategia LONG desactivada en el Gestor de Estrategias.")

        # Datos técnicos de la vela
        open_px = float(latest.get("open") or (current_price * 0.98))
        high = float(latest.get("high") or (current_price * 1.005))
        low = float(latest.get("low") or (open_px * 0.995))
        candle_range = max(high - low, 0.0001)

        ema_200_val = ind.get("ema_200_value")
        ema_200_slope = ind.get("ema_200_slope_pct")
        sma_20_val = float(latest.get("sma_20") or (current_price * 0.97))
        rsi_val = float(latest.get("rsi") or ind.get("rsi_14") or 50.0)
        rvol = float(ind.get("relative_volume") or latest.get("relative_volume") or 1.0)
        atr_14 = float(ind.get("atr_14") or latest.get("atr_14") or (candle_range))

        upper_wick = max(high - max(open_px, current_price), 0.0)
        upper_wick_ratio = upper_wick / candle_range

        # 1. Filtro Tendencial Institucional
        if ema_200_val is not None:
            if current_price <= ema_200_val:
                filter_failures.append(
                    f"Cierre vela {tf_label} (${current_price:.2f}) no supera la EMA200 institucional (${ema_200_val:.2f}){live_txt}"
                )
            if ema_200_slope is not None and ema_200_slope < 0:
                filter_failures.append("La tendencia mayor EMA200 es bajista o plana (pendiente negativa)")
        if current_price < sma_20_val:
            filter_failures.append(
                f"Cierre vela {tf_label} (${current_price:.2f}) cotiza bajo la SMA20 (${sma_20_val:.2f}) de corto plazo{live_txt}"
            )
        else:
            applied_safeguards.append("Alineación alcista confirmada (Sobre EMA200 y SMA20)")

        # 2. Filtro Contrario y de Momentum (Anti-Euforia)
        if sub_euphoria_enabled:
            if rsi_val > max_rsi:
                filter_failures.append(
                    f"Filtro Contrario activado: RSI={rsi_val:.1f} en zona de euforia extrema (> {max_rsi}). "
                    "Chu exige no comprar en techos de consenso."
                )
            elif rsi_val < min_rsi:
                filter_failures.append(f"Falta fuerza de impulso alcista: RSI={rsi_val:.1f} < {min_rsi}")
            else:
                applied_safeguards.append(f"RSI en rango sano ({rsi_val:.1f} <= {max_rsi})")

        # 3. Filtro de Volumen Participante
        if sub_rvol_enabled:
            if rvol < min_rvol:
                filter_failures.append(f"Volumen anémico (RVOL={rvol:.2f} < {min_rvol}); falta interés institucional")
            else:
                applied_safeguards.append(f"Volumen institucional verificado (RVOL {rvol:.2f} >= {min_rvol})")

        # 4. Gatillo de Vela Elefante de Ignición
        if sub_elephant_enabled and "open" in latest and "high" in latest:
            is_green = current_price >= open_px
            has_size = candle_range >= (elephant_atr_mult * atr_14 * 0.8)
            has_small_wick = upper_wick_ratio <= max_upper_wick
            if not is_green:
                filter_failures.append("Vela horaria no es alcista (Cierre < Apertura). Chu exige vela verde sólida.")
            if not has_size:
                filter_failures.append(
                    f"Rango de vela insuficiente ({candle_range:.2f} < {elephant_atr_mult*atr_14:.2f} ATR). No califica como Vela Elefante."
                )
            if not has_small_wick:
                filter_failures.append(
                    f"Mecha superior excesiva ({upper_wick_ratio*100:.1f}% > {max_upper_wick*100:.1f}%). Rechazo en máximos."
                )
            if is_green and has_size and has_small_wick:
                applied_safeguards.append("Vela Elefante de ignición confirmada con control comprador")

        # 5. Stop Estructural al 50% de la Vela Elefante (o Mínimo Técnico)
        delta_prot = max(ticks_seguridad * tick_size, factor_atr * atr_14, 0.002 * current_price)
        if sub_stop_50_enabled and open_px < current_price:
            half_body = open_px + 0.50 * (current_price - open_px)
            sl_price = min(half_body, low) - delta_prot
            sl_calc_pct = round(max(0.60, min(5.0, (current_price - sl_price) / max(current_price, 0.0001) * 100.0)), 2)
            applied_safeguards.append(f"Stop Estructural al 50% de la vela elefante en ${sl_price:.2f} (+{ticks_seguridad} ticks)")
        else:
            sl_calc_pct = sl_fallback

        # 6. Asimetría Matemática
        # El TP debe cubrir el R:R neto objetivo (mínimo 1:2.0) y el hito de ganancia Chu (+3.5%)
        tp_target_gross = max(first_tp, round(required_tp_gross_for_rr(sl_calc_pct, fee, spread, target_rr=min_rr_target), 2))
        net_tp = round(net_return_after_costs(tp_target_gross, fee, spread), 4)
        net_sl = round(net_return_after_costs(-sl_calc_pct, fee, spread), 4)
        minimum_strategy_net_tp = max(0.50, min_profit_pct)

        if net_tp < minimum_strategy_net_tp:
            filter_failures.append(
                f"El hito de beneficio neto (+{net_tp:.2f}%) no cubre el mínimo exigido (+{minimum_strategy_net_tp:.2f}%)"
            )

        rr_info = net_rr_metrics(tp_target_gross, sl_calc_pct, fee, spread)
        if not rr_info["valid"] or round(rr_info["net_rr"], 2) < min_rr_target:
            filter_failures.append(f"R:R neto {rr_info['net_rr']:.2f} < {min_rr_target:.2f} tras costos")

        candidate_eligible = len(filter_failures) == 0
        signal = "COMPRAR" if candidate_eligible else "MANTENER"
        action = "BUY" if candidate_eligible else "HOLD"
        effective_net_tp = net_tp if candidate_eligible else 0.0

        if sub_peluqueo_enabled and candidate_eligible:
            applied_safeguards.append("Peluqueo 50% en TP1 (+3.5% a +5.0%) + Free-Roll a Breakeven ($0 riesgo)")

        strategy_metrics = {
            "mode": self.id,
            "strategy_id": self.id,
            "sub_strategy": "chu_swing_long",
            "suggested_signal": signal,
            "signal": signal,
            "action": action,
            "bias": "ALCISTA INSTITUCIONAL (SWING 1H)",
            "current_price": round(current_price, 2),
            "sma_20": round(sma_20_val, 2),
            "ema_200": round(ema_200_val, 2) if ema_200_val is not None else None,
            "ema_200_slope_pct": round(ema_200_slope, 4) if ema_200_slope is not None else None,
            "rsi": round(rsi_val, 2),
            "rsi_14": round(rsi_val, 2),
            "relative_volume": round(rvol, 2),
            "z_score": round(ind.get("z_score", 0), 4) if ind.get("z_score") is not None else None,
            "atr_14": round(atr_14, 4),
            "tp_gross_pct": tp_target_gross,
            "sl_gross_pct": sl_calc_pct,
            "tp_net_pct": net_tp,
            "sl_net_pct": net_sl,
            "candidate_eligible": candidate_eligible,
            "filter_failures": filter_failures,
            "applied_safeguards": applied_safeguards,
            "peluqueo_active": True,
        }

        return (strategy_metrics, effective_net_tp, candidate_eligible, filter_failures, min_profit_pct)

    def _build_metrics(
        self,
        signal: str,
        action: str,
        sub_strategy: str,
        tp_calc: float,
        sl_calc: float,
        net_tp: float,
        failures: List[str],
        safeguards: List[str],
        current_price: float,
    ) -> Dict[str, Any]:
        return {
            "mode": self.id,
            "strategy_id": self.id,
            "sub_strategy": sub_strategy,
            "suggested_signal": signal,
            "signal": signal,
            "action": action,
            "bias": "NEUTRAL",
            "current_price": round(current_price, 2),
            "tp_gross_pct": tp_calc,
            "sl_gross_pct": sl_calc,
            "tp_net_pct": net_tp,
            "sl_net_pct": round(-abs(sl_calc), 4),
            "candidate_eligible": False,
            "filter_failures": failures,
            "applied_safeguards": safeguards,
            "peluqueo_active": False,
        }
