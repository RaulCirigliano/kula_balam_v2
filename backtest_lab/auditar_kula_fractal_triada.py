"""
Módulo: backtest_lab/auditar_kula_fractal_triada.py
Proyecto: Kula Balam / Backtest Lab
Auditor Cuantitativo de la Tríada Fractal (Alex Ruiz & Cava):
- Marco Macro (1D): Tendencia Direccional (Close > EMA 50).
- Marco Estructural (1H): Retroceso en Zona Dorada de Fibonacci (0.50 - 0.75).
- Marco Táctico (5M): Gatillo de confirmación con VWAP, cruce de EMA 20 y expansión de ATR.
- Fricción estricta del 0.26% round-trip.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.data_loader import DataLoaderLab

def simular_triada_fractal(activo: str, mercado: str = "stocks", friction_rt: float = 0.0026):
    loader = DataLoaderLab()
    try:
        df = loader.cargar(activo=activo, mercado=mercado, timeframe_base="5m", fractales=["1h", "1d"])
    except Exception as e:
        print(f"Error cargando {activo}: {e}")
        return None

    # 1. Indicadores tácticos en 5M
    df["ema_20_5m"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_50_5m"] = df["close"].ewm(span=50, adjust=False).mean()

    # VWAP en 5M
    typical_px = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, 1.0)
    dates = df.index.date if isinstance(df.index, pd.DatetimeIndex) else [0] * len(df)
    df["cum_vol"] = vol.groupby(dates).cumsum()
    df["cum_pv"] = (typical_px * vol).groupby(dates).cumsum()
    df["vwap_5m"] = (df["cum_pv"] / df["cum_vol"]).bfill()

    # ATR 14 en 5M
    prev_c = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
    df["atr_5m"] = tr.rolling(14).mean().bfill()
    df["atr_sma_5m"] = df["atr_5m"].rolling(20).mean().bfill()

    # 2. Condiciones fractales
    # Sub A (Macro 1D): Sesgo alcista diario
    cond_macro = df["sesgo_1d"] == 1 if "sesgo_1d" in df.columns else (df["close"] > df["ema_50_5m"])

    # Sub B (Estructural 1H): Fibo en zona dorada [0.35, 0.70]
    cond_fibo = (df["pos_fibo_1h"] >= 0.30) & (df["pos_fibo_1h"] <= 0.75) if "pos_fibo_1h" in df.columns else True

    # Sub C (Táctico 5M): Cruce sobre EMA 20, precio sobre VWAP y expansión de ATR
    cruce_ema20 = (df["close"].shift(1) <= df["ema_20_5m"].shift(1)) & (df["close"] > df["ema_20_5m"])
    precio_vwap = df["close"] >= (df["vwap_5m"] * 0.999)
    expansion_atr = df["atr_5m"] > df["atr_sma_5m"]

    cond_gatillo_5m = cruce_ema20 & precio_vwap & expansion_atr

    df["signal"] = cond_macro & cond_fibo & cond_gatillo_5m

    # 3. Simulación de órdenes con Salida Asimétrica (Punto 4)
    trades = []
    indices = df.index
    total = len(df)

    i = 50
    while i < total - 1:
        if not df["signal"].iloc[i]:
            i += 1
            continue

        entry_idx = i + 1
        entry_bar = df.iloc[entry_idx]
        p_entry = float(entry_bar["open"])
        atr = float(df["atr_5m"].iloc[i])

        dist_sl = max(1.5 * atr, p_entry * 0.005)
        sl_price = p_entry - dist_sl
        tp1_price = p_entry + (2.0 * dist_sl)
        be_price = p_entry * (1.0 + friction_rt)

        tp1_hit = False
        exit_leg1 = None
        exit_leg2 = None
        exit_reason = None
        exit_idx = entry_idx

        for j in range(entry_idx, min(entry_idx + 120, total)):
            b = df.iloc[j]
            c_open = float(b["open"])
            c_high = float(b["high"])
            c_low = float(b["low"])
            c_close = float(b["close"])
            ema_20 = float(b["ema_20_5m"])

            # Antes de TP1
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

            # Tras TP1: Breakeven y Trailing EMA 20
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
            last_c = float(df["close"].iloc[min(entry_idx + 119, total - 1)])
            exit_leg1 = tp1_price if tp1_hit else last_c
            exit_leg2 = last_c
            exit_reason = "EXPIRACION"

        if exit_leg2 is None:
            exit_leg2 = float(df["close"].iloc[min(entry_idx + 119, total - 1)])

        pnl_1 = ((exit_leg1 - p_entry) / p_entry) - friction_rt
        pnl_2 = ((exit_leg2 - p_entry) / p_entry) - friction_rt
        pnl_tot = ((0.5 * pnl_1) + (0.5 * pnl_2)) * 100.0

        trades.append({
            "fecha": str(indices[entry_idx])[:16],
            "p_entry": round(p_entry, 2),
            "pnl_pct": round(pnl_tot, 2),
            "reason": exit_reason
        })

        i = max(i + 1, exit_idx + 1)

    return pd.DataFrame(trades)

def ejecutar_auditoria():
    print("=" * 80)
    print("🐅 AUDITORÍA CUANTITATIVA: TRÍADA FRACTAL (1D -> 1H FIBO -> 5M VWAP & EMA)")
    print("Fricción: 0.26% Round-Trip | Entrada: Open(i+1) | Peluqueo 50% TP1 + Trailing EMA20")
    print("=" * 80)

    activos = [
        ("NVDA", "stocks"),
        ("QQQ", "stocks"),
        ("SPY", "stocks"),
        ("TSLA", "stocks"),
    ]

    for ticker, mkt in activos:
        df_tr = simular_triada_fractal(ticker, mercado=mkt)
        if df_tr is None or df_tr.empty:
            print(f"⚠️ {ticker}: Sin trades generados.")
            continue

        pnls = df_tr["pnl_pct"]
        wins = pnls[pnls > 0]
        losses = pnls[pnls <= 0]
        pf = (wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else 99.0
        wr = (len(wins) / len(pnls)) * 100.0
        pnl_total = pnls.sum()

        print(f"\nResultados para {ticker}:")
        print(f"  • Trades Totales: {len(pnls)}")
        print(f"  • Win Rate: {wr:.2f}%")
        print(f"  • Profit Factor: {pf:.2f}")
        print(f"  • PnL Neto Acumulado: {pnl_total:+.2f}%")
        print(f"  • Salidas: {df_tr['reason'].value_counts().to_dict()}")

    print("=" * 80)

if __name__ == "__main__":
    ejecutar_auditoria()
