"""
Script: simular_fibo_gatillo_reactivo.py
Proyecto: Kula Balam / Backtest Lab
Objetivo: Gatillo reactivo en 5m (EMA 20 + RSI cruce medio) condicionado a la Zona Fibo de 1H.
Reglas: Directiva Operativa Maestra v3.1 adaptada.
"""

import sys
from datetime import time
from pathlib import Path
import numpy as np
import pandas as pd

def alinear_marcos_fractales(df_in: pd.DataFrame) -> pd.DataFrame:
    df = df_in.copy()
    df.columns = [str(c).lower() for c in df.columns]

    if not isinstance(df.index, pd.DatetimeIndex):
        col_fecha = next((c for c in ['timestamp', 'date', 'datetime', 'time', 'open_time'] if c in df.columns), None)
        if col_fecha:
            df[col_fecha] = pd.to_datetime(df[col_fecha])
            df = df.set_index(col_fecha)
        else:
            raise ValueError("No se encontro columna de fecha/tiempo.")

    df = df.sort_index()

    # 1. Marco Diario (1D)
    df_1d = df.resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }).dropna()
    span_1d = min(50, len(df_1d))
    df_1d['ema_1d'] = df_1d['close'].ewm(span=span_1d, adjust=False).mean()
    df_1d['sesgo_1d'] = np.where(df_1d['close'] > df_1d['ema_1d'], 1, -1)
    df_1d['sesgo_1d_valido'] = df_1d['sesgo_1d'].shift(1).bfill()

    # 2. Marco Macro (Semanal)
    df_macro = df.resample('W').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    span_macro = min(20, len(df_macro))
    df_macro['ema_macro'] = df_macro['close'].ewm(span=span_macro, adjust=False).mean()
    df_macro['sesgo_macro'] = np.where(df_macro['close'] > df_macro['ema_macro'], 1, -1)
    df_macro['sesgo_macro_valido'] = df_macro['sesgo_macro'].shift(1).bfill()

    # 3. Marco Intermedio 1H: Estructura de Swing y Retroceso de Fibonacci
    df_1h = df.resample('1h').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    
    df_1h['swing_high_24h'] = df_1h['high'].rolling(window=24, min_periods=5).max()
    df_1h['swing_low_24h'] = df_1h['low'].rolling(window=24, min_periods=5).min()
    df_1h['rango_swing'] = df_1h['swing_high_24h'] - df_1h['swing_low_24h']
    
    # 0.0 = Minimo, 1.0 = Maximo
    df_1h['pos_fibo_1h'] = (df_1h['close'] - df_1h['swing_low_24h']) / (df_1h['rango_swing'] + 1e-9)
    df_1h['pos_fibo_valida'] = df_1h['pos_fibo_1h'].shift(1).bfill()

    df['sesgo_1d'] = df_1d['sesgo_1d_valido'].reindex(df.index, method='ffill').bfill()
    df['sesgo_macro'] = df_macro['sesgo_macro_valido'].reindex(df.index, method='ffill').bfill()
    df['pos_fibo_1h'] = df_1h['pos_fibo_valida'].reindex(df.index, method='ffill').bfill()

    return df

def calcular_indicadores_reactivos_5m(df_base: pd.DataFrame) -> pd.DataFrame:
    df = df_base.copy()
    
    # EMA 20 y EMA 50
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
    
    # ATR 14 y su SMA 20
    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr_14'] = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df['atr_sma_20'] = df['atr_14'].rolling(window=20).mean()
    
    # Gatillo Reactivo: Cruce de EMA 20
    df['cruce_ema20_bull'] = (df['close'].shift(1) <= df['ema_20'].shift(1)) & (df['close'] > df['ema_20'])
    df['cruce_ema20_bear'] = (df['close'].shift(1) >= df['ema_20'].shift(1)) & (df['close'] < df['ema_20'])
    
    return df

def extraer_senales_confluencia(df_proc: pd.DataFrame) -> pd.DataFrame:
    cond_atr = df_proc['atr_14'] > df_proc['atr_sma_20']
    horas_index = df_proc.index.time
    filtro_horario = (horas_index >= time(10, 0)) & (horas_index <= time(15, 0))
    
    # 1. LONG: Macro alcista + 1H en zona de descuento (0.25 a 0.55) + Giro 5m sobre EMA 20
    f_long_macro = (df_proc['sesgo_macro'] == 1) & (df_proc['sesgo_1d'] == 1)
    f_long_fibo = (df_proc['pos_fibo_1h'] >= 0.25) & (df_proc['pos_fibo_1h'] <= 0.55)
    g_long_reactivo = df_proc['cruce_ema20_bull'] & (df_proc['rsi_14'] >= 45) & (df_proc['rsi_14'] <= 65) & cond_atr
    
    # 2. SHORT: Macro bajista + 1H en zona de rebote/valor (0.45 a 0.75) + Giro 5m bajo EMA 20
    f_short_macro = (df_proc['sesgo_macro'] == -1) & (df_proc['sesgo_1d'] == -1)
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
        lado = 'LONG' if sig == 1 else 'SHORT'
        
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
            'precio_entrada': round(p_entry, 2),
            'pos_fibo_1h': f"{df['pos_fibo_1h'].iloc[i]*100:.1f}%",
            'sl_inicial': round(sl_price, 2),
            'tp1': round(tp1_price, 2),
            'resultado': exit_reason,
            'pnl_neto_pct': round(pnl_total_pct * 100, 2),
            'r_multiple': f"{round(r_multiple, 2)}R"
        })

    return pd.DataFrame(trades)

if __name__ == "__main__":
    ruta_defecto = Path("/home/raul/Escritorio/proyectos/kula_balam_ikigai/backtest_lab/data/datos_historicos/yf_NVDA_5m.parquet")
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else ruta_defecto

    print(f"[*] Cargando: {ruta}")
    df_raw = pd.read_parquet(ruta)
    df_proc = alinear_marcos_fractales(df_raw)
    df_proc = calcular_indicadores_reactivos_5m(df_proc)
    df_signals = extraer_senales_confluencia(df_proc)
    df_trades = simular_salidas(df_signals)

    print("\n" + "="*95)
    print("      KULA BALAM: SIMULACION CON GATILLO REACTIVO 5M (EMA 20) EN ZONA FIBO 1H")
    print("="*95)
    if len(df_trades) > 0:
        print(df_trades.to_string(index=False))
        ganados = df_trades[df_trades['pnl_neto_pct'] > 0]
        perdidos = df_trades[df_trades['pnl_neto_pct'] <= 0]
        wr = (len(ganados) / len(df_trades)) * 100
        pnl_tot = df_trades['pnl_neto_pct'].sum()
        print("-"*95)
        print(f" Total Operaciones : {len(df_trades)} | Ganadas: {len(ganados)} | Perdidas: {len(perdidos)}")
        print(f" Win Rate          : {wr:.2f}% | PnL Acumulado: {pnl_tot:+.2f}%")
    else:
        print("  [i] Ninguna vela cumplio simultaneamente la confluencia: 1D + 1H Fibo + EMA 20 reactiva.")
    print("="*95 + "\n")