"""
Módulo: backend/market_context.py
Proyecto: Kula Balam
Contrato formal de datos entre el Módulo Kula (motor multitemporal/Fibonacci y contexto macro)
y Balam (rol táctico ejecutor al cierre de vela).
"""

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CONTEXT_FILE_PATH = os.path.join(DATA_DIR, "market_context.json")

_lock = threading.Lock()
_CURRENT_CONTEXT: Optional["MarketContextContract"] = None
_CURRENT_CONTEXT_PATH: Optional[str] = None


def _resolve_context_path(path: Optional[str] = None) -> str:
    return path or os.environ.get("KULA_MARKET_CONTEXT_PATH") or CONTEXT_FILE_PATH


class KeyLevelsModel(BaseModel):
    support: float = Field(..., description="Nivel de soporte clave")
    resistance: float = Field(..., description="Nivel de resistencia clave")
    fibo_50: float = Field(..., description="Nivel Fibonacci 0.50 (Zona Dorada)")
    fibo_75: float = Field(..., description="Nivel Fibonacci 0.75 (Límite de Invalidación)")


class MarketContextContract(BaseModel):
    version: str = Field(default="1.0", description="Versión del contrato")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Marca temporal ISO-8601 UTC"
    )
    ticker: str = Field(..., min_length=1, max_length=30, description="Activo seleccionado")
    timeframe: str = Field(default="1h", max_length=10, description="Timeframe de análisis")
    regime: Literal["Calma", "Tendencia", "Crisis"] = Field(
        default="Tendencia",
        description="Régimen de volatilidad y estructura de mercado"
    )
    macro_bias: Literal["LONG", "SHORT", "NEUTRAL"] = Field(
        default="LONG",
        description="Sesgo direccional derivado de 1D vs EMA 50"
    )
    veto_active: bool = Field(
        default=False,
        description="Bandera booleana de bloqueo total de gatillos"
    )
    key_levels: KeyLevelsModel = Field(
        ...,
        description="Niveles técnicos estructurados calculados por el Módulo Kula"
    )
    max_risk_per_trade_usd: float = Field(
        default=0.50,
        gt=0.0,
        le=50.0,
        description="Tope de riesgo monetario exacto en USD por operación"
    )
    ttl_hours: float = Field(
        default=4.0,
        gt=0.0,
        le=72.0,
        description="Vigencia temporal máxima del contexto en horas"
    )
    source: str = Field(
        default="Kula",
        description="Origen emisor del contrato multitemporal"
    )


def _normalize_symbol_token(sym: str) -> str:
    return str(sym or "").strip().upper().replace("-", "/")


def save_market_context(
    context: MarketContextContract,
    path: Optional[str] = None
) -> None:
    """Guarda el contexto en memoria y lo persiste en disco de forma atómica y segura."""
    global _CURRENT_CONTEXT, _CURRENT_CONTEXT_PATH
    file_path = _resolve_context_path(path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with _lock:
        _CURRENT_CONTEXT = context
        _CURRENT_CONTEXT_PATH = file_path
        temp_path = f"{file_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(context.model_dump_json(indent=2))
        os.replace(temp_path, file_path)


def load_market_context(path: Optional[str] = None) -> Optional[MarketContextContract]:
    """Carga el contexto desde memoria o desde el archivo persistido."""
    global _CURRENT_CONTEXT, _CURRENT_CONTEXT_PATH
    file_path = _resolve_context_path(path)
    
    with _lock:
        if _CURRENT_CONTEXT is not None and _CURRENT_CONTEXT_PATH == file_path:
            return _CURRENT_CONTEXT
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                _CURRENT_CONTEXT = MarketContextContract(**data)
                _CURRENT_CONTEXT_PATH = file_path
                return _CURRENT_CONTEXT
            except Exception:
                return None
    return None


def get_active_market_context_for_symbol(
    symbol: str,
    ttl_hours: Optional[float] = None,
    path: Optional[str] = None,
) -> Optional[MarketContextContract]:
    """
    Retorna el MarketContextContract vigente para `symbol` solo si coincide el activo
    y su marca temporal no expiró respecto a `ttl_hours`.
    """
    ctx = load_market_context(path=path)
    if ctx is None:
        return None

    target_norm = _normalize_symbol_token(symbol)
    ctx_norm = _normalize_symbol_token(ctx.ticker)
    target_base = target_norm.split("/")[0]
    ctx_base = ctx_norm.split("/")[0]
    if target_norm != ctx_norm and target_base != ctx_base:
        return None

    eff_ttl = float(ttl_hours if ttl_hours is not None else getattr(ctx, "ttl_hours", 4.0) or 4.0)
    try:
        ts_txt = str(ctx.timestamp).replace("Z", "+00:00")
        parsed_ts = datetime.fromisoformat(ts_txt)
        if parsed_ts.tzinfo is None:
            parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - parsed_ts.astimezone(timezone.utc)) > timedelta(hours=eff_ttl):
            return None
    except Exception:
        return None

    return ctx
