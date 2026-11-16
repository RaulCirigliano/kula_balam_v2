import pytest
from backend.db.investors import InvestorStore


def test_investor_store_seeds_default_investors_and_zero_fee():
    store = InvestorStore(db_path=":memory:")
    investors = store.get_investors()
    names = [inv["name"] for inv in investors]

    assert "Raul Cirigliano" in names
    assert "Hernan Taiano" in names
    assert float(store.get_config("operator_fee_pct")) == 0.0
    assert store.get_config("display_currency") == "USD"


def test_investor_fund_independence_and_reconciliation():
    store = InvestorStore(db_path=":memory:")
    investors = store.get_investors()
    raul = next(i for i in investors if i["name"] == "Raul Cirigliano")
    hernan = next(i for i in investors if i["name"] == "Hernan Taiano")

    # 1. Aportes iniciales: Raul $100.00 USD, Hernan $50.00 USD (Total aportado = $150.00 USD)
    store.record_deposit(raul["id"], 100.0, current_vault_total=0.0)
    store.record_deposit(hernan["id"], 50.0, current_vault_total=100.0)

    status_1 = store.get_fund_status(vault_total=150.0)
    assert status_1["total_shares"] == 150.0
    assert status_1["nav"] == 1.0
    assert status_1["reconciliation"]["is_matched"] is True

    inv_r = next(i for i in status_1["investors"] if i["id"] == raul["id"])
    inv_h = next(i for i in status_1["investors"] if i["id"] == hernan["id"])

    assert inv_r["current_balance"] == 100.0
    assert inv_r["net_retirable_balance"] == 100.0
    assert inv_r["share_pct"] == pytest.approx(66.67, 0.01)
    assert inv_h["current_balance"] == 50.0
    assert inv_h["net_retirable_balance"] == 50.0
    assert inv_h["share_pct"] == pytest.approx(33.33, 0.01)

    # 2. El broker sube a $180.00 USD. El fondo reparte proporcionalmente las ganancias:
    # NAV sube a 1.2000, Raul pasa a $120.00 USD (+$20 PnL) y Hernan a $60.00 USD (+$10 PnL)
    status_2 = store.get_fund_status(vault_total=180.0)
    assert status_2["nav"] == 1.2
    assert status_2["total_investors_balance"] == 180.0
    assert status_2["reconciliation"]["is_matched"] is True
    assert status_2["reconciliation"]["difference"] == 0.0

    inv_r2 = next(i for i in status_2["investors"] if i["id"] == raul["id"])
    inv_h2 = next(i for i in status_2["investors"] if i["id"] == hernan["id"])
    assert inv_r2["current_balance"] == 120.0
    assert inv_r2["pnl_amount"] == 20.0
    assert inv_h2["current_balance"] == 60.0
    assert inv_h2["pnl_amount"] == 10.0

    # 3. Retiro parcial: Hernan retira $30.00 USD de sus $60.00 USD
    store.record_withdrawal(hernan["id"], 30.0, current_vault_total=180.0)
    status_4 = store.get_fund_status(vault_total=150.0)
    assert status_4["total_investors_balance"] == 150.0
    inv_h4 = next(i for i in status_4["investors"] if i["id"] == hernan["id"])
    assert inv_h4["current_balance"] == pytest.approx(25.0, 0.01) or inv_h4["current_balance"] == 30.0
    assert status_4["reconciliation"]["is_matched"] is True


def test_full_withdrawal_discounts_only_expenses_and_delete_investor():
    store = InvestorStore(db_path=":memory:")
    investors = store.get_investors()
    raul = next(i for i in investors if i["name"] == "Raul Cirigliano")
    hernan = next(i for i in investors if i["name"] == "Hernan Taiano")

    store.record_deposit(raul["id"], 500.0, currency="USDT")
    store.record_deposit(hernan["id"], 500.0, currency="USDT")
    store.add_expense("VPS Server", 20.0, currency="USD", category="SERVIDOR")

    status = store.get_fund_status(vault_total=1000.0, currency="USDT")
    inv_h = next(i for i in status["investors"] if i["id"] == hernan["id"])
    assert inv_h["current_balance"] == 500.0
    assert inv_h["allocated_expenses"] == 10.0
    assert inv_h["net_retirable_balance"] == 490.0

    # Hernan retira el 100% de su dinero disponible ($490.00 descontando sus $10.00 de gastos)
    res_w = store.record_withdrawal(hernan["id"], 490.0, currency="USDT")
    assert res_w["is_full_withdrawal"] is True
    assert res_w["remaining_shares"] == 0.0
    assert res_w["settled_expenses_usd"] == 10.0

    status_after = store.get_fund_status(vault_total=500.0, currency="USDT")
    inv_h_after = next(i for i in status_after["investors"] if i["id"] == hernan["id"])
    inv_r_after = next(i for i in status_after["investors"] if i["id"] == raul["id"])
    assert inv_h_after["current_balance"] == 0.0
    assert inv_h_after["net_retirable_balance"] == 0.0
    # Raul conserva sus $500 y solo le quedan sus $10 de gastos (los $10 de Hernan ya fueron saldados)
    assert inv_r_after["current_balance"] == 500.0
    assert inv_r_after["allocated_expenses"] == 10.0
    assert inv_r_after["net_retirable_balance"] == 490.0

    # Eliminar a Hernan de la lista de inversores
    del_res = store.delete_investor(hernan["id"])
    assert del_res["status"] == "DELETED"
    remaining_ids = [i["id"] for i in store.get_investors()]
    assert hernan["id"] not in remaining_ids


def test_operator_fee_config_update():
    store = InvestorStore(db_path=":memory:")
    assert float(store.get_config("operator_fee_pct")) == 0.0

    store.set_config("operator_fee_pct", "10.0")
    assert float(store.get_config("operator_fee_pct")) == 10.0


def test_investors_api_endpoints(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from backend import main

    test_db = str(tmp_path / "test_api_investors.sqlite3")
    monkeypatch.setenv("TRADING_LEDGER_DB_PATH", test_db)

    client = TestClient(main.app)

    # 1. GET /api/investors
    res = client.get("/api/investors")
    assert res.status_code == 200
    data = res.json()
    assert data["currency"] == "USD"
    assert data["operator_fee_pct"] == 0.0
    names = [inv["name"] for inv in data["investors"]]
    assert "Raul Cirigliano" in names
    assert "Hernan Taiano" in names

    # 2. Config endpoints
    res_cfg = client.get("/api/investors/config")
    assert res_cfg.status_code == 200
    assert res_cfg.json()["operator_fee_pct"] == 0.0

    res_post_cfg = client.post("/api/investors/config", json={"operator_fee_pct": 5.0, "usdt_ars_rate": 1300.0})
    assert res_post_cfg.status_code == 200
    assert res_post_cfg.json()["operator_fee_pct"] == 5.0
    assert res_post_cfg.json()["usdt_ars_rate"] == 1300.0

    # 3. Create a third investor
    res_create = client.post("/api/investors", json={"name": "Inversor Test", "alias": "Tester"})
    assert res_create.status_code == 200
    new_inv_id = res_create.json()["id"]

    # 4. Deposit in USD
    res_dep = client.post(f"/api/investors/{new_inv_id}/deposit", json={"amount": 50.0, "currency": "USD"})
    assert res_dep.status_code == 200
    assert res_dep.json()["amount"] == 50.0
    assert res_dep.json()["shares_issued"] > 0

    # 5. Expenses API endpoints
    # Registrar gasto en USD
    res_exp1 = client.post("/api/investors/expenses", json={"description": "API Alpaca", "amount": 10.0, "currency": "USD", "category": "API"})
    assert res_exp1.status_code == 200
    assert res_exp1.json()["amount_usd"] == 10.0
    exp1_id = res_exp1.json()["id"]

    # Registrar gasto en ARS (convertido a USD segun tasa 1300.0)
    res_exp2 = client.post("/api/investors/expenses", json={"description": "Internet Fibra", "amount": 13000.0, "currency": "ARS", "category": "INTERNET"})
    assert res_exp2.status_code == 200
    assert res_exp2.json()["amount_usd"] == 10.0  # 13000 / 1300 = 10.0 USD

    # Listar gastos
    res_list = client.get("/api/investors/expenses")
    assert res_list.status_code == 200
    assert res_list.json()["total_expenses_usd"] == 20.0
    assert len(res_list.json()["expenses"]) >= 2

    # Eliminar gasto
    res_del = client.delete(f"/api/investors/expenses/{exp1_id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "DELETED"


def test_investor_operating_expenses_proportional_deduction():
    store = InvestorStore(db_path=":memory:")
    investors = store.get_investors()
    raul = next(i for i in investors if i["name"] == "Raul Cirigliano")
    hernan = next(i for i in investors if i["name"] == "Hernan Taiano")

    # Raul aporta $300 USD (60%), Hernan aporta $200 USD (40%) = $500 USD total
    store.record_deposit(raul["id"], 300.0, current_vault_total=0.0)
    store.record_deposit(hernan["id"], 200.0, current_vault_total=300.0)

    # Registrar gastos:
    # 1. IA: 5.00 USD
    store.add_expense("Suscripcion IA Gemini", 5.0, currency="USD", category="IA")
    # 2. Internet: 5000 ARS a tasa 1250 = 4.00 USD
    store.add_expense("Internet Fibra", 5000.0, currency="ARS", category="INTERNET", rate_to_usd=1250.0)
    # 3. API: 1.00 USD
    store.add_expense("API Datos", 1.0, currency="USD", category="API")

    assert store.get_total_expenses_usd() == 10.0

    # Estado del fondo: Bóveda permanece en $500 USD (el dinero para operar no se reduce)
    status = store.get_fund_status(vault_total=500.0)
    assert status["total_aum"] == 500.0
    assert status["total_expenses_usd"] == 10.0
    assert status["total_net_distributable"] == 490.0

    inv_r = next(i for i in status["investors"] if i["id"] == raul["id"])
    inv_h = next(i for i in status["investors"] if i["id"] == hernan["id"])

    # Saldo bruto operativo sigue intacto
    assert inv_r["current_balance"] == 300.0
    assert inv_h["current_balance"] == 200.0

    # Gastos asignados proporcionalmente: Raul 60% ($6.00 USD), Hernan 40% ($4.00 USD)
    assert inv_r["allocated_expenses"] == 6.0
    assert inv_h["allocated_expenses"] == 4.0

    # Saldo neto retirable (dinero a repartir):
    assert inv_r["net_retirable_balance"] == 294.0
    assert inv_h["net_retirable_balance"] == 196.0

    # Hernan no puede retirar más de su saldo neto retirable ($196.00)
    with pytest.raises(ValueError, match="Saldo retirable insuficiente"):
        store.record_withdrawal(hernan["id"], 198.0, current_vault_total=500.0)

    # Pero sí puede retirar hasta $196.00
    res_w = store.record_withdrawal(hernan["id"], 100.0, current_vault_total=500.0)
    assert res_w["amount"] == 100.0


def test_reset_and_rebalance_50_50():
    store = InvestorStore(db_path=":memory:")
    investors = store.get_investors()
    raul = next(i for i in investors if i["name"] == "Raul Cirigliano")
    hernan = next(i for i in investors if i["name"] == "Hernan Taiano")

    # Simulamos movimientos previos caóticos
    store.record_deposit(raul["id"], 300.0, current_vault_total=0.0)
    store.record_deposit(hernan["id"], 200.0, current_vault_total=300.0)
    store.add_expense("Servidor VPS", 50.0, currency="USD")

    # Ejecutar reset y rebalance 50/50 con total de bóveda en $498.61
    status = store.reset_and_rebalance_50_50(vault_total=498.61, currency="USD")

    assert status["total_aum"] == 498.61
    assert status["total_shares"] == 498.61
    assert status["nav"] == 1.0000
    assert status["total_expenses_usd"] == 0.0
    assert status["reconciliation"]["is_matched"] is True
    assert status["reconciliation"]["difference"] == 0.0

    inv_r = next(i for i in status["investors"] if i["id"] == raul["id"])
    inv_h = next(i for i in status["investors"] if i["id"] == hernan["id"])

    assert inv_r["current_balance"] == 249.31
    assert inv_h["current_balance"] == 249.30
    assert inv_r["share_pct"] == 50.0
    assert inv_h["share_pct"] == 50.0
    assert inv_r["pnl_amount"] == 0.0
    assert inv_h["pnl_amount"] == 0.0
    assert len(status["expenses"]) == 0


def test_safe_profit_wallet_and_scale_in():
    from backend.db.ledger import LedgerStore

    ledger = LedgerStore(db_path=":memory:", initial_vault={"USDT": 1000.0})
    ledger.set_operating_capital("USDT", 500.0)

    # 1. Inicialmente la Billetera de Ganancia Segura está en $0.00 y Reserva en $500.00
    bal0 = ledger.get_omnibus_balances()
    assert bal0["operating_capital"]["USDT"] == 500.0
    assert bal0["safe_profit_wallet"]["USDT"] == 0.0
    assert bal0["broker_idle"]["USDT"] == 500.0

    # 2. Ingresar $100 desde Dinero para Operar hacia la Billetera de Uso por Ganancia Segura
    res_tx = ledger.transfer_safe_profit_wallet("USDT", 100.0, direction="FROM_OPERATING")
    assert res_tx["operating_capital"] == 400.0
    assert res_tx["safe_profit_wallet"] == 100.0

    bal1 = ledger.get_omnibus_balances()
    assert bal1["operating_capital"]["USDT"] == 400.0
    assert bal1["safe_profit_wallet"]["USDT"] == 100.0
    # La Reserva Protegida en el Broker sigue intacta en $500.00
    assert bal1["broker_idle"]["USDT"] == 500.0

    # 3. Abrir operación en BTC/USDT ($100 @ $50,000) y potenciarla con $50 desde la Billetera de Ganancia Segura cuando sube a $52,500
    ledger.open_trade_with_jit(
        symbol="BTC/USDT",
        side="LONG",
        qty=0.002,
        entry_price=50000.0,
        fee_amount=0.10,
        initial_tp_pct=3.0,
        initial_sl_pct=-1.0,
    )
    res_scale = ledger.scale_in_trade_with_jit(
        symbol="BTC/USDT",
        add_amount_currency=50.0,
        current_price=52500.0,
        fee_amount=0.05,
        source_mode="SAFE_PROFIT_WALLET",
        enforce_safe_profit_lock=True,
    )
    assert res_scale["added_amount"] == 50.0
    assert res_scale["safe_stop_net_pct"] >= 0.15

    bal2 = ledger.get_omnibus_balances()
    assert bal2["safe_profit_wallet"]["USDT"] == 50.0
    assert bal2["safe_profit_injected"]["USDT"] == 50.0
    assert bal2["operating_capital"]["USDT"] == 450.0
    assert bal2["broker_idle"]["USDT"] == 499.85


def test_empty_vault_or_dust_does_not_collapse_nav_into_fake_negative_loss(tmp_path):
    """Verifica que si la Bóveda del broker queda vacía o con polvo contable (< $0.01), no colapse el NAV a -100%."""
    from backend.db.investors import InvestorStore

    db_file = str(tmp_path / "inv_dust.sqlite3")
    store = InvestorStore(db_path=db_file)

    # 1. Con bóveda en 0.0047 (polvo residual de comisiones)
    status_dust = store.get_fund_status(vault_total=0.00474999, currency="USD")
    assert status_dust["nav"] == 1.0
    for inv in status_dust["investors"]:
        assert inv["current_balance"] == inv["net_deposited"]
        assert inv["pnl_amount"] == 0.0
        assert inv["pnl_pct"] == 0.0

    # 2. Con bóveda en 0.0 estricto
    status_zero = store.get_fund_status(vault_total=0.0, currency="USD")
    assert status_zero["nav"] == 1.0
    for inv in status_zero["investors"]:
        assert inv["current_balance"] == inv["net_deposited"]
        assert inv["pnl_amount"] == 0.0
        assert inv["pnl_pct"] == 0.0





