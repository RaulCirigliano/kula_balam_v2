"""
Módulo de Gestión de Inversores y Fondo de Inversión (Cuotapartes / NAV)
Implementa el estándar institucional de cuotapartes para reparto proporcional de utilidades
y pérdidas entre aportantes de capital, alineado con la cuenta del broker en Dólares (USD / Alpaca).

Moneda estándar de la cuenta y del broker: USD (Dólares estadounidenses).
Comisión de operador: Configurable (por defecto 0.0%).
Inversores fundacionales: Raul Cirigliano y Hernan Taiano.
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
DEFAULT_DB_PATH = os.getenv("TRADING_LEDGER_DB_PATH", os.path.join(PROJECT_ROOT, "trading_ledger.sqlite3"))

SCHEMA_INVESTORS = """
CREATE TABLE IF NOT EXISTS investors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    alias TEXT,
    email TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'PAUSED', 'CLOSED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS investor_txns (
    id TEXT PRIMARY KEY,
    investor_id TEXT NOT NULL REFERENCES investors(id) ON DELETE CASCADE,
    currency TEXT NOT NULL DEFAULT 'USD',
    txn_type TEXT NOT NULL CHECK (txn_type IN ('DEPOSIT', 'WITHDRAWAL')),
    amount REAL NOT NULL,
    nav_at_txn REAL NOT NULL,
    shares REAL NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS investor_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investor_expenses (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'GENERAL',
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    rate_to_usd REAL NOT NULL DEFAULT 1.0,
    amount_usd REAL NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class InvestorStore:
    """
    Gestor contable satélite para inversores con motor de cuotapartes (NAV) en USD (Alpaca).
    Mantiene total coherencia y conciliación con la Bóveda en Dólares del broker.
    """

    def __init__(self, db_path: Optional[str] = None):
        from backend.db.ledger import _get_db_lock
        self.db_path = db_path or os.getenv("TRADING_LEDGER_DB_PATH") or DEFAULT_DB_PATH
        self._lock = threading.RLock() if self.db_path == ":memory:" else _get_db_lock(self.db_path)
        self._memory_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row
            self._memory_conn.execute("PRAGMA foreign_keys = ON;")
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _initialize_database(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.executescript(SCHEMA_INVESTORS)
                    self._seed_default_config(conn)
                    self._seed_default_investors(conn)
                    self._auto_heal_initial_deposits(conn)
            finally:
                if self._memory_conn is None:
                    conn.close()

    def _auto_heal_initial_deposits(self, conn: sqlite3.Connection) -> None:
        """
        Corrige la distorsión donde depósitos iniciales se registraron con nav_at_txn > 1.0
        porque el saldo del broker ya contenía el dinero depositado antes de registrarlo.
        Garantiza que aportes iguales tengan exactamente 1 cuota nominal por dólar aportado (1:1).
        """
        rows = conn.execute(
            "SELECT id, amount, nav_at_txn, shares FROM investor_txns WHERE txn_type = 'DEPOSIT'"
        ).fetchall()
        if not rows:
            return
        for r in rows:
            amt = float(r["amount"])
            shs = float(r["shares"])
            nav = float(r["nav_at_txn"])
            # Si el depósito inicial se emitió a un NAV inflado artificialmente (> 1.0)
            if nav > 1.0001 and abs(shs - amt) > 1e-4:
                conn.execute(
                    "UPDATE investor_txns SET nav_at_txn = 1.0, shares = amount WHERE id = ?",
                    (r["id"],),
                )

    def _seed_default_config(self, conn: sqlite3.Connection) -> None:
        defaults = {
            "operator_fee_pct": "0.0",
            "display_currency": "USD",
            "usdt_ars_rate": "1250.0",
        }
        for k, v in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO investor_config (key, value) VALUES (?, ?)",
                (k, v),
            )

    def _seed_default_investors(self, conn: sqlite3.Connection, force: bool = False) -> None:
        if not force:
            already_seeded = conn.execute(
                "SELECT value FROM investor_config WHERE key = 'default_investors_seeded'"
            ).fetchone()
            if already_seeded:
                return
        default_investors = [
            ("inv-raul-cirigliano", "Raul Cirigliano", "Raúl", "raul@trading.local", "Inversor Principal / Titular"),
            ("inv-hernan-taiano", "Hernan Taiano", "Hernán", "hernan@trading.local", "Inversor Aportante"),
        ]
        for inv_id, name, alias, email, notes in default_investors:
            conn.execute(
                """
                INSERT OR IGNORE INTO investors (id, name, alias, email, notes, status)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE')
                """,
                (inv_id, name, alias, email, notes),
            )
        conn.execute(
            "INSERT OR REPLACE INTO investor_config (key, value) VALUES ('default_investors_seeded', '1')"
        )

    def get_config(self, key: str, default: str = "") -> str:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT value FROM investor_config WHERE key = ?", (key,)).fetchone()
                return str(row["value"]) if row else default
            finally:
                if self._memory_conn is None:
                    conn.close()

    def set_config(self, key: str, value: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO investor_config (key, value) VALUES (?, ?)",
                        (key, str(value)),
                    )
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_investors(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, name, alias, email, notes, status, created_at FROM investors ORDER BY created_at ASC"
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                if self._memory_conn is None:
                    conn.close()

    def create_investor(self, name: str, alias: Optional[str] = None, email: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        inv_id = f"inv-{uuid.uuid4().hex[:8]}"
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("El nombre del inversor no puede estar vacío.")

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO investors (id, name, alias, email, notes, status) VALUES (?, ?, ?, ?, ?, 'ACTIVE')",
                        (inv_id, clean_name, alias or clean_name, email or "", notes or ""),
                    )
                return {
                    "id": inv_id,
                    "name": clean_name,
                    "alias": alias or clean_name,
                    "email": email or "",
                    "notes": notes or "",
                    "status": "ACTIVE",
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def delete_investor(self, investor_id: str) -> Dict[str, Any]:
        """Elimina un inversor de la nómina y todas sus transacciones asociadas."""
        with self._lock:
            conn = self._connect()
            try:
                inv = conn.execute("SELECT id, name FROM investors WHERE id = ?", (investor_id,)).fetchone()
                if not inv:
                    raise ValueError(f"Inversor con ID '{investor_id}' no encontrado.")
                with conn:
                    conn.execute("DELETE FROM investor_txns WHERE investor_id = ?", (investor_id,))
                    conn.execute("DELETE FROM investors WHERE id = ?", (investor_id,))
                return {
                    "status": "DELETED",
                    "id": investor_id,
                    "name": inv["name"],
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_total_shares(self, currency: str = "USD") -> float:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COALESCE(SUM(shares), 0.0) AS total_shares FROM investor_txns WHERE currency = ?",
                    (currency,),
                ).fetchone()
                return float(row["total_shares"] or 0.0)
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_investor_shares(self, investor_id: str, currency: str = "USD") -> float:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COALESCE(SUM(shares), 0.0) AS shares FROM investor_txns WHERE investor_id = ? AND currency = ?",
                    (investor_id, currency),
                ).fetchone()
                return float(row["shares"] or 0.0)
            finally:
                if self._memory_conn is None:
                    conn.close()

    def record_deposit(
        self,
        investor_id: str,
        amount: float,
        current_vault_total: float = 0.0,
        currency: str = "USD",
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Registra un aporte de capital en el libro independiente de inversores (1:1 nominal, NAV = 1.0).
        No altera ni depende del saldo del broker.
        """
        deposit_amount = round(float(amount or 0.0), 2)
        if deposit_amount <= 0:
            raise ValueError("El monto del depósito debe ser mayor a cero.")

        with self._lock:
            conn = self._connect()
            try:
                inv = conn.execute("SELECT id, name FROM investors WHERE id = ?", (investor_id,)).fetchone()
                if not inv:
                    raise ValueError(f"Inversor con ID '{investor_id}' no encontrado.")

                total_shares_before = self.get_total_shares(currency)
                nav_at_txn = 1.0
                new_shares = deposit_amount
                txn_id = f"itx-{uuid.uuid4().hex[:12]}"

                with conn:
                    conn.execute(
                        """
                        INSERT INTO investor_txns (id, investor_id, currency, txn_type, amount, nav_at_txn, shares, notes)
                        VALUES (?, ?, ?, 'DEPOSIT', ?, ?, ?, ?)
                        """,
                        (txn_id, investor_id, currency, deposit_amount, nav_at_txn, new_shares, notes),
                    )

                return {
                    "txn_id": txn_id,
                    "investor_id": investor_id,
                    "investor_name": inv["name"],
                    "currency": currency,
                    "txn_type": "DEPOSIT",
                    "amount": deposit_amount,
                    "nav": nav_at_txn,
                    "shares_issued": new_shares,
                    "total_shares_after": total_shares_before + new_shares,
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def record_withdrawal(
        self,
        investor_id: str,
        amount: float,
        current_vault_total: float = 0.0,
        currency: str = "USD",
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Registra un retiro de capital del inversor.
        Permite retirar hasta el 100% de su dinero total descontando únicamente sus gastos prorrateados.
        Si retira el 100% de su disponible neto, liquida su posición a $0.00 y salda su cuota de gastos.
        """
        withdraw_amount = round(float(amount or 0.0), 2)
        if withdraw_amount <= 0:
            raise ValueError("El monto del retiro debe ser mayor a cero.")

        with self._lock:
            conn = self._connect()
            try:
                inv = conn.execute("SELECT id, name FROM investors WHERE id = ?", (investor_id,)).fetchone()
                if not inv:
                    raise ValueError(f"Inversor con ID '{investor_id}' no encontrado.")

                total_shares_before = self.get_total_shares(currency)
                investor_shares = round(max(0.0, self.get_investor_shares(investor_id, currency)), 2)
                if investor_shares <= 0 or total_shares_before <= 0:
                    raise ValueError("El inversor no tiene saldo disponible para retirar.")

                nav_at_txn = 1.0
                gross_bal = investor_shares
                total_expenses_usd = max(0.0, self.get_total_expenses_usd())
                allocated_exp = (
                    round(total_expenses_usd * (investor_shares / total_shares_before), 2)
                    if total_shares_before > 0
                    else 0.0
                )
                net_retirable = max(0.0, round(gross_bal - allocated_exp, 2))

                if withdraw_amount > (net_retirable + 1e-2):
                    raise ValueError(
                        f"Saldo retirable insuficiente. El inversor tiene un saldo actual de ${gross_bal:,.2f} {currency} "
                        f"menos ${allocated_exp:,.2f} USD en gastos operativos deducibles. "
                        f"Máximo retirable neto: ${net_retirable:,.2f} {currency}."
                    )

                # Si retira el total disponible neto (descontando gastos), su saldo queda en 0 y se salda su gasto
                is_full_withdrawal = abs(withdraw_amount - net_retirable) <= 0.02
                if is_full_withdrawal:
                    shares_to_burn = investor_shares
                else:
                    shares_to_burn = withdraw_amount

                txn_id = f"itx-{uuid.uuid4().hex[:12]}"
                with conn:
                    conn.execute(
                        """
                        INSERT INTO investor_txns (id, investor_id, currency, txn_type, amount, nav_at_txn, shares, notes)
                        VALUES (?, ?, ?, 'WITHDRAWAL', ?, ?, ?, ?)
                        """,
                        (txn_id, investor_id, currency, withdraw_amount, nav_at_txn, -shares_to_burn, notes),
                    )
                    if is_full_withdrawal and allocated_exp > 0:
                        exp_settle_id = f"exp-{uuid.uuid4().hex[:10]}"
                        conn.execute(
                            """
                            INSERT INTO investor_expenses (id, description, category, amount, currency, rate_to_usd, amount_usd, notes)
                            VALUES (?, ?, 'GENERAL', ?, 'USD', 1.0, ?, ?)
                            """,
                            (
                                exp_settle_id,
                                f"Gastos descontados en retiro total de {inv['name']}",
                                -allocated_exp,
                                -allocated_exp,
                                f"Liquidación automática de gastos al retirar ${withdraw_amount:,.2f} {currency}",
                            ),
                        )

                return {
                    "txn_id": txn_id,
                    "investor_id": investor_id,
                    "investor_name": inv["name"],
                    "currency": currency,
                    "txn_type": "WITHDRAWAL",
                    "amount": withdraw_amount,
                    "is_full_withdrawal": is_full_withdrawal,
                    "remaining_shares": max(0.0, round(investor_shares - shares_to_burn, 2)),
                    "settled_expenses_usd": allocated_exp if is_full_withdrawal else 0.0,
                    "expenses_deducted": allocated_exp if is_full_withdrawal else 0.0,
                    "nav": nav_at_txn,
                    "shares_burned": shares_to_burn,
                    "total_shares_after": max(0.0, total_shares_before - shares_to_burn),
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def add_expense(
        self,
        description: str,
        amount: float,
        currency: str = "USD",
        category: str = "GENERAL",
        rate_to_usd: Optional[float] = None,
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Registra un gasto operativo o general (IA, internet, APIs, VPS, etc.).
        Si se ingresa en ARS (o no USD), se convierte a USD según la tasa provista o la configurada en el sistema.
        """
        desc = str(description or "").strip()
        if not desc:
            raise ValueError("La descripción o concepto del gasto no puede estar vacía.")

        amt = float(amount or 0.0)
        if amt <= 0:
            raise ValueError("El monto del gasto debe ser mayor a cero.")

        curr = str(currency or "USD").upper().strip()
        cat = str(category or "GENERAL").upper().strip()

        # Determinar tasa de conversión a USD
        if curr in ("USD", "USDT"):
            rate = 1.0
            amt_usd = round(amt, 2)
        else:
            if rate_to_usd is not None and float(rate_to_usd) > 0:
                rate = float(rate_to_usd)
            else:
                rate = float(self.get_config("usdt_ars_rate", "1250.0"))
            amt_usd = round(amt / rate, 2)

        exp_id = f"exp-{uuid.uuid4().hex[:10]}"
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO investor_expenses (id, description, category, amount, currency, rate_to_usd, amount_usd, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (exp_id, desc, cat, amt, curr, rate, amt_usd, notes or ""),
                    )
                return {
                    "id": exp_id,
                    "description": desc,
                    "category": cat,
                    "amount": amt,
                    "currency": curr,
                    "rate_to_usd": rate,
                    "amount_usd": amt_usd,
                    "notes": notes or "",
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_expenses(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retorna la lista de gastos operativos registrados en orden cronológico inverso."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT id, description, category, amount, currency, rate_to_usd, amount_usd, notes, created_at
                    FROM investor_expenses
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                if self._memory_conn is None:
                    conn.close()

    def delete_expense(self, expense_id: str) -> bool:
        """Elimina un gasto operativo previamente registrado."""
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    res = conn.execute("DELETE FROM investor_expenses WHERE id = ?", (expense_id,))
                    return res.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_total_expenses_usd(self) -> float:
        """Retorna la suma total acumulada de gastos operativos en USD."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT COALESCE(SUM(amount_usd), 0.0) AS total FROM investor_expenses").fetchone()
                return round(float(row["total"]), 2) if row else 0.0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_fund_status(
        self,
        vault_total: float,
        currency: str = "USD",
        vault_balances: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Calcula el estado del fondo en la moneda nativa del broker (USD / Alpaca):
        - AUM total en USD (100% operativo en el broker, sin merma para el trading)
        - NAV actual por cuotaparte
        - Desglose por inversor: saldo en operación, gastos generales deducibles y saldo neto retirable
        - Auditoría de reconciliación contra la Bóveda real en USD.
        """
        operator_fee_pct = float(self.get_config("operator_fee_pct", "0.0"))

        with self._lock:
            conn = self._connect()
            try:
                investors_raw = conn.execute(
                    "SELECT id, name, alias, email, notes, status, created_at FROM investors WHERE status = 'ACTIVE' ORDER BY created_at ASC"
                ).fetchall()

                # Obtener movimientos por inversor en la divisa solicitada (USD)
                txns_rows = conn.execute(
                    """
                    SELECT investor_id, txn_type, amount, shares
                    FROM investor_txns
                    WHERE currency = ?
                    ORDER BY created_at ASC
                    """,
                    (currency,),
                ).fetchall()

                # Obtener gastos operativos registrados
                expenses_rows = conn.execute(
                    """
                    SELECT id, description, category, amount, currency, rate_to_usd, amount_usd, notes, created_at
                    FROM investor_expenses
                    ORDER BY created_at DESC
                    """
                ).fetchall()
                expenses_list = [dict(e) for e in expenses_rows]
                total_expenses_usd = round(sum(float(e["amount_usd"]) for e in expenses_list), 2)

                investor_stats: Dict[str, Dict[str, float]] = {
                    r["id"]: {
                        "total_deposited": 0.0,
                        "total_withdrawn": 0.0,
                        "net_deposited": 0.0,
                        "shares": 0.0,
                    }
                    for r in investors_raw
                }

                total_shares = 0.0
                total_deposited_fund = 0.0

                for tx in txns_rows:
                    iid = tx["investor_id"]
                    if iid not in investor_stats:
                        investor_stats[iid] = {
                            "total_deposited": 0.0,
                            "total_withdrawn": 0.0,
                            "net_deposited": 0.0,
                            "shares": 0.0,
                        }

                    amt = float(tx["amount"])
                    shs = float(tx["shares"])

                    if tx["txn_type"] == "DEPOSIT":
                        investor_stats[iid]["total_deposited"] += amt
                        investor_stats[iid]["net_deposited"] += amt
                        total_deposited_fund += amt
                    else:
                        investor_stats[iid]["total_withdrawn"] += amt
                        investor_stats[iid]["net_deposited"] -= amt
                        total_deposited_fund -= amt

                    investor_stats[iid]["shares"] += shs

                # Calcular total de participaciones activas aportadas (capital base de referencia)
                total_shares = sum(
                    max(0.0, investor_stats.get(r["id"], {}).get("shares", 0.0))
                    for r in investors_raw
                )

                # Si el fondo tiene capital en la Bóveda del broker y cuotapartistas con aportes:
                # El NAV y el saldo actual de cada inversor reflejan el patrimonio real proporcional
                clean_vault = max(0.0, round(float(vault_total), 2))
                has_vault_funds = clean_vault >= 0.01 and total_shares > 0
                nav = (clean_vault / total_shares) if has_vault_funds else 1.0

                # Generar reporte por inversor con distribución proporcional de ganancias y pérdidas
                investors_list = []
                total_investors_balance = 0.0

                for r in investors_raw:
                    iid = r["id"]
                    st = investor_stats.get(
                        iid,
                        {
                            "total_deposited": 0.0,
                            "total_withdrawn": 0.0,
                            "net_deposited": 0.0,
                            "shares": 0.0,
                        },
                    )
                    deposited = round(max(0.0, st["net_deposited"]), 2)
                    total_dep = round(st["total_deposited"], 2)
                    total_with = round(st["total_withdrawn"], 2)
                    shs = max(0.0, round(st["shares"], 2))
                    share_pct = round((shs / total_shares * 100.0), 2) if total_shares > 0 else 0.0

                    # Saldo actual = Cuotapartes * NAV (reparto proporcional exacto del dinero de la Bóveda)
                    if has_vault_funds:
                        current_balance = round(shs * nav, 2)
                    else:
                        current_balance = round(shs, 2)

                    # Prorrateo de gastos generales proporcional al saldo actual del inversor
                    allocated_expenses = (
                        round(total_expenses_usd * (shs / total_shares), 2)
                        if total_shares > 0
                        else 0.0
                    )
                    net_retirable_balance = max(0.0, round(current_balance - allocated_expenses, 2))
                    pnl_amount = round(current_balance - deposited, 2)
                    pnl_pct = round((pnl_amount / deposited * 100.0), 2) if deposited > 0 else 0.0
                    net_pnl_amount = round(net_retirable_balance - deposited, 2)
                    net_pnl_pct = round((net_pnl_amount / deposited * 100.0), 2) if deposited > 0 else 0.0

                    total_investors_balance += current_balance

                    investors_list.append({
                        "id": iid,
                        "name": r["name"],
                        "alias": r["alias"] or r["name"],
                        "shares": round(shs, 2),
                        "share_pct": share_pct,
                        "total_deposited": total_dep,
                        "total_withdrawn": total_with,
                        "net_deposited": deposited,
                        "current_balance": current_balance,
                        "allocated_expenses": allocated_expenses,
                        "net_retirable_balance": net_retirable_balance,
                        "net_pnl_amount": net_pnl_amount,
                        "net_pnl_pct": net_pnl_pct,
                        "pnl_amount": pnl_amount,
                        "pnl_pct": pnl_pct,
                        "status": r["status"],
                    })

                total_investors_balance = round(total_investors_balance, 2)
                recon_diff = round(clean_vault - total_investors_balance, 2)
                is_matched = abs(recon_diff) < 0.01

                if is_matched:
                    recon_status = "MATCH"
                elif recon_diff > 0:
                    recon_status = "PENDING_ASSIGNMENT"
                else:
                    recon_status = "EXCEEDED"

                total_net_distributable = max(0.0, round(total_investors_balance - total_expenses_usd, 2))

                return {
                    "currency": currency,
                    "currency_symbol": f"$ {currency}",
                    "total_aum": round(clean_vault, 2),
                    "total_shares": round(total_shares, 2),
                    "nav": round(nav, 4),
                    "total_deposited": round(max(0.0, total_deposited_fund), 2),
                    "total_investors_balance": round(total_investors_balance, 2),
                    "total_expenses_usd": total_expenses_usd,
                    "total_net_distributable": total_net_distributable,
                    "usdt_ars_rate": float(self.get_config("usdt_ars_rate", "1250.0")),
                    "operator_fee_pct": operator_fee_pct,
                    "reconciliation": {
                        "vault_total": round(clean_vault, 2),
                        "investors_total": round(total_investors_balance, 2),
                        "difference": recon_diff,
                        "status": recon_status,
                        "is_matched": is_matched,
                    },
                    "investors": investors_list,
                    "expenses": expenses_list,
                }
            finally:
                if self._memory_conn is None:
                    conn.close()

    def reset_and_rebalance_50_50(
        self,
        vault_total: float,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """
        Limpia todos los movimientos y gastos (deja todo en cero) y registra dos aportes
        exactos del 50% cada uno para Raul Cirigliano y Hernan Taiano, conciliando
        al 100% con el total de la Bóveda en USD (Alpaca) con NAV = 1.0000.
        """
        vault_clean = round(float(vault_total), 2)
        if vault_clean <= 0:
            vault_clean = 500.0

        half_1 = round(vault_clean / 2.0, 2)
        half_2 = round(vault_clean - half_1, 2)

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute("DELETE FROM investor_expenses WHERE currency = ?", (currency,))
                    conn.execute("DELETE FROM investor_txns WHERE currency = ?", (currency,))
                    self._seed_default_investors(conn, force=True)

                    tx1 = f"itx-{uuid.uuid4().hex[:12]}"
                    conn.execute(
                        """
                        INSERT INTO investor_txns (id, investor_id, currency, txn_type, amount, nav_at_txn, shares, notes)
                        VALUES (?, 'inv-raul-cirigliano', ?, 'DEPOSIT', ?, 1.0, ?, 'Aporte inicial 50% Bóveda')
                        """,
                        (tx1, currency, half_1, half_1),
                    )

                    tx2 = f"itx-{uuid.uuid4().hex[:12]}"
                    conn.execute(
                        """
                        INSERT INTO investor_txns (id, investor_id, currency, txn_type, amount, nav_at_txn, shares, notes)
                        VALUES (?, 'inv-hernan-taiano', ?, 'DEPOSIT', ?, 1.0, ?, 'Aporte inicial 50% Bóveda')
                        """,
                        (tx2, currency, half_2, half_2),
                    )
            finally:
                if self._memory_conn is None:
                    conn.close()

        return self.get_fund_status(vault_total=vault_clean, currency=currency)

    def set_investor_capital(
        self,
        investor_id: str,
        new_amount: float,
        vault_total: float,
        currency: str = "USDT",
    ) -> Dict[str, Any]:
        """
        Ajusta directamente el capital contable de un inversor en una divisa específica.
        El libro de inversores es 100% independiente del broker; solo se informa si hay diferencia.
        """
        amt = max(0.0, round(float(new_amount), 2))
        curr = currency.upper().strip()

        with self._lock:
            conn = self._connect()
            try:
                inv = conn.execute("SELECT id, name FROM investors WHERE id = ?", (investor_id,)).fetchone()
                if not inv:
                    raise ValueError(f"Inversor con ID '{investor_id}' no encontrado.")

                with conn:
                    # Limpiar transacciones previas de este inversor en esta divisa
                    conn.execute("DELETE FROM investor_txns WHERE investor_id = ? AND currency = ?", (investor_id, curr))
                    if amt > 0:
                        tx_id = f"itx-{uuid.uuid4().hex[:12]}"
                        conn.execute(
                            """
                            INSERT INTO investor_txns (id, investor_id, currency, txn_type, amount, nav_at_txn, shares, notes)
                            VALUES (?, ?, ?, 'DEPOSIT', ?, 1.0, ?, 'Ajuste manual de saldo contable')
                            """,
                            (tx_id, investor_id, curr, amt, amt),
                        )
            finally:
                if self._memory_conn is None:
                    conn.close()

        return self.get_fund_status(vault_total=vault_total, currency=curr)
