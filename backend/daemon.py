"""
Worker de Fondo Autónomo (Trader Daemon) para Trading Ollama.
Ejecuta el ciclo de análisis cuantitativo y gestión de órdenes de manera autónoma en el servidor Python,
independientemente de si el navegador web está abierto, minimizado o cerrado.
Conectado directamente a PaperBrokerAdapter y LedgerStore (SQLite).
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List

from backend.db.ledger import DEFAULT_DB_PATH, symbol_to_currency
from backend.execution.paper_broker import PaperBrokerAdapter
from backend.quant_analysis import ATR_TP_ATR_MULTIPLIER

logger = logging.getLogger("trader_daemon")

# Umbral (% bruto a favor) que arma el Breakeven. Fallback +0.40% para toda estrategia no listada.
# En estrategias Swing 4H / Promovidas del Lab se exige avance real (>= 1.40%) para no cerrar en céntimos por ruido.
BE_THRESHOLD_GROSS_DEFAULT: float = 0.40
SWING_4H_LAB_STRATEGIES = (
    "1_donchian_breakout_sol_4h",
    "squeeze_dual_eth_fondeo_strict_4h",
    "squeeze_dual_eth_4h_slot1",
    "squeeze_dual_eth_4h",
    "3_squeeze_dual_eth_oos_4h",
)
BE_THRESHOLD_GROSS_BY_STRATEGY: Dict[str, float] = {
    "donchian_breakout_1h": 1.00,
    "1_donchian_breakout_sol_4h": 1.40,
    "squeeze_dual_eth_fondeo_strict_4h": 1.40,
    "squeeze_dual_eth_4h_slot1": 1.40,
    "squeeze_dual_eth_4h": 1.40,
    "3_squeeze_dual_eth_oos_4h": 1.40,
}

# Lista Blanca Estricta Cuantitativa Donchian (4H / 1D):
# 7 activos y temporalidades validados empíricamente
DONCHIAN_CRYPTO_WHITELIST = ("SOL/USDT", "ETH/USDT")
DONCHIAN_TRADFI_WHITELIST = ("AAPL", "AMD", "AVGO", "META", "MSFT")
DONCHIAN_WHITELIST_TIMEFRAMES: Dict[str, str] = {
    "SOL/USDT": "4h",
    "ETH/USDT": "4h",
    "AAPL": "1d",
    "AMD": "1d",
    "AVGO": "1d",
    "META": "1d",
    "MSFT": "1d",
}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RADAR_FILE = os.path.join(PROJECT_ROOT, "buzon_radar.json")
CONTEXTO_MACRO_PATH = os.path.join(PROJECT_ROOT, "backend", "config", "contexto_macro.md")
DAEMON_STATE_DEFAULT_PATH = os.path.join(PROJECT_ROOT, "backend", "config", "daemon_state.json")


def _get_daemon_state_path() -> Optional[str]:
    """Devuelve ruta persistente de daemon_state.json (desactivada en pytest salvo override explícito)."""
    env_path = os.environ.get("DAEMON_STATE_PATH")
    if env_path:
        return env_path
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    return DAEMON_STATE_DEFAULT_PATH


class TraderDaemon:
    def __init__(self, broker: Optional[PaperBrokerAdapter] = None):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.is_running = False
        self.symbol = "SOL/USDT"
        self.timeframe = "4h"
        self.strategy = "donchian_breakout_1h"
        self.allowed_strategies: List[str] = ["kula_balam_cava_ruiz", "donchian_breakout_1h", "squeeze_dual_eth_4h_slot1"]
        self.strategy_lots: Dict[str, float] = {}
        self.strategy_risk_pcts: Dict[str, float] = {}
        self.slot_alloc_pct: Optional[float] = None
        self.engine = "antigravity_operador"
        self.model = "antigravity-tactical-v1"
        self.tp = 2.0   # objetivo BRUTO: 2.0x ATR con R:R neto >= 2.0
        self.sl = 1.0   # SL inicial: 1.0x ATR con piso 0.75%
        self.risk = 0.50
        self.fee = 0.1
        self.spread = 0.05
        self.min_profit_pct = 0.5
        self.mode = "smart"  # 'smart', 'auto', 'copilot'
        self.cycle_count = 0
        self.last_cycle_ts = 0.0
        self.started_at = 0.0
        self._last_watchdog_ts = 0.0
        self.last_signal = "INACTIVO"
        self.last_reason = "El agente de fondo no ha sido iniciado."
        self.last_error: Optional[str] = None
        self.last_injected_directive_ts: Optional[str] = None
        self.cooldown_until: float = 0.0
        self.cooldown_per_symbol: Dict[str, float] = {}
        self.max_positions: int = 2
        self.radar_candidate_symbol: Optional[str] = None
        self.last_active_symbol: Optional[str] = None
        self.macro: str = ""
        self.last_browser_activity_ts: float = 0.0
        self.last_browser_symbol: Optional[str] = None
        self.paused_new_entries: bool = False
        self.pause_reason: str = ""
        self.trailing_key_mode: str = "auto"  # 'auto', 'holgado', 'comprimido'
        self.counterfactual_cache: Dict[str, Dict[str, Any]] = {}
        self.time_decay_cache: Dict[str, Dict[str, Any]] = {}
        self.symbol_indicators: Dict[str, Dict[str, Any]] = {}
        self._evaluated_candles: Dict[tuple, Dict[str, Any]] = {}
        self._next_wakeup_ts: float = 0.0
        self.enable_futures_simulation: bool = False

        # Módulo de Scalping Presencial (Supervisión en vivo con Árbitro IA)
        self.scalping_active: bool = False
        self.scalping_draining: bool = False
        self.scalping_strategy: str = "scalping_vwap_2sigma_5m"
        self.scalping_timeframe: str = "5m"
        self.scalping_symbol: str = "ETH/USDT"
        self.scalping_start_ts: float = 0.0
        self.scalping_trades_opened: int = 0

        # Respaldo de configuración habitual para retorno automático post-scalping
        self.backup_strategy: str = "donchian_breakout_1h"
        self.backup_timeframe: str = "4h"
        self.backup_symbol: str = "SOL/USDT"
        self.backup_mode: str = "smart"

        self._lock = threading.RLock()

        # Adaptador del broker respaldado por SQLite
        self.broker = broker or PaperBrokerAdapter(
            db_path=os.getenv("TRADING_LEDGER_DB_PATH") or DEFAULT_DB_PATH
        )

    def is_stocks_evaluation_window(self, now_dt: Optional[Any] = None) -> bool:
        """
        Determina si estamos dentro de la ventana líquida regular de Wall Street apta para
        evaluar/ejecutar órdenes en acciones US 1D (Lunes a Viernes 09:45 a 15:30 America/New_York,
        fuera del blackout de apertura de 15 min y del blackout de pre-cierre de 30 min).
        Prohibido evaluar nuevas compras con mercado cerrado (AGENTS.md Reglas 1 y 2).
        """
        from datetime import datetime, timezone
        if now_dt is None:
            now_dt = datetime.now(timezone.utc)
        elif now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            ny = now_dt.astimezone(ZoneInfo("America/New_York"))
            if ny.weekday() >= 5:
                return False
            minutes = ny.hour * 60 + ny.minute
            return (9 * 60 + 45) <= minutes < (15 * 60 + 30)
        except Exception:
            is_weekday = now_dt.weekday() < 5
            minutes = now_dt.hour * 60 + now_dt.minute
            return is_weekday and (11 * 60 <= minutes < 16 * 60 + 30)

    def _arm_cooldown(self, symbol: Optional[str] = None) -> float:
        """
        Arma el enfriamiento post-trade de forma AISLADA por activo.
        Para Cripto 24/7 (activos con '/'): enfriamiento corto (60s o 1 vela) para permitir capturar
        inmediatamente oportunidades paralelas en otros pares líquidos (ETH, SOL) o retomar la tendencia.
        Para activos tradicionales bursátiles: 300s (5 min).
        """
        target_sym = symbol or self.symbol or "BTC/USDT"
        is_crypto = "/" in str(target_sym)
        if is_crypto:
            cooldown_s = 60.0  # 1 minuto ágil para criptoactivos 24/7
        else:
            tf_sec_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
            tf_sec = tf_sec_map.get(self.timeframe, 300)
            cooldown_s = float(max(300, min(900, 2 * tf_sec)))

        with self._lock:
            ts = time.time() + cooldown_s
            self.cooldown_per_symbol[target_sym] = ts
            # Solo actualizar el cooldown global si el símbolo coincide con el primario
            if not symbol or symbol == self.symbol:
                self.cooldown_until = ts
        return cooldown_s

    def notify_browser_activity(self, macro: str = "", symbol: Optional[str] = None) -> None:
        with self._lock:
            self.last_browser_activity_ts = time.time()
            if symbol:
                self.last_browser_symbol = str(symbol).strip().upper()
            if macro is not None:
                self.macro = macro

    def _persist_config(self) -> None:
        state_path = _get_daemon_state_path()
        if not state_path:
            return
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            payload = {
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "strategy": self.strategy,
                "allowed_strategies": list(self.allowed_strategies),
                "strategy_lots": dict(getattr(self, "strategy_lots", {})),
                "strategy_risk_pcts": dict(getattr(self, "strategy_risk_pcts", {})),
                "slot_alloc_pct": getattr(self, "slot_alloc_pct", None),
                "engine": self.engine,
                "model": self.model,
                "tp": self.tp,
                "sl": self.sl,
                "risk": self.risk,
                "fee": self.fee,
                "spread": self.spread,
                "min_profit_pct": self.min_profit_pct,
                "mode": self.mode,
                "max_positions": self.max_positions,
                "paused_new_entries": self.paused_new_entries,
                "pause_reason": self.pause_reason,
                "enable_futures_simulation": bool(getattr(self, "enable_futures_simulation", False)),
            }
            tmp_path = f"{state_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, state_path)
        except Exception as exc:
            logger.debug(f"Aviso persistiendo daemon_state.json: {exc}")

    def load_saved_config(self) -> Optional[Dict[str, Any]]:
        state_path = _get_daemon_state_path()
        if not state_path or not os.path.isfile(state_path):
            return None
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.debug(f"Aviso leyendo daemon_state.json: {exc}")
            return None

    def set_paused(self, paused: bool, reason: str = "") -> Dict[str, Any]:
        with self._lock:
            self.paused_new_entries = bool(paused)
            if self.paused_new_entries:
                self.pause_reason = reason.strip() or "Apertura de nuevas posiciones pausada por el operador."
                self.last_signal = "PAUSADO"
                self.last_reason = self.pause_reason
            else:
                self.pause_reason = ""
                self.last_signal = "REANUDADO"
                self.last_reason = reason.strip() or "Operativa autónoma reanudada por instrucción del operador."
            self._persist_config()
            return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            open_positions = self.broker.fetch_positions()
            enriched_positions = []
            for pos in open_positions:
                p_copy = dict(pos)
                sym = p_copy.get("symbol")
                cur_px = 0.0
                try:
                    from backend.main import get_price
                    px_data = get_price(sym)
                    cur_px = float(px_data.get("price", 0.0))
                except Exception:
                    pass
                if cur_px <= 0:
                    cur_px = float(p_copy.get("entry_price", 0.0))
                entry_px = float(p_copy.get("entry_price", 0.0))
                qty = float(p_copy.get("qty", 0.0))
                is_pos_short = str(p_copy.get("side") or "").upper() == "SHORT"
                if is_pos_short:
                    unrealized_pnl = (entry_px - cur_px) * qty if entry_px > 0 else 0.0
                    unrealized_pnl_pct = ((entry_px - cur_px) / entry_px) * 100.0 if entry_px > 0 else 0.0
                else:
                    unrealized_pnl = (cur_px - entry_px) * qty if entry_px > 0 else 0.0
                    unrealized_pnl_pct = ((cur_px - entry_px) / entry_px) * 100.0 if entry_px > 0 else 0.0

                cost_basis = float(p_copy.get("cost_basis") or (entry_px * qty))
                from backend.quant_risk import get_asset_friction_costs
                sym_friction = get_asset_friction_costs(sym)
                fee_rate = sym_friction["fee_pct"] / 100.0
                entry_fee = float(p_copy.get("total_fees") if p_copy.get("total_fees") is not None else (cost_basis * fee_rate))
                est_exit_fee = (qty * cur_px) * fee_rate
                net_unrealized_pnl = unrealized_pnl - entry_fee - est_exit_fee
                net_unrealized_pnl_pct = (net_unrealized_pnl / cost_basis * 100.0) if cost_basis > 0 else 0.0

                px_dec = 5 if ("=X" in str(sym or "").upper() or 0 < cur_px < 10.0) else 2
                p_copy["current_price"] = round(cur_px, px_dec)
                p_copy["unrealized_pnl"] = round(unrealized_pnl, 4)
                p_copy["unrealized_pnl_pct"] = round(unrealized_pnl_pct, 2)
                p_copy["net_unrealized_pnl"] = round(net_unrealized_pnl, 4)
                p_copy["net_unrealized_pnl_pct"] = round(net_unrealized_pnl_pct, 2)
                p_copy["time_decay"] = self.time_decay_cache.get(sym) or {
                    "symbol": sym,
                    "elapsed_hours": float(p_copy.get("time_decay_hours") or 0.0),
                    "status": p_copy.get("time_decay_status") or "NORMAL",
                    "suggestion": p_copy.get("time_decay_suggestion") or ""
                }
                enriched_positions.append(p_copy)

            cooldown_rem = max(0.0, round(self.cooldown_until - time.time(), 1))
            guardian_active = (self._thread is not None and self._thread.is_alive()) and len(open_positions) > 0
            cur_sym = self.last_active_symbol or self.symbol
            from backend.quant_risk import get_asset_friction_costs
            cur_friction = get_asset_friction_costs(cur_sym)
            slots_by_book = {}
            for book_ccy, probe_sym in (("USDT", "ETH/USDT"), ("USD", "AAPL"), ("ARS", "GGAL.BA")):
                st_b = self._compute_book_slot_limits(open_positions, probe_sym, self.strategy)
                slots_by_book[book_ccy] = {
                    "open": len(st_b["book_positions"]),
                    "allowed": st_b["allowed_book_slots"],
                    "free": st_b["book_free"],
                    "in_drop": st_b["in_drop"],
                }
            cur_book_limits = self._compute_book_slot_limits(open_positions, cur_sym, self.strategy)
            return {
                "is_running": self.is_running,
                "paused": self.paused_new_entries,
                "pause_reason": self.pause_reason,
                "guardian_active": guardian_active,
                "symbol": self.symbol,
                "active_symbol": cur_sym,
                "timeframe": self.timeframe,
                "strategy": self.strategy,
                "allowed_strategies": list(self.allowed_strategies),
                "strategy_lots": dict(getattr(self, "strategy_lots", {})),
                "strategy_risk_pcts": dict(getattr(self, "strategy_risk_pcts", {})),
                "slot_alloc_pct": getattr(self, "slot_alloc_pct", None),
                "engine": self.engine,
                "model": self.model,
                "tp": self.tp,
                "sl": self.sl,
                "risk": self.risk,
                "max_positions": self.max_positions,
                "effective_max_positions": (2 if getattr(self, "scalping_active", False) else cur_book_limits["allowed_book_slots"]),
                "slots_by_book": slots_by_book,
                "cupo_dual_btc_activo": getattr(self, "scalping_active", False),
                "is_drop_regime": cur_book_limits["in_drop"],
                "drop_regime_reason": cur_book_limits["drop_reason"],
                "radar_candidate": self.radar_candidate_symbol,
                "fee": cur_friction["fee_pct"],
                "spread": cur_friction["spread_pct"],
                "min_profit_pct": self.min_profit_pct,
                "mode": self.mode,
                "cycle_count": self.cycle_count,
                "last_cycle_ts": self.last_cycle_ts,
                "last_signal": self.last_signal,
                "last_reason": self.last_reason,
                "last_error": self.last_error,
                "cooldown_remaining_s": cooldown_rem,
                "open_positions_count": len(enriched_positions),
                "open_positions": enriched_positions,
                "trailing_telemetry": getattr(self, "counterfactual_cache", {}),
                "time_decay_telemetry": getattr(self, "time_decay_cache", {}),
                "scalping": self.get_scalping_status(),
                "next_wakeup_in_s": max(0.0, round(self._next_wakeup_ts - time.time(), 1)) if self._next_wakeup_ts > 0 else None,
                "evaluated_candles_count": len(self._evaluated_candles),
                "enable_futures_simulation": bool(getattr(self, "enable_futures_simulation", False)),
            }

    def ensure_guardian_running(self) -> bool:
        """Garantiza que el hilo guardián esté corriendo en segundo plano si hay posiciones abiertas."""
        with self._lock:
            if self.broker.fetch_positions():
                if self._thread is None or not self._thread.is_alive():
                    self._stop_event.clear()
                    self._thread = threading.Thread(target=self._run_loop, name="TraderDaemonThread", daemon=True)
                    self._thread.start()
                    logger.info("🛡️ [GUARDIÁN SL/TP] Hilo guardián iniciado para vigilar posiciones abiertas en segundo plano.")
                    return True
        return False

    def get_health_snapshot(self) -> Dict[str, Any]:
        """Lectura rápida y no bloqueante de salud interna del daemon (sin I/O de red)."""
        with self._lock:
            open_cnt = len(self.broker.fetch_positions())
            thread_alive = self._thread is not None and self._thread.is_alive()
            guardian_active = thread_alive and open_cnt > 0
            cooldown_rem = max(0.0, round(self.cooldown_until - time.time(), 1))
            return {
                "is_running": self.is_running,
                "paused": self.paused_new_entries,
                "guardian_active": guardian_active,
                "thread_alive": thread_alive,
                "open_positions_count": open_cnt,
                "cycle_count": self.cycle_count,
                "last_cycle_ts": self.last_cycle_ts,
                "started_at": self.started_at,
                "last_signal": self.last_signal,
                "last_error": self.last_error,
                "cooldown_remaining_s": cooldown_rem,
                "strategy": self.strategy,
                "allowed_strategies": list(self.allowed_strategies),
                "slot_alloc_pct": getattr(self, "slot_alloc_pct", None),
            }

    def start(
        self,
        symbol: str = "SOL/USDT",
        timeframe: str = "4h",
        strategy: str = "donchian_breakout_1h",
        allowed_strategies: Optional[List[str]] = None,
        strategy_lots: Optional[Dict[str, float]] = None,
        strategy_risk_pcts: Optional[Dict[str, float]] = None,
        slot_alloc_pct: Optional[float] = None,
        engine: str = "antigravity_operador",
        model: Optional[str] = "antigravity-tactical-v1",
        tp: float = 2.0,
        sl: float = 1.0,
        risk: float = 0.50,
        fee: float = 0.1,
        spread: float = 0.05,
        min_profit_pct: float = 0.5,
        mode: str = "smart",
        max_positions: int = 2,
        enable_futures_simulation: Optional[bool] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            self.symbol = symbol
            self.timeframe = timeframe
            self.strategy = strategy
            if allowed_strategies is not None:
                self.allowed_strategies = list(allowed_strategies)
            elif strategy != "auto":
                self.allowed_strategies = [strategy]
            else:
                self.allowed_strategies = ["kula_balam_cava_ruiz", "donchian_breakout_1h", "squeeze_dual_eth_4h_slot1"]
            if slot_alloc_pct is not None:
                self.slot_alloc_pct = min(100.0, max(10.0, float(slot_alloc_pct)))
                if strategy_lots is None:
                    self.strategy_lots = {}
                if strategy_risk_pcts is None:
                    self.strategy_risk_pcts = {}
            if strategy_lots is not None:
                self.strategy_lots = {str(k): float(v) for k, v in strategy_lots.items() if float(v) > 0}
            if strategy_risk_pcts is not None:
                self.strategy_risk_pcts = {
                    str(k): min(5.0, max(0.1, float(v)))
                    for k, v in strategy_risk_pcts.items()
                    if float(v) > 0
                }
            self.engine = engine
            self.model = model or "trader-qwen"
            self.tp = tp
            self.sl = sl
            self.risk = risk
            self.fee = fee
            self.spread = spread
            self.min_profit_pct = min_profit_pct
            self.mode = mode
            self.max_positions = max(1, int(max_positions))
            if enable_futures_simulation is not None:
                self.enable_futures_simulation = bool(enable_futures_simulation)
            self._evaluated_candles.clear()
            self._persist_config()

            if self.is_running:
                return {"status": "already_running", "message": "El agente ya está en ejecución.", "config": self.get_status()}

            self.is_running = True
            self.started_at = time.time()
            self.last_signal = "INICIANDO"
            self.last_reason = "Agente de fondo iniciando ciclo autónomo en servidor."
            self.last_error = None
            self._stop_event.clear()

            self._thread = threading.Thread(target=self._run_loop, name="TraderDaemonThread", daemon=True)
            self._thread.start()

            logger.info(f"TraderDaemon iniciado: {self.symbol} [{self.timeframe}] vía {self.engine}/{self.model}")
            return {"status": "started", "config": self.get_status()}

    def stop(self, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            if not self.is_running and (self._thread is None or not self._thread.is_alive()):
                return {"status": "not_running", "message": "El agente no está en ejecución."}

            self.is_running = False
            open_pos = self.broker.fetch_positions()
            if force or not open_pos:
                self._stop_event.set()
                self.last_signal = "DETENIDO"
                self.last_reason = "El agente fue detenido por el usuario o por el sistema."
                guardian_active = False
            else:
                self.last_signal = "DETENIDO_GUARDIAN_ACTIVO"
                self.last_reason = f"Agente detenido para nuevas compras. Guardián de fondo vigilando Stop Loss / Take Profit de {len(open_pos)} posición(es) abierta(s)."
                guardian_active = True

        if force and self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.2)
            self._thread = None
        logger.info(f"TraderDaemon detenido. Guardian activo: {guardian_active}")
        return {"status": "stopped", "message": self.last_reason, "guardian_active": guardian_active}

    def start_scalping(
        self,
        symbol: str = "ETH/USDT",
        strategy: str = "scalping_vwap_2sigma_5m",
        timeframe: str = "5m",
        lot_size: float = 0.01,
    ) -> Dict[str, Any]:
        """Inicia una sesión de scalping presencial supervisada."""
        with self._lock:
            # Respaldar la configuración previa si no estábamos ya en scalping
            if not self.scalping_active and not self.scalping_draining:
                self.backup_strategy = self.strategy
                self.backup_timeframe = self.timeframe
                self.backup_symbol = self.symbol
                self.backup_mode = self.mode

            self.scalping_active = True
            self.scalping_draining = False
            self.scalping_strategy = strategy
            self.scalping_timeframe = timeframe
            self.scalping_symbol = symbol
            self.scalping_lot_size = float(lot_size)
            self.scalping_start_ts = time.time()
            self.scalping_trades_opened = 0

            # Conmutar parámetros del daemon en caliente
            self.symbol = symbol
            self.timeframe = timeframe
            self.strategy = strategy
            self.allowed_strategies = [strategy]
            self.mode = "fixed"

            # Asegurar que el hilo del daemon esté en ejecución
            if not self.is_running:
                self.is_running = True
                self._stop_event.clear()
                if self._thread is None or not self._thread.is_alive():
                    self._thread = threading.Thread(target=self._run_loop, name="TraderDaemonThread", daemon=True)
                    self._thread.start()

            self.last_signal = "SCALPING_PRESENCIAL_ACTIVO"
            self.last_reason = f"Sesión presencial de scalping iniciada en {symbol} [{timeframe}] con estrategia {strategy}."
            logger.info(f"⚡ [SCALPING PRESENCIAL] Iniciado: {symbol} [{timeframe}] - {strategy}. Config habitual respaldada: {self.backup_strategy} [{self.backup_timeframe}].")
            return self.get_scalping_status()

    def stop_scalping(self) -> Dict[str, Any]:
        """Pone fin a la sesión presencial activando el modo Drenado Elegante."""
        with self._lock:
            if not self.scalping_active and not self.scalping_draining:
                return {
                    "status": "not_active",
                    "message": "No hay sesión presencial de scalping activa.",
                    "config": self.get_scalping_status()
                }

            self.scalping_active = False
            self.scalping_draining = True

            # Verificar si quedan posiciones abiertas de scalping
            open_positions = self.broker.fetch_positions() if hasattr(self, "broker") else []
            open_scalp = [
                p for p in open_positions
                if p.get("strategy") == self.scalping_strategy or p.get("symbol") == self.scalping_symbol
            ]

            if not open_scalp:
                # Sin trades pendientes: retorno inmediato al modo habitual
                self._restore_backup_strategy("Sin trades abiertos de scalping al pulsar finalizar.")
                return {
                    "status": "restored",
                    "message": "Sesión finalizada. Sin trades pendientes; restaurado a modo automático de fondo.",
                    "config": self.get_scalping_status()
                }
            else:
                self.last_signal = "SCALPING_DRENANDO"
                self.last_reason = f"Sesión presencial finalizada. Drenando {len(open_scalp)} trade(s) activo(s). Nuevas órdenes bloqueadas."
                logger.info(f"⏳ [SCALPING DRENADO] Modo drenado activado para {len(open_scalp)} trade(s) de scalping. Nuevas compras bloqueadas.")
                return {
                    "status": "draining",
                    "open_positions": len(open_scalp),
                    "message": f"Drenando {len(open_scalp)} posición(es) de scalping activas. Retornará automáticamente al modo de fondo al cerrarse.",
                    "config": self.get_scalping_status()
                }

    def _restore_backup_strategy(self, reason: str = "") -> None:
        """Restaura la configuración previa tras completar el drenado de scalping."""
        self.scalping_active = False
        self.scalping_draining = False
        self.strategy = self.backup_strategy or "donchian_breakout_1h"
        self.timeframe = self.backup_timeframe or "4h"
        self.symbol = self.backup_symbol or "SOL/USDT"
        self.mode = self.backup_mode or "smart"
        self.allowed_strategies = [self.strategy]
        self.last_signal = "MODO_HABITUAL_RESTAURADO"
        self.last_reason = f"Retorno automático a modo de fondo: {self.strategy} [{self.timeframe}] ({reason})"
        logger.info(f"🔄 [RETORNO AUTOMÁTICO] {self.last_reason}")

    def get_scalping_status(self) -> Dict[str, Any]:
        """Retorna el estado en vivo de la sesión presencial de scalping."""
        open_positions = self.broker.fetch_positions() if hasattr(self, "broker") else []
        open_scalp = [
            p for p in open_positions
            if p.get("strategy") == getattr(self, "scalping_strategy", "") or p.get("symbol") == getattr(self, "scalping_symbol", "")
        ]
        elapsed_s = max(0.0, time.time() - getattr(self, "scalping_start_ts", 0.0)) if getattr(self, "scalping_start_ts", 0.0) > 0 else 0.0
        return {
            "active": getattr(self, "scalping_active", False),
            "draining": getattr(self, "scalping_draining", False),
            "symbol": getattr(self, "scalping_symbol", "ETH/USDT"),
            "strategy": getattr(self, "scalping_strategy", "scalping_vwap_2sigma_5m"),
            "timeframe": getattr(self, "scalping_timeframe", "5m"),
            "lot_size": getattr(self, "scalping_lot_size", 0.01),
            "elapsed_minutes": round(elapsed_s / 60.0, 1),
            "open_scalp_positions": len(open_scalp),
            "backup_strategy": getattr(self, "backup_strategy", "donchian_breakout_1h"),
            "backup_timeframe": getattr(self, "backup_timeframe", "4h"),
            "backup_symbol": getattr(self, "backup_symbol", "SOL/USDT"),
        }

    def _log_trade_csv(self, symbol: str, signal: str, price: float, qty: float, status: str, mode: str) -> None:
        """Mantiene sincronizado historial_trades.csv con las operaciones de SQLite."""
        try:
            import csv
            from datetime import datetime

            csv_path = os.getenv("TRADING_OLLAMA_CSV_PATH") or os.path.join(PROJECT_ROOT, "historial_trades.csv")
            now = datetime.now()
            time_str = now.strftime("%H:%M:%S")
            file_exists = os.path.isfile(csv_path)
            with open(csv_path, mode="a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                if not file_exists:
                    writer.writerow(["Time", "Symbol", "Signal", "Price", "Qty", "Fee", "Status", "Mode", "SessionId"])
                writer.writerow([time_str, symbol, signal, price, qty, 0.0, status, mode, 1])
        except Exception as e:
            logger.debug(f"Aviso guardando trade en CSV desde daemon: {e}")

    def _write_contexto_macro_file(
        self,
        active_symbol: str,
        cur_price: float,
        res: Dict[str, Any],
        effective_timeframe: Optional[str] = None,
    ) -> None:
        """Escribe contexto_macro.md en vivo como fuente única de verdad para el Cerebro IA."""
        try:
            from datetime import datetime, timezone, timedelta
            arg_tz = timezone(timedelta(hours=-3))
            now_art = datetime.now(arg_tz).strftime("%Y-%m-%d %H:%M:%S ART")

            ind = res.get("indicators") or {}
            metrics = res.get("strategy_metrics") or {}
            fee_info = res.get("fee_info") or {}

            z_score = ind.get("z_score")
            rsi = ind.get("rsi")
            sma20 = ind.get("sma_20")
            sma50 = ind.get("sma_50")
            ema200 = ind.get("ema_200")
            slope = ind.get("ema_200_slope_pct")

            tp_net = fee_info.get("net_tp") or metrics.get("tp_net_pct")
            sl_net = metrics.get("sl_net_pct")
            net_rr = fee_info.get("net_rr")

            strat = res.get("strategy") or self.strategy
            sig = res.get("signal") or "MANTENER"
            reason = res.get("reason") or ""
            tf_display = effective_timeframe or self.timeframe
            px_dec = 5 if ("=X" in str(active_symbol or "").upper() or 0 < cur_price < 10.0) else 2

            z_txt = f"{z_score:.2f}" if z_score is not None else "N/A"
            rsi_txt = f"{rsi:.1f}" if rsi is not None else "N/A"
            sma20_txt = f"${sma20:.{px_dec}f}" if sma20 is not None else "N/A"
            sma50_txt = f"${sma50:.{px_dec}f}" if sma50 is not None else "N/A"
            ema200_txt = f"${ema200:.{px_dec}f}" if ema200 is not None else "N/A"
            slope_txt = f"{slope:.4f}%" if slope is not None else "N/A"
            tp_txt = f"+{tp_net:.2f}%" if tp_net is not None else "N/A"
            sl_txt = f"{sl_net:.2f}%" if sl_net is not None else "N/A"
            rr_txt = f"{net_rr:.2f}" if net_rr is not None else "N/A"

            content = (
                f"# Contexto Macro en Vivo — Fuente Única de Verdad\n"
                f"*Actualizado automáticamente en cada ciclo de análisis*\n\n"
                f"## 1. Reloj y Sesión de Mercado\n"
                f"- **Hora Local:** {now_art}\n"
                f"- **Activo Analizado:** {active_symbol}\n"
                f"- **Precio Actual:** ${cur_price:.{px_dec}f}\n"
                f"- **Temporalidad:** {tf_display}\n\n"
                f"## 2. Variables Duras e Indicadores\n"
                f"- **Z-Score (Desviación):** {z_txt}\n"
                f"- **RSI (14):** {rsi_txt}\n"
                f"- **SMA 20:** {sma20_txt}\n"
                f"- **SMA 50:** {sma50_txt}\n"
                f"- **EMA 200:** {ema200_txt} (Pendiente: {slope_txt})\n\n"
                f"## 3. Asimetría Matemática y Riesgo (Filtro Determinista)\n"
                f"- **Estrategia Evaluada:** {strat}\n"
                f"- **Take Profit Neto Proyectado:** {tp_txt}\n"
                f"- **Stop Loss Neto:** {sl_txt}\n"
                f"- **Ratio R:R Neto:** {rr_txt} (Mínimo exigido: >= 1.0)\n"
                f"- **Veredicto Técnico:** {sig}\n"
                f"- **Fundamento Técnico:** {reason}\n"
            )
            os.makedirs(os.path.dirname(CONTEXTO_MACRO_PATH), exist_ok=True)
            with open(CONTEXTO_MACRO_PATH, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.debug(f"Aviso actualizando contexto_macro.md: {e}")

    def is_drop_regime_or_tactical_rebound(self, active_symbol: str = "", strategy: str = "") -> Tuple[bool, str]:
        """
        Medida Inmediata 3:
        Determina si el sistema se encuentra en régimen de caídas o buscando un rebote táctico,
        donde la exposición se limita estrictamente a 1 sola posición simultánea.
        Para activos bursátiles tradicionales (SPY, AAPL, CEDEARs, Forex), el macro de Bitcoin no aplica.
        """
        strat = strategy or self.strategy
        if strat in ("mean_reversion_atr", "02_cazador_rebotes_atr_15m"):
            return True, f"Estrategia de rebote táctico ({strat})"

        target_sym = active_symbol or self.symbol or "BTC/USDT"
        from backend.entry_gate import _is_crypto
        if not _is_crypto(target_sym):
            return False, ""

        try:
            from backend.entry_gate import get_btc_macro_status
            btc_stat = get_btc_macro_status()
            if btc_stat.get("veto_active"):
                return True, f"Régimen macro de caídas: {btc_stat.get('reason')}"
        except Exception:
            pass

        return False, ""

    def _compute_book_slot_limits(
        self,
        open_positions: List[Dict[str, Any]],
        target_symbol: str,
        strategy: str = "",
    ) -> Dict[str, Any]:
        """
        Calcula límites y cupos libres aislados por Bóveda/Moneda (USDT, USD, ARS).
        En régimen de caídas de BTC, el tope estricto de 1 posición (o 2 en Cupo Dual
        BTC + Activo Táctico) aplica únicamente al libro cripto USDT sin bloquear USD/ARS.
        """
        from backend.entry_gate import is_btc
        from backend.quant_risk import is_micro_futures_symbol

        book_currency = "SIM_FUTURES" if is_micro_futures_symbol(target_symbol) else symbol_to_currency(target_symbol)
        book_positions = [
            p for p in open_positions
            if ("SIM_FUTURES" if is_micro_futures_symbol(str(p.get("symbol", ""))) else symbol_to_currency(str(p.get("symbol", "")))) == book_currency
        ]
        in_drop, drop_reason = self.is_drop_regime_or_tactical_rebound(target_symbol, strategy or self.strategy)

        has_btc_open = any(is_btc(p.get("symbol", "")) for p in book_positions)
        has_alt_open = any(not is_btc(p.get("symbol", "")) for p in book_positions)
        is_current_btc = is_btc(target_symbol)
        dual_slot_pair = (book_currency == "USDT") and (
            (has_btc_open and not is_current_btc) or (has_alt_open and is_current_btc)
        )

        if self.max_positions <= 1:
            allowed_book_slots = 1
        elif in_drop:
            allowed_book_slots = (
                2
                if (
                    (getattr(self, "scalping_active", False) and book_currency == "USDT")
                    or dual_slot_pair
                    or len(book_positions) == 0
                )
                else 1
            )
        else:
            allowed_book_slots = self.max_positions

        global_free = max(0, self.max_positions - len(open_positions))
        book_free = min(global_free, max(0, allowed_book_slots - len(book_positions)))
        return {
            "currency": book_currency,
            "book_positions": book_positions,
            "in_drop": in_drop,
            "drop_reason": drop_reason,
            "has_btc_open": has_btc_open,
            "has_alt_open": has_alt_open,
            "dual_slot_pair": dual_slot_pair,
            "allowed_book_slots": allowed_book_slots,
            "global_free": global_free,
            "book_free": book_free,
        }

    def _check_radar_for_autorouting(self) -> None:
        """Si estamos en modo smart con auto-orquestador, revisa el buzón de radar e identifica candidatos sin bloquear si hay cupos libres en su bóveda."""
        if self.mode != "smart" or self.strategy != "auto":
            return
        radar_path = os.environ.get("BUZON_RADAR_PATH") or RADAR_FILE
        if not os.path.isfile(radar_path):
            return
        open_positions = self.broker.fetch_positions()
        if len(open_positions) >= self.max_positions:
            return
        try:
            import math
            from backend.radar_inbox import RadarInbox
            from backend.entry_gate import RADAR_TTL_HOURS
            from backend.main import SUPPORTED_SYMBOLS
            from backend.estrategias.registry import is_asset_market_open
            from backend.macro_bias_buffer import MacroBiasBuffer

            cards = RadarInbox(file_path=radar_path).get_active_cards(hours_ttl=max(1, int(math.ceil(RADAR_TTL_HOURS))))
            if not cards:
                return

            bias_buf = MacroBiasBuffer()
            for card in reversed(cards):
                alert_ts = getattr(card, "timestamp", None)
                if not alert_ts or alert_ts == self.last_injected_directive_ts:
                    break
                titular_l = str(getattr(card, "titular", "") or "").lower()
                if ".py" in titular_l and "test" in titular_l:
                    continue
                confidence = float(getattr(card, "confianza", 0) or 0)
                impacto = str(getattr(card, "impacto", "") or "").upper()
                if confidence < 75 or impacto not in {"POSITIVO", "OPORTUNIDAD"}:
                    continue

                asset = str(getattr(card, "activo", "") or "").strip().upper()
                target_sym = None
                if asset in SUPPORTED_SYMBOLS:
                    target_sym = asset
                elif f"{asset}/USDT" in SUPPORTED_SYMBOLS:
                    target_sym = f"{asset}/USDT"
                elif asset.replace("-USD", "/USDT") in SUPPORTED_SYMBOLS:
                    target_sym = asset.replace("-USD", "/USDT")

                if not target_sym:
                    continue
                if self._compute_book_slot_limits(open_positions, target_sym)["book_free"] <= 0:
                    continue
                active_bias = bias_buf.get_bias(target_sym)
                if active_bias and str(active_bias.get("bias", "")).upper() in {"NEGATIVO", "PELIGRO", "VETO"}:
                    continue
                if any(p.get("symbol") == target_sym for p in open_positions):
                    continue

                if not is_asset_market_open(target_sym):
                    logger.info(
                        f"TraderDaemon [MULTI-SLOT]: Directiva de {target_sym} en espera (mercado cerrado por horario). Manteniendo monitoreo."
                    )
                else:
                    logger.info(
                        f"TraderDaemon [MULTI-SLOT]: Directiva radar aceptada para {target_sym} (confianza {confidence}%). Asignado a slot de evaluación."
                    )
                    self.radar_candidate_symbol = target_sym
                    if len(open_positions) == 0:
                        self.symbol = target_sym
                self.last_injected_directive_ts = alert_ts
                break
        except Exception as e:
            logger.debug(f"Error comprobando radar en daemon: {e}")

    def _check_open_positions_protections(self, open_positions: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Evalúa de forma exhaustiva Stop Loss y Take Profit para TODAS las posiciones abiertas en el Ledger.
        Garantiza que ninguna posición abierta quede sin vigilancia independientemente del símbolo activo.
        """
        from backend.main import get_price
        from backend.estrategias.registry import is_asset_market_open

        if open_positions is None:
            open_positions = self.broker.fetch_positions()

        active_syms = {p.get("symbol") for p in open_positions if p.get("symbol")}
        for stale_sym in list(self.counterfactual_cache.keys()):
            if stale_sym not in active_syms:
                self.counterfactual_cache.pop(stale_sym, None)
        for stale_sym in list(self.time_decay_cache.keys()):
            if stale_sym not in active_syms:
                self.time_decay_cache.pop(stale_sym, None)

        liquidated = []
        for pos in list(open_positions):
            sym = pos.get("symbol", "")
            if not sym or not is_asset_market_open(sym):
                continue

            entry_price = float(pos.get("entry_price", 0.0))
            if entry_price <= 0:
                continue

            cur_price = entry_price
            try:
                px_info = get_price(sym)
                cur_price = float(px_info.get("price", entry_price))
            except Exception as px_err:
                logger.debug(f"Precio usando fallback para {sym}: {px_err}")
                continue

            if cur_price <= 0:
                continue

            # Verificación de Timbre de Salida Pre-Cierre (Auto-Flatten preventivo 15 min antes de campana)
            from backend.entry_gate import should_auto_flatten_intraday
            if should_auto_flatten_intraday(sym):
                logger.info(
                    f"🔔 [TIMBRE DE SALIDA] Liquidación automática preventiva de {sym} en ${cur_price} "
                    f"a 15 min del cierre de rueda para eliminar riesgo de Gap Overnight."
                )
                try:
                    res = self.broker.flatten(sym, current_price=cur_price, exit_reason="Timbre de Salida Pre-Cierre")
                except ValueError:
                    continue
                try:
                    from backend.telegram_notifier import notify_trade_closed
                    net_pnl = float((res or {}).get("net_pnl") or 0.0)
                    op_bal = (res or {}).get("operational_balance")
                    v_bal = (res or {}).get("vault_balance")
                    notify_trade_closed(
                        symbol=sym,
                        side=str(pos.get("side") or "LONG").upper(),
                        entry_price=entry_price,
                        exit_price=cur_price,
                        pnl=net_pnl,
                        fees=float(pos.get("total_fees") or 0.0),
                        exit_reason="Timbre de Salida Pre-Cierre",
                        strategy=pos.get("strategy") or self.strategy,
                        cost_basis=float(pos.get("cost_basis") or (entry_price * float(pos.get("qty", 0.0)))),
                        operational_balance=float(op_bal) if op_bal is not None else float(self.broker.balances.get("USDT", 0.0)),
                        vault_balance=float(v_bal) if v_bal is not None else float(self.broker.vault_balances.get("USDT", 0.0)),
                    )
                except Exception as _e_tg_close:
                    logger.warning(f"Error al enviar notificación Telegram de cierre: {_e_tg_close}")
                self._log_trade_csv(sym, "VENDER", cur_price, float(pos.get("qty", 0)), "Ejecutada", "Timbre de Salida Pre-Cierre")
                with self._lock:
                    self.cycle_count += 1
                    self.last_cycle_ts = time.time()
                    self.last_signal = "AUTO_FLATTEN_PRE_CLOSE"
                    self.last_reason = f"Liquidación preventiva pre-campana (16:45 hs) en ${cur_price} ({sym}). Cero riesgo overnight."
                liquidated.append({"symbol": sym, "action": "AUTO_FLATTEN", "price": cur_price, "result": res})
                continue

            sl_pct = float(pos.get("initial_sl_pct") or self.sl)
            raw_tp = pos.get("initial_tp_pct")
            tp_pct = float(raw_tp) if (raw_tp is not None and str(raw_tp).strip() != "") else float(self.tp)
            trade_id = pos.get("id")
            pos_strategy = str(pos.get("strategy") or self.strategy)
            is_pos_short = str(pos.get("side") or "").upper() == "SHORT"
            # Solo en ejecución aislada donchian_breakout_1h se mantiene TP fijo (compatibilidad unit test);
            # en Cerebro Kula Autónomo ("auto"), Donchian y todas las estrategias tácticas/promovidas corren SIN TECHO con Stop Móvil.
            is_donchian = (self.strategy == "donchian_breakout_1h" and pos_strategy == "donchian_breakout_1h")
            FIXED_TP_ONLY_STRATEGIES = ("manual", "nasdaq_araujo_vwap", "mean_reversion_atr", "hyenuk_chu_multibagger")
            is_trailing_runner = (
                self.strategy in ("trailing_trend_runner", "trailing_short_runner", "kula_balam_cava_ruiz", "alex_ruiz_triada_3velas", "triple_confluencia_4h")
                or (self.strategy == "auto" and pos_strategy not in FIXED_TP_ONLY_STRATEGIES)
            )

            # 1. Calcular PnL bruto y neto actual (Simétrico: LONG vs SHORT) con fricción real por activo
            from backend.quant_risk import net_return_after_costs, gross_target_for_net, get_asset_friction_costs, is_micro_futures_symbol
            costs = get_asset_friction_costs(sym, price=entry_price)
            pos_fee = costs["fee_pct"]
            pos_spread = costs["spread_pct"]
            is_micro_fut_sym = is_micro_futures_symbol(sym)
            if is_micro_fut_sym and hasattr(self.broker, "accrue_futures_swap"):
                # Devenga swap por cortes de jornada superados y refresca el Break-Even Real (solo futuros simulados)
                swap_info = self.broker.accrue_futures_swap(sym)
                if swap_info.get("be_price"):
                    pos["be_price"] = swap_info["be_price"]

            if is_pos_short:
                gross_pnl_pct = ((entry_price - cur_price) / entry_price) * 100.0 if entry_price > 0 else 0.0
            else:
                gross_pnl_pct = (cur_price / entry_price - 1.0) * 100.0 if entry_price > 0 else 0.0
            net_pnl_pct = net_return_after_costs(gross_pnl_pct, pos_fee, pos_spread)

            # 2. Rastreo continuo de Extremo Favorable (Pico Máximo para LONG / Valle Mínimo para SHORT)
            cached_peak = float((self.counterfactual_cache.get(sym) or {}).get("peak_price") or entry_price)
            db_peak = float(pos.get("peak_price") or entry_price)
            if is_pos_short:
                peak_price = min(db_peak, cached_peak, cur_price) if (db_peak > 0 and cached_peak > 0) else cur_price
                peak_advanced = peak_price < (db_peak - 1e-8)
                peak_gross_pct = ((entry_price - peak_price) / entry_price) * 100.0 if entry_price > 0 else 0.0
            else:
                peak_price = max(db_peak, cached_peak, cur_price)
                peak_advanced = peak_price > (db_peak + 1e-8)
                peak_gross_pct = ((peak_price / entry_price) - 1.0) * 100.0 if entry_price > 0 else 0.0
            if peak_advanced:
                pos["peak_price"] = peak_price

            be_armed = int(pos.get("be_armed", 0))
            trail_active = int(pos.get("trail_active", 0))
            current_stop_net_pct = float(pos.get("current_stop_net_pct", -sl_pct))

            # Telemetría de Mercado (RSI y ATR) para decisiones de la Llave IA y calibraciones dinámicas
            rsi_val = 50.0
            atr_pct = 0.50
            sym_ind = self.symbol_indicators.get(sym) or {}
            if not sym_ind and hasattr(self, "last_market_data") and self.last_market_data:
                sym_ind = self.last_market_data
            if sym_ind:
                rsi_val = float(sym_ind.get("rsi") or 50.0)
                atr_pct = float(sym_ind.get("atr_pct") or 0.0)
                if atr_pct <= 0 and sym_ind.get("atr_14") and cur_price > 0:
                    atr_pct = (float(sym_ind["atr_14"]) / cur_price) * 100.0

            # Si no hay datos en caché o están desactualizados (> 180s), refrescar de forma ligera sin bloquear
            if (not sym_ind or (time.time() - float(sym_ind.get("ts", 0))) > 180.0) and cur_price > 0:
                try:
                    from backend.main import get_ohlcv
                    from backend.quant_analysis import compute_technical_indicators
                    import pandas as pd
                    raw_ohlcv = get_ohlcv(sym, "15m", 30)
                    if raw_ohlcv and len(raw_ohlcv) >= 15:
                        df_sym = pd.DataFrame(raw_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        calc_ind = compute_technical_indicators(df_sym)
                        latest_raw_c = calc_ind.get("latest")
                        latest_c = latest_raw_c if latest_raw_c is not None else {}
                        calc_rsi = float(latest_c.get("rsi") or 50.0)
                        calc_atr = float(calc_ind.get("atr_14") or 0.0)
                        df_px = float(df_sym['close'].iloc[-1]) if ('close' in df_sym and len(df_sym) > 0) else cur_price
                        base_px = df_px if df_px > 0 else cur_price
                        calc_atr_pct = (calc_atr / base_px * 100.0) if (calc_atr > 0 and base_px > 0) else 0.50
                        if df_px > 0 and cur_price > 0 and abs(df_px - cur_price) / cur_price <= 0.20:
                            self.symbol_indicators[sym] = {
                                "rsi": calc_rsi,
                                "atr_14": calc_atr,
                                "atr_pct": calc_atr_pct,
                                "ts": time.time(),
                            }
                            rsi_val = calc_rsi
                            atr_pct = calc_atr_pct
                except Exception:
                    pass

            # 3. Breakeven Autónomo en Backend (Fórmula Ganadora Raúl):
            # - Escalón 1A (+0.40% a <+0.65% bruto) · Candado de Piso de Costo Real (100% Comisiones Cubiertas + Ganancia Neta):
            #   En una posición con 0.10% de comisión de entrada + 0.10% de salida (0.20% round-trip),
            #   cuando el avance bruto alcanza +0.40% (ej. $77,758 sobre $77,448), el Stop se planta en +0.25% bruto
            #   (+$193 en BTC -> $77,642), cubriendo el 100% de las comisiones ($0.20 USDT) + $0.05 USDT netos
            #   y dejando 0.15% (~$116 en BTC) de colchón de respiración bajo el pico.
            # - Escalón 1B (>= +0.65% bruto) · Breakeven Real Neto (+0.15% neto / ~+0.45% bruto):
            #   Cuando el avance supera +0.65% bruto, el piso sube a +0.45% bruto garantizando +0.15% neto libre de comisiones.
            # Umbral de armado del Breakeven parametrizable por estrategia (fallback global: +0.40%).
            # donchian_breakout_1h: +1.00% (Variante C del backtest comparativo; mejor PnL en BTC y ETH 1H).
            is_forex_sym = "=X" in sym.upper()
            is_swing_lab = pos_strategy in SWING_4H_LAB_STRATEGIES
            be_threshold_gross = 0.08 if is_micro_fut_sym else (0.16 if is_forex_sym else BE_THRESHOLD_GROSS_BY_STRATEGY.get(pos_strategy, BE_THRESHOLD_GROSS_DEFAULT))
            be_lock_net_pct = 0.05 if is_micro_fut_sym else (0.45 if is_swing_lab else 0.15)
            be_early_net_pct = 0.02 if is_micro_fut_sym else (0.20 if is_swing_lab else 0.05)
            be_lock_gross_pct = gross_target_for_net(be_lock_net_pct, pos_fee, pos_spread)
            be_early_gross_pct = max(0.05 if (pos_fee == 0.0 or is_micro_fut_sym or is_forex_sym) else 0.25, round(2.0 * pos_fee + 0.05, 4) if not is_forex_sym else 0.05)
            effective_be_trigger_gross = be_threshold_gross
            updated_trailing = False
            max_reached_gross = max(gross_pnl_pct, peak_gross_pct)
            be_upgrade_threshold = 0.15 if is_micro_fut_sym else (0.25 if is_forex_sym else (1.80 if is_swing_lab else 0.65))
            be_floor_gross_pct = be_lock_gross_pct if max_reached_gross >= be_upgrade_threshold else be_early_gross_pct
            target_be_net_pct = be_lock_net_pct if max_reached_gross >= be_upgrade_threshold else be_early_net_pct
            if is_pos_short:
                be_target_price = entry_price * (1.0 - be_floor_gross_pct / 100.0)
            else:
                be_target_price = entry_price * (1.0 + be_floor_gross_pct / 100.0)

            if is_micro_fut_sym and int(pos.get("tp1_trimmed") or 0) == 1 and float(pos.get("be_price") or 0.0) > 0.0:
                # Break-Even exacto del remanente (comisiones + spread + swap): el stop nunca queda por debajo del BE real
                exact_be_px = float(pos["be_price"])
                be_target_price = min(be_target_price, exact_be_px) if is_pos_short else max(be_target_price, exact_be_px)

            is_be_pass = (cur_price < be_target_price) if is_pos_short else (cur_price > be_target_price)

            # Pre-Breakeven para Shorting (Escalón 0.30% favorable -> comprime SL inicial un 60% si aún no armó BE)
            # Para donchian_breakout_1h y Swing 4H: DESACOPLADO (sin compresión asfixiante prematura)
            if not is_donchian and not is_swing_lab and is_pos_short and be_armed == 0 and max_reached_gross >= 0.30:
                compressed_short_sl_net = -round(abs(sl_pct) * 0.40, 4)
                if current_stop_net_pct < compressed_short_sl_net:
                    current_stop_net_pct = compressed_short_sl_net
                    pos["current_stop_net_pct"] = current_stop_net_pct
                    updated_trailing = True

            if not is_donchian and max_reached_gross >= effective_be_trigger_gross and be_armed == 0 and is_be_pass:
                be_armed = 1
                pos["be_armed"] = 1
                if current_stop_net_pct < be_lock_net_pct:
                    current_stop_net_pct = be_lock_net_pct
                    pos["current_stop_net_pct"] = current_stop_net_pct
                updated_trailing = True
                logger.info(
                    f"🛡️ [DAEMON BREAKEVEN GANADOR +{effective_be_trigger_gross:.2f}%] {sym} ({'SHORT' if is_pos_short else 'LONG'}) alcanzó avance +{max_reached_gross:.2f}% bruto. "
                    f"Stop Loss movido a Breakeven Real (${be_target_price:.4f} / +{be_floor_gross_pct:.2f}% bruto / +{target_be_net_pct:.2f}% neto garantizado). ¡Riesgo cero blindado!"
                )

            # - Escalón 2 · Cerrojo de Scalping Bloqueado (Fórmula Doble Escalón - Idea Raúl):
            #   En cuanto el retorno bruto del precio alcance o supere +1.00% (o +2.00% en Swing 4H Lab):
            #   El Stop Loss queda blindado en piso neto positivo.
            scalp_trigger_gross = 0.25 if (is_forex_sym or is_micro_fut_sym) else (2.00 if is_swing_lab else 1.00)
            scalp_floor_gross = 0.20 if (is_forex_sym or is_micro_fut_sym) else (1.35 if is_swing_lab else 0.80)
            scalp_floor_net_pct = net_return_after_costs(scalp_floor_gross, pos_fee, pos_spread)
            if is_pos_short:
                scalp_target_price = entry_price * (1.0 - scalp_floor_gross / 100.0)
            else:
                scalp_target_price = entry_price * (1.0 + scalp_floor_gross / 100.0)

            if not is_donchian and max_reached_gross >= scalp_trigger_gross:
                if be_armed == 0:
                    be_armed = 1
                    pos["be_armed"] = 1
                if current_stop_net_pct < scalp_floor_net_pct:
                    current_stop_net_pct = scalp_floor_net_pct
                    pos["current_stop_net_pct"] = current_stop_net_pct
                    updated_trailing = True
                    logger.info(
                        f"🔒 [DAEMON CERROJO SCALPING +{scalp_trigger_gross:.2f}% -> +{scalp_floor_gross:.2f}% BRUTO] {sym} ({'SHORT' if is_pos_short else 'LONG'}) "
                        f"alcanzó avance +{max_reached_gross:.2f}% bruto (pico +{peak_gross_pct:.2f}%). "
                        f"Stop Loss blindado en piso de scalping (${scalp_target_price:.4f} / +{scalp_floor_net_pct:.2f}% neto garantizado)."
                    )

            # 4. Trailing Stop Adaptativo (Llave IA - Escalón 3 Trailing sin Techo)
            if is_forex_sym or is_micro_fut_sym:
                base_trailing_dist = max(0.10 if is_micro_fut_sym else 0.12, float(pos.get("trailing_dist_pct") or sl_pct or 0.18))
                trailing_tiers = (
                    (1.20, 0.15, 0.10),
                    (0.60, min(base_trailing_dist, 0.20), 0.12),
                    (0.25, min(base_trailing_dist, 0.22), 0.14),
                )
                default_comp = max(0.10 if is_micro_fut_sym else 0.12, round(base_trailing_dist * 0.85, 2))
            else:
                base_trailing_dist = max(1.5, float(pos.get("trailing_dist_pct") or sl_pct or 2.0))
                trailing_tiers = (
                    (8.0, 1.20, 0.80),
                    (4.0, 1.50, 1.00),
                    # Escalón 3 (Picos > +1.50%): acompaña el pico a una distancia protectora de 1.2% a 1.5% detrás del pico
                    (1.50, min(base_trailing_dist, 1.50), 1.20),
                )
                default_comp = max(1.50, round(base_trailing_dist * 0.85, 2))

            holgado_dist_pct, comprimido_dist_pct = next(
                ((h, c) for thr, h, c in trailing_tiers if peak_gross_pct >= thr),
                (base_trailing_dist, default_comp),
            )

            if is_pos_short:
                holgado_stop_price = peak_price * (1.0 + holgado_dist_pct / 100.0)
                holgado_gross_pct = ((entry_price - holgado_stop_price) / entry_price) * 100.0 if entry_price > 0 else 0.0
                holgado_net_pct = net_return_after_costs(holgado_gross_pct, pos_fee, pos_spread)

                comprimido_stop_price = peak_price * (1.0 + comprimido_dist_pct / 100.0)
                comprimido_gross_pct = ((entry_price - comprimido_stop_price) / entry_price) * 100.0 if entry_price > 0 else 0.0
                comprimido_net_pct = net_return_after_costs(comprimido_gross_pct, pos_fee, pos_spread)
            else:
                holgado_stop_price = peak_price * (1.0 - holgado_dist_pct / 100.0)
                holgado_gross_pct = ((holgado_stop_price / entry_price) - 1.0) * 100.0 if entry_price > 0 else 0.0
                holgado_net_pct = net_return_after_costs(holgado_gross_pct, pos_fee, pos_spread)

                comprimido_stop_price = peak_price * (1.0 - comprimido_dist_pct / 100.0)
                comprimido_gross_pct = ((comprimido_stop_price / entry_price) - 1.0) * 100.0 if entry_price > 0 else 0.0
                comprimido_net_pct = net_return_after_costs(comprimido_gross_pct, pos_fee, pos_spread)

            # Evaluación de la Llave (Auto IA vs Manual)
            configured_key = getattr(self, "trailing_key_mode", "auto").lower()
            if configured_key == "holgado":
                active_mode = "HOLGADO"
                ai_reason = f"Operador forzó Modo Holgado ({holgado_dist_pct}%) para máxima amplitud tendencial."
                active_dist_pct = holgado_dist_pct
                active_stop_price = holgado_stop_price
                chosen_net_pct = holgado_net_pct
                alt_mode = "COMPRIMIDO"
                alt_dist_pct = comprimido_dist_pct
                alt_stop_price = comprimido_stop_price
                alt_net_pct = comprimido_net_pct
            elif configured_key == "comprimido":
                active_mode = "COMPRIMIDO"
                ai_reason = f"Operador forzó Modo Comprimido ({comprimido_dist_pct}%) para máxima retención de ganancia."
                active_dist_pct = comprimido_dist_pct
                active_stop_price = comprimido_stop_price
                chosen_net_pct = comprimido_net_pct
                alt_mode = "HOLGADO"
                alt_dist_pct = holgado_dist_pct
                alt_stop_price = holgado_stop_price
                alt_net_pct = holgado_net_pct
            else:
                # AUTO (IA modula adaptativamente según avance y régimen de volatilidad/RSI):
                # En Swing 4H Lab se elevan los umbrales para que la IA deje correr hacia dólares enteros sin comprimir temprano
                direction_label = "caída" if is_pos_short else "rally"
                tight_regime = is_forex_sym or is_micro_fut_sym
                climax_thr = 1.50 if tight_regime else (10.0 if is_swing_lab else 8.0)
                mature_thr = 0.45 if tight_regime else (3.50 if is_swing_lab else 1.20)
                mature_peak_thr = 0.80 if tight_regime else (5.00 if is_swing_lab else 2.0)
                early_thr = 0.25 if tight_regime else (2.50 if is_swing_lab else 0.70)
                rsi_ext_up = 76.0 if is_swing_lab else 70.0
                rsi_ext_dn = 24.0 if is_swing_lab else 30.0
                if peak_gross_pct >= climax_thr:
                    active_mode = "COMPRIMIDO"
                    ai_reason = f"Clímax de {direction_label} (+{peak_gross_pct:.2f}%). Comprimiendo trailing a {comprimido_dist_pct}% para amarrar la cima/valle."
                elif (rsi_val >= rsi_ext_up and not is_pos_short) or (rsi_val <= rsi_ext_dn and is_pos_short):
                    active_mode = "COMPRIMIDO"
                    ai_reason = f"RSI extremo ({rsi_val:.1f}). Peligro de agotamiento; comprimiendo stop a {comprimido_dist_pct}%."
                elif peak_gross_pct >= mature_thr and (peak_gross_pct >= mature_peak_thr or (rsi_val >= 60.0 and not is_pos_short) or (rsi_val <= 40.0 and is_pos_short)):
                    active_mode = "COMPRIMIDO"
                    ai_reason = f"Tendencia en maduración (+{peak_gross_pct:.2f}%, RSI {rsi_val:.1f}). Comprimiendo trailing a {comprimido_dist_pct}% para retener beneficios."
                elif peak_gross_pct >= early_thr and ((rsi_val >= 65.0 and not is_pos_short) or (rsi_val <= 35.0 and is_pos_short)):
                    active_mode = "COMPRIMIDO"
                    ai_reason = f"Avance temprano con RSI tenso (+{peak_gross_pct:.2f}%, RSI {rsi_val:.1f}). Comprimiendo a {comprimido_dist_pct}% para blindar beneficio."
                else:
                    active_mode = "HOLGADO"
                    ai_reason = f"Tendencia en desarrollo (RSI {rsi_val:.1f}, pico +{peak_gross_pct:.2f}%). Modo Holgado ({holgado_dist_pct}%) activo para dejar correr."

                if active_mode == "COMPRIMIDO":
                    active_dist_pct = comprimido_dist_pct
                    active_stop_price = comprimido_stop_price
                    chosen_net_pct = comprimido_net_pct
                    alt_mode = "HOLGADO"
                    alt_dist_pct = holgado_dist_pct
                    alt_stop_price = holgado_stop_price
                    alt_net_pct = holgado_net_pct
                else:
                    active_dist_pct = holgado_dist_pct
                    active_stop_price = holgado_stop_price
                    chosen_net_pct = holgado_net_pct
                    alt_mode = "COMPRIMIDO"
                    alt_dist_pct = comprimido_dist_pct
                    alt_stop_price = comprimido_stop_price
                    alt_net_pct = comprimido_net_pct

            # Cálculo de diferencial contrafáctico (en % y en USDT)
            counterfactual_diff_pct = chosen_net_pct - alt_net_pct
            qty_pos = float(pos.get("qty", 0.0))
            cost_pos = float(pos.get("cost_basis") or (entry_price * qty_pos) or 100.0)
            counterfactual_diff_usd = cost_pos * (counterfactual_diff_pct / 100.0)

            # Actualizar Trailing Stop activo si el nuevo stop supera el anterior (requiere Breakeven previo para no asfixiar el avance temprano)
            # Para donchian_breakout_1h: DESACOPLADO (salida gobernada exclusivamente por MID_EXIT)
            is_favorable_now = (cur_price < entry_price) if is_pos_short else (cur_price > entry_price)
            if not is_donchian and is_favorable_now and chosen_net_pct > current_stop_net_pct and (be_armed == 1 or trail_active == 1):
                trail_active = 1
                pos["trail_active"] = 1
                current_stop_net_pct = chosen_net_pct
                pos["current_stop_net_pct"] = current_stop_net_pct
                updated_trailing = True
                logger.info(
                    f"📈 [DAEMON LLAVE {active_mode}] {sym} ({'SHORT' if is_pos_short else 'LONG'}) extremo ${peak_price:.2f}. "
                    f"Stop movido a ${active_stop_price:.2f} (+{current_stop_net_pct:.2f}% neto). {ai_reason}"
                )

            # Si el Breakeven Real o el Cerrojo de Scalping supera al trailing bruto,
            # reflejar el Stop Efectivo Real en la telemetría (respetando el piso innegociable)
            if not is_donchian:
                floor_stop_px = scalp_target_price if max_reached_gross >= scalp_trigger_gross else be_target_price
                stop_gross_equiv = gross_target_for_net(current_stop_net_pct, pos_fee, pos_spread)
                if is_pos_short:
                    if be_armed == 1:
                        protected_stop_px = min(floor_stop_px, active_stop_price)
                    elif current_stop_net_pct > -sl_pct:
                        protected_stop_px = min(entry_price * (1.0 - stop_gross_equiv / 100.0), active_stop_price)
                    else:
                        protected_stop_px = active_stop_price
                    if protected_stop_px < active_stop_price:
                        active_stop_price = round(protected_stop_px, 6)
                        chosen_net_pct = round(current_stop_net_pct, 4)
                else:
                    if be_armed == 1:
                        protected_stop_px = max(floor_stop_px, active_stop_price)
                    elif current_stop_net_pct > -sl_pct:
                        protected_stop_px = max(entry_price * (1.0 + stop_gross_equiv / 100.0), active_stop_price)
                    else:
                        protected_stop_px = active_stop_price
                    if protected_stop_px > active_stop_price:
                        active_stop_price = round(protected_stop_px, 6)
                        chosen_net_pct = round(current_stop_net_pct, 4)
            else:
                floor_stop_px = entry_price * (1.0 + sl_pct / 100.0) if is_pos_short else entry_price * (1.0 - sl_pct / 100.0)
                active_stop_price = round(floor_stop_px, 6)
                chosen_net_pct = -sl_pct

            # Almacenar telemetría contrafáctica para la auditoría forense
            cf_info = {
                "symbol": sym,
                "entry_price": entry_price,
                "cur_price": cur_price,
                "peak_price": peak_price,
                "peak_gross_pct": peak_gross_pct,
                "rsi": rsi_val,
                "active_mode": active_mode,
                "active_dist_pct": active_dist_pct,
                "active_stop_price": active_stop_price,
                "active_net_pct": chosen_net_pct,
                "be_armed": be_armed,
                "alt_mode": alt_mode,
                "alt_dist_pct": alt_dist_pct,
                "alt_stop_price": alt_stop_price,
                "alt_net_pct": alt_net_pct,
                "ai_reason": ai_reason,
                "diff_pct": counterfactual_diff_pct,
                "diff_usd": counterfactual_diff_usd,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.counterfactual_cache[sym] = cf_info
            pos["trailing_telemetry"] = cf_info

            # 5. Apretado Progresivo por Tiempo (Opción B: Time-Decay Tightening)
            # & Auditoría Continua con Sugerencia de Conmutación a Opción A o C
            opened_at_str = str(pos.get("opened_at") or "")
            elapsed_hours = 0.0
            if opened_at_str:
                try:
                    clean_ts = opened_at_str.replace("T", " ").split(".")[0].strip()
                    dt_opened = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
                    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                    elapsed_hours = max(0.0, (now_utc - dt_opened).total_seconds() / 3600.0)
                except Exception:
                    pass

            time_decay_status = "NORMAL"
            time_decay_suggestion = "Régimen normal: posición dentro de la ventana esperada de maduración."
            stagnation_thr_pct = 0.20 if is_forex_sym else 1.0
            is_stagnated = (peak_gross_pct < stagnation_thr_pct and gross_pnl_pct < stagnation_thr_pct)

            # Precio exacto donde la operación cubre con holgura comisiones y spread (+0.08% neto garantizado)
            # Evita que un cierre por "Empate B" salga con pérdida neta por comisiones o micro-variaciones de tick.
            gross_for_zero_net = gross_target_for_net(0.08, pos_fee, pos_spread)
            if is_pos_short:
                be_net_zero_price = entry_price * (1.0 - gross_for_zero_net / 100.0)
                time_decay_hit = (cur_price <= be_net_zero_price)
            else:
                be_net_zero_price = entry_price * (1.0 + gross_for_zero_net / 100.0)
                time_decay_hit = (cur_price >= be_net_zero_price)

            if elapsed_hours >= 8.0 and is_stagnated:
                if elapsed_hours >= 16.0:
                    time_decay_status = "TIGHTENING_16H"
                    num_open = len(open_positions)
                    max_slots = getattr(self, "max_positions", 4)
                    if num_open >= max_slots:
                        time_decay_suggestion = (
                            f"🚨 [Sugerencia IA]: Máximo estancamiento ({elapsed_hours:.1f}h) y 100% cupos llenos ({num_open}/{max_slots}). "
                            f"Considerar Opción C (Desalojo por Prioridad) si llega una señal con volumen fresco."
                        )
                    else:
                        time_decay_suggestion = (
                            f"⚠️ [Sugerencia IA]: Posición con {elapsed_hours:.1f}h sin definición. "
                            f"Esperando avance a empate neto (${be_net_zero_price:.4f}). Si deseas liberar el cupo ya, considerar Opción A (cierre a mercado)."
                        )
                elif elapsed_hours >= 12.0:
                    time_decay_status = "TIGHTENING_12H"
                    time_decay_suggestion = (
                        f"⏳ [Decay B · 12h]: Estancamiento severo ({elapsed_hours:.1f}h). "
                        f"Gatillo armado para salir a empate neto (${be_net_zero_price:.4f}) al mínimo avance."
                    )
                else:
                    time_decay_status = "TIGHTENING_8H"
                    time_decay_suggestion = (
                        f"⏳ [Decay B · 8h]: Estancamiento moderado ({elapsed_hours:.1f}h). "
                        f"Esperando avance a empate neto (${be_net_zero_price:.4f}) para salir sin pérdida."
                    )

            decay_info = {
                "symbol": sym,
                "elapsed_hours": round(elapsed_hours, 2),
                "status": time_decay_status,
                "suggestion": time_decay_suggestion,
                "is_stagnated": is_stagnated,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.time_decay_cache[sym] = decay_info
            pos["time_decay"] = decay_info
            pos["time_decay_hours"] = round(elapsed_hours, 2)
            pos["time_decay_status"] = time_decay_status
            pos["time_decay_suggestion"] = time_decay_suggestion

            # Persistir SIEMPRE en SQLite si hubo cambios en peak_price, be_armed, stop o time_decay ANTES de liquidar por Time-Decay
            if updated_trailing or peak_advanced or elapsed_hours >= 8.0:
                if hasattr(self.broker, "update_position_trailing") and trade_id:
                    self.broker.update_position_trailing(
                        trade_id, peak_price, current_stop_net_pct, be_armed=be_armed, trail_active=trail_active,
                        trailing_mode=active_mode, ai_decision_reason=ai_reason, counterfactual_diff=counterfactual_diff_pct,
                        time_decay_hours=round(elapsed_hours, 2),
                        time_decay_status=time_decay_status,
                        time_decay_suggestion=time_decay_suggestion
                    )

            # Regla de Oro Opción B: Salida en empate estricto ($0.00 neto) SOLO si la posición sigue estancada
            # sin haber armado Breakeven Real ni Trailing Stop y sin que el operador haya forzado Modo Holgado.
            # Para donchian_breakout_1h: DESACOPLADO (salida puramente gobernada por MID_EXIT)
            # Para estrategias Swing 4H de Lab (is_swing_lab): requieren >= 36h (9 velas 4H) antes de liquidar por estancamiento; Forex requiere >= 24h.
            min_decay_exit_h = 36.0 if is_swing_lab else (24.0 if is_forex_sym else 8.0)
            if not is_donchian and elapsed_hours >= min_decay_exit_h and is_stagnated and time_decay_hit and be_armed == 0 and trail_active == 0 and configured_key != "holgado":
                exit_label = "Time-Decay Exit (Empate B)"
                logger.info(
                    f"⏳ [TIME-DECAY B] {sym} ({'SHORT' if is_pos_short else 'LONG'}) alcanzó precio de empate neto real ${be_net_zero_price:.4f} "
                    f"(precio actual ${cur_price:.4f}, entrada ${entry_price:.4f}) tras {elapsed_hours:.1f}h. "
                    f"Liquidando posición en empate neto real ($0.00 neto)..."
                )
                try:
                    res = self.broker.flatten(sym, current_price=cur_price, exit_reason=exit_label)
                except ValueError:
                    continue
                try:
                    from backend.telegram_notifier import notify_trade_closed
                    net_pnl = float((res or {}).get("net_pnl") or 0.0)
                    op_bal = (res or {}).get("operational_balance")
                    v_bal = (res or {}).get("vault_balance")
                    notify_trade_closed(
                        symbol=sym,
                        side="SHORT" if is_pos_short else "LONG",
                        entry_price=entry_price,
                        exit_price=cur_price,
                        pnl=net_pnl,
                        fees=float(pos.get("total_fees") or 0.0),
                        exit_reason=exit_label,
                        strategy=pos_strategy,
                        cost_basis=float(pos.get("cost_basis") or (entry_price * float(pos.get("qty", 0.0)))),
                        operational_balance=float(op_bal) if op_bal is not None else float(self.broker.balances.get("USDT", 0.0)),
                        vault_balance=float(v_bal) if v_bal is not None else float(self.broker.vault_balances.get("USDT", 0.0)),
                    )
                except Exception as _e_tg_close:
                    logger.warning(f"Error al enviar notificación Telegram de cierre: {_e_tg_close}")
                self._log_trade_csv(sym, "COMPRAR" if is_pos_short else "VENDER", cur_price, float(pos.get("qty", 0)), "Ejecutada", exit_label)
                cd_s = self._arm_cooldown(sym)
                with self._lock:
                    self.cycle_count += 1
                    self.last_cycle_ts = time.time()
                    self.last_signal = exit_label.upper().replace(" ", "_")
                    self.last_reason = f"{exit_label} ejecutado en ${cur_price} ({sym}). Salida neutral en empate."
                liquidated.append({"symbol": sym, "action": exit_label.upper().replace(" ", "_"), "price": cur_price, "result": res})
                continue

            # 6. Cálculo del precio de salida de Stop Loss (SL Inicial vs Breakeven Real / Cerrojo Scalping / Trailing / Time-Decay)
            floor_stop_px = scalp_target_price if max_reached_gross >= scalp_trigger_gross else be_target_price
            stop_gross_equiv = gross_target_for_net(current_stop_net_pct, pos_fee, pos_spread)
            if is_pos_short:
                if be_armed == 1:
                    sl_price = min(floor_stop_px, active_stop_price if trail_active == 1 else floor_stop_px)
                elif trail_active == 1:
                    sl_price = active_stop_price
                elif current_stop_net_pct > -sl_pct:
                    sl_price = entry_price * (1.0 - stop_gross_equiv / 100.0)
                else:
                    sl_price = entry_price * (1.0 + sl_pct / 100.0)
                tp_price = entry_price * (1.0 - tp_pct / 100.0)
                sl_hit = (cur_price >= sl_price)
                tp_hit = (cur_price <= tp_price)
            else:
                if be_armed == 1:
                    sl_price = max(floor_stop_px, active_stop_price if trail_active == 1 else floor_stop_px)
                elif trail_active == 1:
                    sl_price = active_stop_price
                elif current_stop_net_pct > -sl_pct:
                    sl_price = entry_price * (1.0 + stop_gross_equiv / 100.0)
                else:
                    sl_price = entry_price * (1.0 - sl_pct / 100.0)
                tp_price = entry_price * (1.0 + tp_pct / 100.0)
                sl_hit = (cur_price <= sl_price)
                tp_hit = (cur_price >= tp_price)

            # 6b. Salida Dinámica Donchian Mid-Channel Exit para donchian_breakout_1h
            # DESACTIVADO: Las posiciones solo deben cerrarse por Stop Loss ATR o Take Profit ATR asimétrico (R:R >= 1:2).
            donchian_mid_hit = False
            donchian_mid_val = 0.0
            last_closed_bar_close = cur_price

            if donchian_mid_hit and not sl_hit:
                exit_label = "MID_EXIT (Mitad de Canal Donchian)"
                logger.info(
                    f"🛡️ [DAEMON MID_EXIT] {sym} ({'SHORT' if is_pos_short else 'LONG'}) vela 1H cerrada "
                    f"(${last_closed_bar_close:.2f}) cruzó mitad de canal Donchian (${donchian_mid_val:.2f}). "
                    f"Liquidando a mercado en ${cur_price:.2f}..."
                )
                try:
                    res = self.broker.flatten(sym, current_price=cur_price, exit_reason=exit_label)
                except ValueError:
                    continue
                try:
                    from backend.telegram_notifier import notify_trade_closed
                    net_pnl = float((res or {}).get("net_pnl") or 0.0)
                    op_bal = (res or {}).get("operational_balance")
                    v_bal = (res or {}).get("vault_balance")
                    notify_trade_closed(
                        symbol=sym,
                        side="SHORT" if is_pos_short else "LONG",
                        entry_price=entry_price,
                        exit_price=cur_price,
                        pnl=net_pnl,
                        fees=float(pos.get("total_fees") or 0.0),
                        exit_reason=exit_label,
                        strategy=pos_strategy,
                        cost_basis=float(pos.get("cost_basis") or (entry_price * float(pos.get("qty", 0.0)))),
                        operational_balance=float(op_bal) if op_bal is not None else float(self.broker.balances.get("USDT", 0.0)),
                        vault_balance=float(v_bal) if v_bal is not None else float(self.broker.vault_balances.get("USDT", 0.0)),
                    )
                except Exception as _e_tg_close:
                    logger.warning(f"Error al enviar notificación Telegram de cierre: {_e_tg_close}")
                self._log_trade_csv(sym, "COMPRAR" if is_pos_short else "VENDER", cur_price, float(pos.get("qty", 0)), "Ejecutada", exit_label)
                cd_s = self._arm_cooldown(sym)
                with self._lock:
                    self.cycle_count += 1
                    self.last_cycle_ts = time.time()
                    self.last_signal = "MID_EXIT"
                    self.last_reason = f"{exit_label} ejecutado en ${cur_price} ({sym}). Cruce de mitad de canal por vela 1H cerrada (${last_closed_bar_close:.2f} vs ${donchian_mid_val:.2f})."
                liquidated.append({"symbol": sym, "action": "MID_EXIT", "price": cur_price, "result": res})
                continue

            # Verificación de Stop Loss / Breakeven / Trailing Stop / Time-Decay
            if sl_hit:
                if is_donchian:
                    exit_label = "Stop Loss (ATR Donchian)"
                elif time_decay_status.startswith("TIGHTENING") and current_stop_net_pct >= 0.0:
                    exit_label = "Time-Decay Exit (Empate B)"
                elif trail_active == 1 and current_stop_net_pct > 0.15:
                    exit_label = "Trailing Stop"
                elif be_armed == 1:
                    exit_label = "Breakeven Real"
                else:
                    exit_label = "Stop Loss"
                scalp_tag = " [CERROJO SCALPING]" if max_reached_gross >= scalp_trigger_gross else ""
                logger.info(f"🛑 [DAEMON {exit_label.upper()}{scalp_tag}] Precio actual ${cur_price} tocó {exit_label} ${sl_price:.2f} en {sym} ({'SHORT' if is_pos_short else 'LONG'}). Liquidando...")
                try:
                    res = self.broker.flatten(sym, current_price=cur_price, exit_reason=exit_label)
                except ValueError:
                    continue
                try:
                    from backend.telegram_notifier import notify_trade_closed
                    net_pnl = float((res or {}).get("net_pnl") or 0.0)
                    op_bal = (res or {}).get("operational_balance")
                    v_bal = (res or {}).get("vault_balance")
                    notify_trade_closed(
                        symbol=sym,
                        side="SHORT" if is_pos_short else "LONG",
                        entry_price=entry_price,
                        exit_price=cur_price,
                        pnl=net_pnl,
                        fees=float(pos.get("total_fees") or 0.0),
                        exit_reason=exit_label,
                        strategy=pos_strategy,
                        cost_basis=float(pos.get("cost_basis") or (entry_price * float(pos.get("qty", 0.0)))),
                        operational_balance=float(op_bal) if op_bal is not None else float(self.broker.balances.get("USDT", 0.0)),
                        vault_balance=float(v_bal) if v_bal is not None else float(self.broker.vault_balances.get("USDT", 0.0)),
                    )
                except Exception as _e_tg_close:
                    logger.warning(f"Error al enviar notificación Telegram de cierre: {_e_tg_close}")
                self._log_trade_csv(sym, "COMPRAR" if is_pos_short else "VENDER", cur_price, float(pos.get("qty", 0)), "Ejecutada", exit_label)
                cd_s = self._arm_cooldown(sym)
                with self._lock:
                    self.cycle_count += 1
                    self.last_cycle_ts = time.time()
                    self.last_signal = exit_label.upper().replace(" ", "_")
                    self.last_reason = f"{exit_label} ejecutado automáticamente en ${cur_price} ({sym}). Cooldown activado ({cd_s / 60.0:.1f} min)."
                liquidated.append({"symbol": sym, "action": exit_label.upper().replace(" ", "_"), "price": cur_price, "result": res})
                continue

            # Verificación de Peluqueo 50% (por TP1 o por Clímax de RSI >= 70.0 con avance >= +1.00% bruto) y Take Profit
            already_trimmed = int(pos.get("tp1_trimmed") or 0) == 1
            pos_strategy = pos.get("strategy") or self.strategy
            is_manual = (self.strategy == "manual" or pos_strategy == "manual")
            climax_min_gross = max(2.50, sl_pct) if is_swing_lab else 1.00
            climax_rsi_up = 75.0 if is_swing_lab else 70.0
            climax_rsi_dn = 25.0 if is_swing_lab else 30.0
            rsi_climax_trim = (
                (not is_pos_short and rsi_val >= climax_rsi_up and gross_pnl_pct >= climax_min_gross)
                or (is_pos_short and rsi_val <= climax_rsi_dn and gross_pnl_pct >= climax_min_gross)
            )

            if (tp_hit or rsi_climax_trim) and not is_manual and not is_donchian and not already_trimmed and sl_pct > 0.0:
                total_qty = float(pos.get("qty", 0.0))
                if is_micro_fut_sym:
                    # En Micro-Futuros CME: cerrar exactamente 1 contrato (de 2) en TP1 y dejar 1 corriendo con trailing/BE
                    trim_qty = float(max(1, int(total_qty // 2))) if int(round(total_qty)) >= 2 else 0.0
                    can_trim_pos = (0 < trim_qty < total_qty)
                else:
                    trim_qty = round(total_qty * 0.5, 8)
                    can_trim_pos = (0 < trim_qty < total_qty and (trim_qty * cur_price) >= 5.0)
                if can_trim_pos:
                    trim_reason_code = "PELUQUEO_TP1_50%" if tp_hit else "PELUQUEO_RSI70_50%"
                    trim_action_tag = "PELUQUEO_TP1" if tp_hit else "PELUQUEO_RSI70"
                    trim_trigger_desc = f"TP1 alcanzado (+{tp_pct:.2f}%)" if tp_hit else f"Clímax RSI ({rsi_val:.1f}) con ganancia bruta +{gross_pnl_pct:.2f}%"
                    logger.info(
                        f"✂️ [DAEMON PELUQUEO] {trim_trigger_desc}. Liquidando 50% ({trim_qty}) en ${cur_price} ({sym}). "
                        f"Moviendo Stop Loss del remanente a Breakeven Real (+0.25%) y activando Trailing Stop sin techo."
                    )
                    try:
                        res_trim = self.broker.trim_position(sym, trim_qty=trim_qty, current_price=cur_price, reason=trim_reason_code)
                    except ValueError:
                        continue
                    try:
                        from backend.telegram_notifier import notify_trade_peluqueo
                        trim_pnl = float((res_trim or {}).get("net_pnl") or 0.0)
                        trim_swept = float((res_trim or {}).get("swept_to_vault") or 0.0)
                        rem_qty = float((res_trim or {}).get("remaining_qty") or (total_qty - trim_qty))
                        op_bal = (res_trim or {}).get("operational_balance")
                        v_bal = (res_trim or {}).get("vault_balance")
                        notify_trade_peluqueo(
                            symbol=sym,
                            price=cur_price,
                            trimmed_qty=trim_qty,
                            remaining_qty=rem_qty,
                            pnl_secured=trim_pnl,
                            swept_to_vault=trim_swept,
                            trigger_desc=trim_trigger_desc,
                            operational_balance=float(op_bal) if op_bal is not None else float(self.broker.balances.get("USDT", 0.0)),
                            vault_balance=float(v_bal) if v_bal is not None else float(self.broker.vault_balances.get("USDT", 0.0)),
                        )
                    except Exception as _e_tg_trim:
                        logger.warning(f"Error al enviar notificación Telegram peluqueo: {_e_tg_trim}")
                    self._log_trade_csv(sym, "TRIM_50%", cur_price, trim_qty, "Ejecutada", f"Peluqueo ({trim_action_tag}) + Breakeven")
                    with self._lock:
                        self.cycle_count += 1
                        self.last_cycle_ts = time.time()
                        self.last_signal = trim_action_tag
                        self.last_reason = f"Toma parcial 50% ({trim_trigger_desc}) ejecutada en ${cur_price} ({sym}). Ganancia asegurada; el remanente corre con Trailing Stop ($0 riesgo)."
                    liquidated.append({"symbol": sym, "action": trim_action_tag, "price": cur_price, "result": res_trim})
                    continue

            if tp_hit:

                # Si ya fue peluqueada y es una estrategia runner (sin techo):
                if is_trailing_runner:
                    portion_tag = "50% remanente" if already_trimmed else "100% posición"
                    logger.debug(
                        f"🚀 [DAEMON RUNNER SIN TECHO] {sym} cotiza en ${cur_price:.4f} (superó ref TP ${tp_price:.4f}). "
                        f"{portion_tag} corriendo libre con Trailing Stop activo en ${sl_price:.4f}."
                    )
                    continue

                # Estrategias tradicionales con TP rígido final (ej. TP2 al doble de distancia)
                logger.info(f"🎯 [DAEMON TP] Precio actual ${cur_price} tocó Take Profit ${tp_price:.2f} en {sym}. Liquidando...")
                try:
                    res = self.broker.flatten(sym, current_price=cur_price, exit_reason="Take Profit")
                except ValueError:
                    continue
                try:
                    from backend.telegram_notifier import notify_trade_closed
                    net_pnl = float((res or {}).get("net_pnl") or 0.0)
                    op_bal = (res or {}).get("operational_balance")
                    v_bal = (res or {}).get("vault_balance")
                    notify_trade_closed(
                        symbol=sym,
                        side="SHORT" if is_pos_short else "LONG",
                        entry_price=entry_price,
                        exit_price=cur_price,
                        pnl=net_pnl,
                        fees=float(pos.get("total_fees") or 0.0),
                        exit_reason="Take Profit",
                        strategy=pos_strategy,
                        cost_basis=float(pos.get("cost_basis") or (entry_price * float(pos.get("qty", 0.0)))),
                        operational_balance=float(op_bal) if op_bal is not None else float(self.broker.balances.get("USDT", 0.0)),
                        vault_balance=float(v_bal) if v_bal is not None else float(self.broker.vault_balances.get("USDT", 0.0)),
                    )
                except Exception as _e_tg_close:
                    logger.warning(f"Error al enviar notificación Telegram de cierre: {_e_tg_close}")
                self._log_trade_csv(sym, "VENDER", cur_price, float(pos.get("qty", 0)), "Ejecutada", "Take Profit")
                cd_s = self._arm_cooldown(sym)
                with self._lock:
                    self.cycle_count += 1
                    self.last_cycle_ts = time.time()
                    self.last_signal = "TAKE_PROFIT"
                    self.last_reason = f"Take Profit ejecutado automáticamente en ${cur_price} ({sym}). Cooldown activado ({cd_s / 60.0:.1f} min)."
                liquidated.append({"symbol": sym, "action": "TAKE_PROFIT", "price": cur_price, "result": res})
                continue

        return liquidated

    def _execute_cycle(self) -> None:
        from backend.main import get_analysis, get_price
        from starlette.requests import Request
        from backend.estrategias.registry import is_asset_market_open

        self._check_radar_for_autorouting()

        # 0. Actualizar posiciones espejo de Shadow Testing (Tabla #19)
        ledger_inst = getattr(self.broker, "ledger", None)
        if ledger_inst and hasattr(ledger_inst, "get_open_shadow_trades") and hasattr(ledger_inst, "update_and_close_shadow_trades"):
            try:
                open_shadows = ledger_inst.get_open_shadow_trades()
                for st in open_shadows:
                    st_sym = st.get("symbol")
                    if st_sym:
                        try:
                            px_res = get_price(st_sym)
                            px_cur = float(px_res.get("price") or 0.0)
                            if px_cur > 0:
                                ledger_inst.update_and_close_shadow_trades(
                                    symbol=st_sym,
                                    current_price=px_cur,
                                )
                        except Exception:
                            pass
            except Exception as _st_err:
                logger.debug(f"[Shadow Testing] Error actualizando trades virtuales: {_st_err}")

        # 1. Comprobar posiciones abiertas en el Ledger SQLite y loguear hibernación
        open_positions = self.broker.fetch_positions()
        hibernating = [p for p in open_positions if not is_asset_market_open(p.get("symbol", ""))]
        for hp in hibernating:
            logger.warning(
                f"⚠️ [POSICIÓN CON MERCADO CERRADO] Posición en {hp.get('symbol')} en espera de reapertura de rueda. "
                "En un broker real ninguna orden se ejecutará hasta la próxima sesión (Pre-market/Apertura). "
                "En paper trading local puede forzar salida contable de emergencia a precio oficial de cierre."
            )

        open_market_positions = [p for p in open_positions if is_asset_market_open(p.get("symbol", ""))]

        # 2. Guardián Multi-Posición: evaluar SL / TP en TODAS las posiciones activas
        liquidated = self._check_open_positions_protections(open_market_positions)
        if any(liq["symbol"] == self.symbol for liq in liquidated):
            return

        # Refrescar posiciones abiertas tras evaluación del guardián
        open_positions = self.broker.fetch_positions()
        open_market_positions = [p for p in open_positions if is_asset_market_open(p.get("symbol", ""))]

        # 2b. Control de Drenado Elegante en Scalping Presencial
        if getattr(self, "scalping_draining", False):
            open_scalp = [
                p for p in open_positions
                if p.get("strategy") == getattr(self, "scalping_strategy", "") or p.get("symbol") == getattr(self, "scalping_symbol", "")
            ]
            if not open_scalp:
                self._restore_backup_strategy("Todas las operaciones de scalping han sido liquidadas exitosamente.")
                return
            else:
                logger.info(f"⏳ [SCALPING DRENANDO] Guardián vigilando {len(open_scalp)} trade(s) activo(s). Bloqueada apertura de nuevas órdenes.")
                return

        # Determinar símbolos a procesar en esta pasada:
        # 1. Todas las posiciones abiertas en mercado (para vigilar salidas/ventas).
        # 2. Si hay cupos libres (< max_positions): el candidato del radar y/o el símbolo base.
        symbols_to_process = []
        for p in open_market_positions:
            s = p.get("symbol")
            if s and s not in symbols_to_process:
                symbols_to_process.append(s)

        # Si auto-orquestador y el símbolo base está cerrado, conmutar a SOL/USDT (Cripto 24/7)
        if self.strategy == "auto" and self.symbol and not is_asset_market_open(self.symbol):
            logger.info(
                f"🌙 [AUTO-ORQUESTADOR] Mercado de {self.symbol} cerrado por horario. Conmutando a SOL/USDT (Cripto 24/7)."
            )
            self.symbol = "SOL/USDT"

        global_free_slots = max(0, self.max_positions - len(open_positions))

        def _can_add_candidate(cand_sym: str) -> bool:
            if not cand_sym or cand_sym in symbols_to_process or not is_asset_market_open(cand_sym):
                return False
            c_up = cand_sym.upper()
            is_us_equity = (
                "/" not in c_up
                and "=X" not in c_up
                and "=F" not in c_up
                and not c_up.endswith(".BA")
                and not c_up.startswith("^")
            )
            if is_us_equity and not self.is_stocks_evaluation_window():
                return False
            return self._compute_book_slot_limits(open_positions, cand_sym)["book_free"] > 0

        if global_free_slots > 0:
            # Modo Inteligente (Multi-Activo) con aislamiento por bóveda (USDT, USD, ARS):
            # En donchian_breakout_1h evalúa Cripto (4H) y Acciones TradFi (1D) cada cual según los cupos de su propia bóveda.
            if self.strategy == "donchian_breakout_1h":
                for c_sym in DONCHIAN_CRYPTO_WHITELIST:
                    if _can_add_candidate(c_sym):
                        symbols_to_process.append(c_sym)
                for s_sym in DONCHIAN_TRADFI_WHITELIST:
                    if _can_add_candidate(s_sym):
                        symbols_to_process.append(s_sym)
            else:
                if self.radar_candidate_symbol and _can_add_candidate(self.radar_candidate_symbol):
                    symbols_to_process.append(self.radar_candidate_symbol)
                if self.symbol and _can_add_candidate(self.symbol):
                    symbols_to_process.append(self.symbol)
                if self.mode == "smart":
                    for liquid_sym in ("SOL/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "BTC/USDT"):
                        if _can_add_candidate(liquid_sym):
                            symbols_to_process.append(liquid_sym)
                    try:
                        from backend.estrategias.registry import get_strategy
                        from backend.quant_risk import is_micro_futures_symbol as _is_mf_sym
                        include_futures_sim = _is_mf_sym(self.symbol) or bool(getattr(self, "enable_futures_simulation", False))
                        for a_id in (self.allowed_strategies or []):
                            st_obj = get_strategy(a_id)
                            for rec_sym in (getattr(st_obj, "activos_recomendados", None) or []):
                                if _is_mf_sym(rec_sym) and not include_futures_sim:
                                    continue
                                if _can_add_candidate(rec_sym):
                                    symbols_to_process.append(rec_sym)
                    except Exception:
                        pass
                try:
                    from backend.macro_bias_buffer import MacroBiasBuffer
                    for ab in MacroBiasBuffer().get_all_active():
                        ab_sym = ab.get("symbol")
                        if _can_add_candidate(ab_sym):
                            symbols_to_process.append(ab_sym)
                except Exception:
                    pass

        if getattr(self, "scalping_active", False):
            # Cupo Dual: procesa el activo de scalping (ej. ETH/USDT) y también BTC/USDT para el slot macro
            symbols_to_process = [self.scalping_symbol]
            if "BTC/USDT" not in symbols_to_process and is_asset_market_open("BTC/USDT"):
                symbols_to_process.append("BTC/USDT")
        elif self.strategy == "donchian_breakout_1h":
            # Filtro restrictivo: excluir cualquier activo no perteneciente a la lista blanca (ej. SPY, QQQ)
            symbols_to_process = [s for s in symbols_to_process if s in DONCHIAN_WHITELIST_TIMEFRAMES]
            if not symbols_to_process:
                for c_sym in DONCHIAN_CRYPTO_WHITELIST:
                    if is_asset_market_open(c_sym):
                        symbols_to_process.append(c_sym)
        elif not symbols_to_process and self.symbol:
            symbols_to_process.append(self.symbol)

        evaluated_any_symbol = False
        tf_sec_map = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900,
            "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400,
        }

        for active_symbol in symbols_to_process:
            if self._stop_event.is_set():
                break

            # Exclusión categórica para Donchian: rechazar cualquier símbolo fuera de la lista blanca
            if self.strategy == "donchian_breakout_1h" and active_symbol not in DONCHIAN_WHITELIST_TIMEFRAMES:
                continue

            active_pos = next((p for p in open_market_positions if p.get("symbol") == active_symbol), None)
            has_position = active_pos is not None
            entry_price = float(active_pos["entry_price"]) if has_position else 0.0

            # Si el activo actual tiene su mercado cerrado, prohibido operar fuera de rueda (AGENTS.md Reglas 1 y 2):
            is_tradfi_stock = active_symbol in DONCHIAN_TRADFI_WHITELIST
            is_eval_window = is_tradfi_stock and self.is_stocks_evaluation_window()
            if not is_asset_market_open(active_symbol):
                continue

            # Control horario para nuevas entradas en Wall Street: solo dentro de rueda líquida sin blackouts (09:45-15:30 NY)
            if is_tradfi_stock and not has_position and not is_eval_window:
                continue

            # Consultar precio fresco de mercado
            cur_price = entry_price
            try:
                price_info = get_price(active_symbol)
                cur_price = float(price_info.get("price", entry_price))
            except Exception as px_err:
                logger.debug(f"Precio usando fallback para {active_symbol}: {px_err}")

            if cur_price <= 0:
                continue

            # La consulta del navegador es estrictamente solo lectura: nunca suprimir evaluaciones del daemon.

            # Mock request para llamar a get_analysis de forma interna
            scope = {
                "type": "http",
                "method": "GET",
                "path": "/api/market/analysis",
                "query_string": b"",
                "headers": [(b"host", b"127.0.0.1")],
                "client": ("127.0.0.1", 12345),
            }
            fake_request = Request(scope)

            effective_timeframe = self.timeframe
            effective_strategy = self.strategy
            effective_allowed_strats = self.allowed_strategies

            from backend.entry_gate import is_btc
            if getattr(self, "scalping_active", False):
                if active_symbol == self.scalping_symbol:
                    effective_timeframe = getattr(self, "scalping_timeframe", "5m")
                    effective_strategy = getattr(self, "scalping_strategy", "scalping_vwap_2sigma_5m")
                    effective_allowed_strats = [effective_strategy]
                elif is_btc(active_symbol):
                    effective_timeframe = getattr(self, "backup_timeframe", "4h")
                    effective_strategy = getattr(self, "backup_strategy", "donchian_breakout_1h")
                    effective_allowed_strats = [effective_strategy]
            elif self.strategy == "donchian_breakout_1h":
                effective_timeframe = DONCHIAN_WHITELIST_TIMEFRAMES.get(active_symbol, "4h" if "/" in active_symbol else "1d")
                # Excluir de la ejecución automática cualquier temporalidad intradiaria menor (5m, 15m, 1h)
                if effective_timeframe in ("1m", "3m", "5m", "15m", "30m", "1h"):
                    continue
            elif active_symbol in ("NVDA", "AAPL", "MSFT", "TSLA", "SPY", "QQQ"):
                effective_timeframe = "1d"
            elif "/" in active_symbol and self.timeframe == "15m":
                effective_timeframe = "1h"
            elif self.strategy == "auto":
                from backend.estrategias.registry import resolve_auto_strategy, get_strategy
                matched_tf = None
                is_fx_sym = "=X" in active_symbol.upper()
                allowed_objs = [(a_id, get_strategy(a_id)) for a_id in (effective_allowed_strats or [])]
                # Paso 1: priorizar coincidencia exacta con activo_default == active_symbol
                for a_id, st_obj in allowed_objs:
                    if not st_obj:
                        continue
                    def_asset = str(getattr(st_obj, "activo_default", "") or "").upper()
                    if def_asset == active_symbol.upper():
                        ntf = getattr(st_obj, "native_timeframe", None)
                        if ntf in ("15m", "1h", "4h", "1d"):
                            matched_tf = ntf
                            break
                # Paso 2: coincidencia por clase de activo (priorizando Donchian 1D y Squeeze 4H antes que Kula 5M en activos compartidos)
                if matched_tf is None:
                    allowed_ids_set = {a_id for a_id, _ in allowed_objs}
                    from backend.quant_risk import is_micro_futures_symbol as _is_mf_tf
                    if _is_mf_tf(active_symbol):
                        matched_tf = "5m"
                    elif not is_fx_sym and "/" not in active_symbol and "=F" not in active_symbol.upper():
                        if "donchian_breakout_1h" in allowed_ids_set and active_symbol in DONCHIAN_WHITELIST_TIMEFRAMES:
                            matched_tf = DONCHIAN_WHITELIST_TIMEFRAMES[active_symbol]
                        elif "nasdaq_araujo_vwap" in allowed_ids_set:
                            matched_tf = "15m"
                        elif "hyenuk_chu_multibagger" in allowed_ids_set:
                            matched_tf = "1h"
                        elif "kula_balam_cava_ruiz" in allowed_ids_set:
                            matched_tf = "5m"
                    else:
                        for a_id, st_obj in allowed_objs:
                            if not st_obj:
                                continue
                            def_asset = str(getattr(st_obj, "activo_default", "") or "").upper()
                            if is_fx_sym and "=X" in def_asset:
                                matched_tf = getattr(st_obj, "native_timeframe", None)
                                break
                            if not is_fx_sym and "/" in active_symbol and "=X" not in def_asset:
                                ntf = getattr(st_obj, "native_timeframe", None)
                                if ntf in ("1h", "4h", "1d"):
                                    matched_tf = ntf
                                    break
                                if a_id in ("donchian_breakout_1h", "squeeze_dual_eth_4h"):
                                    matched_tf = "4h"
                                    break
                if matched_tf in ("15m", "1h", "4h", "1d"):
                    effective_timeframe = matched_tf
                else:
                    resolved_strat, _ = resolve_auto_strategy(active_symbol, {})
                    if resolved_strat == "nasdaq_araujo_vwap":
                        effective_timeframe = "15m"
                    elif resolved_strat == "hyenuk_chu_multibagger":
                        effective_timeframe = "1h"
                    elif resolved_strat == "mean_reversion_atr" and self.timeframe not in ("15m", "1h"):
                        effective_timeframe = "15m"

            active_side = str(active_pos.get("side") or "LONG").upper() if active_pos else "LONG"
            cand_key = (active_symbol, effective_timeframe)
            eff_tf_sec = tf_sec_map.get(effective_timeframe, 300)
            config_sig = (
                effective_strategy,
                tuple(effective_allowed_strats or []),
                self.engine,
                self.macro or "",
                bool(self.paused_new_entries),
            )
            if not has_position:
                cached_candle = self._evaluated_candles.get(cand_key)
                if (
                    cached_candle
                    and cached_candle.get("config_sig") == config_sig
                    and time.time() < float(cached_candle.get("next_close_due_ts", 0.0))
                ):
                    continue

            from backend.quant_risk import get_asset_friction_costs, is_micro_futures_symbol
            is_micro_fut_entry = is_micro_futures_symbol(active_symbol)
            active_costs = get_asset_friction_costs(active_symbol, price=cur_price)
            active_fee = active_costs["fee_pct"]
            active_spread = active_costs["spread_pct"]
            eff_min_profit = (
                min(float(self.min_profit_pct), 0.12)
                if is_micro_fut_entry
                else (min(float(self.min_profit_pct), 0.20) if ("=X" in active_symbol.upper()) else float(self.min_profit_pct))
            )

            eval_tp_pct = float(active_pos.get("initial_tp_pct") or self.tp) if (has_position and active_pos) else float(self.tp)
            eval_sl_pct = float(active_pos.get("initial_sl_pct") or self.sl) if (has_position and active_pos) else float(self.sl)

            res = get_analysis(
                request=fake_request,
                symbol=active_symbol,
                timeframe=effective_timeframe,
                engine=self.engine,
                model=self.model,
                strategy=effective_strategy,
                allowed_strategies=effective_allowed_strats,
                tp=eval_tp_pct,
                sl=eval_sl_pct,
                risk=float(self.risk),
                sentiment=0.0,
                macro=self.macro or "",
                fee=float(active_fee),
                spread=float(active_spread),
                min_profit_pct=eff_min_profit,
                has_position=has_position,
                entry_price=entry_price,
                position_side=active_side,
                x_api_token=None,
            )

            evaluated_any_symbol = True
            if self._stop_event.is_set():
                return

            if not has_position and isinstance(res, dict):
                res_candle_ts = res.get("signal_candle_ts")
                if isinstance(res_candle_ts, (int, float)) and int(res_candle_ts) > 0:
                    next_due_ts = float(int(res_candle_ts) + (2 * eff_tf_sec) + 2)
                    if next_due_ts > time.time():
                        self._evaluated_candles[cand_key] = {
                            "signal_candle_ts": int(res_candle_ts),
                            "next_close_due_ts": next_due_ts,
                            "config_sig": config_sig,
                        }

            signal = res.get("signal", "MANTENER")
            reason = res.get("reason", "Análisis completado.")

            with self._lock:
                self.cycle_count += 1
                self.last_cycle_ts = time.time()
                # Prioridad de telemetría: evitar que activos secundarios con señal MANTENER
                # sobrescriban SOL/USDT o una señal de entrada/salida activa evaluada en este mismo ciclo
                should_update_status = True
                if signal == "MANTENER":
                    if self.last_active_symbol == "SOL/USDT" and active_symbol != "SOL/USDT":
                        should_update_status = False
                    elif self.last_signal in ("COMPRAR", "SHORT", "VENDER"):
                        should_update_status = False

                if should_update_status:
                    self.last_active_symbol = active_symbol
                    self.last_signal = signal
                    self.last_reason = reason
                self.last_error = None

            logger.info(f"Ciclo #{self.cycle_count} [{active_symbol}]: {signal} - {reason[:80]}")
            self._write_contexto_macro_file(active_symbol, cur_price, res, effective_timeframe=effective_timeframe)

            # Actualizar telemetría de mercado en vivo por símbolo (RSI, ATR)
            ind_dict = res.get("indicators") or {}
            metrics_dict = res.get("strategy_metrics") or {}
            cur_rsi = ind_dict.get("rsi") if ind_dict.get("rsi") is not None else metrics_dict.get("rsi")
            cur_atr = ind_dict.get("atr_14") if ind_dict.get("atr_14") is not None else metrics_dict.get("atr_14")
            self.symbol_indicators[active_symbol] = {
                "rsi": float(cur_rsi) if cur_rsi is not None else 50.0,
                "atr_14": float(cur_atr) if cur_atr is not None else 0.0,
                "atr_pct": (float(cur_atr) / cur_price * 100.0) if (cur_atr and cur_price > 0) else 0.50,
                "ts": time.time(),
            }

            # 5. Ejecución autónoma de órdenes en el Broker
            if signal == "VENDER" and has_position and cur_price > 0:
                if int((active_pos or {}).get("tp1_trimmed") or 0) == 1 and "Objetivo Take Profit alcanzado" in reason:
                    logger.info(
                        f"🚀 [RUNNER SIN TECHO] {active_symbol} ya ejecutó Peluqueo 50% en TP1. "
                        f"El 50% remanente continúa corriendo bajo Trailing Stop / Breakeven Real."
                    )
                else:
                    logger.info(f"📉 [DAEMON VENTA] Señal de salida confirmada para {active_symbol} a ${cur_price}. Liquidando...")
                    self.broker.flatten(active_symbol, current_price=cur_price)
                    self._log_trade_csv(active_symbol, "VENDER", cur_price, float(active_pos.get("qty", 0)), "Ejecutada", f"{self.mode} - Motor")
                    self._arm_cooldown(active_symbol)

            elif signal in ("COMPRAR", "SHORT") and not has_position and cur_price > 0:
                if self.paused_new_entries:
                    logger.info(f"⏸️ [DAEMON PAUSADO] Entrada en {active_symbol} bloqueada por instrucción del operador.")
                    with self._lock:
                        self.last_signal = "PAUSADO"
                        self.last_reason = self.pause_reason or "Apertura de nuevas posiciones pausada por instrucción del operador."
                    continue

                metrics = res.get("strategy_metrics") or {}
                auto_strat = metrics.get("auto_orchestrator", {}).get("selected_strategy")
                effective_strategy = auto_strat or effective_strategy

                current_open = self.broker.fetch_positions()
                book_limits = self._compute_book_slot_limits(current_open, active_symbol, effective_strategy)
                in_drop = book_limits["in_drop"]
                drop_reason = book_limits["drop_reason"]
                book_positions = book_limits["book_positions"]
                has_btc_open = book_limits["has_btc_open"]
                has_alt_open = book_limits["has_alt_open"]
                is_current_btc = (book_limits["currency"] == "USDT") and is_btc(active_symbol)
                dual_slot_pair = book_limits["dual_slot_pair"]
                allowed_slots = book_limits["allowed_book_slots"]

                if len(book_positions) >= allowed_slots or len(current_open) >= self.max_positions:
                    if in_drop and allowed_slots == 1 and len(book_positions) >= allowed_slots:
                        logger.info(
                            f"🛡️ [RIESGO ASIMÉTRICO EN CAÍDAS · {book_limits['currency']}] Límite estricto de exposición activo ({drop_reason}). "
                            f"Máximo 1 sola posición permitida en caídas dentro de bóveda {book_limits['currency']} (salvo Cupo Dual BTC + Activo Táctico). "
                            f"Ya existe {len(book_positions)} posición en {book_limits['currency']} ({[p.get('symbol') for p in book_positions]}). "
                            f"Orden en {active_symbol} bloqueada."
                        )
                        with self._lock:
                            self.last_signal = "MANTENER"
                            self.last_reason = f"Límite de 1 posición en caídas alcanzado en bóveda {book_limits['currency']} ({len(book_positions)}/1 activa: {drop_reason})"
                    else:
                        logger.info(
                            f"🛡️ [DAEMON MULTI-SLOT] Límite de {allowed_slots} posiciones alcanzado (libro {book_limits['currency']}: {len(book_positions)}/{allowed_slots}, total: {len(current_open)}/{self.max_positions}). Orden en {active_symbol} pospuesta."
                        )
                    continue

                sym_cd = self.cooldown_per_symbol.get(active_symbol, 0.0)
                if time.time() < sym_cd:
                    rem_min = max(0.1, (sym_cd - time.time()) / 60.0)
                    logger.info(f"⏳ [DAEMON COOLDOWN] Orden bloqueada en {active_symbol}. Restan {rem_min:.1f} min tras el último cierre.")
                    continue

                if self.mode == "copilot":
                    logger.info(f"🛡️ [DAEMON COPILOTO] Oportunidad ({signal}) detectada en {active_symbol}, en espera de confirmación.")
                    continue

                from backend.quant_risk import (
                    DEMO_VAULT_PROTECTION_FLOOR_USDT,
                    MAX_RISK_PER_TRADE_PCT,
                    calculate_vault_scaled_risk,
                    is_micro_futures_symbol,
                    normalize_order_qty,
                    risk_sized_qty,
                )
                from backend.entry_gate import entry_gate_failures

                is_micro_fut_order = is_micro_futures_symbol(active_symbol)
                currency = "SIM_FUTURES" if is_micro_fut_order else symbol_to_currency(active_symbol)

                if is_micro_fut_order:
                    fut_bal = self.broker.get_futures_balance() if hasattr(self.broker, "get_futures_balance") else 2500.0
                    if fut_bal < 100.0:
                        logger.warning(f"⚠️ Margen virtual insuficiente en SIM_FUTURES (${fut_bal:.2f}).")
                        continue
                    vault_bal = fut_bal
                    total_equity = fut_bal
                    available_for_entry = fut_bal
                else:
                    cb = self.broker.ledger.check_circuit_breaker(currency)
                    if cb.get("halted"):
                        logger.warning(f"🛑 [CIRCUIT BREAKER] Operativa pausada en {currency}: {cb.get('reason')}")
                        continue

                    vault_bal = self.broker.vault_balances.get(currency, 0.0)
                    if vault_bal < 10.0:
                        logger.warning(f"⚠️ Saldo insuficiente en Bóveda {currency} (${vault_bal:.2f}).")
                        continue

                    op_cap = self.broker.get_operating_capital(currency) if hasattr(self.broker, "get_operating_capital") else vault_bal
                    op_bal = float(self.broker.fetch_balances().get(currency, 0.0)) if hasattr(self.broker, "fetch_balances") else 0.0
                    total_equity = vault_bal + op_bal
                    op_avail = max(0.0, round(op_cap - op_bal, 8))
                    available_for_entry = min(vault_bal, op_avail if op_cap > 0 else vault_bal)
                    if available_for_entry < 5.0 and vault_bal < 15.0:
                        logger.warning(
                            f"⚠️ [CUPO OPERATIVO AGOTADO] Disponible en {currency}: ${available_for_entry:.2f} "
                            f"(Cupo=${op_cap:.2f}, En Posiciones=${op_bal:.2f}). Omitiendo entrada en {active_symbol}."
                        )
                        continue

                desired_side = "SHORT" if (signal == "SHORT" or metrics.get("side") == "SHORT" or effective_strategy == "trailing_short_runner") else "LONG"
                same_book_same_side = [
                    p for p in current_open
                    if ("SIM_FUTURES" if is_micro_futures_symbol(str(p.get("symbol", ""))) else symbol_to_currency(str(p.get("symbol", "")))) == currency
                    and ("SHORT" if str(p.get("side", "LONG")).upper() in ("SHORT", "SELL") else "LONG") == desired_side
                ]
                max_correlated = max(2, self.max_positions - 1) if self.max_positions > 2 else self.max_positions
                if len(same_book_same_side) >= max_correlated:
                    logger.info(
                        f"🛡️ [GUARDIÁN CORRELACIÓN] Bloqueada apertura {desired_side} en {active_symbol}: "
                        f"ya existen {len(same_book_same_side)} posiciones {desired_side} correlacionadas en el libro {currency}."
                    )
                    continue

                # Factor de Convicción Centinela (1X estándar, 2X si hay barrido institucional verificado)
                is_sweep = bool(metrics.get("is_institutional_sweep"))
                sweep_conviction = float(metrics.get("conviction_multiplier") or 1.0)
                max_eff_risk = max(MAX_RISK_PER_TRADE_PCT, min(5.0, float(self.risk)))
                effective_risk_factor = min(float(self.risk) * sweep_conviction, max_eff_risk)
                if is_sweep:
                    logger.info(f"🦈 [CENTINELA BONUS] Barrido institucional confirmado en {active_symbol}: escalando convicción a {sweep_conviction:.1f}X (Riesgo: {effective_risk_factor:.2f}%).")

                # Cálculo de niveles TP / SL cuantitativos por estrategia (uniforme para fórmulas modulares y catálogo dinámico)
                if effective_strategy == "mean_reversion_atr":
                    atr = float(metrics.get("atr_14", 0.0))
                    if atr <= 0:
                        logger.warning("Falta ATR válido para quant ATR. Omitiendo compra.")
                        continue
                    sl_dist = 1.5 * atr
                    sl_pct = (sl_dist / cur_price) * 100.0
                    tp_pct = (ATR_TP_ATR_MULTIPLIER * atr / cur_price) * 100.0
                elif (
                    effective_strategy != "manual"
                    and metrics.get("tp_gross_pct") is not None
                    and metrics.get("sl_gross_pct") is not None
                ):
                    tp_pct = float(metrics["tp_gross_pct"])
                    sl_pct = float(metrics["sl_gross_pct"])
                    if (
                        effective_strategy in ("trailing_trend_runner", "trailing_short_runner", "01_tendencia_institucional_15m", "02_cazador_rebotes_atr_15m")
                        and "=X" in active_symbol.upper()
                    ):
                        from backend.quant_risk import required_tp_gross_for_rr
                        fx_atr_pct = (float(cur_atr) / cur_price * 100.0) if (cur_atr and float(cur_atr) > 0 and cur_price > 0) else 0.15
                        sl_pct = round(max(0.12, 1.4 * fx_atr_pct), 2)
                        tp_pct = round(max(required_tp_gross_for_rr(sl_pct, float(active_fee), float(active_spread), 2.0), 3.0 * fx_atr_pct), 2)
                elif effective_strategy in ("scalping_vwap_2sigma_5m", "scalping_m5_rsi3_adx5_ema50", "smc_liquidity_scalper_m5", "triada_fractal_fibo_ema50_5m", "donchian_15m_atr_runner"):
                    tp_pct = float(metrics.get("tp_gross_pct") or 5.5)
                    sl_pct = float(metrics.get("sl_gross_pct") or 0.7)
                elif effective_strategy in ("trailing_trend_runner", "trailing_short_runner", "01_tendencia_institucional_15m", "02_cazador_rebotes_atr_15m"):
                    tp_pct = 6.0 if effective_strategy in ("trailing_trend_runner", "trailing_short_runner") else 3.0
                    sl_pct = 2.0
                    if "=X" in active_symbol.upper() or "cava_fallo_macd_eurusd" in effective_strategy:
                        from backend.quant_risk import required_tp_gross_for_rr
                        fx_atr_pct = (float(cur_atr) / cur_price * 100.0) if (cur_atr and float(cur_atr) > 0 and cur_price > 0) else 0.15
                        sl_pct = round(max(0.12, 1.4 * fx_atr_pct), 2)
                        tp_pct = round(max(required_tp_gross_for_rr(sl_pct, float(active_fee), float(active_spread), 2.0), 3.0 * fx_atr_pct), 2)
                elif (res.get("candlestick_audit") or {}).get("eligible") and (res.get("candlestick_audit") or {}).get("tp_pct") and (res.get("candlestick_audit") or {}).get("sl_pct"):
                    candle_aud = res.get("candlestick_audit") or {}
                    tp_pct = float(candle_aud["tp_pct"])
                    sl_pct = float(candle_aud["sl_pct"])
                else:
                    tp_pct = float(self.tp)
                    sl_pct = float(self.sl)
                    if "=X" in active_symbol.upper() or "cava_fallo_macd_eurusd" in effective_strategy:
                        from backend.quant_risk import required_tp_gross_for_rr
                        fx_atr_pct = (float(cur_atr) / cur_price * 100.0) if (cur_atr and float(cur_atr) > 0 and cur_price > 0) else 0.15
                        sl_pct = round(max(0.12, 1.4 * fx_atr_pct), 2)
                        tp_pct = round(max(required_tp_gross_for_rr(sl_pct, float(active_fee), float(active_spread), 2.0), 3.0 * fx_atr_pct), 2)

                # Cap Máximo de Stop Loss Inicial en Acciones TradFi 1D (max_sl_pct = 4.8%)
                if active_symbol in DONCHIAN_TRADFI_WHITELIST and sl_pct > 4.8:
                    sl_pct = 4.8

                # --- DIMENSIONAMIENTO ESCALADO A BÓVEDA CON TRINQUETE DE SEGURIDAD ---
                if is_micro_fut_order:
                    qty = float(int(metrics.get("contracts") or 2))
                    risk_log_pct = effective_risk_factor
                else:
                    vault_risk_data = calculate_vault_scaled_risk(
                        total_equity,
                        vault_bal,
                        floor_usdt=DEMO_VAULT_PROTECTION_FLOOR_USDT,
                    )
                    vault_risk_usd = vault_risk_data["risk_usd"]
                    if is_sweep:
                        vault_risk_usd = min(25.0, vault_risk_usd * sweep_conviction)

                    # Si opera Cupo Dual (concurrencia BTC + Activo Táctico dentro de USDT), calibra automáticamente el riesgo al 50%
                    is_dual_exposure = (book_limits["currency"] == "USDT") and (
                        dual_slot_pair or (has_btc_open and not is_current_btc) or (has_alt_open and is_current_btc)
                    )
                    if is_dual_exposure:
                        vault_risk_usd = max(1.0, vault_risk_usd * 0.5)
                        effective_risk_factor = max(0.25, effective_risk_factor * 0.5)
                        logger.info(
                            f"⚖️ [CUPO DUAL BLINDADO] Concurrencia BTC + Activo Táctico detectada. "
                            f"Riesgo calibrado al 50% (${vault_risk_usd:.2f} USD / {effective_risk_factor:.2f}%) para evitar correlación compuesta."
                        )

                    # Blindaje proporcional estricto y dimensionamiento por Slot de Bóveda / Riesgo SL
                    if float(self.risk) >= 1.0:
                        vault_risk_usd = max(vault_risk_usd, total_equity * (effective_risk_factor / 100.0))
                    else:
                        vault_risk_usd = min(vault_risk_usd, total_equity * (effective_risk_factor / 100.0))
                    custom_risk_pct = float(getattr(self, "strategy_risk_pcts", {}).get(effective_strategy, 0.0))
                    slot_alloc_cfg = getattr(self, "slot_alloc_pct", None)

                    if custom_risk_pct > 0 or (slot_alloc_cfg is not None and float(slot_alloc_cfg) > 0):
                        if custom_risk_pct > 0:
                            eff_slot_pct = 95.0 if allowed_slots <= 1 else (60.0 if allowed_slots == 2 else round(min(50.0, 140.0 / allowed_slots), 1))
                            target_risk_pct = min(5.0, max(0.1, custom_risk_pct)) * sweep_conviction
                        else:
                            raw_slot = float(slot_alloc_cfg)
                            eff_slot_pct = 95.0 if raw_slot >= 95.0 else min(95.0, max(10.0, raw_slot))
                            # Tope de pérdida en SL de hasta el 10% del slot (ej. $5.00 máx en slot de $250), o el riesgo configurado
                            target_risk_pct = min(5.0, max(float(self.risk), eff_slot_pct * 0.10)) * sweep_conviction
                        if is_dual_exposure:
                            target_risk_pct = max(0.25, target_risk_pct * 0.5)
                        max_slot_alloc = total_equity * (eff_slot_pct / 100.0)
                        safe_avail = available_for_entry / (1.0 + max(0.0, float(active_fee)) / 100.0 + 0.002)
                        trade_alloc = min(max_slot_alloc, safe_avail if safe_avail > 0 else max_slot_alloc)
                        qty_alloc = trade_alloc / cur_price
                        qty_risk = risk_sized_qty(
                            total_equity,
                            cur_price,
                            sl_pct,
                            float(active_fee),
                            float(active_spread),
                            risk_budget_pct=target_risk_pct,
                            max_notional_pct=eff_slot_pct,
                            risk_budget_usd=None,
                        )
                        qty = normalize_order_qty(None, active_symbol, min(qty_alloc, qty_risk), cur_price)
                        risk_log_pct = target_risk_pct
                    else:
                        default_slot_pct = 50.0 if float(self.risk) >= 1.0 else 35.0
                        max_slot_alloc = total_equity * (default_slot_pct / 100.0)
                        trade_alloc = min(max_slot_alloc, available_for_entry if available_for_entry > 0 else max_slot_alloc)
                        qty_alloc = trade_alloc / cur_price
                        qty_risk = risk_sized_qty(
                            total_equity,
                            cur_price,
                            sl_pct,
                            float(active_fee),
                            float(active_spread),
                            risk_budget_pct=effective_risk_factor,
                            max_notional_pct=default_slot_pct,
                            risk_budget_usd=vault_risk_usd,
                        )
                        custom_lot = float(getattr(self, "strategy_lots", {}).get(effective_strategy, 0.0))
                        if custom_lot > 0:
                            qty = normalize_order_qty(None, active_symbol, min(custom_lot, qty_alloc), cur_price)
                        else:
                            qty = normalize_order_qty(None, active_symbol, min(qty_alloc, qty_risk), cur_price)
                        risk_log_pct = effective_risk_factor

                order_side = "SHORT" if (signal == "SHORT" or metrics.get("side") == "SHORT" or effective_strategy == "trailing_short_runner") else "BUY"

                # Segunda barrera determinista con los niveles definitivos (el daemon es la autoridad de ejecución).
                exec_failures = entry_gate_failures(
                    active_symbol,
                    cur_price,
                    tp_pct,
                    sl_pct,
                    float(active_fee),
                    float(active_spread),
                    atr=float(metrics.get("atr_14") or 0.0) or None,
                    rvol=metrics.get("relative_volume"),
                    order_side=order_side,
                    lower_wick_ratio=float(metrics.get("lower_wick_ratio") or 0.0) if metrics.get("lower_wick_ratio") is not None else None,
                    candle_color="RED" if (metrics.get("candle_color") == "RED" or metrics.get("is_bearish_candle")) else None,
                    skip_btc_macro_veto=getattr(self, "scalping_active", False),
                    timeframe=effective_timeframe,
                )
                if exec_failures:
                    logger.info(f"🚧 [COMPUERTA DAEMON] Entrada bloqueada en {active_symbol}: {' | '.join(exec_failures)}")
                    with self._lock:
                        self.last_signal = "MANTENER"
                        self.last_reason = "Compuerta de entrada: " + " | ".join(exec_failures)
                    continue

                if (qty < 1.0) if is_micro_fut_order else (qty * cur_price < 5.0):
                    logger.warning(f"Monto o contratos de orden insuficientes (qty={qty}, precio={cur_price}).")
                    continue

                # Embudo de Arbitraje On-Demand (Árbitro IA / Choque Informativo)
                from backend.arbiter_funnel import arbitrate_signal
                arb_res = arbitrate_signal(
                    symbol=active_symbol,
                    side=order_side,
                    price=cur_price,
                    sl_pct=sl_pct,
                    tp_pct=tp_pct,
                    strategy=effective_strategy,
                    metrics=metrics,
                )
                if arb_res.get("verdict") == "AHORA_NO":
                    arb_reason = str(arb_res.get("reason") or "Veto informativo por alerta crítica / cisne negro.")
                    logger.info(
                        f"🛑 [ÁRBITRO INFORMATIVO] Entrada bloqueada en {active_symbol} ({order_side}): {arb_reason}. "
                        "Registrando en Shadow Testing (Tabla #19) para auditar Drawdown Ahorrado vs. Ganancia Perdida."
                    )
                    sl_px = cur_price * (1.0 + sl_pct / 100.0) if order_side == "SHORT" else cur_price * (1.0 - sl_pct / 100.0)
                    tp_px = cur_price * (1.0 - tp_pct / 100.0) if order_side == "SHORT" else cur_price * (1.0 + tp_pct / 100.0)
                    ledger_ref = getattr(self.broker, "ledger", None)
                    if ledger_ref and hasattr(ledger_ref, "open_shadow_trade"):
                        ledger_ref.open_shadow_trade(
                            symbol=active_symbol,
                            side=order_side,
                            qty=qty,
                            entry_price=cur_price,
                            sl_price=sl_px,
                            tp_price=tp_px,
                            initial_sl_pct=sl_pct,
                            initial_tp_pct=tp_pct,
                            strategy=effective_strategy,
                            arbiter_verdict="AHORA_NO",
                            arbiter_reason=arb_reason,
                            headlines=arb_res.get("headlines"),
                        )
                    with self._lock:
                        self.last_signal = "MANTENER"
                        self.last_reason = f"[Árbitro AHORA_NO] {arb_reason}"
                    continue

                logger.info(
                    f"💰 [DAEMON {order_side}] Abriendo {qty} {active_symbol} a ${cur_price} "
                    f"(Nocional: ${qty * cur_price:.2f} | Riesgo SL: {risk_log_pct:.2f}% | TP: +{tp_pct:.2f}%, SL: -{sl_pct:.2f}%)"
                )
                sub_strat = metrics.get("sub_strategy")
                if sub_strat:
                    formula_desc = f"{sub_strat} (SL -{sl_pct:.1f}%)"
                elif effective_strategy in ("scalping_vwap_2sigma_5m", "scalping_m5_rsi3_adx5_ema50", "smc_liquidity_scalper_m5", "triada_fractal_fibo_ema50_5m", "donchian_15m_atr_runner"):
                    formula_desc = f"{effective_strategy}_{order_side.lower()} (SL -{sl_pct:.2f}%, TP +{tp_pct:.2f}%)"
                elif effective_strategy == "alex_ruiz_triada_3velas":
                    formula_desc = f"triada_3velas_{order_side.lower()} (SL -{sl_pct:.1f}%)"
                elif effective_strategy == "kula_balam_cava_ruiz":
                    formula_desc = f"cava_ruiz_{order_side.lower()} (SL -{sl_pct:.1f}%)"
                elif effective_strategy == "trailing_trend_runner":
                    formula_desc = "trailing_escalon_runner"
                elif effective_strategy == "trailing_short_runner":
                    formula_desc = "trailing_escalon_short"
                elif effective_strategy in ("01_tendencia_institucional_15m", "02_cazador_rebotes_atr_15m"):
                    formula_desc = f"{effective_strategy} (R:R 1:2.3)"
                elif effective_strategy == "nasdaq_araujo_vwap":
                    formula_desc = "vwap_rebound_londres"
                elif effective_strategy == "hyenuk_chu_multibagger":
                    formula_desc = "hyenuk_vela_elefante"
                elif effective_strategy == "triple_confluencia_4h":
                    formula_desc = f"triple_confluencia_4h_{order_side.lower()} (SL -{sl_pct:.1f}%)"
                elif effective_strategy == "donchian_breakout_1h":
                    formula_desc = f"donchian_breakout_1h_{order_side.lower()} (SL -{sl_pct:.1f}%)"
                elif (res.get("candlestick_audit") or {}).get("eligible"):
                    candle_patt = (res.get("candlestick_audit") or {}).get("pattern") or "Confluencia Velas"
                    formula_desc = f"bulkowski_{candle_patt.lower().replace(' ', '_')} (SL -{sl_pct:.1f}%)"
                else:
                    formula_desc = f"smart_risk_parity_{order_side.lower()} (SL -{sl_pct:.1f}%)"

                self.broker.place_entry(
                    active_symbol,
                    order_side,
                    qty=qty,
                    price=cur_price,
                    initial_tp_pct=tp_pct,
                    initial_sl_pct=sl_pct,
                    strategy=effective_strategy,
                    engine=self.engine or "antigravity_operador",
                    formula=formula_desc,
                )
                if order_side == "SHORT":
                    sl_px = cur_price * (1.0 + sl_pct / 100.0)
                    tp_px = cur_price * (1.0 - tp_pct / 100.0)
                else:
                    sl_px = cur_price * (1.0 - sl_pct / 100.0)
                    tp_px = cur_price * (1.0 + tp_pct / 100.0)
                self.broker.place_protection(active_symbol, qty=qty, stop_loss_price=sl_px, take_profit_price=tp_px, side=order_side)
                self._log_trade_csv(active_symbol, order_side, cur_price, qty, "Ejecutada", f"{effective_strategy} ({self.engine})")
                try:
                    from backend.telegram_notifier import notify_trade_opened
                    notify_trade_opened(
                        symbol=active_symbol,
                        side=order_side,
                        price=cur_price,
                        qty=qty,
                        cost_basis=round(qty * cur_price, 2),
                        sl_pct=sl_pct,
                        tp_pct=tp_pct,
                        strategy=effective_strategy,
                        formula=formula_desc,
                    )
                except Exception as _e_tg:
                    logger.warning(f"Error al enviar notificación Telegram apertura: {_e_tg}")
                if self.mode == "smart" and self.symbol != active_symbol:
                    logger.info(f"⚡ [MODO INTELIGENTE] Auto-ruteando hacia activo con posición abierta: {active_symbol}")
                    self.symbol = active_symbol
                if active_symbol == self.radar_candidate_symbol:
                    self.radar_candidate_symbol = None

        if not evaluated_any_symbol:
            with self._lock:
                self.last_cycle_ts = time.time()
                self.last_error = None
                if self.cycle_count == 0:
                    self.cycle_count = 1

    def _tracked_timeframes(self) -> List[int]:
        """Devuelve las duraciones en segundos de temporalidades activas monitoreadas por el daemon."""
        tf_sec_map = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900,
            "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400,
        }
        secs = set()
        if self.timeframe in tf_sec_map:
            secs.add(tf_sec_map[self.timeframe])
        if getattr(self, "scalping_active", False):
            stf = getattr(self, "scalping_timeframe", "5m")
            if stf in tf_sec_map:
                secs.add(tf_sec_map[stf])
        if self.strategy == "donchian_breakout_1h":
            secs.add(14400)
            secs.add(86400)
        elif self.strategy == "auto":
            try:
                from backend.estrategias.registry import get_strategy
                for a_id in (self.allowed_strategies or []):
                    st_obj = get_strategy(a_id)
                    ntf = getattr(st_obj, "native_timeframe", None) if st_obj else None
                    if ntf in tf_sec_map:
                        secs.add(tf_sec_map[ntf])
            except Exception:
                pass
        if not secs:
            secs.add(300)
        return sorted(secs)

    def _compute_next_wakeup_delay(self, has_open_positions: bool, now_ts: Optional[float] = None) -> float:
        """
        Calcula la espera exacta hasta el próximo pulso de protección o cierre de vela + 3s de asentamiento.
        - Con posiciones abiertas: chequeo SL/BE/Trailing cada <= 5s.
        - Sin posiciones: latido <= 15s, aterrizando exactamente ~3s tras el cierre de vela más próximo.
        """
        now = float(now_ts if now_ts is not None else time.time())
        max_heartbeat = 5.0 if has_open_positions else 15.0
        min_boundary_wait = max_heartbeat
        settle_grace_s = 3.0
        for tf_sec in self._tracked_timeframes():
            bucket_start = (int(now) // tf_sec) * tf_sec
            current_settle = float(bucket_start) + settle_grace_s
            target_ts = current_settle if now < current_settle else (float(bucket_start + tf_sec) + settle_grace_s)
            delta = max(0.5, target_ts - now)
            if delta < min_boundary_wait:
                min_boundary_wait = delta
        return min(max_heartbeat, min_boundary_wait)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.is_running:
                    # _execute_cycle() ya invoca _check_open_positions_protections al inicio del ciclo
                    self._execute_cycle()
                else:
                    open_positions = self.broker.fetch_positions()
                    if open_positions:
                        self._check_open_positions_protections(open_positions)
                    else:
                        logger.info("🛡️ [GUARDIÁN SL/TP] Sin posiciones abiertas pendientes y agente detenido. Finalizando hilo guardián.")
                        break
            except Exception as e:
                logger.error(f"Error en TraderDaemon: {e}")
                with self._lock:
                    self.last_error = str(e)

            # Auto-chequeo determinista Watchdog cada 15 min (0 tokens, sin llamadas a LLM)
            try:
                from backend.health_watchdog import get_health_watchdog, WATCHDOG_PROBE_INTERVAL_S
                now_wd = time.time()
                if self.is_running and self.cycle_count >= 1 and (now_wd - self._last_watchdog_ts) >= WATCHDOG_PROBE_INTERVAL_S:
                    self._last_watchdog_ts = now_wd
                    get_health_watchdog().evaluate(self, force_probe=True, notify_on_red=True)
            except Exception as _e_wd:
                logger.debug(f"Aviso en ciclo watchdog determinista: {_e_wd}")

            # Relojito sincronizado al cierre exacto de vela (+3s asentamiento) con pulso rápido (<= 5s) si hay posiciones
            try:
                open_now = bool(self.broker.fetch_positions())
            except Exception:
                open_now = False
            delay_s = self._compute_next_wakeup_delay(has_open_positions=open_now)
            self._next_wakeup_ts = time.time() + delay_s
            deadline = time.monotonic() + delay_s
            while not self._stop_event.is_set():
                rem = deadline - time.monotonic()
                if rem <= 0:
                    break
                time.sleep(min(0.5, rem))

        with self._lock:
            self._thread = None


# Instancia única singleton del daemon
_daemon_instance: Optional[TraderDaemon] = None
_daemon_lock = threading.Lock()


def get_trader_daemon() -> TraderDaemon:
    global _daemon_instance
    with _daemon_lock:
        if _daemon_instance is None:
            _daemon_instance = TraderDaemon()
        return _daemon_instance
