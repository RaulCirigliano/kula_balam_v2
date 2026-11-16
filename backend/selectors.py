"""
Módulo: backend/selectors.py
Proyecto: Kula Balam
Selector Dinámico de Momentum Relativo para Slot Cripto (ETH vs SOL) con regla de persistencia.
"""

import pandas as pd


def compute_relative_strength_7d(eth_close: pd.Series, sol_close: pd.Series, lookback: int = 168) -> float:
    """
    Calcula la Fuerza Relativa (RS) a 7 días (168 períodos en 1H) entre SOL y ETH:
    RS = Return_7D(SOL) / Return_7D(ETH)
    """
    if len(eth_close) <= lookback or len(sol_close) <= lookback:
        raise ValueError("Longitud insuficiente para calcular retorno a 168 períodos (7D).")
        
    ret_eth = (eth_close.iloc[-1] / eth_close.iloc[-lookback - 1]) - 1.0
    ret_sol = (sol_close.iloc[-1] / sol_close.iloc[-lookback - 1]) - 1.0
    
    if ret_eth == 0.0:
        return float('inf') if ret_sol > 0 else float('-inf')
        
    return float(ret_sol / ret_eth)


def select_crypto_slot(
    eth_close: pd.Series,
    sol_close: pd.Series,
    has_open_position: bool = False,
    current_symbol: str = "ETH/USDT",
    threshold: float = 1.10
) -> str:
    """
    Selector de slot cripto con persistencia de posición abierta.
    - Si existe una posición activa (has_open_position=True): Bloquea la rotación y preserva current_symbol.
    - Si no hay posición activa:
      * Si RS > 1.10 -> Retorna 'SOL/USDT'
      * Si RS <= 1.10 -> Retorna 'ETH/USDT'
    """
    if has_open_position:
        return current_symbol
        
    rs = compute_relative_strength_7d(eth_close, sol_close, lookback=168)
    if rs > threshold:
        return "SOL/USDT"
    return "ETH/USDT"
