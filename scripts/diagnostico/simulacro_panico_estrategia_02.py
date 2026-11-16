"""
Simulacro de Pánico Extremo: Estrategia 02 — Cazador de Rebotes ATR 15m
Dispara una inyección de datos simulados de flash-crash para verificar la captura y ejecución en tiempo real.
"""

import sys
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from backend import main
from tests.test_regressions import _quant_strategy_candles


def ejecutar_simulacro():
    print("=" * 70)
    print("🚨 INICIANDO SIMULACRO DE PÁNICO EXTREMO (Fase 4 · Cazador de Rebotes)")
    print("=" * 70)

    # 1. Crear velas con desplome vertical, mecha de absorción y alto volumen institucional
    # drop_low=122.0, drop_close=126.8 genera lower_wick_ratio = (126.8 - 122.0)/(130.0 - 122.0) = 4.8/8 = 0.60
    now_ms = int(time.time() * 1000)
    velas_panico = _quant_strategy_candles(
        now_ms=now_ms,
        extreme_volume=350,
        timeframe="15m",
        drop_close=126.5,
        drop_low=121.0,
    )

    # Inyectar las velas al motor de mercado
    main.get_ohlcv = lambda *args: velas_panico
    main.churn_block_reason = lambda *args, **kwargs: None

    client = TestClient(main.app)

    print("\n📡 PASO 1: Inyectando flash crash al endpoint /api/market/analysis")
    print("   • Estrategia: 02_cazador_rebotes_atr_15m")
    print("   • Motor: antigravity_operador (Cerebro Táctico Nube)")
    print("   • Activo: BTC/USDT [15m]\n")

    res = client.get(
        "/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=antigravity_operador&strategy=02_cazador_rebotes_atr_15m&tp=3.0&sl=1.5&fee=0.1&spread=0.05"
    )

    if res.status_code != 200:
        print(f"❌ Error HTTP {res.status_code}: {res.text}")
        return

    data = res.json()
    metrics = data.get("strategy_metrics", {})
    indicadores = data.get("indicators", {})

    print("-" * 70)
    print(f"🎯 RESULTADO DEL AUDITOR CUANTITATIVO:")
    print(f"   • Señal Emitida:   [{data.get('signal')}]")
    print(f"   • Setup Detectado: {metrics.get('setup')}")
    print(f"   • Z-Score:         {indicadores.get('z_score')} (Umbral pánico: <= -2.0)")
    print(f"   • RSI(14):         {indicadores.get('rsi')}")
    print(f"   • Absorción Mecha: {indicadores.get('lower_wick_ratio')} (Exigido: >= 0.25)")
    print(f"   • Volumen (RVOL):  {indicadores.get('relative_volume')} (Exigido: >= 0.80)")
    print(f"   • TP Neto Proyec:  +{metrics.get('tp_net_pct')}%")
    print(f"   • SL Neto Proyec:  {metrics.get('sl_net_pct')}%")
    print(f"   • Motivo Táctico:  \"{data.get('reason')}\"")
    print("-" * 70)

    # 2. Simular la salida cuando el precio rebota y alcanza el TP (+3.0%)
    print("\n📈 PASO 2: Verificando Cierre Táctico por Rebote y Take Profit")
    entry_price = 126.5
    velas_rebote = [list(c) for c in velas_panico]
    bounce_price = round(entry_price * 1.035, 2)  # +3.5% de rebote ($130.93)
    # Mantener coherencia estricta de rango OHLCV (High >= Close)
    velas_rebote[-2][2] = bounce_price + 1.0
    velas_rebote[-2][4] = bounce_price
    velas_rebote[-1][2] = bounce_price + 1.0
    velas_rebote[-1][4] = bounce_price
    main.get_ohlcv = lambda *args: velas_rebote

    res_bounce = client.get(
        f"/api/market/analysis?symbol=BTC/USDT&timeframe=15m&engine=antigravity_operador&strategy=02_cazador_rebotes_atr_15m&tp=3.0&sl=1.5&has_position=true&entry_price={entry_price}"
    )
    data_bounce = res_bounce.json()

    print(f"   • Precio Entrada:  ${entry_price}")
    print(f"   • Precio Rebote:   ${data_bounce.get('latest_candle', {}).get('close', bounce_price)}")
    print(f"   • Señal de Salida: [{data_bounce.get('signal')}]")
    print(f"   • Motivo Cierre:   \"{data_bounce.get('reason')}\"")
    print("-" * 70)

    if data.get("signal") == "COMPRAR" and data_bounce.get("signal") == "VENDER":
        print("\n🏆 ¡SIMULACRO COMPLETADO CON ÉXITO ROTUNDO!")
        print("   1. La Estrategia 02 detectó la capitulación extrema.")
        print("   2. Antigravity Operador autorizó la compra instantánea (0% CPU).")
        print("   3. Al rebotar el precio, ejecutó la orden de VENTA para asegurar el beneficio.")
    else:
        print(f"\n⚠️ Señal compra: {data.get('signal')} | Señal venta: {data_bounce.get('signal')}")


if __name__ == "__main__":
    ejecutar_simulacro()
