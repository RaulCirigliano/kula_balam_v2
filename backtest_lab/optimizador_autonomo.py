#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/optimizador_autonomo.py
Proyecto: Kula Balam / Backtest Lab
Propósito: Optimizador Cuantitativo Local con Auditoría Walk-Forward Estricta (70% IS -> 30% OOS Ciego).
  - En series 1H / 4H / 1D: explora familias estructurales de Compresión de Volatilidad (Squeeze Bollinger/Donchian)
    y Régimen Dual Asimétrico (Ruptura Alcista Comprimida + Ruptura Bajista tras Rechazo en EMA 50).
  - En series 5M / 15M TradFi: mantiene barrido de reversión VWAP sometido igualmente a Walk-Forward IS/OOS.
  - Cero uso de OOS en la selección: el ranking se efectúa 100% en In-Sample (IS_H1 + IS_H2), y solo el
    Top 5 se somete a validación ciega Out-of-Sample.
Fricción Institucional Aplicada: 0.03% Forex, 0.10% TradFi Acciones/ETFs, 0.26% Cripto Spot/Perp.
"""

import sys
import json
import itertools
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
import pandas as pd

BASE_LAB_DIR = Path(__file__).resolve().parent
if str(BASE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_LAB_DIR))

from core.metrics import EvaluadorCuantitativo

DATA_DIR = BASE_LAB_DIR / "data" / "datos_historicos"
GANADORAS_FILE = BASE_LAB_DIR / "estrategias_ganadoras.json"
ESTRATEGIAS_MATH_DIR = BASE_LAB_DIR / "estrategias_math"
META_MATH = ESTRATEGIAS_MATH_DIR / "metadata.json"


def cargar_dataset(nombre_ticker: str) -> pd.DataFrame:
    """Carga y prepara dataset asegurando DatetimeIndex UTC causal y columnas OHLCV."""
    ruta = DATA_DIR / nombre_ticker
    if not ruta.exists():
        raise FileNotFoundError(f"Dataset {nombre_ticker} no existe en {DATA_DIR}")

    df = pd.read_parquet(ruta) if ruta.suffix == ".parquet" else pd.read_csv(ruta)
    df.columns = [str(c).lower() for c in df.columns]

    if not isinstance(df.index, pd.DatetimeIndex):
        col_t = next((c for c in ["timestamp", "datetime", "date", "time"] if c in df.columns), None)
        if col_t:
            s_t = df[col_t]
            if pd.api.types.is_numeric_dtype(s_t):
                unit = "ms" if float(s_t.iloc[0]) > 1e11 else "s"
                df[col_t] = pd.to_datetime(s_t, unit=unit, utc=True)
            else:
                df[col_t] = pd.to_datetime(s_t, utc=True)
            df.set_index(col_t, inplace=True)
        else:
            raise ValueError("No se detectó columna temporal válida.")
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = df[col].astype(float)

    prev_c = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.rolling(14).mean().shift(1).bfill()

    vol_col = "volume" if "volume" in df.columns else None
    if vol_col and df[vol_col].sum() > 0:
        vol_sma = df[vol_col].rolling(20).mean().shift(1).bfill()
        df["rvol"] = df[vol_col] / (vol_sma + 1e-9)
    else:
        df["rvol"] = 1.3

    rango = (df["high"] - df["low"]).replace(0, 1e-9)
    techo = df[["open", "close"]].max(axis=1)
    suelo = df[["open", "close"]].min(axis=1)
    df["mecha_sup_pct"] = ((df["high"] - techo) / rango) * 100.0
    df["mecha_inf_pct"] = ((suelo - df["low"]) / rango) * 100.0

    return df


def _obtener_friccion(ticker: str) -> Tuple[float, float]:
    t_up = ticker.upper()
    if any(fx in t_up for fx in ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD"]):
        return 0.0001, 0.00005
    if any(st in t_up for st in ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "GOOGL", "AMZN", "AVGO", "TQQQ", "URA", "USO"]):
        return 0.0002, 0.0003
    return 0.0008, 0.0005


def precalcular_estructural_swing(df: pd.DataFrame) -> pd.DataFrame:
    """Precalcula canales Donchian, Squeeze Bollinger/ATR y EMAs macro sin sesgo de futuro."""
    d = df.copy()
    for sp in [50, 100, 150, 200]:
        d[f"ema_{sp}"] = d["close"].ewm(span=sp, adjust=False).mean()
    d["dist50"] = (d["close"] - d["ema_50"]).abs() / (d["atr"] + 1e-9)

    sma20 = d["close"].shift(1).rolling(20).mean().bfill()
    std20 = d["close"].shift(1).rolling(20).std().bfill()
    d["bb_up"] = sma20 + 2.0 * std20
    d["bb_dn"] = sma20 - 2.0 * std20
    d["bb_w"] = (d["bb_up"] - d["bb_dn"]) / (d["atr"] + 1e-9)
    d["bb_w_med"] = d["bb_w"].rolling(60, min_periods=20).median().bfill()

    for k in [8, 10, 15, 20, 30]:
        d[f"dh_{k}"] = d["high"].shift(1).rolling(k).max().bfill()
        d[f"dl_{k}"] = d["low"].shift(1).rolling(k).min().bfill()
    for dn in [20, 30]:
        d[f"bw_{dn}"] = (d[f"dh_{dn}"] - d[f"dl_{dn}"]) / (d["atr"] + 1e-9)
        d[f"bw_med_{dn}"] = d[f"bw_{dn}"].shift(1).rolling(60, min_periods=20).median().bfill()

    d["high_8"] = d["high"].shift(1).rolling(8).max().bfill()
    return d


def _simular_vector_rango(
    o: np.ndarray,
    h: np.ndarray,
    l: np.ndarray,
    c: np.ndarray,
    sig: np.ndarray,
    sl_a: np.ndarray,
    tp_a: np.ndarray,
    start_idx: int,
    end_idx: int,
    max_hold: int = 84,
) -> List[Dict[str, Any]]:
    trades = []
    pos = False
    ex_bar = -1
    n_tot = len(c)
    lim_sup = min(end_idx, n_tot - 1)

    for i in range(start_idx, lim_sup):
        if pos and i >= ex_bar:
            pos = False
        if pos:
            continue
        side = int(sig[i])
        if side == 0:
            continue

        entry = float(o[i + 1])
        sl = float(sl_a[i])
        tp = float(tp_a[i])
        lim = min(i + max_hold, n_tot - 1)
        p_ex = float(c[lim])
        ex_bar = lim
        rsn = "TIME"

        if side == 1:
            for j in range(i + 1, lim + 1):
                if l[j] <= sl:
                    p_ex, ex_bar, rsn = sl, j, "SL"
                    break
                if h[j] >= tp:
                    p_ex, ex_bar, rsn = tp, j, "TP"
                    break
            pnl = ((p_ex - entry) / entry) * 100.0
        else:
            for j in range(i + 1, lim + 1):
                if h[j] >= sl:
                    p_ex, ex_bar, rsn = sl, j, "SL"
                    break
                if l[j] >= 0 and l[j] <= tp:
                    p_ex, ex_bar, rsn = tp, j, "TP"
                    break
            pnl = ((entry - p_ex) / entry) * 100.0

        trades.append({"pnl_pct": pnl, "reason": rsn, "bar": i})
        pos = True

    return trades


def _generar_senales_estructurales(df: pd.DataFrame, p: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    atr = df["atr"].values
    e50 = df["ema_50"].values
    em = df[f"ema_{p['ema_macro']}"].values
    slp = em - np.roll(em, 8)
    slp[:8] = 0.0

    fam = p["familia"]
    if fam == "BB_SQUEEZE_DUAL":
        bb_s = df["bb_w"].values <= (df["bb_w_med"].values * p["squeeze_mult"])
        lg = (
            (c > em)
            & (slp > 0)
            & bb_s
            & (c > df["bb_up"].values)
            & (c > df[f"dh_{p['donchian_n']}"].values)
            & (c > o)
            & ((h - l) <= 2.6 * atr)
        )
        sh = (
            (c < em)
            & (e50 < em)
            & (slp < 0)
            & (df["high_8"].values >= e50 * 0.985)
            & (c < df[f"dl_{p['bos_short']}"].values)
            & (c < o)
            & ((h - l) <= 2.6 * atr)
        )
    else:  # DONCHIAN_SQUEEZE
        dn = p["donchian_n"]
        cap_bw = float(p.get("cap_atr", 6.0))
        comp = (
            (df[f"bw_{dn}"].values <= cap_bw)
            & (df[f"bw_{dn}"].values <= df[f"bw_med_{dn}"].values * p["squeeze_mult"])
            & ((h - l) <= 2.6 * atr)
        )
        lg = comp & (c > df[f"dh_{dn}"].values) & (c > em) & (slp > 0) & (c >= o)
        sh = comp & (c < df[f"dl_{dn}"].values) & (c < em) & (slp < 0) & (c <= o)

    raw_sig = np.where(lg, 1, np.where(sh, -1, 0))
    filtro_calidad = (
        (df["rvol"].values >= p["rvol_min"])
        & (df["dist50"].values <= p["max_dist_atr"])
        & np.where(raw_sig == 1, df["mecha_sup_pct"].values <= 32.0, df["mecha_inf_pct"].values <= 32.0)
    )
    sig = np.where(filtro_calidad, raw_sig, 0)
    dsl = p["sl_mult"] * atr
    sl_a = np.where(sig == 1, c - dsl, c + dsl)
    tp_a = np.where(sig == 1, c + p["rr_target"] * dsl, c - p["rr_target"] * dsl)
    return sig, sl_a, tp_a


def _construir_codigo_certificado(ticker: str, p: Dict[str, Any], m_full: Dict[str, Any], m_is: Dict[str, Any], m_oos: Dict[str, Any]) -> str:
    arb_sug = "arbitro_squeeze_dual_4h.py" if p.get("familia") == "BB_SQUEEZE_DUAL" else "arbitro_donchian_breakout_1h.py"
    return f'''# -*- coding: utf-8 -*-
"""
Fórmula Estructural Certificada por Walk-Forward Autónomo (70% IS / 30% OOS Ciego)
Dataset Base: {ticker}
Métricas 3Y : N={m_full["trades_totales"]} | PF={m_full["pf_neto"]} | WR={m_full["win_rate_neto"]}% | R:R={m_full["rr_promedio_neto"]} | Max DD={m_full["max_drawdown_pct"]}%
Walk-Forward: IS PF={m_is["pf_neto"]} (N={m_is["trades_totales"]}) | OOS Ciego PF={m_oos["pf_neto"]} (N={m_oos["trades_totales"]}, Ret={m_oos["retorno_neto_total_pct"]}%)
Configuración: {p["descripcion"]}
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = {repr(ticker)}
ARBITRO_IA = {repr(arb_sug)}
MAX_BARS_HOLD = 84
PARAMETROS_CALIBRADOS = {repr(p)}


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_wf_auto_init" not in df.columns:
        prev_c = df["close"].shift(1)
        tr = pd.concat(
            [df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()],
            axis=1,
        ).max(axis=1)
        df["_atr"] = tr.rolling(14).mean().shift(1).bfill()
        df["_ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        em_sp = int(PARAMETROS_CALIBRADOS["ema_macro"])
        df["_ema_m"] = df["close"].ewm(span=em_sp, adjust=False).mean()
        df["_ema_slp"] = df["_ema_m"] - df["_ema_m"].shift(8)

        dn = int(PARAMETROS_CALIBRADOS["donchian_n"])
        df["_dh"] = df["high"].shift(1).rolling(dn).max().bfill()
        df["_dl"] = df["low"].shift(1).rolling(dn).min().bfill()
        df["_bw"] = (df["_dh"] - df["_dl"]) / (df["_atr"] + 1e-9)
        df["_bw_med"] = df["_bw"].shift(1).rolling(60, min_periods=20).median().bfill()

        sma20 = df["close"].shift(1).rolling(20).mean().bfill()
        std20 = df["close"].shift(1).rolling(20).std().bfill()
        df["_bb_up"] = sma20 + 2.0 * std20
        bb_w = (4.0 * std20) / (df["_atr"] + 1e-9)
        df["_bb_w"] = bb_w
        df["_bb_w_med"] = bb_w.rolling(60, min_periods=20).median().bfill()

        bos_sh = int(PARAMETROS_CALIBRADOS.get("bos_short", 8))
        df["_dl_sh"] = df["low"].shift(1).rolling(bos_sh).min().bfill()
        df["_high_8"] = df["high"].shift(1).rolling(8).max().bfill()
        df["_wf_auto_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    c = float(row["close"])
    atr = float(row["_atr"])
    e50 = float(row["_ema_50"])
    em = float(row["_ema_m"])
    slp = float(row["_ema_slp"]) if pd.notna(row["_ema_slp"]) else 0.0

    if (h - l) > (2.6 * atr):
        return False, None, 0.0, 0.0

    fam = PARAMETROS_CALIBRADOS["familia"]
    sq_m = float(PARAMETROS_CALIBRADOS["squeeze_mult"])
    sl_m = float(PARAMETROS_CALIBRADOS["sl_mult"])
    rr = float(PARAMETROS_CALIBRADOS["rr_target"])
    dsl = sl_m * atr

    if fam == "BB_SQUEEZE_DUAL":
        es_long = (c > em) and (slp > 0) and (float(row["_bb_w"]) <= float(row["_bb_w_med"]) * sq_m) and (c > float(row["_bb_up"])) and (c > float(row["_dh"])) and (c > o)
        es_short = (c < em) and (e50 < em) and (slp < 0) and (float(row["_high_8"]) >= e50 * 0.985) and (c < float(row["_dl_sh"])) and (c < o)
    else:
        comp = float(row["_bw"]) <= (float(row["_bw_med"]) * sq_m)
        es_long = comp and (c > float(row["_dh"])) and (c > em) and (slp > 0) and (c > o)
        es_short = comp and (c < float(row["_dl"])) and (c < em) and (slp < 0) and (c < o)

    if es_long:
        return True, "LONG", c - dsl, c + (rr * dsl)
    if es_short:
        return True, "SHORT", c + dsl, c - (rr * dsl)
    return False, None, 0.0, 0.0


# --- ÁRBITRO HEURÍSTICO IA ---
CONFIG_IA = {{
    "asimetria_rr_minima": 2.0,
    "rvol_minimo": 0.70,
    "max_mecha_contra_pct": 32.0,
    "max_distancia_ema50_atrs": 2.8,
}}


def arbitro_ia(fila, lado, entry, sl, tp):
    """
    Evalúa la calidad microestructural de la señal generada por Balam en 4H.
    Devuelve: (autorizado: bool, multiplicador_riesgo: float, motivo: str)
    """
    p_ref = float(fila.get("close", entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr_teorico = recompensa / (riesgo + 1e-9)

    # 1. Veto por Asimetría Matemática Insuficiente (Regla 3: R:R >= 1:2.0)
    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({{rr_teorico:.2f}} < 1:{{CONFIG_IA['asimetria_rr_minima']:.1f}})"

    # 2. Veto por Falta de Participación Institucional (RVOL)
    rvol = float(fila.get("rvol", 1.0))
    if rvol < CONFIG_IA["rvol_minimo"]:
        return False, 0.0, f"VETO Secado de Volumen ({{rvol:.2f}}x < {{CONFIG_IA['rvol_minimo']:.2f}}x)"

    # 3. Veto por Mecha de Absorción / Trampa de Liquidez en Contra
    m_sup = float(fila.get("mecha_superior_pct", 0.0))
    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    lim_mecha = CONFIG_IA["max_mecha_contra_pct"]
    if lado == "LONG" and m_sup > lim_mecha:
        return False, 0.0, f"VETO Absorción Oferta Superior ({{m_sup:.1f}}% > {{lim_mecha:.1f}}%)"
    if lado == "SHORT" and m_inf > lim_mecha:
        return False, 0.0, f"VETO Absorción Demanda Inferior ({{m_inf:.1f}}% > {{lim_mecha:.1f}}%)"

    # 4. Veto por Sobreextensión respecto al Valor Dinámico EMA 50
    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > CONFIG_IA["max_distancia_ema50_atrs"]:
        return False, 0.0, f"VETO Sobreextensión EMA50 ({{dist_ema:.2f}} ATR > {{CONFIG_IA['max_distancia_ema50_atrs']:.1f}})"

    # Sizing dinámico compensado con riesgo objetivo al 0.60% por operación:
    sl_dist_pct = abs(float(entry) - float(sl)) / max(float(entry), 1e-9) * 100.0
    target_risk_pct = 0.60
    sz = round(min(0.22, max(0.12, target_risk_pct / max(sl_dist_pct, 0.20))), 4)
    return True, sz, f"AUTORIZADO por Antigravity CIO (Squeeze Óptimo Grid Search | Sizing sz={{sz:.2f}})"
'''


def ejecutar_barrido_walk_forward_swing(
    ticker: str,
    df_raw: pd.DataFrame,
    evaluador: EvaluadorCuantitativo,
    guardar_ganador: bool = False,
    familia_forzada: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Barrido paramétrico Walk-Forward estricto para series 1H / 4H / 1D:
    1) Selecciona y ordena EXCLUSIVAMENTE en In-Sample (0-70%), exigiendo consistencia IS_H1 e IS_H2.
    2) Desbloquea el 30% Out-of-Sample ciego únicamente sobre el Top 5 seleccionado en IS.
    """
    df = precalcular_estructural_swing(df_raw)
    total = len(df)
    corte_is = int(total * 0.70)
    mid_is = corte_is // 2
    es_diario = "1d" in ticker.lower()
    min_trades_is = 18 if es_diario else 30
    min_trades_full = 25 if es_diario else 42

    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values

    candidatos_grid: List[Dict[str, Any]] = []
    # Familia A: BB Squeeze + Bear EMA50 Breakdown
    if familia_forzada in (None, "BB_SQUEEZE_DUAL"):
        for em_m, dn_n, bk_sh, sq_m, sl_m, rr, rv in itertools.product(
            [100, 200],
            [20, 30],
            [8, 10],
            [1.20, 1.25],
            [1.4, 1.7],
            [2.3, 2.6],
            [1.10, 1.15],
        ):
            candidatos_grid.append({
                "familia": "BB_SQUEEZE_DUAL",
                "ema_macro": em_m,
                "donchian_n": dn_n,
                "bos_short": bk_sh,
                "squeeze_mult": sq_m,
                "sl_mult": sl_m,
                "rr_target": rr,
                "rvol_min": rv,
                "max_dist_atr": 2.8,
                "descripcion": f"BB_Squeeze_Dual(EMA{em_m}, D{dn_n}/BOS{bk_sh}, SQ<={sq_m}x, SL={sl_m}x, RR={rr}, RVOL>={rv})",
            })

    # Familia B: Donchian Squeeze Estructural con Pendiente Macro
    if familia_forzada in (None, "DONCHIAN_SQUEEZE"):
        for em_m, dn_n, sq_m, sl_m, rr, rv in itertools.product(
            [100, 200],
            [20, 30],
            [1.15, 1.25],
            [1.4, 1.6],
            [2.3, 2.4, 2.6],
            [1.15, 1.20],
        ):
            candidatos_grid.append({
                "familia": "DONCHIAN_SQUEEZE",
                "ema_macro": em_m,
                "donchian_n": dn_n,
                "bos_short": 8,
                "cap_atr": 4.4 if es_diario else 6.0,
                "squeeze_mult": sq_m,
                "sl_mult": sl_m,
                "rr_target": rr,
                "rvol_min": rv,
                "max_dist_atr": 3.2,
                "descripcion": f"Donchian_Breakout(EMA{em_m}, D{dn_n}, SQ<={sq_m}x, SL={sl_m}x, RR={rr}, RVOL>={rv})",
            })

    total_combos = len(candidatos_grid)
    con_muestra_is = 0
    aprobados_is = []

    # FASE 1: CALIBRACIÓN ESTRICTAMENTE CIEGA EN IN-SAMPLE (0% -> 70%)
    for p in candidatos_grid:
        sig, sl_a, tp_a = _generar_senales_estructurales(df, p)
        t_is = _simular_vector_rango(o, h, l, c, sig, sl_a, tp_a, 210, corte_is, 84)
        if len(t_is) < min_trades_is:
            continue
        con_muestra_is += 1

        df_is = pd.DataFrame(t_is)
        m_is = evaluador.calcular_metricas(df_is, col_pnl_bruto="pnl_pct")
        if m_is["pf_neto"] < 1.45 or m_is["rr_promedio_neto"] < 2.0 or m_is["max_drawdown_pct"] > 19.5:
            continue

        df_h1 = df_is[df_is["bar"] < mid_is]
        df_h2 = df_is[df_is["bar"] >= mid_is]
        m_h1 = evaluador.calcular_metricas(df_h1, col_pnl_bruto="pnl_pct")
        m_h2 = evaluador.calcular_metricas(df_h2, col_pnl_bruto="pnl_pct")

        if m_h1["pf_neto"] >= 1.15 and m_h2["pf_neto"] >= 1.15:
            score_is = min(m_h1["pf_neto"], m_h2["pf_neto"]) * m_is["pf_neto"]
            aprobados_is.append((score_is, p, sig, sl_a, tp_a, m_is))

    # Ordenar EXCLUSIVAMENTE por robustez In-Sample (CERO acceso a OOS)
    aprobados_is.sort(key=lambda x: x[0], reverse=True)

    # FASE 2: EXAMEN CIEGO OUT-OF-SAMPLE (70% -> 100%) SOLO EN TOP 5 DE IS
    top_evaluados = []
    for _, p, sig, sl_a, tp_a, m_is in aprobados_is[:5]:
        t_full = _simular_vector_rango(o, h, l, c, sig, sl_a, tp_a, 210, total - 1, 84)
        df_full = pd.DataFrame(t_full)
        df_oos = df_full[df_full["bar"] >= corte_is] if not df_full.empty else pd.DataFrame()
        m_full = evaluador.calcular_metricas(df_full, col_pnl_bruto="pnl_pct")
        m_oos = evaluador.calcular_metricas(df_oos, col_pnl_bruto="pnl_pct")
        top_evaluados.append({
            "parametros": p,
            "metricas": m_full,
            "metricas_is": m_is,
            "metricas_oos": m_oos,
        })

    califica_institucional = False
    motivo_no_guardado = ""
    mejor = top_evaluados[0] if top_evaluados else None

    if mejor:
        mf = mejor["metricas"]
        mo = mejor["metricas_oos"]
        if mf["trades_totales"] < min_trades_full:
            motivo_no_guardado = f"Muestra total insuficiente ({mf['trades_totales']} trades < {min_trades_full} requeridos en serie histórica)."
        elif mo["pf_neto"] < 1.10 or mo["retorno_neto_total_pct"] <= 0.0:
            motivo_no_guardado = f"Fallo en validación ciega Out-of-Sample (OOS PF={mo['pf_neto']}, Ret={mo['retorno_neto_total_pct']}%). Degradación fuera de muestra detectada."
        elif mf["pf_neto"] < 1.50:
            motivo_no_guardado = f"Profit Factor 3Y insuficiente ({mf['pf_neto']} < 1.50)."
        elif mf["rr_promedio_neto"] < 2.0:
            motivo_no_guardado = f"Asimetría R:R realizada insuficiente ({mf['rr_promedio_neto']} < 2.0)."
        elif mf["max_drawdown_pct"] > 20.0:
            motivo_no_guardado = f"Drawdown máximo excesivo ({mf['max_drawdown_pct']}% > 20.0%)."
        else:
            califica_institucional = True
    else:
        motivo_no_guardado = "Ninguna combinación superó los umbrales de consistencia dual en In-Sample (IS_H1 + IS_H2)."

    nombre_arch = "tendencia_optimizada_auto.py"
    cod_optimizado = None

    if mejor:
        cod_optimizado = _construir_codigo_certificado(
            ticker,
            mejor["parametros"],
            mejor["metricas"],
            mejor["metricas_is"],
            mejor["metricas_oos"],
        )
        # BLINDAJE ANTI-BASURA: Jamás escribir archivos automáticos sueltos en disco.
        # El resultado se entrega exclusivamente en memoria vía reporte_salida / JSON para la UI.

    reporte_salida = {
        "modo": "WALK_FORWARD_SWING_1H_4H_1D",
        "ticker": ticker,
        "total_evaluadas": total_combos,
        "con_trades_suficientes": con_muestra_is,
        "ganadoras_filtradas": len(aprobados_is),
        "califica_institucional": califica_institucional,
        "archivo_guardado": None,
        "codigo_optimizado": cod_optimizado,
        "motivo_no_guardado": motivo_no_guardado,
        "top_5": top_evaluados,
    }
    GANADORAS_FILE.write_text(json.dumps(reporte_salida, indent=2, ensure_ascii=False), encoding="utf-8")
    return reporte_salida


def precalcular_indicadores_scalping(df: pd.DataFrame, window_session: int = 78) -> pd.DataFrame:
    """Precalcula VWAP rodante para validación intradía TradFi con Walk-Forward."""
    df_calc = df.copy()
    typical_p = (df_calc["high"] + df_calc["low"] + df_calc["close"]) / 3.0
    vol = df_calc["volume"].replace(0, 1.0) if "volume" in df_calc.columns else pd.Series(1.0, index=df_calc.index)
    cum_pv = (typical_p * vol).rolling(window_session, min_periods=20).sum()
    cum_v = vol.rolling(window_session, min_periods=20).sum()
    df_calc["vwap"] = (cum_pv / cum_v).bfill()
    df_calc["rolling_std"] = df_calc["close"].rolling(window_session, min_periods=20).std().bfill()
    return df_calc


def ejecutar_barrido(
    ticker: str = "binance_ETH_USDT_4h.parquet",
    grid: Optional[Dict[str, List[Any]]] = None,
    min_trades: int = 30,
    min_pf: float = 1.45,
    max_dd: float = 20.0,
    min_trades_institucional: int = 45,
    min_pf_institucional: float = 1.50,
    max_dd_institucional: float = 20.0,
    guardar_ganador: bool = False,
    familia_forzada: Optional[str] = None,
) -> Dict[str, Any]:
    """Punto de entrada unificado del Optimizador Autónomo Local."""
    df_raw = cargar_dataset(ticker)
    comision, slippage = _obtener_friccion(ticker)
    evaluador = EvaluadorCuantitativo(comision_pct=comision, slippage_pct=slippage)

    t_low = ticker.lower()
    es_intradia_corto = any(tf in t_low for tf in ["_5m", "_15m", "_1m", "_3m"])

    if not es_intradia_corto and grid is None:
        return ejecutar_barrido_walk_forward_swing(
            ticker=ticker,
            df_raw=df_raw,
            evaluador=evaluador,
            guardar_ganador=guardar_ganador,
            familia_forzada=familia_forzada,
        )

    # Modo intradía corto (ej. TradFi SPY 5M) igualmente blindado con Walk-Forward 70/30 y N >= 45
    df_prep = precalcular_indicadores_scalping(df_raw)
    corte_is = int(len(df_prep) * 0.70)
    if not grid:
        grid = {
            "sigma": [1.8, 2.0, 2.2],
            "rvol": [1.15, 1.30, 1.50],
            "wick_min": [20.0, 25.0, 30.0],
            "sl_mult": [1.2, 1.5, 1.8],
            "rr_target": [2.2],
        }

    keys = list(grid.keys())
    combinaciones = [dict(zip(keys, prod)) for prod in itertools.product(*grid.values())]
    o, h, l, c = df_prep["open"].values, df_prep["high"].values, df_prep["low"].values, df_prep["close"].values
    v, sd, atr = df_prep["vwap"].values, df_prep["rolling_std"].values, df_prep["atr"].values
    rv, ws, wi = df_prep["rvol"].values, df_prep["mecha_sup_pct"].values, df_prep["mecha_inf_pct"].values

    cand_is = []
    con_muestra = 0
    for p in combinaciones:
        up_b = v + float(p["sigma"]) * sd
        lo_b = v - float(p["sigma"]) * sd
        dsl = np.maximum(float(p["sl_mult"]) * atr, c * 0.003)
        lg = (l <= lo_b) & (c > lo_b) & (wi >= float(p["wick_min"])) & (rv >= float(p["rvol"])) & ((v - c) >= 1.2 * dsl)
        sh = (~lg) & (h >= up_b) & (c < up_b) & (ws >= float(p["wick_min"])) & (rv >= float(p["rvol"])) & ((c - v) >= 1.2 * dsl)
        sig = np.where(lg, 1, np.where(sh, -1, 0))
        sl_a = np.where(sig == 1, c - dsl, c + dsl)
        tp_a = np.where(sig == 1, c + float(p["rr_target"]) * dsl, c - float(p["rr_target"]) * dsl)

        t_is = _simular_vector_rango(o, h, l, c, sig, sl_a, tp_a, 50, corte_is, 48)
        if len(t_is) >= min_trades:
            con_muestra += 1
            m_is = evaluador.calcular_metricas(pd.DataFrame(t_is), col_pnl_bruto="pnl_pct")
            if m_is["pf_neto"] >= min_pf and m_is["max_drawdown_pct"] <= max_dd:
                cand_is.append((m_is["pf_neto"], p, sig, sl_a, tp_a, m_is))

    cand_is.sort(key=lambda x: x[0], reverse=True)
    top_out = []
    for _, p, sig, sl_a, tp_a, m_is in cand_is[:5]:
        t_full = _simular_vector_rango(o, h, l, c, sig, sl_a, tp_a, 50, len(c) - 1, 48)
        df_f = pd.DataFrame(t_full)
        df_o = df_f[df_f["bar"] >= corte_is] if not df_f.empty else pd.DataFrame()
        top_out.append({
            "parametros": p,
            "metricas": evaluador.calcular_metricas(df_f, col_pnl_bruto="pnl_pct"),
            "metricas_is": m_is,
            "metricas_oos": evaluador.calcular_metricas(df_o, col_pnl_bruto="pnl_pct"),
        })

    mejor = top_out[0] if top_out else None
    califica = False
    motivo = "Ninguna combinación intradía superó Walk-Forward IS + OOS con muestra institucional >= 45."
    if mejor:
        mf, mo = mejor["metricas"], mejor["metricas_oos"]
        if mf["trades_totales"] >= min_trades_institucional and mf["pf_neto"] >= min_pf_institucional and mf["max_drawdown_pct"] <= max_dd_institucional and mo["pf_neto"] >= 1.15 and mo["retorno_neto_total_pct"] > 0:
            califica = True
            motivo = ""
        else:
            motivo = f"Rechazada por filtro Walk-Forward/Muestra (N={mf['trades_totales']}, PF={mf['pf_neto']}, OOS PF={mo['pf_neto']})."

    rep = {
        "modo": "WALK_FORWARD_INTRADIA",
        "ticker": ticker,
        "total_evaluadas": len(combinaciones),
        "con_trades_suficientes": con_muestra,
        "ganadoras_filtradas": len(cand_is),
        "califica_institucional": califica,
        "archivo_guardado": None,
        "motivo_no_guardado": motivo,
        "top_5": top_out,
    }
    GANADORAS_FILE.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    return rep


if __name__ == "__main__":
    ticker_objetivo = sys.argv[1] if len(sys.argv) > 1 else "binance_ETH_USDT_4h.parquet"
    print(f"\n>>> Iniciando Grid Search Walk-Forward (70% IS / 30% OOS Ciego) sobre: {ticker_objetivo}")
    res = ejecutar_barrido(ticker_objetivo)
    print(f"Combinaciones Evaluadas : {res['total_evaluadas']}")
    print(f"Con Muestra IS Válida   : {res['con_trades_suficientes']}")
    print(f"Aprobadas IS Dual       : {res['ganadoras_filtradas']}")
    print(f"Certificada Walk-Forward: {res['califica_institucional']}")
    if not res["califica_institucional"]:
        print(f"Motivo Retención        : {res['motivo_no_guardado']}")
    for idx, item in enumerate(res.get("top_5", []), 1):
        m = item["metricas"]
        mo = item.get("metricas_oos", {})
        desc = item["parametros"].get("descripcion", str(item["parametros"]))
        print(f"  #{idx} | 3Y: N={m['trades_totales']} PF={m['pf_neto']} WR={m['win_rate_neto']}% RR={m['rr_promedio_neto']} DD={m['max_drawdown_pct']}% | OOS: N={mo.get('trades_totales',0)} PF={mo.get('pf_neto',0)} Ret={mo.get('retorno_neto_total_pct',0)}% | {desc}")
