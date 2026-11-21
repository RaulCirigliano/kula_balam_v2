# -*- coding: utf-8 -*-
"""
Pruebas Unitarias y de Integración para el Sistema de Evaluación de Campaña (2–4 semanas).
Cubre:
  1. Conteo correcto de señales 'VENDER' (regresión del bug 'SHORT') en campaign_audit y auditar_sqlite.
  2. Métricas financieras exactas (PF, R:R realizado, Esperanza USD, Max Drawdown, exit_reasons).
  3. Desglose de shadow_trades por estrategia y arbiter_reason.
  4. Dictámenes automáticos CONSERVAR / CALIBRAR / PODAR / MUESTRA_INSUFICIENTE.
  5. Separación estricta entre bloque `auto` y bloque `operador_presente` (incl. fractal_squeeze_15m).
  6. Snapshots JSON/TXT portables, regla semanal >= 7d, endpoints FastAPI y helpers --stable de lanzar_todo.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from auditar_sqlite import auditar
from backend import main
from backend.campaign_audit import (
    build_campaign_report,
    list_campaign_snapshots,
    maybe_write_weekly_snapshot,
    save_campaign_snapshot,
)
from backend.db.ledger import LedgerStore


def _setup_isolated_env(tmp_path: Path, monkeypatch):
    db_file = str(tmp_path / "campaign_test.sqlite3")
    LedgerStore(db_path=db_file, initial_vault={"USDT": 500.0})
    state_file = tmp_path / "daemon_state.json"
    state_file.write_text(
        json.dumps(
            {
                "symbol": "ETH/USDT",
                "timeframe": "4h",
                "strategy": "auto",
                "allowed_strategies": [
                    "ttm_squeeze_eth_1h",
                    "ttm_squeeze_sol_4h",
                    "1_donchian_breakout_sol_4h",
                    "kula_balam_cava_ruiz",
                ],
            }
        ),
        encoding="utf-8",
    )
    cfg_file = tmp_path / "campaign_config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "campaign_name": "Campaña Test",
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
        ),
        encoding="utf-8",
    )
    snap_dir = tmp_path / "audit_snapshots"
    monkeypatch.setenv("TRADING_LEDGER_DB_PATH", db_file)
    monkeypatch.setenv("DAEMON_STATE_PATH", str(state_file))
    monkeypatch.setenv("CAMPAIGN_CONFIG_PATH", str(cfg_file))
    monkeypatch.setenv("CAMPAIGN_SNAPSHOTS_DIR", str(snap_dir))
    return db_file, state_file, cfg_file, snap_dir


def test_vender_signals_counted_and_blocks_separated(tmp_path, monkeypatch):
    db_file, _, _, _ = _setup_isolated_env(tmp_path, monkeypatch)
    conn = sqlite3.connect(db_file)
    try:
        # 1 señal bajista VENDER de fractal_squeeze_15m (en operador_presente) y 1 COMPRAR de ttm_squeeze_sol_4h (en auto)
        raw_pres = json.dumps(
            {
                "v": 1,
                "stage": "analysis",
                "strategy": "fractal_squeeze_15m",
                "eligible": True,
                "side": "SHORT",
                "tags": [],
                "per_strategy": {
                    "fractal_squeeze_15m": {"eligible": True, "fired": True, "tags": []}
                },
            }
        )
        raw_auto = json.dumps(
            {
                "v": 1,
                "stage": "analysis",
                "strategy": "ttm_squeeze_sol_4h",
                "eligible": True,
                "side": "LONG",
                "tags": [],
                "per_strategy": {
                    "ttm_squeeze_eth_1h": {"eligible": False, "fired": False, "tags": ["SinConfluencia"]},
                    "ttm_squeeze_sol_4h": {"eligible": True, "fired": True, "tags": []},
                },
            }
        )
        now_sql = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO signals (id, symbol, engine, signal, reason, price, timeframe, signal_candle_ts, data_age_s, raw_response, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("s-vender", "ETH/USDT", "antigravity_operador", "VENDER", "Short ok", 1600.0, "15m", 1795200000, 3, raw_pres, now_sql),
        )
        conn.execute(
            "INSERT INTO signals (id, symbol, engine, signal, reason, price, timeframe, signal_candle_ts, data_age_s, raw_response, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("s-comprar", "SOL/USDT", "antigravity_operador", "COMPRAR", "Long ok", 70.0, "4h", 1795200000, 3, raw_auto, now_sql),
        )
        # Señal antigua previa a since_iso que NO debe entrar en la campaña
        conn.execute(
            "INSERT INTO signals (id, symbol, engine, signal, reason, price, timeframe, signal_candle_ts, data_age_s, raw_response, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("s-old", "ETH/USDT", "antigravity_operador", "VENDER", "Old", 2000.0, "15m", 1790000000, 3, raw_pres, "2026-11-10 10:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    report = build_campaign_report(
        db_path=db_file,
        since_iso="2026-11-21T00:00:00Z",
        now_utc=datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc),
    )
    cov_map = {(c["symbol"], c["timeframe"]): c for c in report["signal_coverage"]}
    assert cov_map[("ETH/USDT", "15m")]["candidates"] == 1
    assert cov_map[("SOL/USDT", "4h")]["candidates"] == 1

    auto_by_id = {x["strategy_id"]: x for x in report["auto_strategies"]}
    pres_by_id = {x["strategy_id"]: x for x in report["presencial_strategies"]}
    assert "ttm_squeeze_sol_4h" in auto_by_id and auto_by_id["ttm_squeeze_sol_4h"]["eligible"] == 1
    assert "fractal_squeeze_15m" in pres_by_id and pres_by_id["fractal_squeeze_15m"]["eligible"] == 1
    assert "fractal_squeeze_15m" not in auto_by_id

    txt = auditar(db_path=db_file, since_iso="2026-11-21")
    assert "ETH/USDT   [15m] -> 1 vela(s) evaluada(s) | 1 candidata(s)" in txt
    assert "EVALUACIÓN DE CAMPAÑA (AUTO vs OPERADOR PRESENTE)" in txt


def test_metrics_exit_reasons_shadow_and_all_verdicts(tmp_path, monkeypatch):
    db_file, _, _, _ = _setup_isolated_env(tmp_path, monkeypatch)
    conn = sqlite3.connect(db_file)
    try:
        # 1) ttm_squeeze_sol_4h -> CONSERVAR: 8 trades cerrados (+5, +5, -2, +4, -2, +6, -2, +6) => GP=26, GL=6, PF=4.3333, MaxDD=2.0, R:R=(6.5/2.0)=3.25
        pnls_conservar = [
            (5.0, "TP_ALCANZADO"),
            (5.0, "Take Profit"),
            (-2.0, "STOP_LOSS"),
            (4.0, "TRAILING_STOP"),
            (-2.0, "SL"),
            (6.0, "TP"),
            (-2.0, "SL"),
            (6.0, "Breakeven BE"),
        ]
        for idx, (pnl, exr) in enumerate(pnls_conservar):
            ts = f"2026-11-2{1 + idx // 4} 1{idx}:00:00"
            conn.execute(
                """
                INSERT INTO trades (
                    id, symbol, currency, side, status, qty, entry_price, exit_price, cost_basis,
                    realized_pnl, total_fees, initial_tp_pct, initial_sl_pct, current_stop_net_pct,
                    peak_price, exit_reason, time_decay_hours, counterfactual_diff, strategy, opened_at, closed_at
                ) VALUES (?, ?, 'USDT', 'SHORT', 'CLOSED', 1.0, 100.0, 95.0, 100.0, ?, 0.2, 5.0, 2.0, -2.0, 94.0, ?, 4.0, 0.5, 'ttm_squeeze_sol_4h', ?, ?)
                """,
                (f"t-sol-{idx}", "SOL/USDT", pnl, exr, ts, ts),
            )

        # 2) ttm_squeeze_eth_1h -> CALIBRAR (8 trades cerrados con PF entre 0.80 y 1.20: GP=9.0, GL=9.0 -> PF=1.0)
        for idx, pnl in enumerate([3.0, -3.0, 3.0, -3.0, 1.5, -1.5, 1.5, -1.5]):
            ts = f"2026-11-22 1{idx}:00:00"
            conn.execute(
                """
                INSERT INTO trades (
                    id, symbol, currency, side, status, qty, entry_price, exit_price, cost_basis,
                    realized_pnl, total_fees, initial_tp_pct, initial_sl_pct, current_stop_net_pct,
                    peak_price, exit_reason, strategy, opened_at, closed_at
                ) VALUES (?, 'ETH/USDT', 'USDT', 'SHORT', 'CLOSED', 1.0, 1600.0, 1580.0, 1600.0, ?, 0.1, 4.0, 2.0, -2.0, 1580.0, 'Manual Time Exit', 'ttm_squeeze_eth_1h', ?, ?)
                """,
                (f"t-eth-{idx}", pnl, ts, ts),
            )

        # 3) 1_donchian_breakout_sol_4h -> PODAR por PF < 0.80 con >= 8 trades cerrados (GP=2, GL=10 -> PF=0.20)
        for idx, pnl in enumerate([2.0, -2.0, -2.0, -2.0, -1.0, -1.0, -1.0, -1.0]):
            ts = f"2026-11-23 1{idx}:00:00"
            conn.execute(
                """
                INSERT INTO trades (
                    id, symbol, currency, side, status, qty, entry_price, exit_price, cost_basis,
                    realized_pnl, total_fees, initial_tp_pct, initial_sl_pct, current_stop_net_pct,
                    peak_price, exit_reason, strategy, opened_at, closed_at
                ) VALUES (?, 'SOL/USDT', 'USDT', 'LONG', 'CLOSED', 1.0, 70.0, 68.0, 70.0, ?, 0.1, 4.0, 2.0, -2.0, 71.0, 'SL', '1_donchian_breakout_sol_4h', ?, ?)
                """,
                (f"t-don-{idx}", pnl, ts, ts),
            )

        # 4) kula_balam_cava_ruiz -> 105 evaluaciones sin candidatas ni trades (con now >= 29d -> PODAR)
        raw_idle = json.dumps(
            {
                "v": 1,
                "stage": "analysis",
                "strategy": "kula_balam_cava_ruiz",
                "eligible": False,
                "tags": ["Fibo"],
                "per_strategy": {"kula_balam_cava_ruiz": {"eligible": False, "fired": False, "tags": ["Fibo"]}},
            }
        )
        for idx in range(105):
            conn.execute(
                "INSERT INTO signals (id, symbol, engine, signal, reason, price, timeframe, signal_candle_ts, data_age_s, raw_response, created_at) VALUES (?, 'ETH/USDT', 'antigravity_operador', 'MANTENER', 'Fibo', 1600.0, '4h', ?, 2, ?, '2026-11-25 12:00:00')",
                (f"idle-{idx}", 1795200000 + idx, raw_idle),
            )

        # 5) Shadow trades sobre fractal_squeeze_15m (>= 8 resueltos con Edge IA negativo -> CALIBRAR)
        for idx in range(8):
            conn.execute(
                """
                INSERT INTO shadow_trades (
                    id, symbol, side, status, qty, entry_price, exit_price, sl_price, tp_price,
                    initial_sl_pct, initial_tp_pct, virtual_pnl_usd, virtual_pnl_pct, outcome,
                    strategy, arbiter_reason, opened_at, closed_at
                ) VALUES (?, 'ETH/USDT', 'SHORT', 'CLOSED', 1.0, 1650.0, 1600.0, 1670.0, 1590.0, 1.2, 3.6, 3.0, 3.0, 'MISSED_TP', 'fractal_squeeze_15m', 'VETO IA Mecha Trampa', '2026-11-24 10:00:00', '2026-11-24 12:00:00')
                """,
                (f"sh-fs-{idx}",),
            )
        # Otro shadow en ttm_squeeze_sol_4h SAVED_SL
        conn.execute(
            """
            INSERT INTO shadow_trades (
                id, symbol, side, status, qty, entry_price, exit_price, sl_price, tp_price,
                initial_sl_pct, initial_tp_pct, virtual_pnl_usd, virtual_pnl_pct, outcome,
                strategy, arbiter_reason, opened_at, closed_at
            ) VALUES ('sh-sol-1', 'SOL/USDT', 'LONG', 'CLOSED', 1.0, 70.0, 68.0, 68.0, 75.0, 2.8, 7.1, -4.5, -2.8, 'SAVED_SL', 'ttm_squeeze_sol_4h', 'VETO Sobreextensión EMA50', '2026-11-24 10:00:00', '2026-11-24 12:00:00')
            """
        )
        conn.commit()
    finally:
        conn.close()

    # Con < 28d primero verificar MUESTRA_INSUFICIENTE para kula_balam_cava_ruiz
    rep_early = build_campaign_report(
        db_path=db_file,
        now_utc=datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc),
    )
    early_auto = {x["strategy_id"]: x for x in rep_early["auto_strategies"]}
    assert early_auto["kula_balam_cava_ruiz"]["verdict"] == "MUESTRA_INSUFICIENTE"

    # A 29 días (2026-12-20): verificar todos los cálculos y los 4 dictámenes
    rep = build_campaign_report(
        db_path=db_file,
        now_utc=datetime(2026, 12, 20, 0, 0, tzinfo=timezone.utc),
    )
    auto_map = {x["strategy_id"]: x for x in rep["auto_strategies"]}
    pres_map = {x["strategy_id"]: x for x in rep["presencial_strategies"]}

    sol = auto_map["ttm_squeeze_sol_4h"]
    assert sol["trades_closed"] == 8
    assert sol["wins"] == 5 and sol["losses"] == 3
    assert sol["gross_profit_usd"] == pytest.approx(26.0)
    assert sol["gross_loss_usd"] == pytest.approx(6.0)
    assert sol["net_pnl_usd"] == pytest.approx(20.0)
    assert sol["profit_factor"] == pytest.approx(26.0 / 6.0, rel=1e-3)
    assert sol["avg_win_usd"] == pytest.approx(5.2)
    assert sol["avg_loss_usd"] == pytest.approx(2.0)
    assert sol["realized_rr"] == pytest.approx(2.6)
    assert sol["expectancy_usd"] == pytest.approx(2.5)
    assert sol["max_drawdown_usd"] == pytest.approx(2.0)
    assert sol["exit_reasons"]["TP"]["count"] == 3
    assert sol["exit_reasons"]["SL"]["count"] == 3
    assert sol["exit_reasons"]["TRAILING"]["count"] == 1
    assert sol["exit_reasons"]["BREAKEVEN"]["count"] == 1
    assert sol["net_arbiter_edge_usd"] == pytest.approx(4.5)
    assert sol["verdict"] == "CONSERVAR"

    assert auto_map["ttm_squeeze_eth_1h"]["verdict"] == "CALIBRAR"
    assert auto_map["1_donchian_breakout_sol_4h"]["verdict"] == "PODAR"
    assert auto_map["kula_balam_cava_ruiz"]["verdict"] == "PODAR"
    assert pres_map["fractal_squeeze_15m"]["verdict"] == "CALIBRAR"
    assert pres_map["fractal_squeeze_15m"]["net_arbiter_edge_usd"] == pytest.approx(-24.0)
    assert pres_map["mtf_presencial_5m"]["verdict"] == "MUESTRA_INSUFICIENTE"


def test_snapshots_weekly_cadence_and_fastapi_endpoints(tmp_path, monkeypatch):
    db_file, _, _, snap_dir = _setup_isolated_env(tmp_path, monkeypatch)

    t0 = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    s1 = maybe_write_weekly_snapshot(db_path=db_file, snapshots_dir=str(snap_dir), now_utc=t0)
    assert s1 is not None and Path(s1["path_json"]).exists() and Path(s1["path_txt"]).exists()

    # Dentro de < 7 días no debe generar otro snapshot automático
    s2 = maybe_write_weekly_snapshot(
        db_path=db_file,
        snapshots_dir=str(snap_dir),
        now_utc=t0 + timedelta(days=3),
    )
    assert s2 is None

    # A >= 7 días debe emitir nuevo snapshot semanal
    s3 = maybe_write_weekly_snapshot(
        db_path=db_file,
        snapshots_dir=str(snap_dir),
        now_utc=t0 + timedelta(days=7, minutes=5),
    )
    assert s3 is not None

    snaps = list_campaign_snapshots(str(snap_dir))
    assert len(snaps) == 2

    # Endpoints FastAPI
    client = TestClient(main.app)
    r_get = client.get("/api/audit/campaign?since=2026-11-21")
    assert r_get.status_code == 200
    d_get = r_get.json()
    assert d_get["status"] == "ok"
    assert len(d_get["report"]["auto_strategies"]) == 4
    assert any(x["strategy_id"] == "fractal_squeeze_15m" for x in d_get["report"]["presencial_strategies"])

    r_post = client.post("/api/audit/campaign/snapshot?since=2026-11-21")
    assert r_post.status_code == 200
    assert r_post.json()["snapshot"]["trigger"] == "ui_manual"

    r_list = client.get("/api/audit/campaign/snapshots")
    assert r_list.status_code == 200
    assert len(r_list.json()["snapshots"]) == 3


def test_lanzar_todo_stable_mode_helpers(tmp_path):
    from lanzar_todo import build_uvicorn_command, is_stable_mode, should_start_ollama

    assert is_stable_mode(argv=[], env={}) is False
    assert is_stable_mode(argv=["--stable"], env={}) is True
    assert is_stable_mode(argv=[], env={"KULA_STABLE_MODE": "1"}) is True

    root = tmp_path / "proj"
    cfg_dir = root / "backend" / "config"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "daemon_state.json").write_text(json.dumps({"engine": "antigravity_operador"}), encoding="utf-8")

    assert should_start_ollama(root, stable_mode=False) is True
    assert should_start_ollama(root, stable_mode=True) is False

    (cfg_dir / "daemon_state.json").write_text(json.dumps({"engine": "ollama"}), encoding="utf-8")
    assert should_start_ollama(root, stable_mode=True) is True

    py_exe = Path("/usr/bin/python3")
    cmd_dev = build_uvicorn_command(py_exe, "backend.main:app", 18767, stable_mode=False, reload_dir="backend", reload_excludes=("venv",))
    cmd_stable = build_uvicorn_command(py_exe, "backend.main:app", 18767, stable_mode=True, reload_dir="backend", reload_excludes=("venv",))
    assert "--reload" in cmd_dev and "--reload-dir" in cmd_dev
    assert "--reload" not in cmd_stable and "--reload-dir" not in cmd_stable
