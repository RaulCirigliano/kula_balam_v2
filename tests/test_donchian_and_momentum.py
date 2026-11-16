"""
Módulo: tests/test_donchian_and_momentum.py
Batería de pruebas unitarias para el filtro de Bandwidth Donchian y el selector de momentum relativo (RS).
"""

import pytest
import pandas as pd
from backend.indicators import compute_bandwidth, check_bandwidth_expansion_filter
from backend.selectors import compute_relative_strength_7d, select_crypto_slot


# =====================================================================
# BATERÍA 1: TEST DE FILTRO DE BANDWIDTH (DONCHIAN 1H)
# =====================================================================

class TestDonchianBandwidthFilter:
    
    def test_bandwidth_formula_exactness(self):
        """Valida la precisión del cálculo aritmético del bandwidth con datos controlados."""
        # 23 velas en rango [90, 100], vela 24 extiende a high=110, low=85
        # Donchian High(24) = 110.0, Low(24) = 85.0 -> Rango = 25.0
        # EMA(24) sobre serie constante de 100.0 = 100.0
        # Bandwidth esperado = 25.0 / 100.0 = 0.25
        data = {
            'high': [100.0] * 23 + [110.0],
            'low': [90.0] * 23 + [85.0],
            'close': [100.0] * 24
        }
        df = pd.DataFrame(data)
        bw = compute_bandwidth(df, period_entry=24)
        
        assert bw.iloc[-1] == pytest.approx(0.25, rel=1e-5)

    def test_bandwidth_filter_blocks_on_compression(self):
        """Valida que el filtro bloquee (False) en régimen lateral / compresión de volatilidad."""
        # Primeras 80 velas de alta volatilidad (rango 30), seguidas de 40 velas muertas (rango 4)
        highs = [120.0] * 80 + [102.0] * 40
        lows = [90.0] * 80 + [98.0] * 40
        closes = [105.0] * 80 + [100.0] * 40
        
        df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})
        is_expanding = check_bandwidth_expansion_filter(df, period_entry=24, sma_period=48)
        
        assert is_expanding is False

    def test_bandwidth_filter_approves_on_expansion(self):
        """Valida que el filtro apruebe (True) en rompimiento con expansión genuina."""
        # Primeras 100 velas planas (rango 2), últimas 20 rompiendo con rango 45
        highs = [101.0] * 100 + [140.0] * 20
        lows = [99.0] * 100 + [95.0] * 20
        closes = [100.0] * 100 + [138.0] * 20
        
        df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})
        is_expanding = check_bandwidth_expansion_filter(df, period_entry=24, sma_period=48)
        
        assert is_expanding is True

    def test_bandwidth_insufficient_history(self):
        """Valida que ante historial menor al calentamiento (entry + sma) devuelva False de forma segura."""
        df_short = pd.DataFrame({
            'high': [100.0] * 30,
            'low': [95.0] * 30,
            'close': [98.0] * 30
        })
        assert check_bandwidth_expansion_filter(df_short, period_entry=24, sma_period=48) is False


# =====================================================================
# BATERÍA 2: TEST DE MOMENTUM RELATIVO (RS) Y SELECTOR DE SLOT
# =====================================================================

class TestRelativeStrengthAndSlotSelector:

    def test_rs_calculation_accuracy(self):
        """Valida el cálculo del ratio de retornos a 168 períodos (7 días)."""
        # ETH pasa de 1000 a 1100 (+10.0%)
        # SOL pasa de 100 a 120 (+20.0%)
        # RS = 0.20 / 0.10 = 2.0
        n = 170
        eth_prices = [1000.0] * n
        eth_prices[-1] = 1100.0
        sol_prices = [100.0] * n
        sol_prices[-1] = 120.0
        
        eth_close = pd.Series(eth_prices)
        sol_close = pd.Series(sol_prices)
        
        rs = compute_relative_strength_7d(eth_close, sol_close, lookback=168)
        assert rs == pytest.approx(2.0, rel=1e-5)

    def test_slot_selection_rotates_to_sol_when_rs_exceeds_threshold(self):
        """Si RS > 1.10 y no hay posición activa, debe seleccionar SOL/USDT."""
        n = 170
        eth_prices = [1000.0] * n
        eth_prices[-1] = 1050.0  # +5%
        sol_prices = [100.0] * n
        sol_prices[-1] = 110.0   # +10% -> RS = 2.0 > 1.10
        
        selected = select_crypto_slot(
            pd.Series(eth_prices),
            pd.Series(sol_prices),
            has_open_position=False,
            current_symbol="ETH/USDT",
            threshold=1.10
        )
        assert selected == "SOL/USDT"

    def test_slot_selection_retains_eth_when_rs_below_threshold(self):
        """Si RS <= 1.10, debe mantener el patrullaje en ETH/USDT."""
        n = 170
        eth_prices = [1000.0] * n
        eth_prices[-1] = 1100.0  # +10%
        sol_prices = [100.0] * n
        sol_prices[-1] = 108.0   # +8% -> RS = 0.80 <= 1.10
        
        selected = select_crypto_slot(
            pd.Series(eth_prices),
            pd.Series(sol_prices),
            has_open_position=False,
            current_symbol="ETH/USDT",
            threshold=1.10
        )
        assert selected == "ETH/USDT"

    def test_slot_selection_locks_when_position_is_open(self):
        """Regla crítica de persistencia: si hay posición abierta, NO rota aunque RS sea masivo."""
        n = 170
        eth_prices = [1000.0] * n
        eth_prices[-1] = 1020.0  # +2%
        sol_prices = [100.0] * n
        sol_prices[-1] = 130.0   # +30% -> RS = 15.0 >> 1.10
        
        # Posición activa en ETH/USDT
        selected = select_crypto_slot(
            pd.Series(eth_prices),
            pd.Series(sol_prices),
            has_open_position=True,
            current_symbol="ETH/USDT",
            threshold=1.10
        )
        # Debe blindar la posición y no cambiar el ticker patrullado
        assert selected == "ETH/USDT"
