"""
Compuerta determinista previa a la entrada (auditoría de rendimiento 19-oct-2026).

Centraliza, en Python puro y sobre retornos NETOS, las reglas que evitan abrir operaciones
con esperanza matemática negativa. Se usa tanto en `get_analysis` (API/UI) como en el daemon,
de modo que ambos caminos apliquen exactamente la misma política:

1. R:R neto mínimo (MIN_NET_RR) tras comisiones y spread.
2. Stop fuera del ruido: SL bruto >= 1.5 x ATR%.
3. Volumen relativo mínimo (régimen sin volumen = ruido).
4. Blackout de apertura de Wall Street (primeros 15 min) para acciones/ETFs.
5. Anti-churn: cooldown y memoria de precio tras cierres recientes del mismo símbolo.
6. Revalidación de la directiva del CIO (vigencia, rango de entrada) antes de comprar.
"""

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.quant_risk import (
    MIN_ENTRY_RVOL,
    MIN_NET_RR,
    SL_ATR_NOISE_MULTIPLIER,
    net_rr_metrics,
)

try:  # zoneinfo es estándar desde Python 3.9
    from zoneinfo import ZoneInfo

    NY_TZ: Any = ZoneInfo("America/New_York")
    ARG_TZ: Any = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:  # pragma: no cover - fallback sin base de zonas horarias
    NY_TZ = None
    ARG_TZ = None

OPENING_BLACKOUT_MIN: int = 15          # minutos sin entradas tras la campana de NY
PRE_CLOSE_BLACKOUT_MIN: int = 30       # minutos antes del cierre donde se prohíbe abrir nuevas posiciones
AUTO_FLATTEN_WINDOW_MIN: int = 15      # minutos antes del cierre donde se liquida automáticamente intradía
RADAR_TTL_HOURS: float = 4.0            # vigencia de una directiva del CIO para ejecutar entradas
CIO_ENTRY_TOLERANCE_PCT: float = 0.25   # tolerancia sobre el techo del rango de entrada del CIO
CHURN_COOLDOWN_MIN_STOP: float = 45.0   # minutos tras Stop Loss
CHURN_COOLDOWN_MIN_SOFT: float = 120.0  # minutos tras Breakeven/Trailing/salida inteligente
CHURN_PRICE_MEMORY_HOURS: float = 6.0   # ventana de memoria de precio de la última salida
CHURN_PRICE_BAND_PCT: float = 0.5       # no recomprar dentro de +-0.5% del último precio de salida
MAX_ENTRY_SPREAD_PCT: float = 0.35      # cerco de liquidez: spread máximo tolerable por orden (0.35%)


def _is_crypto(symbol: str) -> bool:
    return "/" in str(symbol or "")


def is_btc(symbol: str) -> bool:
    s = str(symbol or "").strip().upper()
    return s in ("BTC/USDT", "BTC-USD", "BTC/USD", "BTC/BUSD", "BTC/USDC") or s.startswith("BTC/") or s.startswith("BTC-")


def is_crypto_altcoin(symbol: str) -> bool:
    s = str(symbol or "").strip().upper()
    return "/" in s and not is_btc(s)


_BTC_MACRO_CACHE: Dict[str, Any] = {"expires_at": 0.0, "data": None}


def get_btc_macro_status(
    force_refresh: bool = False,
    candles_override: Optional[List[List[float]]] = None,
    ttl_seconds: float = 15.0,
) -> Dict[str, Any]:
    global _BTC_MACRO_CACHE
    import time
    now = time.time()
    if not force_refresh and candles_override is None and _BTC_MACRO_CACHE.get("expires_at", 0) > now:
        cached = _BTC_MACRO_CACHE.get("data")
        if cached is not None:
            return cached

    default_res = {
        "btc_close": 0.0,
        "btc_ema_200_1h": 0.0,
        "btc_vwap_daily": 0.0,
        "below_ema200": False,
        "below_vwap": False,
        "veto_active": False,
        "reason": "",
    }

    candles = candles_override
    if candles is None:
        try:
            from backend.main import get_ohlcv
            candles = get_ohlcv("BTC/USDT", "1h", 220)
        except Exception:
            candles = None

    if not candles or len(candles) < 20:
        if _BTC_MACRO_CACHE.get("data") is not None:
            return _BTC_MACRO_CACHE["data"]
        return default_res

    try:
        import pandas as pd
        import ta

        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        window_ema = min(200, len(df))
        df["ema_200"] = ta.trend.EMAIndicator(close=df["close"], window=window_ema).ema_indicator()
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        day_key = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.floor("D")
        cum_pv = (typical_price * df["volume"]).groupby(day_key).cumsum()
        cum_vol = df["volume"].groupby(day_key).cumsum()
        df["vwap"] = (cum_pv / cum_vol.where(cum_vol > 0)).fillna(df["close"])

        latest = df.iloc[-1]
        c = float(latest["close"])
        e = float(latest["ema_200"]) if not pd.isna(latest["ema_200"]) else c
        v = float(latest["vwap"]) if not pd.isna(latest["vwap"]) else c

        below_ema = bool(c < e)
        below_vwap = bool(c < v)
        veto_active = bool(below_ema or below_vwap)

        reasons = []
        if below_ema:
            reasons.append(f"BTC cotiza bajo EMA200 1H (${c:.2f} < ${e:.2f})")
        if below_vwap:
            reasons.append(f"BTC cotiza bajo VWAP diario (${c:.2f} < ${v:.2f})")

        res = {
            "btc_close": round(c, 2),
            "btc_ema_200_1h": round(e, 2),
            "btc_vwap_daily": round(v, 2),
            "below_ema200": below_ema,
            "below_vwap": below_vwap,
            "veto_active": veto_active,
            "reason": " y ".join(reasons) if reasons else "BTC sobre EMA200 1H y sobre VWAP diario (Macro Alcista)",
        }
        _BTC_MACRO_CACHE["expires_at"] = now + ttl_seconds
        _BTC_MACRO_CACHE["data"] = res
        return res
    except Exception:
        if _BTC_MACRO_CACHE.get("data") is not None:
            return _BTC_MACRO_CACHE["data"]
        return default_res


def check_btc_macro_veto(
    symbol: str,
    order_side: str = "BUY",
    btc_macro_override: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Veto Macro de Bitcoin (Medida Inmediata 2):
    Si BTC cotiza por debajo de su EMA200 en 1H o bajo su VWAP del día,
    bloqueo estricto de compras LONG en cualquier altcoin (XRP, SOL, ETH, BNB, etc.).
    """
    side = str(order_side or "BUY").strip().upper()
    if side not in ("BUY", "LONG"):
        return None  # No veta operaciones SHORT

    if not is_crypto_altcoin(symbol):
        return None  # Aplica exclusivamente a altcoins cripto

    btc_status = btc_macro_override or get_btc_macro_status()
    if btc_status.get("veto_active"):
        reason = btc_status.get("reason", "BTC bajo EMA200 1H o bajo VWAP diario")
        return (
            f"Veto Macro Bitcoin: {reason} [Tick BTC: ${btc_status.get('btc_close', 0):.2f}]. "
            f"Bloqueo estricto de compras LONG en altcoin ({symbol}) sin importar Z-Score (Medida Inmediata 2)."
        )
    return None


def is_us_equity_symbol(symbol: str) -> bool:
    sym = str(symbol or "").strip().upper()
    return bool(sym) and "/" not in sym and "=F" not in sym and "=X" not in sym and not sym.endswith(".BA")


def in_opening_blackout(symbol: str, now_dt: Optional[datetime] = None) -> bool:
    """True durante los primeros OPENING_BLACKOUT_MIN minutos de la sesión regular de NY para acciones/ETFs."""
    if not is_us_equity_symbol(symbol) or NY_TZ is None:
        return False
    now = now_dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    ny = now.astimezone(NY_TZ)
    if ny.weekday() >= 5:
        return False
    minutes = ny.hour * 60 + ny.minute
    open_min = 9 * 60 + 30
    return open_min <= minutes < open_min + OPENING_BLACKOUT_MIN


def in_pre_close_blackout(symbol: str, now_dt: Optional[datetime] = None) -> bool:
    """
    True si estamos a menos de PRE_CLOSE_BLACKOUT_MIN minutos del cierre de sesión regular (o con mercado cerrado)
    para acciones y ETFs con horario bursátil (Wall Street o BYMA).
    Cripto (con '/') retorna siempre False (opera 24/7).
    """
    if _is_crypto(symbol):
        return False

    now = now_dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    sym = str(symbol or "").strip().upper()

    # Acciones y ETFs de EE.UU. (NYSE / NASDAQ)
    if is_us_equity_symbol(sym):
        if NY_TZ is None:
            return False
        ny = now.astimezone(NY_TZ)
        if ny.weekday() >= 5:  # Fin de semana
            return True
        minutes = ny.hour * 60 + ny.minute
        open_min = 9 * 60 + 30
        close_min = 16 * 60
        # Fuera de horario regular o en los últimos 30 minutos antes del cierre
        if minutes < open_min or minutes >= close_min:
            return True
        return (close_min - PRE_CLOSE_BLACKOUT_MIN) <= minutes < close_min

    # Acciones y CEDEARs de BYMA (.BA)
    if sym.endswith(".BA"):
        if ARG_TZ is None:
            return False
        arg = now.astimezone(ARG_TZ)
        if arg.weekday() >= 5:
            return True
        minutes = arg.hour * 60 + arg.minute
        open_min = 11 * 60
        close_min = 17 * 60
        if minutes < open_min or minutes >= close_min:
            return True
        return (close_min - PRE_CLOSE_BLACKOUT_MIN) <= minutes < close_min

    # Mercado Forex / Divisas (=X): 24/5
    if "=X" in sym:
        weekday = now.weekday()
        utc_minutes = now.hour * 60 + now.minute
        if weekday == 5:  # Sábado cerrado
            return True
        if weekday == 6 and utc_minutes < 21 * 60:  # Domingo antes de 21:00 UTC (18:00 ARG)
            return True
        if weekday == 4 and utc_minutes >= 20 * 60 + 30:  # Viernes últimos 30 min antes de 21:00 UTC (18:00 ARG)
            return True
        return False

    return False


def in_forex_sunday_spread_trap(symbol: str, now_dt: Optional[datetime] = None) -> bool:
    """
    True durante las primeras 3 horas de reapertura dominical de Forex (18:00 a 21:00 ARG / 21:00 a 24:00 UTC),
    cuando sólo opera Wellington/Sydney con liquidez interbancaria mínima y spreads artificialmente ensanchados.
    """
    sym = str(symbol or "").strip().upper()
    if "=X" not in sym:
        return False
    now = now_dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    if now.weekday() == 6:  # Domingo UTC
        utc_minutes = now.hour * 60 + now.minute
        return 21 * 60 <= utc_minutes < 24 * 60
    return False


def should_auto_flatten_intraday(symbol: str, now_dt: Optional[datetime] = None) -> bool:
    """
    True durante los últimos AUTO_FLATTEN_WINDOW_MIN minutos antes de la campana de cierre (Timbre de Salida)
    en días hábiles para liquidar posiciones intradía de acciones/ETFs mientras el mercado todavía está abierto y líquido.
    """
    if _is_crypto(symbol):
        return False

    now = now_dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    sym = str(symbol or "").strip().upper()

    if is_us_equity_symbol(sym):
        if NY_TZ is None:
            return False
        ny = now.astimezone(NY_TZ)
        if ny.weekday() >= 5:
            return False
        minutes = ny.hour * 60 + ny.minute
        close_min = 16 * 60
        return (close_min - AUTO_FLATTEN_WINDOW_MIN) <= minutes < close_min

    if sym.endswith(".BA"):
        if ARG_TZ is None:
            return False
        arg = now.astimezone(ARG_TZ)
        if arg.weekday() >= 5:
            return False
        minutes = arg.hour * 60 + arg.minute
        close_min = 17 * 60
        return (close_min - AUTO_FLATTEN_WINDOW_MIN) <= minutes < close_min

    return False


def _parse_db_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        text = str(value).replace("T", " ").split("+")[0].strip()
        return datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def churn_block_reason(
    history: List[Dict[str, Any]],
    symbol: str,
    price: float,
    timeframe_s: int = 900,
    z_score: Optional[float] = None,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """
    Evita re-entradas inmediatas al mismo precio tras un cierre reciente (churn).
    - Cooldown: 45 min tras Stop Loss (o 3 velas si es mayor); 120 min tras Breakeven/Trailing/Inteligente/Manual.
    - Memoria de precio: 6 h sin recomprar dentro de +-0.5% del último precio de salida,
      salvo capitulación nueva (Z <= -2.0).
    """
    now = now or datetime.now(timezone.utc)
    for tr in history or []:
        if tr.get("symbol") != symbol or str(tr.get("status", "")).upper() != "CLOSED":
            continue
        closed = _parse_db_ts(tr.get("closed_at"))
        if closed is None:
            continue
        age_min = (now - closed).total_seconds() / 60.0
        reason = str(tr.get("exit_reason") or "")
        if reason.lower().startswith("stop"):
            cooldown = max(CHURN_COOLDOWN_MIN_STOP, 3 * timeframe_s / 60.0)
        else:
            cooldown = CHURN_COOLDOWN_MIN_SOFT
        if age_min < cooldown:
            return (
                f"Anti-churn: {symbol} cerró hace {age_min:.0f} min por '{reason or 'n/d'}'; "
                f"cooldown de {cooldown:.0f} min activo."
            )
        exit_px = tr.get("exit_price")
        try:
            exit_px = float(exit_px)
        except (TypeError, ValueError):
            exit_px = 0.0
        if (
            exit_px > 0
            and price > 0
            and age_min < CHURN_PRICE_MEMORY_HOURS * 60.0
            and abs(price / exit_px - 1.0) * 100.0 < CHURN_PRICE_BAND_PCT
            and not (z_score is not None and z_score <= -2.0)
        ):
            return (
                f"Anti-churn: precio {price:.2f} a {abs(price / exit_px - 1.0) * 100.0:.2f}% del último cierre "
                f"({exit_px:.2f}) hace {age_min:.0f} min, sin capitulación nueva (Z <= -2.0)."
            )
        return None  # solo importa el cierre más reciente del símbolo
    return None


_RANGE_RE = re.compile(
    r"entrada[^0-9\-]{0,20}([0-9]+(?:[.,][0-9]+)?)\s*(?:-|–|a|hasta)\s*([0-9]+(?:[.,][0-9]+)?)",
    re.IGNORECASE,
)


def parse_entry_range(text: str) -> Optional[tuple]:
    """Extrae (bajo, alto) de textos como 'Entrada: 706.00 - 712.00 USD'. None si no hay rango."""
    if not text:
        return None
    match = _RANGE_RE.search(str(text))
    if not match:
        return None
    try:
        lo = float(match.group(1).replace(",", "."))
        hi = float(match.group(2).replace(",", "."))
    except ValueError:
        return None
    if lo <= 0 or hi <= 0:
        return None
    return (min(lo, hi), max(lo, hi))


def cio_directive_failures(
    card_text: str,
    card_timestamp: Any,
    price: float,
    now: Optional[datetime] = None,
) -> List[str]:
    """
    Revalida una directiva del CIO antes de ejecutar una compra.
    Nota: Z-Score/RSI de la tesis son métricas diarias del Monitor; el bot opera en 15m, por lo que
    la revalidación usa vigencia y rango de entrada (precio), que sí son comparables.
    """
    failures: List[str] = []
    now = now or datetime.now(timezone.utc)

    ts = None
    if card_timestamp:
        try:
            text = str(card_timestamp).replace("Z", "+00:00")
            ts = datetime.fromisoformat(text)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except ValueError:
            ts = None
    if ts is not None:
        age_h = (now - ts).total_seconds() / 3600.0
        if age_h > RADAR_TTL_HOURS:
            failures.append(
                f"Directiva del CIO caducada ({age_h:.1f} h > {RADAR_TTL_HOURS:.0f} h de vigencia para ejecutar)."
            )

    rng = parse_entry_range(card_text)
    if rng and price > 0:
        lo, hi = rng
        ceiling = hi * (1.0 + CIO_ENTRY_TOLERANCE_PCT / 100.0)
        if price > ceiling:
            failures.append(
                f"Precio {price:.2f} por encima del rango de entrada del CIO ({lo:.2f}-{hi:.2f}); "
                "se espera retroceso, no se persigue el precio."
            )
    return failures


def entry_gate_failures(
    symbol: str,
    price: float,
    tp_gross_pct: float,
    sl_gross_pct: float,
    fee_pct: float,
    spread_pct: float,
    atr: Optional[float] = None,
    rvol: Optional[float] = None,
    now_dt: Optional[datetime] = None,
    order_side: str = "BUY",
    btc_macro_override: Optional[Dict[str, Any]] = None,
    lower_wick_ratio: Optional[float] = None,
    candle_color: Optional[str] = None,
    skip_btc_macro_veto: bool = False,
    timeframe: Optional[str] = None,
) -> List[str]:
    """Lista de motivos por los que NO debe abrirse una posición nueva (vacía = aprobada)."""
    failures: List[str] = []

    # 1. Veto Macro de Bitcoin (Medida Inmediata 2):
    # Si BTC cotiza bajo EMA200 1H o bajo VWAP diario, bloqueo estricto de compras LONG en altcoins.
    # Se omite durante sesiones presenciales de scalping supervisadas con Árbitro IA propio.
    if not skip_btc_macro_veto:
        btc_veto = check_btc_macro_veto(symbol, order_side=order_side, btc_macro_override=btc_macro_override)
        if btc_veto:
            failures.append(btc_veto)

    # 2. Veto Centinela: Cuchillo Cayendo (Falling Knife Shield)
    # Si la orden es de COMPRA (LONG) y la vela cae en picada vertical sin mecha de absorción (< 15%),
    # prohibido comprar antes de que la vela cierre y muestre freno o rechazo.
    if str(order_side or "BUY").strip().upper() in ("BUY", "LONG") and lower_wick_ratio is not None and math.isfinite(lower_wick_ratio):
        is_red = (candle_color or "").strip().upper() in ("RED", "BEARISH")
        if lower_wick_ratio < 0.15 and is_red:
            failures.append(
                f"Veto Centinela Cuchillo Cayendo: vela bajista en caída vertical sin absorción previa "
                f"(mecha inferior {lower_wick_ratio * 100:.1f}% < 15.0%). Prohibido comprar en pleno descenso institucional."
            )

    if not all(map(math.isfinite, [price, tp_gross_pct, sl_gross_pct, fee_pct, spread_pct])) or price <= 0:
        failures.append("Parámetros numéricos inválidos (NaN/Inf o precio <= 0) en compuerta de entrada.")
        return failures

    rr = net_rr_metrics(tp_gross_pct, sl_gross_pct, fee_pct, spread_pct)
    if not rr["valid"] or rr["net_rr"] < MIN_NET_RR:
        failures.append(
            f"R:R neto {rr['net_rr']:.2f} < {MIN_NET_RR:.2f} (TP +{tp_gross_pct:.2f}% / SL -{sl_gross_pct:.2f}% brutos; "
            f"neto +{rr['tp_net_pct']}% / {rr['sl_net_pct']}%; acierto de equilibrio {rr['breakeven_win_rate'] * 100:.0f}%)."
        )

    if atr is not None:
        if not math.isfinite(atr) or atr <= 0:
            failures.append("ATR inválido (<= 0 o NaN): imposible verificar distancia de Stop frente al ruido.")
        elif price > 0:
            atr_pct = atr / price * 100.0
            tf_norm = str(timeframe or "").strip().lower()
            min_atr_mult = 1.0 if tf_norm in ("4h", "1d", "daily", "d") else SL_ATR_NOISE_MULTIPLIER
            if sl_gross_pct + 1e-6 < min_atr_mult * atr_pct:
                failures.append(
                    f"Stop dentro del ruido: SL {sl_gross_pct:.2f}% < {min_atr_mult:.1f}xATR ({min_atr_mult * atr_pct:.2f}%)."
                )

    is_forex_spot = "=X" in str(symbol or "").upper()
    if rvol is not None and math.isfinite(rvol) and rvol < MIN_ENTRY_RVOL:
        # En Forex spot (=X) Yahoo Finance reporta Volume=0; no penalizar por limitación del feed gratuito
        if not (is_forex_spot and rvol <= 0.0):
            failures.append(f"Volumen relativo {rvol:.2f} < {MIN_ENTRY_RVOL:.2f}: sin participación suficiente.")

    if spread_pct > MAX_ENTRY_SPREAD_PCT:
        failures.append(
            f"Cerco de liquidez: spread excesivo ({spread_pct:.2f}% > {MAX_ENTRY_SPREAD_PCT:.2f}%). Fricción confiscatoria en activo ilíquido."
        )

    if in_forex_sunday_spread_trap(symbol, now_dt):
        failures.append(
            "Veto Apertura Dominical Forex (18:00-21:00 ARG · Wellington/Sydney): liquidez interbancaria mínima "
            "y spreads ensanchados. Operativa habilitada a partir de Tokio (21:00 ARG) / Londres (04:00 ARG)."
        )

    if in_opening_blackout(symbol, now_dt):
        failures.append(
            f"Blackout de apertura de Wall Street: sin entradas durante los primeros {OPENING_BLACKOUT_MIN} min de campana."
        )

    if in_pre_close_blackout(symbol, now_dt):
        failures.append(
            f"Ventana Pre-Cierre Bursátil: prohibido abrir compras en acciones/ETFs a menos de {PRE_CLOSE_BLACKOUT_MIN} min "
            "del toque de campana (o fuera de rueda) para eliminar riesgo de Gap Overnight."
        )

    return failures

