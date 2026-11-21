# -*- coding: utf-8 -*-
"""
Watchdog Determinista y Semáforo de Salud Operativa (0 Tokens).

Evalúa periódicamente y bajo demanda sin consumir tokens de LLM ni realizar llamadas pagas:
  1. kula_motor: estado del ciclo del TraderDaemon, errores recientes y frescura de ejecución.
  2. guardian_sl: vigencia de vigilancia del Guardián sobre posiciones abiertas.
  3. formulas_sintetico: prueba sintética en memoria de todas las estrategias autorizadas
     (detecta regresiones tipo pd.Series truthiness o salidas NaN antes de operar).
  4. balam_puente: estado de feeds RSS del Monitor del Mercado (puerto 8520) y vigencia del puente macro.
"""

import json
import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

logger = logging.getLogger("health_watchdog")

WATCHDOG_PROBE_INTERVAL_S: float = 900.0  # 15 minutos
TELEGRAM_ALERT_COOLDOWN_S: float = 1800.0  # 30 minutos entre alertas repetidas por luz
CYCLE_STALL_THRESHOLD_S: float = 240.0     # 4 minutos sin avanzar un ciclo activo
STARTUP_GRACE_S: float = 120.0             # 2 minutos de gracia al iniciar
MACRO_TTL_HOURS: float = 3.5


def _default_monitor_url() -> str:
    return (os.environ.get("MONITOR_API_URL") or "http://127.0.0.1:8520").rstrip("/")


def _build_synthetic_market_frame(is_forex: bool = False) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Construye serie sintética coherente en memoria para validación sin red ni tokens."""
    n = 240
    dates = pd.date_range("2026-10-15", periods=n, freq="1h", tz="UTC")
    base = 1.1200 if is_forex else 100.0
    step = 0.0001 if is_forex else 0.15
    closes = [base + (i * step) for i in range(n)]
    wick = 0.0005 if is_forex else 0.60
    body_off = 0.0002 if is_forex else 0.20
    vols = [0.0 if is_forex else 1000.0] * n
    df = pd.DataFrame({
        "timestamp": [int(d.timestamp() * 1000) for d in dates],
        "open": [c - body_off for c in closes],
        "high": [c + wick for c in closes],
        "low": [c - wick for c in closes],
        "close": closes,
        "volume": vols,
    })
    latest_series = pd.Series({
        "open": df["open"].iloc[-1],
        "high": df["high"].iloc[-1],
        "low": df["low"].iloc[-1],
        "close": closes[-1],
        "sma_20": closes[-1] * 0.999,
        "sma_50": closes[-1] * 0.997,
        "rsi": 54.0,
        "vwap": closes[-1] * 0.998,
        "volume": vols[-1],
    })
    atr = 0.0014 if is_forex else 1.25
    ind: Dict[str, Any] = {
        "symbol": "EURUSD=X" if is_forex else "BTC/USDT",
        "timeframe": "1h" if is_forex else "4h",
        "live_price": closes[-1],
        "latest": latest_series,
        "ema_200_value": closes[-1] * 0.985,
        "ema_200_slope_pct": 0.02,
        "atr_14": atr,
        "atr": atr,
        "relative_volume": 0.0 if is_forex else 1.25,
        "lower_wick_ratio": 0.15,
        "upper_wick_ratio": 0.10,
        "z_score": 0.25,
    }
    return df, ind


class HealthWatchdog:
    """Evaluador determinista del ecosistema Kula Balam + Monitor del Mercado."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last_probe_ts: float = 0.0
        self._last_probe_result: Optional[Dict[str, Any]] = None
        self._last_light_states: Dict[str, str] = {}
        self._last_alert_ts: Dict[str, float] = {}

    def probe_active_strategies(self, strategy_ids: List[str], force: bool = False) -> Dict[str, Any]:
        """Ejecuta prueba sintética en memoria de estrategias activas (0 tokens, sin red)."""
        now_ts = time.time()
        with self._lock:
            if (
                not force
                and self._last_probe_result is not None
                and (now_ts - self._last_probe_ts) < WATCHDOG_PROBE_INTERVAL_S
            ):
                return dict(self._last_probe_result)

        from backend.estrategias.registry import evaluate_strategy, get_strategy

        targets = [s for s in strategy_ids if s and s not in ("manual", "auto")]
        if not targets:
            targets = ["trailing_trend_runner", "trailing_short_runner"]

        # Deduplicar preservando orden
        unique_targets = list(dict.fromkeys(targets))
        df_crypto, ind_crypto = _build_synthetic_market_frame(is_forex=False)
        df_fx, ind_fx = _build_synthetic_market_frame(is_forex=True)

        checked: List[str] = []
        failures: List[Dict[str, str]] = []

        for sid in unique_targets:
            strat_obj = get_strategy(sid)
            def_asset = str(getattr(strat_obj, "activo_default", "") or "").upper() if strat_obj else ""
            is_fx = "=X" in def_asset or "eurusd" in sid.lower()
            df_use = df_fx if is_fx else df_crypto
            ind_use = dict(ind_fx if is_fx else ind_crypto)
            fee_use = 0.0 if is_fx else 0.1
            spread_use = 0.012 if is_fx else 0.05
            rt_cost = round((fee_use + spread_use) * 2.0, 4)

            try:
                metrics, _, _, _, _ = evaluate_strategy(
                    strategy_id=sid,
                    ind=ind_use,
                    tp=2.0,
                    sl=1.0,
                    fee=fee_use,
                    spread=spread_use,
                    min_profit_pct=0.20 if is_fx else 0.50,
                    round_trip_cost=rt_cost,
                    net_tp_manual=1.9,
                    df=df_use,
                )
                if not isinstance(metrics, dict):
                    failures.append({"strategy": sid, "error": "Métricas no son diccionario"})
                else:
                    for key in ("tp_gross_pct", "sl_gross_pct", "net_rr"):
                        val = metrics.get(key)
                        if val is not None and not math.isfinite(float(val)):
                            failures.append({"strategy": sid, "error": f"Campo no finito '{key}={val}'"})
                            break
                checked.append(sid)
            except Exception as exc:
                checked.append(sid)
                failures.append({"strategy": sid, "error": f"{type(exc).__name__}: {exc}"})

        total = len(checked)
        passed = max(0, total - len(failures))
        if failures:
            light = {
                "status": "RED",
                "label": f"Fórmulas ({passed}/{total} OK)",
                "detail": "; ".join(f"{f['strategy']}: {f['error']}" for f in failures[:3]),
                "checked": total,
                "passed": passed,
                "failures": failures,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            light = {
                "status": "GREEN",
                "label": f"Fórmulas ({passed}/{total} OK)",
                "detail": f"Auto-test sintético OK en {total} fórmula(s): {', '.join(checked)}.",
                "checked": total,
                "passed": passed,
                "failures": [],
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

        with self._lock:
            self._last_probe_ts = now_ts
            self._last_probe_result = dict(light)
        return light

    def _evaluate_kula_motor(self, snap: Dict[str, Any], now_ts: float) -> Dict[str, Any]:
        is_running = bool(snap.get("is_running"))
        is_paused = bool(snap.get("paused"))
        cycle_count = int(snap.get("cycle_count") or 0)
        last_cycle_ts = float(snap.get("last_cycle_ts") or 0.0)
        started_at = float(snap.get("started_at") or 0.0)
        last_error = snap.get("last_error")
        cooldown_rem = float(snap.get("cooldown_remaining_s") or 0.0)
        last_signal = str(snap.get("last_signal") or "")
        strategy_lbl = str(snap.get("strategy") or "auto")

        if not is_running:
            return {
                "status": "RED",
                "label": "Motor Detenido",
                "detail": "TraderDaemon está detenido; no escanea oportunidades nuevas.",
                "cycle_count": cycle_count,
                "last_error": last_error,
            }

        if last_error:
            return {
                "status": "RED",
                "label": "Motor con Error",
                "detail": f"Último error del ciclo: {last_error}",
                "cycle_count": cycle_count,
                "last_error": last_error,
            }

        if cycle_count == 0:
            up_s = (now_ts - started_at) if started_at > 0 else 0.0
            if started_at > 0 and up_s > STARTUP_GRACE_S:
                return {
                    "status": "RED",
                    "label": "Motor Congelado",
                    "detail": f"Sin completar primer ciclo tras {up_s:.0f}s desde el arranque.",
                    "cycle_count": 0,
                }
            return {
                "status": "YELLOW",
                "label": "Iniciando Ciclo",
                "detail": f"Daemon activo ({strategy_lbl}); ejecutando primer barrido.",
                "cycle_count": 0,
            }

        age_s = max(0.0, now_ts - last_cycle_ts)
        if age_s > CYCLE_STALL_THRESHOLD_S:
            return {
                "status": "RED",
                "label": "Motor Estancado",
                "detail": f"Último ciclo #{cycle_count} hace {age_s / 60.0:.1f} min (> 4 min).",
                "cycle_count": cycle_count,
                "cycle_age_s": round(age_s, 1),
            }

        if is_paused or cooldown_rem > 0 or last_signal == "MERCADO_CERRADO":
            why = "Pausado" if is_paused else (f"Cooldown {cooldown_rem:.0f}s" if cooldown_rem > 0 else "Mercado cerrado")
            return {
                "status": "YELLOW",
                "label": f"Motor ({why})",
                "detail": f"Ciclo #{cycle_count} sano ({why}).",
                "cycle_count": cycle_count,
                "cycle_age_s": round(age_s, 1),
            }

        return {
            "status": "GREEN",
            "label": f"Motor OK (#{cycle_count})",
            "detail": f"Activo en modo '{strategy_lbl}' · último ciclo hace {age_s:.0f}s.",
            "cycle_count": cycle_count,
            "cycle_age_s": round(age_s, 1),
        }

    def _evaluate_guardian(self, snap: Dict[str, Any]) -> Dict[str, Any]:
        open_cnt = int(snap.get("open_positions_count") or 0)
        guardian_active = bool(snap.get("guardian_active"))
        if open_cnt > 0 and not guardian_active:
            return {
                "status": "RED",
                "label": f"Guardián CAÍDO ({open_cnt} pos.)",
                "detail": f"Hay {open_cnt} posición(es) abierta(s) sin hilo Guardián SL/Trailing activo.",
                "open_positions": open_cnt,
                "guardian_active": False,
            }
        if open_cnt > 0:
            return {
                "status": "GREEN",
                "label": f"Guardián OK ({open_cnt} pos.)",
                "detail": f"Guardián vigilando SL/Breakeven/Trailing en {open_cnt} posición(es).",
                "open_positions": open_cnt,
                "guardian_active": True,
            }
        return {
            "status": "GREEN",
            "label": "Guardián Listo (0 pos.)",
            "detail": "Sin posiciones abiertas actualmente; listo para activar protección al entrar.",
            "open_positions": 0,
            "guardian_active": guardian_active,
        }

    def _evaluate_balam_bridge(self, monitor_url: Optional[str] = None) -> Dict[str, Any]:
        base_url = (monitor_url or _default_monitor_url()).rstrip("/")
        now_ts = time.time()

        # 1. Vigencia local del sesgo macro en Kula (MacroBiasBuffer / buzon_radar)
        fresh_macro = False
        macro_age_h: Optional[float] = None
        try:
            from backend.macro_bias_buffer import BUFFER_FILE, parse_iso
            buf_path = os.environ.get("MACRO_BIAS_BUFFER_PATH") or BUFFER_FILE
            if os.path.isfile(buf_path):
                with open(buf_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    newest_ts = 0.0
                    for rec in data.values():
                        if isinstance(rec, dict) and rec.get("created_at"):
                            ts_v = parse_iso(str(rec["created_at"])).timestamp()
                            newest_ts = max(newest_ts, ts_v)
                    if newest_ts > 0:
                        macro_age_h = max(0.0, (now_ts - newest_ts) / 3600.0)
                        fresh_macro = macro_age_h <= MACRO_TTL_HOURS
        except Exception:
            pass

        # 2. Estado HTTP del Monitor del Mercado (0 tokens)
        mon_data: Optional[Dict[str, Any]] = None
        mon_err: Optional[str] = None
        mon_needs_restart = False
        try:
            req = Request(f"{base_url}/api/health/semaforo", method="GET")
            with urlopen(req, timeout=1.2) as resp:
                if resp.status == 200:
                    mon_data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                # Monitor online pero arrancado antes del último cambio (sin --reload)
                try:
                    req2 = Request(f"{base_url}/api/status", method="GET")
                    with urlopen(req2, timeout=1.0) as resp2:
                        if resp2.status == 200:
                            mon_needs_restart = True
                            mon_data = json.loads(resp2.read().decode("utf-8"))
                except Exception as exc2:
                    mon_err = type(exc2).__name__
            else:
                mon_err = f"HTTP {exc.code}"
        except Exception as exc:
            mon_err = type(exc).__name__

        if mon_data is None:
            return {
                "status": "RED",
                "label": "Balam Offline",
                "detail": f"Monitor del Mercado no responde en {base_url} ({mon_err or 'offline'}).",
                "monitor_online": False,
                "fresh_macro": fresh_macro,
                "macro_age_hours": round(macro_age_h, 2) if macro_age_h is not None else None,
            }

        if mon_needs_restart:
            return {
                "status": "YELLOW",
                "label": "Balam (Reiniciar 8520)",
                "detail": "Monitor online sin ruta /api/health/semaforo aún; reiniciar lanzar_todo.sh para activar el semáforo completo en 8520.",
                "monitor_online": True,
                "fresh_macro": fresh_macro,
                "macro_age_hours": round(macro_age_h, 2) if macro_age_h is not None else None,
            }

        lights = mon_data.get("lights") or {}
        rss_l = lights.get("rss_ingesta") or {}
        bridge_l = lights.get("puente_kula") or {}
        feeds_failed = int(rss_l.get("feeds_failed") or 0)
        feeds_ok = int(rss_l.get("feeds_ok") or 0)
        total_feeds = int(rss_l.get("total_feeds") or 0)

        if rss_l.get("status") == "RED" or bridge_l.get("last_inject_ok") is False:
            why = rss_l.get("detail") if rss_l.get("status") == "RED" else bridge_l.get("detail")
            return {
                "status": "RED",
                "label": f"Balam Alerta ({feeds_failed} RSS err)" if rss_l.get("status") == "RED" else "Puente Macro Error",
                "detail": str(why or "Fallo en ingesta RSS o puente hacia Kula."),
                "monitor_online": True,
                "feeds_ok": feeds_ok,
                "feeds_failed": feeds_failed,
                "total_feeds": total_feeds,
                "fresh_macro": fresh_macro,
            }

        if not fresh_macro or rss_l.get("status") == "YELLOW" or bridge_l.get("status") == "YELLOW":
            notes: List[str] = []
            if total_feeds and feeds_ok > 0:
                notes.append(f"RSS {feeds_ok}/{total_feeds} OK")
            elif rss_l.get("label"):
                notes.append(str(rss_l.get("label")))
            if fresh_macro and macro_age_h is not None:
                notes.append(f"macro vigente ({macro_age_h:.1f}h)")
            else:
                notes.append("sin sesgo macro vigente (solo técnico)")
            return {
                "status": "YELLOW",
                "label": "Balam (Solo Técnico)" if not fresh_macro else f"Balam ({feeds_ok}/{total_feeds or '?'} RSS)",
                "detail": " · ".join(notes),
                "monitor_online": True,
                "feeds_ok": feeds_ok,
                "feeds_failed": feeds_failed,
                "total_feeds": total_feeds,
                "fresh_macro": fresh_macro,
                "macro_age_hours": round(macro_age_h, 2) if macro_age_h is not None else None,
            }

        return {
            "status": "GREEN",
            "label": f"Balam OK ({feeds_ok}/{total_feeds or feeds_ok} RSS)",
            "detail": f"Monitor activo ({feeds_ok}/{total_feeds} RSS OK) y sesgo macro vigente ({macro_age_h:.1f}h).",
            "monitor_online": True,
            "feeds_ok": feeds_ok,
            "feeds_failed": feeds_failed,
            "total_feeds": total_feeds,
            "fresh_macro": True,
            "macro_age_hours": round(macro_age_h, 2) if macro_age_h is not None else 0.0,
        }

    def _dispatch_red_transition_alerts(self, lights: Dict[str, Dict[str, Any]], now_ts: float) -> None:
        from backend.telegram_notifier import notify_watchdog_alert

        titles = {
            "kula_motor": "Motor Kula (TraderDaemon)",
            "guardian_sl": "Guardián SL / Trailing",
            "formulas_sintetico": "Test Sintético de Fórmulas",
            "balam_puente": "Monitor Balam / Puente RSS",
        }
        remediations = {
            "kula_motor": "Revisar last_error en Kula y reanudar el agente autónomo.",
            "guardian_sl": "Reiniciar TraderDaemon de inmediato para proteger posiciones abiertas.",
            "formulas_sintetico": "Revisar logs del adaptador/fórmula fallida antes de abrir órdenes.",
            "balam_puente": "Verificar servidor Monitor (puerto 8520) o feeds RSS en config/feeds.yaml.",
        }

        for key, light in lights.items():
            cur_state = str(light.get("status") or "YELLOW")
            with self._lock:
                prev_state = self._last_light_states.get(key)
                last_sent = float(self._last_alert_ts.get(key) or 0.0)
                should_notify = (
                    cur_state == "RED"
                    and (prev_state != "RED" or (now_ts - last_sent) >= TELEGRAM_ALERT_COOLDOWN_S)
                )
                self._last_light_states[key] = cur_state
                if should_notify:
                    self._last_alert_ts[key] = now_ts

            if should_notify:
                try:
                    notify_watchdog_alert(
                        component=titles.get(key, key),
                        title=str(light.get("label") or "FALLO CRÍTICO"),
                        detail=str(light.get("detail") or "Sin detalle"),
                        remediation=remediations.get(key, ""),
                    )
                except Exception as exc:
                    logger.warning("No se pudo enviar alerta Watchdog a Telegram (%s): %s", key, exc)

    @staticmethod
    def _worst_status(*statuses: str) -> str:
        rank = {"GREEN": 0, "YELLOW": 1, "RED": 2}
        worst = "GREEN"
        for st in statuses:
            st_u = str(st or "YELLOW").upper()
            if rank.get(st_u, 1) > rank[worst]:
                worst = st_u if st_u in rank else "YELLOW"
        return worst

    @staticmethod
    def _clip(text: Any, limit: int) -> str:
        flat = " ".join(str(text or "").split())
        return flat if len(flat) <= limit else flat[: limit - 1] + "…"

    def build_quick_check(self, snap: Dict[str, Any], lights: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Chequeo Rápido (3 s): ¿está despierto o dormido? Reutiliza las 4 luces ya evaluadas y la
        telemetría de cobertura del daemon. Determinista, 0 tokens, sin I/O adicional.
        """
        scalp = snap.get("scalping") or {}
        presencial = bool(scalp.get("active") or scalp.get("draining"))
        if presencial:
            mode = "PRESENCIAL"
            formulas = [scalp["strategy"]] if scalp.get("strategy") else []
            tf = str(scalp.get("timeframe") or snap.get("timeframe") or "")
            symbol = str(scalp.get("symbol") or snap.get("active_symbol") or "")
            objective = f"Presencial {symbol} [{tf}]"
        else:
            mode = "AUTO/FONDO"
            strategy_lbl = str(snap.get("strategy") or "auto")
            formulas = list(snap.get("allowed_strategies") or ([strategy_lbl] if strategy_lbl else []))
            tf = str(snap.get("timeframe") or "")
            symbol = str(snap.get("active_symbol") or snap.get("symbol") or "")
            objective = f"Fondo {strategy_lbl} · {symbol}"

        forced = [str(w) for w in (snap.get("forced_tf_warnings") or [])]
        tf_alert = bool(forced)
        formulas_txt = ", ".join(formulas) if formulas else "sin fórmulas"
        mode_text = f"{mode} · {objective} · Fórmulas: {formulas_txt} · TF real: {tf or 'n/d'}"
        if tf_alert:
            mode_text += " · ⚠️ TF forzada: " + "; ".join(forced[:3])

        cov = snap.get("patrol_coverage") or {}
        cov_known = bool(cov.get("expected_symbols"))
        expected = [str(s) for s in (cov.get("expected_symbols") or [])]
        reviewed_set = (
            set(cov.get("evaluated_symbols") or [])
            | set(cov.get("cached_symbols") or [])
            | set(cov.get("market_closed_symbols") or [])
            | set(cov.get("policy_skipped_symbols") or [])
        )
        err_map = dict(cov.get("missing_or_error_symbols") or {})
        reviewed_n = len([s for s in expected if s in reviewed_set and s not in err_map])
        missing = [f"{s} ({why})" for s, why in err_map.items()]
        missing += [f"{s} (sin revisar)" for s in (cov.get("skipped_symbols") or [])]
        closed = list(cov.get("market_closed_symbols") or [])
        if cov_known:
            cov_label = f"{reviewed_n}/{len(expected)} activos revisados"
            if closed:
                cov_label += f" ({len(closed)} con mercado cerrado)"
            if missing:
                cov_label += " · FALTÓ: " + ", ".join(missing[:3])
        else:
            cov_label = "Sin barrido completado aún"

        motor = lights.get("kula_motor") or {}
        guardian = lights.get("guardian_sl") or {}
        balam = lights.get("balam_puente") or {}
        engine = str(snap.get("engine") or "n/d")
        if snap.get("last_error"):
            cerebro_st = "RED"
        elif not snap.get("is_running"):
            cerebro_st = "YELLOW"
        else:
            cerebro_st = "GREEN"
        kula_st = self._worst_status(motor.get("status"), guardian.get("status"))
        triad = {
            "cerebro": {"status": cerebro_st, "label": f"Cerebro: {engine}"},
            "balam": {"status": str(balam.get("status") or "YELLOW"), "label": f"Balam: {balam.get('label') or 'n/d'}"},
            "kula": {
                "status": kula_st,
                "label": f"Kula: {motor.get('label') or 'n/d'} / {guardian.get('label') or 'n/d'}",
            },
        }

        alert_details: List[str] = []
        for key, light in lights.items():
            st_u = str(light.get("status") or "").upper()
            if st_u == "GREEN":
                continue
            if (
                key == "balam_puente"
                and st_u == "YELLOW"
                and bool(light.get("monitor_online"))
                and int(light.get("feeds_failed") or 0) == 0
                and int(light.get("feeds_ok") or 0) > 0
            ):
                continue
            alert_details.append(f"{light.get('label') or key}: {light.get('detail') or 'sin detalle'}")
        if cov_known and missing:
            alert_details.append("Activos sin revisar: " + ", ".join(missing[:3]))
        if tf_alert:
            alert_details.append("Temporalidad forzada: " + "; ".join(forced[:2]))

        is_ok = not alert_details
        reason_full = " ".join(str(snap.get("last_reason") or "").split())
        return {
            "binary_status": "OK" if is_ok else "ALERT",
            "binary_label": "✅ 100% OK" if is_ok else "⚠️ FALTA / ALERTA: " + self._clip("; ".join(alert_details), 240),
            "timeframe": tf,
            "presencial_active": presencial,
            "alert_details": alert_details,
            "active_mode_summary": {
                "mode": mode,
                "objective": objective,
                "formulas": formulas,
                "timeframe": tf,
                "symbol": symbol,
                "forced_tf_warnings": forced,
                "tf_alert": tf_alert,
                "text": mode_text,
            },
            "assets_coverage": {
                "known": cov_known,
                "reviewed": reviewed_n,
                "expected": len(expected),
                "missing": missing,
                "market_closed": closed,
                "label": cov_label,
            },
            "triad_state": triad,
            "last_signal": str(snap.get("last_signal") or ""),
            "last_no_trade_reason": self._clip(reason_full, 220),
            "last_no_trade_reason_full": reason_full,
        }

    def evaluate(
        self,
        daemon: Any,
        force_probe: bool = False,
        notify_on_red: bool = False,
        monitor_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ejecuta evaluación completa del Semáforo de 4 luces sin consumir tokens."""
        now_ts = time.time()
        snap = daemon.get_health_snapshot()
        strat_list = list(snap.get("allowed_strategies") or [])
        if not strat_list and snap.get("strategy"):
            strat_list = [str(snap["strategy"])]

        lights = {
            "kula_motor": self._evaluate_kula_motor(snap, now_ts),
            "guardian_sl": self._evaluate_guardian(snap),
            "formulas_sintetico": self.probe_active_strategies(strat_list, force=force_probe),
            "balam_puente": self._evaluate_balam_bridge(monitor_url=monitor_url),
        }

        if notify_on_red:
            self._dispatch_red_transition_alerts(lights, now_ts)

        states = {v["status"] for v in lights.values()}
        overall = "RED" if "RED" in states else ("YELLOW" if "YELLOW" in states else "GREEN")
        alerts = [
            {"component": k, "status": v["status"], "label": v["label"], "detail": v["detail"]}
            for k, v in lights.items()
            if v["status"] in ("RED", "YELLOW")
        ]

        return {
            "status": overall,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "zero_tokens": True,
            "probe_interval_s": int(WATCHDOG_PROBE_INTERVAL_S),
            "last_probe_ts": self._last_probe_ts,
            "lights": lights,
            "alerts": alerts,
            "quick_check": self.build_quick_check(snap, lights),
        }


_watchdog_instance: Optional[HealthWatchdog] = None
_watchdog_lock = threading.Lock()


def get_health_watchdog() -> HealthWatchdog:
    global _watchdog_instance
    with _watchdog_lock:
        if _watchdog_instance is None:
            _watchdog_instance = HealthWatchdog()
        return _watchdog_instance
