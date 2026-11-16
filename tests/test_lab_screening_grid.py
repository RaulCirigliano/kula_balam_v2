# -*- coding: utf-8 -*-
"""
Pruebas Unitarias para el Módulo de Screening Grid (Barrido Masivo Multi-Activo) en Backtest Lab.
Kula Balam / Backtest Lab
"""

import pytest
from fastapi.testclient import TestClient
from backtest_lab.server import app, DATA_DIR
from backtest_lab.screening_grid import (
    resolver_archivos_universo,
    ejecutar_screening_grid,
    UNIVERSOS_CATALOGO
)
from backtest_lab.generador_ia import _generar_template_donchian_squeeze


def test_resolver_archivos_universo():
    c_4h = resolver_archivos_universo("crypto_4h")
    assert len(c_4h) >= 2
    assert "binance_SOL_USDT_4h.parquet" in c_4h
    assert "binance_ETH_USDT_4h.parquet" in c_4h

    todos = resolver_archivos_universo("todos")
    assert len(todos) >= 3


def test_ejecutar_screening_grid_crypto_4h():
    tmpl = _generar_template_donchian_squeeze("", "SOL", es_1d=False)
    res = ejecutar_screening_grid(
        code_math=tmpl["code_math"],
        code_ia=tmpl["code_ia"],
        universo="crypto_4h",
        top_n=5,
        max_workers=3
    )

    assert "ranking" in res
    assert "resumen_texto" in res
    assert res["total_evaluados"] >= 2
    ranking = res["ranking"]
    assert len(ranking) >= 2

    # El primer clasificado debe tener métricas completas
    top = ranking[0]
    assert "dataset" in top
    assert "pf_neto" in top
    assert "win_rate_neto" in top
    assert "oos_pf" in top
    assert "dictamen" in top

    # Verificar que el resumen contiene la tabla ASCII
    texto = res["resumen_texto"]
    assert "LAB: BARRIDO MASIVO MULTI-ACTIVO & MULTI-TEMPORALIDAD (SCREENING GRID)" in texto
    assert "DATASET / ACTIVO" in texto
    assert "BALANCE INSTITUCIONAL" in texto


def test_api_screening_grid_endpoint():
    client = TestClient(app)
    tmpl = _generar_template_donchian_squeeze("", "SOL", es_1d=False)

    resp = client.post("/api/screening_grid", json={
        "code_math": tmpl["code_math"],
        "code_ia": tmpl["code_ia"],
        "universo": "crypto_4h",
        "top_n": 3,
        "max_workers": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "ranking" in data
    assert "resumen_texto" in data
    assert data["total_evaluados"] >= 2


def test_api_screening_grid_sin_codigo():
    client = TestClient(app)
    resp = client.post("/api/screening_grid", json={
        "code_math": "",
        "code_ia": "",
        "universo": "crypto_4h"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_evaluados"] == 0
    assert "No se recibió código" in data["resumen_texto"]
