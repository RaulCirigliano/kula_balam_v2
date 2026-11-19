# -*- coding: utf-8 -*-
"""
Embudo de Rechazos: etiquetado canónico y persistencia liviana de cada evaluación de vela.

Fuente única de verdad compartida por `daemon.py` (escritor), `health_watchdog.py` (Chequeo Rápido)
y `auditar_sqlite.py` (lector). No contiene reglas de entrada: solo CLASIFICA los textos de rechazo
que ya producen las fórmulas, el árbitro, `entry_gate.py` y el propio daemon.

Esquema del JSON guardado en `signals.raw_response`:
    {
      "v": 1,
      "stage": "analysis" | "gate",      # analysis = veredicto de la fórmula; gate = veto posterior (slot, gate, árbitro...)
      "strategy": "<id fórmula/estrategia efectiva>",
      "eligible": bool,                  # True si la fórmula habilitó candidata en esa vela
      "side": "LONG" | "SHORT" | null,
      "tags": ["ADX1H<18", "Fibo", ...], # etiquetas canónicas de bloqueo (vacío si eligible y sin veto)
      "per_strategy": {"<id>": {"eligible": bool, "tags": [...]}},  # solo en evaluación multi-fórmula
      "forced_tf": ["<id>: nativa 1h ejecutándose en 4h"],          # desajustes de temporalidad
      "signal_original": "SHORT"         # solo si difiere del valor permitido por el CHECK de la tabla
    }

Nota: la tabla `signals` restringe `signal` a COMPRAR/VENDER/MANTENER/ERROR (CHECK en schema.sql).
Por eso un candidato SHORT se persiste como COMPRAR y el lado real queda en `side` / `signal_original`.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

SIGNALS_RETENTION_DAYS: int = 30
SIGNAL_LEDGER_VALUES: Tuple[str, ...] = ("COMPRAR", "VENDER", "MANTENER", "ERROR")
RAW_PAYLOAD_VERSION: int = 1
_REASON_MAX_CHARS: int = 400

# (etiqueta canónica, regex). El orden define el orden de reporte.
_TAG_RULES: List[Tuple[str, "re.Pattern[str]"]] = [
    (tag, re.compile(rx, re.IGNORECASE))
    for tag, rx in [
        ("ADX1H<18", r"ADX1H<\d+|1H Lateral"),
        ("Cruces1H>3", r"Cruces1H>\d+"),
        ("Fibo", r"Fibo[<>]\d"),
        ("MACD", r"MACD (?:sin giro|1H contra|15M contra)"),
        (
            "Gatillo Vela/EMA",
            r"Close(?:<=|>=|<|>)EMA|Vela no (?:alcista|bajista)|Cuerpo \d+%<|Mecha (?:sup|inf)>=\d+%|Sin toque EMA",
        ),
        ("R:R<2.0", r"Net R:R|Asimetr[ií]a neta"),
        ("VetoIA:RVOL", r"Volumen Seco"),
        ("VetoIA:Sobreext", r"Sobreextensi[oó]n"),
        ("VetoIA", r"VETO IA|[ÁA]rbitro IA|VETO_CUSTOM_BRAIN|Custom Brain|VETO Asimetr|VETO Mecha"),
        ("Kula:Mecha50", r"Veto Universal de Mechas"),
        ("Gate:MacroBTC", r"Veto Macro"),
        ("Gate:StopRuido", r"Stop dentro del ruido"),
        ("Gate:RVOL", r"Volumen relativo"),
        ("Gate:R:R", r"R:R neto [\d.]+ <"),
        (
            "Gate:Liquidez/Horario",
            r"Cerco de liquidez|Blackout|Pre-Cierre|Dominical|Cuchillo Cayendo|Centinela|Par[aá]metros num[eé]ricos",
        ),
        ("Slot/Cupo", r"L[ií]mite de \d+ posici"),
        ("Cooldown", r"Cooldown"),
        ("ÁrbitroInfo", r"\[[ÁA]rbitro AHORA_NO\]"),
        ("SinConfluencia", r"Sin confluencia|Ninguna de las \d+ f[oó]rmulas"),
        ("DatosObsoletos", r"Datos obsoletos|mercado cerrado"),
    ]
]

TAG_ORDER: List[str] = [t for t, _ in _TAG_RULES] + ["Pausa", "Otro"]

TAG_LABELS: Dict[str, str] = {
    "ADX1H<18": "1H lateral (ADX1H < 18)",
    "Cruces1H>3": "Serrucho 1H (cruces EMA50 > 3)",
    "Fibo": "Retroceso fuera de zona Fibo",
    "MACD": "Gatillo MACD sin giro/alineación",
    "Gatillo Vela/EMA": "Gatillo vela/cruce EMA incumplido",
    "R:R<2.0": "Asimetría R:R neta < 2.0 (fórmula)",
    "VetoIA": "Veto Árbitro IA (total)",
    "VetoIA:RVOL": "   · Árbitro IA: volumen seco (RVOL)",
    "VetoIA:Sobreext": "   · Árbitro IA: sobreextensión EMA/ATR",
    "Kula:Mecha50": "Veto Kula: mecha contraria >= 50%",
    "Gate:MacroBTC": "entry_gate: Veto Macro BTC",
    "Gate:StopRuido": "entry_gate: stop dentro del ruido ATR",
    "Gate:RVOL": "entry_gate: volumen relativo",
    "Gate:R:R": "entry_gate: R:R neto mínimo",
    "Gate:Liquidez/Horario": "entry_gate: liquidez/horario/centinela",
    "Slot/Cupo": "Cupo de posiciones/slots lleno",
    "Cooldown": "Cooldown anti-churn activo",
    "ÁrbitroInfo": "Árbitro informativo AHORA_NO",
    "SinConfluencia": "Sin confluencia de fórmulas (otras estrategias)",
    "DatosObsoletos": "Datos obsoletos / mercado cerrado",
    "Pausa": "Entradas pausadas por el operador",
    "Otro": "Otro motivo no clasificado",
}


def classify_rejection_tags(texts: Any, extra_tags: Optional[Iterable[str]] = None) -> List[str]:
    """
    Devuelve las etiquetas canónicas (únicas, en orden de reporte) detectadas en uno o varios textos.
    `extra_tags` permite al llamador forzar etiquetas conocidas (ej. 'Pausa').
    Si hay texto no vacío y nada coincide, devuelve ['Otro'].
    """
    if texts is None:
        flat: List[str] = []
    elif isinstance(texts, str):
        flat = [texts]
    else:
        flat = [str(t) for t in texts if t]
    blob = "\n".join(flat)

    found: List[str] = []
    for tag, rx in _TAG_RULES:
        if rx.search(blob):
            found.append(tag)
    for tg in extra_tags or []:
        if tg and tg not in found:
            found.append(tg)
    if not found and blob.strip():
        found.append("Otro")
    return sorted(set(found), key=lambda t: TAG_ORDER.index(t) if t in TAG_ORDER else len(TAG_ORDER))


_FIRED_RX = re.compile(
    r"VETO IA|[ÁA]rbitro IA|VETO_CUSTOM_BRAIN|Custom Brain|Asimetr[ií]a neta|Veto Universal de Mechas",
    re.IGNORECASE,
)


def formula_fired(texts: Any, eligible: bool) -> bool:
    """
    True si la fórmula matemática llegó a emitir señal cruda en esa vela: o quedó elegible, o murió
    DESPUÉS de dispararse (veto del árbitro de la fórmula, asimetría del adaptador o mecha de Kula).
    Los rechazos del propio gatillo (ADX, Fibo, MACD, vela/EMA, 'Net R:R' interno) NO cuentan como señal cruda.
    """
    if eligible:
        return True
    if texts is None:
        return False
    flat = [texts] if isinstance(texts, str) else [str(t) for t in texts if t]
    return bool(_FIRED_RX.search("\n".join(flat)))


def normalize_signal_for_ledger(signal: Any) -> Tuple[str, str]:
    """Mapea la señal del daemon al conjunto permitido por el CHECK de `signals`. Devuelve (valor_db, original)."""
    original = str(signal or "").strip().upper()
    if original in SIGNAL_LEDGER_VALUES:
        return original, original
    if original in ("SHORT", "LONG", "BUY"):
        return "COMPRAR", original
    if original == "SELL":
        return "VENDER", original
    return "MANTENER", original


def build_signal_payload(
    stage: str,
    strategy: str,
    tags: Optional[List[str]] = None,
    eligible: bool = False,
    side: Optional[str] = None,
    per_strategy: Optional[Dict[str, Any]] = None,
    forced_tf: Optional[List[str]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "v": RAW_PAYLOAD_VERSION,
        "stage": stage,
        "strategy": strategy or "",
        "eligible": bool(eligible),
        "side": side,
        "tags": list(tags or []),
    }
    if per_strategy:
        payload["per_strategy"] = per_strategy
    if forced_tf:
        payload["forced_tf"] = list(forced_tf)
    return payload


def clip_reason(reason: Any) -> str:
    text = " ".join(str(reason or "").split())
    return text if len(text) <= _REASON_MAX_CHARS else text[: _REASON_MAX_CHARS - 1] + "…"


def dump_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def parse_payload(raw: Any) -> Dict[str, Any]:
    """Lee `raw_response` de forma segura (devuelve {} si está vacío o no es JSON)."""
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, (str, bytes)) else dict(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def forced_timeframe_warnings(
    strategy_ids: Optional[Iterable[str]],
    timeframe: str,
    get_strategy_fn: Callable[[str], Any],
) -> List[str]:
    """
    Advierte si una fórmula se ejecuta en una temporalidad distinta a la nativa con la que fue certificada.
    Se evalúa sobre la temporalidad EFECTIVA de cada tarea del daemon (no sobre la configurada).
    """
    tf = str(timeframe or "").strip().lower()
    warnings: List[str] = []
    if not tf:
        return warnings
    for sid in strategy_ids or []:
        try:
            strat = get_strategy_fn(sid)
        except Exception:
            strat = None
        if strat is None:
            continue
        native = str(getattr(strat, "native_timeframe", "") or "").strip().lower()
        if native and native != tf:
            warnings.append(f"{sid}: nativa {native} ejecutándose en {tf}")
            continue
        permitted = getattr(strat, "temporalidades_permitidas", None)
        if permitted and tf not in {str(p).lower() for p in permitted}:
            warnings.append(f"{sid}: {tf} fuera de temporalidades permitidas")
    return warnings
