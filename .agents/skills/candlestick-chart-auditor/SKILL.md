---
name: candlestick-chart-auditor
description: >-
  Auditor Cuantitativo de Velas Japonesas, Order Flow Institucional, Psicología de Subasta y Acción del Precio.
  Integra el benchmark estadístico de Thomas Bulkowski (4.7M de velas), análisis de volumen VPA/Wyckoff,
  confluencia con VWAP y medias móviles, y el protocolo de evaluación dual: En Vivo (sin sesgo del futuro, R:R >= 1:2)
  y en Histórico (auditoría ciega en la barra + balance de resultado posterior).
---

# Auditor Cuantitativo de Velas Japonesas & Acción del Precio

Este skill define la inteligencia operativa, matemática y conductual del **Agente Auditor de Velas Japonesas** para el ecosistema de trading.

> **Propósito:** Dotar al monitor y terminales de trading de una capacidad instantánea para decodificar la anatomía de las velas en el gráfico, cruzarla con el volumen institucional (VPA/Wyckoff), medir confluencias con niveles clave (Soporte, Resistencia, EMA 20, VWAP) y dictaminar si existe una asimetría matemática ejecutable ($R:R \ge 1:2$ o $1:3$) o si el operador debe ignorar el ruido.

---

## 🏛️ 1. ATLAS CUANTITATIVO DE FORMACIONES Y BENCHMARK BULKOWSKI

El agente no opera sobre "figuras subjetivas"; se rige exclusivamente por el estudio empírico de más de 4.7 millones de velas en NYSE/NASDAQ y futuros regulados (Thomas Bulkowski Benchmark) y la taxonomía del **Atlas Cuantitativo de Velas Japonesas v2.0**:

### Matriz de Fiabilidad Estadística

| Patrón | Tipo | Frecuencia | Efectividad (%) | Movimiento Promedio | Confirmación Exigida | Veredicto Institucional |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Morning Star (Estrella Mañana)** | Reversión Alcista | Rango 5 (Común) | **78% de éxito** | +5.2% en 10 barras | Moderada | Señal A+ en soporte mayor. Excelente R:R institucional. |
| **Evening Star (Estrella Atardecer)** | Reversión Bajista | Rango 7 (Frecuente) | **72% de éxito** | -4.8% en 10 barras | Moderada | Alta probabilidad de techo en sobrecompra y distribución. |
| **Three White Soldiers (3 Soldados)** | Continuación / Giro | Rango 32 (Poco frecuente) | **82% de continuidad**| +6.4% posterior | Baja | Momentum institucional extremo. Cuidado si RSI > 70. |
| **Rising Three Methods (3 Métodos)**| Continuación Alcista | Rango 45 (Raro) | **74% de continuidad**| +4.9% posterior | Baja | Descanso sano de la tendencia; volumen seco en corrección. |
| **Bullish Engulfing (Envolvente Alc.)**| Reversión Alcista | Rango 2 (Muy Común) | **63% de éxito** | +4.1% | Alta (esperar cierre)| Fiable solo si el volumen del 2º cuerpo duplica al 1º. |
| **Bearish Engulfing (Envolvente Baj.)**| Reversión Bajista | Rango 3 (Muy Común) | **63% de éxito** | -4.3% | Alta (esperar cierre)| Fuerte absorción de oferta institucional. Trampa de toros. |
| **Hammer (Martillo)** | Reversión Alcista | Rango 1 (Más visto) | **60% de éxito** | +3.8% | Obligatoria | En rangos suele fallar; en soporte mayor con volumen es letal. |
| **Shooting Star (Estrella Fugaz)** | Reversión Bajista | Rango 4 (Muy Común) | **59% de éxito** | -3.9% | Obligatoria | Rechazo agresivo de liquidez en resistencias o nuevos máximos. |
| **Dragonfly Doji (Doji Libélula)** | Indecisión / Suelo | Rango 2 (Frecuente) | **51% aislado / 71% en soporte** | Dependiente de nivel| Crítica y Excluyente | Moneda al aire en el aire; con absorción de soporte es señal A+. |

---

## 📐 2. FORMULACIÓN MATEMÁTICA DE ANATOMÍA (MOTOR JS / PYTHON)

Para que el sistema clasifique la vela en microsegundos sin sesgo visual ni consumo de tokens:

### Variables Base
* $\text{Rango Total} = \text{High} - \text{Low}$
* $\text{Cuerpo} = |\text{Close} - \text{Open}|$
* $\text{Mecha Superior} = \text{High} - \max(\text{Open}, \text{Close})$
* $\text{Mecha Inferior} = \min(\text{Open}, \text{Close}) - \text{Low}$

### Reglas Algorítmicas de Clasificación
1. **Doji Clásico / Libélula:**
   $$\text{Cuerpo} \le 0.05 \times \text{Rango Total}$$
   * Libélula: $\text{Mecha Inferior} \ge 3 \times \text{Cuerpo}$ y $\text{Mecha Superior} \le 0.10 \times \text{Rango Total}$.
2. **Martillo (Hammer):**
   $$\text{Mecha Inferior} \ge 2.0 \times \text{Cuerpo} \quad \land \quad \text{Mecha Superior} \le 0.10 \times \text{Rango Total} \quad \land \quad \text{Close} \ge \text{Open}$$
3. **Estrella Fugaz (Shooting Star):**
   $$\text{Mecha Superior} \ge 2.0 \times \text{Cuerpo} \quad \land \quad \text{Mecha Inferior} \le 0.10 \times \text{Rango Total}$$
4. **Envolvente Alcista (Bullish Engulfing):**
   $$\text{Vela}_{t-1}.\text{Close} < \text{Vela}_{t-1}.\text{Open} \quad \land \quad \text{Vela}_t.\text{Close} > \text{Vela}_t.\text{Open}$$
   $$\text{Vela}_t.\text{Open} \le \text{Vela}_{t-1}.\text{Close} \quad \land \quad \text{Vela}_t.\text{Close} \ge \text{Vela}_{t-1}.\text{Open}$$
   $$\text{Volumen}_t \ge 1.8 \times \text{Volumen}_{t-1}$$
5. **Estrella de la Mañana (Morning Star - 3 Velas):**
   * $\text{Vela}_1$: Rango amplio bajista.
   * $\text{Vela}_2$: Doji o cuerpo estrecho con gap bajista relativo ($\text{Cuerpo}_2 \le 0.35 \times \text{Cuerpo}_1$).
   * $\text{Vela}_3$: Alcista fuerte que penetra al menos el $50\%$ del cuerpo de $\text{Vela}_1$:
     $$\text{Vela}_3.\text{Close} \ge \text{Vela}_1.\text{Close} + 0.50 \times (\text{Vela}_1.\text{Open} - \text{Vela}_1.\text{Close})$$

---

## ⚡ 3. COMPORTAMIENTO DEL VOLUMEN (VPA / WYCKOFF)

Una vela sin volumen es una ilusión óptica. El agente audita:
* **RVOL (Relative Volume):**
  $$\text{RVOL} = \frac{\text{Volumen Actual}}{\text{Media de Volumen (20 periodos)}}$$
* **Absorción Institucional:** RVOL $\ge 1.8$ con vela de rechazo (mecha inferior extensa) en soporte. Significa que el dinero inteligente colocó órdenes pasivas de compra y absorbió la capitulación minorista.
* **Esfuerzo vs. Resultado (Anomalía Wyckoff):** RVOL muy alto pero con cuerpo pequeño cerca de resistencia = distribución oculta y agotamiento (alerta inminente de giro bajista).
* **Secado de Oferta:** Pullback de 3 velas con volumen decreciente sostenido ($\text{Vela}_t < \text{Vela}_{t-1} < \text{Vela}_{t-2}$) = retroceso sano para continuación tendencial (Rising Three Methods).

---

## 🎯 4. PROTOCOLO DUAL DE EVALUACIÓN (EN VIVO vs HISTÓRICO)

Para erradicar el sesgo del "diario del lunes" (*hindsight bias*):

### Modo A: Evaluación en Vivo (Forward-Blind / Última Vela)
1. **Contexto Previo (10 Velas Anteriores):**
   * Determinar tendencia inmediata respecto a la EMA 20 y VWAP institucional.
   * Localizar el nivel clave más cercano (Soporte o Resistencia).
2. **Análisis de la Vela Actual:**
   * Clasificar la anatomía y medir RVOL.
3. **Cálculo de Asimetría Obligatoria ($R:R$):**
   * $\text{Stop Loss} = \text{Mínimo del Cuadrante} - 1.5 \times ATR$.
   * $\text{Take Profit} = \text{Siguiente Resistencia Mayor o Banda Superior VWAP}$.
   * **Regla de Oro:** Si $\frac{\text{Take Profit} - \text{Precio}}{\text{Precio} - \text{Stop Loss}} < 2.0 \implies \mathbf{🟡 \; IGNORAR \; / \; ESPERAR}$.
   * **Gatillo de Compra:** Solo si confluencia de patrón alcista + soporte/VWAP + RVOL > 1.5 + $R:R \ge 1:2 \implies \mathbf{🟢 \; COMPRAR \; (LONG)}$.

### Modo B: Evaluación Histórica (Estudio y Backtesting en 2 Tiempos)
Cuando el usuario hace clic sobre una vela pasada:
1. **Fase 1 (Tesis a Ojos Vendados):**
   * El agente ignora todo lo que ocurrió a la derecha.
   * Emite la hipótesis que el operador habría tenido en ese segundo exacto: *"Señal de Compra generada a \$143.60 con SL \$134.20 y TP \$162.00 (R:R 1:2.0) por Martillo en Soporte con RVOL 2.1"*.
2. **Fase 2 (Auditoría con el Diario del Lunes):**
   * El agente inspecciona las siguientes 5 a 10 barras posteriores.
   * Dictamina el resultado real sin maquillar:
     * *«✅ Señal confirmada: En la barra +3 alcanzó el Take Profit (+5.2%). Absorción efectiva.»*
     * *«❌ Trampa de mercado: En la barra +1 el precio perforó el mínimo y activó el Stop Loss. Falso quiebre por divergencia de volumen.»*

---

## 📋 5. PROTOCOLO DE CONFLUENCIA INSTITUCIONAL (CHECKLIST DE 5 FACTORES)

Para que el agente apruebe una tesis con alta convicción ($> 80\%$ de confianza), debe validar:
1. **Tendencia Previa Clara:** Precedida por un movimiento extendido fuera del rango medio.
2. **Ubicación en Nivel Mayor:** Confluencia con Soporte/Resistencia diario, EMA 20 o Banda VWAP ($\pm 2\sigma$).
3. **Anatomía Rigurosa:** Cumplimiento estricto de las proporciones matemáticas de la formación.
4. **Validación VPA:** RVOL $\ge 1.8$ en el gatillo o volumen seco en el pullback.
5. **Confirmación de Cierre:** Superación del máximo (en compras) o perforación del mínimo (en ventas) en la vela posterior.

---

## 🛡️ 6. TRANSPARENCIA EPISTÉMICA Y BLINDAJE DE COSTOS

* **Transparencia:** Todo cálculo de precio, nivel y ratio es determinista y contrastado contra el pipeline del gráfico. Si se emite una interpretación sobre intenciones de mercado, etiquetarla como `[Inferencia Wyckoff]`.
* **Zero-Token Latency:** El seguimiento con el cursor (hover) y el cálculo de cuadrante se ejecutan al 100% en el cliente vía JavaScript. No se invoca ningún modelo de lenguaje en el movimiento de ratón.
* **Consulta IA Bajo Demanda:** Solo si el usuario presiona expresamente *"Consultar Razonamiento IA"* se enviará un payload JSON compacto con el cuadrante a Ollama local (`trader-qwen`) o Gemini, blindado contra bucles infinitos.

---

## 🔬 7. VALIDACIONES CUANTITATIVAS AVANZADAS (DIVERGENCIAS RSI, ATR SQUEEZE Y MULTI-TIMEFRAME)

Para elevar la auditoría al estándar de un fondo cuantitativo institucional y erradicar falsos rompimientos en horas muertas:

### 1. Motor de Divergencias RSI (El Filtro Institucional Definitivo)
El RSI estático ($>70$ o $<30$) es insuficiente: en tendencias fuertes, el oscilador puede permanecer en sobreventa durante horas mientras el precio continúa sangrando.

* **Divergencia Regular Alcista (Gatillo A+ de Reversión):**
  $$\text{Precio}_t < \text{Precio}_{t-k} \quad (\text{Mínimo más bajo / Lower Low}) \quad \land \quad \text{RSI}_t > \text{RSI}_{t-k} \quad (\text{Mínimo más alto / Higher Low})$$
  *Efecto:* Prueba que la velocidad de venta se está agotando aunque el precio caiga por inercia. Transforma un Martillo o Doji Libélula en una señal de confluencia máxima.
* **Divergencia Regular Bajista (Gatillo A+ de Techo):**
  $$\text{Precio}_t > \text{Precio}_{t-k} \quad (\text{Máximo más alto / Higher High}) \quad \land \quad \text{RSI}_t < \text{RSI}_{t-k} \quad (\text{Máximo más bajo / Lower High})$$
  *Efecto:* Trampa de liquidez en euforia. Advierte salida institucional inminente (Estrella Fugaz o Estrella del Atardecer).
* **Penalización Obligatoria:** Si un patrón de giro carece de divergencia RSI confirmada, se debe **reducir el nivel de confianza del informe en un 15%** y exigir confirmación estricta de la vela siguiente.

### 2. Filtro de Compresión de Volatilidad (ATR Squeeze / Mercado Muerto)
El ATR mide el combustible real del mercado en dólares.
* **Ratio de Squeeze:**
  $$\text{ATR\_Ratio} = \frac{\text{ATR}_{14}}{\text{SMA}_{20}(\text{ATR}_{14})}$$
* **Estado "Mercado en Compresión" (Squeeze):**
  Si $\text{ATR\_Ratio} < 0.70$ (es decir, el ATR actual está un 30% o más por debajo de su media móvil de 20 periodos), el mercado está lateralizado, seco de liquidez y sin rango para alcanzar el Take Profit.
* **Directiva de Veto Inviolable:** En compresión, **IGNORAR obligatoriamente todos los patrones de continuación** (ej. Tres Soldados Blancos, Tres Métodos) porque la probabilidad de falsa ruptura (*whipsaw*) se dispara al 70%. Solo operar reversiones extremas en los bordes de bandas VWAP o esperar expansión de volatilidad.

### 3. Alineación de Fractalidad (Multi-Timeframe / Regla de la Marea Mayor)
Ningún algoritmo institucional opera contra la marea de la temporalidad superior.
* **Matriz de Jerarquía Temporal:**
  * **Operativa M1 / M5:** Auditar sesgo en **M15 / H1**.
  * **Operativa M15:** Auditar posición respecto a la **EMA 200 en H1** (1 Hora).
  * **Operativa H1:** Auditar tendencia y soporte mayor en **1D (Diario)**.
* **Regla de Veto de Tendencia Mayor:**
  * **Vetar compras en M15** si en H1 el precio cotiza por debajo de la EMA 200 con pendiente negativa.
  * **Vetar ventas en corto en M15** si en H1 el precio cotiza por encima de la EMA 200 con pendiente positiva.
  * **Gatillo A+:** Solo se autoriza transmisión al Cerebro Operador cuando la vela local (M15), el oscilador (RSI), el combustible (ATR) y la marea macro (H1) apuntan en la misma dirección.
