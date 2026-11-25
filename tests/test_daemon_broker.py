import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend import main
from backend.daemon import TraderDaemon
from backend.execution.paper_broker import PaperBrokerAdapter


@pytest.fixture
def isolated_daemon(tmp_path, monkeypatch):
    csv_file = str(tmp_path / "test_trades.csv")
    monkeypatch.setenv("TRADING_OLLAMA_CSV_PATH", csv_file)
    db_file = str(tmp_path / "test_daemon_ledger.sqlite3")
    monkeypatch.setenv("TRADING_LEDGER_DB_PATH", db_file)
    bias_file = str(tmp_path / "test_macro_bias.json")
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", bias_file)
    broker = PaperBrokerAdapter(initial_vault_usd=1000.0, db_path=db_file, fee_pct=0.10)
    daemon = TraderDaemon(broker=broker)
    daemon.symbol = "BTC/USDT"
    daemon.timeframe = "15m"
    daemon.strategy = "manual"
    daemon.risk = 0.10
    daemon.tp = 3.0
    daemon.sl = 1.0
    daemon.mode = "auto"
    return daemon


def test_daemon_initialization_with_paper_broker(isolated_daemon):
    assert isolated_daemon.is_running is False
    assert isolated_daemon.broker.fetch_positions() == []
    assert isolated_daemon.broker.vault_balances["USDT"] == 1000.0
    assert isolated_daemon.broker.fetch_balances()["USDT"] == 0.0


def test_daemon_executes_buy_when_signal_is_comprar(isolated_daemon):
    fake_analysis = {
        "signal": "COMPRAR",
        "reason": "Test buy trigger",
        "strategy": "manual",
        "strategy_metrics": {},
    }
    fake_price = {"symbol": "BTC/USDT", "price": 100.0}

    with patch("backend.main.get_analysis", return_value=fake_analysis), \
         patch("backend.main.get_price", return_value=fake_price):
        isolated_daemon._execute_cycle()

    positions = isolated_daemon.broker.fetch_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTC/USDT"
    assert positions[0]["status"] == "OPEN"
    assert positions[0]["entry_price"] == 100.0
    assert isolated_daemon.last_signal == "COMPRAR"


def test_daemon_respects_copilot_mode(isolated_daemon):
    isolated_daemon.mode = "copilot"
    fake_analysis = {
        "signal": "COMPRAR",
        "reason": "Copilot buy opportunity",
        "strategy": "manual",
        "strategy_metrics": {},
    }
    fake_price = {"symbol": "BTC/USDT", "price": 100.0}

    with patch("backend.main.get_analysis", return_value=fake_analysis), \
         patch("backend.main.get_price", return_value=fake_price):
        isolated_daemon._execute_cycle()

    # En modo copiloto, no abre la posición autónomamente
    assert isolated_daemon.broker.fetch_positions() == []
    assert isolated_daemon.last_signal == "COMPRAR"


def test_daemon_executes_stop_loss_in_python(isolated_daemon):
    # 1. Abrir posición previa a $100 con SL al 2% ($98.0)
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0)
    isolated_daemon.broker.place_protection("BTC/USDT", qty=1.0, stop_loss_price=98.0, take_profit_price=103.0)
    assert len(isolated_daemon.broker.fetch_positions()) == 1

    # 2. El precio cae a $97.5 (por debajo de $98.0)
    fake_price = {"symbol": "BTC/USDT", "price": 97.5}
    fake_analysis = {"signal": "MANTENER", "reason": "Price dropping"}

    with patch("backend.main.get_price", return_value=fake_price), \
         patch("backend.main.get_analysis", return_value=fake_analysis):
        isolated_daemon._execute_cycle()

    # La posición debe estar cerrada y liquidada en SQLite
    assert isolated_daemon.broker.fetch_positions() == []
    assert isolated_daemon.broker.fetch_balances()["USDT"] == 0.0
    assert isolated_daemon.last_signal == "STOP_LOSS"


def test_daemon_stop_loss_calls_notify_trade_closed(isolated_daemon):
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0, strategy="kula_balam_cava_ruiz")
    isolated_daemon.broker.place_protection("BTC/USDT", qty=1.0, stop_loss_price=98.0, take_profit_price=105.0)

    fake_price = {"symbol": "BTC/USDT", "price": 97.0}
    fake_analysis = {"signal": "MANTENER", "reason": "Caída"}

    with patch("backend.main.get_price", return_value=fake_price), \
         patch("backend.main.get_analysis", return_value=fake_analysis), \
         patch("backend.telegram_notifier.notify_trade_closed") as mock_notify:
        isolated_daemon._execute_cycle()
        assert mock_notify.called
        assert mock_notify.call_args[1]["symbol"] == "BTC/USDT"
        assert mock_notify.call_args[1]["strategy"] == "kula_balam_cava_ruiz"
        assert mock_notify.call_args[1]["exit_reason"] == "Stop Loss"


def test_daemon_executes_take_profit_in_python(isolated_daemon):
    # 1. Abrir posición previa a $100 con TP al 3% ($103.0)
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0)
    isolated_daemon.broker.place_protection("BTC/USDT", qty=1.0, stop_loss_price=98.0, take_profit_price=103.0)
    assert len(isolated_daemon.broker.fetch_positions()) == 1

    # 2. El precio sube a $104.0 (por encima de $103.0)
    fake_price = {"symbol": "BTC/USDT", "price": 104.0}
    fake_analysis = {"signal": "MANTENER", "reason": "Price surging"}

    with patch("backend.main.get_price", return_value=fake_price), \
         patch("backend.main.get_analysis", return_value=fake_analysis):
        isolated_daemon._execute_cycle()

    # La posición debe estar cerrada y con ganancia en la Bóveda
    assert isolated_daemon.broker.fetch_positions() == []
    assert isolated_daemon.broker.fetch_balances()["USDT"] == 0.0
    assert isolated_daemon.last_signal == "TAKE_PROFIT"
    assert isolated_daemon.broker.vault_balances["USDT"] > 1000.0


def test_daemon_take_profit_calls_notify_trade_closed(isolated_daemon):
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0, strategy="nasdaq_araujo_vwap")
    isolated_daemon.broker.place_protection("BTC/USDT", qty=1.0, stop_loss_price=98.0, take_profit_price=103.0)

    fake_price = {"symbol": "BTC/USDT", "price": 104.0}
    fake_analysis = {"signal": "MANTENER", "reason": "Subida"}

    with patch("backend.main.get_price", return_value=fake_price), \
         patch("backend.main.get_analysis", return_value=fake_analysis), \
         patch("backend.telegram_notifier.notify_trade_closed") as mock_notify:
        isolated_daemon._execute_cycle()
        assert mock_notify.called
        assert mock_notify.call_args[1]["symbol"] == "BTC/USDT"
        assert mock_notify.call_args[1]["strategy"] == "nasdaq_araujo_vwap"
        assert mock_notify.call_args[1]["exit_reason"] == "Take Profit"


def test_broker_api_positions_and_flatten_endpoints(monkeypatch, isolated_daemon):
    monkeypatch.setattr("backend.daemon.get_trader_daemon", lambda: isolated_daemon)

    client = TestClient(main.app)

    # 1. Inicialmente no hay posiciones
    res = client.get("/api/broker/positions")
    assert res.status_code == 200
    assert res.json()["positions"] == []

    # 2. Abrir posición manualmente en broker
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0)
    res = client.get("/api/broker/positions")
    assert len(res.json()["positions"]) == 1

    # 3. Llamar a flatten desde la API
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 102.0}), \
         patch("backend.telegram_notifier.notify_trade_closed") as mock_notify_close:
        res = client.post("/api/broker/flatten", json={"symbol": "BTC/USDT", "reason": "Cierre Manual Operador"})
        assert res.status_code == 200
        assert res.json()["result"]["closed"] is True
        assert mock_notify_close.called
        call_kwargs = mock_notify_close.call_args[1]
        assert call_kwargs["symbol"] == "BTC/USDT"
        assert call_kwargs["exit_reason"] == "Cierre Manual Operador"

    # 4. Verificar que se cerró
    assert isolated_daemon.broker.fetch_positions() == []


def test_broker_api_balances_endpoint(monkeypatch, isolated_daemon):
    monkeypatch.setattr("backend.daemon.get_trader_daemon", lambda: isolated_daemon)

    client = TestClient(main.app)
    res = client.get("/api/broker/balances")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "USDT" in data["vault"]
    assert "USD" in data["vault"]
    assert "ARS" in data["vault"]
    assert data["vault"]["USDT"] == 1000.0
    assert data["operational"]["USDT"] == 0.0


def test_broker_api_deposit_and_reset_endpoints(monkeypatch, isolated_daemon):
    monkeypatch.setattr("backend.daemon.get_trader_daemon", lambda: isolated_daemon)

    client = TestClient(main.app)

    # 1. Depósito de $250 USDT
    res_dep = client.post("/api/broker/deposit", json={"amount": 250.0, "currency": "USDT"})
    assert res_dep.status_code == 200
    assert res_dep.json()["vault"]["USDT"] == 1250.0

    # 2. Reset a $500
    res_reset = client.post("/api/broker/reset", json={"initial_amount": 500.0})
    assert res_reset.status_code == 200
    assert res_reset.json()["vault"]["USDT"] == 500.0
    assert isolated_daemon.broker.vault_balances["USDT"] == 500.0


def test_broker_api_trades_endpoint(monkeypatch, isolated_daemon):
    monkeypatch.setattr("backend.daemon.get_trader_daemon", lambda: isolated_daemon)
    client = TestClient(main.app)

    # Inicialmente sin trades
    res = client.get("/api/broker/trades")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["trades"] == []

    # Abrir posición y cerrar
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=0.01, price=50000.0)
    isolated_daemon.broker.flatten("BTC/USDT", current_price=51000.0)

    # Verificar que /api/broker/trades retorna el trade cerrado
    res2 = client.get("/api/broker/trades")
    assert res2.status_code == 200
    trades = res2.json()["trades"]
    assert len(trades) == 1
    assert trades[0]["symbol"] == "BTC/USDT"
    assert trades[0]["status"] == "CLOSED"
    assert trades[0]["entry_price"] == 50000.0
    assert trades[0]["exit_price"] == 51000.0
    assert trades[0]["realized_pnl"] > 0


def test_broker_trim_position_and_peluqueo(isolated_daemon):
    # 1. Abrir posición de 0.01 BTC a $50,000 (costo $500 < $1000 de bóveda)
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=0.01, price=50000.0)
    pos = isolated_daemon.broker.fetch_positions()
    assert len(pos) == 1
    assert pos[0]["qty"] == 0.01

    # 2. Peluqueo: liquidar el 50% (0.005) a $52,000 (+4.0%)
    res_trim = isolated_daemon.broker.trim_position("BTC/USDT", trim_qty=0.005, current_price=52000.0)
    assert res_trim["trimmed"] is True
    assert res_trim["trimmed_qty"] == 0.005
    assert res_trim["remaining_qty"] == 0.005
    assert res_trim["net_pnl"] > 0

    # 3. Verificar que la posición remanente tiene Stop Loss en Breakeven Real (+0.25% buffer)
    pos_after = isolated_daemon.broker.fetch_positions()
    assert len(pos_after) == 1
    assert pos_after[0]["qty"] == 0.005
    assert pos_after[0]["initial_sl_pct"] == 0.0
    assert pos_after[0]["current_stop_net_pct"] == 0.25
    assert pos_after[0]["be_armed"] == 1

    # 4. Cerrar el 50% restante en Breakeven nominal ($50,000) y verificar PnL acumulado positivo y 0 pérdidas consecutivas
    res_close = isolated_daemon.broker.flatten("BTC/USDT", current_price=50000.0)
    assert res_close["closed"] is True
    assert res_close["net_pnl"] > 0  # El PnL acumulado del trade completo sigue siendo positivo
    assert res_close["risk_state"]["consecutive_losses"] == 0
    assert isolated_daemon.broker.fetch_balances()["USDT"] == 0.0


def test_araujo_allows_reentry_after_first_trade_closes(isolated_daemon):
    isolated_daemon.strategy = "nasdaq_araujo_vwap"
    isolated_daemon.mode = "autonomous"

    # 1. Primer trade del día se ejecuta y se cierra (ej. en Breakeven o ganancia temprana)
    assert isolated_daemon.broker.ledger.count_trades_today("BTC/USDT") == 0
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=0.01, price=50000.0)
    isolated_daemon.broker.flatten("BTC/USDT", current_price=50500.0)
    assert isolated_daemon.broker.ledger.count_trades_today("BTC/USDT") == 1

    # 2. Al presentarse un segundo setup válido con R:R >= 2.0 (sin bloqueo rígido de 1 trade/día),
    # el motor permite capturar la continuación tendencial.
    fake_price = {"symbol": "BTC/USDT", "price": 50500.0}
    fake_analysis = {
        "signal": "COMPRAR",
        "reason": "Second breakout continuation",
        "strategy_metrics": {"tp_gross_pct": 2.5, "sl_gross_pct": 1.0},
    }
    with patch("backend.main.get_price", return_value=fake_price), \
         patch("backend.main.get_analysis", return_value=fake_analysis):
        isolated_daemon._execute_cycle()

    assert len(isolated_daemon.broker.fetch_positions()) == 1


def test_swing_position_hibernates_when_market_closed_and_auto_switches_to_crypto(isolated_daemon):
    # Abrir una posición Swing (2 a 10 días) en NVDA (bóveda USD)
    isolated_daemon.symbol = "NVDA"
    isolated_daemon.strategy = "auto"
    isolated_daemon.mode = "autonomous"
    isolated_daemon.broker.place_entry("NVDA", "BUY", qty=2.0, price=120.0)
    assert len(isolated_daemon.broker.fetch_positions()) == 1

    # Simular que el mercado de acciones (NVDA) está cerrado (ej. después de las 17:00 hs o fin de semana),
    # mientras BTC/USDT sigue abierto 24/7
    def fake_market_open(sym, now_dt=None):
        return "/" in str(sym)

    fake_price = {"symbol": "BTC/USDT", "price": 50000.0}
    fake_analysis = {"signal": "MANTENER", "reason": "Crypto night check"}

    with patch("backend.estrategias.registry.is_asset_market_open", side_effect=fake_market_open), \
         patch("backend.main.get_price", return_value=fake_price), \
         patch("backend.main.get_analysis", return_value=fake_analysis):
        isolated_daemon._execute_cycle()

    # 1. La posición de NVDA sigue intacta en espera (no fue cerrada en falso)
    positions = isolated_daemon.broker.fetch_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "NVDA"
    # 2. Y el daemon conmutó automáticamente su radar activo a SOL/USDT (Cripto 24/7)
    assert isolated_daemon.symbol in ("SOL/USDT", "BTC/USDT")


def test_guardian_protects_multiple_concurrent_positions(isolated_daemon):
    # 1. Abrir 2 posiciones concurrentes: BTC/USDT a $100 (SL $98) y SOL/USDT a $50 (SL $49)
    isolated_daemon.symbol = "BTC/USDT"
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0, initial_sl_pct=2.0, initial_tp_pct=4.0)
    isolated_daemon.broker.place_entry("SOL/USDT", "BUY", qty=2.0, price=50.0, initial_sl_pct=2.0, initial_tp_pct=4.0)
    assert len(isolated_daemon.broker.fetch_positions()) == 2

    # 2. Simular que SOL cae por debajo de su SL ($48.0 < $49.0), mientras BTC se mantiene a $99.5 (> $98.0)
    def fake_prices(sym):
        if sym == "SOL/USDT":
            return {"symbol": sym, "price": 48.0}
        return {"symbol": sym, "price": 99.5}

    with patch("backend.main.get_price", side_effect=fake_prices):
        liquidated = isolated_daemon._check_open_positions_protections()

    # 3. Solo SOL debe haber sido liquidado por SL; BTC debe permanecer abierto
    assert len(liquidated) == 1
    assert liquidated[0]["symbol"] == "SOL/USDT"
    assert liquidated[0]["action"] == "STOP_LOSS"

    remaining = isolated_daemon.broker.fetch_positions()
    assert len(remaining) == 1
    assert remaining[0]["symbol"] == "BTC/USDT"


def test_guardian_active_when_agent_stopped_and_stops_on_force(isolated_daemon):
    # 1. Posición abierta con agente detenido (is_running = False)
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0)
    assert isolated_daemon.is_running is False
    assert len(isolated_daemon.broker.fetch_positions()) == 1

    # 2. ensure_guardian_running inicia el hilo de vigilancia
    started = isolated_daemon.ensure_guardian_running()
    assert started is True
    assert isolated_daemon._thread is not None
    assert isolated_daemon._thread.is_alive()

    # 3. stop(force=False) detiene compras pero mantiene el guardián activo
    status = isolated_daemon.stop(force=False)
    assert status["status"] == "stopped"
    assert status["guardian_active"] is True
    assert isolated_daemon.get_status()["guardian_active"] is True

    # 4. stop(force=True) termina el hilo por completo
    isolated_daemon.stop(force=True)
    assert isolated_daemon._thread is None


def test_daemon_breakeven_and_trailing_stop_protection(isolated_daemon):
    # 1. Abrir posición a $100 con TP de 4% y SL de 2%
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0, initial_tp_pct=4.0, initial_sl_pct=2.0)
    pos = isolated_daemon.broker.fetch_positions()[0]
    trade_id = pos["id"]

    # 2. Precio sube a $101.0 (+1.0% bruto). El backend debe armar Breakeven (+0.15% neto garantizado)
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 101.0}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 0  # No liquida, solo sube el stop

    pos_updated = isolated_daemon.broker.fetch_positions()[0]
    assert pos_updated["be_armed"] == 1
    assert pos_updated["current_stop_net_pct"] >= 0.15
    assert pos_updated["peak_price"] == 101.0

    # 3. Precio retrocede a $100.10 (debajo del nivel de Breakeven Real con comisiones). El backend debe cerrar en Breakeven Real
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 100.10}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 1
        assert liquidated[0]["symbol"] == "BTC/USDT"
        assert liquidated[0]["action"] == "BREAKEVEN_REAL"

    # Verificar que no quedan posiciones abiertas
    assert len(isolated_daemon.broker.fetch_positions()) == 0


def test_daemon_pre_breakeven_030_and_breakeven_steps(isolated_daemon):
    # Abrir posición a $100.00 con SL inicial de 2.0% (-2.0%)
    isolated_daemon.broker.place_entry("SOL/USDT", "BUY", qty=1.0, price=100.0, initial_tp_pct=6.0, initial_sl_pct=2.0)

    # Avance temprano: Sube a $100.32 (+0.32% bruto). La estrategia ganadora deja respirar la posición (sin compresión asfixiante)
    with patch("backend.main.get_price", return_value={"symbol": "SOL/USDT", "price": 100.32}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 0

    pos_step1 = isolated_daemon.broker.fetch_positions()[0]
    assert pos_step1["be_armed"] == 0
    assert pos_step1["current_stop_net_pct"] <= -1.90

    # Avance Breakeven: Sube a $100.70 (+0.70% bruto >= umbral ganador)
    # Debe activar Breakeven Real fijando stop con ganancia neta garantizada (+0.15% neto)
    with patch("backend.main.get_price", return_value={"symbol": "SOL/USDT", "price": 100.70}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 0

    pos_step2 = isolated_daemon.broker.fetch_positions()[0]
    assert pos_step2["be_armed"] == 1
    assert pos_step2["current_stop_net_pct"] == pytest.approx(0.15, 0.01)



def test_daemon_trailing_trend_runner_raul_idea(isolated_daemon):
    isolated_daemon.strategy = "trailing_trend_runner"
    isolated_daemon.symbol = "BTC/USDT"

    # 1. Abrir posición a $100 con SL al 2% ($98.0) y TP referencia 6% ($106.0)
    isolated_daemon.broker.place_entry(
        "BTC/USDT", "BUY", qty=1.0, price=100.0, initial_tp_pct=6.0, initial_sl_pct=2.0
    )
    assert len(isolated_daemon.broker.fetch_positions()) == 1

    # 2. Precio sube a $105.0 (+5.0% bruto).
    # Se arma Breakeven, se activa Trailing Stop móvil y peak_price se actualiza a 105.0.
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 105.0}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 0

    pos = isolated_daemon.broker.fetch_positions()[0]
    assert pos["be_armed"] == 1
    assert pos["trail_active"] == 1
    assert pos["peak_price"] == 105.0
    # Stop debe haber subido por trailing detrás de 105 (a ~102.90)
    assert pos["current_stop_net_pct"] > 1.5

    # 3. Precio sube a $120.0 (+20.0% bruto, superando el TP de referencia de $106.0).
    # Con la doctrina Cava-Raúl, ejecuta Peluqueo del 50% y deja el 50% remanente libre con Trailing Stop
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 120.0}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 1
        assert liquidated[0]["action"] == "PELUQUEO_TP1"

    pos = isolated_daemon.broker.fetch_positions()[0]
    assert pos["qty"] == 0.5
    assert pos["tp1_trimmed"] == 1
    assert pos["current_stop_net_pct"] == 0.25  # Breakeven Real tras peluqueo

    # En el siguiente ciclo a $120.0, el 50% remanente actualiza el Trailing Stop detrás del nuevo pico
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 120.0}):
        liq_trail = isolated_daemon._check_open_positions_protections()
        assert len(liq_trail) == 0

    pos_trail = isolated_daemon.broker.fetch_positions()[0]
    assert pos_trail["peak_price"] == 120.0
    # A $120, trailing stop al 2% está en 120 * (1 - 0.02) = 117.60
    # El retorno neto acumulado en el stop debe ser ~ +17%
    assert pos_trail["current_stop_net_pct"] >= 16.5

    # 4. Ahora el mercado se gira y retrocede a $117.0 (por debajo del trailing stop de $117.60).
    # El daemon debe liquidar automáticamente por Trailing Stop y embolsar la ganancia.
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 117.0}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 1
        assert liquidated[0]["symbol"] == "BTC/USDT"
        assert liquidated[0]["action"] == "TRAILING_STOP"
        assert liquidated[0]["result"]["closed"] is True

    # Verificar que la posición quedó cerrada y el saldo en bóveda creció con la ganancia
    assert len(isolated_daemon.broker.fetch_positions()) == 0
    assert isolated_daemon.broker.vault_balances["USDT"] > 1015.0


def test_daemon_doble_escalon_scalping_bloqueado_y_trailing_sin_techo(isolated_daemon):
    """
    Verifica la Fórmula de Doble Escalón: Scalping Bloqueado + Trailing sin Techo (Idea Raúl):
    1. Entrada en $100.00 con SL al 2.0% ($98.00).
    2. Escalón 1: Avance a $100.50 (+0.50% bruto >= +0.40%) activa Breakeven Real (+0.15% neto).
    3. Escalón 2: Avance a $101.10 (+1.10% bruto >= +1.00%) activa Cerrojo de Scalping blindando
       el Stop en +0.80% bruto (+0.50% neto / $100.80).
    4. El precio retrocede a $100.90: la posición se mantiene abierta y corriendo sin asfixia.
    5. El precio retrocede a $100.75 (bajo el piso de scalping): se liquida protegiendo la ganancia firme.
    """
    isolated_daemon.strategy = "trailing_trend_runner"
    isolated_daemon.symbol = "BTC/USDT"

    # 1. Abrir posición a $100.00
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0, initial_tp_pct=6.0, initial_sl_pct=2.0)
    pos = isolated_daemon.broker.fetch_positions()[0]
    assert pos["current_stop_net_pct"] == -2.0

    # 2. Precio sube a $100.50 (+0.50% bruto): Arma Breakeven Real
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 100.50}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 0

    pos_be = isolated_daemon.broker.fetch_positions()[0]
    assert pos_be["be_armed"] == 1
    assert pos_be["current_stop_net_pct"] >= 0.12

    # 3. Precio sube a $101.10 (+1.10% bruto >= +1.00% gatillo): Arma Cerrojo de Scalping
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 101.10}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 0

    pos_scalp = isolated_daemon.broker.fetch_positions()[0]
    assert pos_scalp["be_armed"] == 1
    assert pos_scalp["peak_price"] == 101.10
    # Stop blindado como mínimo en +0.80% bruto (~+0.50% neto)
    assert pos_scalp["current_stop_net_pct"] >= 0.48

    # 4. Retroceso menor a $100.90 (aún por encima del piso de scalping de $100.80): NO se liquida
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 100.90}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 0
    assert len(isolated_daemon.broker.fetch_positions()) == 1

    # 5. Retroceso a $100.75 (toca/perfora el piso de $100.80): Se liquida protegiendo ganancia de scalping
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 100.75}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 1
        assert liquidated[0]["symbol"] == "BTC/USDT"
        assert liquidated[0]["result"]["closed"] is True
        assert liquidated[0]["result"]["net_pnl"] > 0.40  # Ganancia neta firme de scalping protegida


def test_daemon_doble_escalon_short_scalping_bloqueado(isolated_daemon):
    """
    Verifica la Fórmula de Doble Escalón para posiciones en CORTO (SHORT):
    1. Entrada en SHORT a $100.00 con SL inicial a 2.0% ($102.00).
    2. Escalón 1: Caída favorable a $99.50 (+0.50% bruto) activa Breakeven Real (+0.15% neto).
    3. Escalón 2: Caída a $98.90 (+1.10% bruto favorable >= +1.00%) activa Cerrojo de Scalping SHORT,
       blindando el Stop en $99.20 (+0.80% bruto / +0.50% neto garantizado).
    4. Rebote a $99.10 (aún por debajo del stop de $99.20): NO se liquida.
    5. Rebote a $99.25 (supera el stop de scalping): se liquida protegiendo la ganancia de scalping SHORT.
    """
    isolated_daemon.strategy = "trailing_short_runner"
    isolated_daemon.symbol = "ETH/USDT"

    # 1. Abrir posición SHORT a $100.00
    isolated_daemon.broker.place_entry("ETH/USDT", "SHORT", qty=1.0, price=100.0, initial_tp_pct=6.0, initial_sl_pct=2.0)
    pos = isolated_daemon.broker.fetch_positions()[0]
    assert pos["side"] == "SHORT"
    assert pos["current_stop_net_pct"] == -2.0

    # 2. Caída a $99.50 (+0.50% bruto favorable): Arma Breakeven Real en SHORT
    with patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": 99.50}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 0

    pos_be = isolated_daemon.broker.fetch_positions()[0]
    assert pos_be["be_armed"] == 1
    assert pos_be["current_stop_net_pct"] >= 0.12

    # 3. Caída a $98.90 (+1.10% favorable): Arma Cerrojo de Scalping SHORT (piso $99.20)
    with patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": 98.90}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 0

    pos_scalp = isolated_daemon.broker.fetch_positions()[0]
    assert pos_scalp["be_armed"] == 1
    assert pos_scalp["peak_price"] == 98.90
    assert pos_scalp["current_stop_net_pct"] >= 0.48

    # 4. Rebote a $99.10 (aún debajo de $99.20): NO se liquida
    with patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": 99.10}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 0
    assert len(isolated_daemon.broker.fetch_positions()) == 1

    # 5. Rebote a $99.25 (toca el stop de scalping en corto): Se liquida protegiendo ganancia
    with patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": 99.25}):
        liquidated = isolated_daemon._check_open_positions_protections()
        assert len(liquidated) == 1
        assert liquidated[0]["symbol"] == "ETH/USDT"
        assert liquidated[0]["result"]["closed"] is True
        assert liquidated[0]["result"]["net_pnl"] > 0.40  # Ganancia neta de scalping short protegida


def test_daemon_smart_mode_patrols_liquid_watchlist(isolated_daemon):
    isolated_daemon.mode = "smart"
    isolated_daemon.symbol = "BTC/USDT"
    isolated_daemon.max_positions = 4
    isolated_daemon.allowed_strategies = []

    analyzed_symbols = []

    def fake_analysis(**kwargs):
        sym = kwargs.get("symbol")
        analyzed_symbols.append(sym)
        if sym == "BTC/USDT":
            return {"signal": "MANTENER", "reason": "BTC sin setup", "strategy": "manual", "strategy_metrics": {}}
        elif sym == "ETH/USDT":
            return {"signal": "COMPRAR", "reason": "ETH setup detectado", "strategy": "manual", "strategy_metrics": {}}
        return {"signal": "MANTENER", "reason": "Sin setup", "strategy": "manual", "strategy_metrics": {}}

    def fake_price(sym):
        return {"symbol": sym, "price": 100.0}

    with patch("backend.main.get_analysis", side_effect=fake_analysis), \
         patch("backend.main.get_price", side_effect=fake_price), \
         patch("backend.entry_gate.get_btc_macro_status", return_value={"veto_active": False}):
        isolated_daemon._execute_cycle()

    # Debe haber patrullado BTC, ETH, SOL, BNB y XRP en el mismo ciclo
    assert "BTC/USDT" in analyzed_symbols
    assert "ETH/USDT" in analyzed_symbols
    assert "SOL/USDT" in analyzed_symbols
    assert "BNB/USDT" in analyzed_symbols
    assert "XRP/USDT" in analyzed_symbols

    # Debe haber comprado ETH/USDT porque BTC dio MANTENER pero ETH dio COMPRAR
    positions = isolated_daemon.broker.fetch_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "ETH/USDT"
    assert isolated_daemon.symbol == "ETH/USDT"
    # Con protección de telemetría, una entrada COMPRAR no es sobrescrita por el MANTENER de activos posteriores
    assert isolated_daemon.last_active_symbol in ("ETH/USDT", "XRP/USDT")
    assert isolated_daemon.get_status()["active_symbol"] in ("ETH/USDT", "XRP/USDT")


def test_chaos_1_concurrent_double_close_does_not_crash_guardian(isolated_daemon):
    """F-05: Si una posición es cerrada concurrentemente desde la UI mientras el Guardián evalúa múltiples posiciones,
    el Guardián debe atrapar ValueError y seguir protegiendo las demás posiciones en el mismo ciclo."""
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0)
    isolated_daemon.broker.place_protection("BTC/USDT", qty=1.0, stop_loss_price=98.0, take_profit_price=105.0)
    isolated_daemon.broker.place_entry("ETH/USDT", "BUY", qty=1.0, price=100.0)
    isolated_daemon.broker.place_protection("ETH/USDT", qty=1.0, stop_loss_price=98.0, take_profit_price=105.0)

    original_flatten = isolated_daemon.broker.flatten

    def concurrent_flatten(symbol, current_price=None, exit_reason="MANUAL"):
        if symbol == "BTC/USDT":
            # Simula que otro hilo cerró BTC/USDT un milisegundo antes y que el Guardián recibe ValueError
            original_flatten("BTC/USDT", current_price=97.0, exit_reason="MANUAL_UI")
            raise ValueError("No existe posición abierta para BTC/USDT")
        return original_flatten(symbol, current_price=current_price, exit_reason=exit_reason)

    with patch.object(isolated_daemon.broker, "flatten", side_effect=concurrent_flatten), \
         patch("backend.main.get_price", return_value={"price": 97.0}):
        closed_any = isolated_daemon._check_open_positions_protections()

    assert len(closed_any) == 1
    assert closed_any[0]["symbol"] == "ETH/USDT"
    # Ambas posiciones deben estar cerradas: BTC por UI y ETH por el Guardián en el mismo ciclo
    assert len(isolated_daemon.broker.fetch_positions()) == 0


def test_chaos_2_nan_and_negative_atr_rejected_at_entry_gate():
    """F-04: Precio NaN/Inf, ATR <= 0 o ATR NaN deben ser rechazados determinísticamente por Entry Gate."""
    from backend.entry_gate import entry_gate_failures

    failures_nan_price = entry_gate_failures(
        "BTC/USDT", price=float("nan"), tp_gross_pct=2.5, sl_gross_pct=0.8, fee_pct=0.1, spread_pct=0.05, atr=1.0
    )
    assert any("inválidos" in f for f in failures_nan_price)

    failures_zero_atr = entry_gate_failures(
        "BTC/USDT", price=100.0, tp_gross_pct=2.5, sl_gross_pct=0.8, fee_pct=0.1, spread_pct=0.05, atr=0.0
    )
    assert any("ATR inválido" in f for f in failures_zero_atr)

    failures_neg_atr = entry_gate_failures(
        "BTC/USDT", price=100.0, tp_gross_pct=2.5, sl_gross_pct=0.8, fee_pct=0.1, spread_pct=0.05, atr=-5.0
    )
    assert any("ATR inválido" in f for f in failures_neg_atr)


def test_chaos_3_trim_with_multi_position_does_not_leave_op_deficit(isolated_daemon):
    """F-02: Un trim parcial cuando hay múltiples posiciones abiertas jamás debe dejar OP_USDT en negativo ni con residuo."""
    isolated_daemon.broker.set_operating_capital("USDT", 500.0)
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=2.0, price=100.0)
    isolated_daemon.broker.place_entry("ETH/USDT", "BUY", qty=1.0, price=100.0)

    # Trim del 50% (1.0 unidad) de BTC con pérdida (precio 90.0)
    res = isolated_daemon.broker.trim_position("BTC/USDT", trim_qty=1.0, current_price=90.0)
    assert res["trimmed"] is True

    # El saldo en OP_USDT debe ser exactamente el cost_basis remanente (100 de BTC + 100 de ETH = 200.0)
    op_balance = isolated_daemon.broker.ledger.get_account_balance("OP_USDT")
    positions = isolated_daemon.broker.fetch_positions()
    locked = sum(p["cost_basis"] for p in positions)
    assert abs(op_balance - locked) < 1e-6


def test_chaos_4_reset_account_cleans_capital_and_safe_profit_wallet_configs(isolated_daemon):
    """F-01: reset_account debe limpiar operating_capital_config y safe_profit_wallet_config para evitar estados zombis."""
    isolated_daemon.broker.set_operating_capital("USDT", 800.0)
    isolated_daemon.broker.ledger.transfer_safe_profit_wallet("USDT", 150.0, "FROM_OPERATING")
    assert isolated_daemon.broker.ledger.get_safe_profit_wallet("USDT")["available"] == 150.0

    isolated_daemon.broker.reset_account(initial_amount=1000.0)
    assert isolated_daemon.broker.ledger.get_safe_profit_wallet("USDT")["available"] == 0.0
    # Tras reset_account, el capital para operar se reinicia a initial_amount ($1000.0 USDT) en vez del valor zombie ($650.0)
    assert isolated_daemon.broker.get_operating_capital("USDT") == 1000.0


def test_chaos_5_telemetry_cache_purged_after_position_close(isolated_daemon):
    """F-08: Al cerrarse una posición, counterfactual_cache y time_decay_cache deben purgar el símbolo."""
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0)
    isolated_daemon.broker.place_protection("BTC/USDT", qty=1.0, stop_loss_price=98.0, take_profit_price=105.0)
    with patch("backend.main.get_price", return_value={"price": 100.1}):
        isolated_daemon._check_open_positions_protections()
    assert "BTC/USDT" in isolated_daemon.counterfactual_cache

    isolated_daemon.broker.flatten("BTC/USDT", current_price=100.1)
    # En el siguiente ciclo con otra posición, BTC/USDT debe purgarse
    isolated_daemon.broker.place_entry("ETH/USDT", "BUY", qty=1.0, price=100.0)
    isolated_daemon.broker.place_protection("ETH/USDT", qty=1.0, stop_loss_price=98.0, take_profit_price=105.0)
    with patch("backend.main.get_price", return_value={"price": 100.1}):
        isolated_daemon._check_open_positions_protections()
    assert "BTC/USDT" not in isolated_daemon.counterfactual_cache
    assert "ETH/USDT" in isolated_daemon.counterfactual_cache


def test_calibraciones_cuantitativas_a_y_b(isolated_daemon):
    """
    Auditoría cuantitativa Forense:
    1. Calibración A: Trigger BE >= max(0.65%, 1.2x ATR), salida garantizada con PnL neto > 0 (+0.15% neto).
    2. Calibración B: SL inicial acotado a 1.5% max, trailing escalonado desde +0.70% (1.0%) y +1.20% (0.80%).
    3. Monotonía eliminada: Telemetría reporta diferencial contrafáctico dinámico y modulación por RSI/peak.
    """
    import time
    isolated_daemon.strategy = "trailing_trend_runner"
    # Configurar telemetría simulada por símbolo
    isolated_daemon.symbol_indicators["SOL/USDT"] = {
        "rsi": 66.0,
        "atr_14": 0.80,
        "atr_pct": 0.80,
        "ts": time.time(),
    }

    # 1. Abrir posición en SOL a $100 con SL al 2% (estrategia ganadora)
    isolated_daemon.broker.place_entry("SOL/USDT", "BUY", qty=1.0, price=100.0, initial_tp_pct=6.0, initial_sl_pct=2.0)
    pos = isolated_daemon.broker.fetch_positions()[0]
    assert pos["initial_sl_pct"] == 2.0

    # 2. Con avance moderado a $100.30 (+0.30%), NO debe armar BE todavía (requiere +0.40% a +0.60%)
    with patch("backend.main.get_price", return_value={"symbol": "SOL/USDT", "price": 100.30}):
        isolated_daemon._check_open_positions_protections()
    pos = isolated_daemon.broker.fetch_positions()[0]
    assert pos["be_armed"] == 0

    # 3. Precio sube a $100.70 (+0.70% >= 0.60%): Ahora SÍ debe armar Breakeven Real
    with patch("backend.main.get_price", return_value={"symbol": "SOL/USDT", "price": 100.70}):
        isolated_daemon._check_open_positions_protections()
    pos = isolated_daemon.broker.fetch_positions()[0]
    assert pos["be_armed"] == 1
    assert pos["current_stop_net_pct"] >= 0.12

    # 4. Verificar que la telemetría contrafáctica reporta diferencial dinámico (NO monotonía de 0.00%)
    cf = isolated_daemon.counterfactual_cache["SOL/USDT"]
    assert cf["active_dist_pct"] != cf["alt_dist_pct"]
    assert cf["diff_pct"] != 0.0
    assert cf["rsi"] == 66.0

    # 5. Precio retrocede al Stop de Breakeven Real ($100.40):
    # La liquidación debe generar PnL estrictamente positivo tras devengar comisiones
    with patch("backend.main.get_price", return_value={"symbol": "SOL/USDT", "price": 100.40}):
        liquidated = isolated_daemon._check_open_positions_protections()
    assert len(liquidated) == 1
    assert liquidated[0]["action"] == "BREAKEVEN_REAL"
    assert liquidated[0]["result"]["net_pnl"] > 0
    assert liquidated[0]["result"]["net_pnl"] >= 0.05


def test_daemon_short_entry_and_trailing_protection(isolated_daemon):
    """
    Verifica el ciclo de vida completo de una operación en CORTO (SHORT):
    1. Entrada en SHORT ejecutada con side='SHORT'.
    2. El precio cae a favor (+2.0% de ganancia): PnL no realizado positivo, rastreo de valle mínimo (peak_price <= 98.0).
    3. Breakeven Real activado fijando el Stop por debajo del precio de entrada ($99.65 aprox) con +0.15% neto garantizado.
    4. El precio rebota hacia $99.65 (toca el Breakeven Real):
       Liquidación automática con net_pnl estrictamente positivo (>= +0.05 USDT) tras fees.
    """
    import time
    isolated_daemon.strategy = "trailing_short_runner"
    isolated_daemon.symbol_indicators["BTC/USDT"] = {
        "rsi": 40.0,
        "atr_14": 0.40,
        "atr_pct": 0.40,
        "ts": time.time(),
    }

    # 1. Entrada en SHORT a $100.0 con SL inicial a 1.5% ($101.50)
    fake_analysis = {
        "signal": "SHORT",
        "reason": "Test short confluencia bajista",
        "strategy": "trailing_short_runner",
        "strategy_metrics": {"side": "SHORT", "tp_gross_pct": 6.0, "sl_gross_pct": 1.5},
    }
    fake_price = {"symbol": "BTC/USDT", "price": 100.0}

    with patch("backend.main.get_analysis", return_value=fake_analysis), \
         patch("backend.main.get_price", return_value=fake_price):
        isolated_daemon._execute_cycle()

    positions = isolated_daemon.broker.fetch_positions()
    assert len(positions) == 1
    pos = positions[0]
    assert pos["symbol"] == "BTC/USDT"
    assert pos["side"] == "SHORT"
    assert pos["entry_price"] == 100.0

    # 2. El precio cae a $98.0 (movimiento favorable de +2.0% para la posición SHORT)
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 98.0}):
        status_favorable = isolated_daemon.get_status()
        pos_fav = status_favorable["open_positions"][0]
        # PnL no realizado debe ser positivo: (entry - cur) * qty = (100 - 98) * 1.0 = +2.0
        assert pos_fav["unrealized_pnl"] > 0
        assert pos_fav["unrealized_pnl_pct"] > 0

        # Ejecutar ciclo de protecciones a $98.0
        isolated_daemon._check_open_positions_protections()

    pos_after = isolated_daemon.broker.fetch_positions()[0]
    assert pos_after["be_armed"] == 1
    assert pos_after["peak_price"] <= 98.0
    assert pos_after["current_stop_net_pct"] >= 0.12

    # 3. El precio rebota a $99.65 (toca el Stop de Breakeven Real por debajo de la entrada)
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 99.65}):
        liquidated = isolated_daemon._check_open_positions_protections()

    assert len(liquidated) == 1
    assert liquidated[0]["action"] in ("BREAKEVEN_REAL", "TRAILING_STOP")
    assert liquidated[0]["result"]["net_pnl"] > 0
    assert isolated_daemon.broker.fetch_positions() == []


def test_audit_f01_short_pnl_direction_in_quant_risk():
    """F-01: net_pnl_pct_from_prices debe calcular ganancia cuando el precio cae en SHORT y pérdida cuando sube."""
    from backend.quant_risk import net_pnl_pct_from_prices

    # SHORT abierto en $100: si sube a $105 está perdiendo (~-5.3%), NO ganando
    pnl_losing_short = net_pnl_pct_from_prices(100.0, 105.0, fee_pct=0.10, spread_pct=0.05, side="SHORT")
    assert pnl_losing_short < -5.0

    # SHORT abierto en $100: si cae a $95 está ganando (~+4.7% neto)
    pnl_winning_short = net_pnl_pct_from_prices(100.0, 95.0, fee_pct=0.10, spread_pct=0.05, side="SHORT")
    assert pnl_winning_short > 4.5


def test_audit_f02_scale_in_short_blocks_loser_and_allows_winner(isolated_daemon):
    """F-02: scale_in_trade_with_jit en SHORT debe rechazar recargas en pérdida (cur_px > entry) y permitir en ganancia (cur_px < entry)."""
    isolated_daemon.broker.set_operating_capital("USDT", 500.0)
    isolated_daemon.broker.place_entry("BTC/USDT", "SHORT", qty=1.0, price=100.0, initial_tp_pct=6.0, initial_sl_pct=2.0)

    # 1. Si el precio subió a $101.0 (SHORT en pérdida de -1.0%), el Candado de Ganancia Segura DEBE bloquear el scale-in
    with pytest.raises(ValueError, match="Candado de Ganancia Segura"):
        isolated_daemon.broker.scale_in_position("BTC/USDT", add_amount_currency=50.0, current_price=101.0)

    # 2. Si el precio cayó a $98.0 (SHORT en ganancia de +2.0%), el scale-in DEBE ejecutarse y conservar el valle mínimo ($98.0)
    res = isolated_daemon.broker.scale_in_position("BTC/USDT", add_amount_currency=49.0, current_price=98.0)
    assert res["added_amount"] == 49.0
    pos = isolated_daemon.broker.fetch_positions()[0]
    assert pos["peak_price"] == 98.0
    assert pos["be_armed"] == 1
    assert pos["current_stop_net_pct"] >= 0.15


def test_audit_f03_peluqueo_tp1_executes_only_once(isolated_daemon):
    """F-03: El peluqueo del 50% en TP1 debe marcar tp1_trimmed=1 y no volver a recortar recursivamente."""
    isolated_daemon.strategy = "nasdaq_araujo_vwap"
    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0, initial_tp_pct=2.0, initial_sl_pct=1.0)

    # 1. Precio alcanza $102.5 (+2.5% >= TP1 2.0%): recorta el 50% (queda qty=0.5) y marca tp1_trimmed=1
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 102.5}):
        liq1 = isolated_daemon._check_open_positions_protections()
    assert len(liq1) == 1
    assert liq1[0]["action"] == "PELUQUEO_TP1"
    pos = isolated_daemon.broker.fetch_positions()[0]
    assert pos["qty"] == 0.5
    assert pos["tp1_trimmed"] == 1

    # 2. Si el precio salta a $105.0 (>= 2 * TP1 = 4.0%), debe cerrar el 50% restante por Take Profit final en vez de recortar a 0.25
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 105.0}):
        liq2 = isolated_daemon._check_open_positions_protections()
    assert len(liq2) == 1
    assert liq2[0]["action"] == "TAKE_PROFIT"
    assert isolated_daemon.broker.fetch_positions() == []


def test_audit_f04_correlation_guard_blocks_4th_same_side_crypto(isolated_daemon):
    """F-04: Con max_positions=4, el Guardián de Correlación impide abrir una 4ta posición LONG en el mismo libro USDT."""
    isolated_daemon.max_positions = 4
    isolated_daemon.mode = "auto"
    isolated_daemon.broker.set_operating_capital("USDT", 800.0)

    isolated_daemon.broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0)
    isolated_daemon.broker.place_entry("ETH/USDT", "BUY", qty=1.0, price=100.0)
    isolated_daemon.broker.place_entry("SOL/USDT", "BUY", qty=1.0, price=100.0)
    assert len(isolated_daemon.broker.fetch_positions()) == 3

    isolated_daemon.symbol = "BNB/USDT"
    fake_analysis = {"signal": "COMPRAR", "reason": "4th correlated long", "strategy": "manual", "strategy_metrics": {}}
    with patch("backend.main.get_analysis", return_value=fake_analysis), \
         patch("backend.main.get_price", return_value={"symbol": "BNB/USDT", "price": 100.0}):
        isolated_daemon._execute_cycle()

    # Sigue en 3 posiciones porque la 4ta LONG correlacionada en USDT fue bloqueada
    assert len(isolated_daemon.broker.fetch_positions()) == 3


def test_drop_regime_limits_exposure_to_single_position(isolated_daemon):
    """Medida Inmediata 3 + Cupo Dual: En caídas bloquea una segunda altcoin correlacionada (máx 1 altcoin), permitiendo únicamente concurrencia BTC + 1 Activo hasta tope de 2."""
    isolated_daemon.max_positions = 4
    isolated_daemon.mode = "manual"
    isolated_daemon.symbol = "ETH/USDT"
    isolated_daemon.broker.set_operating_capital("USDT", 800.0)

    # 1. Ya existe 1 posición abierta en otra altcoin (SOL/USDT -> cupo altcoin ocupado)
    isolated_daemon.broker.place_entry("SOL/USDT", "BUY", qty=1.0, price=100.0)
    assert len(isolated_daemon.broker.fetch_positions()) == 1

    # 2. Intentar abrir una segunda altcoin (ETH/USDT) durante régimen de caídas
    fake_analysis = {
        "signal": "COMPRAR",
        "reason": "Rebote Z-Score tentador",
        "strategy": "mean_reversion_atr",
        "strategy_metrics": {"atr_14": 2.0, "relative_volume": 1.2},
    }

    def fake_market_open(sym):
        return sym == "ETH/USDT"

    with patch.object(isolated_daemon, "is_drop_regime_or_tactical_rebound", return_value=(True, "BTC bajo EMA200 1H")):
        with patch("backend.main.get_analysis", return_value=fake_analysis), \
             patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": 100.0}), \
             patch("backend.estrategias.registry.is_asset_market_open", side_effect=fake_market_open):
            isolated_daemon._execute_cycle()

    # Debe mantenerse en exactamente 1 sola posición (segunda altcoin bloqueada)
    assert len(isolated_daemon.broker.fetch_positions()) == 1
    assert "Límite de 1 posición" in isolated_daemon.last_reason


def test_trailing_runner_peluqueo_tp1_and_trailing_remainder(isolated_daemon):
    """
    Doctrina Cava / Kula Balam:
    1. trailing_trend_runner ejecuta Peluqueo 50% al tocar TP1 (R:R >= 1:2.0).
    2. El 50% remanente NO se cierra por TP rígido: queda vivo y es gobernado por el Trailing Stop sin techo.
    """
    isolated_daemon.strategy = "trailing_trend_runner"
    isolated_daemon.broker.place_entry(
        "BTC/USDT", "BUY", qty=1.0, price=100.0, initial_tp_pct=2.0, initial_sl_pct=1.0
    )

    # 1. Precio alcanza $102.5 (+2.5% >= TP1 2.0%): debe ejecutar Peluqueo del 50%
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 102.5}):
        liq1 = isolated_daemon._check_open_positions_protections()

    assert len(liq1) == 1
    assert liq1[0]["action"] == "PELUQUEO_TP1"
    positions = isolated_daemon.broker.fetch_positions()
    assert len(positions) == 1
    pos = positions[0]
    assert pos["qty"] == 0.5
    assert pos["tp1_trimmed"] == 1
    assert pos["be_armed"] == 1
    assert pos["current_stop_net_pct"] >= 0.15

    # 2. El precio sube a $105.0 (+5.0%): a diferencia de una estrategia con TP rígido,
    # el runner NO liquida por Take Profit; el 50% remanente sigue corriendo libre con Trailing Stop
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 105.0}):
        liq2 = isolated_daemon._check_open_positions_protections()

    assert len(liq2) == 0  # No liquidado por TP
    positions_after = isolated_daemon.broker.fetch_positions()
    assert len(positions_after) == 1
    assert positions_after[0]["qty"] == 0.5
    assert positions_after[0]["peak_price"] == 105.0


def test_candado_piso_costo_040_con_colchon_respiracion(isolated_daemon):
    """
    Regla General 1:
    Verifica que un avance bruto de +0.41% (ej. BTC de $77,448.48 a $77,767.16) arma inmediatamente
    el Candado de Piso de Costo Real (be_armed=1) situando el stop técnico en
    gross_target_for_net(0.05 + 0.03, fee=0.10, spread=0.05) (~+0.3807% bruto / ~$77,743.33),
    cubriendo el 100% de las comisiones + spread ida y vuelta más colchón anti-slippage,
    de modo que el cierre por Breakeven Real jamás termine en pérdida neta.
    """
    from backend.quant_risk import gross_target_for_net

    isolated_daemon.strategy = "kula_balam_cava_ruiz"
    isolated_daemon.broker.place_entry(
        "BTC/USDT", "BUY", qty=0.00129118, price=77448.48, initial_tp_pct=2.1, initial_sl_pct=0.6
    )
    expected_be_gross = round(gross_target_for_net(0.08, 0.10, 0.05), 4)
    expected_be_price = 77448.48 * (1.0 + expected_be_gross / 100.0)

    # 1. Precio toca $77,767.16 (+0.4115% bruto >= +0.40%): arma el Candado de Piso de Costo Real (+0.3807% bruto)
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 77767.16}):
        liq1 = isolated_daemon._check_open_positions_protections()
    assert len(liq1) == 0

    pos = isolated_daemon.broker.fetch_positions()[0]
    assert pos["be_armed"] == 1
    assert pos["current_stop_net_pct"] == pytest.approx(0.15, 0.01)
    cf = isolated_daemon.counterfactual_cache["BTC/USDT"]
    assert cf["active_stop_price"] == pytest.approx(expected_be_price, abs=1.0)

    # 2. Retroceso menor por encima del piso real ($77,755.00 > $77,743.33): NO cierra la operación
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 77755.00}):
        liq2 = isolated_daemon._check_open_positions_protections()
    assert len(liq2) == 0
    assert len(isolated_daemon.broker.fetch_positions()) == 1

    # 3. Caída a $77,742.00 (debajo de $77,743.33): ejecuta Breakeven Real con GANANCIA NETA POSITIVA tras comisiones
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 77742.00}):
        liq3 = isolated_daemon._check_open_positions_protections()
    assert len(liq3) == 1
    assert liq3[0]["action"] == "BREAKEVEN_REAL"
    assert len(isolated_daemon.broker.fetch_positions()) == 0
    assert liq3[0]["result"]["net_pnl"] > 0.10


def test_peluqueo_50_climax_rsi_70_con_ganancia_1pct(isolated_daemon):
    """
    Regla General 2:
    Verifica el Peluqueo del 50% por Clímax de RSI (RSI >= 70.0 condicionado a ganancia bruta >= +1.00%):
    - Si RSI >= 70 pero la ganancia es pequeña (< 1.00%, ej. +0.41%), NO recorta por centavos.
    - Si el precio pega un tirón a $78,300 (+1.10% bruto, antes del TP1 de +2.1%) con RSI >= 70.0,
      liquida el 50% (PELUQUEO_RSI70), asegura ganancia en mano y deja el 50% remanente corriendo libre.
    """
    import time
    isolated_daemon.strategy = "kula_balam_cava_ruiz"
    isolated_daemon.broker.place_entry(
        "BTC/USDT", "BUY", qty=0.00129118, price=77448.48, initial_tp_pct=2.1, initial_sl_pct=0.6
    )

    # Caso A: RSI en 71.5 pero avance de apenas +0.41% ($77,767.16 < +1.00%): NO debe peluquear
    isolated_daemon.symbol_indicators["BTC/USDT"] = {
        "rsi": 71.5,
        "atr_14": 250.0,
        "atr_pct": 0.32,
        "ts": time.time(),
    }
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 77767.16}):
        liq_early = isolated_daemon._check_open_positions_protections()
    assert len(liq_early) == 0
    pos_early = isolated_daemon.broker.fetch_positions()[0]
    assert pos_early["tp1_trimmed"] == 0

    # Caso B: Tirón a $78,300.00 (+1.10% bruto >= +1.00%, aún debajo de TP1 $79,074.90) con RSI 71.2 >= 70.0
    isolated_daemon.symbol_indicators["BTC/USDT"] = {
        "rsi": 71.2,
        "atr_14": 250.0,
        "atr_pct": 0.32,
        "ts": time.time(),
    }
    with patch("backend.main.get_price", return_value={"symbol": "BTC/USDT", "price": 78300.00}):
        liq_climax = isolated_daemon._check_open_positions_protections()

    assert len(liq_climax) == 1
    assert liq_climax[0]["action"] == "PELUQUEO_RSI70"
    pos_after = isolated_daemon.broker.fetch_positions()[0]
    assert pos_after["tp1_trimmed"] == 1
    assert pos_after["qty"] == pytest.approx(0.00129118 * 0.5, rel=1e-5)
    assert pos_after["be_armed"] == 1
    assert pos_after["current_stop_net_pct"] == 0.25


def test_donchian_breakout_1h_cierre_por_tp(isolated_daemon):
    """
    Verifica que donchian_breakout_1h liquide por Take Profit cuando el precio alcanza el objetivo (2.0x ATR).
    """
    isolated_daemon.strategy = "donchian_breakout_1h"
    isolated_daemon.broker.place_entry(
        "SOL/USDT",
        "BUY",
        qty=1.0,
        price=100.0,
        initial_tp_pct=2.0,
        initial_sl_pct=1.0,
        strategy="donchian_breakout_1h",
    )

    # Avance a +2.5% ($102.5, superando el TP de +2.0%): liquida por Take Profit
    with patch("backend.main.get_price", return_value={"symbol": "SOL/USDT", "price": 102.5}):
        liq_tp = isolated_daemon._check_open_positions_protections()
    assert len(liq_tp) == 1
    assert liq_tp[0]["action"] == "TAKE_PROFIT"
    assert len(isolated_daemon.broker.fetch_positions()) == 0


def test_donchian_breakout_1h_mid_exit_desactivado(isolated_daemon):
    """
    Verifica que MID_EXIT permanezca desactivado: un cruce por debajo de donchian_mid no liquida la posición.
    Las posiciones solo deben cerrarse por Stop Loss o Take Profit.
    """
    isolated_daemon.strategy = "donchian_breakout_1h"
    isolated_daemon.broker.place_entry(
        "SOL/USDT",
        "BUY",
        qty=1.0,
        price=100.0,
        initial_tp_pct=2.0,
        initial_sl_pct=1.0,
        strategy="donchian_breakout_1h",
    )

    # Precio en $99.5 (-0.5%), por encima del SL (-1.0%), no liquida por MID_EXIT
    with patch("backend.main.get_price", return_value={"symbol": "SOL/USDT", "price": 99.5}):
        liq = isolated_daemon._check_open_positions_protections()

    assert len(liq) == 0
    assert len(isolated_daemon.broker.fetch_positions()) == 1


def test_donchian_breakout_1h_cierre_por_stop_loss(isolated_daemon):
    """
    Verifica que el Stop Loss (1.0x ATR con piso 0.75%) liquide la posición al ser tocado.
    """
    isolated_daemon.strategy = "donchian_breakout_1h"
    isolated_daemon.broker.place_entry(
        "SOL/USDT",
        "BUY",
        qty=1.0,
        price=100.0,
        initial_tp_pct=2.0,
        initial_sl_pct=1.0,
        strategy="donchian_breakout_1h",
    )

    # Caída a $98.90 (-1.10% <= -1.00% SL)
    with patch("backend.main.get_price", return_value={"symbol": "SOL/USDT", "price": 98.90}):
        liq = isolated_daemon._check_open_positions_protections()

    assert len(liq) == 1
    assert "STOP_LOSS" in liq[0]["action"]
    assert len(isolated_daemon.broker.fetch_positions()) == 0


def test_daemon_whitelist_7_activos_patrol(isolated_daemon):
    isolated_daemon.mode = "smart"
    isolated_daemon.symbol = "SOL/USDT"
    isolated_daemon.timeframe = "4h"
    isolated_daemon.strategy = "donchian_breakout_1h"
    isolated_daemon.allowed_strategies = ["donchian_breakout_1h"]
    isolated_daemon.max_positions = 2

    analyzed_symbols = []

    def fake_analysis(**kwargs):
        sym = kwargs.get("symbol")
        analyzed_symbols.append(sym)
        return {"signal": "MANTENER", "reason": "No setup", "strategy": "donchian_breakout_1h", "strategy_metrics": {}}

    def fake_price(sym):
        return {"symbol": sym, "price": 100.0}

    with patch("backend.main.get_analysis", side_effect=fake_analysis), \
         patch("backend.main.get_price", side_effect=fake_price), \
         patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch.object(isolated_daemon, "is_stocks_evaluation_window", return_value=True), \
         patch("backend.entry_gate.get_btc_macro_status", return_value={"veto_active": False}):
        isolated_daemon._execute_cycle()

    # En modo smart con donchian_breakout_1h, patrulla los 7 activos validados
    for expected in ("SOL/USDT", "ETH/USDT", "AAPL", "AMD", "AVGO", "META", "MSFT"):
        assert expected in analyzed_symbols
    # Y excluye cualquier activo fuera de la lista blanca
    for excluded in ("NVDA", "SPY", "QQQ", "BTC/USDT", "XRP/USDT"):
        assert excluded not in analyzed_symbols


def test_daemon_strategy_risk_pct_sizing_and_expanded_slot_cap(isolated_daemon):
    """
    Verifica que strategy_risk_pcts calcula la cantidad por paridad de riesgo en Stop Loss (1.5%),
    ampliando el tope por slot hasta 95% (en 1 cupo) y 60% (en 2 cupos) respetando fees.
    """
    isolated_daemon.broker.set_operating_capital("USDT", 1000.0)
    isolated_daemon.mode = "fixed"
    isolated_daemon.symbol = "SOL/USDT"
    isolated_daemon.timeframe = "4h"
    isolated_daemon.strategy = "auto"
    isolated_daemon.allowed_strategies = ["donchian_breakout_1h"]
    isolated_daemon.strategy_risk_pcts = {"donchian_breakout_1h": 1.5}
    isolated_daemon.max_positions = 1  # 1 solo cupo habilitado -> tope ampliado a 95%

    fake_price = {"symbol": "SOL/USDT", "price": 100.0}
    fake_analysis = {
        "signal": "COMPRAR",
        "reason": "Setup Donchian 4H con R:R >= 2",
        "strategy": "donchian_breakout_1h",
        "strategy_metrics": {
            "auto_orchestrator": {"selected_strategy": "donchian_breakout_1h"},
            "sl_gross_pct": 1.5,
            "tp_gross_pct": 3.8,
            "atr_14": 1.0,
            "relative_volume": 1.5,
        },
        "candlestick_audit": {},
    }

    with patch("backend.main.get_analysis", return_value=fake_analysis), \
         patch("backend.main.get_price", return_value=fake_price), \
         patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch("backend.entry_gate.entry_gate_failures", return_value=[]):
        isolated_daemon._execute_cycle()

    positions = isolated_daemon.broker.fetch_positions()
    assert len(positions) == 1
    pos = positions[0]
    # Con $1000 y riesgo 1.5% ($15) con SL bruto 1.5% (~1.79% neto tras fee 0.1% + spread 0.05%):
    # Capital asignado = 15 / 0.0179 ≈ $834 USDT (> antiguo tope de 35% = $350, y <= 95% = $950)
    assert pos["cost_basis"] > 600.0
    assert pos["cost_basis"] <= 950.0


def test_daemon_strategy_risk_pct_forex_1_5_opens_valid_notional(isolated_daemon):
    """
    Verifica que un riesgo SL del 1.5% sobre EURUSD=X calcula una posición en USD válida (>= $5)
    y nunca es bloqueada como orden microscópica.
    """
    isolated_daemon.broker.set_operating_capital("USD", 500.0)
    isolated_daemon.mode = "fixed"
    isolated_daemon.symbol = "EURUSD=X"
    isolated_daemon.timeframe = "1h"
    isolated_daemon.strategy = "auto"
    isolated_daemon.allowed_strategies = ["cava_fallo_macd_eurusd_1h"]
    isolated_daemon.strategy_risk_pcts = {"cava_fallo_macd_eurusd_1h": 1.5}
    isolated_daemon.max_positions = 2  # Multi-slot -> tope 60% ($600 sobre $1000, acotado a op_cap $500)

    fake_price = {"symbol": "EURUSD=X", "price": 1.12}
    fake_analysis = {
        "signal": "COMPRAR",
        "reason": "Cava Fallo MACD Forex 1H",
        "strategy": "cava_fallo_macd_eurusd_1h",
        "strategy_metrics": {
            "auto_orchestrator": {"selected_strategy": "cava_fallo_macd_eurusd_1h"},
            "sl_gross_pct": 0.22,
            "tp_gross_pct": 0.50,
            "atr_14": 0.0018,
            "relative_volume": 1.0,
        },
        "candlestick_audit": {},
    }

    with patch("backend.main.get_analysis", return_value=fake_analysis), \
         patch("backend.main.get_price", return_value=fake_price), \
         patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch("backend.entry_gate.entry_gate_failures", return_value=[]):
        isolated_daemon._execute_cycle()

    positions = isolated_daemon.broker.fetch_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "EURUSD=X"
    # Topeado por op_cap (~$500) con reserva de margen segura
    assert positions[0]["cost_basis"] >= 250.0
    assert positions[0]["qty"] >= 200.0


def test_daemon_vault_slot_alloc_pct_25_with_sl_loss_cap(tmp_path, monkeypatch):
    """
    Verifica el modelo de Bóveda 25/50/100:
    Con $100 en Bóveda USDT y slot_alloc_pct=25% ($25 por operación):
    1) SL normal (-3.0% bruto) invierte los $25.00 exactos (pérdida en SL ≈ -$0.83 < $2.50 máx).
    2) SL muy amplio (-15.0% bruto) recorta el nocional para no superar $2.50 de pérdida máxima en SL.
    """
    from backend.quant_risk import net_return_after_costs

    csv_file = str(tmp_path / "test_slot_trades.csv")
    monkeypatch.setenv("TRADING_OLLAMA_CSV_PATH", csv_file)
    db_file = str(tmp_path / "test_slot_ledger.sqlite3")
    monkeypatch.setenv("TRADING_LEDGER_DB_PATH", db_file)
    bias_file = str(tmp_path / "test_slot_bias.json")
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", bias_file)

    broker = PaperBrokerAdapter(initial_vault_usd=100.0, db_path=db_file, fee_pct=0.10)
    daemon = TraderDaemon(broker=broker)
    daemon.mode = "fixed"
    daemon.symbol = "SOL/USDT"
    daemon.timeframe = "4h"
    daemon.strategy = "auto"
    daemon.allowed_strategies = ["donchian_breakout_1h"]
    daemon.slot_alloc_pct = 25.0
    daemon.max_positions = 4

    # Caso 1: SL ATR -3.02% -> usa los $25.00 del slot completos
    fake_price = {"symbol": "SOL/USDT", "price": 100.0}
    fake_analysis = {
        "signal": "COMPRAR",
        "reason": "Setup Donchian 4H",
        "strategy": "donchian_breakout_1h",
        "strategy_metrics": {
            "auto_orchestrator": {"selected_strategy": "donchian_breakout_1h"},
            "sl_gross_pct": 3.02,
            "tp_gross_pct": 7.85,
            "atr_14": 1.89,
            "relative_volume": 1.5,
        },
        "candlestick_audit": {},
    }
    with patch("backend.main.get_analysis", return_value=fake_analysis), \
         patch("backend.main.get_price", return_value=fake_price), \
         patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch("backend.entry_gate.entry_gate_failures", return_value=[]):
        daemon._execute_cycle()

    pos = daemon.broker.fetch_positions()[0]
    assert abs(pos["cost_basis"] - 25.0) < 0.05
    sl_net_abs = abs(net_return_after_costs(-3.02, 0.10, 0.05))
    assert (pos["cost_basis"] * sl_net_abs / 100.0) <= 2.50 + 1e-6

    # Caso 2: SL muy amplio (-15.0% bruto) en ETH -> recorta el tamaño para no arriesgar más de $2.50 en SL
    daemon.broker.flatten("SOL/USDT", current_price=100.0, exit_reason="Test Reset")
    daemon.cooldown_per_symbol.clear()
    daemon.symbol = "ETH/USDT"
    fake_price_eth = {"symbol": "ETH/USDT", "price": 2000.0}
    fake_analysis_wide = {
        **fake_analysis,
        "strategy_metrics": {
            "auto_orchestrator": {"selected_strategy": "donchian_breakout_1h"},
            "sl_gross_pct": 15.0,
            "tp_gross_pct": 35.0,
            "atr_14": 100.0,
            "relative_volume": 1.5,
        },
    }
    with patch("backend.main.get_analysis", return_value=fake_analysis_wide), \
         patch("backend.main.get_price", return_value=fake_price_eth), \
         patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch("backend.entry_gate.entry_gate_failures", return_value=[]):
        daemon._execute_cycle()

    pos2 = daemon.broker.fetch_positions()[0]
    sl_net_wide = abs(net_return_after_costs(-15.0, 0.10, 0.05))
    # Pérdida en SL estrictamente <= $2.50 (pese a SL de 15%)
    assert pos2["cost_basis"] < 25.0
    assert (pos2["cost_basis"] * sl_net_wide / 100.0) <= 2.50 + 0.01


def test_daemon_auto_active_strategies_uncapped_trailing_runner(isolated_daemon):
    """
    Bajo Cerebro Kula Autónomo ('auto'):
    1. Las estrategias con Peluqueo/Trailing explícito (kula_balam_cava_ruiz, trailing_trend_runner)
       operan SIN TECHO: peluquean 50% en TP1 y dejan correr el remanente con Trailing Stop móvil.
    2. Las estrategias certificadas en Lab con BREAKEVEN_RR == 0.0 y TRAILING_ATR_MULT == 0.0
       (squeeze_dual_eth_4h_slot1, donchian_breakout_1h) liquidan 100% por TAKE_PROFIT sin peluqueo ni trailing.
    """
    for idx, strat_id in enumerate(["kula_balam_cava_ruiz", "trailing_trend_runner"]):
        sym = "ETH/USDT" if idx == 0 else "SOL/USDT"
        isolated_daemon.strategy = "auto"
        isolated_daemon.broker.place_entry(
            sym,
            "BUY",
            qty=1.0,
            price=100.0,
            initial_tp_pct=3.0,
            initial_sl_pct=1.5,
            strategy=strat_id,
        )

        # 1. Alcanza +3.5% ($103.50 >= TP1 3.0%): arma Breakeven/Cerrojo y ejecuta Peluqueo 50%
        with patch("backend.main.get_price", return_value={"symbol": sym, "price": 103.50}), \
             patch("backend.main.get_analysis", return_value={"rsi": 58.0}):
            liq1 = isolated_daemon._check_open_positions_protections()
        assert len(liq1) == 1
        assert liq1[0]["action"] == "PELUQUEO_TP1"

        # 2. Sigue subiendo muy por encima del TP (+10.0% -> $110.00): NO liquida por TAKE_PROFIT; Stop Móvil sube fuerte
        with patch("backend.main.get_price", return_value={"symbol": sym, "price": 110.00}), \
             patch("backend.main.get_analysis", return_value={"rsi": 62.0}):
            liq2 = isolated_daemon._check_open_positions_protections()
        assert liq2 == []
        pos = isolated_daemon.broker.fetch_positions()[0]
        assert pos["qty"] == 0.5
        assert pos["trail_active"] == 1
        assert pos["current_stop_net_pct"] > 7.5

        # 3. Retrocede hacia el Trailing Stop subido ($107.00): cierra por TRAILING_STOP con ganancia alta (no por TP fijo)
        with patch("backend.main.get_price", return_value={"symbol": sym, "price": 107.00}), \
             patch("backend.main.get_analysis", return_value={"rsi": 52.0}):
            liq3 = isolated_daemon._check_open_positions_protections()
        assert len(liq3) == 1
        assert liq3[0]["action"] == "TRAILING_STOP"
        assert liq3[0]["result"]["net_pnl"] > 3.0
        assert isolated_daemon.broker.fetch_positions() == []

    # 4. Estrategias de catálogo sin trailing (TRAILING_ATR_MULT == 0.0) y donchian_breakout_1h cierran 100% en TP
    for idx, strat_id in enumerate(["squeeze_dual_eth_4h_slot1", "donchian_breakout_1h"]):
        sym = "ETH/USDT" if idx == 0 else "SOL/USDT"
        isolated_daemon.strategy = "auto"
        isolated_daemon.broker.place_entry(
            sym,
            "BUY",
            qty=1.0,
            price=100.0,
            initial_tp_pct=3.0,
            initial_sl_pct=1.5,
            strategy=strat_id,
        )
        with patch("backend.main.get_price", return_value={"symbol": sym, "price": 103.50}), \
             patch("backend.main.get_analysis", return_value={"rsi": 58.0}):
            liq_tp = isolated_daemon._check_open_positions_protections()
        assert len(liq_tp) == 1
        assert liq_tp[0]["action"] == "TAKE_PROFIT"
        assert isolated_daemon.broker.fetch_positions() == []


def test_daemon_auto_forex_scaled_breakeven_and_trailing(isolated_daemon):
    """
    En Forex (=X, EURUSD=X) bajo Cerebro Kula ('auto'):
    1. Para `cava_fallo_macd_eurusd_1h` (BREAKEVEN_RR=0.0, TRAILING_ATR_MULT=1.8):
       NO arma Breakeven prematuro en +0.18%, pero sí activa Peluqueo/Trailing escalado a Forex.
    2. Para `kula_balam_cava_ruiz` (con BE habilitado): arma Breakeven Real Forex en +0.18%.
    """
    isolated_daemon.broker.set_operating_capital("USD", 500.0)
    isolated_daemon.strategy = "auto"
    isolated_daemon.broker.place_entry(
        "EURUSD=X",
        "BUY",
        qty=100.0,
        price=1.1200,
        initial_tp_pct=0.45,
        initial_sl_pct=0.21,
        strategy="cava_fallo_macd_eurusd_1h",
    )

    # 1. Avance +0.18% ($1.12202 < 1R=0.21%): como BREAKEVEN_RR == 0.0, NO arma BE prematuro
    with patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch("backend.main.get_price", return_value={"symbol": "EURUSD=X", "price": 1.12202}), \
         patch("backend.main.get_analysis", return_value={"rsi": 56.0}):
        liq1 = isolated_daemon._check_open_positions_protections()
    assert liq1 == []
    pos1 = isolated_daemon.broker.fetch_positions()[0]
    assert pos1["be_armed"] == 0
    assert pos1["trail_active"] == 0

    # 2. Avance +0.50% ($1.12560 >= TP1 0.45%): TRAILING_ATR_MULT=1.8 habilita Peluqueo 50% en EURUSD
    with patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch("backend.main.get_price", return_value={"symbol": "EURUSD=X", "price": 1.12560}), \
         patch("backend.main.get_analysis", return_value={"rsi": 60.0}):
        liq2 = isolated_daemon._check_open_positions_protections()
    assert len(liq2) == 1
    assert liq2[0]["action"] == "PELUQUEO_TP1"

    # 3. Rally Forex a +0.85% ($1.12952): corre SIN TECHO y Trailing Stop acompaña de cerca (<0.20% debajo del pico)
    with patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch("backend.main.get_price", return_value={"symbol": "EURUSD=X", "price": 1.12952}), \
         patch("backend.main.get_analysis", return_value={"rsi": 64.0}):
        liq3 = isolated_daemon._check_open_positions_protections()
    assert liq3 == []
    pos3 = isolated_daemon.broker.fetch_positions()[0]
    assert pos3["trail_active"] == 1
    assert pos3["current_stop_net_pct"] > 0.55

    # 4. Retroceso a $1.12650: cierra por TRAILING_STOP protegiendo +0.55%+ neto
    with patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch("backend.main.get_price", return_value={"symbol": "EURUSD=X", "price": 1.12650}), \
         patch("backend.main.get_analysis", return_value={"rsi": 50.0}):
        liq4 = isolated_daemon._check_open_positions_protections()
    assert len(liq4) == 1
    assert liq4[0]["action"] == "TRAILING_STOP"
    assert liq4[0]["result"]["net_pnl"] > 0

    # 5. Estrategia con BE habilitado (kula_balam_cava_ruiz) en Forex SÍ arma BE Real en +0.18%
    isolated_daemon.broker.place_entry(
        "EURUSD=X",
        "BUY",
        qty=100.0,
        price=1.1200,
        initial_tp_pct=0.45,
        initial_sl_pct=0.21,
        strategy="kula_balam_cava_ruiz",
    )
    with patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
         patch("backend.main.get_price", return_value={"symbol": "EURUSD=X", "price": 1.12202}), \
         patch("backend.main.get_analysis", return_value={"rsi": 56.0}):
        liq_be = isolated_daemon._check_open_positions_protections()
    assert liq_be == []
    assert isolated_daemon.broker.fetch_positions()[0]["be_armed"] == 1


def test_vault_book_slot_isolation_drop_regime_usdt_allows_usd_stocks(tmp_path, monkeypatch):
    """
    Aislamiento contable por bóveda/moneda:
    1) Con BNB/USDT SHORT abierta (1/1 en Bóveda USDT bajo caída de BTC), otra altcoin ETH/USDT queda bloqueada.
    2) Simultáneamente, la Bóveda USD ($500 USD) conserva sus slots libres para evaluar y operar acciones US (AMD)
       sin bloqueo cruzado desde Cripto.
    """
    db_file = str(tmp_path / "vault_isolation_ledger.sqlite3")
    monkeypatch.setenv("TRADING_LEDGER_DB_PATH", db_file)
    monkeypatch.setenv("TRADING_OLLAMA_CSV_PATH", str(tmp_path / "vault_isolation_trades.csv"))
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", str(tmp_path / "vault_isolation_bias.json"))

    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=db_file, fee_pct=0.10)
    broker.set_operating_capital("USDT", 250.0)
    broker.set_operating_capital("USD", 500.0)
    daemon = TraderDaemon(broker=broker)
    daemon.max_positions = 4
    daemon.mode = "smart"
    daemon.symbol = "BNB/USDT"
    daemon.strategy = "auto"
    daemon.allowed_strategies = ["kula_balam_cava_ruiz", "donchian_breakout_1h", "squeeze_dual_eth_4h_slot1"]
    daemon.slot_alloc_pct = 25.0

    # Posición previa en USDT ocupando el único slot permitido para altcoins durante caída BTC
    broker.place_entry("BNB/USDT", "SHORT", qty=0.04, price=670.0, initial_tp_pct=4.5, initial_sl_pct=1.8)

    # Verificar que slots_by_book refleja USDT lleno (1/1, 0 free) y USD independiente libre (0/4, 3 free)
    with patch("backend.entry_gate.get_btc_macro_status", return_value={"veto_active": True, "reason": "BTC < EMA200"}):
        status = daemon.get_status()
        assert status["slots_by_book"]["USDT"]["free"] == 0
        assert status["slots_by_book"]["USD"]["free"] == 3
        assert status["slots_by_book"]["USD"]["in_drop"] is False

        # ETH/USDT no puede abrir segundo cupo altcoin USDT; AMD sí entra en evaluación y abre en libro USD
        def fake_analysis(**kwargs):
            sym = kwargs["symbol"]
            if sym == "AMD":
                return {
                    "signal": "COMPRAR",
                    "reason": "Confluencia Kula Balam 1D/1H en AMD",
                    "strategy": "donchian_breakout_1h",
                    "strategy_metrics": {
                        "auto_orchestrator": {"selected_strategy": "donchian_breakout_1h"},
                        "tp_gross_pct": 4.2,
                        "sl_gross_pct": 1.4,
                        "atr_14": 8.0,
                        "relative_volume": 1.6,
                    },
                    "candlestick_audit": {},
                }
            if sym == "ETH/USDT":
                return {
                    "signal": "COMPRAR",
                    "reason": "Intento altcoin bloqueado",
                    "strategy": "squeeze_dual_eth_4h_slot1",
                    "strategy_metrics": {
                        "auto_orchestrator": {"selected_strategy": "squeeze_dual_eth_4h_slot1"},
                        "tp_gross_pct": 4.0,
                        "sl_gross_pct": 1.5,
                        "atr_14": 30.0,
                    },
                    "candlestick_audit": {},
                }
            return {"signal": "MANTENER", "reason": "Sin señal", "indicators": {}, "strategy_metrics": {}, "fee_info": {}}

        def fake_price(sym):
            return {"symbol": sym, "price": 510.0 if sym == "AMD" else (670.0 if sym == "BNB/USDT" else 2100.0)}

        with patch.object(daemon, "is_stocks_evaluation_window", return_value=True), \
             patch("backend.main.get_analysis", side_effect=fake_analysis), \
             patch("backend.main.get_price", side_effect=fake_price), \
             patch("backend.estrategias.registry.is_asset_market_open", return_value=True), \
             patch("backend.entry_gate.entry_gate_failures", return_value=[]):
            daemon._execute_cycle()

    positions = broker.fetch_positions()
    symbols_open = {p["symbol"] for p in positions}
    assert "BNB/USDT" in symbols_open
    assert "AMD" in symbols_open
    assert "ETH/USDT" not in symbols_open



def test_daemon_clockwork_wakeup_and_closed_candle_dedup(isolated_daemon):
    """
    Verifica sincronización Relojito del daemon:
    1. Despierta ~3s después de cada cierre de vela (+5s con posiciones abiertas).
    2. Evalúa exactamente 1 vez cada vela cerrada por (símbolo, temporalidad) sin repetir escaneos inútiles.
    3. La consulta del navegador nunca inhibe ni saltea la evaluación del daemon.
    """
    import time

    isolated_daemon.symbol = "BNB/USDT"
    isolated_daemon.timeframe = "1h"
    isolated_daemon.strategy = "donchian_breakout_1h"
    isolated_daemon.mode = "fixed"

    # Con 1h: 5s antes del cierre (t=3595) debe esperar exactamente 8.0s hasta 3603s (+3s asentamiento)
    assert isolated_daemon._compute_next_wakeup_delay(has_open_positions=False, now_ts=3595.0) == pytest.approx(8.0)
    # 1s después del cierre (t=3601) aterriza en 3603s (2.0s)
    assert isolated_daemon._compute_next_wakeup_delay(has_open_positions=False, now_ts=3601.0) == pytest.approx(2.0)
    # Con posición abierta, nunca duerme más de 5.0s para custodiar SL/Trailing
    assert isolated_daemon._compute_next_wakeup_delay(has_open_positions=True, now_ts=1200.0) == pytest.approx(5.0)

    # Deduplicación por vela cerrada en _execute_cycle + inmunidad a actividad del navegador
    isolated_daemon.strategy = "manual"
    isolated_daemon.notify_browser_activity(macro="", symbol="BNB/USDT")
    closed_open_ts = ((int(time.time()) // 3600) - 1) * 3600
    eval_calls = []

    def fake_analysis(**kwargs):
        eval_calls.append(kwargs.get("symbol"))
        return {
            "signal": "MANTENER",
            "reason": "Cierre confirmado neutral",
            "signal_candle_ts": closed_open_ts,
            "indicators": {},
            "strategy_metrics": {},
            "fee_info": {},
        }

    with patch("backend.main.get_analysis", side_effect=fake_analysis), \
         patch("backend.main.get_price", return_value={"symbol": "BNB/USDT", "price": 677.01}), \
         patch("backend.estrategias.registry.is_asset_market_open", return_value=True):
        isolated_daemon._execute_cycle()
        assert eval_calls == ["BNB/USDT"]

        # Segunda pasada dentro de la MISMA vela cerrada: no repite llamada costosa
        before_cycle = isolated_daemon.last_cycle_ts
        isolated_daemon._execute_cycle()
        assert eval_calls == ["BNB/USDT"]
        assert isolated_daemon.last_cycle_ts >= before_cycle


def test_kula_cava_sol_1h_and_multitimeframe_buckets(isolated_daemon):
    """
    Camino B:
    1. kula_cava_sol_1h está registrada en catálogo principal con native_timeframe='1h',
       activo_default='SOL/USDT' y supera el HealthWatchdog sintético en GREEN.
    2. En modo 'auto', TraderDaemon evalúa SOL/USDT en paralelo en '4h' (Donchian) y
       '1h' (kula_cava_sol_1h), aislando fórmulas específicas de otros pares (ETH/EURUSD).
    """
    from backend.estrategias.registry import get_strategy
    from backend.health_watchdog import HealthWatchdog

    st = get_strategy("kula_cava_sol_1h")
    assert st is not None
    assert st.native_timeframe == "1h"
    assert st.activo_default == "SOL/USDT"

    wd = HealthWatchdog()
    probe = wd.probe_active_strategies(["kula_cava_sol_1h"], force=True)
    assert probe["status"] == "GREEN"
    assert probe["passed"] == 1

    allowed = [
        "kula_cava_sol_1h",
        "1_donchian_breakout_sol_4h",
        "2_squeeze_dual_eth_4h",
        "donchian_breakout_1h",
        "cava_fallo_macd_eurusd_1h_slot1",
    ]
    sol_buckets = dict(isolated_daemon._resolve_auto_timeframe_buckets("SOL/USDT", allowed))
    assert "1h" in sol_buckets and "4h" in sol_buckets
    assert sol_buckets["1h"] == ["kula_cava_sol_1h"]
    assert "1_donchian_breakout_sol_4h" in sol_buckets["4h"]
    assert "2_squeeze_dual_eth_4h" not in sol_buckets["4h"]
    assert "cava_fallo_macd_eurusd_1h_slot1" not in sol_buckets["1h"]

    eth_buckets = dict(isolated_daemon._resolve_auto_timeframe_buckets("ETH/USDT", allowed))
    assert "1h" not in eth_buckets
    assert "2_squeeze_dual_eth_4h" in eth_buckets["4h"]
    assert "kula_cava_sol_1h" not in eth_buckets.get("1h", []) and "kula_cava_sol_1h" not in eth_buckets["4h"]

    # Verificar evaluación simultánea 4h + 1h sobre SOL/USDT en _execute_cycle
    isolated_daemon.mode = "manual"
    isolated_daemon.symbol = "SOL/USDT"
    isolated_daemon.timeframe = "4h"
    isolated_daemon.strategy = "auto"
    isolated_daemon.allowed_strategies = ["kula_cava_sol_1h", "1_donchian_breakout_sol_4h"]

    calls = []

    def fake_analysis(**kwargs):
        calls.append((kwargs.get("symbol"), kwargs.get("timeframe"), tuple(kwargs.get("allowed_strategies") or [])))
        return {
            "signal": "MANTENER",
            "reason": "Evaluado",
            "indicators": {},
            "strategy_metrics": {},
            "fee_info": {},
        }

    with patch("backend.main.get_analysis", side_effect=fake_analysis), \
         patch("backend.main.get_price", return_value={"symbol": "SOL/USDT", "price": 73.0}), \
         patch("backend.estrategias.registry.is_asset_market_open", return_value=True):
        isolated_daemon._execute_cycle()

    assert calls == [
        ("SOL/USDT", "4h", ("1_donchian_breakout_sol_4h",)),
        ("SOL/USDT", "1h", ("kula_cava_sol_1h",)),
    ]


def test_operador_presente_catalogo_registro_y_watchdog():
    """Verifica el catálogo presencial 1H, registro dinámico y HealthWatchdog en verde."""
    from backend.estrategias.registry import get_strategy
    from backend.health_watchdog import HealthWatchdog

    client = TestClient(main.app)
    resp = client.get("/api/catalogo_formulas")
    assert resp.status_code == 200
    data = resp.json()

    operador = data.get("operador_presente") or []
    operador_by_id = {item["id"]: item for item in operador}
    expected_tfs = {
        "kula_cava_sol_1h": "1h",
        "kula_cava_eth_1h": "1h",
        "cava_fallo_macd_eurusd_1h": "1h",
        "fractal_squeeze_15m": "15m",
        "mtf_presencial_15m": "15m",
        "mtf_presencial_5m": "5m",
    }
    for sid, exp_tf in expected_tfs.items():
        assert sid in operador_by_id, f"Falta {sid} en operador_presente"
        assert operador_by_id[sid]["timeframe"] == exp_tf

    # Verificar que no contaminan el panel autónomo principal
    principal_ids = {item["id"] for item in (data.get("panel_principal") or [])}
    assert "fractal_squeeze_15m" not in principal_ids
    assert "mtf_presencial_15m" not in principal_ids
    assert "mtf_presencial_5m" not in principal_ids

    eth_strat = get_strategy("kula_cava_eth_1h")
    assert eth_strat is not None
    assert getattr(eth_strat, "activo_default", "") == "ETH/USDT"
    assert getattr(eth_strat, "native_timeframe", "") == "1h"

    for mtf_id, exp_tf in (("mtf_presencial_15m", "15m"), ("mtf_presencial_5m", "5m")):
        m_strat = get_strategy(mtf_id)
        assert m_strat is not None
        assert getattr(m_strat, "activo_default", "") == "ETH/USDT"
        assert getattr(m_strat, "native_timeframe", "") == exp_tf

    probe = HealthWatchdog().probe_active_strategies(list(expected_tfs.keys()), force=True)
    assert probe["status"] == "GREEN", f"HealthWatchdog no devolvió GREEN: {probe}"


def test_daemon_presencial_start_stop_preserva_allowed_strategies(isolated_daemon):
    """start_scalping y stop_scalping deben respaldar y restaurar allowed_strategies y slot_alloc_pct."""
    original_allowed = ["kula_cava_sol_1h", "1_donchian_breakout_sol_4h"]
    isolated_daemon.symbol = "SOL/USDT"
    isolated_daemon.timeframe = "4h"
    isolated_daemon.strategy = "auto"
    isolated_daemon.mode = "manual"
    isolated_daemon.slot_alloc_pct = 25.0
    isolated_daemon.allowed_strategies = list(original_allowed)

    with patch.object(isolated_daemon, "_run_loop", return_value=None):
        st_start = isolated_daemon.start_scalping(
            symbol="ETH/USDT",
            strategy="kula_cava_eth_1h",
            timeframe="5m",
            slot_alloc_pct=50.0,
        )
        assert st_start["active"] is True
        assert st_start["timeframe"] == "1h"
        assert st_start["slot_alloc_pct"] == 50.0
        assert isolated_daemon.slot_alloc_pct == 50.0
        assert isolated_daemon.allowed_strategies == ["kula_cava_eth_1h"]
        assert isolated_daemon.symbol == "ETH/USDT"
        assert isolated_daemon.timeframe == "1h"

        st_stop = isolated_daemon.stop_scalping()
        assert st_stop["status"] == "restored"
        assert isolated_daemon.allowed_strategies == original_allowed
        assert isolated_daemon.slot_alloc_pct == 25.0
        assert isolated_daemon.symbol == "SOL/USDT"
        assert isolated_daemon.timeframe == "4h"
        assert isolated_daemon.strategy == "auto"

    isolated_daemon.is_running = False


def test_mtf_presencial_diagnostic_emite_telemetria_real_sin_alterar_reglas():
    """mtf_presencial_15m y mtf_presencial_5m reportan Close, ADX1H, Cruces1H, Fibo y bloqueo real sin cambiar formula_matematica."""
    import numpy as np
    import pandas as pd
    from pathlib import Path
    from backend.estrategias.catalog_adapter import CatalogFormulaStrategy

    # 800 velas de 5m (~66.6h -> >= 55 velas 1H) en rango lateral oscilante (ADX1H < 18)
    idx = pd.date_range("2026-11-10 00:00:00+00:00", periods=800, freq="5min")
    t = np.arange(800, dtype=float)
    base_px = 1800.0 + 4.0 * np.sin(t / 12.0)
    df_5m = pd.DataFrame({
        "timestamp": (idx.as_unit("ns").asi8 // 1_000_000),
        "open": base_px - 0.5,
        "high": base_px + 2.5,
        "low": base_px - 2.5,
        "close": base_px + 0.5,
        "volume": np.full(800, 1200.0),
    })

    cat_dir = Path(__file__).resolve().parent.parent / "backend" / "estrategias" / "catalogo" / "operador_presente"
    for strat_id, fname, tf, fibo_lbl in [
        ("mtf_presencial_15m", "mtf_presencial_15m.py", "15m", "0.48-0.75"),
        ("mtf_presencial_5m", "mtf_presencial_5m.py", "5m", "0.50-0.75"),
    ]:
        df_sub = df_5m.copy()
        if tf == "15m":
            idx15 = pd.date_range("2026-11-05 00:00:00+00:00", periods=400, freq="15min")
            t15 = np.arange(400, dtype=float)
            px15 = 1800.0 + 5.0 * np.sin(t15 / 6.0)
            df_sub = pd.DataFrame({
                "timestamp": (idx15.as_unit("ns").asi8 // 1_000_000),
                "open": px15 - 0.5,
                "high": px15 + 3.0,
                "low": px15 - 3.0,
                "close": px15 + 0.5,
                "volume": np.full(400, 2000.0),
            })

        strat = CatalogFormulaStrategy({"id": strat_id, "timeframe": tf, "activo_default": "ETH/USDT"}, cat_dir / fname)
        mod = strat._load_module()
        ok_before = mod.formula_matematica(df_sub.copy(), len(df_sub) - 1)

        ind = {
            "symbol": "ETH/USDT",
            "timeframe": tf,
            "latest": df_sub.iloc[-1].to_dict(),
            "live_price": float(df_sub["close"].iloc[-1]),
            "atr_14": 5.0,
            "relative_volume": 1.0,
        }
        metrics, _, eligible, failures, _ = strat.evaluar(ind, 2.0, 1.0, 0.10, 0.05, 0.5, 0.3, 2.0, df=df_sub)
        ok_after = mod.formula_matematica(df_sub.copy(), len(df_sub) - 1)

        assert ok_after == ok_before
        assert eligible is False
        tele = metrics.get("presencial_telemetry", "")
        assert tele == failures[0]
        assert f"[ETH/USDT {tf}] Close $" in tele
        assert "ADX1H:" in tele and "(<18)" in tele
        assert "Cruces1H:" in tele
        assert f"Fibo:" in tele and fibo_lbl in tele
        assert "Bloqueo:" in tele and "ADX1H<18" in tele


def test_daemon_presencial_actualiza_last_reason_y_limpia_cache_al_iniciar(isolated_daemon, caplog):
    """Al iniciar sesión presencial limpia caché de vela y registra en last_reason y log la telemetría completa."""
    import logging

    isolated_daemon._evaluated_candles[("ETH/USDT", "5m")] = {
        "signal_candle_ts": 123456,
        "next_close_due_ts": 9999999999.0,
        "config_sig": ("mtf_presencial_5m",),
    }
    with patch.object(isolated_daemon, "_run_loop", return_value=None):
        isolated_daemon.start_scalping(
            symbol="ETH/USDT",
            strategy="mtf_presencial_5m",
            timeframe="5m",
            slot_alloc_pct=100.0,
        )

    assert ("ETH/USDT", "5m") not in isolated_daemon._evaluated_candles
    assert isolated_daemon._wakeup_event.is_set() is True

    tele_espera = (
        "[ETH/USDT 5m] Close $1794.79 | ADX1H: 14.06 (<18) | Cruces1H: 4 (>3) | "
        "Fibo: 0.455 (meta 0.50-0.75, SHORT) | Bloqueo: ADX1H<18, Cruces1H>3, Fibo<0.50 -> En espera"
    )
    fake_hold = {
        "signal": "MANTENER",
        "reason": "[Antigravity Operador]: wrapper genérico largo que debe reemplazarse en presencial.",
        "signal_candle_ts": 1795009500,
        "strategy_metrics": {
            "atr_14": 4.2,
            "presencial_telemetry": tele_espera,
        },
        "indicators": {"rsi": 48.0, "atr_14": 4.2},
    }

    with caplog.at_level(logging.INFO):
        with patch("backend.main.get_analysis", return_value=fake_hold), \
             patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": 1794.79}):
            isolated_daemon._execute_cycle()

    assert isolated_daemon.last_signal == "MANTENER"
    assert isolated_daemon.last_reason == tele_espera
    assert any(tele_espera in rec.message and "KULA CEREBRO" in rec.message for rec in caplog.records)

    # Ahora probar candidata que pasa fórmula pero es vetada por compuerta de entrada
    isolated_daemon._evaluated_candles.pop(("ETH/USDT", "5m"), None)
    fake_buy = {
        "signal": "COMPRAR",
        "reason": "Candidata alcista",
        "signal_candle_ts": 1795009800,
        "strategy_metrics": {
            "tp_gross_pct": 2.4,
            "sl_gross_pct": 1.0,
            "atr_14": 4.2,
            "relative_volume": 0.40,
            "presencial_telemetry": "[ETH/USDT 5m] Close $1810.00 | ADX1H: 24.50 (>=18) | Cruces1H: 1 (<=3) | Fibo: 0.610 (OK, LONG) | Confluencia OK -> Evaluando gatillo",
        },
        "indicators": {"rsi": 55.0, "atr_14": 4.2},
    }
    with patch("backend.main.get_analysis", return_value=fake_buy), \
         patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": 1810.0}), \
         patch("backend.entry_gate.entry_gate_failures", return_value=["RVOL insuficiente (0.40)"]):
        isolated_daemon._execute_cycle()

    assert isolated_daemon.last_signal == "MANTENER"
    assert "ADX1H: 24.50 (>=18)" in isolated_daemon.last_reason
    assert "Bloqueo: Compuerta de entrada: RVOL insuficiente (0.40)" in isolated_daemon.last_reason
    isolated_daemon.is_running = False


def test_daemon_presencial_multi_crypto_escanea_canasta_completa(isolated_daemon):
    """Con MULTI_CRYPTO la sesión presencial evalúa ETH/USDT, SOL/USDT y BTC/USDT en paralelo y consolida telemetría."""
    for s in ("ETH/USDT", "SOL/USDT", "BTC/USDT"):
        isolated_daemon._evaluated_candles[(s, "5m")] = {"signal_candle_ts": 111, "next_close_due_ts": 9999999999.0, "config_sig": ("x",)}

    with patch.object(isolated_daemon, "_run_loop", return_value=None):
        st = isolated_daemon.start_scalping(
            symbol="MULTI_CRYPTO",
            strategy="mtf_presencial_5m",
            timeframe="5m",
            slot_alloc_pct=100.0,
        )

    assert st["active"] is True
    assert st["symbol"] == "MULTI_CRYPTO"
    assert st["symbols"] == ["ETH/USDT", "SOL/USDT", "BTC/USDT"]
    for s in ("ETH/USDT", "SOL/USDT", "BTC/USDT"):
        assert (s, "5m") not in isolated_daemon._evaluated_candles

    evaluated_calls = []

    def fake_get_analysis(**kwargs):
        sym = kwargs["symbol"]
        tf = kwargs["timeframe"]
        strat = kwargs["strategy"]
        evaluated_calls.append((sym, tf, strat))
        tele = f"[{sym} {tf}] Close $100.00 | ADX1H: 15.00 (<18) | Cruces1H: 1 (<=3) | Fibo: 0.550 (OK 0.50-0.75, LONG) | Bloqueo: ADX1H<18 -> En espera"
        return {
            "signal": "MANTENER",
            "reason": tele,
            "signal_candle_ts": 1795010100,
            "strategy_metrics": {"atr_14": 2.0, "presencial_telemetry": tele},
            "indicators": {"rsi": 50.0, "atr_14": 2.0},
        }

    with patch("backend.main.get_analysis", side_effect=fake_get_analysis), \
         patch("backend.main.get_price", return_value={"price": 100.0}):
        isolated_daemon._execute_cycle()

    assert evaluated_calls == [
        ("ETH/USDT", "5m", "mtf_presencial_5m"),
        ("SOL/USDT", "5m", "mtf_presencial_5m"),
        ("BTC/USDT", "5m", "mtf_presencial_5m"),
    ]
    assert "Canasta [ETH:ADX1H<18 · SOL:ADX1H<18]" in isolated_daemon.last_reason
    isolated_daemon.is_running = False


def test_daemon_auto_mantiene_4h_fondo_y_aisla_5m_exclusivo_presencial(isolated_daemon):
    """start(strategy='auto', timeframe='5m') normaliza a 4h y una sesión presencial activa en 5m no es pisada."""
    with patch.object(isolated_daemon, "_run_loop", return_value=None):
        isolated_daemon.start(
            symbol="ETH/USDT",
            timeframe="5m",
            strategy="auto",
            allowed_strategies=["kula_balam_cava_ruiz", "1_donchian_breakout_sol_4h", "kula_cava_eth_1h"],
            slot_alloc_pct=50.0,
        )
        assert isolated_daemon.strategy == "auto"
        assert isolated_daemon.timeframe == "4h"

        st = isolated_daemon.start_scalping(
            symbol="MULTI_CRYPTO",
            strategy="mtf_presencial_5m",
            timeframe="5m",
            slot_alloc_pct=25.0,
        )
        assert st["active"] is True
        assert isolated_daemon.timeframe == "5m"
        assert isolated_daemon.backup_timeframe == "4h"

        # Sincronización tardía desde UI mientras Presencial corre no pisa 5m ni corrompe backup_timeframe
        res_mid = isolated_daemon.start(
            symbol="SOL/USDT",
            timeframe="1m",
            strategy="auto",
            allowed_strategies=["kula_balam_cava_ruiz", "1_donchian_breakout_sol_4h"],
            slot_alloc_pct=50.0,
        )
        assert res_mid["status"] == "presencial_active"
        assert isolated_daemon.scalping_active is True
        assert isolated_daemon.timeframe == "5m"
        assert isolated_daemon.backup_timeframe == "4h"
        assert isolated_daemon.backup_symbol == "SOL/USDT"

        isolated_daemon.stop_scalping()
        assert isolated_daemon.scalping_active is False
        assert isolated_daemon.strategy == "auto"
        assert isolated_daemon.timeframe == "4h"

    isolated_daemon.is_running = False


def test_ttm_squeeze_eth_1h_and_sol_4h_registered_isolated_and_whitelisted(isolated_daemon):
    """
    Opción 1: Las estrategias tendenciales complementarias ttm_squeeze_eth_1h y ttm_squeeze_sol_4h:
    1. Se cargan dinámicamente desde catalogo/principal/ con native_timeframe y activo_default exactos.
    2. Superan el HealthWatchdog sintético en estado GREEN (2/2).
    3. Quedan aisladas por par y temporalidad nativa en _resolve_auto_timeframe_buckets.
    4. Están habilitadas por defecto en daemon_state.json y PRODUCTION_WHITELIST_DEFAULTS.
    """
    import json
    from pathlib import Path
    from backend.estrategias.registry import _sync_catalog_registry, get_strategy
    from backend.health_watchdog import HealthWatchdog

    _sync_catalog_registry()
    st_eth = get_strategy("ttm_squeeze_eth_1h")
    st_sol = get_strategy("ttm_squeeze_sol_4h")
    assert st_eth is not None and st_eth.native_timeframe == "1h" and st_eth.activo_default == "ETH/USDT"
    assert st_sol is not None and st_sol.native_timeframe == "4h" and st_sol.activo_default == "SOL/USDT"

    probe = HealthWatchdog().probe_active_strategies(["ttm_squeeze_eth_1h", "ttm_squeeze_sol_4h"], force=True)
    assert probe["status"] == "GREEN", f"HealthWatchdog no devolvió GREEN: {probe}"
    assert probe["passed"] == 2

    allowed = [
        "kula_balam_cava_ruiz",
        "1_donchian_breakout_sol_4h",
        "2_squeeze_dual_eth_4h",
        "ttm_squeeze_eth_1h",
        "ttm_squeeze_sol_4h",
    ]
    eth_buckets = dict(isolated_daemon._resolve_auto_timeframe_buckets("ETH/USDT", allowed))
    assert eth_buckets.get("1h") == ["ttm_squeeze_eth_1h"]
    assert "2_squeeze_dual_eth_4h" in eth_buckets.get("4h", [])
    assert "ttm_squeeze_sol_4h" not in eth_buckets.get("4h", [])
    assert "ttm_squeeze_sol_4h" not in eth_buckets.get("1h", [])

    sol_buckets = dict(isolated_daemon._resolve_auto_timeframe_buckets("SOL/USDT", allowed))
    assert "ttm_squeeze_sol_4h" in sol_buckets.get("4h", [])
    assert "1_donchian_breakout_sol_4h" in sol_buckets.get("4h", [])
    assert "ttm_squeeze_eth_1h" not in sol_buckets.get("1h", [])
    assert "ttm_squeeze_eth_1h" not in sol_buckets.get("4h", [])

    root = Path(__file__).resolve().parent.parent
    daemon_state = json.loads((root / "backend" / "config" / "daemon_state.json").read_text(encoding="utf-8"))
    assert "ttm_squeeze_eth_1h" in daemon_state.get("allowed_strategies", [])
    assert "ttm_squeeze_sol_4h" in daemon_state.get("allowed_strategies", [])

    app_js = (root / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    wl_start = app_js.index("const PRODUCTION_WHITELIST_DEFAULTS")
    wl_block = app_js[wl_start:app_js.index("]);", wl_start)]
    assert "'ttm_squeeze_eth_1h'" in wl_block
    assert "'ttm_squeeze_sol_4h'" in wl_block


def test_catalog_strategies_no_premature_breakeven_at_044pct(isolated_daemon):
    """
    Regresión del bug en vivo de ETH/USDT SHORT (`2_squeeze_dual_eth_4h`, entrada $1,641.93,
    pico $1,634.71 = +0.44%, rebote $1,641.80 -> -$0.91 por BE prematuro):
    Verifica que `2_squeeze_dual_eth_4h`, `ttm_squeeze_eth_1h`, `ttm_squeeze_sol_4h` y
    `donchian_breakout_1h` (todas con BREAKEVEN_RR == 0.0 y TRAILING_ATR_MULT == 0.0) bajo
    `strategy="auto"` NO activan Pre-BE Short (+0.30%), Escalón 1A/1B (+0.44%), Cerrojo de
    Scalping (+1.20%) ni Trailing Stop, cerrando exclusivamente por SL o TP.
    """
    # Caso A: Reproducción exacta al centavo del incidente ETH/USDT SHORT en 2_squeeze_dual_eth_4h
    isolated_daemon.strategy = "auto"
    isolated_daemon.broker.place_entry(
        "ETH/USDT",
        "SHORT",
        qty=0.289,
        price=1641.93,
        initial_tp_pct=4.5,
        initial_sl_pct=1.8,
        strategy="2_squeeze_dual_eth_4h",
    )

    with patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": 1634.71}):
        liq_peak = isolated_daemon._check_open_positions_protections()
    assert liq_peak == []
    pos_peak = isolated_daemon.broker.fetch_positions()[0]
    assert pos_peak["be_armed"] == 0
    assert pos_peak["trail_active"] == 0
    assert pos_peak["current_stop_net_pct"] == pytest.approx(-1.8, abs=1e-4)

    # Rebote al precio de entrada ($1,641.80): NO debe liquidar por Breakeven Real
    with patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": 1641.80}):
        liq_rebound = isolated_daemon._check_open_positions_protections()
    assert liq_rebound == []
    assert len(isolated_daemon.broker.fetch_positions()) == 1
    isolated_daemon.broker.flatten("ETH/USDT", current_price=1641.80)

    # Caso B: Matriz completa LONG y SHORT para las 3 estrategias pedidas + donchian_breakout_1h
    cases = [
        ("2_squeeze_dual_eth_4h", "ETH/USDT", "SHORT"),
        ("2_squeeze_dual_eth_4h", "ETH/USDT", "LONG"),
        ("ttm_squeeze_eth_1h", "ETH/USDT", "SHORT"),
        ("ttm_squeeze_eth_1h", "ETH/USDT", "LONG"),
        ("ttm_squeeze_sol_4h", "SOL/USDT", "SHORT"),
        ("ttm_squeeze_sol_4h", "SOL/USDT", "LONG"),
        ("donchian_breakout_1h", "SOL/USDT", "SHORT"),
    ]
    for strat_id, sym, side in cases:
        isolated_daemon.strategy = "auto"
        entry_px = 100.0
        isolated_daemon.broker.place_entry(
            sym,
            side,
            qty=1.0,
            price=entry_px,
            initial_tp_pct=4.0,
            initial_sl_pct=2.0,
            strategy=strat_id,
        )

        # 1. Avance +0.35% (zona Pre-BE Short): sin compresión de SL
        px_035 = entry_px * (1.0 - 0.0035) if side == "SHORT" else entry_px * (1.0 + 0.0035)
        with patch("backend.main.get_price", return_value={"symbol": sym, "price": px_035}):
            assert isolated_daemon._check_open_positions_protections() == []
        pos = isolated_daemon.broker.fetch_positions()[0]
        assert pos["be_armed"] == 0, f"{strat_id} {side} armó BE en +0.35%"
        assert pos["current_stop_net_pct"] == pytest.approx(-2.0, abs=1e-4)

        # 2. Avance +0.44% (zona Escalón 1A): be_armed=0, trail_active=0
        px_044 = entry_px * (1.0 - 0.0044) if side == "SHORT" else entry_px * (1.0 + 0.0044)
        with patch("backend.main.get_price", return_value={"symbol": sym, "price": px_044}):
            assert isolated_daemon._check_open_positions_protections() == []
        pos = isolated_daemon.broker.fetch_positions()[0]
        assert pos["be_armed"] == 0, f"{strat_id} {side} sufrió BE prematuro en +0.44%"
        assert pos["trail_active"] == 0, f"{strat_id} {side} activó trailing en +0.44%"
        assert pos["current_stop_net_pct"] == pytest.approx(-2.0, abs=1e-4)

        # 3. Avance +1.20% (zona Cerrojo Scalping): sigue sin BE ni Cerrojo ni Trailing
        px_120 = entry_px * (1.0 - 0.0120) if side == "SHORT" else entry_px * (1.0 + 0.0120)
        with patch("backend.main.get_price", return_value={"symbol": sym, "price": px_120}):
            assert isolated_daemon._check_open_positions_protections() == []
        pos = isolated_daemon.broker.fetch_positions()[0]
        assert pos["be_armed"] == 0, f"{strat_id} {side} activó Cerrojo Scalping en +1.20%"
        assert pos["trail_active"] == 0
        assert pos["current_stop_net_pct"] == pytest.approx(-2.0, abs=1e-4)

        # 4. Retroceso de vuelta al precio de entrada: sigue abierta sin liquidar en falso BE
        with patch("backend.main.get_price", return_value={"symbol": sym, "price": entry_px}):
            assert isolated_daemon._check_open_positions_protections() == []
        assert len(isolated_daemon.broker.fetch_positions()) == 1

        # 5. Alcance de TP (+4.2%): liquida 100% por TAKE_PROFIT (sin peluqueo ni trailing)
        px_tp = entry_px * (1.0 - 0.042) if side == "SHORT" else entry_px * (1.0 + 0.042)
        with patch("backend.main.get_price", return_value={"symbol": sym, "price": px_tp}):
            liq_tp = isolated_daemon._check_open_positions_protections()
        assert len(liq_tp) == 1
        assert liq_tp[0]["action"] == "TAKE_PROFIT"
        assert isolated_daemon.broker.fetch_positions() == []


def test_breakeven_real_covers_fee_spread_and_slippage_no_net_loss(isolated_daemon):
    """
    Verifica que donde SÍ existe Breakeven (ej. `kula_balam_cava_ruiz`), el piso temprano
    usa `gross_target_for_net(be_early_net_pct + anti_slippage, pos_fee, pos_spread)` de modo
    que el retorno neto tras comisiones + spread sea estrictamente positivo tanto en LONG como
    en SHORT y nunca cierre un empate en pérdida neta.
    """
    from backend.quant_risk import gross_target_for_net, net_return_after_costs

    expected_gross = round(gross_target_for_net(0.08, 0.10, 0.05), 4)
    assert expected_gross > 0.35
    assert net_return_after_costs(expected_gross, 0.10, 0.05) >= 0.075

    for side in ("LONG", "SHORT"):
        isolated_daemon.strategy = "kula_balam_cava_ruiz"
        entry_px = 1641.93
        isolated_daemon.broker.place_entry(
            "ETH/USDT",
            side,
            qty=0.10,
            price=entry_px,
            initial_tp_pct=3.0,
            initial_sl_pct=1.5,
            strategy="kula_balam_cava_ruiz",
        )

        # Avance +0.44% arma BE Real en kula_balam_cava_ruiz
        px_arm = entry_px * (1.0 - 0.0044) if side == "SHORT" else entry_px * (1.0 + 0.0044)
        with patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": px_arm}):
            assert isolated_daemon._check_open_positions_protections() == []

        pos = isolated_daemon.broker.fetch_positions()[0]
        assert pos["be_armed"] == 1
        expected_stop = entry_px * (1.0 - expected_gross / 100.0) if side == "SHORT" else entry_px * (1.0 + expected_gross / 100.0)
        cf = isolated_daemon.counterfactual_cache["ETH/USDT"]
        assert cf["active_stop_price"] == pytest.approx(expected_stop, abs=0.05)

        # Cierre justo al cruzar el piso de Breakeven Real: PnL neto estrictamente positivo (> 0)
        px_trigger = expected_stop * 1.0001 if side == "SHORT" else expected_stop * 0.9999
        with patch("backend.main.get_price", return_value={"symbol": "ETH/USDT", "price": px_trigger}):
            liq = isolated_daemon._check_open_positions_protections()
        assert len(liq) == 1
        assert liq[0]["action"] == "BREAKEVEN_REAL"
        assert liq[0]["result"]["net_pnl"] > 0.0
        assert isolated_daemon.broker.fetch_positions() == []






















