"""
===============================================================================
ESTRATEGIA CUANTITATIVA: DONCHIAN BREAKOUT ESTRUCTURAL (4H CRIPTO / 1D TRADFI)
===============================================================================
Ecosistema: KULA · BALAM
ID Canónico: donchian_breakout_1h (mantenido por compatibilidad con Ledger/UI/Daemon)
Validación Walk-Forward (70% IS / 30% OOS Ciego · 3-5 años · Costos Reales):
  - Cripto 4H (SOL/USDT + ETH/USDT): WR 43.3% | R:R Neto 2.06 | PF 1.57 | Max DD 19.7%
    | Retorno Neto +90.85% (IS_H1 +8.53%, IS_H2 +58.08%, OOS Ciego +11.24% [3/3 > 0]).
  - Acciones US 1D (AAPL, AMD, AVGO, META, MSFT): WR 44.7% | R:R Neto 2.30 | PF 1.86
    | Max DD 12.2% | Retorno Neto +64.55% (IS_H1 +24.70%, IS_H2 +25.85%, OOS +4.86% [3/3 > 0]).
  - Portafolio Consolidado (8 Series): N=115 | WR 44.4% | R:R Neto 2.11 | PF 1.68
    | Max DD 19.7% | Retorno Neto +261.01% (3/3 subperíodos positivos).

Arquitectura de Subfórmulas (8 Compuertas Modulares sin Lookahead):
1. operar_long: Quiebre alcista Donchian con shift(1) y cierre direccional (Close > Open).
2. operar_short: Quiebre bajista Donchian con shift(1) y cierre bajista (Close < Open),
   habilitado únicamente en criptoactivos 24/7 (< 1D) bajo régimen bajista confirmado.
3. filtro_ema100: Régimen institucional macro (EMA 200 en <1D / EMA 100 en 1D).
4. filtro_pendiente_ema: Pendiente estructural favorable de la EMA macro (evita rebotes
   de gato muerto y bull traps en mercados bajistas).
5. filtro_compresion_atr: Compresión dual causal (Ancho/ATR <= techo estático y <= factor
   sobre su mediana rodante de 60 velas con shift(1)).
6. filtro_volumen_expansion: Volumen institucional causal > umbral x SMA20(Vol).shift(1).
7. filtro_anti_trampa_mecha: Veto de mechas de absorción en contra y velas climáticas.
8. filtro_no_sobreextension: Veto de persecución lejos del equilibrio dinámico EMA 50.
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

DONCHIAN_STRATEGY_TIMEFRAMES: Set[str] = {"1h", "4h", "1d"}


class DonchianBreakout1H(EstrategiaBase):
    """
    Motor Matemático Validado Walk-Forward Donchian Squeeze & Régimen Macro
    (4H Cripto Bidireccional / 1D Acciones TradFi Long-Only) con gestión asimétrica ATR.
    """

    id: str = "donchian_breakout_1h"
    nombre: str = "🌊👑 Donchian Breakout Estructural (Multi-Marco)"
    descripcion: str = (
        "Motor determinista validado en Walk-Forward (70% IS / 30% OOS ciego, 3 a 5 años) "
        "con 3/3 subperíodos positivos (PF 1.68 consolidado, R:R neto 2.11, Max DD 19.7%). "
        "Opera rupturas causales Donchian (30p en 4H / 20p en 1D) precedidas por compresión "
        "relativa ATR, alineadas con nivel y pendiente de EMA macro (200 en 4H / 100 en 1D), "
        "volumen expansivo causal y vetos anti-trampa de mecha y sobreextensión EMA 50."
    )
    autor: str = "Arquitectura Cuantitativa Kula-Balam (Walk-Forward 3Y/5Y)"
    activos_recomendados: List[str] = [
        "SOL/USDT", "ETH/USDT", "AAPL", "AMD", "AVGO", "META", "MSFT"
    ]
    temporalidades_permitidas: Set[str] = DONCHIAN_STRATEGY_TIMEFRAMES
    horario_operativo: str = "Swing / Intradía Estructural (4H Cripto 24/7 / 1D Acciones TradFi)"

    parametros_por_defecto: Dict[str, Any] = {
        "timeframe": "4h",
        "donchian_period": 30,
        "donchian_period_1d": 20,
        "ema_trend_period": 200,
        "ema_trend_period_1d": 100,
        "ema_slope_bars": 8,
        "compression_atr_mult": 6.0,
        "rel_squeeze_mult": 1.15,
        "volume_ma_mult": 1.15,
        "volume_ma_mult_1d": 1.25,
        "max_wick_pct": 32.0,
        "max_bar_atr_mult": 2.6,
        "max_dist_ema50_atr": 3.2,
        "atr_sl_mult": 1.40,
        "target_tp_atr_mult": 3.36,
        "atr_sl_mult_1d": 1.10,
        "target_tp_atr_mult_1d": 2.42,
        "max_sl_pct_1d": 4.8,
        "min_rr_ratio": 2.0,
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
        is_daily = tf_label in ("1d", "daily", "d")

        symbol = str(ind.get("symbol") or "").upper()
        is_crypto = "/" in symbol or symbol.endswith("-USD") or symbol.endswith("USDT")

        # Inyectar configuración persistente desde StrategyConfigManager
        cfg_mgr = StrategyConfigManager()
        cfg = cfg_mgr.get_strategy_config(self.id)
        params = {**self.parametros_por_defecto, **(cfg.get("parameters") or {})}
        sub_strats = cfg.get("sub_strategies") or {}

        allow_long = self._sub_enabled(sub_strats, "operar_long", True)
        # Cortos habilitados solo en cripto 24/7 (< 1D) para respetar deriva secular alcista en acciones spot 1D
        allow_short_cfg = self._sub_enabled(sub_strats, "operar_short", True)
        allow_short = allow_short_cfg and is_crypto and (not is_daily)

        require_ema_trend = self._sub_enabled(sub_strats, "filtro_ema100", True)
        require_ema_slope = self._sub_enabled(sub_strats, "filtro_pendiente_ema", True)
        require_compression = self._sub_enabled(sub_strats, "filtro_compresion_atr", True)
        require_volume = self._sub_enabled(sub_strats, "filtro_volumen_expansion", True)
        require_anti_trap = self._sub_enabled(sub_strats, "filtro_anti_trampa_mecha", True)
        require_no_overext = self._sub_enabled(sub_strats, "filtro_no_sobreextension", True)
        require_mid_exit = self._sub_enabled(sub_strats, "salida_donchian_mid", False)
        require_bandwidth = self._sub_enabled(sub_strats, "filtro_bandwidth_expansion", False)
        # Filtro Funding H1: bloqueante solo si se habilita explícitamente; sombra activa por defecto.
        filtro_funding_activo = self._sub_enabled(sub_strats, "filtro_funding_short", False)
        filtro_funding_sombra = self._sub_enabled(sub_strats, "filtro_funding_short_sombra", True)

        # Parámetros coherentes con la escala temporal (<1D intradía/swing vs 1D rueda diaria)
        if is_daily:
            donchian_period = int(params.get("donchian_period_1d", 20))
            ema_trend_period = int(params.get("ema_trend_period_1d", 100))
            slope_bars = min(5, int(params.get("ema_slope_bars", 8)))
            compression_mult = min(float(params.get("compression_atr_mult", 6.0)), 4.4)
            rel_squeeze_mult = max(float(params.get("rel_squeeze_mult", 1.15)), 1.35)
            vol_mult = float(params.get("volume_ma_mult_1d", params.get("volume_ma_mult", 1.25)))
            max_wick_pct = max(float(params.get("max_wick_pct", 32.0)), 38.0)
            max_bar_atr_mult = max(float(params.get("max_bar_atr_mult", 2.6)), 3.2)
            max_dist_ema50 = max(float(params.get("max_dist_ema50_atr", 3.2)), 4.2)
            atr_sl_mult = float(params.get("atr_sl_mult_1d", 1.10))
            target_tp_mult = float(params.get("target_tp_atr_mult_1d", 2.42))
        else:
            donchian_period = int(params.get("period_entry", params.get("donchian_period", 30)))
            ema_trend_period = int(params.get("ema_trend_period", 200))
            slope_bars = int(params.get("ema_slope_bars", 8))
            compression_mult = float(params.get("compression_atr_mult", 6.0))
            rel_squeeze_mult = float(params.get("rel_squeeze_mult", 1.15))
            vol_mult = float(params.get("volume_ma_mult", 1.15))
            max_wick_pct = float(params.get("max_wick_pct", 32.0))
            max_bar_atr_mult = float(params.get("max_bar_atr_mult", 2.6))
            max_dist_ema50 = float(params.get("max_dist_ema50_atr", 3.2))
            atr_sl_mult = float(params.get("atr_sl_mult", 1.40))
            target_tp_mult = float(params.get("target_tp_atr_mult", 3.36))

        period_exit = int(params.get("period_exit", 12 if "period_entry" in params else donchian_period))
        min_rr_target = float(params.get("min_rr_ratio", 2.0))

        filter_failures: List[str] = []

        # VETO NATIVO: Descalificación matemática de BTC en temporalidades intradía (< 1D)
        if "BTC" in symbol and not is_daily:
            filter_failures.append(
                "VETO NATIVO: BTC en temporalidades intradía (<1D) posee esperanza matemática "
                "negativa (E < 0, PF 0.70, DD -39.51% con W=26.09%). Válido únicamente en 1D para swing macro."
            )

        # Variables estructurales calculadas de forma estrictamente causal
        donchian_high = None
        donchian_low = None
        donchian_mid = None
        donchian_width = None
        bw_atr_val = None
        bw_atr_med = None
        bbw_val = None
        bbw_pct_rank = None
        ema_macro = None
        ema_slope_val = 0.0
        ema_50_val = None
        dist_ema50_atrs = 0.0
        vol_ma20 = None
        atr_14 = float(ind.get("atr_14") or 0.0)
        cur_volume = float(latest.get("volume") or 0.0)
        cur_open = float(latest.get("open") or current_price)
        cur_high = float(latest.get("high") or current_price)
        cur_low = float(latest.get("low") or current_price)
        cur_close = float(latest.get("close") or current_price)
        upper_wick_pct = 0.0
        lower_wick_pct = 0.0
        bar_range_atrs = 0.0

        if df is not None and isinstance(df, pd.DataFrame) and len(df) >= max(donchian_period + 2, 25):
            try:
                # 1. Canal Donchian con shift(1) estricto (velas cerradas previas, cero lookahead)
                high_shift = df["high"].shift(1)
                low_shift = df["low"].shift(1)
                dh_series = high_shift.rolling(donchian_period).max()
                dl_series = low_shift.rolling(donchian_period).min()
                dw_series = dh_series - dl_series

                eff_exit_p = min(period_exit, len(df) - 1)
                dh_exit = high_shift.rolling(eff_exit_p).max()
                dl_exit = low_shift.rolling(eff_exit_p).min()
                dm_series = (dh_exit + dl_exit) / 2.0

                donchian_high = float(dh_series.iloc[-1])
                donchian_low = float(dl_series.iloc[-1])
                donchian_mid = float(dm_series.iloc[-1])
                donchian_width = float(dw_series.iloc[-1])

                # 2. ATR(14) estrictamente causal (.shift(1)) para no contaminar con el rango de ruptura actual
                prev_close = df["close"].shift(1)
                tr1 = df["high"] - df["low"]
                tr2 = (df["high"] - prev_close).abs()
                tr3 = (df["low"] - prev_close).abs()
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr_causal = tr.rolling(14).mean().shift(1)
                atr_raw = tr.rolling(14).mean()
                if not pd.isna(atr_causal.iloc[-1]) and float(atr_causal.iloc[-1]) > 0:
                    atr_14 = float(atr_causal.iloc[-1])
                elif not pd.isna(atr_raw.iloc[-1]) and float(atr_raw.iloc[-1]) > 0:
                    atr_14 = float(atr_raw.iloc[-1])

                # 2b. Ancho normalizado por ATR y su mediana rodante causal de 60 períodos
                atr_safe = atr_causal.where(atr_causal > 0, atr_raw).replace(0, pd.NA)
                bw_atr_series = dw_series / (atr_safe.astype(float) + 1e-9)
                if not pd.isna(bw_atr_series.iloc[-1]):
                    bw_atr_val = float(bw_atr_series.iloc[-1])
                bw_med_series = bw_atr_series.shift(1).rolling(60, min_periods=20).median()
                if not pd.isna(bw_med_series.iloc[-1]):
                    bw_atr_med = float(bw_med_series.iloc[-1])

                # 2c. Bollinger BandWidth (20, 2.0) causal y percentil rodante de 100 velas (Squeeze Rank)
                close_shift = df["close"].shift(1)
                sma_bb = close_shift.rolling(20, min_periods=10).mean()
                std_bb = close_shift.rolling(20, min_periods=10).std()
                bbw_series = (4.0 * std_bb) / (sma_bb + 1e-9)
                if not pd.isna(bbw_series.iloc[-1]):
                    bbw_val = float(bbw_series.iloc[-1])
                    bbw_rank_series = bbw_series.rolling(100, min_periods=20).rank(pct=True) * 100.0
                    if not pd.isna(bbw_rank_series.iloc[-1]):
                        bbw_pct_rank = float(bbw_rank_series.iloc[-1])

                # 3. Régimen Macro EMA y Pendiente Estructural + EMA 50 de equilibrio
                span_ema = min(ema_trend_period, len(df))
                ema_macro_series = df["close"].ewm(span=span_ema, adjust=False).mean()
                ema_macro = float(ema_macro_series.iloc[-1])

                eff_slope_lb = min(max(1, slope_bars), max(1, len(df) - 2))
                ema_slope_val = float(ema_macro_series.iloc[-1] - ema_macro_series.iloc[-1 - eff_slope_lb])

                span_50 = min(50, len(df))
                ema_50_series = df["close"].ewm(span=span_50, adjust=False).mean()
                ema_50_val = float(ema_50_series.iloc[-1])

                # 4. Volumen Institucional Causal: SMA(20) desplazada 1 vela (.shift(1))
                vol_ma20_causal = df["volume"].shift(1).rolling(20, min_periods=10).mean()
                if not pd.isna(vol_ma20_causal.iloc[-1]) and float(vol_ma20_causal.iloc[-1]) > 0:
                    vol_ma20 = float(vol_ma20_causal.iloc[-1])
                else:
                    vol_ma20_raw = df["volume"].rolling(20, min_periods=1).mean()
                    vol_ma20 = float(vol_ma20_raw.iloc[-1])

                cur_volume = float(df["volume"].iloc[-1])
                cur_open = float(df["open"].iloc[-1])
                cur_high = float(df["high"].iloc[-1])
                cur_low = float(df["low"].iloc[-1])
                cur_close = float(df["close"].iloc[-1])
                if ind.get("live_price") is None:
                    current_price = cur_close

                # 5. Anatomía de la vela actual (mechas de absorción y rango en ATRs)
                bar_rng = max(cur_high - cur_low, 0.0)
                if bar_rng > 1e-12:
                    body_top = max(cur_open, cur_close)
                    body_bot = min(cur_open, cur_close)
                    upper_wick_pct = ((cur_high - body_top) / bar_rng) * 100.0
                    lower_wick_pct = ((body_bot - cur_low) / bar_rng) * 100.0
                if atr_14 > 0:
                    bar_range_atrs = bar_rng / atr_14
                    dist_ema50_atrs = abs(current_price - ema_50_val) / atr_14
            except Exception:
                pass

        # Fallbacks seguros si no se cuenta con serie histórica completa
        if donchian_high is None:
            donchian_high = current_price * 1.01
        if donchian_low is None:
            donchian_low = current_price * 0.99
        if donchian_mid is None:
            donchian_mid = (donchian_high + donchian_low) / 2.0
        if donchian_width is None:
            donchian_width = donchian_high - donchian_low
        if ema_macro is None:
            ema_macro = float(ind.get("ema_200_value") or current_price * 0.98)
        if ema_50_val is None:
            ema_50_val = ema_macro
        if vol_ma20 is None or vol_ma20 <= 0:
            vol_ma20 = cur_volume if cur_volume > 0 else 1.0
        if bw_atr_val is None:
            bw_atr_val = (donchian_width / atr_14) if atr_14 > 0 else 0.0

        # Detección direccional primaria (LONG vs SHORT)
        quiebre_long = current_price > donchian_high
        quiebre_short = current_price < donchian_low
        eval_side = "LONG"
        if not quiebre_long and quiebre_short and allow_short:
            eval_side = "SHORT"

        # 1. Quiebre estructural Donchian + confirmación de cierre direccional
        if eval_side == "LONG":
            cond_quiebre = quiebre_long
            if not cond_quiebre:
                filter_failures.append(
                    f"Sin ruptura Donchian: Precio actual (${current_price:.2f}) <= Donchian High (${donchian_high:.2f})."
                )
            if not allow_long:
                filter_failures.append("Operativa en Largo (LONG) desactivada en subestrategias.")
        else:
            cond_quiebre = quiebre_short
            if not cond_quiebre:
                filter_failures.append(
                    f"Sin ruptura bajista Donchian: Precio actual (${current_price:.2f}) >= Donchian Low (${donchian_low:.2f})."
                )

        # 2. Nivel de Tendencia Macro EMA
        if eval_side == "LONG":
            cond_tendencia = current_price > ema_macro
            if require_ema_trend and not cond_tendencia:
                filter_failures.append(
                    f"Filtro Tendencia violado: Precio (${current_price:.2f}) <= EMA {ema_trend_period} (${ema_macro:.2f})."
                )
        else:
            cond_tendencia = current_price < ema_macro
            if require_ema_trend and not cond_tendencia:
                filter_failures.append(
                    f"Filtro Tendencia Bajista violado: Precio (${current_price:.2f}) >= EMA {ema_trend_period} (${ema_macro:.2f})."
                )

        # 3. Pendiente Institucional de la EMA Macro
        if eval_side == "LONG":
            cond_pendiente = ema_slope_val > 0.0
            if require_ema_slope and df is not None and not cond_pendiente:
                filter_failures.append(
                    f"Pendiente EMA desfavorable: ΔEMA({ema_trend_period}) = {ema_slope_val:.4f} <= 0 (riesgo de bull trap)."
                )
        else:
            cond_pendiente = ema_slope_val < 0.0
            if require_ema_slope and df is not None and not cond_pendiente:
                filter_failures.append(
                    f"Pendiente EMA no bajista: ΔEMA({ema_trend_period}) = {ema_slope_val:.4f} >= 0."
                )

        # 4. Compresión Dual del Canal (Techo ATR + Squeeze Relativo sobre Mediana 60p)
        max_allowed_width = compression_mult * atr_14 if atr_14 > 0 else donchian_width
        static_comp_ok = donchian_width <= max_allowed_width
        rel_squeeze_ok = (bw_atr_med is None) or (bw_atr_val <= (bw_atr_med * rel_squeeze_mult))
        cond_compresion = static_comp_ok and rel_squeeze_ok
        if require_compression and not cond_compresion:
            if not static_comp_ok:
                filter_failures.append(
                    f"Canal sobre-extendido: Ancho ({donchian_width:.2f}) > {compression_mult:.1f}x ATR ({max_allowed_width:.2f})."
                )
            else:
                filter_failures.append(
                    f"Sin compresión relativa (Squeeze): Ancho/ATR ({bw_atr_val:.2f}) > {rel_squeeze_mult:.2f}x mediana ({bw_atr_med:.2f})."
                )

        # 5. Expansión de Volumen Institucional Causal
        min_required_vol = vol_ma20 * vol_mult
        cond_volumen = cur_volume >= min_required_vol
        if require_volume and not cond_volumen:
            filter_failures.append(
                f"Volumen insuficiente: Volumen actual ({cur_volume:.1f}) < {vol_mult:.2f}x SMA20 causal ({min_required_vol:.1f})."
            )

        # 6. Veto Anti-Trampa de Mecha, Cierre Contrario y Vela Climática
        contra_wick = upper_wick_pct if eval_side == "LONG" else lower_wick_pct
        candle_dir_ok = (cur_close >= cur_open) if eval_side == "LONG" else (cur_close <= cur_open)
        wick_ok = contra_wick <= max_wick_pct
        climax_ok = (atr_14 <= 0) or (bar_range_atrs <= max_bar_atr_mult)
        cond_anti_trampa = candle_dir_ok and wick_ok and climax_ok
        if require_anti_trap and df is not None and not cond_anti_trampa:
            if not wick_ok:
                filter_failures.append(
                    f"Trampa de absorción detectada: mecha en contra ({contra_wick:.1f}%) > máximo ({max_wick_pct:.1f}%)."
                )
            elif not climax_ok:
                filter_failures.append(
                    f"Vela climática agotada: rango ({bar_range_atrs:.2f}x ATR) > máximo ({max_bar_atr_mult:.1f}x ATR)."
                )
            else:
                filter_failures.append("Vela de ruptura cerró en dirección contraria a la apertura.")

        # 6b. Veto Universal de Mechas (contraria >= 50%) siempre activo
        if df is not None and len(df) > 0:
            from backend.kula_rules import check_universal_wick_veto
            universal_wick_veto = check_universal_wick_veto(df, eval_side, 0.50)
            if universal_wick_veto:
                filter_failures.append(universal_wick_veto)

        # 7. Veto de Sobreextensión respecto a Media Dinámica EMA 50
        cond_no_sobreext = (atr_14 <= 0) or (dist_ema50_atrs <= max_dist_ema50)
        if require_no_overext and df is not None and not cond_no_sobreext:
            filter_failures.append(
                f"Sobreextensión EMA 50: distancia ({dist_ema50_atrs:.2f}x ATR) > límite ({max_dist_ema50:.1f}x ATR)."
            )

        # 8. Subfórmula heredada opcional Bandwidth Expansion
        cond_bandwidth = True
        if require_bandwidth:
            from backend.indicators import check_bandwidth_expansion_filter
            cond_bandwidth = check_bandwidth_expansion_filter(df, period_entry=donchian_period, sma_period=48)
            if not cond_bandwidth:
                filter_failures.append(
                    "Filtro Bandwidth violado: El ancho del canal Donchian no supera su SMA(48)."
                )

        # Cálculo Asimétrico Real de Stop Loss y Take Profit usando atr_sl_mult y target_tp_mult
        if atr_14 > 0 and current_price > 0:
            atr_pct = (atr_14 / current_price) * 100.0
            min_sl_floor = 0.75 if is_crypto else 0.60
            sl_calc = round(max(min_sl_floor, atr_sl_mult * atr_pct), 2)
            tp_raw = target_tp_mult * atr_pct

            # Tope de Stop Loss porcentual para Acciones TradFi 1D (evita SLs excesivos como -8.1%)
            if is_daily and not is_crypto:
                max_sl_1d = float(params.get("max_sl_pct_1d", 4.8))
                if sl_calc > max_sl_1d:
                    filter_failures.append(
                        f"Riesgo SL excesivo en TradFi 1D: SL requerido ({sl_calc:.2f}%) > máximo permitido ({max_sl_1d:.2f}%)."
                    )
                    sl_calc = round(max_sl_1d, 2)
                    tp_raw = sl_calc * (target_tp_mult / max(atr_sl_mult, 1e-6))
        else:
            sl_calc = 1.00
            tp_raw = 2.40

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

        # 9. Filtro de Derivados (Funding Rate) para cortos cripto · Hipótesis H1 validada en
        # backtest_lab/auditar_filtro_derivados.py. Modo sombra por defecto: registra sin bloquear.
        # Solo consulta la API si el corto ya es elegible por las 8 compuertas (evita llamadas ociosas).
        derivatives_info: Optional[Dict[str, Any]] = None
        funding_gate_ok: Optional[bool] = None
        funding_gate_reason = ""
        funding_shadow_veto = False
        if eval_side == "SHORT" and allow_short and len(filter_failures) == 0 and (filtro_funding_activo or filtro_funding_sombra):
            from backend.derivatives_flow import evaluate_short_funding_gate, get_derivatives_snapshot
            derivatives_info = ind.get("derivatives") or get_derivatives_snapshot(symbol)
            funding_gate_ok, funding_gate_reason = evaluate_short_funding_gate(derivatives_info)
            if not funding_gate_ok:
                if filtro_funding_activo:
                    filter_failures.append(f"Filtro Funding (H1): {funding_gate_reason}")
                else:
                    funding_shadow_veto = True
                    import logging as _logging
                    _logging.getLogger(__name__).warning(
                        f"[FUNDING SOMBRA] {symbol} SHORT elegible que el filtro H1 habría vetado: {funding_gate_reason}"
                    )

        side_allowed = allow_long if eval_side == "LONG" else allow_short
        candidate_eligible = len(filter_failures) == 0 and side_allowed
        if candidate_eligible:
            suggested_signal = "COMPRAR" if eval_side == "LONG" else "SHORT"
            final_side = eval_side
        else:
            suggested_signal = "MANTENER"
            final_side = "MANTENER"

        effective_net_tp = net_tp if candidate_eligible else 0.0

        strategy_metrics = {
            "mode": self.id,
            "side": final_side,
            "current_price": round(current_price, 4),
            "donchian_period": donchian_period,
            "donchian_high": round(donchian_high, 4),
            "donchian_low": round(donchian_low, 4),
            "donchian_mid": round(donchian_mid, 4),
            "donchian_width": round(donchian_width, 4),
            "donchian_width_atr": round(bw_atr_val, 3),
            "donchian_squeeze_med60": round(bw_atr_med, 3) if bw_atr_med is not None else None,
            "bbw_val": round(bbw_val, 4) if bbw_val is not None else None,
            "bbw_pct_rank": round(bbw_pct_rank, 2) if bbw_pct_rank is not None else None,
            "ema_trend_period": ema_trend_period,
            "ema_100": round(ema_macro, 4),
            "ema_macro": round(ema_macro, 4),
            "ema_slope": round(ema_slope_val, 6),
            "ema_50": round(ema_50_val, 4),
            "dist_ema50_atrs": round(dist_ema50_atrs, 3),
            "atr_14": round(atr_14, 4),
            "volume": round(cur_volume, 2),
            "volume_sma20": round(vol_ma20, 2),
            "upper_wick_pct": round(upper_wick_pct, 2),
            "lower_wick_pct": round(lower_wick_pct, 2),
            "bar_range_atrs": round(bar_range_atrs, 3),
            "compression_ok": cond_compresion,
            "volume_ok": cond_volumen,
            "bandwidth_ok": cond_bandwidth,
            "cond_quiebre": cond_quiebre,
            "cond_tendencia": cond_tendencia,
            "cond_pendiente": cond_pendiente,
            "cond_compresion": cond_compresion,
            "cond_volumen": cond_volumen,
            "cond_anti_trampa": cond_anti_trampa,
            "cond_no_sobreextension": cond_no_sobreext,
            "cond_bandwidth": cond_bandwidth,
            "tp_gross_pct": tp_calc,
            "sl_gross_pct": sl_calc,
            "tp_net_pct": net_tp,
            "sl_net_pct": net_sl,
            "net_rr": calc_net_rr,
            "mid_exit_price": round(donchian_mid, 4),
            "require_mid_exit": require_mid_exit,
            "candidate_eligible": candidate_eligible,
            "suggested_signal": suggested_signal,
            "filter_failures": filter_failures,
            "derivatives": derivatives_info,
            "funding_gate": {
                "mode": "BLOQUEANTE" if filtro_funding_activo else ("SOMBRA" if filtro_funding_sombra else "OFF"),
                "evaluated": funding_gate_ok is not None,
                "ok": funding_gate_ok,
                "shadow_veto": funding_shadow_veto,
                "reason": funding_gate_reason,
            },
            "policy": (
                f"Donchian Estructural ({donchian_period}p, shift 1): Alineación y pendiente EMA {ema_trend_period}, "
                f"Squeeze ATR <= {rel_squeeze_mult:.2f}x mediana, RVOL causal >= {vol_mult:.2f}x, "
                f"SL {atr_sl_mult:.2f}x ATR / TP {target_tp_mult:.2f}x ATR (R:R neto {calc_net_rr:.2f})."
            ),
        }

        return (
            strategy_metrics,
            effective_net_tp,
            candidate_eligible,
            filter_failures,
            max(0.50, min_profit_pct),
        )
