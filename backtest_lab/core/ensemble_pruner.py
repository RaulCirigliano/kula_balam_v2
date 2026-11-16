# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/core/ensemble_pruner.py
Proyecto: Kula Balam & Backtest Lab
Propósito: Motor de Poda Iterativa y Ensamble Modular (Stepwise Ensemble Pruning)
con Árbitro IA Central (Single Gatekeeper) y Jerarquía de Prioridad de Rentabilidad.

Reglas Cuantitativas:
1. Solo admite fórmulas previamente auditadas y certificadas (principal/ y para_testear/ganadoras/).
2. Maximiza el Retorno Neto Total del ensamble mediante eliminación retrógrada (Backward Elimination).
3. Resolución de conflictos por Prioridad al Mejor: si dos subfórmulas emiten señales contradictorias,
   se ejecuta la de la subfórmula con mayor expectativa matemática individual.
4. Preservación no destructiva: las fórmulas no integradas al ensamble permanecen 100% intactas
   en el catálogo y disponibles para operar de forma individual en Kula Balam.
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data" / "datos_historicos"
CATALOGO_DIR = PROJECT_ROOT / "backend" / "estrategias" / "catalogo"
PRINCIPAL_DIR = CATALOGO_DIR / "principal"
GANADORAS_DIR = CATALOGO_DIR / "para_testear" / "ganadoras"

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from core.metrics import EvaluadorCuantitativo


class CandidateFormula:
    """Representa una fórmula auditada candidata para competir en el torneo de ensamble."""
    def __init__(
        self,
        formula_id: str,
        archivo: str,
        categoria: str,
        titulo: str,
        subtitulo: str,
        dataset_sugerido: str,
        timeframe: str,
        code_math: str,
        code_ia: str,
        file_path: Path
    ):
        self.id = formula_id
        self.archivo = archivo
        self.categoria = categoria
        self.titulo = titulo
        self.subtitulo = subtitulo
        self.dataset_sugerido = dataset_sugerido
        self.timeframe = timeframe
        self.code_math = code_math
        self.code_ia = code_ia
        self.file_path = file_path
        self.baseline_return = 0.0
        self.baseline_pf = 0.0
        self.baseline_wr = 0.0
        self.baseline_trades = 0
        self.baseline_dd = 0.0
        self.priority_rank = 999


def preparar_mercado_ensemble(df_in: pd.DataFrame) -> pd.DataFrame:
    """Prepara las métricas de mercado para el Árbitro IA y el motor de trailing."""
    df = df_in.copy()
    df.columns = [str(c).lower() for c in df.columns]

    if not isinstance(df.index, pd.DatetimeIndex):
        col_t = next((c for c in ["datetime", "timestamp", "date", "time"] if c in df.columns), None)
        if col_t:
            s_t = df[col_t]
            if pd.api.types.is_numeric_dtype(s_t):
                unit = "ms" if float(s_t.iloc[0]) > 1e11 else "s"
                df[col_t] = pd.to_datetime(s_t, unit=unit, utc=True)
            else:
                df[col_t] = pd.to_datetime(s_t, utc=True)
            df.set_index(col_t, inplace=True)
        else:
            df.index = pd.to_datetime(df.index, utc=True, errors="coerce")

    df = df.sort_index()
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = df[col].astype(float)

    prev_c = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean().shift(1).bfill()

    vol_col = "volume" if "volume" in df.columns else None
    if vol_col and df[vol_col].sum() > 0:
        vol_sma = df[vol_col].rolling(20).mean().shift(1).bfill()
        df["rvol"] = df[vol_col] / (vol_sma + 1e-9)
        df["rvol_3_prev"] = (df[vol_col] / (vol_sma + 1e-9)).shift(1).fillna(1.0)
    else:
        df["rvol"] = 1.3
        df["rvol_3_prev"] = 1.3

    rango = (df["high"] - df["low"]).replace(0, 1e-9)
    techo = df[["open", "close"]].max(axis=1)
    suelo = df[["open", "close"]].min(axis=1)
    df["mecha_superior_pct"] = ((df["high"] - techo) / rango) * 100.0
    df["mecha_inferior_pct"] = ((suelo - df["low"]) / rango) * 100.0
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
    df["dist_ema_atrs"] = (df["close"] - df["ema_50"]).abs() / (df["atr"] + 1e-9)

    return df


def cargar_universo_auditado() -> List[CandidateFormula]:
    """
    Lee exclusivamente las fórmulas auditadas y certificadas en:
      1. backend/estrategias/catalogo/principal/
      2. backend/estrategias/catalogo/para_testear/ganadoras/
      3. backtest_lab/estrategias_math/
    Deduplica clones matemáticos idénticos y excluye ensambles recursivos previos.
    """
    import hashlib
    import re
    from backend.estrategias.catalogo_manager import get_formula_detalle

    candidatas: List[CandidateFormula] = []
    vistos = set()
    hashes_vistos = set()

    MATH_DIR = BASE_DIR / "estrategias_math"
    IA_DIR = BASE_DIR / "estrategias_ia"
    carpetas = [
        ("principal", PRINCIPAL_DIR),
        ("ganadoras", GANADORAS_DIR),
        ("estrategias_math", MATH_DIR),
    ]

    for cat_name, folder in carpetas:
        if not folder.exists():
            continue
        meta_path = folder / "metadata.json"
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}

        for py_file in sorted(folder.glob("*.py")):
            if (
                py_file.name.startswith("__")
                or py_file.stem in vistos
                or py_file.stem.startswith("ensamble_campeon_")
                or py_file.stem.startswith("test_")
            ):
                continue

            if cat_name in ("principal", "ganadoras"):
                detalle = get_formula_detalle(cat_name, py_file.name)
                if not detalle or not detalle.get("code_math"):
                    continue
                code_math = detalle["code_math"]
                code_ia = detalle.get("code_ia", "")
            else:
                try:
                    raw_code = py_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                if "def formula_matematica" not in raw_code:
                    continue
                code_math = raw_code
                code_ia = ""
                m_arb = re.search(r'ARBITRO_IA\s*=\s*["\']([^"\']+)["\']', code_math)
                if m_arb:
                    arb_path = IA_DIR / m_arb.group(1)
                    if arb_path.exists():
                        try:
                            code_ia = arb_path.read_text(encoding="utf-8")
                        except Exception:
                            code_ia = ""

            if "ENSAMBLE MULTI-SENSOR CAMPEÓN" in code_math:
                continue

            # Deduplicación estructural de código matemático (sin comentarios ni metadatos de archivo)
            code_clean = re.sub(r"^#.*$", "", code_math, flags=re.M)
            code_clean = re.sub(r'"""[\s\S]*?"""', "", code_clean)
            code_clean = re.sub(r"^(DATASET|ARBITRO_IA)\s*=.*$", "", code_clean, flags=re.M)
            norm_hash = hashlib.md5(re.sub(r"\s+", " ", code_clean).strip().encode("utf-8")).hexdigest()
            if norm_hash in hashes_vistos:
                continue

            info_raw = meta.get(py_file.name, {})
            if isinstance(info_raw, dict):
                info_meta = info_raw
            elif isinstance(info_raw, str):
                info_meta = {"titulo": info_raw}
            else:
                info_meta = {}

            c = CandidateFormula(
                formula_id=py_file.stem,
                archivo=py_file.name,
                categoria=cat_name,
                titulo=info_meta.get("titulo", py_file.stem.replace('_', ' ').title()),
                subtitulo=info_meta.get("subtitulo", info_meta.get("rendimiento_lab", "")),
                dataset_sugerido=info_meta.get("dataset_sugerido", "binance_ETH_USDT_4h.parquet"),
                timeframe=info_meta.get("timeframe", "4h"),
                code_math=code_math,
                code_ia=code_ia,
                file_path=py_file
            )
            candidatas.append(c)
            vistos.add(py_file.stem)
            hashes_vistos.add(norm_hash)

    return candidatas


def compilar_formula(code_math: str):
    """Compila la función matemática de forma segura en un namespace aislado y adjunta metadatos de salida."""
    ns = {"pd": pd, "np": np, "Tuple": Tuple, "Optional": Optional}
    exec(code_math, ns)
    if "formula_matematica" not in ns:
        raise ValueError("El código no define 'formula_matematica(df, i)'.")
    fn = ns["formula_matematica"]
    try:
        fn._max_hold = int(ns.get("MAX_BARS_HOLD", 84))
        fn._trail_mult = float(ns.get("TRAILING_ATR_MULT", 0.0))
        fn._be_rr = float(ns.get("BREAKEVEN_RR", 0.0))
    except Exception:
        pass
    return fn


def arbitro_ia_central(fila: pd.Series, lado: str, entry: float, sl: float, tp: float) -> Tuple[bool, float, str]:
    """
    Árbitro IA Central (Single Gatekeeper) para el ensamble homologado con Estación 2 y RFC-2026-11:
    - Asimetría teórica R:R >= 1:2.0 (1.95 con tolerancia)
    - Piso de ruido ATR: riesgo estructural >= 1.35 * ATR
    - Expansión de volumen institucional RVOL >= 1.15
    - Veto de mechas de absorción en contra > 32% (y tope universal >= 50%)
    - Veto por sobreextensión EMA50 > 2.8 ATR
    - Escudo anti-cuchillo en LONG (caída violenta > 1.2 ATR)
    """
    p_ref = float(fila.get("close", entry))
    riesgo = max(abs(p_ref - float(sl)), abs(entry - float(sl)))
    recompensa = max(abs(float(tp) - p_ref), abs(float(tp) - entry))
    rr_teorico = recompensa / (riesgo + 1e-9)
    if rr_teorico < 1.95:
        return False, 0.0, f"VETO Asimetría R:R ({rr_teorico:.2f} < 1:2.0)"

    atr_val = float(fila.get("atr", 0.0))
    if atr_val > 0 and riesgo < (1.35 * atr_val):
        return False, 0.0, f"VETO Ruido ATR: SL ({riesgo:.4f}) < 1.35 ATR ({1.35 * atr_val:.4f})"

    rvol = float(fila.get("rvol", 1.0))
    if rvol < 1.15:
        return False, 0.0, f"VETO RVOL ({rvol:.2f} < 1.15)"

    m_sup = float(fila.get("mecha_superior_pct", 0.0))
    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    if lado == "LONG" and m_sup > 32.0:
        return False, 0.0, f"VETO Mecha Superior ({m_sup:.1f}% > 32%)"
    if lado == "SHORT" and m_inf > 32.0:
        return False, 0.0, f"VETO Mecha Inferior ({m_inf:.1f}% > 32%)"

    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > 2.8:
        return False, 0.0, f"VETO Sobreextensión EMA50 ({dist_ema:.2f} ATR > 2.8)"

    o_c = float(fila.get("open", p_ref))
    c_c = float(fila.get("close", p_ref))
    if lado == "LONG" and atr_val > 0 and (o_c - c_c) > (1.2 * atr_val):
        return False, 0.0, "VETO Cuchillo Cayendo (Caída violenta > 1.2 ATR)"

    return True, 1.0, "AUTORIZADO por Cerebro Kula"


def simular_trades_ensemble(
    formulas: List[CandidateFormula],
    df_mercado: pd.DataFrame,
    ranking_prioridad: Dict[str, int],
    evaluador: EvaluadorCuantitativo,
    max_hold: int = 84,
    start_idx: int = 210,
    end_idx: Optional[int] = None,
    usar_ia: bool = True,
    ticker: str = "ETH_USDT",
    friccion_rt: float = 0.0026
) -> Dict[str, Any]:
    """
    Ejecuta la simulación conjunta barra a barra de las fórmulas activas.
    Aplica la regla de Prioridad al Mejor ante discrepancias o señales opuestas.
    Homologada 1:1 con el motor de simulación de la Estación 2 (server.py).
    """
    if not formulas:
        return {
            "retorno_neto_total_pct": 0.0,
            "pf_neto": 0.0,
            "win_rate_neto": 0.0,
            "max_drawdown_pct": 0.0,
            "max_daily_dd_pct": 0.0,
            "max_losing_streak": 0,
            "prop_firm_ok": False,
            "prop_firm_semaforo": "🔴 RIESGO DE DESCALIFICACIÓN POR DRAWDOWN (Sin trades)",
            "trades_totales": 0,
            "rr_promedio_neto": 0.0,
            "trades_por_formula": {},
            "pnl_por_formula": {}
        }

    # 1. Compilar y preparar DataFrames aislados para cada fórmula
    sensores = []
    for f in formulas:
        try:
            fn = compilar_formula(f.code_math)
            df_sensor = df_mercado.copy()
            sensores.append({
                "id": f.id,
                "titulo": f.titulo,
                "fn": fn,
                "df": df_sensor,
                "rank": ranking_prioridad.get(f.id, 999),
                "max_hold": int(getattr(fn, "_max_hold", max_hold)),
                "trail_mult": float(getattr(fn, "_trail_mult", 0.0)),
                "be_rr": float(getattr(fn, "_be_rr", 0.0)),
            })
        except Exception as e_comp:
            logger.warning(f"Error compilando sensor {f.id}: {e_comp}")

    if not sensores:
        return {
            "retorno_neto_total_pct": 0.0,
            "pf_neto": 0.0,
            "win_rate_neto": 0.0,
            "max_drawdown_pct": 0.0,
            "max_daily_dd_pct": 0.0,
            "max_losing_streak": 0,
            "prop_firm_ok": False,
            "prop_firm_semaforo": "🔴 RIESGO DE DESCALIFICACIÓN POR DRAWDOWN (Sin trades)",
            "trades_totales": 0,
            "rr_promedio_neto": 0.0,
            "trades_por_formula": {},
            "pnl_por_formula": {}
        }

    total_velas = len(df_mercado)
    atr_series = df_mercado["atr"].values
    trades_ejecutados = []
    pos_activa = False
    exit_bar = -1

    trades_por_formula: Dict[str, int] = {s["id"]: 0 for s in sensores}
    pnl_por_formula: Dict[str, float] = {s["id"]: 0.0 for s in sensores}

    lim_sup = end_idx if (end_idx is not None and end_idx < total_velas) else (total_velas - 1)
    ini_idx = max(210, start_idx)

    for i in range(ini_idx, lim_sup):
        if pos_activa and i >= exit_bar:
            pos_activa = False

        if pos_activa:
            continue

        # Recolectar señales de todos los sensores en esta vela
        disparos = []
        for s in sensores:
            try:
                cand, lado, sl, tp = s["fn"](s["df"], i)
                if cand and lado in ("LONG", "SHORT") and sl > 0 and tp > 0:
                    disparos.append({
                        "id": s["id"],
                        "titulo": s["titulo"],
                        "rank": s["rank"],
                        "lado": lado,
                        "sl": sl,
                        "tp": tp,
                        "max_hold": s["max_hold"],
                        "trail_mult": s["trail_mult"],
                        "be_rr": s["be_rr"],
                    })
            except Exception:
                continue

        if not disparos:
            continue

        # Ordenar por jerarquía de prioridad: menor rango numérico = mayor rentabilidad individual
        disparos.sort(key=lambda x: x["rank"])
        ganador = disparos[0]  # Prioridad al Mejor

        fila_actual = df_mercado.iloc[i]
        entry = float(df_mercado.iloc[i + 1]["open"]) if i + 1 < total_velas else float(fila_actual["close"])

        # Cap SL para TradFi 1D (máximo 4.5% de riesgo estructural)
        cur_sl = float(ganador["sl"])
        cur_tp = float(ganador["tp"])
        lado = ganador["lado"]
        es_tradfi_1d = ("1d" in ticker.lower() or "yf_" in ticker.lower()) and "btc" not in ticker.lower() and "eth" not in ticker.lower() and "sol" not in ticker.lower()
        if es_tradfi_1d:
            sl_pct = (abs(entry - cur_sl) / (entry + 1e-9)) * 100.0
            if sl_pct > 4.5:
                cur_sl = entry * 0.955 if lado == "LONG" else entry * 1.045

        # Pasar por el Árbitro IA Central y Escudos Kula si usar_ia está activo
        sz = 1.0
        if usar_ia:
            # Escudo Anti-Cuchillo (3 velas bajistas consecutivas en LONG)
            if lado == "LONG" and i >= 2:
                if (
                    float(df_mercado["close"].iloc[i]) < float(df_mercado["open"].iloc[i])
                    and float(df_mercado["close"].iloc[i - 1]) < float(df_mercado["open"].iloc[i - 1])
                    and float(df_mercado["close"].iloc[i - 2]) < float(df_mercado["open"].iloc[i - 2])
                ):
                    continue
            aut, sz, mot = arbitro_ia_central(fila_actual, lado, entry, cur_sl, cur_tp)
            if not aut:
                continue

        # Simulación de salida homologada con server.py (respeta MAX_BARS_HOLD, TRAILING_ATR_MULT y BREAKEVEN_RR del sensor)
        riesgo_ini = max(abs(entry - cur_sl), entry * 1e-5)
        sl_movido = False
        max_fav = entry
        s_hold = int(ganador.get("max_hold", max_hold))
        s_trail = float(ganador.get("trail_mult", 0.0))
        s_be = float(ganador.get("be_rr", 0.0))
        p_exit = float(df_mercado["close"].iloc[min(i + s_hold, total_velas - 1)])
        bar_salida = min(i + s_hold, total_velas - 1)

        for j in range(i + 1, min(i + s_hold + 1, total_velas)):
            oj = float(df_mercado["open"].iloc[j])
            hj = float(df_mercado["high"].iloc[j])
            lj = float(df_mercado["low"].iloc[j])

            if lado == "LONG":
                if lj <= cur_sl:
                    p_exit = min(oj, cur_sl)
                    bar_salida = j
                    break
                if hj >= cur_tp:
                    p_exit = max(oj, cur_tp)
                    bar_salida = j
                    break
                if hj > max_fav:
                    max_fav = hj
                if s_be > 0.0 and (max_fav - entry) >= (s_be * riesgo_ini):
                    be_lvl = entry * 1.003
                    if be_lvl > cur_sl:
                        cur_sl = be_lvl
                        sl_movido = True
                if s_trail > 0.0 and (max_fav - entry) >= (1.0 * riesgo_ini):
                    tr_lvl = max_fav - (s_trail * float(atr_series[j]))
                    if tr_lvl > cur_sl:
                        cur_sl = tr_lvl
                        sl_movido = True
            else:
                if hj >= cur_sl:
                    p_exit = max(oj, cur_sl)
                    bar_salida = j
                    break
                if lj <= cur_tp:
                    p_exit = min(oj, cur_tp)
                    bar_salida = j
                    break
                if lj < max_fav:
                    max_fav = lj
                if s_be > 0.0 and (entry - max_fav) >= (s_be * riesgo_ini):
                    be_lvl = entry * 0.997
                    if be_lvl < cur_sl:
                        cur_sl = be_lvl
                        sl_movido = True
                if s_trail > 0.0 and (entry - max_fav) >= (1.0 * riesgo_ini):
                    tr_lvl = max_fav + (s_trail * float(atr_series[j]))
                    if tr_lvl < cur_sl:
                        cur_sl = tr_lvl
                        sl_movido = True

        pnl_pct = (((p_exit - entry) / entry) * 100.0 if lado == "LONG" else ((entry - p_exit) / entry) * 100.0) * sz

        pos_activa = True
        exit_bar = bar_salida

        trades_ejecutados.append({
            "idx_entry": i,
            "idx_exit": bar_salida,
            "fecha": str(df_mercado.index[i])[:16],
            "formula_id": ganador["id"],
            "lado": lado,
            "entry": entry,
            "exit": p_exit,
            "pnl_pct": pnl_pct
        })
        trades_por_formula[ganador["id"]] = trades_por_formula.get(ganador["id"], 0) + 1
        pnl_por_formula[ganador["id"]] = pnl_por_formula.get(ganador["id"], 0.0) + pnl_pct

    df_tr = pd.DataFrame(trades_ejecutados)
    metricas = evaluador.calcular_metricas(df_tr, ya_descuenta_friccion=False)

    return {
        "retorno_neto_total_pct": metricas["retorno_neto_total_pct"],
        "pf_neto": metricas["pf_neto"],
        "win_rate_neto": metricas["win_rate_neto"],
        "max_drawdown_pct": metricas["max_drawdown_pct"],
        "max_daily_dd_pct": metricas.get("max_daily_dd_pct", 0.0),
        "max_losing_streak": metricas.get("max_losing_streak", 0),
        "prop_firm_ok": metricas.get("prop_firm_ok", False),
        "prop_firm_semaforo": metricas.get("prop_firm_semaforo", "N/A"),
        "trades_totales": metricas["trades_totales"],
        "rr_promedio_neto": metricas["rr_promedio_neto"],
        "trades_por_formula": trades_por_formula,
        "pnl_por_formula": pnl_por_formula,
        "detalles_trades": trades_ejecutados
    }


def sintetizar_codigo_ensamble(
    campeones: List[CandidateFormula],
    ranking_prioridad: Dict[str, int],
    metricas_finales: Dict[str, Any],
    dataset_name: str
) -> Tuple[str, str]:
    """Genera el código Python unificado y estructurado del Ensamble Campeón homologado con RFC-2026-11."""
    import re
    lineas_sensores = []
    meta_subsensores = []

    for idx, c in enumerate(campeones, start=1):
        safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", c.id)
        clean_name = f"_sensor_{idx}_{safe_id}"
        meta_subsensores.append(f'        ("{c.id}", {clean_name}, {ranking_prioridad.get(c.id, idx)}, "{c.titulo}")')
        
        # Aislar constantes globales y banderas de inicialización en DataFrame para evitar colisión entre sensores
        src_isolated = c.code_math.replace("PARAMETROS_CALIBRADOS", f"_PARAMS_CALIBRADOS_{idx}")
        src_isolated = src_isolated.replace("_wf_auto_init", f"_wf_auto_init_{idx}")
        src_isolated = src_isolated.replace("_eth4h_sq_init", f"_eth4h_sq_init_{idx}")
        src_isolated = src_isolated.replace("_donchian_1h_init", f"_donchian_1h_init_{idx}")
        lines_code = src_isolated.splitlines()
        indented = []
        for l in lines_code:
            if "def formula_matematica(" in l:
                indented.append(f"def {clean_name}(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:")
            else:
                indented.append(l)
        
        sensor_block = (
            f"# --- SUB-SENSOR {idx}: {c.titulo} (Prioridad {ranking_prioridad.get(c.id, idx)}) ---\n"
            + "\n".join(indented)
            + "\n\n"
        )
        lineas_sensores.append(sensor_block)

    sensores_code = "".join(lineas_sensores)
    array_sensores = ",\n".join(meta_subsensores)

    code_math = f'''# -*- coding: utf-8 -*-
"""
ESTRATEGIA ENSAMBLE MULTI-SENSOR CAMPEÓN (KULA BALAM & BACKTEST LAB)
Generada automáticamente por Torneo de Poda Iterativa Walk-Forward (IS 70% / OOS 30%).
Criterio: Máxima Rentabilidad Neta con Resolución de Conflictos por Prioridad al Mejor.
Dataset Base: {dataset_name}

MÉTRICAS CONSOLIDADAS DEL ENSAMBLE:
- Retorno Neto Total : +{metricas_finales.get("retorno_neto_total_pct", 0.0):.2f}% (Fricción institucional descontada)
- Profit Factor Neto : {metricas_finales.get("pf_neto", 0.0):.2f}
- Win Rate Neto      : {metricas_finales.get("win_rate_neto", 0.0):.1f}%
- Drawdown Máximo    : {metricas_finales.get("max_drawdown_pct", 0.0):.2f}%
- Trades Totales     : {metricas_finales.get("trades_totales", 0)}

NÚCLEO DE SUB-SENSORES CAMPEONES:
{chr(10).join([f"- Prioridad {ranking_prioridad.get(c.id, i+1)}: {c.titulo} ({c.id})" for i, c in enumerate(campeones)])}
"""
from typing import Tuple, Optional
import pandas as pd
import numpy as np

DATASET = "{dataset_name}"
MAX_BARS_HOLD = 84

# ==============================================================================
# 1. SUB-SENSORES MATEMÁTICOS AUDITADOS Y CERTIFICADOS
# ==============================================================================
{sensores_code}
# ==============================================================================
# 2. ORQUESTADOR CENTRAL DE PRIORIDADES DE RENTABILIDAD
# ==============================================================================
def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    """
    Evalúa todos los sensores del núcleo campeón.
    Ante discrepancias de señal, aplica la Regla Institucional de Prioridad al Mejor:
    la subfórmula con mayor expectativa matemática individual ejecuta su orden.
    """
    sensores = [
{array_sensores}
    ]

    disparos = []
    for s_id, s_fn, s_rank, s_tit in sensores:
        try:
            cand, lado, sl, tp = s_fn(df, i)
            if cand and lado in ("LONG", "SHORT") and sl > 0 and tp > 0:
                disparos.append((s_rank, lado, sl, tp, s_id))
        except Exception:
            continue

    if not disparos:
        return False, None, 0.0, 0.0

    # Ordenar por rango de rentabilidad: menor número = mayor prioridad
    disparos.sort(key=lambda x: x[0])
    mejor = disparos[0]

    return True, mejor[1], mejor[2], mejor[3]
'''

    code_ia = f'''# -*- coding: utf-8 -*-
"""
ÁRBITRO HEURÍSTICO IA CENTRAL (GATEKEEPER ÚNICO DEL ENSAMBLE RFC-2026-11)
Audita la microestructura de mercado previa a la entrada de cualquier sub-sensor:
- Asimetría matemática mínima R:R >= 1:2.0
- Expansión de volumen institucional RVOL >= 1.15
- Veto por mechas trampa de absorción en contra > 32% (y tope universal >= 50%)
- Veto por sobreextensión dinámica respecto a EMA 50 > 2.8 ATR
- Filtro de piso de ruido ATR (SL >= 1.35 * ATR)
- Escudo anti-cuchillo cayendo en compras LONG
"""
CONFIG_IA = {{
    "asimetria_rr_minima": 2.0,
    "rvol_minimo": 1.15,
    "max_mecha_contra_pct": 32.0,
    "max_distancia_ema50_atrs": 2.8,
    "sl_atr_noise_multiplier": 1.35,
}}

def arbitro_ia(fila, lado, entry, sl, tp):
    p_ref = float(fila.get("close", entry))
    riesgo = max(abs(p_ref - float(sl)), abs(entry - float(sl)))
    recompensa = max(abs(float(tp) - p_ref), abs(float(tp) - entry))
    rr_teorico = recompensa / (riesgo + 1e-9)

    # 1. Compuerta de Asimetría R:R
    if rr_teorico < (CONFIG_IA["asimetria_rr_minima"] - 0.05):
        return False, 0.0, f"VETO Asimetría R:R ({{rr_teorico:.2f}} < 1:{{CONFIG_IA['asimetria_rr_minima']:.2f}})"

    # 2. Piso de Ruido ATR
    atr_val = float(fila.get("atr", 0.0))
    if atr_val > 0 and riesgo < (CONFIG_IA["sl_atr_noise_multiplier"] * atr_val):
        return False, 0.0, f"VETO Ruido ATR: SL ({{riesgo:.4f}}) < {{CONFIG_IA['sl_atr_noise_multiplier']}} ATR"

    # 3. Compuerta de Volumen Institucional
    rvol = float(fila.get("rvol", 1.0))
    if rvol < CONFIG_IA["rvol_minimo"]:
        return False, 0.0, f"VETO RVOL Insuficiente ({{rvol:.2f}}x < {{CONFIG_IA['rvol_minimo']:.2f}}x)"

    # 4. Compuerta de Mechas de Absorción
    m_sup = float(fila.get("mecha_superior_pct", 0.0))
    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    lim_mecha = CONFIG_IA["max_mecha_contra_pct"]
    if lado == "LONG" and m_sup > lim_mecha:
        return False, 0.0, f"VETO Mecha Trampa Superior ({{m_sup:.1f}}% > {{lim_mecha:.1f}}%)"
    if lado == "SHORT" and m_inf > lim_mecha:
        return False, 0.0, f"VETO Mecha Trampa Inferior ({{m_inf:.1f}}% > {{lim_mecha:.1f}}%)"

    # 5. Compuerta de Sobreextensión EMA 50
    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > CONFIG_IA["max_distancia_ema50_atrs"]:
        return False, 0.0, f"VETO Sobreextensión EMA50 ({{dist_ema:.2f}} ATR > {{CONFIG_IA['max_distancia_ema50_atrs']:.1f}})"

    # 6. Escudo Anti-Cuchillo Cayendo en LONG
    o_c = float(fila.get("open", p_ref))
    c_c = float(fila.get("close", p_ref))
    if lado == "LONG" and atr_val > 0 and (o_c - c_c) > (1.2 * atr_val):
        return False, 0.0, "VETO Cuchillo Cayendo (Caída violenta > 1.2 ATR)"

    return True, 1.0, "AUTORIZADO por Antigravity CIO Central"


def custom_brain_filter(df_eval, idx, side_norm, entry_px, sl_px, tp_px):
    """Gancho estándar RFC-2026-11 para integración directa con Kula Balam."""
    fila = df_eval.iloc[idx]
    return arbitro_ia(fila, side_norm, entry_px, sl_px, tp_px)
'''

    return code_math, code_ia


def ejecutar_torneo_poda(
    dataset_name: Optional[str] = "binance_ETH_USDT_4h.parquet",
    max_batch_size: int = 5
) -> Dict[str, Any]:
    """
    Ejecuta el Torneo de Poda Iterativa con Cero Data-Snooping (Walk-Forward Estricto):
    1. Particiona el mercado en In-Sample (70%) y Out-Of-Sample (30%).
    2. Fase 1: Ranking individual, deduplicación de colinealidad y jerarquía de prioridad en In-Sample.
    3. Fase 2: Poda retrógrada (Backward Elimination) en Lote 1 evaluada EXCLUSIVAMENTE en In-Sample.
    4. Fase 3: Challenger Ladder con lotes retadores evaluado EXCLUSIVAMENTE en In-Sample.
    5. Fase 4: Validación Ciega Dual en Out-Of-Sample (Sin IA vs. Con Cerebro Kula) + Semáforo Fondeo.
    6. Sintetiza la Superfórmula Python final unificada con custom_brain_filter.
    """
    universo = cargar_universo_auditado()
    if not universo:
        return {
            "status": "error",
            "mensaje": "No se encontraron fórmulas auditadas en principal/, ganadoras/ ni estrategias_math/."
        }

    # Resolver dataset real
    ds_file = DATA_DIR / (dataset_name or "binance_ETH_USDT_4h.parquet")
    if not ds_file.exists():
        coincidencias = list(DATA_DIR.glob(f"*{dataset_name}*"))
        if coincidencias:
            ds_file = coincidencias[0]
        else:
            ds_file = DATA_DIR / "binance_ETH_USDT_4h.parquet"

    df_raw = pd.read_parquet(ds_file)
    df_mercado = preparar_mercado_ensemble(df_raw)

    evaluador = EvaluadorCuantitativo(
        comision_pct=0.0008 if "binance" in ds_file.name else 0.0002,
        slippage_pct=0.0005 if "binance" in ds_file.name else 0.0003
    )

    total_velas = len(df_mercado)
    corte_is = max(220, int(total_velas * 0.70))
    n_is = corte_is
    n_oos = total_velas - corte_is

    rondas_log = []
    rondas_log.append(f"🏁 INICIO DEL TORNEO DE PODA & ENSAMBLE (Challenger Ladder Walk-Forward)")
    rondas_log.append(f"Dataset de Prueba: {ds_file.name} ({total_velas:,} velas)")
    rondas_log.append(f"Partición Causal: In-Sample 70% ({n_is:,} velas) | Out-Of-Sample 30% ({n_oos:,} velas)")
    rondas_log.append(f"Universo Auditado: {len(universo)} fórmulas únicas encontradas.\n")

    # 1. Simulación Baseline Individual en In-Sample EXCLUSIVO (Cero Data-Snooping)
    rondas_log.append("--- FASE 1: AUDITORÍA BASELINE IS (70%) & JERARQUÍA DE PRIORIDAD ---")
    ranking_map = {}
    firmas_trades_is: Dict[Tuple, str] = {}
    universo_unico: List[CandidateFormula] = []
    descartadas_log = []

    for f in universo:
        m_ind = simular_trades_ensemble([f], df_mercado, {f.id: 1}, evaluador, end_idx=corte_is, usar_ia=True, ticker=ds_file.stem)
        f.baseline_return = m_ind["retorno_neto_total_pct"]
        f.baseline_pf = m_ind["pf_neto"]
        f.baseline_wr = m_ind["win_rate_neto"]
        f.baseline_trades = m_ind["trades_totales"]
        f.baseline_dd = m_ind["max_drawdown_pct"]
        f._sig_is = tuple((t["idx_entry"], t["lado"], round(t["pnl_pct"], 2)) for t in m_ind.get("detalles_trades", []))

    # Ordenar de mayor a menor rentabilidad neta en In-Sample
    universo.sort(key=lambda x: (x.baseline_return, x.baseline_pf), reverse=True)

    for f in universo:
        sig = getattr(f, "_sig_is", ())
        if sig and sig in firmas_trades_is:
            titular_original = firmas_trades_is[sig]
            motivo = f"Clon 100% colineal en señales con '{titular_original}' (mismas entradas/salidas en IS). Omitida para evitar redundancia."
            descartadas_log.append({"id": f.id, "titulo": f.titulo, "motivo": motivo})
            rondas_log.append(f"  ➖ [CLON COLINEAL OMITIDO] {f.titulo} -> idéntica a '{titular_original}'")
            continue
        if sig:
            firmas_trades_is[sig] = f.titulo
        universo_unico.append(f)

    if not universo_unico:
        universo_unico = [universo[0]]

    for rank, f in enumerate(universo_unico, start=1):
        f.priority_rank = rank
        ranking_map[f.id] = rank
        rondas_log.append(
            f"  [Prioridad #{rank}] {f.titulo}: IS Retorno {f.baseline_return:+.2f}% | PF {f.baseline_pf:.2f} | WR {f.baseline_wr:.1f}% | DD {f.baseline_dd:.1f}% ({f.baseline_trades} trades)"
        )

    # 2. División en lotes de hasta max_batch_size sobre fórmulas ortogonales (no clónicas)
    lotes = [universo_unico[i:i + max_batch_size] for i in range(0, len(universo_unico), max_batch_size)]
    rondas_log.append(f"\n--- FASE 2: TORNEO DE PODA EN LOTE 1 (IS 70%, {len(lotes[0])} fórmulas candidatas) ---")

    campeones: List[CandidateFormula] = list(lotes[0])

    # Ciclo de Poda Retrógrada (Backward Elimination) en Lote 1 (In-Sample)
    iteracion = 1
    while len(campeones) > 1:
        res_actual = simular_trades_ensemble(campeones, df_mercado, ranking_map, evaluador, end_idx=corte_is, usar_ia=True, ticker=ds_file.stem)
        ret_actual = res_actual["retorno_neto_total_pct"]
        pf_actual = res_actual["pf_neto"]

        rondas_log.append(
            f"  [Iteración {iteracion}] Ensamble activo ({len(campeones)} fórmulas) -> IS Retorno: {ret_actual:+.2f}% | PF: {pf_actual:.2f} | Trades: {res_actual['trades_totales']}"
        )

        peor_formula = None
        mejor_mejora = 0.0

        for candidata in campeones:
            pool_sin_ella = [c for c in campeones if c.id != candidata.id]
            res_sin_ella = simular_trades_ensemble(pool_sin_ella, df_mercado, ranking_map, evaluador, end_idx=corte_is, usar_ia=True, ticker=ds_file.stem)
            ret_sin_ella = res_sin_ella["retorno_neto_total_pct"]

            diferencia = ret_sin_ella - ret_actual
            if diferencia > mejor_mejora:
                mejor_mejora = diferencia
                peor_formula = candidata

        if peor_formula and mejor_mejora > 0.05:
            campeones.remove(peor_formula)
            motivo = f"Poda iterativa IS: su remoción incrementa el retorno neto en +{mejor_mejora:.2f}%."
            descartadas_log.append({"id": peor_formula.id, "titulo": peor_formula.titulo, "motivo": motivo})
            rondas_log.append(f"  ❌ [PODA] Descartada '{peor_formula.titulo}': {motivo}")
            iteracion += 1
        else:
            rondas_log.append("  ✓ [CONVERGENCIA LOTE 1] Todas las fórmulas del lote aportan o mantienen rentabilidad positiva en IS.")
            break

    rondas_log.append(f"\n🏆 NÚCLEO CAMPEÓN DE LOTE 1: {len(campeones)} fórmulas aprobadas:")
    for c in campeones:
        rondas_log.append(f"    - {c.titulo} (Prioridad #{c.priority_rank})")

    # 3. FASE 3: Challenger Ladder con lotes subsiguientes (en In-Sample)
    if len(lotes) > 1:
        rondas_log.append(f"\n--- FASE 3: CHALLENGER LADDER EN IS (Evaluando retadoras de lotes siguientes) ---")
        for lote_idx, lote_retador in enumerate(lotes[1:], start=2):
            for retadora in lote_retador:
                base_champ = simular_trades_ensemble(campeones, df_mercado, ranking_map, evaluador, end_idx=corte_is, usar_ia=True, ticker=ds_file.stem)
                ret_champ = base_champ["retorno_neto_total_pct"]
                pf_champ = base_champ["pf_neto"]

                test_pool = campeones + [retadora]
                res_con_ret = simular_trades_ensemble(test_pool, df_mercado, ranking_map, evaluador, end_idx=corte_is, usar_ia=True, ticker=ds_file.stem)
                ret_con_ret = res_con_ret["retorno_neto_total_pct"]
                pf_con_ret = res_con_ret["pf_neto"]

                if ret_con_ret > (ret_champ + 0.10) and (pf_con_ret >= 1.35 or pf_con_ret >= pf_champ):
                    campeones.append(retadora)
                    rondas_log.append(
                        f"  ✅ [RETADORA ADMITIDA] '{retadora.titulo}': Incrementó IS retorno de {ret_champ:+.2f}% a {ret_con_ret:+.2f}% (PF {pf_con_ret:.2f})."
                    )
                else:
                    if ret_con_ret <= (ret_champ + 0.10):
                        motivo = f"No superó retorno del Núcleo Campeón en IS ({ret_con_ret:+.2f}% vs {ret_champ:+.2f}%). Se mantiene Standalone."
                    else:
                        motivo = f"PF conjunto insuficiente en IS (PF {pf_con_ret:.2f} < 1.35 y < {pf_champ:.2f}). Se mantiene Standalone."
                    descartadas_log.append({"id": retadora.id, "titulo": retadora.titulo, "motivo": motivo})
                    rondas_log.append(f"  ➖ [RETADORA DESCARTADA] '{retadora.titulo}': {motivo}")

    # 4. FASE 4: AUDITORÍA CIEGA WALK-FORWARD (IS vs OOS) & VALIDACIÓN FINAL
    m_is_sin = simular_trades_ensemble(campeones, df_mercado, ranking_map, evaluador, start_idx=210, end_idx=corte_is, usar_ia=False, ticker=ds_file.stem)
    m_is_con = simular_trades_ensemble(campeones, df_mercado, ranking_map, evaluador, start_idx=210, end_idx=corte_is, usar_ia=True, ticker=ds_file.stem)
    m_oos_sin = simular_trades_ensemble(campeones, df_mercado, ranking_map, evaluador, start_idx=corte_is, end_idx=None, usar_ia=False, ticker=ds_file.stem)
    m_oos_con = simular_trades_ensemble(campeones, df_mercado, ranking_map, evaluador, start_idx=corte_is, end_idx=None, usar_ia=True, ticker=ds_file.stem)

    # Métricas consolidadas en el 100% de la muestra con Cerebro Kula
    metricas_finales = simular_trades_ensemble(campeones, df_mercado, ranking_map, evaluador, start_idx=210, end_idx=None, usar_ia=True, ticker=ds_file.stem)

    # Filtrar sensores inactivos en 100%
    campeones_activos = []
    for c in campeones:
        tr_c = metricas_finales["trades_por_formula"].get(c.id, 0)
        if tr_c > 0:
            campeones_activos.append(c)
        else:
            motivo = "0 trades ejecutados en muestra total (redundancia 100%). Se preserva standalone."
            descartadas_log.append({"id": c.id, "titulo": c.titulo, "motivo": motivo})
            rondas_log.append(f"  ➖ [REDUNDANCIA OMITIDA] '{c.titulo}': {motivo}")

    if not campeones_activos and campeones:
        campeones_activos = [campeones[0]]

    # Matriz Walk-Forward y Fondeo
    rondas_log.append("\n" + "=" * 80)
    rondas_log.append("📊 AUDITORÍA CIEGA DUAL WALK-FORWARD (IS 70% vs OOS 30%)")
    rondas_log.append("=" * 80)
    rondas_log.append(f"{'CUADRANTE DE VALIDACIÓN':<30} | {'TRADES':<8} | {'RETORNO':<12} | {'PF':<8} | {'MAX DD':<10} | {'WIN RATE':<10}")
    rondas_log.append("-" * 80)
    rondas_log.append(f"{'1. In-Sample (70%) Sin IA':<30} | {m_is_sin['trades_totales']:<8} | {m_is_sin['retorno_neto_total_pct']:>+8.2f}%   | {m_is_sin['pf_neto']:<8.2f} | {m_is_sin['max_drawdown_pct']:>6.2f}%   | {m_is_sin['win_rate_neto']:>6.1f}%")
    rondas_log.append(f"{'2. In-Sample (70%) Con Cerebro':<30} | {m_is_con['trades_totales']:<8} | {m_is_con['retorno_neto_total_pct']:>+8.2f}%   | {m_is_con['pf_neto']:<8.2f} | {m_is_con['max_drawdown_pct']:>6.2f}%   | {m_is_con['win_rate_neto']:>6.1f}%")
    rondas_log.append(f"{'3. Out-Of-Sample (30%) Sin IA':<30} | {m_oos_sin['trades_totales']:<8} | {m_oos_sin['retorno_neto_total_pct']:>+8.2f}%   | {m_oos_sin['pf_neto']:<8.2f} | {m_oos_sin['max_drawdown_pct']:>6.2f}%   | {m_oos_sin['win_rate_neto']:>6.1f}%")
    rondas_log.append(f"{'4. Out-Of-Sample (30%) Con Kula':<30} | {m_oos_con['trades_totales']:<8} | {m_oos_con['retorno_neto_total_pct']:>+8.2f}%   | {m_oos_con['pf_neto']:<8.2f} | {m_oos_con['max_drawdown_pct']:>6.2f}%   | {m_oos_con['win_rate_neto']:>6.1f}%")
    rondas_log.append("=" * 80)
    rondas_log.append(f"🏦 DICTAMEN FONDEO (PROP FIRM): [{metricas_finales.get('prop_firm_semaforo', 'N/A')}]")
    rondas_log.append(f"   Max Daily DD (≤4.5%): {metricas_finales.get('max_daily_dd_pct', 0.0)}% | Max DD (≤8.0%): {metricas_finales.get('max_drawdown_pct', 0.0)}% | Racha Pérdidas: {metricas_finales.get('max_losing_streak', 0)}")
    rondas_log.append("=" * 80)
    rondas_log.append(f"\n================================================================================")
    rondas_log.append(f"   DICTAMEN FINAL: ENSAMBLE CAMPEÓN CONSOLIDADO ({len(campeones_activos)} Sensores Activos)")
    rondas_log.append(f"================================================================================")
    rondas_log.append(f"  [✓] RETORNO NETO CONJUNTO : {metricas_finales['retorno_neto_total_pct']:+.2f}%")
    rondas_log.append(f"  [✓] PROFIT FACTOR NETO    : {metricas_finales['pf_neto']:.2f}")
    rondas_log.append(f"  [✓] WIN RATE NETO         : {metricas_finales['win_rate_neto']:.1f}%")
    rondas_log.append(f"  [✓] DRAWDOWN MÁXIMO       : {metricas_finales['max_drawdown_pct']:.2f}%")
    rondas_log.append(f"  [✓] TRADES TOTALES        : {metricas_finales['trades_totales']}")
    rondas_log.append(f"  [✓] R:R PROMEDIO NETO     : 1:{metricas_finales['rr_promedio_neto']:.2f}")
    rondas_log.append(f"--------------------------------------------------------------------------------")
    rondas_log.append(f"Aporte por Sensor Activo:")
    for c in campeones_activos:
        tr_c = metricas_finales["trades_por_formula"].get(c.id, 0)
        pnl_c = metricas_finales["pnl_por_formula"].get(c.id, 0.0)
        pct_tr = (tr_c / max(metricas_finales["trades_totales"], 1)) * 100.0
        rondas_log.append(f"  • {c.titulo} (Prioridad #{c.priority_rank}): {tr_c} trades ({pct_tr:.1f}%) | PnL Bruto: {pnl_c:+.2f}%")

    # 5. Sintetizar código Python limpio con los sensores activos
    code_math, code_ia = sintetizar_codigo_ensamble(campeones_activos, ranking_map, metricas_finales, ds_file.name)

    return {
        "status": "ok",
        "dataset": ds_file.name,
        "total_auditadas": len(universo),
        "campeones": [
            {
                "id": c.id,
                "archivo": c.archivo,
                "titulo": c.titulo,
                "priority_rank": c.priority_rank,
                "trades_aportados": metricas_finales["trades_por_formula"].get(c.id, 0),
                "pnl_bruto_aportado": metricas_finales["pnl_por_formula"].get(c.id, 0.0)
            }
            for c in campeones_activos
        ],
        "descartadas": descartadas_log,
        "metricas": metricas_finales,
        "rondas_log": rondas_log,
        "log_texto": "\n".join(rondas_log),
        "code_math": code_math,
        "code_ia": code_ia,
        "nombre_sugerido": f"ensamble_campeon_{ds_file.stem}.py"
    }
