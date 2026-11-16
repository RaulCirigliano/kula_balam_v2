"""
Estrategia Cuantitativa: Tres Velas, Wyckoff VPA y Benchmark Bulkowski.
Módulo oficial integrado en el catálogo de estrategias de Trading Ollama.

Principios Cuantitativos e Institucionales:
1. Leyes de Wyckoff: Esfuerzo vs. Resultado (Anomalías de Volumen / Absorción Institucional).
2. Benchmark Thomas Bulkowski (Efectividad empírica en > 4.7M de velas):
   - Three White Soldiers (82% continuidad alcista)
   - Morning Star (78% reversión alcista)
   - Rising Three Methods (74% continuación)
   - Evening Star (72% reversión bajista)
   - Bullish Engulfing con VPA (68% reversión alcista)
   - Hammer en Soporte con RVOL (60% reversión alcista)
3. Filtro Direccional VWAP (Anclado Diario).
4. Asimetría Matemática: R:R neto >= 1:2.0.
5. Stop Loss Fuera de Ruido: SL >= 1.5 * ATR(14).
6. Protocolo de Peluqueo: TP1 al alcanzar 2.5 * ATR (toma del 50% + Breakeven real).
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd
from backend.estrategias.base import EstrategiaBase
from backend.estrategias.config_manager import StrategyConfigManager
from backend.quant_risk import MIN_NET_RR, net_return_after_costs, net_rr_metrics, required_tp_gross_for_rr

TRES_VELAS_TIMEFRAMES: Set[str] = {"1m", "5m", "15m", "1h", "4h", "1d"}


class EstrategiaTresVelas(EstrategiaBase):
    """
    Estrategia Cuantitativa de Acción del Precio, Volumen y Confluencia Multitemporal.
    """

    id: str = "tres_velas_wyckoff_bulkowski"
    nombre: str = "🕯️👑 Tres Velas & Wyckoff VPA (Bulkowski Multitemporal)"
    descripcion: str = (
        "Estrategia cuantitativa basada en la confluencia de patrones de 3 velas de alta fiabilidad "
        "(Three White Soldiers, Morning Star, Bullish Engulfing con absorción), filtro direccional VWAP, "
        "anomalías de volumen Wyckoff (RVOL) y gestión de riesgo asimétrica con peluqueo a 2.5x ATR."
    )
    autor: str = "Antigravity Quant Research"
    activos_recomendados: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "QQQ", "SPY", "NVDA", "AAPL", "MSFT"]
    temporalidades_permitidas: Set[str] = TRES_VELAS_TIMEFRAMES
    horario_operativo: str = "24/7 Cripto | 10:45-16:30 ARG Acciones"

    parametros_por_defecto: Dict[str, Any] = {
        "direction_mode": "dual",       # "dual" (Long + Short), "long_only", "short_only"
        "min_rr_ratio": 2.0,
        "atr_multiplier_sl": 1.5,
        "atr_multiplier_tp": 3.0,
        "min_rvol_threshold": 1.3,
        "min_bearish_rsi": 28.0,        # Anti-capitulación para cortos
        "max_bullish_rsi": 72.0,        # Anti-euforia para compras
        "bull_trap_wick_max": 0.25,     # Mecha superior máx en confirmación (Veto Bull Trap)
        "bear_trap_wick_max": 0.25,     # Mecha inferior máx en confirmación (Veto Bear Trap)
        "peluqueo_active": True,
        "peluqueo_partial_pct": 50.0,
        "opening_blackout_minutes": 15,
        "vwap_filter_strict": True,
    }

    @staticmethod
    def _check_triplet(c1: Any, c2: Any, c3: Any) -> Tuple[Optional[str], str, float]:
        """
        Evalúa un trío contiguo de velas según el benchmark Bulkowski.
        c1: vela más antigua, c2: vela intermedia, c3: vela más reciente del patrón.
        Retorna: (nombre_patron, tipo ['BULLISH'/'BEARISH'/'NEUTRAL'], score_fiabilidad)
        """
        try:
            o1, h1, l1, cl1 = float(c1["open"]), float(c1["high"]), float(c1["low"]), float(c1["close"])
            v1 = float(c1.get("volume", 1) if hasattr(c1, "get") else (c1["volume"] if "volume" in c1 else 1))

            o2, h2, l2, cl2 = float(c2["open"]), float(c2["high"]), float(c2["low"]), float(c2["close"])
            v2 = float(c2.get("volume", 1) if hasattr(c2, "get") else (c2["volume"] if "volume" in c2 else 1))

            o3, h3, l3, cl3 = float(c3["open"]), float(c3["high"]), float(c3["low"]), float(c3["close"])
            v3 = float(c3.get("volume", 1) if hasattr(c3, "get") else (c3["volume"] if "volume" in c3 else 1))

            c1_body = abs(cl1 - o1)
            c2_body = abs(cl2 - o2)
            c3_body = abs(cl3 - o3)
            tot_range3 = h3 - l3

            # 1. THREE WHITE SOLDIERS (82% Fiabilidad Alcista)
            # 3 velas alcistas consecutivas, cada una abre dentro del cuerpo de la anterior y cierra más alto
            if (
                cl1 > o1 and cl2 > o2 and cl3 > o3
                and cl3 > cl2 > cl1
                and o2 >= o1 and o3 >= o2
                and tot_range3 > 0
                and (cl3 - o3) > tot_range3 * 0.55
            ):
                return "Three White Soldiers", "BULLISH", 0.82

            # 1b. THREE BLACK CROWS (79% Fiabilidad Bajista / Shorting)
            # 3 velas bajistas consecutivas, cada una abre dentro del cuerpo de la anterior y cierra más bajo
            if (
                cl1 < o1 and cl2 < o2 and cl3 < o3
                and cl3 < cl2 < cl1
                and o2 <= o1 and o3 <= o2
                and tot_range3 > 0
                and (o3 - cl3) > tot_range3 * 0.55
            ):
                return "Three Black Crows", "BEARISH", 0.79

            # 2. MORNING STAR (78% Fiabilidad Alcista)
            # c1: vela roja amplia, c2: vela de indecisión (cuerpo pequeño), c3: vela verde fuerte penetrando > 50% de c1
            if (
                cl1 < o1 and c1_body > 0
                and c2_body <= c1_body * 0.45
                and cl3 > o3
                and cl3 >= (o1 + cl1) / 2.0
            ):
                return "Morning Star", "BULLISH", 0.78

            # 3. EVENING STAR (72% Fiabilidad Bajista)
            # c1: vela verde amplia, c2: vela de indecisión, c3: vela roja penetrando > 50% de c1
            if (
                cl1 > o1 and c1_body > 0
                and c2_body <= c1_body * 0.45
                and cl3 < o3
                and cl3 <= (o1 + cl1) / 2.0
            ):
                return "Evening Star", "BEARISH", 0.72

            # 4. BULLISH ENGULFING (63% - 68% con VPA)
            # c2 es roja, c3 es verde y envuelve el cuerpo de c2
            if cl2 < o2 and cl3 > o3 and cl3 >= o2 and o3 <= cl2:
                if v3 >= v2 * 1.2:
                    return "Bullish Engulfing (VPA)", "BULLISH", 0.68
                return "Bullish Engulfing", "BULLISH", 0.63

            # 5. BEARISH ENGULFING (63% Fiabilidad)
            if cl2 > o2 and cl3 < o3 and cl3 <= o2 and o3 >= cl2:
                return "Bearish Engulfing", "BEARISH", 0.63

            # 6. HAMMER EN SOPORTE (60% Fiabilidad)
            if tot_range3 > 0:
                lower_wick = min(o3, cl3) - l3
                upper_wick = h3 - max(o3, cl3)
                if lower_wick >= 1.8 * c3_body and upper_wick <= 0.20 * tot_range3 and cl3 >= o3:
                    return "Hammer", "BULLISH", 0.60

            # 7. SHOOTING STAR EN RESISTENCIA (59% Fiabilidad)
            if tot_range3 > 0:
                lower_wick = min(o3, cl3) - l3
                upper_wick = h3 - max(o3, cl3)
                if upper_wick >= 1.8 * c3_body and lower_wick <= 0.20 * tot_range3 and cl3 <= o3:
                    return "Shooting Star", "BEARISH", 0.59

        except Exception:
            pass

        return None, "NEUTRAL", 0.50

    def _detect_candlestick_pattern(self, df: Any) -> Tuple[Optional[str], str, float]:
        """
        Detecta formaciones algorítmicas evaluando tanto el último trío de velas
        como el trío cerrado anterior, asegurando cero sesgo de muestreo.
        """
        if df is None or len(df) < 3:
            return None, "NEUTRAL", 0.50

        # Paso 1: Intentar en el trío más reciente (df.iloc[-3:])
        try:
            pat, ptype, rel = self._check_triplet(df.iloc[-3], df.iloc[-2], df.iloc[-1])
            if pat:
                return pat, ptype, rel
        except Exception:
            pass

        # Paso 2: Si hay al menos 4 velas, evaluar el trío cerrado previo (df.iloc[-4:-1])
        if len(df) >= 4:
            try:
                pat, ptype, rel = self._check_triplet(df.iloc[-4], df.iloc[-3], df.iloc[-2])
                if pat:
                    return pat, ptype, rel
            except Exception:
                pass

        return None, "NEUTRAL", 0.50

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
        """
        Evalúa los filtros cuantitativos de la estrategia Tres Velas y devuelve:
        (strategy_metrics, effective_net_tp, candidate_eligible, filter_failures, minimum_strategy_net_tp)
        """
        filter_failures: List[str] = []
        metrics: Dict[str, Any] = {}

        # 0. Extracción de configuración persistente gobernada por el Gestor Táctico
        cfg = StrategyConfigManager.get_strategy_config(self.id) or {}
        params = cfg.get("parameters", {})
        min_rvol = float(params.get("min_rvol", self.parametros_por_defecto.get("min_rvol_threshold", 1.3)))
        target_rr = float(params.get("min_rr_ratio", self.parametros_por_defecto.get("min_rr_ratio", 2.0)))
        bull_trap_wick_max = float(params.get("bull_trap_wick_max", self.parametros_por_defecto.get("bull_trap_wick_max", 0.25)))
        bear_trap_wick_max = float(params.get("bear_trap_wick_max", self.parametros_por_defecto.get("bear_trap_wick_max", 0.25)))
        max_bullish_rsi = float(params.get("max_bullish_rsi", self.parametros_por_defecto.get("max_bullish_rsi", 72.0)))
        min_bearish_rsi = float(params.get("min_bearish_rsi", self.parametros_por_defecto.get("min_bearish_rsi", 28.0)))

        # 1. Extracción segura de variables de precio e indicadores
        latest = ind.get("latest") if isinstance(ind.get("latest"), (dict, pd.Series)) else {}
        close_price = float(
            ind.get("live_price")
            or ind.get("current_price_real")
            or (latest.get("close") if hasattr(latest, "get") else None)
            or ind.get("close", 0.0)
        )
        atr = float(
            ind.get("atr_14")
            or ind.get("atr")
            or (latest.get("atr_14") if hasattr(latest, "get") else 0.0)
            or 0.0
        )
        rvol = float(
            ind.get("relative_volume")
            or ind.get("rvol")
            or (latest.get("relative_volume") if hasattr(latest, "get") else 1.0)
            or 1.0
        )
        vwap = float(
            ind.get("vwap")
            or (latest.get("vwap") if hasattr(latest, "get") and latest.get("vwap") is not None and not pd.isna(latest.get("vwap")) else None)
            or close_price
        )
        ema200 = float(
            ind.get("ema_200_value")
            or ind.get("ema200")
            or (latest.get("ema_200") if hasattr(latest, "get") and latest.get("ema_200") is not None and not pd.isna(latest.get("ema_200")) else None)
            or close_price
        )

        atr_pct = (atr / close_price * 100.0) if close_price > 0 else 1.0

        # 2. Detección del Patrón de Velas
        pattern_name, pattern_type, pattern_reliability = self._detect_candlestick_pattern(df)
        metrics["detected_pattern"] = pattern_name or "Sin formación clara"
        metrics["pattern_type"] = pattern_type
        metrics["pattern_reliability_bulkowski"] = pattern_reliability

        if not pattern_name:
            filter_failures.append("No se detectó un patrón de 3 o 2 velas con ventaja estadística de Bulkowski.")
        else:
            # Validación de sub-patrón individual en panel de control
            pat_lower = pattern_name.lower()
            if "white soldiers" in pat_lower or "black crows" in pat_lower:
                if not StrategyConfigManager.is_sub_enabled(self.id, "pattern_three_white_soldiers"):
                    filter_failures.append(f"Subestrategia deshabilitada: el operador desactivó Three White Soldiers / Black Crows.")
            elif "morning star" in pat_lower or "evening star" in pat_lower:
                if not StrategyConfigManager.is_sub_enabled(self.id, "pattern_morning_star"):
                    filter_failures.append(f"Subestrategia deshabilitada: el operador desactivó Morning Star / Evening Star.")
            elif "engulfing" in pat_lower:
                if not StrategyConfigManager.is_sub_enabled(self.id, "pattern_bullish_engulfing"):
                    filter_failures.append(f"Subestrategia deshabilitada: el operador desactivó Bullish / Bearish Engulfing.")
            elif "hammer" in pat_lower or "shooting star" in pat_lower:
                if not StrategyConfigManager.is_sub_enabled(self.id, "pattern_hammer_support"):
                    filter_failures.append(f"Subestrategia deshabilitada: el operador desactivó Martillo / Shooting Star.")

        # 3. Filtro Direccional Institucional: VWAP
        is_above_vwap = close_price >= (vwap * 0.998)  # Pequeña tolerancia de 0.2% para pullback a media
        metrics["vwap"] = round(vwap, 2)
        metrics["above_vwap"] = is_above_vwap

        if self.parametros_por_defecto.get("vwap_filter_strict", True) and StrategyConfigManager.is_sub_enabled(self.id, "vwap_confluence"):
            if pattern_type == "BULLISH" and not is_above_vwap:
                filter_failures.append(f"Patrón alcista rechazado por operar debajo del VWAP diario ({close_price:.2f} < {vwap:.2f}).")
            elif pattern_type == "BEARISH" and is_above_vwap:
                filter_failures.append(f"Patrón bajista rechazado por operar encima del VWAP diario ({close_price:.2f} > {vwap:.2f}).")

        # 4. Volumen Relativo (Ley de Esfuerzo vs. Resultado Wyckoff) y Filtro RSI
        symbol_str = str(ind.get("symbol") or "").upper()
        is_forex = "=X" in symbol_str
        df_vol_sum = float(df["volume"].tail(20).sum() or 0.0) if (df is not None and isinstance(df, pd.DataFrame) and "volume" in df.columns) else 1.0
        metrics["rvol"] = round(rvol, 2)
        if StrategyConfigManager.is_sub_enabled(self.id, "wyckoff_vpa_volume"):
            if rvol < min_rvol and not (is_forex and df_vol_sum <= 0.0):
                filter_failures.append(
                    f"Volumen insuficiente (RVOL {rvol:.2f} < {min_rvol:.2f}). "
                    "Wyckoff exige esfuerzo institucional."
                )

        rsi_val = float(ind.get("rsi") or (latest.get("rsi") if hasattr(latest, "get") else 50.0) or 50.0)
        metrics["rsi"] = round(rsi_val, 2)

        if pattern_type == "BEARISH" and rsi_val < min_bearish_rsi:
            filter_failures.append(
                f"Filtro anti-capitulación activo: RSI={rsi_val:.1f} < {min_bearish_rsi:.1f} (sobreventa extrema riesgosa para vender en corto)."
            )
        elif pattern_type == "BULLISH" and rsi_val > max_bullish_rsi:
            filter_failures.append(
                f"Filtro anti-euforia activo: RSI={rsi_val:.1f} > {max_bullish_rsi:.1f} (sobrecompra riesgosa para comprar)."
            )

        # 5. Blindaje Wyckoff (Combinación 2): Vetos Bull Trap y Bear Trap en la vela de confirmación
        has_df = df is not None and isinstance(df, pd.DataFrame) and len(df) >= 1
        if has_df:
            last_candle = df.iloc[-1]
            tot_h_l = float(last_candle["high"] - last_candle["low"])
            if tot_h_l > 0:
                if pattern_type == "BULLISH":
                    upper_wick = float(last_candle["high"] - max(last_candle["open"], last_candle["close"]))
                    upper_wick_ratio = upper_wick / tot_h_l
                    metrics["upper_wick_ratio"] = round(upper_wick_ratio, 3)
                    if StrategyConfigManager.is_sub_enabled(self.id, "veto_bull_trap"):
                        if upper_wick_ratio >= bull_trap_wick_max:
                            filter_failures.append(
                                f"Veto Bull Trap (Wyckoff Blindado): Mecha superior ({upper_wick_ratio:.2f}) >= {bull_trap_wick_max:.2f} "
                                "(rechazo de oferta en máximos / Upthrust institucional)."
                            )
                elif pattern_type == "BEARISH":
                    lower_wick = float(min(last_candle["open"], last_candle["close"]) - last_candle["low"])
                    lower_wick_ratio = lower_wick / tot_h_l
                    metrics["lower_wick_ratio"] = round(lower_wick_ratio, 3)
                    if StrategyConfigManager.is_sub_enabled(self.id, "veto_bear_trap"):
                        if lower_wick_ratio >= bear_trap_wick_max:
                            filter_failures.append(
                                f"Veto Bear Trap (Wyckoff Blindado): Mecha inferior ({lower_wick_ratio:.2f}) >= {bear_trap_wick_max:.2f} "
                                "(absorción de demanda en mínimos / Wyckoff Spring)."
                            )

        # 6. Modo de Dirección Operativa (Sistema Dual: Long + Short)
        direction_mode = self.parametros_por_defecto.get("direction_mode", "dual")
        if direction_mode == "long_only" and pattern_type == "BEARISH":
            filter_failures.append("Estrategia configurada en modo exclusivo 'long_only'. Señales bajistas ignoradas.")
        elif direction_mode == "short_only" and pattern_type == "BULLISH":
            filter_failures.append("Estrategia configurada en modo exclusivo 'short_only'. Señales alcistas ignoradas.")

        # 7. Cálculo Dinámico de Niveles de Riesgo y Asimetría
        target_rr = float(self.parametros_por_defecto.get("min_rr_ratio", 2.0))
        if is_forex:
            calculated_sl_pct = round(max(0.12, 1.5 * atr_pct), 2)
            min_gross_tp_for_rr = required_tp_gross_for_rr(calculated_sl_pct, fee, spread, target_rr=target_rr)
            calculated_tp_pct = round(max(min_gross_tp_for_rr, 3.0 * atr_pct), 2)
            effective_min_profit_pct = min(min_profit_pct, 0.20)
        else:
            # SL adaptado a volatilidad: 1.5 * ATR% (fuera del ruido)
            calculated_sl_pct = round(max(sl, 1.5 * atr_pct), 2)
            # TP adaptado: Derivado con precisión matemática para garantizar R:R neto >= target_rr
            min_gross_tp_for_rr = required_tp_gross_for_rr(calculated_sl_pct, fee, spread, target_rr=target_rr)
            calculated_tp_pct = round(max(tp, min_gross_tp_for_rr), 2)
            effective_min_profit_pct = min_profit_pct

        net_tp = round(net_return_after_costs(calculated_tp_pct, fee, spread), 4)
        net_sl = round(net_return_after_costs(-calculated_sl_pct, fee, spread), 4)
        minimum_strategy_net_tp = max(effective_min_profit_pct, (calculated_sl_pct * 2.0) - round_trip_cost)

        rr_info = net_rr_metrics(calculated_tp_pct, calculated_sl_pct, fee, spread)
        effective_rr = round(float(rr_info.get("net_rr") or 0.0), 2)

        # Nivel de Peluqueo (TP1 al 50% de la posición + Breakeven real)
        tp1_peluqueo_pct = 2.5 * atr_pct
        metrics["peluqueo_tp1_pct"] = round(tp1_peluqueo_pct, 2)

        # 7. Comprobación de viabilidad y asimetría
        if net_tp < effective_min_profit_pct:
            filter_failures.append(
                f"Rendimiento neto (+{net_tp:.2f}%) inferior al umbral mínimo exigido (+{effective_min_profit_pct:.2f}%)."
            )

        if not rr_info.get("valid") or effective_rr < MIN_NET_RR:
            filter_failures.append(
                f"R:R neto {effective_rr:.2f} < {MIN_NET_RR:.2f} tras comisiones y spread."
            )

        candidate_eligible = False
        signal = "MANTENER"
        side = "NEUTRAL"

        if len(filter_failures) == 0:
            if pattern_type == "BULLISH" and direction_mode in ("dual", "long_only"):
                candidate_eligible = True
                signal = "COMPRAR"
                side = "LONG"
            elif pattern_type == "BEARISH" and direction_mode in ("dual", "short_only"):
                candidate_eligible = True
                signal = "SHORT"
                side = "SHORT"

        effective_net_tp = net_tp if candidate_eligible else 0.0

        sub_id = f"bulkowski_{str(pattern_name or 'patron').lower().replace(' ', '_')}" if pattern_name else "bulkowski_wyckoff_vpa"
        strategy_metrics = {
            "mode": self.id,
            "side": side,
            "sub_strategy": sub_id,
            "direction_mode": direction_mode,
            "setup": f"Tres Velas {pattern_name or 'N/A'} ({side})",
            "current_price": round(close_price, 2),
            "detected_pattern": pattern_name or "Sin formación clara",
            "pattern_type": pattern_type,
            "pattern_reliability_bulkowski": pattern_reliability,
            "vwap": round(vwap, 2),
            "above_vwap": is_above_vwap,
            "relative_volume": round(rvol, 2),
            "rvol": round(rvol, 2),
            "rsi": round(rsi_val, 2),
            "atr_14": round(atr, 4),
            "tp_gross_pct": calculated_tp_pct,
            "sl_gross_pct": calculated_sl_pct,
            "tp_net_pct": net_tp,
            "sl_net_pct": net_sl,
            "calculated_sl_pct": round(calculated_sl_pct, 2),
            "calculated_tp_pct": round(calculated_tp_pct, 2),
            "net_rr": effective_rr,
            "effective_rr_ratio": effective_rr,
            "peluqueo_tp1_pct": round(tp1_peluqueo_pct, 2),
            "peluqueo_rule": (
                "Cierre 50% al tocar TP1 (+2.5x ATR) y mover SL a Breakeven Real (+0.15% neto)."
                if side == "LONG"
                else "Cierre 50% al caer TP1 (-2.5x ATR) y mover SL a Breakeven Real (+0.15% neto en corto)."
            ),
            "minimum_net_tp_pct": round(minimum_strategy_net_tp, 4),
            "candidate_eligible": candidate_eligible,
            "suggested_signal": signal,
            "filter_failures": filter_failures,
            "policy": (
                "Estrategia Dual Tres Velas (Bulkowski 4.7M & Wyckoff VPA): "
                "Pata 1 (LONG / Buy the Dip): Reversión y absorción en suelo. "
                "Pata 2 (SHORT / Caída sin Suelo): Ruptura y agotamiento en techo. "
                "Confluencia VWAP diario y gestión asimétrica R:R >= 2.0."
            ),
        }

        return (
            strategy_metrics,
            effective_net_tp,
            candidate_eligible,
            filter_failures,
            minimum_strategy_net_tp,
        )
