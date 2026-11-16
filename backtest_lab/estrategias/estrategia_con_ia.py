"""
Script: estrategia_con_ia.py
Proyecto: Kula Balam / Backtest Lab
Objetivo: Plantilla Modular para auditar cualquier Fórmula Matemática arbitrada por IA.
Instrucciones:
  1. Configura 'INSTRUCCIONES_IA' arriba.
  2. Pega tu fórmula matemática en 'tu_formula_matematica(df, i)'.
  3. No necesitas modificar nada más del motor inferior.
"""

import sys
from pathlib import Path
from typing import Dict, Tuple

# Inyectar paths del entorno
BASE_LAB_DIR = Path(__file__).resolve().parent.parent
BASE_PROJ_DIR = BASE_LAB_DIR.parent
for p in [str(BASE_LAB_DIR), str(BASE_PROJ_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
import pandas as pd
from core.metrics import EvaluadorCuantitativo


# =============================================================================
# BLOQUE 1: INSTRUCCIONES Y DIRECTIVAS DE LA IA (CEREBRO ANTIGRAVITY CIO)
# Activa con True o desactiva con False las reglas que quieras aplicar:
# =============================================================================
INSTRUCCIONES_IA = {
    # -------------------------------------------------------------------------
    # TILDES DE ACTIVACIÓN (True = Activo | False = Ignorado / Opcional)
    # -------------------------------------------------------------------------
    "activar_filtro_mechas": True,          # ¿Vetar trampas de absorción con mechas?
    "activar_filtro_sobreextension": False, # ¿Vetar si el precio está lejos de la media?
    "activar_filtro_volumen": False,        # ¿Exigir volumen relativo (RVOL)?
    "activar_asimetria_estricta": True,     # ¿Exigir asimetría R:R >= 1:2.0?

    # Parámetros numéricos (solo aplican si su tilde está en True arriba)
    "asimetria_rr_minima": 2.0,             # Ratio R:R mínimo
    "max_mecha_rechazo_pct": 35.0,          # % máximo de mecha en contra permitida
    "max_distancia_ema_atrs": 3.0,          # Distancia máxima en ATRs de la EMA
    "rvol_minimo_exigido": 1.15,            # RVOL mínimo institucional
}


# =============================================================================
# BLOQUE 2: AQUÍ PEGAS TU FÓRMULA MATEMÁTICA EN PYTHON
# Modifica esta función con tus reglas de entrada, Stop Loss y Take Profit.
# =============================================================================
def tu_formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, str, float, float]:
    """
    Recibe el dataframe 'df' con todos los indicadores y el índice actual 'i'.
    Devuelve:
      - es_candidato (bool): True si tu matemática dio señal de compra o venta.
      - lado (str): "LONG" para compras, "SHORT" para ventas (o None).
      - sl (float): Precio exacto de Stop Loss.
      - tp (float): Precio exacto de Take Profit.
    """
    row = df.iloc[i]
    close = row["close"]
    atr = row["atr"] if not np.isnan(row["atr"]) and row["atr"] > 0 else (close * 0.01)

    # -------------------------------------------------------------------------
    # EJEMPLO: RUPTURA DONCHIAN (Pega aquí tus condiciones: RSI, Medias, Fibo, etc.)
    # -------------------------------------------------------------------------
    donchian_alto = df["high"].iloc[max(0, i - 20):i].max()
    donchian_bajo = df["low"].iloc[max(0, i - 20):i].min()

    rr_obj = INSTRUCCIONES_IA.get("asimetria_rr_minima", 2.0)

    # 1. Regla de COMPRA (LONG)
    if close > donchian_alto:
        sl = close - (1.0 * atr)                      # Stop Loss a 1.0 ATR
        tp = close + (rr_obj * (close - sl))          # TP a R:R objetivo
        return True, "LONG", sl, tp

    # 2. Regla de VENTA (SHORT)
    elif close < donchian_bajo:
        sl = close + (1.0 * atr)                      # Stop Loss a 1.0 ATR
        tp = close - (rr_obj * (sl - close))          # TP a R:R objetivo
        return True, "SHORT", sl, tp

    # Sin señal en esta vela
    return False, None, 0.0, 0.0


# =============================================================================
# BLOQUE 3: ÁRBITRO AUTOMÁTICO DE IA (OBEDECE LAS TILDES DEL BLOQUE 1)
# =============================================================================
class ArbitroIA:
    def __init__(self, directivas: Dict):
        self.d = directivas

    def auditar_senal(self, fila: pd.Series, lado: str, entry: float, sl: float, tp: float) -> Tuple[bool, float, str]:
        riesgo = abs(entry - sl)
        recompensa = abs(tp - entry)
        rr = recompensa / (riesgo + 1e-9)

        # 1. Asimetría R:R (opcional por tilde)
        if self.d.get("activar_asimetria_estricta", True):
            rr_min = self.d.get("asimetria_rr_minima", 2.0)
            if rr < (rr_min - 1e-4):
                return False, 0.0, f"VETO Asimetría R:R ({rr:.2f} < 1:{rr_min})"

        # 2. Mechas Trampa (opcional por tilde)
        if self.d.get("activar_filtro_mechas", False):
            max_m = self.d.get("max_mecha_rechazo_pct", 35.0)
            m_sup = fila.get("mecha_superior_pct", 0.0)
            m_inf = fila.get("mecha_inferior_pct", 0.0)
            if lado == "LONG" and m_sup > max_m:
                return False, 0.0, f"VETO Mecha superior ({m_sup:.1f}% > {max_m}%)"
            if lado == "SHORT" and m_inf > max_m:
                return False, 0.0, f"VETO Mecha inferior ({m_inf:.1f}% > {max_m}%)"

        # 3. Sobreextensión (opcional por tilde)
        if self.d.get("activar_filtro_sobreextension", False):
            max_dist = self.d.get("max_distancia_ema_atrs", 3.0)
            dist_val = fila.get("dist_ema_atrs", 0.0)
            if dist_val > max_dist:
                return False, 0.0, f"VETO Sobreextensión ({dist_val:.1f} ATRs > {max_dist})"

        # 4. Volumen (opcional por tilde)
        if self.d.get("activar_filtro_volumen", False):
            min_rvol = self.d.get("rvol_minimo_exigido", 1.15)
            rvol_val = fila.get("rvol", 1.0)
            if rvol_val < min_rvol:
                return False, 0.0, f"VETO Volumen débil ({rvol_val:.2f}x < {min_rvol}x)"

        return True, 1.0, "AUTORIZADO por Antigravity CIO"


# =============================================================================
# BLOQUE 4: MOTOR DE DATOS Y SIMULACIÓN
# =============================================================================
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

    # Indicadores estándar para que los use tu fórmula
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
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
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
    df["dist_ema_atrs"] = (df["close"] - df["ema_50"]).abs() / (df["atr"] + 1e-9)

    return df


def simular(df: pd.DataFrame, ticker: str):
    evaluador = EvaluadorCuantitativo(comision_pct=0.0008, slippage_pct=0.0005)
    arbitro = ArbitroIA(INSTRUCCIONES_IA)

    trades_pura = []
    trades_ia = []
    vetos_ia = []

    pos_pura = False
    exit_idx_pura = -1
    pos_ia = False
    exit_idx_ia = -1

    total = len(df)
    indices = df.index

    for i in range(50, total - 1):
        if pos_pura and i >= exit_idx_pura:
            pos_pura = False
        if pos_ia and i >= exit_idx_ia:
            pos_ia = False

        # 1. EVALUAR TU FÓRMULA MATEMÁTICA
        es_candidato, lado, sl, tp = tu_formula_matematica(df, i)
        if not es_candidato:
            continue

        entry = df.iloc[i + 1]["open"] if i + 1 < total else df.iloc[i]["close"]

        # Simular desenlace futuro
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

        # REGISTRO 1: TU FÓRMULA MATEMÁTICA PURA
        if not pos_pura:
            trades_pura.append({"fecha": str(indices[i])[:16], "pnl_pct": pnl_bruto})
            pos_pura = True
            exit_idx_pura = exit_bar

        # REGISTRO 2: TU FÓRMULA + ÁRBITRO IA ANTIGRAVITY
        if not pos_ia:
            ok, sizing, motivo = arbitro.auditar_senal(df.iloc[i], lado, entry, sl, tp)
            if ok:
                trades_ia.append({"fecha": str(indices[i])[:16], "pnl_pct": pnl_bruto * sizing})
                pos_ia = True
                exit_idx_ia = exit_bar
            else:
                vetos_ia.append({"fecha": str(indices[i])[:16], "pnl_evitado": round(pnl_bruto, 2), "motivo": motivo})

    # Resumen y Reporte
    df_p = pd.DataFrame(trades_pura)
    df_i = pd.DataFrame(trades_ia)

    res_p = evaluador.calcular_metricas(df_p, col_pnl_bruto="pnl_pct")
    res_i = evaluador.calcular_metricas(df_i, col_pnl_bruto="pnl_pct")

    print("\n" + "=" * 90)
    print(f"   LAB: TU FÓRMULA MATEMÁTICA vs. TU FÓRMULA ARBITRADA POR IA ANTIGRAVITY")
    print(f"   Activo: {ticker} | Fricción: 0.26% Round-Trip | R:R Exigido: >= 1:{INSTRUCCIONES_IA['asimetria_rr_minima']}")
    print("=" * 90)
    print(f"{'MÉTRICA CUANTITATIVA':<32} | {'FÓRMULA PURA':<24} | {'FÓRMULA + IA ANTIGRAVITY':<24}")
    print("-" * 90)
    print(f"{'Operaciones Totales':<32} | {res_p['trades_totales']:<24} | {res_i['trades_totales']:<24}")
    print(f"{'Win Rate Neto':<32} | {res_p['win_rate_neto']}%{'':<18} | {res_i['win_rate_neto']}%{'':<18}")
    print(f"{'Profit Factor Neto':<32} | {res_p['pf_neto']:<24} | {res_i['pf_neto']:<24}")
    print(f"{'Ratio R:R Realizado':<32} | {res_p['rr_promedio_neto']:<24} | {res_i['rr_promedio_neto']:<24}")
    print(f"{'Retorno Neto Total':<32} | {res_p['retorno_neto_total_pct']}%{'':<18} | {res_i['retorno_neto_total_pct']}%{'':<18}")
    print(f"{'Máximo Drawdown':<32} | {res_p['max_drawdown_pct']}%{'':<18} | {res_i['max_drawdown_pct']}%{'':<18}")
    print("-" * 90)
    print(f"{'DICTAMEN':<32} | {res_p['dictamen'][:24]:<24} | {res_i['dictamen'][:24]:<24}")
    print("=" * 90)

    print(f"\n[+] Total de Señales Vetadas por la IA: {len(vetos_ia)}")
    if vetos_ia:
        trampas = [v for v in vetos_ia if v["pnl_evitado"] <= 0]
        buenas = [v for v in vetos_ia if v["pnl_evitado"] > 0]
        print(f"    - Pérdidas / Trampas evitadas con éxito : {len(trampas)}")
        print(f"    - Ganancias sacrificadas por prudencia  : {len(buenas)}")
        print("\n[*] Últimos Vetos de la IA:")
        for v in vetos_ia[-3:]:
            print(f"    • {v['fecha']} [PnL evitado: {v['pnl_evitado']:+.2f}%] -> {v['motivo']}")
    print("\n" + "=" * 90 + "\n")


if __name__ == "__main__":
    def_file = Path("/home/raul/Escritorio/proyectos/kula_balam_ikigai/backtest_lab/data/datos_historicos/binance_BTC_USDT_1h.parquet")
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else def_file
    print(f"[*] Cargando: {ruta.name}")
    df_raw = pd.read_parquet(ruta) if ruta.suffix == ".parquet" else pd.read_csv(ruta)
    df_prep = preparar_mercado(df_raw)
    ticker = ruta.stem.replace("binance_", "").replace("yf_", "")
    simular(df_prep, ticker=ticker)
