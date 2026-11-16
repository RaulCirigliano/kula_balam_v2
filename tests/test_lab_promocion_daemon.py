# -*- coding: utf-8 -*-
"""
Pruebas Unitarias para el Módulo de Promoción a Daemon en Vivo (Fase 4).
Valida el mapeo de datasets a símbolos del broker, la generación de tarjetas de oportunidad
en buzon_radar.json, el archivado en promovidas/ y la integración con el auto-enrutador del TraderDaemon.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backtest_lab.server import (
    app,
    mapear_dataset_a_simbolo,
    PROMOVIDAS_DIR,
    BASE_DIR
)
from backend.radar_inbox import BUZON_FILE


def test_mapear_dataset_a_simbolo():
    assert mapear_dataset_a_simbolo("binance_SOL_USDT_4h.parquet") == "SOL/USDT"
    assert mapear_dataset_a_simbolo("binance_BTC_USDT_1d.parquet") == "BTC/USDT"
    assert mapear_dataset_a_simbolo("binance_ETH_USDT_15m.parquet") == "ETH/USDT"
    assert mapear_dataset_a_simbolo("yf_AAPL_1d.parquet") == "AAPL"
    assert mapear_dataset_a_simbolo("yf_SPY_1d.parquet") == "SPY"
    assert mapear_dataset_a_simbolo("yf_EURUSD_1d.parquet") == "EURUSD=X"
    assert mapear_dataset_a_simbolo("AUTO") == "SOL/USDT"
    assert mapear_dataset_a_simbolo("") == "SOL/USDT"


def test_api_promover_a_produccion_exitoso(tmp_path, monkeypatch):
    import urllib.request
    from backend import radar_inbox

    isolated_buzon = tmp_path / "buzon_radar.json"
    isolated_bias = tmp_path / "macro_bias_buffer.json"
    monkeypatch.setattr(radar_inbox, "BUZON_FILE", str(isolated_buzon))
    monkeypatch.setenv("BUZON_RADAR_PATH", str(isolated_buzon))
    monkeypatch.setenv("MACRO_BIAS_BUFFER_PATH", str(isolated_bias))

    def _no_live_http(*args, **kwargs):
        raise OSError("Disabled live HTTP bridge in unit test")

    monkeypatch.setattr(urllib.request, "urlopen", _no_live_http)

    client = TestClient(app)
    sample_math = '''# -*- coding: utf-8 -*-
DATASET = "binance_SOL_USDT_4h.parquet"
def formula_matematica(df, i):
    return False, None, 0.0, 0.0
'''
    sample_ia = '''def arbitro_ia(fila, lado, entry, sl, tp): return True, 1.0, "OK"'''

    payload = {
        "ticker": "binance_SOL_USDT_4h.parquet",
        "code_math": sample_math,
        "code_ia": sample_ia,
        "nombre": "donchian_breakout_test.py",
        "slot_id": 2,
        "confianza": 88,
        "justificacion": "Estrategia validada con PF=2.0 y R:R=2.6 en SOL 4H"
    }

    arch_guardado = None
    try:
        resp = client.post("/api/promover_a_produccion", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "ok"
        assert data["activo"] == "SOL/USDT"
        assert data["slot_id"] == 2
        assert data["confianza"] == 88
        assert "card_id" in data
        assert data["card_id"].startswith("lab-promoted-")

        # 1. Verificar archivo guardado en promovidas/
        arch_guardado = PROMOVIDAS_DIR / data["archivo_guardado"]
        assert arch_guardado.exists()
        assert "donchian_breakout_test" in arch_guardado.name
        content = arch_guardado.read_text(encoding="utf-8")
        assert "ESTRATEGIA CERTIFICADA EN BACKTEST LAB" in content
        assert "SOL/USDT" in content

        # 2. Verificar tarjeta en buzon_radar aislado
        assert isolated_buzon.exists()
        cards = json.loads(isolated_buzon.read_text(encoding="utf-8"))
        card_promovida = next((c for c in cards if c.get("id") == data["card_id"]), None)
        assert card_promovida is not None
        assert card_promovida["activo"] == "SOL/USDT"
        assert card_promovida["confianza"] == 88
        assert card_promovida["impacto"] == "POSITIVO"
    finally:
        if arch_guardado is not None and arch_guardado.exists():
            arch_guardado.unlink()
        for cat_sub in ["principal", "operador_presente", "para_testear/ganadoras"]:
            target_cat_dir = BASE_DIR.parent / "backend" / "estrategias" / "catalogo" / cat_sub
            cand_f = target_cat_dir / "donchian_breakout_test.py"
            if cand_f.exists():
                cand_f.unlink()
            meta_p = target_cat_dir / "metadata.json"
            if meta_p.exists():
                try:
                    mg = json.loads(meta_p.read_text(encoding="utf-8"))
                    if "donchian_breakout_test.py" in mg:
                        del mg["donchian_breakout_test.py"]
                        meta_p.write_text(json.dumps(mg, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass
        math_cand = BASE_DIR / "estrategias_math" / "donchian_breakout_test.py"
        if math_cand.exists():
            math_cand.unlink()
        math_meta = BASE_DIR / "estrategias_math" / "metadata.json"
        if math_meta.exists():
            try:
                mm = json.loads(math_meta.read_text(encoding="utf-8"))
                if "donchian_breakout_test.py" in mm:
                    del mm["donchian_breakout_test.py"]
                    math_meta.write_text(json.dumps(mm, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass


def test_api_promover_codigo_vacio():
    client = TestClient(app)
    resp = client.post("/api/promover_a_produccion", json={"code_math": ""})
    assert resp.status_code == 400


def test_enrutamiento_radar_daemon():
    # Comprobar que el formato emitido por la promoción es compatible con TraderDaemon
    from backend.radar_inbox import parse_iso_timestamp, OpportunityCard
    from datetime import datetime, timezone

    card = OpportunityCard(
        id="lab-promoted-test1234",
        timestamp=datetime.now(timezone.utc).isoformat(),
        activo="SOL/USDT",
        titular="[LAB PROMOTION] donchian_breakout.py (SOL/USDT) -> Slot 1",
        impacto="POSITIVO",
        confianza=85,
        justificacion="Estrategia validada en Lab"
    )

    assert card.confianza >= 75
    assert card.impacto == "POSITIVO"
    dt = parse_iso_timestamp(card.timestamp)
    assert dt is not None
    assert card.activo == "SOL/USDT"
