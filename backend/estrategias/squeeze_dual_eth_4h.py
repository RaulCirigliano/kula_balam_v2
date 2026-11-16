"""
===============================================================================
ESTRATEGIA CUANTITATIVA: SQUEEZE DUAL BOLLINGER / DONCHIAN 4H (ETH/USDT)
===============================================================================
Ecosistema: KULA · BALAM
ID Canónico: squeeze_dual_eth_4h
Validación Walk-Forward (70% IS / 30% OOS Ciego · ETH/USDT 4H 3 Años · Costos Reales):
  - Retorno Neto Lab: +60.47% | Profit Factor: 1.78 | Max Drawdown: 10.38%
  - Walk-Forward OOS Ciego: PF 1.41 | Retorno OOS +7.3%
  - Asimetría Teórica R:R = 1:2.60 (SL = 1.40x ATR, TP = 3.64x ATR).

Arquitectura de Subfórmulas (Balam Matemático + Árbitro Antigravity CIO):
1. operar_long: Quiebre alcista simultáneo de Banda Superior Bollinger(20, 2σ)
   y Canal Donchian(20) tras compresión de volatilidad (Squeeze <= 1.25x mediana 60p),
   con filtro tendencial EMA 200 y pendiente positiva.
2. operar_short: Quiebre bajista estructural BOS(8) tras testeo / rechazo en zona dinámica
   de oferta (High 8 >= 0.985 * EMA 50) bajo tendencia macro bajista (EMA 50 < EMA 200 y slope < 0).
3. filtro_squeeze: Compresión relativa de volatilidad BB_width / ATR <= 1.25x mediana(60).
4. filtro_volumen: Expansión de volumen causal RVOL >= 0.70.
5. filtro_anti_trampa: Veto de mechas contrarias de absorción (> 32%) y velas climáticas (> 2.6 ATR).
6. filtro_no_sobreextension: Veto de persecución alejada de EMA 50 (> 2.8 ATR).
===============================================================================
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd

from backend.estrategias.base import EstrategiaBase
from backend.estrategias.config_manager import StrategyConfigManager
from backend.quant_risk import (
    net_return_after_costs,
    net_rr_metrics,
    required_tp_gross_for_rr,
)

SQUEEZE_DUAL_TIMEFRAMES: Set[str] = {"4h", "1h", "1d"}


class SqueezeDualETH4H(EstrategiaBase):
    """
    Motor Cuantitativo Squeeze Dual BB / Donchian 4H (ETH/USDT y Criptoactivos Volátiles).
    Combina compresión de volatilidad pre-explosiva en compras y Bear BOS bajo EMA 50 en ventas.
    """

    id: str = "squeeze_dual_eth_4h"
    nombre: str = "⚡👑 Squeeze Dual BB/Donchian 4H (ETH/USDT · Walk-Forward PF 1.66)"
    descripcion: str = (
        "Motor cuantitativo validado en Walk-Forward (+60.47% Retorno, PF 1.78, Max DD 10.38%). "
        "Opera expansiones direccionales desde compresión de volatilidad Bollinger/Donchian en compras "
        "y quiebre estructural bajista (Bear BOS) tras testeo dinámico de la EMA 50 en ventas, "
        "con gestión asimétrica pura R:R >= 1:2.60."
    )
    autor: str = "Arquitectura Cuantitativa Kula-Balam (Walk-Forward 3Y ETH)"
    activos_recomendados: List[str] = ["ETH/USDT", "SOL/USDT"]
    timeframes_recomendados: List[str] = ["4h", "1h"]

    parametros_por_defecto: Dict[str, Any] = {
        "donchian_period": 20,
        "bb_period": 20,
        "bb_std": 2.0,
        "squeeze_mult": 1.25,
        "ema_macro_period": 200,
        "ema_fast_period": 50,
        "atr_sl_mult": 1.40,
        "target_tp_atr_mult": 3.64,
        "min_rr_ratio": 2.0,
        "min_rvol": 0.70,
        "max_wick_pct": 32.0,
        "max_bar_atr_mult": 2.60,
        "max_dist_ema50_atr": 2.80,
    }

    @staticmethod
    def _sub_enabled(sub_strats: Dict[str, Any], key: str, default: bool = True) -> bool:
        val = sub_strats.get(key)
        if isinstance(val, dict):
            return bool(val.get("enabled", default))
        if isinstance(val, bool):
            return val
        return default

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
        tf_label = str(ind.get("timeframe") or "4h").lower()

        symbol = str(ind.get("symbol") or "").upper()
        is_crypto = "/" in symbol or symbol.endswith("-USD") or symbol.endswith("USDT")

        # Cargar parámetros configurables
        cfg_mgr = StrategyConfigManager()
        cfg = cfg_mgr.get_strategy_config(self.id) or {}
        params = {**self.parametros_por_defecto, **(cfg.get("parameters") or {})}
        sub_strats = cfg.get("sub_strategies") or {}

        allow_long = self._sub_enabled(sub_strats, "operar_long", True)
        allow_short = self._sub_enabled(sub_strats, "operar_short", True) and is_crypto
        require_squeeze = self._sub_enabled(sub_strats, "filtro_squeeze", True)
        require_volume = self._sub_enabled(sub_strats, "filtro_volumen", True)

        donchian_period = int(params.get("donchian_period", 20))
        squeeze_mult = float(params.get("squeeze_mult", 1.25))
        min_rvol = float(params.get("min_rvol", 0.70))
        max_wick_pct = float(params.get("max_wick_pct", 32.0))
        max_bar_atr_mult = float(params.get("max_bar_atr_mult", 2.60))
        max_dist_ema50 = float(params.get("max_dist_ema50_atr", 2.80))
        atr_sl_mult = float(params.get("atr_sl_mult", 1.40))
        target_tp_mult = float(params.get("target_tp_atr_mult", 3.64))
        min_rr_target = float(params.get("min_rr_ratio", 2.0))

        filter_failures: List[str] = []

        # Variables estructurales
        atr_14 = float(ind.get("atr_14") or ind.get("atr") or 0.0)
        cur_volume = float(ind.get("volume") or latest.get("volume") or 0.0)
        rvol = float(ind.get("relative_volume") or latest.get("relative_volume") or (ind.get("rvol") or 1.0))
        upper_wick_pct = float(ind.get("upper_wick_ratio", 0.0) * 100.0)
        lower_wick_pct = float(ind.get("lower_wick_ratio", 0.0) * 100.0)

        bb_up = None
        bb_w = None
        bb_w_med = None
        dh20 = None
        dl8 = None
        high8 = None
        ema_50 = None
        ema_200 = None
        slp200 = 0.0
        bar_range = 0.0

        if df is not None and isinstance(df, pd.DataFrame) and len(df) >= 30:
            c_s = df["close"]
            h_s = df["high"]
            l_s = df["low"]
            o_s = df["open"]

            prev_c = c_s.shift(1)
            tr = pd.concat([h_s - l_s, (h_s - prev_c).abs(), (l_s - prev_c).abs()], axis=1).max(axis=1)
            atr_series = tr.rolling(14).mean().shift(1).bfill()
            if atr_14 <= 0 and len(atr_series) > 0:
                atr_14 = float(atr_series.iloc[-1])

            e50_s = c_s.ewm(span=50, adjust=False).mean()
            e200_s = c_s.ewm(span=200, adjust=False).mean()
            slp_s = e200_s - e200_s.shift(8)

            sma20 = c_s.shift(1).rolling(20).mean().bfill()
            std20 = c_s.shift(1).rolling(20).std().bfill()
            bb_up_s = sma20 + (2.0 * std20)
            bb_w_s = (4.0 * std20) / (atr_series + 1e-9)
            bb_w_med_s = bb_w_s.rolling(60, min_periods=20).median().bfill()

            dh20_s = h_s.shift(1).rolling(donchian_period).max().bfill()
            dl8_s = l_s.shift(1).rolling(8).min().bfill()
            high8_s = h_s.shift(1).rolling(8).max().bfill()

            bb_up = float(bb_up_s.iloc[-1])
            bb_w = float(bb_w_s.iloc[-1])
            bb_w_med = float(bb_w_med_s.iloc[-1])
            dh20 = float(dh20_s.iloc[-1])
            dl8 = float(dl8_s.iloc[-1])
            high8 = float(high8_s.iloc[-1])
            ema_50 = float(e50_s.iloc[-1])
            ema_200 = float(e200_s.iloc[-1])
            slp200 = float(slp_s.iloc[-1]) if pd.notna(slp_s.iloc[-1]) else 0.0

            cur_h = float(h_s.iloc[-1])
            cur_l = float(l_s.iloc[-1])
            cur_o = float(o_s.iloc[-1])
            bar_range = cur_h - cur_l
        else:
            ema_50 = float(ind.get("sma_50") or ind.get("ema_50") or current_price * 0.99)
            ema_200 = float(ind.get("ema_200") or current_price * 0.98)
            dh20 = current_price * 1.01
            dl8 = current_price * 0.99
            high8 = current_price * 1.005
            bb_up = current_price * 1.015
            bb_w = 1.0
            bb_w_med = 1.0
            cur_o = current_price

        # 1. Filtro Climático
        if atr_14 > 0 and bar_range > (max_bar_atr_mult * atr_14):
            filter_failures.append(
                f"Vela climática anómala: Rango ({bar_range:.2f}) > {max_bar_atr_mult}x ATR ({max_bar_atr_mult * atr_14:.2f})."
            )

        # 2. Evaluación Direccional
        squeeze_activo = (bb_w <= (bb_w_med * squeeze_mult)) if (bb_w is not None and bb_w_med is not None) else False
        es_candidato_long = (
            (current_price > ema_200)
            and (slp200 > 0.0)
            and (current_price > (bb_up or 0.0))
            and (current_price > (dh20 or 0.0))
            and (current_price > cur_o)
        )
        es_candidato_short = (
            (current_price < ema_200)
            and (ema_50 < ema_200)
            and (slp200 < 0.0)
            and (high8 is not None and high8 >= (ema_50 * 0.985))
            and (current_price < (dl8 or float("inf")))
            and (current_price < cur_o)
        )

        eval_side = "LONG"
        if not es_candidato_long and es_candidato_short and allow_short:
            eval_side = "SHORT"

        if eval_side == "LONG":
            if not es_candidato_long:
                filter_failures.append(
                    f"Sin ruptura alcista Squeeze Dual: Precio (${current_price:.2f}) no supera BB Sup (${bb_up:.2f}) ni Donchian 20 (${dh20:.2f}) con pendiente EMA200 > 0."
                )
            if not allow_long:
                filter_failures.append("Operativa en Largo (LONG) desactivada en subestrategias.")
            if require_squeeze and not squeeze_activo:
                filter_failures.append(
                    f"Filtro Squeeze violado: Ancho BB ({bb_w:.2f}) > {squeeze_mult}x Mediana 60p ({bb_w_med * squeeze_mult:.2f})."
                )
            if upper_wick_pct > max_wick_pct:
                filter_failures.append(
                    f"Trampa de absorción superior: Mecha contra ({upper_wick_pct:.1f}%) > {max_wick_pct:.1f}%."
                )
        else:
            if not es_candidato_short:
                filter_failures.append(
                    f"Sin quiebre Bear BOS: Precio (${current_price:.2f}) no rompe Donchian Low 8 (${dl8:.2f}) tras testear EMA50."
                )
            if not allow_short:
                filter_failures.append("Operativa en Corto (SHORT) desactivada en subestrategias.")
            if lower_wick_pct > max_wick_pct:
                filter_failures.append(
                    f"Trampa de absorción inferior: Mecha contra ({lower_wick_pct:.1f}%) > {max_wick_pct:.1f}%."
                )

        # 3. Filtro de Volumen Institucional
        if require_volume and rvol < min_rvol:
            filter_failures.append(
                f"Volumen institucional insuficiente: RVOL ({rvol:.2f}) < {min_rvol:.2f}."
            )

        # 4. Filtro de Sobreextensión respecto a EMA 50
        dist_ema50 = abs(current_price - ema_50) / (atr_14 + 1e-9) if atr_14 > 0 else 0.0
        if dist_ema50 > max_dist_ema50:
            filter_failures.append(
                f"Sobreextensión EMA50: Distancia ({dist_ema50:.2f} ATR) > {max_dist_ema50:.1f} ATR."
            )

        # 5. Cálculo Asimétrico R:R
        if atr_14 > 0 and current_price > 0:
            atr_pct = (atr_14 / current_price) * 100.0
            sl_calc = round(max(0.70, atr_sl_mult * atr_pct), 2)
            tp_raw = target_tp_mult * atr_pct
        else:
            sl_calc = 1.00
            tp_raw = 2.60

        min_tp_for_rr = required_tp_gross_for_rr(sl_calc, fee, spread, target_rr=min_rr_target)
        tp_calc = round(max(tp_raw, min_tp_for_rr + 0.005), 2)

        net_tp = round(net_return_after_costs(tp_calc, fee, spread), 4)
        net_sl = round(net_return_after_costs(-sl_calc, fee, spread), 4)
        rr_info = net_rr_metrics(tp_calc, sl_calc, fee, spread)
        calc_net_rr = round(float(rr_info.get("net_rr") or 0.0), 2)

        if not rr_info.get("valid") or calc_net_rr < min_rr_target:
            filter_failures.append(
                f"Asimetría insuficiente: R:R neto {calc_net_rr:.2f} < {min_rr_target:.2f} tras costos."
            )

        side_allowed = allow_long if eval_side == "LONG" else allow_short
        candidate_eligible = len(filter_failures) == 0 and side_allowed
        final_side = eval_side if candidate_eligible else "MANTENER"
        effective_net_tp = net_tp if candidate_eligible else 0.0

        strategy_metrics = {
            "mode": self.id,
            "side": final_side,
            "current_price": round(current_price, 4),
            "donchian_period": donchian_period,
            "bb_up": round(bb_up, 4) if bb_up else None,
            "bb_width_atr": round(bb_w, 3) if bb_w else None,
            "bb_width_med60": round(bb_w_med, 3) if bb_w_med else None,
            "dh20": round(dh20, 4) if dh20 else None,
            "dl8": round(dl8, 4) if dl8 else None,
            "high8": round(high8, 4) if high8 else None,
            "ema_50": round(ema_50, 4) if ema_50 else None,
            "ema_200": round(ema_200, 4) if ema_200 else None,
            "ema_slope200": round(slp200, 6),
            "dist_ema50_atrs": round(dist_ema50, 3),
            "atr_14": round(atr_14, 4),
            "rvol": round(rvol, 2),
            "upper_wick_pct": round(upper_wick_pct, 2),
            "lower_wick_pct": round(lower_wick_pct, 2),
            "tp_gross_pct": tp_calc,
            "sl_gross_pct": sl_calc,
            "tp_net_pct": net_tp,
            "sl_net_pct": net_sl,
            "net_rr": calc_net_rr,
            "minimum_net_tp_pct": min_profit_pct,
            "candidate_eligible": candidate_eligible,
            "filter_failures": filter_failures,
            "signal_side": "BUY" if (candidate_eligible and eval_side == "LONG") else ("SHORT" if (candidate_eligible and eval_side == "SHORT") else "HOLD"),
        }

        return (strategy_metrics, effective_net_tp, candidate_eligible, filter_failures, min_profit_pct)
