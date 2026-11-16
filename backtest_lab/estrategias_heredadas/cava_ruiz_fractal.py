# -*- coding: utf-8 -*-
"""
ESTRATEGIA HEREDADA EN CONTENEDOR DE AUDITORÍA: Kula Balam Cava & Ruiz
Doctrina: Tríada Fractal, Zona Dorada Fibonacci (0.50 - 0.75), Soporte EMA 50 y Secado RVOL.
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_BTC_USDT_4h.parquet"
MAX_BARS_HOLD = 48

def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_cava_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
        df["_atr14"] = tr.rolling(14).mean().shift(1).bfill()
        df["_ema50"] = df["close"].ewm(span=50, adjust=False).mean().shift(1)
        df["_ema200"] = df["close"].ewm(span=200, adjust=False).mean().shift(1)
        df["_h30"] = df["high"].shift(1).rolling(30).max().bfill()
        df["_l30"] = df["low"].shift(1).rolling(30).min().bfill()
        vol = df["volume"] if "volume" in df.columns else pd.Series(1.0, index=df.index)
        vol_sma = vol.rolling(20).mean().shift(1).bfill()
        df["_rvol"] = (vol / (vol_sma + 1e-9)).shift(1)
        df["_cava_init"] = True

    if i < 65:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    c = float(row["close"])
    o = float(row["open"])
    l = float(row["low"])
    h = float(row["high"])
    e50 = float(row["_ema50"])
    e200 = float(row["_ema200"])
    h30 = float(row["_h30"])
    l30 = float(row["_l30"])
    atr = float(row["_atr14"])
    rvol = float(row["_rvol"])

    rng_fibo = max(h30 - l30, 1e-9)
    fibo_50 = h30 - (0.50 * rng_fibo)
    fibo_75 = h30 - (0.75 * rng_fibo)

    # Filtro Macro: Tendencia alcista EMA 50 > EMA 200
    if e50 <= e200:
        return False, None, 0.0, 0.0

    # Retroceso a Zona Dorada (0.50 a 0.75) con soporte en EMA 50
    en_zona_dorada = (c <= fibo_50) and (c >= fibo_75)
    cierre_sobre_ema = (c > e50) and (c > o)
    secado_vol = rvol < 1.10

    if en_zona_dorada and cierre_sobre_ema and secado_vol:
        sl_dist = max(c - fibo_75 + (0.5 * atr), 1.5 * atr)
        tp_dist = 2.2 * sl_dist  # Asimetría R:R 1:2.2
        return True, "LONG", c - sl_dist, c + tp_dist

    return False, None, 0.0, 0.0


def arbitro_ia(fila, lado, entry, sl, tp) -> Tuple[bool, float, str]:
    dist_sl = abs(float(entry) - float(sl))
    dist_tp = abs(float(tp) - float(entry))
    rr = dist_tp / (dist_sl + 1e-9)

    if rr < 2.0:
        return False, 0.0, f"VETO Asimetría insuficiente ({rr:.2f} < 1:2.0)"

    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    if m_inf < 15.0:
        return False, 0.0, f"VETO Falta de mecha de absorción ({m_inf:.1f}% < 15%)"

    return True, 1.0, "AUTORIZADO: Cava & Ruiz Zona Dorada y Secado Confirmado"
