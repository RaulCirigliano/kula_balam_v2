"""
Estrategia Trailing Dinámico: Tendencia sin Techo con Doble Escalón (Idea Raúl).
Formulación cuantitativa de seguimiento de tendencia pura sin Take Profit rígido (sin techo).

Mecánica Operativa de los 3 Escalones:
1. Stop Loss Inicial:
   - Ubicado fuera del ruido de mercado (mínimo 1.5x ATR% o 2.0% base).
   - TP de referencia (TP_ref >= 6.0% para R:R neto >= 2.0 ante compuerta matemática).
2. Escalón 1 · Breakeven de Seguridad (+0.40% bruto):
   - Apenas el retorno bruto alcance +0.40% (cubriendo costos de 0.30% RT):
   - Mover el Stop Loss a Breakeven Real bloqueando +0.15% neto garantizado (Riesgo $0).
3. Escalón 2 · Cerrojo de Scalping (+1.00% gatillo -> +0.80% piso bloqueado):
   - En cuanto el retorno bruto del precio alcance o supere +1.00%:
   - El Stop Loss debe subir inmediatamente y quedar blindado como mínimo en +0.80% bruto
     (que equivale a +0.50% neto en mano tras pagar comisiones y spread).
   - Este piso es innegociable: el Stop Loss jamás puede descender de este nivel.
4. Escalón 3 · Trailing sin Techo (Picos > +1.50%):
   - Si el precio sigue subiendo haciendo nuevos picos (ej. +2%, +3%, +5%):
   - El Trailing Stop acompaña el precio máximo (peak_price) a una distancia protectora
     de 1.2% a 1.5% detrás del pico (o sl_pct).
   - Sin Take Profit rígido que corte la subida.
   - Si el activo se da vuelta, vende asegurando el trailing, y en el peor de los casos
     nunca sale por debajo de los +0.80% brutos (+0.50% neto) del Escalón 2.
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

TRAILING_RUNNER_TIMEFRAMES: Set[str] = {"15m", "1h", "4h"}


class TrailingTrendRunner(EstrategiaBase):
    id: str = "trailing_trend_runner"
    nombre: str = "🏃👑 Trailing Dinámico: Tendencia sin Techo"
    descripcion: str = (
        "Estrategia de tendencia pura sin Take Profit rígido (sin techo) calibrada con la Fórmula de Doble Escalón: "
        "Escalón 1: Breakeven de Seguridad a +0.40% bruto (+0.15% neto garantizado, Riesgo $0). "
        "Escalón 2: Cerrojo de Scalping al tocar +1.00% bruto blindando un piso firme innegociable de +0.80% bruto (+0.50% neto). "
        "Escalón 3: Trailing sin techo para picos > +1.50% a distancia 1.2%-1.5% detrás del máximo sin cortar el rally. "
        "La posición solo se liquida cuando el mercado se gira y toca el trailing stop, embolsando la ganancia acumulada."
    )
    autor: str = "Raúl Cirigliano / Formulación Cuantitativa"
    activos_recomendados: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "NVDA", "TSLA", "QQQ", "SPY"]
    temporalidades_permitidas: Set[str] = TRAILING_RUNNER_TIMEFRAMES
    horario_operativo: str = "24/7 (Cripto) / Horario Bursátil Regular (Acciones/ETFs)"
    parametros_por_defecto: Dict[str, Any] = {
        "timeframe": "15m",
        "sl_pct": 2.0,                  # Distancia de Stop Loss inicial (mínimo 2.0% o 1.5x ATR%)
        "be_trigger_pct": 0.40,         # Escalón 1: Disparador de Breakeven (+0.40% bruto)
        "be_lock_net_pct": 0.15,        # Escalón 1: Bloqueo neto garantizado (+0.15% neto)
        "scalp_trigger_pct": 1.00,      # Escalón 2: Disparador Cerrojo Scalping (+1.00% bruto)
        "scalp_floor_gross_pct": 0.80,  # Escalón 2: Piso firme de scalping (+0.80% bruto / +0.50% neto)
        "trailing_dist_pct": 1.20,      # Escalón 3: Distancia protectora de seguimiento detrás del pico
        "reference_tp_pct": 6.0,        # TP de referencia para evaluación R:R neto >= 2.0
        "min_rsi": 40.0,                # Impulso alcista mínimo
        "max_rsi": 72.0,                # Filtro anti-euforia (no comprar en techos de consenso)
        "min_rvol": 0.80,               # Volumen mínimo institucional participante
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

        min_rsi = float(self.parametros_por_defecto.get("min_rsi", 40.0))
        max_rsi = float(self.parametros_por_defecto.get("max_rsi", 72.0))
        min_rvol = float(self.parametros_por_defecto.get("min_rvol", 0.80))
        # Calibración Cripto Fin de Semana: el volumen medio de fin de semana es 20-30% menor al de rueda bursátil regular
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
                    min_rvol = 0.65
            except Exception:
                pass

        # 1. Distancia de Stop Loss adaptativa (fuera del ruido ATR; escala Forex en =X)
        base_sl = 0.12 if is_forex else float(self.parametros_por_defecto.get("sl_pct", 2.0))
        fallback_sl = 0.22 if is_forex else base_sl
        if atr_14 > 0 and current_price > 0:
            atr_pct = (atr_14 / current_price) * 100.0
            sl_calc = round(max(base_sl, SL_ATR_NOISE_MULTIPLIER * atr_pct), 2)
        else:
            sl_calc = fallback_sl

        # 2. Objetivo Take Profit 1 (Peluqueo 50% con R:R neto >= 2.0 garantizado tras costos)
        min_tp_for_rr = required_tp_gross_for_rr(sl_calc, fee, spread, target_rr=2.0)
        tp_calc = round(max(min_tp_for_rr, sl_calc * 2.0), 2)

        net_tp = round(net_return_after_costs(tp_calc, fee, spread), 4)
        net_sl = round(net_return_after_costs(-sl_calc, fee, spread), 4)
        eff_min_profit = min(min_profit_pct, 0.20) if is_forex else min_profit_pct
        minimum_strategy_net_tp = max(0.20 if is_forex else 0.50, eff_min_profit)

        filter_failures: List[str] = []

        # Filtro 0: Veto Macro de Bitcoin (Blindaje contra colapsos de mercado)
        try:
            from backend.entry_gate import is_crypto_altcoin, get_btc_macro_status
            if is_crypto_altcoin(sym_str):
                btc_status = get_btc_macro_status()
                if btc_status.get("veto_active"):
                    filter_failures.append(
                        f"Veto Macro Bitcoin: {btc_status.get('reason')} [BTC: ${btc_status.get('btc_close', 0):.2f}]. Compras en altcoins bloqueadas para evitar atrapar cuchillos cayendo."
                    )
        except Exception:
            pass

        # Filtro 1: Tendencia Institucional Adaptativa (Macro EMA200 o Táctica SMA50)
        # Permite capturar micro-tendencias y giros tempranos cuando el precio supera la SMA50 con alineación SMA20
        tendencia_macro_alcista = (ema_200_val is not None and current_price >= ema_200_val)
        tendencia_tactica_alcista = (
            sma_50_val is not None
            and current_price >= sma_50_val
            and sma_20_val >= sma_50_val * 0.998
            and (ema_200_val is None or current_price >= ema_200_val * 0.990)
        )
        if not (tendencia_macro_alcista or tendencia_tactica_alcista):
            ref_ema = f"EMA200: ${ema_200_val:{px_fmt}}" if ema_200_val else "EMA200"
            ref_sma50 = f"SMA50: ${sma_50_val:{px_fmt}}" if sma_50_val else "SMA50"
            filter_failures.append(
                f"Cierre vela {tf_label} (${current_price:{px_fmt}}) cotiza bajo la EMA200 institucional ({ref_ema}, {ref_sma50}){live_txt}"
            )
        if ema_200_val is not None and current_price < ema_200_val and ema_200_slope is not None and ema_200_slope < -0.05:
            filter_failures.append(
                f"La EMA200 tiene pendiente fuertemente bajista ({ema_200_slope:.4f}%)"
            )

        # Filtro 2: Impulso de Corto Plazo (SMA 20)
        # Permite hasta 0.5% de tolerancia en retrocesos sanos a la media
        if current_price < (sma_20_val * 0.995):
            filter_failures.append(
                f"Cierre vela {tf_label} (${current_price:{px_fmt}}) cotiza bajo la SMA20 (${sma_20_val:{px_fmt}}) de corto plazo{live_txt}"
            )

        # Filtro 3: Momentum y Anti-Euforia (RSI)
        if rsi_val > max_rsi:
            filter_failures.append(
                f"Filtro Anti-Euforia activo: RSI={rsi_val:.1f} > {max_rsi} (sobrecompra riesgosa para abrir)"
            )
        if rsi_val < min_rsi:
            filter_failures.append(
                f"Falta fuerza de impulso alcista: RSI={rsi_val:.1f} < {min_rsi}"
            )

        # Filtro 4: Volumen Participante (exento en Forex spot sin volumen centralizado)
        if not is_forex and rvol < min_rvol:
            filter_failures.append(
                f"Volumen insuficiente: RVOL={rvol:.2f} < {min_rvol} (sin interés institucional)"
            )

        # Filtro 4b: Gatillo de Velas Japonesas y Veto de Agotamiento en Techo
        candlestick_info = {"pattern": None, "type": "NEUTRAL", "reliability": 0.5}
        if df is not None and len(df) >= 3:
            try:
                from backend.estrategias.tres_velas_wyckoff_bulkowski import EstrategiaTresVelas
                pat_name, pat_type, pat_rel = EstrategiaTresVelas()._detect_candlestick_pattern(df)
                if pat_name:
                    candlestick_info = {"pattern": pat_name, "type": pat_type, "reliability": pat_rel}
                    if pat_type == "BEARISH":
                        filter_failures.append(
                            f"Patrón de rechazo/agotamiento en techo detectado ({pat_name}). Veto preventivo para no comprar en pico."
                        )
            except Exception:
                pass

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
        signal = "COMPRAR" if candidate_eligible else "MANTENER"
        effective_net_tp = net_tp if candidate_eligible else 0.0

        strategy_metrics = {
            "mode": self.id,
            "current_price": round(current_price, px_dec),
            "sma_20": round(sma_20_val, px_dec),
            "ema_200": round(ema_200_val, px_dec) if ema_200_val is not None else None,
            "ema_200_slope_pct": round(ema_200_slope, 4) if ema_200_slope is not None else None,
            "rsi": round(rsi_val, 2),
            "relative_volume": round(rvol, 2),
            "candlestick_trigger": candlestick_info,
            "z_score": round(ind.get("z_score", 0), 4) if ind.get("z_score") is not None else None,
            "atr_14": round(atr_14, 8) if atr_14 > 0 else None,
            "lower_wick_ratio": round(ind.get("lower_wick_ratio", 0), 4) if ind.get("lower_wick_ratio") is not None else None,
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
                "Trailing Dinámico: Tendencia sin Techo (Idea Raúl). Entrada con SL protector fuera del ruido, "
                "asegura Breakeven al avanzar y acompaña el pico con Trailing Stop continuo sin límite superior."
            ),
        }

        return (
            strategy_metrics,
            effective_net_tp,
            candidate_eligible,
            filter_failures,
            minimum_strategy_net_tp,
        )
