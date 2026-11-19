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

import numpy as np
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


def _format_price_tele(px: float, symbol: str = "") -> str:
    """Formatea precio según escala de mercado (Forex/alts baratos vs Cripto mayor)."""
    is_small = "=X" in str(symbol).upper() or (0 < px < 10.0)
    return f"{px:.4f}" if is_small else f"{px:.2f}"


def format_presencial_telemetry(
    diag: Dict[str, Any],
    symbol: str = "",
    timeframe: str = "",
    extra_vetoes: Optional[List[str]] = None,
) -> str:
    """Formatea en una línea los valores reales medidos y el motivo exacto de bloqueo."""
    sym = str(symbol or diag.get("symbol") or "").strip() or "ACTIVO"
    tf = str(timeframe or diag.get("timeframe") or "").strip() or "tf"
    px = float(diag.get("close") or 0.0)
    px_txt = f"${_format_price_tele(px, sym)}" if px > 0 else "N/A"
    hdr = f"[{sym} {tf}] Close {px_txt}"

    vetoes = list(diag.get("reasons") or [])
    for ev in (extra_vetoes or []):
        ev_s = str(ev or "").strip()
        if ev_s and ev_s not in vetoes:
            vetoes.append(ev_s)

    if not diag.get("ready", False):
        why = ", ".join(vetoes) if vetoes else "Historial insuficiente"
        return f"{hdr} | {why} -> En espera"

    adx1h = float(diag.get("adx1h", 0.0))
    adx_min = float(diag.get("adx_min", 18.0))
    adx_cmp = f"<{adx_min:.0f}" if adx1h < adx_min else f">={adx_min:.0f}"

    crosses = int(round(float(diag.get("crosses1h", 0))))
    cross_max = int(diag.get("crosses_max", 3))
    cross_cmp = f">{cross_max}" if crosses > cross_max else f"<={cross_max}"

    retr = float(diag.get("retr", 0.0))
    f_min = float(diag.get("fibo_min", 0.50))
    f_max = float(diag.get("fibo_max", 0.75))
    fibo_ok = f_min <= retr <= f_max
    fibo_tag = f"OK {f_min:.2f}-{f_max:.2f}" if fibo_ok else f"meta {f_min:.2f}-{f_max:.2f}"

    side_lbl = str(diag.get("side") or "").strip()
    side_suffix = f", {side_lbl}" if side_lbl else ""
    base = (
        f"{hdr} | ADX1H: {adx1h:.2f} ({adx_cmp}) | "
        f"Cruces1H: {crosses} ({cross_cmp}) | "
        f"Fibo: {retr:.3f} ({fibo_tag}{side_suffix})"
    )
    if vetoes:
        return f"{base} | Bloqueo: {', '.join(vetoes)} -> En espera"
    return f"{base} | Confluencia OK -> Evaluando gatillo"


def build_mtf_presencial_diagnostic(
    df: pd.DataFrame,
    i: int,
    spec: Dict[str, Any],
    symbol: str = "",
    timeframe: str = "",
    extra_vetoes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Reconstruye la telemetría diagnóstica exacta de estrategias MTF Presenciales (1H -> 15M/5M)
    a partir de `df` ya evaluado por `formula_matematica`, sin alterar ninguna regla matemática.
    """
    tf_label = str(timeframe or spec.get("default_tf") or "")
    min_i = int(spec.get("min_i", 320))
    adx_min = float(spec.get("adx_min", 18.0))
    cross_max = int(spec.get("crosses_max", 3))
    f_min = float(spec.get("fibo_min", 0.50))
    f_max = float(spec.get("fibo_max", 0.75))

    def _incomplete(why: str, close_val: float = 0.0) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "ready": False,
            "symbol": symbol,
            "timeframe": tf_label,
            "close": close_val,
            "reasons": [why],
        }
        d["line"] = format_presencial_telemetry(d, symbol, tf_label, extra_vetoes)
        return d

    if df is None or len(df) == 0 or i < 0 or i >= len(df):
        return _incomplete("Sin velas disponibles")

    r = df.iloc[i]
    c = float(r.get("close", 0.0) or 0.0)
    bad_col = str(spec.get("bad_col") or "")
    if (bad_col and bad_col in df.columns and bool(df[bad_col].iloc[0])) or i < min_i:
        return _incomplete(f"Historial insuficiente ({len(df)} velas, min {min_i + 1})", c)
    if "_hi_adx" not in df.columns or pd.isna(r.get("_hi_ema50")) or pd.isna(r.get("_hi_atr1")):
        return _incomplete("Indicadores 1H aún sin calentar (NaN)", c)

    o = float(r["open"])
    h = float(r["high"])
    l = float(r["low"])
    atr_trig = float(r.get("_atr_trig", 0.0) or 0.0)
    adx1h = float(r.get("_hi_adx", 0.0) or 0.0)
    crosses1h = float(r.get("_hi_crosses", 0.0) or 0.0)
    ema1h = float(r["_hi_ema50"])
    ema1h_p = float(r["_hi_ema50_prev"])
    sw_h = float(r["_hi_sw_h"])
    sw_l = float(r["_hi_sw_l"])
    atr1 = float(r["_hi_atr1"])
    rng_fibo = max(sw_h - sw_l, 1e-9)
    bull_1h = int(r["_hi_bull_imp"]) == 1
    is_ema_falling = ema1h < ema1h_p * 0.995
    if is_ema_falling and not bull_1h and c < ema1h * 0.998:
        side = "SHORT"
    elif bull_1h:
        side = "LONG"
    else:
        side = "SHORT" if c < ema1h else "LONG"

    retr = ((sw_h - c) / rng_fibo) if side == "LONG" else ((c - sw_l) / rng_fibo)

    reasons: List[str] = []
    if atr_trig <= 0 or c <= 0:
        reasons.append("ATR/Precio inválido")
    if adx1h < adx_min:
        reasons.append(f"ADX1H<{adx_min:.0f}")
    if crosses1h > cross_max:
        reasons.append(f"Cruces1H>{cross_max}")
    if retr < f_min:
        reasons.append(f"Fibo<{f_min:.2f}")
    elif retr > f_max:
        reasons.append(f"Fibo>{f_max:.2f}")

    # Si pasó contexto 1H + Fibo, detallamos por qué frenó la capa de ejecución
    if not reasons:
        e_trig = float(r["_ema_trig"])
        rng = max(h - l, 1e-9)
        body_pct = abs(c - o) / rng
        lookback = int(spec.get("cross_lookback", 6))
        body_min = float(spec.get("body_min", 0.30))
        ema_prev = df["_ema_trig"].iloc[max(0, i - lookback):i]
        has_mid_tf = bool(spec.get("has_mid_tf", False))

        if has_mid_tf:
            hi_macd_ok = (int(r["_hi_macd_up"]) == 1) if side == "LONG" else (int(r["_hi_macd_dn"]) == 1)
            mid_col = "_mid_macd_up" if side == "LONG" else "_mid_macd_dn"
            mid_macd_ok = (not pd.isna(r[mid_col])) and int(r[mid_col]) == 1
            if not hi_macd_ok:
                reasons.append(f"MACD 1H contra {side}")
            if not mid_macd_ok:
                reasons.append(f"MACD 15M contra {side}")
        else:
            hc = float(r["_hist"])
            hp1 = float(df["_hist"].iloc[i - 1])
            hp2 = float(df["_hist"].iloc[i - 2])
            mc = float(r["_macd"])
            mp1 = float(df["_macd"].iloc[i - 1])
            if side == "LONG":
                macd_ok = (hc > hp1 or hc > hp2 or mc > mp1) and (int(r["_hi_macd_up"]) == 1)
            else:
                macd_ok = (hc < hp1 or hc < hp2 or mc < mp1) and (int(r["_hi_macd_dn"]) == 1)
            if not macd_ok:
                reasons.append(f"MACD sin giro {side}")

        if side == "LONG":
            if c < ema1h * 0.995:
                reasons.append("Close<EMA1H*0.995")
            if not (c > e_trig):
                reasons.append(f"Close<=EMA({e_trig:.2f})")
            elif not (c > o):
                reasons.append("Vela no alcista")
            elif body_pct < body_min:
                reasons.append(f"Cuerpo {body_pct*100:.0f}%<{body_min*100:.0f}%")
            elif ((h - max(o, c)) / rng) >= 0.45:
                reasons.append("Mecha sup>=45%")
            elif not (df["low"].iloc[max(0, i - lookback):i] <= ema_prev * 1.002).any():
                reasons.append(f"Sin toque EMA en {lookback}v")
            loc_low = float(df.iloc[max(0, i - int(spec.get("loc_lookback", 12))):i + 1]["low"].min())
            sl_dist = min(3.0 * atr1, max(c - loc_low + 0.2 * atr1, 1.0 * atr1, float(spec.get("sl_floor_pct", 0.008)) * c))
            sl_px, tp_px = c - sl_dist, sw_h
        else:
            if c > ema1h * 1.005:
                reasons.append("Close>EMA1H*1.005")
            if not (c < e_trig):
                reasons.append(f"Close>=EMA({e_trig:.2f})")
            elif not (c < o):
                reasons.append("Vela no bajista")
            elif body_pct < body_min:
                reasons.append(f"Cuerpo {body_pct*100:.0f}%<{body_min*100:.0f}%")
            elif ((min(o, c) - l) / rng) >= 0.45:
                reasons.append("Mecha inf>=45%")
            elif not (df["high"].iloc[max(0, i - lookback):i] >= ema_prev * 0.998).any():
                reasons.append(f"Sin toque EMA en {lookback}v")
            loc_high = float(df.iloc[max(0, i - int(spec.get("loc_lookback", 12))):i + 1]["high"].max())
            sl_dist = min(3.0 * atr1, max(loc_high - c + 0.2 * atr1, 1.0 * atr1, float(spec.get("sl_floor_pct", 0.008)) * c))
            sl_px, tp_px = c + sl_dist, sw_l

        if not reasons:
            sl_pct = abs(c - sl_px) / c * 100.0
            tp_pct = ((tp_px - c) / c * 100.0) if side == "LONG" else ((c - tp_px) / c * 100.0)
            rr_val = net_rr_metrics(tp_pct, sl_pct, 0.10, 0.05).get("net_rr", 0.0)
            if tp_pct <= 0 or float(rr_val or 0.0) < 2.0:
                reasons.append(f"Net R:R {float(rr_val or 0.0):.2f}<2.0")

    d: Dict[str, Any] = {
        "ready": True,
        "symbol": symbol,
        "timeframe": tf_label,
        "close": c,
        "adx1h": adx1h,
        "adx_min": adx_min,
        "crosses1h": int(round(crosses1h)),
        "crosses_max": cross_max,
        "retr": retr,
        "fibo_min": f_min,
        "fibo_max": f_max,
        "side": side,
        "sw_l": sw_l,
        "sw_h": sw_h,
        "ema1h": ema1h,
        "reasons": reasons,
    }
    d["line"] = format_presencial_telemetry(d, symbol, tf_label, extra_vetoes)
    return d


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

        def _base_metrics(
            eligible: bool,
            failures: List[str],
            side: str = "MANTENER",
            sl_p: float = default_sl_pct,
            tp_p: float = default_tp_pct,
            arb_msg: str = "",
            presencial_telemetry: str = "",
            shadow_veto_candidate: Optional[Dict[str, Any]] = None,
        ) -> Tuple[Dict[str, Any], float, bool, List[str], float]:
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
                "presencial_telemetry": presencial_telemetry,
            }
            if shadow_veto_candidate is not None:
                metrics["shadow_veto_candidate"] = shadow_veto_candidate
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
            sym_hint = symbol or self.activo_default or "ACTIVO"
            tf_hint = str(ind.get("timeframe") or self.native_timeframe or "")

            ok, side, sl_px, tp_px = mod.formula_matematica(df_eval, idx)
            if not ok or not side:
                tele_line = ""
                if hasattr(mod, "diagnosticar_vela"):
                    try:
                        diag = mod.diagnosticar_vela(df_eval, idx, symbol=sym_hint, timeframe=tf_hint)
                        if isinstance(diag, dict):
                            tele_line = str(diag.get("line") or "").strip()
                        elif isinstance(diag, str):
                            tele_line = diag.strip()
                    except Exception as diag_exc:
                        logger.debug(f"Telemetría diagnóstica omitida en '{self.id}': {diag_exc}")
                if not tele_line:
                    tele_line = f"[{sym_hint} {tf_hint}] Close ${_format_price_tele(entry_px, sym_hint)} | Bloqueo: sin confluencia en '{self.id}' -> En espera"
                return _base_metrics(False, [tele_line], presencial_telemetry=tele_line)

            side_norm = "SHORT" if str(side).upper() in ("SHORT", "SELL") else "LONG"
            sl_dist_pct = abs(entry_px - float(sl_px)) / entry_px * 100.0 if (entry_px > 0 and sl_px) else default_sl_pct
            tp_dist_pct = abs(float(tp_px) - entry_px) / entry_px * 100.0 if (entry_px > 0 and tp_px) else default_tp_pct

            sl_calc = round(min(25.0, max(0.12 if is_forex else 0.70, sl_dist_pct)), 2)
            min_tp_rr = required_tp_gross_for_rr(sl_calc, fee, spread, target_rr=2.0)
            tp_calc = round(max(tp_dist_pct, min_tp_rr + 0.01), 2)

            failures: List[str] = []
            arb_msg = "Sin árbitro heurístico"
            arbiter_vetoed = False

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
                        arbiter_vetoed = True
                        failures.append(f"[Custom Brain {self.id}] VETO_CUSTOM_BRAIN: {arb_msg}")
                except Exception as exc:
                    logger.warning(f"Error ejecutando custom_brain_filter en '{self.id}': {exc}")
                    arb_msg = f"Error ({exc})"
                    arbiter_vetoed = True
                    failures.append(f"[Custom Brain {self.id}] VETO_CUSTOM_BRAIN: Error ({exc})")
            elif hasattr(mod, "arbitro_ia"):
                fila = df_eval.iloc[idx]
                arb_ok, _, arb_reason = mod.arbitro_ia(fila, side_norm, entry_px, float(sl_px), float(tp_px))
                arb_msg = str(arb_reason)
                if not arb_ok:
                    arbiter_vetoed = True
                    failures.append(f"[Árbitro IA {self.id}] {arb_msg}")

            rr_info = net_rr_metrics(tp_calc, sl_calc, fee, spread)
            if not rr_info.get("valid") or float(rr_info.get("net_rr") or 0.0) < 1.95:
                failures.append(f"Asimetría neta insuficiente en '{self.id}': R:R {rr_info.get('net_rr', 0.0)} < 1.95")

            shadow_cand: Optional[Dict[str, Any]] = None
            if arbiter_vetoed and entry_px > 0:
                sl_v = float(sl_px) if (sl_px and float(sl_px) > 0) else (
                    entry_px * (1.0 - sl_calc / 100.0) if side_norm == "LONG" else entry_px * (1.0 + sl_calc / 100.0)
                )
                tp_v = float(tp_px) if (tp_px and float(tp_px) > 0) else (
                    entry_px * (1.0 + tp_calc / 100.0) if side_norm == "LONG" else entry_px * (1.0 - tp_calc / 100.0)
                )
                shadow_cand = {
                    "symbol": sym_hint,
                    "strategy": self.id,
                    "side": side_norm,
                    "entry_price": round(entry_px, 6 if is_forex else 4),
                    "sl_price": round(sl_v, 6 if is_forex else 4),
                    "tp_price": round(tp_v, 6 if is_forex else 4),
                    "initial_sl_pct": sl_calc,
                    "initial_tp_pct": tp_calc,
                    "arbiter_verdict": "VETO_ARBITRO_IA",
                    "arbiter_reason": arb_msg,
                }

            tele_line = ""
            if hasattr(mod, "diagnosticar_vela"):
                try:
                    diag = mod.diagnosticar_vela(
                        df_eval,
                        idx,
                        symbol=sym_hint,
                        timeframe=tf_hint,
                        extra_vetoes=failures if failures else None,
                    )
                    if isinstance(diag, dict):
                        tele_line = str(diag.get("line") or "").strip()
                    elif isinstance(diag, str):
                        tele_line = diag.strip()
                except Exception as diag_exc:
                    logger.debug(f"Telemetría diagnóstica post-gatillo omitida en '{self.id}': {diag_exc}")
            if not tele_line:
                if failures:
                    tele_line = f"[{sym_hint} {tf_hint}] Close ${_format_price_tele(entry_px, sym_hint)} | Bloqueo: {'; '.join(failures)} -> En espera"
                else:
                    tele_line = f"[{sym_hint} {tf_hint}] Close ${_format_price_tele(entry_px, sym_hint)} | {side_norm} R:R {rr_info.get('net_rr', 0.0)} -> Candidata"

            return _base_metrics(
                len(failures) == 0,
                failures,
                side=side_norm,
                sl_p=sl_calc,
                tp_p=tp_calc,
                arb_msg=arb_msg,
                presencial_telemetry=tele_line,
                shadow_veto_candidate=shadow_cand,
            )

        except Exception as exc:
            logger.warning(f"Error ejecutando fórmula de catálogo '{self.id}': {exc}")
            return _base_metrics(False, [f"Error ejecutando '{self.id}': {exc}"])


def discover_catalog_principal_strategies(existing_ids: Set[str]) -> Dict[str, CatalogFormulaStrategy]:
    """
    Descubre dinámicamente las estrategias promovidas en `catalogo/principal/` y
    `catalogo/operador_presente/` cuyo ID aún no tenga una clase manual registrada en `existing_ids`.
    """
    from backend.estrategias.catalogo_manager import OPERADOR_DIR, PRINCIPAL_DIR, _read_metadata

    discovered: Dict[str, CatalogFormulaStrategy] = {}
    for folder in (PRINCIPAL_DIR, OPERADOR_DIR):
        if not folder.exists():
            continue
        meta_map = _read_metadata(folder)
        for py_file in sorted(folder.glob("*.py")):
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
