"""
===============================================================================
MÓDULO DE NOTIFICACIONES TELEGRAM PARA KULA · BALAM
===============================================================================
Permite enviar alertas operativas en tiempo real, notificaciones de checkpoints,
ejecuciones de órdenes y vetos de riesgo directamente al teléfono del operador.
Usa urllib.request de la biblioteca estándar para evitar dependencias externas.
===============================================================================
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger("telegram_notifier")

_ENV_LOADED = False


def _ensure_env():
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k not in os.environ:
                        os.environ[k] = v
    _ENV_LOADED = True


def get_telegram_credentials() -> tuple[Optional[str], Optional[str]]:
    _ensure_env()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    return token, chat_id


def send_telegram_message(text: str, parse_mode: Optional[str] = "HTML") -> bool:
    """
    Envía un mensaje a Telegram.
    Soporta HTML o Markdown. Por defecto HTML para evitar errores de escape.
    Silencia automáticamente durante la ejecución de pruebas (pytest).
    """
    if "PYTEST_CURRENT_TEST" in os.environ or os.getenv("TESTING") == "1":
        logger.debug("Silenciando notificación Telegram: entorno de pruebas (pytest) detectado.")
        return False

    token, chat_id = get_telegram_credentials()
    if not token or not chat_id:
        logger.debug("Telegram no configurado: falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return bool(res_data.get("ok"))
    except Exception as e:
        logger.warning(f"Error enviando mensaje a Telegram: {e}")
        return False


def notify_trade_opened(
    symbol: str,
    side: str,
    price: float,
    qty: float,
    cost_basis: float,
    sl_pct: float,
    tp_pct: float,
    strategy: str,
    formula: Optional[str] = None,
) -> bool:
    """Notifica apertura de posición con niveles cuantitativos y capital invertido."""
    is_long = side.upper() in ("BUY", "LONG")
    side_icon = "🟢 LONG (COMPRA)" if is_long else "🔴 SHORT (VENTA)"
    msg = (
        f"<b>🚀 NUEVA POSICIÓN ABIERTA (EN CURSO)</b>\n\n"
        f"<b>Dirección:</b> <b>{side_icon}</b>\n"
        f"<b>Activo:</b> <code>{symbol}</code>\n"
        f"<b>Precio Entrada:</b> ${price:,.4f}\n"
        f"<b>Capital Invertido:</b> <b>${cost_basis:,.2f} USDT</b> (Cantidad: {qty})\n"
        f"<b>Stop Loss:</b> -{sl_pct:.2f}% (Stop a Misa + 2 ticks)\n"
        f"<b>Take Profit 1:</b> +{tp_pct:.2f}% (Peluqueo 50%)\n"
        f"<b>Estrategia:</b> <code>{strategy}</code>\n"
    )
    if formula:
        msg += f"<b>Gatillo:</b> <i>{formula}</i>\n"
    msg += "\n<i>Operación iniciada. Los resultados y saldos contables se actualizarán al cierre o toma parcial.</i>\n"
    return send_telegram_message(msg)


def notify_trade_peluqueo(
    symbol: str,
    price: float,
    trimmed_qty: float,
    remaining_qty: float,
    pnl_secured: float,
    swept_to_vault: float,
    trigger_desc: str,
    operational_balance: Optional[float] = None,
    vault_balance: Optional[float] = None,
) -> bool:
    """Notifica la ejecución de un Peluqueo 50% (Toma parcial asegurada a Bóveda + Breakeven en remanente)."""
    msg = (
        f"<b>✂️ 50% GANANCIA ASEGURADA A BÓVEDA (RIESGO CERO)</b>\n\n"
        f"<i>Nota operativa: La orden NO fue rechazada. Se ejecutó la toma del 50% en objetivo y se blindó la ganancia en Bóveda. "
        f"El 50% restante continúa activo en el mercado con Stop Loss en Breakeven (Riesgo Cero).</i>\n\n"
        f"<b>Activo:</b> <code>{symbol}</code>\n"
        f"<b>Precio Ejecución:</b> ${price:,.4f}\n"
        f"<b>Motivo Gatillo:</b> {trigger_desc}\n"
        f"<b>Cantidad Liquidada:</b> {trimmed_qty} (50% de la posición)\n"
        f"<b>Remanente en Mercado:</b> {remaining_qty} (Riesgo $0 / Breakeven)\n"
        f"<b>Ganancia Neta Asegurada:</b> <b>+${pnl_secured:,.4f} USDT</b>\n"
    )
    if swept_to_vault > 0.0:
        msg += f"<b>Transferido a Bóveda:</b> <code>+${swept_to_vault:,.2f} USDT</code>\n"

    if operational_balance is not None or vault_balance is not None:
        msg += "\n<b>🏦 Saldo Contable Actual:</b>\n"
        if operational_balance is not None:
            msg += f"• Operativo: <code>${operational_balance:,.2f} USDT</code>\n"
        if vault_balance is not None:
            msg += f"• Bóveda Asegurada: <code>${vault_balance:,.2f} USDT</code>\n"

    return send_telegram_message(msg)


def notify_trade_closed(
    symbol: str,
    side: str,
    entry_price: float,
    exit_price: float,
    pnl: float,
    fees: float,
    exit_reason: str,
    strategy: str,
    cost_basis: Optional[float] = None,
    operational_balance: Optional[float] = None,
    vault_balance: Optional[float] = None,
) -> bool:
    """Notifica cierre definitivo de una operación con resultado (ganancia/pérdida), capital y saldo contable."""
    is_positive = pnl >= 0.0
    sign = "+" if is_positive else ""
    header_badge = "🟢 OPERACIÓN CERRADA CON GANANCIA" if is_positive else "🔴 OPERACIÓN CERRADA CON PÉRDIDA"
    verdict_desc = "Ganancia neta acreditada" if is_positive else "Pérdida neta final deducida"

    # Cálculo de rendimiento porcentual bruto
    pnl_pct = 0.0
    if entry_price > 0:
        if side.upper() in ("SHORT", "SELL"):
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100.0
        else:
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100.0

    side_label = "LONG (COMPRA)" if side.upper() in ("LONG", "BUY") else "SHORT (VENTA)"

    msg = (
        f"<b>{header_badge}</b>\n\n"
        f"<b>Activo:</b> <code>{symbol}</code> ({side_label})\n"
        f"<b>Entrada:</b> ${entry_price:,.4f} ➡️ <b>Salida:</b> ${exit_price:,.4f}\n"
    )
    if cost_basis is not None and cost_basis > 0:
        msg += f"<b>Capital Invertido Original:</b> ${cost_basis:,.2f} USDT\n"

    msg += (
        f"<b>Rendimiento:</b> <code>{pnl_pct:+.2f}%</code>\n"
        f"<b>Resultado Neto:</b> <b>{sign}${pnl:,.4f} USDT</b> ({verdict_desc})\n"
        f"<b>Comisiones Pagadas:</b> ${fees:,.4f} USDT\n"
        f"<b>Motivo de Salida:</b> <i>{exit_reason}</i>\n"
        f"<b>Estrategia Ejecutora:</b> <code>{strategy}</code>\n"
    )

    if operational_balance is not None or vault_balance is not None:
        msg += "\n<b>🏦 Saldo Contable Actual:</b>\n"
        if operational_balance is not None:
            msg += f"• Operativo: <code>${operational_balance:,.2f} USDT</code>\n"
        if vault_balance is not None:
            msg += f"• Bóveda Asegurada: <code>${vault_balance:,.2f} USDT</code>\n"

    return send_telegram_message(msg)


def notify_checkpoint(
    checkpoint_id: str,
    title: str,
    summary: str,
    metrics: Optional[Dict[str, Any]] = None,
) -> bool:
    """Envía un informe de checkpoint operativo a Telegram."""
    msg = (
        f"<b>📊 CHECKPOINT DE AUDITORÍA · {checkpoint_id}</b>\n"
        f"<b>{title}</b>\n\n"
        f"{summary}\n"
    )
    if metrics:
        msg += "\n<b>Métricas de Control:</b>\n"
        for k, v in metrics.items():
            msg += f"• <b>{k}:</b> <code>{v}</code>\n"
    return send_telegram_message(msg)


def notify_watchdog_alert(
    component: str,
    title: str,
    detail: str,
    remediation: str = "",
) -> bool:
    """Envía alerta de Watchdog determinista (0 tokens) ante transición a estado ROJO."""
    msg = (
        f"<b>🚨 ALERTA WATCHDOG KULA · {component}</b>\n"
        f"<b>Estado:</b> {title}\n\n"
        f"<b>Diagnóstico:</b> {detail}\n"
    )
    if remediation:
        msg += f"<b>Acción sugerida:</b> <i>{remediation}</i>\n"
    return send_telegram_message(msg)
