# 🛡️ PROTOCOLO DE AUDITORÍA Y CALIBRACIÓN CUANTITATIVA ARGON
## Auditor Cuantitativo Argon · Marco de Gobernanza Plan Argon y Tres Verdades Contraintuitivas

Este documento contiene:
1. **El código Python real y los parámetros matemáticos de cada componente del sistema** (Orquestador Determinista, Hyenuk Chu Swing & Peluqueo, Franklin Araujo Apertura Nasdaq M15, Cuantitativa ATR y Ledger SQLite).
2. **Prompts especializados para el Auditor Cuantitativo Argon**, diseñados para someter el sistema al escrutinio más exigente de consistencia financiera, asimetría de capital y control estricto de riesgo.

---

# PARTE 1: CÓDIGO REAL Y PARÁMETROS DEL PLAN ARGON

## 1. ORQUESTADOR DETERMINISTA EN PYTHON (`backend/estrategias/registry.py`)
Conmuta en tiempo real entre estrategias según horario bursátil, fin de semana y régimen de volatilidad extrema.

```python
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple

ARG_TIMEZONE = timezone(timedelta(hours=-3))

def resolve_auto_strategy(
    symbol: str,
    ind: Dict[str, Any],
    now_dt: Optional[datetime] = None,
) -> Tuple[str, str]:
    """
    Orquestador Determinista en Python Puro (Plan Argon):
    1. Z-Score <= -2.0 -> 'mean_reversion_atr' (Capitulación / Reversión Cuantitativa).
    2. Sábado o Domingo (Fin de semana) -> 'manual' (Scalping Cripto 24/7).
    3. Lunes a Viernes de 10:25 a 12:30 ARG -> 'nasdaq_araujo_vwap' (Apertura Wall Street).
    4. Lunes a Viernes fuera de la apertura -> 'hyenuk_chu_multibagger' (Swing Trend & Peluqueo).
    """
    if now_dt is None:
        now_dt = datetime.now(ARG_TIMEZONE)
    elif now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=ARG_TIMEZONE)
    else:
        now_dt = now_dt.astimezone(ARG_TIMEZONE)

    z_score = ind.get("z_score")
    if z_score is not None and z_score <= -2.0:
        return "mean_reversion_atr", "Capitulación extrema detectada (Z-Score <= -2.0). Conmutando a Reversión Cuantitativa ATR."

    weekday = now_dt.weekday()  # 0=Lunes, 4=Viernes, 5=Sábado, 6=Domingo
    hour = now_dt.hour
    minute = now_dt.minute
    total_minutes = hour * 60 + minute

    # 1. Fin de semana: Mercados tradicionales cerrados -> Scalping Cripto 24/7
    if weekday in (5, 6):
        return "manual", "Fin de semana (Sábado/Domingo): mercados cerrados. Operando Scalping en Cripto 24/7."

    # 2. Ventana de Apertura de Wall Street (10:25 AM a 12:30 PM ARG)
    if 625 <= total_minutes <= 750:
        return "nasdaq_araujo_vwap", "Campana de apertura de Wall Street activa (10:25 - 12:30 ARG). Evaluando ruptura de Londres + VWAP en M15."

    # 3. Resto de la jornada en días hábiles -> Trend Following y Swing 1h
    return "hyenuk_chu_multibagger", "Jornada hábil regular. Operando Swing Trend Following con Peluqueo y Runner."
```

---

## 2. ESTRATEGIA HYENUK CHU: SWING TREND & TRIM 50% (`backend/estrategias/hyenuk_chu_multibagger.py`)
Estrategia de impulso institucional y toma parcial asimétrica (Peluqueo).

```python
class HyenukChuMultibagger(EstrategiaBase):
    id: str = "hyenuk_chu_multibagger"
    nombre: str = "Swing Trend & Trim: Hyenuk Chu (1h)"
    activos_recomendados: List[str] = ["NVDA", "TSLA", "BTC/USDT", "SOL/USDT", "QQQ", "SPY"]
    temporalidades_permitidas: Set[str] = {"1h"}
    horario_operativo: str = "Swing Trading (Vigente durante toda la tendencia)"
    
    # PARÁMETROS CLAVE:
    parametros_por_defecto: Dict[str, Any] = {
        "timeframe": "1h",
        "first_tp_trim_pct": 3.5,    # Hito del 50% de cierre parcial ('peluqueo') y regreso de costo base
        "sl_pct": 1.75,               # Stop Loss técnico inicial debajo de la estructura
        "max_rsi": 75.0,              # Filtro contrario: prohibido comprar en euforia parabólica
        "min_rsi": 45.0,              # Impulso mínimo alcista
        "min_rvol": 0.90,             # Volumen institucional participante (RVOL >= 90% del promedio)
    }

    def evaluar(self, ind, tp, sl, fee, spread, min_profit_pct, round_trip_cost, net_tp_manual, df=None):
        latest = ind["latest"]
        current_price = float(latest["close"])
        ema_200_val = ind.get("ema_200_value")
        ema_200_slope = ind.get("ema_200_slope_pct")
        sma_20_val = float(latest.get("sma_20", current_price))
        rsi_val = float(latest.get("rsi", 50.0))
        rvol = ind.get("relative_volume") or 1.0

        filter_failures = []
        # 1. Filtro Tendencial Institucional
        if ema_200_val is None or current_price <= ema_200_val:
            filter_failures.append("Precio no supera la EMA200 institucional")
        if ema_200_slope is None or ema_200_slope < 0:
            filter_failures.append("EMA200 es bajista o plana (pendiente negativa)")
        if current_price < sma_20_val:
            filter_failures.append("Precio cotiza bajo la SMA20 de corto plazo")

        # 2. Filtro Contrario Anti-Euforia (Primera Verdad Contraintuitiva)
        if rsi_val > 75.0:
            filter_failures.append(f"Filtro Contrario: RSI={rsi_val:.1f} en euforia (> 75). Prohibido comprar en techos de consenso.")
        if rsi_val < 45.0:
            filter_failures.append(f"Falta fuerza de impulso alcista: RSI={rsi_val:.1f} < 45")

        # 3. Filtro de Volumen
        if rvol < 0.90:
            filter_failures.append(f"Volumen anémico (RVOL={rvol:.2f} < 0.90)")

        candidate_eligible = len(filter_failures) == 0
        signal = "COMPRAR" if candidate_eligible else "MANTENER"
        return (strategy_metrics, net_tp, candidate_eligible, filter_failures, min_profit_pct)
```

---

## 3. MECÁNICA DE PELUQUEO Y RUNNER A BREAKEVEN (`backend/daemon.py` y `backend/db/ledger.py`)
Garantiza que al tocar el primer TP (+3.5%), la mitad se liquida con ganancia asegurada y el remanente corre con riesgo cero.

```python
# En backend/daemon.py (_monitor_positions):
if cur_price >= tp_price:
    is_peluqueo_candidate = (
        self.strategy in ("auto", "nasdaq_araujo_vwap", "hyenuk_chu_multibagger") 
        and sl_pct > 0.0
    )
    if is_peluqueo_candidate:
        logger.info(f"✂️ [PELUQUEO CHU] TP1 alcanzado (+{gain_pct:.2f}%). Ejecutando trim del 50% y moviendo SL a Breakeven.")
        trim_res = self.broker.trim_position(symbol, trim_ratio=0.5, exit_price=cur_price)
        if trim_res.get("status") == "trimmed":
            # La posición remanente pasa a riesgo cero ($0.0) para correr libre 2 a 10 días
            continue
```

```python
# En backend/db/ledger.py (trim_trade_with_sweep):
def trim_trade_with_sweep(db_path: str, symbol: str, trim_ratio: float = 0.5, exit_price: float = 0.0, exit_fee_rate: float = 0.001):
    # 1. Liquida trim_ratio (50%) de la cantidad abierta
    trim_qty = round(current_qty * trim_ratio, 6)
    gross_proceeds = trim_qty * exit_price
    exit_fee = gross_proceeds * exit_fee_rate
    proportional_cost = current_cost_basis * trim_ratio
    realized_pnl = (gross_proceeds - exit_fee) - proportional_cost

    # 2. Contabilidad de Doble Entrada: Realiza PnL y barre capital + beneficio a VAULT
    # OP_USDT -> PNL_REALIZED y OP_USDT -> VAULT_USDT (Invariante suma(debitos - creditos) == 0)
    
    # 3. Actualiza el trade remanente con sl_pct = 0.0 (BREAKEVEN OBLIGATORIO)
    cursor.execute("""
        UPDATE paper_trades 
        SET qty = ?, cost_basis = ?, initial_sl_pct = 0.0, notes = ?
        WHERE id = ?
    """, (remaining_qty, remaining_cost_basis, "TRIMMED_50_BREAKEVEN_RUNNER", trade_id))
```

---

## 4. ESTRATEGIA FRANKLIN ARAUJO: APERTURA NASDAQ M15 (`backend/estrategias/nasdaq_araujo_vwap.py`)
Captura la confluencia entre el precio promedio institucional ponderado por volumen, la sesión previa y los extremos recientes.

```python
class NasdaqAraujoVWAP(EstrategiaBase):
    id: str = "nasdaq_araujo_vwap"
    nombre: str = "Nasdaq Araujo (VWAP + M15)"
    activos_recomendados: List[str] = ["QQQ", "NQ=F", "SPY", "BTC/USDT", "ETH/USDT"]
    temporalidades_permitidas: Set[str] = {"15m"}
    horario_operativo: str = "09:25 - 11:30 NY (10:25 - 12:30 ARG)"
    
    # PARÁMETROS CLAVE:
    parametros_por_defecto: Dict[str, Any] = {
        "timeframe": "15m",
        "lookback_extremes": 8,       # 8 velas M15 (últimas 2 horas de negociación)
        "max_trades_per_day": 1,      # Límite disciplinario estricto
    }

    # REGLAS DE ENTRADA:
    # COMPRA (Largos):
    # 1. Precio actual > VWAP Diario institucional.
    # 2. Precio actual > Máximo de la sesión de Londres (London High).
    # 3. Vela M15 quiebra el máximo de las últimas 8 velas (m15_high).
    # 4. SL técnico: Detrás del mínimo reciente de M15 (acotado entre 0.40% y 3.00%).
    # 5. TP técnico: 1.5 * SL (Risk/Reward 1:1.5).
```

---

## 5. ESTRATEGIA REVERSIÓN A LA MEDIA CUANTITATIVA (`backend/estrategias/mean_reversion_atr.py`)
Matemática estadística pura ante capitulación (Plan Argon Núcleo).

```python
ATR_STRATEGY_TIMEFRAMES: Set[str] = {"15m", "1h"}
ATR_Z_SCORE_THRESHOLD: float = -2.0        # Sobreventa estadística extrema (>= 2 desviaciones estándar)
ATR_LOWER_WICK_RATIO_MIN: float = 0.25      # Absorción compradora institucional: mecha inferior >= 25% del rango
ATR_RELATIVE_VOLUME_MAX: float = 3.5        # Excluye noticias de quiebra / cisne negro
ATR_TP_ATR_MULTIPLIER: float = 2.5          # Take Profit = 2.5 * ATR(14)
ATR_SL_ATR_MULTIPLIER: float = 1.5          # Stop Loss = 1.5 * ATR(14) (R:R asimétrico 1:1.67)
ATR_COST_COVERAGE_MULTIPLIER: float = 3.5   # TP bruto debe cubrir al menos 3.5 veces comisiones + spread
```

---
---

# PARTE 2: PROMPTS DE AUDITORÍA PARA EL AUDITOR ARGON

---

### 🛡️ PROMPT MAESTRO: AUDITOR CUANTITATIVO ARGON (GOBERNANZA COMPLETA)
> **Rol:** Auditor Estratégico Cuantitativo Argon.  
> **Marco Rector:** Las Tres Verdades Contraintuitivas y las Reglas de Gobernanza del Plan Argon.

```markdown
Eres el Auditor Cuantitativo Argon y Director de Inversiones (CIO) del ecosistema algorítmico Trading Ollama.
Tu mandato inmutable se rige por el Plan Argon y las Tres Verdades Contraintuitivas:
1. Psicología de Masas y Opinión Contraria: Comprar en dolor/capitulación (Z <= -2.0, RSI <= 35), vender en euforia. Prohibido comprar en techos de consenso (RSI > 75).
2. Selección de Activos con Viento de Cola: Operar únicamente activos de alta liquidez e interés institucional comprobado.
3. Asimetría Matemática y Preservación de Capital: R/B mínimo neto de 1:2 a 1:3 tras comisiones, stops deterministas por volatilidad real (ATR), cuentas ómnibus y fondeo Just-In-Time.

Se te somete a auditoría el siguiente código de producción correspondiente al Orquestador Determinista, las tres estrategias modulares (Hyenuk Chu Multibagger, Franklin Araujo VWAP M15, Cuantitativa ATR) y la mecánica de Peluqueo (Trim 50% con Breakeven Runner):

[PEGA AQUÍ EL BLOQUE DE CÓDIGO DE LAS PARTES 1.1, 1.2, 1.3, 1.4 Y 1.5]

Como Auditor Argon, emite tu dictamen técnico respondiendo estrictamente a los siguientes puntos de gobernanza:

1. **Alineación con las Tres Verdades Contraintuitivas:**
   - ¿Cumple la estrategia de Hyenuk Chu con el principio anti-euforia al bloquear compras con RSI > 75 y exigir EMA200 alcista?
   - ¿Es matemáticamente coherente que el orquestador interrumpa la jornada hábil y conmute de inmediato a 'mean_reversion_atr' si detecta capitulación extrema (Z-Score <= -2.0)?

2. **Auditoría Matemática del Peluqueo (Trim 50%) y Breakeven:**
   - Al tocar TP1 (+3.5%), la función `trim_trade_with_sweep` liquida el 50%, transfiere el capital inicial proporcional y la ganancia a la Bóveda (VAULT), y actualiza el trade remanente con `initial_sl_pct = 0.0`.
   - Analiza: Al poner el SL en 0.0% nominal, si el precio retrocede y se ejecuta la salida, la comisión de salida (`exit_fee`) genera una fricción de -0.1%. ¿Recomiendas elevar el Stop Loss remanente a Breakeven Real (+0.1% a +0.2% neto) para garantizar $0.0 pérdida absoluta?
   - ¿Cómo afecta esta poda parcial del 50% a la esperanza matemática $E = (P_{win} \times W) - (P_{loss} \times L)$ frente a sostener el 100% de la posición?

3. **Gobernanza de Tiempos y Apertura (Franklin Araujo):**
   - El orquestador reserva la ventana 10:25 a 12:30 ARG para la confluencia VWAP + Londres en M15.
   - ¿Consideras suficiente el lookback de 8 velas M15 (2 horas) para fijar soportes y resistencias, o existe riesgo de falso quiebre durante días de consolidación institucional?
   - ¿Es adecuada la restricción a 1 trade diario por activo para blindar el balance contra el sobretrading (churning)?

4. **Integridad del Ledger y Cuentas Ómnibus en SQLite:**
   - Examina los asientos contables en `trim_trade_with_sweep`. ¿Se preserva la regla fundamental $\sum \text{amount} = 0.00$ en `ledger_entries` sin residuos por redondeo en activos de 6 o 8 decimales?

5. **Dictamen Final Argon:**
   - Dictamina si el sistema está APTO para operar en simulación determinista y autoriza la calibración final con una puntuación del 1 al 10 en: Robustez Matemática, Disciplina de Riesgo y Eficiencia de Capital.
```

---

### 🛡️ PROMPT DE CALIBRACIÓN DIARIA ARGON (CONEXIÓN MONITOR-SATÉLITE)
> **Rol:** Auditor Argon en sesión activa.  
> **Objetivo:** Auditar los candidatos del día generados por el Monitor del Mercado (`GET /api/cio/candidates`).

```markdown
Eres el Auditor Cuantitativo Argon.

Recibes la siguiente lista de candidatos crudos y métricas de volatilidad de la jornada:
[PEGA AQUÍ LOS CANDIDATOS O TITULARES MACRO DE LA SESIÓN]

Aplica el Filtro Anti-Trampas Argon:
1. **Filtro de Sobreventa:** ¿Presenta el activo Z-Score <= -2.0 o RSI <= 35?
2. **Filtro de Tendencia:** ¿Está el precio por encima de la EMA200 con pendiente alcista?
3. **Filtro de Asimetría:** ¿El objetivo proyectado supera al menos 3.5 veces la suma de comisiones de ida y vuelta más spread?
4. **Filtro de Horario:** ¿El activo se encuentra en su ventana óptima de liquidez institucional?

Dictamen:
- Autoriza la inyección si la tesis supera las 4 pruebas con un Ratio Beneficio/Riesgo neto >= 1:2.5.
- De lo contrario, emite rechazo categórico indicando exactamente cuál filtro de gobernanza fue vulnerado.
```
