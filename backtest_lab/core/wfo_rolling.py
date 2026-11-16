"""
Módulo: backtest_lab/core/wfo_rolling.py
Proyecto: Kula Balam / Backtest Lab
Objetivo: Validación Walk-Forward Deslizante (Rolling WFO) con preservación de warmup_bars
y Filtro de Estabilidad por Meseta (Parameter Plateau) vía distancia de Chebyshev.
"""

import numpy as np
import pandas as pd
from typing import Callable, Dict, Any, List


def run_rolling_wfo(
    df: pd.DataFrame,
    eval_window_fn: Callable[[pd.DataFrame, int, int], Dict[str, Any]],
    n_windows: int = 5,
    is_ratio: float = 0.70,
    warmup_bars: int = 250
) -> Dict[str, Any]:
    """
    Ejecuta validación Walk-Forward deslizante (Rolling WFO) preservando el colchón de calentamiento
    de indicadores (warmup_bars) para no generar NaNs en EMA200/ATR al inicio de cada ventana.

    eval_window_fn(df_slice, eval_start_rel_idx, eval_end_rel_idx):
        Recibe el DataFrame con prefijo de warmup y evalúa entradas únicamente entre
        [eval_start_rel_idx, eval_end_rel_idx]. Debe retornar {'net_return_pct': float, 'trades_count': int, 'profit_factor': float}.
    """
    total_bars = len(df)
    usable_bars = total_bars - warmup_bars
    if usable_bars < (n_windows * 60):
        return {
            "wfo_valid": False,
            "reason": f"Historial insuficiente ({total_bars} velas) para {n_windows} ventanas con warmup={warmup_bars}.",
            "wfe_ratio": 0.0,
            "wfo_passed": False,
            "windows": []
        }

    oos_len = int(usable_bars / (n_windows + (is_ratio / (1.0 - is_ratio))))
    is_len = int(oos_len * (is_ratio / (1.0 - is_ratio)))
    if oos_len < 20 or is_len < 40:
        oos_len = max(20, usable_bars // (n_windows + 2))
        is_len = oos_len * 2

    windows_report: List[Dict[str, Any]] = []
    is_returns_per_bar: List[float] = []
    oos_returns_per_bar: List[float] = []
    positive_oos_windows = 0

    for w_idx in range(n_windows):
        is_start = warmup_bars + (w_idx * oos_len)
        is_end = is_start + is_len
        oos_start = is_end
        oos_end = min(total_bars, oos_start + oos_len)

        if oos_end - oos_start < 10:
            break

        slice_is_start = max(0, is_start - warmup_bars)
        df_is = df.iloc[slice_is_start:is_end].copy()
        res_is = eval_window_fn(df_is, is_start - slice_is_start, len(df_is))

        slice_oos_start = max(0, oos_start - warmup_bars)
        df_oos = df.iloc[slice_oos_start:oos_end].copy()
        res_oos = eval_window_fn(df_oos, oos_start - slice_oos_start, len(df_oos))

        ret_is = float(res_is.get("net_return_pct", 0.0))
        ret_oos = float(res_oos.get("net_return_pct", 0.0))

        bars_is = max(1, is_end - is_start)
        bars_oos = max(1, oos_end - oos_start)

        is_returns_per_bar.append(ret_is / bars_is)
        oos_returns_per_bar.append(ret_oos / bars_oos)

        if ret_oos > 0.0:
            positive_oos_windows += 1

        windows_report.append({
            "window_index": w_idx + 1,
            "is_bars": bars_is,
            "oos_bars": bars_oos,
            "is_return_pct": round(ret_is, 2),
            "oos_return_pct": round(ret_oos, 2),
            "oos_pf": round(float(res_oos.get("profit_factor", 0.0)), 2),
            "oos_trades": int(res_oos.get("trades_count", 0))
        })

    mean_is_rate = float(np.mean(is_returns_per_bar)) if is_returns_per_bar else 0.0
    mean_oos_rate = float(np.mean(oos_returns_per_bar)) if oos_returns_per_bar else 0.0

    if mean_is_rate <= 1e-9 or mean_oos_rate <= 0.0:
        wfe_ratio = 0.0
    else:
        wfe_ratio = round(mean_oos_rate / mean_is_rate, 2)

    n_eval = len(windows_report)
    consistency_ratio = (positive_oos_windows / n_eval) if n_eval > 0 else 0.0
    wfo_passed = bool(wfe_ratio >= 0.50 and consistency_ratio >= 0.60)

    return {
        "wfo_valid": True,
        "n_windows": n_eval,
        "wfe_ratio": wfe_ratio,
        "positive_oos_windows": positive_oos_windows,
        "consistency_pct": round(consistency_ratio * 100.0, 1),
        "wfo_passed": wfo_passed,
        "windows": windows_report
    }


def compute_plateau_robust_score(
    grid_results: List[Dict[str, Any]],
    param_keys: List[str],
    metric_key: str = "net_return_pct",
    center_weight: float = 0.50
) -> List[Dict[str, Any]]:
    """
    Filtro de Estabilidad por Meseta (Parameter Plateau) para el Optimizador de Rejilla.
    Penaliza picos aislados promediando cada combinación con sus vecinos inmediatos en la grilla.
    """
    if not grid_results or not param_keys:
        return grid_results

    unique_vals = {
        k: sorted(list({row["params"][k] for row in grid_results if k in row.get("params", {})}))
        for k in param_keys
    }
    val_to_idx = {
        k: {v: idx for idx, v in enumerate(vals)}
        for k, vals in unique_vals.items()
    }

    coord_map = {}
    for row in grid_results:
        p = row.get("params", {})
        coord = tuple(val_to_idx[k].get(p.get(k), -999) for k in param_keys)
        coord_map[coord] = row

    enriched = []
    for coord, row in coord_map.items():
        center_val = float(row.get(metric_key, 0.0))
        neighbor_vals = []
        for other_coord, other_row in coord_map.items():
            if other_coord == coord:
                continue
            if all(abs(a - b) <= 1 for a, b in zip(coord, other_coord)):
                neighbor_vals.append(float(other_row.get(metric_key, 0.0)))

        if neighbor_vals:
            mean_neighbors = float(np.mean(neighbor_vals))
            min_neighbor = float(np.min(neighbor_vals))
            cliff_penalty = 0.50 if min_neighbor < 0.0 else 1.0
            plateau_score = ((center_weight * center_val) + ((1.0 - center_weight) * mean_neighbors)) * cliff_penalty
        else:
            plateau_score = center_val

        new_row = dict(row)
        new_row["plateau_score"] = round(plateau_score, 4)
        new_row["neighbors_evaluated"] = len(neighbor_vals)
        enriched.append(new_row)

    enriched.sort(key=lambda x: x.get("plateau_score", -999999.0), reverse=True)
    return enriched
