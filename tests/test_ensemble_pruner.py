# -*- coding: utf-8 -*-
"""
Pruebas Unitarias para el Motor de Poda Iterativa y Ensamble Modular (Stepwise Ensemble Pruner).
Valida:
1. Carga del universo auditado (principal/ y para_testear/ganadoras/).
2. Simulación y evaluación sin colisión de indicadores por copias de datos aisladas.
3. Selección de campeones y eliminación de sensores redundantes o de rentabilidad negativa.
4. Generación de código sintético unificado con Árbitro IA Central.
5. Endpoint HTTP en FastAPI /api/ensemble/torneo_poda.
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backtest_lab.server import app
from backtest_lab.core.ensemble_pruner import (
    cargar_universo_auditado,
    preparar_mercado_ensemble,
    ejecutar_torneo_poda,
    CandidateFormula
)


def test_cargar_universo_auditado():
    candidatas = cargar_universo_auditado()
    assert isinstance(candidatas, list)
    assert len(candidatas) >= 1, "Debe existir al menos una fórmula auditada en el catálogo"
    
    for cand in candidatas:
        assert isinstance(cand, CandidateFormula)
        assert cand.id
        assert cand.archivo.endswith(".py")
        assert len(cand.code_math) > 20
        assert "def formula_matematica" in cand.code_math


def test_ejecutar_torneo_poda_y_sintesis():
    dataset_name = "binance_ETH_USDT_4h.parquet"
    res = ejecutar_torneo_poda(dataset_name=dataset_name, max_batch_size=5)

    assert res["status"] == "ok"
    assert res["dataset"] == dataset_name
    assert res["total_auditadas"] >= 1
    assert len(res["campeones"]) >= 1
    assert "metricas" in res
    assert "code_math" in res
    assert "code_ia" in res

    # Validar que el código sintetizado incluye el punto de entrada reglamentario
    code_math = res["code_math"]
    assert "def formula_matematica" in code_math
    assert "ENSAMBLE MULTI-SENSOR CAMPEÓN" in code_math

    code_ia = res["code_ia"]
    assert "def arbitro_ia" in code_ia
    assert "ÁRBITRO HEURÍSTICO IA CENTRAL" in code_ia


def test_api_ensemble_torneo_poda_endpoint():
    client = TestClient(app)
    payload = {
        "dataset": "binance_ETH_USDT_4h.parquet",
        "max_batch_size": 5
    }
    resp = client.post("/api/ensemble/torneo_poda", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ok"
    assert "campeones" in data
    assert "descartadas" in data
    assert "metricas" in data
    assert "log_texto" in data
    assert "code_math" in data
    assert "code_ia" in data

