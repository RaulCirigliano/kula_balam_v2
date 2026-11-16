# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
import talib.abstract as ta
from technical import qtpylib


class BbandRsiStrategy(IStrategy):
    """
    Estrategia Freqtrade de Reversión a la Media en Bandas Bollinger con Sobreventa RSI.
    """
    INTERFACE_VERSION = 3
    can_short: bool = False
    timeframe = "1h"

    stoploss = -0.025  # SL 2.5%
    minimal_roi = {
        "0": 0.055    # TP 5.5% (R:R 1:2.20)
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bandas Bollinger
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        # RSI y Media móvil de volumen
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['volume_mean_20'] = dataframe['volume'].rolling(window=20).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['close'] <= dataframe['bb_lowerband']) &
                (dataframe['rsi'] < 35) &
                (dataframe['volume'] > dataframe['volume_mean_20'])
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['close'] >= dataframe['bb_middleband']) |
                (dataframe['rsi'] > 70)
            ),
            'exit_long'] = 1

        return dataframe
