# -*- coding: utf-8 -*-
"""
Motor analítico de campaña de evaluación (2 a 4 semanas) para Kula Balam.

Opera estrictamente en modo read-only sobre `trading_ledger.sqlite3` (0 tokens LLM, $0 USD)
para comparar el rendimiento real en vivo de las fórmulas de `auto` y `operador_presente/`,
detectar puntos de fuga por tipo de salida, auditar `shadow_trades` del Árbitro IA y emitir
dictámenes objetivos (`CONSERVAR`, `CALIBRAR`, `PODAR`, `MUESTRA_INSUFICIENTE`).
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from backend.rejection_funnel import formula_fired, forced_timeframe_warnings, parse_payload

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_CAMPAIGN_CONFIG: Dict[str, Any] = {
    "campaign_name": "Enfriamiento Kula Balam v2 (Auto 4H + Presencial 15M ETH)",
    "since_iso": "2026-11-21T00:00:00Z",
    "target_weeks": 4,
    "target_days": 28,
    "min_resolved_events": 15,
    "min_strategy_trades": 8,
    "min_strategy_shadow_resolved": 8,
    "min_prune_days": 28,
    "min_prune_evals": 100,
    "weekly_snapshot_interval_days": 7,
}

EXIT_REASON_KEYS: Tuple[str, ...] = ("TP", "SL", "BREAKEVEN", "TRAILING", "TIME_MANUAL")


def resolve_default_db_path(db_path: Optional[str] = None) -> str:
    if db_path:
        return str(db_path)
    env_db = os.getenv("TRADING_LEDGER_DB_PATH")
    if env_db:
        return str(env_db)
    candidates = [
        PROJECT_ROOT / "trading_ledger.sqlite3",
        Path("/home/raul/Escritorio/proyectos/kula_balam/trading_ledger.sqlite3"),
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return str(candidates[0])


def resolve_snapshots_dir(snapshots_dir: Optional[str] = None) -> Path:
    if snapshots_dir:
        return Path(snapshots_dir)
    env_dir = os.getenv("CAMPAIGN_SNAPSHOTS_DIR")
    if env_dir:
        return Path(env_dir)
    return PROJECT_ROOT / "data" / "audit_snapshots"


def load_campaign_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CAMPAIGN_CONFIG)
    raw_path = config_path or os.getenv("CAMPAIGN_CONFIG_PATH")
    path = Path(raw_path) if raw_path else (PROJECT_ROOT / "backend" / "config" / "campaign_config.json")
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception:
            pass
    return cfg


def normalize_since_utc(since_iso: Optional[str], fallback_iso: str) -> Tuple[datetime, str, str]:
    """Normaliza una fecha o timestamp ISO a UTC y formato SQLite (`YYYY-MM-DD HH:MM:SS`)."""
    raw = str(since_iso or fallback_iso or "2026-11-21T00:00:00Z").strip()
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        raw = f"{raw}T00:00:00+00:00"
    elif raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_utc = dt.astimezone(timezone.utc)
    except Exception:
        dt_utc = datetime(2026, 11, 21, 0, 0, 0, tzinfo=timezone.utc)
    iso_z = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    sqlite_ts = dt_utc.strftime("%Y-%m-%d %H:%M:%S")
    return dt_utc, iso_z, sqlite_ts


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1;",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _classify_exit_reason(reason: Optional[str]) -> str:
    txt = str(reason or "").strip().lower()
    if not txt:
        return "TIME_MANUAL"
    if "trail" in txt:
        return "TRAILING"
    if "breakeven" in txt or txt == "be" or txt.startswith("be ") or " be " in txt or "be_" in txt:
        return "BREAKEVEN"
    if "take profit" in txt or "take_profit" in txt or "objetivo" in txt or "tp" in txt.split() or txt.startswith("tp"):
        return "TP"
    if "stop" in txt or txt == "sl" or txt.startswith("sl ") or "sl_" in txt or " sl" in txt:
        return "SL"
    return "TIME_MANUAL"


def _load_daemon_state(daemon_state_path: Optional[str] = None) -> Dict[str, Any]:
    raw_path = daemon_state_path or os.getenv("DAEMON_STATE_PATH")
    path = Path(raw_path) if raw_path else (PROJECT_ROOT / "backend" / "config" / "daemon_state.json")
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _load_presencial_catalog() -> Dict[str, Dict[str, Any]]:
    meta_path = PROJECT_ROOT / "backend" / "estrategias" / "catalogo" / "operador_presente" / "metadata.json"
    result: Dict[str, Dict[str, Any]] = {}
    if not meta_path.exists():
        return result
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for fname, entry in raw.items():
                if not isinstance(entry, dict):
                    continue
                sid = str(entry.get("id") or Path(fname).stem).strip()
                if sid:
                    result[sid] = {
                        "id": sid,
                        "titulo": str(entry.get("titulo") or sid),
                        "timeframe": str(entry.get("timeframe") or ""),
                        "activo_default": str(entry.get("activo_default") or ""),
                    }
    except Exception:
        pass
    return result


def _empty_strategy_bucket(strategy_id: str, group: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    meta = meta or {}
    return {
        "strategy_id": strategy_id,
        "group": group,
        "timeframe": str(meta.get("timeframe") or ""),
        "activo_default": str(meta.get("activo_default") or ""),
        "evals": 0,
        "raw_fired": 0,
        "eligible": 0,
        "trades_open": 0,
        "trades_closed": 0,
        "wins": 0,
        "losses": 0,
        "breakevens": 0,
        "win_rate_pct": 0.0,
        "gross_profit_usd": 0.0,
        "gross_loss_usd": 0.0,
        "net_pnl_usd": 0.0,
        "total_fees_usd": 0.0,
        "profit_factor": 0.0,
        "avg_win_usd": 0.0,
        "avg_loss_usd": 0.0,
        "realized_rr": 0.0,
        "expectancy_usd": 0.0,
        "max_drawdown_usd": 0.0,
        "exit_reasons": {k: {"count": 0, "net_pnl_usd": 0.0} for k in EXIT_REASON_KEYS},
        "avg_time_decay_hours": 0.0,
        "avg_counterfactual_diff": 0.0,
        "shadow_vetoed_total": 0,
        "shadow_open": 0,
        "shadow_resolved": 0,
        "shadow_saved_sl": 0,
        "shadow_missed_tp": 0,
        "shadow_expired": 0,
        "shadow_saved_dd_usd": 0.0,
        "shadow_missed_gain_usd": 0.0,
        "shadow_expired_pnl_usd": 0.0,
        "net_arbiter_edge_usd": 0.0,
        "shadow_reasons": {},
        "virtual_open": 0,
        "virtual_closed": 0,
        "virtual_wins": 0,
        "virtual_losses": 0,
        "virtual_expired": 0,
        "virtual_win_rate_pct": 0.0,
        "virtual_gross_profit_usd": 0.0,
        "virtual_gross_loss_usd": 0.0,
        "virtual_net_pnl_usd": 0.0,
        "virtual_fees_usd": 0.0,
        "virtual_profit_factor": 0.0,
        "virtual_realized_rr": 0.0,
        "virtual_max_drawdown_usd": 0.0,
        "verdict": "MUESTRA_INSUFICIENTE",
        "verdict_reason": "",
    }


def _evaluate_verdict(stats: Dict[str, Any], days_elapsed: float, cfg: Dict[str, Any]) -> Tuple[str, str]:
    min_trades = int(cfg.get("min_strategy_trades", 8))
    min_shadow = int(cfg.get("min_strategy_shadow_resolved", 8))
    min_prune_days = float(cfg.get("min_prune_days", 28))
    min_prune_evals = int(cfg.get("min_prune_evals", 100))

    closed = int(stats["trades_closed"])
    pf = float(stats["profit_factor"])
    net_pnl = float(stats["net_pnl_usd"])
    shadow_res = int(stats["shadow_resolved"])
    edge_ia = float(stats["net_arbiter_edge_usd"])
    elig = int(stats["eligible"])
    evals = int(stats["evals"])

    if closed >= min_trades:
        if pf >= 1.20 and net_pnl > 0.0:
            return "CONSERVAR", f"{closed} trades cerrados, PF={pf:.2f} >= 1.20 y PnL=+${net_pnl:.2f}"
        if pf < 0.80:
            return "PODAR", f"{closed} trades cerrados con PF={pf:.2f} < 0.80 (PnL=${net_pnl:.2f})"
        return "CALIBRAR", f"{closed} trades cerrados con rendimiento marginal (PF={pf:.2f}, PnL=${net_pnl:.2f})"

    if shadow_res >= min_shadow and edge_ia < 0.0:
        return "CALIBRAR", f"{shadow_res} vetos resueltos con Edge IA negativo (-${abs(edge_ia):.2f})"

    v_closed = int(stats.get("virtual_closed") or 0)
    if str(stats.get("group") or "") == "operador_presente" and v_closed >= min_trades:
        v_pf = float(stats.get("virtual_profit_factor") or 0.0)
        v_net = float(stats.get("virtual_net_pnl_usd") or 0.0)
        if v_pf >= 1.20 and v_net > 0.0:
            return "CONSERVAR", f"[Eval Virtual Paralela] {v_closed} virtuales cerrados, PF={v_pf:.2f} >= 1.20 y PnL=+${v_net:.2f}"
        if v_pf < 0.80:
            return "PODAR", f"[Eval Virtual Paralela] {v_closed} virtuales cerrados con PF={v_pf:.2f} < 0.80 (PnL=${v_net:.2f})"
        return "CALIBRAR", f"[Eval Virtual Paralela] {v_closed} virtuales cerrados con rendimiento marginal (PF={v_pf:.2f}, PnL=${v_net:.2f})"

    if days_elapsed >= min_prune_days and elig == 0 and closed == 0 and v_closed == 0 and evals >= min_prune_evals:
        return "PODAR", f"0 candidatas y 0 trades tras {days_elapsed:.1f}d ({evals} velas evaluadas)"

    return (
        "MUESTRA_INSUFICIENTE",
        f"Muestra en curso ({closed}/{min_trades} reales · {v_closed}/{min_trades} virtuales · {shadow_res} vetos · {days_elapsed:.1f}d)",
    )


def _compute_series_metrics(events: List[Tuple[float, float]]) -> Dict[str, Any]:
    """Calcula wins, losses, WR, PF, avg win/loss, R:R realizado, MaxDD, fees y PnL sobre una serie ordenada."""
    wins = losses = be = 0
    win_pnls: List[float] = []
    loss_pnls: List[float] = []
    equity = peak = max_dd = total_fees = net_total = 0.0
    for pnl, fees in events:
        total_fees += fees
        net_total += pnl
        if pnl > 1e-6:
            wins += 1
            win_pnls.append(pnl)
        elif pnl < -1e-6:
            losses += 1
            loss_pnls.append(pnl)
        else:
            be += 1
        equity += pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    decided = wins + losses
    gp = sum(win_pnls)
    gl = abs(sum(loss_pnls))
    avg_w = (gp / len(win_pnls)) if win_pnls else 0.0
    avg_l = (gl / len(loss_pnls)) if loss_pnls else 0.0
    n = len(events)
    return {
        "closed": n,
        "wins": wins,
        "losses": losses,
        "breakevens": be,
        "win_rate_pct": round((wins / decided) * 100.0, 2) if decided > 0 else 0.0,
        "gross_profit_usd": round(gp, 4),
        "gross_loss_usd": round(gl, 4),
        "net_pnl_usd": round(net_total, 4),
        "total_fees_usd": round(total_fees, 4),
        "profit_factor": round(gp / gl, 4) if gl > 1e-9 else (99.0 if gp > 1e-9 else 0.0),
        "avg_win_usd": round(avg_w, 4),
        "avg_loss_usd": round(avg_l, 4),
        "realized_rr": round(avg_w / avg_l, 4) if avg_l > 1e-9 else 0.0,
        "expectancy_usd": round(net_total / n, 4) if n > 0 else 0.0,
        "max_drawdown_usd": round(max_dd, 4),
    }


def _finalize_strategy_stats(
    stats: Dict[str, Any],
    closed_rows: List[sqlite3.Row],
    closed_virtual_rows: List[sqlite3.Row],
    days_elapsed: float,
    cfg: Dict[str, Any],
) -> None:
    if closed_rows:
        closed_sorted = sorted(
            closed_rows,
            key=lambda r: (str(r["closed_at"] or r["opened_at"] or ""), str(r["opened_at"] or ""), str(r["id"] or "")),
        )
        td_vals: List[float] = []
        cf_vals: List[float] = []
        real_events: List[Tuple[float, float]] = []
        for r in closed_sorted:
            pnl = float(r["realized_pnl"] or 0.0)
            fees = float(r["total_fees"] or 0.0)
            real_events.append((pnl, fees))
            ex_key = _classify_exit_reason(r["exit_reason"])
            stats["exit_reasons"][ex_key]["count"] += 1
            stats["exit_reasons"][ex_key]["net_pnl_usd"] = round(
                stats["exit_reasons"][ex_key]["net_pnl_usd"] + pnl, 4
            )
            if r["time_decay_hours"] is not None:
                td_vals.append(float(r["time_decay_hours"] or 0.0))
            if r["counterfactual_diff"] is not None:
                cf_vals.append(float(r["counterfactual_diff"] or 0.0))

        m_real = _compute_series_metrics(real_events)
        stats["trades_closed"] = m_real["closed"]
        stats["wins"] = m_real["wins"]
        stats["losses"] = m_real["losses"]
        stats["breakevens"] = m_real["breakevens"]
        stats["win_rate_pct"] = m_real["win_rate_pct"]
        stats["gross_profit_usd"] = m_real["gross_profit_usd"]
        stats["gross_loss_usd"] = m_real["gross_loss_usd"]
        stats["net_pnl_usd"] = m_real["net_pnl_usd"]
        stats["total_fees_usd"] = round(float(stats["total_fees_usd"]) + m_real["total_fees_usd"], 4)
        stats["profit_factor"] = m_real["profit_factor"]
        stats["avg_win_usd"] = m_real["avg_win_usd"]
        stats["avg_loss_usd"] = m_real["avg_loss_usd"]
        stats["realized_rr"] = m_real["realized_rr"]
        stats["expectancy_usd"] = m_real["expectancy_usd"]
        stats["max_drawdown_usd"] = m_real["max_drawdown_usd"]
        stats["avg_time_decay_hours"] = round(sum(td_vals) / len(td_vals), 2) if td_vals else 0.0
        stats["avg_counterfactual_diff"] = round(sum(cf_vals) / len(cf_vals), 4) if cf_vals else 0.0

    if closed_virtual_rows:
        virt_sorted = sorted(
            closed_virtual_rows,
            key=lambda r: (str(r["closed_at"] or r["opened_at"] or ""), str(r["opened_at"] or ""), str(r["id"] or "")),
        )
        virt_events: List[Tuple[float, float]] = []
        v_expired = 0
        for vr in virt_sorted:
            sym = str(vr["symbol"] or "")
            qty = float(vr["qty"] or 0.0)
            entry_px = float(vr["entry_price"] or 0.0)
            fee_rt = (0.0026 if "/" in sym else 0.0006) * abs(entry_px * qty)
            outcome_u = str(vr["outcome"] or "").upper()
            vpnl = float(vr["virtual_pnl_usd"] or 0.0)
            if outcome_u == "MISSED_TP":
                gross = abs(vpnl)
            elif outcome_u == "SAVED_SL":
                gross = -abs(vpnl)
            else:
                gross = vpnl
                v_expired += 1
            virt_events.append((gross - fee_rt, fee_rt))

        m_virt = _compute_series_metrics(virt_events)
        stats["virtual_closed"] = m_virt["closed"]
        stats["virtual_wins"] = m_virt["wins"]
        stats["virtual_losses"] = m_virt["losses"]
        stats["virtual_expired"] = v_expired
        stats["virtual_win_rate_pct"] = m_virt["win_rate_pct"]
        stats["virtual_gross_profit_usd"] = m_virt["gross_profit_usd"]
        stats["virtual_gross_loss_usd"] = m_virt["gross_loss_usd"]
        stats["virtual_net_pnl_usd"] = m_virt["net_pnl_usd"]
        stats["virtual_fees_usd"] = m_virt["total_fees_usd"]
        stats["virtual_profit_factor"] = m_virt["profit_factor"]
        stats["virtual_realized_rr"] = m_virt["realized_rr"]
        stats["virtual_max_drawdown_usd"] = m_virt["max_drawdown_usd"]

    stats["saved_dd_usd"] = round(stats["shadow_saved_dd_usd"], 4)
    stats["shadow_saved_dd_usd"] = round(stats["shadow_saved_dd_usd"], 4)
    stats["shadow_missed_gain_usd"] = round(stats["shadow_missed_gain_usd"], 4)
    stats["shadow_expired_pnl_usd"] = round(stats["shadow_expired_pnl_usd"], 4)
    stats["net_arbiter_edge_usd"] = round(stats["shadow_saved_dd_usd"] - stats["shadow_missed_gain_usd"], 4)

    verdict, verdict_reason = _evaluate_verdict(stats, days_elapsed, cfg)
    stats["verdict"] = verdict
    stats["verdict_reason"] = verdict_reason


def _summarize_group(items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(items)
    closed = sum(int(x["trades_closed"]) for x in rows)
    wins = sum(int(x["wins"]) for x in rows)
    losses = sum(int(x["losses"]) for x in rows)
    be = sum(int(x["breakevens"]) for x in rows)
    gp = sum(float(x["gross_profit_usd"]) for x in rows)
    gl = sum(float(x["gross_loss_usd"]) for x in rows)
    net = sum(float(x["net_pnl_usd"]) for x in rows)
    fees = sum(float(x["total_fees_usd"]) for x in rows)
    decided = wins + losses
    return {
        "strategies_count": len(rows),
        "evals": sum(int(x["evals"]) for x in rows),
        "raw_fired": sum(int(x["raw_fired"]) for x in rows),
        "eligible": sum(int(x["eligible"]) for x in rows),
        "trades_open": sum(int(x["trades_open"]) for x in rows),
        "trades_closed": closed,
        "wins": wins,
        "losses": losses,
        "breakevens": be,
        "win_rate_pct": round((wins / decided) * 100.0, 2) if decided > 0 else 0.0,
        "gross_profit_usd": round(gp, 4),
        "gross_loss_usd": round(gl, 4),
        "net_pnl_usd": round(net, 4),
        "total_fees_usd": round(fees, 4),
        "profit_factor": round(gp / gl, 4) if gl > 1e-9 else (99.0 if gp > 1e-9 else 0.0),
    }


def build_campaign_report(
    db_path: Optional[str] = None,
    since_iso: Optional[str] = None,
    include_presencial: bool = True,
    daemon_state_path: Optional[str] = None,
    config_path: Optional[str] = None,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Construye el reporte cuantitativo completo de campaña en modo solo lectura sobre SQLite."""
    cfg = load_campaign_config(config_path)
    now_dt = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    since_dt, since_z, since_sql = normalize_since_utc(since_iso, str(cfg.get("since_iso") or "2026-11-21T00:00:00Z"))
    days_elapsed = round(max(0.0, (now_dt - since_dt).total_seconds() / 86400.0), 2)

    target_db = resolve_default_db_path(db_path)
    daemon_cfg = _load_daemon_state(daemon_state_path)
    cfg_strategy = str(daemon_cfg.get("strategy") or "auto")
    cfg_tf = str(daemon_cfg.get("timeframe") or "4h")
    cfg_symbol = str(daemon_cfg.get("symbol") or "ETH/USDT")
    auto_ids: List[str] = list(
        daemon_cfg.get("allowed_strategies") or ([cfg_strategy] if cfg_strategy != "auto" else [])
    )
    presencial_catalog = _load_presencial_catalog() if include_presencial else {}

    buckets: Dict[str, Dict[str, Any]] = {}
    for sid in auto_ids:
        if sid and sid not in buckets:
            buckets[sid] = _empty_strategy_bucket(sid, "auto")
    for sid, meta in presencial_catalog.items():
        if sid not in buckets:
            buckets[sid] = _empty_strategy_bucket(sid, "operador_presente", meta)

    def _get_or_create_bucket(sid: str) -> Dict[str, Any]:
        clean = str(sid or "").strip() or "sin_estrategia"
        if clean not in buckets:
            grp = "operador_presente" if clean in presencial_catalog else "other"
            buckets[clean] = _empty_strategy_bucket(clean, grp, presencial_catalog.get(clean))
        return buckets[clean]

    signal_coverage: List[Dict[str, Any]] = []
    closed_trades_by_sid: Dict[str, List[sqlite3.Row]] = defaultdict(list)
    closed_virtual_by_sid: Dict[str, List[sqlite3.Row]] = defaultdict(list)
    shadow_reasons_global: Dict[str, Dict[str, Any]] = {}
    risk_events: Dict[str, int] = {}
    forced_tf_alerts: List[str] = []
    shadow_totals = {
        "vetoed_total": 0,
        "open": 0,
        "resolved": 0,
        "saved_sl": 0,
        "missed_tp": 0,
        "expired": 0,
        "saved_dd_usd": 0.0,
        "missed_gain_usd": 0.0,
        "expired_pnl_usd": 0.0,
        "net_arbiter_edge_usd": 0.0,
    }
    manual_triada_summary = {
        "open": 0,
        "closed": 0,
        "wins": 0,
        "losses": 0,
        "expired": 0,
        "net_pnl_usd": 0.0,
    }

    if os.path.exists(target_db):
        conn = sqlite3.connect(target_db, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            # 1. Cobertura y evaluaciones desde tabla `signals`
            if _table_exists(cursor, "signals"):
                cursor.execute(
                    """
                    SELECT symbol, timeframe, COUNT(*) as evals,
                           SUM(CASE WHEN signal IN ('COMPRAR', 'VENDER') THEN 1 ELSE 0 END) as candidates
                    FROM signals
                    WHERE created_at >= ?
                    GROUP BY symbol, timeframe
                    ORDER BY evals DESC, symbol ASC;
                    """,
                    (since_sql,),
                )
                for row in cursor.fetchall():
                    signal_coverage.append(
                        {
                            "symbol": str(row["symbol"]),
                            "timeframe": str(row["timeframe"]),
                            "evals": int(row["evals"] or 0),
                            "candidates": int(row["candidates"] or 0),
                        }
                    )

                cursor.execute(
                    """
                    SELECT signal, reason, raw_response
                    FROM signals
                    WHERE created_at >= ?;
                    """,
                    (since_sql,),
                )
                seen_forced = set()
                for srow in cursor.fetchall():
                    payload = parse_payload(srow["raw_response"])
                    for fw in (payload.get("forced_tf") or []):
                        fws = str(fw).strip()
                        if fws and fws not in seen_forced:
                            seen_forced.add(fws)
                            forced_tf_alerts.append(fws)

                    if payload.get("stage") == "gate":
                        continue

                    per_st = payload.get("per_strategy")
                    if isinstance(per_st, dict) and per_st:
                        for sid, sdata in per_st.items():
                            b = _get_or_create_bucket(sid)
                            b["evals"] += 1
                            if isinstance(sdata, dict):
                                if sdata.get("eligible"):
                                    b["eligible"] += 1
                                    b["raw_fired"] += 1
                                elif sdata.get("fired"):
                                    b["raw_fired"] += 1
                    else:
                        sid = str(payload.get("strategy") or "").strip()
                        if sid:
                            b = _get_or_create_bucket(sid)
                            b["evals"] += 1
                            is_elig = bool(payload.get("eligible")) or (
                                str(srow["signal"] or "").upper() in ("COMPRAR", "VENDER")
                            )
                            if is_elig:
                                b["eligible"] += 1
                                b["raw_fired"] += 1
                            elif formula_fired([srow["reason"]], False):
                                b["raw_fired"] += 1

            # 2. Trades reales / simulados
            if _table_exists(cursor, "trades"):
                cursor.execute(
                    """
                    SELECT id, symbol, side, status, realized_pnl, total_fees, exit_reason,
                           time_decay_hours, counterfactual_diff, strategy, opened_at, closed_at
                    FROM trades
                    WHERE (status = 'OPEN' AND opened_at >= ?)
                       OR (status = 'CLOSED' AND COALESCE(closed_at, opened_at) >= ?);
                    """,
                    (since_sql, since_sql),
                )
                for trow in cursor.fetchall():
                    sid = str(trow["strategy"] or "").strip() or "sin_estrategia"
                    b = _get_or_create_bucket(sid)
                    if str(trow["status"] or "").upper() == "OPEN":
                        b["trades_open"] += 1
                        b["total_fees_usd"] = round(b["total_fees_usd"] + float(trow["total_fees"] or 0.0), 4)
                    else:
                        closed_trades_by_sid[sid].append(trow)

            # 3. Shadow testing (vetos Árbitro IA) vs Evaluación Paralela Virtual (EVAL_PARALELA)
            if _table_exists(cursor, "shadow_trades"):
                cursor.execute(
                    """
                    SELECT id, symbol, qty, entry_price, status, outcome, virtual_pnl_usd,
                           strategy, arbiter_verdict, arbiter_reason, opened_at, closed_at
                    FROM shadow_trades
                    WHERE (status = 'OPEN' AND opened_at >= ?)
                       OR (status = 'CLOSED' AND COALESCE(closed_at, opened_at) >= ?);
                    """,
                    (since_sql, since_sql),
                )
                for sh in cursor.fetchall():
                    status_u = str(sh["status"] or "").upper()
                    verdict_u = str(sh["arbiter_verdict"] or "").upper()
                    if verdict_u == "MANUAL_TRIADA":
                        if status_u == "OPEN":
                            manual_triada_summary["open"] += 1
                        elif status_u == "CLOSED":
                            manual_triada_summary["closed"] += 1
                            vpnl_m = float(sh["virtual_pnl_usd"] or 0.0)
                            out_m = str(sh["outcome"] or "").upper()
                            if out_m == "EXPIRED":
                                manual_triada_summary["expired"] += 1
                            elif vpnl_m > 1e-6:
                                manual_triada_summary["wins"] += 1
                            elif vpnl_m < -1e-6:
                                manual_triada_summary["losses"] += 1
                            manual_triada_summary["net_pnl_usd"] = round(
                                manual_triada_summary["net_pnl_usd"] + vpnl_m, 4
                            )
                        continue

                    sid = str(sh["strategy"] or "").strip() or "sin_estrategia"
                    b = _get_or_create_bucket(sid)
                    if verdict_u == "EVAL_PARALELA":
                        if status_u == "OPEN":
                            b["virtual_open"] += 1
                        elif status_u == "CLOSED":
                            closed_virtual_by_sid[sid].append(sh)
                        continue

                    reason_lbl = str(sh["arbiter_reason"] or "Sin motivo").strip() or "Sin motivo"
                    outcome_u = str(sh["outcome"] or "").upper()
                    vpnl = float(sh["virtual_pnl_usd"] or 0.0)

                    b["shadow_vetoed_total"] += 1
                    shadow_totals["vetoed_total"] += 1
                    sr_strat = b["shadow_reasons"].setdefault(
                        reason_lbl, {"vetoed": 0, "saved_sl": 0, "missed_tp": 0, "expired": 0, "edge_usd": 0.0}
                    )
                    sr_glob = shadow_reasons_global.setdefault(
                        reason_lbl,
                        {"reason": reason_lbl, "vetoed": 0, "open": 0, "resolved": 0, "saved_sl": 0, "missed_tp": 0, "expired": 0, "edge_usd": 0.0},
                    )
                    sr_strat["vetoed"] += 1
                    sr_glob["vetoed"] += 1

                    if status_u == "OPEN":
                        b["shadow_open"] += 1
                        shadow_totals["open"] += 1
                        sr_glob["open"] += 1
                    elif status_u == "CLOSED":
                        b["shadow_resolved"] += 1
                        shadow_totals["resolved"] += 1
                        sr_glob["resolved"] += 1
                        if outcome_u == "SAVED_SL":
                            saved = abs(vpnl)
                            b["shadow_saved_sl"] += 1
                            b["shadow_saved_dd_usd"] += saved
                            shadow_totals["saved_sl"] += 1
                            shadow_totals["saved_dd_usd"] += saved
                            sr_strat["saved_sl"] += 1
                            sr_strat["edge_usd"] = round(sr_strat["edge_usd"] + saved, 4)
                            sr_glob["saved_sl"] += 1
                            sr_glob["edge_usd"] = round(sr_glob["edge_usd"] + saved, 4)
                        elif outcome_u == "MISSED_TP":
                            b["shadow_missed_tp"] += 1
                            b["shadow_missed_gain_usd"] += vpnl
                            shadow_totals["missed_tp"] += 1
                            shadow_totals["missed_gain_usd"] += vpnl
                            sr_strat["missed_tp"] += 1
                            sr_strat["edge_usd"] = round(sr_strat["edge_usd"] - vpnl, 4)
                            sr_glob["missed_tp"] += 1
                            sr_glob["edge_usd"] = round(sr_glob["edge_usd"] - vpnl, 4)
                        elif outcome_u == "EXPIRED":
                            b["shadow_expired"] += 1
                            b["shadow_expired_pnl_usd"] += vpnl
                            shadow_totals["expired"] += 1
                            shadow_totals["expired_pnl_usd"] += vpnl
                            sr_strat["expired"] += 1
                            sr_glob["expired"] += 1

            # 4. Risk events
            if _table_exists(cursor, "risk_events"):
                cursor.execute(
                    """
                    SELECT event_type, COUNT(*) as cnt
                    FROM risk_events
                    WHERE created_at >= ?
                    GROUP BY event_type;
                    """,
                    (since_sql,),
                )
                for rr in cursor.fetchall():
                    risk_events[str(rr["event_type"])] = int(rr["cnt"] or 0)
        finally:
            conn.close()

    # Verificar alertas de temporalidad forzada estáticas del daemon_state actual
    try:
        from backend.estrategias.registry import _sync_catalog_registry, get_strategy

        _sync_catalog_registry()
        if cfg_strategy == "auto" and str(cfg_tf).strip().lower() not in ("4h", "1d"):
            msg = f"Selector de fondo 'auto' en {cfg_tf} (debe ser 4h)"
            if msg not in forced_tf_alerts:
                forced_tf_alerts.insert(0, msg)
            for fw in forced_timeframe_warnings(auto_ids, cfg_tf, get_strategy):
                if fw not in forced_tf_alerts:
                    forced_tf_alerts.append(fw)
        elif cfg_strategy != "auto":
            for fw in forced_timeframe_warnings(auto_ids, cfg_tf, get_strategy):
                if fw not in forced_tf_alerts:
                    forced_tf_alerts.append(fw)
    except Exception:
        pass

    # Finalizar estadísticas por estrategia
    for sid, b in buckets.items():
        _finalize_strategy_stats(
            b,
            closed_trades_by_sid.get(sid, []),
            closed_virtual_by_sid.get(sid, []),
            days_elapsed,
            cfg,
        )

    auto_list = [buckets[s] for s in auto_ids if s in buckets]
    presencial_list = [buckets[s] for s in sorted(presencial_catalog.keys()) if s in buckets and s not in set(auto_ids)]
    other_list = [b for sid, b in sorted(buckets.items()) if b["group"] == "other"]

    # Enriquecer metadata de auto_strategies desde registry cuando falte
    try:
        from backend.estrategias.registry import get_strategy

        for row in auto_list + other_list:
            st = get_strategy(row["strategy_id"])
            if st is not None:
                if not row["timeframe"]:
                    row["timeframe"] = str(getattr(st, "native_timeframe", "") or cfg_tf)
                if not row["activo_default"]:
                    row["activo_default"] = str(getattr(st, "activo_default", "") or "")
    except Exception:
        pass

    all_rows = auto_list + presencial_list + other_list
    total_summary = _summarize_group(all_rows)
    auto_summary = _summarize_group(auto_list)
    presencial_summary = _summarize_group(presencial_list)

    ps_open = sum(int(x.get("virtual_open") or 0) for x in all_rows)
    ps_closed = sum(int(x.get("virtual_closed") or 0) for x in all_rows)
    ps_wins = sum(int(x.get("virtual_wins") or 0) for x in all_rows)
    ps_losses = sum(int(x.get("virtual_losses") or 0) for x in all_rows)
    ps_expired = sum(int(x.get("virtual_expired") or 0) for x in all_rows)
    ps_gp = sum(float(x.get("virtual_gross_profit_usd") or 0.0) for x in all_rows)
    ps_gl = sum(float(x.get("virtual_gross_loss_usd") or 0.0) for x in all_rows)
    ps_net = sum(float(x.get("virtual_net_pnl_usd") or 0.0) for x in all_rows)
    ps_fees = sum(float(x.get("virtual_fees_usd") or 0.0) for x in all_rows)
    ps_decided = ps_wins + ps_losses
    parallel_shadow_summary = {
        "open": ps_open,
        "closed": ps_closed,
        "virtual_resolved": ps_closed,
        "wins": ps_wins,
        "losses": ps_losses,
        "expired": ps_expired,
        "win_rate_pct": round((ps_wins / ps_decided) * 100.0, 2) if ps_decided > 0 else 0.0,
        "gross_profit_usd": round(ps_gp, 4),
        "gross_loss_usd": round(ps_gl, 4),
        "net_pnl_usd": round(ps_net, 4),
        "fees_usd": round(ps_fees, 4),
        "profit_factor": round(ps_gp / ps_gl, 4) if ps_gl > 1e-9 else (99.0 if ps_gp > 1e-9 else 0.0),
    }

    shadow_totals["saved_dd_usd"] = round(shadow_totals["saved_dd_usd"], 4)
    shadow_totals["missed_gain_usd"] = round(shadow_totals["missed_gain_usd"], 4)
    shadow_totals["expired_pnl_usd"] = round(shadow_totals["expired_pnl_usd"], 4)
    shadow_totals["net_arbiter_edge_usd"] = round(
        shadow_totals["saved_dd_usd"] - shadow_totals["missed_gain_usd"], 4
    )

    min_resolved = int(cfg.get("min_resolved_events", 15))
    target_days = int(cfg.get("target_days", 28))
    resolved_events = int(total_summary["trades_closed"]) + int(shadow_totals["resolved"])
    progress_pct = round(min(100.0, (resolved_events / max(1, min_resolved)) * 100.0), 1)

    # Desglose agregado de exit_reasons
    global_exits = {k: {"count": 0, "net_pnl_usd": 0.0} for k in EXIT_REASON_KEYS}
    for row in all_rows:
        for k in EXIT_REASON_KEYS:
            global_exits[k]["count"] += int(row["exit_reasons"][k]["count"])
            global_exits[k]["net_pnl_usd"] = round(
                global_exits[k]["net_pnl_usd"] + float(row["exit_reasons"][k]["net_pnl_usd"]), 4
            )

    shadow_reasons_sorted = sorted(
        shadow_reasons_global.values(), key=lambda x: (-int(x["vetoed"]), x["reason"])
    )

    return {
        "campaign": {
            "name": str(cfg.get("campaign_name") or DEFAULT_CAMPAIGN_CONFIG["campaign_name"]),
            "since_iso": since_z,
            "since_sql": since_sql,
            "target_weeks": int(cfg.get("target_weeks", 4)),
            "target_days": target_days,
            "min_resolved_events": min_resolved,
            "daemon_mode": cfg_strategy,
            "daemon_timeframe": cfg_tf,
            "daemon_base_symbol": cfg_symbol,
        },
        "generated_at_utc": now_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "db_path": target_db,
        "summary": {
            **total_summary,
            "resolved_events": resolved_events,
            "min_resolved_events": min_resolved,
            "progress_pct": progress_pct,
            "days_elapsed": days_elapsed,
            "target_days": target_days,
            "cooling_complete": resolved_events >= min_resolved,
            "auto": auto_summary,
            "presencial": presencial_summary,
            "shadow": shadow_totals,
            "parallel_shadow": parallel_shadow_summary,
            "manual_triada": manual_triada_summary,
            "exit_reasons": global_exits,
        },
        "auto_strategies": auto_list,
        "presencial_strategies": presencial_list,
        "other_strategies": other_list,
        "signal_coverage": signal_coverage,
        "shadow_by_reason": shadow_reasons_sorted,
        "infrastructure": {
            "risk_events": risk_events,
            "forced_tf_alerts_count": len(forced_tf_alerts),
            "forced_tf_warnings": forced_tf_alerts,
        },
    }


def _format_strategy_table(title: str, rows: List[Dict[str, Any]], show_virtual: bool = False) -> List[str]:
    lines = [title]
    if not rows:
        lines.append("  (Sin estrategias registradas en este bloque)")
        return lines
    tr_hdr = "Tr(V)" if show_virtual else "Tr"
    pnl_hdr = "PnL Virt" if show_virtual else "PnL USD"
    header = (
        f"  {'Estrategia':<33} | {'Velas':>5} | {'Crud':>4} | {'Cand':>4} | {tr_hdr:>5} | "
        f"{'WR':>6} | {'PF':>5} | {'R:R':>4} | {pnl_hdr:>9} | {'Edge IA':>8} | Dictamen"
    )
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    for r in rows:
        use_v = bool(show_virtual and int(r.get("trades_closed") or 0) == 0 and (int(r.get("virtual_closed") or 0) > 0 or int(r.get("virtual_open") or 0) > 0))
        tr_str = f"{int(r.get('virtual_closed') or 0)}V" if use_v else f"{int(r.get('trades_closed') or 0)}"
        wr_val = float(r.get("virtual_win_rate_pct") if use_v else r.get("win_rate_pct") or 0.0)
        pf_val = float(r.get("virtual_profit_factor") if use_v else r.get("profit_factor") or 0.0)
        rr_val = float(r.get("virtual_realized_rr") if use_v else r.get("realized_rr") or 0.0)
        pnl_val = float(r.get("virtual_net_pnl_usd") if use_v else r.get("net_pnl_usd") or 0.0)
        lines.append(
            f"  {r['strategy_id']:<33} | {r['evals']:>5} | {r['raw_fired']:>4} | {r['eligible']:>4} | "
            f"{tr_str:>5} | {wr_val:>5.1f}% | {pf_val:>5.2f} | "
            f"{rr_val:>4.2f} | {pnl_val:>+9.2f} | {r['net_arbiter_edge_usd']:>+8.2f} | {r['verdict']}"
        )
    return lines


def format_campaign_text(report: Dict[str, Any]) -> str:
    """Genera un resumen textual estructurado para CLI, snapshots .txt y pegado en auditorías IA."""
    camp = report.get("campaign") or {}
    summ = report.get("summary") or {}
    sh = summ.get("shadow") or {}
    ps = summ.get("parallel_shadow") or {}
    infra = report.get("infrastructure") or {}
    exits = summ.get("exit_reasons") or {}

    lines: List[str] = []
    lines.append("--- [ 📊 EVALUACIÓN DE CAMPAÑA (AUTO vs OPERADOR PRESENTE) ] ---")
    lines.append(
        f"  Campaña: {camp.get('name', 'Kula Balam')} | Desde: {camp.get('since_iso')} "
        f"| Día {summ.get('days_elapsed', 0):.1f}/{summ.get('target_days', 28)}"
    )
    lines.append(
        f"  Meta Muestral Enfriamiento: {summ.get('resolved_events', 0)}/{summ.get('min_resolved_events', 15)} "
        f"eventos resueltos ({summ.get('progress_pct', 0):.1f}%) | "
        f"PnL Neto (Real VAULT): ${summ.get('net_pnl_usd', 0.0):+.2f} | PF Global: {summ.get('profit_factor', 0.0):.2f} | "
        f"Edge Árbitro IA: ${sh.get('net_arbiter_edge_usd', 0.0):+.2f}"
    )
    if ps.get("closed", 0) > 0 or ps.get("open", 0) > 0:
        lines.append(
            f"  Eval Paralela Virtual (15m/5m sin slot): {ps.get('closed', 0)} cerrados ({ps.get('open', 0)} ab.) | "
            f"WR={ps.get('win_rate_pct', 0.0):.1f}% | PF={ps.get('profit_factor', 0.0):.2f} | PnL Virt=${ps.get('net_pnl_usd', 0.0):+.2f}"
        )
    lines.append("")
    lines.extend(_format_strategy_table("  [A] BLOQUE AUTO (DAEMON DE FONDO · VAULT_USDT)", report.get("auto_strategies") or []))
    lines.append("")
    lines.extend(
        _format_strategy_table("  [B] BLOQUE OPERADOR PRESENTE (EVAL PARALELA VIRTUAL + SESIONES)", report.get("presencial_strategies") or [], show_virtual=True)
    )
    if report.get("other_strategies"):
        lines.append("")
        lines.extend(_format_strategy_table("  [C] OTRAS ESTRATEGIAS OBSERVADAS EN DB", report["other_strategies"]))

    lines.append("")
    exit_parts = [f"{k}={int(exits.get(k, {}).get('count', 0))} (${float(exits.get(k, {}).get('net_pnl_usd', 0.0)):+.2f})" for k in EXIT_REASON_KEYS]
    lines.append(f"  🔎 Puntos de fuga (exit_reason): {' | '.join(exit_parts)}")

    sh_reasons = report.get("shadow_by_reason") or []
    if sh_reasons:
        lines.append("  👻 Desglose Shadow Testing por motivo:")
        for sr in sh_reasons[:8]:
            lines.append(
                f"     • {sr['reason']}: {sr['vetoed']} vetos "
                f"(SL ahorrado={sr['saved_sl']}, TP perdido={sr['missed_tp']}, Exp={sr['expired']}) | Edge=${sr['edge_usd']:+.2f}"
            )

    risk_ev = infra.get("risk_events") or {}
    forced = infra.get("forced_tf_warnings") or []
    lines.append(
        f"  🛡️ Infraestructura: RiskEvents={risk_ev if risk_ev else '0'} | Alertas TF forzada={len(forced)}"
    )
    lines.append("")
    return "\n".join(lines)


def save_campaign_snapshot(
    db_path: Optional[str] = None,
    since_iso: Optional[str] = None,
    snapshots_dir: Optional[str] = None,
    trigger: str = "manual",
    daemon_state_path: Optional[str] = None,
    config_path: Optional[str] = None,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    now_dt = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    report = build_campaign_report(
        db_path=db_path,
        since_iso=since_iso,
        include_presencial=True,
        daemon_state_path=daemon_state_path,
        config_path=config_path,
        now_utc=now_dt,
    )
    snap_dir = resolve_snapshots_dir(snapshots_dir)
    snap_dir.mkdir(parents=True, exist_ok=True)
    slug = now_dt.strftime("%Y-%m-%d_%H%M%S")
    json_path = snap_dir / f"{slug}_campaign.json"
    txt_path = snap_dir / f"{slug}_campaign.txt"

    payload = {
        "schema_version": 1,
        "trigger": str(trigger or "manual"),
        "created_at_utc": now_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "report": report,
    }
    text_summary = format_campaign_text(report)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    txt_path.write_text(text_summary, encoding="utf-8")

    return {
        "filename_json": json_path.name,
        "filename_txt": txt_path.name,
        "path_json": str(json_path),
        "path_txt": str(txt_path),
        "created_at_utc": payload["created_at_utc"],
        "trigger": payload["trigger"],
        "report": report,
    }


def list_campaign_snapshots(snapshots_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    snap_dir = resolve_snapshots_dir(snapshots_dir)
    if not snap_dir.exists():
        return []
    items: List[Dict[str, Any]] = []
    for fpath in sorted(snap_dir.glob("*_campaign.json"), reverse=True):
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            rep = data.get("report") or {}
            summ = rep.get("summary") or {}
            sh = summ.get("shadow") or {}
            items.append(
                {
                    "filename": fpath.name,
                    "created_at_utc": str(data.get("created_at_utc") or rep.get("generated_at_utc") or ""),
                    "trigger": str(data.get("trigger") or "manual"),
                    "days_elapsed": float(summ.get("days_elapsed") or 0.0),
                    "resolved_events": int(summ.get("resolved_events") or 0),
                    "trades_closed": int(summ.get("trades_closed") or 0),
                    "net_pnl_usd": float(summ.get("net_pnl_usd") or 0.0),
                    "net_arbiter_edge_usd": float(sh.get("net_arbiter_edge_usd") or 0.0),
                }
            )
        except Exception:
            continue
    return items


def maybe_write_weekly_snapshot(
    db_path: Optional[str] = None,
    snapshots_dir: Optional[str] = None,
    interval_days: Optional[int] = None,
    daemon_state_path: Optional[str] = None,
    config_path: Optional[str] = None,
    now_utc: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    cfg = load_campaign_config(config_path)
    req_days = int(interval_days if interval_days is not None else cfg.get("weekly_snapshot_interval_days", 7))
    now_dt = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)

    existing = list_campaign_snapshots(snapshots_dir)
    if existing:
        latest_ts = str(existing[0].get("created_at_utc") or "").strip()
        if latest_ts:
            try:
                norm_ts = latest_ts[:-1] + "+00:00" if latest_ts.endswith("Z") else latest_ts
                last_dt = datetime.fromisoformat(norm_ts)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if (now_dt - last_dt.astimezone(timezone.utc)) < timedelta(days=req_days):
                    return None
            except Exception:
                pass

    return save_campaign_snapshot(
        db_path=db_path,
        snapshots_dir=snapshots_dir,
        trigger="weekly_auto",
        daemon_state_path=daemon_state_path,
        config_path=config_path,
        now_utc=now_dt,
    )
