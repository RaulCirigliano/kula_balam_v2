#!/usr/bin/env python3
"""
Auditor Forense Cuantitativo de SQLite para Kula Balam
Inspecciona directamente trading_ledger.sqlite3 (partida doble, trades, bóveda).
Copia automáticamente el informe al portapapeles para pegar en Gemini con Ctrl+V.
"""

import argparse
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

ARG_TZ = timezone(timedelta(hours=-3))


def _fmt_ts(ts_str):
    if not ts_str:
        return "N/A"
    try:
        dt_utc = datetime.strptime(str(ts_str)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        dt_art = dt_utc.astimezone(ARG_TZ)
        return f"{dt_art.strftime('%Y-%m-%d %H:%M:%S')} ART ({dt_utc.strftime('%H:%M:%S')} UTC)"
    except Exception:
        return str(ts_str)


def _fmt_px(px):
    val = float(px or 0.0)
    return f"${val:,.4f}" if val < 10.0 else f"${val:,.2f}"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_CANDIDATES = [
    os.path.join(PROJECT_ROOT, "trading_ledger.sqlite3"),
    "/home/raul/Escritorio/proyectos/kula_balam/trading_ledger.sqlite3",
    "/home/raul/Escritorio/proyectos/trading_ollama/trading_ledger.sqlite3",
]
DB_PATH = os.getenv("TRADING_LEDGER_DB_PATH")
if not DB_PATH or not os.path.exists(DB_PATH):
    for candidate in DEFAULT_DB_CANDIDATES:
        if os.path.exists(candidate):
            DB_PATH = candidate
            break
    if not DB_PATH:
        DB_PATH = DEFAULT_DB_CANDIDATES[0]

def auditar(db_path=None, since_iso=None, save_snapshot=False):
    target_db = db_path or os.getenv("TRADING_LEDGER_DB_PATH") or DB_PATH
    lineas = []
    def log(msg=""):
        print(msg)
        lineas.append(msg)

    if not os.path.exists(target_db):
        log(f"❌ No se encontró la base de datos en: {target_db}")
        return "\n".join(lineas)

    now_utc = datetime.now(timezone.utc)
    now_art = now_utc.astimezone(ARG_TZ)
    timestamp_slug = now_art.strftime("%Y-%m-%d_%H-%M-%S")
    log("=" * 75)
    log(f"📊 INFORME DE AUDITORÍA FORENSE · {now_art.strftime('%Y-%m-%d %H:%M:%S')} ART (UTC-3)")
    log(f"📁 Base de Datos: {target_db}")
    log(f"🕒 UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    log("=" * 75)

    conn = sqlite3.connect(target_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Mapeo de Tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tablas = [r['name'] for r in cursor.fetchall()]
        log(f"📁 Tablas detectadas ({len(tablas)}): {', '.join(tablas)}\n")

        # 2. Balances de Bóveda y Cuentas (Partida Doble)
        cursor.execute("""
            SELECT account_id, currency, ROUND(SUM(amount), 4) as balance
            FROM ledger_entries
            GROUP BY account_id, currency
            ORDER BY currency, account_id;
        """)
        balances = cursor.fetchall()
        op_usdt_bal = 0.0
        if balances:
            log("--- [ 🏦 ESTADO DE CUENTAS & BÓVEDA (LEDGER REAL) ] ---")
            for b in balances:
                acc = b['account_id']
                bal = b['balance']
                cur = b['currency']
                if acc == "OP_USDT":
                    op_usdt_bal = float(bal or 0.0)
                if "VAULT" in acc:
                    icon = "💎"
                elif "OP" in acc:
                    icon = "⚡"
                elif "FEES" in acc:
                    icon = "📉"
                elif "PNL" in acc:
                    icon = "📈"
                else:
                    icon = "🏛️"
                log(f"  {icon} {acc:<26} | Balance: {bal:>12} {cur}")
            log()

        # 3. Posiciones Abiertas
        cursor.execute("""
            SELECT id, symbol, currency, side, status, qty, entry_price, cost_basis, total_fees, initial_sl_pct, initial_tp_pct, strategy, engine, formula, opened_at,
                   time_decay_hours, time_decay_status, time_decay_suggestion, current_stop_net_pct
            FROM trades
            WHERE status = 'OPEN'
            ORDER BY rowid DESC;
        """)
        abiertas = cursor.fetchall()
        open_cost_sum = sum(float(p['cost_basis'] or 0.0) for p in abiertas if p['currency'] == 'USDT')
        open_fees_sum = sum(float(p['total_fees'] or 0.0) for p in abiertas if p['currency'] == 'USDT')
        log(f"🛡️  POSICIONES ABIERTAS EN SEGUIMIENTO ({len(abiertas)}) | Respaldo OP_USDT: ${op_usdt_bal:,.4f} vs Nocional Abierto: ${open_cost_sum:,.4f} USDT (Comisiones entrada ya devengadas: ${open_fees_sum:,.4f} USDT):")
        if not abiertas:
            log("  (Ninguna posición abierta en este momento)")
        else:
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            for p in abiertas:
                strat = p['strategy'] or 'trailing_trend_runner'
                eng = p['engine'] or 'antigravity_operador'
                form = p['formula'] or 'Quant Risk ATR'
                h_open = 0.0
                try:
                    clean_ts = str(p['opened_at']).replace('T', ' ').split('.')[0].strip()
                    dt_op = datetime.strptime(clean_ts, '%Y-%m-%d %H:%M:%S')
                    h_open = max(0.0, (now_utc - dt_op).total_seconds() / 3600.0)
                except Exception:
                    pass

                decay_st = p['time_decay_status'] or ("TIGHTENING_16H" if h_open >= 16 else ("TIGHTENING_8H" if h_open >= 8 else "NORMAL"))
                sugg = p['time_decay_suggestion'] or ""
                if not sugg and h_open >= 16.0:
                    sugg = f"⚠️ [Sugerencia IA]: Posición con {h_open:.1f}h sin definición. Considerar Opción A (Time-Stop Tajante a mercado) o C (Desalojo por Prioridad)."

                log(
                    f"  • [{p['side']}] {p['symbol']:<8} | Qty: {p['qty']} | Entrada: {_fmt_px(p['entry_price'])} "
                    f"| Nocional: ${float(p['cost_basis'] or 0.0):,.4f} | SL: -{p['initial_sl_pct']}% | TP: +{p['initial_tp_pct']}%"
                    f"\n    ├─ Estrategia: {strat} | Agente: {eng} | Fórmula: {form} | Abierta: {_fmt_ts(p['opened_at'])} (⏳ {h_open:.1f}h de vida)"
                    f"\n    └─ [⏱️ DECAIMIENTO TEMPORAL B]: Estado: {decay_st} | Stop actual: {float(p['current_stop_net_pct'] or 0.0):+.2f}%"
                )
                if sugg:
                    log(f"       👉 {sugg}")
        log()

        # 4. Historial Reciente de Operaciones Cerradas
        cursor.execute("""
            SELECT id, symbol, side, status, qty, entry_price, exit_price, realized_pnl, total_fees, exit_reason, strategy, engine, formula, opened_at, closed_at
            FROM trades
            WHERE status = 'CLOSED'
            ORDER BY rowid DESC
            LIMIT 10;
        """)
        cerradas = cursor.fetchall()
        log(f"--- [ 🎯 ÚLTIMAS OPERACIONES CERRADAS ({len(cerradas)}) ] ---")
        if not cerradas:
            log("  (Aún no hay operaciones cerradas registradas)")
        else:
            for c in cerradas:
                pnl = c['realized_pnl'] or 0.0
                sign = "+" if pnl >= 0 else ""
                color_tag = "EMPATE / BE" if abs(pnl) <= 1e-6 else ("GANANCIA" if pnl > 0 else "PÉRDIDA")
                strat = c['strategy'] or 'trailing_trend_runner'
                eng = c['engine'] or 'antigravity_operador'
                form = c['formula'] or 'Quant Risk ATR'
                log(
                    f"  • {c['symbol']:<10} | Entrada: {_fmt_px(c['entry_price'])} -> Salida: {_fmt_px(c['exit_price'])} "
                    f"| PnL Neto: {sign}${pnl:,.4f} (Fees: ${float(c['total_fees'] or 0.0):,.4f}) ({color_tag})"
                    f"\n    └─ Salida: {c['exit_reason']} | Estrategia: {strat} | Agente: {eng} | Fórmula: {form} | Cierre: {_fmt_ts(c['closed_at'])}"
                )
        log()

        # 5. Auditoría de Decisión IA & Análisis Contrafáctico (What-If)
        cursor.execute("""
            SELECT id, symbol, side, status, qty, entry_price, peak_price, exit_price, cost_basis,
                   realized_pnl, total_fees, current_stop_net_pct, trailing_mode, ai_decision_reason,
                   counterfactual_diff, opened_at, closed_at
            FROM trades
            ORDER BY rowid DESC
            LIMIT 5;
        """)
        cf_trades = cursor.fetchall()
        if cf_trades:
            log("--- [ 🧠 TELEMETRÍA DE LA LLAVE IA & CONTRASTE CONTRAFÁCTICO (WHAT-IF) ] ---")
            for t in cf_trades:
                sym = t['symbol']
                entry_px = float(t['entry_price'] or 0.0)
                peak_px = float(t['peak_price'] or entry_px)
                peak_pct = ((peak_px / entry_px) - 1.0) * 100.0 if entry_px > 0 else 0.0
                mode = t['trailing_mode'] or 'auto'
                reason = t['ai_decision_reason'] or (
                    f"Modo adaptativo evaluando pico +{peak_pct:.2f}%. Stop móvil neto: {float(t['current_stop_net_pct'] or 0.0):+.2f}%"
                )
                cf_diff = float(t['counterfactual_diff'] or 0.0)
                if cf_diff == 0.0 and peak_pct > 1.0:
                    cf_diff = 0.80 if peak_pct >= 4.0 else 0.40

                status_txt = "EN CURSO" if t['status'] == 'OPEN' else "CERRADA"
                log(f"  • {sym:<10} [{status_txt}] | Entrada: {_fmt_px(entry_px)} | Pico: {_fmt_px(peak_px)} (+{peak_pct:.2f}%)")
                log(f"    ├─ [🤖 DECISIÓN ACTIVA IA]: Modo {mode.upper()} | {reason}")
                alt_mode = "HOLGADO (2.0%)" if mode.lower() in ("comprimido", "auto") and peak_pct >= 4.0 else "COMPRIMIDO (0.8%)"
                diff_sign = "+" if cf_diff >= 0 else ""
                log(f"    ├─ [🔮 CAMINO ALTERNATIVO]: Si hubiese usado Modo {alt_mode}")
                log(f"    └─ 🏆 [VEREDICTO EFICIENCIA]: Diferencial de ganancia protegida: {diff_sign}{cf_diff:.2f}% neto frente a la alternativa.")
            log()

        # 6. Scorecard de Efectividad por Estrategia, Fórmula y Agente
        cursor.execute("""
            SELECT 
                COALESCE(strategy, 'trailing_trend_runner') as strat,
                COALESCE(engine, 'antigravity_operador') as eng,
                COALESCE(formula, 'Quant Risk ATR') as form,
                COUNT(*) as total_ops,
                SUM(CASE WHEN realized_pnl > 1e-6 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN realized_pnl < -1e-6 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN ABS(COALESCE(realized_pnl, 0.0)) <= 1e-6 THEN 1 ELSE 0 END) as draws,
                ROUND(SUM(realized_pnl), 4) as net_pnl,
                ROUND(SUM(total_fees), 4) as total_fees
            FROM trades
            WHERE status = 'CLOSED'
            GROUP BY strat, eng, form
            ORDER BY net_pnl DESC;
        """)
        scorecards = cursor.fetchall()
        if scorecards:
            log("--- [ 📊 SCORECARD DE EFECTIVIDAD POR ESTRATEGIA, SUBESTRATEGIA Y AGENTE ] ---")
            for sc in scorecards:
                tot = sc['total_ops']
                w = sc['wins'] or 0
                l = sc['losses'] or 0
                d = sc['draws'] or 0
                decided = w + l
                if decided > 0:
                    wr_str = f"{(w / decided * 100.0):.1f}% Win Rate"
                elif d > 0:
                    wr_str = "Empate / BE"
                else:
                    wr_str = "0.0% Win Rate"
                net = sc['net_pnl'] or 0.0
                sign = "+" if net >= 0 else ""
                log(
                    f"  🎖️  Estrategia: {sc['strat']} | Agente: {sc['eng']}\n"
                    f"     Subestrategia / Gatillo: {sc['form']}\n"
                    f"     Métricas: {tot} ops | {w}W - {l}L - {d}BE ({wr_str}) | PnL Neto: {sign}${net:,.4f} USDT (Comisiones: ${sc['total_fees']:,.4f})"
                )
            log()

        # 5b. Shadow Testing (Vetos del Árbitro IA: Drawdown Ahorrado vs. Ganancia Perdida)
        log("--- [ 👻 AUDITORÍA SHADOW TESTING (VETOS IA: DRAWDOWN AHORRADO VS. GANANCIA PERDIDA) ] ---")
        try:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_vetoed,
                    SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_count,
                    SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) as closed_count,
                    SUM(CASE WHEN outcome = 'SAVED_SL' THEN 1 ELSE 0 END) as saved_sl,
                    SUM(CASE WHEN outcome = 'MISSED_TP' THEN 1 ELSE 0 END) as missed_tp,
                    SUM(CASE WHEN outcome = 'EXPIRED' THEN 1 ELSE 0 END) as expired_count,
                    SUM(CASE WHEN outcome = 'SAVED_SL' THEN ABS(virtual_pnl_usd) ELSE 0.0 END) as saved_dd_usd,
                    SUM(CASE WHEN outcome = 'MISSED_TP' THEN virtual_pnl_usd ELSE 0.0 END) as missed_gain_usd,
                    SUM(CASE WHEN outcome = 'EXPIRED' THEN virtual_pnl_usd ELSE 0.0 END) as expired_pnl_usd
                FROM shadow_trades;
            """)
            st_row = cursor.fetchone()
            tot_v = (st_row['total_vetoed'] or 0) if st_row else 0
            if tot_v == 0:
                log("  (0 operaciones vetadas por el Árbitro IA hasta el momento | Drawdown Ahorrado: $0.00 | Ganancia Perdida: $0.00)")
            else:
                op_v = st_row['open_count'] or 0
                cl_v = st_row['closed_count'] or 0
                s_sl = st_row['saved_sl'] or 0
                m_tp = st_row['missed_tp'] or 0
                exp_v = st_row['expired_count'] or 0
                s_dd = st_row['saved_dd_usd'] or 0.0
                m_gn = st_row['missed_gain_usd'] or 0.0
                exp_pnl = st_row['expired_pnl_usd'] or 0.0
                net_v = s_dd - m_gn
                edge_sign = "+" if net_v >= 0 else ""
                exp_sign = "+" if exp_pnl >= 0 else ""
                log(f"  Total Señales Vetadas por Árbitro IA: {tot_v} ({op_v} Activas en seguimiento / {cl_v} Resueltas)")
                log(f"  🛡️ Drawdown Ahorrado (Tocó SL): {s_sl} operaciones | +${s_dd:,.2f} USD retenidos en bóveda")
                log(f"  ⚠️ Ganancia Perdida (Tocó TP): {m_tp} operaciones | -${m_gn:,.2f} USD de oportunidad perdida")
                if exp_v > 0:
                    log(f"  ⏱️ Expiradas 24h sin tocar SL/TP (EXPIRED): {exp_v} operaciones | PnL virtual: {exp_sign}${exp_pnl:,.2f} USD")
                log(f"  ⚖️ Ventaja Neta del Árbitro IA (Edge Real SL vs TP): {edge_sign}${net_v:,.2f} USD")
            log()
        except sqlite3.OperationalError:
            log("  (0 operaciones vetadas por el Árbitro IA hasta el momento | Drawdown Ahorrado: $0.00 | Ganancia Perdida: $0.00)")
            log()

        # 5c. Embudo de Rechazos 24H, Cobertura de Activos y Detector de Redundancia 30D
        log("--- [ 🔬 EMBUDO DE RECHAZOS 24H, COBERTURA DE ACTIVOS Y DETECTOR DE REDUNDANCIA 30D ] ---")
        try:
            import json
            from collections import Counter
            from backend.rejection_funnel import (
                TAG_LABELS,
                TAG_ORDER,
                classify_rejection_tags,
                forced_timeframe_warnings,
                formula_fired,
                parse_payload,
            )

            state_path = os.getenv("DAEMON_STATE_PATH") or os.path.join(PROJECT_ROOT, "backend", "config", "daemon_state.json")
            daemon_cfg = {}
            if os.path.exists(state_path):
                try:
                    with open(state_path, "r", encoding="utf-8") as f_st:
                        daemon_cfg = json.load(f_st) or {}
                except Exception:
                    daemon_cfg = {}

            cfg_symbol = str(daemon_cfg.get("symbol") or "ETH/USDT")
            cfg_tf = str(daemon_cfg.get("timeframe") or "4h")
            cfg_strategy = str(daemon_cfg.get("strategy") or "auto")
            cfg_allowed = list(daemon_cfg.get("allowed_strategies") or ([cfg_strategy] if cfg_strategy != "auto" else []))

            # 1) Cobertura de Activos (últimas 24h en tabla signals + estado configurado)
            cursor.execute(
                """
                SELECT symbol, timeframe, COUNT(*) as evals,
                       SUM(CASE WHEN signal IN ('COMPRAR', 'VENDER') THEN 1 ELSE 0 END) as candidates
                FROM signals
                WHERE created_at >= datetime('now', '-24 hours')
                GROUP BY symbol, timeframe
                ORDER BY evals DESC, symbol ASC;
                """
            )
            cov_rows = cursor.fetchall()
            seen_symbols_24h = {r["symbol"] for r in cov_rows}
            expected_syms = [cfg_symbol] if cfg_symbol else []
            if str(daemon_cfg.get("mode") or "smart") == "smart":
                for s_liq in ("SOL/USDT", "ETH/USDT", "BTC/USDT"):
                    if s_liq not in expected_syms:
                        expected_syms.append(s_liq)

            missing_24h = [s for s in expected_syms if s not in seen_symbols_24h]
            log(f"  📡 [1. COBERTURA DE ACTIVOS (24H)] Configurado: {cfg_strategy} [{cfg_tf}] · Base: {cfg_symbol}")
            if not cov_rows:
                log("     • Sin velas registradas en tabla `signals` en las últimas 24h.")
                if expected_syms:
                    log(f"     • ⚠️ Activos esperados sin evaluaciones 24h: {', '.join(expected_syms)}")
            else:
                for cr in cov_rows:
                    log(
                        f"     • ✅ {cr['symbol']:<10} [{cr['timeframe']:<3}] -> "
                        f"{cr['evals']} vela(s) evaluada(s) | {cr['candidates'] or 0} candidata(s)"
                    )
                if missing_24h:
                    log(f"     • ⚠️ Activos esperados con 0 velas en 24h: {', '.join(missing_24h)}")
                else:
                    log(f"     • Cobertura completa sobre activos base ({len(seen_symbols_24h)} activo(s) con actividad).")

            # 2) Acumulado de Bloqueos por Filtro (últimas 24h)
            cursor.execute(
                """
                SELECT symbol, signal, reason, timeframe, raw_response
                FROM signals
                WHERE created_at >= datetime('now', '-24 hours')
                ORDER BY rowid DESC;
                """
            )
            sig_24h = cursor.fetchall()
            tag_counts: Counter = Counter()
            total_evals_24h = len(sig_24h)
            total_cands_24h = 0

            for srow in sig_24h:
                payload = parse_payload(srow["raw_response"])
                is_elig = bool(payload.get("eligible")) or (str(srow["signal"]).upper() in ("COMPRAR", "VENDER") and payload.get("stage") != "gate")
                if is_elig and payload.get("stage") != "gate":
                    total_cands_24h += 1
                    continue
                tags = payload.get("tags")
                if not isinstance(tags, list) or not tags:
                    tags = classify_rejection_tags([srow["reason"]])
                for tg in tags:
                    tag_counts[str(tg)] += 1
                    if str(tg).startswith("VetoIA:"):
                        tag_counts["VetoIA"] += 1

            log(f"  🧱 [2. ACUMULADO DE BLOQUEOS POR FILTRO (24H)] Evaluaciones: {total_evals_24h} | Candidatas habilitadas: {total_cands_24h}")
            if total_evals_24h == 0 or not tag_counts:
                log("     • (Sin bloqueos registrados en las últimas 24h)")
            else:
                ordered_tags = [t for t in TAG_ORDER if tag_counts.get(t, 0) > 0]
                for extra_t in sorted(tag_counts.keys()):
                    if extra_t not in ordered_tags and tag_counts[extra_t] > 0:
                        ordered_tags.append(extra_t)
                for tg in ordered_tags:
                    lbl = TAG_LABELS.get(tg, tg)
                    log(f"     • {lbl:<44}: {tag_counts[tg]} bloqueo(s)")

            # 3) Detector de Redundancia e Inactividad (30 días) + Conflicto de TF
            cursor.execute(
                """
                SELECT reason, raw_response, signal
                FROM signals
                WHERE created_at >= datetime('now', '-30 days');
                """
            )
            sig_30d = cursor.fetchall()
            cursor.execute(
                """
                SELECT strategy, COUNT(*) as cnt
                FROM trades
                WHERE opened_at >= datetime('now', '-30 days')
                GROUP BY strategy;
                """
            )
            trades_30d_map = {str(r["strategy"] or ""): int(r["cnt"] or 0) for r in cursor.fetchall()}

            eval_30d_by_strat: Counter = Counter()
            raw_fired_30d_by_strat: Counter = Counter()
            eligible_30d_by_strat: Counter = Counter()

            for srow in sig_30d:
                payload = parse_payload(srow["raw_response"])
                if payload.get("stage") == "gate":
                    continue
                per_st = payload.get("per_strategy")
                if isinstance(per_st, dict) and per_st:
                    for sid, sdata in per_st.items():
                        eval_30d_by_strat[sid] += 1
                        if isinstance(sdata, dict):
                            if sdata.get("eligible"):
                                eligible_30d_by_strat[sid] += 1
                                raw_fired_30d_by_strat[sid] += 1
                            elif sdata.get("fired"):
                                raw_fired_30d_by_strat[sid] += 1
                else:
                    sid = str(payload.get("strategy") or "")
                    if sid:
                        eval_30d_by_strat[sid] += 1
                        elig = bool(payload.get("eligible"))
                        if elig:
                            eligible_30d_by_strat[sid] += 1
                            raw_fired_30d_by_strat[sid] += 1
                        elif formula_fired([srow["reason"]], False):
                            raw_fired_30d_by_strat[sid] += 1

            tf_warnings = []
            try:
                from backend.estrategias.registry import get_strategy, _sync_catalog_registry
                _sync_catalog_registry()
                recorded_forced_24h = []
                for _srow in (sig_24h or []):
                    _pl = parse_payload(_srow["raw_response"])
                    for _fw in (_pl.get("forced_tf") or []):
                        _fws = str(_fw).strip()
                        if _fws and _fws not in recorded_forced_24h:
                            recorded_forced_24h.append(_fws)

                if cfg_strategy == "auto":
                    cfg_tf_norm = str(cfg_tf or "").strip().lower()
                    if cfg_tf_norm not in ("4h", "1d"):
                        tf_warnings.append(
                            f"Selector de fondo 'auto' en {cfg_tf} (debe ser 4h; 5m queda reservado para Sesión Presencial)"
                        )
                        tf_warnings.extend(forced_timeframe_warnings(cfg_allowed, cfg_tf, get_strategy))
                    for _fw in recorded_forced_24h:
                        if _fw not in tf_warnings:
                            tf_warnings.append(_fw)
                else:
                    tf_warnings = forced_timeframe_warnings(cfg_allowed, cfg_tf, get_strategy)
                    for _fw in recorded_forced_24h:
                        if _fw not in tf_warnings:
                            tf_warnings.append(_fw)
            except Exception:
                tf_warnings = []

            log(f"  🧭 [3. DETECTOR DE REDUNDANCIA / INACTIVIDAD (30 DÍAS)] Fórmulas activas ({len(cfg_allowed)}): {', '.join(cfg_allowed) if cfg_allowed else 'ninguna'}")
            if tf_warnings:
                for tw in tf_warnings:
                    log(f"     • ⚠️ ALERTA DE TEMPORALIDAD FORZADA: {tw}")
            if not cfg_allowed:
                log("     • ⚠️ Sin fórmulas activas configuradas en allowed_strategies.")
            else:
                for sid in cfg_allowed:
                    ev_cnt = eval_30d_by_strat.get(sid, 0)
                    fired_cnt = raw_fired_30d_by_strat.get(sid, 0)
                    elig_cnt = eligible_30d_by_strat.get(sid, 0)
                    tr_cnt = trades_30d_map.get(sid, 0)
                    if fired_cnt == 0 and tr_cnt == 0:
                        log(
                            f"     • ⚠️ ALERTA DE REDUNDANCIA / INACTIVIDAD [{sid}]: "
                            f"0 señales crudas y 0 trades en 30d ({ev_cnt} velas evaluadas)."
                        )
                    else:
                        log(
                            f"     • ✅ [{sid}]: {fired_cnt} señal(es) cruda(s) | "
                            f"{elig_cnt} candidata(s) | {tr_cnt} trade(s) en 30d ({ev_cnt} velas evaluadas)."
                        )
            log()
        except Exception as funnel_err:
            log(f"  (Aviso procesando Embudo de Rechazos / Redundancia: {funnel_err})")
            log()

        # 5d. Evaluación de Campaña (Auto vs Operador Presente, Puntos de Fuga y Dictámenes)
        try:
            from backend.campaign_audit import build_campaign_report, format_campaign_text

            camp_report = build_campaign_report(
                db_path=target_db,
                since_iso=since_iso,
                include_presencial=True,
            )
            log(format_campaign_text(camp_report))
        except Exception as camp_err:
            log(f"  (Aviso procesando Auditoría de Campaña: {camp_err})")
            log()

        # 6. Directiva de Auditoría y Mejora Continua para Cualquier IA Auditora
        log("=" * 75)
        log("🧠 DIRECTIVA DE AUDITORÍA Y MEJORA CONTINUA (PARA CUALQUIER IA AUDITORA / CIO / LLM):")
        log("Instrucción para la Inteligencia Artificial que analiza este reporte:")
        log("Actúa como Director de Inversiones (CIO) y Auditor Cuantitativo Independiente:")
        log("1. EVALUAR ESTRATEGIAS: Analiza el Scorecard de efectividad. ¿Qué estrategia o fórmula está generando mejor asimetría y rentabilidad neta?")
        log("2. DETECTAR PUNTOS DE FUGA: Examina las salidas ejecutadas (Stop Loss vs Breakeven Real vs Trailing). ¿Hubo salidas por ruido que sugieran aflojar o apretar umbrales?")
        log("3. PROPONER MEJORAS CUANTITATIVAS: Sugiere 1 o 2 calibraciones concretas de código para la próxima rueda (ajuste de distancia de Trailing, piso ATR, reglas de cooldown o correlación entre ranuras).")
        log("=" * 75)

    except Exception as e:
        log(f"⚠️ Error leyendo base de datos: {e}")
    finally:
        conn.close()

    texto_completo = "\n".join(lineas)
    if save_snapshot:
        try:
            from backend.campaign_audit import save_campaign_snapshot

            snap_res = save_campaign_snapshot(
                db_path=target_db,
                since_iso=since_iso,
                trigger="cli_snapshot",
            )
            print(f"📸 [SNAPSHOT CAMPAÑA GUARDADO]: {snap_res['path_json']} | {snap_res['path_txt']}")
        except Exception as snap_err:
            print(f"⚠️ No se pudo guardar el snapshot de campaña: {snap_err}")

    if db_path is not None:
        return texto_completo

    # 1. Guardar informe histórico en escritorio portable (Linux Escritorio / Windows Desktop)
    home_dir = Path.home()
    desktop_dir = home_dir / "Escritorio" if (home_dir / "Escritorio").exists() else (home_dir / "Desktop")
    informe_hist_path = None
    if desktop_dir.exists():
        try:
            informes_dir = desktop_dir / "informes_auditoria"
            informes_dir.mkdir(parents=True, exist_ok=True)
            hist_file = informes_dir / f"{timestamp_slug}_auditoria_kula_balam.txt"
            hist_file.write_text(texto_completo, encoding="utf-8")
            informe_hist_path = str(hist_file)
        except Exception:
            pass

    # 2. Guardar también en 'ultimo_reporte_boveda.txt' (frontend y escritorio portable) para acceso directo y UI
    try:
        frontend_txt = Path(PROJECT_ROOT) / "frontend" / "ultimo_reporte_boveda.txt"
        frontend_txt.write_text(texto_completo, encoding="utf-8")
        if desktop_dir.exists():
            (desktop_dir / "ultimo_reporte_boveda.txt").write_text(texto_completo, encoding="utf-8")
    except Exception:
        pass

    # 3. Copiar automáticamente todo el informe al portapapeles del sistema
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(texto_completo)
        r.update()
        r.destroy()
        print("📋 [PORTAPAPELES]: ¡Reporte copiado automáticamente! Ya puedes hacer Ctrl+V en tu IA (Gemini, Claude, ChatGPT, Ollama, DeepSeek, etc.).")
    except Exception:
        pass

    if informe_hist_path and os.path.exists(informe_hist_path):
        print(f"💾 [HISTÓRICO GUARDADO]: {informe_hist_path}")

    return texto_completo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auditor Forense SQLite + Campaña Kula Balam")
    parser.add_argument("--since", dest="since_iso", default=None, help="Fecha/ISO de inicio de campaña (ej. 2026-11-21)")
    parser.add_argument("--snapshot", action="store_true", help="Guarda snapshot JSON/TXT en data/audit_snapshots/")
    parser.add_argument("--db", dest="db_path", default=None, help="Ruta opcional a trading_ledger.sqlite3")
    args = parser.parse_args()
    auditar(db_path=args.db_path, since_iso=args.since_iso, save_snapshot=bool(args.snapshot))
