import pytest
from fastapi.testclient import TestClient

from backend.db.ledger import LedgerStore
from backend.execution.paper_broker import PaperBrokerAdapter
from backend import main


def test_omnibus_accounts_start_with_zero_operational_balance():
    ledger = LedgerStore(db_path=":memory:", initial_vault={"USDT": 500.0, "USD": 1000.0, "ARS": 250_000.0})
    balances = ledger.get_omnibus_balances()

    # Regla 1 GEMINI.md: Aislamiento por defecto ($0 en billeteras operativas)
    assert balances["operational"] == {"USDT": 0.0, "USD": 0.0, "ARS": 0.0}
    assert balances["vault"] == {"USDT": 500.0, "USD": 1000.0, "ARS": 250_000.0}
    assert ledger.verify_double_entry_integrity()["valid"] is True


def test_jit_funding_and_sweep_back_preserve_double_entry_and_zero_operational_balance():
    ledger = LedgerStore(db_path=":memory:", initial_vault={"USDT": 500.0, "USD": 500.0, "ARS": 500_000.0})

    # 1. Abrir trade en BTC/USDT con fondeo Just-In-Time (1.0 BTC a $100 + $0.10 fee = $100.10 desde Bóveda)
    opened = ledger.open_trade_with_jit(
        symbol="BTC/USDT",
        qty=1.0,
        entry_price=100.0,
        fee_amount=0.10,
    )
    assert opened["status"] == "OPEN"
    assert opened["allocated_jit"] == pytest.approx(100.10)

    mid_balances = ledger.get_omnibus_balances()
    assert mid_balances["vault"]["USDT"] == pytest.approx(399.90)
    assert mid_balances["operational"]["USDT"] == pytest.approx(100.0)
    assert mid_balances["fees_paid"]["USDT"] == pytest.approx(0.10)

    # 2. Prohibir segundo trade abierto simultáneo en el mismo símbolo (one_open_trade_per_symbol)
    with pytest.raises(ValueError, match="Ya existe una posición abierta"):
        ledger.open_trade_with_jit(symbol="BTC/USDT", qty=0.5, entry_price=101.0)

    # 3. Cerrar trade con ganancia ($105.00, comisión de salida $0.105) -> Sweep-Back automático a Bóveda
    closed = ledger.close_trade_with_sweep(
        symbol="BTC/USDT",
        exit_price=105.0,
        exit_fee_amount=0.105,
        exit_reason="TAKE_PROFIT",
    )

    # Ganancia bruta = +5.00, comisiones totales = 0.205, PnL neto = +4.795
    assert closed["gross_pnl"] == pytest.approx(5.0)
    assert closed["total_fees"] == pytest.approx(0.205)
    assert closed["net_pnl"] == pytest.approx(4.795)
    # Billetera operativa vuelve estrictamente a $0.00 tras el Sweep-Back
    assert closed["operational_balance"] == pytest.approx(0.0)
    assert closed["vault_balance"] == pytest.approx(504.795)

    integrity = ledger.verify_double_entry_integrity()
    assert integrity["valid"] is True


def test_transactional_circuit_breaker_halts_after_three_consecutive_losses():
    ledger = LedgerStore(db_path=":memory:", initial_vault={"USDT": 1000.0, "USD": 1000.0, "ARS": 100_000.0})
    base_ts = int(__import__("time").time())

    for i in range(3):
        ledger.open_trade_with_jit(
            symbol="ETH/USDT", qty=1.0, entry_price=100.0, fee_amount=0.1, now_ts=base_ts + i * 60
        )
        res = ledger.close_trade_with_sweep(
            symbol="ETH/USDT",
            exit_price=99.5,
            exit_fee_amount=0.1,
            exit_reason="STOP_LOSS",
            now_ts=base_ts + i * 60 + 30,
        )

    assert res["risk_state"]["halted"] is True
    assert res["risk_state"]["consecutive_losses"] == 3

    # Intentar abrir un 4to trade con Circuit Breaker activo debe ser bloqueado
    with pytest.raises(RuntimeError, match="Circuit Breaker activo"):
        ledger.open_trade_with_jit(
            symbol="ETH/USDT", qty=1.0, entry_price=100.0, fee_amount=0.1, now_ts=base_ts + 300
        )

    # Reinicio manual por el operador restaura la operativa
    ledger.reset_circuit_breaker("USDT")
    assert ledger.check_circuit_breaker("USDT", now_ts=base_ts + 360)["halted"] is False


def test_paper_broker_adapter_executes_jit_protection_and_emergency_flatten():
    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=":memory:", fee_pct=0.10)
    assert broker.fetch_balances() == {"USDT": 0.0, "USD": 0.0, "ARS": 0.0}

    entry = broker.place_entry("BTC/USDT", "BUY", qty=1.0, price=100.0)
    assert entry["status"] == "FILLED"
    assert len(broker.fetch_positions()) == 1

    # Orden de protección válida
    oco = broker.place_protection("BTC/USDT", qty=1.0, stop_loss_price=98.0, take_profit_price=104.0)
    assert oco["status"] == "NEW"
    assert len(broker.fetch_open_orders("BTC/USDT")) == 1

    # Flatten de emergencia liquida posición y devuelve fondos a Bóveda (OP = 0.0)
    flat = broker.flatten("BTC/USDT", current_price=101.0)
    assert flat["closed"] is True
    assert flat["operational_balance"] == pytest.approx(0.0)
    assert broker.fetch_positions() == []
    assert broker.fetch_open_orders("BTC/USDT") == []


def test_ledger_api_endpoints_expose_omnibus_state(monkeypatch, tmp_path):
    test_ledger = LedgerStore(db_path=str(tmp_path / "test_ledger.sqlite3"))
    monkeypatch.setattr("backend.db.ledger.get_default_ledger", lambda: test_ledger)

    client = TestClient(main.app)
    res = client.get("/api/ledger/state")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "ok"
    assert payload["balances"]["operational"] == {"USDT": 0.0, "USD": 0.0, "ARS": 0.0}
    assert payload["double_entry_integrity"]["valid"] is True


def test_withdrawing_funds_clamps_operating_capital_and_prevents_ghost_500(tmp_path):
    """Verifica que retirar fondos vacíe el capital para operar y no invente 500 fantasma."""
    ledger = LedgerStore(db_path=str(tmp_path / "ghost_500.sqlite3"), initial_vault={"USDT": 500.0})
    ledger.set_operating_capital("USDT", 500.0)

    # Inicialmente $500 asignados
    assert ledger.get_operating_capital("USDT") == 500.0
    omnibus0 = ledger.get_omnibus_balances()
    assert omnibus0["total_equity"]["USDT"] == 500.0
    assert omnibus0["operating_capital"]["USDT"] == 500.0

    # Retirar $300: total equity queda en $200 -> capital para operar se acota a $200
    ledger.withdraw(amount=300.0, currency="USDT")
    assert ledger.get_operating_capital("USDT") == 200.0
    omnibus1 = ledger.get_omnibus_balances()
    assert omnibus1["total_equity"]["USDT"] == 200.0
    assert omnibus1["operating_capital"]["USDT"] == 200.0

    # Retirar los $200 restantes: total equity queda en $0.0 -> capital para operar DEBE ser 0.0 (NO 500)
    ledger.withdraw(amount=200.0, currency="USDT")
    assert ledger.get_operating_capital("USDT") == 0.0
    omnibus2 = ledger.get_omnibus_balances()
    assert omnibus2["total_equity"]["USDT"] == 0.0
    assert omnibus2["operating_capital"]["USDT"] == 0.0
    assert omnibus2["operating_available"]["USDT"] == 0.0
    assert omnibus2["broker_idle"]["USDT"] == 0.0


def test_vault_thermometer_accounting_ratios_consistency(tmp_path):
    """Verifica consistencia contable del termómetro de bóveda y ranuras ante asignaciones parciales."""
    ledger = LedgerStore(db_path=str(tmp_path / "thermo_acc.sqlite3"), initial_vault={"USDT": 100.0})
    ledger.set_operating_capital("USDT", 80.0)

    omni = ledger.get_omnibus_balances()
    vault_cash = omni["vault"]["USDT"]
    total_eq = omni["total_equity"]["USDT"]
    op_cap = omni["operating_capital"]["USDT"]

    assert vault_cash == 100.0
    assert total_eq == 100.0
    assert op_cap == 80.0

    # Simular ratios del termómetro dinámico para 25%, 50% y 100%
    for frac, expected_slots, expected_slot_amt in [(0.25, 4, 20.0), (0.50, 2, 40.0), (1.00, 1, 80.0)]:
        slot_amt = op_cap * frac
        assert round(slot_amt, 2) == expected_slot_amt
        assert int(round(1 / frac)) == expected_slots
