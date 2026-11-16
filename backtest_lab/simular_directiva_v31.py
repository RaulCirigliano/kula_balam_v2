"""
Script: simular_directiva_v31.py
Proyecto: Kula Balam / Backtest Lab
Objetivo: Simulación fractal completa (1D -> 1H Fibo -> 5m EMA 20) usando DataLoaderLab.
Uso por terminal: python simular_directiva_v31.py NVDA stocks 5m
"""

import sys
from datetime import time
from pathlib import Path
import numpy as np
import pandas as pd

from core.data_loader import DataLoaderLab

def calcular_indicadores_reactivos(df_base: pd.DataFrame) -> pd.DataFrame:
    df = df_base.copy()
    
    # EMAs 5m
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # RSI 14
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df['rsi_14'] = 100.0 - (100.0 / (1.0 + rs))
    
    # ATR 14
    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr_14'] = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df['atr_sma_20'] = df['atr_14'].rolling(window=20).mean()
    
    # Cruces reactivos EMA 20
    df['cruce_ema20_bull'] = (df['close'].shift(1) <= df['ema_20'].shift(1)) & (df['close'] > df['ema_20'])
    df['cruce_ema20_bear'] = (df['close'].shift(1) >= df['ema_20'].shift(1)) & (df['close'] < df['ema_20'])
    
    return df

def extraer_senales(df_proc: pd.DataFrame) -> pd.DataFrame:
    cond_atr = df_proc['atr_14'] > df_proc['atr_sma_20']
    horas_index = df_proc.index.time
    filtro_horario = (horas_index >= time(10, 0)) & (horas_index <= time(15, 0))
    
    # Confluencia Long
    f_long_macro = (df_proc['sesgo_1w'] == 1) & (df_proc['sesgo_1d'] == 1)
    f_long_fibo = (df_proc['pos_fibo_1h'] >= 0.25) & (df_proc['pos_fibo_1h'] <= 0.55)
    g_long_reactivo = df_proc['cruce_ema20_bull'] & (df_proc['rsi_14'] >= 45) & (df_proc['rsi_14'] <= 65) & cond_atr
    
    # Confluencia Short
    f_short_macro = (df_proc['sesgo_1w'] == -1) & (df_proc['sesgo_1d'] == -1)
    f_short_fibo = (df_proc['pos_fibo_1h'] >= 0.45) & (df_proc['pos_fibo_1h'] <= 0.75)
    g_short_reactivo = df_proc['cruce_ema20_bear'] & (df_proc['rsi_14'] >= 35) & (df_proc['rsi_14'] <= 55) & cond_atr
    
    df_signals = df_proc.copy()
    df_signals['signal'] = 0
    df_signals.loc[filtro_horario & f_long_macro & f_long_fibo & g_long_reactivo, 'signal'] = 1
    df_signals.loc[filtro_horario & f_short_macro & f_short_fibo & g_short_reactivo, 'signal'] = -1
    
    return df_signals

def simular_salidas(df: pd.DataFrame, comision_pct: float = 0.0005) -> pd.DataFrame:
    trades = []
    indices = df.index
    
    for i in range(len(df) - 1):
        sig = df['signal'].iloc[i]
        if sig == 0:
            continue
            
        t_entry = indices[i]
        p_entry = df['close'].iloc[i]
        atr = df['atr_14'].iloc[i]
        sl_dist = 1.5 * atr
        lado = 'SHORT' if sig == -1 else 'LONG'
        
        if lado == 'LONG':
            sl_price = p_entry - sl_dist
            tp1_price = p_entry + (2.0 * sl_dist)
            be_price = p_entry * (1.0 + comision_pct)
        else:
            sl_price = p_entry + sl_dist
            tp1_price = p_entry - (2.0 * sl_dist)
            be_price = p_entry * (1.0 - comision_pct)
            
        tp1_hit = False
        exit_price_50_1 = None
        exit_price_50_2 = None
        exit_reason = None
        current_sl = sl_price
        
        for j in range(i + 1, min(i + 80, len(df))):
            high_j = df['high'].iloc[j]
            low_j = df['low'].iloc[j]
            close_j = df['close'].iloc[j]
            ema_j = df['ema_20'].iloc[j]
            curr_time = indices[j]
            
            if lado == 'LONG':
                if not tp1_hit:
                    if low_j <= current_sl:
                        exit_price_50_1 = current_sl
                        exit_price_50_2 = current_sl
                        exit_reason = 'SL_INICIAL'
                        break
                    if high_j >= tp1_price:
                        tp1_hit = True
                        exit_price_50_1 = tp1_price
                        current_sl = be_price
                else:
                    if low_j <= current_sl:
                        exit_price_50_2 = current_sl
                        exit_reason = 'TP1_Y_BE'
                        break
                    if close_j < ema_j:
                        exit_price_50_2 = close_j
                        exit_reason = 'TP1_Y_TRAILING_EMA20'
                        break
            else:
                if not tp1_hit:
                    if high_j >= current_sl:
                        exit_price_50_1 = current_sl
                        exit_price_50_2 = current_sl
                        exit_reason = 'SL_INICIAL'
                        break
                    if low_j <= tp1_price:
                        tp1_hit = True
                        exit_price_50_1 = tp1_price
                        current_sl = be_price
                else:
                    if high_j >= current_sl:
                        exit_price_50_2 = current_sl
                        exit_reason = 'TP1_Y_BE'
                        break
                    if close_j > ema_j:
                        exit_price_50_2 = close_j
                        exit_reason = 'TP1_Y_TRAILING_EMA20'
                        break
                        
        if exit_reason is None:
            last_c = df['close'].iloc[min(i + 79, len(df) - 1)]
            exit_price_50_1 = tp1_price if tp1_hit else last_c
            exit_price_50_2 = last_c
            exit_reason = 'CIERRE_VENTANA'

        if lado == 'LONG':
            pnl_1 = ((exit_price_50_1 - p_entry) / p_entry) - (2 * comision_pct)
            pnl_2 = ((exit_price_50_2 - p_entry) / p_entry) - (2 * comision_pct)
        else:
            pnl_1 = ((p_entry - exit_price_50_1) / p_entry) - (2 * comision_pct)
            pnl_2 = ((p_entry - exit_price_50_2) / p_entry) - (2 * comision_pct)
            
        pnl_total_pct = (0.5 * pnl_1) + (0.5 * pnl_2)
        r_unit = sl_dist / p_entry
        r_multiple = pnl_total_pct / (r_unit + 1e-9)

        trades.append({
            'trade': len(trades) + 1,
            'fecha': str(t_entry)[:16],
            'lado': lado,
            'entrada': round(p_entry, 2),
            'fibo_1h': f"{df['pos_fibo_1h'].iloc[i]*100:.1f}%",
            'sl': round(sl_price, 2),
            'tp1': round(tp1_price, 2),
            'resultado': exit_reason,
            'pnl_pct': round(pnl_total_pct * 100, 2),
            'r': f"{round(r_multiple, 2)}R"
        })

    return pd.DataFrame(trades)

if __name__ == "__main__":
    activo = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    mercado = sys.argv[2] if len(sys.argv) > 2 else "stocks"
    tf = sys.argv[3] if len(sys.argv) > 3 else "5m"

    loader = DataLoaderLab()
    df_raw = loader.cargar(activo=activo, mercado=mercado, timeframe_base=tf, fractales=["1h", "1D", "1W"])
    df_proc = calcular_indicadores_reactivos(df_raw)
    df_signals = extraer_senales(df_proc)
    df_trades = simular_salidas(df_signals)

    print("\n" + "="*85)
    print(f"   KULA BALAM: SIMULACIÓN DIRECTIVA v3.1 | {activo.upper()} ({mercado}) [{tf}]")
    print("="*85)
    if len(df_trades) > 0:
        print(df_trades.to_string(index=False))
        ganados = df_trades[df_trades['pnl_pct'] > 0]
        wr = (len(ganados) / len(df_trades)) * 100
        pnl_tot = df_trades['pnl_pct'].sum()
        print("-"*85)
        print(f" Trades: {len(df_trades)} | Win Rate: {wr:.2f}% | PnL Acumulado: {pnl_tot:+.2f}%")
    else:
        print("  [i] Sin operaciones válidas bajo confluencia fractal completa.")
    print("="*85 + "\n")
