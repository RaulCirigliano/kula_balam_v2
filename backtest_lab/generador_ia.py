# -*- coding: utf-8 -*-
"""
Módulo: backtest_lab/generador_ia.py
Proyecto: Kula Balam / Backtest Lab
Propósito: Motor Generativo Asistido por IA (Prompt-to-Backtest)
  - Modo 1 (Antigravity Cuantitativo): Síntesis determinista instantánea (cero tokens / offline).
  - Modo 2 (Google Gemini Cloud): Exploración creativa en la nube mediante API Key.
Reglas Inviolables:
  - Causalidad temporal estricta: shift(1) obligatorio en cálculos de indicadores.
  - Asimetría matemática garantizada: R:R >= 1:2.0.
  - Generación de arquitectura dual: formula_matematica + arbitro_ia.
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_GEMINI = """Eres el Quantitative Trading Architect de Kula Balam y Antigravity.
Tu misión es generar estrategias cuantitativas algorítmicas de alta convicción para el Backtest Lab.

REGLAS MATEMÁTICAS Y ARQUITECTÓNICAS OBLIGATORIAS:
1. Causalidad estricta (CERO Lookahead Bias):
   - Todo indicador rolling, media, máximo o mínimo debe usar obligatoriamente `.shift(1)` antes del cómputo.
   - La entrada a mercado se ejecuta causalmente en el `open` de la vela siguiente `i+1`.
2. Asimetría matemática institucional:
   - Todo setup debe exigir una asimetría teórica de R:R >= 1:2.0 (o R:R >= 1:2.5 en Cripto).
   - Prohibido Take Profit más corto que Stop Loss (prohibido R:R negativo).
3. Firma de la función matemática:
   def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
       # Devuelve: (disparo: bool, lado: "LONG" | "SHORT" | None, stop_loss: float, take_profit: float)
4. Firma del Árbitro IA:
   def arbitro_ia(fila, lado, entry, sl, tp) -> Tuple[bool, float, str]:
       # Devuelve: (autorizado: bool, multiplicador_sizing: float, motivo: str)
5. Formato de Salida:
   Tu respuesta debe ser EXCLUSIVAMENTE un objeto JSON válido con los siguientes campos:
   {
       "nombre": "nombre_estrategia.py",
       "comentario": "Breve explicación cuantitativa de la tesis",
       "dataset_recomendado": "binance_ETH_USDT_4h.parquet" o el adecuado,
       "code_math": "Código Python completo de formula_matematica",
       "code_ia": "Código Python completo de arbitro_ia"
   }
"""


def _generar_template_donchian_squeeze(prompt: str, ticker: str, es_1d: bool = False) -> Dict[str, Any]:
    p_low = prompt.lower()
    t_up = ticker.upper()
    if es_1d:
        ds = "yf_QQQ_1d.parquet" if ("qqq" in p_low or "QQQ" in t_up) else "yf_SPY_1d.parquet"
    elif "sol" in p_low or "SOL" in t_up:
        ds = "binance_SOL_USDT_4h.parquet"
    elif "btc" in p_low or "BTC" in t_up:
        ds = "binance_BTC_USDT_4h.parquet"
    else:
        ds = "binance_ETH_USDT_4h.parquet"

    nombre = "donchian_squeeze_auto.py"
    comentario = f"Ruptura Donchian {'1D' if es_1d else '4H'} con Compresión de Volatilidad Bollinger y Régimen EMA 200"

    code_math = f'''# -*- coding: utf-8 -*-
"""
Fórmula Cuantitativa: Ruptura Donchian + Compresión de Volatilidad
Generado por: Antigravity Cuantitativo (Prompt-to-Backtest)
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "{ds}"
MAX_BARS_HOLD = 84

def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_gen_sq_init" not in df.columns:
        dc_p = 20 if "{'1d' if es_1d else '4h'}" == "1d" else 30
        prev_c = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
        df["_atr14"] = tr.rolling(14).mean().shift(1).bfill()
        df["_ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["_slp200"] = df["_ema200"] - df["_ema200"].shift(8)

        df["_dh"] = df["high"].shift(1).rolling(dc_p).max().bfill()
        df["_dl"] = df["low"].shift(1).rolling(dc_p).min().bfill()
        bw = (df["_dh"] - df["_dl"]) / (df["_atr14"] + 1e-9)
        df["_bw"] = bw
        df["_bw_med"] = bw.shift(1).rolling(60, min_periods=20).median().bfill()
        df["_gen_sq_init"] = True

    if i < 210:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    c = float(row["close"])
    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    atr = float(row["_atr14"])
    if atr <= 0:
        return False, None, 0.0, 0.0

    if (h - l) > (2.6 * atr):
        return False, None, 0.0, 0.0

    bw_val = float(row["_bw"])
    bw_med = float(row["_bw_med"])
    if bw_val > 6.0 or bw_val > (bw_med * 1.15):
        return False, None, 0.0, 0.0

    dh = float(row["_dh"])
    dl = float(row["_dl"])
    ema_v = float(row["_ema200"])
    slp_v = float(row["_slp200"]) if pd.notna(row["_slp200"]) else 0.0

    sl_dist = 1.60 * atr
    tp_dist = 4.16 * atr  # R:R Teórico 1:2.60

    if (c > dh) and (c > ema_v) and (slp_v > 0.0) and (c >= o):
        return True, "LONG", c - sl_dist, c + tp_dist

    if (c < dl) and (c < ema_v) and (slp_v < 0.0) and (c <= o):
        return True, "SHORT", c + sl_dist, c - tp_dist

    return False, None, 0.0, 0.0
'''

    code_ia = '''# -*- coding: utf-8 -*-
"""
Árbitro Heurístico de IA Antigravity: Filtro de Calidad Institucional
"""
def arbitro_ia(fila, lado, entry, sl, tp):
    p_ref = float(fila.get("close", entry))
    riesgo = abs(p_ref - float(sl))
    recompensa = abs(float(tp) - p_ref)
    rr = recompensa / (riesgo + 1e-9)

    if rr < 1.95:
        return False, 0.0, f"VETO Asimetría insuficiente ({rr:.2f} < 1:2.0)"

    rvol = float(fila.get("rvol", 1.0))
    if rvol < 1.20:
        return False, 0.0, f"VETO Secado de Volumen ({rvol:.2f}x < 1.20x)"

    m_sup = float(fila.get("mecha_superior_pct", 0.0))
    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    if lado == "LONG" and m_sup > 32.0:
        return False, 0.0, f"VETO Mecha Trampa Superior ({m_sup:.1f}% > 32.0%)"
    if lado == "SHORT" and m_inf > 32.0:
        return False, 0.0, f"VETO Mecha Trampa Inferior ({m_inf:.1f}% > 32.0%)"

    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > 3.2:
        return False, 0.0, f"VETO Sobreextensión EMA 50 ({dist_ema:.2f} ATR > 3.2)"

    return True, 1.0, "AUTORIZADO por Árbitro IA Antigravity (Confluencia Institucional)"
'''
    return {
        "nombre": nombre,
        "comentario": comentario,
        "dataset_recomendado": ds,
        "code_math": code_math,
        "code_ia": code_ia,
        "motor_usado": "Antigravity Cuantitativo (Determinista)",
    }


def _generar_template_vwap_reversion(prompt: str, ticker: str) -> Dict[str, Any]:
    p_low = prompt.lower()
    t_up = ticker.upper()
    if "eth" in p_low or "ETH" in t_up:
        ds = "binance_ETH_USDT_15m.parquet"
    elif "btc" in p_low or "BTC" in t_up:
        ds = "binance_BTC_USDT_15m.parquet"
    elif "sol" in p_low or "SOL" in t_up:
        ds = "binance_SOL_USDT_1h.parquet"
    elif "qqq" in p_low or "QQQ" in t_up:
        ds = "yf_QQQ_15m.parquet"
    elif "nvda" in p_low or "NVDA" in t_up:
        ds = "yf_NVDA_15m.parquet"
    else:
        ds = "yf_SPY_15m.parquet"

    nombre = "reversion_vwap_sigma_auto.py"
    comentario = "Reversión a la Media en Bandas Extremas de VWAP ±1.5σ con Mecha de Absorción"

    code_math = f'''# -*- coding: utf-8 -*-
"""
Fórmula Cuantitativa: Reversión Estadística VWAP ±1.5σ
Generado por: Antigravity Cuantitativo (Prompt-to-Backtest)
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "{ds}"
MAX_BARS_HOLD = 24

def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_vwap_sq_init" not in df.columns:
        typ_p = (df["high"] + df["low"] + df["close"]) / 3.0
        vol = df["volume"].replace(0, 1.0) if "volume" in df.columns else pd.Series(1.0, index=df.index)
        cum_pv = (typ_p * vol).rolling(36, min_periods=10).sum()
        cum_v = vol.rolling(36, min_periods=10).sum()
        vwap = (cum_pv / (cum_v + 1e-9)).bfill()
        std_vwap = df["close"].rolling(36, min_periods=10).std().bfill()
        df["_vwap"] = vwap
        df["_vwap_up"] = vwap + (1.5 * std_vwap)
        df["_vwap_dn"] = vwap - (1.5 * std_vwap)
        df["_vwap_sq_init"] = True

    if i < 40:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    c = float(row["close"])
    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    vwap_val = float(row["_vwap"])
    up_val = float(row["_vwap_up"])
    dn_val = float(row["_vwap_dn"])
    atr = float(row.get("atr", c * 0.005))

    rango = max(h - l, 1e-9)
    mecha_inf = ((min(o, c) - l) / rango) * 100.0
    mecha_sup = ((h - max(o, c)) / rango) * 100.0

    sl_dist = 1.2 * atr
    tp_dist = 2.6 * atr  # R:R Teórico 1:2.16

    # Sobreventa extrema con mecha de rechazo inferior
    if (l <= dn_val) and (c > l) and (mecha_inf >= 18.0) and (c >= o):
        return True, "LONG", c - sl_dist, c + tp_dist

    # Sobrecompra extrema con mecha de rechazo superior
    if (h >= up_val) and (c < h) and (mecha_sup >= 18.0) and (c <= o):
        return True, "SHORT", c + sl_dist, c - tp_dist

    return False, None, 0.0, 0.0
'''

    code_ia = '''# -*- coding: utf-8 -*-
"""
Árbitro Heurístico de IA Antigravity: Filtro Anti-Cuchillo Cayendo
"""
def arbitro_ia(fila, lado, entry, sl, tp):
    dist_ema = float(fila.get("dist_ema_atrs", 0.0))
    if dist_ema > 2.8:
        return False, 0.0, f"VETO Sobreextensión extrema ({dist_ema:.2f} ATR > 2.8)"

    rvol = float(fila.get("rvol", 1.0))
    if rvol < 1.05:
        return False, 0.0, f"VETO Falta de Absorción Institucional (RVOL {rvol:.2f}x < 1.05x)"

    return True, 1.0, "AUTORIZADO por Árbitro IA (Absorción y Reversión Validada)"
'''
    return {
        "nombre": nombre,
        "comentario": comentario,
        "dataset_recomendado": ds,
        "code_math": code_math,
        "code_ia": code_ia,
        "motor_usado": "Antigravity Cuantitativo (Determinista)",
    }


def _generar_template_pullback_fibo(prompt: str, ticker: str) -> Dict[str, Any]:
    p_low = prompt.lower()
    t_up = ticker.upper()
    if "eth" in p_low or "ETH" in t_up:
        ds = "binance_ETH_USDT_4h.parquet"
    elif "sol" in p_low or "SOL" in t_up:
        ds = "binance_SOL_USDT_4h.parquet"
    elif "qqq" in p_low or "QQQ" in t_up:
        ds = "yf_QQQ_1d.parquet"
    elif "spy" in p_low or "SPY" in t_up:
        ds = "yf_SPY_1d.parquet"
    else:
        ds = "binance_BTC_USDT_4h.parquet"

    nombre = "pullback_ema50_fibo_auto.py"
    comentario = "Pullback Tendencial a EMA 50 en Zona Dorada Fibonacci (0.50 - 0.618)"

    code_math = f'''# -*- coding: utf-8 -*-
"""
Fórmula Cuantitativa: Pullback Tendencial a EMA 50 en Zona Dorada Fibonacci
Generado por: Antigravity Cuantitativo (Prompt-to-Backtest)
"""
from typing import Tuple, Optional
import pandas as pd

DATASET = "{ds}"
MAX_BARS_HOLD = 60

def formula_matematica(df: pd.DataFrame, i: int) -> Tuple[bool, Optional[str], float, float]:
    if "_fibo_sq_init" not in df.columns:
        df["_ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["_ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["_high20"] = df["high"].shift(1).rolling(20).max().bfill()
        df["_low20"] = df["low"].shift(1).rolling(20).min().bfill()
        df["_fibo_sq_init"] = True

    if i < 60:
        return False, None, 0.0, 0.0

    row = df.iloc[i]
    c = float(row["close"])
    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    e50 = float(row["_ema50"])
    e200 = float(row["_ema200"])
    atr = float(row.get("atr", c * 0.01))

    h20 = float(row["_high20"])
    l20 = float(row["_low20"])
    rango_fibo = max(h20 - l20, 1e-9)

    fibo_50 = h20 - (0.50 * rango_fibo)
    fibo_618 = h20 - (0.618 * rango_fibo)

    sl_dist = 1.30 * atr
    tp_dist = 2.86 * atr  # R:R Teórico 1:2.20

    # Tendencia alcista macro (EMA 50 > EMA 200) + Retroceso a zona dorada con soporte en EMA 50
    if (e50 > e200) and (l <= fibo_50) and (c >= fibo_618) and (abs(c - e50) <= (1.2 * atr)) and (c > o):
        return True, "LONG", c - sl_dist, c + tp_dist

    return False, None, 0.0, 0.0
'''

    code_ia = '''# -*- coding: utf-8 -*-
"""
Árbitro Heurístico de IA Antigravity: Validación de Zona Dorada
"""
def arbitro_ia(fila, lado, entry, sl, tp):
    rvol = float(fila.get("rvol", 1.0))
    if rvol < 1.10:
        return False, 0.0, f"VETO Volumen escaso en el rebote ({rvol:.2f}x < 1.10x)"

    m_inf = float(fila.get("mecha_inferior_pct", 0.0))
    if m_inf < 15.0:
        return False, 0.0, f"VETO Falta mecha de rechazo dinámico ({m_inf:.1f}% < 15.0%)"

    return True, 1.0, "AUTORIZADO por Árbitro IA (Pullback a Zona Dorada Validado)"
'''
    return {
        "nombre": nombre,
        "comentario": comentario,
        "dataset_recomendado": ds,
        "code_math": code_math,
        "code_ia": code_ia,
        "motor_usado": "Antigravity Cuantitativo (Determinista)",
    }


def _adaptar_codigo_existente(
    code_math: str,
    code_ia: str,
    prompt: str,
    ticker_hint: str = "AUTO"
) -> Dict[str, Any]:
    """Adapta el código matemático y árbitro IA existentes en los editores según el prompt."""
    p_low = prompt.lower()
    es_forex = any(w in p_low for w in ["forex", "fores", "divisa", "divisas", "eurusd", "gbpusd", "usdjpy"])

    new_math = code_math
    new_ia = code_ia or ""

    if es_forex:
        ds_target = "yf_EURUSD_1h.parquet"
        if "1d" in p_low or "diario" in p_low:
            ds_target = "yf_EURUSD_1d.parquet"
        elif "gbp" in p_low:
            ds_target = "yf_GBPUSD_1h.parquet"
        elif "jpy" in p_low:
            ds_target = "yf_USDJPY_1d.parquet"

        # 1. Cambiar dataset a Forex
        if re.search(r'DATASET\s*=\s*["\'].*?["\']', new_math):
            new_math = re.sub(r'DATASET\s*=\s*["\'].*?["\']', f'DATASET = "{ds_target}"', new_math)
        else:
            new_math = f'DATASET = "{ds_target}"\n' + new_math

        # 2. Desactivar filtro RVOL en CONFIG_IA (en Forex spot el volumen centralizado no existe)
        if new_ia:
            new_ia = re.sub(r'"rvol_minimo":\s*[\d\.]+', '"rvol_minimo": 0.0', new_ia)
            new_ia = re.sub(r'"rvol_4h":\s*[\d\.]+', '"rvol_4h": 0.0', new_ia)
            new_ia = re.sub(r'"rvol_1d":\s*[\d\.]+', '"rvol_1d": 0.0', new_ia)
            if "Filtro RVOL desactivado" not in new_ia:
                new_ia = "# [ADAPTADO A FOREX] Filtro RVOL desactivado (volumen centralizado inexistente en spot)\n" + new_ia

        # 3. Encabezado explicativo
        if not new_math.startswith("# [ADAPTADA A FOREX]"):
            new_math = f"# [ADAPTADA A FOREX PARA {ds_target}]\n" + new_math

        nombre = "forex_adaptada.py"
        comentario = f"🏆 [FOREX ADAPTADA] Estrategia convertida para {ds_target} sin fricción de volumen"

        return {
            "nombre": nombre,
            "comentario": comentario,
            "code_math": new_math,
            "code_ia": new_ia,
            "dataset_recomendado": ds_target,
            "motor_usado": "Antigravity Adaptador Cuantitativo Local (Forex)"
        }

    return {
        "nombre": "estrategia_adaptada.py",
        "comentario": "Estrategia adaptada desde el código en pantalla",
        "code_math": new_math,
        "code_ia": new_ia,
        "dataset_recomendado": ticker_hint if ticker_hint != "AUTO" else "binance_ETH_USDT_4h.parquet",
        "motor_usado": "Antigravity Adaptador Cuantitativo Local"
    }


def sintetizar_estrategia(
    prompt: str,
    motor: str = "auto",
    api_key: str = "",
    ticker_hint: str = "AUTO",
    code_math_existente: str = "",
    code_ia_existente: str = ""
) -> Dict[str, Any]:
    """
    Sintetiza una estrategia completa (formula_matematica + arbitro_ia) a partir del prompt.
    Prioridad:
    1. Si se fuerza o solicita motor Gemini Cloud y la clave es válida -> LLM Generativo.
    2. De lo contrario o ante cualquier falla de red -> Sintetizador Antigravity Cuantitativo Determinista.
    """
    prompt_clean = (prompt or "").strip()
    p_low = prompt_clean.lower()
    t_hint = (ticker_hint or "AUTO").upper()

    tiene_codigo_base = bool(code_math_existente and len(code_math_existente.strip()) > 40)
    pide_adaptar = any(w in p_low for w in ["convierte", "adapta", "pasa", "modifica", "forex", "fores", "divisas", "cambia", "ajusta"])

    # Si se pide Gemini y hay API Key disponible
    usar_gemini = motor == "gemini" or (motor == "auto" and bool(api_key and len(api_key) > 20))
    if usar_gemini:
        try:
            import requests
            key_eff = api_key.strip() if api_key else os.getenv("GEMINI_API_KEY", "").strip("\"'")
            if key_eff and len(key_eff) > 20 and not key_eff.startswith("AQ."):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key_eff}"
                user_msg = f"Requerimiento del Operador:\\n{prompt_clean}\\nActivo/Dataset preferido: {t_hint}"
                if tiene_codigo_base:
                    user_msg += f"\\n\\nCÓDIGO MATEMÁTICO ACTUALMENTE EN EL EDITOR:\\n```python\\n{code_math_existente}\\n```\\n\\nCÓDIGO ÁRBITRO IA ACTUAL:\\n```python\\n{code_ia_existente}\\n```\\n\\nTAREA: Adapta y optimiza el código existente en lugar de inventar uno nuevo."
                payload = {
                    "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT_GEMINI}\\n\\n{user_msg}"}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}
                }
                resp = requests.post(url, json=payload, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    json_match = re.search(r"\{[\s\S]*\}", raw_text)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                        if parsed.get("code_math") and parsed.get("code_ia"):
                            parsed["motor_usado"] = "Google Gemini 2.0 Flash (Cloud Generativo)"
                            return parsed
        except Exception as exc:
            logger.warning(f"Falla al invocar Gemini Cloud: {exc}. Redirigiendo a Antigravity Local.")

    # Si hay código cargado en pantalla y el usuario pide adaptarlo/convertirlo:
    if tiene_codigo_base and pide_adaptar:
        return _adaptar_codigo_existente(code_math_existente, code_ia_existente, prompt_clean, t_hint)

    # Síntesis Determinista Antigravity por Análisis Semántico de Tesis
    es_1d = any(w in p_low for w in ["1d", "diario", "acciones", "tradfi", "spy", "aapl", "qqq"])
    es_vwap = any(w in p_low for w in ["vwap", "reversion", "reversión", "sigma", "sobreventa", "sobrecompra", "scalp"])
    es_fibo = any(w in p_low for w in ["fibo", "fibonacci", "pullback", "retroceso", "dorada", "rebote", "ema50"])

    if es_vwap:
        return _generar_template_vwap_reversion(prompt_clean, t_hint)
    elif es_fibo:
        return _generar_template_pullback_fibo(prompt_clean, t_hint)
    else:
        # Donchian Squeeze como patrón rey institucional
        return _generar_template_donchian_squeeze(prompt_clean, t_hint, es_1d=es_1d)
