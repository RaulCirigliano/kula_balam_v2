# -*- coding: utf-8 -*-
"""
Auditoría Walk-Forward del Filtro de Derivados (Funding Rate / Open Interest) sobre
donchian_breakout_1h en Cripto 4H (SOL/USDT, ETH/USDT; BTC/USDT como control de robustez).

Metodología (hipótesis PRE-REGISTRADAS, umbrales fijos, sin optimización):
  - Señales: réplica causal de donchian_breakout_1h con los parámetros de producción
    (parametros_por_defecto en backend/estrategias/donchian_breakout_1h.py).
  - Partición: P1 [0-35%] | P2 [35-70%] | OOS ciego [70-100%].
  - Fricción real: get_asset_friction_costs (fee + spread) vía net_return_after_costs.
  - Funding: último fundingRate LIQUIDADO con fundingTime <= cierre de la vela de señal (causal).

Hipótesis:
  H1  SHORT solo si funding_last > 0      (lado largo aún apalancado: combustible para liquidaciones).
  H2  Veto SHORT si funding_last < -0.01% (cortos saturados: riesgo de short squeeze).
  H3  SHORT solo si media funding 24h (3 liquidaciones) > 0.
  L1  Veto LONG si funding_last > +0.03%  (largos sobrecalentados).

Open Interest: Binance solo expone ~30 días de histórico (openInterestHist), insuficiente para
Walk-Forward. Se reporta únicamente como muestra descriptiva.
"""
import sys
import time
import json
from pathlib import Path

import numpy as np
import pandas as pd
import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.quant_risk import get_asset_friction_costs, net_return_after_costs, required_tp_gross_for_rr  # noqa: E402

DATA_DIR = ROOT / "backtest_lab" / "data" / "datos_historicos"
CACHE_DIR = ROOT / "backtest_lab" / "data" / "derivados"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CFG = {
    "donchian_period": 30, "ema_trend_period": 200, "ema_slope_bars": 8,
    "compression_atr_mult": 6.0, "rel_squeeze_mult": 1.15, "volume_ma_mult": 1.20,
    "max_wick_pct": 32.0, "max_bar_atr_mult": 2.6, "max_dist_ema50_atr": 3.2,
    "atr_sl_mult": 1.60, "target_tp_atr_mult": 4.16, "min_rr_ratio": 2.0,
}
TF_MS = 4 * 3600 * 1000


def descargar_funding(symbol_fut: str, start_ms: int) -> pd.Series:
    cache = CACHE_DIR / f"funding_{symbol_fut}.parquet"
    if cache.exists():
        s = pd.read_parquet(cache)["rate"]
        if len(s) and int(s.index[-1].value // 10**6) > int(time.time() * 1000) - 2 * 86400 * 1000:
            return s
    rows, cur = [], start_ms
    with httpx.Client(timeout=15.0) as cli:
        while True:
            r = cli.get("https://fapi.binance.com/fapi/v1/fundingRate",
                        params={"symbol": symbol_fut, "startTime": cur, "limit": 1000})
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            rows.extend(batch)
            last = int(batch[-1]["fundingTime"])
            if len(batch) < 1000:
                break
            cur = last + 1
            time.sleep(0.25)
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["fundingTime"].astype("int64"), unit="ms")
    s = df.set_index("ts")["fundingRate"].astype(float).rename("rate").sort_index()
    s = s[~s.index.duplicated()]
    s.to_frame().to_parquet(cache)
    return s


def simular(df: pd.DataFrame, symbol: str, start_idx: int, end_idx: int) -> list:
    c_ = get_asset_friction_costs(symbol)
    fee, spread = float(c_["fee_pct"]), float(c_["spread_pct"])
    prev_c = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().shift(1)
    rvol = df["volume"] / (df["volume"].shift(1).rolling(20, min_periods=10).mean() + 1e-9)
    rango = (df["high"] - df["low"]).replace(0, 1e-9)
    techo = df[["open", "close"]].max(axis=1)
    suelo = df[["open", "close"]].min(axis=1)
    m_sup = ((df["high"] - techo) / rango) * 100.0
    m_inf = ((suelo - df["low"]) / rango) * 100.0
    ema50 = df["close"].ewm(span=50, adjust=False).mean()
    ema_mac = df["close"].ewm(span=CFG["ema_trend_period"], adjust=False).mean()
    slp = ema_mac - ema_mac.shift(CFG["ema_slope_bars"])
    dist50 = (df["close"] - ema50).abs() / (atr + 1e-9)
    n = CFG["donchian_period"]
    dh = df["high"].shift(1).rolling(n).max()
    dl = df["low"].shift(1).rolling(n).min()
    bw = (dh - dl) / (atr + 1e-9)
    bw_med = bw.shift(1).rolling(60, min_periods=20).median()

    O, H, L, C = (df[k].values for k in ("open", "high", "low", "close"))
    i = max(CFG["ema_trend_period"] + 10, start_idx)
    max_hold = 84
    trades = []
    while i < end_idx - 1:
        a = float(atr.iloc[i])
        if np.isnan(a) or a <= 0 or np.isnan(dh.iloc[i]):
            i += 1
            continue
        o, h, l, c = O[i], H[i], L[i], C[i]
        ok_common = ((h - l) <= CFG["max_bar_atr_mult"] * a and float(rvol.iloc[i]) >= CFG["volume_ma_mult"]
                     and float(dist50.iloc[i]) <= CFG["max_dist_ema50_atr"]
                     and float(bw.iloc[i]) <= CFG["compression_atr_mult"]
                     and (np.isnan(bw_med.iloc[i]) or float(bw.iloc[i]) <= float(bw_med.iloc[i]) * CFG["rel_squeeze_mult"]))
        side = None
        if ok_common:
            e = float(ema_mac.iloc[i])
            s = float(slp.iloc[i]) if not np.isnan(slp.iloc[i]) else 0.0
            if c > dh.iloc[i] and c > o and c > e and s > 0 and m_sup.iloc[i] <= CFG["max_wick_pct"]:
                side = "LONG"
            elif c < dl.iloc[i] and c < o and c < e and s < 0 and m_inf.iloc[i] <= CFG["max_wick_pct"]:
                side = "SHORT"
        if side is None:
            i += 1
            continue
        atr_pct = a / c * 100.0
        sl_pct = round(max(0.75, CFG["atr_sl_mult"] * atr_pct), 2)
        tp_pct = round(max(CFG["target_tp_atr_mult"] * atr_pct,
                           required_tp_gross_for_rr(sl_pct, fee, spread, target_rr=CFG["min_rr_ratio"]) + 0.005), 2)
        sl_px = c * (1 - sl_pct / 100) if side == "LONG" else c * (1 + sl_pct / 100)
        tp_px = c * (1 + tp_pct / 100) if side == "LONG" else c * (1 - tp_pct / 100)
        exit_j, outcome, gross = min(len(df) - 1, i + max_hold), "TIME", 0.0
        for j in range(i + 1, min(len(df), i + max_hold + 1)):
            if side == "LONG":
                if L[j] <= sl_px:
                    outcome, gross, exit_j = "SL", -sl_pct, j; break
                if H[j] >= tp_px:
                    outcome, gross, exit_j = "TP", tp_pct, j; break
            else:
                if H[j] >= sl_px:
                    outcome, gross, exit_j = "SL", -sl_pct, j; break
                if L[j] <= tp_px:
                    outcome, gross, exit_j = "TP", tp_pct, j; break
            exit_j = j
        if outcome == "TIME":
            cj = C[exit_j]
            gross = (cj / c - 1) * 100 if side == "LONG" else (c - cj) / c * 100
        signal_close_ts = df.index[i] + pd.Timedelta(hours=4)
        trades.append({"symbol": symbol, "side": side, "outcome": outcome, "ts": signal_close_ts,
                       "net_pct": net_return_after_costs(gross, fee, spread), "bars": exit_j - i})
        i = exit_j + 1
    return trades


def resumen(tr: list) -> dict:
    if not tr:
        return {"n": 0, "wr": 0.0, "pf": 0.0, "rr": 0.0, "ret": 0.0, "dd": 0.0}
    r = np.array([t["net_pct"] for t in tr])
    w, ls = r[r > 0], r[r <= 0]
    eq = np.cumprod(1 + r / 100.0)
    dd = float(np.max(1 - eq / np.maximum.accumulate(eq)) * 100)
    pf = float(w.sum() / abs(ls.sum())) if ls.sum() != 0 else float("inf")
    rr = float(w.mean() / abs(ls.mean())) if len(w) and len(ls) else 0.0
    return {"n": len(r), "wr": len(w) / len(r) * 100, "pf": pf, "rr": rr, "ret": float((eq[-1] - 1) * 100), "dd": dd}


def fmt(s: dict) -> str:
    return f"N={s['n']:3d} WR={s['wr']:5.1f}% PF={s['pf']:5.2f} RR={s['rr']:4.2f} Ret={s['ret']:+7.2f}% DD={s['dd']:5.1f}%"


def main() -> None:
    simbolos = [("SOL/USDT", "SOLUSDT", True), ("ETH/USDT", "ETHUSDT", True), ("BTC/USDT", "BTCUSDT", False)]
    filtros = {
        "BASE": lambda t: True,
        "H1 short si fund>0": lambda t: t["side"] != "SHORT" or t["f_last"] > 0,
        "H2 veto short fund<-0.01%": lambda t: t["side"] != "SHORT" or t["f_last"] >= -0.0001,
        "H3 short si fund24h>0": lambda t: t["side"] != "SHORT" or t["f_24h"] > 0,
        "L1 veto long fund>+0.03%": lambda t: t["side"] != "LONG" or t["f_last"] <= 0.0003,
    }
    resultados = {}
    for prod_only in (True, False):
        etiqueta = "PRODUCCIÓN (SOL+ETH)" if prod_only else "CONTROL (SOL+ETH+BTC)"
        periodos = {"P1": [], "P2": [], "OOS": []}
        for sym, fut, en_prod in simbolos:
            if prod_only and not en_prod:
                continue
            df = pd.read_parquet(DATA_DIR / f"binance_{sym.replace('/', '_')}_4h.parquet")
            df.columns = [c.lower() for c in df.columns]
            df = df.sort_index().astype(float)
            fund = descargar_funding(fut, int(df.index[0].value // 10**6) - 86400 * 1000)
            f24 = fund.rolling(3, min_periods=1).mean()
            i35, i70 = int(len(df) * 0.35), int(len(df) * 0.70)
            for lbl, a, b in (("P1", 0, i35), ("P2", i35, i70), ("OOS", i70, len(df))):
                for t in simular(df, sym, a, b):
                    pos = fund.index.searchsorted(t["ts"], side="right") - 1
                    t["f_last"] = float(fund.iloc[pos]) if pos >= 0 else 0.0
                    t["f_24h"] = float(f24.iloc[pos]) if pos >= 0 else 0.0
                    periodos[lbl].append(t)
        print(f"\n=================== {etiqueta} · donchian_breakout_1h 4H ===================")
        for nombre, fn in filtros.items():
            p = {k: [t for t in v if fn(t)] for k, v in periodos.items()}
            full = resumen(p["P1"] + p["P2"] + p["OOS"])
            sh = resumen([t for t in p["P1"] + p["P2"] + p["OOS"] if t["side"] == "SHORT"])
            s1, s2, s3 = resumen(p["P1"]), resumen(p["P2"]), resumen(p["OOS"])
            pos = sum(1 for s in (s1, s2, s3) if s["ret"] > 0)
            print(f"  {nombre:28s} | FULL {fmt(full)} | P1 {s1['ret']:+6.2f}%({s1['n']}) P2 {s2['ret']:+6.2f}%({s2['n']}) "
                  f"OOS {s3['ret']:+6.2f}%({s3['n']}) PF_OOS={s3['pf']:.2f} [{pos}/3] | SOLO SHORT {fmt(sh)}")
            resultados[f"{etiqueta}|{nombre}"] = {"full": full, "p1": s1, "p2": s2, "oos": s3, "short": sh, "positivos": pos}
        shorts = [t for v in periodos.values() for t in v if t["side"] == "SHORT"]
        print("  Detalle SHORTs (ts, símbolo, funding_last %, net %):")
        for t in shorts:
            print(f"    {t['ts']} {t['symbol']:9s} f={t['f_last']*100:+.4f}% f24={t['f_24h']*100:+.4f}% net={t['net_pct']:+.2f}% {t['outcome']}")

    # Open Interest: solo descriptivo (~30 días)
    try:
        with httpx.Client(timeout=15.0) as cli:
            for fut in ("SOLUSDT", "ETHUSDT"):
                r = cli.get("https://fapi.binance.com/futures/data/openInterestHist",
                            params={"symbol": fut, "period": "4h", "limit": 500})
                r.raise_for_status()
                d = r.json()
                print(f"\n  OI {fut}: {len(d)} velas 4H disponibles ({len(d)*4/24:.1f} días) -> insuficiente para Walk-Forward.")
    except Exception as e:  # noqa: BLE001
        print(f"  OI no disponible: {e}")

    out = ROOT / "backtest_lab" / "historial" / "auditoria_filtro_derivados.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(resultados, indent=2, default=float), encoding="utf-8")
    print(f"\nResultados guardados en {out}")


if __name__ == "__main__":
    main()
