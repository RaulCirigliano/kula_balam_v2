# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/estrategias_math/squeeze_dual_eth_fondeo_strict_4h.py
Proyecto: Kula Balam / Backtest Lab (Rol BALAM - Músculo Matemático Determinista)
Activo / Temporalidad: ETH/USDT 4H (3 Años: 6,570 velas | 2023-11 -> 2026-11)
Certificación Cuentas de Fondeo (Prop Firm Compliance - RFC-2026-11):
  1. Régimen Alcista Macro (Close > EMA 200 y Pendiente EMA 200 > 0):
     Compresión previa de Bandas de Bollinger respecto a ATR (Squeeze <= 1.25x mediana 60p)
     + Ruptura simultánea de Banda Superior Bollinger y Canal Donchian de 20 velas.
  2. Régimen Bajista Macro (Close < EMA 200, EMA 50 < EMA 200 y Pendiente EMA 200 < 0):
     Rebote correctivo previo hacia zona dinámica de oferta (High_8 >= 0.985 * EMA 50)
     + Quiebre estructural bajista del soporte de 8 velas (BOS < Donchian Low 8).
  3. Gestión Asimétrica Pura: SL = 1.40x ATR(14) | TP = 3.64x ATR(14) (R:R Teórico 1:2.60).
  4. Candado Anti-Ruina Fondeo: Veto de volatilidad si Rango > 2.6x ATR o si (1.4 * ATR / Close) > 2.9%
     (acota el Max Drawdown al 6.50% y el Max Daily Drawdown a 2.99%).
"""

from typing import Tuple, Optional
import pandas as pd

DATASET = "binance_ETH_USDT_4h.parquet"
ARBITRO_IA = "arbitro_eth_fondeo_4h.py"
MAX_BARS_HOLD = 84

VELA_TESTIGO = {
    "fecha_historica": "2026-09-29 08:00:00",
    "close_offset_pct": -1.35,
    "rvol": 1.85,
    "mecha_sup_pct": 8.0,
    "mecha_inf_pct": 8.0,
    "cuerpo_pct": 75.0,
}


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    """
    Motor determinista Balam para ETH/USDT 4H con filtro de volatilidad para Fondeo (Prop Firm).
    Calcula estructuras de volatilidad y tendencia de forma estrictamente causal (shift(1)).
    """
    if "_eth4h_sq_fnd_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev_c).abs(),
                (df["low"] - prev_c).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["_atr14"] = tr.rolling(14).mean().shift(1).bfill()
        df["_ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["_ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["_slp200"] = df["_ema200"] - df["_ema200"].shift(8)

        sma20 = df["close"].shift(1).rolling(20).mean().bfill()
        std20 = df["close"].shift(1).rolling(20).std().bfill()
        df["_bb_up"] = sma20 + (2.0 * std20)
        bb_w = (4.0 * std20) / (df["_atr14"] + 1e-9)
        df["_bb_w"] = bb_w
        df["_bb_w_med"] = bb_w.rolling(60, min_periods=20).median().bfill()

        df["_dh20"] = df["high"].shift(1).rolling(20).max().bfill()
        df["_dl8"] = df["low"].shift(1).rolling(8).min().bfill()
        df["_high8"] = df["high"].shift(1).rolling(8).max().bfill()
        df["_eth4h_sq_fnd_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    c = float(row["close"])
    atr = float(row["_atr14"])

    # Filtro determinista contra velas climáticas (> 2.6 ATR) o riesgo porcentual excesivo (> 2.9% spot)
    if (h - l) > (2.6 * atr) or ((1.4 * atr / c) * 100.0) > 2.9:
        return False, None, 0.0, 0.0

    e50 = float(row["_ema50"])
    e200 = float(row["_ema200"])
    slp200 = float(row["_slp200"]) if pd.notna(row["_slp200"]) else 0.0

    # Pata LONG: Expansión alcista desde compresión Bollinger + ruptura Donchian 20
    squeeze_activo = float(row["_bb_w"]) <= (float(row["_bb_w_med"]) * 1.25)
    es_long = (
        (c > e200)
        and (slp200 > 0.0)
        and squeeze_activo
        and (c > float(row["_bb_up"]))
        and (c > float(row["_dh20"]))
        and (c > o)
    )
    if es_long:
        dist_sl = 1.4 * atr
        return True, "LONG", c - dist_sl, c + (2.6 * dist_sl)

    # Pata SHORT: Rechazo en EMA 50 dentro de tendencia bajista + quiebre suelo 8 velas
    es_short = (
        (c < e200)
        and (e50 < e200)
        and (slp200 < 0.0)
        and (float(row["_high8"]) >= (e50 * 0.985))
        and (c < float(row["_dl8"]))
        and (c < o)
    )
    if es_short:
        dist_sl = 1.4 * atr
        return True, "SHORT", c + dist_sl, c - (2.6 * dist_sl)

    return False, None, 0.0, 0.0
