from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from backend.estrategias.kula_balam_cava_ruiz import KulaBalamCavaRuiz
from backend.execution.paper_broker import PaperBrokerAdapter
from backend.quant_risk import (
    build_futures_friction_profile,
    calculate_funding_cost,
    calculate_futures_pnl,
    compute_futures_breakeven_price,
    count_rollover_crossings,
)

NY = ZoneInfo("America/New_York")


def _ts(y: int, m: int, d: int, h: int, mi: int = 0) -> float:
    return datetime(y, m, d, h, mi, tzinfo=NY).timestamp()


# 2026-11-10 es martes
TUE_10 = _ts(2026, 11, 10, 10)
TUE_15 = _ts(2026, 11, 10, 15)
WED_10 = _ts(2026, 11, 11, 10)
THU_10 = _ts(2026, 11, 12, 10)
FRI_10 = _ts(2026, 11, 13, 10)
MON_10 = _ts(2026, 11, 16, 10)


@pytest.fixture
def broker(tmp_path):
    return PaperBrokerAdapter(initial_vault_usd=500.0, db_path=str(tmp_path / "friction.sqlite3"))


def _spot_snapshot(b: PaperBrokerAdapter):
    return (dict(b.vault_balances), dict(b.balances), dict(b.operating_capital_balances))


def test_friction_profile_validation_and_pure_models():
    profile = build_futures_friction_profile("MES=F", spread_ticks_per_side=1, swap_per_contract_night=1.25)
    assert profile.commission_round_trip == pytest.approx(2.50)
    assert profile.spread_cost_per_side(2) == pytest.approx(2.50)
    assert profile.swap_per_contract_night == 1.25

    with pytest.raises(ValueError):
        build_futures_friction_profile("SPY")
    with pytest.raises(ValueError):
        build_futures_friction_profile("MES=F", commission_per_side=-1.0)
    with pytest.raises(ValueError):
        build_futures_friction_profile("MES=F", spread_ticks_per_side=float("nan"))
    with pytest.raises(ValueError):
        calculate_futures_pnl("MES=F", 6000, 6001, 1, swap_usd=-0.5)
    with pytest.raises(ValueError):
        compute_futures_breakeven_price("MES=F", 6000, "LONG", 0)

    # Modo por defecto intacto: solo comisiones fijas
    base = calculate_futures_pnl("MES=F", 6000.0, 6010.25, 2, "LONG")
    assert base["net_pnl"] == pytest.approx(97.50)
    assert base["spread_cost"] == 0.0 and base["swap_cost"] == 0.0

    # Con spread (1 tick/lado) y swap (USD) se descuenta el total desglosado
    full = calculate_futures_pnl("MES=F", 6000.0, 6010.25, 2, "LONG", spread_ticks_per_side=1, swap_usd=3.0)
    assert full["gross_pnl"] == pytest.approx(102.50)
    assert full["total_commission"] == pytest.approx(5.00)
    assert full["spread_cost"] == pytest.approx(5.00)
    assert full["swap_cost"] == pytest.approx(3.00)
    assert full["net_pnl"] == pytest.approx(89.50)

    # Funding perpetuos: LONG paga con tasa positiva, SHORT cobra; solo intervalos completos de 8h
    long_f = calculate_funding_cost(1000.0, 0.01, 17.0, "LONG")
    short_f = calculate_funding_cost(1000.0, 0.01, 17.0, "SHORT")
    assert long_f["intervals"] == 2
    assert long_f["funding_cost_usd"] == pytest.approx(0.20)
    assert short_f["funding_cost_usd"] == pytest.approx(-0.20)
    with pytest.raises(ValueError):
        calculate_funding_cost(1000.0, 0.01, -1.0)


def test_rollover_crossings_weekdays_weekend_and_triple_swap():
    assert count_rollover_crossings(TUE_10, TUE_15) == 0
    assert count_rollover_crossings(TUE_10, WED_10) == 1
    assert count_rollover_crossings(TUE_10, THU_10) == 2
    # Viernes 10:00 -> lunes 10:00: solo el corte del viernes (sábado/domingo no cuentan)
    assert count_rollover_crossings(FRI_10, MON_10) == 1
    # Miércoles triple swap: martes 10:00 -> jueves 10:00 = corte martes (x1) + corte miércoles (x3)
    assert count_rollover_crossings(TUE_10, THU_10, triple_swap_weekday=2) == 4
    assert count_rollover_crossings(THU_10, TUE_10) == 0


def test_intraday_liquidation_has_zero_swap_and_exact_breakeven(broker):
    snap = _spot_snapshot(broker)
    entry = broker.place_entry(
        "MES=F", "BUY", qty=2, price=6000.0,
        friction={"spread_ticks_per_side": 1, "swap_per_contract_night": 1.25, "now_ts": TUE_10},
    )
    assert entry["entry_commission"] == pytest.approx(2.50)
    assert entry["entry_spread_cost"] == pytest.approx(2.50)
    assert broker.get_futures_balance() == pytest.approx(2495.0)

    # TP1 intradía: 1 contrato a 6010 -> 50 bruto - 2.5 comisiones - 2.5 spread = 45.0 neto, swap 0
    trim = broker.trim_position("MES=F", trim_qty=1, current_price=6010.0, now_ts=TUE_15)
    assert trim["swap_cost_leg"] == 0.0 and trim["swap_nights"] == 0
    assert trim["commission_leg"] == pytest.approx(2.50)
    assert trim["spread_cost_leg"] == pytest.approx(2.50)
    assert trim["net_pnl"] == pytest.approx(45.0)
    # BE remanente: (1.25 + 1.25 + 2.5 spread) / $5 = 1.0 punto
    assert trim["be_price"] == pytest.approx(6001.0)
    assert broker.get_futures_breakeven("MES=F")["be_price"] == pytest.approx(6001.0)

    # Liquidar el remanente exactamente en el BE => pérdida neta real $0
    close = broker.flatten("MES=F", current_price=trim["be_price"], exit_reason="Breakeven Real", now_ts=TUE_15)
    assert close["swap_cost"] == 0.0
    assert close["spread_cost"] == pytest.approx(5.00)
    assert close["total_fees"] == pytest.approx(5.00)
    leg = close["net_pnl"] - trim["net_pnl"]
    assert leg == pytest.approx(0.0, abs=1e-9)
    assert broker.get_futures_balance() == pytest.approx(2545.0)

    acc = broker.get_futures_account()
    assert acc["total_swap"] == 0.0
    assert acc["total_spread"] == pytest.approx(5.00)
    assert acc["total_fees"] == pytest.approx(5.00)
    assert _spot_snapshot(broker) == snap
    assert broker.ledger.verify_double_entry_integrity()["valid"] is True


def test_multiday_liquidation_adds_accrued_swap_to_breakeven(broker):
    snap = _spot_snapshot(broker)
    entry = broker.place_entry(
        "MES=F", "BUY", qty=2, price=6000.0,
        friction={"spread_ticks_per_side": 1, "swap_per_contract_night": 1.25, "now_ts": TUE_10},
    )

    # Miércoles 10:00 (1 corte superado): swap 1.25 x 2 contratos = 2.50 debitado
    trim = broker.trim_position("MES=F", trim_qty=1, current_price=6010.0, now_ts=WED_10)
    assert trim["swap_nights"] == 1
    assert trim["swap_cost_leg"] == pytest.approx(1.25)
    assert trim["net_pnl"] == pytest.approx(50.0 - 2.5 - 2.5 - 1.25)
    # BE remanente: 1.25 + 1.25 + 2.5 spread + 1.25 swap = 6.25 -> 1.25 puntos
    assert trim["be_price"] == pytest.approx(6001.25)

    # Jueves 10:00 (2do corte): el swap del remanente sube a 2.50 y el BE se recalcula en la posición
    accr = broker.accrue_futures_swap("MES=F", now_ts=THU_10)
    assert accr["nights"] == 1
    assert accr["swap_charged"] == pytest.approx(1.25)
    assert accr["be_price"] == pytest.approx(6001.5)
    assert broker.get_futures_breakeven("MES=F")["be_price"] == pytest.approx(6001.5)

    # Sin nuevo corte no se vuelve a devengar (idempotente)
    again = broker.accrue_futures_swap("MES=F", now_ts=THU_10)
    assert again["nights"] == 0 and again["swap_charged"] == 0.0

    close = broker.flatten("MES=F", current_price=accr["be_price"], exit_reason="Breakeven Real", now_ts=THU_10)
    leg = close["net_pnl"] - trim["net_pnl"]
    assert leg == pytest.approx(0.0, abs=1e-9)
    assert close["swap_cost"] == pytest.approx(3.75)  # 2.50 (2 contratos) + 1.25 (remanente)

    # Contabilidad: balance = capital inicial + PnL realizado neto; desglose coincide con eventos
    acc = broker.get_futures_account()
    assert acc["total_swap"] == pytest.approx(3.75)
    assert acc["realized_pnl"] == pytest.approx(43.75)
    assert acc["balance"] == pytest.approx(2543.75)
    breakdown = broker.ledger.get_futures_cost_breakdown(entry["trade_id"])
    assert breakdown["swap"] == pytest.approx(3.75)
    assert breakdown["commission"] == pytest.approx(5.00)
    assert breakdown["spread"] == pytest.approx(5.00)
    assert breakdown["total_friction"] == pytest.approx(13.75)

    row = broker.ledger.get_trade_history(limit=5)[0]
    assert row["symbol"] == "MES=F" and row["status"] == "CLOSED"
    assert _spot_snapshot(broker) == snap


def test_breakeven_rounds_to_protective_tick_and_short_side(broker):
    # Costos 7.50 sobre 1 contrato MES = 1.5 puntos exactos; con 8.0 = 1.6 pts -> redondeo protector al tick
    exact = compute_futures_breakeven_price("MES=F", 6000.0, "LONG", 1, spread_ticks_per_side=1, swap_usd=2.5)
    assert exact["be_price"] == pytest.approx(6001.5)
    rounded = compute_futures_breakeven_price("MES=F", 6000.0, "LONG", 1, spread_ticks_per_side=1, swap_usd=3.0)
    assert rounded["be_price_exact"] == pytest.approx(6001.6)
    assert rounded["be_price"] == pytest.approx(6001.75)
    net_at_be = calculate_futures_pnl("MES=F", 6000.0, rounded["be_price"], 1, "LONG", spread_ticks_per_side=1, swap_usd=3.0)["net_pnl"]
    assert 0.0 <= net_at_be < 1.25

    short = compute_futures_breakeven_price("MNQ=F", 21000.0, "SHORT", 1, spread_ticks_per_side=1, swap_usd=0.0)
    # costos: 2.5 comisión + 1.0 spread = 3.5 / $2 = 1.75 pts por debajo de la entrada
    assert short["be_price"] == pytest.approx(20998.25)
    net_short = calculate_futures_pnl("MNQ=F", 21000.0, short["be_price"], 1, "SHORT", spread_ticks_per_side=1)["net_pnl"]
    assert net_short == pytest.approx(0.0, abs=1e-9)


def test_strategy_exposes_friction_model_for_micro_futures():
    strat = KulaBalamCavaRuiz()
    ind = {"symbol": "MES=F", "live_price": 6000.0, "atr_14": 3.0, "relative_volume": 1.0}
    metrics, _, _, _, _ = strat.evaluar(
        ind=ind, tp=1.5, sl=0.5, fee=0.0, spread=0.0, min_profit_pct=0.1,
        round_trip_cost=0.0, net_tp_manual=1.4, df=None,
    )
    fm = metrics["friction_model"]
    assert fm["commission_per_contract_side"] == pytest.approx(1.25)
    assert fm["remaining_contracts_after_tp1"] == 1
    # Perfil por defecto (sin spread ni swap): BE = entrada +/- (2.5 / $5) = 0.5 pt (LONG)
    assert fm["breakeven_points_intraday"] == pytest.approx(0.5)
    assert fm["breakeven_price_intraday"] == pytest.approx(6000.5) or fm["breakeven_price_intraday"] == pytest.approx(5999.5)
    assert fm["breakeven_price_overnight"] == pytest.approx(fm["breakeven_price_intraday"])
