# -*- coding: utf-8 -*-
"""
Adaptador Dinámico de Fórmulas Promovidas del Backtest Lab al Motor Kula/Balam.

Permite que cualquier archivo `.py` promovido a `backend/estrategias/catalogo/principal/`
(con interfaz `formula_matematica(df, i)` y opcionalmente `arbitro_ia(fila, lado, entry, sl, tp)`)
sea ejecutado nativamente por `STRATEGY_REGISTRY`, `evaluate_strategy` y `TraderDaemon`,
sin necesidad de registrar clases manuales en `registry.py`.
"""

import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from backend.estrategias.base import EstrategiaBase
from backend.quant_risk import (
    net_return_after_costs,
    net_rr_metrics,
    required_tp_gross_for_rr,
)

logger = logging.getLogger(__name__)


def _prepare_eval_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye una copia segura con DatetimeIndex UTC (si existe columna `timestamp`)
    y columnas de microestructura estándar esperadas por `arbitro_ia`.
    """
    df_eval = df.copy()
    if not isinstance(df_eval.index, pd.DatetimeIndex) and "timestamp" in df_eval.columns:
        try:
            idx = pd.to_datetime(df_eval["timestamp"], unit="ms", utc=True, errors="coerce")
            if idx.notna().all():
                df_eval.index = idx
        except Exception:
            pass

    if "atr" not in df_eval.columns:
        prev_c = df_eval["close"].shift(1)
        tr = pd.concat(
            [
                df_eval["high"] - df_eval["low"],
                (df_eval["high"] - prev_c).abs(),
                (df_eval["low"] - prev_c).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df_eval["atr"] = tr.rolling(14, min_periods=1).mean().shift(1).bfill()

    if "rvol" not in df_eval.columns:
        if "volume" in df_eval.columns and float(df_eval["volume"].sum()) > 0.0:
            vol_sma = df_eval["volume"].rolling(20, min_periods=1).mean().shift(1).bfill()
            df_eval["rvol"] = df_eval["volume"] / (vol_sma + 1e-9)
        else:
            df_eval["rvol"] = 1.3

    rango = (df_eval["high"] - df_eval["low"]).replace(0, 1e-9)
    techo = df_eval[["open", "close"]].max(axis=1)
    suelo = df_eval[["open", "close"]].min(axis=1)

    if "mecha_superior_pct" not in df_eval.columns:
        df_eval["mecha_superior_pct"] = ((df_eval["high"] - techo) / rango) * 100.0
    if "mecha_inferior_pct" not in df_eval.columns:
        df_eval["mecha_inferior_pct"] = ((suelo - df_eval["low"]) / rango) * 100.0
    if "ema_50" not in df_eval.columns:
        df_eval["ema_50"] = df_eval["close"].ewm(span=50, adjust=False).mean()
    if "dist_ema_atrs" not in df_eval.columns:
        df_eval["dist_ema_atrs"] = (df_eval["close"] - df_eval["ema_50"]).abs() / (df_eval["atr"] + 1e-9)

    return df_eval


class CatalogFormulaStrategy(EstrategiaBase):
    """Adaptador EstrategiaBase para fórmulas matemáticas puras promovidas desde Backtest Lab."""

    def __init__(self, meta: Dict[str, Any], file_path: Path):
        self.id = str(meta.get("id") or file_path.stem)
        self.nombre = str(meta.get("titulo") or self.id)
        self.descripcion = str(meta.get("descripcion") or meta.get("subtitulo") or "")
        self.autor = "Backtest Lab (Promovida)"
        self.file_path = Path(file_path)
        self.activo_default = str(meta.get("activo_default") or "").strip()
        self.activos_recomendados = [self.activo_default] if self.activo_default else []
        self.native_timeframe = str(meta.get("timeframe") or "4h").lower()
        self.temporalidades_permitidas = {"1m", "5m", "15m", "1h", "4h", "1d"}
        self.horario_operativo = "24/5 Forex" if "=X" in self.activo_default.upper() else "24/7"
        self.parametros_por_defecto = {
            "native_timeframe": self.native_timeframe,
            "lote_sugerido": float(meta.get("lote_sugerido", 0.10)),
            "dataset_sugerido": meta.get("dataset_sugerido", ""),
        }
        self._cached_module: Optional[ModuleType] = None
        self._cached_mtime: float = -1.0

    def _load_module(self) -> ModuleType:
        mtime = self.file_path.stat().st_mtime
        if self._cached_module is not None and mtime == self._cached_mtime:
            return self._cached_module
        spec = importlib.util.spec_from_file_location(f"kula_cat_{self.id}", str(self.file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"No se pudo cargar spec para {self.file_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._cached_module = mod
        self._cached_mtime = mtime
        return mod

    def _asset_class_mismatch(self, symbol: str) -> Optional[str]:
        """Evita cruzar fórmulas especializadas entre Forex (=X), Cripto (/) y Acciones."""
        if not symbol or not self.activo_default:
            return None
        sym_u = symbol.upper()
        def_u = self.activo_default.upper()
        if "=X" in def_u and "=X" not in sym_u:
            return f"Fórmula '{self.id}' calibrada para Forex ({self.activo_default}); activo {symbol} excluido."
        if "/" in def_u and "=X" in sym_u:
            return f"Fórmula '{self.id}' calibrada para Cripto ({self.activo_default}); par Forex {symbol} excluido."
        return None

    def evaluar(
        self,
        ind: Dict[str, Any],
        tp: float,
        sl: float,
        fee: float,
        spread: float,
        min_profit_pct: float,
        round_trip_cost: float,
        net_tp_manual: float,
        df: Optional[Any] = None,
    ) -> Tuple[Dict[str, Any], float, bool, List[str], float]:
        def _safe_float(val: Any, default: float = 0.0) -> float:
            if val is None:
                return default
            try:
                f = float(val)
                return default if pd.isna(f) else f
            except (TypeError, ValueError):
                return default

        symbol = str(ind.get("symbol") or "").strip()
        latest_raw = ind.get("latest")
        latest = latest_raw if isinstance(latest_raw, (dict, pd.Series)) else {}
        live_px = _safe_float(ind.get("live_price"), 0.0)
        latest_close = _safe_float(latest.get("close") if hasattr(latest, "get") else 0.0, 0.0)
        current_price = live_px if live_px > 0 else latest_close
        atr_14 = _safe_float(ind.get("atr_14"), 0.0) or _safe_float(ind.get("atr"), 0.0)
        is_forex = "=X" in symbol.upper() or "=X" in self.activo_default.upper()

        raw_default_sl = (1.4 * atr_14 / current_price * 100.0) if (atr_14 > 0 and current_price > 0) else (0.22 if is_forex else 1.40)
        default_sl_pct = round(min(25.0, max(0.12 if is_forex else 0.70, raw_default_sl)), 2)
        default_tp_pct = round(required_tp_gross_for_rr(default_sl_pct, fee, spread, target_rr=2.0) + 0.01, 2)

        def _base_metrics(eligible: bool, failures: List[str], side: str = "MANTENER", sl_p: float = default_sl_pct, tp_p: float = default_tp_pct, arb_msg: str = "") -> Tuple[Dict[str, Any], float, bool, List[str], float]:
            n_tp = round(net_return_after_costs(tp_p, fee, spread), 4)
            n_sl = round(net_return_after_costs(-sl_p, fee, spread), 4)
            rr_info = net_rr_metrics(tp_p, sl_p, fee, spread)
            c_rr = round(float(rr_info.get("net_rr") or 0.0), 2)
            eff_net = n_tp if eligible else 0.0
            sig = "SHORT" if (eligible and side == "SHORT") else ("COMPRAR" if eligible else "MANTENER")
            metrics = {
                "mode": self.id,
                "side": side if eligible else "MANTENER",
                "suggested_signal": sig,
                "signal_side": "SHORT" if (eligible and side == "SHORT") else ("BUY" if eligible else "HOLD"),
                "current_price": round(current_price, 6 if is_forex else 4),
                "atr_14": round(atr_14, 6 if is_forex else 4),
                "relative_volume": round(float(ind.get("relative_volume") or 1.0), 3),
                "lower_wick_ratio": float(ind.get("lower_wick_ratio") or 0.0),
                "tp_gross_pct": tp_p,
                "sl_gross_pct": sl_p,
                "tp_net_pct": n_tp,
                "sl_net_pct": n_sl,
                "net_rr": c_rr,
                "minimum_net_tp_pct": min_profit_pct,
                "candidate_eligible": eligible,
                "filter_failures": failures,
                "arbitro_ia_verdict": arb_msg,
            }
            return (metrics, eff_net, eligible, failures, min_profit_pct)

        mismatch = self._asset_class_mismatch(symbol)
        if mismatch:
            return _base_metrics(False, [mismatch])

        if df is None or not isinstance(df, pd.DataFrame) or len(df) < 30:
            return _base_metrics(False, [f"Historial OHLCV insuficiente para evaluar '{self.id}'."])

        try:
            mod = self._load_module()
            if not hasattr(mod, "formula_matematica"):
                return _base_metrics(False, [f"Módulo '{self.id}' sin función 'formula_matematica'."])

            df_eval = _prepare_eval_dataframe(df)
            idx = len(df_eval) - 1
            entry_px = float(current_price or df_eval["close"].iloc[idx])
            atr_14 = float(df_eval["atr"].iloc[idx] or atr_14)

            ok, side, sl_px, tp_px = mod.formula_matematica(df_eval, idx)
            if not ok or not side:
                return _base_metrics(False, [f"Sin confluencia en fórmula '{self.id}' sobre vela cerrada actual."])

            side_norm = "SHORT" if str(side).upper() in ("SHORT", "SELL") else "LONG"
            sl_dist_pct = abs(entry_px - float(sl_px)) / entry_px * 100.0 if (entry_px > 0 and sl_px) else default_sl_pct
            tp_dist_pct = abs(float(tp_px) - entry_px) / entry_px * 100.0 if (entry_px > 0 and tp_px) else default_tp_pct

            sl_calc = round(min(25.0, max(0.12 if is_forex else 0.70, sl_dist_pct)), 2)
            min_tp_rr = required_tp_gross_for_rr(sl_calc, fee, spread, target_rr=2.0)
            tp_calc = round(max(tp_dist_pct, min_tp_rr + 0.01), 2)

            failures: List[str] = []
            arb_msg = "Sin árbitro heurístico"

            # Soporte de Gancho Extensible custom_brain_filter (prioritario) y fallback a arbitro_ia legacy
            if hasattr(mod, "custom_brain_filter"):
                try:
                    cbf_res = mod.custom_brain_filter(df_eval, idx, side_norm, entry_px, float(sl_px), float(tp_px))
                    if isinstance(cbf_res, tuple):
                        if len(cbf_res) == 2:
                            cbf_ok, cbf_reason = cbf_res
                        elif len(cbf_res) >= 3:
                            cbf_ok, _, cbf_reason = cbf_res[0], cbf_res[1], cbf_res[2]
                        else:
                            cbf_ok, cbf_reason = bool(cbf_res[0]), "CUSTOM_BRAIN"
                    else:
                        cbf_ok, cbf_reason = bool(cbf_res), "CUSTOM_BRAIN"
                    arb_msg = str(cbf_reason)
                    if not cbf_ok:
                        failures.append(f"[Custom Brain {self.id}] VETO_CUSTOM_BRAIN: {arb_msg}")
                except Exception as exc:
                    logger.warning(f"Error ejecutando custom_brain_filter en '{self.id}': {exc}")
                    failures.append(f"[Custom Brain {self.id}] VETO_CUSTOM_BRAIN: Error ({exc})")
            elif hasattr(mod, "arbitro_ia"):
                fila = df_eval.iloc[idx]
                arb_ok, _, arb_reason = mod.arbitro_ia(fila, side_norm, entry_px, float(sl_px), float(tp_px))
                arb_msg = str(arb_reason)
                if not arb_ok:
                    failures.append(f"[Árbitro IA {self.id}] {arb_msg}")

            rr_info = net_rr_metrics(tp_calc, sl_calc, fee, spread)
            if not rr_info.get("valid") or float(rr_info.get("net_rr") or 0.0) < 1.95:
                failures.append(f"Asimetría neta insuficiente en '{self.id}': R:R {rr_info.get('net_rr', 0.0)} < 1.95")

            return _base_metrics(len(failures) == 0, failures, side=side_norm, sl_p=sl_calc, tp_p=tp_calc, arb_msg=arb_msg)

        except Exception as exc:
            logger.warning(f"Error ejecutando fórmula de catálogo '{self.id}': {exc}")
            return _base_metrics(False, [f"Error ejecutando '{self.id}': {exc}"])


def discover_catalog_principal_strategies(existing_ids: Set[str]) -> Dict[str, CatalogFormulaStrategy]:
    """
    Descubre dinámicamente las estrategias promovidas en `backend/estrategias/catalogo/principal/`
    cuyo ID aún no tenga una clase manual registrada en `existing_ids`.
    """
    from backend.estrategias.catalogo_manager import PRINCIPAL_DIR, _read_metadata

    discovered: Dict[str, CatalogFormulaStrategy] = {}
    if not PRINCIPAL_DIR.exists():
        return discovered

    meta_map = _read_metadata(PRINCIPAL_DIR)
    for py_file in sorted(PRINCIPAL_DIR.glob("*.py")):
        info = dict(meta_map.get(py_file.name, {}))
        strat_id = str(info.get("id") or py_file.stem)
        if not strat_id or strat_id in existing_ids or strat_id in discovered:
            continue
        info["id"] = strat_id
        info["archivo"] = py_file.name
        try:
            discovered[strat_id] = CatalogFormulaStrategy(info, py_file)
        except Exception as exc:
            logger.warning(f"No se pudo registrar adaptador para {py_file.name}: {exc}")

    return discovered
