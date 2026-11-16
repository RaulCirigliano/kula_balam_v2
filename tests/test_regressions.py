from datetime import datetime, timedelta, timezone
import json
import math
from types import SimpleNamespace
import time
from typing import get_type_hints
import sys
import importlib.util

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main, radar_inbox


@pytest.fixture(autouse=True)
def clear_optional_api_token(monkeypatch):
    monkeypatch.delenv("APP_SECRET_TOKEN", raising=False)
    monkeypatch.delenv("APP_TOKEN", raising=False)


def test_system_models_reports_offline():
    response = TestClient(main.app).get("/api/system/models")
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["models"] == []


def test_system_brain_post_persists_valid_selection(monkeypatch, tmp_path):
    state_path = tmp_path / "backend-config" / "brain_state.json"
    monkeypatch.setattr(main, "BRAIN_STATE_PATH", str(state_path))
    response = TestClient(main.app).post(
        "/api/system/brain",
        json={"engine": "ollama", "model": "deepseek-r1:8b"},
    )

    assert response.status_code == 200
    assert response.json() == {"engine": "ollama", "model": "deepseek-r1:8b"}
    assert json.loads(state_path.read_text(encoding="utf-8")) == response.json()
    assert TestClient(main.app).get("/api/system/brain").json() == response.json()


def test_system_brain_rejects_invalid_selection():
    response = TestClient(main.app).post(
        "/api/system/brain",
        json={"engine": "ollama", "model": "../untrusted"},
    )

    assert response.status_code == 422


def test_system_brain_cors_allows_monitor_origin():
    response = TestClient(main.app).options(
        "/api/system/brain",
        headers={
            "Origin": "http://127.0.0.1:8520",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8520"


def test_current_macro_promotes_timezone_aware_monitor_card(monkeypatch):
    card = SimpleNamespace(
        id="card-1",
        activo="SPY",
        impacto="POSITIVO",
        confianza=95,
        timestamp=datetime.now(timezone.utc).isoformat(),
        justificacion="Señal validada",
        titular="Titular",
    )

    class FakeInbox:
        def get_active_cards(self, hours_ttl):
            return [card]

    monkeypatch.setattr(radar_inbox, "RadarInbox", FakeInbox)
    monkeypatch.setattr(main, "INJECTED_MACRO", {"timestamp": None})

    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    result = main.get_current_injected_macro(request, None)

    assert result["asset"] == "SPY"
    assert result["source"] == "Monitor del Mercado (Auto)"
    assert result["text"] == "Señal validada"


def test_newer_manual_macro_wins_over_older_monitor_card(monkeypatch):
    now = datetime.now(timezone.utc)
    older_card = SimpleNamespace(
        id="old-card",
        activo="SPY",
        impacto="POSITIVO",
        confianza=95,
        timestamp=(now - timedelta(hours=1)).isoformat(),
        justificacion="Tesis anterior",
        titular="Titular anterior",
    )

    class FakeInbox:
        def get_active_cards(self, hours_ttl):
            return [older_card]

    monkeypatch.setattr(radar_inbox, "RadarInbox", FakeInbox)
    manual = {
        "id": "manual",
        "asset": "BTC/USDT",
        "text": "Tesis manual reciente",
        "timestamp": now.isoformat(),
    }
    monkeypatch.setattr(main, "INJECTED_MACRO", manual)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    result = main.get_current_injected_macro(request, None)

    assert result["id"] == "manual"


def test_radar_inbox_keeps_recent_timezone_aware_cards(tmp_path):
    inbox = radar_inbox.RadarInbox(str(tmp_path / "radar.json"))
    card = radar_inbox.OpportunityCard(
        id="aware-card",
        timestamp=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        activo="SPY",
        titular="Alerta reciente",
        impacto="POSITIVO",
        confianza=90,
        justificacion="Prueba aislada",
    )

    inbox.add_card(card)

    assert [active.id for active in inbox.get_active_cards()] == ["aware-card"]


def test_invalid_macro_confidence_returns_422_without_persisting():
    response = TestClient(main.app).post(
        "/api/macro/inject",
        json={"asset": "SPY", "text": "Alerta", "confidence": "no-es-numero"},
    )

    assert response.status_code == 422


def test_invalid_macro_timestamp_returns_400():
    response = TestClient(main.app).post(
        "/api/macro/inject",
        json={"asset": "SPY", "text": "Alerta", "timestamp": "ayer a las 10"},
    )

    assert response.status_code == 400


def test_macro_injection_accepts_valid_utc_payload(tmp_path, monkeypatch):
    saved = []

    class FakeInbox:
        def add_card(self, card):
            saved.append(card)

    monkeypatch.setattr(radar_inbox, "RadarInbox", FakeInbox)
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", str(tmp_path / "macro_bias_buffer.json"))
    monkeypatch.setenv("BUZON_RADAR_PATH", str(tmp_path / "buzon_radar.json"))
    monkeypatch.setattr(main, "INJECTED_MACRO", dict(main.INJECTED_MACRO))
    response = TestClient(main.app).post(
        "/api/macro/inject",
        json={
            "asset": "spy",
            "text": "Tesis de prueba",
            "confidence": 88,
            "timestamp": "2026-10-14T12:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["asset"] == "SPY"
    assert response.json()["data"]["timestamp"] == "2026-10-14T12:00:00+00:00"
    assert saved[0].timestamp == "2026-10-14T12:00:00+00:00"


def test_macro_injection_rejects_non_local_client_without_token(monkeypatch):
    request = SimpleNamespace(client=SimpleNamespace(host="192.0.2.10"))
    payload = main.MacroInjectionRequest(asset="SPY", text="Tesis")

    with pytest.raises(HTTPException) as error:
        main.inject_macro_from_monitor(payload, request)

    assert error.value.status_code == 403


def test_macro_radar_requires_and_accepts_configured_token(monkeypatch):
    monkeypatch.setenv("APP_SECRET_TOKEN", "test-token")

    class EmptyInbox:
        def get_active_cards(self, hours_ttl):
            return []

    monkeypatch.setattr(radar_inbox, "RadarInbox", EmptyInbox)
    client = TestClient(main.app)

    assert client.get("/api/macro/radar?source=monitor").status_code == 401
    response = client.get(
        "/api/macro/radar?source=monitor",
        headers={"X-API-Token": "test-token"},
    )

    assert response.status_code == 200


def test_macro_radar_returns_waiting_state_when_inbox_is_empty(monkeypatch):
    class EmptyInbox:
        def get_active_cards(self, hours_ttl=72):
            return []

    monkeypatch.setattr(radar_inbox, "RadarInbox", EmptyInbox)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    result = main.get_macro_radar(request, engine="local", source="monitor", x_api_token=None)

    assert isinstance(result, list)
    assert result[0]["asset"] == "MONITOR_ESPERA"
    assert result[0]["type"] == "Neutral"
    assert "Buzón satélite vacío" in result[0]["reason"]


def test_macro_radar_reads_active_cards_from_inbox(monkeypatch):
    from backend.radar_inbox import OpportunityCard

    class FakeInbox:
        def get_active_cards(self, hours_ttl=72):
            return [
                OpportunityCard(
                    id="test-card-1",
                    timestamp="2026-11-04T12:00:00",
                    activo="SPY",
                    titular="Titular SPY",
                    impacto="POSITIVO",
                    confianza=87,
                    justificacion="Tesis de prueba SPY"
                )
            ]

    monkeypatch.setattr(radar_inbox, "RadarInbox", FakeInbox)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    result = main.get_macro_radar(request, engine="local", source="monitor", x_api_token=None)

    assert isinstance(result, list)
    assert result[0]["asset"] == "SPY"
    assert result[0]["type"] == "Oportunidad"
    assert result[0]["confidence"] == 87


def test_market_history_malformed_data_returns_gateway_error(monkeypatch):
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: [[1, 2]])

    response = TestClient(main.app).get("/api/market/history?symbol=BTC/USDT")

    assert response.status_code == 502


def test_external_ohlcv_nan_is_rejected_before_caching(monkeypatch):
    monkeypatch.setattr(
        main,
        "_fetch_raw_ohlcv",
        lambda *args: [[int(time.time() * 1000), 10, 11, 9, float("nan"), 1]],
    )

    response = TestClient(main.app).get(
        "/api/market/history?symbol=ETH/USDT&timeframe=1m"
    )

    assert response.status_code == 502
    assert "no finita" in response.json()["detail"]


def test_ohlcv_validation_sorts_and_deduplicates_identical_timestamps():
    candles = [
        [120_000, 11, 13, 10, 12, 5],
        [60_000, 10, 12, 9, 11, 4],
        [60_000, 10, 12, 9, 11, 4],
    ]

    normalized = main._validate_ohlcv_data(candles, "BTC/USDT")

    assert [candle[0] for candle in normalized] == [60_000, 120_000]


def test_ohlcv_validation_rejects_conflicting_duplicate_timestamps():
    candles = [
        [60_000, 10, 12, 9, 11, 4],
        [60_000, 10, 13, 9, 12, 5],
    ]

    with pytest.raises(ValueError, match="contradictorias"):
        main._validate_ohlcv_data(candles, "BTC/USDT")


def test_closed_ohlcv_data_excludes_in_progress_candle():
    candles = [
        [60_000, 10, 12, 9, 11, 4],
        [120_000, 11, 13, 10, 12, 5],
    ]

    closed = main._closed_ohlcv_data(candles, "BTC/USDT", "1m", now_ms=121_000)

    assert [candle[0] for candle in closed] == [60_000]


def test_continuous_crypto_ohlcv_rejects_missing_intervals():
    candles = [
        [60_000, 10, 12, 9, 11, 4],
        [180_000, 11, 13, 10, 12, 5],
    ]

    with pytest.raises(ValueError, match="Hueco OHLCV"):
        main._validate_ohlcv_continuity(candles, "BTC/USDT", "1m")


def test_equity_ohlcv_allows_expected_market_session_gaps():
    candles = [
        [60_000, 10, 12, 9, 11, 4],
        [86_460_000, 11, 13, 10, 12, 5],
    ]

    main._validate_ohlcv_continuity(candles, "SPY", "1m")


def test_external_non_finite_price_is_rejected(monkeypatch):
    main._CACHE_DATA.clear()
    monkeypatch.setattr(
        main.exchange,
        "fetch_ticker",
        lambda symbol: {"last": float("nan"), "timestamp": int(time.time() * 1000)},
    )

    response = TestClient(main.app).get("/api/market/price?symbol=ETH/USDT")

    assert response.status_code == 502
    assert "precio o timestamp inválido" in response.json()["detail"]


def test_market_analysis_returns_signal_from_mocked_market_data(monkeypatch):
    now_ms = int(time.time() * 1000)
    candles = []
    for index in range(300):
        close = 100 + index * 0.05 + math.sin(index / 4) * 2
        candles.append([
            now_ms - (299 - index) * 60_000,
            close,
            close + 1,
            close - 1,
            close,
            100 + index,
        ])
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)

    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local"
    )

    assert response.status_code == 200
    assert response.json()["signal"] in {"COMPRAR", "VENDER", "MANTENER"}
    assert response.json()["indicators"]["current_price"] is not None
    fee_info = response.json()["fee_info"]
    assert fee_info["round_trip_spread"] == 0.1
    assert fee_info["round_trip_cost"] == 0.3
    assert fee_info["net_tp"] == pytest.approx(main.net_return_after_costs(3, 0.1, 0.05), abs=0.0001)


def test_market_analysis_uses_closed_candles_and_actual_lower_wick(monkeypatch):
    now_ms = int(time.time() * 1000)
    current_candle_open_ms = now_ms // 60_000 * 60_000
    candles = []
    for index in range(300):
        close = 100 + index * 0.05 + math.sin(index / 4) * 2
        candles.append([
            current_candle_open_ms - (299 - index) * 60_000,
            close,
            close + 1,
            close - 1,
            close,
            100 + index,
        ])

    closed_candle = candles[-2]
    closed_candle[1:5] = [100, 110, 90, 104]
    open_candle = candles[-1]
    open_candle[1:5] = [104, 10_001, 103, 10_000]
    fetch_calls = []

    def fake_get_ohlcv(*args):
        fetch_calls.append(args)
        return candles

    monkeypatch.setattr(main, "get_ohlcv", fake_get_ohlcv)
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local"
    )

    assert response.status_code == 200
    result = response.json()
    assert fetch_calls[0][2] == main.ANALYSIS_OHLCV_LIMIT
    assert result["signal_candle_ts"] == (current_candle_open_ms - 60_000) // 1000
    assert result["latest_candle"]["close"] == 104
    assert result["indicators"]["current_price"] == 104
    assert result["indicators"]["lower_wick_ratio"] == pytest.approx(0.5)
    assert result["indicators"]["ema_200"] is not None
    assert result["indicators"]["ema_200_slope_pct"] is not None


def test_market_analysis_rejects_insufficient_closed_candle_history(monkeypatch):
    now_ms = int(time.time() * 1000)
    candles = [
        [now_ms - (99 - index) * 60_000, 100, 101, 99, 100, 10]
        for index in range(100)
    ]
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)

    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["signal"] == "MANTENER"
    assert "al menos 205" in result["reason"]


def _quant_strategy_candles(now_ms, extreme_volume=200, timeframe="15m", drop_close=127.2, drop_low=126.0):
    step_ms = main.TIMEFRAME_SECONDS.get(timeframe, 900) * 1000
    current_candle_open_ms = now_ms // step_ms * step_ms
    candles = []
    for index in range(300):
        close = 100 + index * 0.1
        candles.append([
            current_candle_open_ms - (299 - index) * step_ms,
            close,
            close + 0.5,
            close - 0.5,
            close,
            100,
        ])
    candles[-2][1:5] = [129.8, 130.0, drop_low, drop_close]
    candles[-2][5] = extreme_volume
    candles[-1][1:5] = [drop_close, 130.0, drop_low, 129.0]
    return candles


def test_atr_strategy_generates_candidate_from_deterministic_filters(monkeypatch):
    from backend.estrategias.mean_reversion_atr import MeanReversionATR
    monkeypatch.setattr(MeanReversionATR, "long_entries_suspended", False)
    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="15m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)
    monkeypatch.setattr(main, "churn_block_reason", lambda *args, **kwargs: None)
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=local&strategy=mean_reversion_atr"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["strategy"] == "mean_reversion_atr"
    assert result["signal"] == "COMPRAR"
    assert result["strategy_metrics"]["candidate_eligible"] is True
    assert result["strategy_metrics"]["z_score"] <= -2
    assert result["strategy_metrics"]["lower_wick_ratio"] >= 0.25
    assert result["strategy_metrics"]["tp_gross_pct"] >= result["fee_info"]["round_trip_cost"] * 3.5
    assert result["strategy_metrics"]["tp_net_pct"] >= 0.5


def test_atr_strategy_long_entries_suspended_by_default(monkeypatch):
    """Medida Inmediata 1: Compras Long en mean_reversion_atr deben estar suspendidas por defecto."""
    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="15m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)
    monkeypatch.setattr(main, "churn_block_reason", lambda *args, **kwargs: None)
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=local&strategy=mean_reversion_atr"
    )
    assert response.status_code == 200
    result = response.json()
    assert result["signal"] == "MANTENER"
    assert result["strategy_metrics"]["candidate_eligible"] is False
    assert any("suspendidas" in f.lower() for f in result["strategy_metrics"]["filter_failures"])


def test_atr_strategy_rejects_extreme_volume_deterministically(monkeypatch):
    # En un retroceso normal (Pullback en tendencia), volumen extremo RVOL > 3.5 denota avalancha institucional y debe ser rechazado
    candles = _quant_strategy_candles(
        int(time.time() * 1000), extreme_volume=500, timeframe="15m", drop_close=128.5, drop_low=128.0
    )
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)
    monkeypatch.setattr(
        main.requests,
        "post",
        lambda *args, **kwargs: pytest.fail("IA no debe llamarse cuando Python rechaza la candidata"),
    )
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=qwen&strategy=mean_reversion_atr"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["signal"] == "MANTENER"
    assert result["strategy_metrics"]["candidate_eligible"] is False
    assert any("Volumen" in failure for failure in result["strategy_metrics"]["filter_failures"])


def test_selected_ai_can_veto_but_not_create_atr_candidate(monkeypatch):
    from backend.estrategias.mean_reversion_atr import MeanReversionATR
    monkeypatch.setattr(MeanReversionATR, "long_entries_suspended", False)
    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="15m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    captured_payloads = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": '{"signal":"MANTENER","reason":"veto contextual"}'}]
                        }
                    }
                ]
            }

    def fake_post(url, json, timeout):
        captured_payloads.append(json)
        return FakeResponse()

    monkeypatch.setattr(main.requests, "post", fake_post)
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=gemini&strategy=mean_reversion_atr"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["strategy_metrics"]["candidate_eligible"] is True
    assert result["signal"] == "MANTENER"
    assert "MODO AUDITOR CUANTITATIVO" in captured_payloads[0]["contents"][0]["parts"][0]["text"]
    assert captured_payloads[0].get("generationConfig", {}).get("temperature") == 0.0


def test_retired_local_engines_evaluate_quant_candidate_without_external_calls(monkeypatch):
    from backend.estrategias.mean_reversion_atr import MeanReversionATR
    monkeypatch.setattr(MeanReversionATR, "long_entries_suspended", False)
    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="15m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)

    def unexpected_post(*args, **kwargs):
        raise AssertionError("No debe haber peticiones HTTP en motores locales retirados")

    monkeypatch.setattr(main.requests, "post", unexpected_post)
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=qwen&strategy=mean_reversion_atr"
    )
    assert response.status_code == 200
    result = response.json()
    assert result["strategy_metrics"]["candidate_eligible"] is True


def test_atr_strategy_rejects_1m_and_5m_timeframes_with_422(monkeypatch):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("No se debe consultar mercado ni invocar LLMs para temporalidades rechazadas")

    monkeypatch.setattr(main, "get_ohlcv", unexpected_call)
    monkeypatch.setattr(main.requests, "post", unexpected_call)

    # 1m rechazado con 422
    res_1m = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local&strategy=mean_reversion_atr"
    )
    assert res_1m.status_code == 422
    assert "solo admite temporalidades" in res_1m.json()["detail"]

    # 5m rechazado con 422
    res_5m = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=5m&engine=qwen&strategy=mean_reversion_atr"
    )
    assert res_5m.status_code == 422
    assert "solo admite temporalidades" in res_5m.json()["detail"]


def test_atr_strategy_accepts_1h_timeframe(monkeypatch):
    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="1h")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1h&engine=local&strategy=mean_reversion_atr"
    )
    assert response.status_code == 200
    assert response.json()["strategy"] == "mean_reversion_atr"


def test_atr_ai_auditor_error_or_timeout_fails_safe_to_mantener(monkeypatch):
    from backend.estrategias.mean_reversion_atr import MeanReversionATR
    monkeypatch.setattr(MeanReversionATR, "long_entries_suspended", False)
    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="15m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)

    # 1. Simular timeout en el LLM
    def fake_timeout(*args, **kwargs):
        import requests
        raise requests.exceptions.Timeout("Timeout simulado en Qwen")

    monkeypatch.setattr(main.requests, "post", fake_timeout)
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=qwen&strategy=mean_reversion_atr"
    )
    assert response.status_code == 200
    result = response.json()
    assert result["strategy_metrics"]["candidate_eligible"] is True
    assert result["signal"] == "MANTENER"
    assert "Fail-Safe" in result["reason"]

    # 2. Simular respuesta JSON malformada o inválida
    class FakeMalformedResponse:
        status_code = 200
        def json(self):
            return {"response": "Texto basura sin estructura JSON"}

    monkeypatch.setattr(main.requests, "post", lambda *args, **kwargs: FakeMalformedResponse())
    response_malformed = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=qwen&strategy=mean_reversion_atr"
    )
    assert response_malformed.status_code == 200
    result_malformed = response_malformed.json()
    assert result_malformed["signal"] == "MANTENER"


def test_manual_strategy_still_allows_1m_and_5m(monkeypatch):
    # Generar velas de 1m y 5m
    c_1m = _quant_strategy_candles(int(time.time() * 1000), timeframe="1m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: c_1m)

    res_1m = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local&strategy=manual"
    )
    assert res_1m.status_code == 200
    assert res_1m.json()["strategy"] == "manual"



def test_market_analysis_rejects_unknown_strategy():
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&strategy=unexpected"
    )
    assert response.status_code == 422


def test_market_analysis_blocks_non_positive_net_return(monkeypatch):
    def unexpected_market_fetch(*args):
        raise AssertionError("El filtro de costos debe actuar antes de obtener precios")

    monkeypatch.setattr(main, "get_ohlcv", unexpected_market_fetch)

    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local&tp=1&fee=0.5"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["signal"] == "MANTENER"
    assert result["fee_info"]["viable"] is False
    assert result["fee_info"]["round_trip_fee"] == 1


def test_market_analysis_does_not_double_count_deducted_costs(monkeypatch):
    now_ms = int(time.time() * 1000)
    candles = []
    for index in range(300):
        close = 100 + index * 0.05 + math.sin(index / 4) * 2
        candles.append([
            now_ms - (299 - index) * 60_000,
            close,
            close + 1,
            close - 1,
            close,
            100 + index,
        ])
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)

    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local&tp=1.5&fee=0.5"
    )

    assert response.status_code == 200
    fee_info = response.json()["fee_info"]
    assert fee_info["net_tp"] > 0
    assert fee_info["net_tp"] < fee_info["round_trip_cost"]
    # "viable" ahora exige además R:R neto >= MIN_NET_RR: con comisión 0.5% y SL 1.0% el R:R neto es ~0.19.
    assert fee_info["net_rr"] < fee_info["min_net_rr"]
    assert fee_info["viable"] is False


def test_market_analysis_uses_configured_minimum_net_profit(monkeypatch):
    def unexpected_market_fetch(*args):
        raise AssertionError("El mínimo neto debe filtrarse antes de consultar velas")

    monkeypatch.setattr(main, "get_ohlcv", unexpected_market_fetch)
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local&tp=1.5&fee=0.1&spread=0.05&min_profit_pct=1.3"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["signal"] == "MANTENER"
    assert result["fee_info"]["net_tp"] < 1.3
    assert result["fee_info"]["min_profit_pct"] == 1.3
    assert result["fee_info"]["viable"] is False


def test_cost_filter_does_not_block_exit_analysis_for_open_positions(monkeypatch):
    now_ms = int(time.time() * 1000)
    candles = []
    for index in range(300):
        close = 100 + index * 0.05 + math.sin(index / 4) * 2
        candles.append([
            now_ms - (299 - index) * 60_000,
            close,
            close + 1,
            close - 1,
            close,
            100 + index,
        ])
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)

    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local&tp=1&fee=0.5&has_position=true&entry_price=100"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["indicators"]["current_price"] is not None
    assert result["fee_info"]["viable"] is False
    assert "rentabilidad neta no positiva" not in result["reason"]


def test_market_analysis_blocks_when_net_target_does_not_cover_fees_and_spread(monkeypatch):
    def unexpected_market_fetch(*args):
        raise AssertionError("El filtro de costos debe actuar antes de obtener precios")

    monkeypatch.setattr(main, "get_ohlcv", unexpected_market_fetch)
    response = TestClient(main.app).get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=1m&engine=local&tp=1&fee=0.1&spread=0.4"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["signal"] == "MANTENER"
    assert result["fee_info"]["round_trip_cost"] == 1
    assert result["fee_info"]["net_tp"] < result["fee_info"]["round_trip_cost"]


def test_market_analysis_rejects_invalid_financial_parameters():
    client = TestClient(main.app)
    for params in [
        "fee=-0.1",
        "fee=nan",
        "spread=-0.1",
        "spread=5.1",
        "min_profit_pct=-0.1",
        "min_profit_pct=5.1",
        "tp=inf",
        "risk=1.1",
        "sentiment=2",
        "entry_price=-1",
    ]:
        response = client.get(f"/api/market/analysis?symbol=BTC/USDT&{params}")
        assert response.status_code == 422, params


def test_cio_bridge_script_attaches_configured_api_token(monkeypatch):
    script_path = (
        main.PROJECT_ROOT
        + "/.agents/skills/macro-cio-auditor/scripts/audit_and_inject.py"
    )
    spec = importlib.util.spec_from_file_location("macro_cio_script", script_path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    monkeypatch.delenv("TRADING_OLLAMA_API_TOKEN", raising=False)
    monkeypatch.setenv("APP_SECRET_TOKEN", "test-secret")
    assert script.auth_headers()["X-API-Token"] == "test-secret"

    monkeypatch.delenv("APP_SECRET_TOKEN")
    monkeypatch.setenv("TRADING_OLLAMA_API_TOKEN", "bridge-secret")
    assert script.auth_headers()["X-API-Token"] == "bridge-secret"


def test_trade_log_rejects_non_finite_or_negative_values():
    client = TestClient(main.app)
    trade = {
        "timeString": "2026-10-14 12:00:00",
        "symbol": "BTC/USDT",
        "signal": "COMPRAR",
        "price": 100,
        "status": "Ejecutada",
        "mode": "Paper",
        "qty": 1,
        "fee": 0.1,
    }
    with pytest.raises(ValidationError):
        main.TradeLogRequest(**{**trade, "price": float("nan")})
    for invalid in [{"qty": -1}, {"fee": -0.1}]:
        response = client.post("/api/log_trade", json={**trade, **invalid})
        assert response.status_code == 422


def test_trade_log_storage_failure_returns_http_error(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "CSV_FILE_PATH", str(tmp_path / "missing" / "trades.csv"))
    trade = {
        "timeString": "2026-10-14 12:00:00",
        "symbol": "BTC/USDT",
        "signal": "COMPRAR",
        "price": 100,
        "status": "Ejecutada",
        "mode": "Paper",
        "qty": 1,
        "fee": 0.1,
    }

    response = TestClient(main.app).post("/api/log_trade", json=trade)

    assert response.status_code == 500
    assert response.json()["detail"] == "No se pudo guardar el registro de la operación."


def test_trade_log_persists_valid_paper_trade_to_configured_path(monkeypatch, tmp_path):
    path = tmp_path / "trades.csv"
    monkeypatch.setattr(main, "CSV_FILE_PATH", str(path))
    trade = {
        "timeString": "2026-10-14 12:00:00",
        "symbol": "BTC/USDT",
        "signal": "COMPRAR",
        "price": 100,
        "status": "Ejecutada",
        "mode": "Paper",
        "qty": 1,
        "fee": 0.1,
    }

    response = TestClient(main.app).post("/api/log_trade", json=trade)

    assert response.status_code == 200
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "BTC/USDT" in lines[1]


def test_invalid_symbol_is_rejected_without_market_request():
    response = TestClient(main.app).get("/api/market/price?symbol=NOT-A-SYMBOL")

    assert response.status_code == 400


def test_time_decay_tightening_and_suggestions(monkeypatch):
    from backend.daemon import TraderDaemon
    from backend.execution.paper_broker import PaperBrokerAdapter
    import tempfile
    import os

    monkeypatch.setattr(main, "get_price", lambda sym: {"price": 50000.0})

    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tf:
        temp_db = tf.name

    try:
        broker = PaperBrokerAdapter(db_path=temp_db)
        broker.ledger.deposit(1000.0, "USDT")
        daemon = TraderDaemon(broker=broker)

        # Simular una posición abierta hace 20 horas estancada
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        opened_at_20h = (now_dt - timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S")

        pos = {
            "id": "test-trade-decay-1",
            "symbol": "BTC/USDT",
            "currency": "USDT",
            "side": "LONG",
            "status": "OPEN",
            "qty": 0.01,
            "entry_price": 50000.0,
            "cost_basis": 500.0,
            "initial_sl_pct": 2.0,
            "initial_tp_pct": 6.0,
            "current_stop_net_pct": -2.0,
            "be_armed": 0,
            "trail_active": 0,
            "peak_price": 50050.0,  # +0.10% bruto (estancada)
            "opened_at": opened_at_20h,
        }

        # Ejecutar verificación de protecciones con precio actual plano (50000.0)
        res = daemon._check_open_positions_protections([pos])
        
        # Verificar que la Opción B apretó el stop por tiempo y sugirió A o C
        assert pos["time_decay_hours"] >= 19.9
        assert pos["time_decay_status"] == "TIGHTENING_16H"
        assert "Sugerencia IA" in pos["time_decay_suggestion"]
        assert "BTC/USDT" in daemon.time_decay_cache
        assert daemon.time_decay_cache["BTC/USDT"]["status"] == "TIGHTENING_16H"

        # Verificar endpoint API
        client = TestClient(main.app)
        api_res = client.get("/api/time_stop/telemetry")
        assert api_res.status_code == 200
        assert "telemetry" in api_res.json()
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)


def test_agent_chat_pause_resume_and_directive_flow(tmp_path, monkeypatch):
    """Verifica que Pausar/Reanudar en Chat bloquee entradas y que Directivas no se traten como veto en CIO."""
    from datetime import datetime, timezone
    from fastapi.testclient import TestClient
    from backend.daemon import TraderDaemon
    from backend.execution.paper_broker import PaperBrokerAdapter
    from backend import radar_inbox

    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", str(tmp_path / "bias.json"))
    monkeypatch.setenv("BUZON_RADAR_PATH", str(tmp_path / "buzon.json"))
    monkeypatch.setattr(radar_inbox, "BUZON_FILE", str(tmp_path / "buzon.json"))
    monkeypatch.setattr(main, "INJECTED_MACRO", dict(main.INJECTED_MACRO))

    db_file = str(tmp_path / "chat_ledger.sqlite3")
    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=db_file)
    td = TraderDaemon(broker=broker)
    td.symbol = "BTC/USDT"
    td.strategy = "manual"
    monkeypatch.setattr("backend.daemon.get_trader_daemon", lambda: td)

    candles = _quant_strategy_candles(int(time.time() * 1000), timeframe="15m")
    monkeypatch.setattr(main, "get_ohlcv", lambda *args: candles)
    monkeypatch.setattr(main, "get_cached_price", lambda sym: {"symbol": sym, "price": candles[-1][4]})

    client = TestClient(main.app)
    res_pause = client.post("/api/agent/chat", json={"message": "pausa operativa"})
    assert res_pause.status_code == 200
    assert res_pause.json()["action"] == "PAUSE"
    assert td.paused_new_entries is True

    res_blocked = client.get("/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=antigravity_operador&strategy=manual")
    assert res_blocked.status_code == 200
    assert res_blocked.json()["signal"] == "MANTENER"
    assert "Pausa Operador" in res_blocked.json()["reason"]

    res_resume = client.post("/api/agent/chat", json={"message": "reanudar"})
    assert res_resume.status_code == 200
    assert res_resume.json()["action"] == "RESUME"
    assert td.paused_new_entries is False

    res_dir = client.post("/api/agent/chat", json={"message": "Directiva: prioriza oro ahora"})
    assert res_dir.status_code == 200
    dir_data = res_dir.json()
    assert dir_data["action"] == "DIRECTIVE_INJECTED"
    assert dir_data["asset"] == "GC=F"
    assert main.INJECTED_MACRO["type"] == "Directiva de Operador"

    res_cio = client.get("/api/market/analysis?symbol=GC=F&timeframe=15m&engine=antigravity_cio&strategy=manual")
    assert res_cio.status_code == 200
    assert "Directiva de Alerta/Peligro detectada" not in res_cio.json()["reason"]


def test_session_clock_respects_us_dst_edt_vs_est():
    """Verifica reloj bursátil NY -> ART en EDT (octubre: 10:30 ART) vs EST (noviembre: 11:30 ART)."""
    from datetime import datetime, timedelta, timezone

    arg_tz = timezone(timedelta(hours=-3))
    dt_oct_edt = datetime(2026, 10, 19, 10, 35, tzinfo=arg_tz)
    sess_edt = main._compute_session_clock(dt_oct_edt.astimezone(timezone.utc))
    assert sess_edt["blackout_active"] is True
    assert sess_edt["ny_open_art"] == "10:30"

    dt_nov_est_1035 = datetime(2026, 11, 10, 10, 35, tzinfo=arg_tz)
    sess_est_pre = main._compute_session_clock(dt_nov_est_1035.astimezone(timezone.utc))
    assert sess_est_pre["blackout_active"] is False
    assert "Pre-Market" in sess_est_pre["name"]
    assert sess_est_pre["ny_open_art"] == "11:30"
    assert sess_est_pre["ny_close_art"] == "18:00"

    dt_nov_est_1135 = datetime(2026, 11, 10, 11, 35, tzinfo=arg_tz)
    sess_est_open = main._compute_session_clock(dt_nov_est_1135.astimezone(timezone.utc))
    assert sess_est_open["blackout_active"] is True

    dt_nov_est_1730 = datetime(2026, 11, 10, 17, 30, tzinfo=arg_tz)
    sess_est_power = main._compute_session_clock(dt_nov_est_1730.astimezone(timezone.utc))
    assert "Power Hour" in sess_est_power["name"]


def test_kula_multitemporal_triad_attached_and_daemon_browser_isolation(tmp_path, monkeypatch):
    """Verifica Tríada 1D-1H-5M real en get_analysis y no congelamiento global del daemon por actividad del navegador."""
    from backend.daemon import TraderDaemon
    from backend.execution.paper_broker import PaperBrokerAdapter

    now_ms = int(time.time() * 1000)

    def _make_tf(step_ms: int, n: int, base: float, slope: float):
        start = now_ms - n * step_ms
        return [
            [start + i * step_ms, base + i * slope, base + i * slope + 2.0, base + i * slope - 2.0, base + i * slope, 500.0]
            for i in range(n)
        ]

    ohlcv_5m = _make_tf(300_000, 260, 100.0, 0.1)
    ohlcv_1h = _make_tf(3_600_000, 80, 100.0, 0.2)
    ohlcv_1d = _make_tf(86_400_000, 70, 200.0, -1.0)  # 1D bajista para probar veto Regla 0

    def mock_get_ohlcv(sym, tf, limit):
        if tf == "1d":
            return ohlcv_1d
        if tf == "1h":
            return ohlcv_1h
        return ohlcv_5m

    monkeypatch.setattr(main, "get_ohlcv", mock_get_ohlcv)
    monkeypatch.setattr(main, "get_cached_price", lambda sym: {"symbol": sym, "price": ohlcv_5m[-1][4]})
    monkeypatch.setattr(main, "CONTEXT_FILE_PATH", str(tmp_path / "ctx.json"), raising=False)
    monkeypatch.setenv("KULA_MARKET_CONTEXT_PATH", str(tmp_path / "ctx.json"))
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", str(tmp_path / "bias.json"))

    client = TestClient(main.app)
    res = client.get("/api/market/analysis?symbol=BTC/USDT&timeframe=5m&engine=antigravity_operador&strategy=kula_balam_cava_ruiz")
    assert res.status_code == 200
    sm = res.json()["strategy_metrics"]
    assert sm["triad_mode"] == "multitemporal_1d_1h_5m"

    # Navegador consultando BTC/USDT no debe impedir evaluación de otros activos en el daemon
    monkeypatch.setenv("TRADING_OLLAMA_CSV_PATH", str(tmp_path / "daemon_iso_trades.csv"))
    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=str(tmp_path / "daemon_iso.sqlite3"))
    td = TraderDaemon(broker=broker)
    td.symbol = "SOL/USDT"
    td.strategy = "manual"
    td.mode = "fixed"
    td.notify_browser_activity(macro="", symbol="BTC/USDT")
    evaluated = []

    def fake_analysis(**kwargs):
        evaluated.append(kwargs["symbol"])
        return {"signal": "MANTENER", "reason": "OK", "indicators": {}, "strategy_metrics": {}, "fee_info": {}}

    monkeypatch.setattr("backend.main.get_analysis", fake_analysis)
    monkeypatch.setattr("backend.main.get_price", lambda sym: {"symbol": sym, "price": 150.0})
    monkeypatch.setattr("backend.estrategias.registry.is_asset_market_open", lambda sym: True)
    td._execute_cycle()
    assert "SOL/USDT" in evaluated


def test_daemon_preserves_catalog_tp_sl_and_filters_test_radar(tmp_path, monkeypatch):
    """Verifica que el daemon preserve tp_gross_pct/sl_gross_pct de catálogo e ignore tarjetas *_test.py."""
    from datetime import datetime, timezone
    from backend.daemon import TraderDaemon
    from backend.execution.paper_broker import PaperBrokerAdapter

    buzon_file = tmp_path / "buzon_test.json"
    buzon_file.write_text(
        json.dumps([
            {
                "id": "t-real",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "activo": "SOL/USDT",
                "titular": "Alerta Monitor: SOL/USDT (Oportunidad)",
                "impacto": "POSITIVO",
                "confianza": 88,
                "justificacion": "Oportunidad real",
            },
            {
                "id": "t-noise",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "activo": "ETH/USDT",
                "titular": "[LAB PROMOTION] donchian_breakout_test.py (ETH/USDT)",
                "impacto": "POSITIVO",
                "confianza": 95,
                "justificacion": "Test artifact",
            },
        ]),
        encoding="utf-8",
    )
    monkeypatch.setenv("BUZON_RADAR_PATH", str(buzon_file))
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", str(tmp_path / "bias.json"))
    monkeypatch.setenv("TRADING_OLLAMA_CSV_PATH", str(tmp_path / "cat_tp_sl_trades.csv"))

    broker = PaperBrokerAdapter(initial_vault_usd=500.0, db_path=str(tmp_path / "cat_tp_sl.sqlite3"))
    td = TraderDaemon(broker=broker)
    td.mode = "smart"
    td.strategy = "auto"
    td._check_radar_for_autorouting()
    assert td.radar_candidate_symbol == "SOL/USDT"

    td.radar_candidate_symbol = None
    td.mode = "fixed"
    td.symbol = "ETH/USDT"
    td.timeframe = "4h"
    td.strategy = "squeeze_dual_eth_4h_slot1"
    td.tp = 2.0
    td.sl = 1.0
    fake_res = {
        "signal": "COMPRAR",
        "reason": "Squeeze Dual ETH 4H",
        "strategy": "squeeze_dual_eth_4h_slot1",
        "strategy_metrics": {
            "tp_gross_pct": 4.8,
            "sl_gross_pct": 1.6,
            "atr_14": 40.0,
            "relative_volume": 1.3,
        },
        "candlestick_audit": {},
    }
    monkeypatch.setattr("backend.main.get_analysis", lambda **kw: fake_res)
    monkeypatch.setattr("backend.main.get_price", lambda sym: {"symbol": sym, "price": 2500.0})
    monkeypatch.setattr("backend.estrategias.registry.is_asset_market_open", lambda sym: True)
    monkeypatch.setattr("backend.entry_gate.entry_gate_failures", lambda *a, **kw: [])
    td._execute_cycle()
    pos = broker.fetch_positions()
    assert len(pos) == 1
    assert pos[0]["symbol"] == "ETH/USDT"
    assert abs(float(pos[0]["initial_tp_pct"]) - 4.8) < 1e-4
    assert abs(float(pos[0]["initial_sl_pct"]) - 1.6) < 1e-4


def test_closed_candle_strict_blocks_midcandle_bnb_short_breakout_and_ui_readonly(monkeypatch):
    """
    Evita entradas tardías en mitad de vela abierta (caso real BNB/USDT SHORT @ 673.23):
    Aunque live_price perfore Donchian Low en la vela viva, get_analysis(has_position=False) evalúa
    estrictamente el cierre de la última vela cerrada y mantiene GET /api/market/analysis como solo lectura.
    """
    from unittest.mock import patch

    step_ms = 3_600_000
    now_ms = int(time.time() * 1000)
    current_open_ms = (now_ms // step_ms) * step_ms
    candles = []
    for i in range(260):
        px = 685.0 - (i * 0.02)
        candles.append([
            current_open_ms - (259 - i) * step_ms,
            px + 0.5,
            px + 1.0,
            674.8,
            px,
            10_000.0,
        ])
    # Última vela CERRADA (candles[-2]) cerró en 677.01 sin romper el suelo de 674.8
    candles[-2][1:5] = [678.5, 679.0, 674.9, 677.01]
    candles[-2][5] = 35_000.0
    # Vela ABIERTA en curso (candles[-1]) cae a 673.23 en vivo
    candles[-1][1:5] = [677.01, 677.2, 670.06, 673.23]
    candles[-1][5] = 45_000.0

    monkeypatch.setattr(main, "get_ohlcv", lambda sym, tf, limit: candles)
    monkeypatch.setattr(main, "get_cached_price", lambda sym: {"symbol": sym, "price": 673.23})
    monkeypatch.setattr("backend.estrategias.registry.is_asset_market_open", lambda sym: True)

    with patch("backend.daemon.TraderDaemon.notify_browser_activity") as mock_notify:
        res = TestClient(main.app).get(
            "/api/market/analysis?symbol=BNB/USDT&timeframe=1h&engine=antigravity_operador&strategy=donchian_breakout_1h&has_position=false"
        )
    assert res.status_code == 200
    payload = res.json()
    assert mock_notify.called is False
    assert payload["signal"] == "MANTENER"
    assert payload["entry_evaluation_mode"] == "closed_candle_strict"
    assert payload["indicators"]["current_price"] == pytest.approx(677.01, rel=1e-4)
    assert payload["strategy_metrics"]["current_price"] == pytest.approx(677.01, rel=1e-4)
    assert payload["strategy_metrics"]["side"] != "SHORT"
    assert payload["latest_spot_price"] == pytest.approx(673.23, rel=1e-4)
    assert any("Sin ruptura" in f for f in (payload["strategy_metrics"].get("filter_failures") or []))


def test_get_ohlcv_cache_invalidates_across_candle_boundary(monkeypatch):
    """Al cruzar exactamente un cierre de vela, get_ohlcv debe invalidar la caché aunque el TTL de 2s no expire."""
    fetch_calls = []

    def fake_fetch(symbol, timeframe, limit):
        fetch_calls.append(len(fetch_calls) + 1)
        return [[1_700_000_000_000 + i * 3_600_000, 100.0, 101.0, 99.0, 100.5, 50.0] for i in range(10)]

    now_holder = {"t": 3599.4}
    monkeypatch.setattr(main.time, "time", lambda: now_holder["t"])
    monkeypatch.setattr(main, "_fetch_raw_ohlcv", fake_fetch)

    main._CACHE_DATA.pop("ohlcv:BNB/USDT:1h:50", None)
    main.get_ohlcv("BNB/USDT", "1h", 50)
    assert len(fetch_calls) == 1

    # Mismo bucket (3599.8 < 3600): hit de caché válido
    now_holder["t"] = 3599.8
    main.get_ohlcv("BNB/USDT", "1h", 50)
    assert len(fetch_calls) == 1

    # Cruza cierre horario (3600.4 - 3599.4 = 1.0s < TTL 2.0s, pero nuevo bucket): invalida inmediato
    now_holder["t"] = 3600.4
    main.get_ohlcv("BNB/USDT", "1h", 50)
    assert len(fetch_calls) == 2



