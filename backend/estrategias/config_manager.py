"""
===============================================================================
GESTOR DE CONFIGURACIÓN DINÁMICA DE ESTRATEGIAS Y SUBESTRATEGIAS
===============================================================================
Ecosistema: KULA · BALAM
Permite la inspección, conmutación en caliente (Feature Toggling por checkboxes),
calibración de parámetros y archivado (soft-delete) sin reiniciar el servidor
ni modificar código fuente.
===============================================================================
"""

import json
import os
import threading
from typing import Any, Dict, List, Optional

CONFIG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "strategies_config.json",
)

_lock = threading.RLock()

DEFAULT_STRATEGY_CONFIGS: Dict[str, Dict[str, Any]] = {
    "kula_balam_cava_ruiz": {
        "id": "kula_balam_cava_ruiz",
        "nombre": "🐅👑 Kula Balam: Cava & Ruiz (Tríada 1D-1H-5M & Fallo MACD)",
        "active": True,
        "sub_strategies": {
            "operar_long": {
                "name": "Operar en Largo (LONG)",
                "description": "Permite compras tácticas en retrocesos hacia la Zona Dorada de Fibonacci.",
                "enabled": True,
            },
            "operar_short": {
                "name": "Operar en Corto (SHORT)",
                "description": "Permite ventas tácticas en rebotes correctivos bajo EMA 50.",
                "enabled": True,
            },
            "fibo_golden_zone": {
                "name": "Filtro Zona Dorada Fibonacci (0.50 - 0.75)",
                "description": "Exige que el retroceso/rebote se sitúe estrictamente entre 0.50 y 0.75.",
                "enabled": True,
            },
            "fallo_macd": {
                "name": "Gatillo de Fallo de MACD",
                "description": "Exige agotamiento de momentum e inflexión favorable en histograma MACD.",
                "enabled": True,
            },
            "secado_volumen": {
                "name": "Secado de Volumen (RVOL < 0.85)",
                "description": "Verifica falta de presión institucional contraria en la corrección.",
                "enabled": True,
            },
            "filtro_ema50": {
                "name": "Cierre sobre/bajo EMA 50",
                "description": "Exige que la vela de confirmación cierre del lado correcto de la EMA 50.",
                "enabled": True,
            },
            "peluqueo_tp1": {
                "name": "Peluqueo 50% en TP1 + Breakeven",
                "description": "Cierra el 50% de la posición en R:R >= 2.0 y ancla Stop a riesgo cero.",
                "enabled": True,
            },
        },
        "parameters": {
            "min_rr_ratio": 2.0,
            "fibo_golden_zone_min": 0.50,
            "fibo_golden_zone_max": 0.75,
            "peluqueo_partial_pct": 50.0,
            "atr_multiplier_sl": 1.5,
        },
    },
    "tres_velas_wyckoff_bulkowski": {
        "id": "tres_velas_wyckoff_bulkowski",
        "nombre": "🕯️👑 Tres Velas & Wyckoff VPA (Bulkowski Multitemporal)",
        "active": True,
        "sub_strategies": {
            "pattern_three_white_soldiers": {
                "name": "Three White Soldiers (82% Éxito)",
                "description": "Tres velas alcistas consecutivas con máximos crecientes y volumen ascendente.",
                "enabled": True,
            },
            "pattern_morning_star": {
                "name": "Morning Star / Estrella de la Mañana (78% Éxito)",
                "description": "Patrón de giro en 3 velas con doji de absorción en soporte.",
                "enabled": True,
            },
            "pattern_bullish_engulfing": {
                "name": "Bullish Engulfing / Vela Envolvente (68% Éxito)",
                "description": "Vela verde amplia que envuelve completamente el rango de la vela roja previa.",
                "enabled": True,
            },
            "pattern_hammer_support": {
                "name": "Martillo en Soporte con Absorción",
                "description": "Vela martillo con mecha inferior >= 60% testeando soporte clave.",
                "enabled": True,
            },
            "wyckoff_vpa_volume": {
                "name": "Volumen Institucional Wyckoff (RVOL >= 1.3)",
                "description": "Exige volumen relativo anormal confirmando presencia institucional.",
                "enabled": True,
            },
            "vwap_confluence": {
                "name": "Confluencia con VWAP Diario",
                "description": "Exige que el patrón opere con el precio sosteniendo el VWAP intradía.",
                "enabled": True,
            },
            "veto_bull_trap": {
                "name": "🛡️ Veto Bull Trap (Mecha superior excesiva)",
                "description": "Veta compras si la vela de confirmación deja mecha superior >= 25% (Upthrust institucional).",
                "enabled": True,
            },
            "veto_bear_trap": {
                "name": "🛡️ Veto Bear Trap (Mecha inferior excesiva)",
                "description": "Veta ventas si la vela deja mecha inferior >= 25% (Spring o absorción compradora).",
                "enabled": True,
            },
        },
        "parameters": {
            "min_rvol": 1.30,
            "min_rr_ratio": 2.0,
            "atr_multiplier_sl": 1.5,
            "bull_trap_wick_max": 0.25,
            "bear_trap_wick_max": 0.25,
            "max_bullish_rsi": 72.0,
            "min_bearish_rsi": 28.0,
        },
    },
    "alex_ruiz_triada_3velas": {
        "id": "alex_ruiz_triada_3velas",
        "nombre": "📐👑 Alex Ruiz: La Tríada de las 3 Velas (LONG & SHORT)",
        "active": True,
        "sub_strategies": {
            "operar_long": {
                "name": "Operar en Largo (LONG)",
                "description": "Habilita compras con régimen alcista sobre EMA 50 diaria y quiebre de 3 velas.",
                "enabled": True,
            },
            "operar_short": {
                "name": "Operar en Corto (SHORT Blindado)",
                "description": "Habilita ventas en corto bajo EMA 50 con compuertas de seguridad.",
                "enabled": True,
            },
            "veto_bear_trap": {
                "name": "Veto Bear Trap (Mecha inferior >= 40%)",
                "description": "Anula inmediatamente la orden de venta si la vela muestra absorción compradora.",
                "enabled": True,
            },
            "veto_rsi_oversold": {
                "name": "Veto Clímax de Sobreventa (RSI <= 30)",
                "description": "Prohíbe terminantemente vender en corto en el suelo (prevención de short squeeze).",
                "enabled": True,
            },
            "veto_bull_trap": {
                "name": "Veto Bull Trap (Mecha superior >= 40%)",
                "description": "Anula inmediatamente compras si la vela es rechazada por vendedores en máximos.",
                "enabled": True,
            },
            "veto_cohete_alcista": {
                "name": "Veto Cohete Alcista (Sin mecha superior)",
                "description": "Impide abrir cortos contra velas verdes verticales sin agotamiento previo.",
                "enabled": True,
            },
            "gatillo_3velas": {
                "name": "Gatillo Táctico de 3 Velas en 5M",
                "description": "Exige quiebre estricto del extremo de la Vela 2 al cierre de la Vela 3.",
                "enabled": True,
            },
            "peluqueo_tp1": {
                "name": "Peluqueo 50% en TP1 + Runner en TP2",
                "description": "Toma de ganancias al 50% con R:R >= 2.0 y trailing stop para el remanente.",
                "enabled": True,
            },
        },
        "parameters": {
            "min_rr_ratio": 2.0,
            "bear_trap_wick_max": 0.40,
            "bull_trap_wick_max": 0.40,
            "rsi_oversold_short_veto": 30.0,
            "rsi_overbought_long_veto": 70.0,
            "factor_atr_stop": 0.20,
            "ticks_seguridad": 2,
        },
    },
    "nasdaq_araujo_vwap": {
        "id": "nasdaq_araujo_vwap",
        "nombre": "🏛️👑 Nasdaq Araujo: Francotirador VWAP Wall Street (LONG & SHORT)",
        "active": True,
        "sub_strategies": {
            "operar_long": {
                "name": "Operar en Largo (LONG sobre VWAP)",
                "description": "Permite compras tácticas en retrocesos hacia el VWAP diario con mecha de rechazo.",
                "enabled": True,
            },
            "operar_short": {
                "name": "Operar en Corto (SHORT bajo VWAP)",
                "description": "Permite ventas tácticas en rebotes contra el VWAP diario con mecha de rechazo.",
                "enabled": True,
            },
            "filtro_horario_wall_street": {
                "name": "Candado Horario Wall Street (09:35 - 11:00 NY)",
                "description": "Limita la operativa a la ventana de máxima liquidez institucional de la campana.",
                "enabled": True,
            },
            "salto_primeros_5min": {
                "name": "Salto Anti-Caos Primeros 5 Minutos (09:30 - 09:35 NY)",
                "description": "Veta operaciones durante la subasta de apertura inicial mientras se estabiliza el VWAP.",
                "enabled": True,
            },
            "filtro_rechazo_vwap": {
                "name": "Rechazo Obligatorio con Mecha (>= 30%)",
                "description": "Exige mecha de absorción contra la línea del VWAP para confirmar presencia compradora/vendedora.",
                "enabled": True,
            },
            "filtro_rvol_institucional": {
                "name": "Volumen Institucional en VWAP (RVOL >= 1.2)",
                "description": "Exige confirmación de volumen anormal en la defensa del benchmark.",
                "enabled": True,
            },
            "veto_bear_trap": {
                "name": "Veto Bear Trap (Mecha inferior >= 40%)",
                "description": "Anula ventas cortas si la vela muestra absorción institucional en mínimos.",
                "enabled": True,
            },
            "veto_rsi_oversold": {
                "name": "Veto Clímax de Sobreventa (RSI <= 30)",
                "description": "Prohíbe terminantemente abrir cortos en sobreventa extrema (anti-squeeze).",
                "enabled": True,
            },
            "peluqueo_tp1": {
                "name": "Peluqueo 50% en TP1 + Runner en TP2",
                "description": "Toma de ganancias parcial con R:R >= 2.0 y anclaje de Stop Loss a Breakeven ($0 riesgo).",
                "enabled": True,
            },
        },
        "parameters": {
            "min_rr_ratio": 2.0,
            "min_rvol": 1.20,
            "min_rejection_wick": 0.30,
            "bear_trap_wick_max": 0.40,
            "rsi_oversold_short_veto": 30.0,
            "factor_atr_stop": 0.15,
            "ticks_seguridad": 2,
            "tick_size": 0.01,
        },
    },
    "hyenuk_chu_multibagger": {
        "id": "hyenuk_chu_multibagger",
        "nombre": "🐘👑 Hyenuk Chu: Swing Multibagger",
        "active": True,
        "sub_strategies": {
            "operar_long": {
                "name": "Operar en Largo (Swing 1H)",
                "description": "Permite compras tácticas en tendencias sobre EMA200 alcista y SMA20.",
                "enabled": True,
            },
            "filtro_vela_elefante": {
                "name": "Gatillo de Vela Elefante (Rango >= 1.0x ATR)",
                "description": "Exige vela verde sólida de ignición con mecha superior pequeña.",
                "enabled": True,
            },
            "filtro_rvol_institucional": {
                "name": "Volumen Institucional Participante (RVOL >= 1.10)",
                "description": "Verifica participación de grandes fondos en el despegue.",
                "enabled": True,
            },
            "filtro_anti_euforia_rsi": {
                "name": "Filtro Contrario Anti-Euforia (RSI <= 75)",
                "description": "Prohíbe terminantemente comprar en techos de euforia masiva.",
                "enabled": True,
            },
            "stop_estructural_50pct": {
                "name": "Stop Estructural al 50% de la Vela Elefante",
                "description": "Ubica el Stop en el equilibrio de la subasta con margen de 2 ticks.",
                "enabled": True,
            },
            "peluqueo_tp1": {
                "name": "Peluqueo 50% en TP1 (+3.5%) + Free-Roll",
                "description": "Asegura ganancias en el primer hito y deja correr el resto a riesgo cero.",
                "enabled": True,
            },
        },
        "parameters": {
            "min_rr_ratio": 2.0,
            "first_tp_trim_pct": 3.50,
            "sl_fallback_pct": 1.75,
            "min_rvol": 1.10,
            "max_rsi_euphoria": 75.0,
            "min_rsi": 45.0,
            "elephant_atr_multiplier": 1.0,
            "max_upper_wick": 0.25,
            "factor_atr_stop": 0.15,
            "ticks_seguridad": 2,
            "tick_size": 0.01,
        },
    },
    "trailing_trend_runner": {
        "id": "trailing_trend_runner",
        "nombre": "🏃👑 Trailing Dinámico: Tendencia sin Techo",
        "active": True,
        "sub_strategies": {
            "operar_long": {
                "name": "Operar en Largo (LONG)",
                "description": "Permite compras tácticas en microtendencias alcistas sobre SMA20 y SMA50/EMA200.",
                "enabled": True,
            },
            "veto_macro_btc": {
                "name": "🛡️ Veto Macro Bitcoin (Blindaje anti-caídas)",
                "description": "Bloquea compras en altcoins si Bitcoin cotiza bajo EMA200 1H o VWAP diario.",
                "enabled": True,
            },
            "candado_costo_real": {
                "name": "🔒 Candado de Piso de Costo Real (+0.40% bruto)",
                "description": "Arma Breakeven asegurando 100% de comisiones cubiertas más ganancia neta garantizada.",
                "enabled": True,
            },
            "cerrojo_scalping": {
                "name": "🔐 Cerrojo de Scalping (+1.00% -> +0.80% piso)",
                "description": "Blinda un piso innegociable de +0.80% bruto (+0.50% neto) al superar +1.00%.",
                "enabled": True,
            },
            "trailing_sin_techo": {
                "name": "📈 Trailing Stop sin Techo",
                "description": "Acompaña el precio máximo protegiendo ganancias sin cortar subidas exponenciales.",
                "enabled": True,
            },
        },
        "parameters": {
            "min_rr_ratio": 2.0,
            "sl_pct": 0.80,
            "be_trigger_pct": 0.40,
            "be_lock_net_pct": 0.15,
            "scalp_trigger_pct": 1.00,
            "scalp_floor_gross_pct": 0.80,
            "trailing_dist_pct": 1.20,
            "min_rvol": 0.80,
            "min_rsi": 40.0,
            "max_rsi": 72.0,
        },
    },
    "triple_confluencia_4h": {
        "id": "triple_confluencia_4h",
        "nombre": "🔱👑 Triple Confluencia Swing 4H (EMA 21/89 + RSI + Expansión ATR)",
        "active": True,
        "sub_strategies": {
            "operar_long": {
                "name": "Operar en Largo (LONG sobre EMA 21/89)",
                "description": "Permite compras tendenciales con EMA 21 > EMA 89 y precio sosteniendo la media rápida.",
                "enabled": True,
            },
            "operar_short": {
                "name": "Operar en Corto (SHORT bajo EMA 21/89)",
                "description": "Permite ventas cortas en tendencias bajistas con EMA 21 < EMA 89 y precio bajo la media rápida.",
                "enabled": True,
            },
            "filtro_expansion_atr": {
                "name": "Filtro de Expansión ATR (ATR14 > SMA20_ATR)",
                "description": "Garantiza que la volatilidad se está expandiendo y veta entradas en rangos laterales muertos.",
                "enabled": True,
            },
            "veto_macro_btc": {
                "name": "Veto Macro Bitcoin (Blindaje en altcoins)",
                "description": "Bloquea compras en altcoins si Bitcoin cotiza bajo EMA200 1H o VWAP diario.",
                "enabled": True,
            },
            "peluqueo_tp1": {
                "name": "Peluqueo 50% en TP1 (3.0x ATR) + Breakeven",
                "description": "Toma el 50% de beneficio al alcanzar R:R >= 2.0 y traslada Stop a riesgo cero.",
                "enabled": True,
            },
        },
        "parameters": {
            "min_rr_ratio": 2.0,
            "atr_sl_mult": 1.5,
            "atr_tp_mult": 3.0,
            "min_rvol": 0.85,
            "peluqueo_partial_pct": 50.0,
            "rsi_long_min": 50.0,
            "rsi_short_max": 50.0,
            "ema_fast_period": 21,
            "ema_slow_period": 89,
        },
    },
    "donchian_breakout_1h": {
        "id": "donchian_breakout_1h",
        "nombre": "🌊👑 Donchian Breakout Estructural (Multi-Marco)",
        "active": True,
        "sub_strategies": {
            "operar_long": {
                "name": "Operar en Largo (Quiebre Donchian High)",
                "description": "Abre compra en cierre > máximo Donchian causal (shift 1) en 4H Cripto y 1D Acciones.",
                "enabled": True,
            },
            "operar_short": {
                "name": "Operar en Corto Cripto 24/7 (Quiebre Donchian Low)",
                "description": "Abre corto en cierre < mínimo Donchian causal (shift 1) solo en cripto (<1D) bajo régimen bajista.",
                "enabled": True,
            },
            "filtro_ema100": {
                "name": "Filtro Régimen Institucional (EMA 200 en 4H / EMA 100 en 1D)",
                "description": "Exige precio alineado con la media exponencial macro del marco operativo.",
                "enabled": True,
            },
            "filtro_pendiente_ema": {
                "name": "Filtro Pendiente Estructural EMA (Anti-Bull/Bear Trap)",
                "description": "Exige que la pendiente de la EMA macro acompañe la dirección del quiebre para filtrar rebotes falsos.",
                "enabled": True,
            },
            "filtro_compresion_atr": {
                "name": "Filtro Compresión Dual (Squeeze Relativo 60p + Techo ATR)",
                "description": "Exige canal comprimido respecto a su mediana de 60 velas y dentro del techo máximo en ATRs.",
                "enabled": True,
            },
            "filtro_volumen_expansion": {
                "name": "Expansión de Volumen Causal (> Umbral x SMA20 shift 1)",
                "description": "Exige participación institucional superando la media de volumen de las 20 velas cerradas previas.",
                "enabled": True,
            },
            "filtro_anti_trampa_mecha": {
                "name": "Veto Mecha de Absorción y Vela Climática",
                "description": "Bloquea rupturas con mecha en contra excesiva, cierre contrario a apertura o vela agotada.",
                "enabled": True,
            },
            "filtro_no_sobreextension": {
                "name": "Veto Sobreextensión Media Dinámica (EMA 50)",
                "description": "Impide perseguir rupturas alejadas en exceso del equilibrio dinámico EMA 50 medido en ATRs.",
                "enabled": True,
            },
            "salida_donchian_mid": {
                "name": "Salida Dinámica por Mitad de Canal (MID_EXIT - Opcional)",
                "description": "Desactivada por defecto para respetar el desarrollo completo hasta Stop Loss o Take Profit ATR.",
                "enabled": False,
            },
        },
        "parameters": {
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
            "min_rr_ratio": 2.0,
            "lot_size": 0.10,
        },
    },
    "squeeze_dual_eth_4h": {
        "id": "squeeze_dual_eth_4h",
        "nombre": "⚡👑 Squeeze Dual BB/Donchian 4H (ETH/USDT · Walk-Forward PF 1.66)",
        "active": True,
        "sub_strategies": {
            "operar_long": {"name": "Operar Largo en Expansión Bollinger Superior", "enabled": True},
            "operar_short": {"name": "Operar Corto en Quiebre BOS Bajista", "enabled": True},
            "filtro_squeeze": {"name": "Compresión Ancho Bollinger <= 1.2x Mediana", "enabled": True},
            "filtro_volumen": {"name": "Expansión Volumen Institucional RVOL >= 1.10", "enabled": True},
        },
        "parameters": {
            "donchian_period": 30,
            "ema_macro_period": 200,
            "squeeze_mult": 1.20,
            "atr_sl_mult": 1.70,
            "target_tp_atr_mult": 4.42,
            "min_rr_ratio": 2.60,
            "lot_size": 0.01,
        },
    },
    "scalping_vwap_2sigma_5m": {
        "id": "scalping_vwap_2sigma_5m",
        "nombre": "🧲📦 Reversión VWAP ±1.5σ (Cuarentena Scalping)",
        "active": False,
        "sub_strategies": {
            "filtro_mecha_absorcion": {"name": "Mecha de Absorción >= 15%", "enabled": True},
            "filtro_dist_ema50": {"name": "Filtro Anti-Sobreextensión EMA50", "enabled": True},
        },
        "parameters": {
            "vwap_window": 36,
            "sigma_mult": 1.5,
            "min_wick_pct": 15.0,
            "sl_pct": 0.70,
            "tp_pct": 5.50,
            "min_rr_ratio": 2.0,
            "lot_size": 0.01,
        },
    },
    "smc_liquidity_scalper_m5": {
        "id": "smc_liquidity_scalper_m5",
        "nombre": "🎯📦 SMC Liquidity Sweep & BOS (Cuarentena Scalping)",
        "active": False,
        "sub_strategies": {
            "filtro_barrido": {"name": "Confirmación de Barrido de Liquidez", "enabled": True},
            "filtro_bos": {"name": "Quiebre de Estructura (BOS)", "enabled": True},
        },
        "parameters": {
            "lookback_sweep": 20,
            "min_rr_ratio": 2.0,
            "lot_size": 0.01,
        },
    },
    "donchian_15m_atr_runner": {
        "id": "donchian_15m_atr_runner",
        "nombre": "🌊📦 Ruptura Donchian 15M + ATR (Cuarentena Scalping)",
        "active": False,
        "sub_strategies": {
            "filtro_atr_expansion": {"name": "Filtro Expansión Volatilidad ATR", "enabled": True},
        },
        "parameters": {
            "donchian_period": 20,
            "min_rr_ratio": 2.0,
            "lot_size": 0.01,
        },
    },
    "triada_fractal_fibo_ema50_5m": {
        "id": "triada_fractal_fibo_ema50_5m",
        "nombre": "📐📦 Tríada Fractal Fibo + EMA50 (Cuarentena Scalping)",
        "active": False,
        "sub_strategies": {
            "zona_dorada_fibo": {"name": "Zona Dorada Fibonacci 0.50-0.75", "enabled": True},
            "equilibrio_ema50": {"name": "Equilibrio Dinámico EMA 50", "enabled": True},
        },
        "parameters": {
            "fibo_min": 0.50,
            "fibo_max": 0.75,
            "min_rr_ratio": 2.0,
            "lot_size": 0.01,
        },
    },
    "scalping_m5_rsi3_adx5_ema50": {
        "id": "scalping_m5_rsi3_adx5_ema50",
        "nombre": "⚡📦 RSI(3) + ADX(5) + EMA50 (Cuarentena Scalping)",
        "active": False,
        "sub_strategies": {
            "filtro_rsi3": {"name": "Oscilador Extremo RSI(3)", "enabled": True},
            "filtro_adx5": {"name": "Fuerza Tendencial ADX(5)", "enabled": True},
        },
        "parameters": {
            "rsi_oversold": 20.0,
            "rsi_overbought": 80.0,
            "min_adx": 20.0,
            "min_rr_ratio": 2.0,
            "lot_size": 0.01,
        },
    },
}


class StrategyConfigManager:
    """Administrador central persistente de subestrategias y parámetros."""

    @classmethod
    def _load_raw(cls) -> Dict[str, Dict[str, Any]]:
        with _lock:
            if not os.path.exists(CONFIG_FILE_PATH):
                cls._save_raw(DEFAULT_STRATEGY_CONFIGS)
                return json.loads(json.dumps(DEFAULT_STRATEGY_CONFIGS))
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Fusionar con los valores por defecto por si se agregan nuevas estrategias o sub-flags
                merged = json.loads(json.dumps(DEFAULT_STRATEGY_CONFIGS))
                for s_id, s_conf in data.items():
                    if s_id in merged:
                        if "active" in s_conf:
                            merged[s_id]["active"] = bool(s_conf["active"])
                        if "sub_strategies" in s_conf:
                            for sub_id, sub_data in s_conf["sub_strategies"].items():
                                if sub_id in merged[s_id]["sub_strategies"]:
                                    if isinstance(sub_data, dict) and "enabled" in sub_data:
                                        merged[s_id]["sub_strategies"][sub_id]["enabled"] = bool(sub_data["enabled"])
                                    elif isinstance(sub_data, bool):
                                        merged[s_id]["sub_strategies"][sub_id]["enabled"] = sub_data
                        if "parameters" in s_conf:
                            for p_key, p_val in s_conf["parameters"].items():
                                if p_key in merged[s_id]["parameters"]:
                                    merged[s_id]["parameters"][p_key] = p_val
                    else:
                        merged[s_id] = s_conf
                return merged
            except Exception:
                return json.loads(json.dumps(DEFAULT_STRATEGY_CONFIGS))

    @classmethod
    def _save_raw(cls, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def get_all_configs(cls) -> Dict[str, Dict[str, Any]]:
        """Retorna la configuración completa de todas las estrategias."""
        return cls._load_raw()

    @classmethod
    def get_strategy_config(cls, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Retorna la configuración de una estrategia puntual."""
        configs = cls._load_raw()
        return configs.get(strategy_id)

    @classmethod
    def is_sub_enabled(cls, strategy_id: str, sub_id: str, default: bool = True) -> bool:
        """Verifica en tiempo real si una subestrategia (checkbox) está tildada."""
        conf = cls.get_strategy_config(strategy_id)
        if not conf:
            return default
        sub = conf.get("sub_strategies", {}).get(sub_id)
        if isinstance(sub, dict):
            return bool(sub.get("enabled", default))
        if isinstance(sub, bool):
            return sub
        return default

    @classmethod
    def is_strategy_active(cls, strategy_id: str, default: bool = True) -> bool:
        """Verifica si la estrategia general está activa (no archivada)."""
        conf = cls.get_strategy_config(strategy_id)
        if not conf:
            return default
        return bool(conf.get("active", default))

    @classmethod
    def toggle_sub_strategy(cls, strategy_id: str, sub_id: str, enabled: bool) -> bool:
        """Conmuta el checkbox de una subestrategia específica."""
        with _lock:
            data = cls._load_raw()
            if strategy_id not in data:
                return False
            if sub_id not in data[strategy_id].get("sub_strategies", {}):
                return False
            data[strategy_id]["sub_strategies"][sub_id]["enabled"] = bool(enabled)
            cls._save_raw(data)
            return True

    @classmethod
    def update_parameters(cls, strategy_id: str, params: Dict[str, Any]) -> bool:
        """Actualiza parámetros cuantitativos numéricos de una estrategia."""
        with _lock:
            data = cls._load_raw()
            if strategy_id not in data:
                return False
            curr_params = data[strategy_id].setdefault("parameters", {})
            for k, v in params.items():
                if k in curr_params:
                    try:
                        curr_params[k] = float(v) if isinstance(curr_params[k], (int, float)) else v
                    except Exception:
                        pass
            cls._save_raw(data)
            return True

    @classmethod
    def toggle_strategy_active(cls, strategy_id: str, active: bool) -> bool:
        """Habilita o archiva (soft-delete) una estrategia completa."""
        with _lock:
            data = cls._load_raw()
            if strategy_id not in data:
                return False
            data[strategy_id]["active"] = bool(active)
            cls._save_raw(data)
            return True

    @classmethod
    def get_parameter(cls, strategy_id: str, param_name: str, fallback: Any = None) -> Any:
        """Obtiene el valor actual de un parámetro numérico."""
        conf = cls.get_strategy_config(strategy_id)
        if not conf:
            return fallback
        return conf.get("parameters", {}).get(param_name, fallback)

    @classmethod
    def reset_strategy_to_default(cls, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Restablece los parámetros y subestrategias a los valores originales de fábrica."""
        with _lock:
            if strategy_id not in DEFAULT_STRATEGY_CONFIGS:
                return None
            data = cls._load_raw()
            default_copy = json.loads(json.dumps(DEFAULT_STRATEGY_CONFIGS[strategy_id]))
            data[strategy_id] = default_copy
            cls._save_raw(data)
            return default_copy
