# -*- coding: utf-8 -*-
"""
Servicio determinista (0 tokens LLM) para la Terminal de la Tríada Multitemporal (1D · 1H · 5M/15M).

Consume exclusivamente los valores reales devueltos por:
  - backend.kula_rules.evaluate_kula_trigger() y check_universal_wick_veto()
  - backend.candlestick_auditor.audit_candlestick_confluence()
  - backend.quant_risk (get_asset_friction_costs, calculate_guarded_stop_loss, net_return_after_costs, risk_sized_qty)

NO modifica reglas matemáticas, entry_gate, schema.sql ni la campaña `auto`.
Las ejecuciones asistidas se registran en seguimiento virtual aislado (`shadow_trades` con
`strategy='manual_triada'` y `arbiter_verdict='MANUAL_TRIADA'`) para no contaminar `VAULT_USDT`,
`one_open_trade_per_symbol`, `auto` ni el Edge del Árbitro IA.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from backend.candlestick_auditor import audit_candlestick_confluence
from backend.indicators import compute_rvol_tod
from backend.kula_rules import (
    check_universal_wick_veto,
    compute_atr,
    compute_ema,
    evaluate_kula_trigger,
)
from backend.quant_risk import (
    calculate_guarded_stop_loss,
    get_asset_friction_costs,
    net_return_after_costs,
    risk_sized_qty,
)


ALLOWED_TACTICAL_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h", "1d")


def normalize_triada_symbol(raw: str) -> str:
    s = str(raw or "").strip().upper()
    if not s:
        return "BTC/USDT"
    if "/" in s:
        return s.replace("//", "/")
    if s.endswith("USDT") and len(s) > 4:
        return f"{s[:-4]}/USDT"
    return s


def _symbol_compact(raw: str) -> str:
    return str(raw or "").replace("/", "").strip().upper()


def _vault_currency_for_symbol(symbol: str) -> str:
    s = str(symbol or "").upper()
    if s.endswith(".BA"):
        return "ARS"
    if "/USDT" in s or s.endswith("USDT"):
        return "USDT"
    return "USD"


def _to_epoch_sec(ts_val: Any) -> int:
    try:
        v = float(ts_val)
        if v > 1e12:
            v = v / 1000.0
        return int(v)
    except Exception:
        return 0


def _build_ema_points(df: pd.DataFrame, span: int, px_dec: int, max_points: int = 120) -> List[Dict[str, Any]]:
    if df is None or len(df) < 5 or "close" not in df.columns or "timestamp" not in df.columns:
        return []
    sub = df.tail(max_points).copy()
    ema_s = compute_ema(df["close"].astype(float), min(span, max(5, len(df)))).loc[sub.index]
    out: List[Dict[str, Any]] = []
    for idx, row in sub.iterrows():
        t_sec = _to_epoch_sec(row["timestamp"])
        val = float(ema_s.loc[idx])
        if t_sec > 0 and math.isfinite(val):
            out.append({"time": t_sec, "value": round(val, px_dec)})
    return out


def _fetch_closed_df(symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
    import backend.main as main_mod

    try:
        raw = main_mod.get_ohlcv(symbol, timeframe, limit)
        closed = main_mod._closed_ohlcv_data(raw, symbol, timeframe)
        if not closed or len(closed) < 20:
            return None
        return pd.DataFrame(closed, columns=["timestamp", "open", "high", "low", "close", "volume"])
    except Exception:
        return None


def _compute_swing_and_fibo(df_1h: Optional[pd.DataFrame], side: str, px_dec: int) -> Dict[str, Optional[float]]:
    """Replica exactamente el lookback=min(50, len(df_1h)) de backend/kula_rules.py:143-153."""
    if df_1h is None or len(df_1h) < 5:
        return {
            "swing_high": None,
            "swing_low": None,
            "fibo_50": None,
            "fibo_75": None,
            "zone_min": None,
            "zone_max": None,
            "invalidation_price": None,
        }
    lookback = min(50, len(df_1h))
    swing_high = float(df_1h["high"].tail(lookback).max())
    swing_low = float(df_1h["low"].tail(lookback).min())
    diff = swing_high - swing_low
    if diff <= 0:
        return {
            "swing_high": round(swing_high, px_dec),
            "swing_low": round(swing_low, px_dec),
            "fibo_50": None,
            "fibo_75": None,
            "zone_min": None,
            "zone_max": None,
            "invalidation_price": None,
        }

    is_long = str(side or "LONG").upper() in ("LONG", "BUY")
    if is_long:
        fibo_50 = swing_high - (0.50 * diff)
        fibo_75 = swing_high - (0.75 * diff)
    else:
        fibo_50 = swing_low + (0.50 * diff)
        fibo_75 = swing_low + (0.75 * diff)

    return {
        "swing_high": round(swing_high, px_dec),
        "swing_low": round(swing_low, px_dec),
        "fibo_50": round(fibo_50, px_dec),
        "fibo_75": round(fibo_75, px_dec),
        "zone_min": round(min(fibo_50, fibo_75), px_dec),
        "zone_max": round(max(fibo_50, fibo_75), px_dec),
        "invalidation_price": round(fibo_75, px_dec),
    }


def _find_open_auto_position(broker: Any, symbol: str) -> Optional[Dict[str, Any]]:
    if broker is None or not hasattr(broker, "fetch_positions"):
        return None
    target_norm = _symbol_compact(symbol)
    try:
        positions = broker.fetch_positions() or []
    except Exception:
        return None
    for pos in positions:
        if _symbol_compact(pos.get("symbol", "")) == target_norm:
            return {
                "id": pos.get("id"),
                "symbol": pos.get("symbol"),
                "side": pos.get("side"),
                "strategy": pos.get("strategy") or "auto",
                "entry_price": pos.get("entry_price"),
            }
    return None


def _find_open_manual_shadow(broker: Any, symbol: str) -> Optional[Dict[str, Any]]:
    ledger = getattr(broker, "ledger", None) if broker is not None else None
    if ledger is None or not hasattr(ledger, "get_open_shadow_trades"):
        return None
    try:
        rows = ledger.get_open_shadow_trades(symbol=symbol) or []
    except Exception:
        return None
    for row in rows:
        if str(row.get("arbiter_verdict") or "").upper() == "MANUAL_TRIADA":
            return {
                "id": row.get("id"),
                "symbol": row.get("symbol"),
                "side": row.get("side"),
                "qty": float(row.get("qty") or 0.0),
                "entry_price": float(row.get("entry_price") or 0.0),
                "sl_price": float(row.get("sl_price") or 0.0),
                "tp_price": float(row.get("tp_price") or 0.0),
                "initial_sl_pct": float(row.get("initial_sl_pct") or 0.0),
                "initial_tp_pct": float(row.get("initial_tp_pct") or 0.0),
                "strategy": row.get("strategy") or "manual_triada",
                "arbiter_verdict": "MANUAL_TRIADA",
                "opened_at": row.get("opened_at"),
            }
    return None


def _resolve_vault_capital(broker: Any, symbol: str) -> Tuple[float, str]:
    currency = _vault_currency_for_symbol(symbol)
    default_cap = 500000.0 if currency == "ARS" else 500.0
    if broker is None:
        return default_cap, currency
    try:
        vaults = getattr(broker, "vault_balances", None)
        if isinstance(vaults, dict) and float(vaults.get(currency, 0.0) or 0.0) > 0:
            return float(vaults[currency]), currency
    except Exception:
        pass
    try:
        ledger = getattr(broker, "ledger", None)
        if ledger is not None and hasattr(ledger, "get_account_balance"):
            bal = float(ledger.get_account_balance(f"VAULT_{currency}") or 0.0)
            if bal > 0:
                return bal, currency
    except Exception:
        pass
    return default_cap, currency


def _evaluate_session_and_tf_guard(
    symbol: str,
    tf_norm: str,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Paso 1 del Protocolo Presencial:
      - Ventanas horarias de liquidez institucional en ART (UTC-3):
          * LONDRES_NY_AM: 09:30 - 13:30 ART
          * NY_POWER_HOUR: 15:30 - 17:30 ART
      - Zonas bloqueadas (blackout):
          * LUNCH_LULL: 14:00 - 15:30 ART (chop sin dirección)
          * FOREX_SUNDAY_TRAP: Domingo 18:00 - 21:00 ART en activos FX (=X)
      - Piso de temporalidad en cripto presencial:
          * En cripto (/USDT), 15m recomendado (5m permitido con advertencia; 1m/3m bloqueado por fricción 0.26% RT).
    """
    ref_utc = now_utc if now_utc is not None else datetime.now(timezone.utc)
    if ref_utc.tzinfo is None:
        ref_utc = ref_utc.replace(tzinfo=timezone.utc)
    art_dt = ref_utc.astimezone(timezone(timedelta(hours=-3)))
    hm = art_dt.hour * 60 + art_dt.minute
    weekday = art_dt.weekday()  # 0=Mon .. 6=Sun

    is_fx = "=X" in str(symbol or "").upper()
    is_crypto = "/USDT" in str(symbol or "").upper() or str(symbol or "").upper().endswith("USDT")

    window_code = "FUERA_VENTANA_PRIMARIA"
    window_label = f"Sesión Libre ({art_dt.strftime('%H:%M')} ART)"
    is_blackout = False
    blackout_reason: Optional[str] = None

    if is_fx and weekday == 6 and (18 * 60 <= hm < 21 * 60):
        window_code = "FOREX_SUNDAY_TRAP"
        window_label = "Apertura Dom. Forex (Spread Alto)"
        is_blackout = True
        blackout_reason = "Ventana bloqueada: apertura dominical Forex (18:00–21:00 ART) con spread ensanchado."
    elif 9 * 60 + 30 <= hm <= 13 * 60 + 30:
        window_code = "LONDRES_NY_AM"
        window_label = "Londres / NY AM (09:30–13:30 ART)"
    elif 14 * 60 <= hm < 15 * 60 + 30:
        window_code = "LUNCH_LULL"
        window_label = "Lunch Lull NY (14:00–15:30 ART)"
        is_blackout = True
        blackout_reason = "Ventana bloqueada: Lunch Lull NY (14:00–15:30 ART) — baja liquidez y falsas rupturas."
    elif 15 * 60 + 30 <= hm <= 17 * 60 + 30:
        window_code = "NY_POWER_HOUR"
        window_label = "NY Power Hour (15:30–17:30 ART)"

    tf_clean = str(tf_norm or "15m").lower()
    tf_floor_ok = True
    tf_warning: Optional[str] = None
    if is_crypto:
        if tf_clean in ("1m", "3m"):
            tf_floor_ok = False
            tf_warning = f"Temporalidad {tf_clean} bloqueada en cripto presencial (mínimo 15m recomendado por fricción 0.26% RT)."
        elif tf_clean == "5m":
            tf_warning = "Escala 5m con mayor ruido frente a comisión 0.26% RT (recomendado 15m presencial)."

    return {
        "art_time": art_dt.strftime("%H:%M"),
        "window_code": window_code,
        "window_label": window_label,
        "is_primary_window": window_code in ("LONDRES_NY_AM", "NY_POWER_HOUR"),
        "is_blackout": is_blackout,
        "blackout_reason": blackout_reason,
        "tf_norm": tf_clean,
        "tf_floor_ok": tf_floor_ok,
        "tf_recommended": "15m" if is_crypto else "1h",
        "tf_warning": tf_warning,
    }


def _evaluate_setup_a_squeeze(
    df_1h: Optional[pd.DataFrame],
    df_tactical: Optional[pd.DataFrame],
    side: str,
    rule0_ok: bool,
    rule1_ok: bool,
    rule2_ok: bool,
    px_dec: int,
) -> Dict[str, Any]:
    """
    Paso 3 · Setup A — Ruptura tras Compresión 1H -> 15M (modelo fractal_squeeze_15m):
      1. Estructura 1H alineada (Cierre vs EMA50 1H + Abanico EMA21/EMA89 1H) y 1D no roto en contra.
      2. Compresión previa en marco táctico: Bollinger(20, 2.0) dentro de Keltner(20, 1.60*ATR14)
         en al menos 1 de las últimas 4 velas cerradas previas.
      3. Vela de ruptura cerrada por fuera de Keltner a favor de 1H con expansión ATR(14) > SMA(ATR, 20).
    """
    if df_tactical is None or len(df_tactical) < 25:
        return {
            "triggered": False,
            "squeeze_recent": False,
            "breakout_bar": False,
            "atr_expanding": False,
            "kc_upper": None,
            "kc_lower": None,
        }

    is_long = str(side or "LONG").upper() in ("LONG", "BUY")
    c = df_tactical["close"].astype(float)
    o = df_tactical["open"].astype(float)

    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    bbu = sma20 + 2.0 * std20
    bbd = sma20 - 2.0 * std20

    ema20 = compute_ema(c, 20)
    atr14 = compute_atr(df_tactical, 14)
    atr_sma20 = atr14.rolling(20, min_periods=5).mean()

    kc_mult = 1.60
    kcu = ema20 + kc_mult * atr14
    kcd = ema20 - kc_mult * atr14

    in_sq = ((bbu < kcu) & (bbd > kcd)).astype(int)
    sq_recent_series = in_sq.shift(1).rolling(4, min_periods=1).max()

    last_idx = df_tactical.index[-1]
    sq_recent = bool(float(sq_recent_series.loc[last_idx] or 0.0) > 0)
    c_last = float(c.loc[last_idx])
    o_last = float(o.loc[last_idx])
    kcu_last = float(kcu.loc[last_idx]) if not pd.isna(kcu.loc[last_idx]) else c_last
    kcd_last = float(kcd.loc[last_idx]) if not pd.isna(kcd.loc[last_idx]) else c_last
    atr_last = float(atr14.loc[last_idx]) if not pd.isna(atr14.loc[last_idx]) else 0.0
    atr_sma_last = float(atr_sma20.loc[last_idx]) if not pd.isna(atr_sma20.loc[last_idx]) else 0.0

    atr_expanding = bool(atr_last > 0 and atr_sma_last > 0 and atr_last >= atr_sma_last)
    if is_long:
        breakout_bar = bool(c_last > kcu_last and c_last > o_last)
    else:
        breakout_bar = bool(c_last < kcd_last and c_last < o_last)

    structure_ok = bool(rule0_ok and rule1_ok and rule2_ok)
    triggered = bool(structure_ok and sq_recent and breakout_bar and atr_expanding)

    return {
        "triggered": triggered,
        "structure_ok": structure_ok,
        "squeeze_recent": sq_recent,
        "breakout_bar": breakout_bar,
        "atr_expanding": atr_expanding,
        "kc_upper": round(kcu_last, px_dec) if math.isfinite(kcu_last) else None,
        "kc_lower": round(kcd_last, px_dec) if math.isfinite(kcd_last) else None,
    }


def _evaluate_rvol_bipolar_gate(
    df_tactical: Optional[pd.DataFrame],
    tf_norm: str,
    symbol: str,
    active_setup: str,
    fallback_rvol: float = 1.0,
) -> Dict[str, Any]:
    """
    Paso 4 — Confirmación con RVOL-TOD Bipolar (base 1.0x):
      - En Forex (=X, sin volumen centralizado): exento automáticamente.
      - Setup A (Ruptura Squeeze): exige RVOL-TOD >= 1.80x (barra verde alta institucional).
      - Setup B (Pullback Fibo 0.50-0.75): exige RVOL-TOD >= 1.10x (barra verde sobre media horaria 1.0x;
        rechaza barras rojas < 1.0x).
    """
    is_fx = "=X" in str(symbol or "").upper()
    if is_fx:
        return {
            "rvol_tod": None,
            "min_required": 0.0,
            "ok": True,
            "polarity": "FX_EXEMPT",
            "label": "FX Exento (sin vol. centralizado)",
        }

    rvol_tod_val: Optional[float] = None
    if df_tactical is not None and len(df_tactical) >= 5:
        try:
            s_rvol = compute_rvol_tod(df_tactical, timeframe=tf_norm, lookback_days=5)
            if len(s_rvol) > 0 and s_rvol.iloc[-1] is not None and not pd.isna(s_rvol.iloc[-1]):
                rvol_tod_val = round(float(s_rvol.iloc[-1]), 2)
        except Exception:
            rvol_tod_val = None

    if rvol_tod_val is None:
        rvol_tod_val = round(float(fallback_rvol or 1.0), 2)

    if active_setup == "SETUP_A_SQUEEZE":
        min_req = 1.80
    else:
        min_req = 1.10

    ok = bool(rvol_tod_val >= min_req)
    polarity = "GREEN_ABOVE_AVG" if rvol_tod_val >= 1.0 else "RED_BELOW_AVG"
    return {
        "rvol_tod": rvol_tod_val,
        "min_required": min_req,
        "ok": ok,
        "polarity": polarity,
        "label": f"{rvol_tod_val:.2f}x / req ≥ {min_req:.2f}x ({'Verde' if rvol_tod_val >= 1.0 else 'Rojo < 1.0x'})",
    }


def _check_daily_presencial_limits(
    broker: Any,
    now_utc: Optional[datetime] = None,
    max_daily_trades: int = 2,
    max_daily_sl: int = 2,
) -> Dict[str, Any]:
    """
    Paso 5 — Cupo Duro de Sesión Presencial:
      - Máximo 2 operaciones MANUAL_TRIADA por día.
      - Máximo 2 SL en el día (-1.0% bóveda) -> stop diario hasta el día siguiente.
    """
    ref_utc = now_utc if now_utc is not None else datetime.now(timezone.utc)
    if ref_utc.tzinfo is None:
        ref_utc = ref_utc.replace(tzinfo=timezone.utc)
    art_tz = timezone(timedelta(hours=-3))
    art_now = ref_utc.astimezone(art_tz)
    day_start_art = art_now.replace(hour=0, minute=0, second=0, microsecond=0)
    # SQLite CURRENT_TIMESTAMP usa formato 'YYYY-MM-DD HH:MM:SS' en UTC
    day_start_utc_sql = day_start_art.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    daily_trades = 0
    daily_sl = 0
    ledger = getattr(broker, "ledger", None) if broker is not None else None
    conn_fn = (getattr(ledger, "_connect", None) or getattr(ledger, "_get_connection", None)) if ledger is not None else None
    if callable(conn_fn):
        try:
            with conn_fn() as conn:
                rows = conn.execute(
                    """
                    SELECT outcome, status
                    FROM shadow_trades
                    WHERE arbiter_verdict = 'MANUAL_TRIADA'
                      AND REPLACE(opened_at, 'T', ' ') >= ?
                    """,
                    (day_start_utc_sql,),
                ).fetchall()
                daily_trades = len(rows)
                for r in rows:
                    outcome = str(r["outcome"] if isinstance(r, dict) or hasattr(r, "keys") else r[0] or "").upper()
                    if outcome == "SAVED_SL":
                        daily_sl += 1
        except Exception:
            pass

    quota_ok = daily_trades < max_daily_trades
    sl_stop_ok = daily_sl < max_daily_sl
    block_reason: Optional[str] = None
    if not sl_stop_ok:
        block_reason = f"Stop diario presencial activado ({daily_sl}/{max_daily_sl} SL hoy = -1.0% bóveda)."
    elif not quota_ok:
        block_reason = f"Cupo diario presencial alcanzado ({daily_trades}/{max_daily_trades} operaciones hoy)."

    return {
        "daily_trades_count": daily_trades,
        "max_daily_trades": max_daily_trades,
        "daily_sl_count": daily_sl,
        "max_daily_sl": max_daily_sl,
        "quota_ok": quota_ok,
        "sl_stop_ok": sl_stop_ok,
        "ok": bool(quota_ok and sl_stop_ok),
        "block_reason": block_reason,
    }


def _build_execution_plan(
    *,
    symbol: str,
    side: str,
    cur_price: float,
    atr_val: float,
    fibo_info: Dict[str, Optional[float]],
    trigger_res: Dict[str, Any],
    wick_veto_reason: Optional[str],
    risk_pct: float,
    target_rr: float,
    broker: Any,
    px_dec: int,
    presencial_protocol: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    is_long = str(side or "LONG").upper() in ("LONG", "BUY")
    costs = get_asset_friction_costs(symbol)
    fee_pct = float(costs.get("fee_pct", 0.10))
    spread_pct = float(costs.get("spread_pct", 0.05))
    round_trip_cost = round((fee_pct + spread_pct) * 2.0, 4)

    sym_up = symbol.upper()
    is_fx = "=X" in sym_up
    is_crypto = "/USDT" in sym_up or sym_up.endswith("USDT")
    tick_size = 0.0001 if is_fx else (0.0001 if cur_price < 1.0 else 0.01)
    # Paso 5: en cripto presencial, SL >= max(1.2%, 1.8 * ATR%) para blindarse del 0.26% RT
    atr_pct = ((atr_val / cur_price) * 100.0) if (cur_price > 0 and atr_val > 0) else 0.0
    if is_fx:
        base_sl_pct = 0.15
    elif is_crypto:
        base_sl_pct = max(1.20, round(1.8 * atr_pct, 4))
    else:
        base_sl_pct = max(1.00, round(1.5 * atr_pct, 4))

    # Stop Loss técnico: integra blindaje ATR de quant_risk.py + nivel de invalidación Fibo 0.75
    fibo_inv = fibo_info.get("invalidation_price")
    support_ref: Optional[float] = None
    proto = presencial_protocol or {}
    active_setup = str(proto.get("active_setup") or "SETUP_B_FIBO_PULLBACK")
    # En Setup A (ruptura post-compresión) el precio rompe máximo/mínimo de Keltner; el stop técnico es por ATR/estructura
    if active_setup != "SETUP_A_SQUEEZE" and fibo_inv is not None and cur_price > 0:
        if is_long and fibo_inv < cur_price:
            support_ref = float(fibo_inv)
        elif (not is_long) and fibo_inv > cur_price:
            # Simetría para SHORT usando distancia desde cur_price hacia arriba
            support_ref = cur_price - (float(fibo_inv) - cur_price)

    guarded = calculate_guarded_stop_loss(
        price=cur_price,
        support_price=support_ref,
        atr=atr_val if atr_val > 0 else None,
        base_sl_pct=base_sl_pct,
        tick_size=tick_size,
        symbol=symbol,
    )
    sl_gross_pct = float(guarded.get("sl_pct") or base_sl_pct)
    if sl_gross_pct <= 0 or not math.isfinite(sl_gross_pct):
        sl_gross_pct = base_sl_pct
    if is_crypto:
        sl_gross_pct = max(1.20, sl_gross_pct)
    # Paso 5: en acciones EE. UU. / CEDEARs cap <= 4.8% (evita veto 5.0% de entry_gate); en cripto cap <= 8.0%
    max_sl_cap = 8.0 if is_crypto else (1.5 if is_fx else 4.8)
    sl_gross_pct = round(min(sl_gross_pct, max_sl_cap), 4)

    sl_price = (
        round(cur_price * (1.0 - sl_gross_pct / 100.0), px_dec)
        if is_long
        else round(cur_price * (1.0 + sl_gross_pct / 100.0), px_dec)
    )

    sl_net_pct = abs(float(net_return_after_costs(-abs(sl_gross_pct), fee_pct, spread_pct)))
    desired_rr = max(2.0, float(target_rr or 2.0))
    # Resolver tp_gross_pct exacto tal que net_return_after_costs(tp_gross_pct, fee, spread) / sl_net_pct >= desired_rr
    req_net_tp = desired_rr * sl_net_pct
    tp_gross_pct = round(req_net_tp + round_trip_cost + 0.02, 4)
    net_tp_pct = float(net_return_after_costs(tp_gross_pct, fee_pct, spread_pct))
    net_rr = round(net_tp_pct / sl_net_pct, 2) if sl_net_pct > 1e-9 else 0.0

    tp_price = (
        round(cur_price * (1.0 + tp_gross_pct / 100.0), px_dec)
        if is_long
        else round(cur_price * (1.0 - tp_gross_pct / 100.0), px_dec)
    )

    eff_risk_pct = max(0.1, min(2.0, float(risk_pct or 0.5)))
    vault_capital, currency = _resolve_vault_capital(broker, symbol)
    qty_raw = risk_sized_qty(
        capital=vault_capital,
        price=cur_price,
        sl_gross_pct=sl_gross_pct,
        fee_pct=fee_pct,
        spread_pct=spread_pct,
        risk_budget_pct=eff_risk_pct,
        max_notional_pct=50.0,
    )
    qty_dec = 6 if cur_price >= 50.0 else 4
    qty = round(float(qty_raw or 0.0), qty_dec)
    notional_usd = round(qty * cur_price, 2)
    risk_budget_usd = round(vault_capital * (eff_risk_pct / 100.0), 2)

    open_auto_pos = _find_open_auto_position(broker, symbol)
    active_manual_sim = _find_open_manual_shadow(broker, symbol)

    setup_triggered = bool(proto.get("setup_triggered", trigger_res.get("triggered")))
    rvol_gate = proto.get("rvol_gate") or {}
    session_guard = proto.get("session_guard") or {}
    daily_limits = proto.get("daily_limits") or {}

    block_reasons: List[str] = []
    if not setup_triggered:
        fails = trigger_res.get("failures") or []
        summary_fail = "; ".join(str(x) for x in fails[:2]) if fails else "No se activa Setup A (Squeeze 1H→15M) ni Setup B (Pullback Fibo 0.50–0.75)."
        block_reasons.append(f"Gatillo sin luz verde: {summary_fail}")
    if setup_triggered and rvol_gate and not bool(rvol_gate.get("ok", True)):
        block_reasons.append(
            f"RVOL bipolar insuficiente ({rvol_gate.get('rvol_tod', 0.0):.2f}x < {rvol_gate.get('min_required', 1.1):.2f}x requerido para {proto.get('active_setup_label') or active_setup})."
        )
    if session_guard and not bool(session_guard.get("tf_floor_ok", True)):
        block_reasons.append(str(session_guard.get("tf_warning") or "Temporalidad inferior al piso presencial permitido."))
    if session_guard and bool(session_guard.get("is_blackout", False)):
        block_reasons.append(str(session_guard.get("blackout_reason") or "Ventana horaria bloqueada por baja liquidez."))
    if daily_limits and not bool(daily_limits.get("ok", True)):
        block_reasons.append(str(daily_limits.get("block_reason") or "Cupo diario presencial alcanzado."))
    if wick_veto_reason:
        block_reasons.append(str(wick_veto_reason))
    if net_rr < 2.0:
        block_reasons.append(f"Asimetría neta insuficiente (R:R {net_rr:.2f} < 2.00).")
    if open_auto_pos is not None:
        block_reasons.append(
            f"{symbol} ya tiene posición OPEN en auto ({open_auto_pos.get('strategy')}) — bloqueado para proteger one_open_trade_per_symbol."
        )
    if qty <= 0 or cur_price <= 0:
        block_reasons.append("Tamaño de posición calculado inválido (qty <= 0).")

    return {
        "can_execute": len(block_reasons) == 0,
        "block_reasons": block_reasons,
        "side": "LONG" if is_long else "SHORT",
        "active_setup": active_setup,
        "active_setup_label": proto.get("active_setup_label") or active_setup,
        "entry_price": round(cur_price, px_dec),
        "sl_price": sl_price,
        "tp_price": tp_price,
        "sl_gross_pct": round(sl_gross_pct, 2),
        "tp_gross_pct": round(tp_gross_pct, 2),
        "sl_net_pct": round(sl_net_pct, 2),
        "tp_net_pct": round(net_tp_pct, 2),
        "net_rr": net_rr,
        "fee_pct": fee_pct,
        "spread_pct": spread_pct,
        "round_trip_cost_pct": round_trip_cost,
        "risk_pct": eff_risk_pct,
        "risk_budget_usd": risk_budget_usd,
        "vault_capital": round(vault_capital, 2),
        "currency": currency,
        "qty": qty,
        "notional_usd": notional_usd,
        "strategy": "manual_triada",
        "arbiter_verdict": "MANUAL_TRIADA",
        "storage_mode": "isolated_virtual_shadow",
        "open_auto_position": open_auto_pos,
        "active_manual_sim": active_manual_sim,
    }


def evaluate_triada_snapshot(
    symbol: str,
    timeframe: str = "5m",
    direction_mode: str = "dual",
    risk_pct: float = 0.5,
    target_rr: float = 2.0,
    df_1d: Optional[pd.DataFrame] = None,
    df_1h: Optional[pd.DataFrame] = None,
    df_tactical: Optional[pd.DataFrame] = None,
    broker: Any = None,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Evalúa los 5 puntos de la Tríada Multitemporal + el Protocolo Presencial de 5 Pasos
    (Ventana horaria y piso TF, Estructura 1H, Setup A Squeeze / Setup B Fibo, RVOL-TOD bipolar
    y Cupo duro diario 2 ops / 2 SL) usando exclusivamente backend.kula_rules, backend.indicators,
    backend.candlestick_auditor y backend.quant_risk (0 tokens LLM).
    """
    import backend.main as main_mod

    norm_symbol = normalize_triada_symbol(symbol)
    tf_norm = str(timeframe or "5m").strip().lower()
    if tf_norm not in ALLOWED_TACTICAL_TIMEFRAMES:
        tf_norm = "5m"
    dir_mode = str(direction_mode or "dual").strip().lower()
    if broker is not None:
        broker_ref = broker
    else:
        try:
            from backend.daemon import get_trader_daemon
            broker_ref = get_trader_daemon().broker
        except Exception:
            broker_ref = None

    if df_1d is None:
        df_1d = _fetch_closed_df(norm_symbol, "1d", 120)
    if df_1h is None:
        df_1h = _fetch_closed_df(norm_symbol, "1h", 120)
    if df_tactical is None:
        df_tactical = df_1h if tf_norm == "1h" else _fetch_closed_df(norm_symbol, tf_norm, 150)

    if df_tactical is None or len(df_tactical) < 20:
        return {
            "status": "error",
            "symbol": norm_symbol,
            "timeframe": tf_norm,
            "error": f"Historial insuficiente para {norm_symbol} [{tf_norm}].",
        }

    cur_price = float(df_tactical["close"].iloc[-1])
    px_dec = 5 if ("=X" in norm_symbol or 0 < cur_price < 10.0) else 2

    # 1. Auditoría de velas Bulkowski + Wyckoff VPA + RSI Divergencia (0 tokens)
    ind = main_mod.compute_technical_indicators(df_tactical)
    costs = get_asset_friction_costs(norm_symbol)
    is_fx = "=X" in norm_symbol
    candlestick_audit = audit_candlestick_confluence(
        symbol=norm_symbol,
        df=df_tactical,
        ind=ind,
        fee=float(costs.get("fee_pct", 0.10)),
        spread=float(costs.get("spread_pct", 0.05)),
        min_profit_pct=0.20 if is_fx else 0.50,
    )

    # 2. Resolución de dirección y evaluación real de evaluate_kula_trigger()
    if dir_mode == "long_only":
        chosen_side = "LONG"
        trigger_res = evaluate_kula_trigger(
            df_1h=df_1h,
            df_5m=df_tactical,
            df_tactical=df_tactical,
            current_price=cur_price,
            side="LONG",
            df_1d=df_1d,
        )
    elif dir_mode == "short_only":
        chosen_side = "SHORT"
        trigger_res = evaluate_kula_trigger(
            df_1h=df_1h,
            df_5m=df_tactical,
            df_tactical=df_tactical,
            current_price=cur_price,
            side="SHORT",
            df_1d=df_1d,
        )
    else:
        res_long = evaluate_kula_trigger(
            df_1h=df_1h,
            df_5m=df_tactical,
            df_tactical=df_tactical,
            current_price=cur_price,
            side="LONG",
            df_1d=df_1d,
        )
        res_short = evaluate_kula_trigger(
            df_1h=df_1h,
            df_5m=df_tactical,
            df_tactical=df_tactical,
            current_price=cur_price,
            side="SHORT",
            df_1d=df_1d,
        )
        if res_long.get("triggered"):
            chosen_side, trigger_res = "LONG", res_long
        elif res_short.get("triggered"):
            chosen_side, trigger_res = "SHORT", res_short
        else:
            # Elegir lado coherente con estructura 1H (Cierre vs EMA50 1H)
            ema50_1h_ref = (res_long.get("metrics") or {}).get("ema50_1h")
            if ema50_1h_ref is not None and cur_price < float(ema50_1h_ref):
                chosen_side, trigger_res = "SHORT", res_short
            else:
                chosen_side, trigger_res = "LONG", res_long

    # 3. Veto universal de mechas real sobre última vela cerrada táctica
    wick_veto_reason = check_universal_wick_veto(df_tactical, side=chosen_side)
    wick_veto_active = bool(wick_veto_reason)

    rules = trigger_res.get("rules") or {}
    metrics = trigger_res.get("metrics") or {}
    regime = str(trigger_res.get("volatility_regime") or "COMPRESSION").upper()

    # 4. Niveles exactos para los 5 puntos sobre las velas
    close_1d = round(float(df_1d["close"].iloc[-1]), px_dec) if (df_1d is not None and len(df_1d) > 0) else None
    ema50_1d = metrics.get("ema50_1d")
    rule0_ok = bool(rules.get("rule0_1d_macro_bias"))
    rule1_ok = bool(rules.get("rule1_close_gt_ema50"))
    rule2_ok = bool(rules.get("rule2_ema21_gt_ema89"))
    rule3_ok = bool(rules.get("rule3_fibo_zone"))
    rule4_ok = bool(rules.get("rule4_atr_expansion_tactical"))

    # 4B. Protocolo Presencial de 5 Pasos (Setup A Squeeze 1H->15M + Setup B Pullback Fibo + RVOL Bipolar + Sesión/Cupo)
    session_guard = _evaluate_session_and_tf_guard(norm_symbol, tf_norm, now_utc=now_utc)
    setup_a_info = _evaluate_setup_a_squeeze(
        df_1h=df_1h,
        df_tactical=df_tactical,
        side=chosen_side,
        rule0_ok=rule0_ok,
        rule1_ok=rule1_ok,
        rule2_ok=rule2_ok,
        px_dec=px_dec,
    )
    setup_b_ok = bool(trigger_res.get("triggered"))
    setup_a_ok = bool(setup_a_info.get("triggered"))
    if setup_a_ok and setup_b_ok:
        active_setup = "SETUP_AB_CONFLUENCE"
        active_setup_label = "Setup A+B (Squeeze + Fibo 0.50–0.75)"
    elif setup_a_ok:
        active_setup = "SETUP_A_SQUEEZE"
        active_setup_label = "Setup A (Ruptura Compresión 1H→15M)"
    elif setup_b_ok:
        active_setup = "SETUP_B_FIBO_PULLBACK"
        active_setup_label = "Setup B (Pullback Zona Dorada Fibo)"
    else:
        active_setup = "NONE"
        active_setup_label = "En espera de Setup A (Squeeze) o B (Fibo)"

    setup_triggered = bool(setup_a_ok or setup_b_ok)

    fibo_info = _compute_swing_and_fibo(df_1h, chosen_side, px_dec)
    # Preservar exactitud de fibo_zone_min/max devuelto por evaluate_kula_trigger
    if metrics.get("fibo_zone_min"):
        fibo_info["zone_min"] = metrics["fibo_zone_min"]
    if metrics.get("fibo_zone_max"):
        fibo_info["zone_max"] = metrics["fibo_zone_max"]

    last_candle_ts = _to_epoch_sec(df_tactical["timestamp"].iloc[-1])
    pattern_name = str(candlestick_audit.get("pattern_name") or "NONE")
    rvol_val = float(candlestick_audit.get("rvol") or 1.0)
    rvol_gate = _evaluate_rvol_bipolar_gate(
        df_tactical=df_tactical,
        tf_norm=tf_norm,
        symbol=norm_symbol,
        active_setup="SETUP_A_SQUEEZE" if (setup_a_ok and not setup_b_ok) else "SETUP_B_FIBO_PULLBACK",
        fallback_rvol=rvol_val,
    )
    daily_limits = _check_daily_presencial_limits(broker_ref, now_utc=now_utc)

    presencial_protocol = {
        "session_guard": session_guard,
        "structure_1h_aligned": bool(rule0_ok and rule1_ok and rule2_ok),
        "active_setup": active_setup,
        "active_setup_label": active_setup_label,
        "setup_triggered": setup_triggered,
        "setup_a_squeeze": setup_a_info,
        "setup_b_fibo_pullback": {
            "triggered": setup_b_ok,
            "fibo_zone_ok": rule3_ok,
            "atr_expansion_ok": rule4_ok,
        },
        "rvol_gate": rvol_gate,
        "daily_limits": daily_limits,
    }

    rvol_display = float(rvol_gate.get("rvol_tod") if rvol_gate.get("rvol_tod") is not None else rvol_val)
    rsi_div = str(candlestick_audit.get("rsi_divergence") or "NONE")
    rsi_div_desc = str(candlestick_audit.get("rsi_divergence_desc") or "")

    if wick_veto_active:
        marker_text = "⚠️ VETO MECHA >= 50%"
        marker_kind = "wick_veto"
    else:
        div_tag = ""
        if rsi_div == "BULLISH_DIV":
            div_tag = " · Div RSI+"
        elif rsi_div == "BEARISH_DIV":
            div_tag = " · Div RSI-"
        pat_clean = pattern_name if pattern_name not in ("NONE", "NEUTRAL", "") else "Vela"
        marker_text = f"{pat_clean} · RVOL {rvol_display:.2f}x{div_tag}"
        marker_kind = "pattern"

    atr_val = float(metrics.get("atr_tactical") or ind.get("atr_14") or 0.0)
    if atr_val <= 0 and len(df_tactical) >= 15:
        try:
            atr_s = compute_atr(df_tactical, 14)
            if not pd.isna(atr_s.iloc[-1]):
                atr_val = float(atr_s.iloc[-1])
        except Exception:
            atr_val = 0.0

    execution_plan = _build_execution_plan(
        symbol=norm_symbol,
        side=chosen_side,
        cur_price=cur_price,
        atr_val=atr_val,
        fibo_info=fibo_info,
        trigger_res=trigger_res,
        wick_veto_reason=wick_veto_reason,
        risk_pct=risk_pct,
        target_rr=target_rr,
        broker=broker_ref,
        px_dec=px_dec,
        presencial_protocol=presencial_protocol,
    )

    overlays = {
        "rule0_macro_1d": {
            "ok": rule0_ok,
            "ema50_1d": ema50_1d,
            "close_1d": close_1d,
            "label": f"EMA50 1D ({'✅' if rule0_ok else '❌'})",
        },
        "rules12_structure_1h": {
            "rule1_ok": rule1_ok,
            "rule2_ok": rule2_ok,
            "aligned": rule1_ok and rule2_ok,
            "ema50_1h": metrics.get("ema50_1h"),
            "ema21_1h": metrics.get("ema21_1h"),
            "ema89_1h": metrics.get("ema89_1h"),
            "label": (
                f"EMA50 1H ({'✅' if rule1_ok else '❌'}) · "
                f"Abanico 21/89 ({'✅' if rule2_ok else '❌'})"
            ),
            "series_ema50": _build_ema_points(df_1h, 50, px_dec) if df_1h is not None else [],
            "series_ema21": _build_ema_points(df_1h, 21, px_dec) if df_1h is not None else [],
            "series_ema89": _build_ema_points(df_1h, 89, px_dec) if df_1h is not None else [],
        },
        "rule3_fibo_golden_zone": {
            "ok": rule3_ok,
            **fibo_info,
        },
        "rule4_atr_switch": {
            "ok": rule4_ok,
            "regime": regime,
            "badge_text": "EXPANSION (Retroceso)" if regime == "EXPANSION" else "COMPRESSION (Ruptura)",
            "atr_tactical": metrics.get("atr_tactical"),
            "atr_sma_tactical": metrics.get("atr_sma_tactical"),
        },
        "rule5_wick_and_candlestick": {
            "wick_veto_active": wick_veto_active,
            "wick_veto_reason": wick_veto_reason,
            "pattern_name": pattern_name,
            "pattern_desc": candlestick_audit.get("pattern_desc") or "",
            "win_rate": candlestick_audit.get("win_rate"),
            "rvol": rvol_display,
            "rvol_tod": rvol_gate.get("rvol_tod"),
            "rvol_min_required": rvol_gate.get("min_required"),
            "rvol_ok": rvol_gate.get("ok"),
            "rsi_divergence": rsi_div,
            "rsi_divergence_desc": rsi_div_desc,
            "last_candle_ts": last_candle_ts,
            "marker_text": marker_text,
            "marker_kind": marker_kind,
        },
    }

    return {
        "status": "ok",
        "symbol": norm_symbol,
        "timeframe": tf_norm,
        "direction_mode": dir_mode,
        "evaluated_side": chosen_side,
        "current_price": round(cur_price, px_dec),
        "px_dec": px_dec,
        "triggered": bool(setup_triggered and rvol_gate.get("ok", True) and (not wick_veto_active)),
        "trigger": trigger_res,
        "candlestick_audit": candlestick_audit,
        "presencial_protocol": presencial_protocol,
        "overlays": overlays,
        "execution_plan": execution_plan,
    }


def execute_triada_simulation(
    symbol: str,
    timeframe: str = "5m",
    direction_mode: str = "dual",
    risk_pct: float = 0.5,
    target_rr: float = 2.0,
    df_1d: Optional[pd.DataFrame] = None,
    df_1h: Optional[pd.DataFrame] = None,
    df_tactical: Optional[pd.DataFrame] = None,
    broker: Any = None,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Ejecuta el disparo manual asistido en seguimiento virtual aislado (`shadow_trades` con
    `strategy='manual_triada'` y `arbiter_verdict='MANUAL_TRIADA'`), revalidando en servidor
    todas las compuertas (luz verde Tríada / Setup A o B, RVOL bipolar, ventana de sesión,
    cupo diario 2 ops / 2 SL, R:R >= 2.0, sin veto de mecha y sin posición OPEN en auto).
    """
    import backend.main as main_mod

    if broker is not None:
        broker_ref = broker
    else:
        try:
            from backend.daemon import get_trader_daemon
            broker_ref = get_trader_daemon().broker
        except Exception:
            broker_ref = None
    snap = evaluate_triada_snapshot(
        symbol=symbol,
        timeframe=timeframe,
        direction_mode=direction_mode,
        risk_pct=risk_pct,
        target_rr=target_rr,
        df_1d=df_1d,
        df_1h=df_1h,
        df_tactical=df_tactical,
        broker=broker_ref,
        now_utc=now_utc,
    )
    if snap.get("status") != "ok":
        return {"status": "blocked", "executed": False, "reasons": [snap.get("error") or "Error de datos"], "snapshot": snap}

    plan = snap["execution_plan"]
    if not plan.get("can_execute"):
        return {
            "status": "blocked",
            "executed": False,
            "reasons": list(plan.get("block_reasons") or ["Condiciones de seguridad no cumplidas."]),
            "snapshot": snap,
        }

    ledger_ref = getattr(broker_ref, "ledger", None) if broker_ref is not None else None
    if ledger_ref is None or not hasattr(ledger_ref, "open_shadow_trade"):
        return {
            "status": "error",
            "executed": False,
            "reasons": ["Ledger SQLite no disponible para registrar simulación aislada."],
            "snapshot": snap,
        }

    shadow_id = ledger_ref.open_shadow_trade(
        symbol=snap["symbol"],
        side=plan["side"],
        qty=float(plan["qty"]),
        entry_price=float(plan["entry_price"]),
        sl_price=float(plan["sl_price"]),
        tp_price=float(plan["tp_price"]),
        initial_sl_pct=float(plan["sl_gross_pct"]),
        initial_tp_pct=float(plan["tp_gross_pct"]),
        strategy="manual_triada",
        arbiter_verdict="MANUAL_TRIADA",
        arbiter_reason=(
            f"Ejecución asistida Tríada [{snap['timeframe']}] · R:R neto 1:{plan['net_rr']:.2f} "
            f"· Riesgo {plan['risk_pct']:.2f}% (${plan['risk_budget_usd']:.2f}) · Aislado de VAULT_USDT"
        ),
        deduplicate=True,
    )

    active_sim = _find_open_manual_shadow(broker_ref, snap["symbol"]) or {
        "id": shadow_id,
        "symbol": snap["symbol"],
        "side": plan["side"],
        "qty": float(plan["qty"]),
        "entry_price": float(plan["entry_price"]),
        "sl_price": float(plan["sl_price"]),
        "tp_price": float(plan["tp_price"]),
        "initial_sl_pct": float(plan["sl_gross_pct"]),
        "initial_tp_pct": float(plan["tp_gross_pct"]),
        "strategy": "manual_triada",
        "arbiter_verdict": "MANUAL_TRIADA",
    }
    snap["execution_plan"]["active_manual_sim"] = active_sim

    return {
        "status": "ok",
        "executed": True,
        "shadow_id": shadow_id,
        "storage_mode": "isolated_virtual_shadow",
        "strategy": "manual_triada",
        "arbiter_verdict": "MANUAL_TRIADA",
        "simulation": active_sim,
        "snapshot": snap,
    }
