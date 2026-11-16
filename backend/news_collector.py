# -*- coding: utf-8 -*-
"""
Módulo: backend/news_collector.py
Colector Quirúrgico de Noticias y Sensores de Régimen para Kula Balam.
Consulta titulares específicos por activo bajo demanda con caché TTL de 300 segundos,
conectando al Monitor del Mercado (puerto 8520), feeds RSS dirigidos por activo/mercado,
e índices macro institucionales (^VIX, DXY, derivados, buffer macro),
bajo política estricta fail-open sin lanzar excepciones.
"""

import time
import os
import json
import logging
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

_NEWS_CACHE: Dict[str, Dict[str, Any]] = {}
_INDICES_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS: float = 300.0


def _determine_asset_class(symbol: str) -> str:
    """Clasifica el activo en CRYPTO, FOREX o EQUITY_US."""
    clean = str(symbol or "").strip().upper()
    if "/" in clean or clean.endswith("USDT") or clean in ("BTC", "ETH", "SOL"):
        return "CRYPTO"
    if "=X" in clean or clean in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"):
        return "FOREX"
    return "EQUITY_US"


def _fetch_targeted_rss(base_sym: str, asset_class: str, timeout_s: float = 2.5) -> List[Dict[str, str]]:
    """
    Consulta Google News RSS con sintaxis booleana específica para la familia del activo.
    Retorna como máximo 5 titulares recientes de las últimas 24h.
    """
    if asset_class == "CRYPTO":
        query = f"{base_sym}+AND+(ETF+OR+hack+OR+exploit+OR+SEC+OR+liquidation+OR+FOMC+OR+CPI)+when:1d"
    elif asset_class == "FOREX":
        query = f"{base_sym}+OR+ECB+OR+Lagarde+OR+Federal+Reserve+OR+CPI+OR+NFP+when:1d"
    else:
        query = f"{base_sym}+AND+(earnings+OR+guidance+OR+SEC+OR+Fed+OR+CPI+OR+downgrade+OR+upgrade)+when:1d"

    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KulaBalam/1.0", "Accept": "application/rss+xml, text/xml"}
    )
    headlines = []
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")
            for item in items[:5]:
                t = (item.findtext("title") or "").strip()
                if t:
                    src = item.findtext("source") or "GoogleNews"
                    pub = item.findtext("pubDate") or ""
                    desc = (item.findtext("description") or t)[:280]
                    headlines.append({
                        "title": t,
                        "source": str(src),
                        "published": str(pub),
                        "summary": str(desc),
                    })
    except Exception as exc:
        logger.debug(f"Aviso en _fetch_targeted_rss para {base_sym}: {exc}")
    return headlines


def collect_headlines_for_symbol(symbol: str, timeout_s: float = 3.5) -> List[Dict[str, str]]:
    """
    Recolecta titulares recientes relevantes para el activo indicado.
    Aplica caché en memoria con TTL de 300 segundos.
    Retorna lista de diccionarios [{"title": ..., "source": ..., "published": ..., "summary": ...}].
    Estrictamente fail-open: nunca arroja excepciones hacia el llamador.
    """
    clean_sym = str(symbol or "").strip().upper()
    now = time.time()

    # 1. Comprobar caché en memoria
    cached = _NEWS_CACHE.get(clean_sym)
    if cached and (now - float(cached.get("timestamp", 0.0))) < CACHE_TTL_SECONDS:
        return list(cached.get("headlines", []))

    headlines: List[Dict[str, str]] = []
    base_sym = clean_sym.split("/")[0].replace("=X", "")
    asset_class = _determine_asset_class(clean_sym)

    # 2. Consultar el Monitor del Mercado local (http://127.0.0.1:8520)
    monitor_url = (os.environ.get("MONITOR_API_URL") or "http://127.0.0.1:8520").rstrip("/")
    endpoints = [
        f"{monitor_url}/api/reports/latest",
        f"{monitor_url}/api/news?symbol={base_sym}",
        f"{monitor_url}/api/macro/inbox",
    ]
    for url in endpoints:
        try:
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "KulaBalam-Arbiter/1.0"}
            )
            with urllib.request.urlopen(req, timeout=min(timeout_s, 2.0)) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        # Soporte para estructura reports/latest (dashboard.cards y dashboard.dangers)
                        dash = data.get("dashboard") or {}
                        if isinstance(dash, dict):
                            for card in dash.get("cards", []) + dash.get("dangers", []):
                                c_ticker = str(card.get("ticker") or "").upper()
                                c_title = str(card.get("title") or "")
                                if base_sym in c_ticker or base_sym in c_title.upper() or any(k in c_title.upper() for k in ("FED", "FOMC", "CPI", "INFLATION", "SEC", "WAR")):
                                    items.append({
                                        "title": c_title,
                                        "source": str(card.get("source") or "Monitor Dashboard"),
                                        "published": str(card.get("timestamp") or ""),
                                        "summary": str(card.get("thesis") or card.get("description") or c_title)[:280],
                                    })
                        if not items:
                            items = data.get("news") or data.get("items") or data.get("articles") or []
                        if not items and "title" in data:
                            items = [data]

                    for it in items:
                        t = str(it.get("title") or it.get("text") or "").strip()
                        if t and (base_sym in t.upper() or any(k in t.upper() for k in ("FED", "FOMC", "CPI", "INFLATION", "SEC", "WAR"))):
                            headlines.append({
                                "title": t,
                                "source": str(it.get("source") or it.get("origin") or "Monitor 8520"),
                                "published": str(it.get("published") or it.get("published_at") or it.get("timestamp") or ""),
                                "summary": str(it.get("summary") or it.get("content") or t)[:280],
                            })
                    if headlines:
                        break
        except Exception:
            continue

    # 3. Fallback de lectura desde disco (radar_inbox)
    if not headlines:
        try:
            from backend.radar_inbox import MacroRadarInbox
            inbox = MacroRadarInbox()
            active_cards = inbox.get_active_cards(clean_sym)
            for c in active_cards:
                headlines.append({
                    "title": str(c.get("text") or c.get("title") or ""),
                    "source": "RadarInbox",
                    "published": str(c.get("timestamp") or ""),
                    "summary": str(c.get("actionable") or c.get("text") or "")[:280],
                })
        except Exception:
            pass

    # 4. Fallback activo: Búsqueda RSS Quirúrgica On-Demand
    # En entorno pytest se aísla de la red externa a menos que se fuerce TEST_ALLOW_LIVE_NETWORK=1
    if not headlines:
        if not (os.getenv("PYTEST_CURRENT_TEST") and not os.getenv("TEST_ALLOW_LIVE_NETWORK")):
            headlines = _fetch_targeted_rss(base_sym, asset_class, timeout_s=min(timeout_s, 2.5))

    _NEWS_CACHE[clean_sym] = {
        "timestamp": now,
        "headlines": headlines,
    }
    return headlines


def _fetch_vix_index_safely(timeout_s: float = 2.0) -> Tuple[Optional[float], float]:
    """Obtiene el nivel y variación diaria del índice ^VIX con fail-open estricto."""
    if os.getenv("PYTEST_CURRENT_TEST") and not os.getenv("TEST_ALLOW_LIVE_NETWORK"):
        return None, 0.0
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=5d"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KulaBalam/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            res = data.get("chart", {}).get("result", [None])[0]
            if res:
                meta = res.get("meta", {})
                reg_price = meta.get("regularMarketPrice")
                prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
                if reg_price is not None:
                    lvl = float(reg_price)
                    chg = (((lvl - float(prev_close)) / float(prev_close)) * 100.0) if prev_close else 0.0
                    return round(lvl, 2), round(chg, 2)
    except Exception as exc:
        logger.debug(f"Aviso consultando VIX vía HTTP: {exc}")

    # Fallback opcional a yfinance si estuviese cacheado
    try:
        import yfinance as yf
        ticker = yf.Ticker("^VIX")
        fast = getattr(ticker, "fast_info", None)
        if fast and hasattr(fast, "last_price") and fast.last_price is not None:
            lvl = float(fast.last_price)
            prev = float(getattr(fast, "previous_close", lvl) or lvl)
            chg = (((lvl - prev) / prev) * 100.0) if prev > 0 else 0.0
            return round(lvl, 2), round(chg, 2)
    except Exception:
        pass

    return None, 0.0


def collect_regime_and_sentiment_indices(symbol: str, timeout_s: float = 2.5) -> Dict[str, Any]:
    """
    Recolecta índices institucionales complementarios (^VIX, DXY, Derivados Binance, Buffer Macro CIO).
    Aplica caché con TTL de 300 segundos y política 100% fail-open.
    """
    clean_sym = str(symbol or "").strip().upper()
    now = time.time()

    cached = _INDICES_CACHE.get(clean_sym)
    if cached and (now - float(cached.get("timestamp", 0.0))) < CACHE_TTL_SECONDS:
        return dict(cached.get("indices", {}))

    asset_class = _determine_asset_class(clean_sym)

    # 1. Obtener VIX global
    vix_cached = _INDICES_CACHE.get("^VIX")
    if vix_cached and (now - float(vix_cached.get("timestamp", 0.0))) < CACHE_TTL_SECONDS:
        vix_lvl, vix_chg = vix_cached.get("vix_level"), vix_cached.get("vix_change_pct", 0.0)
    else:
        vix_lvl, vix_chg = _fetch_vix_index_safely(timeout_s=min(timeout_s, 2.0))
        _INDICES_CACHE["^VIX"] = {"timestamp": now, "vix_level": vix_lvl, "vix_change_pct": vix_chg}

    indices: Dict[str, Any] = {
        "symbol": clean_sym,
        "asset_class": asset_class,
        "vix_level": vix_lvl,
        "vix_change_pct": vix_chg,
        "funding_last": None,
        "funding_24h_avg": None,
        "oi_delta_pct": None,
        "macro_buffer_bias": None,
        "macro_buffer_confidence": None,
        "market_context_regime": None,
        "market_context_veto": False,
    }

    # 2. Flujo de Derivados para Cripto (Binance Futures)
    if asset_class == "CRYPTO":
        try:
            from backend.derivatives_flow import get_derivatives_snapshot
            deriv_snap = get_derivatives_snapshot(clean_sym)
            if deriv_snap:
                indices["funding_last"] = deriv_snap.get("funding_last")
                indices["funding_24h_avg"] = deriv_snap.get("funding_24h_avg")
                indices["oi_delta_pct"] = deriv_snap.get("oi_delta_pct")
        except Exception as exc:
            logger.debug(f"Aviso leyendo derivados cripto para {clean_sym}: {exc}")

    # 3. Buffer Macro CIO local (0 ms)
    try:
        from backend.macro_bias_buffer import MacroBiasBuffer
        bias_rec = MacroBiasBuffer().get_bias(clean_sym)
        if bias_rec:
            indices["macro_buffer_bias"] = bias_rec.get("bias")
            indices["macro_buffer_confidence"] = bias_rec.get("confidence")
    except Exception as exc:
        logger.debug(f"Aviso leyendo MacroBiasBuffer para {clean_sym}: {exc}")

    # 4. Market Context Contract local (0 ms)
    try:
        from backend.market_context import get_active_market_context_for_symbol
        ctx = get_active_market_context_for_symbol(clean_sym)
        if ctx:
            indices["market_context_regime"] = getattr(ctx, "regime", None)
            indices["market_context_veto"] = bool(getattr(ctx, "veto_active", False))
    except Exception as exc:
        logger.debug(f"Aviso leyendo MarketContextContract para {clean_sym}: {exc}")

    _INDICES_CACHE[clean_sym] = {
        "timestamp": now,
        "indices": indices,
    }
    return indices


def clear_news_cache(symbol: Optional[str] = None) -> None:
    """Limpia la caché de titulares e índices para testing o reseteo forzado."""
    if symbol:
        s = str(symbol).strip().upper()
        _NEWS_CACHE.pop(s, None)
        _INDICES_CACHE.pop(s, None)
    else:
        _NEWS_CACHE.clear()
        _INDICES_CACHE.clear()
