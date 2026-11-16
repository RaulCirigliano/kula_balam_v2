"""
Módulo de Gestión Cuantitativa de Riesgo, Esperanza Matemática y Criterio de Kelly.
Kula Balam - Arquitectura Cuantitativa (Fase Argon)

DOCUMENTACIÓN DE FÓRMULAS Y UNIDADES:
1. Esperanza Matemática Neta (EV_neto):
   EV_neto = (P_w * R_win_net) + ((1 - P_w) * R_loss_net)
   Donde:
   - P_w: Probabilidad de acierto (fracción en [0.0, 1.0]).
   - R_win_net: Retorno porcentual neto esperado al Take Profit (descontando comisiones de entrada,
     salida, spread por lado y slippage).
   - R_loss_net: Retorno porcentual neto esperado al Stop Loss (negativo, acumulando pérdidas y costos).
   - Unidades: porcentajes expresados en la misma escala (ej. +1.5 para +1.5%, -1.0 para -1.0%).
   - Costos transaccionales: Los costos se descuentan una única vez a través de la función
     net_return_after_costs (evitando deducciones duplicadas).

2. Criterio de Kelly (Quarter-Kelly):
   b = |R_win_net| / |R_loss_net|  (Payoff Ratio o ratio beneficio/riesgo neto)
   f* = (P_w * b - (1 - P_w)) / b = P_w - (1 - P_w) / b
   f_seguro = 0.25 * f*  (Fracción conservadora Quarter-Kelly)
   - Si EV_neto <= 0 o f* <= 0: la asignación de capital es estrictamente 0.0 (capital preservado).
   - f_seguro se acota además por un presupuesto de riesgo máximo configurable (max_risk_budget_pct).

ADVERTENCIA ESTADÍSTICA:
- No se debe inventar ni suponer una probabilidad histórica P_w sin una muestra out-of-sample representativa.
- La confianza del LLM NO representa una probabilidad estadística de acierto.
- Sin un dataset etiquetado fuera de muestra con N >= 30 trades, el Criterio de Kelly permanece
  DESACTIVADO POR DEFECTO (enabled=False), utilizándose el presupuesto fijo de riesgo como opción segura.
"""

from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Dict, Any, List, Optional
import math


def net_return_after_costs(gross_move_pct: float, fee_pct: float, spread_pct: float) -> float:
    """
    Calcula el retorno neto porcentual tras deducir comisiones y spread en entrada y salida.
    Fórmula de capitalización:
      entry_factor = (1 + fee/100) * (1 + spread/100)
      exit_factor = (1 - fee/100) * (1 - spread/100)
      net_pct = ((1 + gross/100) * exit_factor / entry_factor - 1) * 100
    """
    if not all(map(math.isfinite, [gross_move_pct, fee_pct, spread_pct])):
        return float("nan")
    if gross_move_pct <= -100 or fee_pct < 0 or spread_pct < 0 or fee_pct >= 100 or spread_pct >= 100:
        return float("nan")
    entry_cost_factor = (1 + fee_pct / 100) * (1 + spread_pct / 100)
    exit_proceeds_factor = (1 - fee_pct / 100) * (1 - spread_pct / 100)
    return ((1 + gross_move_pct / 100) * exit_proceeds_factor / entry_cost_factor - 1) * 100


ASSET_CLASS_FUTURES_MICRO: str = "FUTURES_MICRO"

MICRO_FUTURES_SPECS: Dict[str, Dict[str, Any]] = {
    "MES=F": {
        "symbol": "MES=F",
        "root": "MES",
        "name": "Micro E-mini S&P 500",
        "asset_class": ASSET_CLASS_FUTURES_MICRO,
        "multiplier": 5.0,
        "tick_size": 0.25,
        "tick_value": 1.25,
        "commission_per_side": 1.25,
        "commission_round_trip": 2.50,
        "default_contracts": 2,
        # Fricción parametrizable: CME no cobra swap (el costo de carry vive en el roll/basis) [Inferencia]; 0.0 por defecto.
        "spread_ticks_per_side": 0.0,
        "swap_per_contract_night": 0.0,
        "ref_price": 6000.0,
    },
    "MNQ=F": {
        "symbol": "MNQ=F",
        "root": "MNQ",
        "name": "Micro E-mini Nasdaq-100",
        "asset_class": ASSET_CLASS_FUTURES_MICRO,
        "multiplier": 2.0,
        "tick_size": 0.25,
        "tick_value": 0.50,
        "commission_per_side": 1.25,
        "commission_round_trip": 2.50,
        "default_contracts": 2,
        # Fricción parametrizable: CME no cobra swap (el costo de carry vive en el roll/basis) [Inferencia]; 0.0 por defecto.
        "spread_ticks_per_side": 0.0,
        "swap_per_contract_night": 0.0,
        "ref_price": 21000.0,
    },
}

_MICRO_FUTURES_ALIASES: Dict[str, str] = {
    "MES": "MES=F",
    "MES=F": "MES=F",
    "MNQ": "MNQ=F",
    "MNQ=F": "MNQ=F",
}


def is_micro_futures_symbol(symbol: str) -> bool:
    """True si el símbolo corresponde a un contrato micro-futuro soportado (MES / MNQ)."""
    sym = str(symbol or "").upper().strip()
    return sym in _MICRO_FUTURES_ALIASES


def get_micro_futures_spec(symbol: str) -> Optional[Dict[str, Any]]:
    """Retorna la especificación contractual de micro-futuros CME (multiplicador, tick, comisión)."""
    sym = str(symbol or "").upper().strip()
    canonical = _MICRO_FUTURES_ALIASES.get(sym)
    if not canonical:
        return None
    return dict(MICRO_FUTURES_SPECS[canonical])


@dataclass(frozen=True)
class FuturesFrictionProfile:
    """
    Perfil modular de fricción de un contrato micro-futuro (USD por contrato salvo indicación):
    - commission_per_side: comisión fija por contrato y por lado (round-trip = 2x).
    - spread_ticks_per_side: slippage/spread asumido por lado, en ticks (0.0 = sin deslizamiento).
    - swap_per_contract_night: costo de mantenimiento por contrato y por corte de jornada superado.
    """

    symbol: str
    multiplier: float
    tick_size: float
    tick_value: float
    commission_per_side: float
    spread_ticks_per_side: float = 0.0
    swap_per_contract_night: float = 0.0

    @property
    def commission_round_trip(self) -> float:
        return self.commission_per_side * 2.0

    def spread_cost_per_side(self, contracts: float) -> float:
        return self.spread_ticks_per_side * self.tick_value * float(contracts)


def _require_non_negative(name: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} debe ser numérico (recibido {value!r}).") from exc
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} debe ser finito y >= 0 (recibido {value!r}).")
    return number


def build_futures_friction_profile(
    symbol: str,
    commission_per_side: Optional[float] = None,
    spread_ticks_per_side: Optional[float] = None,
    swap_per_contract_night: Optional[float] = None,
) -> FuturesFrictionProfile:
    """Construye el perfil de fricción desde la especificación del contrato con overrides validados."""
    spec = get_micro_futures_spec(symbol)
    if spec is None:
        raise ValueError(f"Símbolo no registrado en FUTURES_MICRO: '{symbol}'")
    return FuturesFrictionProfile(
        symbol=str(spec["symbol"]),
        multiplier=float(spec["multiplier"]),
        tick_size=float(spec["tick_size"]),
        tick_value=float(spec["tick_value"]),
        commission_per_side=_require_non_negative(
            "commission_per_side",
            spec["commission_per_side"] if commission_per_side is None else commission_per_side,
        ),
        spread_ticks_per_side=_require_non_negative(
            "spread_ticks_per_side",
            spec.get("spread_ticks_per_side", 0.0) if spread_ticks_per_side is None else spread_ticks_per_side,
        ),
        swap_per_contract_night=_require_non_negative(
            "swap_per_contract_night",
            spec.get("swap_per_contract_night", 0.0) if swap_per_contract_night is None else swap_per_contract_night,
        ),
    )


def count_rollover_crossings(
    start_ts: float,
    end_ts: float,
    rollover_hour_ny: int = 17,
    triple_swap_weekday: Optional[int] = None,
) -> int:
    """
    Cuenta los cortes de jornada (por defecto 17:00 America/New_York, lunes a viernes) cruzados en (start_ts, end_ts].
    - Sábado y domingo no generan corte (mercado cerrado).
    - `triple_swap_weekday` (0=lunes ... 4=viernes) pondera ese corte x3, convención habitual de CFDs.
    """
    start = float(start_ts)
    end = float(end_ts)
    if not (math.isfinite(start) and math.isfinite(end)):
        raise ValueError("start_ts y end_ts deben ser finitos.")
    if end <= start:
        return 0
    if not (0 <= int(rollover_hour_ny) <= 23):
        raise ValueError("rollover_hour_ny debe estar entre 0 y 23.")
    try:
        from zoneinfo import ZoneInfo
        tz: Any = ZoneInfo("America/New_York")
    except Exception:  # pragma: no cover - fallback sin base tz
        tz = timezone(timedelta(hours=-5))
    start_dt = datetime.fromtimestamp(start, tz)
    end_dt = datetime.fromtimestamp(end, tz)
    day = start_dt.date()
    total = 0
    guard = 0
    while day <= end_dt.date() and guard < 5000:
        guard += 1
        cutoff = datetime.combine(day, dtime(int(rollover_hour_ny), 0), tzinfo=tz)
        if day.weekday() < 5 and start_dt < cutoff <= end_dt:
            total += 3 if (triple_swap_weekday is not None and day.weekday() == int(triple_swap_weekday)) else 1
        day += timedelta(days=1)
    return total


def calculate_funding_cost(
    notional_usd: float,
    funding_rate_pct_per_interval: float,
    hours_held: float,
    side: str = "LONG",
    interval_hours: float = 8.0,
) -> Dict[str, Any]:
    """
    Funding Rate de perpetuos cripto: se liquida por cada intervalo completo retenido (8h por defecto).
    Tasa positiva: LONG paga y SHORT cobra; tasa negativa invierte el flujo.
    `funding_cost_usd` > 0 es costo; < 0 es crédito. No se aplica a operativa Spot (no genera funding).
    """
    notional = _require_non_negative("notional_usd", notional_usd)
    hours = _require_non_negative("hours_held", hours_held)
    interval = float(interval_hours)
    rate = float(funding_rate_pct_per_interval)
    if not math.isfinite(rate) or not math.isfinite(interval) or interval <= 0.0:
        raise ValueError("funding_rate_pct_per_interval e interval_hours deben ser finitos (intervalo > 0).")
    intervals = int(hours // interval)
    is_short = str(side or "LONG").strip().upper() in ("SHORT", "SELL")
    direction = -1.0 if is_short else 1.0
    cost = direction * notional * (rate / 100.0) * intervals
    return {
        "intervals": intervals,
        "side": "SHORT" if is_short else "LONG",
        "funding_rate_pct_per_interval": rate,
        "funding_cost_usd": round(cost, 8),
    }


def calculate_futures_pnl(
    symbol: str,
    entry_price: float,
    exit_price: float,
    contracts: float,
    side: str = "LONG",
    commission_per_side: Optional[float] = None,
    spread_ticks_per_side: Optional[float] = None,
    swap_usd: float = 0.0,
) -> Dict[str, Any]:
    """
    Calcula el PnL bruto y neto de contratos de micro-futuros CME por puntos y ticks:
      PnL_bruto = (exit - entry) * multiplicador * n_contratos  (LONG; inverso para SHORT)
      Fricción = comisiones (entrada + salida) + spread (ticks por lado x tick_value) + swap acumulado (USD).
      PnL_neto = PnL_bruto - fricción
    Con spread_ticks_per_side=0 y swap_usd=0 equivale al modelo original (solo comisiones fijas).
    """
    profile = build_futures_friction_profile(
        symbol,
        commission_per_side=commission_per_side,
        spread_ticks_per_side=spread_ticks_per_side,
    )
    if not all(map(math.isfinite, [float(entry_price), float(exit_price), float(contracts)])):
        raise ValueError("Precio de entrada/salida y número de contratos deben ser finitos.")
    n_contracts = float(contracts)
    if entry_price <= 0 or exit_price <= 0 or n_contracts <= 0:
        raise ValueError("Precios y número de contratos deben ser mayores que cero.")
    swap_cost = _require_non_negative("swap_usd", swap_usd)

    is_short = str(side or "LONG").strip().upper() in ("SHORT", "SELL")
    points_diff = (float(entry_price) - float(exit_price)) if is_short else (float(exit_price) - float(entry_price))
    ticks_diff = points_diff / profile.tick_size

    gross_pnl = points_diff * profile.multiplier * n_contracts
    entry_commission = profile.commission_per_side * n_contracts
    exit_commission = profile.commission_per_side * n_contracts
    total_commission = entry_commission + exit_commission
    entry_spread_cost = profile.spread_cost_per_side(n_contracts)
    exit_spread_cost = profile.spread_cost_per_side(n_contracts)
    spread_cost = entry_spread_cost + exit_spread_cost
    total_friction = total_commission + spread_cost + swap_cost
    net_pnl = gross_pnl - total_friction

    return {
        "symbol": profile.symbol,
        "asset_class": ASSET_CLASS_FUTURES_MICRO,
        "side": "SHORT" if is_short else "LONG",
        "contracts": n_contracts,
        "multiplier": profile.multiplier,
        "tick_size": profile.tick_size,
        "tick_value": profile.tick_value,
        "points_diff": round(points_diff, 6),
        "ticks_diff": round(ticks_diff, 6),
        "gross_pnl": round(gross_pnl, 4),
        "entry_commission": round(entry_commission, 4),
        "exit_commission": round(exit_commission, 4),
        "total_commission": round(total_commission, 4),
        "entry_spread_cost": round(entry_spread_cost, 4),
        "exit_spread_cost": round(exit_spread_cost, 4),
        "spread_cost": round(spread_cost, 4),
        "swap_cost": round(swap_cost, 4),
        "total_friction": round(total_friction, 4),
        "net_pnl": round(net_pnl, 4),
    }


def compute_futures_breakeven_price(
    symbol: str,
    entry_price: float,
    side: str,
    contracts: float,
    commission_per_side: Optional[float] = None,
    spread_ticks_per_side: Optional[float] = None,
    swap_usd: float = 0.0,
    round_to_tick: bool = True,
) -> Dict[str, Any]:
    """
    Precio de Break-Even Real de `contracts` contratos: nivel donde el PnL neto de esa pata es exactamente $0:
      costos = comisiones (entrada + salida) + spread (entrada + salida) + swap acumulado (USD)
      BE = entrada +/- costos / (multiplicador x contratos)
    Con `round_to_tick`, el BE se redondea hacia el lado protector (LONG: techo; SHORT: piso) al tick,
    de modo que liquidar en ese precio nunca arroja pérdida neta (excedente < 1 tick).
    """
    profile = build_futures_friction_profile(
        symbol,
        commission_per_side=commission_per_side,
        spread_ticks_per_side=spread_ticks_per_side,
    )
    px = float(entry_price)
    n_contracts = float(contracts)
    if not (math.isfinite(px) and math.isfinite(n_contracts)) or px <= 0 or n_contracts <= 0:
        raise ValueError("entry_price y contracts deben ser finitos y mayores que cero.")
    swap_total = _require_non_negative("swap_usd", swap_usd)

    commission_total = profile.commission_round_trip * n_contracts
    spread_total = profile.spread_cost_per_side(n_contracts) * 2.0
    total_friction = commission_total + spread_total + swap_total
    required_points = total_friction / (profile.multiplier * n_contracts)

    is_short = str(side or "LONG").strip().upper() in ("SHORT", "SELL")
    be_exact = px - required_points if is_short else px + required_points
    be_price = be_exact
    if round_to_tick:
        ticks = round(be_exact / profile.tick_size, 9)
        be_price = (math.floor(ticks) if is_short else math.ceil(ticks)) * profile.tick_size
    return {
        "symbol": profile.symbol,
        "side": "SHORT" if is_short else "LONG",
        "contracts": n_contracts,
        "be_price": round(be_price, 6),
        "be_price_exact": round(be_exact, 6),
        "required_points": round(required_points, 6),
        "required_ticks": round(required_points / profile.tick_size, 4),
        "commission_total": round(commission_total, 4),
        "spread_total": round(spread_total, 4),
        "swap_total": round(swap_total, 4),
        "total_friction": round(total_friction, 4),
    }


def get_asset_friction_costs(symbol: str, price: Optional[float] = None) -> Dict[str, Any]:
    """
    Retorna la estructura cuantitativa real de costos transaccionales (comisión y spread) por clase de activo:
    - Micro-Futuros CME ('MES=F', 'MNQ=F'): Clase 'FUTURES_MICRO', comisión fija $1.25/contrato por lado ($2.50 RT).
    - Criptomonedas ('/'): Fee 0.10% (Binance/Bybit spot), Spread 0.05%.
    - Forex Spot ('=X'): Fee 0.00% (Broker Standard sin comisión por ticket), Spread 0.012% (~1.2 pips).
    - Acciones / ETFs US (AAPL, NVDA, QQQ, SPY): Fee 0.00% (Broker Zero-Commission Alpaca/Robinhood), Spread 0.010%.
    - Futuros / Commodities ('=F'): Fee 0.00%, Spread 0.020%.
    - Acciones Locales BYMA ('.BA'): Fee 0.50% (Arancel de bolsa y broker argentino), Spread 0.100%.
    """
    sym = str(symbol or "").upper().strip()
    micro_spec = get_micro_futures_spec(sym)
    if micro_spec is not None:
        ref_px = float(price) if (price is not None and math.isfinite(float(price)) and float(price) > 0) else float(micro_spec["ref_price"])
        notional_per_contract = ref_px * float(micro_spec["multiplier"])
        fee_pct = round((float(micro_spec["commission_per_side"]) / notional_per_contract) * 100.0, 5)
        spread_pct = round((float(micro_spec["tick_size"]) / ref_px) * 100.0, 5)
        return {
            "fee_pct": fee_pct,
            "spread_pct": spread_pct,
            "asset_type": ASSET_CLASS_FUTURES_MICRO,
            "asset_class": ASSET_CLASS_FUTURES_MICRO,
            "multiplier": float(micro_spec["multiplier"]),
            "tick_size": float(micro_spec["tick_size"]),
            "tick_value": float(micro_spec["tick_value"]),
            "commission_per_contract_side": float(micro_spec["commission_per_side"]),
            "commission_round_trip_per_contract": float(micro_spec["commission_round_trip"]),
            "default_contracts": int(micro_spec["default_contracts"]),
        }
    if "=X" in sym:
        return {"fee_pct": 0.0, "spread_pct": 0.012, "asset_type": "FOREX"}
    elif "/" in sym:
        return {"fee_pct": 0.10, "spread_pct": 0.050, "asset_type": "CRYPTO"}
    elif ".BA" in sym:
        return {"fee_pct": 0.50, "spread_pct": 0.100, "asset_type": "BYMA"}
    elif "=F" in sym:
        return {"fee_pct": 0.0, "spread_pct": 0.020, "asset_type": "COMMODITIES"}
    else:
        return {"fee_pct": 0.0, "spread_pct": 0.010, "asset_type": "US_EQUITIES"}


# --- GOBERNANZA DE ASIMETRÍA NETA (auditoría 19-oct-2026) ---
# Con costos ida/vuelta ~0.3% un TP 0.8% / SL 0.5% tiene R:R neto 0.63 (requiere 61% de aciertos).
# Estos umbrales se aplican sobre retornos NETOS, nunca sobre movimientos brutos.
MIN_NET_RR: float = 1.5            # R:R neto mínimo aceptado para abrir una posición
TARGET_NET_RR: float = 2.0         # R:R neto objetivo al derivar un TP bruto
SL_ATR_NOISE_MULTIPLIER: float = 1.35  # el SL bruto debe ser >= 1.35 x ATR% (fuera del ruido; calibrado para Donchian 1.40x)
MIN_ENTRY_RVOL: float = 0.5        # volumen relativo mínimo para abrir (régimen sin volumen = ruido)
MAX_RISK_PER_TRADE_PCT: float = 0.5  # pérdida neta máxima por operación como % de la bóveda
SWEEP_BONUS_RISK_MULTIPLIER: float = 2.0  # Convicción 2X ante confirmación de barrido institucional (Trullás/Wyckoff)

# --- TRINQUETE Y ESCALABILIDAD DE BÓVEDA (ALEX RUIZ + CAVA) ---
VAULT_PROTECTION_FLOOR_USDT: float = 800.0       # Piso frío canónico de contrato unitario
DEMO_VAULT_PROTECTION_FLOOR_USDT: float = 350.0  # Piso operativo para Bóveda Demo de $500 USD (habilita dólares enteros)
MAX_SINGLE_TRADE_RISK_USD: float = 10.0          # Tope base de riesgo por trade ($10 USDT)
MIN_SINGLE_TRADE_RISK_USD: float = 5.0           # Piso mínimo de riesgo por trade ($5 USDT)
TARGET_VAULT_RISK_PCT: float = 1.0               # 1.0% de riesgo base sobre patrimonio total consolidado
DEFENSIVE_FLOOR_RISK_USD: float = 2.50           # Riesgo defensivo si la Bóveda toca o cae del piso


def calculate_vault_scaled_risk(
    total_equity: float,
    vault_balance: float,
    floor_usdt: float = VAULT_PROTECTION_FLOOR_USDT,
) -> Dict[str, Any]:
    """
    Calcula el presupuesto de riesgo en dólares escalado a la Bóveda Kula:
    - Si vault_balance > floor_usdt: arriesga 1.0% del patrimonio consolidado (entre $5 y $10 USD).
    - Si vault_balance <= floor_usdt: trinquete defensivo activado (arriesga solo $2.50 USD).
    """
    if vault_balance <= floor_usdt:
        risk_usd = DEFENSIVE_FLOOR_RISK_USD
        mode = "DEFENSIVE_FLOOR"
    else:
        calc_risk = total_equity * (TARGET_VAULT_RISK_PCT / 100.0)
        risk_usd = min(MAX_SINGLE_TRADE_RISK_USD, max(MIN_SINGLE_TRADE_RISK_USD, calc_risk))
        mode = "ACCUMULATION_SCALED"
    return {
        "risk_usd": round(risk_usd, 4),
        "mode": mode,
        "floor_usdt": floor_usdt,
        "total_equity": round(total_equity, 2),
    }


def calculate_guarded_stop_loss(
    price: float,
    support_price: Optional[float] = None,
    atr: Optional[float] = None,
    base_sl_pct: float = 1.0,
    tick_size: float = 0.01,
    symbol: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calcula el Stop Loss con el Blindaje Pasivo del Centinela (anti-Stop Hunt).
    Asegura que el Stop Loss nunca quede situado en el soporte evidente donde cazan las manos fuertes,
    añadiendo una holgura de invalidación estructural:
      invalid_margin = max(2 * tick_size, 0.20 * atr, 0.0015 * price)
      sl_gross_pct >= max(base_sl_pct, 1.5 * atr_pct, soporte_pct + invalid_margin_pct)
    """
    if not math.isfinite(price) or price <= 0:
        return {"sl_pct": base_sl_pct, "sl_price": 0.0, "margin_pct": 0.0, "is_guarded": False}

    is_forex = bool(symbol and "=X" in str(symbol).upper())
    eff_base_sl = 0.12 if (is_forex and base_sl_pct == 1.0) else base_sl_pct
    eff_tick = 0.0001 if (is_forex and tick_size == 0.01) else float(tick_size or (0.0001 if is_forex else 0.01))
    atr_val = float(atr or 0.0)
    atr_pct = (atr_val / price * 100.0) if (atr_val > 0 and price > 0) else 0.0

    # Margen de invalidación estructural de parqué (Cava / Trullás)
    invalid_margin_pts = max(2.0 * eff_tick, 0.20 * atr_val, (0.0004 if is_forex else 0.0015) * price)
    invalid_margin_pct = (invalid_margin_pts / price) * 100.0

    if support_price is not None and math.isfinite(support_price) and 0 < support_price < price:
        dist_to_support_pct = ((price - support_price) / price) * 100.0
        structural_sl_pct = dist_to_support_pct + invalid_margin_pct
    else:
        structural_sl_pct = eff_base_sl + invalid_margin_pct

    # El SL final debe estar siempre fuera del ruido ATR (mínimo 1.5x ATR) y respetar el soporte blindado
    final_sl_pct = round(max(eff_base_sl, SL_ATR_NOISE_MULTIPLIER * atr_pct, structural_sl_pct), 2)
    sl_price = round(price * (1.0 - final_sl_pct / 100.0), 5 if is_forex else 4)

    return {
        "sl_pct": final_sl_pct,
        "sl_price": sl_price,
        "margin_pct": round(invalid_margin_pct, 4),
        "is_guarded": True,
    }


def detect_institutional_sweep_bonus(
    df: Optional[Any] = None,
    rvol: Optional[float] = None,
    lower_wick_ratio: Optional[float] = None,
    current_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Detector de Huella Institucional (David Trullás / Wyckoff Spring):
    No es un peaje bloqueante. Actúa como un Acelerador de Convicción 2X.
    Condiciones de absorción por creadores de mercado:
    1. RVOL >= 1.5x (volumen anómalo institucional).
    2. Mecha inferior de absorción >= 35% del rango de la vela (rechazo de mínimos).
    3. Perforación y rescate de soporte previo (Spring) si se dispone de DataFrame de velas.
    """
    rvol_val = float(rvol or 1.0)
    wick_ratio = float(lower_wick_ratio or 0.0)

    # Verificación de soporte perforado y recuperado (Spring institucional)
    has_spring = False
    if df is not None and hasattr(df, "iloc") and len(df) >= 10:
        try:
            lookback = min(len(df), 25)
            sub = df.tail(lookback)
            last_c = sub.iloc[-1]
            prior_low = float(sub.iloc[:-1]["low"].min())
            if float(last_c["low"]) <= prior_low and float(last_c["close"]) > prior_low:
                has_spring = True
        except Exception:
            has_spring = False

    # Detección: RVOL >= 1.5x Y mecha inferior >= 35% (o confirmación de Spring con RVOL >= 1.3)
    sweep_detected = bool((rvol_val >= 1.5 and wick_ratio >= 0.35) or (has_spring and rvol_val >= 1.3))

    conviction_mult = SWEEP_BONUS_RISK_MULTIPLIER if sweep_detected else 1.0
    risk_pct = 0.50 if sweep_detected else 0.25

    return {
        "sweep_detected": sweep_detected,
        "conviction_multiplier": conviction_mult,
        "risk_budget_pct": risk_pct,
        "rvol": round(rvol_val, 2),
        "lower_wick_ratio": round(wick_ratio, 3),
        "has_spring": has_spring,
        "reason": (
            "🦈 BARRIDO INSTITUCIONAL DETECTADO (CONVICCIÓN 2X): Volumen de absorción RVOL "
            f"{rvol_val:.2f} con rechazo {wick_ratio * 100:.1f}%."
            if sweep_detected
            else "Operativa estándar 1X (régimen normal sin barrido extremo)."
        ),
    }


def net_rr_metrics(tp_gross_pct: float, sl_gross_pct: float, fee_pct: float, spread_pct: float) -> Dict[str, Any]:
    """
    R:R neto y tasa de acierto de equilibrio para un par TP/SL brutos.
      tp_net = net_return_after_costs(+tp), sl_net = |net_return_after_costs(-sl)|
      R:R_neto = tp_net / sl_net
      win_rate_equilibrio = sl_net / (tp_net + sl_net)
    """
    tp_net = net_return_after_costs(tp_gross_pct, fee_pct, spread_pct)
    sl_net_signed = net_return_after_costs(-abs(sl_gross_pct), fee_pct, spread_pct)
    if not (math.isfinite(tp_net) and math.isfinite(sl_net_signed)) or sl_net_signed >= 0 or tp_net <= 0:
        return {"tp_net_pct": tp_net, "sl_net_pct": sl_net_signed, "net_rr": 0.0, "breakeven_win_rate": 1.0, "valid": False}
    sl_net = abs(sl_net_signed)
    return {
        "tp_net_pct": round(tp_net, 4),
        "sl_net_pct": round(sl_net_signed, 4),
        "net_rr": round(tp_net / sl_net, 4),
        "breakeven_win_rate": round(sl_net / (tp_net + sl_net), 4),
        "valid": True,
    }


def gross_target_for_net(net_target_pct: float, fee_pct: float, spread_pct: float) -> float:
    """
    Inversa de net_return_after_costs: movimiento BRUTO necesario para obtener `net_target_pct` neto.
      gross = ((1 + net/100) * entry_factor / exit_factor - 1) * 100
    """
    entry_cost_factor = (1 + fee_pct / 100) * (1 + spread_pct / 100)
    exit_proceeds_factor = (1 - fee_pct / 100) * (1 - spread_pct / 100)
    return ((1 + net_target_pct / 100) * entry_cost_factor / exit_proceeds_factor - 1) * 100


def required_tp_gross_for_rr(sl_gross_pct: float, fee_pct: float, spread_pct: float, target_rr: float = TARGET_NET_RR) -> float:
    """TP bruto que logra `target_rr` neto dado un SL bruto (incluye el costo en ambos lados de la ecuación)."""
    sl_net = abs(net_return_after_costs(-abs(sl_gross_pct), fee_pct, spread_pct))
    return round(gross_target_for_net(target_rr * sl_net, fee_pct, spread_pct), 4)


def net_pnl_pct_from_prices(
    entry_price: float,
    price: float,
    fee_pct: float,
    spread_pct: float,
    side: str = "LONG",
) -> float:
    """PnL neto (%) de una posición (LONG o SHORT) con la misma ecuación compuesta que el resto del sistema."""
    if not entry_price or entry_price <= 0 or not price or price <= 0:
        return 0.0
    is_short = str(side or "LONG").upper() in ("SHORT", "SELL")
    gross_pct = (
        ((entry_price - price) / entry_price) * 100.0
        if is_short
        else ((price / entry_price) - 1.0) * 100.0
    )
    return net_return_after_costs(gross_pct, fee_pct, spread_pct)


def risk_sized_qty(
    capital: float,
    price: float,
    sl_gross_pct: float,
    fee_pct: float,
    spread_pct: float,
    risk_budget_pct: float = MAX_RISK_PER_TRADE_PCT,
    max_notional_pct: float = 50.0,
    risk_budget_usd: Optional[float] = None,
) -> float:
    """
    Cantidad tal que la pérdida NETA al Stop (precio + comisiones + spread) no excede el presupuesto de riesgo:
    - Si se especifica `risk_budget_usd`: usa el monto en dólares exacto (ej. $10.00 USD).
    - De lo contrario: usa `capital * risk_budget_pct / 100.0`.
    El nocional queda acotado a max_notional_pct del capital (evita sobre-exposición).
    """
    if capital <= 0 or price <= 0:
        return 0.0
    sl_net = abs(net_return_after_costs(-abs(sl_gross_pct), fee_pct, spread_pct))
    if not math.isfinite(sl_net) or sl_net <= 0:
        return 0.0
    target_loss = (
        float(risk_budget_usd)
        if (risk_budget_usd is not None and risk_budget_usd > 0)
        else (capital * risk_budget_pct / 100.0)
    )
    qty_risk = target_loss / (price * sl_net / 100.0)
    qty_cap = (capital * max_notional_pct / 100.0) / price
    return min(qty_risk, qty_cap)


def calculate_net_expected_value(
    win_rate: float,
    r_win_gross_pct: float,
    r_loss_gross_pct: float,
    fee_per_side_pct: float,
    spread_per_side_pct: float,
    slippage_pct: float = 0.0,
) -> Dict[str, Any]:
    """
    Calcula la esperanza matemática neta (EV_neto) deduciendo comisiones, spread y slippage.

    Parámetros:
      win_rate: P_w en escala fraccionaria [0.0, 1.0].
      r_win_gross_pct: movimiento bruto proyectado al Take Profit (ej. 2.5%).
      r_loss_gross_pct: movimiento bruto proyectado al Stop Loss (positivo, ej. 1.5%).
      fee_per_side_pct: comisión por orden del broker (ej. 0.10 para 0.10%).
      spread_per_side_pct: medio-spread por orden (ej. 0.05 para 0.05%).
      slippage_pct: deslizamiento estimado total (ej. 0.02 para 0.02%).
    """
    params = [win_rate, r_win_gross_pct, r_loss_gross_pct, fee_per_side_pct, spread_per_side_pct, slippage_pct]
    if not all(map(math.isfinite, params)):
        return {"viable": False, "ev_net_pct": float("nan"), "error": "Parámetro no finito"}

    if not (0.0 <= win_rate <= 1.0):
        return {"viable": False, "ev_net_pct": float("nan"), "error": "win_rate debe estar entre 0.0 y 1.0"}

    if r_win_gross_pct <= 0 or r_loss_gross_pct <= 0:
        return {"viable": False, "ev_net_pct": float("nan"), "error": "Los recorridos brutos deben ser positivos"}

    if fee_per_side_pct < 0 or spread_per_side_pct < 0 or slippage_pct < 0:
        return {"viable": False, "ev_net_pct": float("nan"), "error": "Costos y slippage deben ser no negativos"}

    # Retorno neto al acierto (descuenta comisiones de entrada y salida, spread y slippage)
    r_win_net = net_return_after_costs(r_win_gross_pct, fee_per_side_pct, spread_per_side_pct) - slippage_pct

    # Retorno neto al fallo (negativo, acumulando la pérdida de precio más todos los costos)
    r_loss_net = net_return_after_costs(-r_loss_gross_pct, fee_per_side_pct, spread_per_side_pct) - slippage_pct

    if not (math.isfinite(r_win_net) and math.isfinite(r_loss_net)):
        return {"viable": False, "ev_net_pct": float("nan"), "error": "Cálculo de retorno neto inválido"}

    ev_net_pct = (win_rate * r_win_net) + ((1.0 - win_rate) * r_loss_net)

    return {
        "viable": ev_net_pct > 0 and r_win_net > 0,
        "ev_net_pct": round(ev_net_pct, 6),
        "r_win_net_pct": round(r_win_net, 6),
        "r_loss_net_pct": round(r_loss_net, 6),
        "is_positive": ev_net_pct > 0,
        "payoff_ratio": round(abs(r_win_net) / abs(r_loss_net), 4) if abs(r_loss_net) > 0 else 0.0,
    }


def calculate_quarter_kelly(
    win_rate: float,
    r_win_net_pct: float,
    r_loss_net_pct: float,
    max_risk_budget_pct: float = 0.01,
) -> Dict[str, Any]:
    """
    Calcula la fracción de Quarter-Kelly f_seguro = 0.25 * ((P_w * b - (1 - P_w)) / b).
    Retorna asignación cero (0.0) si la esperanza neta no es positiva o si Kelly <= 0.
    """
    if not all(map(math.isfinite, [win_rate, r_win_net_pct, r_loss_net_pct, max_risk_budget_pct])):
        return {"viable": False, "quarter_kelly_fraction": 0.0, "allocated_risk_budget": 0.0, "reason": "Entrada no finita"}

    if not (0.0 <= win_rate <= 1.0):
        return {"viable": False, "quarter_kelly_fraction": 0.0, "allocated_risk_budget": 0.0, "reason": "win_rate fuera de [0, 1]"}

    if r_win_net_pct <= 0 or r_loss_net_pct >= 0:
        return {"viable": False, "quarter_kelly_fraction": 0.0, "allocated_risk_budget": 0.0, "reason": "Retornos netos inconsistentes"}

    abs_loss = abs(r_loss_net_pct)
    if abs_loss <= 0:
        return {"viable": False, "quarter_kelly_fraction": 0.0, "allocated_risk_budget": 0.0, "reason": "Pérdida neta nula"}

    b = r_win_net_pct / abs_loss
    if b <= 0:
        return {"viable": False, "quarter_kelly_fraction": 0.0, "allocated_risk_budget": 0.0, "reason": "Payoff ratio no positivo"}

    # Esperanza neta: si no es positiva, asignación estrictamente cero
    ev_check = (win_rate * r_win_net_pct) + ((1.0 - win_rate) * r_loss_net_pct)
    if ev_check <= 0:
        return {
            "viable": False,
            "full_kelly_fraction": 0.0,
            "quarter_kelly_fraction": 0.0,
            "allocated_risk_budget": 0.0,
            "payoff_ratio": round(b, 4),
            "reason": f"Esperanza matemática neta no es positiva ({ev_check:.4f}%)",
        }

    full_kelly = (win_rate * b - (1.0 - win_rate)) / b
    if full_kelly <= 0:
        return {
            "viable": False,
            "full_kelly_fraction": 0.0,
            "quarter_kelly_fraction": 0.0,
            "allocated_risk_budget": 0.0,
            "payoff_ratio": round(b, 4),
            "reason": "Fracción de Kelly menor o igual a cero",
        }

    quarter_kelly = 0.25 * full_kelly
    capped_budget = min(quarter_kelly, max(0.0, max_risk_budget_pct))

    return {
        "viable": True,
        "full_kelly_fraction": round(full_kelly, 6),
        "quarter_kelly_fraction": round(quarter_kelly, 6),
        "allocated_risk_budget": round(capped_budget, 6),
        "payoff_ratio": round(b, 4),
        "ev_net_pct": round(ev_check, 6),
    }


def estimate_out_of_sample_win_rate(
    trade_outcomes: List[Any],
    min_sample_size: int = 30,
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    """
    Estima la probabilidad de acierto con intervalo de confianza de Wilson (límite inferior).
    Exige una muestra mínima (N >= min_sample_size) fuera de muestra; de lo contrario declara
    la estimación como no validada y rechaza habilitar Kelly.
    """
    if not isinstance(trade_outcomes, list):
        return {"valid": False, "reason": "trade_outcomes debe ser una lista", "sample_size": 0}

    n = len(trade_outcomes)
    if n < min_sample_size:
        return {
            "valid": False,
            "sample_size": n,
            "min_required": min_sample_size,
            "p_w_point": None,
            "p_w_conservative": None,
            "reason": f"Muestra insuficiente ({n} < {min_sample_size}) para validación estadística fuera de muestra.",
        }

    # Contar aciertos (booleanos True o flotantes netos > 0)
    wins = 0
    for outcome in trade_outcomes:
        if isinstance(outcome, bool) and outcome:
            wins += 1
        elif isinstance(outcome, (int, float)) and outcome > 0:
            wins += 1

    p_hat = wins / n

    # Valor crítico z para intervalo de Wilson (95% -> z=1.96, 90% -> z=1.645)
    z = 1.96 if confidence_level >= 0.95 else 1.645
    denom = 1.0 + (z**2) / n
    center = p_hat + (z**2) / (2 * n)
    margin = z * math.sqrt((p_hat * (1.0 - p_hat) / n) + ((z**2) / (4 * (n**2))))
    p_lower = max(0.0, (center - margin) / denom)
    p_upper = min(1.0, (center + margin) / denom)

    return {
        "valid": True,
        "sample_size": n,
        "wins": wins,
        "p_w_point": round(p_hat, 4),
        "p_w_conservative": round(p_lower, 4),
        "p_w_upper": round(p_upper, 4),
        "confidence_level": confidence_level,
    }


def get_atr_strategy_risk_status() -> Dict[str, Any]:
    """
    Devuelve el estado de gobernanza del Criterio de Kelly y dimensionamiento cuantitativo.
    Kelly permanece APAGADO por defecto hasta contar con dataset walk-forward validado.
    """
    return {
        "kelly_active": False,
        "default_mode": "fixed_risk_budget",
        "fixed_risk_budget_pct": 0.0025,  # 0.25% del capital por trade
        "status": "PENDIENTE_DE_VALIDACION_OUT_OF_SAMPLE",
        "reason": (
            "No se dispone de muestra histórica etiquetada fuera de muestra suficiente (N >= 30) "
            "evaluada en walk-forward con costos reales para validar estadísticamente P_w."
        ),
        "required_validations": [
            "Dataset histórico local OHLCV de 15m/1h etiquetado sin data-snooping",
            "Muestra out-of-sample evaluada en walk-forward con N >= 30 operaciones",
            "Verificación de slippage real en libros de órdenes institucionales",
            "Límite inferior conservador de Wilson score para P_w > 0.50 neto",
        ],
    }


def quantize_decimal(value: float, decimals: int = 8) -> float:
    """Redondeo determinista Decimal (ROUND_HALF_UP) para evitar deriva IEEE-754."""
    from decimal import Decimal, ROUND_HALF_UP
    if not math.isfinite(float(value)):
        return 0.0
    q = Decimal("10") ** (-int(decimals))
    return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def normalize_order_qty(exchange_inst: Any, symbol: str, raw_qty: float, price: float) -> float:
    """
    Normaliza la cantidad de orden respetando stepSize y minNotional del exchange cuando están cargados,
    o aplicando truncamiento seguro Decimal sin exceder el presupuesto disponible.
    """
    from decimal import Decimal, ROUND_DOWN
    if not math.isfinite(float(raw_qty)) or raw_qty <= 0 or not math.isfinite(float(price)) or price <= 0:
        return 0.0
    if "/" in symbol and exchange_inst is not None:
        try:
            markets = getattr(exchange_inst, "markets", None)
            if markets and symbol in markets:
                precise_qty = float(exchange_inst.amount_to_precision(symbol, raw_qty))
                market = markets.get(symbol, {})
                min_cost = float((market.get("limits", {}).get("cost") or {}).get("min") or 0.0)
                if min_cost > 0 and (precise_qty * price) < min_cost:
                    return 0.0
                return precise_qty
        except Exception:
            pass
    step = Decimal("0.00000001") if "/" in symbol else Decimal("0.000001")
    return float(Decimal(str(raw_qty)).quantize(step, rounding=ROUND_DOWN))

