"""
Módulo de Estrategias Cuantitativas y Modulares para Trading Ollama.
"""

from backend.estrategias.base import EstrategiaBase
from backend.estrategias.registry import (
    STRATEGY_REGISTRY,
    get_strategy,
    list_strategies,
    is_valid_strategy,
    get_supported_strategy_ids,
    get_allowed_timeframes,
    evaluate_strategy,
)
from backend.estrategias.mean_reversion_atr import (
    MeanReversionATR,
    ATR_STRATEGY_TIMEFRAMES,
    ATR_Z_SCORE_THRESHOLD,
    ATR_LOWER_WICK_RATIO_MIN,
    ATR_RELATIVE_VOLUME_MAX,
    ATR_TP_ATR_MULTIPLIER,
    ATR_SL_ATR_MULTIPLIER,
    ATR_COST_COVERAGE_MULTIPLIER,
    ATR_MIN_NET_TP_PCT,
)
from backend.estrategias.nasdaq_araujo_vwap import (
    NasdaqAraujoVWAP,
    ARAUJO_STRATEGY_TIMEFRAMES,
)
from backend.estrategias.hyenuk_chu_multibagger import (
    HyenukChuMultibagger,
    CHU_STRATEGY_TIMEFRAMES,
)
from backend.estrategias.trailing_trend_runner import (
    TrailingTrendRunner,
    TRAILING_RUNNER_TIMEFRAMES,
)
from backend.estrategias.trailing_short_runner import (
    TrailingShortRunner,
    TRAILING_SHORT_RUNNER_TIMEFRAMES,
)
from backend.estrategias.tres_velas_wyckoff_bulkowski import (
    EstrategiaTresVelas,
    TRES_VELAS_TIMEFRAMES,
)
from backend.estrategias.kula_balam_cava_ruiz import (
    KulaBalamCavaRuiz,
    KULA_BALAM_TIMEFRAMES,
)
from backend.estrategias.alex_ruiz_triada_3velas import (
    AlexRuizTriada3Velas,
    ALEX_RUIZ_TIMEFRAMES,
)
from backend.estrategias.triple_confluencia_4h import (
    TripleConfluencia4H,
    TRIPLE_CONFLUENCIA_TIMEFRAMES,
)
from backend.estrategias.donchian_breakout_1h import (
    DonchianBreakout1H,
    DONCHIAN_STRATEGY_TIMEFRAMES,
)

__all__ = [
    "EstrategiaBase",
    "STRATEGY_REGISTRY",
    "get_strategy",
    "list_strategies",
    "is_valid_strategy",
    "get_supported_strategy_ids",
    "get_allowed_timeframes",
    "evaluate_strategy",
    "KulaBalamCavaRuiz",
    "AlexRuizTriada3Velas",
    "TripleConfluencia4H",
    "DonchianBreakout1H",
    "DONCHIAN_STRATEGY_TIMEFRAMES",
    "TRIPLE_CONFLUENCIA_TIMEFRAMES",
    "KULA_BALAM_TIMEFRAMES",
    "MeanReversionATR",
    "ATR_STRATEGY_TIMEFRAMES",
    "ATR_Z_SCORE_THRESHOLD",
    "ATR_LOWER_WICK_RATIO_MIN",
    "ATR_RELATIVE_VOLUME_MAX",
    "ATR_TP_ATR_MULTIPLIER",
    "ATR_SL_ATR_MULTIPLIER",
    "ATR_COST_COVERAGE_MULTIPLIER",
    "ATR_MIN_NET_TP_PCT",
    "NasdaqAraujoVWAP",
    "ARAUJO_STRATEGY_TIMEFRAMES",
    "HyenukChuMultibagger",
    "CHU_STRATEGY_TIMEFRAMES",
    "TrailingTrendRunner",
    "TrailingShortRunner",
    "TRAILING_RUNNER_TIMEFRAMES",
    "TRAILING_SHORT_RUNNER_TIMEFRAMES",
    "EstrategiaTresVelas",
    "TRES_VELAS_TIMEFRAMES",
]
