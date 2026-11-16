"""
Verificador Evolutivo Determinista y Memoria de Supervivencia (RLVR) en SQLite.

Implementa selección natural algorítmica sobre decisiones de la IA:
- Evalúa de forma 100% determinista el futuro de una señal sobre N velas posteriores.
- Conserva únicamente las decisiones que sobreviven matemáticamente:
  1. 'TP_GANADOR': Señal COMPRAR que alcanza el Take Profit sin tocar antes el Stop Loss
     (asumiendo siempre el peor caso si ambos ocurren en la misma vela) y cuyo retorno neto
     supera el umbral mínimo tras comisiones y spread.
  2. 'VETO_SALVADOR': Señal MANTENER (cuando una estrategia sugería candidata de compra)
     donde el precio posterior efectivamente se desploma tocando el Stop Loss, evitando una pérdida.
"""

from datetime import datetime, timezone
import math
import os
import sqlite3
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RLVR_DB_PATH = os.path.join(PROJECT_ROOT, "backend", "data", "memoria_rlvr.db")


def _resolve_db_path(db_path: Optional[str] = None) -> str:
    return db_path or os.getenv("RLVR_MEMORIA_DB_PATH") or DEFAULT_RLVR_DB_PATH


def inicializar_memoria_db(db_path: Optional[str] = None) -> str:
    """
    Crea la tabla SQLite `memoria_supervivencia` si no existe.
    Devuelve la ruta absoluta del archivo SQLite inicializado.
    """
    target_path = _resolve_db_path(db_path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with sqlite3.connect(target_path, timeout=10.0) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memoria_supervivencia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                rsi REAL NOT NULL,
                vwap_diff_pct REAL NOT NULL,
                ema_slope_pct REAL NOT NULL,
                lower_wick_ratio REAL NOT NULL,
                signal TEXT NOT NULL,
                reason TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK(outcome IN ('TP_GANADOR', 'VETO_SALVADOR')),
                pnl_neto REAL NOT NULL,
                fecha TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memoria_strategy
            ON memoria_supervivencia (strategy_name, outcome)
            """
        )
        conn.commit()
    return target_path


def verificar_resultado_real(
    df_velas_futuras: Any,
    precio_entrada: float,
    signal_ia: str,
    tp_bruto_pct: float,
    sl_bruto_pct: float,
    costo_ida_vuelta_pct: float,
    min_profit_neto_pct: float,
) -> Dict[str, Any]:
    """
    Función 100% determinista que evalúa las siguientes N velas después de una decisión.
    - Si en una misma vela el precio toca el Stop Loss (low <= sl_price) y el Take Profit (high >= tp_price),
      asume SIEMPRE el peor caso (tocó primero el Stop Loss).
    - Si signal_ia == 'COMPRAR' y toca TP con PnL neto >= min_profit_neto_pct -> sobrevivio=True, outcome='TP_GANADOR'.
    - Si signal_ia == 'MANTENER' y el precio se desploma tocando el SL -> sobrevivio=True, outcome='VETO_SALVADOR'.
    - En cualquier otro caso -> sobrevivio=False.
    """
    if precio_entrada <= 0 or df_velas_futuras is None:
        return {"sobrevivio": False, "outcome": None, "pnl_neto": 0.0}

    sig = str(signal_ia or "").strip().upper()
    tp_price = precio_entrada * (1.0 + abs(float(tp_bruto_pct)) / 100.0)
    sl_price = precio_entrada * (1.0 - abs(float(sl_bruto_pct)) / 100.0)
    net_tp_pct = round(abs(float(tp_bruto_pct)) - float(costo_ida_vuelta_pct), 4)
    net_sl_pct = round(-abs(float(sl_bruto_pct)) - float(costo_ida_vuelta_pct), 4)

    # Soportar tanto pandas DataFrame como lista de dicts/tuplas
    if hasattr(df_velas_futuras, "iterrows"):
        rows = [row for _, row in df_velas_futuras.iterrows()]
    elif isinstance(df_velas_futuras, list):
        rows = df_velas_futuras
    else:
        return {"sobrevivio": False, "outcome": None, "pnl_neto": 0.0}

    if not rows:
        return {"sobrevivio": False, "outcome": None, "pnl_neto": 0.0}

    hit_tp = False
    hit_sl = False

    for candle in rows:
        high_val = float(candle["high"]) if isinstance(candle, dict) or hasattr(candle, "__getitem__") else float(candle[2])
        low_val = float(candle["low"]) if isinstance(candle, dict) or hasattr(candle, "__getitem__") else float(candle[3])

        # Peor caso primero: verificar siempre Stop Loss antes que Take Profit en la misma vela
        if low_val <= sl_price:
            hit_sl = True
            break
        if high_val >= tp_price:
            hit_tp = True
            break

    if sig == "COMPRAR":
        if hit_tp and not hit_sl and net_tp_pct >= float(min_profit_neto_pct):
            return {
                "sobrevivio": True,
                "outcome": "TP_GANADOR",
                "pnl_neto": net_tp_pct,
            }
        return {
            "sobrevivio": False,
            "outcome": None,
            "pnl_neto": net_sl_pct if hit_sl else 0.0,
        }

    if sig == "MANTENER":
        if hit_sl:
            # El veto salvó al capital de una pérdida real de net_sl_pct
            return {
                "sobrevivio": True,
                "outcome": "VETO_SALVADOR",
                "pnl_neto": abs(net_sl_pct),
            }
        return {
            "sobrevivio": False,
            "outcome": None,
            "pnl_neto": 0.0,
        }

    return {"sobrevivio": False, "outcome": None, "pnl_neto": 0.0}


def limpiar_memoria_antigua(
    max_registros: int = 500,
    max_dias: int = 30,
    purgar_todo: bool = False,
    db_path: Optional[str] = None,
) -> int:
    """
    Protocolo de higiene y rotación automática de la Memoria Evolutiva:
    - Si `purgar_todo=True`, vacía toda la tabla y compacta el archivo (`VACUUM`).
    - Si no, elimina registros con antigüedad mayor a `max_dias` y mantiene como máximo
      los últimos `max_registros` (ventana móvil de régimen actual), evitando que la base
      crezca indefinidamente o conserve regímenes de mercado obsoletos.
    Devuelve la cantidad de filas eliminadas.
    """
    target_path = _resolve_db_path(db_path)
    if not os.path.exists(target_path):
        return 0
    with sqlite3.connect(target_path, timeout=10.0) as conn:
        if purgar_todo:
            cur = conn.execute("DELETE FROM memoria_supervivencia")
            deleted = int(cur.rowcount or 0)
            conn.commit()
            conn.execute("VACUUM")
            return deleted

        cur_old = conn.execute(
            """
            DELETE FROM memoria_supervivencia
            WHERE datetime(fecha) < datetime('now', ?)
            """,
            (f"-{int(max_dias)} days",),
        )
        deleted_old = int(cur_old.rowcount or 0)

        cur_cap = conn.execute(
            """
            DELETE FROM memoria_supervivencia
            WHERE id NOT IN (
                SELECT id FROM memoria_supervivencia
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (int(max_registros),),
        )
        deleted_cap = int(cur_cap.rowcount or 0)
        conn.commit()
        return deleted_old + deleted_cap


def guardar_precedente_verificado(
    symbol: str,
    strategy_name: str,
    rsi: float,
    vwap_diff_pct: float,
    ema_slope_pct: float,
    lower_wick_ratio: float,
    signal: str,
    reason: str,
    outcome: str,
    pnl_neto: float,
    fecha: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Guarda un caso verificado que sobrevivió al filtro evolutivo en SQLite y aplica rotación automática."""
    target_path = inicializar_memoria_db(db_path)
    ts_str = fecha or datetime.now(timezone.utc).isoformat()
    sym_clean = str(symbol).strip().upper()
    strat_clean = str(strategy_name).strip()
    rsi_r = round(float(rsi or 0.0), 4)
    vwap_r = round(float(vwap_diff_pct or 0.0), 4)
    ema_r = round(float(ema_slope_pct or 0.0), 6)
    wick_r = round(float(lower_wick_ratio or 0.0), 4)
    sig_clean = str(signal).strip().upper()
    out_clean = str(outcome).strip().upper()

    with sqlite3.connect(target_path, timeout=10.0) as conn:
        existing = conn.execute(
            """
            SELECT id FROM memoria_supervivencia
            WHERE symbol = ? AND strategy_name = ? AND rsi = ? AND vwap_diff_pct = ? AND outcome = ?
            LIMIT 1
            """,
            (sym_clean, strat_clean, rsi_r, vwap_r, out_clean),
        ).fetchone()
        if existing:
            return int(existing[0])

        cur = conn.execute(
            """
            INSERT INTO memoria_supervivencia (
                symbol, strategy_name, rsi, vwap_diff_pct, ema_slope_pct,
                lower_wick_ratio, signal, reason, outcome, pnl_neto, fecha
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sym_clean,
                strat_clean,
                rsi_r,
                vwap_r,
                ema_r,
                wick_r,
                sig_clean,
                str(reason).strip()[:300],
                out_clean,
                round(float(pnl_neto or 0.0), 4),
                ts_str,
            ),
        )
        conn.commit()
        row_id = int(cur.lastrowid or 0)

    try:
        limpiar_memoria_antigua(max_registros=500, max_dias=30, db_path=target_path)
    except Exception:
        pass
    return row_id


def obtener_precedentes_ganadores(
    strategy_name: str,
    rsi_actual: float,
    vwap_diff_actual: float,
    ema_slope_actual: float,
    wick_actual: float,
    limite: int = 3,
    db_path: Optional[str] = None,
) -> str:
    """
    Busca en `memoria_supervivencia` los `limite` casos pasados verificados cuyos indicadores
    técnicos sean matemáticamente más cercanos al momento actual (distancia euclidiana normalizada).
    Devuelve un bloque de texto formateado para inyectar en el prompt, o '' si no hay datos.
    """
    try:
        target_path = _resolve_db_path(db_path)
        if not os.path.exists(target_path):
            return ""

        with sqlite3.connect(target_path, timeout=5.0) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT symbol, strategy_name, rsi, vwap_diff_pct, ema_slope_pct,
                       lower_wick_ratio, signal, reason, outcome, pnl_neto
                FROM memoria_supervivencia
                WHERE strategy_name = ?
                ORDER BY id DESC
                LIMIT 500
                """,
                (str(strategy_name or "manual"),),
            ).fetchall()

            if not rows:
                rows = conn.execute(
                    """
                    SELECT symbol, strategy_name, rsi, vwap_diff_pct, ema_slope_pct,
                           lower_wick_ratio, signal, reason, outcome, pnl_neto
                    FROM memoria_supervivencia
                    ORDER BY id DESC
                    LIMIT 500
                    """
                ).fetchall()

        if not rows:
            return ""

        r_now = float(rsi_actual if rsi_actual is not None else 50.0)
        v_now = float(vwap_diff_actual if vwap_diff_actual is not None else 0.0)
        e_now = float(ema_slope_actual if ema_slope_actual is not None else 0.0)
        w_now = float(wick_actual if wick_actual is not None else 0.0)

        scored: List[ tuple[float, sqlite3.Row] ] = []
        for r in rows:
            # Normalización de escalas para que RSI (0-100) no eclipse a VWAP diff (%), EMA slope (%) y Wick (0-1)
            d_rsi = (float(r["rsi"]) - r_now) / 25.0
            d_vwap = (float(r["vwap_diff_pct"]) - v_now) / 1.0
            d_ema = (float(r["ema_slope_pct"]) - e_now) / 0.25
            d_wick = (float(r["lower_wick_ratio"]) - w_now) / 0.35
            dist = math.sqrt(d_rsi * d_rsi + d_vwap * d_vwap + d_ema * d_ema + d_wick * d_wick)
            scored.append((dist, r))

        # 1. Filtro estricto de cercanía matemática: si el mercado actual no se parece, NO inyectar ruido
        MAX_DIST_THRESHOLD = 0.65
        valid_scored = [item for item in scored if item[0] <= MAX_DIST_THRESHOLD]
        if not valid_scored:
            return ""

        # 2. Selección simétrica balanceada para evitar sesgo de confirmación en modelos pequeños (3B)
        tp_candidates = [item for item in valid_scored if item[1]["outcome"] == "TP_GANADOR"]
        veto_candidates = [item for item in valid_scored if item[1]["outcome"] == "VETO_SALVADOR"]

        tp_candidates.sort(key=lambda x: x[0])
        veto_candidates.sort(key=lambda x: x[0])

        top_matches: List[sqlite3.Row] = []
        if tp_candidates and veto_candidates:
            # Si existen ambas clases, balancear (máx 2 de una y al menos 1 de la otra)
            top_matches.append(tp_candidates[0][1])
            top_matches.append(veto_candidates[0][1])
            if len(tp_candidates) > 1 and len(top_matches) < limite:
                top_matches.append(tp_candidates[1][1])
            elif len(veto_candidates) > 1 and len(top_matches) < limite:
                top_matches.append(veto_candidates[1][1])
        else:
            valid_scored.sort(key=lambda item: item[0])
            top_matches = [item[1] for item in valid_scored[: max(1, int(limite))]]

        if not top_matches:
            return ""

        lines = [
            "EXPERIENCIA PREVIA VERIFICADA (Casos históricos matemáticamente afines que sobrevivieron al filtro — contrasta siempre aciertos y vetos, no copies a ciegas):"
        ]
        for idx, m in enumerate(top_matches, start=1):
            accion_desc = (
                f"Acierto al COMPRAR (+{float(m['pnl_neto']):.2f}% neto)"
                if m["outcome"] == "TP_GANADOR"
                else f"Acierto al MANTENER/VETAR (evitó caída de -{abs(float(m['pnl_neto'])):.2f}%)"
            )
            lines.append(
                f"  {idx}. [{m['outcome']} | {m['symbol']} | {m['strategy_name']}] "
                f"RSI={float(m['rsi']):.1f}, Precio vs VWAP={float(m['vwap_diff_pct']):+.2f}%, "
                f"Pendiente EMA200={float(m['ema_slope_pct']):+.4f}%, Mecha={float(m['lower_wick_ratio']):.2f} "
                f"-> Decisión: {m['signal']} ({accion_desc}). Motivo: {m['reason']}"
            )
        return "\n".join(lines)
    except Exception:
        return ""

