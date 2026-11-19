# -*- coding: utf-8 -*-
"""
Pruebas Unitarias para el Watchdog Determinista y Semáforo de Salud (0 Tokens).
"""

import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend import main
from backend.daemon import TraderDaemon
from backend.execution.paper_broker import PaperBrokerAdapter
from backend.health_watchdog import HealthWatchdog


def _make_daemon(tmp_path):
    db_file = str(tmp_path / "watchdog_ledger.sqlite3")
    broker = PaperBrokerAdapter(initial_vault_usd=100.0, db_path=db_file)
    d = TraderDaemon(broker=broker)
    d.is_running = True
    d.started_at = time.time() - 60.0
    d.cycle_count = 3
    d.last_cycle_ts = time.time() - 10.0
    d.strategy = "auto"
    d.allowed_strategies = [
        "squeeze_dual_eth_4h_slot1",
        "donchian_breakout_1h",
        "cava_fallo_macd_eurusd_1h",
    ]
    return d


def test_watchdog_synthetic_probe_active_strategies(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADING_LEDGER_DB_PATH", str(tmp_path / "wd1.sqlite3"))
    wd = HealthWatchdog()
    res = wd.probe_active_strategies(
        ["squeeze_dual_eth_4h_slot1", "donchian_breakout_1h", "cava_fallo_macd_eurusd_1h"],
        force=True,
    )
    assert res["status"] == "GREEN"
    assert res["checked"] == 3
    assert res["passed"] == 3
    assert res["failures"] == []


def test_watchdog_catches_nan_or_exception_in_strategy(monkeypatch):
    wd = HealthWatchdog()

    class BrokenStrat:
        activo_default = "BTC/USDT"

        def evaluar(self, **kwargs):
            return {"tp_gross_pct": float("nan"), "sl_gross_pct": 1.0, "net_rr": 2.0}, 0.0, False, [], 0.5

    with patch("backend.estrategias.registry.get_strategy", return_value=BrokenStrat()), \
         patch("backend.estrategias.registry.evaluate_strategy", return_value=({"tp_gross_pct": float("nan"), "sl_gross_pct": 1.0, "net_rr": 2.0}, 0.0, False, [], 0.5)):
        res = wd.probe_active_strategies(["broken_test_strat"], force=True)

    assert res["status"] == "RED"
    assert res["passed"] == 0
    assert len(res["failures"]) == 1
    assert "no finito" in res["failures"][0]["error"]


def test_watchdog_evaluate_lights_and_red_telegram_transition_cooldown(tmp_path, monkeypatch):
    buf_path = tmp_path / "macro_buf.json"
    buf_path.write_text(
        json.dumps({"BTC/USDT": {"created_at": datetime.now(timezone.utc).isoformat()}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", str(buf_path))

    daemon = _make_daemon(tmp_path)
    daemon.broker.place_entry("SOL/USDT", "BUY", qty=0.5, price=85.0, initial_tp_pct=3.0, initial_sl_pct=1.5)

    # Sin hilo corriendo + 1 posición abierta => guardian_sl debe pasar a RED
    wd = HealthWatchdog()

    fake_mon_payload = json.dumps({
        "status": "GREEN",
        "lights": {
            "rss_ingesta": {"status": "GREEN", "feeds_ok": 20, "feeds_failed": 0, "total_feeds": 20},
            "puente_kula": {"status": "GREEN", "last_inject_ok": True},
        },
    }).encode("utf-8")

    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = fake_mon_payload
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = False

    with patch("backend.health_watchdog.urlopen", return_value=fake_resp), \
         patch("backend.telegram_notifier.notify_watchdog_alert", return_value=True) as mock_tg:
        out1 = wd.evaluate(daemon, force_probe=True, notify_on_red=True, monitor_url="http://127.0.0.1:8520")
        assert out1["status"] == "RED"
        assert out1["lights"]["guardian_sl"]["status"] == "RED"
        assert out1["lights"]["kula_motor"]["status"] == "GREEN"
        assert out1["lights"]["formulas_sintetico"]["status"] == "GREEN"
        assert mock_tg.call_count == 1

        # Segunda evaluación inmediata en RED no debe repetir spam por cooldown de 30 min
        out2 = wd.evaluate(daemon, force_probe=False, notify_on_red=True, monitor_url="http://127.0.0.1:8520")
        assert out2["lights"]["guardian_sl"]["status"] == "RED"
        assert mock_tg.call_count == 1


def test_api_health_semaforo_endpoint_returns_4_lights():
    client = TestClient(main.app)
    with patch("backend.health_watchdog.urlopen", side_effect=OSError("monitor offline")):
        res = client.get("/api/health/semaforo?probe=true")
    assert res.status_code == 200
    data = res.json()
    assert data["zero_tokens"] is True
    assert set(data["lights"].keys()) == {
        "kula_motor",
        "guardian_sl",
        "formulas_sintetico",
        "balam_puente",
    }
    assert data["lights"]["formulas_sintetico"]["status"] == "GREEN"
    assert data["lights"]["balam_puente"]["status"] == "RED"


def test_watchdog_monitor_404_falls_back_to_status_yellow():
    import io
    from urllib.error import HTTPError
    from backend.daemon import get_trader_daemon

    wd = HealthWatchdog()

    def fake_urlopen(req, timeout=1.0):
        url = getattr(req, "full_url", str(req))
        if url.endswith("/api/health/semaforo"):
            raise HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = json.dumps({"reports_count": 83, "total_feeds": 20}).encode("utf-8")
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return resp

    with patch("backend.health_watchdog.urlopen", side_effect=fake_urlopen):
        out = wd.evaluate(get_trader_daemon(), force_probe=True, notify_on_red=False, monitor_url="http://127.0.0.1:8520")
    assert out["lights"]["balam_puente"]["status"] == "YELLOW"
    assert out["lights"]["balam_puente"]["monitor_online"] is True


def test_watchdog_quick_check_binary_ok_and_alert_states(tmp_path, monkeypatch):
    buf_path = tmp_path / "macro_qc.json"
    buf_path.write_text(
        json.dumps({"BTC/USDT": {"created_at": datetime.now(timezone.utc).isoformat()}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", str(buf_path))

    daemon = _make_daemon(tmp_path)
    daemon.last_reason = "[ETH/USDT 15m] Close $1793.60 | ADX1H: 13.68 (<18) | Bloqueo: ADX1H<18 -> En espera"
    daemon.last_patrol_coverage = {
        "ts": time.time(),
        "expected_symbols": ["SOL/USDT", "ETH/USDT"],
        "evaluated_symbols": ["SOL/USDT"],
        "cached_symbols": ["ETH/USDT"],
        "market_closed_symbols": [],
        "skipped_symbols": [],
        "policy_skipped_symbols": [],
        "missing_or_error_symbols": {},
    }
    daemon.forced_tf_warnings = []

    fake_mon_payload = json.dumps({
        "status": "GREEN",
        "lights": {
            "rss_ingesta": {"status": "GREEN", "feeds_ok": 20, "feeds_failed": 0, "total_feeds": 20},
            "puente_kula": {"status": "GREEN", "last_inject_ok": True},
        },
    }).encode("utf-8")
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = fake_mon_payload
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = False

    wd = HealthWatchdog()
    with patch("backend.health_watchdog.urlopen", return_value=fake_resp):
        res_ok = wd.evaluate(daemon, force_probe=True, notify_on_red=False, monitor_url="http://127.0.0.1:8520")

    qc_ok = res_ok["quick_check"]
    assert qc_ok["binary_status"] == "OK"
    assert qc_ok["binary_label"] == "✅ 100% OK"
    assert qc_ok["assets_coverage"]["reviewed"] == 2
    assert qc_ok["assets_coverage"]["expected"] == 2
    assert "ADX1H: 13.68" in qc_ok["last_no_trade_reason"]
    assert qc_ok["triad_state"]["cerebro"]["status"] == "GREEN"
    assert qc_ok["triad_state"]["balam"]["status"] == "GREEN"
    assert qc_ok["triad_state"]["kula"]["status"] == "GREEN"

    # Si Balam está en "Balam (Solo Técnico)" con Monitor online y 20/20 RSS OK => NO debe disparar FALTA / ALERTA
    buf_path.unlink(missing_ok=True)
    with patch("backend.health_watchdog.urlopen", return_value=fake_resp):
        res_solo_tec = wd.evaluate(daemon, force_probe=False, notify_on_red=False, monitor_url="http://127.0.0.1:8520")
    assert res_solo_tec["lights"]["balam_puente"]["status"] == "YELLOW"
    assert res_solo_tec["lights"]["balam_puente"]["label"] == "Balam (Solo Técnico)"
    assert res_solo_tec["quick_check"]["binary_status"] == "OK"
    assert res_solo_tec["quick_check"]["binary_label"] == "✅ 100% OK"

    # Si falta un activo o hay TF forzada => debe pasar a ALERT con detalle
    daemon.last_patrol_coverage["missing_or_error_symbols"] = {"ETH/USDT": "Precio <= 0"}
    daemon.forced_tf_warnings = ["kula_cava_eth_1h: nativa 1h ejecutándose en 4h"]
    with patch("backend.health_watchdog.urlopen", return_value=fake_resp):
        res_alert = wd.evaluate(daemon, force_probe=False, notify_on_red=False, monitor_url="http://127.0.0.1:8520")

    qc_alert = res_alert["quick_check"]
    assert qc_alert["binary_status"] == "ALERT"
    assert qc_alert["binary_label"].startswith("⚠️ FALTA / ALERTA:")
    assert qc_alert["active_mode_summary"]["tf_alert"] is True
    assert qc_alert["assets_coverage"]["reviewed"] == 1


