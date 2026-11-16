"""
Pruebas Unitarias y de Integración para el Registro Central de Estrategias Cuantitativas.
"""

import pytest
import pandas as pd
from fastapi.testclient import TestClient
from backend import main
from backend.estrategias import (
    STRATEGY_REGISTRY,
    get_strategy,
    list_strategies,
    is_valid_strategy,
    get_supported_strategy_ids,
    get_allowed_timeframes,
    MeanReversionATR,
)


def test_list_strategies_endpoint():
    client = TestClient(main.app)
    response = client.get("/api/strategies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    ids = {s["id"] for s in data}
    # Oficiales activas (4 sólidas)
    assert "manual" in ids
    assert "auto" in ids
    assert "kula_balam_cava_ruiz" in ids
    assert "tres_velas_wyckoff_bulkowski" in ids
    assert len(ids) == 4

    # Alias /api/estrategias
    res_es = client.get("/api/estrategias")
    assert res_es.status_code == 200
    assert len(res_es.json()) == len(data)

    # Catálogo de Laboratorio / Caja de Ideas
    res_lab = client.get("/api/strategies/laboratory")
    assert res_lab.status_code == 200
    lab_ids = {s["id"] for s in res_lab.json()}
    assert "mean_reversion_atr" in lab_ids
    assert "nasdaq_araujo_vwap" in lab_ids
    assert "hyenuk_chu_multibagger" in lab_ids
    assert "trailing_trend_runner" in lab_ids
    assert "trailing_short_runner" in lab_ids

    # Con include_laboratory=true
    res_all = client.get("/api/strategies?include_laboratory=true")
    assert res_all.status_code == 200
    all_ids = {s["id"] for s in res_all.json()}
    assert ids.issubset(all_ids)
    assert lab_ids.issubset(all_ids)


def test_registry_helper_functions():
    assert is_valid_strategy("manual") is True
    assert is_valid_strategy("kula_balam_cava_ruiz") is True
    assert is_valid_strategy("mean_reversion_atr") is True
    assert is_valid_strategy("nasdaq_araujo_vwap") is True
    assert is_valid_strategy("hyenuk_chu_multibagger") is True
    assert is_valid_strategy("trailing_trend_runner") is True
    assert is_valid_strategy("trailing_short_runner") is True
    assert is_valid_strategy("tres_velas_wyckoff_bulkowski") is True
    assert is_valid_strategy("estrategia_inexistente") is False

    supported = get_supported_strategy_ids()
    assert "manual" in supported
    assert "kula_balam_cava_ruiz" in supported
    assert "mean_reversion_atr" in supported
    assert "nasdaq_araujo_vwap" in supported
    assert "hyenuk_chu_multibagger" in supported
    assert "trailing_trend_runner" in supported
    assert "trailing_short_runner" in supported
    assert "tres_velas_wyckoff_bulkowski" in supported

    strat = get_strategy("mean_reversion_atr")
    assert strat is not None
    assert isinstance(strat, MeanReversionATR)
    assert get_strategy("manual") is None

    # Timeframes permitidos
    assert get_allowed_timeframes("manual") == {"1m", "5m", "15m", "1h"}
    assert get_allowed_timeframes("kula_balam_cava_ruiz") == {"1m", "5m", "15m", "1h", "4h", "1d"}
    assert get_allowed_timeframes("mean_reversion_atr") == {"15m", "1h"}
    assert get_allowed_timeframes("nasdaq_araujo_vwap") == {"15m"}
    assert get_allowed_timeframes("hyenuk_chu_multibagger") == {"1h"}
    assert get_allowed_timeframes("trailing_trend_runner") == {"15m", "1h", "4h"}
    assert get_allowed_timeframes("tres_velas_wyckoff_bulkowski") == {"1m", "5m", "15m", "1h", "4h", "1d"}


def test_invalid_strategy_rejected_with_422():
    client = TestClient(main.app)
    res = client.get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=local&strategy=estrategia_ficticia"
    )
    assert res.status_code == 422
    assert res.json()["detail"] == "Estrategia no soportada."


def test_mean_reversion_atr_timeframe_restriction():
    client = TestClient(main.app)
    # 1m y 5m deben ser rechazados con HTTP 422 para mean_reversion_atr
    res_1m = client.get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local&strategy=mean_reversion_atr"
    )
    assert res_1m.status_code == 422
    assert "solo admite temporalidades" in res_1m.json()["detail"]

    res_5m = client.get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=5m&engine=local&strategy=mean_reversion_atr"
    )
    assert res_5m.status_code == 422
    assert "solo admite temporalidades" in res_5m.json()["detail"]


def test_nasdaq_araujo_timeframe_restriction():
    client = TestClient(main.app)
    res_1m = client.get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local&strategy=nasdaq_araujo_vwap"
    )
    assert res_1m.status_code == 422
    assert "solo admite temporalidades" in res_1m.json()["detail"]


def test_nasdaq_araujo_evaluar_signals():
    import pandas as pd
    from backend.estrategias.nasdaq_araujo_vwap import NasdaqAraujoVWAP

    strat = NasdaqAraujoVWAP()
    
    # 1. Caso COMPRA: precio sobre VWAP, sobre Londres y quebrando máximo reciente
    df_bull = pd.DataFrame([
        {"open": 100, "high": 105, "low": 99, "close": 102, "volume": 1000},
        {"open": 102, "high": 108, "low": 101, "close": 107, "volume": 1200},
        {"open": 107, "high": 112, "low": 106, "close": 111, "volume": 1500},
    ] * 5)
    ind_bull = {
        "latest": {"close": 120, "high": 121, "low": 118, "vwap": 110},
        "z_score": 0.5,
        "ema_200_value": 100.0,
        "atr_14": 2.0,
        "relative_volume": 1.5,
        "lower_wick_ratio": 0.3,
    }
    metrics, net_tp, eligible, failures, min_tp = strat.evaluar(
        ind=ind_bull, tp=2.0, sl=1.0, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=1.7, df=df_bull
    )
    assert metrics["suggested_signal"] == "COMPRAR"
    assert eligible is True
    assert len(failures) == 0

    # 2. Caso MANTENER por falta de confluencia (bajo VWAP pero sobre Londres)
    ind_neutral = {
        "latest": {"close": 105, "high": 106, "low": 104, "vwap": 115},
        "z_score": -0.5,
        "ema_200_value": 100.0,
        "atr_14": 2.0,
        "relative_volume": 1.0,
        "lower_wick_ratio": 0.2,
    }
    metrics_neu, _, eligible_neu, failures_neu, _ = strat.evaluar(
        ind=ind_neutral, tp=2.0, sl=1.0, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=1.7, df=df_bull
    )
    assert eligible_neu is False
    assert any("confluencia" in f.lower() for f in failures_neu)


def test_hyenuk_chu_timeframe_restriction():
    client = TestClient(main.app)
    res_15m = client.get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=local&strategy=hyenuk_chu_multibagger"
    )
    assert res_15m.status_code == 422
    assert "solo admite temporalidades" in res_15m.json()["detail"]


def test_hyenuk_chu_evaluar_signals():
    from backend.estrategias.hyenuk_chu_multibagger import HyenukChuMultibagger

    strat = HyenukChuMultibagger()

    # 1. Caso COMPRAR: precio sobre EMA200 alcista y SMA20, RSI sano (55), RVOL suficiente
    ind_bull = {
        "latest": {"close": 150.0, "sma_20": 140.0, "rsi": 55.0},
        "ema_200_value": 120.0,
        "ema_200_slope_pct": 0.05,
        "relative_volume": 1.2,
    }
    metrics, net_tp, eligible, failures, min_tp = strat.evaluar(
        ind=ind_bull, tp=3.5, sl=1.75, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=3.2
    )
    assert metrics["suggested_signal"] == "COMPRAR"
    assert eligible is True
    assert len(failures) == 0

    # 2. Caso MANTENER por euforia extrema (RSI > 75)
    ind_euphoria = {
        "latest": {"close": 150.0, "sma_20": 140.0, "rsi": 82.0},
        "ema_200_value": 120.0,
        "ema_200_slope_pct": 0.05,
        "relative_volume": 1.2,
    }
    metrics_eup, _, eligible_eup, failures_eup, _ = strat.evaluar(
        ind=ind_euphoria, tp=3.5, sl=1.75, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=3.2
    )
    assert metrics_eup["suggested_signal"] == "MANTENER"
    assert eligible_eup is False
    assert any("euforia" in f.lower() for f in failures_eup)


def test_auto_orchestrator_resolution():
    from datetime import datetime
    from backend.estrategias.registry import resolve_auto_strategy, ARG_TIMEZONE

    # 1. Fin de semana (Sábado a las 14:00 ARG):
    # En activos cripto activa Trailing Dinámico (Idea Raúl); en acciones tradicionales manual
    dt_sat = datetime(2026, 10, 17, 14, 0, tzinfo=ARG_TIMEZONE)
    strat_id, reason = resolve_auto_strategy("BTC/USDT", {"z_score": 0.0}, now_dt=dt_sat)
    assert strat_id == "trailing_trend_runner"
    assert "Fin de semana" in reason

    strat_id_stock, reason_stock = resolve_auto_strategy("AAPL", {"z_score": 0.0}, now_dt=dt_sat)
    assert strat_id_stock == "manual"
    assert "cerrados" in reason_stock

    # 2. Lunes a las 11:00 ARG (Campana de apertura Wall Street):
    # Índices/Acciones (QQQ/SPY) -> nasdaq_araujo_vwap; Cripto (BTC/USDT) mantiene trailing_trend_runner 24/7
    dt_mon_morning = datetime(2026, 10, 19, 11, 0, tzinfo=ARG_TIMEZONE)
    strat_id_eq, reason_eq = resolve_auto_strategy("QQQ", {"z_score": 0.5}, now_dt=dt_mon_morning)
    assert strat_id_eq == "nasdaq_araujo_vwap"
    assert "apertura de Wall Street" in reason_eq

    strat_id_btc, _ = resolve_auto_strategy("BTC/USDT", {"z_score": 0.5}, now_dt=dt_mon_morning)
    assert strat_id_btc == "trailing_trend_runner"

    # 3. Miércoles a las 15:30 ARG (Sesión regular de tendencia):
    # Índices/Acciones (QQQ/SPY) -> hyenuk_chu_multibagger; Cripto (BTC/USDT) mantiene trailing_trend_runner 24/7
    dt_wed_afternoon = datetime(2026, 10, 21, 15, 30, tzinfo=ARG_TIMEZONE)
    strat_id_eq_pm, reason_eq_pm = resolve_auto_strategy("QQQ", {"z_score": 0.2}, now_dt=dt_wed_afternoon)
    assert strat_id_eq_pm == "hyenuk_chu_multibagger"
    assert "Swing Trend" in reason_eq_pm

    strat_id_btc_pm, _ = resolve_auto_strategy("BTC/USDT", {"z_score": 0.2}, now_dt=dt_wed_afternoon)
    assert strat_id_btc_pm == "trailing_trend_runner"

    # 4. Miércoles a las 21:00 ARG (Día hábil fuera de horario bursátil >= 17:00 ARG):
    # Cripto opera con Trailing Dinámico (Idea Raúl); acciones tradicionales manual
    dt_wed_night = datetime(2026, 10, 21, 21, 0, tzinfo=ARG_TIMEZONE)
    strat_id, reason = resolve_auto_strategy("BTC/USDT", {"z_score": 0.1}, now_dt=dt_wed_night)
    assert strat_id == "trailing_trend_runner"
    assert "Fuera de horario bursátil" in reason

    strat_id_stock_night, reason_stock_night = resolve_auto_strategy("AAPL", {"z_score": 0.1}, now_dt=dt_wed_night)
    assert strat_id_stock_night == "manual"

    # 5. Pánico / Capitulación extrema (Z-Score <= -2.0) en cualquier momento -> mean_reversion_atr
    strat_id, reason = resolve_auto_strategy("BTC/USDT", {"z_score": -2.3}, now_dt=dt_sat)
    assert strat_id == "mean_reversion_atr"
    assert "Capitulación extrema" in reason

    # 6. Pullback / Retroceso saludable (-1.2 <= Z-Score <= -0.4) en cualquier momento -> mean_reversion_atr
    strat_id, reason = resolve_auto_strategy("BTC/USDT", {"z_score": -0.8}, now_dt=dt_sat)
    assert strat_id == "mean_reversion_atr"
    assert "Retroceso saludable" in reason

    from backend.estrategias.registry import is_asset_market_open
    assert is_asset_market_open("BTC/USDT", now_dt=dt_sat) is True
    assert is_asset_market_open("QQQ", now_dt=dt_sat) is False
    assert is_asset_market_open("QQQ", now_dt=dt_wed_night) is False
    assert is_asset_market_open("QQQ", now_dt=dt_wed_afternoon) is True


def test_auto_strategy_evaluation():
    from datetime import datetime
    from backend.estrategias.registry import evaluate_strategy, ARG_TIMEZONE

    # Evaluando en modo "auto" un Lunes a las 15:00 ARG en un activo bursátil (QQQ) -> delega en hyenuk_chu_multibagger
    dt_mon_afternoon = datetime(2026, 10, 19, 15, 0, tzinfo=ARG_TIMEZONE)
    ind = {
        "symbol": "QQQ",
        "latest": {"close": 150.0, "sma_20": 140.0, "rsi": 55.0},
        "ema_200_value": 120.0,
        "ema_200_slope_pct": 0.05,
        "relative_volume": 1.2,
        "z_score": 0.1,
    }
    metrics, net_tp, eligible, failures, min_tp = evaluate_strategy(
        strategy_id="auto",
        ind=ind,
        tp=3.5,
        sl=1.75,
        fee=0.1,
        spread=0.05,
        min_profit_pct=0.15,
        round_trip_cost=0.3,
        net_tp_manual=3.2,
        now_dt=dt_mon_afternoon,
    )
    assert "auto_orchestrator" in metrics
    assert metrics["auto_orchestrator"]["selected_strategy"] == "hyenuk_chu_multibagger"
    assert metrics["suggested_signal"] == "COMPRAR"
    assert eligible is True


def test_trailing_trend_runner_timeframe_restriction():
    client = TestClient(main.app)
    # 1m y 5m deben ser rechazados con HTTP 422 para trailing_trend_runner (15m, 1h, 4h permitidos)
    for tf in ("1m", "5m"):
        res = client.get(
            f"/api/market/analysis?symbol=BTC/USDT&timeframe={tf}&engine=local&strategy=trailing_trend_runner"
        )
        assert res.status_code == 422
        assert "solo admite temporalidades" in res.json()["detail"]


def test_trailing_trend_runner_evaluar_signals():
    from backend.estrategias.trailing_trend_runner import TrailingTrendRunner

    strat = TrailingTrendRunner()

    # 1. Caso COMPRAR (Tendencia alcista confluente, RSI sano, RVOL institucional)
    ind_bull = {
        "latest": {"close": 100.0, "sma_20": 98.0, "rsi": 55.0},
        "ema_200_value": 90.0,
        "ema_200_slope_pct": 0.08,
        "relative_volume": 1.3,
        "atr_14": 1.2,
    }
    metrics, net_tp, eligible, failures, min_tp = strat.evaluar(
        ind=ind_bull, tp=6.0, sl=2.0, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=5.7
    )
    assert metrics["suggested_signal"] == "COMPRAR"
    assert eligible is True
    assert len(failures) == 0
    assert metrics["trailing_no_ceiling"] is True
    assert metrics["sl_gross_pct"] == 2.0  # Estrategia Ganadora: SL inicial 2.0% protector fuera del ruido ATR

    # 2. Caso MANTENER por precio bajo EMA200 (fuera de tendencia)
    ind_downtrend = {
        "latest": {"close": 85.0, "sma_20": 86.0, "rsi": 50.0},
        "ema_200_value": 95.0,
        "ema_200_slope_pct": -0.1,
        "relative_volume": 1.0,
        "atr_14": 1.0,
    }
    metrics_down, _, eligible_down, failures_down, _ = strat.evaluar(
        ind=ind_downtrend, tp=6.0, sl=2.0, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=5.7
    )
    assert metrics_down["suggested_signal"] == "MANTENER"
    assert eligible_down is False
    assert any("ema200" in f.lower() for f in failures_down)

    # 3. Caso MANTENER por euforia extrema (RSI > 72)
    ind_euphoria = {
        "latest": {"close": 120.0, "sma_20": 115.0, "rsi": 78.0},
        "ema_200_value": 90.0,
        "ema_200_slope_pct": 0.08,
        "relative_volume": 1.3,
        "atr_14": 1.2,
    }
    metrics_eup, _, eligible_eup, failures_eup, _ = strat.evaluar(
        ind=ind_euphoria, tp=6.0, sl=2.0, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=5.7
    )
    assert metrics_eup["suggested_signal"] == "MANTENER"
    assert eligible_eup is False
    assert any("euforia" in f.lower() for f in failures_eup)

    # 4. Caso COMPRAR táctico temprano (Precio sobre SMA50 y SMA20 con impulso hacia EMA200)
    ind_tactical = {
        "latest": {"close": 94.6, "sma_20": 94.2, "sma_50": 93.8, "rsi": 58.0},
        "ema_200_value": 95.0,  # A menos de 0.5% de quebrar la EMA200
        "ema_200_slope_pct": 0.01,
        "relative_volume": 1.1,
        "atr_14": 1.2,
    }
    metrics_tac, _, eligible_tac, failures_tac, _ = strat.evaluar(
        ind=ind_tactical, tp=6.0, sl=2.0, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=5.7
    )
    assert metrics_tac["suggested_signal"] == "COMPRAR"
    assert eligible_tac is True
    assert len(failures_tac) == 0


def test_mean_reversion_atr_dual_path():
    from backend.estrategias.mean_reversion_atr import MeanReversionATR

    strat = MeanReversionATR()

    # 0. Verificación de seguridad (Medida Inmediata 1): Entradas LONG suspendidas por defecto
    assert strat.long_entries_suspended is True

    # 1. Camino A: Pullback saludable en tendencia alcista (precio > EMA200, Z entre -1.2 y -0.4)
    ind_pullback = {
        "latest": {"close": 100.0},
        "ema_200_value": 90.0,
        "ema_200_slope_pct": 0.05,
        "z_score": -0.8,
        "lower_wick_ratio": 0.25,
        "relative_volume": 1.1,
        "atr_14": 2.0,
    }

    # Bloqueo activo por suspensión
    _, _, susp_elig, susp_fails, _ = strat.evaluar(
        ind=ind_pullback, tp=5.0, sl=3.0, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=4.7
    )
    assert susp_elig is False
    assert any("suspendidas" in f.lower() for f in susp_fails)

    # Permitir prueba de la matemática algorítmica interna
    strat.long_entries_suspended = False

    metrics_a, net_tp_a, eligible_a, failures_a, min_tp_a = strat.evaluar(
        ind=ind_pullback, tp=5.0, sl=3.0, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=4.7
    )
    assert eligible_a is True
    assert len(failures_a) == 0
    assert metrics_a["setup"] == "Pullback en Tendencia Alcista"
    assert metrics_a["candidate_eligible"] is True

    # 2. Camino B: Rebote de pánico extremo / capitulación (Z <= -2.0, RVOL explosivo > 3.5 permitido por liquidaciones)
    ind_panico = {
        "latest": {"close": 80.0},
        "ema_200_value": 95.0,  # Perforó la media móvil por la caída violenta
        "ema_200_slope_pct": -0.02,
        "z_score": -2.4,
        "lower_wick_ratio": 0.32,
        "relative_volume": 4.8,  # RVOL explosivo institucional
        "atr_14": 3.0,
    }
    metrics_b, net_tp_b, eligible_b, failures_b, min_tp_b = strat.evaluar(
        ind=ind_panico, tp=7.5, sl=4.5, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=7.2
    )
    assert eligible_b is True
    assert len(failures_b) == 0
    assert metrics_b["setup"] == "Rebote de Pánico Extremo (Z ≤ -2.0)"
    assert metrics_b["candidate_eligible"] is True

    # 3. Caso MANTENER: En tierra de nadie (bajo EMA200 pero Z no llega a pánico extremo)
    ind_no_setup = {
        "latest": {"close": 85.0},
        "ema_200_value": 95.0,
        "ema_200_slope_pct": -0.01,
        "z_score": -1.0,
        "lower_wick_ratio": 0.15,
        "relative_volume": 1.0,
        "atr_14": 2.0,
    }
    metrics_c, net_tp_c, eligible_c, failures_c, min_tp_c = strat.evaluar(
        ind=ind_no_setup, tp=5.0, sl=3.0, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=4.7
    )
    assert eligible_c is False
    assert len(failures_c) > 0
    assert metrics_c["setup"] is None

    # 4. Caso MANTENER: Pullback con volumen excesivo (RVOL 4.2 > 3.5 denota avalancha, no retroceso sano)
    ind_pullback_vol_excess = {
        "latest": {"close": 100.0},
        "ema_200_value": 90.0,
        "ema_200_slope_pct": 0.05,
        "z_score": -0.8,
        "lower_wick_ratio": 0.25,
        "relative_volume": 4.2,  # Excede ATR_RELATIVE_VOLUME_MAX en retroceso
        "atr_14": 2.0,
    }
    metrics_d, _, eligible_d, failures_d, _ = strat.evaluar(
        ind=ind_pullback_vol_excess, tp=5.0, sl=3.0, fee=0.1, spread=0.05, min_profit_pct=0.15,
        round_trip_cost=0.3, net_tp_manual=4.7
    )
    assert eligible_d is False
    assert any("retroceso excesivo" in f.lower() for f in failures_d)


def test_auto_strategy_with_cio_engine_produces_informative_reason(monkeypatch):
    from fastapi.testclient import TestClient
    from backend import main
    import time
    from tests.test_regressions import _quant_strategy_candles

    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="15m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)

    client = TestClient(main.app)
    res = client.get("/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=antigravity_cio&strategy=auto")
    assert res.status_code == 200
    data = res.json()
    assert data["signal"] == "MANTENER"
    assert data["reason"] != "Filtro determinista (auto): "
    assert len(data["reason"]) > 25


def test_antigravity_operador_engine_execution(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import main
    import time
    from tests.test_regressions import _quant_strategy_candles

    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="15m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)
    monkeypatch.setattr(main, "BRAIN_STATE_PATH", str(tmp_path / "brain_state.json"))

    client = TestClient(main.app)
    
    # 1. Sin posición previa y sin confluencia -> MANTENER
    res = client.get("/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=antigravity_operador&strategy=01_tendencia_institucional_15m")
    assert res.status_code == 200
    data = res.json()
    assert data["signal"] in ("MANTENER", "COMPRAR")
    assert "[Antigravity Operador" in data["reason"]

    # 2. Con posición activa y TP alcanzado -> VENDER
    # Si entry_price es 100 y último close es ~90000, PnL es enorme
    res_tp = client.get("/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=antigravity_operador&strategy=01_tendencia_institucional_15m&has_position=true&entry_price=100.0&tp=2.0")
    assert res_tp.status_code == 200
    data_tp = res_tp.json()
    assert data_tp["signal"] == "VENDER"
    assert "Take Profit" in data_tp["reason"]

    # 3. Configuración de cerebro vía endpoint
    res_brain = client.post("/api/system/brain", json={"engine": "antigravity_operador", "model": "antigravity_operador"})
    assert res_brain.status_code == 200
    assert res_brain.json()["engine"] == "antigravity_operador"


def test_cazador_rebotes_02_integration(monkeypatch):
    from fastapi.testclient import TestClient
    from backend import main
    import time
    from tests.test_regressions import _quant_strategy_candles

    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="15m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)

    client = TestClient(main.app)
    res = client.get("/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=antigravity_operador&strategy=02_cazador_rebotes_atr_15m")
    assert res.status_code == 200
    data = res.json()
    assert data["strategy"] == "02_cazador_rebotes_atr_15m"
    assert data["signal"] in ("COMPRAR", "MANTENER")
    assert "strategy_metrics" in data
    assert data["strategy_metrics"]["mode"] == "02_cazador_rebotes_atr_15m"


def test_trailing_short_runner_evaluar_signals():
    strat = get_strategy("trailing_short_runner")
    assert strat is not None

    # Escenario 1: Confluencia bajista válida (Precio < EMA200, Precio < SMA20, RSI en [28, 58], RVOL >= 0.8)
    ind_bearish = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "ema_200_value": 105.0,
        "ema_200_slope_pct": -0.15,
        "relative_volume": 1.2,
        "atr_14": 0.5,
        "latest": {
            "close": 100.0,
            "sma_20": 102.0,
            "rsi": 45.0,
        }
    }
    metrics, net_tp, cond, notes, sl = strat.evaluar(
        ind=ind_bearish,
        tp=3.0,
        sl=1.0,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.5,
        round_trip_cost=0.17,
        net_tp_manual=2.83,
    )
    assert cond is True
    assert metrics["suggested_signal"] == "SHORT"
    assert metrics["side"] == "SHORT"
    assert metrics["net_rr"] >= 2.0
    assert sl <= 1.50
    assert net_tp >= sl * 2.0

    # Escenario 2: Sobreventa extrema (RSI < 28) -> Bloqueado por filtro anti-capitulación
    ind_oversold = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "ema_200_value": 105.0,
        "ema_200_slope_pct": -0.15,
        "relative_volume": 1.2,
        "atr_14": 0.5,
        "latest": {
            "close": 100.0,
            "sma_20": 102.0,
            "rsi": 22.0,  # Extremadamente sobrevendido
        }
    }
    m2, tp2, c2, n2, sl2 = strat.evaluar(
        ind=ind_oversold,
        tp=3.0,
        sl=1.0,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.5,
        round_trip_cost=0.17,
        net_tp_manual=2.83,
    )
    assert c2 is False
    assert m2["suggested_signal"] == "MANTENER"
    assert "sobreventa extrema" in n2[0]

    # Escenario 3: Alcista (Precio > EMA200) -> MANTENER
    ind_bullish = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "ema_200_value": 95.0,
        "ema_200_slope_pct": 0.15,
        "relative_volume": 1.2,
        "atr_14": 0.5,
        "latest": {
            "close": 100.0,
            "sma_20": 98.0,
            "rsi": 55.0,
        }
    }
    m3, tp3, c3, n3, sl3 = strat.evaluar(
        ind=ind_bullish,
        tp=3.0,
        sl=1.0,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.5,
        round_trip_cost=0.17,
        net_tp_manual=2.83,
    )
    assert c3 is False
    assert m3["suggested_signal"] == "MANTENER"

    # Escenario 4: Falsa ruptura / Alineación de medias contraria (SMA20 > EMA200) -> MANTENER
    ind_contrary_ma = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "ema_200_value": 80654.84,
        "ema_200_slope_pct": -0.0069,
        "relative_volume": 1.4,
        "atr_14": 150.0,
        "latest": {
            "close": 80626.01,
            "sma_20": 80674.23,  # SMA20 > EMA200 (falla estructura bajista)
            "rsi": 42.0,
        }
    }
    m4, _, c4, notes4, _ = strat.evaluar(
        ind=ind_contrary_ma,
        tp=3.0, sl=1.0, fee=0.075, spread=0.02,
        min_profit_pct=0.5, round_trip_cost=0.17, net_tp_manual=2.83,
    )
    assert c4 is False
    assert m4["suggested_signal"] == "MANTENER"
    assert any("SMA20" in note and "EMA200" in note for note in notes4)

    # Escenario 5: Zona de fricción con EMA200 (< 0.20% de distancia) -> MANTENER
    ind_friction = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "ema_200_value": 100.0,
        "ema_200_slope_pct": -0.15,
        "relative_volume": 1.2,
        "atr_14": 0.5,
        "latest": {
            "close": 99.90,  # 0.10% de distancia (< 0.20% umbral)
            "sma_20": 99.95,
            "rsi": 45.0,
        }
    }
    m5, _, c5, notes5, _ = strat.evaluar(
        ind=ind_friction,
        tp=3.0, sl=1.0, fee=0.075, spread=0.02,
        min_profit_pct=0.5, round_trip_cost=0.17, net_tp_manual=2.83,
    )
    assert c5 is False
    assert m5["suggested_signal"] == "MANTENER"
    assert any("zona de fricción" in note for note in notes5)

    # Escenario 6: Candado macro bajista no confirmado en Cripto -> MANTENER
    ind_macro_unconfirmed = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "ema_200_value": 105.0,
        "ema_200_slope_pct": -0.15,
        "relative_volume": 1.2,
        "atr_14": 0.5,
        "macro_bearish": False,
        "latest": {
            "close": 100.0,
            "sma_20": 102.0,
            "rsi": 45.0,
        }
    }
    m6, _, c6, notes6, _ = strat.evaluar(
        ind=ind_macro_unconfirmed,
        tp=3.0, sl=1.0, fee=0.075, spread=0.02,
        min_profit_pct=0.5, round_trip_cost=0.17, net_tp_manual=2.83,
    )
    assert c6 is False
    assert m6["suggested_signal"] == "MANTENER"
    assert any("Régimen macro multitemporal" in note for note in notes6)


def test_resolve_auto_strategy_bearish_routes_to_short():
    from backend.estrategias.registry import resolve_auto_strategy
    from datetime import datetime, timezone, timedelta
    arg_tz = timezone(timedelta(hours=-3))

    # Fuera de hora Wall Street (ej. 20:00 ARG un martes)
    dt_night = datetime(2026, 10, 20, 20, 0, tzinfo=arg_tz)
    ind_bearish = {
        "ema_200_value": 105.0,
        "latest": {
            "close": 98.0,
            "sma_20": 100.0,
            "rsi": 42.0,
        }
    }
    # En Forex (=X), régimen bajista va directamente a trailing_short_runner
    strat_id_fx, reason_fx = resolve_auto_strategy("EUR/USD=X", ind_bearish, now_dt=dt_night)
    assert strat_id_fx == "trailing_short_runner"
    assert "régimen bajista confirmado" in reason_fx.lower()

    # En Cripto (/), régimen bajista sin confirmación macro va a mean_reversion_atr (compra en pullback)
    strat_id_crypto, reason_crypto = resolve_auto_strategy("BTC/USDT", ind_bearish, now_dt=dt_night)
    assert strat_id_crypto == "mean_reversion_atr"
    assert "retroceso intradía" in reason_crypto.lower()

    # En Cripto con macro bajista confirmada, sí autoriza trailing_short_runner
    ind_macro_bearish = dict(ind_bearish)
    ind_macro_bearish["macro_bearish"] = True
    strat_id_macro, reason_macro = resolve_auto_strategy("BTC/USDT", ind_macro_bearish, now_dt=dt_night)
    assert strat_id_macro == "trailing_short_runner"

    # Si es alcista (precio > EMA200), va a trailing_trend_runner
    ind_bullish = {
        "ema_200_value": 90.0,
        "latest": {
            "close": 98.0,
            "sma_20": 95.0,
            "rsi": 55.0,
        }
    }
    strat_id_bull, reason_bull = resolve_auto_strategy("BTC/USDT", ind_bullish, now_dt=dt_night)
    assert strat_id_bull == "trailing_trend_runner"


def test_tres_velas_wyckoff_bulkowski_evaluar_signals():
    import pandas as pd
    from backend.estrategias.tres_velas_wyckoff_bulkowski import EstrategiaTresVelas

    strat = EstrategiaTresVelas()

    # 1. Caso Morning Star sobre VWAP con RVOL alto -> COMPRAR
    df_morning_star = pd.DataFrame([
        # Vela 1: bajista amplia
        {"open": 100.0, "high": 100.5, "low": 90.0, "close": 91.0, "volume": 1000},
        # Vela 2: pequeña indecisión (doji)
        {"open": 90.8, "high": 91.5, "low": 90.0, "close": 90.5, "volume": 600},
        # Vela 3: fuerte rebote alcista penetrando > 50% de vela 1 (91 + 4.5 = 95.5)
        {"open": 90.6, "high": 98.0, "low": 90.2, "close": 97.0, "volume": 1800},
    ])
    ind_valid = {
        "latest": {"close": 97.0, "high": 98.0, "low": 90.2, "vwap": 94.0, "atr_14": 2.0},
        "live_price": 97.0,
        "current_price_real": 97.0,
        "vwap": 94.0,
        "atr_14": 2.0,
        "relative_volume": 1.8,
    }
    metrics, net_tp, eligible, failures, min_tp = strat.evaluar(
        ind=ind_valid,
        tp=4.0,
        sl=1.5,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.17,
        net_tp_manual=3.83,
        df=df_morning_star,
    )
    assert eligible is True
    assert metrics["suggested_signal"] == "COMPRAR"
    assert metrics["detected_pattern"] == "Morning Star"
    assert metrics["pattern_reliability_bulkowski"] == 0.78
    assert metrics["net_rr"] >= 2.0
    assert metrics["above_vwap"] is True

    # 2. Caso Three White Soldiers -> COMPRAR
    df_soldiers = pd.DataFrame([
        {"open": 90.0, "high": 93.0, "low": 89.8, "close": 92.5, "volume": 1000},
        {"open": 92.0, "high": 95.5, "low": 91.8, "close": 95.0, "volume": 1200},
        {"open": 94.8, "high": 98.5, "low": 94.5, "close": 98.0, "volume": 1500},
    ])
    ind_soldiers = {
        "live_price": 98.0,
        "vwap": 93.0,
        "atr_14": 1.5,
        "relative_volume": 1.6,
        "latest": {"close": 98.0, "vwap": 93.0, "atr_14": 1.5},
    }
    m_sold, tp_sold, elig_sold, fail_sold, _ = strat.evaluar(
        ind=ind_soldiers,
        tp=4.0,
        sl=1.5,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.17,
        net_tp_manual=3.83,
        df=df_soldiers,
    )
    assert elig_sold is True
    assert m_sold["suggested_signal"] == "COMPRAR"
    assert m_sold["detected_pattern"] == "Three White Soldiers"
    assert m_sold["pattern_reliability_bulkowski"] == 0.82

    # 3. Caso Rechazo por operar bajo VWAP (Patrón alcista pero mercado bajo agua)
    ind_under_vwap = {
        "live_price": 97.0,
        "vwap": 105.0,  # VWAP muy por encima
        "atr_14": 2.0,
        "relative_volume": 1.8,
        "latest": {"close": 97.0, "vwap": 105.0, "atr_14": 2.0},
    }
    m_vwap, _, elig_vwap, fail_vwap, _ = strat.evaluar(
        ind=ind_under_vwap,
        tp=4.0,
        sl=1.5,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.17,
        net_tp_manual=3.83,
        df=df_morning_star,
    )
    assert elig_vwap is False
    assert m_vwap["suggested_signal"] == "MANTENER"
    assert any("debajo del VWAP" in f for f in fail_vwap)

    # 4. Caso Rechazo por volumen insuficiente (RVOL < 1.3)
    ind_low_vol = {
        "live_price": 97.0,
        "vwap": 94.0,
        "atr_14": 2.0,
        "relative_volume": 0.8,  # RVOL insuficiente
        "latest": {"close": 97.0, "vwap": 94.0, "atr_14": 2.0},
    }
    m_vol, _, elig_vol, fail_vol, _ = strat.evaluar(
        ind=ind_low_vol,
        tp=4.0,
        sl=1.5,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.17,
        net_tp_manual=3.83,
        df=df_morning_star,
    )
    assert elig_vol is False
    assert any("Volumen insuficiente" in f for f in fail_vol)

    # 5. Caso Sistema Dual: Three Black Crows bajo VWAP -> SHORT
    df_crows = pd.DataFrame([
        {"open": 100.0, "high": 100.2, "low": 96.0, "close": 96.5, "volume": 1200},
        {"open": 96.2, "high": 96.5, "low": 93.0, "close": 93.5, "volume": 1400},
        {"open": 93.4, "high": 93.5, "low": 89.5, "close": 90.0, "volume": 1800},
    ])
    ind_crows = {
        "live_price": 90.0,
        "vwap": 95.0,  # cotizando bajo VWAP
        "atr_14": 1.5,
        "relative_volume": 1.6,
        "rsi": 42.0,
        "latest": {"close": 90.0, "vwap": 95.0, "atr_14": 1.5, "rsi": 42.0},
    }
    m_crows, tp_crows, elig_crows, fail_crows, _ = strat.evaluar(
        ind=ind_crows,
        tp=4.0,
        sl=1.5,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.17,
        net_tp_manual=3.83,
        df=df_crows,
    )
    assert elig_crows is True
    assert m_crows["suggested_signal"] == "SHORT"
    assert m_crows["side"] == "SHORT"
    assert m_crows["detected_pattern"] == "Three Black Crows"
    assert m_crows["pattern_reliability_bulkowski"] == 0.79
    assert m_crows["net_rr"] >= 2.0

    # 6. Caso Sistema Dual: Evening Star bajo VWAP -> SHORT
    df_evening_star = pd.DataFrame([
        # Vela 1: alcista amplia
        {"open": 90.0, "high": 99.5, "low": 89.5, "close": 99.0, "volume": 1000},
        # Vela 2: pequeña indecisión (doji)
        {"open": 99.2, "high": 100.0, "low": 98.8, "close": 99.5, "volume": 600},
        # Vela 3: fuerte caída bajista penetrando > 50% de vela 1
        {"open": 99.1, "high": 99.3, "low": 91.0, "close": 92.0, "volume": 1800},
    ])
    ind_evening = {
        "live_price": 92.0,
        "vwap": 97.0,  # cotizando bajo VWAP
        "atr_14": 2.0,
        "relative_volume": 1.7,
        "rsi": 45.0,
        "latest": {"close": 92.0, "vwap": 97.0, "atr_14": 2.0, "rsi": 45.0},
    }
    m_eve, _, elig_eve, fail_eve, _ = strat.evaluar(
        ind=ind_evening,
        tp=4.0,
        sl=1.5,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.17,
        net_tp_manual=3.83,
        df=df_evening_star,
    )
    assert elig_eve is True
    assert m_eve["suggested_signal"] == "SHORT"
    assert m_eve["side"] == "SHORT"
    assert m_eve["detected_pattern"] == "Evening Star"
    assert m_eve["pattern_reliability_bulkowski"] == 0.72

    # 7. Caso Anti-Capitulación en Corto: RSI < 28 bloquea el SHORT
    ind_panic_short = {
        "live_price": 90.0,
        "vwap": 95.0,
        "atr_14": 1.5,
        "relative_volume": 1.6,
        "rsi": 22.0,  # sobreventa extrema
        "latest": {"close": 90.0, "vwap": 95.0, "atr_14": 1.5, "rsi": 22.0},
    }
    m_pan, _, elig_pan, fail_pan, _ = strat.evaluar(
        ind=ind_panic_short,
        tp=4.0,
        sl=1.5,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.17,
        net_tp_manual=3.83,
        df=df_crows,
    )
    assert elig_pan is False
    assert m_pan["suggested_signal"] == "MANTENER"
    assert any("sobreventa extrema" in f for f in fail_pan)

    # 8. Caso Blindaje Wyckoff (Combinación 2): Veto Bull Trap por mecha superior >= 25%
    df_morning_bull_trap = pd.DataFrame([
        {"open": 100.0, "high": 100.5, "low": 90.0, "close": 91.0, "volume": 1000},
        {"open": 90.8, "high": 91.5, "low": 90.0, "close": 90.5, "volume": 600},
        # Range total: 102.0 - 90.2 = 11.8. Cierre en 96.0. Mecha superior: 102.0 - 96.0 = 6.0 (50.8% del rango)
        {"open": 90.6, "high": 102.0, "low": 90.2, "close": 96.0, "volume": 1800},
    ])
    ind_bt = {
        "latest": {"close": 96.0, "high": 102.0, "low": 90.2, "vwap": 94.0, "atr_14": 2.0},
        "live_price": 96.0,
        "vwap": 94.0,
        "atr_14": 2.0,
        "relative_volume": 1.8,
        "rsi": 55.0,
    }
    m_bt, _, elig_bt, fail_bt, _ = strat.evaluar(
        ind=ind_bt,
        tp=4.0,
        sl=1.5,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.17,
        net_tp_manual=3.83,
        df=df_morning_bull_trap,
    )
    assert elig_bt is False
    assert any("Veto Bull Trap" in f for f in fail_bt)


def test_kula_balam_cava_ruiz_evaluation():
    """
    Verifica la evaluación táctica de la estrategia Kula Balam (Alex Ruiz + José Luis Cava):
    - Tríada fractal (1D Contexto -> 1H Zona Dorada Fibonacci -> 5M Gatillo).
    - Cierre sobre EMA50.
    - Asimetría matemática R:R >= 2.0.
    - Margen de invalidación adaptativo de 2 ticks.
    - Activación de compuertas de veto si se rompe la zona dorada o surge bull trap.
    """
    strat = get_strategy("kula_balam_cava_ruiz")
    assert strat is not None
    assert strat.id == "kula_balam_cava_ruiz"

    # Construir DataFrame sintético de 35 velas
    # Swing: parte en 90, sube a 100, retrocede a ~94.5 (Golden Zone 55%), y cierra en 95.0 sobre EMA50
    records = []
    base_price = 90.0
    for i in range(25):
        price = base_price + (i * 0.4)  # sube hasta 100.0
        records.append({
            "open": price - 0.2,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 1000.0 + (i * 10),
        })

    # Retroceso controlado con secado de volumen a la zona 94.5
    for i, p in enumerate([98.0, 96.5, 95.2, 94.2, 94.0]):
        records.append({
            "open": p + 0.5,
            "high": p + 0.8,
            "low": p - 0.3,
            "close": p,
            "volume": 300.0 - (i * 20),  # secado de volumen claro (RVOL < 0.85)
        })

    # Vela gatillo de rebote en 94.8 con mecha inferior de absorción (cierra en 95.0)
    records.append({
        "open": 94.2,
        "high": 95.2,
        "low": 93.9,
        "close": 95.0,
        "volume": 850.0,
    })

    df_setup = pd.DataFrame(records)

    ind_ok = {
        "live_price": 95.0,
        "atr_14": 1.2,
        "relative_volume": 1.1,
        "lower_wick_ratio": 0.30,  # absorción institucional presente
        "rsi": 48.0,
        "symbol": "BTC/USDT",
        "latest": {"close": 95.0, "atr_14": 1.2, "relative_volume": 1.1, "rsi": 48.0},
    }

    metrics, net_tp, eligible, failures, min_tp = strat.evaluar(
        ind=ind_ok,
        tp=3.0,
        sl=1.2,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.19,
        net_tp_manual=2.81,
        df=df_setup,
    )

    assert eligible is True, f"Fallo inesperado de filtros: {failures}"
    assert metrics["suggested_signal"] == "COMPRAR"
    assert metrics["side"] == "LONG"
    assert metrics["in_golden_zone"] is True
    assert metrics["net_rr_ratio"] >= 2.0
    assert metrics["sl_margin_2ticks_pct"] > 0
    assert "peluqueo_rule" in metrics

    # Caso Veto 1: Perforación profunda de Fibonacci (> 0.78 de retroceso)
    records_broken = list(records)
    # Colapsar precio a 91.0 (retroceso > 90% desde 100 hasta 90)
    records_broken.append({
        "open": 93.0,
        "high": 93.2,
        "low": 90.8,
        "close": 91.0,
        "volume": 1200.0,
    })
    df_broken = pd.DataFrame(records_broken)
    ind_broken = dict(ind_ok, live_price=91.0)
    m_brk, _, elig_brk, fail_brk, _ = strat.evaluar(
        ind=ind_broken,
        tp=3.0,
        sl=1.2,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.19,
        net_tp_manual=2.81,
        df=df_broken,
    )
    assert elig_brk is False
    assert m_brk["suggested_signal"] == "MANTENER"
    assert any("perforó el 0.75 de Fibonacci" in f for f in fail_brk)

    # Caso Veto 2: Bull trap (mecha superior >= 50%)
    records_trap = list(records)
    records_trap[-1] = {
        "open": 94.2,
        "high": 97.0,  # mecha superior enorme (97.0 - 94.5 = 2.5 vs rango total 3.0 -> 83%)
        "low": 94.0,
        "close": 94.5,
        "volume": 850.0,
    }
    df_trap = pd.DataFrame(records_trap)
    m_trap, _, elig_trap, fail_trap, _ = strat.evaluar(
        ind=ind_ok,
        tp=3.0,
        sl=1.2,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.50,
        round_trip_cost=0.19,
        net_tp_manual=2.81,
        df=df_trap,
    )
    assert elig_trap is False
    assert any("Veto Bull Trap" in f for f in fail_trap)


def test_evaluate_strategy_with_allowed_strategies():
    from backend.estrategias.registry import evaluate_strategy
    dummy_ind = {
        "symbol": "BTC/USDT",
        "close": 100.0,
        "rsi": 50.0,
        "atr_14": 1.5,
        "z_score": -0.5,
        "relative_volume": 1.0,
        "ema_200_value": 90.0,
        "ema_200_slope_pct": 0.5,
        "lower_wick_ratio": 0.3,
        "latest": {"close": 100.0, "rsi": 50.0, "symbol": "BTC/USDT"},
    }
    # 1. Sin estrategias autorizadas (lista vacía)
    metrics, net_tp, elig, fails, _ = evaluate_strategy(
        strategy_id="auto",
        ind=dummy_ind,
        tp=2.1,
        sl=0.6,
        fee=0.1,
        spread=0.05,
        min_profit_pct=0.5,
        round_trip_cost=0.3,
        net_tp_manual=1.8,
        allowed_strategies=[],
    )
    assert elig is False
    assert any("Sin fórmulas" in f for f in fails)

    # 2. Con estrategias específicas autorizadas
    metrics2, net_tp2, elig2, fails2, _ = evaluate_strategy(
        strategy_id="auto",
        ind=dummy_ind,
        tp=2.1,
        sl=0.6,
        fee=0.1,
        spread=0.05,
        min_profit_pct=0.5,
        round_trip_cost=0.3,
        net_tp_manual=1.8,
        allowed_strategies=["kula_balam_cava_ruiz"],
    )
    # Debe evaluar únicamente la autorizada
    assert isinstance(metrics2, dict)


def test_daemon_allowed_strategies_start():
    client = TestClient(main.app)
    res = client.post("/api/daemon/start", json={
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "strategy": "auto",
        "allowed_strategies": ["kula_balam_cava_ruiz", "tres_velas_wyckoff_bulkowski"],
        "tp": 2.1,
        "sl": 0.6,
        "mode": "smart"
    })
    assert res.status_code == 200
    stat = client.get("/api/daemon/status").json()
    assert "allowed_strategies" in stat
    assert "kula_balam_cava_ruiz" in stat["allowed_strategies"]
    assert "tres_velas_wyckoff_bulkowski" in stat["allowed_strategies"]
    client.post("/api/daemon/stop")


def test_alex_ruiz_triada_3velas_registration_and_properties():
    from backend.estrategias.registry import get_strategy, is_valid_strategy, STRATEGY_REGISTRY
    assert is_valid_strategy("alex_ruiz_triada_3velas") is True
    assert "alex_ruiz_triada_3velas" in STRATEGY_REGISTRY
    strat = get_strategy("alex_ruiz_triada_3velas")
    assert strat is not None
    info = strat.to_dict()
    assert info["id"] == "alex_ruiz_triada_3velas"
    assert "Alex Ruiz" in info["nombre"]
    assert "5m" in info["temporalidades_permitidas"]


def test_alex_ruiz_triada_3velas_long_and_safety_shorts():
    from backend.estrategias.alex_ruiz_triada_3velas import AlexRuizTriada3Velas
    strat = AlexRuizTriada3Velas()

    # 1. Simulación LONG válida
    # Impulso alcista de 100 a 120, luego retroceso a la Zona Dorada Fibo (0.50-0.75) cerrando sobre EMA 50
    prices_long = [102.0] * 20
    prices_long += [100.0]  # swing low en 100
    prices_long += [102.0 + (i * 1.8) for i in range(11)]  # sube a 120
    prices_long += [120.0 - (i * 1.2) for i in range(10)]  # retrocede a ~109.2
    df_long = pd.DataFrame({
        "open": [p * 0.999 for p in prices_long],
        "high": [p * 1.002 for p in prices_long],
        "low": [p * 0.998 for p in prices_long],
        "close": prices_long,
        "volume": [1000.0] * len(prices_long)
    })
    # Últimas 3 velas: V1 caída a 107.8, V2 pausa en 108.0, V3 rompe a 109.2
    df_long.iloc[-3] = {"open": 109.0, "high": 109.1, "low": 107.5, "close": 107.8, "volume": 1000}
    df_long.iloc[-2] = {"open": 107.8, "high": 108.3, "low": 107.5, "close": 108.0, "volume": 800}
    df_long.iloc[-1] = {"open": 108.0, "high": 109.5, "low": 107.8, "close": 109.2, "volume": 2000}

    ind_long = {
        "symbol": "BTC/USDT",
        "live_price": 109.2,
        "atr_14": 0.8,
        "rsi": 52.0,
        "relative_volume": 1.5,
        "lower_wick_ratio": 0.25,
        "upper_wick_ratio": 0.15,
        "sma_50": 105.0,
    }

    metrics, net_tp, eligible, failures, min_p = strat.evaluar(
        ind=ind_long,
        tp=2.1,
        sl=0.6,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.5,
        round_trip_cost=0.17,
        net_tp_manual=1.9,
        df=df_long,
    )
    assert eligible is True
    assert metrics["suggested_signal"] == "COMPRAR"
    assert metrics["target_side"] == "LONG"
    assert metrics["net_rr_ratio"] >= 2.0

    # 2. Simulación SHORT válida con confluencia
    # Tendencia bajista: caída de 140 a 100 y rebote correctivo a la Zona Dorada Fibo (0.50-0.75) cerrando bajo EMA 50
    prices_short = [140.0 - (i * 2.0) for i in range(21)]  # 140 cae a 100
    prices_short += [100.0 + (i * 2.4) for i in range(11)]  # 100 rebota a 124
    df_short = pd.DataFrame({
        "open": [p * 0.999 for p in prices_short],
        "high": [p * 1.002 for p in prices_short],
        "low": [p * 0.998 for p in prices_short],
        "close": prices_short,
        "volume": [1000.0] * len(prices_short)
    })
    # V1 rebote a 124.5, V2 doji pausa en 124.2, V3 quiebre bajista a 121.8 bajo EMA 50
    df_short.iloc[-3] = {"open": 123.5, "high": 124.8, "low": 123.4, "close": 124.5, "volume": 1000}
    df_short.iloc[-2] = {"open": 124.5, "high": 124.8, "low": 124.0, "close": 124.2, "volume": 800}
    df_short.iloc[-1] = {"open": 124.2, "high": 124.3, "low": 121.5, "close": 121.8, "volume": 2200}

    ind_short = {
        "symbol": "ETH/USDT",
        "side": "SHORT",
        "live_price": 121.8,
        "atr_14": 0.8,
        "rsi": 45.0,  # En rango sano, no sobreventa
        "relative_volume": 1.4,
        "lower_wick_ratio": 0.10,
        "upper_wick_ratio": 0.20,
        "sma_50": 128.0,
    }

    m_s, net_tp_s, elig_s, fails_s, _ = strat.evaluar(
        ind=ind_short,
        tp=2.1,
        sl=0.6,
        fee=0.075,
        spread=0.02,
        min_profit_pct=0.5,
        round_trip_cost=0.17,
        net_tp_manual=1.9,
        df=df_short,
    )
    assert elig_s is True
    assert m_s["suggested_signal"] == "SHORT"
    assert m_s["target_side"] == "SHORT"
    assert m_s["net_rr_ratio"] >= 2.0

    # 3. COMPUERTAS DE SEGURIDAD SHORT:
    # A) Veto Bear Trap: Mecha inferior excesiva (>= 40%) en V3
    df_trap = df_short.copy()
    # Vela de rango 121.0 a 124.0 (3.0 pts), close en 122.8, low en 121.0 -> mecha inferior = 1.8 / 3.0 = 60%
    df_trap.iloc[-1] = {"open": 123.5, "high": 124.0, "low": 121.0, "close": 122.8, "volume": 2000}
    _, _, elig_trap, fails_trap, _ = strat.evaluar(
        ind=ind_short, tp=2.1, sl=0.6, fee=0.075, spread=0.02, min_profit_pct=0.5, round_trip_cost=0.17, net_tp_manual=1.9, df=df_trap
    )
    assert elig_trap is False
    assert any("Bear Trap" in f for f in fails_trap)

    # B) Veto Clímax de Sobreventa: RSI <= 30.0 no puede shortear
    ind_oversold = dict(ind_short)
    ind_oversold["rsi"] = 28.0
    _, _, elig_os, fails_os, _ = strat.evaluar(
        ind=ind_oversold, tp=2.1, sl=0.6, fee=0.075, spread=0.02, min_profit_pct=0.5, round_trip_cost=0.17, net_tp_manual=1.9, df=df_short
    )
    assert elig_os is False
    assert any("Sobreventa" in f for f in fails_os)


def test_alex_ruiz_evaluar_oportunidad_multitemporal_backtest():
    from backend.estrategias.alex_ruiz_triada_3velas import AlexRuizTriada3Velas
    strat = AlexRuizTriada3Velas()

    def _generar_serie(precios):
        return pd.DataFrame({
            "open": [p * 0.999 for p in precios],
            "high": [p * 1.002 for p in precios],
            "low": [p * 0.998 for p in precios],
            "close": precios,
            "volume": [1000.0] * len(precios),
        })

    # Caso 1: LONG
    df_1d_l = _generar_serie([100.0 + (i * 0.8) for i in range(60)])
    df_1h_l = _generar_serie([140.0 + (i * 1.0) for i in range(21)] + [160.0 - (i * 1.2) for i in range(11)])
    df_5m_l = _generar_serie([147.0 + (i * 0.02) for i in range(60)])
    df_5m_l.iloc[-3] = {"open": 148.2, "high": 148.3, "low": 147.4, "close": 147.5, "volume": 1200}
    df_5m_l.iloc[-2] = {"open": 147.5, "high": 147.9, "low": 147.4, "close": 147.7, "volume": 800}
    df_5m_l.iloc[-1] = {"open": 147.7, "high": 148.8, "low": 147.6, "close": 148.6, "volume": 2500}

    op_long = strat.evaluar_oportunidad("BTC/USDT", df_1d_l, df_1h_l, df_5m_l)
    assert op_long is not None
    assert op_long["direccion"] == "LONG"
    assert op_long["ratio_rr"] == "1:2.00"

    # Caso 2: SHORT
    df_1d_s = _generar_serie([160.0 - (i * 0.8) for i in range(60)])
    df_1h_s = _generar_serie([130.0 - (i * 1.5) for i in range(21)] + [100.0 + (i * 1.8) for i in range(11)])
    df_5m_s = _generar_serie([119.0 - (i * 0.02) for i in range(60)])
    df_5m_s.iloc[-3] = {"open": 117.8, "high": 118.6, "low": 117.7, "close": 118.5, "volume": 1200}
    df_5m_s.iloc[-2] = {"open": 118.5, "high": 118.6, "low": 118.1, "close": 118.2, "volume": 750}
    df_5m_s.iloc[-1] = {"open": 118.2, "high": 118.3, "low": 117.2, "close": 117.3, "volume": 2400}

    op_short = strat.evaluar_oportunidad("SOL/USDT", df_1d_s, df_1h_s, df_5m_s)
    assert op_short is not None
    assert op_short["direccion"] == "SHORT"
    assert op_short["ratio_rr"] == "1:2.00"


def test_strategy_config_manager_and_endpoints():
    from backend.estrategias.config_manager import StrategyConfigManager
    client = TestClient(main.app)

    # 1. GET /api/estrategias/config
    res = client.get("/api/estrategias/config")
    assert res.status_code == 200
    configs = res.json()
    assert "kula_balam_cava_ruiz" in configs
    assert "alex_ruiz_triada_3velas" in configs
    assert "tres_velas_wyckoff_bulkowski" in configs

    # 2. Desmarcar subestrategia 'operar_short' en alex_ruiz_triada_3velas
    toggle_res = client.post("/api/estrategias/toggle_sub", json={
        "strategy_id": "alex_ruiz_triada_3velas",
        "sub_id": "operar_short",
        "enabled": False,
    })
    assert toggle_res.status_code == 200
    assert StrategyConfigManager.is_sub_enabled("alex_ruiz_triada_3velas", "operar_short") is False

    # 3. Volver a activarla
    toggle_res2 = client.post("/api/estrategias/toggle_sub", json={
        "strategy_id": "alex_ruiz_triada_3velas",
        "sub_id": "operar_short",
        "enabled": True,
    })
    assert toggle_res2.status_code == 200
    assert StrategyConfigManager.is_sub_enabled("alex_ruiz_triada_3velas", "operar_short") is True

    # 4. Actualizar parámetros
    param_res = client.post("/api/estrategias/update_params", json={
        "strategy_id": "alex_ruiz_triada_3velas",
        "parameters": {"min_rr_ratio": 2.5},
    })
    assert param_res.status_code == 200
    assert StrategyConfigManager.get_parameter("alex_ruiz_triada_3velas", "min_rr_ratio") == 2.5

    # Restaurar
    client.post("/api/estrategias/update_params", json={
        "strategy_id": "alex_ruiz_triada_3velas",
        "parameters": {"min_rr_ratio": 2.0},
    })

    # 5. Toggle active
    active_res = client.post("/api/estrategias/toggle_active", json={
        "strategy_id": "alex_ruiz_triada_3velas",
        "active": True,
    })
    assert active_res.status_code == 200
    assert StrategyConfigManager.is_strategy_active("alex_ruiz_triada_3velas") is True

    # 6. Restablecer valores de fábrica (Reset Defaults)
    client.post("/api/estrategias/update_params", json={
        "strategy_id": "alex_ruiz_triada_3velas",
        "parameters": {"min_rr_ratio": 9.99},
    })
    assert StrategyConfigManager.get_parameter("alex_ruiz_triada_3velas", "min_rr_ratio") == 9.99
    reset_res = client.post("/api/estrategias/reset_defaults", json={
        "strategy_id": "alex_ruiz_triada_3velas"
    })
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "ok"
    assert StrategyConfigManager.get_parameter("alex_ruiz_triada_3velas", "min_rr_ratio") == 2.0


def test_nasdaq_araujo_vwap_safeguards_and_shorts():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import pandas as pd
    from backend.estrategias.nasdaq_araujo_vwap import NasdaqAraujoVWAP
    from backend.estrategias.config_manager import StrategyConfigManager

    strat = NasdaqAraujoVWAP()
    ny_tz = ZoneInfo("America/New_York")

    # Martes 10:00 NY (dentro de ventana 09:35 - 11:00 NY)
    valid_tuesday_ny = datetime(2026, 11, 3, 10, 0, tzinfo=ny_tz)
    # Martes 09:32 NY (primeros 5 minutos de subasta caótica)
    opening_noise_ny = datetime(2026, 11, 3, 9, 32, tzinfo=ny_tz)
    # Sábado 10:00 NY (fin de semana)
    weekend_ny = datetime(2026, 11, 7, 10, 0, tzinfo=ny_tz)

    df_sample = pd.DataFrame([
        {"open": 400, "high": 402, "low": 398, "close": 401, "volume": 10000},
        {"open": 401, "high": 403, "low": 399, "close": 402, "volume": 12000},
        {"open": 402, "high": 404, "low": 400, "close": 403, "volume": 15000},
    ] * 5)

    # 1. Caso SHORT válido: QQQ cotizando bajo VWAP (398.5 vs 401), rebote testeando VWAP con mecha superior >= 30% y RVOL 1.5
    ind_short = {
        "symbol": "QQQ",
        "latest": {"open": 399.5, "high": 401.0, "low": 398.0, "close": 398.5, "vwap": 401.0},
        "relative_volume": 1.5,
        "rsi_14": 45.0,
        "atr_14": 1.5,
    }
    m, net_tp, elig, fails, _ = strat.evaluar(
        ind=ind_short, tp=2.0, sl=1.0, fee=0.05, spread=0.02, min_profit_pct=0.20,
        round_trip_cost=0.15, net_tp_manual=1.8, df=df_sample, now_dt=valid_tuesday_ny
    )
    assert m["signal"] == "VENDER"
    assert m["sub_strategy"] == "araujo_vwap_short"
    assert elig is True
    assert len(fails) == 0
    assert any("Stop a Misa" in s for s in m["applied_safeguards"])

    # 2. Veto Cripto 24/7 (BTC/USDT)
    ind_crypto = {**ind_short, "symbol": "BTC/USDT"}
    _, _, elig_c, fails_c, _ = strat.evaluar(
        ind=ind_crypto, tp=2.0, sl=1.0, fee=0.05, spread=0.02, min_profit_pct=0.20,
        round_trip_cost=0.15, net_tp_manual=1.8, df=df_sample, now_dt=valid_tuesday_ny
    )
    assert elig_c is False
    assert any("par cripto 24/7" in f for f in fails_c)

    # 3. Veto Primeros 5 Minutos (09:32 NY)
    _, _, elig_noise, fails_noise, _ = strat.evaluar(
        ind=ind_short, tp=2.0, sl=1.0, fee=0.05, spread=0.02, min_profit_pct=0.20,
        round_trip_cost=0.15, net_tp_manual=1.8, df=df_sample, now_dt=opening_noise_ny
    )
    assert elig_noise is False
    assert any("Primeros 5 min" in f for f in fails_noise)

    # 4. Veto Fin de Semana
    _, _, elig_wknd, fails_wknd, _ = strat.evaluar(
        ind=ind_short, tp=2.0, sl=1.0, fee=0.05, spread=0.02, min_profit_pct=0.20,
        round_trip_cost=0.15, net_tp_manual=1.8, df=df_sample, now_dt=weekend_ny
    )
    assert elig_wknd is False
    assert any("fin de semana" in f for f in fails_wknd)

    # 5. Veto Clímax de Sobreventa RSI <= 30 (anti-squeeze)
    ind_rsi_oversold = {**ind_short, "rsi_14": 25.0}
    _, _, elig_rsi, fails_rsi, _ = strat.evaluar(
        ind=ind_rsi_oversold, tp=2.0, sl=1.0, fee=0.05, spread=0.02, min_profit_pct=0.20,
        round_trip_cost=0.15, net_tp_manual=1.8, df=df_sample, now_dt=valid_tuesday_ny
    )
    assert elig_rsi is False
    assert any("RSI" in f and "Sobreventa" in f for f in fails_rsi)

    # 6. Desactivar subestrategia SHORT vía config manager
    StrategyConfigManager.toggle_sub_strategy("nasdaq_araujo_vwap", "operar_short", False)
    _, _, elig_off, fails_off, _ = strat.evaluar(
        ind=ind_short, tp=2.0, sl=1.0, fee=0.05, spread=0.02, min_profit_pct=0.20,
        round_trip_cost=0.15, net_tp_manual=1.8, df=df_sample, now_dt=valid_tuesday_ny
    )
    assert elig_off is False
    assert any("Subestrategia SHORT desactivada" in f for f in fails_off)
    # Restaurar
    StrategyConfigManager.toggle_sub_strategy("nasdaq_araujo_vwap", "operar_short", True)


def test_hyenuk_chu_multibagger_safeguards_and_elephant_candle():
    from backend.estrategias.hyenuk_chu_multibagger import HyenukChuMultibagger
    from backend.estrategias.config_manager import StrategyConfigManager

    strat = HyenukChuMultibagger()

    # 1. Caso COMPRAR con Vela Elefante en 1H:
    # Open: 140, High: 151, Low: 139.5, Close: 150 (Vela verde con cuerpo de 10 puntos, mecha sup = 1 punto / 11.5 = 8.7% <= 25%)
    ind_elephant = {
        "symbol": "NVDA",
        "timeframe": "1h",
        "latest": {
            "open": 140.0,
            "high": 151.0,
            "low": 139.5,
            "close": 150.0,
            "sma_20": 138.0,
            "rsi": 58.0,
        },
        "ema_200_value": 130.0,
        "ema_200_slope_pct": 0.08,
        "relative_volume": 1.6,
        "atr_14": 4.5,
    }

    metrics, net_tp, eligible, failures, _ = strat.evaluar(
        ind=ind_elephant, tp=4.0, sl=2.0, fee=0.05, spread=0.02, min_profit_pct=0.20,
        round_trip_cost=0.15, net_tp_manual=3.8
    )

    assert metrics["signal"] == "COMPRAR"
    assert eligible is True
    assert len(failures) == 0
    assert any("Vela Elefante" in s for s in metrics["applied_safeguards"])
    assert any("Stop Estructural" in s for s in metrics["applied_safeguards"])
    assert any("Peluqueo 50%" in s for s in metrics["applied_safeguards"])

    # 2. Veto por Euforia (RSI > 75)
    ind_euphoria = {
        **ind_elephant,
        "latest": {**ind_elephant["latest"], "rsi": 80.0},
    }
    _, _, elig_eup, fails_eup, _ = strat.evaluar(
        ind=ind_euphoria, tp=4.0, sl=2.0, fee=0.05, spread=0.02, min_profit_pct=0.20,
        round_trip_cost=0.15, net_tp_manual=3.8
    )
    assert elig_eup is False
    assert any("euforia" in f.lower() for f in fails_eup)

    # 3. Veto por Mecha Superior Excesiva (Rechazo en techos > 25%)
    ind_big_wick = {
        **ind_elephant,
        "latest": {
            **ind_elephant["latest"],
            "open": 140.0,
            "high": 160.0,
            "low": 139.5,
            "close": 145.0,  # Upper wick = 160 - 145 = 15 points (73% of range)
        },
    }
    _, _, elig_wick, fails_wick, _ = strat.evaluar(
        ind=ind_big_wick, tp=4.0, sl=2.0, fee=0.05, spread=0.02, min_profit_pct=0.20,
        round_trip_cost=0.15, net_tp_manual=3.8
    )
    assert elig_wick is False
    assert any("Mecha superior excesiva" in f for f in fails_wick)

    # 4. Conmutar subestrategia operar_long vía StrategyConfigManager
    StrategyConfigManager.toggle_sub_strategy("hyenuk_chu_multibagger", "operar_long", False)
    _, _, elig_off, fails_off, _ = strat.evaluar(
        ind=ind_elephant, tp=4.0, sl=2.0, fee=0.05, spread=0.02, min_profit_pct=0.20,
        round_trip_cost=0.15, net_tp_manual=3.8
    )
    assert elig_off is False
    assert any("Subestrategia LONG desactivada" in f for f in fails_off)
    # Restaurar
    StrategyConfigManager.toggle_sub_strategy("hyenuk_chu_multibagger", "operar_long", True)


def test_alex_ruiz_triada_gold_gcf():
    """Valida la calibración de Oro (GC=F) en Alex Ruiz Tríada (ventana COMEX, Fibo 0.70 y mechas 35%)."""
    from datetime import datetime, timezone, timedelta
    from backend.estrategias.alex_ruiz_triada_3velas import AlexRuizTriada3Velas
    from backend.estrategias.config_manager import StrategyConfigManager

    strat = AlexRuizTriada3Velas()
    assert "GC=F" in strat.activos_recomendados

    # Miércoles 11:30 ART (Dentro de la ventana COMEX 09:30 - 14:00 ARG)
    dt_open = datetime(2026, 11, 4, 11, 30, tzinfo=timezone(timedelta(hours=-3)))

    prices_gold = [3720.0] * 25
    prices_gold += [3720.0 + (i * 18.0) for i in range(11)]  # sube a 3900 (rango 180)
    prices_gold += [3900.0 - (i * 10.0) for i in range(10)]  # retrocede a ~3810 (~50% retroceso)
    df_gold = pd.DataFrame({
        "open": [p * 0.999 for p in prices_gold],
        "high": [p * 1.002 for p in prices_gold],
        "low": [p * 0.998 for p in prices_gold],
        "close": prices_gold,
        "volume": [1500.0] * len(prices_gold),
    })
    # 3 velas en 5M en 3805-3810: V1 pausa en 3795, V2 doji en 3800, V3 confirma rompiendo V2 a 3810
    df_gold.iloc[-3] = {"open": 3805.0, "high": 3808.0, "low": 3795.0, "close": 3798.0, "volume": 1200}
    df_gold.iloc[-2] = {"open": 3798.0, "high": 3803.0, "low": 3796.0, "close": 3800.0, "volume": 1000}
    df_gold.iloc[-1] = {"open": 3800.0, "high": 3812.0, "low": 3799.0, "close": 3810.0, "volume": 2500}

    ind_gold = {
        "symbol": "GC=F",
        "live_price": 3810.0,
        "atr_14": 8.5,
        "rsi": 54.0,
        "relative_volume": 1.4,
        "lower_wick_ratio": 0.20,
        "upper_wick_ratio": 0.15,
        "sma_50": 3760.0,
        "now_dt": dt_open,
    }

    metrics, net_tp, eligible, failures, _ = strat.evaluar(
        ind=ind_gold, tp=2.0, sl=0.8, fee=0.04, spread=0.01,
        min_profit_pct=0.3, round_trip_cost=0.09, net_tp_manual=1.9,
        df=df_gold,
    )
    assert eligible is True
    assert metrics["suggested_signal"] == "COMPRAR"
    assert metrics["in_golden_zone"] is True

    # 2. Fuera de ventana institucional (ej: 15:30 ART)
    dt_closed = datetime(2026, 11, 4, 15, 30, tzinfo=timezone(timedelta(hours=-3)))
    ind_gold_closed = dict(ind_gold, now_dt=dt_closed)
    _, _, elig_c, fails_c, _ = strat.evaluar(
        ind=ind_gold_closed, tp=2.0, sl=0.8, fee=0.04, spread=0.01,
        min_profit_pct=0.3, round_trip_cost=0.09, net_tp_manual=1.9,
        df=df_gold,
    )
    assert elig_c is False
    assert any("fuera de ventana institucional COMEX" in f for f in fails_c)

    # 3. Veto Bull Trap en Oro (Mecha superior >= 35%)
    df_bull_trap = df_gold.copy()
    df_bull_trap.iloc[-1] = {"open": 3800.0, "high": 3825.0, "low": 3799.0, "close": 3805.0, "volume": 2500}
    # Rango total = 26, Upper wick = 3825 - 3805 = 20 -> 20/26 = 76.9% >= 35%
    _, _, elig_bt, fails_bt, _ = strat.evaluar(
        ind=ind_gold, tp=2.0, sl=0.8, fee=0.04, spread=0.01,
        min_profit_pct=0.3, round_trip_cost=0.09, net_tp_manual=1.9,
        df=df_bull_trap,
    )
    assert elig_bt is False
    assert any("Veto Bull Trap" in f for f in fails_bt)


def test_triple_confluencia_4h_evaluacion():
    import pandas as pd
    from backend.estrategias.triple_confluencia_4h import TripleConfluencia4H

    strat = TripleConfluencia4H()
    assert strat.id == "triple_confluencia_4h"
    assert "4h" in strat.temporalidades_permitidas

    # Crear serie histórica simulada con tendencia alcista y expansión de volatilidad creciente
    prices = [100.0 + i * 1.5 for i in range(40)]
    # Volatilidad en expansión: rangos high-low que crecen en las últimas velas
    highs = [p + (1.0 + (i * 0.1)) for i, p in enumerate(prices)]
    lows = [p - (1.0 + (i * 0.1)) for i, p in enumerate(prices)]
    df_bull = pd.DataFrame({
        "open": [p - 0.5 for p in prices],
        "high": highs,
        "low": lows,
        "close": prices,
        "volume": [1000 + i * 50 for i in range(40)],
    })

    ind_bull = {
        "symbol": "BTC/USDT",
        "timeframe": "4h",
        "live_price": prices[-1],
        "latest": {
            "close": prices[-1],
            "rsi": 62.0,
            "sma_20": prices[-3],
        },
        "relative_volume": 1.25,
        "atr_14": 2.5,
    }

    metrics, net_tp, eligible, failures, min_p = strat.evaluar(
        ind=ind_bull, tp=4.0, sl=2.0, fee=0.1, spread=0.05, min_profit_pct=0.5,
        round_trip_cost=0.3, net_tp_manual=3.7, df=df_bull
    )

    assert metrics["suggested_signal"] in ("COMPRAR", "MANTENER")
    assert metrics["side"] in ("LONG", "MANTENER")
    assert metrics["volatility_expansion"] is True
    assert metrics["net_rr"] >= 1.95


def test_donchian_breakout_1h_evaluacion():
    """Valida la formulación matemática empírica de DonchianBreakout1H sobre velas 1H."""
    import pandas as pd
    from backend.estrategias.donchian_breakout_1h import DonchianBreakout1H

    strat = DonchianBreakout1H()

    # Construir 35 velas 1H sintéticas con canal comprimido previo y ruptura alcista
    n = 35
    highs = []
    lows = []
    closes = []
    volumes = []

    # Primeras 33 velas en rango estrecho [95, 100]
    for i in range(33):
        lows.append(95.0 + (i % 2) * 1.0)
        highs.append(99.0 + (i % 2) * 1.0)
        closes.append(97.0 + (i % 2) * 1.0)
        volumes.append(100.0)

    # Vela 34: RUPTURA ALCISTA DONCHIAN
    # Máximo Donchian previo (rolling 20 con shift 1): 100.0
    lows.append(99.0)
    highs.append(105.0)
    closes.append(103.5)  # Close > donchian_high (103.5 > 100.0)
    volumes.append(250.0)  # Volumen 250 > 100 * 1.25 (125)

    df_breakout = pd.DataFrame({
        "timestamp": [1600000000 + i * 3600 for i in range(34)],
        "open": [closes[max(0, i - 1)] for i in range(34)],
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })

    ind_breakout = {
        "symbol": "ETH/USDT",
        "timeframe": "1h",
        "live_price": closes[-1],
        "latest": {
            "close": closes[-1],
        },
        "atr_14": 2.0,
    }

    metrics, net_tp, eligible, failures, min_p = strat.evaluar(
        ind=ind_breakout, tp=6.0, sl=3.0, fee=0.075, spread=0.02, min_profit_pct=0.2,
        round_trip_cost=0.17, net_tp_manual=5.83, df=df_breakout
    )

    assert eligible is True
    assert len(failures) == 0
    assert metrics["suggested_signal"] == "COMPRAR"
    assert metrics["side"] == "LONG"
    assert metrics["cond_quiebre"] is True
    assert metrics["cond_tendencia"] is True
    assert metrics["cond_compresion"] is True
    assert metrics["cond_volumen"] is True
    assert metrics["donchian_high"] == 100.0
    assert metrics["mid_exit_price"] > 0
    assert metrics["net_rr"] >= 1.95

    # 2. Caso Bloqueo por Falta de Volumen
    df_low_vol = df_breakout.copy()
    df_low_vol.loc[df_low_vol.index[-1], "volume"] = 80.0  # Menor que SMA20 * 1.25
    metrics_lv, _, eligible_lv, failures_lv, _ = strat.evaluar(
        ind=ind_breakout, tp=6.0, sl=3.0, fee=0.075, spread=0.02, min_profit_pct=0.2,
        round_trip_cost=0.17, net_tp_manual=5.83, df=df_low_vol
    )
    assert eligible_lv is False
    assert any("volumen" in f.lower() for f in failures_lv)


def test_donchian_breakout_1h_btc_intraday_veto():
    """Valida que BTC en temporalidades intradía (< 1D) sea descalificado por Veto Nativo."""
    from backend.estrategias.donchian_breakout_1h import DonchianBreakout1H

    strat = DonchianBreakout1H()
    ind_btc = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "live_price": 50000.0,
        "latest": {"close": 50000.0},
        "atr_14": 500.0,
    }
    metrics, net_tp, eligible, failures, _ = strat.evaluar(
        ind=ind_btc, tp=6.0, sl=3.0, fee=0.075, spread=0.02, min_profit_pct=0.2,
        round_trip_cost=0.17, net_tp_manual=5.83, df=None
    )
    assert eligible is False
    assert any("VETO NATIVO: BTC" in f for f in failures)

















def test_umbral_breakeven_por_estrategia_donchian_y_fallback():
    """donchian_breakout_1h arma Breakeven a +1.00% bruto; el resto usa el fallback de +0.40%."""
    from backend.daemon import BE_THRESHOLD_GROSS_BY_STRATEGY, BE_THRESHOLD_GROSS_DEFAULT

    assert BE_THRESHOLD_GROSS_DEFAULT == 0.40
    assert BE_THRESHOLD_GROSS_BY_STRATEGY.get("donchian_breakout_1h") == 1.00
    for strat in ("kula_balam_cava_ruiz", "tres_velas_wyckoff_bulkowski", "triple_confluencia_4h", "manual", None):
        assert BE_THRESHOLD_GROSS_BY_STRATEGY.get(strat, BE_THRESHOLD_GROSS_DEFAULT) == 0.40


def test_donchian_subformulas_short_mecha_sobreextension_y_compuerta():
    """
    Audita las 8 subfórmulas mejoradas de DonchianBreakout1H y su compatibilidad con entry_gate_failures:
    1. SHORT habilitado en Cripto 4H bajo régimen bajista, pero bloqueado en Acciones TradFi 1D.
    2. Veto de trampa de absorción (mecha en contra > 32%).
    3. Veto de sobreextensión respecto a EMA 50 (> 3.2x ATR).
    4. Sensibilidad real de SL/TP dinámicos ATR y aprobación en entry_gate_failures(timeframe='4h').
    """
    import pandas as pd
    from unittest.mock import patch
    from backend.estrategias.donchian_breakout_1h import DonchianBreakout1H
    from backend.entry_gate import entry_gate_failures

    strat = DonchianBreakout1H()

    # Serie bajista comprimida de 70 velas con ruptura bajista limpia en la última vela
    opens, highs, lows, closes, vols = [], [], [], [], []
    for i in range(69):
        base = 120.0 - i * 0.15  # tendencia bajista suave -> EMA macro descendiendo
        opens.append(base + 0.3)
        highs.append(base + 1.2)
        lows.append(base - 1.2)
        closes.append(base - 0.2)
        vols.append(100.0)

    # Vela 70: quiebre bajista Donchian limpio
    last_base = 120.0 - 68 * 0.15
    opens.append(last_base - 0.5)
    highs.append(last_base - 0.2)
    lows.append(last_base - 3.6)
    closes.append(last_base - 3.3)  # cierre sólido cerca del mínimo (mecha inferior < 10%)
    vols.append(180.0)  # RVOL 1.80x > 1.15x

    df_short = pd.DataFrame({
        "timestamp": [1700000000 + i * 14400 for i in range(70)],
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": vols,
    })

    # 1a. En SOL/USDT 4H -> SHORT aprobado y pasa entry_gate_failures(timeframe="4h")
    ind_sol_4h = {
        "symbol": "SOL/USDT",
        "timeframe": "4h",
        "live_price": closes[-1],
        "latest": {"open": opens[-1], "high": highs[-1], "low": lows[-1], "close": closes[-1], "volume": vols[-1]},
        "atr_14": 2.4,
    }
    m_s, _, elig_s, fails_s, _ = strat.evaluar(
        ind=ind_sol_4h, tp=6.0, sl=3.0, fee=0.10, spread=0.05,
        min_profit_pct=0.2, round_trip_cost=0.30, net_tp_manual=5.7, df=df_short
    )
    assert elig_s is True, f"Esperaba SHORT elegible en SOL/USDT 4H, falló por: {fails_s}"
    assert m_s["side"] == "SHORT"
    assert m_s["suggested_signal"] == "SHORT"
    assert m_s["net_rr"] >= 2.0

    gate_fails = entry_gate_failures(
        "SOL/USDT",
        closes[-1],
        m_s["tp_gross_pct"],
        m_s["sl_gross_pct"],
        0.10,
        0.05,
        atr=m_s["atr_14"],
        rvol=1.8,
        order_side="SHORT",
        timeframe="4h",
    )
    assert gate_fails == []

    # 1b. Misma serie bajista en AAPL 1D -> SHORT bloqueado (acciones spot US solo operan LONG)
    ind_aapl_1d = {
        "symbol": "AAPL",
        "timeframe": "1d",
        "live_price": closes[-1],
        "latest": {"open": opens[-1], "high": highs[-1], "low": lows[-1], "close": closes[-1], "volume": vols[-1]},
        "atr_14": 2.4,
    }
    _, _, elig_eq, fails_eq, _ = strat.evaluar(
        ind=ind_aapl_1d, tp=6.0, sl=3.0, fee=0.0, spread=0.01,
        min_profit_pct=0.2, round_trip_cost=0.02, net_tp_manual=5.98, df=df_short
    )
    assert elig_eq is False

    # 2. Veto Anti-Trampa de Mecha: si la mecha inferior del SHORT supera 32% del rango total -> rechazado
    df_wick_trap = df_short.copy()
    df_wick_trap.loc[df_wick_trap.index[-1], "low"] = last_base - 6.0  # mecha inferior enorme de absorción
    _, _, elig_w, fails_w, _ = strat.evaluar(
        ind=ind_sol_4h, tp=6.0, sl=3.0, fee=0.10, spread=0.05,
        min_profit_pct=0.2, round_trip_cost=0.30, net_tp_manual=5.7, df=df_wick_trap
    )
    assert elig_w is False
    assert any("mecha" in f.lower() or "climática" in f.lower() for f in fails_w)

    # 3. Sensibilidad real a parámetros atr_sl_mult y target_tp_atr_mult
    custom_cfg = {
        "parameters": {
            **strat.parametros_por_defecto,
            "atr_sl_mult": 1.80,
            "target_tp_atr_mult": 4.50,
        },
        "sub_strategies": {},
    }
    with patch("backend.estrategias.config_manager.StrategyConfigManager.get_strategy_config", return_value=custom_cfg):
        m_custom, _, elig_c, _, _ = strat.evaluar(
            ind=ind_sol_4h, tp=6.0, sl=3.0, fee=0.10, spread=0.05,
            min_profit_pct=0.2, round_trip_cost=0.30, net_tp_manual=5.7, df=df_short
        )
    assert elig_c is True
    assert m_custom["sl_gross_pct"] > m_s["sl_gross_pct"]
    assert m_custom["tp_gross_pct"] > m_s["tp_gross_pct"]


def test_promoted_catalog_strategies_registered_and_evaluated_in_multi_strategy():
    """Verifica que las fórmulas promovidas al catálogo principal se registren y evalúen sin descartarse."""
    from backend.estrategias.registry import (
        STRATEGY_REGISTRY,
        evaluate_strategy,
        get_strategy,
        is_valid_strategy,
    )

    assert is_valid_strategy("squeeze_dual_eth_4h_slot1") is True
    assert is_valid_strategy("cava_fallo_macd_eurusd_1h") is True
    assert "squeeze_dual_eth_4h_slot1" in STRATEGY_REGISTRY
    assert "cava_fallo_macd_eurusd_1h" in STRATEGY_REGISTRY

    fx_strat = get_strategy("cava_fallo_macd_eurusd_1h")
    assert fx_strat is not None
    assert fx_strat.native_timeframe == "1h"
    assert "EURUSD=X" in fx_strat.activos_recomendados

    # Construir serie mínima OHLCV para validar que evaluate_strategy evalúa las 3 sin descartar las promovidas
    dates = pd.date_range("2026-11-01", periods=230, freq="1h", tz="UTC")
    closes = [1.1000 + (i * 0.0001) for i in range(230)]
    df = pd.DataFrame({
        "timestamp": [int(d.timestamp() * 1000) for d in dates],
        "open": [c - 0.0003 for c in closes],
        "high": [c + 0.0005 for c in closes],
        "low": [c - 0.0005 for c in closes],
        "close": closes,
        "volume": [1000.0] * 230,
    })
    ind = {
        "symbol": "ETH/USDT",
        "timeframe": "4h",
        "live_price": closes[-1],
        "latest": {"open": df["open"].iloc[-1], "high": df["high"].iloc[-1], "low": df["low"].iloc[-1], "close": closes[-1], "volume": 1000.0},
        "atr_14": 0.001,
        "relative_volume": 1.0,
    }
    m, _, _, fails, _ = evaluate_strategy(
        strategy_id="auto",
        ind=ind,
        tp=2.1,
        sl=0.6,
        fee=0.1,
        spread=0.05,
        min_profit_pct=0.5,
        round_trip_cost=0.3,
        net_tp_manual=1.8,
        df=df,
        allowed_strategies=["squeeze_dual_eth_4h_slot1", "donchian_breakout_1h", "cava_fallo_macd_eurusd_1h"],
    )
    assert "3 fórmulas autorizadas" in " ".join(fails) or m["auto_orchestrator"]["selected_strategy"] in (
        "squeeze_dual_eth_4h_slot1",
        "donchian_breakout_1h",
        "cava_fallo_macd_eurusd_1h",
    )

    # Aislamiento de clase de activo: cava_fallo_macd_eurusd_1h no opera cripto; squeeze_dual_eth_4h_slot1 no opera Forex
    _, _, elig_fx_on_crypto, fails_fx_c, _ = fx_strat.evaluar(
        ind=ind, tp=2.1, sl=0.6, fee=0.1, spread=0.05, min_profit_pct=0.5, round_trip_cost=0.3, net_tp_manual=1.8, df=df
    )
    assert elig_fx_on_crypto is False
    assert any("Forex" in f for f in fails_fx_c)

    sq_strat = get_strategy("squeeze_dual_eth_4h_slot1")
    assert sq_strat is not None
    ind_fx = {**ind, "symbol": "EURUSD=X"}
    _, _, elig_cr_on_fx, fails_cr_f, _ = sq_strat.evaluar(
        ind=ind_fx, tp=2.1, sl=0.6, fee=0.0, spread=0.02, min_profit_pct=0.5, round_trip_cost=0.04, net_tp_manual=2.0, df=df
    )
    assert elig_cr_on_fx is False
    assert any("Cripto" in f for f in fails_cr_f)


def test_catalog_adapter_accepts_pandas_series_latest_without_502(monkeypatch):
    """
    Regresión HTTP 502 en catalog_adapter.py:
    Cuando compute_technical_indicators devuelve ind['latest'] como pd.Series,
    evaluar() y GET /api/market/analysis no deben lanzar ValueError por verdad ambigua
    y deben aplicar costos reales de Forex (=X) si no se pasan por query.
    """
    import time
    from tests.test_regressions import _quant_strategy_candles

    dates = pd.date_range("2026-11-01", periods=230, freq="1h", tz="UTC")
    closes = [1.1200 + (i * 0.0001) for i in range(230)]
    df = pd.DataFrame({
        "timestamp": [int(d.timestamp() * 1000) for d in dates],
        "open": [c - 0.0003 for c in closes],
        "high": [c + 0.0005 for c in closes],
        "low": [c - 0.0005 for c in closes],
        "close": closes,
        "volume": [0.0] * 230,
    })
    series_latest = pd.Series({
        "open": df["open"].iloc[-1],
        "high": df["high"].iloc[-1],
        "low": df["low"].iloc[-1],
        "close": closes[-1],
        "volume": 0.0,
    })

    fx_strat = get_strategy("cava_fallo_macd_eurusd_1h")
    assert fx_strat is not None
    ind_fx = {
        "symbol": "EURUSD=X",
        "timeframe": "1h",
        "live_price": closes[-1],
        "latest": series_latest,
        "atr_14": 0.0014,
        "relative_volume": 0.0,
    }
    m_fx, *_ = fx_strat.evaluar(
        ind=ind_fx, tp=2.0, sl=1.0, fee=0.0, spread=0.012, min_profit_pct=0.20, round_trip_cost=0.024, net_tp_manual=1.9, df=df
    )
    assert isinstance(m_fx, dict)
    assert m_fx["current_price"] == pytest.approx(closes[-1], rel=1e-5)

    sq_strat = get_strategy("squeeze_dual_eth_4h_slot1")
    assert sq_strat is not None
    ind_cr = {**ind_fx, "symbol": "ETH/USDT", "timeframe": "4h"}
    m_cr, *_ = sq_strat.evaluar(
        ind=ind_cr, tp=2.0, sl=1.0, fee=0.1, spread=0.05, min_profit_pct=0.5, round_trip_cost=0.3, net_tp_manual=1.7, df=df
    )
    assert isinstance(m_cr, dict)

    # Validar vía HTTP GET /api/market/analysis sin pasar fee/spread -> sin 502 y con fricción Forex
    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="1h")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)
    monkeypatch.setattr(main, "get_cached_price", lambda sym: {"symbol": sym, "price": candles[-1][4]})
    client = TestClient(main.app)
    res = client.get("/api/market/analysis?symbol=EURUSD=X&timeframe=1h&engine=local&strategy=cava_fallo_macd_eurusd_1h")
    assert res.status_code == 200
    body = res.json()
    assert body["fee_info"]["fee_per_order"] == 0.0
    assert body["fee_info"]["spread_per_side"] == 0.012


def test_forex_sl_cost_scaling_in_trailing_runners_and_auto(monkeypatch):
    import time
    from datetime import datetime, timezone, timedelta
    from backend.estrategias.trailing_trend_runner import TrailingTrendRunner
    from backend.estrategias.trailing_short_runner import TrailingShortRunner
    from backend.estrategias.registry import resolve_auto_strategy
    from tests.test_regressions import _quant_strategy_candles

    # TrailingTrendRunner en EURUSD=X debe usar escala Forex (~0.19% SL, min_tp <= 0.20%, 5 decimales), no piso crypto 2.0%
    ind_fx_long = {
        "symbol": "EURUSD=X",
        "latest": pd.Series({"close": 1.12345, "sma_20": 1.1210, "sma_50": 1.1190, "rsi": 56.0}),
        "ema_200_value": 1.1100,
        "ema_200_slope_pct": 0.02,
        "relative_volume": 0.0,
        "atr_14": 0.0014,
    }
    m_long, _, elig_long, _, min_tp_long = TrailingTrendRunner().evaluar(
        ind=ind_fx_long, tp=2.0, sl=1.0, fee=0.0, spread=0.012, min_profit_pct=0.5, round_trip_cost=0.024, net_tp_manual=1.9
    )
    assert elig_long is True
    assert 0.12 <= m_long["sl_gross_pct"] <= 0.30
    assert min_tp_long <= 0.20
    assert m_long["current_price"] == 1.12345

    # TrailingShortRunner en EURUSD=X debe usar escala Forex (no piso crypto 0.80%)
    ind_fx_short = {
        "symbol": "EURUSD=X",
        "latest": pd.Series({"close": 1.11543, "sma_20": 1.1180, "sma_50": 1.1200, "rsi": 42.0}),
        "ema_200_value": 1.1250,
        "ema_200_slope_pct": -0.02,
        "relative_volume": 0.0,
        "atr_14": 0.0014,
    }
    m_short, _, elig_short, _, min_tp_short = TrailingShortRunner().evaluar(
        ind=ind_fx_short, tp=2.0, sl=1.0, fee=0.0, spread=0.012, min_profit_pct=0.5, round_trip_cost=0.024, net_tp_manual=1.9
    )
    assert elig_short is True
    assert 0.12 <= m_short["sl_gross_pct"] <= 0.30
    assert min_tp_short <= 0.20
    assert m_short["current_price"] == 1.11543

    # Validar también la invocación interna del daemon (fake_request sin query params reales -> sin KeyError 'query_string')
    from starlette.requests import Request as StarletteRequest
    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="1h")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)
    monkeypatch.setattr(main, "get_cached_price", lambda sym: {"symbol": sym, "price": candles[-1][4]})
    daemon_req = StarletteRequest({
        "type": "http",
        "method": "GET",
        "path": "/api/market/analysis",
        "headers": [(b"host", b"127.0.0.1")],
        "client": ("127.0.0.1", 12345),
    })
    direct_res = main.get_analysis(
        request=daemon_req,
        symbol="EURUSD=X",
        timeframe="1h",
        engine="local",
        strategy="cava_fallo_macd_eurusd_1h",
        fee=0.0,
        spread=0.012,
    )
    assert direct_res["fee_info"]["fee_per_order"] == 0.0

    # resolve_auto_strategy con Z-Score en rango [-1.2, -0.4] en Forex NO debe desviar a mean_reversion_atr (cripto)
    arg_tz = timezone(timedelta(hours=-3))
    dt_tue = datetime(2026, 10, 20, 14, 0, tzinfo=arg_tz)
    strat_id, _ = resolve_auto_strategy("EURUSD=X", {**ind_fx_long, "z_score": -0.8}, now_dt=dt_tue)
    assert strat_id == "trailing_trend_runner"

    # En horario de invierno US (EST UTC-5, nov-2026): 10:35 ART es pre-market; 11:35 ART apertura; 17:30 ART sesión regular
    assert resolve_auto_strategy("QQQ", {"z_score": 0.2}, now_dt=datetime(2026, 11, 10, 10, 35, tzinfo=arg_tz))[0] == "manual"
    assert resolve_auto_strategy("QQQ", {"z_score": 0.2}, now_dt=datetime(2026, 11, 10, 11, 35, tzinfo=arg_tz))[0] == "nasdaq_araujo_vwap"
    assert resolve_auto_strategy("QQQ", {"z_score": 0.2}, now_dt=datetime(2026, 11, 10, 17, 30, tzinfo=arg_tz))[0] == "hyenuk_chu_multibagger"


def test_nasdaq_strategies_include_sl_net_pct_without_502(tmp_path, monkeypatch):
    """
    Regresión HTTP 502 KeyError 'sl_net_pct':
    Verifica que nasdaq_araujo_vwap y hyenuk_chu_multibagger devuelvan siempre 'sl_net_pct'
    tanto en evaluación normal como en fallback _build_metrics, y pasen GET /api/market/analysis con HTTP 200.
    """
    from fastapi.testclient import TestClient
    from backend import main
    from backend.estrategias.nasdaq_araujo_vwap import NasdaqAraujoVWAP
    from backend.estrategias.hyenuk_chu_multibagger import HyenukChuMultibagger
    from tests.test_regressions import _quant_strategy_candles
    import time

    candles_15m = _quant_strategy_candles(int(time.time() * 1000), timeframe="15m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles_15m)
    monkeypatch.setattr(main, "get_cached_price", lambda sym: {"symbol": sym, "price": candles_15m[-1][4]})
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", str(tmp_path / "bias.json"))
    monkeypatch.setenv("STRATEGIES_CONFIG_PATH", str(tmp_path / "strat_cfg.json"))

    client = TestClient(main.app)
    for strat_id, tf in (("nasdaq_araujo_vwap", "15m"), ("hyenuk_chu_multibagger", "1h")):
        resp = client.get(f"/api/market/analysis?symbol=QQQ&timeframe={tf}&engine=antigravity_operador&strategy={strat_id}")
        assert resp.status_code == 200, f"{strat_id} devolvió {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "sl_net_pct" in body["strategy_metrics"]
        assert isinstance(body["strategy_metrics"]["sl_net_pct"], (int, float))

    # Verificar explícitamente rutas fallback _build_metrics de ambas estrategias
    m_araujo = NasdaqAraujoVWAP()._build_metrics("MANTENER", "HOLD", "NEUTRAL", "araujo_inactive", 2.0, 1.0, 1.7, [], [], 500.0, 498.0)
    assert "sl_net_pct" in m_araujo
    m_hyenuk = HyenukChuMultibagger()._build_metrics("MANTENER", "HOLD", "chu_out_of_hours", 2.0, 1.0, 1.7, [], [], 500.0)
    assert "sl_net_pct" in m_hyenuk




