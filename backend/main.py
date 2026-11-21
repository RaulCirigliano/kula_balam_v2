from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
import ccxt
import os
import time
import re
import hmac
import csv
import json
import threading
import requests
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import socket
import logging
from backend.market_context import MarketContextContract, save_market_context, load_market_context

logger = logging.getLogger("kula_balam")
try:
    import urllib3.util.connection as urllib3_conn
    urllib3_conn.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

# Constantes de Raíz y Rutas Absolutas (Bloque 5 item 8)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE_PATH = os.path.join(PROJECT_ROOT, ".env")
CSV_FILE_PATH = os.path.join(PROJECT_ROOT, "historial_trades.csv")
CSV_LEGACY_PATH = os.path.join(PROJECT_ROOT, "historial_trades_legacy.csv")
SHARED_DIRECTIVES_PATH = os.path.join(PROJECT_ROOT, "AGENTS.md")
BRAIN_STATE_PATH = os.path.join(PROJECT_ROOT, "backend", "config", "brain_state.json")

# Cargar variables de entorno desde la raíz del proyecto
load_dotenv(ENV_FILE_PATH)

app = FastAPI(title="Kula Balam AI API", description="API para el motor de trading algorítmico Kula Balam")

# Seguridad: TrustedHostMiddleware (Bloque 5 item 6)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["127.0.0.1", "localhost", "testserver", "192.168.100.16", "192.168.100.10", "100.79.33.85", "ArteBarro"]
)

# Seguridad: CORS restrictivo con puertos realmente utilizados (Bloque 5 item 6)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://localhost",
        "http://127.0.0.1:18767",
        "http://localhost:18767",
        "http://127.0.0.1:18087",
        "http://localhost:18087",
        "http://127.0.0.1:8520",
        "http://localhost:8520",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|100\.\d+\.\d+\.\d+)(:(18767|18087|8520|8080|3000|5500|5173))?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    try:
        from backend.daemon import get_trader_daemon
        daemon = get_trader_daemon()
        saved_brain = _read_brain_state()
        saved_daemon = daemon.load_saved_config() or {}
        daemon.start(
            symbol=saved_daemon.get("symbol") or "SOL/USDT",
            timeframe=saved_daemon.get("timeframe") or "4h",
            strategy=saved_daemon.get("strategy") or "donchian_breakout_1h",
            allowed_strategies=saved_daemon.get("allowed_strategies") or ["kula_balam_cava_ruiz", "donchian_breakout_1h", "squeeze_dual_eth_4h_slot1"],
            strategy_lots=saved_daemon.get("strategy_lots"),
            strategy_risk_pcts=saved_daemon.get("strategy_risk_pcts"),
            slot_alloc_pct=saved_daemon.get("slot_alloc_pct"),
            engine=saved_brain.get("engine") or saved_daemon.get("engine") or "antigravity_operador",
            model=saved_brain.get("model") or saved_daemon.get("model") or "antigravity-tactical-v1",
            tp=float(saved_daemon.get("tp", 2.0)),
            sl=float(saved_daemon.get("sl", 1.0)),
            risk=float(saved_daemon.get("risk", 0.50)),
            fee=float(saved_daemon.get("fee", 0.1)),
            spread=float(saved_daemon.get("spread", 0.05)),
            min_profit_pct=float(saved_daemon.get("min_profit_pct", 0.5)),
            mode=saved_daemon.get("mode") or "smart",
            max_positions=int(saved_daemon.get("max_positions", 2)),
            enable_futures_simulation=saved_daemon.get("enable_futures_simulation"),
        )
        if saved_daemon.get("paused_new_entries"):
            daemon.set_paused(True, saved_daemon.get("pause_reason") or "Pausa restaurada tras reinicio.")
        print(
            f"🚀 [STARTUP] TraderDaemon iniciado en modo {daemon.mode} "
            f"({daemon.max_positions} slots, estrategia {daemon.strategy} [{daemon.timeframe}], motor {daemon.engine})."
        )
    except Exception as exc:
        print(f"⚠️ [STARTUP] No se pudo auto-iniciar el TraderDaemon: {exc}")


# Locks de concurrencia a nivel de proceso e inter-proceso (con Monitor del Mercado)
import contextlib
import os
import tempfile

try:
    import fcntl
except ImportError:
    fcntl = None

CSV_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
_KEY_LOCKS: Dict[str, threading.Lock] = {}
_CACHE_DATA: Dict[str, Dict[str, Any]] = {}
_BRAIN_STATE_LOCK = threading.Lock()

# Símbolos soportados alineados estrictamente con el selector del frontend (Bloque 5 item 3)
SUPPORTED_SYMBOLS = [
    # Criptomonedas
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BTC-USD", "ETH-USD", "SOL-USD", "BNB/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT",
    # Materias Primas, Energía y Micro-Futuros CME
    "CL=F", "GC=F", "SI=F", "NG=F", "MES=F", "MNQ=F",
    # Mercado Forex / Divisas Internacionales (24/5)
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X",
    # Bonos e Índices Macro
    "TLT", "^GSPC", "SPY", "QQQ",
    # Acciones y Empresas Globales
    "BABA", "NVDA", "AAPL", "AMD", "AVGO", "META", "TSLA", "MSFT",
    # Mercado Argentino (Acciones / CEDEARs)
    "GGAL.BA", "YPFD.BA", "PAMP.BA", "BMA.BA", "ALUA.BA", "TXAR.BA",
    # China, Asia y ETFs Temáticos
    "MCHI", "KWEB", "BOTZ", "^HSI", "^N225"
]
VALID_SYMBOLS = SUPPORTED_SYMBOLS

def validate_symbol(symbol: str):
    """Valida que el símbolo pertenezca a la lista oficial soportada."""
    if not symbol or symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Símbolo no soportado: '{symbol}'. Símbolos permitidos: {SUPPORTED_SYMBOLS}")

VALID_TIMEFRAMES = {"1m", "5m", "15m", "1h", "4h", "1d"}
TIMEFRAME_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
ANALYSIS_OHLCV_LIMIT = 1000
MIN_ANALYSIS_CLOSED_CANDLES = 205
CONTINUOUS_MARKET_SYMBOLS = {"BTC-USD", "ETH-USD", "SOL-USD"}

from backend.quant_analysis import (
    ATR_STRATEGY_TIMEFRAMES,
    ATR_Z_SCORE_THRESHOLD,
    ATR_LOWER_WICK_RATIO_MIN,
    ATR_RELATIVE_VOLUME_MAX,
    ATR_TP_ATR_MULTIPLIER,
    ATR_SL_ATR_MULTIPLIER,
    ATR_COST_COVERAGE_MULTIPLIER,
    ATR_MIN_NET_TP_PCT,
    net_return_after_costs,
    normalize_signal,
    sanitize_ctx,
    build_macro_directive,
    compute_technical_indicators,
    evaluate_strategy_metrics,
    evaluate_local_engine_signal,
)
from backend.estrategias import (
    get_supported_strategy_ids,
    get_allowed_timeframes,
    list_strategies,
    get_strategy,
)
from backend.quant_risk import net_pnl_pct_from_prices, net_rr_metrics, MIN_NET_RR
from backend.entry_gate import (
    RADAR_TTL_HOURS,
    cio_directive_failures,
    churn_block_reason,
    entry_gate_failures,
    get_btc_macro_status,
)


def validate_timeframe(timeframe: str):
    """Valida que el timeframe pertenezca al conjunto oficial permitido (Bloque 5 item 3)."""
    if not timeframe or timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Timeframe no soportado: '{timeframe}'. Timeframes permitidos: {list(VALID_TIMEFRAMES)}")

def verify_auth_token(request: Request, x_api_token: Optional[str] = Header(None)):
    """Validación de seguridad usando hmac.compare_digest para prevenir timing attacks (Bloque 5 item 6)."""
    secret_token = os.getenv("APP_SECRET_TOKEN") or os.getenv("APP_TOKEN")
    if secret_token:
        if not x_api_token or not hmac.compare_digest(str(x_api_token), str(secret_token)):
            raise HTTPException(status_code=401, detail="Token de API inválido o ausente.")
    else:
        client_host = request.client.host if request.client else ""
        if client_host not in ["127.0.0.1", "localhost", "::1", "testclient"]:
            raise HTTPException(status_code=403, detail="Acceso restringido a localhost.")

# Inicializamos el exchange ccxt (Binance para cripto) con timeout estricto y rate-limiter (ISO 25010)
exchange = ccxt.binance({"timeout": 8000, "enableRateLimit": True})
CCXT_LOCK = threading.Lock()
MAX_CACHE_KEYS = 256

# Helper para locks granulares por clave de caché con poda acotada de entradas expiradas
def _get_key_lock(key: str) -> threading.Lock:
    with _CACHE_LOCK:
        if len(_CACHE_DATA) > MAX_CACHE_KEYS:
            now_t = time.time()
            expired_keys = [k for k, v in list(_CACHE_DATA.items()) if isinstance(v, dict) and now_t >= v.get("expires_at", 0)]
            for k in expired_keys:
                _CACHE_DATA.pop(k, None)
                if k != key:
                    _KEY_LOCKS.pop(k, None)
        if key not in _KEY_LOCKS:
            _KEY_LOCKS[key] = threading.Lock()
        return _KEY_LOCKS[key]

# --- LECTURA DE MERCADO CON CACHÉ TTL Y PREVENCIÓN DE DESCARGAS DUPLICADAS (Bloque 5 item 4) ---
def _validate_ohlcv_data(data: Any, symbol: str) -> List[List[float]]:
    if not isinstance(data, list) or not data:
        raise ValueError(f"Feed vacío o inválido para {symbol}")

    validated = []
    for index, candle in enumerate(data):
        if not isinstance(candle, (list, tuple)) or len(candle) < 6:
            raise ValueError(f"Vela OHLCV mal formada para {symbol} en la posición {index}")
        try:
            values = [float(value) for value in candle[:6]]
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Vela OHLCV no numérica para {symbol} en la posición {index}") from exc
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Vela OHLCV no finita para {symbol} en la posición {index}")
        timestamp, open_price, high, low, close, volume = values
        if timestamp <= 0 or min(open_price, high, low, close) <= 0 or volume < 0:
            raise ValueError(f"Vela OHLCV fuera de rango para {symbol} en la posición {index}")
        if low > high or not (low <= open_price <= high) or not (low <= close <= high):
            raise ValueError(f"Rango OHLCV inconsistente para {symbol} en la posición {index}")
        validated.append([int(timestamp), open_price, high, low, close, volume])

    candles_by_timestamp: Dict[int, List[float]] = {}
    for candle in validated:
        timestamp = int(candle[0])
        previous = candles_by_timestamp.get(timestamp)
        if previous is not None and previous != candle:
            raise ValueError(f"Velas OHLCV contradictorias con el mismo timestamp para {symbol}: {timestamp}")
        candles_by_timestamp[timestamp] = candle
    return [candles_by_timestamp[timestamp] for timestamp in sorted(candles_by_timestamp)]

def _closed_ohlcv_data(data: Any, symbol: str, timeframe: str, now_ms: Optional[int] = None) -> List[List[float]]:
    """Devuelve únicamente velas completas; los timestamps OHLCV marcan el inicio de cada vela."""
    validate_timeframe(timeframe)
    candles = _validate_ohlcv_data(data, symbol)
    current_time_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    candle_duration_ms = TIMEFRAME_SECONDS[timeframe] * 1000
    return [
        candle
        for candle in candles
        if candle[0] + candle_duration_ms <= current_time_ms
    ]

def _validate_ohlcv_continuity(candles: List[List[float]], symbol: str, timeframe: str) -> None:
    if '/' not in symbol and symbol not in CONTINUOUS_MARKET_SYMBOLS:
        return
    expected_interval_ms = TIMEFRAME_SECONDS[timeframe] * 1000
    for previous, current in zip(candles, candles[1:]):
        interval_ms = int(current[0] - previous[0])
        if interval_ms != expected_interval_ms:
            raise ValueError(
                f"Hueco OHLCV para {symbol}: intervalo esperado {expected_interval_ms}ms, "
                f"recibido {interval_ms}ms entre {int(previous[0])} y {int(current[0])}"
            )

def _fetch_raw_ohlcv(symbol: str, timeframe: str, limit: int):
    if '/' not in symbol:
        import yfinance as yf
        if timeframe in ['1m', '5m']:
            period = '5d'
        elif timeframe == '1d':
            period = '2y'
        else:
            period = '60d'
        ticker = yf.Ticker(symbol)
        try:
            df_yf = ticker.history(period=period, interval=timeframe, timeout=10)
        except TypeError:
            df_yf = ticker.history(period=period, interval=timeframe)
        if df_yf.empty:
            raise Exception(f'No se encontraron datos de {symbol} en Yahoo Finance')
        df_yf.reset_index(inplace=True)
        col_name = df_yf.columns[0]
        df_yf['timestamp'] = df_yf[col_name].apply(lambda x: int(x.timestamp() * 1000))
        df_yf.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
        # Yahoo puede devolver filas con OHLC NaN (vela parcial/feriado); se descartan para no romper la validación de feed.
        df_yf = df_yf.dropna(subset=['open', 'high', 'low', 'close'])
        df_yf['volume'] = df_yf['volume'].fillna(0.0)
        if df_yf.empty:
            raise Exception(f'No se encontraron velas válidas de {symbol} en Yahoo Finance')
        data = df_yf[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(limit).values.tolist()
    else:
        with CCXT_LOCK:
            data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    return data

def get_ohlcv(symbol: str, timeframe: str, limit: int):
    ttl = 2.0 if '/' in symbol else 15.0
    tf_sec = TIMEFRAME_SECONDS.get(timeframe, 60)
    cache_key = f"ohlcv:{symbol}:{timeframe}:{limit}"
    now = time.time()
    current_bucket = int(now // tf_sec)
    with _CACHE_LOCK:
        entry = _CACHE_DATA.get(cache_key)
        if entry and now < entry["expires_at"] and entry.get("bucket") == current_bucket:
            return entry["data"]

    key_lock = _get_key_lock(cache_key)
    with key_lock:
        now_locked = time.time()
        locked_bucket = int(now_locked // tf_sec)
        with _CACHE_LOCK:
            entry = _CACHE_DATA.get(cache_key)
            if entry and now_locked < entry["expires_at"] and entry.get("bucket") == locked_bucket:
                return entry["data"]
        data = _validate_ohlcv_data(_fetch_raw_ohlcv(symbol, timeframe, limit), symbol)
        store_now = time.time()
        with _CACHE_LOCK:
            _CACHE_DATA[cache_key] = {
                "data": data,
                "expires_at": store_now + ttl,
                "bucket": int(store_now // tf_sec),
            }
        return data

def _fetch_raw_price(symbol: str):
    if '/' in symbol:
        with CCXT_LOCK:
            ticker = exchange.fetch_ticker(symbol)
        quote_ts = int(ticker.get('timestamp') or (time.time() * 1000))
        price = float(ticker['last'])
    else:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        try:
            hist = ticker.history(period='1d', interval='1m', timeout=10)
        except TypeError:
            hist = ticker.history(period='1d', interval='1m')
        if hist.empty:
            try:
                hist = ticker.history(period='5d', interval='1m', timeout=10)
            except TypeError:
                hist = ticker.history(period='5d', interval='1m')
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            quote_ts = int(hist.index[-1].timestamp() * 1000)
        else:
            raise Exception(f"No se pudieron obtener cotizaciones de {symbol} en Yahoo Finance")
    if not math.isfinite(price) or price <= 0 or not math.isfinite(float(quote_ts)) or quote_ts <= 0:
        raise ValueError(f"Feed devolvió precio o timestamp inválido para {symbol}")
    return float(price), int(quote_ts)

def get_cached_price(symbol: str):
    ttl = 2.0 if '/' in symbol else 15.0
    cache_key = f"price:{symbol}"
    now = time.time()
    with _CACHE_LOCK:
        entry = _CACHE_DATA.get(cache_key)
        if entry and now < entry["expires_at"]:
            return entry["data"]

    key_lock = _get_key_lock(cache_key)
    with key_lock:
        with _CACHE_LOCK:
            entry = _CACHE_DATA.get(cache_key)
            if entry and time.time() < entry["expires_at"]:
                return entry["data"]
        price, quote_ts = _fetch_raw_price(symbol)
        result = {"price": price, "ts": int(time.time() * 1000), "quote_ts": quote_ts}
        with _CACHE_LOCK:
            _CACHE_DATA[cache_key] = {"data": result, "expires_at": time.time() + ttl}
        return result

# --- ENDPOINTS DE CONFIGURACIÓN Y ESTADO ---
class ApiKeyRequest(BaseModel):
    api_key: str


class BrainStateRequest(BaseModel):
    engine: str = Field(min_length=1, max_length=40)
    model: Optional[str] = Field(default=None, max_length=120)
    auto_engine: Optional[bool] = Field(default=None)

class FailoverTriggerRequest(BaseModel):
    source: Optional[str] = Field(default="operador", max_length=50)
    reason: Optional[str] = Field(default="Agotamiento de tokens o interrupción técnica del servicio", max_length=500)

class MacroInjectionRequest(BaseModel):
    asset: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_=./^\-]+$")
    text: str = Field(min_length=1, max_length=5000)
    confidence: float = Field(default=80, ge=0, le=100, allow_inf_nan=False)
    type: str = Field(default="Oportunidad", max_length=50)
    source: str = Field(default="Monitor de Mercado", max_length=120)
    timestamp: Optional[str] = Field(default=None, max_length=64)
    id: Optional[str] = Field(default=None, max_length=100)


class StrategyAdvisorRequest(BaseModel):
    user_prompt: str = Field(min_length=1, max_length=1000)
    symbol: Optional[str] = Field(default="BTC/USDT", max_length=40)
    current_strategy: Optional[str] = Field(default="auto", max_length=50)


@app.post("/api/strategy/advisor")
def advise_strategy(req: StrategyAdvisorRequest, request: Request, x_api_token: Optional[str] = Header(None)):
    """
    Agente Asesor Cuantitativo de Estrategias:
    Analiza la intención del operador, el activo y el contexto temporal para recomendar
    la estrategia óptima con justificación y botón de aplicación inmediata en 1 clic.
    """
    verify_auth_token(request, x_api_token)
    prompt_lower = req.user_prompt.strip().lower()
    symbol = (req.symbol or "BTC/USDT").strip().upper()

    # Palabras clave por estrategia
    cero_words = [
        "cero", "estrategia cero", "fase 1", "fase 3", "tendencia institucional", "estrategia 01", "qwen 15m"
    ]
    panic_words = [
        "caida", "caída", "rebote", "panico", "pánico", "crash", "desplome",
        "sobreventa", "capitulacion", "capitulación", "barato", "comprar abajo",
        "suelo", "piso", "dip", "correccion", "corrección"
    ]
    opening_words = [
        "apertura", "campana", "londres", "araujo", "m15", "inicio de rueda",
        "ny open", "wall street", "rompimiento", "quiebre", "primera hora"
    ]
    trend_words = [
        "tendencia", "swing", "dias", "días", "tranquilo", "subida", "prolijo",
        "peluqueo", "trim", "asegurar", "riesgo cero", "chu", "1h", "institucional"
    ]
    rally_words = [
        "sin techo", "rally", "subir", "correr", "dejar correr", "no me saque",
        "trailing", "máximos", "maximos", "ganancias libres", "raul", "subida libre", "parabolico"
    ]

    if any(w in prompt_lower for w in cero_words):
        selected_id = "01_tendencia_institucional_15m"
        selected_name = "🏛️ Tendencia Institucional 15m (Estrategia Cero)"
        reason = (
            f"Estrategia base cuantitativa auditada para {symbol}. "
            "Exige confluencia técnica en velas de 15m: Precio sobre EMA200 y SMA20, RSI > 40 y volumen RVOL > 0.8."
        )
        action_plan = "Stop Loss a 1.5×ATR fuera del ruido, Take Profit a +3.0% y salida inmediata si el precio cruza bajo SMA20."
        timeframe = "15m"
        risk_pct = 0.25
    elif any(w in prompt_lower for w in panic_words):
        selected_id = "mean_reversion_atr"
        selected_name = "🧯 Cazador de Rebotes tras Caída Fuerte (Capitulación)"
        reason = (
            f"Detecté que buscas aprovechar una corrección o pánico de mercado en {symbol}. "
            "Esta estrategia espera que la sobreventa sea extrema (Z-Score ≤ -2.0) y confirma que hayan entrado "
            "compradores pasivos (mecha de absorción) antes de comprar."
        )
        action_plan = "Stop Loss a 1.5×ATR fuera del ruido y Take Profit proyectado a 4.0×ATR para capturar el rebote."
        timeframe = "15m"
        risk_pct = 0.25
    elif any(w in prompt_lower for w in opening_words):
        selected_id = "nasdaq_araujo_vwap"
        selected_name = "🎯 Francotirador de Apertura de Bolsa (M15)"
        reason = (
            f"Tu objetivo coincide con la campana de apertura de Wall Street para {symbol}. "
            "Esta estrategia evalúa la ruptura del rango de la sesión europea de Londres con el VWAP diario a favor."
        )
        action_plan = "Máximo 1 trade de alta precisión al día en velas M15, con Stop técnico inmediato y R:R neto ≥ 2.0."
        timeframe = "15m"
        risk_pct = 0.25
    elif any(w in prompt_lower for w in rally_words):
        selected_id = "trailing_trend_runner"
        selected_name = "🚀 Rally sin Techo: Ganancias Libres con Stop Móvil"
        reason = (
            f"Querés maximizar una subida fuerte en {symbol} sin que un Take Profit prematuro te corte las ganancias. "
            "El Stop Loss sube detrás del precio máximo alcanzado protegiendo tu capital."
        )
        action_plan = "Pasa a Breakeven Real a +0.40% bruto (+0.15% neto libre de riesgo) y acompaña al precio a 2% de distancia."
        timeframe = "1h"
        risk_pct = 0.50
    elif any(w in prompt_lower for w in trend_words):
        selected_id = "hyenuk_chu_multibagger"
        selected_name = "📈 Seguidor de Tendencia con Ganancia Asegurada (Swing 1h)"
        reason = (
            f"Para operaciones tranquilas de varios días en {symbol} siguiendo la tendencia mayor (EMA200), "
            "con filtro anti-euforia (RSI ≤ 70)."
        )
        action_plan = "Al llegar al primer hito (+3.5%), vende el 50% (Peluqueo) y el saldo restante corre a Breakeven con $0 riesgo."
        timeframe = "1h"
        risk_pct = 0.25
    else:
        selected_id = "auto"
        selected_name = "🤖 Piloto Automático Inteligente (Por Horario y Régimen)"
        reason = (
            f"Para tu objetivo general en {symbol}, la mejor recomendación es delegar en el Orquestador: "
            "conmuta solo según el horario bursátil, fin de semana y volatilidad."
        )
        action_plan = "Apertura Araujo (10:25-12:30 ARG) ➔ Swing Chu (tarde) ➔ Reversión ATR (si hay crash) ➔ Cripto 24/7 (findes)."
        timeframe = "15m"
        risk_pct = 0.25

    return {
        "status": "ok",
        "user_prompt": req.user_prompt,
        "recommended_strategy_id": selected_id,
        "recommended_strategy_name": selected_name,
        "reason": reason,
        "action_plan": action_plan,
        "suggested_timeframe": timeframe,
        "suggested_risk_pct": risk_pct,
    }


@app.post("/api/config/gemini")
def save_gemini_key(req: ApiKeyRequest, request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    # Validación con regex (Bloque 5 item 6)
    if not re.match(r'^[A-Za-z0-9_.\-]{20,128}$', req.api_key):
        raise HTTPException(status_code=400, detail="Formato de API Key inválido. Debe contener entre 20 y 128 caracteres válidos.")

    lines = []
    found = False
    if os.path.exists(ENV_FILE_PATH):
        with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    new_lines = []
    for line in lines:
        if line.strip().startswith("GEMINI_API_KEY="):
            new_lines.append(f'GEMINI_API_KEY="{req.api_key}"\n')
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f'GEMINI_API_KEY="{req.api_key}"\n')

    with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    try:
        os.chmod(ENV_FILE_PATH, 0o600)
    except Exception:
        pass

    os.environ["GEMINI_API_KEY"] = req.api_key
    return {"status": "ok", "message": "API Key de Gemini configurada con éxito en .env."}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Motor de Trading AI en línea"}


_FAILOVER_ALERT: Dict[str, Any] = {
    "active": False,
    "source": None,
    "reason": None,
    "switched_to": "gemini",
    "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
    "timestamp": None,
    "message": "",
    "dismissed": False,
}


def execute_gemini_failover(
    source: str = "operador",
    reason: str = "Agotamiento de tokens o interrupción técnica del servicio",
) -> Dict[str, Any]:
    """
    Ejecuta la conmutación de emergencia a la API de Google (Google Gemini)
    SOLO si la conmutación automática (auto_engine) está habilitada por el operador.
    Si auto_engine es False (Modo Manual Fijo), descarta la conmutación y preserva
    rígidamente el motor seleccionado por el usuario.
    """
    global _FAILOVER_ALERT
    try:
        current_brain = _read_brain_state()
    except Exception:
        current_brain = {"engine": "antigravity_operador", "auto_engine": False}

    auto_enabled = bool(current_brain.get("auto_engine", False))
    if not auto_enabled:
        logger.info(
            f"[Failover Descartado] Petición de failover recibida de '{source}' por '{reason}', "
            "pero la conmutación automática está DESACTIVADA (Modo Manual Fijo). "
            f"Se conserva el motor activo: {current_brain.get('engine')}."
        )
        return {
            "active": False,
            "source": source,
            "reason": reason,
            "switched_to": None,
            "model": current_brain.get("model"),
            "timestamp": time.time(),
            "message": f"Conmutación automática descartada: Modo Manual Fijo activo ({current_brain.get('engine')}).",
            "dismissed": True,
            "auto_engine_blocked": True,
        }

    gem_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    now_ts = time.time()
    source_label = (
        "Operador Táctico"
        if "operador" in source.lower()
        else ("Director de Inversiones (CIO)" if "cio" in source.lower() else source.upper())
    )
    msg = (
        f"🚨 ALERTA CRÍTICA: {source_label} ha dejado de operar por '{reason}'. "
        f"Se ha conmutado automáticamente a la API de Google ({gem_model}) "
        "tanto en el CIO (Monitor del Mercado) como en el Operador para asegurar la continuidad operativa 24/7."
    )
    failover_data = {
        "active": True,
        "source": source,
        "reason": reason,
        "switched_to": "gemini",
        "model": gem_model,
        "timestamp": now_ts,
        "message": msg,
        "dismissed": False,
    }
    _FAILOVER_ALERT = failover_data

    # 1. Persistir estado del cerebro central a Gemini
    new_state = {
        "engine": "gemini",
        "model": gem_model,
        "auto_engine": True,
        "failover_event": failover_data,
    }
    temp_path = f"{BRAIN_STATE_PATH}.tmp"
    try:
        os.makedirs(os.path.dirname(BRAIN_STATE_PATH), exist_ok=True)
        with _BRAIN_STATE_LOCK:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(new_state, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, BRAIN_STATE_PATH)
    except Exception as exc:
        logger.error(f"Error persistiendo failover en brain_state.json: {exc}")

    # 2. Sincronizar motor del Daemon en caliente
    try:
        from backend.daemon import get_trader_daemon
        daemon = get_trader_daemon()
        if daemon:
            daemon.engine = "gemini"
            daemon.model = gem_model
    except Exception:
        pass

    # 3. Notificar en segundo plano al Monitor del Mercado (puerto 8520 · CIO)
    def _notify_cio():
        try:
            requests.post(
                "http://127.0.0.1:8520/api/system/brain",
                json={"engine": "gemini", "model": gem_model, "auto_engine": True},
                timeout=2.0,
            )
        except Exception:
            pass
    threading.Thread(target=_notify_cio, daemon=True).start()

    logger.warning(f"🚨 [CONMUTACIÓN AUTOMÁTICA GEMINI]: {msg}")
    return failover_data


def _read_brain_state() -> Dict[str, Any]:
    global _FAILOVER_ALERT
    if not os.path.exists(BRAIN_STATE_PATH):
        return {"engine": "antigravity_operador", "model": "antigravity_operador", "auto_engine": False}
    try:
        with open(BRAIN_STATE_PATH, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="No se pudo leer la configuración central del cerebro.") from exc
    if not isinstance(state, dict):
        raise HTTPException(status_code=500, detail="La configuración central del cerebro tiene un formato inválido.")
    validated = _validate_brain_state(
        state.get("engine", "antigravity_operador"),
        state.get("model"),
        state.get("auto_engine", False) if "auto_engine" in state else None
    )
    if state.get("engine") != "gemini":
        _FAILOVER_ALERT["active"] = False
        _FAILOVER_ALERT["dismissed"] = True
    elif "failover_event" in state and isinstance(state["failover_event"], dict):
        validated["failover_event"] = state["failover_event"]
        if state["failover_event"].get("active") and not _FAILOVER_ALERT.get("active"):
            _FAILOVER_ALERT = state["failover_event"]
    return validated


def _validate_brain_state(engine: Any, model: Any, auto_engine: Any = None) -> Dict[str, Any]:
    if not isinstance(engine, str) or engine not in {"ollama", "gemini", "local", "antigravity_cio", "antigravity_operador"}:
        raise HTTPException(status_code=422, detail="Motor de cerebro no soportado.")
    clean_model = model.strip() if isinstance(model, str) else None
    if clean_model:
        if not re.fullmatch(r"[A-Za-z0-9._:/-]{1,120}", clean_model) or any(part in {"", ".", ".."} for part in clean_model.split("/")):
            raise HTTPException(status_code=422, detail="Nombre de modelo inválido.")
    res: Dict[str, Any] = {"engine": engine, "model": clean_model or None}
    if auto_engine is not None:
        res["auto_engine"] = bool(auto_engine)
    return res


def _shared_brain_directives() -> str:
    try:
        with open(SHARED_DIRECTIVES_PATH, "r", encoding="utf-8") as directives_file:
            base_directives = directives_file.read()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="No se pudieron leer las directivas canónicas del cerebro.") from exc

    macro_context_path = os.path.join(PROJECT_ROOT, "backend", "config", "contexto_macro.md")
    if os.path.isfile(macro_context_path):
        try:
            with open(macro_context_path, "r", encoding="utf-8") as f:
                macro_live = f.read().strip()
            if macro_live:
                return f"{base_directives}\n\n---\n{macro_live}"
        except Exception:
            pass
    return base_directives


@app.get("/api/system/models")
def get_system_models(request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    return {
        "available": False,
        "models": [],
        "cached_at": None,
        "error": "Ollama no está disponible; infraestructura local de IA descontinuada en favor del motor cuantitativo.",
    }


@app.get("/api/system/brain")
def get_system_brain(request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    with _BRAIN_STATE_LOCK:
        return _read_brain_state()


@app.post("/api/system/brain")
def set_system_brain(
    req: BrainStateRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    verify_auth_token(request, x_api_token)
    state = _validate_brain_state(req.engine, req.model, req.auto_engine)

    # Si el usuario selecciona manualmente Antigravity u otro motor, se desactiva cualquier alerta de failover
    global _FAILOVER_ALERT
    if req.engine != "gemini":
        _FAILOVER_ALERT["active"] = False
        _FAILOVER_ALERT["dismissed"] = True

    state_dir = os.path.dirname(BRAIN_STATE_PATH)
    temp_path = f"{BRAIN_STATE_PATH}.tmp"
    try:
        os.makedirs(state_dir, exist_ok=True)
        with _BRAIN_STATE_LOCK:
            with open(temp_path, "w", encoding="utf-8") as state_file:
                json.dump(state, state_file, ensure_ascii=False, indent=2)
                state_file.flush()
                os.fsync(state_file.fileno())
            os.replace(temp_path, BRAIN_STATE_PATH)
    except OSError as exc:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail="No se pudo guardar la configuración central del cerebro.") from exc

    # Sincronizar en caliente el Daemon si está corriendo
    try:
        from backend.daemon import get_trader_daemon
        daemon = get_trader_daemon()
        if daemon:
            daemon.engine = req.engine
            daemon.model = req.model
    except Exception:
        pass

    return state


@app.get("/api/system/failover-alert")
def get_failover_alert():
    """Retorna el estado de la alerta de conmutación de emergencia por caída o agotamiento de tokens."""
    global _FAILOVER_ALERT
    if not _FAILOVER_ALERT.get("active") and os.path.exists(BRAIN_STATE_PATH):
        try:
            with open(BRAIN_STATE_PATH, "r", encoding="utf-8") as f:
                st = json.load(f)
                if isinstance(st, dict) and isinstance(st.get("failover_event"), dict):
                    _FAILOVER_ALERT = st["failover_event"]
        except Exception:
            pass
    return _FAILOVER_ALERT


@app.post("/api/system/failover-alert/trigger")
def trigger_failover_alert(
    req: FailoverTriggerRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Dispara manualmente o por evento técnico la conmutación a Google Gemini en CIO y Operador."""
    verify_auth_token(request, x_api_token)
    return execute_gemini_failover(source=req.source or "operador", reason=req.reason or "Interrupción operativa")


@app.post("/api/system/failover-alert/dismiss")
def dismiss_failover_alert(request: Request, x_api_token: Optional[str] = Header(None)):
    """Descarta y oculta la alerta de conmutación tras ser vista por el usuario."""
    verify_auth_token(request, x_api_token)
    global _FAILOVER_ALERT
    _FAILOVER_ALERT["dismissed"] = True
    _FAILOVER_ALERT["active"] = False
    if os.path.exists(BRAIN_STATE_PATH):
        try:
            with _BRAIN_STATE_LOCK:
                with open(BRAIN_STATE_PATH, "r", encoding="utf-8") as f:
                    st = json.load(f)
                if isinstance(st, dict) and "failover_event" in st:
                    st["failover_event"]["dismissed"] = True
                    st["failover_event"]["active"] = False
                    with open(BRAIN_STATE_PATH, "w", encoding="utf-8") as f:
                        json.dump(st, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return {"status": "ok", "message": "Alerta de conmutación descartada."}


@app.get("/api/system/engine-check")
def check_system_engines(request: Request, x_api_token: Optional[str] = Header(None)):
    """Verifica en cascada estricta la salud de los motores: Antigravity -> Google Gemini -> Qwen 2.5 (Ollama)."""
    verify_auth_token(request, x_api_token)

    # 1. Prioridad 1: Antigravity Operador / CIO
    antigravity_ok = True
    antigravity_details = "⚡ Antigravity Operador Activo (0% CPU · Directivas Listas)"

    # 2. Prioridad 2: Google Gemini (Nube)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    gemini_ok = bool(gemini_key and len(gemini_key.strip()) >= 20)
    gemini_details = "✨ Google Gemini Conectado (API Key Configurada)" if gemini_ok else "⚠️ Google Gemini no configurado (Falta GEMINI_API_KEY)"

    # 3. Prioridad 3: Qwen 2.5 (Ollama Local - Descontinuado)
    qwen_ok = False
    qwen_details = "Desactivado (Infraestructura Ollama retirada en favor de modelos cuantitativos)"

    # 4. Prioridad 4: Modelo Matemático Cuantitativo (Local Determinista)
    matematico_details = "⚙️ Modelo Matemático Cuantitativo Activo (Puro Código Python · Fallback Seguro 100% Disponible)"

    active_brain = _read_brain_state()
    return {
        "status": "ok",
        "hierarchy": ["antigravity_operador", "ai", "ollama|trader-qwen", "local"],
        "active_engine": active_brain.get("engine", "antigravity_operador"),
        "checks": {
            "antigravity": {
                "priority": 1,
                "status": "ok" if antigravity_ok else "error",
                "available": antigravity_ok,
                "name": "Antigravity Operador",
                "icon": "⚡",
                "details": antigravity_details,
            },
            "gemini": {
                "priority": 2,
                "status": "ok" if gemini_ok else "unconfigured",
                "available": gemini_ok,
                "name": "Google Gemini",
                "icon": "✨",
                "details": gemini_details,
            },
            "qwen": {
                "priority": 3,
                "status": "ok" if qwen_ok else "offline",
                "available": qwen_ok,
                "name": "Qwen 2.5 (Ollama)",
                "icon": "🤖",
                "details": qwen_details,
            },
            "matematico": {
                "priority": 4,
                "status": "ok",
                "available": True,
                "name": "Modelo Matemático",
                "icon": "⚙️",
                "details": matematico_details,
            },
        },
    }


@app.get("/api/strategies")
@app.get("/api/estrategias")
def get_available_strategies(include_laboratory: bool = False):
    """Retorna el catálogo oficial de estrategias disponibles (modulares)."""
    return list_strategies(include_laboratory=include_laboratory)


@app.get("/api/catalogo_formulas")
def api_kula_get_catalogo_formulas():
    """Retorna el catálogo vivo y dinámico de fórmulas (Single Source of Truth)."""
    from backend.estrategias.catalogo_manager import get_catalogo_completo
    return get_catalogo_completo()


@app.get("/api/catalogo_formulas/{categoria}/{archivo}")
def api_kula_get_formula_detalle(categoria: str, archivo: str):
    """Retorna el detalle y código de una fórmula específica del catálogo."""
    from backend.estrategias.catalogo_manager import get_formula_detalle
    res = get_formula_detalle(categoria, archivo)
    if not res:
        raise HTTPException(status_code=404, detail="Fórmula no encontrada en catálogo.")
    return res


@app.delete("/api/catalogo_formulas/{categoria}/{archivo}")
def api_kula_delete_formula(categoria: str, archivo: str):
    """Elimina físicamente una fórmula de su carpeta y la desautoriza en Kula Balam."""
    from backend.estrategias.catalogo_manager import eliminar_formula
    try:
        return eliminar_formula(categoria, archivo)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar fórmula: {str(e)}")


@app.get("/api/strategies/laboratory")
def get_laboratory_strategies():
    """Retorna las estrategias archivadas en la Caja de Buenas Ideas (Laboratorio Cuantitativo)."""
    from backend.estrategias.registry import list_laboratory_strategies
    return list_laboratory_strategies()


class ToggleSubStrategyRequest(BaseModel):
    strategy_id: str
    sub_id: str
    enabled: bool


class UpdateParamsRequest(BaseModel):
    strategy_id: str
    parameters: Dict[str, Any]


class ToggleActiveRequest(BaseModel):
    strategy_id: str
    active: bool


class ResetStrategyRequest(BaseModel):
    strategy_id: str


@app.get("/api/estrategias/config")
def get_strategies_config():
    """Retorna la jerarquía completa de estrategias, subestrategias y parámetros editables."""
    from backend.estrategias.config_manager import StrategyConfigManager
    return StrategyConfigManager.get_all_configs()


@app.post("/api/estrategias/toggle_sub")
def toggle_sub_strategy_endpoint(req: ToggleSubStrategyRequest):
    """Conmuta el checkbox de una subestrategia específica en caliente."""
    from backend.estrategias.config_manager import StrategyConfigManager
    ok = StrategyConfigManager.toggle_sub_strategy(req.strategy_id, req.sub_id, req.enabled)
    if not ok:
        raise HTTPException(status_code=400, detail="Estrategia o subestrategia no encontrada.")
    return {"status": "ok", "strategy_id": req.strategy_id, "sub_id": req.sub_id, "enabled": req.enabled}


@app.post("/api/estrategias/update_params")
def update_strategy_params_endpoint(req: UpdateParamsRequest):
    """Actualiza parámetros cuantitativos numéricos de una estrategia."""
    from backend.estrategias.config_manager import StrategyConfigManager
    ok = StrategyConfigManager.update_parameters(req.strategy_id, req.parameters)
    if not ok:
        raise HTTPException(status_code=400, detail="Estrategia no encontrada.")
    return {"status": "ok", "strategy_id": req.strategy_id, "parameters": req.parameters}


@app.post("/api/estrategias/toggle_active")
def toggle_strategy_active_endpoint(req: ToggleActiveRequest):
    """Activa o archiva (soft-delete) una estrategia completa."""
    from backend.estrategias.config_manager import StrategyConfigManager
    ok = StrategyConfigManager.toggle_strategy_active(req.strategy_id, req.active)
    if not ok:
        raise HTTPException(status_code=400, detail="Estrategia no encontrada.")
    return {"status": "ok", "strategy_id": req.strategy_id, "active": req.active}


@app.post("/api/estrategias/reset_defaults")
def reset_strategy_defaults_endpoint(req: ResetStrategyRequest):
    """Restablece los parámetros y submódulos de una estrategia a sus valores originales de fábrica."""
    from backend.estrategias.config_manager import StrategyConfigManager
    cfg = StrategyConfigManager.reset_strategy_to_default(req.strategy_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Estrategia no encontrada en valores por defecto.")
    return {"status": "ok", "strategy_id": req.strategy_id, "config": cfg}


@app.get("/api/market/price")
def get_price(symbol: str = "BTC/USDT"):
    validate_symbol(symbol)
    try:
        cached = get_cached_price(symbol)
        now_s = time.time()
        quote_ts = cached.get("quote_ts", cached.get("ts"))
        quote_ts_s = (quote_ts / 1000.0) if quote_ts > 1e11 else quote_ts
        quote_age_s = max(0, int(now_s - quote_ts_s))
        stale_threshold_s = 20 if '/' in symbol else 150
        market_open = bool(quote_age_s < 900 or (symbol.endswith('.BA') and quote_age_s < 1800))
        feed_delayed = bool(quote_age_s > stale_threshold_s and market_open)
        return {
            "symbol": symbol,
            "price": cached["price"],
            "ts": cached["ts"],
            "quote_ts": int(quote_ts_s * 1000),
            "quote_age_s": quote_age_s,
            "data_age_s": quote_age_s,
            "stale_threshold_s": stale_threshold_s,
            "market_open": market_open,
            "feed_delayed": feed_delayed
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/market/history")
def get_history(symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 100):
    validate_symbol(symbol)
    validate_timeframe(timeframe)
    # Acotar limit a rango seguro 10..1000 (Soporte de historial extendido para paneo fluido)
    bounded_limit = max(10, min(1000, int(limit)))
    try:
        warmup_limit = bounded_limit + 25
        ohlcv = get_ohlcv(symbol, timeframe, warmup_limit)
        import pandas as pd
        import ta
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['sma_20'] = ta.trend.SMAIndicator(close=df['close'], window=20).sma_indicator()
        df['vwap'] = ta.volume.VolumeWeightedAveragePrice(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'], window=14).volume_weighted_average_price()
        
        vwap_std = df['close'].rolling(window=14).std()
        df['vwap_upper'] = df['vwap'] + vwap_std
        df['vwap_lower'] = df['vwap'] - vwap_std
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
        df['atr'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
        
        if len(df) > bounded_limit:
            df = df.tail(bounded_limit)
        
        formatted_data = []
        for index, row in df.iterrows():
            item = {
                "time": int(row['timestamp'] / 1000),
                "open": row['open'],
                "high": row['high'],
                "low": row['low'],
                "close": row['close'],
                "volume": row['volume']
            }
            if not pd.isna(row['sma_20']):
                item["sma_20"] = round(row['sma_20'], 2)
            if not pd.isna(row['vwap']):
                item["vwap"] = round(row['vwap'], 2)
            if not pd.isna(row['vwap_upper']):
                item["vwap_upper"] = round(row['vwap_upper'], 2)
            if not pd.isna(row['vwap_lower']):
                item["vwap_lower"] = round(row['vwap_lower'], 2)
            if not pd.isna(row['rsi']):
                item["rsi"] = round(row['rsi'], 2)
            if not pd.isna(row['atr']) and float(row['atr']) > 0:
                item["atr"] = round(row['atr'], 4)
            formatted_data.append(item)
            
        if formatted_data and not df.empty:
            latest_ts_raw = df.iloc[-1]['timestamp']
            latest_ts_s = (latest_ts_raw / 1000.0) if latest_ts_raw > 1e11 else latest_ts_raw
            formatted_data[-1]["last_candle_age_s"] = max(0, int(time.time() - latest_ts_s))
            
        return formatted_data
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# --- RADAR DE MICROESTRUCTURA DE MERCADO EN TIEMPO REAL ---
_RADAR_OVERVIEW_CACHE: Dict[str, Any] = {"data": None, "expires_at": 0.0}
_RADAR_OVERVIEW_LOCK = threading.Lock()


@app.get("/api/market/radar-overview")
def get_market_radar_overview(force: bool = False):
    """
    Retorna métricas de microestructura en tiempo real para los 5 pares principales
    (BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT) con EMA, RSI14, RVOL y
    diagnóstico cualitativo en castellano. Caché TTL de 15 segundos (omite caché si force=True).
    """
    global _RADAR_OVERVIEW_CACHE
    now = time.time()
    with _RADAR_OVERVIEW_LOCK:
        if not force and _RADAR_OVERVIEW_CACHE["data"] and now < _RADAR_OVERVIEW_CACHE["expires_at"]:
            return _RADAR_OVERVIEW_CACHE["data"]

    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
    tickers = {}
    try:
        with CCXT_LOCK:
            tickers = exchange.fetch_tickers(symbols)
    except Exception:
        tickers = {}

    from concurrent.futures import ThreadPoolExecutor
    import pandas as pd
    import ta

    # Obtener posiciones abiertas en daemon para marcar 'Orden activa'
    active_syms = set()
    try:
        from backend.daemon import get_trader_daemon
        daemon_pos = get_trader_daemon().broker.fetch_positions()
        active_syms = {p.get("symbol") for p in daemon_pos}
    except Exception:
        pass

    def _eval_symbol(sym: str) -> Dict[str, Any]:
        tick = tickers.get(sym, {})
        px = float(tick.get("last") or 0.0)
        chg = float(tick.get("percentage") or 0.0)
        rsi = 50.0
        rvol = 1.0
        regime = "LATERAL"
        try:
            candles = get_ohlcv(sym, "15m", 55)
            if candles and len(candles) >= 20:
                df = pd.DataFrame(candles, columns=["t", "o", "h", "l", "c", "v"])
                rsi_s = ta.momentum.RSIIndicator(close=df["c"], window=14).rsi()
                rsi = float(rsi_s.iloc[-1]) if not rsi_s.empty and pd.notna(rsi_s.iloc[-1]) else 50.0
                ema_s = ta.trend.EMAIndicator(close=df["c"], window=20).ema_indicator()
                ema_val = float(ema_s.iloc[-1]) if not ema_s.empty and pd.notna(ema_s.iloc[-1]) else px
                vol_mean = float(df["v"].iloc[-21:-1].mean() or 1.0)
                rvol = float(df["v"].iloc[-1] / vol_mean) if vol_mean > 0 else 1.0
                regime = "ALCISTA" if px >= ema_val else "BAJISTA"
        except Exception:
            pass

        # Diagnóstico en español
        if sym in active_syms:
            reason = "🔵 Posición abierta en ejecución táctica"
        elif rsi >= 70.0:
            reason = f"🟠 Frenado por sobrecompra (RSI {rsi:.1f})"
        elif rsi <= 30.0:
            reason = f"🟡 En sobreventa extrema (RSI {rsi:.1f})"
        elif rvol < 0.35:
            reason = f"⚪ En espera por bajo volumen (RVOL {rvol:.2f})"
        elif regime == "ALCISTA":
            reason = f"🟢 Estructura alcista sobre EMA (RVOL {rvol:.2f})"
        else:
            reason = f"🔴 Presión bajista bajo EMA (RVOL {rvol:.2f})"

        return {
            "symbol": sym,
            "price": px,
            "change_24h": round(chg, 2),
            "rsi": round(rsi, 1),
            "rvol": round(rvol, 2),
            "regime": regime,
            "has_position": sym in active_syms,
            "reason": reason,
        }

    with ThreadPoolExecutor(max_workers=5) as pool:
        items = list(pool.map(_eval_symbol, symbols))

    result = {
        "status": "ok",
        "timestamp": int(now * 1000),
        "items": items,
    }

    with _RADAR_OVERVIEW_LOCK:
        _RADAR_OVERVIEW_CACHE = {
            "data": result,
            "expires_at": now + 15.0,
        }

    return result

# --- PUENTE CON MONITOR DEL MERCADO (PROYECTO EXTERNO) ---
INJECTED_MACRO: Dict[str, Any] = {
    "id": None,
    "asset": "",
    "text": "",
    "confidence": 75,
    "type": "Oportunidad",
    "source": "Monitor de Mercado",
    "timestamp": None
}

@app.post("/api/macro/inject")
def inject_macro_from_monitor(data: MacroInjectionRequest, request: Request, x_api_token: Optional[str] = Header(None)):
    """
    Recibe la oportunidad y tesis macro validada desde el proyecto independiente Monitor del Mercado.
    Registra la tarjeta en el Buzón Persistente (buzon_radar.json) y actualiza el estado inyectado en vivo.
    """
    global INJECTED_MACRO
    verify_auth_token(request, x_api_token)
    import uuid
    from backend.radar_inbox import RadarInbox, OpportunityCard, parse_iso_timestamp

    asset = data.asset.strip().upper()
    text = data.text.strip()
    if not asset or not text:
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios: 'asset' y 'text'")

    conf = int(data.confidence)
    raw_type = data.type.strip()
    impact = "POSITIVO" if raw_type.upper() in ["OPORTUNIDAD", "POSITIVO"] else ("NEGATIVO" if raw_type.upper() in ["PELIGRO", "NEGATIVO"] else "NEUTRAL")
    if data.timestamp:
        try:
            ts = parse_iso_timestamp(data.timestamp).isoformat()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="El campo 'timestamp' debe ser una fecha ISO-8601 válida.") from exc
    else:
        ts = datetime.now().astimezone().isoformat()
    card_id = data.id or str(uuid.uuid4())

    INJECTED_MACRO = {
        "id": card_id,
        "asset": asset,
        "text": text,
        "confidence": conf,
        "type": raw_type,
        "source": data.source,
        "timestamp": ts
    }

    # Guardar también en el buzón persistente
    try:
        inbox = RadarInbox()
        inbox.add_card(OpportunityCard(
            id=card_id,
            timestamp=ts,
            activo=asset,
            titular=f"Alerta Monitor: {asset} ({raw_type})",
            impacto=impact,
            confianza=conf,
            justificacion=text[:300]
        ))
    except Exception as e:
        print(f"Advertencia guardando en buzón radar: {e}")

    # Guardar en el Buffer de Sesgo Macro con Latencia de Absorción (TTL 2.5h)
    try:
        from backend.macro_bias_buffer import MacroBiasBuffer
        MacroBiasBuffer().set_bias(
            symbol=asset,
            bias=impact,
            confidence=conf,
            thesis=text,
            ttl_hours=2.5,
            source=data.source or "Monitor del Mercado (CIO)",
        )
    except Exception as e:
        print(f"Advertencia guardando en macro_bias_buffer: {e}")

    return {
        "status": "ok",
        "message": f"Directiva macro inyectada con éxito para {asset}.",
        "data": INJECTED_MACRO
    }

@app.get("/api/macro/current_injected")
def get_current_injected_macro(request: Request, x_api_token: Optional[str] = Header(None)):
    """Permite al frontend consultar la directiva activa más reciente: inyección manual del CIO o auto-promoción de alertas frescas (>=80% confianza) desde buzon_radar.json."""
    global INJECTED_MACRO
    verify_auth_token(request, x_api_token)
    from backend.radar_inbox import RadarInbox, parse_iso_timestamp
    
    injected_ts = None
    if INJECTED_MACRO and INJECTED_MACRO.get("timestamp"):
        try:
            injected_ts = parse_iso_timestamp(INJECTED_MACRO.get("timestamp")).timestamp()
        except Exception:
            pass

    # Evaluar la alerta fresca más calificada en el buzón satélite
    best_monitor_card = None
    best_monitor_ts = None
    try:
        cards = RadarInbox().get_active_cards(hours_ttl=int(math.ceil(RADAR_TTL_HOURS)))
        for c in reversed(cards):
            raw_imp = str(c.impacto).strip().upper()
            is_opp = raw_imp in ["POSITIVO", "OPORTUNIDAD"]
            c_asset = str(c.activo or "").strip().upper()
            if is_opp and c.confianza >= 80 and c_asset and c_asset not in {"GENERAL", "NONE", "N/A"}:
                try:
                    c_ts = parse_iso_timestamp(c.timestamp).timestamp()
                    best_monitor_card = c
                    best_monitor_ts = c_ts
                    break
                except Exception:
                    continue
    except Exception as e:
        print(f"Advertencia evaluando auto-promoción en buzon_radar: {e}")

    # Prioridad por timestamp: si la alerta del monitor es más nueva que la inyección previa, auto-promoverla
    if best_monitor_card and best_monitor_ts:
        if not injected_ts or best_monitor_ts > injected_ts:
            return {
                "id": best_monitor_card.id,
                "asset": best_monitor_card.activo,
                "text": best_monitor_card.justificacion or best_monitor_card.titular,
                "confidence": best_monitor_card.confianza,
                "type": "Oportunidad",
                "source": "Monitor del Mercado (Auto)",
                "timestamp": best_monitor_card.timestamp
            }

    if INJECTED_MACRO and INJECTED_MACRO.get("timestamp"):
        return INJECTED_MACRO

    if best_monitor_card:
        return {
            "id": best_monitor_card.id,
            "asset": best_monitor_card.activo,
            "text": best_monitor_card.justificacion or best_monitor_card.titular,
            "confidence": best_monitor_card.confianza,
            "type": "Oportunidad",
            "source": "Monitor del Mercado (Auto)",
            "timestamp": best_monitor_card.timestamp
        }

    return INJECTED_MACRO


@app.post("/api/kula/market-context")
def set_kula_market_context(context: MarketContextContract, request: Request, x_api_token: Optional[str] = Header(None)):
    """
    Recibe y valida el contrato estricto de contexto de mercado emitido por Balam (Punto 1).
    Persiste en disco (data/market_context.json) y actualiza el caché en memoria para Kula.
    """
    verify_auth_token(request, x_api_token)
    save_market_context(context)
    return {
        "status": "ok",
        "message": f"Contrato de contexto de mercado actualizado para {context.ticker}.",
        "data": context.model_dump()
    }


@app.get("/api/kula/market-context")
def get_kula_market_context(request: Request, x_api_token: Optional[str] = Header(None)):
    """Devuelve el contrato de contexto de mercado activo para Kula."""
    verify_auth_token(request, x_api_token)
    ctx = load_market_context()
    if ctx is None:
        return {"status": "empty", "data": None}
    return {"status": "ok", "data": ctx.model_dump()}



@app.get("/api/monitor/scan-suggestions")
def get_monitor_scan_suggestions():
    """
    Retorna el informe más reciente de escaneo de Monitor del Mercado (puerto 8520 o reportes en disco)
    con las sugerencias de estudio de velas para el terminal del CIO.
    """
    import urllib.request
    import json
    from pathlib import Path
    from datetime import datetime

    # 1. Intentar consulta HTTP al servidor local de Monitor del Mercado (puerto 8520)
    try:
        req = urllib.request.Request("http://127.0.0.1:8520/api/reports/latest", headers={"Accept": "application/json", "Host": "127.0.0.1:8520"})
        with urllib.request.urlopen(req, timeout=1.8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return {"status": "ok", "source": "monitor_http_8520", "report": data}
    except Exception:
        pass

    # 2. Intentar lectura directa del último reporte en disco
    try:
        from backend.main import BASE_DIR
        monitor_dir = BASE_DIR.parent / "monitor del mercado"
        reports_dir = monitor_dir / "reportes"
        if reports_dir.exists():
            all_reports = sorted(reports_dir.glob("*/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if all_reports:
                latest_md = all_reports[0]
                text = latest_md.read_text(encoding="utf-8")
                return {
                    "status": "ok",
                    "source": "monitor_disk_reports",
                    "report": {
                        "timestamp": datetime.fromtimestamp(latest_md.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "name": latest_md.name,
                        "raw_snippet": text[:1500]
                    }
                }
    except Exception:
        pass

    return {"status": "fallback", "source": "default", "message": "Monitor del mercado no disponible"}


@app.get("/api/macro/bias-buffer")
def get_macro_bias_buffer():
    """
    Retorna el estado de los sesgos macro tácticos vigentes en el Buffer con Latencia de Absorción (TTL 2.5h).
    """
    from backend.macro_bias_buffer import MacroBiasBuffer
    buffer = MacroBiasBuffer()
    return {
        "status": "ok",
        "active_biases": buffer.get_all_active(),
    }


# --- MACRO RADAR Y BUZÓN (PASIVO MONITOR DEL MERCADO) ---
@app.get("/api/macro/radar")
def get_macro_radar(
    request: Request,
    engine: str = "local",
    source: str = "monitor",
    model: Optional[str] = None,
    x_api_token: Optional[str] = Header(None),
):
    verify_auth_token(request, x_api_token)
    try:
        from backend.radar_inbox import RadarInbox
        inbox = RadarInbox()
        active_cards = inbox.get_active_cards(hours_ttl=72)
        if active_cards:
            res = []
            for c in reversed(active_cards):
                res.append({
                    "asset": c.activo,
                    "type": "Oportunidad" if c.impacto == "POSITIVO" else ("Peligro" if c.impacto == "NEGATIVO" else "Neutral"),
                    "confidence": c.confianza,
                    "reason": c.justificacion,
                    "titular": c.titular,
                    "schedule": "Inmediato",
                    "source": "Monitor de Mercado"
                })
            return res
        else:
            return [{"asset": "MONITOR_ESPERA", "type": "Neutral", "confidence": 0, "reason": "Buzón satélite vacío. Listo para recibir alertas desde Monitor de Mercado.", "schedule": "-", "source": "Monitor de Mercado"}]
    except Exception as e:
        return [{"asset": "SYS_ERR", "type": "Peligro", "confidence": 0, "reason": str(e), "schedule": "-"}]


def _attach_multitemporal_frames(
    ind: Dict[str, Any],
    symbol: str,
    timeframe: str,
    df: Any,
    strategy: str,
    allowed_strategies: Optional[List[str]],
) -> None:
    """
    Adjunta df_1h y df_1d reales a `ind` cuando Kula Balam (o Piloto Automático) los requiere
    para validar la Tríada 1D-1H-5M sin sesgo ni fallos en mocks de test de 1 sola temporalidad.
    """
    import pandas as pd

    needs_mtf = (
        strategy == "kula_balam_cava_ruiz"
        or "kula_balam_cava_ruiz" in (allowed_strategies or [])
        or strategy == "auto"
    )
    if not needs_mtf:
        return

    if timeframe == "1h":
        ind["df_1h"] = df
    elif timeframe == "1d":
        ind["df_1d"] = df

    expected_min_spacing_ms = {"1h": 1_800_000, "1d": 43_200_000}
    for tf_need in ("1h", "1d"):
        key = f"df_{tf_need}"
        if key in ind and ind[key] is not None:
            continue
        try:
            raw_tf = get_ohlcv(symbol, tf_need, 120)
            closed_tf = _closed_ohlcv_data(raw_tf, symbol, tf_need)
            if len(closed_tf) < 25:
                continue
            df_tf = pd.DataFrame(closed_tf, columns=["timestamp", "open", "high", "low", "close", "volume"])
            median_diff = df_tf["timestamp"].diff().median()
            if pd.isna(median_diff) or float(median_diff) < expected_min_spacing_ms[tf_need]:
                continue
            ind[key] = df_tf
        except Exception:
            continue


def _resolve_active_macro_directive(symbol: str, has_position: bool = False) -> Dict[str, Any]:
    """Unifica inyección macro en memoria, buzon_radar.json, MacroBiasBuffer y MarketContextContract para CIO/Operador."""
    from backend.radar_inbox import RadarInbox
    from backend.macro_bias_buffer import MacroBiasBuffer
    from backend.market_context import get_active_market_context_for_symbol

    norm_sym = symbol.replace("/", "-").upper()
    base_asset = symbol.split("/")[0].upper()
    sym_upper = symbol.upper()
    is_crypto = "/" in symbol
    valid_tokens = {norm_sym, base_asset, sym_upper, "GENERAL"}
    if is_crypto:
        valid_tokens.add("CRYPTO")
    direct_tokens = {norm_sym, base_asset, sym_upper}

    cio_card = None
    veto_reason: Optional[str] = None
    operator_focus: Optional[str] = None

    if INJECTED_MACRO and INJECTED_MACRO.get("asset"):
        inj_asset = str(INJECTED_MACRO.get("asset", "")).strip().upper()
        if inj_asset in valid_tokens:
            expired = (not has_position) and bool(cio_directive_failures("", INJECTED_MACRO.get("timestamp"), 0.0))
            if not expired:
                inj_type = str(INJECTED_MACRO.get("type", "")).strip().upper()
                inj_text = str(INJECTED_MACRO.get("text", "")).strip()
                if inj_type in ("PELIGRO", "ALERTA", "VETO", "NEGATIVO"):
                    veto_reason = inj_text or "Alerta macro activa"
                    cio_card = INJECTED_MACRO
                elif inj_type == "DIRECTIVA DE OPERADOR":
                    txt_l = inj_text.lower()
                    if any(k in txt_l for k in ("veto", "bloquear", "no operar", "peligro")):
                        veto_reason = inj_text
                    else:
                        if inj_asset in direct_tokens:
                            operator_focus = inj_text
                        cio_card = INJECTED_MACRO
                else:
                    cio_card = INJECTED_MACRO

    try:
        cards = RadarInbox().get_active_cards(hours_ttl=int(math.ceil(RADAR_TTL_HOURS)))
        for c in reversed(cards):
            c_asset = str(c.activo or "").strip().upper()
            if c_asset not in direct_tokens or c.confianza < 75:
                continue
            c_imp = str(c.impacto or "").strip().upper()
            c_text = (c.justificacion or c.titular or "").strip()
            if c_imp in ("NEGATIVO", "PELIGRO", "VETO", "ALERTA"):
                if not veto_reason:
                    veto_reason = c_text or f"Alerta Radar {c.activo} ({c.confianza}%)"
                if not cio_card:
                    cio_card = {
                        "asset": c.activo,
                        "text": c_text,
                        "confidence": c.confianza,
                        "type": c.impacto,
                        "timestamp": c.timestamp,
                    }
                break
            if not cio_card and c_imp in ("POSITIVO", "OPORTUNIDAD"):
                cio_card = {
                    "asset": c.activo,
                    "text": c_text,
                    "confidence": c.confianza,
                    "type": c.impacto,
                    "timestamp": c.timestamp,
                }
                break
    except Exception:
        pass

    try:
        active_bias = MacroBiasBuffer().get_bias(symbol)
        if active_bias:
            b_type = str(active_bias.get("bias", "")).upper()
            if b_type in ("NEGATIVO", "PELIGRO", "VETO") and not veto_reason:
                veto_reason = str(active_bias.get("thesis") or f"Sesgo macro NEGATIVO en buffer ({active_bias.get('source', 'CIO')})").strip()
    except Exception:
        pass

    kula_ctx = get_active_market_context_for_symbol(symbol)
    return {
        "card": cio_card,
        "veto": veto_reason,
        "operator_focus": operator_focus,
        "kula_context": kula_ctx,
    }


def _kula_context_veto(kula_ctx: Any, desired_signal: str) -> Optional[str]:
    """Evalúa veto direccional/estructural a partir del MarketContextContract vigente."""
    if kula_ctx is None:
        return None
    if getattr(kula_ctx, "veto_active", False):
        return f"Contrato Kula con veto activo para {kula_ctx.ticker} (régimen: {kula_ctx.regime})"
    side_needed = "SHORT" if str(desired_signal).upper() == "SHORT" else "LONG"
    bias = str(getattr(kula_ctx, "macro_bias", "NEUTRAL") or "NEUTRAL").upper()
    if bias in ("LONG", "SHORT") and bias != side_needed:
        return f"Sesgo macro 1D del Contrato Kula ({bias}) incompatible con {side_needed} en {kula_ctx.ticker}"
    return None


def _compute_session_clock(now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    """Calcula la sesión bursátil real en America/New_York (DST-aware) convertida a hora Argentina (ART UTC-3)."""
    from zoneinfo import ZoneInfo

    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    arg_tz = timezone(timedelta(hours=-3))
    ny_tz = ZoneInfo("America/New_York")
    now_art = now_utc.astimezone(arg_tz)
    now_ny = now_utc.astimezone(ny_tz)
    ny_min = now_ny.hour * 60 + now_ny.minute
    weekday = now_ny.weekday()

    open_art_hm = now_ny.replace(hour=9, minute=30, second=0, microsecond=0).astimezone(arg_tz).strftime("%H:%M")
    blackout_end_art_hm = now_ny.replace(hour=9, minute=45, second=0, microsecond=0).astimezone(arg_tz).strftime("%H:%M")
    golden_art_hm = now_ny.replace(hour=10, minute=15, second=0, microsecond=0).astimezone(arg_tz).strftime("%H:%M")
    power_art_hm = now_ny.replace(hour=15, minute=0, second=0, microsecond=0).astimezone(arg_tz).strftime("%H:%M")
    close_art_hm = now_ny.replace(hour=16, minute=0, second=0, microsecond=0).astimezone(arg_tz).strftime("%H:%M")

    blackout_active = False
    if weekday < 5:
        if 9 * 60 + 30 <= ny_min < 9 * 60 + 45:
            session_name = f"Blackout de Apertura Wall Street ({open_art_hm} - {blackout_end_art_hm} ART)"
            blackout_active = True
            next_milestone = f"{blackout_end_art_hm} ART · Estabilización Post-Blackout ({golden_art_hm} Ventana Dorada)"
        elif 9 * 60 + 45 <= ny_min < 10 * 60 + 15:
            session_name = "Apertura Wall Street & Calibración Post-Blackout"
            next_milestone = f"{golden_art_hm} ART · Ventana Dorada Institucional CIO"
        elif 10 * 60 + 15 <= ny_min < 15 * 60:
            session_name = "Ventana Dorada & Sesión Regular Wall Street"
            next_milestone = f"{power_art_hm} ART · Power Hour Institucional"
        elif 15 * 60 <= ny_min < 16 * 60:
            session_name = "Power Hour Wall Street (Rebalanceo y Cierre)"
            next_milestone = f"{close_art_hm} ART · Cierre de Rueda Tradicional (16:00 NY)"
        elif ny_min >= 16 * 60:
            session_name = "Mercados Tradicionales Cerrados (Cripto 24/7 Activa)"
            next_milestone = "21:00 ART · Sesión Asiática (Tokio / HK)"
        else:
            session_name = "Pre-Market / Madrugada Wall Street"
            next_milestone = f"{open_art_hm} ART · Campana Regular Wall Street (09:30 NY)"
    else:
        session_name = "Fin de Semana Bursátil (Cripto 24/7 Activa)"
        next_milestone = f"Lunes {open_art_hm} ART · Campana Wall Street (09:30 NY)"

    return {
        "now_art": now_art,
        "now_ny": now_ny,
        "name": session_name,
        "blackout_active": blackout_active,
        "next_milestone": next_milestone,
        "ny_open_art": open_art_hm,
        "ny_close_art": close_art_hm,
    }


# --- MOTOR CUANTITATIVO Y ORQUESTADOR DE ANÁLISIS ---
@app.get("/api/market/analysis")
def get_analysis(
    request: Request,
    symbol: str = "BTC/USDT",
    timeframe: str = "1m",
    engine: str = "local",
    model: Optional[str] = None,
    strategy: str = "manual",
    tp: float = Query(3.0, gt=0, le=100, allow_inf_nan=False),
    sl: float = Query(1.0, gt=0, le=100, allow_inf_nan=False),
    risk: float = Query(1.0, ge=0, le=1, allow_inf_nan=False),
    sentiment: float = Query(0.0, ge=-1, le=1, allow_inf_nan=False),
    macro: str = "",
    fee: float = Query(0.1, ge=0, le=10, allow_inf_nan=False),
    spread: float = Query(0.05, ge=0, le=5, allow_inf_nan=False),
    min_profit_pct: float = Query(0.15, ge=0, le=5, allow_inf_nan=False),
    has_position: bool = False,
    entry_price: float = Query(0.0, ge=0, allow_inf_nan=False),
    position_side: str = "LONG",
    allowed_strategies: Optional[List[str]] = Query(None),
    x_api_token: Optional[str] = Header(None)
):
    verify_auth_token(request, x_api_token)
    validate_symbol(symbol)
    validate_timeframe(timeframe)
    if strategy not in get_supported_strategy_ids():
        raise HTTPException(status_code=422, detail="Estrategia no soportada.")
    if engine not in {"local", "ai", "gemini", "deepseek", "ollama", "qwen", "antigravity_cio", "antigravity_operador"}:
        raise HTTPException(
            status_code=422,
            detail="Este motor no está conectado como analista de señales de la Trinchera.",
        )
    if model and not re.match(r"^[a-zA-Z0-9_\-\.:]{1,64}$", model):
        raise HTTPException(status_code=422, detail="Nombre de modelo inválido.")
    allowed_tfs = get_allowed_timeframes(strategy)
    if timeframe not in allowed_tfs:
        raise HTTPException(
            status_code=422,
            detail=f"La estrategia '{strategy}' solo admite temporalidades {sorted(list(allowed_tfs))}. Recibido: '{timeframe}'."
        )

    # GET /api/market/analysis es estrictamente solo lectura (no muta ni inhibe al daemon de fondo).

    try:
        import pandas as pd

        fee = float(fee.default if hasattr(fee, "default") else fee)
        spread = float(spread.default if hasattr(spread, "default") else spread)
        query_params = None
        if request is not None and getattr(request, "client", None) != ("127.0.0.1", 12345):
            try:
                query_params = request.query_params
            except Exception:
                query_params = None
        from backend.quant_risk import is_micro_futures_symbol, get_asset_friction_costs
        if ("=X" in symbol.upper() or is_micro_futures_symbol(symbol)) and query_params is not None:
            if "fee" not in query_params or "spread" not in query_params:
                asset_costs = get_asset_friction_costs(symbol)
                if "fee" not in query_params:
                    fee = float(asset_costs["fee_pct"])
                if "spread" not in query_params:
                    spread = float(asset_costs["spread_pct"])
        tp = float(tp.default if hasattr(tp, "default") else tp)
        sl = float(sl.default if hasattr(sl, "default") else sl)
        min_profit_pct = float(min_profit_pct.default if hasattr(min_profit_pct, "default") else min_profit_pct)
        risk = float(risk.default if hasattr(risk, "default") else risk)
        sentiment = float(sentiment.default if hasattr(sentiment, "default") else sentiment)
        entry_price = float(entry_price.default if hasattr(entry_price, "default") else entry_price)
        position_side = str(position_side.default if hasattr(position_side, "default") else (position_side or "LONG")).upper()
        allowed_strategies = allowed_strategies.default if hasattr(allowed_strategies, "default") else allowed_strategies

        round_trip_fee = round(fee * 2.0, 3)
        round_trip_spread = round(spread * 2.0, 3)
        round_trip_cost = round(round_trip_fee + round_trip_spread, 3)
        net_tp = round(net_return_after_costs(tp, fee, spread), 4)
        target_tp_pct = round(max(float(net_tp), float(min_profit_pct)), 4)
        shared_directives = _shared_brain_directives() if engine != "local" else ""

        # Fees and spread are already deducted by net_return_after_costs.
        if strategy == "manual" and not has_position and net_tp < min_profit_pct:
            return {
                "symbol": symbol,
                "signal": "MANTENER",
                "reason": f"Filtro de beneficio mínimo: rentabilidad neta estimada ({net_tp}%) inferior al mínimo configurado ({min_profit_pct}%).",
                "fee_info": {
                    "fee_per_order": fee,
                    "round_trip_fee": round_trip_fee,
                    "spread_per_side": spread,
                    "round_trip_spread": round_trip_spread,
                    "round_trip_cost": round_trip_cost,
                    "net_tp": net_tp,
                    "min_profit_pct": min_profit_pct,
                    "viable": False,
                },
                "indicators": {"rsi": None, "sma_20": None, "sma_50": None, "current_price": None},
                "latest_candle": None
            }

        raw_ohlcv = get_ohlcv(symbol, timeframe, ANALYSIS_OHLCV_LIMIT)
        ohlcv = _closed_ohlcv_data(raw_ohlcv, symbol, timeframe)
        _validate_ohlcv_continuity(ohlcv, symbol, timeframe)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        if len(df) < MIN_ANALYSIS_CLOSED_CANDLES:
            current_close = float(df.iloc[-1]['close']) if not df.empty else None
            return {
                "symbol": symbol,
                "signal": "MANTENER",
                "reason": (
                    f"Historial insuficiente para análisis estable ({len(df)} velas cerradas; "
                    f"se requieren al menos {MIN_ANALYSIS_CLOSED_CANDLES} para calentar indicadores de largo plazo)."
                ),
                "fee_info": {
                    "fee_per_order": fee,
                    "round_trip_fee": round_trip_fee,
                    "spread_per_side": spread,
                    "round_trip_spread": round_trip_spread,
                    "round_trip_cost": round_trip_cost,
                    "net_tp": net_tp,
                    "min_profit_pct": min_profit_pct,
                    "viable": False,
                },
                "indicators": {"rsi": None, "sma_20": None, "sma_50": None, "current_price": current_close},
                "latest_candle": None
            }

        # Freshness is measured from the close of the last completed candle.
        tf_sec = TIMEFRAME_SECONDS[timeframe]
        latest_candle_open_ts_ms = int(df.iloc[-1]['timestamp'])
        latest_candle_close_ts_s = (latest_candle_open_ts_ms / 1000.0) + tf_sec
        last_candle_age_s = max(0, int(time.time() - latest_candle_close_ts_s))
        signal_candle_ts = int(latest_candle_open_ts_ms / 1000)

        # Si age > 3*timeframe_segundos => MANTENER por datos obsoletos / mercado cerrado
        if last_candle_age_s > (3 * tf_sec):
            return {
                "symbol": symbol,
                "signal": "MANTENER",
                "reason": f"Datos obsoletos / mercado cerrado (antigüedad de datos: {last_candle_age_s}s > {3 * tf_sec}s).",
                "data_age_s": last_candle_age_s,
                "signal_candle_ts": signal_candle_ts,
                "fee_info": {
                    "fee_per_order": fee,
                    "round_trip_fee": round_trip_fee,
                    "spread_per_side": spread,
                    "round_trip_spread": round_trip_spread,
                    "round_trip_cost": round_trip_cost,
                    "net_tp": net_tp,
                    "min_profit_pct": min_profit_pct,
                    "viable": False,
                },
                "indicators": {"rsi": None, "sma_20": None, "sma_50": None, "current_price": float(df.iloc[-1]['close'])},
                "latest_candle": None
            }

        ind = compute_technical_indicators(df)
        ind["timeframe"] = timeframe
        live_px = None
        try:
            live_px = float(get_cached_price(symbol).get("price"))
        except Exception:
            if raw_ohlcv:
                live_px = float(raw_ohlcv[-1][4])
        closed_close = float(ind["latest"]["close"])
        ind["spot_live_price"] = live_px
        # Nuevas entradas evalúan estrictamente el cierre confirmado de la vela cerrada (sin fuga de tick en vela abierta).
        ind["live_price"] = live_px if has_position else closed_close
        ind["closed_candle_only"] = not has_position
        ind["symbol"] = symbol
        _attach_multitemporal_frames(ind, symbol, timeframe, df, strategy, allowed_strategies)
        latest = ind["latest"]
        previous = ind["previous"]
        current_price_real = ind["current_price_real"]
        ema_200_value = ind["ema_200_value"]
        ema_200_slope_pct = ind["ema_200_slope_pct"]
        lower_wick_ratio = ind["lower_wick_ratio"]
        lower_wick_ratio_val = ind["lower_wick_ratio_val"]
        z_score = ind["z_score"]
        atr_14 = ind["atr_14"]
        relative_volume = ind["relative_volume"]

        (
            strategy_metrics,
            net_tp,
            quant_candidate_eligible,
            quant_filter_failures,
            minimum_strategy_net_tp,
        ) = evaluate_strategy_metrics(
            strategy=strategy,
            ind=ind,
            tp=tp,
            sl=sl,
            fee=fee,
            spread=spread,
            min_profit_pct=min_profit_pct,
            round_trip_cost=round_trip_cost,
            net_tp_manual=net_tp,
            df=df,
            allowed_strategies=allowed_strategies,
        )
        tp_gross_pct = strategy_metrics.get("tp_gross_pct", tp)
        sl_gross_pct = strategy_metrics.get("sl_gross_pct", sl)
        strategy_net_tp = strategy_metrics.get("tp_net_pct", net_tp)
        strategy_net_sl = strategy_metrics.get(
            "sl_net_pct", round(net_return_after_costs(-sl, fee, spread), 4)
        )
        effective_strategy = (
            strategy_metrics.get("auto_orchestrator", {}).get("selected_strategy", strategy)
            if isinstance(strategy_metrics, dict)
            else strategy
        )
        is_quant_strategy = effective_strategy not in ("manual", "auto")
        prompt_tp = tp_gross_pct if is_quant_strategy and tp_gross_pct is not None else tp
        prompt_sl = sl_gross_pct if is_quant_strategy and sl_gross_pct is not None else sl
        quant_prompt_block = ""
        expected_sig = strategy_metrics.get("suggested_signal", "COMPRAR")
        if is_quant_strategy and quant_candidate_eligible and not has_position and engine != "local":
            quant_prompt_block = (
                f"\nMODO AUDITOR CUANTITATIVO: Python ya calculó todas las métricas y habilitó una candidata {expected_sig}. "
                "No recalcules métricas ni inventes datos. Tu única autoridad es vetar (responde MANTENER) si ves una "
                "contradicción contextual clara, datos/tesis inconsistentes o riesgo excepcional. No puedes autorizar "
                f"una compra si Python no la habilitó ni cambiar las reglas de costos/riesgo. Si no hay motivo concreto "
                f"para vetar, devuelve {expected_sig}. Devuelve el JSON del formato solicitado.\n"
                f"Métricas deterministas: {strategy_metrics}\n"
            )

        signal = "MANTENER"
        reason = "El mercado está en zona neutral."

        price_real = float(latest['close'])
        px_dec = 5 if ("=X" in symbol.upper() or 0 < price_real < 10.0) else 2
        rsi_val = round(latest['rsi'], 2)
        sma20_val = round(latest['sma_20'], px_dec)
        price_val = round(price_real, px_dec)
        macd_curr = latest['macd_diff']
        macd_prev = previous['macd_diff']
        bb_low = latest['bb_low']
        bb_high = latest['bb_high']
        vwap_val = latest['vwap'] if not pd.isna(latest['vwap']) else price_real

        # Auditor Cuantitativo Determinista de Velas y Buffer de Sesgo Macro (0 Tokens)
        from backend.candlestick_auditor import audit_candlestick_confluence
        candlestick_audit = audit_candlestick_confluence(
            symbol=symbol,
            df=df,
            ind=ind,
            fee=fee,
            spread=spread,
            min_profit_pct=min_profit_pct,
        )

        if engine != "local" and not has_position:
            try:
                from backend.verificador_evolutivo import obtener_precedentes_ganadores
                vwap_diff_pct_now = ((price_real - float(vwap_val)) / float(vwap_val)) * 100.0 if float(vwap_val) > 0 else 0.0
                eff_strat_name = effective_strategy
                precedentes_txt = obtener_precedentes_ganadores(
                    strategy_name=eff_strat_name,
                    rsi_actual=float(rsi_val),
                    vwap_diff_actual=vwap_diff_pct_now,
                    ema_slope_actual=float(ema_200_slope_pct or 0.0),
                    wick_actual=float(lower_wick_ratio or 0.0),
                    limite=3,
                )
                if precedentes_txt:
                    quant_prompt_block = f"{quant_prompt_block}\n{precedentes_txt}\n"
            except Exception:
                pass

        # Estrategias cuantitativas modulares: filtrado determinista previo
        if is_quant_strategy and not has_position and not quant_candidate_eligible and engine != "antigravity_operador":
            strat_label = f"Piloto Automático · {effective_strategy}" if strategy == "auto" else effective_strategy
            prefix = "Filtro cuantitativo ATR: " if effective_strategy == "mean_reversion_atr" else f"Filtro determinista ({strat_label}): "
            failure_msg = "; ".join(quant_filter_failures) if quant_filter_failures else (strategy_metrics.get("policy") or "Filtros técnicos no cumplidos")
            signal = "MANTENER"
            reason = prefix + failure_msg
        elif effective_strategy == "mean_reversion_atr" and not has_position and engine == "local":
            signal = "COMPRAR"
            setup_lbl = strategy_metrics.get("setup") or "Setup Cuantitativo ATR"
            reason = (
                f"Candidata cuantitativa válida ({setup_lbl}): Z-Score {z_score:.2f}, "
                f"absorción {lower_wick_ratio:.2f}, RVOL {relative_volume:.2f}; "
                f"TP neto estimado +{strategy_net_tp:.3f}% y SL neto {strategy_net_sl:.3f}%."
            )
        elif is_quant_strategy and not has_position and engine == "local":
            signal = strategy_metrics.get("suggested_signal", "COMPRAR")
            policy_desc = strategy_metrics.get("policy") or "Todos los filtros técnicos superados."
            reason = f"Candidata determinista aprobada ({effective_strategy}): {policy_desc}"
        elif engine == "local":
            signal, reason = evaluate_local_engine_signal(
                has_position=has_position,
                entry_price=entry_price,
                price_val=price_val,
                vwap_val=vwap_val,
                rsi_val=rsi_val,
                macd_prev=macd_prev,
                macd_curr=macd_curr,
                bb_low=bb_low,
                bb_high=bb_high,
                net_tp=net_tp,
                min_profit_pct=min_profit_pct,
            )

        # --- MOTOR ANTIGRAVITY CIO & OPERADOR TÁCTICO (CAPA UNIFICADA) ---
        elif engine in ("antigravity_cio", "antigravity_operador"):
            macro_state = _resolve_active_macro_directive(symbol, has_position=has_position)
            cio_card = macro_state["card"]
            macro_veto = macro_state["veto"]
            operator_focus = macro_state["operator_focus"]
            kula_ctx = macro_state["kula_context"]

            current_pnl_net_pct = (
                round(net_pnl_pct_from_prices(entry_price, price_real, fee, spread, side=position_side), 3)
                if (has_position and entry_price > 0)
                else 0.0
            )
            daemon_paused = False
            pause_msg = ""
            try:
                from backend.daemon import get_trader_daemon
                td = get_trader_daemon()
                daemon_paused = bool(getattr(td, "paused_new_entries", False))
                pause_msg = str(getattr(td, "pause_reason", "") or "Apertura pausada por operador.")
            except Exception:
                pass

            engine_label = "Antigravity CIO" if engine == "antigravity_cio" else "Antigravity Operador"
            if has_position:
                if current_pnl_net_pct >= target_tp_pct:
                    signal = "VENDER"
                    reason = f"[{engine_label}]: Objetivo Take Profit alcanzado (+{current_pnl_net_pct:.2f}% neto >= +{target_tp_pct:.2f}%). Cierre táctico autorizado."
                elif strategy_metrics.get("suggested_exit", False):
                    signal = "VENDER"
                    reason = f"[{engine_label}]: Salida táctica por estrategia {effective_strategy}: señal de salida confirmada. Cierre autorizado."
                else:
                    signal = "MANTENER"
                    conf_txt = f" ({cio_card['confidence']}% conf)" if cio_card else ""
                    reason = f"[{engine_label}]: Posición activa en ${entry_price:,.{px_dec}f} (PnL neto {current_pnl_net_pct:+.2f}%). Sosteniendo hacia objetivo +{target_tp_pct:.2f}%{conf_txt}."
            elif daemon_paused:
                signal = "MANTENER"
                reason = f"[{engine_label} · Pausa Operador]: {pause_msg}"
            elif macro_veto:
                signal = "MANTENER"
                if engine == "antigravity_cio":
                    reason = f"[Antigravity CIO]: Directiva de Alerta/Peligro detectada para {symbol}. Compras vetadas: {macro_veto}."
                else:
                    reason = f"[Antigravity Operador · Veto Macro]: {macro_veto}. Operación bloqueada por prudencia institucional."
            elif engine == "antigravity_cio":
                if not cio_card:
                    signal = "MANTENER"
                    reason = (
                        f"[Antigravity CIO]: Sin directiva macro de alta convicción activa para {symbol} "
                        "en el Monitor del Mercado (puerto 8520). Preservando 100% liquidez en caja."
                    )
                else:
                    conf = int(cio_card.get("confidence", 80))
                    c_type = str(cio_card.get("type", "Oportunidad")).upper()
                    c_text = str(cio_card.get("text", "")).strip()
                    is_directive_op = c_type == "DIRECTIVA DE OPERADOR"
                    is_bullish = c_type in ("OPORTUNIDAD", "POSITIVO") or is_directive_op

                    if not is_bullish:
                        signal = "MANTENER"
                        reason = f"[Antigravity CIO]: Directiva de Alerta/Peligro detectada para {symbol} ({conf}% conf). Compras vetadas."
                    else:
                        cio_failures = cio_directive_failures(c_text, cio_card.get("timestamp"), price_real)
                        desired_side = strategy_metrics.get("suggested_signal", "COMPRAR")
                        ctx_veto = _kula_context_veto(kula_ctx, desired_side)

                        if cio_failures:
                            signal = "MANTENER"
                            reason = f"[Antigravity CIO · Revalidación]: {' '.join(cio_failures)}"
                        elif ctx_veto:
                            signal = "MANTENER"
                            reason = f"[Antigravity CIO · Contexto Kula]: {ctx_veto}."
                        elif is_quant_strategy and quant_candidate_eligible:
                            signal = desired_side
                            setup_lbl = strategy_metrics.get("setup") or effective_strategy
                            reason = f"[Antigravity CIO · {setup_lbl}]: Tesis macro/directiva activa ({conf}% conf) + confluencia cuantitativa ({signal})."
                        elif candlestick_audit.get("eligible"):
                            signal = "COMPRAR"
                            reason = f"[Antigravity CIO · {candlestick_audit['verdict']}]: {candlestick_audit['reason']}"
                        else:
                            signal = "MANTENER"
                            reason = (
                                f"[Antigravity CIO · Latencia de Absorción]: Tesis activa ({conf}% conf), "
                                f"pero velas aún sin confirmar ({candlestick_audit['verdict']}). {candlestick_audit['reason']}"
                            )
            else:
                desired_side = strategy_metrics.get("suggested_signal", "COMPRAR") if is_quant_strategy else "COMPRAR"
                ctx_veto = _kula_context_veto(kula_ctx, desired_side)

                focus_note = f" [Directiva Operador: {operator_focus}]" if operator_focus else ""
                if ctx_veto:
                    signal = "MANTENER"
                    reason = f"[Antigravity Operador · Contexto Kula]: {ctx_veto}.{focus_note}"
                elif is_quant_strategy:
                    if quant_candidate_eligible:
                        signal = desired_side
                        setup_lbl = strategy_metrics.get("setup") or effective_strategy
                        sl_mag = abs(strategy_net_sl or 1.0)
                        rr_ratio = round(strategy_net_tp / sl_mag, 2) if sl_mag > 0 else 2.0
                        reason = (
                            f"[Antigravity Operador · Ejecución Táctica]: Confluencia confirmada para {setup_lbl}. "
                            f"R:R neto {rr_ratio}x tras comisiones ({round_trip_cost}%). "
                            f"SL fuera del ruido ATR ({strategy_metrics.get('sl_gross_pct', sl):.2f}%). "
                            f"Orden de {signal} autorizada instantáneamente (0% CPU).{focus_note}"
                        )
                    else:
                        signal = "MANTENER"
                        fail_desc = "; ".join(quant_filter_failures) if quant_filter_failures else (strategy_metrics.get("policy") or "Filtros técnicos pendientes")
                        reason = f"[Antigravity Operador]: Esperando confluencia en {effective_strategy}. {candlestick_audit['verdict']}. Pendiente: {fail_desc}.{focus_note}"
                elif candlestick_audit.get("eligible"):
                    signal = "COMPRAR"
                    reason = f"[Antigravity Operador · {candlestick_audit['verdict']}]: {candlestick_audit['reason']}{focus_note}"
                elif candlestick_audit.get("verdict", "").startswith("[CHEQUEADO: ABSTENCIÓN"):
                    signal = "MANTENER"
                    reason = f"[Antigravity Operador]: {candlestick_audit['verdict']} - {candlestick_audit['reason']}{focus_note}"
                else:
                    loc_sig, loc_rsn = evaluate_local_engine_signal(
                        has_position=has_position,
                        entry_price=entry_price,
                        price_val=price_real,
                        vwap_val=vwap_val,
                        rsi_val=rsi_val,
                        macd_prev=macd_prev,
                        macd_curr=macd_curr,
                        bb_low=bb_low,
                        bb_high=bb_high,
                        net_tp=net_tp,
                        min_profit_pct=min_profit_pct,
                    )
                    signal = loc_sig
                    reason = f"[Antigravity Operador]: {loc_rsn}{focus_note}"

        # --- MOTOR 2: GEMINI AI ---
        elif engine in ("ai", "gemini"):
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key or api_key == "tu_clave_aqui_sin_comillas":
                signal = "ERROR"
                reason = "[AVISO] Falta GEMINI_API_KEY en ajustes. IA Desconectada."
            else:
                try:
                    import requests
                    import json
                    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
                    pos_info = f"Posición ACTIVA ya abierta a ${entry_price}." if has_position else "Sin posición abierta (100% liquidez)."
                    full_prompt = (
                        f"{shared_directives}\n\nEres un Senior Quantitative Trader Institucional operando algorítmicamente.\n"
                        f"El usuario opera en velas de {timeframe}, arriesgando el {int(risk * 100)}%.\n"
                        f"TP (+{prompt_tp}%) y SL (-{prompt_sl}%) son movimientos BRUTOS de precio. La rentabilidad neta estimada del TP tras costos es +{net_tp}%.\n\n"
                        f"COSTOS DEL BROKER:\n"
                        f"- Comisión por orden: {fee}%\n"
                        f"- Comisión ida y vuelta: {round_trip_fee}%\n"
                        f"- Spread estimado por lado: {spread}% (ida y vuelta: {round_trip_spread}%)\n"
                        f"- Costo total estimado ida y vuelta: {round_trip_cost}%\n"
                        f"- Ganancia neta proyectada al acierto: +{net_tp}%\n\n"
                        f"- Beneficio neto mínimo configurado para tomar ganancias: {min_profit_pct}%\n\n"
                        f"ESTADO DE POSICIÓN ACTUAL:\n"
                        f"- {pos_info}\n\n"
                        f"ESTRUCTURA TÉCNICA DEL ACTIVO {symbol}:\n"
                        f"- Precio: ${price_val} | VWAP: ${round(latest['vwap'], 2) if not pd.isna(latest['vwap']) else 'N/A'} | "
                        f"EMA200: ${round(ema_200_value, 2) if ema_200_value is not None else 'N/A'} (pendiente 5 velas: {round(ema_200_slope_pct, 4) if ema_200_slope_pct is not None else 'N/A'}%) | "
                        f"RSI(14): {rsi_val} | MACD: {round(latest['macd_diff'], 2) if not pd.isna(latest['macd_diff']) else 'N/A'}\n"
                        f"- Bandas Bollinger: Inf=${round(bb_low, 2) if not pd.isna(bb_low) else 'N/A'}, Sup=${round(bb_high, 2) if not pd.isna(bb_high) else 'N/A'} | "
                        f"Mecha inferior de vela cerrada (ratio del rango): {lower_wick_ratio_val}\n"
                        f"- Sentimiento del Mercado: {sentiment}\n\n"
                        f"CONTEXTO MACRO:\n{build_macro_directive(macro)}\n\n"
                        f"{quant_prompt_block}"
                        f"REGLAS ANTI-OVERTRADING:\n"
                        f"1. Si ya hay una posición abierta, está PROHIBIDO comprar de nuevo; responde MANTENER o VENDER.\n"
                        f"2. Si no hay posición, solo compra si el TP neto estimado alcanza el beneficio neto mínimo configurado ({min_profit_pct}%).\n"
                        f"3. Con posición abierta, no propongas una toma de ganancias si el PnL neto positivo no alcanza ese mínimo. Una salida por pérdida/invalidez de tesis sí puede proponerse; nunca retengas una posición para evitar un Stop Loss o cierre de protección.\n\n"
                        f'Tu respuesta debe ser EXCLUSIVAMENTE en formato JSON válido estricto sin markdown:\n'
                        f'{{"signal": "COMPRAR", "reason": "Justificación concisa"}}'
                    )

                    gem_url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
                    gem_payload = {
                        "contents": [{"parts": [{"text": full_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.0 if is_quant_strategy else 0.2,
                            "responseMimeType": "application/json"
                        }
                    }
                    gem_resp = requests.post(gem_url, json=gem_payload, timeout=12)
                    if gem_resp.status_code == 200:
                        gem_data = gem_resp.json()
                        raw_parts = gem_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
                        content_str = raw_parts[0].get("text", "").strip() if raw_parts else ""
                        json_match = re.search(r'\{.*\}', content_str, re.DOTALL)
                        if json_match:
                            ia_decision = json.loads(json_match.group(0))
                            signal = normalize_signal(ia_decision.get("signal", "MANTENER"))
                            reason = str(ia_decision.get("reason", "Decisión procesada por Gemini."))
                        else:
                            signal = "MANTENER"
                            reason = "Gemini no devolvió una estructura JSON válida."
                    elif gem_resp.status_code == 429:
                        loc_sig, loc_rsn = evaluate_local_engine_signal(
                            has_position=has_position,
                            entry_price=entry_price,
                            price_val=price_val,
                            vwap_val=vwap_val,
                            rsi_val=rsi_val,
                            macd_prev=macd_prev,
                            macd_curr=macd_curr,
                            bb_low=bb_low,
                            bb_high=bb_high,
                            net_tp=net_tp,
                            min_profit_pct=min_profit_pct,
                        )
                        signal = loc_sig
                        reason = f"[Fallback Cuantitativo por Cuota Gemini]: {loc_rsn}"
                    else:
                        signal = "ERROR"
                        reason = f"Gemini API HTTP {gem_resp.status_code}: {gem_resp.text[:120]}"
                except Exception as e:
                    signal = "ERROR"
                    reason = f"Error en el Agente Gemini: {str(e)}"

        # --- MOTORES LOCALES / RETIRADOS (MIGRACIÓN CUANTITATIVA) ---
        elif engine in ("deepseek", "ollama", "qwen"):
            loc_sig, loc_rsn = evaluate_local_engine_signal(
                has_position=has_position,
                entry_price=entry_price,
                price_val=price_val,
                vwap_val=vwap_val,
                rsi_val=rsi_val,
                macd_prev=macd_prev,
                macd_curr=macd_curr,
                bb_low=bb_low,
                bb_high=bb_high,
                net_tp=net_tp,
                min_profit_pct=min_profit_pct,
            )
            signal = loc_sig
            reason = f"[Motor Cuantitativo Local - {engine} migrado]: {loc_rsn}"

        # Fallback de Seguridad ante interrupción de IA (sin mutar brain_state.json en disco)
        if signal == "ERROR":
            err_reason = str(reason or "")
            if is_quant_strategy:
                signal = "MANTENER"
                reason = f"Auditor de IA (Veto / Fail-Safe): {err_reason}"
            else:
                loc_sig, loc_rsn = evaluate_local_engine_signal(
                    has_position=has_position,
                    entry_price=entry_price,
                    price_val=price_val,
                    vwap_val=vwap_val,
                    rsi_val=rsi_val,
                    macd_prev=macd_prev,
                    macd_curr=macd_curr,
                    bb_low=bb_low,
                    bb_high=bb_high,
                    net_tp=net_tp,
                    min_profit_pct=min_profit_pct,
                )
                signal = loc_sig
                reason = f"[Nivel 4 Matemático tras fallo en {engine}]: {loc_rsn}"

        # Red de seguridad final en servidor contra DCA / overtrading y Cuchillo Cayendo
        if signal != "ERROR":
            signal = normalize_signal(signal)
            if has_position and signal in ("COMPRAR", "SHORT"):
                signal = "MANTENER"
                reason = "Servidor: posición abierta detectada, compras/shorts bloqueados para evitar overtrading/DCA."
            elif not has_position and signal == "VENDER":
                signal = "MANTENER"
                reason = "Servidor: sin posición abierta, venta ignorada."
            elif (
                not has_position
                and signal == "COMPRAR"
                and not is_quant_strategy
                and rsi_val is not None
                and float(rsi_val) < 25.0
            ):
                signal = "MANTENER"
                reason = (
                    f"Filtro Anti-Cuchillo Cayendo (Servidor): Compra bloqueada en pleno desplome "
                    f"(RSI={rsi_val} < 25). Aunque la tesis macro sea favorable, se espera piso y giro confirmado."
                )
        if (
            is_quant_strategy
            and not has_position
            and quant_candidate_eligible
        ):
            target_signal = strategy_metrics.get("suggested_signal", "COMPRAR")
            if signal != target_signal:
                veto_reason = reason if reason else "El auditor de IA vetó o no confirmó la candidata cuantitativa."
                orig_signal = signal
                signal = "MANTENER"
                reason = f"Auditor de IA (Veto / Fail-Safe): {veto_reason}"

        # --- COMPUERTA DETERMINISTA DE ENTRADA (auditoría 19-oct-2026) ---
        # Python manda sobre cualquier motor: R:R neto, stop fuera del ruido ATR, volumen, apertura y anti-churn.
        gate_tp = float(tp_gross_pct) if tp_gross_pct is not None else float(tp)
        gate_sl = float(sl_gross_pct) if sl_gross_pct is not None else float(sl)
        rr_info = net_rr_metrics(gate_tp, gate_sl, fee, spread)
        if not has_position and signal in ("COMPRAR", "SHORT"):
            c_color = "RED" if (ind.get("close", 0) < ind.get("open", 0)) else "GREEN"
            gate_failures = entry_gate_failures(
                symbol,
                price_real,
                gate_tp,
                gate_sl,
                fee,
                spread,
                atr=atr_14,
                rvol=relative_volume,
                order_side="SHORT" if signal == "SHORT" else "BUY",
                lower_wick_ratio=float(lower_wick_ratio) if lower_wick_ratio is not None else None,
                candle_color=c_color,
                timeframe=timeframe,
            )
            try:
                from backend.daemon import get_trader_daemon

                recent_trades = get_trader_daemon().broker.fetch_trade_history(limit=30)
                churn_reason = churn_block_reason(
                    recent_trades,
                    symbol,
                    price_real,
                    timeframe_s=TIMEFRAME_SECONDS[timeframe],
                    z_score=z_score,
                )
                if churn_reason:
                    gate_failures.append(churn_reason)
            except Exception:
                pass
            if gate_failures:
                signal = "MANTENER"
                reason = "Compuerta de entrada: " + " | ".join(gate_failures)

        return {
            "symbol": symbol,
            "strategy": strategy,
            "signal": signal,
            "reason": reason,
            "data_age_s": last_candle_age_s,
            "signal_candle_ts": signal_candle_ts,
            "fee_info": {
                "fee_per_order": fee,
                "round_trip_fee": round_trip_fee,
                "spread_per_side": spread,
                "round_trip_spread": round_trip_spread,
                "round_trip_cost": round_trip_cost,
                "net_tp": net_tp,
                "min_profit_pct": min_profit_pct,
                "net_rr": rr_info.get("net_rr"),
                "min_net_rr": MIN_NET_RR,
                "breakeven_win_rate": rr_info.get("breakeven_win_rate"),
                "viable": net_tp >= minimum_strategy_net_tp and bool(rr_info.get("net_rr", 0) >= MIN_NET_RR)
            },
            "indicators": {
                "rsi": round(latest['rsi'], 2) if not pd.isna(latest['rsi']) else None,
                "sma_20": round(latest['sma_20'], px_dec) if not pd.isna(latest['sma_20']) else None,
                "sma_50": round(latest['sma_50'], px_dec) if not pd.isna(latest['sma_50']) else None,
                "ema_200": ema_200_value,
                "ema_200_slope_pct": ema_200_slope_pct,
                "current_price": current_price_real,
                "z_score": strategy_metrics.get("z_score"),
                "atr_14": strategy_metrics.get("atr_14"),
                "relative_volume": strategy_metrics.get("relative_volume"),
                "lower_wick_ratio": lower_wick_ratio
            },
            "strategy_metrics": strategy_metrics,
            "candlestick_audit": candlestick_audit,
            "btc_macro_status": get_btc_macro_status(),
            "latest_spot_price": round(live_px, px_dec) if live_px is not None else None,
            "entry_evaluation_mode": "live_exit" if has_position else "closed_candle_strict",
            "latest_candle": {
                "time": int(latest['timestamp'] / 1000),
                "open": latest['open'],
                "high": latest['high'],
                "low": latest['low'],
                "close": latest['close']
            }
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

# --- REGISTRO DE TRADES EN CSV CON MIGRACIÓN DE ENCABEZADO ANTIGUO (Bloque 5 item 9) ---
class TradeLogRequest(BaseModel):
    timeString: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=30)
    signal: str = Field(min_length=1, max_length=30)
    price: float = Field(gt=0, allow_inf_nan=False)
    status: str = Field(min_length=1, max_length=40)
    mode: str = Field(min_length=1, max_length=40)
    qty: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    fee: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    session_id: int = Field(default=1, ge=1)

@app.post("/api/log_trade")
def log_trade(trade: TradeLogRequest, request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    with CSV_LOCK:
        try:
            if os.path.isfile(CSV_FILE_PATH):
                with open(CSV_FILE_PATH, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                # Si el archivo tiene formato legacy (6 columnas o sin SessionId), migrarlo
                cols = [c.strip() for c in first_line.split(",")]
                if len(cols) == 6 or "SessionId" not in first_line:
                    try:
                        os.replace(CSV_FILE_PATH, CSV_LEGACY_PATH)
                    except Exception as m_err:
                        print(f"Aviso migrando CSV legacy: {m_err}")

            file_exists = os.path.isfile(CSV_FILE_PATH)
            with open(CSV_FILE_PATH, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                if not file_exists:
                    writer.writerow(["Time", "Symbol", "Signal", "Price", "Qty", "Fee", "Status", "Mode", "SessionId"])
                writer.writerow([trade.timeString, trade.symbol, trade.signal, trade.price, trade.qty, trade.fee, trade.status, trade.mode, trade.session_id])
            return {"status": "success", "message": "Trade logged successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail="No se pudo guardar el registro de la operación.") from e


# --- ENDPOINTS CONTABLES DE DOBLE PARTIDA Y CUENTAS ÓMNIBUS (SQLite) ---
@app.get("/api/ledger/state")
def get_ledger_state(request: Request, x_api_token: Optional[str] = Header(None)):
    """
    Expone el estado contable de doble partida en SQLite:
    Bóveda (VAULT), Billeteras Operativas (OPERATIONAL en $0.00 en reposo),
    posiciones abiertas, integridad contable y estado del Circuit Breaker por divisa.
    """
    verify_auth_token(request, x_api_token)
    from backend.db.ledger import get_default_ledger, SUPPORTED_CURRENCIES

    ledger = get_default_ledger()
    balances = ledger.get_omnibus_balances()
    integrity = ledger.verify_double_entry_integrity()
    risk_by_currency = {
        curr: ledger.check_circuit_breaker(curr) for curr in SUPPORTED_CURRENCIES
    }
    from backend.daemon import get_trader_daemon
    daemon = get_trader_daemon()
    trailing_telemetry = getattr(daemon, "counterfactual_cache", {})
    trailing_key_mode = getattr(daemon, "trailing_key_mode", "auto")
    time_decay_telemetry = getattr(daemon, "time_decay_cache", {})

    return {
        "status": "ok",
        "balances": balances,
        "open_positions": ledger.get_open_positions(),
        "risk_state": risk_by_currency,
        "double_entry_integrity": integrity,
        "trailing_telemetry": trailing_telemetry,
        "trailing_key_mode": trailing_key_mode,
        "time_decay_telemetry": time_decay_telemetry,
    }


@app.get("/api/trailing/telemetry")
def get_trailing_telemetry(request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    daemon = get_trader_daemon()
    return {
        "status": "ok",
        "trailing_key_mode": getattr(daemon, "trailing_key_mode", "auto"),
        "telemetry": getattr(daemon, "counterfactual_cache", {}),
    }


@app.get("/api/time_stop/telemetry")
def get_time_stop_telemetry(request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    daemon = get_trader_daemon()
    return {
        "status": "ok",
        "telemetry": getattr(daemon, "time_decay_cache", {}),
    }


@app.post("/api/trailing/key_mode")
def set_trailing_key_mode(request: Request, mode: str = "auto", x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    daemon = get_trader_daemon()
    clean_mode = str(mode or "auto").strip().lower()
    if clean_mode not in ("auto", "holgado", "comprimido"):
        clean_mode = "auto"
    daemon.trailing_key_mode = clean_mode
    return {
        "status": "ok",
        "trailing_key_mode": daemon.trailing_key_mode,
        "message": f"Modo de Llave Trailing Stop actualizado a: {daemon.trailing_key_mode.upper()}",
    }


@app.get("/api/ledger/audit")
@app.post("/api/ledger/audit")
def run_ledger_audit(request: Request, x_api_token: Optional[str] = Header(None)):
    """
    Ejecuta la auditoría forense de SQLite en tiempo real,
    actualiza el reporte de texto plano y devuelve el estado completo del ledger.
    """
    verify_auth_token(request, x_api_token)
    report_text = ""
    try:
        import sys
        if PROJECT_ROOT not in sys.path:
            sys.path.insert(0, PROJECT_ROOT)
        from auditar_sqlite import auditar
        report_text = auditar() or ""
    except Exception as e:
        logger.warning(f"Error al ejecutar auditar_sqlite en /api/ledger/audit: {e}")

    from backend.db.ledger import get_default_ledger, SUPPORTED_CURRENCIES
    ledger = get_default_ledger()
    balances = ledger.get_omnibus_balances()
    integrity = ledger.verify_double_entry_integrity()
    risk_by_currency = {
        curr: ledger.check_circuit_breaker(curr) for curr in SUPPORTED_CURRENCIES
    }

    if not report_text:
        txt_path = os.path.join(PROJECT_ROOT, "frontend", "ultimo_reporte_boveda.txt")
        if os.path.exists(txt_path):
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    report_text = f.read()
            except Exception:
                pass

    from backend.daemon import get_trader_daemon
    daemon = get_trader_daemon()

    return {
        "status": "ok",
        "message": "Auditoría SQLite ejecutada en tiempo real",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "balances": balances,
        "open_positions": ledger.get_open_positions(),
        "risk_state": risk_by_currency,
        "double_entry_integrity": integrity,
        "trailing_telemetry": getattr(daemon, "counterfactual_cache", {}),
        "trailing_key_mode": getattr(daemon, "trailing_key_mode", "auto"),
        "report_text": report_text,
    }


@app.get("/api/audit/campaign")
def get_campaign_audit(
    since: Optional[str] = Query(None),
    include_presencial: bool = Query(True),
):
    """Devuelve la auditoría cuantitativa read-only de la campaña (auto vs operador_presente)."""
    from backend.campaign_audit import build_campaign_report, format_campaign_text

    report = build_campaign_report(
        since_iso=since,
        include_presencial=include_presencial,
    )
    return {
        "status": "ok",
        "report": report,
        "text_summary": format_campaign_text(report),
    }


@app.get("/api/audit/campaign/snapshots")
def get_campaign_snapshots():
    """Lista los snapshots históricos guardados en data/audit_snapshots/ para comparación entre semanas."""
    from backend.campaign_audit import list_campaign_snapshots

    return {
        "status": "ok",
        "snapshots": list_campaign_snapshots(),
    }


@app.post("/api/audit/campaign/snapshot")
def create_campaign_snapshot(
    request: Request,
    since: Optional[str] = Query(None),
    x_api_token: Optional[str] = Header(None),
):
    """Guarda manualmente un snapshot JSON/TXT de campaña en data/audit_snapshots/."""
    verify_auth_token(request, x_api_token)
    from backend.campaign_audit import list_campaign_snapshots, save_campaign_snapshot

    snap = save_campaign_snapshot(since_iso=since, trigger="ui_manual")
    return {
        "status": "ok",
        "snapshot": {
            "filename_json": snap["filename_json"],
            "filename_txt": snap["filename_txt"],
            "created_at_utc": snap["created_at_utc"],
            "trigger": snap["trigger"],
        },
        "snapshots": list_campaign_snapshots(),
    }


@app.post("/api/ledger/reset_circuit_breaker")
def reset_ledger_circuit_breaker(
    request: Request,
    currency: Optional[str] = None,
    x_api_token: Optional[str] = Header(None),
):
    """Permite al operador reiniciar el Circuit Breaker transaccional en SQLite."""
    verify_auth_token(request, x_api_token)
    from backend.db.ledger import get_default_ledger, SUPPORTED_CURRENCIES

    if currency and currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=400, detail=f"Divisa no soportada: {currency}")
    ledger = get_default_ledger()
    ledger.reset_circuit_breaker(currency)
    return {
        "status": "ok",
        "message": f"Circuit Breaker reiniciado para {currency or 'todas las divisas'}.",
    }


# --- ENDPOINTS DEL BROKER TRANSACCIONAL (PaperBrokerAdapter) ---
class FlattenRequest(BaseModel):
    symbol: str = "BTC/USDT"
    price: Optional[float] = None
    reason: str = "EMERGENCY_FLATTEN"
    skip_csv_log: bool = False


@app.get("/api/broker/balances")
def get_broker_balances(request: Request, x_api_token: Optional[str] = Header(None)):
    """Retorna los saldos reales segregados: Patrimonio Total, Bóveda Efectivo, En Posiciones y Dinero para Operar."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    omnibus = daemon.broker.ledger.get_omnibus_balances() if hasattr(daemon.broker, "ledger") else {}
    vault = omnibus.get("vault", daemon.broker.vault_balances)
    operational = omnibus.get("operational", daemon.broker.balances)
    total_equity = omnibus.get(
        "total_equity",
        {curr: round(vault.get(curr, 0.0) + operational.get(curr, 0.0), 8) for curr in vault},
    )
    operating = omnibus.get("operating_capital", getattr(daemon.broker, "operating_capital_balances", {}))
    operating_available = omnibus.get(
        "operating_available",
        {curr: max(0.0, round(operating.get(curr, 0.0) - operational.get(curr, 0.0), 8)) for curr in vault},
    )
    idle = omnibus.get(
        "broker_idle",
        {curr: max(0.0, round(total_equity.get(curr, 0.0) - operating.get(curr, 0.0), 8)) for curr in vault},
    )
    return {
        "status": "ok",
        "total_equity": total_equity,
        "vault": vault,
        "operating_capital": operating,
        "operating_available": operating_available,
        "safe_profit_wallet": omnibus.get("safe_profit_wallet", {}),
        "safe_profit_injected": omnibus.get("safe_profit_injected", {}),
        "broker_idle": idle,
        "operational": operational,
        "fees_paid": omnibus.get("fees_paid", {}),
        "realized_pnl": omnibus.get("realized_pnl", {}),
        "futures_simulation": daemon.broker.get_futures_account() if hasattr(daemon.broker, "get_futures_account") else None,
    }


class BrokerDepositRequest(BaseModel):
    amount: float = 100.0
    currency: str = "USDT"
    investor_id: Optional[str] = None


class BrokerWithdrawRequest(BaseModel):
    amount: float = 100.0
    currency: str = "USDT"
    investor_id: Optional[str] = None


class BrokerOperatingCapitalRequest(BaseModel):
    amount: float = 500.0
    currency: str = "USDT"
    action: str = "set"  # "set", "transfer", "return"


class BrokerSafeProfitWalletRequest(BaseModel):
    amount: float = 50.0
    currency: str = "USDT"
    direction: str = "FROM_OPERATING"  # "FROM_OPERATING" | "TO_OPERATING"


class BrokerResetRequest(BaseModel):
    initial_amount: float = 500.0


@app.post("/api/broker/deposit")
def broker_deposit(
    req: BrokerDepositRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Inyecta fondos reales/paper en la Bóveda del broker (independiente del libro de inversores)."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    new_bal = daemon.broker.deposit(amount=req.amount, currency=req.currency)
    omnibus = daemon.broker.ledger.get_omnibus_balances() if hasattr(daemon.broker, "ledger") else {}

    return {
        "status": "ok",
        "currency": req.currency,
        "deposited": req.amount,
        "vault_balance": new_bal,
        "vault": daemon.broker.vault_balances,
        "total_equity": omnibus.get("total_equity", {}),
        "operating_capital": daemon.broker.get_operating_capital(req.currency),
    }


@app.post("/api/broker/withdraw")
def broker_withdraw(
    req: BrokerWithdrawRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Retira fondos de la Bóveda del broker (independiente del libro de inversores)."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    try:
        new_bal = daemon.broker.withdraw(amount=req.amount, currency=req.currency)
        omnibus = daemon.broker.ledger.get_omnibus_balances() if hasattr(daemon.broker, "ledger") else {}

        return {
            "status": "ok",
            "currency": req.currency,
            "withdrawn": req.amount,
            "vault_balance": new_bal,
            "vault": daemon.broker.vault_balances,
            "total_equity": omnibus.get("total_equity", {}),
            "operating_capital": daemon.broker.get_operating_capital(req.currency),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/broker/operating-capital")
def broker_operating_capital(
    req: BrokerOperatingCapitalRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Asigna o transfiere capital entre la Bóveda del Broker y el Dinero para Operar en la mesa de trading."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    try:
        if req.action == "transfer":
            new_op = daemon.broker.transfer_to_operating(currency=req.currency, amount=req.amount)
        elif req.action == "return":
            new_op = daemon.broker.return_to_broker(currency=req.currency, amount=req.amount)
        else:
            new_op = daemon.broker.set_operating_capital(currency=req.currency, amount=req.amount)
        return {
            "status": "ok",
            "currency": req.currency,
            "action": req.action,
            "amount": req.amount,
            "operating_capital": new_op,
            "vault": daemon.broker.vault_balances,
            "operating_capital_balances": daemon.broker.operating_capital_balances,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/broker/safe-profit-wallet")
def broker_safe_profit_wallet(
    req: BrokerSafeProfitWalletRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Transfiere fondos entre el Dinero para Operar y la Billetera de Uso por Ganancia Segura."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    try:
        res = daemon.broker.ledger.transfer_safe_profit_wallet(
            currency=req.currency,
            amount=req.amount,
            direction=req.direction,
        )
        return {
            "status": "ok",
            **res,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/broker/reset")
def broker_reset(
    req: BrokerResetRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Reinicia la cuenta contable de Paper Trading y restablece inversores al 50/50 exacto."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    from backend.db.investors import InvestorStore

    daemon = get_trader_daemon()
    vault = daemon.broker.reset_account(initial_amount=req.initial_amount)
    try:
        daemon.broker.reset_futures_account()
    except Exception:
        pass
    try:
        if hasattr(daemon, "counterfactual_cache") and isinstance(daemon.counterfactual_cache, dict):
            daemon.counterfactual_cache.clear()
    except Exception:
        pass

    try:
        broker_db = getattr(getattr(daemon.broker, "ledger", None), "db_path", None)
        store = InvestorStore(db_path=broker_db) if broker_db else InvestorStore()
        store.reset_and_rebalance_50_50(vault_total=req.initial_amount, currency="USD")
        store.reset_and_rebalance_50_50(vault_total=req.initial_amount, currency="USDT")
    except Exception as inv_err:
        logger.warning(f"Aviso reseteando libro de inversores: {inv_err}")

    return {
        "status": "ok",
        "message": f"Cuenta y nómina de inversores reiniciadas a ${req.initial_amount:.2f}.",
        "vault": vault,
        "operating_capital": daemon.broker.operating_capital_balances,
    }


@app.get("/api/broker/positions")
def get_broker_positions(request: Request, x_api_token: Optional[str] = Header(None)):
    """Retorna las posiciones abiertas reportadas por el broker transaccional en SQLite."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    return {
        "status": "ok",
        "positions": daemon.broker.fetch_positions(),
        "open_orders": daemon.broker.fetch_open_orders(),
    }


@app.get("/api/broker/trades")
def get_broker_trades(request: Request, x_api_token: Optional[str] = Header(None)):
    """Retorna el historial completo de operaciones registradas en el Ledger SQLite."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    return {
        "status": "ok",
        "vault_balances": daemon.broker.vault_balances,
        "trades": daemon.broker.fetch_trade_history(),
    }


class BrokerEntryRequest(BaseModel):
    symbol: str = "BTC/USDT"
    qty: float
    price: float
    tp_pct: float = 0.8
    sl_pct: float = 0.5


@app.post("/api/broker/entry")
def open_broker_position(
    req: BrokerEntryRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Sincroniza una apertura de posición del navegador hacia el Ledger SQLite del servidor."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    existing = [p for p in daemon.broker.fetch_positions() if p.get("symbol") == req.symbol]
    if existing:
        return {"status": "already_open", "position": existing[0]}

    res = daemon.broker.place_entry(
        req.symbol,
        "BUY",
        qty=float(req.qty),
        price=float(req.price),
        initial_tp_pct=float(req.tp_pct),
        initial_sl_pct=float(req.sl_pct),
    )
    sl_px = float(req.price) * (1.0 - float(req.sl_pct) / 100.0)
    tp_px = float(req.price) * (1.0 + float(req.tp_pct) / 100.0)
    daemon.broker.place_protection(req.symbol, qty=float(req.qty), stop_loss_price=sl_px, take_profit_price=tp_px)
    daemon.ensure_guardian_running()

    try:
        from backend.telegram_notifier import notify_trade_opened
        cost_basis = round(float(req.qty) * float(req.price), 2)
        notify_trade_opened(
            symbol=req.symbol,
            side="LONG",
            price=float(req.price),
            qty=float(req.qty),
            cost_basis=cost_basis,
            sl_pct=float(req.sl_pct),
            tp_pct=float(req.tp_pct),
            strategy=daemon.strategy or "MANUAL_OPERADOR",
            formula="Apertura Manual desde Cockpit",
        )
    except Exception as _e_tg_entry:
        import logging
        logging.getLogger("kula_balam").warning(f"Error al enviar notificación Telegram de apertura manual: {_e_tg_entry}")

    # Esta ruta sincroniza una apertura ya ejecutada en el navegador, por lo que no se rechaza; se advierte
    # explícitamente si los niveles tienen R:R neto inferior al mínimo (la compuerta de get_analysis evita
    # que el sistema las abra de forma automática).
    rr_info = net_rr_metrics(float(req.tp_pct), float(req.sl_pct), float(daemon.fee), float(daemon.spread))
    response: Dict[str, Any] = {"status": "ok", "result": res, "net_rr": rr_info.get("net_rr")}
    if rr_info.get("net_rr", 0.0) < MIN_NET_RR:
        response["warning"] = (
            f"R:R neto {rr_info.get('net_rr', 0.0):.2f} < {MIN_NET_RR:.2f}: TP +{req.tp_pct}% / SL -{req.sl_pct}% "
            f"requiere {rr_info.get('breakeven_win_rate', 1.0) * 100:.0f}% de aciertos para empatar."
        )
    return response


@app.post("/api/broker/flatten")
def flatten_broker_position(
    req: FlattenRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Cierre de emergencia / manual / SL / TP a mercado desde el broker y sweep-back a la bóveda."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    cur_px = float(req.price) if req.price and req.price > 0 else 0.0
    if cur_px <= 0:
        price_info = get_price(req.symbol)
        cur_px = float(price_info.get("price", 0.0))

    target_pos = None
    if hasattr(daemon.broker, "ledger"):
        matches = [p for p in daemon.broker.ledger.get_open_positions() if p.get("symbol") == req.symbol]
        if matches:
            target_pos = matches[0]

    res = daemon.broker.flatten(req.symbol, current_price=cur_px, exit_reason=req.reason)
    if res.get("closed"):
        daemon._arm_cooldown(req.symbol)
        if not req.skip_csv_log:
            daemon._log_trade_csv(req.symbol, "VENDER", cur_px, 0.0, "Ejecutada", req.reason or "Manual Flatten")
        if target_pos:
            try:
                from backend.telegram_notifier import notify_trade_closed
                entry_px = float(target_pos.get("entry_price") or cur_px)
                side_str = str(target_pos.get("side") or "LONG").upper()
                c_basis = float(target_pos.get("cost_basis") or (entry_px * float(target_pos.get("qty") or 0.0)))
                strat = str(target_pos.get("strategy") or daemon.strategy or "MANUAL_OPERADOR")
                exit_label = req.reason or "Manual Flatten Operador"
                notify_trade_closed(
                    symbol=req.symbol,
                    side=side_str,
                    entry_price=entry_px,
                    exit_price=float(res.get("exit_price") or cur_px),
                    pnl=float(res.get("net_pnl") or 0.0),
                    fees=float(target_pos.get("total_fees") or 0.0),
                    exit_reason=exit_label,
                    strategy=strat,
                    cost_basis=c_basis,
                    operational_balance=res.get("operational_balance"),
                    vault_balance=res.get("vault_balance"),
                )
            except Exception as _e_tg_close:
                import logging
                logging.getLogger("kula_balam").warning(f"Error al enviar notificación Telegram de flatten manual: {_e_tg_close}")
    return {
        "status": "ok",
        "result": res,
    }


class BrokerScaleInRequest(BaseModel):
    symbol: str
    amount: float
    current_price: Optional[float] = None
    source_mode: str = "OPERATING_POOL"  # "OPERATING_POOL" o "SAFE_PROFIT_WALLET"
    enforce_safe_profit_lock: bool = True


class BrokerRotatePositionRequest(BaseModel):
    from_symbol: str
    to_symbol: str
    amount: Optional[float] = None
    from_price: Optional[float] = None
    to_price: Optional[float] = None
    enforce_safe_profit_lock: bool = True


@app.post("/api/broker/scale-in")
def scale_in_broker_position(
    req: BrokerScaleInRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """
    Potencia una operación abierta en ganancia (Piramidación con Riesgo Cero):
    Inyecta capital adicional desde el Cupo Libre ('OPERATING_POOL') o desde la
    Billetera de Ganancia Segura / Reserva ('SAFE_PROFIT_WALLET'), recalcula el
    precio promedio de entrada y blinda el Stop Loss en ganancia neta.
    """
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    cur_px = float(req.current_price) if req.current_price and req.current_price > 0 else 0.0
    if cur_px <= 0:
        px_info = get_price(req.symbol)
        cur_px = float(px_info.get("price", 0.0))

    try:
        res = daemon.broker.scale_in_position(
            symbol=req.symbol,
            add_amount_currency=req.amount,
            current_price=cur_px,
            source_mode=req.source_mode,
            enforce_safe_profit_lock=req.enforce_safe_profit_lock,
        )
        daemon.ensure_guardian_running()
        return {
            "status": "ok",
            "result": res,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/broker/rotate-position")
def rotate_broker_position(
    req: BrokerRotatePositionRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """
    Rotación Táctica de Capital (Cerrar operación tranquila -> Potenciar operación vigorosa):
    1. Cierra a mercado `from_symbol` y libera su capital hacia el cupo operativo.
    2. Inyecta el capital liberado en `to_symbol` aplicando el Candado de Ganancia Segura.
    """
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon

    if req.from_symbol == req.to_symbol:
        raise HTTPException(status_code=400, detail="El activo de origen y el activo de destino deben ser distintos.")

    daemon = get_trader_daemon()
    open_positions = daemon.broker.fetch_positions()
    pos_from = next((p for p in open_positions if p.get("symbol") == req.from_symbol), None)
    pos_to = next((p for p in open_positions if p.get("symbol") == req.to_symbol), None)

    if not pos_from:
        raise HTTPException(status_code=404, detail=f"No existe posición abierta en {req.from_symbol} para rotar.")
    if not pos_to:
        raise HTTPException(status_code=404, detail=f"No existe posición abierta en {req.to_symbol} para potenciar.")

    from_px = float(req.from_price) if req.from_price and req.from_price > 0 else 0.0
    if from_px <= 0:
        from_px = float(get_price(req.from_symbol).get("price", 0.0)) or float(pos_from.get("entry_price", 0.0))

    to_px = float(req.to_price) if req.to_price and req.to_price > 0 else 0.0
    if to_px <= 0:
        to_px = float(get_price(req.to_symbol).get("price", 0.0)) or float(pos_to.get("entry_price", 0.0))

    # 1. Verificar que la posición origen (lenta) esté en POSITIVO (NUNCA cerrar en negativo para rotar)
    from_entry = float(pos_from.get("entry_price", 0.0))
    from_is_short = str(pos_from.get("side") or "LONG").upper() in ("SHORT", "SELL")
    from_unrealized_pct = (
        ((from_entry - from_px) / from_entry * 100.0)
        if from_is_short
        else ((from_px - from_entry) / from_entry * 100.0)
    ) if from_entry > 0 else 0.0
    if req.enforce_safe_profit_lock and from_unrealized_pct <= 0.0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Regla de Rotación sin Pérdida: NUNCA se cierra una posición en negativo o en cero para rotar. "
                f"La posición origen ({req.from_symbol}) debe estar en positivo (actual {from_unrealized_pct:+.2f}%)."
            ),
        )

    # 2. Verificar el candado de ganancia en el destino ANTES de cerrar la posición de origen
    to_entry = float(pos_to.get("entry_price", 0.0))
    to_is_short = str(pos_to.get("side") or "LONG").upper() in ("SHORT", "SELL")
    to_unrealized_pct = (
        ((to_entry - to_px) / to_entry * 100.0)
        if to_is_short
        else ((to_px - to_entry) / to_entry * 100.0)
    ) if to_entry > 0 else 0.0
    if req.enforce_safe_profit_lock and to_unrealized_pct < 0.20:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Candado de Ganancia Segura: la posición destino ({req.to_symbol}) debe estar en ganancia "
                f"(+0.20% mín., actual {to_unrealized_pct:+.2f}%) antes de rotarle capital."
            ),
        )
    if req.enforce_safe_profit_lock and to_unrealized_pct <= from_unrealized_pct:
        raise HTTPException(
            status_code=400,
            detail=(
                f"La posición destino ({req.to_symbol}: {to_unrealized_pct:+.2f}%) debe tener mayor fuerza/ganancia "
                f"que la posición lenta de origen ({req.from_symbol}: {from_unrealized_pct:+.2f}%)."
            ),
        )

    freed_cost = float(pos_from.get("cost_basis", 0.0))
    rotate_amount = round(float(req.amount) if req.amount and req.amount > 0 else freed_cost, 2)

    try:
        close_res = daemon.broker.flatten(
            req.from_symbol,
            current_price=from_px,
            exit_reason=f"ROTATE_TO_{req.to_symbol}",
        )
        if close_res.get("closed"):
            daemon._arm_cooldown(req.from_symbol)
            daemon._log_trade_csv(
                req.from_symbol,
                "VENDER",
                from_px,
                0.0,
                "Ejecutada",
                f"Rotación hacia {req.to_symbol}",
            )
            try:
                from backend.telegram_notifier import notify_trade_closed
                entry_px = float(pos_from.get("entry_price") or from_px)
                side_str = str(pos_from.get("side") or "LONG").upper()
                c_basis = float(pos_from.get("cost_basis") or (entry_px * float(pos_from.get("qty") or 0.0)))
                strat = str(pos_from.get("strategy") or daemon.strategy or "ROTATION")
                notify_trade_closed(
                    symbol=req.from_symbol,
                    side=side_str,
                    entry_price=entry_px,
                    exit_price=float(close_res.get("exit_price") or from_px),
                    pnl=float(close_res.get("net_pnl") or 0.0),
                    fees=float(pos_from.get("total_fees") or 0.0),
                    exit_reason=f"Rotación hacia {req.to_symbol}",
                    strategy=strat,
                    cost_basis=c_basis,
                    operational_balance=close_res.get("operational_balance"),
                    vault_balance=close_res.get("vault_balance"),
                )
            except Exception as _e_tg_rot:
                import logging
                logging.getLogger("kula_balam").warning(f"Error al enviar notificación Telegram de rotación: {_e_tg_rot}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fallo al cerrar posición origen ({req.from_symbol}): {e}")

    try:
        scale_res = daemon.broker.scale_in_position(
            symbol=req.to_symbol,
            add_amount_currency=rotate_amount,
            current_price=to_px,
            source_mode="OPERATING_POOL",
            enforce_safe_profit_lock=req.enforce_safe_profit_lock,
        )
        daemon.ensure_guardian_running()
        return {
            "status": "ok",
            "closed_from": close_res,
            "scaled_into": scale_res,
        }
    except Exception as e:
        raise HTTPException(
            status_code=409,
            detail=(
                f"La posición lenta ({req.from_symbol}) se cerró con éxito y sus fondos volvieron al Dinero para Operar, "
                f"pero no se pudo inyectar en {req.to_symbol}: {e}"
            ),
        )


# --- WORKER AUTÓNOMO DE FONDO (DAEMON PYTHON) ---
class DaemonStartRequest(BaseModel):
    symbol: str = "SOL/USDT"
    timeframe: str = "4h"
    strategy: str = "donchian_breakout_1h"
    allowed_strategies: Optional[List[str]] = None
    strategy_lots: Optional[Dict[str, float]] = None
    strategy_risk_pcts: Optional[Dict[str, float]] = None
    slot_alloc_pct: Optional[float] = None
    engine: str = "antigravity_operador"
    model: Optional[str] = "antigravity-tactical-v1"
    tp: float = 2.0
    sl: float = 1.0
    risk: float = 0.50
    fee: float = 0.1
    spread: float = 0.05
    min_profit_pct: float = 0.5
    mode: str = "smart"
    max_positions: int = 2
    enable_futures_simulation: Optional[bool] = None


@app.get("/api/daemon/status")
def get_daemon_status(request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    return get_trader_daemon().get_status()


@app.get("/api/health/semaforo")
def get_health_semaforo(
    request: Request,
    probe: bool = False,
    x_api_token: Optional[str] = Header(None),
):
    """Semáforo operativo determinista de 4 luces (0 tokens IA)."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    from backend.health_watchdog import get_health_watchdog
    return get_health_watchdog().evaluate(
        get_trader_daemon(),
        force_probe=bool(probe),
        notify_on_red=False,
    )


@app.post("/api/daemon/start")
def start_daemon(req: DaemonStartRequest, request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    return get_trader_daemon().start(
        symbol=req.symbol,
        timeframe=req.timeframe,
        strategy=req.strategy,
        allowed_strategies=req.allowed_strategies,
        strategy_lots=req.strategy_lots,
        strategy_risk_pcts=req.strategy_risk_pcts,
        slot_alloc_pct=req.slot_alloc_pct,
        engine=req.engine,
        model=req.model,
        tp=req.tp,
        sl=req.sl,
        risk=req.risk,
        fee=req.fee,
        spread=req.spread,
        min_profit_pct=req.min_profit_pct,
        mode=req.mode,
        max_positions=req.max_positions,
        enable_futures_simulation=req.enable_futures_simulation,
    )


@app.post("/api/daemon/stop")
def stop_daemon(request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    return get_trader_daemon().stop()


class ScalpingStartRequest(BaseModel):
    symbol: str = "ETH/USDT"
    strategy: str = "scalping_vwap_2sigma_5m"
    timeframe: str = "5m"
    lot_size: float = 0.01
    slot_alloc_pct: Optional[float] = None


@app.get("/api/daemon/scalping/status")
def get_daemon_scalping_status(request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    return get_trader_daemon().get_scalping_status()


@app.post("/api/daemon/scalping/start")
def start_daemon_scalping(req: ScalpingStartRequest, request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    return get_trader_daemon().start_scalping(
        symbol=req.symbol,
        strategy=req.strategy,
        timeframe=req.timeframe,
        lot_size=req.lot_size,
        slot_alloc_pct=req.slot_alloc_pct,
    )


@app.post("/api/daemon/scalping/stop")
def stop_daemon_scalping(request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    return get_trader_daemon().stop_scalping()


@app.get("/api/strategies/scalping")
def get_scalping_strategies(request: Request, x_api_token: Optional[str] = Header(None)):
    verify_auth_token(request, x_api_token)
    from backend.estrategias.registry import list_scalping_strategies
    return list_scalping_strategies()


# ==============================================================================
# --- MÓDULO SATÉLITE DE GESTIÓN DE INVERSORES (CUOTAPARTES / NAV EN ARS) ---
# ==============================================================================

class InvestorCreateRequest(BaseModel):
    name: str
    alias: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


class InvestorTxnRequest(BaseModel):
    amount: float
    currency: str = "USD"
    notes: Optional[str] = ""


class InvestorConfigUpdateRequest(BaseModel):
    operator_fee_pct: Optional[float] = None
    usdt_ars_rate: Optional[float] = None


class InvestorExpenseCreateRequest(BaseModel):
    description: str
    amount: float
    currency: str = "USD"
    category: str = "GENERAL"
    rate_to_usd: Optional[float] = None
    notes: Optional[str] = ""


class InvestorSetCapitalRequest(BaseModel):
    amount: float
    currency: str = "USDT"


def _get_broker_equity_snapshot() -> Dict[str, Any]:
    """Obtiene el patrimonio total real del broker (Efectivo en Bóveda + Invertido en Posiciones Abiertas)."""
    from backend.daemon import get_trader_daemon

    daemon = get_trader_daemon()
    omnibus = daemon.broker.ledger.get_omnibus_balances() if hasattr(daemon.broker, "ledger") else {}
    vault = omnibus.get("vault", daemon.broker.vault_balances)
    operational = omnibus.get("operational", daemon.broker.balances)
    total_equity = omnibus.get(
        "total_equity",
        {curr: round(vault.get(curr, 0.0) + operational.get(curr, 0.0), 8) for curr in vault},
    )
    operating_capital = omnibus.get("operating_capital", getattr(daemon.broker, "operating_capital_balances", {}))
    operating_available = omnibus.get(
        "operating_available",
        {curr: max(0.0, round(operating_capital.get(curr, 0.0) - operational.get(curr, 0.0), 8)) for curr in vault},
    )
    broker_idle = omnibus.get(
        "broker_idle",
        {curr: max(0.0, round(total_equity.get(curr, 0.0) - operating_capital.get(curr, 0.0), 8)) for curr in vault},
    )
    return {
        "vault": vault,
        "operational": operational,
        "total_equity": total_equity,
        "operating_capital": operating_capital,
        "operating_available": operating_available,
        "broker_idle": broker_idle,
    }


@app.post("/api/investors/{investor_id}/set-capital")
def set_investor_capital_endpoint(
    investor_id: str,
    req: InvestorSetCapitalRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Permite ajustar directamente el capital contable de un inversor (independiente del broker)."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore

    store = InvestorStore()
    snap = _get_broker_equity_snapshot()
    target_currency = (req.currency or "USDT").upper().strip()
    vault_total = float(snap["total_equity"].get(target_currency, 0.0))
    try:
        return store.set_investor_capital(
            investor_id=investor_id,
            new_amount=req.amount,
            vault_total=vault_total,
            currency=target_currency,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/investors")
def get_investors_fund(
    request: Request,
    currency: str = "USD",
    x_api_token: Optional[str] = Header(None),
):
    """
    Retorna el estado contable del libro de inversores (100% independiente del broker)
    junto con el reporte de diferencia contra el Patrimonio Total del Broker (Efectivo + Activos Abiertos).
    """
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore

    store = InvestorStore()
    snap = _get_broker_equity_snapshot()
    target_currency = currency.upper().strip()
    total_equity_map = snap["total_equity"]
    raw_vault = float(total_equity_map.get(target_currency, 0.0))
    vault_total = raw_vault if raw_vault >= 0.01 else 0.0

    fund_status = store.get_fund_status(
        vault_total=vault_total,
        currency=target_currency,
        vault_balances=total_equity_map,
    )
    fund_status["vault_balances"] = total_equity_map
    fund_status["vault_cash_balances"] = snap["vault"]
    fund_status["operational_balances"] = snap["operational"]
    fund_status["vault_cash"] = round(float(snap["vault"].get(target_currency, 0.0)), 2)
    fund_status["in_positions"] = round(float(snap["operational"].get(target_currency, 0.0)), 2)
    fund_status["operating_capital"] = round(float(snap["operating_capital"].get(target_currency, 0.0)), 2)
    fund_status["operating_available"] = round(float(snap["operating_available"].get(target_currency, 0.0)), 2)
    fund_status["broker_idle"] = round(float(snap["broker_idle"].get(target_currency, 0.0)), 2)
    return fund_status


@app.post("/api/investors")
def create_investor_endpoint(
    req: InvestorCreateRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Crea un nuevo inversor aportante."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore
    store = InvestorStore()
    try:
        return store.create_investor(name=req.name, alias=req.alias, email=req.email, notes=req.notes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/investors/{investor_id}")
def delete_investor_endpoint(
    investor_id: str,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Elimina (quita) un inversor del libro de inversores junto con sus movimientos contables."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore
    store = InvestorStore()
    try:
        return store.delete_investor(investor_id=investor_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/investors/{investor_id}/deposit")
def investor_deposit_endpoint(
    investor_id: str,
    req: InvestorTxnRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Registra un ingreso de dinero al inversor en el libro contable (independiente del broker)."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore

    store = InvestorStore()
    snap = _get_broker_equity_snapshot()
    target_currency = (req.currency or "USD").upper().strip()
    vault_total = float(snap["total_equity"].get(target_currency, 0.0))
    try:
        return store.record_deposit(
            investor_id=investor_id,
            amount=req.amount,
            current_vault_total=vault_total,
            currency=target_currency,
            notes=req.notes or "",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/investors/{investor_id}/withdraw")
def investor_withdraw_endpoint(
    investor_id: str,
    req: InvestorTxnRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Registra un retiro de dinero del inversor (permite retirar el 100% descontando solo gastos)."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore

    store = InvestorStore()
    snap = _get_broker_equity_snapshot()
    target_currency = (req.currency or "USD").upper().strip()
    vault_total = float(snap["total_equity"].get(target_currency, 0.0))
    try:
        return store.record_withdrawal(
            investor_id=investor_id,
            amount=req.amount,
            current_vault_total=vault_total,
            currency=target_currency,
            notes=req.notes or "",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/investors/expenses")
def get_investor_expenses_endpoint(
    request: Request,
    limit: int = 100,
    x_api_token: Optional[str] = Header(None),
):
    """Retorna la lista de gastos operativos registrados y el total acumulado en USD."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore
    store = InvestorStore()
    return {
        "expenses": store.get_expenses(limit=limit),
        "total_expenses_usd": store.get_total_expenses_usd(),
        "usdt_ars_rate": float(store.get_config("usdt_ars_rate", "1250.0")),
    }


@app.post("/api/investors/expenses")
def add_investor_expense_endpoint(
    req: InvestorExpenseCreateRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Registra un gasto general/operativo y lo convierte a USD para su deducción proporcional al retirar."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore
    store = InvestorStore()
    try:
        return store.add_expense(
            description=req.description,
            amount=req.amount,
            currency=req.currency,
            category=req.category,
            rate_to_usd=req.rate_to_usd,
            notes=req.notes or "",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/investors/expenses/{expense_id}")
def delete_investor_expense_endpoint(
    expense_id: str,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Elimina un gasto operativo registrado."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore
    store = InvestorStore()
    deleted = store.delete_expense(expense_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Gasto operativo no encontrado.")
    return {"status": "DELETED", "id": expense_id}


@app.get("/api/investors/config")
def get_investors_config_endpoint(request: Request, x_api_token: Optional[str] = Header(None)):
    """Retorna los parámetros de configuración del fondo (comisión operador y tipo de cambio)."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore
    store = InvestorStore()
    return {
        "operator_fee_pct": float(store.get_config("operator_fee_pct", "0.0")),
        "display_currency": store.get_config("display_currency", "USD"),
        "usdt_ars_rate": float(store.get_config("usdt_ars_rate", "1250.0")),
    }


@app.post("/api/investors/config")
def update_investors_config_endpoint(
    req: InvestorConfigUpdateRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Actualiza la comisión del operador o el tipo de cambio de referencia."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore
    store = InvestorStore()
    if req.operator_fee_pct is not None:
        if req.operator_fee_pct < 0 or req.operator_fee_pct > 50:
            raise HTTPException(status_code=400, detail="La comisión del operador debe estar entre 0% y 50%.")
        store.set_config("operator_fee_pct", str(req.operator_fee_pct))
    if req.usdt_ars_rate is not None:
        if req.usdt_ars_rate <= 0:
            raise HTTPException(status_code=400, detail="El tipo de cambio debe ser mayor a cero.")
        store.set_config("usdt_ars_rate", str(req.usdt_ars_rate))
    return {
        "status": "ok",
        "operator_fee_pct": float(store.get_config("operator_fee_pct", "0.0")),
        "usdt_ars_rate": float(store.get_config("usdt_ars_rate", "1250.0")),
    }


@app.post("/api/investors/reset")
def reset_investors_endpoint(
    request: Request,
    currency: str = "USD",
    x_api_token: Optional[str] = Header(None),
):
    """Reinicia a cero movimientos y gastos de inversores y reparte 50/50 el patrimonio total del broker."""
    verify_auth_token(request, x_api_token)
    from backend.db.investors import InvestorStore
    store = InvestorStore()
    snap = _get_broker_equity_snapshot()
    target_currency = currency.upper().strip()
    vault_total = float(snap["total_equity"].get(target_currency, 0.0))
    return store.reset_and_rebalance_50_50(vault_total=vault_total, currency=target_currency)


class AgentChatRequest(BaseModel):
    message: str
    user: Optional[str] = "Operator"


def _extract_target_asset_from_message(msg_lower: str, default_symbol: str = "BTC/USDT") -> str:
    """Extrae el símbolo objetivo desde lenguaje natural en el chat del operador."""
    alias_map = [
        ("eurusd", "EURUSD=X"), ("eur/usd", "EURUSD=X"), ("gbpusd", "GBPUSD=X"),
        ("usdjpy", "USDJPY=X"), ("audusd", "AUDUSD=X"), ("usdcad", "USDCAD=X"), ("usdchf", "USDCHF=X"),
        ("petróleo", "CL=F"), ("petroleo", "CL=F"), ("wti", "CL=F"), ("cl=f", "CL=F"),
        ("oro", "GC=F"), ("gold", "GC=F"), ("gc=f", "GC=F"),
        ("plata", "SI=F"), ("si=f", "SI=F"), ("ng=f", "NG=F"),
        ("nasdaq", "QQQ"), ("qqq", "QQQ"), ("spy", "SPY"), ("s&p", "SPY"),
        ("bitcoin", "BTC/USDT"), ("btc", "BTC/USDT"),
        ("ethereum", "ETH/USDT"), ("eth", "ETH/USDT"),
        ("solana", "SOL/USDT"), ("sol", "SOL/USDT"),
        ("bnb", "BNB/USDT"), ("xrp", "XRP/USDT"), ("ada", "ADA/USDT"), ("doge", "DOGE/USDT"),
        ("nvda", "NVDA"), ("aapl", "AAPL"), ("msft", "MSFT"), ("tsla", "TSLA"),
        ("amd", "AMD"), ("avgo", "AVGO"), ("meta", "META"), ("amzn", "AMZN"),
        ("baba", "BABA"), ("kweb", "KWEB"),
    ]
    for alias, target in alias_map:
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", msg_lower):
            return target
    for sym in SUPPORTED_SYMBOLS:
        if sym.lower() in msg_lower:
            return sym
    return default_symbol


@app.get("/api/agent/live-status")
def get_agent_live_status(request: Request, x_api_token: Optional[str] = Header(None)):
    """Retorna telemetría unificada en vivo de Kula Balam y la sesión bursátil real (America/New_York -> ART)."""
    verify_auth_token(request, x_api_token)
    from backend.daemon import get_trader_daemon
    from backend.market_context import load_market_context

    daemon = get_trader_daemon()
    status = daemon.get_status()
    vaults = daemon.broker.vault_balances
    open_pos = daemon.broker.fetch_positions()

    now_utc = datetime.now(timezone.utc)
    sess = _compute_session_clock(now_utc)
    now_art = sess["now_art"]
    kula_ctx = load_market_context()

    return {
        "online": True,
        "ecosystem": "Kula Balam",
        "timestamp": now_utc.isoformat(),
        "time_art": now_art.strftime("%H:%M:%S ART"),
        "cycle_count": status.get("cycle_count", 0),
        "is_running": status.get("is_running", False),
        "paused": bool(status.get("paused", False)),
        "pause_reason": status.get("pause_reason", ""),
        "symbol": status.get("symbol", "SOL/USDT"),
        "active_symbol": status.get("active_symbol", status.get("symbol", "SOL/USDT")),
        "strategy": status.get("strategy", "donchian_breakout_1h"),
        "engine": status.get("engine", "antigravity_operador"),
        "mode": status.get("mode", "smart"),
        "last_signal": status.get("last_signal", "MANTENER"),
        "last_reason": status.get("last_reason", "Vigilancia pasiva de mercado en curso"),
        "open_positions_count": len(open_pos),
        "vaults": vaults,
        "kula_context": kula_ctx.model_dump() if kula_ctx else None,
        "session": {
            "name": sess["name"],
            "blackout_active": sess["blackout_active"],
            "next_milestone": sess["next_milestone"],
            "ny_open_art": sess["ny_open_art"],
            "ny_close_art": sess["ny_close_art"],
        },
    }


@app.post("/api/agent/chat")
def post_agent_chat_endpoint(
    req: AgentChatRequest,
    request: Request,
    x_api_token: Optional[str] = Header(None),
):
    """Canal de chat bidireccional y recepción de directivas ejecutables para Kula Balam."""
    import uuid
    verify_auth_token(request, x_api_token)
    global INJECTED_MACRO
    from backend.daemon import get_trader_daemon
    daemon = get_trader_daemon()
    status = daemon.get_status()
    vaults = daemon.broker.vault_balances
    positions = daemon.broker.fetch_positions()

    user_msg = (req.message or "").strip()
    msg_lower = user_msg.lower()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Comandos Ejecutables de Control (Reanudar, Pausar, Directivas)
    if any(k in msg_lower for k in ("reanud", "reactiv", "despaus", "resumir", "resume")):
        updated_status = daemon.set_paused(False, reason=f"Reanudado vía chat del operador: {user_msg}")
        reply = (
            f"▶️ **Operativa Reanudada:** `Kula Balam` retoma evaluación de nuevas entradas en `{updated_status.get('symbol')}` "
            f"vía `{updated_status.get('strategy')}` (`{updated_status.get('engine')}`)."
        )
        return {"reply": reply, "timestamp": now_iso, "action": "RESUME", "paused": False}

    if any(k in msg_lower for k in ("pausa", "detener", "frenar")):
        daemon.set_paused(True, reason=f"Pausa ordenada vía chat: {user_msg}")
        reply = (
            "⏸️ **Instrucción de Pausa Aplicada en Daemon:** Apertura de nuevas posiciones bloqueada "
            "para preservar liquidez hasta orden de reanudación. El guardián SL/TP sigue protegiendo posiciones abiertas."
        )
        return {"reply": reply, "timestamp": now_iso, "action": "PAUSE", "paused": True}

    if (
        msg_lower.startswith("directiva:")
        or "enfócate en" in msg_lower
        or "enfocate en" in msg_lower
        or "prioriza" in msg_lower
        or "cautela" in msg_lower
    ):
        directive_text = user_msg
        target_asset = _extract_target_asset_from_message(msg_lower, default_symbol=status.get("symbol") or "BTC/USDT")
        is_veto_msg = any(k in msg_lower for k in ("veto", "peligro", "negativo", "no operar", "no comprar"))
        directive_type = "Peligro" if is_veto_msg else "Directiva de Operador"

        INJECTED_MACRO = {
            "id": str(uuid.uuid4()),
            "asset": target_asset,
            "text": directive_text,
            "confidence": 90,
            "type": directive_type,
            "source": "Chat Interactivo del Operador",
            "timestamp": now_iso,
        }
        if not is_veto_msg and target_asset in SUPPORTED_SYMBOLS:
            try:
                daemon.radar_candidate_symbol = target_asset
            except Exception:
                pass
        reply = (
            f"✅ **Directiva asimilada e inyectada a Kula Balam:**\n> *\"{directive_text}\"*\n\n"
            f"• **Activo asignado:** `{target_asset}`\n"
            f"• **Clasificación:** `{directive_type}` (90% de convicción)\n"
            f"• **Efecto:** El motor y el daemon calibrarán filtros y prioridad hacia este lineamiento táctico."
        )
        return {"reply": reply, "timestamp": now_iso, "action": "DIRECTIVE_INJECTED", "asset": target_asset}

    # 2. Respuestas Conversacionales con Gemini API en Vivo y Contexto Real
    api_key = os.getenv("GEMINI_API_KEY")
    sess = _compute_session_clock()
    if api_key and api_key != "tu_clave_aqui_sin_comillas":
        try:
            import requests
            gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

            # Contexto contable y operativo en vivo
            open_pos_summary = []
            for p in positions:
                sym = p.get('symbol', 'DESCONOCIDO')
                side = p.get('side', 'BUY')
                entry = p.get('costBasis') or p.get('entryPrice') or p.get('entry_price') or 0
                open_pos_summary.append(f"{sym} ({side} entrada ${entry})")
            pos_str = ", ".join(open_pos_summary) if open_pos_summary else "Ninguna (100% líquidas en bóveda)"
            pause_label = "PAUSADO PARA NUEVAS ENTRADAS" if status.get("paused") else "ACTIVO"

            prompt_system = (
                "Eres el Módulo Kula del ecosistema Kula Balam: el cerebro de inteligencia estratégica multitemporal "
                "(Tríada 1D-1H-5M, Zona Dorada Fibonacci 0.50-0.75 y EMA 50) que guía al rol táctico Balam "
                "(paciencia en liquidez y gatillo al cierre de vela). La Bóveda sigue bajo custodia estricta.\n"
                "Responde al operador con sobriedad técnica, precisión cuantitativa y cero adulación.\n\n"
                f"DATOS REALES DEL SISTEMA EN ESTE INSTANTE:\n"
                f"- Estado operativo: {pause_label} | Sesión actual: {sess['name']}\n"
                f"- Activo en vigilancia: {status.get('active_symbol', status.get('symbol', 'SOL/USDT'))}\n"
                f"- Temporalidad: {status.get('timeframe', '4h')}\n"
                f"- Estrategia activa: {status.get('strategy', 'donchian_breakout_1h')}\n"
                f"- Motor: {status.get('engine', 'antigravity_operador')}\n"
                f"- Bóveda USDT: {vaults.get('USDT', 0):.2f} USDT | Bóveda USD: ${vaults.get('USD', 0):.2f} USD | Bóveda ARS: ${vaults.get('ARS', 0):,.2f} ARS\n"
                f"- Posiciones abiertas ({len(positions)}/{status.get('max_positions', 2)} slots): {pos_str}\n"
                f"- Ciclo de patrullaje: #{status.get('cycle_count', 0)}\n"
                f"- Última señal emitida: {status.get('last_signal', 'MANTENER')}\n"
                f"- Motivo del último ciclo: {status.get('last_reason', 'Vigilancia de microestructura')}\n\n"
                "DIRECTIVAS DE COMUNICACIÓN:\n"
                "1. Sé claro, directo y cuantitativo. Usa formato Markdown limpio.\n"
                "2. Si preguntan por saldo o bóvedas, reporta las cifras exactas arriba indicadas.\n"
                "3. Si preguntan por inactividad o filtros, fundamenta con R:R neto, ATR, RVOL, horario real Wall Street (09:30-16:00 NY) o veto macro.\n"
                "4. Responde en español, máximo 2 o 3 párrafos concisos."
            )

            gem_url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
            gem_payload = {
                "contents": [{"parts": [{"text": f"{prompt_system}\n\nMensaje del operador:\n\"{user_msg}\""}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
            }
            gem_resp = requests.post(gem_url, json=gem_payload, timeout=12)
            if gem_resp.status_code == 200:
                gem_data = gem_resp.json()
                raw_parts = gem_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
                reply_text = raw_parts[0].get("text", "").strip() if raw_parts else ""
                if reply_text:
                    return {"reply": reply_text, "timestamp": now_iso, "action": "CHAT_RESPONSE"}
        except Exception as e:
            logger.warning(f"Error al consultar Gemini para chat: {e}")

    # Fallback determinista: Ficha técnica Kula Balam en vivo
    estado_txt = "PAUSADO (nuevas entradas bloqueadas)" if status.get("paused") else "ACTIVO"
    reply = (
        f"📋 **Reporte de Estado — Módulo Kula | Rol Balam ({estado_txt}):**\n\n"
        f"• **Sesión:** `{sess['name']}` (próximo hito: `{sess['next_milestone']}`).\n"
        f"• **Patrullaje:** `Ciclo #{status.get('cycle_count', 0)}` en `{status.get('active_symbol', status.get('symbol', 'SOL/USDT'))}` ({status.get('timeframe', '4h')}).\n"
        f"• **Estrategia / Motor:** `{status.get('strategy', 'donchian_breakout_1h')}` vía `{status.get('engine', 'antigravity_operador')}`.\n"
        f"• **Posiciones Abiertas:** `{len(positions)}/{status.get('max_positions', 2)} slots` ocupados.\n"
        f"• **Bóvedas:** `{vaults.get('USDT', 0):.2f} USDT` | `${vaults.get('USD', 0):.2f} USD` | `${vaults.get('ARS', 0):,.2f} ARS`.\n"
        f"• **Último Veredicto:** `{status.get('last_signal', 'MANTENER')}`.\n"
        f"• **Condición Técnica:** {status.get('last_reason', 'Esperando confluencia en Tríada 1D-1H-5M y cierre de vela')}."
    )
    return {"reply": reply, "timestamp": now_iso, "action": "CHAT_RESPONSE"}


if __name__ == "__main__":
    import uvicorn
    # Arranque estandarizado backend.main:app (Bloque 5 item 8)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=18767, reload=False)
