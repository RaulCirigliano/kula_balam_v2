# -*- coding: utf-8 -*-
"""
Estrategia Multitemporal Presencial 15M (1H Contexto/Fibo -> 15M Cruce EMA15)
Para supervisión presencial del operador en vivo (ETH/USDT y Cripto 15m).
Nota transparente Lab: PF=2.02-2.10, MC DD 95%=3.47%, WFE 3/5-4/5 en 187 días (N=14-21),
pero en prueba larga de 3 años (106k velas) cae al forzar N>=100 -> requiere filtro presencial del operador.
"""
from typing import Tuple, Optional
import numpy as np
import pandas as pd

DATASET = "binance_ETH_USDT_15m.parquet"
ARBITRO_IA = "arbitro_mtf_presencial.py"
MAX_BARS_HOLD = 144
BREAKEVEN_RR = 0.0
TRAILING_ATR_MULT = 0.0
ATR_SLIPPAGE_K = 0.05

def _net_ret(gross_pct: float, fee: float, spread: float) -> float:
    e = (1.0 + fee / 100.0) * (1.0 + spread / 100.0)
    x = (1.0 - fee / 100.0) * (1.0 - spread / 100.0)
    return ((1.0 + gross_pct / 100.0) * x / e - 1.0) * 100.0


def _net_rr(tp_gross_pct: float, sl_gross_pct: float, fee: float = 0.10, spread: float = 0.05) -> float:
    tp_n = _net_ret(tp_gross_pct, fee, spread)
    sl_n = _net_ret(-abs(sl_gross_pct), fee, spread)
    if sl_n >= 0 or tp_n <= 0:
        return 0.0
    return tp_n / abs(sl_n)


def _adx_series(h: pd.Series, l: pd.Series, c: pd.Series, period: int = 14) -> pd.Series:
    up = h.diff()
    dn = -l.diff()
    plus_dm = up.where((up > dn) & (up > 0), 0.0)
    minus_dm = dn.where((dn > up) & (dn > 0), 0.0)
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr_s = tr.ewm(alpha=1.0 / period, adjust=False).mean().replace(0, np.nan)
    plus_di = 100.0 * (plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_s)
    minus_di = 100.0 * (minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_s)
    dx = (100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0.0)
    return dx.ewm(alpha=1.0 / period, adjust=False).mean().fillna(0.0)


def _pos_extremes(df_sub: pd.DataFrame, window: int):
    h_arr = df_sub["high"].values
    l_arr = df_sub["low"].values
    n = len(df_sub)
    hp = np.zeros(n, dtype=int)
    lp = np.zeros(n, dtype=int)
    for k in range(n):
        s = max(0, k - window + 1)
        hp[k] = int(np.argmax(h_arr[s:k + 1]))
        lp[k] = int(np.argmin(l_arr[s:k + 1]))
    return hp, lp


def _ensure_dt_index(df: pd.DataFrame) -> Optional[pd.DatetimeIndex]:
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")
    for col in ("timestamp", "datetime", "date", "time"):
        if col in df.columns:
            s = df[col]
            if pd.api.types.is_numeric_dtype(s):
                unit = "ms" if float(s.iloc[0]) > 1e11 else "s"
                idx = pd.to_datetime(s, unit=unit, utc=True, errors="coerce")
            else:
                idx = pd.to_datetime(s, utc=True, errors="coerce")
            if idx.notna().all():
                return pd.DatetimeIndex(idx)
    return None


def _map_closed_htf(df_htf: pd.DataFrame, cols: list, cur_idx: pd.DatetimeIndex, prefix: str, target_df: pd.DataFrame) -> None:
    htf_ns = df_htf.index.asi8
    cur_ns = cur_idx.asi8
    pos = np.searchsorted(htf_ns, cur_ns, side="right") - 2
    valid = pos >= 0
    safe_pos = np.clip(pos, 0, max(0, len(df_htf) - 1))
    for c_name in cols:
        arr = df_htf[c_name].to_numpy(dtype=float)
        mapped = np.where(valid, arr[safe_pos], np.nan)
        target_df[f"{prefix}{c_name}"] = mapped


def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_mtf_15m_init" not in df.columns:
        dt_idx = _ensure_dt_index(df)
        if dt_idx is None or len(df) < 325:
            df["_mtf_15m_bad"] = True
            df["_mtf_15m_init"] = True
            return False, None, 0.0, 0.0

        df_work = pd.DataFrame({
            "open": df["open"].astype(float).values,
            "high": df["high"].astype(float).values,
            "low": df["low"].astype(float).values,
            "close": df["close"].astype(float).values,
            "volume": df["volume"].astype(float).values if "volume" in df.columns else np.ones(len(df)),
        }, index=dt_idx)

        agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        df_1h = df_work.resample("1h", label="left", closed="left").agg(agg).dropna()
        if len(df_1h) < 55:
            df["_mtf_15m_bad"] = True
            df["_mtf_15m_init"] = True
            return False, None, 0.0, 0.0

        p_c1 = df_1h["close"].shift(1)
        tr1 = pd.concat([df_1h["high"] - df_1h["low"], (df_1h["high"] - p_c1).abs(), (df_1h["low"] - p_c1).abs()], axis=1).max(axis=1)
        df_1h["atr1"] = tr1.rolling(14).mean().bfill()
        df_1h["ema50"] = df_1h["close"].ewm(span=50, adjust=False).mean()
        df_1h["ema50_prev"] = df_1h["ema50"].shift(4)
        df_1h["adx"] = _adx_series(df_1h["high"], df_1h["low"], df_1h["close"], 14)
        df_1h["sw_h"] = df_1h["high"].rolling(36).max()
        df_1h["sw_l"] = df_1h["low"].rolling(36).min()
        hp_hi, lp_hi = _pos_extremes(df_1h, 36)
        df_1h["bull_imp"] = (hp_hi >= lp_hi).astype(float)
        above_hi = (df_1h["close"] > df_1h["ema50"]).astype(int)
        df_1h["crosses"] = above_hi.diff().abs().fillna(0.0).rolling(6).sum()
        e12_1 = df_1h["close"].ewm(span=12, adjust=False).mean()
        e26_1 = df_1h["close"].ewm(span=26, adjust=False).mean()
        m1 = e12_1 - e26_1
        s1 = m1.ewm(span=9, adjust=False).mean()
        h1 = m1 - s1
        df_1h["macd_up"] = ((h1 > h1.shift(1)) | (h1 > h1.shift(2)) | (m1 > m1.shift(1))).astype(float)
        df_1h["macd_dn"] = ((h1 < h1.shift(1)) | (h1 < h1.shift(2)) | (m1 < m1.shift(1))).astype(float)

        cols_hi = ["close", "atr1", "ema50", "ema50_prev", "adx", "sw_h", "sw_l", "bull_imp", "crosses", "macd_up", "macd_dn"]
        _map_closed_htf(df_1h, cols_hi, dt_idx, "_hi_", df)

        prev_c = df_work["close"].shift(1)
        tr_t = pd.concat([df_work["high"] - df_work["low"], (df_work["high"] - prev_c).abs(), (df_work["low"] - prev_c).abs()], axis=1).max(axis=1)
        df["_atr_trig"] = tr_t.rolling(14).mean().shift(1).bfill().values
        df["_ema_trig"] = df_work["close"].ewm(span=15, adjust=False).mean().values
        v_ma = df_work["volume"].rolling(20).mean().shift(1).replace(0, 1.0)
        df["_rvol_trig"] = (df_work["volume"] / v_ma).fillna(1.0).values
        e12 = df_work["close"].ewm(span=12, adjust=False).mean()
        e26 = df_work["close"].ewm(span=26, adjust=False).mean()
        mc = e12 - e26
        sg = mc.ewm(span=9, adjust=False).mean()
        df["_macd"] = mc.values
        df["_hist"] = (mc - sg).values
        df["_adx_1h"] = df["_hi_adx"].fillna(25.0)
        df["_mtf_15m_bad"] = False
        df["_mtf_15m_init"] = True

    if bool(df["_mtf_15m_bad"].iloc[0]) or i < 320:
        return False, None, 0.0, 0.0

    r = df.iloc[i]
    c, o, h, l = float(r["close"]), float(r["open"]), float(r["high"]), float(r["low"])
    atr15 = float(r["_atr_trig"])
    if atr15 <= 0 or c <= 0 or pd.isna(r["_hi_ema50"]) or pd.isna(r["_hi_atr1"]):
        return False, None, 0.0, 0.0
    if float(r["_hi_adx"]) < 18.0 or float(r["_hi_crosses"]) > 3:
        return False, None, 0.0, 0.0

    ema1h = float(r["_hi_ema50"])
    ema1h_p = float(r["_hi_ema50_prev"])
    sw_h, sw_l = float(r["_hi_sw_h"]), float(r["_hi_sw_l"])
    atr1 = float(r["_hi_atr1"])
    rng_fibo = max(sw_h - sw_l, 1e-9)
    bull_1h = int(r["_hi_bull_imp"]) == 1
    is_ema_falling = ema1h < ema1h_p * 0.995
    if is_ema_falling and not bull_1h and c < ema1h * 0.998:
        side = "SHORT"
    elif bull_1h:
        side = "LONG"
    else:
        side = "SHORT" if c < ema1h else "LONG"

    retr = ((sw_h - c) / rng_fibo) if side == "LONG" else ((c - sw_l) / rng_fibo)
    if not (0.48 <= retr <= 0.75):
        return False, None, 0.0, 0.0

    hc, hp1, hp2 = float(r["_hist"]), float(df["_hist"].iloc[i - 1]), float(df["_hist"].iloc[i - 2])
    mc, mp1 = float(r["_macd"]), float(df["_macd"].iloc[i - 1])
    e_tr = float(r["_ema_trig"])
    rng = max(h - l, 1e-9)
    body_pct = abs(c - o) / rng
    ema_prev = df["_ema_trig"].iloc[max(0, i - 6):i]

    if side == "LONG":
        macd_ok = (hc > hp1 or hc > hp2 or mc > mp1) and (int(r["_hi_macd_up"]) == 1)
        cross_ok = (c > e_tr) and (c > o) and (body_pct >= 0.30) and ((h - max(o, c)) / rng < 0.45) and (df["low"].iloc[max(0, i - 6):i] <= ema_prev * 1.002).any()
        if not (macd_ok and cross_ok and c >= ema1h * 0.995):
            return False, None, 0.0, 0.0
        loc_low = float(df.iloc[max(0, i - 12):i + 1]["low"].min())
        sl_dist = min(3.0 * atr1, max(c - loc_low + 0.2 * atr1, 1.0 * atr1, 0.008 * c))
        sl_px, tp_px = c - sl_dist, sw_h
    else:
        macd_ok = (hc < hp1 or hc < hp2 or mc < mp1) and (int(r["_hi_macd_dn"]) == 1)
        cross_ok = (c < e_tr) and (c < o) and (body_pct >= 0.30) and (((min(o, c) - l) / rng) < 0.45) and (df["high"].iloc[max(0, i - 6):i] >= ema_prev * 0.998).any()
        if not (macd_ok and cross_ok and c <= ema1h * 1.005):
            return False, None, 0.0, 0.0
        loc_high = float(df.iloc[max(0, i - 12):i + 1]["high"].max())
        sl_dist = min(3.0 * atr1, max(loc_high - c + 0.2 * atr1, 1.0 * atr1, 0.008 * c))
        sl_px, tp_px = c + sl_dist, sw_l

    sl_pct = abs(c - sl_px) / c * 100.0
    tp_pct = (tp_px - c) / c * 100.0 if side == "LONG" else (c - tp_px) / c * 100.0
    if tp_pct <= 0 or sl_pct <= 0 or _net_rr(tp_pct, sl_pct, 0.10, 0.05) < 2.0:
        return False, None, 0.0, 0.0
    return True, side, float(sl_px), float(tp_px)
