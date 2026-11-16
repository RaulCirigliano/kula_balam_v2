"""
Script: auditar_kula_balam_vs_antigravity.py
Proyecto: Kula Balam / Backtest Lab
Objetivo: Auditoría dual comparativa:
         1. Balam Cuantitativo Puro (Ruptura Fractal + Zona Fibo sin árbitro).
         2. Ecosistema Completo: Balam + Kula (Riesgo/Sizing) + Antigravity (CIO Veto de Trampas y Asimetría R:R >= 1:2).
Velocidad: Ejecución nativa en memoria (menos de 1 segundo).
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Inyectar paths para importar desde backtest_lab y kula_balam_ikigai
BASE_LAB_DIR = Path(__file__).resolve().parent.parent
BASE_PROJ_DIR = BASE_LAB_DIR.parent
for p in [str(BASE_LAB_DIR), str(BASE_PROJ_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
import pandas as pd
from core.metrics import EvaluadorCuantitativo


# =============================================================================
# MOTOR CUANTITATIVO BALAM (balam.py adaptado a backtest vectorizado)
# =============================================================================
def preparar_datos_balam(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = df_raw.copy()
    df.columns = [str(c).lower() for c in df.columns]

    if not isinstance(df.index, pd.DatetimeIndex):
        col_t = next((c for c in ["timestamp", "date", "datetime", "time"] if c in df.columns), None)
        if col_t:
            df[col_t] = pd.to_datetime(df[col_t])
            df.set_index(col_t, inplace=True)
        else:
            raise ValueError("No se detectó columna temporal válida.")

    df = df.sort_index()

    # 1. Marco Diario (1D) para Sesgo Macro (Alex Ruiz / Balam)
    df_1d = df.resample("1D").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
    }).dropna()
    span_1d = min(50, len(df_1d))
    df_1d["ema_50"] = df_1d["close"].ewm(span=span_1d, adjust=False).mean()
    df_1d["ema_slope"] = df_1d["ema_50"] - df_1d["ema_50"].shift(2)
    df_1d["macro_bias"] = np.where(
        (df_1d["close"] > df_1d["ema_50"]) & (df_1d["ema_slope"] >= 0), "LONG",
        np.where((df_1d["close"] < df_1d["ema_50"]) & (df_1d["ema_slope"] <= 0), "SHORT", "NEUTRAL")
    )
    df["macro_bias"] = df_1d["macro_bias"].shift(1).reindex(df.index, method="ffill").bfill()

    # 2. ATR 14 y Volumen Medio
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean().shift(1)

    vol_col = "volume" if "volume" in df.columns else None
    if vol_col and df[vol_col].sum() > 0:
        df["vol_sma20"] = df[vol_col].rolling(20).mean().shift(1)
        df["rvol"] = df[vol_col] / (df["vol_sma20"] + 1e-9)
    else:
        df["rvol"] = 1.25

    # 3. Fractales de Williams (5 velas)
    h = df["high"]
    l = df["low"]
    is_f_high = (h.shift(2) > h.shift(3)) & (h.shift(2) > h.shift(4)) & (h.shift(2) > h.shift(1)) & (h.shift(2) > h)
    is_f_low = (l.shift(2) < l.shift(3)) & (l.shift(2) < l.shift(4)) & (l.shift(2) < l.shift(1)) & (l.shift(2) < l)
    df["fractal_high"] = np.where(is_f_high, h.shift(2), np.nan)
    df["fractal_low"] = np.where(is_f_low, l.shift(2), np.nan)
    df["last_fractal_high"] = df["fractal_high"].ffill().bfill().shift(1)
    df["last_fractal_low"] = df["fractal_low"].ffill().bfill().shift(1)

    # 4. Métricas de Acción del Precio (Cava / Wyckoff para Antigravity CIO)
    rango_total = (df["high"] - df["low"]).replace(0, 1e-9)
    cuerpo_techo = df[["open", "close"]].max(axis=1)
    cuerpo_suelo = df[["open", "close"]].min(axis=1)
    df["mecha_superior_pct"] = ((df["high"] - cuerpo_techo) / rango_total) * 100.0
    df["mecha_inferior_pct"] = ((cuerpo_suelo - df["low"]) / rango_total) * 100.0

    # Distancia a la EMA 50 en ATRs (sobreextensión)
    df["ema_50_local"] = df["close"].ewm(span=50, adjust=False).mean()
    df["dist_ema_atrs"] = (df["close"] - df["ema_50_local"]).abs() / (df["atr"] + 1e-9)

    return df


# =============================================================================
# ÁRBITRO DE INTELIGENCIA DE MERCADO (ANTIGRAVITY CIO + KULA RISK)
# =============================================================================
class ArbitroAntigravityKula:
    """
    Arbitraje del CIO de Antigravity (Acción del Precio y Asimetría) 
    combinado con la política de gestión de riesgo de Kula.
    """
    def __init__(self, saldo_inicial: float = 100.0, riesgo_usd_fijo: float = 1.00):
        self.saldo = saldo_inicial
        self.riesgo_usd = riesgo_usd_fijo
        self.posiciones_abiertas = 0

    def auditar_candidato(self, row: pd.Series, lado: str, entry: float, sl: float, tp: float) -> Tuple[bool, float, str]:
        # 1. Auditoría de Asimetría Matemática R:R
        riesgo = abs(entry - sl)
        recompensa = abs(tp - entry)
        rr_teorico = recompensa / (riesgo + 1e-9)

        if rr_teorico < 1.95:
            return False, 0.0, f"VETO Asimetría insuficiente ({rr_teorico:.2f} < 1:2.0)"

        # 2. Veto Antigravity: Mecha de rechazo / trampa de liquidez
        if lado == "LONG" and row["mecha_superior_pct"] > 35.0:
            return False, 0.0, f"VETO Mecha superior ({row['mecha_superior_pct']:.1f}% > 35% trampa institucional)"
        if lado == "SHORT" and row["mecha_inferior_pct"] > 35.0:
            return False, 0.0, f"VETO Mecha inferior ({row['mecha_inferior_pct']:.1f}% > 35% trampa institucional)"

        # 3. Veto Antigravity: Sobreextensión del precio (evitar techo/piso de Onda C)
        if row["dist_ema_atrs"] > 3.2:
            return False, 0.0, f"VETO Sobreextensión ({row['dist_ema_atrs']:.1f} ATRs de EMA50)"

        # 4. Kula Risk Position Sizing
        risk_pct = riesgo / entry
        if risk_pct < 0.005 or risk_pct > 0.05:
            return False, 0.0, f"VETO Kula Risk fuera de rango ({risk_pct*100:.2f}%)"

        # Ponderación normal 1.0x o reducida 0.75x si RVOL es moderado
        multiplicador = 1.0 if row["rvol"] >= 1.35 else 0.75
        return True, multiplicador, "APROBADO por Kula Risk y CIO Antigravity"


# =============================================================================
# MOTOR DE AUDITORÍA DUAL
# =============================================================================
def ejecutar_auditoria_dual(df: pd.DataFrame, ticker: str):
    evaluador = EvaluadorCuantitativo(comision_pct=0.0008, slippage_pct=0.0005)
    arbitro = ArbitroAntigravityKula(saldo_inicial=100.0, riesgo_usd_fijo=1.00)

    trades_balam_puro = []
    trades_kula_antigravity = []
    vetos_emitidos = []

    pos_activa_puro = False
    salida_idx_puro = -1

    pos_activa_dual = False
    salida_idx_dual = -1

    total_filas = len(df)
    indices = df.index

    print(f"[*] Analizando {total_filas} velas para {ticker}...")

    for i in range(50, total_filas - 1):
        if pos_activa_puro and i >= salida_idx_puro:
            pos_activa_puro = False
        if pos_activa_dual and i >= salida_idx_dual:
            pos_activa_dual = False

        row = df.iloc[i]
        bias = row["macro_bias"]
        if bias not in ["LONG", "SHORT"]:
            continue

        s_high = row["last_fractal_high"]
        s_low = row["last_fractal_low"]
        s_range = max(0.0001, s_high - s_low)
        atr_val = row["atr"]
        if np.isnan(atr_val) or atr_val <= 0:
            continue

        close_actual = row["close"]
        v_prev1 = df.iloc[i - 1]
        v_prev2 = df.iloc[i - 2]

        es_candidato = False
        lado = None
        entry = df.iloc[i + 1]["open"] if i + 1 < total_filas else close_actual

        if bias == "LONG":
            fibo = (s_high - close_actual) / s_range
            in_zone = 0.45 <= fibo <= 0.75
            bos = (close_actual > v_prev1["high"]) and (close_actual > v_prev2["high"])
            vol_ok = row["rvol"] >= 1.05
            if in_zone and bos and vol_ok:
                es_candidato = True
                lado = "LONG"
                base_low = min(close_actual, v_prev1["low"], v_prev2["low"])
                sl = base_low - (0.85 * atr_val)
                tp = entry + ((entry - sl) * 2.0)

        elif bias == "SHORT":
            fibo = (close_actual - s_low) / s_range
            in_zone = 0.45 <= fibo <= 0.75
            bos = (close_actual < v_prev1["low"]) and (close_actual < v_prev2["low"])
            vol_ok = row["rvol"] >= 1.05
            if in_zone and bos and vol_ok:
                es_candidato = True
                lado = "SHORT"
                base_high = max(close_actual, v_prev1["high"], v_prev2["high"])
                sl = base_high + (0.85 * atr_val)
                tp = entry - ((sl - entry) * 2.0)

        if not es_candidato:
            continue

        # Simular desenlace del trade
        p_exit = df["close"].iloc[min(i + 48, total_filas - 1)]
        exit_bar = min(i + 48, total_filas - 1)
        resultado = "CIERRE_VENTANA"

        for j in range(i + 1, min(i + 49, total_filas)):
            h_j = df["high"].iloc[j]
            l_j = df["low"].iloc[j]
            if lado == "LONG":
                if l_j <= sl:
                    p_exit = sl
                    resultado = "STOP_LOSS"
                    exit_bar = j
                    break
                if h_j >= tp:
                    p_exit = tp
                    resultado = "TAKE_PROFIT"
                    exit_bar = j
                    break
            else:
                if h_j >= sl:
                    p_exit = sl
                    resultado = "STOP_LOSS"
                    exit_bar = j
                    break
                if l_j <= tp:
                    p_exit = tp
                    resultado = "TAKE_PROFIT"
                    exit_bar = j
                    break

        pnl_bruto_pct = ((p_exit - entry) / entry) * 100.0 if lado == "LONG" else ((entry - p_exit) / entry) * 100.0

        # RAMA 1: Balam Puro (Sin Filtro)
        if not pos_activa_puro:
            trades_balam_puro.append({
                "fecha": str(indices[i])[:16],
                "lado": lado,
                "pnl_pct": pnl_bruto_pct,
                "resultado": resultado
            })
            pos_activa_puro = True
            salida_idx_puro = exit_bar

        # RAMA 2: Kula & Balam + Antigravity CIO
        if not pos_activa_dual:
            aprobado, sizing, motivo = arbitro.auditar_candidato(row, lado, entry, sl, tp)
            if aprobado:
                trades_kula_antigravity.append({
                    "fecha": str(indices[i])[:16],
                    "lado": lado,
                    "pnl_pct": pnl_bruto_pct * sizing,
                    "resultado": resultado,
                    "sizing": sizing
                })
                pos_activa_dual = True
                salida_idx_dual = exit_bar
            else:
                vetos_emitidos.append({
                    "fecha": str(indices[i])[:16],
                    "lado": lado,
                    "pnl_evitado": round(pnl_bruto_pct, 2),
                    "motivo": motivo
                })

    # Métricas Estrictas con Fricción Real
    df_pura = pd.DataFrame(trades_balam_puro)
    df_dual = pd.DataFrame(trades_kula_antigravity)

    res_pura = evaluador.calcular_metricas(df_pura, col_pnl_bruto="pnl_pct")
    res_dual = evaluador.calcular_metricas(df_dual, col_pnl_bruto="pnl_pct")

    # Presentación en Consola de Lab
    print("\n" + "=" * 90)
    print("   KULA BALAM // AUDITORÍA DUAL NATIVA: BALAM PURO vs. KULA-BALAM + ANTIGRAVITY CIO")
    print(f"   Activo: {ticker} | Fricción: 0.26% Round-Trip | Exigencia Asimétrica R:R >= 1:2.0")
    print("=" * 90)

    print(f"{'MÉTRICA CUANTITATIVA':<32} | {'BALAM PURO':<24} | {'KULA-BALAM + CIO':<24}")
    print("-" * 90)
    print(f"{'Operaciones Totales':<32} | {res_pura['trades_totales']:<24} | {res_dual['trades_totales']:<24}")
    print(f"{'Win Rate Neto':<32} | {res_pura['win_rate_neto']}%{'':<18} | {res_dual['win_rate_neto']}%{'':<18}")
    print(f"{'Profit Factor Neto':<32} | {res_pura['pf_neto']:<24} | {res_dual['pf_neto']:<24}")
    print(f"{'Ratio R:R Realizado':<32} | {res_pura['rr_promedio_neto']:<24} | {res_dual['rr_promedio_neto']:<24}")
    print(f"{'Retorno Neto Total':<32} | {res_pura['retorno_neto_total_pct']}%{'':<18} | {res_dual['retorno_neto_total_pct']}%{'':<18}")
    print(f"{'Máximo Drawdown':<32} | {res_pura['max_drawdown_pct']}%{'':<18} | {res_dual['max_drawdown_pct']}%{'':<18}")
    print("-" * 90)
    print(f"{'DICTAMEN FINAL':<32} | {res_pura['dictamen'][:24]:<24} | {res_dual['dictamen'][:24]:<24}")
    print("=" * 90)

    # Balance de Vetos
    print(f"\n[+] Total de Señales Vetadas por Antigravity CIO: {len(vetos_emitidos)}")
    if vetos_emitidos:
        trampas = [v for v in vetos_emitidos if v["pnl_evitado"] <= 0]
        ganadas_perdidas = [v for v in vetos_emitidos if v["pnl_evitado"] > 0]
        print(f"    - Trampas evitadas con éxito (Trades que habrían perdido): {len(trampas)}")
        print(f"    - Operaciones ganadoras sacrificadas por prudencia        : {len(ganadas_perdidas)}")
        print("\n[*] Muestra de Vetos Institucionales aplicados:")
        for v in vetos_emitidos[:4]:
            print(f"    • {v['fecha']} ({v['lado']}) [PnL evitado: {v['pnl_evitado']:+.2f}%] -> {v['motivo']}")

    print("\n" + "=" * 90 + "\n")


if __name__ == "__main__":
    def_file = Path("/home/raul/Escritorio/proyectos/kula_balam_ikigai/backtest_lab/data/datos_historicos/binance_BTC_USDT_1h.parquet")
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else def_file

    print(f"[*] Cargando: {ruta.name}")
    df_raw = pd.read_parquet(ruta) if ruta.suffix == ".parquet" else pd.read_csv(ruta)
    df_proc = preparar_datos_balam(df_raw)
    ticker = ruta.stem.replace("binance_", "").replace("yf_", "")
    ejecutar_auditoria_dual(df_proc, ticker=ticker)
