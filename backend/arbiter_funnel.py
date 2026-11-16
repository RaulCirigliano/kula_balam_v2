# -*- coding: utf-8 -*-
"""
Módulo: backend/arbiter_funnel.py
Embudo de Arbitraje On-Demand para Kula Balam.
Se ejecuta únicamente cuando la entrada cuantitativa ya ha sido validada por el motor matemático.
Consulta titulares vía `news_collector.py`, calcula el Vector de Impacto Estructurado
(NLP Sentiment Score, VIX, Derivados, Buffer Macro y ciclo de vela 4H) y aplica compuertas
de veto por choque estructural, pánico de volatilidad o alertas críticas bajo política fail-open.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from backend.news_collector import (
    collect_headlines_for_symbol,
    collect_regime_and_sentiment_indices,
)

logger = logging.getLogger(__name__)

# Palabras clave de alertas críticas estructurales que justifican un veto de emergencia
UNIVERSAL_SHOCK_KEYWORDS = (
    "FOMC",
    "CPI SURPRISE",
    "INTEREST RATE HIKE",
    "EMERGENCY RATE",
    "BANKS HALT",
    "BLACK SWAN",
    "WAR ESCALATION",
    "NUCLEAR",
    "MISSILE STRIKE",
)

LONG_VETO_KEYWORDS = (
    "HACK",
    "EXPLOIT",
    "INSOLVENCY",
    "BANKRUPTCY",
    "FRAUD",
    "SEC LAWSUIT",
    "DELISTING",
    "DEPEG",
    "HALT TRADING",
    "EXCHANGE COLLAPSE",
    "RUG PULL",
)

SHORT_VETO_KEYWORDS = (
    "SHORT SQUEEZE",
    "ETF APPROVAL",
    "STRATEGIC RESERVE",
    "MASSIVE BUYBACK",
    "HOSTILE TAKEOVER",
    "BAILOUT",
)

NLP_BEARISH_TERMS = (
    "MISS",
    "DOWNGRADE",
    "PLUNGE",
    "OUTFLOW",
    "LIQUIDATION",
    "HAWKISH",
    "CRASH",
    "BEAR",
    "INFLATION SURGE",
)

NLP_BULLISH_TERMS = (
    "BEAT",
    "UPGRADE",
    "INFLOW",
    "APPROVAL",
    "DOVISH",
    "RECORD HIGH",
    "RALLY",
    "BULL",
    "SURGE",
)


def build_impact_vector(
    symbol: str,
    side: str,
    headlines: List[Dict[str, str]],
    indices: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Traduce las noticias crudas y los índices cuantitativos en un Vector de Impacto Estructurado:
      - nlp_sentiment_score (-100 a +100)
      - event_type: SYSTEMIC_SHOCK | ASSET_HAZARD | DIRECTIONAL_CATALYST | VIX_PANIC | NONE
      - implied_bias: ALCISTA | BAJISTA | CLIMA_VOLATILIDAD | NEUTRAL
      - near_4h_close: True si restan <= 30 min para el cierre de vela 4H
    """
    metrics = metrics or {}
    norm_side = str(side or "").upper()
    vix_lvl = indices.get("vix_level")
    vix_chg = float(indices.get("vix_change_pct") or 0.0)

    # 1. Puntuación de Sentimiento NLP (-100 a +100)
    sentiment_raw = 0.0
    detected_events = []
    has_universal_shock = False
    has_asset_hazard = False
    has_directional_catalyst = False

    for h in headlines:
        txt = f"{str(h.get('title') or '')} {str(h.get('summary') or '')}".upper()

        for kw in UNIVERSAL_SHOCK_KEYWORDS:
            if kw in txt:
                has_universal_shock = True
                sentiment_raw -= 60.0
                detected_events.append(f"SHOCK:{kw}")

        for kw in LONG_VETO_KEYWORDS:
            if kw in txt:
                has_asset_hazard = True
                sentiment_raw -= 40.0
                detected_events.append(f"HAZARD:{kw}")

        for kw in SHORT_VETO_KEYWORDS:
            if kw in txt:
                has_directional_catalyst = True
                sentiment_raw += 40.0
                detected_events.append(f"CATALYST:{kw}")

        for term in NLP_BEARISH_TERMS:
            if term in txt:
                sentiment_raw -= 20.0

        for term in NLP_BULLISH_TERMS:
            if term in txt:
                sentiment_raw += 20.0

    sentiment_score = max(-100.0, min(100.0, sentiment_raw))

    # 2. Clasificación del Tipo de Evento
    if has_universal_shock:
        event_type = "SYSTEMIC_SHOCK"
    elif has_asset_hazard:
        event_type = "ASSET_HAZARD"
    elif has_directional_catalyst:
        event_type = "DIRECTIONAL_CATALYST"
    elif vix_lvl is not None and (vix_lvl >= 28.5 or vix_chg >= 12.0):
        event_type = "VIX_PANIC"
    else:
        event_type = "NONE"

    # 3. Sesgo Implícito
    if event_type == "SYSTEMIC_SHOCK" or any("CPI" in e or "FOMC" in e for e in detected_events):
        implied_bias = "CLIMA_VOLATILIDAD"
    elif sentiment_score <= -30.0 or event_type in ("ASSET_HAZARD", "VIX_PANIC"):
        implied_bias = "BAJISTA"
    elif sentiment_score >= 30.0 or event_type == "DIRECTIONAL_CATALYST":
        implied_bias = "ALCISTA"
    else:
        implied_bias = "NEUTRAL"

    # 4. Sincronización con el Ciclo de Vela 4H (últimos 30 minutos antes del cierre)
    now_utc = datetime.now(timezone.utc)
    near_4h_close = bool((now_utc.hour % 4 == 3) and (now_utc.minute >= 30))

    return {
        "symbol": symbol,
        "side": norm_side,
        "nlp_sentiment_score": round(sentiment_score, 1),
        "event_type": event_type,
        "implied_bias": implied_bias,
        "near_4h_close": near_4h_close,
        "vix_level": vix_lvl,
        "vix_change_pct": vix_chg,
        "funding_last": indices.get("funding_last"),
        "macro_buffer_bias": indices.get("macro_buffer_bias"),
        "market_context_regime": indices.get("market_context_regime"),
        "market_context_veto": indices.get("market_context_veto", False),
    }


def arbitrate_signal(
    symbol: str,
    side: str,
    price: float,
    sl_pct: float,
    tp_pct: float,
    strategy: str,
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Función síncrona y segura de arbitraje informativo.
    Solo se invoca cuando la entrada cuantitativa ya ha sido validada por el motor matemático.
    Retorna un diccionario:
      {
         "verdict": "OPERAR" | "AHORA_NO",
         "reason": str,
         "headlines": List[Dict[str, str]],
         "impact_vector": Dict[str, Any]
      }
    Fail-Open: En caso de timeout, falta de red o cualquier excepción interna,
    el veredicto es "OPERAR" para no asfixiar el algoritmo.
    """
    metrics = metrics or {}
    norm_side = str(side or "").upper()
    headlines: List[Dict[str, str]] = []

    try:
        headlines = collect_headlines_for_symbol(symbol, timeout_s=3.5)
    except Exception as exc:
        logger.warning(f"Error al recolectar titulares para arbitraje en {symbol}: {exc}")
        return {
            "verdict": "OPERAR",
            "reason": f"Fail-Open: Error en colector de noticias ({exc}). Señal matemática permitida.",
            "headlines": [],
            "impact_vector": {},
        }

    # Recolectar índices de régimen y construir Vector de Impacto (Fail-Open)
    try:
        indices = collect_regime_and_sentiment_indices(symbol, timeout_s=2.5)
    except Exception as exc:
        logger.debug(f"Aviso recolectando índices en arbitrate_signal para {symbol}: {exc}")
        indices = {}

    impact_vector = build_impact_vector(symbol, norm_side, headlines, indices, metrics)

    # 1. Auditoría de Choque Estructural por Reglas Cuantitativas de Texto
    for h in headlines:
        title_upper = str(h.get("title") or "").upper()
        summary_upper = str(h.get("summary") or "").upper()
        full_text = f"{title_upper} {summary_upper}"

        # Choque universal inminente (macro cisne negro)
        for kw in UNIVERSAL_SHOCK_KEYWORDS:
            if kw in full_text:
                reason = f"Veto Árbitro Informativo: Alerta macro crítica detectada ('{kw}') en titular: '{h.get('title')}'."
                logger.info(f"🚫 [ARBITER VETO] {symbol} {norm_side} rechazado: {reason}")
                return {
                    "verdict": "AHORA_NO",
                    "reason": reason,
                    "headlines": headlines,
                    "impact_vector": impact_vector,
                }

        # Choques específicos por dirección
        if norm_side in ("LONG", "BUY"):
            for kw in LONG_VETO_KEYWORDS:
                if kw in full_text:
                    reason = f"Veto Árbitro Informativo: Riesgo bajista severo / insolvencia ('{kw}') en titular: '{h.get('title')}'."
                    logger.info(f"🚫 [ARBITER VETO] {symbol} LONG rechazado: {reason}")
                    return {
                        "verdict": "AHORA_NO",
                        "reason": reason,
                        "headlines": headlines,
                        "impact_vector": impact_vector,
                    }
        elif norm_side in ("SHORT", "SELL"):
            for kw in SHORT_VETO_KEYWORDS:
                if kw in full_text:
                    reason = f"Veto Árbitro Informativo: Riesgo de squeeze o catalizador alcista ('{kw}') en titular: '{h.get('title')}'."
                    logger.info(f"🚫 [ARBITER VETO] {symbol} SHORT rechazado: {reason}")
                    return {
                        "verdict": "AHORA_NO",
                        "reason": reason,
                        "headlines": headlines,
                        "impact_vector": impact_vector,
                    }

    # 2. Veto por Pánico en Índice ^VIX (CBOE) para compras (LONG)
    if norm_side in ("LONG", "BUY"):
        vix = indices.get("vix_level")
        vix_chg = float(indices.get("vix_change_pct") or 0.0)
        if vix is not None:
            is_equity = ("/" not in symbol and "=X" not in symbol)
            if is_equity and (vix >= 28.5 or vix_chg >= 12.0):
                reason = f"Veto Árbitro Informativo: Pánico sistémico en índice VIX ({vix:.2f}, cambio {vix_chg:+.1f}%) invalida compras en acciones ({symbol})."
                logger.info(f"🚫 [ARBITER VIX VETO] {symbol}: {reason}")
                return {
                    "verdict": "AHORA_NO",
                    "reason": reason,
                    "headlines": headlines,
                    "impact_vector": impact_vector,
                }
            elif (not is_equity) and ("/" in symbol) and (vix >= 32.0 and vix_chg >= 15.0):
                reason = f"Veto Árbitro Informativo: Contagio macro de liquidez por shock extremo en VIX ({vix:.2f}, cambio {vix_chg:+.1f}%) invalida compras cripto ({symbol})."
                logger.info(f"🚫 [ARBITER VIX VETO] {symbol}: {reason}")
                return {
                    "verdict": "AHORA_NO",
                    "reason": reason,
                    "headlines": headlines,
                    "impact_vector": impact_vector,
                }

    # 3. Veto por Buffer Macro CIO o Contexto de Mercado en Crisis
    if indices.get("market_context_veto") is True or str(indices.get("macro_buffer_bias") or "").upper() == "PELIGRO":
        reason = "Veto Árbitro Informativo: Directiva activa de PELIGRO / Crisis en Buffer Macro CIO."
        logger.info(f"🚫 [ARBITER MACRO VETO] {symbol}: {reason}")
        return {
            "verdict": "AHORA_NO",
            "reason": reason,
            "headlines": headlines,
            "impact_vector": impact_vector,
        }

    # 4. Veto por Clima de Volatilidad en Ventana de Cierre de Vela 4H (últimos 30m)
    if impact_vector.get("near_4h_close") and (impact_vector.get("implied_bias") == "CLIMA_VOLATILIDAD" or (indices.get("vix_level") or 0.0) >= 25.0):
        rr = tp_pct / max(sl_pct, 1e-9)
        if rr < 2.30:
            reason = f"Veto Árbitro Informativo: Precaución por cierre de vela 4H en clima de volatilidad (R:R {rr:.2f} < 2.30)."
            logger.info(f"🚫 [ARBITER 4H VETO] {symbol}: {reason}")
            return {
                "verdict": "AHORA_NO",
                "reason": reason,
                "headlines": headlines,
                "impact_vector": impact_vector,
            }

    return {
        "verdict": "OPERAR",
        "reason": "Veredicto Árbitro: Confluencia cuantitativa aprobada; sin veto informativo ni alertas críticas.",
        "headlines": headlines,
        "impact_vector": impact_vector,
    }
