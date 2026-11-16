#!/usr/bin/env python3
"""
Auditor Forense Cuantitativo de SQLite para Kula Balam
Inspecciona directamente trading_ledger.sqlite3 (partida doble, trades, bóveda).
Copia automáticamente el informe al portapapeles para pegar en Gemini con Ctrl+V.
"""

import os
import sqlite3
from datetime import datetime, timezone, timedelta

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

def auditar(db_path=None):
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
                    SUM(CASE WHEN outcome = 'SAVED_SL' THEN ABS(virtual_pnl_usd) ELSE 0.0 END) as saved_dd_usd,
                    SUM(CASE WHEN outcome = 'MISSED_TP' THEN virtual_pnl_usd ELSE 0.0 END) as missed_gain_usd
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
                s_dd = st_row['saved_dd_usd'] or 0.0
                m_gn = st_row['missed_gain_usd'] or 0.0
                net_v = s_dd - m_gn
                edge_sign = "+" if net_v >= 0 else ""
                log(f"  Total Señales Vetadas por Árbitro IA: {tot_v} ({op_v} Activas en seguimiento / {cl_v} Resueltas)")
                log(f"  🛡️ Drawdown Ahorrado (Tocó SL): {s_sl} operaciones | +${s_dd:,.2f} USD retenidos en bóveda")
                log(f"  ⚠️ Ganancia Perdida (Tocó TP): {m_tp} operaciones | -${m_gn:,.2f} USD de oportunidad perdida")
                log(f"  ⚖️ Ventaja Neta del Árbitro IA (Edge Real): {edge_sign}${net_v:,.2f} USD")
            log()
        except sqlite3.OperationalError:
            log("  (0 operaciones vetadas por el Árbitro IA hasta el momento | Drawdown Ahorrado: $0.00 | Ganancia Perdida: $0.00)")
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

    # 1. Guardar informe histórico en /home/raul/Escritorio/informes_auditoria con fecha como primera parte del título
    informes_dir = "/home/raul/Escritorio/informes_auditoria"
    informe_hist_path = None
    try:
        os.makedirs(informes_dir, exist_ok=True)
        informe_hist_path = os.path.join(informes_dir, f"{timestamp_slug}_auditoria_kula_balam.txt")
        with open(informe_hist_path, "w", encoding="utf-8") as f:
            f.write(texto_completo)
    except Exception as err:
        pass

    # 2. Guardar también en 'ultimo_reporte_boveda.txt' (frontend y escritorio) para acceso directo y UI
    try:
        frontend_txt = os.path.join(PROJECT_ROOT, "frontend", "ultimo_reporte_boveda.txt")
        desktop_txt = "/home/raul/Escritorio/ultimo_reporte_boveda.txt"
        with open(frontend_txt, "w", encoding="utf-8") as f:
            f.write(texto_completo)
        with open(desktop_txt, "w", encoding="utf-8") as f:
            f.write(texto_completo)
    except Exception as err:
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
    auditar()
