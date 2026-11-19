# -*- coding: utf-8 -*-
"""
Pruebas Unitarias para el Catálogo Dinámico de Fórmulas del Sistema (Single Source of Truth).
Verifica:
  1. GET /api/catalogo_formulas retorna las 3 categorías principales.
  2. GET /api/catalogo_formulas/{cat}/{archivo} entrega código matemático y árbitro IA.
  3. DELETE /api/catalogo_formulas/{cat}/{archivo} borra físicamente y desautoriza en Kula Balam.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backtest_lab.server import app as lab_app
from backend.main import app as kula_app
from backend.estrategias.catalogo_manager import (
    get_catalogo_completo,
    get_formula_detalle,
    eliminar_formula,
    GANADORAS_DIR,
    _write_metadata,
    _read_metadata
)


def test_catalogo_listado_en_lab_y_kula():
    client_lab = TestClient(lab_app)
    client_kula = TestClient(kula_app)

    res_lab = client_lab.get("/api/catalogo_formulas")
    assert res_lab.status_code == 200
    data_lab = res_lab.json()
    assert "panel_principal" in data_lab
    assert "operador_presente" in data_lab
    assert "para_testear" in data_lab
    assert len(data_lab["panel_principal"]) >= 1
    assert isinstance(data_lab["operador_presente"], list)

    res_kula = client_kula.get("/api/catalogo_formulas")
    assert res_kula.status_code == 200
    data_kula = res_kula.json()
    assert len(data_kula["panel_principal"]) == len(data_lab["panel_principal"])
    assert len(data_kula["operador_presente"]) == len(data_lab["operador_presente"])


def test_catalogo_detalle_formula():
    client_lab = TestClient(lab_app)
    res = client_lab.get("/api/catalogo_formulas/operador_presente/kula_cava_eth_1h.py")
    assert res.status_code == 200
    data = res.json()
    assert data["archivo"] == "kula_cava_eth_1h.py"
    assert "Kula Cava" in data["titulo"]
    assert "formula_matematica" in data["code_math"]
    assert "arbitro_ia" in data["code_ia"]
    assert data["dataset_sugerido"] == "binance_ETH_USDT_1h.parquet"


def test_catalogo_borrado_completo():
    client_lab = TestClient(lab_app)

    # 1. Crear una fórmula temporal en ganadoras/ para prueba de borrado
    temp_file = GANADORAS_DIR / "temp_borrado_test.py"
    temp_file.write_text("# temporal\ndef formula_matematica(df, i):\n    return False, None, 0.0, 0.0\n", encoding="utf-8")
    meta = _read_metadata(GANADORAS_DIR)
    meta["temp_borrado_test.py"] = {
        "id": "temp_borrado_test",
        "titulo": "Fórmula de Prueba",
        "timeframe": "1h"
    }
    _write_metadata(GANADORAS_DIR, meta)

    # Verificar que aparece en el listado
    cat_pre = get_catalogo_completo()
    nombres_gan_pre = [it["archivo"] for it in cat_pre["para_testear"]["ganadoras"]]
    assert "temp_borrado_test.py" in nombres_gan_pre

    # 2. Ejecutar DELETE vía API
    res_del = client_lab.delete("/api/catalogo_formulas/para_testear_ganadoras/temp_borrado_test.py")
    assert res_del.status_code == 200
    del_data = res_del.json()
    assert del_data["status"] == "ok"
    assert del_data["eliminado"] == "temp_borrado_test.py"

    # 3. Verificar que el archivo fue borrado físicamente del disco
    assert not temp_file.exists()

    # 4. Verificar que desapareció del catálogo
    cat_post = get_catalogo_completo()
    nombres_gan_post = [it["archivo"] for it in cat_post["para_testear"]["ganadoras"]]
    assert "temp_borrado_test.py" not in nombres_gan_post


def test_evaluador_cuentas_fondeo():
    import pandas as pd
    from backtest_lab.core.metrics import EvaluadorCuantitativo

    evaluador = EvaluadorCuantitativo()

    # Caso 1: Estrategia ganadora con bajo drawdown (Apta para fondeo)
    # 20 trades: 12 ganadores de +2.5% y 8 perdedores de -1.0% (Retorno neto positivo, DD bajo, PF alto)
    trades_aptos = pd.DataFrame({
        "pnl_pct": [2.5, -1.0, 2.5, 2.5, -1.0, 2.5, -1.0, 2.5, 2.5, -1.0,
                    2.5, -1.0, 2.5, 2.5, -1.0, 2.5, -1.0, 2.5, 2.5, -1.0]
    })
    res_apto = evaluador.calcular_metricas(trades_aptos, col_pnl_bruto="pnl_pct", ya_descuenta_friccion=True)
    assert res_apto["apta_fondeo"] is True
    assert "APTA" in res_apto["fondeo_dictamen"]

    # Caso 2: Estrategia con Drawdown excesivo (> 8.0%) -> NO apta para fondeo
    trades_quemados = pd.DataFrame({
        "pnl_pct": [3.0, -9.0, 2.0, -8.0, 1.0, -6.0, 3.0, 2.0, 1.0, -5.0,
                    2.0, -4.0, 1.0, -3.0, 2.0, -4.0, 1.0, -3.0, 2.0, -4.0]
    })
    res_quemado = evaluador.calcular_metricas(trades_quemados, col_pnl_bruto="pnl_pct", ya_descuenta_friccion=True)
    assert res_quemado["apta_fondeo"] is False
    assert "NO APTA" in res_quemado["fondeo_dictamen"]

