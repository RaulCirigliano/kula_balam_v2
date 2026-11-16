# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.metrics import EvaluadorCuantitativo

# Importar Fórmulas Matemáticas y Árbitro IA
from estrategias_math.donchian_breakout import formula_matematica as math_donchian
from estrategias_math.fibo_golden_zone import formula_matematica as math_fibo
from estrategias_ia.arbitro_antigravity_cava import arbitro_ia

DATA_DIR = BASE_DIR / "data" / "datos_historicos"

def preparar_mercado(df_in: pd.DataFrame) -> pd.DataFrame:
    df = df_in.copy()
    df.columns = [str(c).lower() for c in df.columns]
    if not isinstance(df.index, pd.DatetimeIndex):
        col_t = next((c for c in ["timestamp", "date", "datetime", "time"] if c in df.columns), None)
        if col_t:
            df[col_t] = pd.to_datetime(df[col_t])
            df.set_index(col_t, inplace=True)
        else:
            raise ValueError("No se detectó columna temporal válida.")
    df = df.sort_index()

    prev_c = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean().shift(1)

    vol_col = "volume" if "volume" in df.columns else None
    if vol_col and df[vol_col].sum() > 0:
        df["vol_sma"] = df[vol_col].rolling(20).mean().shift(1)
        df["rvol"] = df[vol_col] / (df["vol_sma"] + 1e-9)
    else:
        df["rvol"] = 1.3

    rango = (df["high"] - df["low"]).replace(0, 1e-9)
    techo = df[["open", "close"]].max(axis=1)
    suelo = df[["open", "close"]].min(axis=1)
    df["mecha_superior_pct"] = ((df["high"] - techo) / rango) * 100.0
    df["mecha_inferior_pct"] = ((suelo - df["low"]) / rango) * 100.0
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["dist_ema_atrs"] = (df["close"] - df["ema_50"]).abs() / (df["atr"] + 1e-9)
    return df

def auditar_activo(archivo: str, func_math, nombre_estrategia: str, dias_ventana: int = 30):
    ruta = DATA_DIR / archivo
    if not ruta.exists():
        return None

    df_raw = pd.read_parquet(ruta) if ruta.suffix == ".parquet" else pd.read_csv(ruta)
    df = preparar_mercado(df_raw)

    evaluador = EvaluadorCuantitativo(comision_pct=0.0008, slippage_pct=0.0005)
    total = len(df)
    indices = df.index
    
    fecha_limite = indices[-1] - pd.Timedelta(days=dias_ventana)

    trades_math = []
    trades_ia = []
    vetos_ia = []

    pos_m = False
    exit_m = -1
    pos_i = False
    exit_i = -1

    for i in range(50, total - 1):
        # Liberar posiciones si ya expiraron
        if pos_m and i >= exit_m:
            pos_m = False
        if pos_i and i >= exit_i:
            pos_i = False

        # Solo registrar operaciones que ocurran dentro de los últimos 'dias_ventana'
        es_en_ventana = indices[i] >= fecha_limite

        es_candidato, lado, sl, tp = func_math(df, i)
        if not es_candidato:
            continue

        entry = df.iloc[i + 1]["open"] if i + 1 < total else df.iloc[i]["close"]
        p_exit = df["close"].iloc[min(i + 48, total - 1)]
        exit_bar = min(i + 48, total - 1)

        for j in range(i + 1, min(i + 49, total)):
            hj = df["high"].iloc[j]
            lj = df["low"].iloc[j]
            if lado == "LONG":
                if lj <= sl:
                    p_exit = sl
                    exit_bar = j
                    break
                if hj >= tp:
                    p_exit = tp
                    exit_bar = j
                    break
            else:
                if hj >= sl:
                    p_exit = sl
                    exit_bar = j
                    break
                if lj <= tp:
                    p_exit = tp
                    exit_bar = j
                    break

        pnl_bruto = ((p_exit - entry) / entry) * 100.0 if lado == "LONG" else ((entry - p_exit) / entry) * 100.0

        if es_en_ventana:
            if not pos_m:
                trades_math.append({"fecha": str(indices[i])[:16], "pnl_pct": pnl_bruto})
                pos_m = True
                exit_m = exit_bar

            ok, sizing, motivo = arbitro_ia(df.iloc[i], lado, entry, sl, tp)
            if ok:
                if not pos_i:
                    trades_ia.append({"fecha": str(indices[i])[:16], "pnl_pct": pnl_bruto * sizing})
                    pos_i = True
                    exit_i = exit_bar
            else:
                vetos_ia.append({"fecha": str(indices[i])[:16], "pnl_evitado": round(pnl_bruto, 2), "motivo": motivo})
        else:
            # Mantener simulación de posición fuera de ventana para evitar sesgo de entrada
            if not pos_m:
                pos_m = True
                exit_m = exit_bar
            ok, sizing, motivo = arbitro_ia(df.iloc[i], lado, entry, sl, tp)
            if ok and not pos_i:
                pos_i = True
                exit_i = exit_bar

    res_m = evaluador.calcular_metricas(pd.DataFrame(trades_math), col_pnl_bruto="pnl_pct")
    res_i = evaluador.calcular_metricas(pd.DataFrame(trades_ia), col_pnl_bruto="pnl_pct")

    trampas_evitadas = len([v for v in vetos_ia if v["pnl_evitado"] <= 0])
    buenas_sacrificadas = len([v for v in vetos_ia if v["pnl_evitado"] > 0])

    return {
        "archivo": archivo,
        "estrategia": nombre_estrategia,
        "math": res_m,
        "ia": res_i,
        "vetos_totales": len(vetos_ia),
        "trampas_evitadas": trampas_evitadas,
        "buenas_sacrificadas": buenas_sacrificadas,
    }

def main():
    activos = [
        # CRIPTO 1H
        ("binance_BTC_USDT_1h.parquet", "Cripto", "BTC/USDT 1H"),
        ("binance_ETH_USDT_1h.parquet", "Cripto", "ETH/USDT 1H"),
        ("binance_SOL_USDT_1h.parquet", "Cripto", "SOL/USDT 1H"),
        # FOREX 1H & 1D
        ("yf_EURUSD_1h.parquet", "Forex", "EUR/USD 1H"),
        ("yf_GBPUSD_1h.parquet", "Forex", "GBP/USD 1H"),
        ("yf_USDJPY_1d.parquet", "Forex", "USD/JPY 1D"),
        ("yf_USDCAD_1d.parquet", "Forex", "USD/CAD 1D"),
        # TRADFI ACCIONES & ÍNDICES 1D
        ("yf_SPY_1d.parquet", "TradFi", "S&P 500 (SPY) 1D"),
        ("yf_QQQ_1d.parquet", "TradFi", "Nasdaq (QQQ) 1D"),
        ("yf_NVDA_1d.parquet", "TradFi", "NVIDIA (NVDA) 1D"),
        ("yf_AAPL_1d.parquet", "TradFi", "Apple (AAPL) 1D"),
        ("yf_TSLA_1d.parquet", "TradFi", "Tesla (TSLA) 1D"),
    ]

    print("=" * 105)
    print("   AUDITORÍA MENSUAL MULTIACTIVO: FÓRMULAS MATEMÁTICAS vs. ÁRBITRO IA ANTIGRAVITY (ÚLTIMOS 30 DÍAS)")
    print("   Fricción: 0.26% Round-Trip | R:R Mínimo Exigido: >= 1:2.0 | Ventana: 30 Días")
    print("=" * 105)

    estrategias = [
        ("Donchian Breakout (20)", math_donchian),
        ("Fibo Golden Zone (0.50-0.75)", math_fibo)
    ]

    for nom_est, func_est in estrategias:
        print(f"\n>>> ESTRATEGIA: {nom_est.upper()}")
        print("-" * 105)
        print(f"{'ACTIVO / MERCADO':<22} | {'TRADES (M vs IA)':<17} | {'WIN RATE (M vs IA)':<19} | {'RETORNO NETO':<18} | {'TRAMPAS EVITADAS':<16}")
        print("-" * 105)

        tot_trades_m = 0
        tot_trades_i = 0
        tot_ret_m = 0.0
        tot_ret_i = 0.0
        tot_trampas = 0

        for arch, mercado, label in activos:
            res = auditar_activo(arch, func_est, nom_est, dias_ventana=30)
            if not res:
                continue

            m = res["math"]
            ia = res["ia"]

            tm = m["trades_totales"]
            ti = ia["trades_totales"]
            wrm = f"{m['win_rate_neto']}%"
            wri = f"{ia['win_rate_neto']}%"
            retm = f"{m['retorno_neto_total_pct']:+.2f}%"
            reti = f"{ia['retorno_neto_total_pct']:+.2f}%"
            trampas = f"{res['trampas_evitadas']}/{res['vetos_totales']}"

            tot_trades_m += tm
            tot_trades_i += ti
            tot_ret_m += m['retorno_neto_total_pct']
            tot_ret_i += ia['retorno_neto_total_pct']
            tot_trampas += res['trampas_evitadas']

            str_trades = f"{tm:>3} vs {ti:<3}"
            str_wr = f"{wrm:>6} vs {wri:<6}"
            str_ret = f"{retm:>7} vs {reti:<7}"

            print(f"{label:<22} | {str_trades:<17} | {str_wr:<19} | {str_ret:<18} | {trampas:<16}")

        print("-" * 105)
        print(f"{'TOTAL CONSOLIDADO':<22} | {tot_trades_m:>3} vs {tot_trades_i:<3}          |                       | {tot_ret_m:>+7.2f}% vs {tot_ret_i:>+7.2f}%   | {tot_trampas} pérdidas evitadas")
        print("=" * 105)

if __name__ == "__main__":
    main()
