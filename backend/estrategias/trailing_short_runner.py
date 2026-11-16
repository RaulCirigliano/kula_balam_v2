"""
Estrategia Trailing Dinámico en Corto: Caída sin Suelo (Shorting Raúl).
Formulación cuantitativa simétrica para operar y capturar movimientos bajistas mediante ventas en corto.

Principios operativos:
1. Entrada en confluencia técnica bajista:
   - Precio cotizando bajo la EMA200 institucional con pendiente negativa o neutral.
   - Precio cotizando bajo la SMA20 (impulso descendente de corto plazo).
   - Filtro anti-capitulación y anti-short squeeze (RSI entre 28 y 58, sin sobreventa extrema).
   - Volumen institucional vendedor participante (RVOL >= 0.80).
2. Protección determinista inicial (Fase 1):
   - Stop Loss ubicado por encima del precio de entrada (acotado fuera del ruido ATR con tope máximo de 1.50%).
   - Objetivo de referencia (TP_ref >= 6.0% para R:R neto >= 2.0 ante la compuerta matemática).
3. Gestión dinámica en vuelo (Trailing Stop descendente sin suelo):
   - Escalón 1 (Pre-Breakeven al caer +0.30% favorable): Comprime inmediatamente el Stop Loss un 60% (de +1.50% a +0.60%).
   - Escalón 2 (Breakeven Real al caer max(0.65%, 1.2x ATR)): Fija el Stop por debajo de la entrada en terreno neto garantizado (+0.15% neto tras comisiones).
   - Escalón 3 (Trailing dinámico escalonado): Comprime trailing desde +0.70% (dist 1.0%) y +1.20% (dist 0.80%) persiguiendo los valles (mínimos).
   - Salida automática cuando el precio rebota y toca el Trailing Stop, recomprando para embolsar la ganancia acumulada.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd
from backend.estrategias.base import EstrategiaBase
from backend.quant_risk import (
    MIN_NET_RR,
    SL_ATR_NOISE_MULTIPLIER,
    net_return_after_costs,
    net_rr_metrics,
    required_tp_gross_for_rr,
)

TRAILING_SHORT_RUNNER_TIMEFRAMES: Set[str] = {"15m", "1h", "4h"}


class TrailingShortRunner(EstrategiaBase):
    id: str = "trailing_short_runner"
    nombre: str = "🐻👑 Trailing Short Runner (Caída sin Suelo)"
    descripcion: str = (
        "Estrategia de seguimiento de tendencia bajista sin Take Profit rígido (sin suelo). Permite capturar caídas "
        "completas acompañando al precio mediante un Trailing Stop dinámico que baja protegiendo las ganancias. "
        "El Stop Loss inicial se ubica por encima del precio fuera del ruido ATR (máximo 1.50%), se asegura a Breakeven Real "
        "neto garantizado al caer max(0.65%, 1.2x ATR), y comprime el trailing en escalones persiguiendo mínimos. "
        "La posición solo se cierra cuando el mercado rebota y toca el trailing stop, recomprando y embolsando la ganancia."
    )
    autor: str = "Raúl Cirigliano / Formulación Cuantitativa Short"
    activos_recomendados: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "NVDA", "TSLA", "QQQ", "SPY"]
    temporalidades_permitidas: Set[str] = TRAILING_SHORT_RUNNER_TIMEFRAMES
    horario_operativo: str = "24/7 (Cripto) / Horario Bursátil Regular (Acciones/ETFs)"
    parametros_por_defecto: Dict[str, Any] = {
        "timeframe": "1h",
        "sl_pct": 1.5,                  # Fase 1: Stop Loss inicial por encima del precio (máximo 1.5%)
        "pre_be_gross_pct": 0.30,       # Escalón 1: caída de +0.30% favorable -> comprime SL un 60%
        "be_gross_pct": 0.65,           # Fase 2: umbral base de activación Breakeven Real (max(0.65%, 1.2x ATR))
        "be_lock_net_pct": 0.15,        # Stop de Breakeven Real (+0.15% neto garantizado tras comisiones)
        "trailing_dist_pct": 1.5,       # Distancia base de seguimiento por encima del precio mínimo
        "reference_tp_pct": 6.0,        # TP de referencia para evaluación R:R neto >= 2.0
        "min_rsi": 28.0,                # Filtro anti-capitulación (no shortear sobreventa extrema < 28)
        "max_rsi": 50.0,                # Impulso bajista máximo (debe cotizar en terreno vendedor <= 50)
        "min_rvol": 1.00,               # Volumen mínimo institucional participante
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
        latest = ind["latest"]
        current_price = float(latest["close"])
        ema_200_val = ind.get("ema_200_value")
        ema_200_slope = ind.get("ema_200_slope_pct")
        sma_20_val = float(latest["sma_20"]) if "sma_20" in latest and not pd.isna(latest["sma_20"]) else current_price
        sma_50_val = float(latest["sma_50"]) if "sma_50" in latest and not pd.isna(latest.get("sma_50")) else None
        rsi_val = float(latest["rsi"]) if "rsi" in latest and not pd.isna(latest["rsi"]) else 50.0
        rvol = ind.get("relative_volume") or 1.0
        atr_14 = float(ind.get("atr_14") or 0.0)
        tf_label = ind.get("timeframe") or "15m"
        live_px = ind.get("live_price")

        min_rsi = float(self.parametros_por_defecto.get("min_rsi", 28.0))
        max_rsi = float(self.parametros_por_defecto.get("max_rsi", 50.0))
        min_rvol = float(self.parametros_por_defecto.get("min_rvol", 1.00))
        # Calibración Cripto Fin de Semana
        sym_str = str(ind.get("symbol") or (latest.get("symbol", "") if hasattr(latest, "get") else ""))
        is_forex = "=X" in sym_str.upper()
        px_dec = 5 if is_forex else 2
        px_fmt = ".4f" if is_forex else ".2f"
        live_txt = f" [Tick vivo: ${live_px:{px_fmt}}]" if (live_px is not None and live_px > 0) else ""
        if "/" in sym_str:
            try:
                from datetime import datetime, timezone, timedelta
                arg_tz = timezone(timedelta(hours=-3))
                if datetime.now(arg_tz).weekday() in (5, 6):
                    min_rvol = 0.80
            except Exception:
                pass

        # 1. Distancia de Stop Loss adaptativa (escala Forex en =X vs Cripto/Acciones)
        max_sl_cap = 0.60 if is_forex else float(self.parametros_por_defecto.get("sl_pct", 1.5))
        min_sl_floor = 0.12 if is_forex else 0.80
        fallback_sl = 0.22 if is_forex else max_sl_cap
        if atr_14 > 0 and current_price > 0:
            atr_pct = (atr_14 / current_price) * 100.0
            sl_calc = round(min(max_sl_cap, max(min_sl_floor, SL_ATR_NOISE_MULTIPLIER * atr_pct)), 2)
        else:
            sl_calc = fallback_sl

        # 2. Objetivo Take Profit 1 en corto (Peluqueo 50% con R:R neto >= 2.0 garantizado tras costos)
        min_tp_for_rr = required_tp_gross_for_rr(sl_calc, fee, spread, target_rr=2.0)
        tp_calc = round(max(min_tp_for_rr, sl_calc * 2.0), 2)

        net_tp = round(net_return_after_costs(tp_calc, fee, spread), 4)
        net_sl = round(net_return_after_costs(-sl_calc, fee, spread), 4)
        eff_min_profit = min(min_profit_pct, 0.20) if is_forex else min_profit_pct
        minimum_strategy_net_tp = max(0.20 if is_forex else 0.50, eff_min_profit)

        filter_failures: List[str] = []

        # Filtro 1: Tendencia Institucional Bajista Confirmada (Macro EMA200 con Pendiente Negativa)
        if ema_200_val is not None:
            if current_price > ema_200_val:
                ref_ema = f"EMA200: ${ema_200_val:{px_fmt}}"
                filter_failures.append(
                    f"Cierre vela {tf_label} (${current_price:{px_fmt}}) cotiza sobre la EMA200 institucional ({ref_ema}){live_txt}"
                )
            elif current_price > (ema_200_val * 0.998):
                # Cotizando a menos de 0.20% bajo la EMA200: zona de fricción/ruido marginal sin quiebre confirmado
                filter_failures.append(
                    f"Precio (${current_price:{px_fmt}}) en zona de fricción con la EMA200 (${ema_200_val:{px_fmt}}); quiebre bajista insuficiente (< 0.20% de distancia)"
                )
            if ema_200_slope is not None and ema_200_slope > -0.005:
                filter_failures.append(
                    f"La EMA200 tiene pendiente alcista o neutral ({ema_200_slope:.4f}% > -0.005%) - falta confirmación de descarga institucional"
                )
        elif sma_50_val is not None:
            if current_price > sma_50_val:
                filter_failures.append(
                    f"Cierre vela {tf_label} (${current_price:{px_fmt}}) cotiza sobre la SMA50 táctica (${sma_50_val:{px_fmt}}){live_txt}"
                )

        # Filtro 2: Cascada Bajista Estructural (Alineación de Medias Móviles)
        # En tendencia bajista confirmada, las medias rápidas deben ubicarse debajo de las lentas.
        if sma_20_val is not None and ema_200_val is not None and sma_20_val > ema_200_val:
            filter_failures.append(
                f"Alineación técnica inválida para short: SMA20 (${sma_20_val:{px_fmt}}) cotiza sobre EMA200 (${ema_200_val:{px_fmt}}) - estructura alcista intacta"
            )
        if sma_20_val is not None and sma_50_val is not None and sma_20_val > (sma_50_val * 1.005):
            filter_failures.append(
                f"Alineación contraria: SMA20 (${sma_20_val:{px_fmt}}) > SMA50 (${sma_50_val:{px_fmt}}) - estructura intermedia no bajista"
            )
        if sma_50_val is not None and ema_200_val is not None and sma_50_val > (ema_200_val * 1.005):
            filter_failures.append(
                f"Estructura táctica alcista: SMA50 (${sma_50_val:{px_fmt}}) > EMA200 (${ema_200_val:{px_fmt}})"
            )

        # Filtro 3: Impulso de Corto Plazo Descendente (SMA 20)
        if current_price > sma_20_val:
            filter_failures.append(
                f"Cierre vela {tf_label} (${current_price:{px_fmt}}) cotiza sobre la SMA20 (${sma_20_val:{px_fmt}}) de corto plazo{live_txt}"
            )

        # Filtro 4: Momentum Bajista y Filtro Anti-Capitulación / Anti-Short Squeeze (RSI)
        if rsi_val < min_rsi:
            filter_failures.append(
                f"Filtro Anti-Capitulación activo: RSI={rsi_val:.1f} < {min_rsi} (sobreventa extrema riesgosa para abrir short)"
            )
        if rsi_val > max_rsi:
            filter_failures.append(
                f"Falta fuerza de caída bajista: RSI={rsi_val:.1f} > {max_rsi} (mercado fuera de la zona de continuación bajista <= 50.0)"
            )

        # Filtro 5: Volumen Participante Institucional (RVOL; exento en Forex spot)
        if not is_forex and rvol < min_rvol:
            filter_failures.append(
                f"Volumen insuficiente: RVOL={rvol:.2f} < {min_rvol} (sin presión vendedora institucional comprobada)"
            )

        # Filtro 6: Candado Macro Multitemporal (si está disponible en ind)
        if ind.get("macro_bearish") is False and "/" in sym_str:
            filter_failures.append(
                "Régimen macro multitemporal no confirma tendencia bajista en Cripto 24/7 (riesgo de short contratendencial)"
            )

        # Filtro 5: Asimetría y Viabilidad tras costos
        if net_tp < minimum_strategy_net_tp:
            filter_failures.append(
                f"El objetivo de referencia neto (+{net_tp:.2f}%) no cubre el mínimo (+{minimum_strategy_net_tp:.2f}%)"
            )

        rr_info = net_rr_metrics(tp_calc, sl_calc, fee, spread)
        if not rr_info["valid"] or rr_info["net_rr"] < MIN_NET_RR:
            filter_failures.append(
                f"R:R neto {rr_info['net_rr']:.2f} < {MIN_NET_RR:.2f} tras costos de ida y vuelta"
            )

        candidate_eligible = len(filter_failures) == 0
        signal = "SHORT" if candidate_eligible else "MANTENER"
        effective_net_tp = net_tp if candidate_eligible else 0.0

        strategy_metrics = {
            "mode": self.id,
            "side": "SHORT",
            "current_price": round(current_price, px_dec),
            "sma_20": round(sma_20_val, px_dec),
            "ema_200": round(ema_200_val, px_dec) if ema_200_val is not None else None,
            "ema_200_slope_pct": round(ema_200_slope, 4) if ema_200_slope is not None else None,
            "rsi": round(rsi_val, 2),
            "relative_volume": round(rvol, 2),
            "z_score": round(ind.get("z_score", 0), 4) if ind.get("z_score") is not None else None,
            "atr_14": round(atr_14, 8) if atr_14 > 0 else None,
            "tp_gross_pct": tp_calc,
            "sl_gross_pct": sl_calc,
            "tp_net_pct": net_tp,
            "sl_net_pct": net_sl,
            "net_rr": round(float(rr_info.get("net_rr") or 0.0), 2),
            "trailing_dist_pct": sl_calc,
            "trailing_no_ceiling": True,
            "minimum_net_tp_pct": round(minimum_strategy_net_tp, 4),
            "candidate_eligible": candidate_eligible,
            "suggested_signal": signal,
            "filter_failures": filter_failures,
            "policy": (
                "Trailing Dinámico en Corto: Caída sin Suelo (Shorting Raúl). Entrada vendida con SL inicial por encima "
                "del precio, asegura Breakeven Real en caída y acompaña los valles con Trailing Stop continuo descendente."
            ),
        }

        return (
            strategy_metrics,
            effective_net_tp,
            candidate_eligible,
            filter_failures,
            minimum_strategy_net_tp,
        )
