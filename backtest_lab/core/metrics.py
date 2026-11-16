"""
Módulo: backtest_lab/core/metrics.py
Proyecto: Kula Balam / Backtest Lab
Objetivo: Auditor Cuantitativo Estricto de Fricción, Asimetría R:R, Partición IS/OOS y Drawdown.
"""

from typing import Dict, Tuple, Optional, List, Any
import numpy as np
import pandas as pd


class EvaluadorCuantitativo:
    """
    Auditor de métricas con deducción obligatoria de fricción de mercado
    (comisión + slippage + spread) y exigencia de asimetría matemática R:R >= 1:2.0.
    """

    def __init__(
        self,
        comision_pct: float = 0.0008,  # 0.08% por lado (taker institucional)
        slippage_pct: float = 0.0005,  # 0.05% slippage estimado por lado
    ):
        self.comision_pct = comision_pct
        self.slippage_pct = slippage_pct
        # Fricción total ida y vuelta (Round-Trip)
        self.friccion_roundtrip = 2.0 * (self.comision_pct + self.slippage_pct)

    def particionar_is_oos(
        self, df: pd.DataFrame, ratio_is: float = 0.70
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Divide el dataset cronológicamente en:
        - In-Sample (IS, 70% por defecto): Calibración y optimización.
        - Out-of-Sample (OOS, 30% por defecto): Auditoría ciega sin sesgo de sobreajuste.
        """
        corte = int(len(df) * ratio_is)
        df_is = df.iloc[:corte].copy()
        df_oos = df.iloc[corte:].copy()
        return df_is, df_oos

    def calcular_metricas(
        self,
        df_trades: pd.DataFrame,
        col_pnl_bruto: str = "pnl_pct",
        ya_descuenta_friccion: bool = False,
        timeframe: str = "4h",
    ) -> Dict:
        """
        Calcula las métricas cuantitativas estrictas a partir del registro de trades.
        """
        if df_trades.empty:
            mc_empty = run_monte_carlo_bootstrap([])
            suff_empty = check_sample_sufficiency(0, timeframe=timeframe)
            return {
                "status": "SIN_TRADES",
                "aprobado": False,
                "apta_fondeo": False,
                "fondeo_dictamen": "❌ NO APTA (Sin trades)",
                "trades_totales": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "w_l_be": "0W-0L-0BE",
                "pf_neto": 0.0,
                "win_rate_neto": 0.0,
                "rr_promedio_neto": 0.0,
                "max_drawdown_pct": 0.0,
                "max_daily_dd_pct": 0.0,
                "max_losing_streak": 0,
                "prop_firm_ok": False,
                "prop_firm_semaforo": "🔴 RIESGO DE DESCALIFICACIÓN POR DRAWDOWN (Sin trades)",
                "retorno_neto_total_pct": 0.0,
                "sortino_ratio": 0.0,
                "mc_max_dd_95_pct": 0.0,
                "monte_carlo": mc_empty,
                "sample_sufficiency": suff_empty,
                "dictamen": "❌ [DESCARTADA (Sin trades generados)]",
            }

        # Vector de PnL en fracción decimal
        vals = df_trades[col_pnl_bruto].astype(float).values
        if "pct" in col_pnl_bruto.lower() or "porc" in col_pnl_bruto.lower() or (np.abs(vals) > 1.0).any():
            pnl_raw = vals / 100.0
        else:
            pnl_raw = vals

        if ya_descuenta_friccion:
            pnl_neto_dec = pnl_raw
        else:
            pnl_neto_dec = pnl_raw - self.friccion_roundtrip

        # Separar ganancias y pérdidas netas
        ganadores = pnl_neto_dec[pnl_neto_dec > 0]
        perdedores = pnl_neto_dec[pnl_neto_dec < 0]

        # Conteo con tolerancia 1e-6 (W - L - BE)
        wins = int((pnl_neto_dec > 1e-6).sum())
        losses = int((pnl_neto_dec < -1e-6).sum())
        draws = int((np.abs(pnl_neto_dec) <= 1e-6).sum())
        w_l_be = f"{wins}W-{losses}L-{draws}BE"

        suma_ganancias = float(ganadores.sum())
        suma_perdidas = float(abs(perdedores.sum()))

        # Profit Factor Neto
        pf_neto = (
            round(suma_ganancias / (suma_perdidas + 1e-9), 2)
            if suma_perdidas > 0
            else (99.0 if suma_ganancias > 0 else 0.0)
        )

        # Win Rate Neto
        total_trades = len(pnl_neto_dec)
        win_rate = round((len(ganadores) / total_trades) * 100.0, 2)

        # Asimetría media realizada (Payoff Ratio / R:R promedio neto)
        avg_win = float(ganadores.mean()) if len(ganadores) > 0 else 0.0
        avg_loss = float(abs(perdedores.mean())) if len(perdedores) > 0 else 1e-9
        rr_promedio = round(avg_win / avg_loss, 2)

        # Curva de equidad y Drawdown Máximo
        equity_curve = np.cumprod(1.0 + pnl_neto_dec)
        peak = np.maximum.accumulate(equity_curve)
        drawdowns = (equity_curve - peak) / peak
        max_dd_pct = round(abs(float(drawdowns.min())) * 100.0, 2) if len(drawdowns) > 0 else 0.0

        # Racha máxima de pérdidas consecutivas (Losing Streak)
        max_losing_streak = 0
        cur_streak = 0
        for pnl in pnl_neto_dec:
            if pnl < -1e-6:
                cur_streak += 1
                if cur_streak > max_losing_streak:
                    max_losing_streak = cur_streak
            else:
                cur_streak = 0

        # Drawdown diario máximo (Prop Firm Daily DD <= 4.5%)
        max_daily_dd_pct = 0.0
        if "fecha" in df_trades.columns:
            try:
                fechas = df_trades["fecha"].astype(str).str.slice(0, 10)
                s_pnl = pd.Series(np.asarray(pnl_neto_dec, dtype=float), index=fechas.values)
                pnl_por_dia = s_pnl.groupby(level=0).apply(
                    lambda s: float(np.cumprod(1.0 + s.values)[-1] - 1.0) * 100.0
                )
                peor_dia = float(pnl_por_dia.min()) if not pnl_por_dia.empty else 0.0
                if peor_dia < 0.0:
                    max_daily_dd_pct = round(abs(peor_dia), 2)
            except Exception:
                max_daily_dd_pct = 0.0

        # Retorno total acumulado neto
        retorno_total_pct = round(float((equity_curve[-1] - 1.0) * 100.0), 2) if len(equity_curve) > 0 else 0.0

        # Dictamen algorítmico estricto
        # Exigencias mínimas de ventaja matemática real:
        # 1. Asimetría R:R realizada >= 2.0 (o R:R >= 1.5 con Win Rate > 55%)
        # 2. Profit Factor neto >= 1.5
        # 3. Mínimo estadístico de 20 operaciones
        # 4. Máximo Drawdown < 20%
        aprobado = (
            (pf_neto >= 1.5)
            and (rr_promedio >= 2.0 or (rr_promedio >= 1.5 and win_rate >= 55.0))
            and (total_trades >= 20)
            and (max_dd_pct <= 20.0)
        )

        # Evaluación de Aptitud para Cuentas de Fondeo (Prop Firm Challenge FTMO/Topstep/Apex):
        # 1. Máximo Drawdown Total <= 8.0% (Umbral estricto para no quemar la cuenta)
        # 2. Profit Factor Neto >= 1.50
        # 3. Asimetría R:R Realizada >= 1.50
        # 4. Retorno Neto Total >= 8.0% (Objetivo de ganancia de fase 1)
        # 5. Mínimo de trades >= 15
        fallas_fondeo = []
        if max_dd_pct > 8.0:
            fallas_fondeo.append(f"Max DD {max_dd_pct}% > 8.0%")
        if max_daily_dd_pct > 4.5:
            fallas_fondeo.append(f"Daily DD {max_daily_dd_pct}% > 4.5%")
        if pf_neto < 1.50:
            fallas_fondeo.append(f"PF {pf_neto} < 1.50")
        if rr_promedio < 1.50:
            fallas_fondeo.append(f"R:R {rr_promedio} < 1.50")
        if retorno_total_pct < 8.0:
            fallas_fondeo.append(f"Ret {retorno_total_pct}% < 8% target")
        if total_trades < 15:
            fallas_fondeo.append(f"Muestra N={total_trades} < 15")

        apta_fondeo = len(fallas_fondeo) == 0
        if apta_fondeo:
            fondeo_dictamen = "✅ APTA (DD ≤ 8%, Daily DD ≤ 4.5%, PF ≥ 1.5, Target ≥ 8%)"
        else:
            fondeo_dictamen = f"❌ NO APTA ({', '.join(fallas_fondeo[:2])})"

        # Semáforo Prop Firm específico
        prop_firm_ok = (max_daily_dd_pct <= 4.5) and (max_dd_pct <= 8.0) and (total_trades >= 15)
        if prop_firm_ok:
            prop_firm_semaforo = "🟢 APTO FONDEO (Daily DD y Max DD en regla)"
        else:
            motivos_pf = []
            if max_daily_dd_pct > 4.5:
                motivos_pf.append(f"Daily DD {max_daily_dd_pct}% > 4.5%")
            if max_dd_pct > 8.0:
                motivos_pf.append(f"Max DD {max_dd_pct}% > 8.0%")
            if total_trades < 15:
                motivos_pf.append(f"N={total_trades} < 15")
            det_pf = f" ({', '.join(motivos_pf)})" if motivos_pf else ""
            prop_firm_semaforo = f"🔴 RIESGO DE DESCALIFICACIÓN POR DRAWDOWN{det_pf}"

        if aprobado:
            dictamen = "✅ [POSITIVA (Asimetría y Robustez Validadas)]"
        elif pf_neto >= 1.2 and rr_promedio >= 1.3:
            dictamen = "⚠️ [NEUTRA (Marginal o Muestra Insuficiente)]"
        else:
            dictamen = "❌ [DESCARTADA (Falla Asimetría, PF o Drawdown)]"

        pnl_neto_list = [float(x) for x in pnl_neto_dec]
        sortino_val = calculate_sortino_ratio(pnl_neto_list)
        mc_res = run_monte_carlo_bootstrap(pnl_neto_list, n_sims=1000, seed=42)
        suff_res = check_sample_sufficiency(total_trades, timeframe=timeframe)

        return {
            "status": "OK",
            "aprobado": aprobado,
            "apta_fondeo": apta_fondeo,
            "fondeo_dictamen": fondeo_dictamen,
            "prop_firm_ok": prop_firm_ok,
            "prop_firm_semaforo": prop_firm_semaforo,
            "trades_totales": total_trades,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "w_l_be": w_l_be,
            "pf_neto": pf_neto,
            "win_rate_neto": win_rate,
            "rr_promedio_neto": rr_promedio,
            "max_drawdown_pct": max_dd_pct,
            "max_daily_dd_pct": max_daily_dd_pct,
            "max_losing_streak": max_losing_streak,
            "retorno_neto_total_pct": retorno_total_pct,
            "friccion_roundtrip_pct": round(self.friccion_roundtrip * 100.0, 3),
            "sortino_ratio": sortino_val,
            "mc_max_dd_95_pct": mc_res["mc_max_dd_95_pct"],
            "monte_carlo": mc_res,
            "sample_sufficiency": suff_res,
            "dictamen": dictamen,
        }

    def imprimir_reporte(self, metricas: Dict, titulo: str = "AUDITORÍA CUANTITATIVA RIGUROSA"):
        """Imprime un informe en consola con formato formal para el Backtest Lab."""
        ancho = 68
        print("\n" + "=" * ancho)
        print(f" {titulo.center(ancho - 2)}")
        print("=" * ancho)
        print(f" Trades Evaluados   : {metricas.get('trades_totales', 0)}")
        print(f" Fricción Aplicada  : {metricas.get('friccion_roundtrip_pct', 0.0)}% por trade (Ida + Vuelta)")
        print(f" Profit Factor Neto : {metricas.get('pf_neto', 0.0)}")
        print(f" Win Rate Neto      : {metricas.get('win_rate_neto', 0.0)}%")
        print(f" Ratio R:R Realizado: {metricas.get('rr_promedio_neto', 0.0)} (Exigencia >= 2.0)")
        print(f" Retorno Neto Total : {metricas.get('retorno_neto_total_pct', 0.0)}%")
        print(f" Drawdown Máximo    : {metricas.get('max_drawdown_pct', 0.0)}%")
        print(f" Apta Cuentas Fondeo: {metricas.get('fondeo_dictamen', 'N/A')}")
        print("-" * ancho)
        print(f" DICTAMEN FINAL     : {metricas.get('dictamen', 'N/A')}")
        print("=" * ancho + "\n")


def calculate_sortino_ratio(
    trades_pnl_pct: List[float],
    target_return: float = 0.0,
    periods_per_year: float = 252.0
) -> float:
    """
    Calcula el Ratio Sortino penalizando únicamente la volatilidad negativa (downside deviation).
    trades_pnl_pct: Lista de retornos porcentuales en tanto por uno (ej. 0.025 para +2.5%) o en % (se normaliza).
    """
    if not trades_pnl_pct or len(trades_pnl_pct) < 2:
        return 0.0

    arr = np.asarray(trades_pnl_pct, dtype=np.float64)
    if np.max(np.abs(arr)) > 2.0:
        arr = arr / 100.0

    mean_ret = np.mean(arr) - target_return
    downside_diff = np.minimum(0.0, arr - target_return)
    downside_std = np.sqrt(np.mean(np.square(downside_diff)))

    if downside_std < 1e-6:
        return 99.99 if mean_ret > 0 else 0.0

    scale = np.sqrt(min(len(arr), periods_per_year))
    sortino = (mean_ret / downside_std) * scale
    return round(float(np.clip(sortino, -99.99, 99.99)), 2)


def run_monte_carlo_bootstrap(
    trades_pnl_pct: List[float],
    n_sims: int = 1000,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Simulación Monte Carlo vectorizada con reemplazo (Bootstrapping) en < 10ms.
    Retorna el Max Drawdown en el percentil 95 de peor escenario y el retorno en percentil 5.
    """
    n_trades = len(trades_pnl_pct) if trades_pnl_pct else 0
    if n_trades < 5:
        return {
            "mc_valid": False,
            "mc_sims": 0,
            "mc_max_dd_95_pct": 0.0,
            "mc_median_dd_pct": 0.0,
            "mc_ret_p05_pct": 0.0,
            "mc_ruin_prob_8pct": 0.0
        }

    arr = np.asarray(trades_pnl_pct, dtype=np.float64)
    if np.max(np.abs(arr)) > 2.0:
        arr = arr / 100.0

    arr = np.clip(arr, -0.99, 10.0)

    rng = np.random.default_rng(seed)
    sampled_returns = rng.choice(arr, size=(n_sims, n_trades), replace=True)

    equity_curves = np.empty((n_sims, n_trades + 1), dtype=np.float64)
    equity_curves[:, 0] = 1.0
    np.cumprod(1.0 + sampled_returns, axis=1, out=equity_curves[:, 1:])

    running_peaks = np.maximum.accumulate(equity_curves, axis=1)
    drawdowns = (running_peaks - equity_curves) / running_peaks
    max_dd_per_sim = np.max(drawdowns, axis=1) * 100.0

    final_returns_pct = (equity_curves[:, -1] - 1.0) * 100.0

    mc_dd_95 = float(np.percentile(max_dd_per_sim, 95))
    mc_dd_50 = float(np.percentile(max_dd_per_sim, 50))
    mc_ret_05 = float(np.percentile(final_returns_pct, 5))
    ruin_prob_8pct = float(np.mean(max_dd_per_sim > 8.0) * 100.0)

    return {
        "mc_valid": True,
        "mc_sims": n_sims,
        "mc_max_dd_95_pct": round(mc_dd_95, 2),
        "mc_median_dd_pct": round(mc_dd_50, 2),
        "mc_ret_p05_pct": round(mc_ret_05, 2),
        "mc_ruin_prob_8pct": round(ruin_prob_8pct, 2)
    }


def check_sample_sufficiency(n_trades: int, timeframe: str = "1h") -> Dict[str, Any]:
    """
    Verifica si la muestra de operaciones cerrada tiene significancia estadística según el timeframe.
    """
    tf_clean = str(timeframe).lower().strip()
    is_intraday_fast = any(tf_clean.endswith(x) or tf_clean == x for x in ("1m", "3m", "5m", "15m", "30m"))
    min_required = 100 if is_intraday_fast else 30
    return {
        "sample_sufficiency_ok": bool(n_trades >= min_required),
        "n_trades_evaluated": int(n_trades),
        "min_trades_required": int(min_required)
    }


def enrich_institutional_metrics(
    base_metrics: Dict[str, Any],
    trades_pnl_pct: List[float],
    timeframe: str = "4h"
) -> Dict[str, Any]:
    """Extensor aditivo no destructivo para enriquecer diccionarios de métricas."""
    out = dict(base_metrics) if base_metrics else {}
    pnl_list = list(trades_pnl_pct) if trades_pnl_pct else []
    mc = run_monte_carlo_bootstrap(pnl_list)
    suff = check_sample_sufficiency(len(pnl_list), timeframe=timeframe)
    out["sortino_ratio"] = calculate_sortino_ratio(pnl_list)
    out["mc_max_dd_95_pct"] = mc["mc_max_dd_95_pct"]
    out["monte_carlo"] = mc
    out["sample_sufficiency"] = suff
    return out

