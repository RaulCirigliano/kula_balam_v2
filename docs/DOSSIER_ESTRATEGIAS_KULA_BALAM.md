# Dossier Técnico de Arquitectura y Catálogo de Estrategias: Ecosistema Kula · Balam

Este documento detalla el funcionamiento operativo, los mecanismos de gobernanza de riesgo y las especificaciones técnicas de las 5 estrategias de mercado implementadas en el sistema para su auditoría y evaluación algorítmica.

---

## 1. Arquitectura de Ejecución y Gobernanza de Riesgo

El sistema desacopla la decisión de capital, la compuerta de seguridad y las fórmulas tácticas deterministas en tres capas jerárquicas:

```
[ MERCADO OHLCV ]
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. CEREBRO KULA (Portfolio & Vault Manager)                 │
│    • Bóveda Sweep-Back y cuenta de riesgo segregada.        │
│    • Dimensionamiento de posición: Criterio Quarter-Kelly.   │
│    • Multi-Slot Dinámico: 25%, 50% o 100% según régimen.    │
│    • Contabilidad formal por partida doble en SQLite.       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. FÓRMULAS TÁCTICAS AUTORIZADAS (allowed_strategies)       │
│    • El operador selecciona qué estrategias están activas.  │
│    • Evaluación paralela determinista en Python puro.       │
│    • Selección por Máxima Asimetría: Gana el mayor R:R neto.│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. PORTERO CENTINELA BALAM (Risk Gatekeeper)                │
│    • Veto por Cuchillo Cayendo (Falling Knife Shield).      │
│    • Veto Bull Trap y Bear Trap (absorción contraria).      │
│    • Veto Clímax de Sobreventa (RSI <= 30 en cortos).       │
│    • Blindaje "Stop a Misa": Extremo técnico + 2 ticks ATR. │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼ [Aprobado: R:R >= 1:2.0]
┌─────────────────────────────────────────────────────────────┐
│ 4. DAEMON BROKER / PAPER TRADING                            │
│    • Registro contable con subestrategia exacta en SQLite.  │
└─────────────────────────────────────────────────────────────┘
```

### Reglas Universales de Salida del Sistema
1. **Asimetría Matemática Obligatoria:** Ninguna orden es autorizada si el ratio beneficio/riesgo neto de comisiones y spread no cumple $R:R \ge 1:2.0$.
2. **Stop a Misa con Holgura de Seguridad:** El Stop Loss jamás se coloca en el soporte/resistencia obvio donde cazan los creadores de mercado. Se le suma automáticamente un margen estructural de invalidación:
   $$\Delta_{\text{stop}} = \max \left( 2 \times \text{TickSize}, \, 0.15 \times \text{ATR}_{14}, \, 0.0015 \times \text{Precio} \right)$$
3. **Peluqueo Sistemático 50/50 (Doctrina Cava / Chu):** Al alcanzar el primer objetivo (TP1 con $R:R \ge 1:2.0$), se liquida el **50% de la posición**, financiando el riesgo del trade. El Stop Loss se traslada automáticamente a **Breakeven ($+1$ tick)** para garantizar que la operación remanente corra a riesgo cero (*Free-Roll*).

---

## 2. Catálogo Oficial de Estrategias

---

### Estrategia 1: Cava & Ruiz (`kula_balam_cava_ruiz`)
* **Autoría:** Fusión Alex Ruiz (Tríada fractal) + José Luis Cava (Doctrina de parqué).
* **Marco Temporal:** Tríada Fractal 1D $\rightarrow$ 1H $\rightarrow$ 5M.
* **Activos Recomendados:** BTC/USDT, ETH/USDT, SOL/USDT, QQQ, SPY, NVDA.
* **Régimen de Mercado:** Tendencias saludables con retrocesos ordenados a zonas de valor.
* **Mecánica de Entrada:**
  * **1D (Contexto):** Precio cotizando sobre la media de referencia en estructura alcista.
  * **1H (Estructura):** Retroceso correctivo en la **Zona Dorada de Fibonacci** (entre el $0.50$ y el $0.75$ del impulso previo) en confluencia con la $\text{EMA}_{50}$. Si perfora el $0.75$, se anula la hipótesis por estructura rota.
  * **Agotamiento Onda C (Cava):** Secado evidente de volumen en la corrección ($\text{RVOL} < 0.85$) con divergencia o fallo en MACD/RSI.
  * **5M (Gatillo):** Cierre de vela con mecha de rechazo inferior $\ge 30\%$ del rango total reaccionando en un nodo de alto volumen previo (POC).
* **Gestión de Salida:** Stop a Misa bajo el mínimo de invalidación $+2$ ticks. Peluqueo del $50\%$ en TP1 ($R:R \ge 1:2.0$) con pase a Breakeven y Trailing Stop libre en TP2.
* **Subestrategias Conmutables:** `[x] Operar Long`, `[x] Operar Short`, `[x] Zona Dorada Fibo (0.50-0.75)`, `[x] Fallo MACD`, `[x] Secado RVOL < 0.85`, `[x] Peluqueo TP1`.

---

### Estrategia 2: Tres Velas & Wyckoff VPA (`tres_velas_wyckoff_bulkowski`)
* **Autoría:** Richard Wyckoff (Price Action & Volume) + Thomas Bulkowski (Benchmark 4.7M de velas).
* **Marco Temporal:** Multitemporal con ejecución táctica en 5M y 15M.
* **Activos Recomendados:** Criptoactivos de alta liquidez y acciones líderes de Wall Street.
* **Régimen de Mercado:** Consolidaciones, fases de acumulación institucional y rupturas de volatilidad.
* **Mecánica de Entrada:**
  * Detecta maniobras de absorción institucional (*Spring* o falso quiebre bajista recuperado).
  * Evalúa patrones empíricos de alto acierto de Bulkowski:
    * *Three White Soldiers* (tasa histórica de acierto del $82\%$).
    * *Morning Star / Estrella de la Mañana* (tasa de acierto del $78\%$).
    * *Bullish Engulfing / Vela Envolvente* (tasa de acierto del $68\%$).
    * *Hammer en Soporte* con mecha inferior $\ge 60\%$.
  * Exige confirmación de volumen institucional anormal ($\text{RVOL} \ge 1.30$) y confluencia sobre el VWAP intradiario.
* **Gestión de Salida:** Stop Loss bajo la zona de absorción $+2$ ticks. TP1 escalado a $2.5 \times \text{ATR}$ con peluqueo y trailing stop remanente.
* **Subestrategias Conmutables:** Casillas independientes para cada patrón de Bulkowski, filtro de volumen Wyckoff y confluencia VWAP.

---

### Estrategia 3: Alex Ruiz Tríada de las 3 Velas (`alex_ruiz_triada_3velas`)
* **Autoría:** Alex Ruiz (*Gatillo Algorítmico de Acciones*) con blindaje de parqué.
* **Marco Temporal:** Tríada Fractal 1D $\rightarrow$ 1H $\rightarrow$ 5M.
* **Activos Recomendados:** BTC/USDT, ETH, SOL, QQQ, SPY, NVDA, AAPL, GC=F (Oro COMEX), CL=F (Petróleo).
* **Régimen de Mercado:** Operativa bidireccional (LONG y SHORT) en tendencias definidas.
* **Especialización en Oro y Commodities (`GC=F`):**
  * *Candado Horario COMEX:* Lunes a Viernes de 09:30 a 14:00 ARG (cruce Londres - Nueva York).
  * *Zona Dorada Acotada:* Fibo 0.50 a 0.70 (invalida si rebasa 0.72).
  * *Risk-Guards de Metales:* Veto Bull Trap y Bear Trap al 35% de mecha (`wick_max = 0.35`) y colchón $\Delta_{\text{stop}} = 0.25 \times \text{ATR}$.
  * *Bóveda:* Paper Trading con nocional fraccionado de onzas contra la cuenta `OP_USD`.
* **Mecánica de Entrada (Bidireccional):**
  * **En LONG:**
    1. 1D: Estructura macro alcista sobre $\text{EMA}_{50}$.
    2. 1H: Retroceso que descansa en la Zona Dorada de Fibonacci ($0.50 - 0.75$).
    3. 5M (Gatillo de 3 Velas): $V_1$ (impulso), $V_2$ (pausa/testeo en $\text{EMA}_{50}$ con mecha de rechazo) y $V_3$ (confirmación alcista que quiebra el máximo de $V_2$ y cierra sobre $\text{EMA}_{50}$).
  * **En SHORT (Venta en Corto):**
    1. 1D: Estructura macro bajista bajo $\text{EMA}_{50}$.
    2. 1H: Rebote correctivo contratendencial hacia la Zona Dorada Fibo ($0.50 - 0.75$).
    3. 5M (Gatillo de 3 Velas en Corto): $V_1$ (rebote contra resistencia), $V_2$ (pausa) y $V_3$ (confirmación bajista que quiebra el mínimo de $V_2$ y cierra bajo $\text{EMA}_{50}$).
* **Compuertas Defensivas de Seguridad (Risk-Guards):**
  * **Veto *Bear Trap*:** Anula ventas cortas si la vela presenta una mecha inferior $\ge 40\%$ (absorción de compras).
  * **Veto Clímax de Sobreventa:** Prohíbe terminantemente abrir cortos si $\text{RSI}_{14} \le 30$ (neutraliza el riesgo de *short squeeze* violento).
  * **Veto *Bull Trap*:** Anula compras si la vela presenta una mecha superior $\ge 40\%$.
  * **Veto Cohete Alcista:** Prohíbe cortos si la vela 1H previa fue una expansión vertical sin consolidación ($\text{RVOL} > 2.0$).
* **Gestión de Salida:** Stop a Misa con margen de 2 ticks adaptativo. Peluqueo 50/50 en TP1 ($R:R \ge 1:2.0$) y trailing guiado por la $\text{EMA}_{50}$ en 5M.

---

### Estrategia 4: Nasdaq Araujo VWAP Wall Street (`nasdaq_araujo_vwap`)
* **Autoría:** Franklin Araujo (*Francotirador de Apertura*).
* **Marco Temporal:** Intradía M15.
* **Activos Recomendados:** QQQ, SPY, NQ=F, NVDA, AAPL, MSFT, TSLA, CEDEARs de BYMA.
* **Régimen de Mercado:** Campana de apertura de Wall Street y volatilidad institucional en torno al VWAP.
* **Candados y Seguros de Parqué:**
  * **Candado de Activos:** Exclusivo para renta variable de Wall Street e índices. Veta de forma terminante pares cripto 24/7 (donde el VWAP no tiene campana de apertura ni reinicio de volumen).
  * **Candado Horario Estricto (Time-Window Gate):** Rueda de Lunes a Viernes de **09:35 a 11:00 NY (10:35 a 12:00 ARG)**. Fuera de esa ventana entra en reposo absoluto ($0\%$ cómputo).
  * **Salto Anti-Caos de los Primeros 5 Minutos (09:30 a 09:35 NY):** Veta órdenes durante la subasta de apertura inicial mientras el VWAP acumula muestra suficiente y estabiliza su flujo.
  * **Rechazo Obligatorio contra VWAP:**
    * *En LONG:* Precio sobre VWAP diario con testeo y mecha inferior $\ge 30\%$, o ruptura del rango de la sesión europea de Londres con volumen.
    * *En SHORT:* Precio bajo VWAP diario con testeo y mecha superior $\ge 30\%$, o quiebre del soporte de Londres.
  * **Volumen Institucional:** Exige $\text{RVOL} \ge 1.20$.
  * **Risk-Guards:** Veto *Bear Trap* ($\ge 40\%$), Veto *Bull Trap* ($\ge 40\%$) y Veto Sobreventa $\text{RSI} \le 30$.
* **Gestión de Salida:** Stop a Misa más allá del VWAP $+2$ ticks. Peluqueo del $50\%$ en TP1 ($R:R \ge 1:2.0$) con pase a Breakeven y trailing stop en VWAP.

---

### Estrategia 5: Hyenuk Chu Swing Trend & Trim (`hyenuk_chu_multibagger`)
* **Autoría:** Hyenuk Chu (Filosofía secular multibagger de 20 años en Wall Street).
* **Marco Temporal:** Gráfico Horario 1H (Swing Trading de 2 a 10 días).
* **Activos Recomendados:** NVDA, TSLA, BTC/USDT, QQQ, SPY, CEDEARs líderes de BYMA (YPFD, GGAL, PAMP).
* **Régimen de Mercado:** Grandes olas tendenciales seculares saliendo de acumulaciones de largo plazo.
* **Mecánica de Entrada y Seguros:**
  * **Direccionalidad Exclusiva en LONG:** Prohíbe compras en corto por asimetría de ruina matemática en activos corporativos.
  * **Gatillo de Vela Elefante de Ignición:** Vela verde amplia de expansión ($\text{Range} \ge 1.0 \times \text{ATR}_{14}$), control comprador con mecha superior pequeña ($\le 25\%$ del rango) y volumen institucional participante ($\text{RVOL} \ge 1.10$).
  * **Alineación Tendencial:** Precio sobre $\text{EMA}_{200}$ alcista y sobre $\text{SMA}_{20}$.
  * **Filtro Contrario Anti-Euforia:** Veto taxativo si $\text{RSI}_{14} > 75$ (evita comprar en techos de euforia masiva). Impulso mínimo $\text{RSI}_{14} \ge 45$.
  * **Stop Estructural al 50% de la Vela Elefante:** Ubicado en el punto de equilibrio de la subasta ($50\%$ del cuerpo de la vela elefante) o en su mínimo técnico, sumando **2 ticks de margen**.
  * **Peluqueo 50/50 y Free-Roll:** Al alcanzar TP1 ($+3.5\%$ a $+5.0\%$ neto con $R:R \ge 1:2.0$), liquida el $50\%$ de la posición para financiar el riesgo y traslada el Stop Loss a Breakeven ($+1$ tick). El $50\%$ restante corre libre persiguiendo la $\text{SMA}_{20}$ horaria de 2 a 10 días.

---

## 3. Matriz Comparativa de Fórmulas

| Estrategia | Timeframe | Dirección | Activo Objetivo | Ventana Operativa | Stop Loss | TP1 / Peluqueo |
| :--- | :---: | :---: | :--- | :--- | :--- | :--- |
| **Cava & Ruiz** | 1D-1H-5M | Long / Short | Cripto & Acciones Líderes | 24/7 Cripto · Rueda Wall Street | Invalidación Fibo $+2$ ticks | 50% en $R:R \ge 1:2.0$ $\rightarrow$ BE |
| **Wyckoff Bulkowski** | 5M / 15M | Long | Cripto & Wall Street | Rupturas de Acumulación | Suelo de Absorción $+2$ ticks | 50% en $2.5\times\text{ATR}$ $\rightarrow$ BE |
| **Alex Ruiz Tríada** | 1D-1H-5M | Long / Short | Cripto & Wall Street | 24/7 Cripto · Rueda Wall Street | Extremo 3 Velas $+2$ ticks | 50% en $R:R \ge 1:2.0$ $\rightarrow$ BE |
| **Nasdaq Araujo** | M15 | Long / Short | Exclusivo Wall Street (QQQ/SPY) | Lun-Vie 09:35 - 11:00 NY | Extremo VWAP $+2$ ticks | 50% en $R:R \ge 1:2.0$ $\rightarrow$ BE |
| **Hyenuk Chu Swing** | 1H | Solo LONG | Acciones Líderes & Cripto Swing | Continuo (Swing 2 a 10 días) | 50% Vela Elefante $+2$ ticks | 50% en $+3.5\%$ a $+5.0\%$ $\rightarrow$ BE |

---

## 4. Gobernanza Dinámica: El Gestor de Estrategias

Todas las estrategias están gobernadas por el **Gestor de Estrategias** (`config_manager.py` y modal en frontend):
1. **Feature Toggling:** Cada compuerta interna cuenta con casillas de verificación independientes (ej. `[x] Operar Long`, `[x] Operar Short`, `[x] Veto Bear Trap`, `[x] Veto Sobreventa RSI <= 30`, `[x] Peluqueo TP1`).
2. **Blindaje Decimal:** Sanitización transparente de comas y puntos (`.replace(',', '.')`), permitiendo calibrar parámetros cuantitativos sin errores de conversión.
3. **Restablecimiento de Fábrica (*Fail-Safe Reset*):** Cada estrategia cuenta con el botón `🔄 Reset Fábrica` respaldado por `POST /api/estrategias/reset_defaults` para restaurar los parámetros matemáticos óptimos con un solo clic.
4. **Auditoría Forense Granular:** El daemon registra en cada orden el identificador exacto de la subestrategia ejecutada (`triada_3velas_long`, `triada_3velas_short`, `araujo_vwap_short`, `chu_swing_long`), permitiendo auditar el rendimiento individual en el *Scorecard* de `auditar_sqlite.py`.