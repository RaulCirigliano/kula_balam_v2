# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
import talib.abstract as ta
from technical import qtpylib


class TurtleDonchianStrategy(IStrategy):
    """
    Estrategia Freqtrade de Ruptura Tendencial Estilo Tortugas Donchian 30 periodos.
    """
    INTERFACE_VERSION = 3
    can_short: bool = False
    timeframe = "4h"

    stoploss = -0.035  # SL 3.5%
    minimal_roi = {
        "0": 0.084    # TP 8.4% (R:R 1:2.40)
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Donchian High / Low 30 periodos
        dataframe['donchian_high'] = dataframe['high'].rolling(30).max()
        dataframe['donchian_low'] = dataframe['low'].rolling(30).min()
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['volume_mean_20'] = dataframe['volume'].rolling(window=20).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['donchian_high'].shift(1)) &
                (dataframe['close'] > dataframe['ema200']) &
                (dataframe['volume'] > dataframe['volume_mean_20'] * 1.15)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['close'] < dataframe['ema200'])
            ),
            'exit_long'] = 1

        return dataframe
