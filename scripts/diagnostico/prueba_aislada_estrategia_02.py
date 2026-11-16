"""
Prueba Aislada: Estrategia 02 — Cazador de Rebotes ATR 15m (Fase 4)
Verifica la función matemática determinista pura y la clase EstrategiaBase sin dependencias de red.
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.estrategias.cazador_rebotes_02 import evaluar_estrategia, CazadorRebotes02


def test_evaluar_estrategia_pura():
    print("=================================================================")
    print("TEST 1: Función Matemática Pura (evaluar_estrategia)")
    print("=================================================================")

    # Escenario A: Mercado Neutral (Debe rechazar)
    datos_neutral = {
        "z_score": 0.2,
        "rsi": 54.0,
        "rvol": 0.6,
        "lower_wick_ratio": 0.05,
        "rr_neto": 0.8,
    }
    viable, motivo = evaluar_estrategia(datos_neutral)
    print(f"[-] Escenario Neutral: viable={viable} | Motivo: {motivo}")
    assert viable is False, "Debe rechazar mercado neutral"

    # Escenario B: Pánico Extremo con Absorción y Volumen (Debe aprobar)
    datos_panico = {
        "z_score": -2.4,
        "rsi": 28.0,
        "rvol": 1.5,
        "lower_wick_ratio": 0.35,
        "rr_neto": 1.75,
    }
    viable, motivo = evaluar_estrategia(datos_panico)
    print(f"[+] Escenario Pánico Extremo: viable={viable} | Motivo: {motivo}")
    assert viable is True, "Debe aprobar pánico extremo"

    # Escenario C: Pullback Sano en Tendencia (Debe aprobar)
    datos_pullback = {
        "z_score": -0.85,
        "rsi": 42.0,
        "rvol": 1.2,
        "lower_wick_ratio": 0.30,
        "rr_neto": 1.45,
    }
    viable, motivo = evaluar_estrategia(datos_pullback)
    print(f"[+] Escenario Pullback Sano: viable={viable} | Motivo: {motivo}")
    assert viable is True, "Debe aprobar pullback sano"

    # Escenario D: Pánico pero Sin Volumen (Debe rechazar)
    datos_sin_vol = {
        "z_score": -2.5,
        "rsi": 22.0,
        "rvol": 0.35,
        "lower_wick_ratio": 0.40,
        "rr_neto": 1.5,
    }
    viable, motivo = evaluar_estrategia(datos_sin_vol)
    print(f"[-] Escenario Sin Volumen: viable={viable} | Motivo: {motivo}")
    assert viable is False, "Debe rechazar sin volumen institucional"

    # Escenario E: Confluencia pero R:R Neto Insuficiente tras comisiones (Debe rechazar)
    datos_mal_rr = {
        "z_score": -2.5,
        "rsi": 22.0,
        "rvol": 1.2,
        "lower_wick_ratio": 0.40,
        "rr_neto": 0.75,
    }
    viable, motivo = evaluar_estrategia(datos_mal_rr)
    print(f"[-] Escenario R:R Insuficiente: viable={viable} | Motivo: {motivo}")
    assert viable is False, "Debe rechazar R:R < 1.0"

    print("\n>>> TEST 1 COMPLETADO EXITOSAMENTE: 5/5 ESCENARIOS VALIDADOS <<<\n")


def test_clase_estrategia_modular():
    print("=================================================================")
    print("TEST 2: Clase Modular Cuantitativa (CazadorRebotes02.evaluar)")
    print("=================================================================")

    strat = CazadorRebotes02()
    assert strat.id == "02_cazador_rebotes_atr_15m"

    # Simular entrada técnica completa
    ind = {
        "latest": {"close": 80000.0, "rsi": 29.5},
        "price": 80000.0,
        "atr_14": 800.0,
        "z_score": -2.3,
        "lower_wick_ratio": 0.32,
        "relative_volume": 1.4,
        "timeframe": "15m",
        "live_price": 80010.0,
    }

    metrics, net_tp, eligible, failures, min_tp = strat.evaluar(
        ind=ind,
        tp=3.0,
        sl=1.5,
        fee=0.1,
        spread=0.05,
        min_profit_pct=0.5,
        round_trip_cost=0.3,
        net_tp_manual=2.5,
    )

    print(f"[+] Elegible: {eligible}")
    print(f"[+] Señal sugerida: {metrics['suggested_signal']}")
    print(f"[+] Setup: {metrics['setup']}")
    print(f"[+] TP neto: +{metrics['tp_net_pct']}% | SL neto: {metrics['sl_net_pct']}%")
    print(f"[+] Fallos: {failures}")

    assert eligible is True, "Debe ser elegible para compra"
    assert metrics["suggested_signal"] == "COMPRAR"
    assert metrics["setup"] == "Rebote de Pánico Extremo"

    print("\n>>> TEST 2 COMPLETADO EXITOSAMENTE: CLASE MODULAR OPERATIVA <<<\n")


if __name__ == "__main__":
    test_evaluar_estrategia_pura()
    test_clase_estrategia_modular()
    print("🎉 TODOS LOS TESTS AISLADOS DE LA ESTRATEGIA 02 PASARON EN VERDE.")
