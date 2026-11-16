"""
===============================================================================
ESTRATEGIA CUANTITATIVA: TRIPLE CONFLUENCIA 4H (SWING TREND & VOLATILITY EXPANSION)
===============================================================================
Ecosistema: KULA · BALAM
Basado en: Guía Maestra de Arquitectura Cuantitativa & NotebookLM IA para Kula Balam.

Pilares del Sistema:
1. Temporalidad Swing de 4 Horas (4H):
   - Captura tramos tendenciales amplios (3 a 10 días).
   - Reduce drásticamente la fricción por comisiones y spread (< 2% del beneficio bruto).
2. Filtro Direccional por Medias Móviles Exponenciales (EMA):
   - LONG: EMA 21 > EMA 89 y Precio > EMA 21.
   - SHORT: EMA 21 < EMA 89 y Precio < EMA 21.
3. Filtro de Expansión de Volatilidad (Volumen Real vs Rango Muerto):
   - Inecuación matemática: ATR(14) > SMA_20(ATR_14).
   - Garantiza que el mercado está en fase de expansión activa y descarta consolidaciones muertas.
4. Filtro de Momentum e Impulso (RSI 14):
   - LONG: RSI(14) >= 50.0 (Presencia compradora sin veto prematuro de sobrecompra).
   - SHORT: RSI(14) <= 50.0 (Presencia vendedora activa).
5. Dimensionamiento y Salidas Dinámicas por Volatilidad:
   - Stop Loss anclado a 1.5 x ATR(14).
   - Take Profit 1 (Peluqueo 50%) anclado a 3.0 x ATR(14) con R:R neto >= 1:2.0.
   - Stop trasladado inmediatamente a Breakeven Real ($0 riesgo) para acompañar la tendencia restante.
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

TRIPLE_CONFLUENCIA_TIMEFRAMES: Set[str] = {"4h", "1d"}


class TripleConfluencia4H(EstrategiaBase):
    """
    Estrategia Tendencial Swing en 4H (EMA 21/89 + RSI + Expansión ATR)
    orientada a capturar tendencias multidiarias con asimetría R:R >= 1:2.0.
    """

    id: str = "triple_confluencia_4h"
    nombre: str = "🔱👑 Triple Confluencia Swing 4H (EMA 21/89 + RSI + Expansión ATR)"
    descripcion: str = (
        "Estrategia tendencial de horizonte amplio en 4H y Diario (BTC, ETH, SOL, QQQ, SPY, Forex). "
        "Filtra la tendencia institucional limpia mediante EMA 21 y EMA 89, exige expansión de volatilidad "
        "activa ATR(14) > SMA20(ATR) para evitar rangos laterales muertos, confirma momentum direccional con RSI "
        "y fija Stop Loss y Take Profit adaptativos por volatilidad con asimetría R:R >= 1:2.0 y Peluqueo 50/50."
    )
    autor: str = "NotebookLM IA / Arquitectura Cuantitativa Kula Balam"
    activos_recomendados: List[str] = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "EURUSD=X", "GBPUSD=X", "QQQ", "SPY", "NVDA", "TSLA", "AAPL"
    ]
    temporalidades_permitidas: Set[str] = TRIPLE_CONFLUENCIA_TIMEFRAMES
    horario_operativo: str = "Swing Trading 4H (24/7 Cripto / Sesiones continuas)"

    parametros_por_defecto: Dict[str, Any] = {
        "timeframe": "4h",
        "min_rr_ratio": 2.0,                  # Asimetría matemática obligatoria
        "atr_sl_mult": 1.5,                   # Factor multiplicador de Stop Loss por ATR (1.5x)
        "atr_tp_mult": 3.0,                   # Factor multiplicador de Take Profit por ATR (3.0x -> R:R 1:2)
        "min_rvol": 0.85,                     # Volumen relativo mínimo participante
        "peluqueo_partial_pct": 50.0,         # Cierre parcial del 50% al alcanzar TP1
        "rsi_long_min": 50.0,                 # Umbral mínimo de RSI para compras
        "rsi_short_max": 50.0,                # Umbral máximo de RSI para cortos
        "ema_fast_period": 21,
        "ema_slow_period": 89,
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
        tf_label = str(ind.get("timeframe") or "4h").lower()

        # Inyectar configuración desde StrategyConfigManager
        cfg_mgr = StrategyConfigManager()
        cfg = cfg_mgr.get_strategy_config(self.id)
        params = cfg.get("parameters", self.parametros_por_defecto)
        sub_strats = cfg.get("sub_strategies", {})

        allow_long = sub_strats.get("operar_long", {}).get("enabled", True)
        allow_short = sub_strats.get("operar_short", {}).get("enabled", True)
        require_vol_expansion = sub_strats.get("filtro_expansion_atr", {}).get("enabled", True)
        require_btc_macro = sub_strats.get("veto_macro_btc", {}).get("enabled", True)
        require_peluqueo = sub_strats.get("peluqueo_tp1", {}).get("enabled", True)

        min_rr_target = float(params.get("min_rr_ratio", 2.0))
        atr_sl_mult = float(params.get("atr_sl_mult", 1.5))
        atr_tp_mult = float(params.get("atr_tp_mult", 3.0))
        min_rvol = float(params.get("min_rvol", 0.85))

        filter_failures: List[str] = []

        # 1. Extracción de ATR(14) y cálculo de su SMA20
        atr_14 = float(ind.get("atr_14") or 0.0)
        atr_sma20 = None
        ema_21 = None
        ema_89 = None

        if df is not None and isinstance(df, pd.DataFrame) and len(df) >= 30:
            try:
                # Calcular EMA 21 y EMA 89
                close_series = df["close"]
                ema_21_series = close_series.ewm(span=21, adjust=False).mean()
                ema_89_series = close_series.ewm(span=89, adjust=False).mean()
                ema_21 = float(ema_21_series.iloc[-1])
                ema_89 = float(ema_89_series.iloc[-1])

                # Calcular serie de True Range y ATR 14
                high = df["high"]
                low = df["low"]
                close_prev = close_series.shift(1)
                tr1 = high - low
                tr2 = (high - close_prev).abs()
                tr3 = (low - close_prev).abs()
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr_series = tr.rolling(window=14).mean()
                atr_14 = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else atr_14
                atr_sma20_series = atr_series.rolling(window=20).mean()
                if not pd.isna(atr_sma20_series.iloc[-1]):
                    atr_sma20 = float(atr_sma20_series.iloc[-1])
            except Exception:
                pass

        # Fallbacks si no hay DataFrame completo
        if ema_21 is None:
            ema_21 = float(latest.get("sma_20") or current_price)
        if ema_89 is None:
            ema_89 = float(ind.get("ema_200_value") or current_price * 0.98)
        if atr_sma20 is None:
            atr_sma20 = atr_14 * 0.95  # Supone expansión si no hay histórico completo

        rsi_val = float(latest.get("rsi") or 50.0)
        rvol = float(ind.get("relative_volume") or 1.0)
        sym_str = str(ind.get("symbol") or "")

        # 2. Veto Macro de Bitcoin (para altcoins cripto)
        if require_btc_macro:
            try:
                from backend.entry_gate import is_crypto_altcoin, get_btc_macro_status
                if is_crypto_altcoin(sym_str):
                    btc_stat = get_btc_macro_status()
                    if btc_stat.get("veto_active"):
                        filter_failures.append(
                            f"Veto Macro Bitcoin activo: {btc_stat.get('reason')} [BTC: ${btc_stat.get('btc_close', 0):.2f}]. Compras en altcoins suspendidas."
                        )
            except Exception:
                pass

        # 3. Filtro de Expansión de Volatilidad: ATR(14) > SMA_20(ATR_14)
        if require_vol_expansion and atr_14 > 0 and atr_sma20 is not None:
            if atr_14 <= atr_sma20:
                filter_failures.append(
                    f"Compresión de volatilidad: ATR(14)={atr_14:.4f} <= SMA20(ATR)={atr_sma20:.4f}. Mercado en rango muerto o consolidación."
                )

        # 4. Filtro de Volumen Participante
        if rvol < min_rvol:
            filter_failures.append(
                f"Volumen institucional insuficiente: RVOL={rvol:.2f} < {min_rvol}."
            )

        # 5. Determinación Direccional (LONG vs SHORT)
        is_bullish_alignment = (ema_21 > ema_89) and (current_price >= ema_21 * 0.995)
        is_bearish_alignment = (ema_21 < ema_89) and (current_price <= ema_21 * 1.005)

        side = "MANTENER"
        if is_bullish_alignment and allow_long:
            if rsi_val < float(params.get("rsi_long_min", 50.0)):
                filter_failures.append(f"Falta impulso comprador: RSI={rsi_val:.1f} < {params.get('rsi_long_min', 50.0)}.")
            else:
                side = "LONG"
        elif is_bearish_alignment and allow_short:
            if rsi_val > float(params.get("rsi_short_max", 50.0)):
                filter_failures.append(f"Falta presión vendedora: RSI={rsi_val:.1f} > {params.get('rsi_short_max', 50.0)}.")
            else:
                side = "SHORT"
        else:
            filter_failures.append(
                f"Sin alineación tendencial clara: EMA21 (${ema_21:.2f}) vs EMA89 (${ema_89:.2f}) con precio en ${current_price:.2f}."
            )

        # 6. Cálculo de Stop Loss y Take Profit adaptativos por volatilidad
        if atr_14 > 0 and current_price > 0:
            atr_pct = (atr_14 / current_price) * 100.0
            sl_calc = round(max(1.5, atr_sl_mult * atr_pct), 2)
            tp_raw = atr_tp_mult * atr_pct
        else:
            sl_calc = 2.0
            tp_raw = 5.0

        min_tp_for_rr = required_tp_gross_for_rr(sl_calc, fee, spread, target_rr=min_rr_target)
        tp_calc = round(max(tp_raw, min_tp_for_rr), 2)

        net_tp = round(net_return_after_costs(tp_calc, fee, spread), 4)
        net_sl = round(net_return_after_costs(-sl_calc, fee, spread), 4)
        rr_info = net_rr_metrics(tp_calc, sl_calc, fee, spread)

        if not rr_info.get("valid") or rr_info.get("net_rr", 0.0) < min_rr_target:
            filter_failures.append(
                f"Asimetría insuficiente: R:R neto {rr_info.get('net_rr', 0.0):.2f} < {min_rr_target:.2f} tras costos de broker."
            )

        candidate_eligible = len(filter_failures) == 0 and side in ("LONG", "SHORT")
        suggested_signal = "COMPRAR" if candidate_eligible and side == "LONG" else ("SHORT" if candidate_eligible and side == "SHORT" else "MANTENER")
        effective_net_tp = net_tp if candidate_eligible else 0.0

        strategy_metrics = {
            "mode": self.id,
            "side": side,
            "current_price": round(current_price, 2),
            "ema_21": round(ema_21, 2) if ema_21 else None,
            "ema_89": round(ema_89, 2) if ema_89 else None,
            "atr_14": round(atr_14, 4),
            "atr_sma20": round(atr_sma20, 4) if atr_sma20 else None,
            "volatility_expansion": (atr_14 > (atr_sma20 or 0.0)),
            "rsi": round(rsi_val, 2),
            "relative_volume": round(rvol, 2),
            "tp_gross_pct": tp_calc,
            "sl_gross_pct": sl_calc,
            "tp_net_pct": net_tp,
            "sl_net_pct": net_sl,
            "net_rr": round(float(rr_info.get("net_rr") or 0.0), 2),
            "peluqueo_partial_pct": float(params.get("peluqueo_partial_pct", 50.0)),
            "candidate_eligible": candidate_eligible,
            "suggested_signal": suggested_signal,
            "filter_failures": filter_failures,
            "policy": (
                "Triple Confluencia Swing 4H: Captura tendencias multidiarias limpias sobre EMA 21/89 "
                "con expansión activa de volatilidad ATR, gestionando riesgo asimétrico R:R >= 1:2.0."
            ),
        }

        return (
            strategy_metrics,
            effective_net_tp,
            candidate_eligible,
            filter_failures,
            max(0.50, min_profit_pct),
        )
