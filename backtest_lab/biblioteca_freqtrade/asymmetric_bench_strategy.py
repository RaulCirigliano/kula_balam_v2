# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
import talib.abstract as ta
from technical import qtpylib


class AsymmetricBenchStrategy(IStrategy):
    """
    Estrategia Cuantitativa de Benchmark con Asimetría Matemática R:R >= 1:2.
    Diseñada por algo-benchmark-auditor para contrastar con trading_ollama y monitor del mercado.
    """
    INTERFACE_VERSION = 3

    # Operativa Spot en Binance
    can_short: bool = False
    timeframe = "5m"

    # Reglas Estrictas de Asimetría R:R >= 1:2
    stoploss = -0.02  # Riesgo máximo 2%
    minimal_roi = {
        "0": 0.04,   # Objetivo inicial +4% (Ratio 1:2 exacto)
        "30": 0.03,  # Protección +3% tras 30 minutos
        "60": 0.02   # Asegurar +2% tras 60 minutos
    }

    # Trailing Stop Dinámico
    trailing_stop = True
    trailing_stop_positive = 0.01          # Trailing a 1.0% de distancia
    trailing_stop_positive_offset = 0.015   # Se activa al superar +1.5%
    trailing_only_offset_is_reached = True

    # Parámetros de ejecución
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Medias Exponenciales (Tendencia)
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)

        # Momento y Volatilidad (ATR14 y RSI14)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # Filtro de Liquidez / Volumen
        dataframe['volume_mean_20'] = dataframe['volume'].rolling(window=20).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # Tendencia alcista clara
                (dataframe['close'] > dataframe['ema20']) &
                (dataframe['ema20'] > dataframe['ema50']) &
                # Pullback con momento recuperándose (RSI entre 35 y 65)
                (dataframe['rsi'] > 45) &
                (dataframe['rsi'] < 65) &
                # Confirmación de volumen institucional
                (dataframe['volume'] > dataframe['volume_mean_20']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # Salida por pérdida de tendencia o agotamiento extremo
                (dataframe['close'] < dataframe['ema20']) |
                (dataframe['rsi'] > 80)
            ),
            'exit_long'] = 1

        return dataframe
