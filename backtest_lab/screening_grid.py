# -*- coding: utf-8 -*-
"""
===============================================================================
MÓDULO DE SCREENING GRID: BARRIDO MASIVO MULTI-ACTIVO & MULTI-TEMPORALIDAD
===============================================================================
Ecosistema: KULA · BALAM / BACKTEST LAB
Evalúa una estrategia cuantitativa (Fórmula + Árbitro IA) en paralelo contra todo
el universo de datasets históricos sin sesgo de selección a un solo activo.
===============================================================================
"""

import sys
import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "datos_historicos"

UNIVERSOS_CATALOGO: Dict[str, List[str]] = {
    "crypto_4h": [
        "binance_SOL_USDT_4h.parquet",
        "binance_ETH_USDT_4h.parquet",
        "binance_BTC_USDT_4h.parquet",
    ],
    "crypto_todos": [
        "binance_SOL_USDT_4h.parquet",
        "binance_ETH_USDT_4h.parquet",
        "binance_BTC_USDT_4h.parquet",
        "binance_SOL_USDT_1h.parquet",
        "binance_ETH_USDT_1h.parquet",
        "binance_BTC_USDT_1h.parquet",
        "binance_ETH_USDT_15m.parquet",
        "binance_BTC_USDT_15m.parquet",
        "binance_SOL_USDT_1d.parquet",
        "binance_ETH_USDT_1d.parquet",
        "binance_BTC_USDT_1d.parquet",
    ],
    "tradfi_1d": [
        "yf_SPY_1d.parquet",
        "yf_QQQ_1d.parquet",
        "yf_AAPL_1d.parquet",
        "yf_AMD_1d.parquet",
        "yf_AMZN_1d.parquet",
        "yf_AVGO_1d.parquet",
        "yf_META_1d.parquet",
        "yf_MSFT_1d.parquet",
        "yf_NVDA_1d.parquet",
        "yf_TSLA_1d.parquet",
        "yf_TQQQ_1d.parquet",
        "yf_URA_1d.parquet",
        "yf_USO_1d.parquet",
    ],
    "tradfi_intradia": [
        "yf_SPY_15m.parquet",
        "yf_SPY_5m.parquet",
        "yf_QQQ_15m.parquet",
        "yf_QQQ_5m.parquet",
        "yf_NVDA_15m.parquet",
        "yf_NVDA_5m.parquet",
        "yf_TSLA_15m.parquet",
        "yf_TSLA_5m.parquet",
        "yf_META_15m.parquet",
        "yf_AMD_15m.parquet",
    ],
    "forex": [
        "yf_EURUSD_1d.parquet",
        "yf_EURUSD_1h.parquet",
        "yf_GBPUSD_1d.parquet",
        "yf_GBPUSD_1h.parquet",
        "yf_USDJPY_1d.parquet",
        "yf_USDCAD_1d.parquet",
    ],
    "todos": [
        # Cartera núcleo institucional multiactivo
        "binance_SOL_USDT_4h.parquet",
        "binance_ETH_USDT_4h.parquet",
        "binance_BTC_USDT_4h.parquet",
        "yf_SPY_1d.parquet",
        "yf_QQQ_1d.parquet",
        "yf_AAPL_1d.parquet",
        "yf_NVDA_1d.parquet",
        "yf_MSFT_1d.parquet",
        "yf_EURUSD_1d.parquet",
        "yf_GBPUSD_1d.parquet",
        "yf_SPY_15m.parquet",
        "binance_ETH_USDT_15m.parquet",
    ]
}


def resolver_archivos_universo(universo: str) -> List[str]:
    """Obtiene la lista de datasets existentes para un universo."""
    u_norm = (universo or "todos").lower().strip()
    candidatos = UNIVERSOS_CATALOGO.get(u_norm)
    if not candidatos:
        if u_norm in ["completo", "todo", "full"]:
            candidatos = sorted([f.name for f in DATA_DIR.glob("*.parquet")])
        else:
            candidatos = UNIVERSOS_CATALOGO["todos"]

    existentes = [f for f in candidatos if (DATA_DIR / f).exists()]
    return existentes


def _ejecutar_un_backtest(tmp_script: str, dataset_name: str, base_dir: Path) -> Optional[Dict[str, Any]]:
    """Ejecuta el script temporal contra un dataset específico y extrae su payload JSON."""
    data_path = DATA_DIR / dataset_name
    if not data_path.exists():
        return None

    cmd = [sys.executable, "-u", tmp_script, str(data_path), "--json"]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(base_dir) + os.pathsep + str(base_dir.parent) + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=35,
            env=env,
            cwd=str(base_dir),
        )
        out = res.stdout or ""
        if "###JSON_METRICAS_INICIO###" in out and "###JSON_METRICAS_FIN###" in out:
            ini = out.index("###JSON_METRICAS_INICIO###") + len("###JSON_METRICAS_INICIO###")
            fin = out.index("###JSON_METRICAS_FIN###")
            payload = json.loads(out[ini:fin].strip())
            return payload
    except Exception:
        pass
    return None


def ejecutar_screening_grid(
    code_math: str,
    code_ia: str = "",
    universo: str = "todos",
    top_n: int = 15,
    max_workers: int = 4
) -> Dict[str, Any]:
    """
    Ejecuta el screening masivo en paralelo contra todos los datasets del universo solicitado.
    """
    try:
        from backtest_lab.server import generar_script_ejecucion, BASE_DIR
    except ImportError:
        from server import generar_script_ejecucion, BASE_DIR

    datasets = resolver_archivos_universo(universo)
    if not datasets:
        return {
            "universo": universo,
            "total_evaluados": 0,
            "aptos": 0,
            "ranking": [],
            "resumen_texto": "No se encontraron datasets válidos en el disco para este universo."
        }

    # Generar script ejecutor temporal
    codigo_completo = generar_script_ejecucion(code_math, code_ia or "")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(codigo_completo)
        tmp_script_path = tmp.name

    resultados: List[Dict[str, Any]] = []

    try:
        workers = min(max_workers, len(datasets), os.cpu_count() or 4)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futuros = {
                executor.submit(_ejecutar_un_backtest, tmp_script_path, ds, BASE_DIR): ds
                for ds in datasets
            }
            for fut in as_completed(futuros):
                ds_name = futuros[fut]
                try:
                    data = fut.result()
                    if data:
                        resultados.append(data)
                    else:
                        resultados.append({
                            "ticker": ds_name.replace("binance_", "").replace("yf_", "").replace(".parquet", ""),
                            "dataset": ds_name,
                            "mercado": "Error/Sin Muestra",
                            "trades_totales": 0,
                            "win_rate_neto": 0.0,
                            "pf_neto": 0.0,
                            "rr_promedio_neto": 0.0,
                            "retorno_neto_total_pct": 0.0,
                            "max_drawdown_pct": 0.0,
                            "dictamen": "❌ DESCARTADA (Sin Muestra)",
                            "is_pf": 0.0,
                            "is_wr": 0.0,
                            "is_trades": 0,
                            "oos_pf": 0.0,
                            "oos_wr": 0.0,
                            "oos_trades": 0,
                            "oos_ret": 0.0,
                            "vetos_ia": 0,
                            "aprobado": False
                        })
                except Exception:
                    pass
    finally:
        if os.path.exists(tmp_script_path):
            os.remove(tmp_script_path)

    # Función de ordenamiento cuantitativo (Scoring)
    def _calcular_score(item: Dict[str, Any]) -> float:
        aprobado = 100.0 if item.get("aprobado") else 0.0
        oos_pf = float(item.get("oos_pf", 0.0))
        pf = float(item.get("pf_neto", 0.0))
        wr = float(item.get("win_rate_neto", 0.0))
        ret = float(item.get("retorno_neto_total_pct", 0.0))
        dd = float(item.get("max_drawdown_pct", 0.0))
        trades = int(item.get("trades_totales", 0))

        if trades < 10:
            return -100.0 + trades

        # Fórmula de scoring institucional
        score = aprobado + (oos_pf * 40.0) + (pf * 25.0) + (wr * 0.4) + (ret * 0.2) - (dd * 0.8)
        return score

    resultados.sort(key=_calcular_score, reverse=True)
    ranking = resultados[:top_n]

    n_aptos = sum(1 for r in ranking if r.get("aprobado"))
    n_descartados = len(ranking) - n_aptos

    # Generar tabla ASCII formateada
    lineas = [
        "",
        "=" * 125,
        "   LAB: BARRIDO MASIVO MULTI-ACTIVO & MULTI-TEMPORALIDAD (SCREENING GRID)",
        f"   Universo: {universo.upper()} | Activos Evaluados: {len(ranking)} | Aptos: {n_aptos} | Descartados: {n_descartados}",
        "=" * 125,
        f"{'#':<3} | {'DATASET / ACTIVO':<28} | {'TRADES':<7} | {'WIN RATE':<9} | {'PF NETO':<8} | {'OOS PF':<7} | {'RETORNO':<10} | {'MAX DD':<8} | {'FONDEO':<9} | {'DICTAMEN':<22}",
        "-" * 125
    ]

    for idx, r in enumerate(ranking, 1):
        ds_cortado = r.get("dataset", "")[:26]
        tr = str(r.get("trades_totales", 0))
        wr = f"{r.get('win_rate_neto', 0.0):.1f}%"
        pf = f"{r.get('pf_neto', 0.0):.2f}"
        oos_pf = f"{r.get('oos_pf', 0.0):.2f}"
        ret = f"{r.get('retorno_neto_total_pct', 0.0):+.1f}%"
        dd = f"{r.get('max_drawdown_pct', 0.0):.1f}%"
        fondeo = "✅ APTA" if r.get("apta_fondeo") else "❌ NO"
        dictamen = r.get("dictamen", "")

        lineas.append(
            f"{idx:<3} | {ds_cortado:<28} | {tr:<7} | {wr:<9} | {pf:<8} | {oos_pf:<7} | {ret:<10} | {dd:<8} | {fondeo:<9} | {dictamen:<22}"
        )

    lineas.append("=" * 125)
    lineas.append("[🏆] BALANCE INSTITUCIONAL:")
    lineas.append(f"     • Activos que superaron la valla institucional: {n_aptos} de {len(ranking)}")
    if ranking and ranking[0].get("aprobado"):
        top = ranking[0]
        lineas.append(f"     • Activo Rey / Mejor Desempeño: {top.get('dataset')} (PF: {top.get('pf_neto')} | OOS PF: {top.get('oos_pf')} | Ret: {top.get('retorno_neto_total_pct')}%)")
    lineas.append("=" * 115)
    lineas.append("")

    resumen_texto = "\n".join(lineas)

    return {
        "universo": universo,
        "total_evaluados": len(ranking),
        "aptos": n_aptos,
        "ranking": ranking,
        "resumen_texto": resumen_texto
    }
