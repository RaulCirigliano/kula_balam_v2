"""
===============================================================================
TEST SUITE: NOTIFICADOR TELEGRAM DE KULA · BALAM
===============================================================================
Verifica la supresión de envíos en entorno de tests, y la correcta construcción
y formato cuantitativo de las alertas operativas (aperturas, peluqueo, cierres).
===============================================================================
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from backend.telegram_notifier import (
    notify_checkpoint,
    notify_trade_closed,
    notify_trade_opened,
    notify_trade_peluqueo,
    send_telegram_message,
)


class TestTelegramNotifier(unittest.TestCase):
    def test_pytest_environment_silence(self):
        """Verifica que si PYTEST_CURRENT_TEST está activo, nunca intente enviar por red."""
        with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "true"}):
            result = send_telegram_message("Test message")
            self.assertFalse(result)

    @patch("backend.telegram_notifier.get_telegram_credentials")
    @patch("urllib.request.urlopen")
    def test_send_telegram_message_success(self, mock_urlopen, mock_creds):
        """Verifica el envío mockeado cuando hay credenciales válidas fuera de pytest."""
        mock_creds.return_value = ("fake_token_123", "fake_chat_456")
        
        # Simular respuesta exitosa de la API de Telegram
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True}).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        # Desactivar temporalmente variable de test
        with patch.dict(os.environ, {}, clear=True):
            ok = send_telegram_message("<b>Prueba</b>")
            self.assertTrue(ok)
            self.assertTrue(mock_urlopen.called)

    @patch("backend.telegram_notifier.send_telegram_message")
    def test_notify_trade_opened_format(self, mock_send):
        """Verifica que notify_trade_opened incluya 'Capital Invertido' y estado EN CURSO."""
        mock_send.return_value = True
        
        notify_trade_opened(
            symbol="BTC/USDT",
            side="BUY",
            price=50500.0,
            qty=0.00076363,
            cost_basis=38.56,
            sl_pct=1.0,
            tp_pct=2.5,
            strategy="nasdaq_araujo_vwap",
            formula="vwap_rebound_londres",
        )
        self.assertTrue(mock_send.called)
        msg = mock_send.call_args[0][0]
        self.assertIn("NUEVA POSICIÓN ABIERTA (EN CURSO)", msg)
        self.assertIn("LONG (COMPRA)", msg)
        self.assertIn("BTC/USDT", msg)
        self.assertIn("Capital Invertido:", msg)
        self.assertIn("$38.56 USDT", msg)
        self.assertNotIn("Nocional:", msg)  # Confirmar eliminación de término confuso

    @patch("backend.telegram_notifier.send_telegram_message")
    def test_notify_trade_peluqueo_format(self, mock_send):
        """Verifica que notify_trade_peluqueo aclare que NO es un rechazo y detalle bóveda."""
        mock_send.return_value = True

        notify_trade_peluqueo(
            symbol="BTC/USDT",
            price=102.50,
            trimmed_qty=0.13927,
            remaining_qty=0.13927,
            pnl_secured=0.3481,
            swept_to_vault=14.62,
            trigger_desc="TP1 alcanzado (+2.00%)",
            operational_balance=100.0,
            vault_balance=895.70,
        )
        self.assertTrue(mock_send.called)
        msg = mock_send.call_args[0][0]
        self.assertIn("50% GANANCIA ASEGURADA A BÓVEDA", msg)
        self.assertIn("La orden NO fue rechazada", msg)
        self.assertIn("Ganancia Neta Asegurada:", msg)
        self.assertIn("+$0.3481 USDT", msg)
        self.assertIn("Bóveda Asegurada: <code>$895.70 USDT</code>", msg)
        self.assertIn("Operativo: <code>$100.00 USDT</code>", msg)

    @patch("backend.telegram_notifier.send_telegram_message")
    def test_notify_trade_closed_loss(self, mock_send):
        """Verifica que notify_trade_closed para pérdidas informe capital original y saldos."""
        mock_send.return_value = True

        notify_trade_closed(
            symbol="SOL/USDT",
            side="LONG",
            entry_price=50.0,
            exit_price=48.0,
            pnl=-4.196,
            fees=0.10,
            exit_reason="Stop Loss",
            strategy="trailing_trend_runner",
            cost_basis=100.0,
            operational_balance=95.80,
            vault_balance=895.70,
        )
        self.assertTrue(mock_send.called)
        msg = mock_send.call_args[0][0]
        self.assertIn("OPERACIÓN CERRADA CON PÉRDIDA", msg)
        self.assertIn("Capital Invertido Original:", msg)
        self.assertIn("$100.00 USDT", msg)
        self.assertIn("$-4.1960 USDT", msg)
        self.assertIn("Bóveda Asegurada:", msg)
        self.assertIn("Operativo:", msg)

    @patch("backend.telegram_notifier.send_telegram_message")
    def test_notify_trade_closed_profit(self, mock_send):
        """Verifica que notify_trade_closed para ganancias informe con badge positivo."""
        mock_send.return_value = True

        notify_trade_closed(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            exit_price=51500.0,
            pnl=14.85,
            fees=0.15,
            exit_reason="Take Profit",
            strategy="alex_ruiz_triada_3velas",
            cost_basis=500.0,
            operational_balance=114.85,
            vault_balance=895.70,
        )
        self.assertTrue(mock_send.called)
        msg = mock_send.call_args[0][0]
        self.assertIn("OPERACIÓN CERRADA CON GANANCIA", msg)
        self.assertIn("<b>Capital Invertido Original:</b> $500.00 USDT", msg)
        self.assertIn("+3.00%", msg)
        self.assertNotIn("++", msg)
        self.assertIn("+$14.8500 USDT", msg)
        self.assertIn("Ganancia neta acreditada", msg)
        self.assertIn("Bóveda Asegurada:", msg)


if __name__ == "__main__":
    unittest.main()
