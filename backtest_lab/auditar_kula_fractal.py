"""
Módulo: backtest_lab/auditar_kula_fractal.py
Proyecto: Kula Balam / Backtest Lab
Auditor Cuantitativo Forense de Subfórmulas Fractales (VWAP + Fibonacci + RSI + ATR).
Comprueba el valor agregado de cada subfórmula individual y la confluencia global.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from estrategias_math.kula_fractal_vwap_fibo import (
    calcular_indicadores_fractales,
    evaluar_confluencia_en_barra,
)

DATA_DIR = BASE_DIR / "data" / "datos_historicos"


def simular_activo_fractal(archivo: str, friction_rt: float = 0.0026):
    ruta = DATA_DIR / archivo
    if not ruta.exists():
        return None

    df_raw = pd.read_parquet(ruta)
    df = calcular_indicadores_fractales(df_raw)

    total = len(df)
    indices = df.index
    trades = []

    conteo_sub_a = 0
    conteo_sub_b = 0
    conteo_sub_c = 0
    conteo_total_confluencia = 0

    i = 60
    while i < total - 1:
        res = evaluar_confluencia_en_barra(df, i)

        if res["sub_a_tendencia"]:
            conteo_sub_a += 1
        if res["sub_b_fibo_rsi"]:
            conteo_sub_b += 1
        if res["sub_c_atr"]:
            conteo_sub_c += 1

        if not res["disparo"]:
            i += 1
            continue

        conteo_total_confluencia += 1

        # Ejecución determinista al Open de la barra siguiente
        entry_idx = i + 1
        entry_bar = df.iloc[entry_idx]
        p_entry = float(entry_bar["open"])
        atr = float(res["atr"])

        dist_sl = max(1.5 * atr, p_entry * 0.005)
        sl_price = p_entry - dist_sl
        tp1_price = p_entry + (2.0 * dist_sl)
        be_price = p_entry * (1.0 + friction_rt)

        tp1_hit = False
        exit_leg1 = None
        exit_leg2 = None
        exit_reason = None
        exit_idx = entry_idx

        # Monitoreo de salida asimétrica (Punto 4)
        for j in range(entry_idx, min(entry_idx + 150, total)):
            b = df.iloc[j]
            c_open = float(b["open"])
            c_high = float(b["high"])
            c_low = float(b["low"])
            c_close = float(b["close"])
            ema_20 = float(b["ema_20"])

            # 1. Antes de TP1
            if not tp1_hit:
                if c_open <= sl_price:
                    exit_leg1 = c_open
                    exit_leg2 = c_open
                    exit_reason = "SL_GAP"
                    exit_idx = j
                    break
                if c_low <= sl_price:
                    exit_leg1 = sl_price
                    exit_leg2 = sl_price
                    exit_reason = "SL_INICIAL"
                    exit_idx = j
                    break
                if c_high >= tp1_price:
                    tp1_hit = True
                    exit_leg1 = tp1_price

            # 2. Tras TP1: Breakeven y Trailing EMA 20
            if tp1_hit:
                if c_low <= be_price:
                    exit_leg2 = be_price
                    exit_reason = "TP1_Y_BE"
                    exit_idx = j
                    break
                if c_close < ema_20:
                    exit_leg2 = c_close
                    exit_reason = "TP1_Y_TRAILING_EMA20"
                    exit_idx = j
                    break

        if exit_leg1 is None:
            last_c = float(df["close"].iloc[min(entry_idx + 149, total - 1)])
            exit_leg1 = last_c
            exit_leg2 = last_c
            exit_reason = "EXPIRACION"

        if exit_leg2 is None:
            exit_leg2 = float(df["close"].iloc[min(entry_idx + 149, total - 1)])

        # PnL neto ponderado 50% TP1 + 50% Remanente deduciendo comisiones
        pnl_1 = ((exit_leg1 - p_entry) / p_entry) - friction_rt
        pnl_2 = ((exit_leg2 - p_entry) / p_entry) - friction_rt
        pnl_total = ((0.5 * pnl_1) + (0.5 * pnl_2)) * 100.0

        trades.append({
            "fecha": str(indices[entry_idx])[:16],
            "p_entry": round(p_entry, 2),
            "pnl_pct": round(pnl_total, 2),
            "reason": exit_reason,
        })

        # Salto hasta finalizar el trade
        i = max(i + 1, exit_idx + 1)

    df_trades = pd.DataFrame(trades)
    return {
        "df_trades": df_trades,
        "conteo_sub_a": conteo_sub_a,
        "conteo_sub_b": conteo_sub_b,
        "conteo_sub_c": conteo_sub_c,
        "conteo_confluencia": conteo_total_confluencia,
        "total_velas": total
    }


def ejecutar_auditoria_completa():
    archivos = [
        ("NVDA (5m)", "yf_NVDA_5m.parquet"),
        ("NVDA (15m)", "yf_NVDA_15m.parquet"),
        ("ETH/USDT (15m)", "binance_ETH_USDT_15m.parquet"),
        ("ETH/USDT (1h)", "binance_ETH_USDT_1h.parquet"),
        ("TQQQ (1d)", "yf_TQQQ_1d.parquet"),
        ("USO (1d)", "yf_USO_1d.parquet"),
    ]

    print("=" * 82)
    print("🔬 AUDITORÍA FORENSE DE SUBFÓRMULAS FRACTALES (BACKTEST LAB)")
    print("Sub A: Close > EMA50 & VWAP | Sub B: Fibo [0.50, 0.75] & RSI <= 48 | Sub C: ATR Expansion")
    print("=" * 82)

    resumen_filas = []

    for label, arch in archivos:
        res = simular_activo_fractal(arch, friction_rt=0.0026)
        if not res or res["df_trades"].empty:
            continue

        df_t = res["df_trades"]
        pnls = df_t["pnl_pct"]
        wins = pnls[pnls > 0]
        losses = pnls[pnls <= 0]
        pf = (wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else 99.0
        wr = (len(wins) / len(pnls)) * 100.0
        pnl_tot = pnls.sum()

        resumen_filas.append({
            "Activo / TF": label,
            "Velas": res["total_velas"],
            "Sub A (Tend)": res["conteo_sub_a"],
            "Sub B (Fibo)": res["conteo_sub_b"],
            "Confluencia": len(pnls),
            "Win Rate": f"{wr:.1f}%",
            "Profit Factor": round(pf, 2),
            "PnL Neto": f"{pnl_tot:+.2f}%",
        })

    print(pd.DataFrame(resumen_filas).to_string(index=False))
    print("=" * 82)


if __name__ == "__main__":
    ejecutar_auditoria_completa()
