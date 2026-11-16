"""
Módulo: tests/test_market_context.py
Pruebas del contrato formal de datos entre Balam y Kula (Punto 1).
"""

import pytest
import os
import json
from fastapi.testclient import TestClient
from backend.main import app
from backend.market_context import (
    MarketContextContract,
    KeyLevelsModel,
    save_market_context,
    load_market_context,
)

client = TestClient(app)


def test_market_context_contract_validation():
    """Valida que el modelo Pydantic acepte datos válidos y rechace regímenes o sesgos inválidos."""
    valid_data = {
        "version": "1.0",
        "ticker": "SOL/USDT",
        "timeframe": "1h",
        "regime": "Tendencia",
        "macro_bias": "LONG",
        "veto_active": False,
        "key_levels": {
            "support": 180.0,
            "resistance": 200.0,
            "fibo_50": 190.0,
            "fibo_75": 185.0
        },
        "max_risk_per_trade_usd": 0.50
    }
    contract = MarketContextContract(**valid_data)
    assert contract.ticker == "SOL/USDT"
    assert contract.regime == "Tendencia"
    assert contract.key_levels.fibo_50 == 190.0

    # Régimen inválido
    with pytest.raises(Exception):
        invalid_data = valid_data.copy()
        invalid_data["regime"] = "Invalido"
        MarketContextContract(**invalid_data)

    # Riesgo negativo o cero
    with pytest.raises(Exception):
        invalid_data = valid_data.copy()
        invalid_data["max_risk_per_trade_usd"] = 0.0
        MarketContextContract(**invalid_data)


def test_market_context_save_and_load(tmp_path):
    """Valida la persistencia atómica en disco y carga en memoria."""
    temp_file = str(tmp_path / "market_context.json")
    contract = MarketContextContract(
        ticker="ETH/USDT",
        timeframe="1h",
        regime="Calma",
        macro_bias="NEUTRAL",
        veto_active=True,
        key_levels=KeyLevelsModel(
            support=2400.0,
            resistance=2600.0,
            fibo_50=2500.0,
            fibo_75=2450.0
        ),
        max_risk_per_trade_usd=0.50
    )
    save_market_context(contract, path=temp_file)
    assert os.path.exists(temp_file)

    loaded = load_market_context(path=temp_file)
    assert loaded is not None
    assert loaded.ticker == "ETH/USDT"
    assert loaded.veto_active is True


def test_market_context_api_endpoints(tmp_path, monkeypatch):
    """Valida los endpoints HTTP POST y GET en FastAPI sin contaminar data/market_context.json."""
    from backend import market_context

    isolated_path = str(tmp_path / "api_market_context.json")
    monkeypatch.setenv("KULA_MARKET_CONTEXT_PATH", isolated_path)
    monkeypatch.setattr(market_context, "_CURRENT_CONTEXT", None)
    monkeypatch.setattr(market_context, "_CURRENT_CONTEXT_PATH", None)

    payload = {
        "version": "1.0",
        "ticker": "AAPL",
        "timeframe": "1d",
        "regime": "Tendencia",
        "macro_bias": "LONG",
        "veto_active": False,
        "key_levels": {
            "support": 220.0,
            "resistance": 240.0,
            "fibo_50": 230.0,
            "fibo_75": 225.0
        },
        "max_risk_per_trade_usd": 0.50
    }
    response = client.post("/api/kula/market-context", json=payload)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "ok"
    assert res_json["data"]["ticker"] == "AAPL"

    get_resp = client.get("/api/kula/market-context")
    assert get_resp.status_code == 200
    get_json = get_resp.json()
    assert get_json["status"] == "ok"
    assert get_json["data"]["ticker"] == "AAPL"


def test_get_active_market_context_ttl_and_symbol_isolation(tmp_path, monkeypatch):
    """Verifica vigencia TTL, match por símbolo y aislamiento de caché entre rutas."""
    from datetime import datetime, timedelta, timezone
    from backend import market_context
    from backend.market_context import get_active_market_context_for_symbol

    p1 = str(tmp_path / "ctx1.json")
    p2 = str(tmp_path / "ctx2.json")
    monkeypatch.setattr(market_context, "_CURRENT_CONTEXT", None)
    monkeypatch.setattr(market_context, "_CURRENT_CONTEXT_PATH", None)

    fresh_ctx = MarketContextContract(
        ticker="SOL/USDT",
        timeframe="4h",
        regime="Tendencia",
        macro_bias="LONG",
        veto_active=False,
        key_levels=KeyLevelsModel(support=140.0, resistance=170.0, fibo_50=155.0, fibo_75=147.5),
        max_risk_per_trade_usd=0.50,
        ttl_hours=2.0,
    )
    save_market_context(fresh_ctx, path=p1)
    assert get_active_market_context_for_symbol("SOL/USDT", path=p1) is not None
    assert get_active_market_context_for_symbol("BTC/USDT", path=p1) is None

    expired_ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    stale_ctx = MarketContextContract(
        ticker="ETH/USDT",
        timestamp=expired_ts,
        timeframe="4h",
        regime="Crisis",
        macro_bias="SHORT",
        veto_active=True,
        key_levels=KeyLevelsModel(support=2100.0, resistance=2400.0, fibo_50=2250.0, fibo_75=2175.0),
        max_risk_per_trade_usd=0.50,
        ttl_hours=2.0,
    )
    save_market_context(stale_ctx, path=p2)
    assert get_active_market_context_for_symbol("ETH/USDT", path=p2) is None
    assert get_active_market_context_for_symbol("SOL/USDT", path=p1) is not None
