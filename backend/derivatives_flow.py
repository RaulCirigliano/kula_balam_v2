# -*- coding: utf-8 -*-
"""
Flujo de Derivados Cripto (Binance USDⓈ-M Futures, endpoints públicos sin API key).

Expone Funding Rate liquidado y Open Interest como telemetría y como filtro de
confirmación opcional para cortos de donchian_breakout_1h.

Evidencia (backtest_lab/auditar_filtro_derivados.py, SOL+ETH 4H, 2023-11 -> 2026-11):
  - Hipótesis H1 "SHORT solo si funding_last > 0":
      SHORTs N 25 -> 17 | PF 1.63 -> 2.05 | DD 20.1% -> 11.8% | OOS PF total 1.10 -> 1.38.
  - Muestra reducida (8 cortos vetados): sin significancia estadística robusta.
    Por eso el filtro arranca en MODO SOMBRA (registra el veto sin bloquear).
  - Open Interest: Binance solo publica ~30 días de histórico -> no validable en
    Walk-Forward; se expone únicamente como telemetría descriptiva.

Política de fallo: FAIL-OPEN. Si la API no responde, el filtro no bloquea y lo informa.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

FAPI_BASE = "https://fapi.binance.com"
CACHE_TTL_S = 300.0
HTTP_TIMEOUT_S = 4.0
OI_LOOKBACK_BARS_4H = 6  # 24 horas

_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def to_futures_symbol(symbol: str) -> Optional[str]:
    """'SOL/USDT' -> 'SOLUSDT'. Devuelve None para activos sin perpetuo USDT (acciones, FX, micro-futuros)."""
    s = str(symbol or "").upper().strip()
    if "/" in s:
        base, quote = s.split("/", 1)
        quote = quote.split(":", 1)[0]
        if quote in ("USDT", "USDC") and base.isalnum():
            return f"{base}{quote}"
        return None
    if s.endswith("USDT") and s.isalnum():
        return s
    return None


def _fetch(fut_symbol: str) -> Dict[str, Any]:
    with httpx.Client(timeout=HTTP_TIMEOUT_S) as cli:
        fr = cli.get(f"{FAPI_BASE}/fapi/v1/fundingRate", params={"symbol": fut_symbol, "limit": 3})
        fr.raise_for_status()
        rates = [float(x["fundingRate"]) for x in fr.json()]
        if not rates:
            raise ValueError("fundingRate vacío")
        oi = cli.get(
            f"{FAPI_BASE}/futures/data/openInterestHist",
            params={"symbol": fut_symbol, "period": "4h", "limit": OI_LOOKBACK_BARS_4H + 1},
        )
        oi.raise_for_status()
        oi_rows = oi.json()
    oi_now = float(oi_rows[-1]["sumOpenInterest"]) if oi_rows else None
    oi_prev = float(oi_rows[0]["sumOpenInterest"]) if len(oi_rows) > 1 else None
    oi_chg = ((oi_now / oi_prev) - 1.0) * 100.0 if (oi_now and oi_prev) else None
    return {
        "available": True,
        "futures_symbol": fut_symbol,
        "funding_last": rates[-1],
        "funding_24h_avg": sum(rates) / len(rates),
        "open_interest": oi_now,
        "oi_change_pct_24h": round(oi_chg, 3) if oi_chg is not None else None,
        "error": None,
        "fetched_at": time.time(),
    }


def get_derivatives_snapshot(symbol: str, use_cache: bool = True) -> Dict[str, Any]:
    """Snapshot de funding/OI con caché TTL de 5 minutos. Nunca lanza excepciones."""
    fut = to_futures_symbol(symbol)
    if not fut:
        return {"available": False, "futures_symbol": None, "error": "Sin perpetuo USDT para este activo."}
    now = time.time()
    if use_cache:
        with _cache_lock:
            hit = _cache.get(fut)
            if hit and (now - hit[0]) < CACHE_TTL_S:
                return dict(hit[1])
    try:
        snap = _fetch(fut)
    except Exception as exc:  # noqa: BLE001 - fail-open deliberado
        logger.warning(f"[DERIVADOS] Snapshot no disponible para {fut}: {exc}")
        snap = {"available": False, "futures_symbol": fut, "error": str(exc), "fetched_at": now}
    with _cache_lock:
        _cache[fut] = (now, snap)
    return dict(snap)


def evaluate_short_funding_gate(snapshot: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Hipótesis H1: un SHORT se confirma solo si el último funding liquidado es > 0
    (el lado largo aún paga apalancamiento: hay combustible para liquidaciones en cascada).
    Fail-open si no hay datos.
    """
    if not snapshot or not snapshot.get("available"):
        err = (snapshot or {}).get("error") or "sin datos"
        return True, f"Filtro funding sin datos ({err}); fail-open."
    f_last = float(snapshot.get("funding_last") or 0.0)
    oi_txt = snapshot.get("oi_change_pct_24h")
    oi_desc = f", OI 24h {oi_txt:+.2f}%" if isinstance(oi_txt, (int, float)) else ""
    if f_last > 0:
        return True, f"Funding {f_last * 100:+.4f}% > 0: largos apalancados, corto confirmado{oi_desc}."
    return False, (
        f"Funding {f_last * 100:+.4f}% <= 0: cortos ya saturados (riesgo de short squeeze){oi_desc}."
    )
