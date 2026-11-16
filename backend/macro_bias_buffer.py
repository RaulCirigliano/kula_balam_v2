"""
Buffer de Sesgo Macro con Latencia de Absorción y Descarte Silencioso.
Almacena temporalmente directivas macro del CIO (Monitor del Mercado) con TTL de 2 a 3 horas,
permitiendo que el mercado absorba el ruido de apertura (Opening Range Volatility)
sin gastar tokens de LLM ni saturar el hardware.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("macro_bias_buffer")
_BUFFER_LOCK = threading.RLock()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUFFER_FILE = os.environ.get("MACRO_BIAS_BUFFER_PATH") or os.path.join(PROJECT_ROOT, "backend", "config", "macro_bias_buffer.json")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _now_utc().isoformat()


def parse_iso(ts_str: str) -> datetime:
    if not ts_str:
        return _now_utc()
    normalized = f"{ts_str[:-1]}+00:00" if ts_str.endswith("Z") else ts_str
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed.astimezone(timezone.utc)
    except Exception:
        return _now_utc()


class MacroBiasBuffer:
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or os.environ.get("MACRO_BIAS_BUFFER_PATH") or BUFFER_FILE
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            self._atomic_save({})

    def _atomic_save(self, data: Dict[str, Any]) -> None:
        tmp_path = f"{self.file_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.file_path)

    def _load_data(self) -> Dict[str, Any]:
        if not os.path.exists(self.file_path):
            return {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except Exception as e:
            logger.warning(f"Error cargando macro_bias_buffer: {e}")
            return {}

    def set_bias(
        self,
        symbol: str,
        bias: str,  # "ALCISTA" / "BAJISTA" / "NEUTRAL" / "PELIGRO"
        confidence: int = 80,
        thesis: str = "",
        ttl_hours: float = 2.5,
        target_session: str = "IMMEDIATE",  # "IMMEDIATE" o "OPENING_BELL"
        source: str = "Monitor del Mercado (CIO)",
    ) -> Dict[str, Any]:
        """
        Registra o actualiza el sesgo macro táctico para un activo.
        TTL por defecto: 2.5 horas (ventana de absorción de 10 velas de 15m).
        """
        norm_sym = symbol.strip().upper()
        now = _now_utc()
        expires = now + timedelta(hours=ttl_hours)

        record = {
            "symbol": norm_sym,
            "bias": bias.upper(),
            "confidence": int(confidence),
            "thesis": thesis.strip(),
            "ttl_hours": float(ttl_hours),
            "target_session": target_session,
            "source": source,
            "created_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "status": "PENDING_VALIDATION",  # PENDING_VALIDATION | CONFIRMED_BUY | CONFIRMED_SELL | DISCARDED_EXPIRED | VETOED
            "checked_verdict": None,
            "validation_history": [],
        }

        with _BUFFER_LOCK:
            data = self._load_data()
            data[norm_sym] = record
            self._atomic_save(data)
            logger.info(f"🛰️ [MACRO BIAS BUFFER] Sesgo {record['bias']} registrado para {norm_sym} (TTL: {ttl_hours}h).")

        return record

    def get_bias(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Retorna el sesgo activo si aún no ha expirado y no fue descartado.
        Si expiró, actualiza el estado a DISCARDED_EXPIRED en silencio.
        """
        norm_sym = symbol.strip().upper()
        with _BUFFER_LOCK:
            data = self._load_data()
            record = data.get(norm_sym)
            if not record:
                # Comprobar variantes con guión o barra (BTC/USDT vs BTC-USDT)
                alt_sym = norm_sym.replace("/", "-") if "/" in norm_sym else norm_sym.replace("-", "/")
                record = data.get(alt_sym)
                if not record:
                    # Comprobar "GENERAL" o "CRYPTO"
                    if "CRYPTO" in data and ("BTC" in norm_sym or "ETH" in norm_sym or "SOL" in norm_sym):
                        record = data.get("CRYPTO")

            if not record:
                return None

            now = _now_utc()
            exp = parse_iso(record.get("expires_at", ""))

            if now > exp:
                if record.get("status") == "PENDING_VALIDATION":
                    record["status"] = "DISCARDED_EXPIRED"
                    record["checked_verdict"] = "[CHEQUEADO: DESCARTADO · EXPIRÓ LATENCIA DE ABSORCIÓN]"
                    self._atomic_save(data)
                    logger.info(f"⏳ [MACRO BIAS BUFFER] Sesgo para {norm_sym} expiró sin confirmación de velas. Descartado.")
                return None

            if record.get("status") == "DISCARDED_EXPIRED":
                return None

            return record

    def update_verdict(
        self,
        symbol: str,
        status: str,
        verdict: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Actualiza el dictamen de validación de velas en el buffer."""
        norm_sym = symbol.strip().upper()
        with _BUFFER_LOCK:
            data = self._load_data()
            record = data.get(norm_sym)
            if not record:
                return None

            record["status"] = status
            record["checked_verdict"] = verdict
            if details:
                hist = record.setdefault("validation_history", [])
                hist.append({
                    "timestamp": _iso_now(),
                    "verdict": verdict,
                    "details": details,
                })
                # Mantener solo las últimas 5 validaciones
                record["validation_history"] = hist[-5:]

            self._atomic_save(data)
            return record

    def get_all_active(self) -> List[Dict[str, Any]]:
        """Retorna todos los sesgos vigentes no expirados."""
        with _BUFFER_LOCK:
            data = self._load_data()
            now = _now_utc()
            active = []
            modified = False

            for sym, rec in data.items():
                exp = parse_iso(rec.get("expires_at", ""))
                if now > exp:
                    if rec.get("status") == "PENDING_VALIDATION":
                        rec["status"] = "DISCARDED_EXPIRED"
                        rec["checked_verdict"] = "[CHEQUEADO: DESCARTADO · EXPIRÓ LATENCIA DE ABSORCIÓN]"
                        modified = True
                elif rec.get("status") != "DISCARDED_EXPIRED":
                    active.append(rec)

            if modified:
                self._atomic_save(data)

            return active

    def clear_all(self) -> None:
        with _BUFFER_LOCK:
            self._atomic_save({})
