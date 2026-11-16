from typing import Dict, Any, List, Optional
import sqlite3
import uuid
from backend.execution.broker_base import BrokerAdapter
from backend.db.ledger import LedgerStore, symbol_to_currency


class PaperBrokerAdapter(BrokerAdapter):
    """
    Implementación transaccional de Paper Trading sobre BrokerAdapter (Fase 5).
    Respaldada por LedgerStore (SQLite de doble partida):
    - Aislamiento por defecto: Billeteras operativas en $0.00.
    - Just-In-Time Funding (ALLOCATE) al abrir entrada.
    - Sweep-Back Automático (SWEEP_BACK) al cerrar o liquidar por flatten().
    """

    def __init__(
        self,
        initial_vault_usd: float = 500.0,
        db_path: str = ":memory:",
        fee_pct: float = 0.10,
    ):
        self.vault_usd = initial_vault_usd
        self.fee_pct = fee_pct
        self.ledger = LedgerStore(
            db_path=db_path,
            initial_vault={
                "USDT": initial_vault_usd,
                "USD": initial_vault_usd,
                "ARS": initial_vault_usd * 1000.0,
            },
        )
        self.protection_orders: Dict[str, Dict[str, Any]] = {}

    @property
    def balances(self) -> Dict[str, float]:
        """Retorna los saldos actuales de las billeteras operativas (en reposo siempre $0.0)."""
        return self.ledger.get_omnibus_balances()["operational"]

    @property
    def vault_balances(self) -> Dict[str, float]:
        """Retorna los saldos actuales de la Bóveda Central por divisa."""
        return self.ledger.get_omnibus_balances()["vault"]

    @property
    def operating_capital_balances(self) -> Dict[str, float]:
        """Retorna los saldos asignados para operar en la mesa de trading."""
        return self.ledger.get_omnibus_balances()["operating_capital"]

    def get_operating_capital(self, currency: str = "USDT") -> float:
        """Retorna el capital asignado para operar en una divisa específica."""
        return self.ledger.get_operating_capital(currency)

    def set_operating_capital(self, currency: str, amount: float) -> float:
        """Establece el monto de capital asignado a la operativa de trading."""
        return self.ledger.set_operating_capital(currency, amount)

    def transfer_to_operating(self, currency: str, amount: float) -> float:
        """Transfiere capital desde la reserva pasiva del broker hacia la cuenta de operar."""
        return self.ledger.transfer_to_operating(currency, amount)

    def return_to_broker(self, currency: str, amount: float) -> float:
        """Devuelve capital desde la cuenta de operar hacia la tesorería pasiva del broker."""
        return self.ledger.return_to_broker(currency, amount)

    def deposit(self, amount: float, currency: str = "USDT") -> float:
        """Deposita fondos en la Bóveda del Paper Broker."""
        return self.ledger.deposit(amount=amount, currency=currency)

    def withdraw(self, amount: float, currency: str = "USDT") -> float:
        """Retira fondos de la Bóveda del Paper Broker."""
        return self.ledger.withdraw(amount=amount, currency=currency)

    def reset_account(self, initial_amount: float = 500.0) -> Dict[str, float]:
        """Reinicia la cuenta contable y cancela protecciones."""
        self.protection_orders.clear()
        return self.ledger.reset_account(initial_amount=initial_amount)

    def get_futures_account(self) -> Dict[str, Any]:
        """Retorna el estado aislado de la cuenta simulada de micro-futuros (SIM_FUTURES)."""
        return self.ledger.get_futures_sim_account()

    def accrue_futures_swap(self, symbol: str, now_ts: Optional[float] = None) -> Dict[str, Any]:
        """Devenga el swap pendiente por cortes de jornada superados y recalcula el Break-Even Real (solo futuros)."""
        try:
            return self.ledger.accrue_futures_swap(symbol, now_ts=now_ts)
        except (ValueError, sqlite3.Error) as exc:
            return {"accrued": False, "symbol": symbol, "nights": 0, "swap_charged": 0.0, "be_price": None, "error": str(exc)}

    def get_futures_breakeven(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Break-Even Real vigente de la posición abierta de futuros con desglose de costos acumulados."""
        from backend.quant_risk import get_micro_futures_spec

        spec = get_micro_futures_spec(symbol)
        canon = spec["symbol"] if spec else symbol
        pos = next((p for p in self.ledger.get_open_futures_positions() if p["symbol"] == canon), None)
        if pos is None:
            return None
        return {
            "symbol": canon,
            "side": pos["side"],
            "contracts": float(pos["contracts"]),
            "entry_price": float(pos["entry_price"]),
            "be_price": float(pos["be_price"]) if pos.get("be_price") else None,
            "entry_commission": float(pos.get("entry_commission") or 0.0),
            "exit_commission": float(pos.get("exit_commission") or 0.0),
            "spread_cost": float(pos.get("spread_cost") or 0.0),
            "swap_cost": float(pos.get("swap_cost") or 0.0),
            "breakdown": self.ledger.get_futures_cost_breakdown(str(pos["id"])),
        }

    def get_futures_balance(self) -> float:
        """Retorna el saldo disponible en la cuenta virtual aislada de micro-futuros."""
        return float(self.ledger.get_futures_sim_account().get("balance", 0.0))

    def reset_futures_account(self, initial_balance: float = 2500.0) -> Dict[str, Any]:
        """Reinicia la cuenta simulada de micro-futuros sin afectar USDT/USD/ARS."""
        from backend.quant_risk import is_micro_futures_symbol
        for oid, odata in list(self.protection_orders.items()):
            if is_micro_futures_symbol(str(odata.get("symbol", ""))):
                self.protection_orders.pop(oid, None)
        return self.ledger.reset_futures_sim_account(initial_balance=initial_balance)

    def get_symbol_fee_pct(self, symbol: str) -> float:
        """Determina la tasa de comisión real por clase de activo (Forex/Acciones = 0.0%, Cripto = 0.10%)."""
        from backend.quant_risk import get_asset_friction_costs
        costs = get_asset_friction_costs(symbol)
        return float(costs["fee_pct"])

    def place_entry(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        initial_tp_pct: float = 0.8,
        initial_sl_pct: float = 0.5,
        strategy: str = "trailing_trend_runner",
        engine: str = "antigravity_operador",
        formula: str = "Quant Risk ATR",
        friction: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta una orden de entrada simulada con fondeo Just-In-Time desde la Bóveda
        (o en la cuenta aislada SIM_FUTURES para micro-futuros MES/MNQ).
        """
        exec_price = float(price or 0.0)
        if exec_price <= 0:
            return {
                "status": "simulated",
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": 0.0,
                "order_type": order_type,
            }

        from backend.quant_risk import is_micro_futures_symbol

        if is_micro_futures_symbol(symbol):
            n_contracts = float(int(max(1, round(qty))))
            fut_info = self.ledger.open_futures_trade(
                symbol=symbol,
                contracts=n_contracts,
                entry_price=exec_price,
                initial_tp_pct=initial_tp_pct,
                initial_sl_pct=initial_sl_pct,
                side="LONG" if side.upper() in ("BUY", "LONG") else "SHORT",
                strategy=strategy,
                engine=engine,
                formula=formula,
                spread_ticks_per_side=(friction or {}).get("spread_ticks_per_side"),
                swap_per_contract_night=(friction or {}).get("swap_per_contract_night"),
                now_ts=(friction or {}).get("now_ts"),
            )
            return {
                "status": "FILLED",
                "trade_id": fut_info["trade_id"],
                "order_id": f"fut-entry-{fut_info['trade_id'][:12]}",
                "symbol": fut_info["symbol"],
                "asset_class": "FUTURES_MICRO",
                "side": side.upper(),
                "qty": n_contracts,
                "contracts": n_contracts,
                "price": exec_price,
                "fee_amount": fut_info["fee_amount"],
                "entry_commission": fut_info["entry_commission"],
                "entry_spread_cost": fut_info["entry_spread_cost"],
                "be_price": fut_info["be_price"],
                "allocated_jit": 0.0,
                "futures_balance": fut_info["futures_balance"],
                "order_type": order_type,
            }

        fee_rate = self.get_symbol_fee_pct(symbol)
        fee_amount = round(qty * exec_price * (fee_rate / 100.0), 8)
        trade_info = self.ledger.open_trade_with_jit(
            symbol=symbol,
            qty=qty,
            entry_price=exec_price,
            fee_amount=fee_amount,
            initial_tp_pct=initial_tp_pct,
            initial_sl_pct=initial_sl_pct,
            side="LONG" if side.upper() in ("BUY", "LONG") else "SHORT",
            strategy=strategy,
            engine=engine,
            formula=formula,
        )
        return {
            "status": "FILLED",
            "trade_id": trade_info["trade_id"],
            "order_id": trade_info["order_id"],
            "symbol": symbol,
            "side": side.upper(),
            "qty": qty,
            "price": exec_price,
            "fee_amount": fee_amount,
            "allocated_jit": trade_info["allocated_jit"],
            "order_type": order_type,
        }

    def place_protection(
        self,
        symbol: str,
        qty: float,
        stop_loss_price: float,
        take_profit_price: float,
        side: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Coloca una orden bracket / OCO de protección vinculada a la posición abierta."""
        is_short = False
        if side is not None:
            is_short = str(side).upper() == "SHORT"
        else:
            open_pos = next((p for p in self.ledger.get_open_positions() if p["symbol"] == symbol), None)
            if open_pos:
                is_short = str(open_pos.get("side") or "").upper() == "SHORT"

        is_invalid = (
            stop_loss_price <= 0
            or take_profit_price <= 0
            or (stop_loss_price <= take_profit_price if is_short else stop_loss_price >= take_profit_price)
        )
        if is_invalid:
            # Si la protección es inválida o rechazada, protocolo obligatorio: flatten inmediato
            self.flatten(symbol, current_price=max(stop_loss_price, 1.0))
            raise ValueError("Orden de protección inválida; posición cerrada por seguridad (flatten).")

        order_id = f"oco-{uuid.uuid4().hex[:12]}"
        order_data = {
            "order_id": order_id,
            "status": "NEW",
            "symbol": symbol,
            "qty": qty,
            "stop_loss": stop_loss_price,
            "take_profit": take_profit_price,
        }
        self.protection_orders[order_id] = order_data
        return order_data

    def amend_protection(
        self,
        protection_order_id: str,
        new_stop_price: float,
        new_tp_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Actualiza dinámicamente el stop price por Breakeven o Trailing Stop."""
        order = self.protection_orders.get(protection_order_id)
        if order:
            order["stop_loss"] = new_stop_price
            if new_tp_price is not None:
                order["take_profit"] = new_tp_price
        return {
            "status": "AMENDED" if order else "simulated",
            "order_id": protection_order_id,
            "new_stop": new_stop_price,
            "new_tp": new_tp_price,
        }

    def cancel_protection(self, protection_order_id: str) -> bool:
        """Cancela una orden de protección activa."""
        order = self.protection_orders.pop(protection_order_id, None)
        if order:
            order["status"] = "CANCELLED"
        return True

    def update_position_trailing(
        self,
        trade_id: str,
        peak_price: float,
        current_stop_net_pct: float,
        be_armed: int = 1,
        trail_active: int = 0,
        trailing_mode: Optional[str] = None,
        ai_decision_reason: Optional[str] = None,
        counterfactual_diff: Optional[float] = None,
        time_decay_hours: Optional[float] = None,
        time_decay_status: Optional[str] = None,
        time_decay_suggestion: Optional[str] = None,
    ) -> bool:
        """Sincroniza la subida de stop por Breakeven, Trailing o decaimiento temporal en SQLite y memoria."""
        return self.ledger.update_trade_trailing(
            trade_id=trade_id,
            peak_price=peak_price,
            current_stop_net_pct=current_stop_net_pct,
            be_armed=be_armed,
            trail_active=trail_active,
            trailing_mode=trailing_mode,
            ai_decision_reason=ai_decision_reason,
            counterfactual_diff=counterfactual_diff,
            time_decay_hours=time_decay_hours,
            time_decay_status=time_decay_status,
            time_decay_suggestion=time_decay_suggestion,
        )

    def flatten(
        self,
        symbol: str,
        current_price: Optional[float] = None,
        exit_reason: str = "EMERGENCY_FLATTEN",
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Cierre de emergencia a mercado: liquida la posición abierta en `symbol`
        y ejecuta el Sweep-Back inmediato a la Bóveda (o liquidación aislada para micro-futuros).
        """
        from backend.quant_risk import is_micro_futures_symbol, get_micro_futures_spec

        target_sym = symbol
        if is_micro_futures_symbol(symbol):
            spec = get_micro_futures_spec(symbol)
            target_sym = spec["symbol"] if spec else symbol

        open_positions = [p for p in self.ledger.get_open_positions() if p["symbol"] in (symbol, target_sym)]
        # Cancelar cualquier protección activa del símbolo
        for oid, odata in list(self.protection_orders.items()):
            if odata.get("symbol") in (symbol, target_sym):
                self.protection_orders.pop(oid, None)

        if not open_positions:
            return {"status": "simulated_flattened", "symbol": symbol, "closed": False}

        pos = open_positions[0]
        exit_px = float(current_price if current_price and current_price > 0 else pos["entry_price"])
        if is_micro_futures_symbol(symbol):
            fut_res = self.ledger.close_futures_trade(
                symbol=target_sym,
                exit_price=exit_px,
                exit_reason=exit_reason or "EMERGENCY_FLATTEN",
                now_ts=now_ts,
            )
            return {
                "status": "simulated_flattened",
                "symbol": target_sym,
                "asset_class": "FUTURES_MICRO",
                "closed": True,
                "exit_price": exit_px,
                "gross_pnl": fut_res["gross_pnl"],
                "net_pnl": fut_res["net_pnl"],
                "leg_net_pnl": fut_res["leg_net_pnl"],
                "total_fees": fut_res["total_fees"],
                "spread_cost": fut_res["spread_cost"],
                "swap_cost": fut_res["swap_cost"],
                "swap_nights": fut_res["swap_nights"],
                "futures_balance": fut_res["futures_balance"],
                "swept_to_vault": 0.0,
                "operational_balance": 0.0,
                "vault_balance": fut_res["futures_balance"],
            }

        qty = float(pos["qty"])
        fee_rate = self.get_symbol_fee_pct(symbol)
        exit_fee = round(qty * exit_px * (fee_rate / 100.0), 8)
        sweep_res = self.ledger.close_trade_with_sweep(
            symbol=symbol,
            exit_price=exit_px,
            exit_fee_amount=exit_fee,
            exit_reason=exit_reason or "EMERGENCY_FLATTEN",
        )
        return {
            "status": "simulated_flattened",
            "symbol": symbol,
            "closed": True,
            "exit_price": exit_px,
            "net_pnl": sweep_res["net_pnl"],
            "swept_to_vault": sweep_res["swept_to_vault"],
            "operational_balance": sweep_res["operational_balance"],
            "vault_balance": sweep_res["vault_balance"],
            "risk_state": sweep_res["risk_state"],
        }

    def trim_position(
        self,
        symbol: str,
        trim_qty: float,
        current_price: Optional[float] = None,
        reason: str = "PARTIAL_TRIM_TP1",
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Toma parcial de ganancias (Trimming / Peluqueo):
        Liquida `trim_qty` de la posición abierta, transfiere ganancias a la Bóveda
        y ajusta el Stop Loss del remanente a Breakeven.
        """
        from backend.quant_risk import is_micro_futures_symbol, get_micro_futures_spec

        target_sym = symbol
        if is_micro_futures_symbol(symbol):
            spec = get_micro_futures_spec(symbol)
            target_sym = spec["symbol"] if spec else symbol

        open_positions = [p for p in self.ledger.get_open_positions() if p["symbol"] in (symbol, target_sym)]
        if not open_positions:
            return {"status": "no_open_position", "symbol": symbol, "trimmed": False}

        pos = open_positions[0]
        exit_px = float(current_price if current_price and current_price > 0 else pos["entry_price"])
        if is_micro_futures_symbol(symbol):
            trim_contracts = float(max(1, int(round(trim_qty))))
            fut_trim = self.ledger.trim_futures_trade(
                symbol=target_sym,
                trim_contracts=trim_contracts,
                exit_price=exit_px,
                exit_reason=reason,
                now_ts=now_ts,
            )
            return {
                "status": "trimmed",
                "symbol": target_sym,
                "asset_class": "FUTURES_MICRO",
                "trimmed": True,
                "trimmed_qty": fut_trim["trimmed_qty"],
                "remaining_qty": fut_trim["remaining_qty"],
                "exit_price": exit_px,
                "gross_pnl": fut_trim["gross_pnl"],
                "net_pnl": fut_trim["net_pnl"],
                "be_price": fut_trim["be_price"],
                "commission_leg": fut_trim["commission_leg"],
                "spread_cost_leg": fut_trim["spread_cost_leg"],
                "swap_cost_leg": fut_trim["swap_cost_leg"],
                "swap_nights": fut_trim["swap_nights"],
                "futures_balance": fut_trim["futures_balance"],
                "swept_to_vault": 0.0,
                "operational_balance": 0.0,
                "vault_balance": fut_trim["futures_balance"],
            }

        fee_rate = self.get_symbol_fee_pct(symbol)
        exit_fee = round(trim_qty * exit_px * (fee_rate / 100.0), 8)
        trim_res = self.ledger.trim_trade_with_sweep(
            symbol=symbol,
            trim_qty=trim_qty,
            exit_price=exit_px,
            exit_fee_amount=exit_fee,
            exit_reason=reason,
        )
        return {
            "status": "trimmed",
            "symbol": symbol,
            "trimmed": True,
            "trimmed_qty": trim_res["trimmed_qty"],
            "remaining_qty": trim_res["remaining_qty"],
            "exit_price": exit_px,
            "net_pnl": trim_res["net_pnl"],
            "swept_to_vault": trim_res["swept_to_vault"],
            "operational_balance": trim_res.get("operational_balance"),
            "vault_balance": trim_res["vault_balance"],
        }

    def scale_in_position(
        self,
        symbol: str,
        add_amount_currency: float,
        current_price: float,
        source_mode: str = "OPERATING_POOL",
        enforce_safe_profit_lock: bool = True,
    ) -> Dict[str, Any]:
        """
        Piramidación con Riesgo Cero (Potenciar Ganadora):
        Inyecta `add_amount_currency` a una posición abierta en ganancia, recalculando
        el precio promedio ponderado y asegurando el Stop Loss por encima del nuevo promedio.
        """
        fee_rate = self.get_symbol_fee_pct(symbol)
        fee_amount = round(float(add_amount_currency) * (fee_rate / 100.0), 8)
        return self.ledger.scale_in_trade_with_jit(
            symbol=symbol,
            add_amount_currency=add_amount_currency,
            current_price=current_price,
            fee_amount=fee_amount,
            source_mode=source_mode,
            enforce_safe_profit_lock=enforce_safe_profit_lock,
        )

    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna las órdenes de protección actualmente activas."""
        if symbol:
            return [o for o in self.protection_orders.values() if o.get("symbol") == symbol]
        return list(self.protection_orders.values())

    def fetch_positions(self) -> List[Dict[str, Any]]:
        """Retorna las posiciones actualmente abiertas en el Ledger."""
        return self.ledger.get_open_positions()

    def fetch_balances(self) -> Dict[str, float]:
        """Retorna saldos operativos actuales."""
        return dict(self.balances)

    def fetch_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna el historial de operaciones desde el Ledger SQLite."""
        return self.ledger.get_trade_history(limit=limit)
