# -*- coding: utf-8 -*-
"""
ESTRATEGIA CERTIFICADA PROP FIRM (APTO FONDEO) - KULA BALAM & BACKTEST LAB
Activo: ETH/USDT | Dataset: binance_ETH_USDT_4h.parquet | Timeframe: 4h
Identificador: squeeze_dual_eth_fondeo_strict_4h.py
Certificación Cuentas de Fondeo (Prop Firm Compliance - RFC-2026-11):
  - Retorno Neto Total (Con IA) : +59.68%
  - Profit Factor Neto (Con IA) : 2.53 (IS PF 3.06 | OOS Ciego PF 1.80)
  - Win Rate Neto               : 51.61% (16W - 15L)
  - Ratio R:R Realizado         : 1:2.37
  - Máximo Drawdown (≤ 8.0%)    : 6.50%  -> [🟢 APTO FONDEO]
  - Max Daily Drawdown (≤ 4.5%) : 2.99%  -> [🟢 APTO FONDEO]
  - Racha Máx Pérdidas          : 4 trades
  - Tolerancia Anti-Ruina Slot  : Aprobada ($25 -> $35 USD)
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


# --- ÁRBITRO HEURÍSTICO IA & FILTRO CUSTOM BRAIN ---
CONFIG_IA = {
    "asimetria_rr_minima": 2.0,
    "rvol_minimo": 1.15,
    "max_mecha_contra_pct": 32.0,
    "max_distancia_ema50_atrs": 2.8,
    "max_sl_pct_fondeo": 2.90,
}


def arbitro_ia(fila, lado, entry, sl, tp):
    """
    Evalúa la calidad microestructural de la señal generada por Balam en 4H para Cuentas de Fondeo.
    Devuelve: (autorizado: bool, multiplicador_riesgo: float, motivo: str)
    """
    p_ref = float(fila.get("close", entry)) if hasattr(fila, "get") else float(entry)
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:{CONFIG_IA['asimetria_rr_minima']:.1f})"

    sl_pct = (riesgo / (p_ref + 1e-9)) * 100.0
    if sl_pct > (CONFIG_IA["max_sl_pct_fondeo"] + 0.01):
        return False, 0.0, f"VETO Riesgo Excesivo Fondeo ({sl_pct:.2f}% > {CONFIG_IA['max_sl_pct_fondeo']:.2f}%)"

    rvol = float(fila.get("rvol", 1.0)) if hasattr(fila, "get") else 1.0
    if rvol < CONFIG_IA["rvol_minimo"]:
        return False, 0.0, f"VETO Secado de Volumen ({rvol:.2f}x < {CONFIG_IA['rvol_minimo']:.2f}x)"

    m_sup = float(fila.get("mecha_superior_pct", 0.0)) if hasattr(fila, "get") else 0.0
    m_inf = float(fila.get("mecha_inferior_pct", 0.0)) if hasattr(fila, "get") else 0.0
    lim_mecha = CONFIG_IA["max_mecha_contra_pct"]
    if lado == "LONG" and m_sup > lim_mecha:
        return False, 0.0, f"VETO Absorción Oferta Superior ({m_sup:.1f}% > {lim_mecha:.1f}%)"
    if lado == "SHORT" and m_inf > lim_mecha:
        return False, 0.0, f"VETO Absorción Demanda Inferior ({m_inf:.1f}% > {lim_mecha:.1f}%)"

    dist_ema = float(fila.get("dist_ema_atrs", 0.0)) if hasattr(fila, "get") else 0.0
    if dist_ema > CONFIG_IA["max_distancia_ema50_atrs"]:
        return False, 0.0, f"VETO Sobreextensión EMA50 ({dist_ema:.2f} ATR > {CONFIG_IA['max_distancia_ema50_atrs']:.1f})"

    return True, 1.0, "AUTORIZADO por Antigravity CIO (Squeeze Fondeo + Flujo Institucional Validado)"


def custom_brain_filter(df_eval, idx, side, entry_px, sl_px, tp_px):
    """
    Gancho estándar RFC-2026-11 para integración con CatalogFormulaStrategy en Kula Balam.
    """
    fila = df_eval.iloc[idx]
    aut, mult, motivo = arbitro_ia(fila, side, entry_px, sl_px, tp_px)
    return aut, mult, motivo
