import math
import time
from backend import main


def test_get_history_includes_vwap_bands(monkeypatch):
    now_ms = int(time.time() * 1000)
    candles = [
        [now_ms - (29 - i) * 3_600_000, 100.0 + i, 102.0 + i, 99.0 + i, 101.0 + i, 50.0 + i]
        for i in range(30)
    ]
    monkeypatch.setattr(main, "get_ohlcv", lambda symbol, timeframe, limit: candles)

    data = main.get_history(symbol="BTC/USDT", timeframe="1h", limit=30)

    assert isinstance(data, list)
    assert len(data) == 30
    assert any("vwap_upper" in row for row in data)
    assert any("vwap_lower" in row for row in data)
    assert "last_candle_age_s" in data[-1]


def test_engine_check_cascade_order(monkeypatch):
    class DummyClient:
        host = "127.0.0.1"

    class DummyRequest:
        client = DummyClient()

    res = main.check_system_engines(request=DummyRequest())
    assert res["status"] == "ok"
    assert res["hierarchy"] == ["antigravity_operador", "ai", "ollama|trader-qwen", "local"]
    assert "checks" in res
    assert res["checks"]["antigravity"]["priority"] == 1
    assert res["checks"]["gemini"]["priority"] == 2
    assert res["checks"]["qwen"]["priority"] == 3
    assert res["checks"]["matematico"]["priority"] == 4
