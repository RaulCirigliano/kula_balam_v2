"""
Motor Contable Transaccional de Doble Partida (SQLite) - Arquitectura Cuentas Ómnibus.
Implementa las directivas estrictas de GEMINI.md y CONTEXTO.md (Sección 6.1 y 6.5):
1. Aislamiento por defecto: Billeteras operativas (USDT, USD, ARS) inician siempre en $0.00.
2. Just-In-Time Funding (ALLOCATE): Transferencia exacta de Bóveda a Billetera Operativa al abrir un trade.
3. Sweep-Back Automático (SWEEP_BACK): Al cerrar posición, capital base + PnL neto regresan inmediatamente a la Bóveda,
   restaurando la Billetera Operativa a $0.00.
4. Invariante de Doble Partida: Toda transacción en ledger_txns exige SUM(amount) == 0.0 en ledger_entries.
5. Circuit Breaker Transaccional: Pérdidas consecutivas (>= 3) o Drawdown diario (>= 3%) en SQLite.
"""

from __future__ import annotations

import math
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
DEFAULT_DB_PATH = os.getenv("TRADING_LEDGER_DB_PATH", os.path.join(PROJECT_ROOT, "trading_ledger.sqlite3"))

SUPPORTED_CURRENCIES = ("USDT", "USD", "ARS")


def symbol_to_currency(symbol: str) -> str:
    """Determina la divisa contable asociada a un símbolo soportado."""
    sym = str(symbol or "").strip().upper()
    if sym.endswith(".BA"):
        return "ARS"
    if "/USDT" in sym or sym.endswith("USDT"):
        return "USDT"
    return "USD"


_GLOBAL_DB_LOCKS: Dict[str, threading.RLock] = {}
_GLOBAL_DB_LOCKS_GUARD = threading.Lock()


def _get_db_lock(db_path: str) -> threading.RLock:
    """Devuelve un RLock compartido por ruta absoluta de base de datos SQLite."""
    key = ":memory:" if db_path == ":memory:" else os.path.abspath(db_path)
    with _GLOBAL_DB_LOCKS_GUARD:
        lock = _GLOBAL_DB_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _GLOBAL_DB_LOCKS[key] = lock
        return lock


class LedgerStore:
    """
    Almacén transaccional en SQLite para Cuentas Ómnibus, Trades, Órdenes, Fills y Circuit Breaker.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        initial_vault: Optional[Dict[str, float]] = None,
    ):
        self.db_path = db_path or os.getenv("TRADING_LEDGER_DB_PATH") or DEFAULT_DB_PATH
        self._lock = threading.RLock() if self.db_path == ":memory:" else _get_db_lock(self.db_path)
        self._memory_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row
            self._memory_conn.execute("PRAGMA foreign_keys = ON;")

        default_vault = {"USDT": 500.0, "USD": 500.0, "ARS": 500_000.0}
        if initial_vault:
            for k, v in initial_vault.items():
                if k in SUPPORTED_CURRENCIES and math.isfinite(float(v)) and float(v) >= 0:
                    default_vault[k] = float(v)
        self._initial_vault = default_vault
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        return conn

    def _initialize_database(self) -> None:
        with self._lock:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            conn = self._connect()
            try:
                with conn:
                    conn.executescript(schema_sql)
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS operating_capital_config (
                            currency TEXT PRIMARY KEY CHECK (currency IN ('USDT', 'USD', 'ARS')),
                            amount REAL NOT NULL,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS safe_profit_wallet_config (
                            currency TEXT PRIMARY KEY CHECK (currency IN ('USDT', 'USD', 'ARS')),
                            amount REAL NOT NULL DEFAULT 0.0,
                            injected_total REAL NOT NULL DEFAULT 0.0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                    for col_name, col_type, default_val in [
                        ("strategy", "TEXT", "'trailing_trend_runner'"),
                        ("engine", "TEXT", "'antigravity_operador'"),
                        ("formula", "TEXT", "'Quant Risk ATR'"),
                        ("tp1_trimmed", "INTEGER", "0"),
                    ]:
                        try:
                            conn.execute(f"ALTER TABLE trades ADD COLUMN {col_name} {col_type} DEFAULT {default_val}")
                        except sqlite3.OperationalError:
                            pass
                    # Tablas aisladas para simulación de Micro-Futuros CME (MES=F / MNQ=F):
                    # NUNCA alteran ni descuentan las bóvedas reales Spot (USDT, USD, ARS).
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS futures_sim_account (
                            account_id TEXT PRIMARY KEY DEFAULT 'SIM_FUTURES',
                            initial_balance REAL NOT NULL DEFAULT 2500.0,
                            balance REAL NOT NULL DEFAULT 2500.0,
                            realized_pnl REAL NOT NULL DEFAULT 0.0,
                            total_fees REAL NOT NULL DEFAULT 0.0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS futures_trades (
                            id TEXT PRIMARY KEY,
                            symbol TEXT NOT NULL,
                            asset_class TEXT NOT NULL DEFAULT 'FUTURES_MICRO',
                            side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT')),
                            status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
                            contracts REAL NOT NULL,
                            initial_contracts REAL NOT NULL,
                            multiplier REAL NOT NULL,
                            tick_size REAL NOT NULL,
                            tick_value REAL NOT NULL,
                            entry_price REAL NOT NULL,
                            exit_price REAL,
                            realized_pnl REAL DEFAULT 0.0,
                            total_fees REAL DEFAULT 0.0,
                            initial_tp_pct REAL NOT NULL,
                            initial_sl_pct REAL NOT NULL,
                            current_stop_net_pct REAL NOT NULL,
                            be_armed INTEGER DEFAULT 0,
                            trail_active INTEGER DEFAULT 0,
                            peak_price REAL NOT NULL,
                            tp1_trimmed INTEGER DEFAULT 0,
                            trailing_mode TEXT DEFAULT 'auto',
                            ai_decision_reason TEXT,
                            counterfactual_diff REAL DEFAULT 0.0,
                            time_decay_hours REAL DEFAULT 0.0,
                            time_decay_status TEXT DEFAULT 'NORMAL',
                            time_decay_suggestion TEXT DEFAULT '',
                            strategy TEXT DEFAULT 'kula_balam_cava_ruiz',
                            engine TEXT DEFAULT 'antigravity_operador',
                            formula TEXT DEFAULT 'Kula Triad Futures',
                            exit_reason TEXT,
                            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            closed_at TIMESTAMP
                        );
                        """
                    )
                    conn.execute(
                        """
                        CREATE UNIQUE INDEX IF NOT EXISTS one_open_futures_trade_per_symbol
                        ON futures_trades (symbol)
                        WHERE status = 'OPEN';
                        """
                    )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO futures_sim_account (account_id, initial_balance, balance, realized_pnl, total_fees)
                        VALUES ('SIM_FUTURES', 2500.0, 2500.0, 0.0, 0.0);
                        """
                    )
                    # Migración aditiva del desglose de fricción (comisión / spread / swap) de micro-futuros
                    for tbl, col, ddl in [
                        ("futures_sim_account", "total_spread", "REAL NOT NULL DEFAULT 0.0"),
                        ("futures_sim_account", "total_swap", "REAL NOT NULL DEFAULT 0.0"),
                        ("futures_trades", "spread_ticks_per_side", "REAL NOT NULL DEFAULT 0.0"),
                        ("futures_trades", "swap_per_contract_night", "REAL NOT NULL DEFAULT 0.0"),
                        ("futures_trades", "opened_ts", "REAL"),
                        ("futures_trades", "last_swap_ts", "REAL"),
                        ("futures_trades", "swap_accrued_per_contract", "REAL NOT NULL DEFAULT 0.0"),
                        ("futures_trades", "entry_commission", "REAL NOT NULL DEFAULT 0.0"),
                        ("futures_trades", "exit_commission", "REAL NOT NULL DEFAULT 0.0"),
                        ("futures_trades", "spread_cost", "REAL NOT NULL DEFAULT 0.0"),
                        ("futures_trades", "swap_cost", "REAL NOT NULL DEFAULT 0.0"),
                        ("futures_trades", "be_price", "REAL"),
                    ]:
                        try:
                            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {ddl}")
                        except sqlite3.OperationalError:
                            pass
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS futures_cost_events (
                            id TEXT PRIMARY KEY,
                            trade_id TEXT NOT NULL,
                            symbol TEXT NOT NULL,
                            event_type TEXT NOT NULL CHECK (event_type IN (
                                'ENTRY_COMMISSION', 'EXIT_COMMISSION', 'ENTRY_SPREAD', 'EXIT_SPREAD', 'SWAP'
                            )),
                            amount REAL NOT NULL,
                            contracts REAL NOT NULL DEFAULT 0.0,
                            note TEXT DEFAULT '',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                    # Tabla #19: shadow_trades (Shadow Testing / Operaciones Espejo vetadas por Árbitro IA)
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS shadow_trades (
                            id TEXT PRIMARY KEY,
                            symbol TEXT NOT NULL,
                            side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT', 'BUY', 'SELL')),
                            status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
                            qty REAL NOT NULL,
                            entry_price REAL NOT NULL,
                            exit_price REAL,
                            sl_price REAL NOT NULL,
                            tp_price REAL NOT NULL,
                            initial_sl_pct REAL NOT NULL,
                            initial_tp_pct REAL NOT NULL,
                            virtual_pnl_usd REAL DEFAULT 0.0,
                            virtual_pnl_pct REAL DEFAULT 0.0,
                            outcome TEXT CHECK (outcome IN ('SAVED_SL', 'MISSED_TP', 'EXPIRED', 'PENDING', NULL)),
                            strategy TEXT NOT NULL,
                            arbiter_verdict TEXT DEFAULT 'AHORA_NO',
                            arbiter_reason TEXT,
                            headlines_json TEXT,
                            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            closed_at TIMESTAMP
                        );
                        """
                    )
                    self._seed_accounts_and_vault(conn)
            finally:
                if self._memory_conn is None:
                    conn.close()

    def _seed_accounts_and_vault(self, conn: sqlite3.Connection) -> None:
        """
        Crea las cuentas contables estándar para cada divisa y deposita el capital inicial
        exclusivamente en las cuentas VAULT (Billeteras Operativas siempre en $0.00).
        """
        today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for currency in SUPPORTED_CURRENCIES:
            accounts = [
                (f"EXTERNAL_TREASURY_{currency}", f"Tesorería Externa {currency}", "VAULT", currency),
                (f"VAULT_{currency}", f"Bóveda Central {currency}", "VAULT", currency),
                (f"OP_{currency}", f"Billetera Operativa {currency}", "OPERATIONAL", currency),
                (f"FEES_{currency}", f"Comisiones Pagadas {currency}", "EXPENSE_FEES", currency),
                (f"PNL_{currency}", f"Resultados Realizados {currency}", "PNL", currency),
            ]
            for acc_id, name, acc_type, curr in accounts:
                conn.execute(
                    "INSERT OR IGNORE INTO accounts (id, name, type, currency) VALUES (?, ?, ?, ?)",
                    (acc_id, name, acc_type, curr),
                )

            # Si la bóveda no tiene ningún asiento previo, realizar depósito fundacional en doble partida
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM ledger_entries WHERE account_id = ?",
                (f"VAULT_{currency}",),
            ).fetchone()
            initial_amount = self._initial_vault.get(currency, 0.0)
            if row["cnt"] == 0 and initial_amount > 0:
                self._record_double_entry_tx(
                    conn=conn,
                    description=f"Fondeo inicial de Bóveda ({currency})",
                    ref_type="DEPOSIT",
                    ref_id="INITIAL_SEED",
                    currency=currency,
                    entries=[
                        (f"EXTERNAL_TREASURY_{currency}", -initial_amount),
                        (f"VAULT_{currency}", +initial_amount),
                    ],
                )

            conn.execute(
                """
                INSERT OR IGNORE INTO risk_state (
                    book_currency, day_key, start_equity, realized_pnl, consecutive_losses, halted_until, halt_reason
                ) VALUES (?, ?, ?, 0.0, 0, NULL, NULL)
                """,
                (currency, today_key, max(initial_amount, 1.0)),
            )

    def _record_double_entry_tx(
        self,
        conn: sqlite3.Connection,
        description: str,
        ref_type: str,
        ref_id: Optional[str],
        currency: str,
        entries: List[tuple[str, float]],
    ) -> str:
        """
        Inserta una transacción contable de doble partida verificando que la suma algebraica sea 0.0.
        """
        if not entries or len(entries) < 2:
            raise ValueError("Una transacción de doble partida requiere al menos 2 asientos.")

        total_sum = sum(float(amount) for _, amount in entries)
        if abs(total_sum) > 1e-6:
            raise ValueError(
                f"Violación de invariante de doble partida ({ref_type}): suma={total_sum:.8f} != 0"
            )

        txn_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO ledger_txns (id, description, ref_type, ref_id) VALUES (?, ?, ?, ?)",
            (txn_id, description, ref_type, ref_id),
        )
        for account_id, amount in entries:
            if not math.isfinite(float(amount)):
                raise ValueError(f"Monto no finito para cuenta {account_id}")
            conn.execute(
                """
                INSERT INTO ledger_entries (id, txn_id, account_id, amount, currency)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), txn_id, account_id, round(float(amount), 8), currency),
            )
        return txn_id

    def _get_account_balance_conn(self, conn: sqlite3.Connection, account_id: str) -> float:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0.0) AS bal FROM ledger_entries WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        return round(float(row["bal"]), 8) if row else 0.0

    def get_account_balance(self, account_id: str) -> float:
        with self._lock:
            conn = self._connect()
            try:
                return self._get_account_balance_conn(conn, account_id)
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_omnibus_balances(self) -> Dict[str, Dict[str, float]]:
        """
        Retorna los saldos actuales de la Bóveda (VAULT), Billeteras Operativas (OPERATIONAL),
        Comisiones acumuladas (FEES) y PnL realizado (PNL) por cada divisa.
        """
        with self._lock:
            conn = self._connect()
            try:
                result: Dict[str, Dict[str, float]] = {
                    "vault": {},
                    "operational": {},
                    "total_equity": {},
                    "operating_capital": {},
                    "operating_available": {},
                    "safe_profit_wallet": {},
                    "safe_profit_injected": {},
                    "broker_idle": {},
                    "fees_paid": {},
                    "realized_pnl": {},
                    "realized_pnl_net": {},
                }
                for curr in SUPPORTED_CURRENCIES:
                    vault_bal = self._get_account_balance_conn(conn, f"VAULT_{curr}")
                    op_bal = self._get_account_balance_conn(conn, f"OP_{curr}")
                    total_eq = round(vault_bal + op_bal, 8)
                    result["vault"][curr] = vault_bal
                    result["operational"][curr] = op_bal
                    result["total_equity"][curr] = total_eq
                    result["fees_paid"][curr] = self._get_account_balance_conn(conn, f"FEES_{curr}")

                    # Leer Billetera de Ganancia Segura / Potenciación
                    row_sw = conn.execute(
                        "SELECT amount, injected_total FROM safe_profit_wallet_config WHERE currency = ?",
                        (curr,),
                    ).fetchone()
                    safe_wallet_amt = max(0.0, float(row_sw["amount"])) if row_sw is not None else 0.0
                    safe_injected_amt = max(0.0, float(row_sw["injected_total"])) if row_sw is not None else 0.0

                    # Leer capital asignado a operar (acotado al patrimonio total menos la billetera de ganancia segura)
                    row_op = conn.execute(
                        "SELECT amount FROM operating_capital_config WHERE currency = ?", (curr,)
                    ).fetchone()
                    clean_total_eq = total_eq if total_eq >= 0.01 else 0.0
                    max_op_allowed = max(0.0, clean_total_eq - safe_wallet_amt)
                    if clean_total_eq <= 0.0:
                        op_amt = 0.0
                    elif row_op is not None:
                        op_amt = min(float(row_op["amount"]), max_op_allowed)
                    else:
                        default_op = 500.0 if curr != "ARS" else 500_000.0
                        op_amt = min(default_op, max_op_allowed)
                    result["operating_capital"][curr] = round(op_amt, 4)
                    result["operating_available"][curr] = round(max(0.0, op_amt - op_bal), 4)
                    result["safe_profit_wallet"][curr] = round(safe_wallet_amt if clean_total_eq > 0 else 0.0, 4)
                    result["safe_profit_injected"][curr] = round(safe_injected_amt, 4)
                    result["broker_idle"][curr] = round(max(0.0, clean_total_eq - op_amt - safe_wallet_amt), 4)

                    # En contabilidad, la cuenta PNL se debita cuando el usuario gana (+ en VAULT, - en PNL)
                    # Invertimos el signo para presentar el PnL neto ganado/perdido de forma intuitiva
                    pnl_acct = self._get_account_balance_conn(conn, f"PNL_{curr}")
                    result["realized_pnl"][curr] = round(-pnl_acct, 8)
                    # `realized_pnl` de la cuenta PNL es BRUTO (las comisiones van a FEES_*): el neto real las descuenta.
                    result["realized_pnl_net"][curr] = round(-pnl_acct - result["fees_paid"][curr], 8)
                return result
            finally:
                if self._memory_conn is None:
                    conn.close()

    def deposit(self, amount: float, currency: str = "USDT") -> float:
        """Deposita fondos en la Bóveda de la divisa especificada."""
        curr = symbol_to_currency(currency)
        if curr not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Divisa no soportada: {curr}")
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("El monto a depositar debe ser finito y mayor que 0.")

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    self._record_double_entry_tx(
                        conn=conn,
                        description=f"Depósito manual en Bóveda ({curr})",
                        ref_type="DEPOSIT",
                        ref_id=str(uuid.uuid4())[:8],
                        currency=curr,
                        entries=[
                            (f"EXTERNAL_TREASURY_{curr}", -float(amount)),
                            (f"VAULT_{curr}", +float(amount)),
                        ],
                    )
                    return self._get_account_balance_conn(conn, f"VAULT_{curr}")
            finally:
                if self._memory_conn is None:
                    conn.close()

    def withdraw(self, amount: float, currency: str = "USDT") -> float:
        """Retira fondos de la Bóveda hacia la Tesorería Externa."""
        curr = symbol_to_currency(currency)
        if curr not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Divisa no soportada: {curr}")
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("El monto a retirar debe ser finito y mayor que 0.")

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    current_vault = self._get_account_balance_conn(conn, f"VAULT_{curr}")
                    if amount > current_vault:
                        raise ValueError(f"Saldo insuficiente en Bóveda ({curr}): disponible {current_vault:.2f}, solicitado {amount:.2f}")

                    self._record_double_entry_tx(
                        conn=conn,
                        description=f"Retiro manual de Bóveda ({curr})",
                        ref_type="WITHDRAW",
                        ref_id=str(uuid.uuid4())[:8],
                        currency=curr,
                        entries=[
                            (f"VAULT_{curr}", -float(amount)),
                            (f"EXTERNAL_TREASURY_{curr}", +float(amount)),
                        ],
                    )

                    # Ajustar operating_capital_config y safe_profit_wallet_config para no exceder el nuevo patrimonio
                    new_vault = self._get_account_balance_conn(conn, f"VAULT_{curr}")
                    op_bal = self._get_account_balance_conn(conn, f"OP_{curr}")
                    new_total_eq = max(0.0, round(new_vault + op_bal, 8))
                    if new_total_eq < 0.01:
                        new_total_eq = 0.0

                    row_op = conn.execute("SELECT amount FROM operating_capital_config WHERE currency = ?", (curr,)).fetchone()
                    if row_op is not None and float(row_op["amount"]) > new_total_eq:
                        conn.execute("UPDATE operating_capital_config SET amount = ?, updated_at = CURRENT_TIMESTAMP WHERE currency = ?", (new_total_eq, curr))

                    row_sw = conn.execute("SELECT amount FROM safe_profit_wallet_config WHERE currency = ?", (curr,)).fetchone()
                    if row_sw is not None and float(row_sw["amount"]) > new_total_eq:
                        conn.execute("UPDATE safe_profit_wallet_config SET amount = ?, updated_at = CURRENT_TIMESTAMP WHERE currency = ?", (new_total_eq, curr))

                    return new_vault
            finally:
                if self._memory_conn is None:
                    conn.close()

    def reset_account(self, initial_amount: float = 500.0) -> Dict[str, float]:
        """Limpia transacciones, reinicia las Bóvedas al monto inicial y resetea el Circuit Breaker."""
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute("DELETE FROM fills")
                    conn.execute("DELETE FROM orders")
                    conn.execute("DELETE FROM trades")
                    conn.execute("DELETE FROM ledger_entries")
                    conn.execute("DELETE FROM ledger_txns")
                    conn.execute("DELETE FROM risk_events")
                    conn.execute("DELETE FROM risk_state")
                    conn.execute("DELETE FROM operating_capital_config")
                    conn.execute("DELETE FROM safe_profit_wallet_config")
                    try:
                        conn.execute("DELETE FROM shadow_trades")
                    except sqlite3.OperationalError:
                        pass
                    try:
                        conn.execute("DELETE FROM signals")
                    except sqlite3.OperationalError:
                        pass

                    today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    for curr in SUPPORTED_CURRENCIES:
                        init_amt = initial_amount if curr != "ARS" else initial_amount * 1000.0
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"Reinicio de Bóveda ({curr})",
                            ref_type="DEPOSIT",
                            ref_id="RESET_SEED",
                            currency=curr,
                            entries=[
                                (f"EXTERNAL_TREASURY_{curr}", -init_amt),
                                (f"VAULT_{curr}", +init_amt),
                            ],
                        )
                        conn.execute(
                            """
                            INSERT INTO risk_state (
                                book_currency, day_key, start_equity, realized_pnl, consecutive_losses, halted_until, halt_reason
                            ) VALUES (?, ?, ?, 0.0, 0, NULL, NULL)
                            """,
                            (curr, today_key, max(init_amt, 1.0)),
                        )
                        conn.execute(
                            """
                            INSERT INTO operating_capital_config (currency, amount, updated_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(currency) DO UPDATE SET amount = excluded.amount, updated_at = CURRENT_TIMESTAMP
                            """,
                            (curr, init_amt),
                        )
                    return {
                        curr: self._get_account_balance_conn(conn, f"VAULT_{curr}")
                        for curr in SUPPORTED_CURRENCIES
                    }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_operating_capital(self, currency: str = "USDT") -> float:
        """Retorna el capital asignado para operar en la divisa especificada, acotado al patrimonio total en el broker."""
        curr = symbol_to_currency(currency)
        with self._lock:
            conn = self._connect()
            try:
                vault_bal = self._get_account_balance_conn(conn, f"VAULT_{curr}")
                op_bal = self._get_account_balance_conn(conn, f"OP_{curr}")
                total_eq = round(vault_bal + op_bal, 8)
                if total_eq < 0.01:
                    return 0.0
                row = conn.execute(
                    "SELECT amount FROM operating_capital_config WHERE currency = ?", (curr,)
                ).fetchone()
                if row is not None:
                    stored = float(row["amount"])
                    return round(min(stored, total_eq), 4)
                default_val = 500.0 if curr != "ARS" else 500_000.0
                return round(min(default_val, total_eq), 4)
            finally:
                if self._memory_conn is None:
                    conn.close()

    def set_operating_capital(self, currency: str, amount: float) -> float:
        """Asigna explícitamente el monto de capital para operar verificando no exceder el patrimonio total en el broker."""
        curr = symbol_to_currency(currency)
        amt = max(0.0, float(amount))
        with self._lock:
            conn = self._connect()
            try:
                vault_bal = self._get_account_balance_conn(conn, f"VAULT_{curr}")
                op_bal = self._get_account_balance_conn(conn, f"OP_{curr}")
                total_eq = round(vault_bal + op_bal, 8)
                if amt > (total_eq + 1e-4):
                    raise ValueError(
                        f"El capital para operar (${amt:,.2f} {curr}) no puede superar el patrimonio total en el broker (${total_eq:,.2f} {curr})."
                    )
                with conn:
                    conn.execute(
                        """
                        INSERT INTO operating_capital_config (currency, amount, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(currency) DO UPDATE SET amount = excluded.amount, updated_at = CURRENT_TIMESTAMP
                        """,
                        (curr, amt),
                    )
                return amt
            finally:
                if self._memory_conn is None:
                    conn.close()

    def transfer_to_operating(self, currency: str, amount: float) -> float:
        """Transfiere un importe desde el saldo libre del broker hacia la cuenta para operar."""
        curr = symbol_to_currency(currency)
        curr_op = self.get_operating_capital(curr)
        new_target = curr_op + float(amount)
        return self.set_operating_capital(curr, new_target)

    def return_to_broker(self, currency: str, amount: float) -> float:
        """Devuelve un importe desde la cuenta para operar de vuelta a la reserva pasiva del broker."""
        curr = symbol_to_currency(currency)
        curr_op = self.get_operating_capital(curr)
        new_target = max(0.0, curr_op - float(amount))
        return self.set_operating_capital(curr, new_target)

    def get_safe_profit_wallet(self, currency: str = "USDT") -> Dict[str, float]:
        """Retorna el saldo disponible y el acumulado inyectado de la Billetera de Ganancia Segura."""
        curr = symbol_to_currency(currency)
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT amount, injected_total FROM safe_profit_wallet_config WHERE currency = ?",
                    (curr,),
                ).fetchone()
                if row is None:
                    return {"available": 0.0, "injected_total": 0.0}
                return {
                    "available": round(max(0.0, float(row["amount"])), 4),
                    "injected_total": round(max(0.0, float(row["injected_total"])), 4),
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def transfer_safe_profit_wallet(
        self,
        currency: str,
        amount: float,
        direction: str = "FROM_OPERATING",
    ) -> Dict[str, float]:
        """
        Transfiere fondos entre 'Dinero para Operar' y la 'Billetera de Uso por Ganancia Segura':
        - direction='FROM_OPERATING': descuenta del saldo libre de Dinero para Operar y lo guarda en la Billetera de Ganancia Segura.
        - direction='TO_OPERATING': devuelve saldo de la Billetera de Ganancia Segura hacia Dinero para Operar.
        """
        curr = symbol_to_currency(currency)
        amt = round(float(amount), 4)
        if not math.isfinite(amt) or amt <= 0:
            raise ValueError("El monto a transferir debe ser mayor que 0.")

        dir_norm = str(direction or "FROM_OPERATING").strip().upper()
        if dir_norm not in ("FROM_OPERATING", "TO_OPERATING"):
            raise ValueError("Dirección inválida. Usa FROM_OPERATING o TO_OPERATING.")

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    vault_bal = self._get_account_balance_conn(conn, f"VAULT_{curr}")
                    op_bal = self._get_account_balance_conn(conn, f"OP_{curr}")
                    total_eq = round(vault_bal + op_bal, 8)

                    row_sw = conn.execute(
                        "SELECT amount, injected_total FROM safe_profit_wallet_config WHERE currency = ?",
                        (curr,),
                    ).fetchone()
                    sw_avail = max(0.0, float(row_sw["amount"])) if row_sw is not None else 0.0
                    sw_inj = max(0.0, float(row_sw["injected_total"])) if row_sw is not None else 0.0

                    row_op = conn.execute(
                        "SELECT amount FROM operating_capital_config WHERE currency = ?",
                        (curr,),
                    ).fetchone()
                    default_op = 500000.0 if curr == "ARS" else 500.0
                    max_op_allowed = max(0.0, total_eq - sw_avail)
                    cur_op = min(float(row_op["amount"]), max_op_allowed) if row_op is not None else min(default_op, max_op_allowed)
                    op_free = max(0.0, round(cur_op - op_bal, 4))

                    if dir_norm == "FROM_OPERATING":
                        if amt > op_free + 0.05:
                            raise ValueError(
                                f"Saldo libre insuficiente en Dinero para Operar: tienes ${op_free:.2f} {curr} libres "
                                f"(${op_bal:.2f} {curr} están usados en posiciones abiertas) y solicitaste separar ${amt:.2f} {curr}."
                            )
                        new_op = max(op_bal, round(cur_op - amt, 4))
                        new_sw = round(sw_avail + amt, 4)
                    else:
                        if amt > sw_avail + 0.05:
                            raise ValueError(
                                f"Saldo insuficiente en Billetera de Ganancia Segura: disponible ${sw_avail:.2f} {curr}, "
                                f"solicitado ${amt:.2f} {curr}."
                            )
                        new_sw = max(0.0, round(sw_avail - amt, 4))
                        new_op = min(total_eq - new_sw, round(cur_op + amt, 4))

                    conn.execute(
                        """
                        INSERT INTO operating_capital_config (currency, amount, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(currency) DO UPDATE SET amount = excluded.amount, updated_at = CURRENT_TIMESTAMP
                        """,
                        (curr, new_op),
                    )
                    conn.execute(
                        """
                        INSERT INTO safe_profit_wallet_config (currency, amount, injected_total, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(currency) DO UPDATE SET
                            amount = excluded.amount,
                            injected_total = excluded.injected_total,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (curr, new_sw, sw_inj),
                    )
                    return {
                        "currency": curr,
                        "operating_capital": round(new_op, 4),
                        "operating_available": round(max(0.0, new_op - op_bal), 4),
                        "safe_profit_wallet": round(new_sw, 4),
                        "safe_profit_injected": round(sw_inj, 4),
                    }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def allocate_jit(self, currency: str, amount: float, ref_id: Optional[str] = None) -> str:
        """
        Just-In-Time Funding: transfiere exactamente `amount` desde VAULT_{currency}
        hacia OP_{currency} verificando disponibilidad de fondos.
        """
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Divisa no soportada: {currency}")
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("El monto de fondeo JIT debe ser finito y positivo.")

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    vault_bal = self._get_account_balance_conn(conn, f"VAULT_{currency}")
                    if vault_bal + 1e-8 < amount:
                        raise ValueError(
                            f"Fondos insuficientes en Bóveda ({currency}): disponible={vault_bal:.4f}, requerido={amount:.4f}"
                        )
                    return self._record_double_entry_tx(
                        conn=conn,
                        description=f"Fondeo Just-In-Time desde Bóveda ({currency})",
                        ref_type="ALLOCATE",
                        ref_id=ref_id,
                        currency=currency,
                        entries=[
                            (f"VAULT_{currency}", -round(amount, 8)),
                            (f"OP_{currency}", +round(amount, 8)),
                        ],
                    )
            finally:
                if self._memory_conn is None:
                    conn.close()

    def sweep_back(
        self,
        currency: str,
        gross_pnl: float = 0.0,
        total_fees: float = 0.0,
        ref_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sweep-Back Automático:
        1. Asienta el PnL bruto y las comisiones en la billetera operativa (`OP_{currency}`).
        2. Transfiere inmediatamente la totalidad del saldo resultante de `OP_{currency}`
           de regreso a `VAULT_{currency}`, dejando la billetera operativa en exactamente $0.00.
        """
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Divisa no soportada: {currency}")
        if not (math.isfinite(gross_pnl) and math.isfinite(total_fees)) or total_fees < 0:
            raise ValueError("Parámetros de PnL o comisión inválidos en Sweep-Back.")

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    # 1. Registrar PnL bruto realizado si es distinto de cero
                    if abs(gross_pnl) > 1e-8:
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"Resultado bruto de operación ({currency})",
                            ref_type="PNL_REALIZED",
                            ref_id=ref_id,
                            currency=currency,
                            entries=[
                                (f"PNL_{currency}", -round(gross_pnl, 8)),
                                (f"OP_{currency}", +round(gross_pnl, 8)),
                            ],
                        )

                    # 2. Registrar comisiones pagadas si son mayores a cero
                    if total_fees > 1e-8:
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"Comisiones round-trip de broker ({currency})",
                            ref_type="TRADE_FEE",
                            ref_id=ref_id,
                            currency=currency,
                            entries=[
                                (f"OP_{currency}", -round(total_fees, 8)),
                                (f"FEES_{currency}", +round(total_fees, 8)),
                            ],
                        )

                    # 3. Barrer todo el saldo remanente de la billetera operativa a la Bóveda
                    op_balance = self._get_account_balance_conn(conn, f"OP_{currency}")
                    sweep_tx_id = None
                    swept_amount = 0.0
                    if op_balance > 1e-8:
                        swept_amount = op_balance
                        sweep_tx_id = self._record_double_entry_tx(
                            conn=conn,
                            description=f"Sweep-Back automático a Bóveda ({currency})",
                            ref_type="SWEEP_BACK",
                            ref_id=ref_id,
                            currency=currency,
                            entries=[
                                (f"OP_{currency}", -round(op_balance, 8)),
                                (f"VAULT_{currency}", +round(op_balance, 8)),
                            ],
                        )
                    elif op_balance < -1e-8:
                        # Si la pérdida superó el capital asignado, absorber desde la Bóveda para restaurar OP a 0.0
                        deficit = abs(op_balance)
                        sweep_tx_id = self._record_double_entry_tx(
                            conn=conn,
                            description=f"Cobertura de déficit operativo desde Bóveda ({currency})",
                            ref_type="SWEEP_BACK",
                            ref_id=ref_id,
                            currency=currency,
                            entries=[
                                (f"VAULT_{currency}", -round(deficit, 8)),
                                (f"OP_{currency}", +round(deficit, 8)),
                            ],
                        )

                    final_op = self._get_account_balance_conn(conn, f"OP_{currency}")
                    final_vault = self._get_account_balance_conn(conn, f"VAULT_{currency}")
                    return {
                        "sweep_tx_id": sweep_tx_id,
                        "swept_amount": round(swept_amount, 8),
                        "operational_balance": final_op,
                        "vault_balance": final_vault,
                    }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def check_circuit_breaker(self, currency: str, now_ts: Optional[int] = None) -> Dict[str, Any]:
        """Verifica si el libro de una divisa se encuentra detenido por el Circuit Breaker."""
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Divisa no soportada: {currency}")
        now_val = int(now_ts if now_ts is not None else time.time())
        today_key = datetime.fromtimestamp(now_val, tz=timezone.utc).strftime("%Y-%m-%d")

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    row = conn.execute(
                        "SELECT * FROM risk_state WHERE book_currency = ?", (currency,)
                    ).fetchone()
                    if not row:
                        return {"halted": False, "reason": None, "consecutive_losses": 0, "realized_pnl": 0.0}

                    halted_until = row["halted_until"]
                    if halted_until and now_val < int(halted_until):
                        return {
                            "halted": True,
                            "halted_until": int(halted_until),
                            "reason": row["halt_reason"],
                            "consecutive_losses": int(row["consecutive_losses"]),
                            "realized_pnl": float(row["realized_pnl"]),
                        }

                    # Si expiró el halt o cambió el día UTC, reiniciar contadores diarios
                    if (halted_until and now_val >= int(halted_until)) or row["day_key"] != today_key:
                        vault_now = self._get_account_balance_conn(conn, f"VAULT_{currency}")
                        op_now = self._get_account_balance_conn(conn, f"OP_{currency}")
                        equity_now = max(vault_now + op_now, 1.0)
                        conn.execute(
                            """
                            UPDATE risk_state
                            SET day_key = ?, start_equity = ?, realized_pnl = 0.0,
                                consecutive_losses = 0, halted_until = NULL, halt_reason = NULL,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE book_currency = ?
                            """,
                            (today_key, equity_now, currency),
                        )
                        return {"halted": False, "reason": None, "consecutive_losses": 0, "realized_pnl": 0.0}

                    return {
                        "halted": False,
                        "halted_until": None,
                        "reason": None,
                        "consecutive_losses": int(row["consecutive_losses"]),
                        "realized_pnl": float(row["realized_pnl"]),
                    }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def _update_risk_on_close(
        self,
        conn: sqlite3.Connection,
        currency: str,
        net_pnl: float,
        now_ts: Optional[int] = None,
        overall_trade_pnl: Optional[float] = None,
    ) -> Dict[str, Any]:
        now_val = int(now_ts if now_ts is not None else time.time())
        row = conn.execute(
            "SELECT * FROM risk_state WHERE book_currency = ?", (currency,)
        ).fetchone()
        if not row:
            return {"halted": False}

        effective_outcome = overall_trade_pnl if overall_trade_pnl is not None else net_pnl
        consecutive_losses = int(row["consecutive_losses"]) + 1 if effective_outcome < 0 else 0
        realized_pnl = round(float(row["realized_pnl"]) + float(net_pnl), 8)
        start_equity = max(float(row["start_equity"]), 1.0)
        drawdown_pct = abs(min(0.0, realized_pnl)) / start_equity * 100.0 if realized_pnl < 0 else 0.0

        halted_until = None
        halt_reason = None
        if consecutive_losses >= 3:
            halted_until = now_val + 86_400
            halt_reason = f"3 pérdidas consecutivas alcanzadas ({consecutive_losses})."
        elif drawdown_pct >= 3.0:
            halted_until = now_val + 86_400
            halt_reason = f"Drawdown diario máximo alcanzado ({drawdown_pct:.2f}% >= 3.00%)."

        conn.execute(
            """
            UPDATE risk_state
            SET realized_pnl = ?, consecutive_losses = ?, halted_until = ?, halt_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE book_currency = ?
            """,
            (realized_pnl, consecutive_losses, halted_until, halt_reason, currency),
        )

        if halted_until:
            conn.execute(
                """
                INSERT INTO risk_events (id, book_currency, event_type, reason, details)
                VALUES (?, ?, 'CIRCUIT_BREAKER_TRIGGERED', ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    currency,
                    halt_reason,
                    f"net_pnl={net_pnl:.4f}, realized_pnl={realized_pnl:.4f}, drawdown_pct={drawdown_pct:.2f}%",
                ),
            )

        return {
            "halted": halted_until is not None,
            "halted_until": halted_until,
            "reason": halt_reason,
            "consecutive_losses": consecutive_losses,
            "realized_pnl": realized_pnl,
            "drawdown_pct": round(drawdown_pct, 4),
        }

    def reset_circuit_breaker(self, currency: Optional[str] = None) -> None:
        """Permite al operador reiniciar manualmente el Circuit Breaker."""
        targets = [currency] if currency in SUPPORTED_CURRENCIES else list(SUPPORTED_CURRENCIES)
        today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    for curr in targets:
                        conn.execute(
                            """
                            UPDATE risk_state
                            SET day_key = ?, realized_pnl = 0.0, consecutive_losses = 0,
                                halted_until = NULL, halt_reason = NULL, updated_at = CURRENT_TIMESTAMP
                            WHERE book_currency = ?
                            """,
                            (today_key, curr),
                        )
                        conn.execute(
                            """
                            INSERT INTO risk_events (id, book_currency, event_type, reason, details)
                            VALUES (?, ?, 'RESET', 'Reinicio manual por el operador', NULL)
                            """,
                            (str(uuid.uuid4()), curr),
                        )
            finally:
                if self._memory_conn is None:
                    conn.close()

    def open_trade_with_jit(
        self,
        symbol: str,
        qty: float,
        entry_price: float,
        fee_amount: float = 0.0,
        initial_tp_pct: float = 0.8,
        initial_sl_pct: float = 0.5,
        side: str = "LONG",
        now_ts: Optional[int] = None,
        strategy: str = "trailing_trend_runner",
        engine: str = "antigravity_operador",
        formula: str = "Quant Risk ATR",
    ) -> Dict[str, Any]:
        """
        Ejecuta atómicamente:
        1. Verificación del Circuit Breaker.
        2. Fondeo Just-In-Time (VAULT -> OP) por el costo base + comisión de entrada.
        3. Inserción del trade en estado OPEN (protegido por índice único `one_open_trade_per_symbol`).
        4. Registro de la orden ENTRY y su fill inicial.
        """
        if qty <= 0 or entry_price <= 0 or fee_amount < 0:
            raise ValueError("Parámetros de entrada inválidos para abrir trade.")

        currency = symbol_to_currency(symbol)
        cost_basis = round(qty * entry_price, 8)
        required_jit = round(cost_basis + fee_amount, 8)
        trade_id = str(uuid.uuid4())
        order_id = str(uuid.uuid4())
        fill_id = str(uuid.uuid4())
        order_side_str = "SELL" if str(side or "LONG").upper() in ("SHORT", "SELL") else "BUY"

        with self._lock:
            cb_status = self.check_circuit_breaker(currency, now_ts=now_ts)
            if cb_status["halted"]:
                raise RuntimeError(f"Circuit Breaker activo en {currency}: {cb_status['reason']}")

            conn = self._connect()
            try:
                with conn:
                    vault_bal = self._get_account_balance_conn(conn, f"VAULT_{currency}")
                    if vault_bal + 1e-8 < required_jit:
                        raise ValueError(
                            f"Saldo insuficiente en Bóveda {currency} para JIT: disponible={vault_bal:.4f}, requerido={required_jit:.4f}"
                        )

                    # 1. Fondeo Just-In-Time (VAULT -> OP)
                    self._record_double_entry_tx(
                        conn=conn,
                        description=f"JIT Allocation para apertura ({side}) de {symbol}",
                        ref_type="ALLOCATE",
                        ref_id=trade_id,
                        currency=currency,
                        entries=[
                            (f"VAULT_{currency}", -required_jit),
                            (f"OP_{currency}", +required_jit),
                        ],
                    )

                    # 2. Si hay comisión de entrada, devengarla de OP a FEES
                    if fee_amount > 1e-8:
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"Comisión de entrada en {symbol}",
                            ref_type="TRADE_FEE",
                            ref_id=trade_id,
                            currency=currency,
                            entries=[
                                (f"OP_{currency}", -round(fee_amount, 8)),
                                (f"FEES_{currency}", +round(fee_amount, 8)),
                            ],
                        )

                    # 3. Crear registro en tabla `trades`
                    conn.execute(
                        """
                        INSERT INTO trades (
                            id, symbol, currency, side, status, qty, entry_price,
                            cost_basis, total_fees, initial_tp_pct, initial_sl_pct,
                            current_stop_net_pct, peak_price, strategy, engine, formula
                        ) VALUES (?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            trade_id,
                            symbol,
                            currency,
                            side,
                            qty,
                            entry_price,
                            cost_basis,
                            round(fee_amount, 8),
                            initial_tp_pct,
                            initial_sl_pct,
                            -abs(initial_sl_pct),
                            entry_price,
                            strategy,
                            engine,
                            formula,
                        ),
                    )

                    # 4. Registrar orden y fill de entrada
                    conn.execute(
                        """
                        INSERT INTO orders (
                            id, trade_id, client_order_id, symbol, side, type, role, qty, price, status
                        ) VALUES (?, ?, ?, ?, ?, 'MARKET', 'ENTRY', ?, ?, 'FILLED')
                        """,
                        (order_id, trade_id, f"entry-{trade_id[:12]}", symbol, order_side_str, qty, entry_price),
                    )
                    conn.execute(
                        """
                        INSERT INTO fills (id, order_id, symbol, qty, price, fee_amount, fee_currency)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (fill_id, order_id, symbol, qty, entry_price, round(fee_amount, 8), currency),
                    )

                    return {
                        "trade_id": trade_id,
                        "order_id": order_id,
                        "symbol": symbol,
                        "currency": currency,
                        "qty": qty,
                        "entry_price": entry_price,
                        "cost_basis": cost_basis,
                        "allocated_jit": required_jit,
                        "status": "OPEN",
                    }
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"Ya existe una posición abierta para {symbol} (invariante one_open_trade_per_symbol)."
                ) from exc
            finally:
                if self._memory_conn is None:
                    conn.close()

    def close_trade_with_sweep(
        self,
        symbol: str,
        exit_price: float,
        exit_fee_amount: float = 0.0,
        exit_reason: str = "TAKE_PROFIT_OR_MANUAL",
        now_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Cierra la posición activa en `symbol`, contabiliza el PnL y comisiones en doble partida,
        ejecuta el Sweep-Back automático a la Bóveda (dejando OP en $0.00) y actualiza el Circuit Breaker.
        """
        if exit_price <= 0 or exit_fee_amount < 0:
            raise ValueError("Precio o comisión de salida inválidos.")

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    trade = conn.execute(
                        "SELECT * FROM trades WHERE symbol = ? AND status = 'OPEN'",
                        (symbol,),
                    ).fetchone()
                    if not trade:
                        raise ValueError(f"No existe posición abierta para {symbol}.")

                    trade_id = trade["id"]
                    currency = trade["currency"]
                    qty = float(trade["qty"])
                    entry_price = float(trade["entry_price"])
                    prior_realized_pnl = float(trade["realized_pnl"] or 0.0)
                    prior_total_fees = float(trade["total_fees"] or 0.0)

                    entry_fill = conn.execute(
                        """
                        SELECT COALESCE(SUM(f.qty), 0.0) AS initial_qty, COALESCE(SUM(f.fee_amount), 0.0) AS entry_fee
                        FROM orders o
                        LEFT JOIN fills f ON f.order_id = o.id
                        WHERE o.trade_id = ? AND o.role = 'ENTRY'
                        """,
                        (trade_id,),
                    ).fetchone()
                    init_qty = float(entry_fill["initial_qty"]) if entry_fill and entry_fill["initial_qty"] else qty
                    init_entry_fee = (
                        float(entry_fill["entry_fee"])
                        if entry_fill and entry_fill["entry_fee"] is not None
                        else prior_total_fees
                    )
                    remaining_entry_fee = round(init_entry_fee * (qty / init_qty), 8) if init_qty > 0 else prior_total_fees

                    is_short = str(trade["side"] if "side" in trade.keys() else "").upper() == "SHORT"
                    gross_pnl = round(
                        (entry_price - exit_price) * qty if is_short else (exit_price - entry_price) * qty,
                        8,
                    )
                    total_fees = round(prior_total_fees + exit_fee_amount, 8)
                    leg_net_pnl = round(gross_pnl - exit_fee_amount - remaining_entry_fee, 8)
                    cumulative_net_pnl = round(prior_realized_pnl + leg_net_pnl, 8)

                    # 1. Registrar PnL bruto realizado en OP
                    if abs(gross_pnl) > 1e-8:
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"PnL bruto al cerrar {symbol}",
                            ref_type="PNL_REALIZED",
                            ref_id=trade_id,
                            currency=currency,
                            entries=[
                                (f"PNL_{currency}", -gross_pnl),
                                (f"OP_{currency}", +gross_pnl),
                            ],
                        )

                    # 2. Registrar comisión de salida si corresponde
                    if exit_fee_amount > 1e-8:
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"Comisión de salida en {symbol}",
                            ref_type="TRADE_FEE",
                            ref_id=trade_id,
                            currency=currency,
                            entries=[
                                (f"OP_{currency}", -round(exit_fee_amount, 8)),
                                (f"FEES_{currency}", +round(exit_fee_amount, 8)),
                            ],
                        )

                    # 3. Sweep-Back del saldo operativo liberado por este trade de vuelta a la Bóveda,
                    # preservando intacto en OP_{currency} el cost_basis de las demás posiciones abiertas (Multi-Slot).
                    other_open_row = conn.execute(
                        "SELECT COALESCE(SUM(cost_basis), 0.0) AS locked_cost FROM trades WHERE currency = ? AND status = 'OPEN' AND id != ?",
                        (currency, trade_id),
                    ).fetchone()
                    locked_by_others = round(float(other_open_row["locked_cost"] or 0.0), 8) if other_open_row else 0.0
                    op_balance = self._get_account_balance_conn(conn, f"OP_{currency}")
                    available_to_sweep = round(op_balance - locked_by_others, 8)
                    swept_amount = 0.0
                    if available_to_sweep > 1e-8:
                        swept_amount = available_to_sweep
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"Sweep-Back a Bóveda tras cerrar {symbol}",
                            ref_type="SWEEP_BACK",
                            ref_id=trade_id,
                            currency=currency,
                            entries=[
                                (f"OP_{currency}", -round(available_to_sweep, 8)),
                                (f"VAULT_{currency}", +round(available_to_sweep, 8)),
                            ],
                        )
                    elif available_to_sweep < -1e-8:
                        deficit = abs(available_to_sweep)
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"Cobertura de déficit operativo tras cerrar {symbol}",
                            ref_type="SWEEP_BACK",
                            ref_id=trade_id,
                            currency=currency,
                            entries=[
                                (f"VAULT_{currency}", -round(deficit, 8)),
                                (f"OP_{currency}", +round(deficit, 8)),
                            ],
                        )

                    # 4. Cancelar órdenes de protección abiertas vinculadas al trade
                    conn.execute(
                        """
                        UPDATE orders
                        SET status = 'CANCELLED', updated_at = CURRENT_TIMESTAMP
                        WHERE trade_id = ? AND status IN ('NEW', 'PARTIALLY_FILLED')
                        """,
                        (trade_id,),
                    )

                    # 5. Actualizar estado del trade a CLOSED preservando el PnL acumulado total
                    conn.execute(
                        """
                        UPDATE trades
                        SET status = 'CLOSED', exit_price = ?, realized_pnl = ?,
                            total_fees = ?, exit_reason = ?, closed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (exit_price, cumulative_net_pnl, total_fees, exit_reason, trade_id),
                    )

                    # 6. Actualizar Circuit Breaker (usa leg_net_pnl para PnL diario y cumulative_net_pnl para racha)
                    risk_update = self._update_risk_on_close(
                        conn=conn,
                        currency=currency,
                        net_pnl=leg_net_pnl,
                        now_ts=now_ts,
                        overall_trade_pnl=cumulative_net_pnl,
                    )

                    return {
                        "trade_id": trade_id,
                        "symbol": symbol,
                        "currency": currency,
                        "exit_price": exit_price,
                        "gross_pnl": gross_pnl,
                        "total_fees": total_fees,
                        "net_pnl": cumulative_net_pnl,
                        "leg_net_pnl": leg_net_pnl,
                        "swept_to_vault": round(swept_amount, 8),
                        "operational_balance": self._get_account_balance_conn(conn, f"OP_{currency}"),
                        "vault_balance": self._get_account_balance_conn(conn, f"VAULT_{currency}"),
                        "risk_state": risk_update,
                    }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def trim_trade_with_sweep(
        self,
        symbol: str,
        trim_qty: float,
        exit_price: float,
        exit_fee_amount: float = 0.0,
        exit_reason: str = "PARTIAL_TRIM_TP1",
        now_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Cierra parcialmente la posición activa en `symbol` (Trimming / Peluqueo):
        - Liquida `trim_qty` de la posición abierta.
        - Registra PnL proporcional y comisión de salida en doble partida.
        - Hace Sweep-Back a Bóveda del capital liberado + PnL neto en efectivo.
        - Reduce `qty` y `cost_basis` en `trades` y mueve Stop Loss a Breakeven Real (+0.25% neto).
        """
        if trim_qty <= 0 or exit_price <= 0 or exit_fee_amount < 0:
            raise ValueError("Parámetros de cierre parcial inválidos.")

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    trade = conn.execute(
                        "SELECT * FROM trades WHERE symbol = ? AND status = 'OPEN'",
                        (symbol,),
                    ).fetchone()
                    if not trade:
                        raise ValueError(f"No existe posición abierta para {symbol}.")

                    trade_id = trade["id"]
                    currency = trade["currency"]
                    total_qty = float(trade["qty"])
                    entry_price = float(trade["entry_price"])
                    cost_basis = float(trade["cost_basis"])
                    prior_total_fees = float(trade["total_fees"] or 0.0)

                    if trim_qty >= total_qty:
                        raise ValueError(f"trim_qty ({trim_qty}) debe ser menor que la posición total ({total_qty}).")

                    entry_fill = conn.execute(
                        """
                        SELECT COALESCE(SUM(f.qty), 0.0) AS initial_qty, COALESCE(SUM(f.fee_amount), 0.0) AS entry_fee
                        FROM orders o
                        LEFT JOIN fills f ON f.order_id = o.id
                        WHERE o.trade_id = ? AND o.role = 'ENTRY'
                        """,
                        (trade_id,),
                    ).fetchone()
                    init_qty = float(entry_fill["initial_qty"]) if entry_fill and entry_fill["initial_qty"] else total_qty
                    init_entry_fee = (
                        float(entry_fill["entry_fee"])
                        if entry_fill and entry_fill["entry_fee"] is not None
                        else prior_total_fees
                    )
                    allocated_entry_fee = round(init_entry_fee * (trim_qty / init_qty), 8) if init_qty > 0 else 0.0

                    trim_ratio = trim_qty / total_qty
                    trim_cost = round(cost_basis * trim_ratio, 8)
                    is_short = str(trade["side"] if "side" in trade.keys() else "").upper() == "SHORT"
                    gross_pnl = round(
                        (entry_price - exit_price) * trim_qty if is_short else (exit_price - entry_price) * trim_qty,
                        8,
                    )
                    cash_net_pnl = round(gross_pnl - exit_fee_amount, 8)
                    net_pnl = round(gross_pnl - exit_fee_amount - allocated_entry_fee, 8)

                    # 1. Registrar PnL bruto realizado en OP
                    if abs(gross_pnl) > 1e-8:
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"PnL bruto por toma parcial de {symbol}",
                            ref_type="PNL_REALIZED",
                            ref_id=trade_id,
                            currency=currency,
                            entries=[
                                (f"PNL_{currency}", -gross_pnl),
                                (f"OP_{currency}", +gross_pnl),
                            ],
                        )

                    # 2. Registrar comisión de salida proporcional
                    if exit_fee_amount > 1e-8:
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"Comisión de salida parcial en {symbol}",
                            ref_type="TRADE_FEE",
                            ref_id=trade_id,
                            currency=currency,
                            entries=[
                                (f"OP_{currency}", -round(exit_fee_amount, 8)),
                                (f"FEES_{currency}", +round(exit_fee_amount, 8)),
                            ],
                        )

                    # 3. Sweep-Back a Bóveda del capital liberado + ganancia neta en efectivo (acotado al saldo libre en OP)
                    other_open_row = conn.execute(
                        "SELECT COALESCE(SUM(cost_basis), 0.0) AS locked_cost FROM trades WHERE currency = ? AND status = 'OPEN' AND id != ?",
                        (currency, trade_id),
                    ).fetchone()
                    remaining_this_cost = round(cost_basis - trim_cost, 8)
                    locked_total = round(float(other_open_row["locked_cost"] or 0.0) + remaining_this_cost, 8) if other_open_row else remaining_this_cost
                    op_balance = self._get_account_balance_conn(conn, f"OP_{currency}")
                    swept_amount = round(min(max(0.0, op_balance - locked_total), max(0.0, trim_cost + cash_net_pnl)), 8)
                    if swept_amount > 1e-8:
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"Sweep-Back por peluqueo parcial de {symbol}",
                            ref_type="SWEEP_BACK",
                            ref_id=trade_id,
                            currency=currency,
                            entries=[
                                (f"OP_{currency}", -swept_amount),
                                (f"VAULT_{currency}", +swept_amount),
                            ],
                        )

                    # 4. Actualizar trade: reducir qty y cost_basis, activar Breakeven Real (+0.25% buffer sobre entrada) y marcar tp1_trimmed=1
                    new_qty = round(total_qty - trim_qty, 8)
                    new_cost = round(cost_basis - trim_cost, 8)
                    conn.execute(
                        """
                        UPDATE trades
                        SET qty = ?, cost_basis = ?, realized_pnl = ROUND(realized_pnl + ?, 8),
                            total_fees = ROUND(total_fees + ?, 8), initial_sl_pct = 0.0, current_stop_net_pct = 0.25,
                            be_armed = 1, tp1_trimmed = 1, initial_tp_pct = initial_tp_pct * 2.0
                        WHERE id = ?
                        """,
                        (new_qty, new_cost, net_pnl, exit_fee_amount, trade_id),
                    )

                    # 5. Actualizar Circuit Breaker
                    risk_update = self._update_risk_on_close(
                        conn=conn, currency=currency, net_pnl=net_pnl, now_ts=now_ts
                    )

                    return {
                        "trade_id": trade_id,
                        "symbol": symbol,
                        "currency": currency,
                        "trimmed_qty": trim_qty,
                        "remaining_qty": new_qty,
                        "exit_price": exit_price,
                        "gross_pnl": gross_pnl,
                        "exit_fee": exit_fee_amount,
                        "net_pnl": net_pnl,
                        "swept_to_vault": swept_amount,
                        "operational_balance": self._get_account_balance_conn(conn, f"OP_{currency}"),
                        "vault_balance": self._get_account_balance_conn(conn, f"VAULT_{currency}"),
                        "risk_state": risk_update,
                    }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def scale_in_trade_with_jit(
        self,
        symbol: str,
        add_amount_currency: float,
        current_price: float,
        fee_amount: float = 0.0,
        source_mode: str = "OPERATING_POOL",
        enforce_safe_profit_lock: bool = True,
    ) -> Dict[str, Any]:
        """
        Piramidación / Potenciar Ganadora sobre una posición abierta (`symbol`):
        - Permite inyectar capital adicional (`add_amount_currency`) en una posición abierta que ya está en ganancia.
        - `source_mode`:
            * 'OPERATING_POOL': utiliza el saldo libre del Dinero para Operar (o liberado al rotar una lenta).
            * 'SAFE_PROFIT_WALLET': utiliza la Reserva / Billetera de Ganancia Segura, ampliando automáticamente el cupo operativo.
        - Calcula el Nuevo Precio Promedio Ponderado (`new_entry_price`) y activa el Candado de Ganancia Segura
          (`be_armed = 1`, `current_stop_net_pct >= 0.25%` sobre el nuevo precio promedio) para garantizar Riesgo Cero.
        """
        add_cost = round(float(add_amount_currency or 0.0), 8)
        cur_px = float(current_price or 0.0)
        fee_val = max(0.0, round(float(fee_amount or 0.0), 8))
        if add_cost <= 0 or cur_px <= 0:
            raise ValueError("El monto a inyectar y el precio actual deben ser mayores a cero.")

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    trade = conn.execute(
                        "SELECT * FROM trades WHERE symbol = ? AND status = 'OPEN'",
                        (symbol,),
                    ).fetchone()
                    if not trade:
                        raise ValueError(f"No existe posición abierta en {symbol} para potenciar.")

                    trade_id = trade["id"]
                    currency = trade["currency"]
                    old_qty = float(trade["qty"])
                    old_entry = float(trade["entry_price"])
                    old_cost = float(trade["cost_basis"])
                    old_fees = float(trade["total_fees"] or 0.0)
                    old_stop_net = float(trade["current_stop_net_pct"] or -0.5)
                    is_short = str(trade["side"] if "side" in trade.keys() else "LONG").upper() in ("SHORT", "SELL")
                    prev_peak = float(trade["peak_price"] or old_entry)
                    old_peak = min(prev_peak, cur_px) if is_short else max(prev_peak, cur_px)

                    unrealized_pct = (
                        ((old_entry - cur_px) / old_entry * 100.0)
                        if is_short
                        else ((cur_px - old_entry) / old_entry * 100.0)
                    ) if old_entry > 0 else 0.0
                    if enforce_safe_profit_lock and unrealized_pct < 0.20:
                        raise ValueError(
                            f"Candado de Ganancia Segura activo: {symbol} ({'SHORT' if is_short else 'LONG'}) debe estar en ganancia (+0.20% mín., actual {unrealized_pct:+.2f}%) "
                            f"antes de inyectarle más capital para no promediar a la baja."
                        )

                    add_qty = round(add_cost / cur_px, 8)
                    required_jit = round(add_cost + fee_val, 8)
                    vault_bal = self._get_account_balance_conn(conn, f"VAULT_{currency}")
                    op_bal = self._get_account_balance_conn(conn, f"OP_{currency}")

                    if vault_bal + 1e-8 < required_jit:
                        raise ValueError(
                            f"Efectivo insuficiente en Bóveda ({currency}): disponible=${vault_bal:.2f}, requerido=${required_jit:.2f}."
                        )

                    # Verificar o ampliar el cupo de Dinero para Operar según el modo elegido
                    row_cfg = conn.execute(
                        "SELECT amount FROM operating_capital_config WHERE currency = ?", (currency,)
                    ).fetchone()
                    total_equity = vault_bal + op_bal
                    default_op = 500000.0 if currency == "ARS" else 500.0
                    cur_op_cap = float(row_cfg["amount"]) if row_cfg else min(default_op, total_equity)
                    op_available = max(0.0, cur_op_cap - op_bal)

                    if source_mode == "SAFE_PROFIT_WALLET":
                        row_sw = conn.execute(
                            "SELECT amount, injected_total FROM safe_profit_wallet_config WHERE currency = ?",
                            (currency,),
                        ).fetchone()
                        sw_avail = max(0.0, float(row_sw["amount"])) if row_sw is not None else 0.0
                        sw_inj = max(0.0, float(row_sw["injected_total"])) if row_sw is not None else 0.0
                        if add_cost > sw_avail + 0.05:
                            raise ValueError(
                                f"Saldo insuficiente en la Billetera de Uso por Ganancia Segura (${sw_avail:.2f} {currency} disponibles, "
                                f"solicitado ${add_cost:.2f} {currency}). Primero cárgale fondos desde 'Dinero para Operar' en la tarjeta de la Billetera."
                            )
                        new_sw_avail = max(0.0, round(sw_avail - add_cost, 4))
                        new_sw_inj = round(sw_inj + add_cost, 4)
                        new_op_cap = min(total_equity - new_sw_avail, round(cur_op_cap + add_cost, 4))
                        conn.execute(
                            """
                            INSERT INTO safe_profit_wallet_config (currency, amount, injected_total, updated_at)
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(currency) DO UPDATE SET
                                amount = excluded.amount,
                                injected_total = excluded.injected_total,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            (currency, new_sw_avail, new_sw_inj),
                        )
                        conn.execute(
                            """
                            INSERT INTO operating_capital_config (currency, amount, updated_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(currency) DO UPDATE SET amount = excluded.amount, updated_at = CURRENT_TIMESTAMP
                            """,
                            (currency, new_op_cap),
                        )
                    else:
                        if add_cost > op_available + 0.05:
                            raise ValueError(
                                f"Cupo libre insuficiente en Dinero para Operar (${op_available:.2f} {currency} disponibles, "
                                f"solicitado ${add_cost:.2f} {currency}). Carga fondos en la 'Billetera de Uso por Ganancia Segura' o rota una posición lenta."
                            )

                    # 1. Fondeo Just-In-Time (VAULT -> OP)
                    self._record_double_entry_tx(
                        conn=conn,
                        description=f"JIT Scale-In (Potenciar Ganadora) en {symbol} ({source_mode})",
                        ref_type="ALLOCATE",
                        ref_id=trade_id,
                        currency=currency,
                        entries=[
                            (f"VAULT_{currency}", -required_jit),
                            (f"OP_{currency}", +required_jit),
                        ],
                    )

                    # 2. Registrar comisión de la recarga
                    if fee_val > 1e-8:
                        self._record_double_entry_tx(
                            conn=conn,
                            description=f"Comisión de Scale-In en {symbol}",
                            ref_type="TRADE_FEE",
                            ref_id=trade_id,
                            currency=currency,
                            entries=[
                                (f"OP_{currency}", -fee_val),
                                (f"FEES_{currency}", +fee_val),
                            ],
                        )

                    # 3. Calcular Nuevo Precio Promedio Ponderado y blindar el Stop Loss en ganancia segura
                    new_qty = round(old_qty + add_qty, 8)
                    new_cost = round(old_cost + add_cost, 8)
                    new_entry = round(new_cost / new_qty, 8)
                    new_fees = round(old_fees + fee_val, 8)

                    # Candado de Ganancia Segura: Stop Loss garantizado como mínimo en Breakeven Real (+0.20% sobre nuevo promedio)
                    # sin superar el precio actual menos un margen de respiración de 0.15%
                    headroom_pct = (
                        ((new_entry - cur_px) / new_entry * 100.0)
                        if is_short
                        else ((cur_px - new_entry) / new_entry * 100.0)
                    ) if new_entry > 0 else 0.0
                    safe_stop_pct = max(0.15, min(max(old_stop_net, 0.25), max(0.15, headroom_pct * 0.5)))

                    conn.execute(
                        """
                        UPDATE trades
                        SET qty = ?, entry_price = ?, cost_basis = ?, total_fees = ?,
                            peak_price = ?, be_armed = 1, trail_active = 1, current_stop_net_pct = ?
                        WHERE id = ?
                        """,
                        (new_qty, new_entry, new_cost, new_fees, old_peak, round(safe_stop_pct, 4), trade_id),
                    )

                    # 4. Registrar orden y fill de recarga
                    order_id = str(uuid.uuid4())
                    fill_id = str(uuid.uuid4())
                    order_side_str = "SELL" if is_short else "BUY"
                    conn.execute(
                        """
                        INSERT INTO orders (
                            id, trade_id, client_order_id, symbol, side, type, role, qty, price, status
                        ) VALUES (?, ?, ?, ?, ?, 'MARKET', 'ENTRY', ?, ?, 'FILLED')
                        """,
                        (order_id, trade_id, f"scalein-{order_id[:12]}", symbol, order_side_str, add_qty, cur_px),
                    )
                    conn.execute(
                        """
                        INSERT INTO fills (id, order_id, symbol, qty, price, fee_amount, fee_currency)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (fill_id, order_id, symbol, add_qty, cur_px, fee_val, currency),
                    )

                    return {
                        "trade_id": trade_id,
                        "order_id": order_id,
                        "symbol": symbol,
                        "currency": currency,
                        "source_mode": source_mode,
                        "added_amount": round(add_cost, 2),
                        "added_qty": add_qty,
                        "old_entry_price": old_entry,
                        "new_entry_price": new_entry,
                        "old_cost_basis": round(old_cost, 2),
                        "new_cost_basis": round(new_cost, 2),
                        "new_qty": new_qty,
                        "safe_stop_net_pct": round(safe_stop_pct, 4),
                        "vault_balance": self._get_account_balance_conn(conn, f"VAULT_{currency}"),
                        "operational_balance": self._get_account_balance_conn(conn, f"OP_{currency}"),
                    }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def count_trades_today(self, symbol: Optional[str] = None) -> int:
        """Cuenta cuántos trades se abrieron en la jornada bursátil actual (ART UTC-3, para límite de 1 trade/día)."""
        with self._lock:
            conn = self._connect()
            try:
                if symbol:
                    row = conn.execute(
                        "SELECT COUNT(*) AS cnt FROM trades WHERE symbol = ? AND date(opened_at, '-3 hours') = date('now', '-3 hours')",
                        (symbol,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT COUNT(*) AS cnt FROM trades WHERE date(opened_at, '-3 hours') = date('now', '-3 hours')"
                    ).fetchone()
                return int(row["cnt"]) if row else 0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def update_trade_trailing(
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
        """Actualiza el pico máximo alcanzado, el stop neto móvil (Breakeven / Trailing), la telemetría contrafáctica y decaimiento temporal en SQLite."""
        with self._lock:
            conn = self._connect()
            try:
                params = (
                    float(peak_price),
                    float(current_stop_net_pct),
                    int(be_armed),
                    int(trail_active),
                    trailing_mode,
                    ai_decision_reason,
                    counterfactual_diff,
                    time_decay_hours,
                    time_decay_status,
                    time_decay_suggestion,
                    str(trade_id),
                )
                cur = conn.execute(
                    """
                    UPDATE trades
                    SET peak_price = ?,
                        current_stop_net_pct = ?,
                        be_armed = ?,
                        trail_active = ?,
                        trailing_mode = COALESCE(?, trailing_mode),
                        ai_decision_reason = COALESCE(?, ai_decision_reason),
                        counterfactual_diff = COALESCE(?, counterfactual_diff),
                        time_decay_hours = COALESCE(?, time_decay_hours),
                        time_decay_status = COALESCE(?, time_decay_status),
                        time_decay_suggestion = COALESCE(?, time_decay_suggestion)
                    WHERE id = ? AND status = 'OPEN'
                    """,
                    params,
                )
                if cur.rowcount == 0:
                    conn.execute(
                        """
                        UPDATE futures_trades
                        SET peak_price = ?,
                            current_stop_net_pct = ?,
                            be_armed = ?,
                            trail_active = ?,
                            trailing_mode = COALESCE(?, trailing_mode),
                            ai_decision_reason = COALESCE(?, ai_decision_reason),
                            counterfactual_diff = COALESCE(?, counterfactual_diff),
                            time_decay_hours = COALESCE(?, time_decay_hours),
                            time_decay_status = COALESCE(?, time_decay_status),
                            time_decay_suggestion = COALESCE(?, time_decay_suggestion)
                        WHERE id = ? AND status = 'OPEN'
                        """,
                        params,
                    )
                conn.commit()
                return True
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_futures_sim_account(self) -> Dict[str, Any]:
        """Devuelve el estado aislado de la cuenta de simulación de Micro-Futuros."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT account_id, initial_balance, balance, realized_pnl, total_fees, total_spread, total_swap, updated_at FROM futures_sim_account WHERE account_id = 'SIM_FUTURES'"
                ).fetchone()
                if not row:
                    return {"account_id": "SIM_FUTURES", "initial_balance": 2500.0, "balance": 2500.0, "realized_pnl": 0.0, "total_fees": 0.0}
                return {
                    "account_id": row["account_id"],
                    "initial_balance": round(float(row["initial_balance"]), 4),
                    "balance": round(float(row["balance"]), 4),
                    "realized_pnl": round(float(row["realized_pnl"]), 4),
                    "total_fees": round(float(row["total_fees"]), 4),
                    "total_spread": round(float(row["total_spread"]), 4),
                    "total_swap": round(float(row["total_swap"]), 4),
                    "updated_at": row["updated_at"],
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def reset_futures_sim_account(self, initial_balance: float = 2500.0) -> Dict[str, Any]:
        """Reinicia la cuenta simulada de micro-futuros sin afectar las bóvedas Spot (USDT, USD, ARS)."""
        init_bal = float(initial_balance)
        if not math.isfinite(init_bal) or init_bal <= 0:
            raise ValueError("El saldo inicial simulado debe ser positivo.")
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute("DELETE FROM futures_trades")
                    conn.execute("DELETE FROM futures_cost_events")
                    conn.execute(
                        """
                        INSERT INTO futures_sim_account (account_id, initial_balance, balance, realized_pnl, total_fees, updated_at)
                        VALUES ('SIM_FUTURES', ?, ?, 0.0, 0.0, CURRENT_TIMESTAMP)
                        ON CONFLICT(account_id) DO UPDATE SET
                            initial_balance = excluded.initial_balance,
                            balance = excluded.balance,
                            realized_pnl = 0.0,
                            total_fees = 0.0,
                            total_spread = 0.0,
                            total_swap = 0.0,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (init_bal, init_bal),
                    )
                return self.get_futures_sim_account()
            finally:
                if self._memory_conn is None:
                    conn.close()

    def _record_futures_cost_event(
        self,
        conn: sqlite3.Connection,
        trade_id: str,
        symbol: str,
        event_type: str,
        amount: float,
        contracts: float,
        note: str = "",
    ) -> None:
        """Registra un costo de fricción desglosado (comisión, spread o swap) en `futures_cost_events`."""
        if abs(float(amount)) <= 1e-12:
            return
        conn.execute(
            """
            INSERT INTO futures_cost_events (id, trade_id, symbol, event_type, amount, contracts, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), trade_id, symbol, event_type, round(float(amount), 8), float(contracts), note),
        )

    def _futures_be_for_trade(
        self,
        symbol: str,
        entry_price: float,
        side: str,
        contracts: float,
        spread_ticks: float,
        swap_usd: float,
    ) -> float:
        """Break-Even Real de `contracts` contratos cubriendo comisiones + spread + swap acumulado."""
        from backend.quant_risk import compute_futures_breakeven_price

        res = compute_futures_breakeven_price(
            symbol=symbol,
            entry_price=entry_price,
            side=side,
            contracts=contracts,
            spread_ticks_per_side=spread_ticks,
            swap_usd=swap_usd,
        )
        return float(res["be_price"])

    def _accrue_futures_swap_conn(self, conn: sqlite3.Connection, trade: Any, now_ts: float) -> Dict[str, Any]:
        """
        Devenga el swap por cada corte de jornada superado desde el último devengo (misma transacción del caller).
        El costo es por contrato y por noche; se debita de SIM_FUTURES y queda atribuido por contrato.
        """
        from backend.quant_risk import count_rollover_crossings

        swap_pc = float(trade["swap_per_contract_night"] or 0.0)
        accrued_pc = float(trade["swap_accrued_per_contract"] or 0.0)
        contracts = float(trade["contracts"])
        last_ts = float(trade["last_swap_ts"] or trade["opened_ts"] or now_ts)
        nights = count_rollover_crossings(last_ts, now_ts) if swap_pc > 0.0 else 0
        charged = 0.0
        if nights > 0:
            charged = round(swap_pc * nights * contracts, 8)
            accrued_pc = round(accrued_pc + swap_pc * nights, 8)
            conn.execute(
                """
                UPDATE futures_sim_account
                SET balance = ROUND(balance - ?, 8),
                    total_swap = ROUND(total_swap + ?, 8),
                    updated_at = CURRENT_TIMESTAMP
                WHERE account_id = 'SIM_FUTURES'
                """,
                (charged, charged),
            )
            conn.execute(
                """
                UPDATE futures_trades
                SET swap_accrued_per_contract = ?, swap_cost = ROUND(swap_cost + ?, 8), last_swap_ts = ?
                WHERE id = ?
                """,
                (accrued_pc, charged, float(now_ts), trade["id"]),
            )
            self._record_futures_cost_event(
                conn, trade["id"], trade["symbol"], "SWAP", charged, contracts, f"{nights} corte(s) de jornada"
            )
        return {"nights": nights, "swap_charged": charged, "swap_accrued_per_contract": accrued_pc}

    def accrue_futures_swap(self, symbol: str, now_ts: Optional[float] = None) -> Dict[str, Any]:
        """Devenga swap pendiente de la posición abierta y recalcula su Break-Even Real. Aislado de bóvedas Spot."""
        from backend.quant_risk import get_micro_futures_spec

        spec = get_micro_futures_spec(symbol)
        canon_sym = spec["symbol"] if spec else symbol
        ts = float(now_ts if now_ts is not None else time.time())
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    trade = conn.execute(
                        "SELECT * FROM futures_trades WHERE symbol = ? AND status = 'OPEN'", (canon_sym,)
                    ).fetchone()
                    if not trade:
                        return {"accrued": False, "symbol": canon_sym, "nights": 0, "swap_charged": 0.0, "be_price": None}
                    res = self._accrue_futures_swap_conn(conn, trade, ts)
                    contracts = float(trade["contracts"])
                    be_price = float(trade["be_price"] or 0.0)
                    if res["swap_charged"] > 0.0:
                        be_price = self._futures_be_for_trade(
                            canon_sym,
                            float(trade["entry_price"]),
                            str(trade["side"]),
                            contracts,
                            float(trade["spread_ticks_per_side"] or 0.0),
                            res["swap_accrued_per_contract"] * contracts,
                        )
                        conn.execute("UPDATE futures_trades SET be_price = ? WHERE id = ?", (be_price, trade["id"]))
                return {
                    "accrued": res["swap_charged"] > 0.0,
                    "symbol": canon_sym,
                    "trade_id": trade["id"],
                    "nights": res["nights"],
                    "swap_charged": res["swap_charged"],
                    "swap_accrued_per_contract": res["swap_accrued_per_contract"],
                    "be_price": be_price if be_price > 0 else None,
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_futures_cost_breakdown(self, trade_id: str) -> Dict[str, Any]:
        """Suma el desglose de fricción de un trade de futuros (comisiones, spread, swap) desde `futures_cost_events`."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT event_type, ROUND(SUM(amount), 8) AS total FROM futures_cost_events WHERE trade_id = ? GROUP BY event_type",
                    (str(trade_id),),
                ).fetchall()
                by_type = {str(r["event_type"]): float(r["total"]) for r in rows}
                commission = round(by_type.get("ENTRY_COMMISSION", 0.0) + by_type.get("EXIT_COMMISSION", 0.0), 8)
                spread = round(by_type.get("ENTRY_SPREAD", 0.0) + by_type.get("EXIT_SPREAD", 0.0), 8)
                swap = round(by_type.get("SWAP", 0.0), 8)
                return {
                    "trade_id": str(trade_id),
                    "by_type": by_type,
                    "commission": commission,
                    "spread": spread,
                    "swap": swap,
                    "total_friction": round(commission + spread + swap, 8),
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def open_futures_trade(
        self,
        symbol: str,
        contracts: float,
        entry_price: float,
        initial_tp_pct: float = 0.8,
        initial_sl_pct: float = 0.4,
        side: str = "LONG",
        strategy: str = "kula_balam_cava_ruiz",
        engine: str = "antigravity_operador",
        formula: str = "Kula Triad Futures",
        spread_ticks_per_side: Optional[float] = None,
        swap_per_contract_night: Optional[float] = None,
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Abre una operación simulada en `futures_trades` descontando comisión fija por contrato ($1.25/lado) y
        spread de entrada (ticks) en `futures_sim_account`, con desglose en `futures_cost_events`.
        Aislado totalmente de USDT/USD/ARS.
        """
        from backend.quant_risk import build_futures_friction_profile, get_micro_futures_spec

        spec = get_micro_futures_spec(symbol)
        if spec is None:
            raise ValueError(f"Símbolo no soportado en simulación de micro-futuros: {symbol}")
        n_contracts = float(contracts or spec["default_contracts"])
        if n_contracts <= 0 or entry_price <= 0:
            raise ValueError("Contratos y precio de entrada deben ser positivos.")
        profile = build_futures_friction_profile(
            symbol,
            spread_ticks_per_side=spread_ticks_per_side,
            swap_per_contract_night=swap_per_contract_night,
        )

        canon_sym = profile.symbol
        entry_commission = round(profile.commission_per_side * n_contracts, 8)
        entry_spread = round(profile.spread_cost_per_side(n_contracts), 8)
        entry_cost = round(entry_commission + entry_spread, 8)
        trade_side = "SHORT" if str(side or "LONG").strip().upper() in ("SHORT", "SELL") else "LONG"
        trade_id = str(uuid.uuid4())
        opened_ts = float(now_ts if now_ts is not None else time.time())
        be_price = self._futures_be_for_trade(
            canon_sym, float(entry_price), trade_side, n_contracts, profile.spread_ticks_per_side, 0.0
        )

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    acc_row = conn.execute(
                        "SELECT balance FROM futures_sim_account WHERE account_id = 'SIM_FUTURES'"
                    ).fetchone()
                    cur_bal = float(acc_row["balance"]) if acc_row else 2500.0
                    if cur_bal < entry_cost + 25.0:
                        raise ValueError(f"Margen virtual insuficiente en cuenta simulada de futuros (${cur_bal:.2f}).")

                    conn.execute(
                        """
                        UPDATE futures_sim_account
                        SET balance = ROUND(balance - ?, 8),
                            total_fees = ROUND(total_fees + ?, 8),
                            total_spread = ROUND(total_spread + ?, 8),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE account_id = 'SIM_FUTURES'
                        """,
                        (entry_cost, entry_commission, entry_spread),
                    )
                    params = (
                        trade_id, canon_sym, "FUTURES_MICRO", trade_side, "OPEN", n_contracts, n_contracts,
                        profile.multiplier, profile.tick_size, profile.tick_value, float(entry_price),
                        entry_commission, float(initial_tp_pct), float(initial_sl_pct), -abs(float(initial_sl_pct)),
                        float(entry_price), strategy, engine, formula, profile.spread_ticks_per_side,
                        profile.swap_per_contract_night, opened_ts, opened_ts, entry_commission, entry_spread,
                        be_price,
                    )
                    conn.execute(
                        f"""
                        INSERT INTO futures_trades (
                            id, symbol, asset_class, side, status, contracts, initial_contracts,
                            multiplier, tick_size, tick_value, entry_price, total_fees,
                            initial_tp_pct, initial_sl_pct, current_stop_net_pct, peak_price,
                            strategy, engine, formula, spread_ticks_per_side, swap_per_contract_night,
                            opened_ts, last_swap_ts, entry_commission, spread_cost, be_price
                        ) VALUES ({", ".join(["?"] * len(params))})
                        """,
                        params,
                    )
                    self._record_futures_cost_event(conn, trade_id, canon_sym, "ENTRY_COMMISSION", entry_commission, n_contracts)
                    self._record_futures_cost_event(conn, trade_id, canon_sym, "ENTRY_SPREAD", entry_spread, n_contracts)
                acc_after = self.get_futures_sim_account()
                return {
                    "trade_id": trade_id,
                    "symbol": canon_sym,
                    "asset_class": "FUTURES_MICRO",
                    "currency": "SIM_FUTURES",
                    "side": trade_side,
                    "contracts": n_contracts,
                    "qty": n_contracts,
                    "multiplier": profile.multiplier,
                    "tick_size": profile.tick_size,
                    "tick_value": profile.tick_value,
                    "entry_price": float(entry_price),
                    "fee_amount": entry_cost,
                    "entry_commission": entry_commission,
                    "entry_spread_cost": entry_spread,
                    "be_price": be_price,
                    "futures_balance": acc_after["balance"],
                    "status": "OPEN",
                }
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Ya existe una posición abierta en micro-futuros para {canon_sym}.") from exc
            finally:
                if self._memory_conn is None:
                    conn.close()

    def trim_futures_trade(
        self,
        symbol: str,
        trim_contracts: float,
        exit_price: float,
        exit_reason: str = "PELUQUEO_TP1_50%",
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Cierra parcialmente contratos en TP1 (ej. 1 de 2). El contrato remanente pasa a Break-Even Real:
        precio que cubre comisiones de entrada y salida + spread + swap acumulado del remanente ($0 neto al liquidar).
        """
        from backend.quant_risk import calculate_futures_pnl, get_micro_futures_spec

        spec = get_micro_futures_spec(symbol)
        canon_sym = spec["symbol"] if spec else symbol
        if trim_contracts <= 0 or exit_price <= 0:
            raise ValueError("Contratos a recortar y precio de salida deben ser positivos.")
        ts = float(now_ts if now_ts is not None else time.time())

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    trade = conn.execute(
                        "SELECT * FROM futures_trades WHERE symbol = ? AND status = 'OPEN'",
                        (canon_sym,),
                    ).fetchone()
                    if not trade:
                        raise ValueError(f"No existe posición abierta en futuros para {canon_sym}.")

                    total_contracts = float(trade["contracts"])
                    if trim_contracts >= total_contracts:
                        raise ValueError(
                            f"trim_contracts ({trim_contracts}) debe ser menor que contratos abiertos ({total_contracts})."
                        )

                    accr = self._accrue_futures_swap_conn(conn, trade, ts)
                    accrued_pc = float(accr["swap_accrued_per_contract"])
                    spread_ticks = float(trade["spread_ticks_per_side"] or 0.0)
                    entry_price = float(trade["entry_price"])
                    side = str(trade["side"])
                    pnl_info = calculate_futures_pnl(
                        symbol=canon_sym,
                        entry_price=entry_price,
                        exit_price=float(exit_price),
                        contracts=float(trim_contracts),
                        side=side,
                        spread_ticks_per_side=spread_ticks,
                        swap_usd=accrued_pc * float(trim_contracts),
                    )
                    gross_pnl = float(pnl_info["gross_pnl"])
                    exit_fee = float(pnl_info["exit_commission"])
                    exit_spread = float(pnl_info["exit_spread_cost"])
                    leg_net_pnl = float(pnl_info["net_pnl"])
                    cash_delta = round(gross_pnl - exit_fee - exit_spread, 8)
                    remaining_contracts = round(total_contracts - float(trim_contracts), 8)

                    be_price = self._futures_be_for_trade(
                        canon_sym, entry_price, side, remaining_contracts, spread_ticks, accrued_pc * remaining_contracts
                    )
                    be_gross_pct = round(abs(be_price - entry_price) / entry_price * 100.0, 4)

                    conn.execute(
                        """
                        UPDATE futures_sim_account
                        SET balance = ROUND(balance + ?, 8),
                            realized_pnl = ROUND(realized_pnl + ?, 8),
                            total_fees = ROUND(total_fees + ?, 8),
                            total_spread = ROUND(total_spread + ?, 8),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE account_id = 'SIM_FUTURES'
                        """,
                        (cash_delta, leg_net_pnl, exit_fee, exit_spread),
                    )
                    conn.execute(
                        """
                        UPDATE futures_trades
                        SET contracts = ?,
                            realized_pnl = ROUND(realized_pnl + ?, 8),
                            total_fees = ROUND(total_fees + ?, 8),
                            exit_commission = ROUND(exit_commission + ?, 8),
                            spread_cost = ROUND(spread_cost + ?, 8),
                            initial_sl_pct = 0.0,
                            current_stop_net_pct = ?,
                            be_armed = 1,
                            tp1_trimmed = 1,
                            initial_tp_pct = initial_tp_pct * 2.0,
                            be_price = ?
                        WHERE id = ?
                        """,
                        (
                            remaining_contracts, leg_net_pnl, exit_fee, exit_fee, exit_spread,
                            be_gross_pct, be_price, trade["id"],
                        ),
                    )
                    self._record_futures_cost_event(conn, trade["id"], canon_sym, "EXIT_COMMISSION", exit_fee, trim_contracts, exit_reason)
                    self._record_futures_cost_event(conn, trade["id"], canon_sym, "EXIT_SPREAD", exit_spread, trim_contracts, exit_reason)
                acc_after = self.get_futures_sim_account()
                return {
                    "trade_id": trade["id"],
                    "symbol": canon_sym,
                    "asset_class": "FUTURES_MICRO",
                    "currency": "SIM_FUTURES",
                    "trimmed_qty": float(trim_contracts),
                    "remaining_qty": remaining_contracts,
                    "exit_price": float(exit_price),
                    "gross_pnl": gross_pnl,
                    "exit_fee": exit_fee,
                    "commission_leg": float(pnl_info["total_commission"]),
                    "spread_cost_leg": float(pnl_info["spread_cost"]),
                    "swap_cost_leg": float(pnl_info["swap_cost"]),
                    "swap_nights": accr["nights"],
                    "net_pnl": leg_net_pnl,
                    "be_price": be_price,
                    "futures_balance": acc_after["balance"],
                    "swept_to_vault": 0.0,
                    "vault_balance": acc_after["balance"],
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def close_futures_trade(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str = "TAKE_PROFIT_OR_MANUAL",
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Cierra la posición simulada: liquida PnL neto por ticks/multiplicador incluyendo spread y swap acumulado."""
        from backend.quant_risk import calculate_futures_pnl, get_micro_futures_spec

        spec = get_micro_futures_spec(symbol)
        canon_sym = spec["symbol"] if spec else symbol
        if exit_price <= 0:
            raise ValueError("El precio de salida debe ser positivo.")
        ts = float(now_ts if now_ts is not None else time.time())

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    trade = conn.execute(
                        "SELECT * FROM futures_trades WHERE symbol = ? AND status = 'OPEN'",
                        (canon_sym,),
                    ).fetchone()
                    if not trade:
                        raise ValueError(f"No existe posición abierta en futuros para {canon_sym}.")

                    accr = self._accrue_futures_swap_conn(conn, trade, ts)
                    accrued_pc = float(accr["swap_accrued_per_contract"])
                    rem_contracts = float(trade["contracts"])
                    prior_realized_pnl = float(trade["realized_pnl"] or 0.0)
                    prior_fees = float(trade["total_fees"] or 0.0)
                    prior_spread = float(trade["spread_cost"] or 0.0)
                    prior_swap = float(trade["swap_cost"] or 0.0) + float(accr["swap_charged"])
                    pnl_info = calculate_futures_pnl(
                        symbol=canon_sym,
                        entry_price=float(trade["entry_price"]),
                        exit_price=float(exit_price),
                        contracts=rem_contracts,
                        side=str(trade["side"]),
                        spread_ticks_per_side=float(trade["spread_ticks_per_side"] or 0.0),
                        swap_usd=accrued_pc * rem_contracts,
                    )
                    gross_pnl = float(pnl_info["gross_pnl"])
                    exit_fee = float(pnl_info["exit_commission"])
                    exit_spread = float(pnl_info["exit_spread_cost"])
                    leg_net_pnl = float(pnl_info["net_pnl"])
                    cumulative_net_pnl = round(prior_realized_pnl + leg_net_pnl, 4)
                    total_fees = round(prior_fees + exit_fee, 4)
                    total_spread = round(prior_spread + exit_spread, 4)
                    cash_delta = round(gross_pnl - exit_fee - exit_spread, 8)

                    conn.execute(
                        """
                        UPDATE futures_sim_account
                        SET balance = ROUND(balance + ?, 8),
                            realized_pnl = ROUND(realized_pnl + ?, 8),
                            total_fees = ROUND(total_fees + ?, 8),
                            total_spread = ROUND(total_spread + ?, 8),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE account_id = 'SIM_FUTURES'
                        """,
                        (cash_delta, leg_net_pnl, exit_fee, exit_spread),
                    )
                    conn.execute(
                        """
                        UPDATE futures_trades
                        SET status = 'CLOSED',
                            exit_price = ?,
                            realized_pnl = ?,
                            total_fees = ?,
                            exit_commission = ROUND(exit_commission + ?, 8),
                            spread_cost = ?,
                            exit_reason = ?,
                            closed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (float(exit_price), cumulative_net_pnl, total_fees, exit_fee, total_spread, exit_reason, trade["id"]),
                    )
                    self._record_futures_cost_event(conn, trade["id"], canon_sym, "EXIT_COMMISSION", exit_fee, rem_contracts, exit_reason)
                    self._record_futures_cost_event(conn, trade["id"], canon_sym, "EXIT_SPREAD", exit_spread, rem_contracts, exit_reason)
                acc_after = self.get_futures_sim_account()
                return {
                    "trade_id": trade["id"],
                    "symbol": canon_sym,
                    "asset_class": "FUTURES_MICRO",
                    "currency": "SIM_FUTURES",
                    "contracts_closed": rem_contracts,
                    "exit_price": float(exit_price),
                    "gross_pnl": gross_pnl,
                    "leg_net_pnl": leg_net_pnl,
                    "net_pnl": cumulative_net_pnl,
                    "total_fees": total_fees,
                    "spread_cost": total_spread,
                    "swap_cost": round(prior_swap, 8),
                    "swap_nights": accr["nights"],
                    "futures_balance": acc_after["balance"],
                    "swept_to_vault": 0.0,
                    "vault_balance": acc_after["balance"],
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_open_futures_positions(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM futures_trades WHERE status = 'OPEN' ORDER BY opened_at ASC"
                ).fetchall()
                result: List[Dict[str, Any]] = []
                for r in rows:
                    d = dict(r)
                    d["qty"] = float(d["contracts"])
                    d["currency"] = "SIM_FUTURES"
                    d["cost_basis"] = 0.0  # Aislado de bóvedas Spot USDT/USD/ARS
                    d["notional_value"] = round(float(d["contracts"]) * float(d["multiplier"]) * float(d["entry_price"]), 2)
                    result.append(d)
                return result
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_open_positions(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE status = 'OPEN' ORDER BY opened_at ASC"
                ).fetchall()
                positions = [dict(r) for r in rows]
            finally:
                if self._memory_conn is None:
                    conn.close()
        positions.extend(self.get_open_futures_positions())
        return positions

    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna el historial de operaciones (Spot + Micro-Futuros) ordenadas por fecha reciente."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT id, symbol, currency, side, status, qty, entry_price, exit_price,
                           cost_basis, realized_pnl, total_fees, initial_tp_pct, initial_sl_pct,
                           current_stop_net_pct, peak_price, be_armed, trail_active,
                           trailing_mode, ai_decision_reason, counterfactual_diff,
                           time_decay_hours, time_decay_status, time_decay_suggestion,
                           strategy, engine, formula, opened_at, closed_at, exit_reason
                    FROM trades
                    ORDER BY COALESCE(closed_at, opened_at) DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                spot_hist = [dict(r) for r in rows]
                f_rows = conn.execute(
                    """
                    SELECT id, symbol, 'SIM_FUTURES' AS currency, asset_class, side, status,
                           contracts AS qty, contracts, multiplier, tick_size, tick_value,
                           entry_price, exit_price, 0.0 AS cost_basis, realized_pnl, total_fees,
                           initial_tp_pct, initial_sl_pct, current_stop_net_pct, peak_price,
                           be_armed, trail_active, trailing_mode, ai_decision_reason,
                           counterfactual_diff, time_decay_hours, time_decay_status,
                           time_decay_suggestion, strategy, engine, formula,
                           opened_at, closed_at, exit_reason
                    FROM futures_trades
                    ORDER BY COALESCE(closed_at, opened_at) DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                fut_hist = [dict(r) for r in f_rows]
                combined = spot_hist + fut_hist
                combined.sort(key=lambda x: str(x.get("closed_at") or x.get("opened_at") or ""), reverse=True)
                return combined[:limit]
            finally:
                if self._memory_conn is None:
                    conn.close()

    def record_signal_evaluation(
        self,
        symbol: str,
        engine: str,
        signal: str,
        reason: str,
        price: float,
        timeframe: str,
        signal_candle_ts: Optional[int] = None,
        data_age_s: Optional[int] = None,
        raw_response: Any = None,
    ) -> Optional[str]:
        """
        Persiste en `signals` el veredicto de una vela evaluada (Embudo de Rechazos).
        - Respeta el CHECK de la tabla: SHORT/LONG/BUY se guardan como COMPRAR y el original queda en raw_response.
        - Retención liviana: borra filas con más de SIGNALS_RETENTION_DAYS (poda amortizada, no en cada insert).
        - No toca saldos, trades ni cuentas.
        """
        from backend.rejection_funnel import (
            SIGNALS_RETENTION_DAYS,
            clip_reason,
            dump_payload,
            normalize_signal_for_ledger,
            parse_payload,
        )

        ledger_signal, original = normalize_signal_for_ledger(signal)
        payload = parse_payload(raw_response) if raw_response else {}
        if original and original != ledger_signal:
            payload["signal_original"] = original
        raw_text = dump_payload(payload) if payload else None

        try:
            px = float(price)
        except (TypeError, ValueError):
            px = 0.0
        if not math.isfinite(px):
            px = 0.0
        sig_id = str(uuid.uuid4())

        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO signals (
                        id, symbol, engine, signal, reason, price, timeframe,
                        signal_candle_ts, data_age_s, raw_response
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sig_id,
                        str(symbol),
                        str(engine or "local"),
                        ledger_signal,
                        clip_reason(reason) or "(sin motivo)",
                        px,
                        str(timeframe or ""),
                        int(signal_candle_ts or 0),
                        int(data_age_s or 0),
                        raw_text,
                    ),
                )
                now_m = time.monotonic()
                last_prune = float(getattr(self, "_signals_last_prune_mono", 0.0) or 0.0)
                if last_prune <= 0.0 or (now_m - last_prune) >= 3600.0:
                    conn.execute(
                        "DELETE FROM signals WHERE created_at < datetime('now', ?)",
                        (f"-{int(SIGNALS_RETENTION_DAYS)} days",),
                    )
                    self._signals_last_prune_mono = now_m
                conn.commit()
                return sig_id
            finally:
                if self._memory_conn is None:
                    conn.close()

    def open_shadow_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        initial_sl_pct: float,
        initial_tp_pct: float,
        strategy: str,
        arbiter_verdict: str = "AHORA_NO",
        arbiter_reason: str = "",
        headlines: Optional[List[Dict[str, str]]] = None,
        deduplicate: bool = True,
    ) -> str:
        """
        Registra una operación virtual vetada por el árbitro en la Tabla #19 shadow_trades.
        No descuenta saldos de ninguna bóveda real (USDT, USD, ARS) ni altera la tabla trades.
        Si `deduplicate=True` y ya existe un shadow OPEN para `(symbol, strategy, side)`, retorna su id.
        """
        import uuid
        import json
        shadow_id = str(uuid.uuid4())
        headlines_json = json.dumps(headlines or [])
        norm_side = "SHORT" if str(side or "").upper() in ("SHORT", "SELL") else "LONG"
        with self._lock:
            conn = self._connect()
            try:
                if deduplicate:
                    existing = conn.execute(
                        """
                        SELECT id FROM shadow_trades
                        WHERE status = 'OPEN' AND symbol = ? AND strategy = ? AND side = ? AND COALESCE(arbiter_verdict, '') = ?
                        LIMIT 1
                        """,
                        (symbol, strategy, norm_side, str(arbiter_verdict or "")),
                    ).fetchone()
                    if existing:
                        return str(existing["id"])
                conn.execute(
                    """
                    INSERT INTO shadow_trades (
                        id, symbol, side, status, qty, entry_price, exit_price,
                        sl_price, tp_price, initial_sl_pct, initial_tp_pct,
                        virtual_pnl_usd, virtual_pnl_pct, outcome, strategy,
                        arbiter_verdict, arbiter_reason, headlines_json, opened_at, closed_at
                    ) VALUES (
                        ?, ?, ?, 'OPEN', ?, ?, NULL,
                        ?, ?, ?, ?,
                        0.0, 0.0, 'PENDING', ?,
                        ?, ?, ?, CURRENT_TIMESTAMP, NULL
                    )
                    """,
                    (
                        shadow_id,
                        symbol,
                        norm_side,
                        float(qty),
                        float(entry_price),
                        float(sl_price),
                        float(tp_price),
                        float(initial_sl_pct),
                        float(initial_tp_pct),
                        strategy,
                        arbiter_verdict,
                        arbiter_reason,
                        headlines_json,
                    ),
                )
                conn.commit()
                return shadow_id
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_open_shadow_trades(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna las posiciones virtuales abiertas en shadow_trades."""
        with self._lock:
            conn = self._connect()
            try:
                if symbol:
                    rows = conn.execute(
                        "SELECT * FROM shadow_trades WHERE status = 'OPEN' AND symbol = ? ORDER BY opened_at ASC",
                        (symbol,)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM shadow_trades WHERE status = 'OPEN' ORDER BY opened_at ASC"
                    ).fetchall()
                return [dict(r) for r in rows]
            finally:
                if self._memory_conn is None:
                    conn.close()

    def update_and_close_shadow_trades(
        self,
        symbol: str,
        current_price: float,
        high_price: Optional[float] = None,
        low_price: Optional[float] = None,
        expiry_hours: float = 24.0,
    ) -> List[Dict[str, Any]]:
        """
        Evalúa y liquida virtualmente operaciones en shadow_trades.
        - Si toca SL: outcome = 'SAVED_SL' (Drawdown Ahorrado).
        - Si toca TP: outcome = 'MISSED_TP' (Ganancia Perdida).
        - Si supera `expiry_hours` (24h por defecto) sin tocar SL ni TP: outcome = 'EXPIRED'.
        """
        closed_trades: List[Dict[str, Any]] = []
        cur_p = float(current_price)
        high_p = float(high_price if high_price is not None else current_price)
        low_p = float(low_price if low_price is not None else current_price)
        now_utc = datetime.now(timezone.utc)

        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM shadow_trades WHERE status = 'OPEN' AND symbol = ?",
                    (symbol,)
                ).fetchall()
                for r in rows:
                    row = dict(r)
                    side = row["side"].upper()
                    entry_px = float(row["entry_price"])
                    sl_px = float(row["sl_price"])
                    tp_px = float(row["tp_price"])
                    qty = float(row["qty"])
                    sl_pct = float(row["initial_sl_pct"])
                    tp_pct = float(row["initial_tp_pct"])
                    outcome = None
                    exit_px = None
                    v_pnl_usd = 0.0
                    v_pnl_pct = 0.0

                    if side in ("LONG", "BUY"):
                        if low_p <= sl_px:
                            outcome = "SAVED_SL"
                            exit_px = sl_px
                            v_pnl_pct = -abs(sl_pct)
                            v_pnl_usd = (sl_px - entry_px) * qty
                        elif high_p >= tp_px:
                            outcome = "MISSED_TP"
                            exit_px = tp_px
                            v_pnl_pct = abs(tp_pct)
                            v_pnl_usd = (tp_px - entry_px) * qty
                    else:  # SHORT
                        if high_p >= sl_px:
                            outcome = "SAVED_SL"
                            exit_px = sl_px
                            v_pnl_pct = -abs(sl_pct)
                            v_pnl_usd = (entry_px - sl_px) * qty
                        elif low_p <= tp_px:
                            outcome = "MISSED_TP"
                            exit_px = tp_px
                            v_pnl_pct = abs(tp_pct)
                            v_pnl_usd = (entry_px - tp_px) * qty

                    if outcome is None and expiry_hours and float(expiry_hours) > 0 and row.get("opened_at"):
                        try:
                            raw_ts = str(row["opened_at"]).replace("Z", "+00:00").strip()
                            dt_open = datetime.fromisoformat(raw_ts)
                            if dt_open.tzinfo is None:
                                dt_open = dt_open.replace(tzinfo=timezone.utc)
                            if (now_utc - dt_open).total_seconds() >= float(expiry_hours) * 3600.0:
                                outcome = "EXPIRED"
                                exit_px = cur_p
                                if side in ("LONG", "BUY"):
                                    v_pnl_pct = ((cur_p - entry_px) / entry_px * 100.0) if entry_px > 0 else 0.0
                                    v_pnl_usd = (cur_p - entry_px) * qty
                                else:
                                    v_pnl_pct = ((entry_px - cur_p) / entry_px * 100.0) if entry_px > 0 else 0.0
                                    v_pnl_usd = (entry_px - cur_p) * qty
                        except Exception:
                            pass

                    if outcome is not None:
                        conn.execute(
                            """
                            UPDATE shadow_trades
                            SET status = 'CLOSED',
                                exit_price = ?,
                                virtual_pnl_usd = ?,
                                virtual_pnl_pct = ?,
                                outcome = ?,
                                closed_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                            """,
                            (exit_px, v_pnl_usd, v_pnl_pct, outcome, row["id"]),
                        )
                        row.update({
                            "status": "CLOSED",
                            "exit_price": exit_px,
                            "virtual_pnl_usd": v_pnl_usd,
                            "virtual_pnl_pct": v_pnl_pct,
                            "outcome": outcome,
                        })
                        closed_trades.append(row)
                if closed_trades:
                    conn.commit()
                return closed_trades
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_shadow_trades_summary(self) -> Dict[str, Any]:
        """Calcula el balance forense de Drawdown Ahorrado vs. Ganancia Perdida."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_vetoed,
                        SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_count,
                        SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) as closed_count,
                        SUM(CASE WHEN outcome = 'SAVED_SL' THEN 1 ELSE 0 END) as saved_sl_count,
                        SUM(CASE WHEN outcome = 'MISSED_TP' THEN 1 ELSE 0 END) as missed_tp_count,
                        SUM(CASE WHEN outcome = 'EXPIRED' THEN 1 ELSE 0 END) as expired_count,
                        SUM(CASE WHEN outcome = 'SAVED_SL' THEN ABS(virtual_pnl_usd) ELSE 0.0 END) as saved_drawdown_usd,
                        SUM(CASE WHEN outcome = 'MISSED_TP' THEN virtual_pnl_usd ELSE 0.0 END) as missed_profit_usd,
                        SUM(CASE WHEN outcome = 'EXPIRED' THEN virtual_pnl_usd ELSE 0.0 END) as expired_pnl_usd
                    FROM shadow_trades
                    """
                ).fetchone()
                total = int(row["total_vetoed"] or 0)
                saved_count = int(row["saved_sl_count"] or 0)
                missed_count = int(row["missed_tp_count"] or 0)
                expired_count = int(row["expired_count"] or 0)
                closed_count = int(row["closed_count"] or 0)
                saved_dd = float(row["saved_drawdown_usd"] or 0.0)
                missed_prof = float(row["missed_profit_usd"] or 0.0)
                expired_pnl = float(row["expired_pnl_usd"] or 0.0)
                net_saved = saved_dd - missed_prof
                accuracy = (saved_count / closed_count * 100.0) if closed_count > 0 else 0.0

                return {
                    "total_vetoed": total,
                    "open_count": int(row["open_count"] or 0),
                    "closed_count": closed_count,
                    "saved_sl_count": saved_count,
                    "missed_tp_count": missed_count,
                    "expired_count": expired_count,
                    "saved_drawdown_usd": round(saved_dd, 4),
                    "missed_profit_usd": round(missed_prof, 4),
                    "expired_pnl_usd": round(expired_pnl, 4),
                    "net_saved_usd": round(net_saved, 4),
                    "arbiter_accuracy_pct": round(accuracy, 2),
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def verify_double_entry_integrity(self) -> Dict[str, Any]:
        """
        Verifica matemáticamente que todas las transacciones registradas en ledger_txns
        sumen exactamente 0.0 en ledger_entries.
        """
        with self._lock:
            conn = self._connect()
            try:
                imbalanced = conn.execute(
                    """
                    SELECT txn_id, SUM(amount) AS net_sum
                    FROM ledger_entries
                    GROUP BY txn_id
                    HAVING ABS(SUM(amount)) > 1e-6
                    """
                ).fetchall()
                total_txns = conn.execute("SELECT COUNT(*) AS cnt FROM ledger_txns").fetchone()["cnt"]
                return {
                    "valid": len(imbalanced) == 0,
                    "total_transactions": int(total_txns),
                    "imbalanced_transactions": [dict(r) for r in imbalanced],
                }
            finally:
                if self._memory_conn is None:
                    conn.close()


_DEFAULT_LEDGER: Optional[LedgerStore] = None
_DEFAULT_LEDGER_LOCK = threading.Lock()


def get_default_ledger() -> LedgerStore:
    global _DEFAULT_LEDGER
    with _DEFAULT_LEDGER_LOCK:
        if _DEFAULT_LEDGER is None:
            _DEFAULT_LEDGER = LedgerStore()
        return _DEFAULT_LEDGER
