"""
Registro Central y Catálogo de Estrategias de Trading.
Permite descubrir, listar y evaluar estrategias dinámicamente.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from backend.estrategias.base import EstrategiaBase
from backend.estrategias.mean_reversion_atr import MeanReversionATR
from backend.estrategias.nasdaq_araujo_vwap import NasdaqAraujoVWAP
from backend.estrategias.hyenuk_chu_multibagger import HyenukChuMultibagger
from backend.estrategias.trailing_trend_runner import TrailingTrendRunner
from backend.estrategias.trailing_short_runner import TrailingShortRunner
from backend.estrategias.tendencia_institucional_01 import TendenciaInstitucional01
from backend.estrategias.cazador_rebotes_02 import CazadorRebotes02
from backend.estrategias.tres_velas_wyckoff_bulkowski import EstrategiaTresVelas
from backend.estrategias.kula_balam_cava_ruiz import KulaBalamCavaRuiz
from backend.estrategias.alex_ruiz_triada_3velas import AlexRuizTriada3Velas
from backend.estrategias.triple_confluencia_4h import TripleConfluencia4H
from backend.estrategias.donchian_breakout_1h import DonchianBreakout1H
from backend.estrategias.squeeze_dual_eth_4h import SqueezeDualETH4H
from backend.estrategias.scalping_cuantitativo_5m import (
    ScalpingVWAP2Sigma5M,
    ScalpingM5RSI3ADX5,
    SMCLiquidityScalper5M,
    TriadaFractalFibo5M,
    Donchian15MATRRunner,
)

# 1. Estrategias Titulares Oficiales (Activas en UI y Operativa)
OFFICIAL_STRATEGIES: Dict[str, EstrategiaBase] = {
    DonchianBreakout1H.id: DonchianBreakout1H(),
    SqueezeDualETH4H.id: SqueezeDualETH4H(),
    KulaBalamCavaRuiz.id: KulaBalamCavaRuiz(),
    EstrategiaTresVelas.id: EstrategiaTresVelas(),
}

# 2. Caja de Buenas Ideas & Laboratorio Cuantitativo (Estrategias Experimentales/Archivadas)
LABORATORY_STRATEGIES: Dict[str, EstrategiaBase] = {
    DonchianBreakout1H.id: DonchianBreakout1H(),
    TripleConfluencia4H.id: TripleConfluencia4H(),
    AlexRuizTriada3Velas.id: AlexRuizTriada3Velas(),
    NasdaqAraujoVWAP.id: NasdaqAraujoVWAP(),
    HyenukChuMultibagger.id: HyenukChuMultibagger(),
    TrailingTrendRunner.id: TrailingTrendRunner(),
    TrailingShortRunner.id: TrailingShortRunner(),
    MeanReversionATR.id: MeanReversionATR(),
    TendenciaInstitucional01.id: TendenciaInstitucional01(),
    CazadorRebotes02.id: CazadorRebotes02(),
}

# 3. Estrategias de Scalping Presencial (5M & 15M Validadas en Lab)
SCALPING_STRATEGIES: Dict[str, EstrategiaBase] = {
    ScalpingVWAP2Sigma5M.id: ScalpingVWAP2Sigma5M(),
    ScalpingM5RSI3ADX5.id: ScalpingM5RSI3ADX5(),
    SMCLiquidityScalper5M.id: SMCLiquidityScalper5M(),
    TriadaFractalFibo5M.id: TriadaFractalFibo5M(),
    Donchian15MATRRunner.id: Donchian15MATRRunner(),
}

# Diccionario maestro unificado para resolución interna sin regresiones
STRATEGY_REGISTRY: Dict[str, EstrategiaBase] = {
    **OFFICIAL_STRATEGIES,
    **LABORATORY_STRATEGIES,
    **SCALPING_STRATEGIES,
}


def _sync_catalog_registry() -> None:
    """Registra y refresca dinámicamente fórmulas promovidas en catalogo/principal/."""
    try:
        from backend.estrategias.catalog_adapter import discover_catalog_principal_strategies

        static_ids = set(OFFICIAL_STRATEGIES.keys()) | set(LABORATORY_STRATEGIES.keys()) | set(SCALPING_STRATEGIES.keys())
        extras = discover_catalog_principal_strategies(static_ids)
        if extras:
            STRATEGY_REGISTRY.update(extras)
    except Exception:
        pass


_sync_catalog_registry()


from datetime import datetime, timezone, timedelta

ARG_TIMEZONE = timezone(timedelta(hours=-3))


def _us_equity_session_open(now_dt: datetime) -> bool:
    """
    Sesión regular de Wall Street 09:30-16:00 hora de Nueva York evaluada con la zona horaria real
    (America/New_York). Antes se usaba 10:25-17:00 ARG fijo: abría 5 min antes de la campana y se
    desfasaba una hora cuando EE. UU. cambia de horario (1-nov-2026).
    """
    try:
        from zoneinfo import ZoneInfo

        ny = now_dt.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        total = now_dt.hour * 60 + now_dt.minute
        return 630 <= total < 1020
    if ny.weekday() >= 5:
        return False
    minutes = ny.hour * 60 + ny.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


def is_asset_market_open(symbol: str, now_dt: Optional[datetime] = None) -> bool:
    """
    Verifica determinísticamente si el mercado del activo está abierto en `now_dt` (ARG UTC-3):
    - Cripto (contiene '/'): Abierto 24/7 (True).
    - Sábado/Domingo: Acciones y ETFs cerrados (False); futuros '=F' abren domingo >= 19:00 ARG.
    - Lunes a Viernes:
      - BYMA ('.BA'): 11:00 a 17:00 ARG (660 a 1020 min).
      - Wall Street (QQQ, SPY, NVDA, etc.): 10:25 a 17:00 ARG (625 a 1020 min).
    """
    if not symbol:
        return True
    sym = str(symbol).strip().upper()
    if "/" in sym:
        return True

    if now_dt is None:
        now_dt = datetime.now(ARG_TIMEZONE)
    elif now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=ARG_TIMEZONE)
    else:
        now_dt = now_dt.astimezone(ARG_TIMEZONE)

    weekday = now_dt.weekday()  # 0=Lunes ... 5=Sábado, 6=Domingo
    total_minutes = now_dt.hour * 60 + now_dt.minute

    # 0. Mercado Forex (=X): opera 24/5 continuo desde Domingo 18:00 ARG hasta Viernes 18:00 ARG
    if "=X" in sym:
        if weekday == 5:  # Sábado cerrado
            return False
        if weekday == 6:  # Domingo abre a las 18:00 ARG (Apertura Sydney/Tokio)
            return total_minutes >= 18 * 60
        if weekday == 4:  # Viernes cierra a las 18:00 ARG (Cierre Nueva York)
            return total_minutes < 18 * 60
        return True

    # 0.1 Bolsas de Asia (^HSI, ^N225): Rueda nocturna Dom 21:00 a Vie 05:00 ARG
    if sym in ("^HSI", "^N225"):
        if weekday == 5:  # Sábado cerrado
            return False
        if weekday == 6:  # Domingo abre 21:00 ARG
            return total_minutes >= 21 * 60
        if weekday == 4:  # Viernes cierra 05:00 ARG
            return total_minutes < 5 * 60
        return total_minutes >= 21 * 60 or total_minutes < 5 * 60

    if weekday == 5:  # Sábado
        return False
    if weekday == 6:  # Domingo
        if "=F" in sym and total_minutes >= 19 * 60:
            return True
        return False

    if sym.endswith(".BA"):
        return 660 <= total_minutes < 1020
    if "=F" not in sym:
        return _us_equity_session_open(now_dt)
    if weekday == 4 and total_minutes >= 19 * 60:
        return False
    return not (18 * 60 <= total_minutes < 19 * 60)


def resolve_auto_strategy(
    symbol: str,
    ind: Dict[str, Any],
    now_dt: Optional[datetime] = None,
) -> Tuple[str, str]:
    """
    Orquestador Determinista en Python Puro:
    Determina la estrategia óptima en tiempo real según día de la semana, hora bursátil y régimen técnico:
    1. Z-Score <= -2.0 -> 'mean_reversion_atr' (Camino 2: Pánico Extremo / Capitulación).
    2. -1.2 <= Z-Score <= -0.4 -> 'mean_reversion_atr' (Camino 1: Pullback / Retroceso Saludable).
    3. Lunes a Viernes de 09:25 a 11:30 NY -> 'nasdaq_araujo_vwap' (Apertura Wall Street).
    4. Lunes a Viernes de 11:31 a 16:00 NY -> 'hyenuk_chu_multibagger' (Swing Trend & Peluqueo).
    5. Cripto 24/7 (Fines de semana y fuera de horario Wall Street):
       - Si el precio sostiene SMA50 y RSI >= 40 -> 'trailing_trend_runner' (Tendencia sin Techo).
       - Si el mercado corrige o consolida -> 'mean_reversion_atr' (Caza de Rebotes y Reversión).
    """
    if now_dt is None:
        now_dt = datetime.now(ARG_TIMEZONE)
    elif now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=ARG_TIMEZONE)
    else:
        now_dt = now_dt.astimezone(ARG_TIMEZONE)

    # Prioridad Cuantitativa 1: Oportunidades de Reversión y Pánico por Z-Score
    # (Exento para Forex =X: sin volumen centralizado, las divisas 24/5 siguen flujo tendencial/trailing)
    is_forex_sym = "=X" in symbol.upper()
    z_score = ind.get("z_score")
    if z_score is not None and not is_forex_sym:
        if z_score <= -2.0:
            return (
                "mean_reversion_atr",
                "Capitulación extrema detectada (Z-Score <= -2.0). Conmutando a Reversión Cuantitativa ATR (Camino 2: Pánico Extremo).",
            )
        if -1.2 <= z_score <= -0.4:
            return (
                "mean_reversion_atr",
                f"Retroceso saludable detectado (Z-Score: {z_score:.2f} en rango [-1.2, -0.4]). Conmutando a Reversión Cuantitativa ATR (Camino 1: Pullback en Tendencia).",
            )

    weekday = now_dt.weekday()  # 0=Lunes, 4=Viernes, 5=Sábado, 6=Domingo
    hour = now_dt.hour
    minute = now_dt.minute
    total_minutes = hour * 60 + minute

    # Extracción de métricas para conmutación simétrica Alcista (LONG) vs Bajista (SHORT)
    latest_raw = ind.get("latest")
    latest_obj = latest_raw if latest_raw is not None else {}
    px = float(latest_obj.get("close") or 0.0)
    ema_200 = float(ind.get("ema_200_value") or 0.0)
    sma_20 = float(latest_obj.get("sma_20") or 0.0)
    sma_50 = float(latest_obj.get("sma_50") or 0.0)
    ema_200_slope = ind.get("ema_200_slope_pct")
    rsi_val = 50.0
    if latest_obj is not None:
        try:
            rsi_val = float(latest_obj.get("rsi") or 50.0)
        except Exception:
            pass

    # Condición cuantitativa de régimen bajista estructural (no ruido intradía):
    # 1. Precio cotizando con holgura bajo la EMA200 institucional (>= 0.20% de distancia)
    # 2. Cascada bajista de medias: SMA20 no puede superar la EMA200 ni la SMA50
    # 3. Pendiente descendente de EMA200 institucional (no ascendente ni plana)
    # 4. Momentum activo en terreno vendedor [28.0, 50.0]
    is_bearish = (
        px > 0 and ema_200 > 0
        and px <= (ema_200 * 0.998)
        and (sma_20 == 0.0 or sma_20 <= ema_200)
        and (sma_50 == 0.0 or (sma_50 <= ema_200 * 1.005 and (sma_20 == 0.0 or sma_20 <= sma_50 * 1.005)))
        and (ema_200_slope is None or ema_200_slope <= -0.005)
        and 28.0 <= rsi_val <= 50.0
    )

    # 1. Cripto 24/7 y Forex 24/5: Operan SIEMPRE con Trailing Dinámico (LONG o SHORT) y Cazador de Rebotes ATR,
    #    sin quedar forzados ni bloqueados por estrategias exclusivas de índices bursátiles de Wall Street.
    if "/" in symbol or "=X" in symbol:
        mkt_label = "Forex 24/5" if "=X" in symbol else "Cripto 24/7"
        if weekday in (5, 6) and "=X" in symbol:
            return "manual", "Fin de semana: mercado Forex 24/5 cerrado."
        lower_wick = float(ind.get("lower_wick_ratio") or 0.0)
        if not is_forex_sym and ((lower_wick >= 0.35 and rsi_val <= 45.0) or (z_score is not None and z_score <= -1.0)):
            return (
                "02_cazador_rebotes_atr_15m",
                f"{mkt_label}: Rebote en soporte detectado (mecha absorción {lower_wick:.2f}, RSI {rsi_val:.1f}). Conmutando a Cazador de Rebotes ATR.",
            )
        if is_bearish:
            # En Forex (=X) el mercado es bidireccional puro por pares de divisas, o si Cripto tiene macro bajista confirmada
            if "=X" in symbol or ind.get("macro_bearish") is True:
                return (
                    "trailing_short_runner",
                    f"{mkt_label} en régimen bajista confirmado (${px:.2f} < EMA200 ${ema_200:.2f}, RSI {rsi_val:.1f}). Operando Trailing en Corto (Shorting Raúl).",
                )
            # En Cripto 24/7 ("/"): NO abrir shorts contratendenciales en retrocesos intradía ordinarios.
            # Se conmuta a 'mean_reversion_atr' para comprar el rebote en soporte con R:R >= 1:2
            return (
                "mean_reversion_atr",
                f"{mkt_label} en retroceso intradía (${px:.2f} < EMA200 ${ema_200:.2f}, RSI {rsi_val:.1f}). Conmutando a Reversión Cuantitativa ATR (Compra en Pullback sin shortear en mercado alcista).",
            )
        if weekday in (5, 6):
            return "trailing_trend_runner", "Fin de semana (Cripto 24/7 activa). Operando Trailing Dinámico: Tendencia sin Techo (Idea Raúl)."
        return "trailing_trend_runner", f"Fuera de horario bursátil de Wall Street ({mkt_label} activa). Operando Trailing Dinámico: Tendencia sin Techo (Idea Raúl)."

    sym_upper = str(symbol or "").strip().upper()

    # 2. Mercado local BYMA (.BA): Rueda fija 11:00 a 17:00 ART
    if sym_upper.endswith(".BA"):
        if weekday in (5, 6):
            return "manual", "Fin de semana: rueda BYMA cerrada."
        if 660 <= total_minutes < 1020:
            return "hyenuk_chu_multibagger", "Rueda regular BYMA activa (11:00 - 17:00 ART). Operando Swing Trend Following."
        return "manual", "Fuera de horario bursátil BYMA (17:00 - 11:00 ART)."

    # 3. Acciones/ETFs/Índices Wall Street y Futuros CME (=F): evaluados dinámicamente en America/New_York (DST-aware)
    try:
        from zoneinfo import ZoneInfo
        now_ny = now_dt.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        now_ny = now_dt - timedelta(hours=1)
    ny_weekday = now_ny.weekday()
    ny_minutes = now_ny.hour * 60 + now_ny.minute

    if "=F" in sym_upper:
        if not is_asset_market_open(sym_upper, now_dt):
            return "manual", "Futuros CME en pausa/mantenimiento o fin de semana."
        if is_bearish:
            return "trailing_short_runner", "Futuros en régimen bajista confirmado. Operando Trailing en Corto."
        if 9 * 60 + 25 <= ny_minutes <= 11 * 60 + 30 and ny_weekday < 5:
            return "nasdaq_araujo_vwap", "Ventana institucional Wall Street para futuros (09:25 - 11:30 NY). Evaluando VWAP en M15."
        return "trailing_trend_runner", "Sesión electrónica continua de futuros (=F) activa. Operando Trailing Dinámico."

    # Fin de semana para activos tradicionales (Acciones / ETFs / Índices): mercados cerrados
    if ny_weekday in (5, 6):
        return "manual", "Fin de semana: mercados bursátiles tradicionales cerrados."

    art_open_hm = now_ny.replace(hour=9, minute=30, second=0, microsecond=0).astimezone(ARG_TIMEZONE).strftime("%H:%M")
    art_close_hm = now_ny.replace(hour=16, minute=0, second=0, microsecond=0).astimezone(ARG_TIMEZONE).strftime("%H:%M")

    # Ventana de Apertura Wall Street (09:25 - 11:30 NY; 10:25-12:30 EDT / 11:25-13:30 EST en ART)
    if 9 * 60 + 25 <= ny_minutes <= 11 * 60 + 30:
        return (
            "nasdaq_araujo_vwap",
            f"Campana de apertura de Wall Street activa (09:25 - 11:30 NY | apertura {art_open_hm} ARG). Evaluando ruptura de Londres + VWAP en M15.",
        )

    # Sesión regular Wall Street abierta (11:31 - 16:00 NY) -> Trend Following y Swing 1h
    if 11 * 60 + 30 < ny_minutes < 16 * 60:
        return (
            "hyenuk_chu_multibagger",
            f"Jornada hábil regular Wall Street ({now_ny.strftime('%H:%M')} NY | cierre {art_close_hm} ARG). Operando Swing Trend Following con Peluqueo y Runner.",
        )

    # Días de semana fuera de horario bursátil de Wall Street
    return (
        "manual",
        f"Fuera de horario bursátil de Wall Street (sesión regular 09:30 - 16:00 NY / {art_open_hm} - {art_close_hm} ARG).",
    )


def get_strategy(strategy_id: str) -> Optional[EstrategiaBase]:
    """Obtiene la instancia de una estrategia por su identificador."""
    if strategy_id not in STRATEGY_REGISTRY:
        _sync_catalog_registry()
    return STRATEGY_REGISTRY.get(strategy_id)


def is_valid_strategy(strategy_id: str) -> bool:
    """Verifica si el id de estrategia es soportado por el motor (incluyendo 'manual' y 'auto')."""
    if strategy_id in ("manual", "auto"):
        return True
    if strategy_id not in STRATEGY_REGISTRY:
        _sync_catalog_registry()
    return strategy_id in STRATEGY_REGISTRY


def get_supported_strategy_ids() -> Set[str]:
    """Retorna el conjunto de IDs de estrategias válidas."""
    _sync_catalog_registry()
    return {"manual", "auto"} | set(STRATEGY_REGISTRY.keys())


def get_allowed_timeframes(strategy_id: str) -> Set[str]:
    """Retorna las temporalidades permitidas para una estrategia."""
    if strategy_id == "manual":
        return {"1m", "5m", "15m", "1h"}
    if strategy_id == "auto":
        return {"1m", "5m", "15m", "1h", "4h", "1d"}
    strat = get_strategy(strategy_id)
    if strat:
        return strat.temporalidades_permitidas
    return {"15m", "1h"}


def list_strategies(include_laboratory: bool = False) -> List[Dict[str, Any]]:
    """
    Lista las estrategias para consumo de la UI.
    Por defecto retorna únicamente las 4 opciones sólidas oficiales:
    1. 🐅 Kula Balam: Cava & Ruiz (Oficial 24/7 con Peluqueo y Trailing Libre)
    2. 🕯️ Tres Velas & Wyckoff VPA (Bulkowski Multitemporal)
    3. 🤖 Piloto Automático Inteligente (Auto)
    4. 🛠️ Manual / Discrecional
    """
    result = [
        OFFICIAL_STRATEGIES[KulaBalamCavaRuiz.id].to_dict(),
        OFFICIAL_STRATEGIES[EstrategiaTresVelas.id].to_dict(),
        {
            "id": "auto",
            "nombre": "🤖👑 Piloto Automático Inteligente (Por Horario y Régimen)",
            "descripcion": "Orquestador dinámico: conmuta autónomamente entre Kula Balam (24/7 Cripto) y Renta Variable bursátil según el reloj de mercado y el régimen macro.",
            "autor": "Orquestador Determinista Python",
            "activos_recomendados": ["Todos"],
            "temporalidades_permitidas": ["1m", "5m", "15m", "1h"],
            "horario_operativo": "24/7 (Conmutación dinámica)",
            "parametros_por_defecto": {},
        },
        {
            "id": "manual",
            "nombre": "🛠️ Manual / Discrecional",
            "descripcion": "Operativa manual o estándar basada en los niveles de TP/SL fijos seleccionados en el panel.",
            "autor": "Usuario / Operador",
            "activos_recomendados": ["Todos"],
            "temporalidades_permitidas": ["1m", "5m", "15m", "1h"],
            "horario_operativo": "24/7",
            "parametros_por_defecto": {},
        },
    ]
    if include_laboratory:
        for strat in LABORATORY_STRATEGIES.values():
            result.append(strat.to_dict())
    return result


def list_laboratory_strategies() -> List[Dict[str, Any]]:
    """Lista las estrategias archivadas en la Caja de Buenas Ideas (Laboratorio Cuantitativo)."""
    return [strat.to_dict() for strat in LABORATORY_STRATEGIES.values()]


def list_scalping_strategies() -> List[Dict[str, Any]]:
    """Lista las estrategias de scalping presencial validadas en Lab para consumo de la UI."""
    return [strat.to_dict() for strat in SCALPING_STRATEGIES.values()]


def evaluate_strategy(
    strategy_id: str,
    ind: Dict[str, Any],
    tp: float,
    sl: float,
    fee: float,
    spread: float,
    min_profit_pct: float,
    round_trip_cost: float,
    net_tp_manual: float,
    df: Optional[Any] = None,
    now_dt: Optional[datetime] = None,
    allowed_strategies: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], float, bool, List[str], float]:
    """
    Despacha la evaluación a la estrategia modular correspondiente.
    Si se especifican allowed_strategies, evalúa exclusivamente las estrategias autorizadas
    por el operador y selecciona la de mayor asimetría neta R:R.
    """
    if allowed_strategies is not None:
        if any(s not in STRATEGY_REGISTRY for s in allowed_strategies):
            _sync_catalog_registry()
        valid_allowed = [s for s in allowed_strategies if s in STRATEGY_REGISTRY]
        if len(valid_allowed) == 0:
            from backend.quant_risk import net_return_after_costs
            strategy_metrics = {
                "mode": "kula_cerebro",
                "allowed_strategies": [],
                "candidate_eligible": False,
                "filter_failures": ["El operador no autorizó ninguna fórmula táctica en el selector multi-check (0 tildadas)."],
                "tp_gross_pct": tp,
                "sl_gross_pct": sl,
                "tp_net_pct": 0.0,
                "sl_net_pct": round(net_return_after_costs(-sl, fee, spread), 4),
                "minimum_net_tp_pct": min_profit_pct,
            }
            return (strategy_metrics, 0.0, False, ["Sin fórmulas tácticas autorizadas por el operador en el selector"], min_profit_pct)

        # Evaluar ÚNICAMENTE las estrategias autorizadas por el operador
        from backend.quant_risk import detect_institutional_sweep_bonus
        sweep_bonus = detect_institutional_sweep_bonus(
            df=df,
            rvol=ind.get("relative_volume") or (ind.get("latest", {}).get("relative_volume") if hasattr(ind.get("latest", {}), "get") else 1.0),
            lower_wick_ratio=ind.get("lower_wick_ratio") or (ind.get("latest", {}).get("lower_wick_ratio") if hasattr(ind.get("latest", {}), "get") else 0.0),
            current_price=float(ind.get("live_price") or ind.get("price") or 0.0),
        )

        from backend.kula_rules import check_universal_wick_veto

        eligible_candidates = []
        first_eval = None
        kula_eval = None
        donchian_eval = None

        for s_id in valid_allowed:
            strat = get_strategy(s_id)
            if strat is None:
                continue
            m, eff_net, elig, fails, min_p = strat.evaluar(
                ind=ind,
                tp=tp,
                sl=sl,
                fee=fee,
                spread=spread,
                min_profit_pct=min_profit_pct,
                round_trip_cost=round_trip_cost,
                net_tp_manual=net_tp_manual,
                df=df,
            )

            # Veto Universal de Mechas (contraria >= 50%) para todo candidato
            eval_side = m.get("side") or ("LONG" if eff_net > 0 else "SHORT")
            if df is not None and len(df) > 0:
                wick_veto_msg = check_universal_wick_veto(df, eval_side, 0.50)
                if wick_veto_msg:
                    if wick_veto_msg not in fails:
                        fails.append(wick_veto_msg)
                    elig = False
                    m["candidate_eligible"] = False
                    m["suggested_signal"] = "MANTENER"
                    m["side"] = "MANTENER"

            m["institutional_sweep"] = sweep_bonus
            m["is_institutional_sweep"] = sweep_bonus["sweep_detected"]
            m["conviction_multiplier"] = sweep_bonus["conviction_multiplier"]

            eval_tuple = (s_id, m, eff_net, elig, fails, min_p)
            if s_id == "kula_balam_cava_ruiz":
                kula_eval = eval_tuple
            elif s_id == "donchian_breakout_1h":
                donchian_eval = eval_tuple

            if first_eval is None:
                first_eval = eval_tuple
            cand_rr = float(m.get("net_rr") or 0.0)
            if elig and cand_rr >= 1.95:
                eligible_candidates.append(eval_tuple)

        if eligible_candidates:
            # Seleccionar la fórmula que ofrece máxima asimetría neta R:R (priorizando barrido institucional si existe)
            best_id, m, eff_net, elig, fails, min_p = max(
                eligible_candidates,
                key=lambda x: (
                    x[1].get("is_institutional_sweep", False),
                    float(x[1].get("net_rr") or 0.0),
                    x[2],
                ),
            )
            best_rr = float(m.get("net_rr") or 0.0)
            sweep_msg = " + 🦈 Convicción 2X por Barrido Institucional" if m.get("is_institutional_sweep") else ""
            m["auto_orchestrator"] = {
                "selected_strategy": best_id,
                "reason": f"Cerebro Kula seleccionó '{best_id}' entre las {len(valid_allowed)} autorizadas por ofrecer máxima asimetría neta (R:R {best_rr:.2f}, TP neto +{eff_net:.2f}%){sweep_msg}."
            }
            return (m, eff_net, elig, fails, min_p)

        # Si ninguna fue elegible, retornar la primera autorizada indicando que ninguna cumplió
        if first_eval:
            # Conmutador Regla 4: Si kula_balam_cava_ruiz reportó COMPRESSION (ATR <= SMA), conmuta first_eval a Donchian 4H
            is_kula_compressed = False
            if kula_eval:
                k_m = kula_eval[1]
                v_reg = k_m.get("volatility_regime") or (k_m.get("kula_trigger", {}).get("volatility_regime"))
                if v_reg == "COMPRESSION":
                    is_kula_compressed = True

            commuted_to_donchian = False
            if is_kula_compressed and donchian_eval:
                first_eval = donchian_eval
                commuted_to_donchian = True

            s_id, m, eff_net, _, fails, min_p = first_eval
            fails_copy = list(fails)
            fails_copy.append(f"Ninguna de las {len(valid_allowed)} fórmulas autorizadas ({', '.join(valid_allowed)}) encontró confluencia en este régimen.")
            auto_reason = (
                "[Conmutador Regla 4: ATR <= SMA -> Modo Compresión Donchian 4H]"
                if commuted_to_donchian
                else f"Evaluadas {len(valid_allowed)} fórmulas autorizadas; ninguna cumplió confluencia simultánea."
            )
            m["auto_orchestrator"] = {
                "selected_strategy": s_id,
                "reason": auto_reason,
            }
            return (m, eff_net, False, fails_copy, min_p)

    auto_info = None
    target_strategy_id = strategy_id
    if strategy_id == "auto":
        symbol = str(ind.get("symbol") or (ind.get("latest", {}).get("symbol") if hasattr(ind.get("latest", {}), "get") else "") or "BTC/USDT")
        target_strategy_id, auto_reason = resolve_auto_strategy(symbol, ind, now_dt=now_dt)
        auto_info = {"selected_strategy": target_strategy_id, "reason": auto_reason}

    strat = get_strategy(target_strategy_id)
    if strat is not None:
        from backend.quant_risk import detect_institutional_sweep_bonus
        sweep_bonus = detect_institutional_sweep_bonus(
            df=df,
            rvol=ind.get("relative_volume") or (ind.get("latest", {}).get("relative_volume") if hasattr(ind.get("latest", {}), "get") else 1.0),
            lower_wick_ratio=ind.get("lower_wick_ratio") or (ind.get("latest", {}).get("lower_wick_ratio") if hasattr(ind.get("latest", {}), "get") else 0.0),
            current_price=float(ind.get("live_price") or ind.get("price") or 0.0),
        )
        metrics, eff_net_tp, eligible, failures, min_tp = strat.evaluar(
            ind=ind,
            tp=tp,
            sl=sl,
            fee=fee,
            spread=spread,
            min_profit_pct=min_profit_pct,
            round_trip_cost=round_trip_cost,
            net_tp_manual=net_tp_manual,
            df=df,
        )
        metrics["institutional_sweep"] = sweep_bonus
        metrics["is_institutional_sweep"] = sweep_bonus["sweep_detected"]
        metrics["conviction_multiplier"] = sweep_bonus["conviction_multiplier"]
        if auto_info:
            metrics["auto_orchestrator"] = auto_info
        return (metrics, eff_net_tp, eligible, failures, min_tp)

    # Fallback para 'manual'
    from backend.quant_risk import net_return_after_costs

    strategy_metrics = {
        "mode": "manual",
        "z_score": round(ind["z_score"], 4) if ind.get("z_score") is not None else None,
        "z_score_threshold": -2.0,
        "ema_200": round(ind["ema_200_value"], 6) if ind.get("ema_200_value") is not None else None,
        "ema_200_slope_pct": round(ind["ema_200_slope_pct"], 6) if ind.get("ema_200_slope_pct") is not None else None,
        "atr_14": round(ind["atr_14"], 8) if ind.get("atr_14") is not None else None,
        "relative_volume": round(ind["relative_volume"], 4) if ind.get("relative_volume") is not None else None,
        "lower_wick_ratio": round(ind["lower_wick_ratio"], 4) if ind.get("lower_wick_ratio") is not None else None,
        "tp_gross_pct": tp,
        "sl_gross_pct": sl,
        "tp_net_pct": net_tp_manual,
        "sl_net_pct": round(net_return_after_costs(-sl, fee, spread), 4),
        "minimum_net_tp_pct": min_profit_pct,
        "candidate_eligible": None,
        "filter_failures": [],
    }
    if auto_info:
        strategy_metrics["auto_orchestrator"] = auto_info
    return (strategy_metrics, net_tp_manual, False, [], min_profit_pct)
