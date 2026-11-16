# 🏛️ GUÍA MAESTRA DE CONFIGURACIÓN TURNKEY — ECOSISTEMA ANTIGRAVITY
### *Trading Ollama (:18767) + Monitor del Mercado (:8520 / :8521)*
**Director de Inversiones (CIO) & Auditor Estratégico Cuantitativo**

---

## 📌 Visión de Arquitectura del Ecosistema

```mermaid
flowchart TD
    A["Monitor del Mercado (:8520 / :8521)"] -->|1. Ingesta Cuantitativa & RSS| B["Antigravity CIO (Razonamiento Superior)"]
    B -->|2. Filtro 3 Verdades Contraintuitivas| B
    B -->|3. POST /api/cio/publish (auto_inject: true)| A
    A -->|4. Puente HTTP /api/macro/inject| C["Trading Ollama (:18767 Cockpit)"]
    C -->|5. Ejecución Automática / Copiloto| D["Broker / Exchange (Simulado o Real)"]
```

Esta guía define la calibración exacta y reproducible de cada componente visual y operativo de **Trading Ollama** (Cockpit) y **Monitor del Mercado** (Terminal Cuantitativa) para 3 estrategias canónicas de grado institucional.

---

## 🧭 MAPA DE COMPONENTES DEL PANEL (TRADING OLLAMA)

| Componente Visual | Elemento / ID HTML | Función Operativa |
| :--- | :--- | :--- |
| **Navbar Superior** | `#assetSelect` | Selector del activo en pantalla (Cripto, Macro, Big Tech, BYMA). |
| **Navbar Superior** | `#navAgentModeSelect` | Modo de Ruteo: `🧠 Inteligente (Multi-Activo)`, `⚡ Autónomo (Activo Fijo)` o `🛡️ Copiloto`. |
| **Navbar Superior** | `#agentToggle` | Interruptor maestro de encendido/apagado del bot de trading. |
| **Ajustes de Estrategia** | `#timeframeSelect` | Temporalidad de análisis (`1m`, `5m`, `15m`, `1h`). |
| **Ajustes de Estrategia** | `#strategyModeSelect` | Motor operativo: `Manual (TP/SL porcentual)` o `Cuantitativa (Reversión ATR)`. |
| **Gestión de Riesgo** | `#riskSelect` | Tamaño de posición manual (`25%`, `50%`, `100%` del capital asignable). |
| **Gestión de Riesgo** | `#quantRiskBudgetSelect` | Presupuesto de riesgo ATR (`0.25%`, `0.50%`, `1.00%` pérdida máx/trade). |
| **Parámetros TP/SL** | `#tpSlSelect` | Rango bruto objetivo (`0.5|-0.3`, `0.8|-0.5`, `1.5|-1.0`, `3.0|-2.0`). |
| **Filtro Anti-Desgaste** | `#minProfitPctInput` | Beneficio neto mínimo tras comisiones y spread (ej. `0.15%`, `0.30%`). |
| **Estructura de Costos** | `#brokerFeeSelect` | Comisión del broker por orden (`0.10%` Cripto, `0.02%` US, `0.00%` Cero, `0.50%` ARS). |
| **Estructura de Costos** | `#spreadInput` | Spread estimado por lado (`0.05%` estándar, `0.02%` líquidos). |
| **Control Horario** | `#scheduleModeSelect` | Régimen: `24/7 (Libre)` o `Rango Horario Específico (timeStart / timeEnd)`. |
| **Motor de Análisis** | `#engineSelect` | Cerebro: `🤖 Qwen 2.5 (trader-qwen)`, `⚙️ Local Matemático` o `✨ Gemini`. |
| **Radar Macro** | `#investmentToggle` | Interruptor del receptor de tesis macro/contrarian. |
| **Radar Macro** | `#investmentSourceSelect`| Fuente de tesis: `🖥️ Monitor del Mercado (:8520)`. |
| **Terminal de Control** | `#decisionLog` | Registro en tiempo real de validaciones matemáticas, veto de IA y órdenes. |

---

## ⚡ LAS 3 ESTRATEGIAS CANÓNICAS TURNKEY

---

### 🟢 ESTRATEGIA 1: Micro-compras (Scalping Cripto 24/7 / Fuera de Horario)
> **Objetivo:** Capturar micro-ganancias rápidas en activos de negociación continua (24/7) explotando ineficiencias de corto plazo sin exposición nocturna prolongada.

#### 1. Configuración del Cockpit (Trading Ollama :18767)
* **Navbar Superior:**
  * **Activo Inicial:** `BTC/USDT` (o `ETH/USDT`, `SOL/USDT`).
  * **Modo de Agente (`#navAgentModeSelect`):** `🧠 Inteligente (Multi-Activo)` *(o `⚡ Autónomo` si se opera un solo par)*.
* **Ajustes de Estrategia:**
  * **Temporalidad (`#timeframeSelect`):** `5m (Equilibrado)` *(o `1m` para ráfagas de alta liquidez)*.
  * **Estrategia de Trading (`#strategyModeSelect`):** `Manual: TP/SL porcentual del panel`.
  * **TP / SL (`#tpSlSelect`):** `Scalping Intradía (+0.8% / -0.5%) [Recomendado]` *(o `Scalping Rápido (+0.5% / -0.3%)`)*.
* **Gestión de Riesgo:**
  * **Tamaño de Posición (`#riskSelect`):** `25% del capital (Conservador)` *(máximo `50%`)*.
  * **Beneficio Neto Mínimo (`#minProfitPctInput`):** `0.15%` *(innegociable para cubrir costos)*.
* **Costos y Comisiones:**
  * **Comisión Broker (`#brokerFeeSelect`):** `0.10% (Cripto Spot - Binance / Bybit)` *(o `0.05%` si se usan BNB/VIP/Maker)*.
  * **Spread Estimado (`#spreadInput`):** `0.05%`.
  * *Verificación:* El badge de costos ida/vuelta debe marcar $\le 0.30\%$.
* **Horario de Operación:**
  * **Horario (`#scheduleModeSelect`):** `24/7 (Libre)`.
* **Cerebro y Radar:**
  * **Motor de Análisis (`#engineSelect`):** `🤖 Qwen 2.5 (IA Local · trader-qwen)` *(o `⚙️ Modelo Matemático Local`)*.
  * **Radar de Oportunidades (`#investmentToggle`):** `ON` (Activado).
  * **Fuente del Radar (`#investmentSourceSelect`):** `🖥️ Monitor del Mercado (:8520)`.

#### 2. Rol del Monitor del Mercado (:8520 / :8521)
* **Categoría de Escaneo:** `crypto_and_alternatives` (Criptoactivos).
* **Vigilancia Cuantitativa:** Filtrar $Z\text{-Score} \le -1.5$ sobre la $EMA_{200}$ de 15m/1h en `BTC-USD`, `ETH-USD` y `SOL-USD`.
* **Filtro Centinela de Noticias Críticas:** Monitorear shocks geopolíticos externos o saltos en crudo (`CL=F`) que drenen liquidez cripto hacia el dólar/oro.

---

### 🔵 ESTRATEGIA 2: Apertura Institucional (Nasdaq 100 / Franklin Araujo M15 + VWAP)
> **Objetivo:** Capturar la expansión direccional institucional provocada por la campana de apertura de Wall Street, operando falsos quiebres de pre-mercado/Londres apoyados en VWAP. Regla de oro: **1 trade al día**.

#### 1. Configuración del Cockpit (Trading Ollama :18767)
* **Navbar Superior:**
  * **Activo Inicial:** `QQQ` (Invesco QQQ Trust) *(o `SPY`, `NVDA`, `AAPL`)*.
  * **Modo de Agente (`#navAgentModeSelect`):** `⚡ Autónomo (Activo Fijo)` *(o `🛡️ Copiloto` para confirmación humana)*.
* **Ajustes de Estrategia:**
  * **Temporalidad (`#timeframeSelect`):** `15m (Tendencias seguras)`.
  * **Estrategia de Trading (`#strategyModeSelect`):** `Apertura Nasdaq: Franklin Araujo (M15 + VWAP)`.
  * **TP / SL (`#tpSlSelect`):** Auto-calculado técnicamente detrás de los extremos de Londres / M15 (o manual `Swing Corto +1.5% / -1.0%`).
* **Gestión de Riesgo:**
  * **Tamaño de Posición (`#riskSelect`):** `25% del capital (Conservador)`.
  * **Beneficio Neto Mínimo (`#minProfitPctInput`):** `0.20%`.
  * **Regla Disciplinaria:** **1 trade único por jornada**. Cerrada la posición (por TP o SL), apagar el agente.
* **Costos y Comisiones:**
  * **Comisión Broker (`#brokerFeeSelect`):** `0.02% (Acciones / ETFs EE.UU. - IBKR / Alpaca)` *(o `0.00%` Schwab/Robinhood)*.
  * **Spread Estimado (`#spreadInput`):** `0.03%`.
* **Horario de Operación (Ventana de Francotirador):**
  * **Horario (`#scheduleModeSelect`):** `Rango Horario Específico`.
  * **Desde (`#timeStart`):** `10:25` ARG (09:25 NY).
  * **Hasta (`#timeEnd`):** `12:30` ARG (11:30 NY).
  * *Razón:* Evita gaps ciegos y opera exclusivamente la primera hora y media de mayor volumen institucional.
* **Cerebro y Radar:**
  * **Motor de Análisis (`#engineSelect`):** `🤖 Qwen 2.5` o `✨ Google Gemini`.
  * **Radar de Oportunidades (`#investmentToggle`):** `ON`.
  * **Fuente del Radar (`#investmentSourceSelect`):** `🖥️ Monitor del Mercado (:8520)`.

#### 2. Protocolo Franklin Araujo (M15 + VWAP)
1. **Fase Pre-Market (10:00 - 10:25 ARG):** Marcar en el gráfico el Máximo y Mínimo de la sesión europea (Londres: 04:00 - 10:00 ARG).
2. **Campana (10:30 ARG):** Esperar la primera vela M15 (10:30 - 10:45 ARG).
3. **Condición de Entrada:**
   * **Largo:** Barrido de liquidez bajo el mínimo de Londres con rechazo y recuperación por encima de VWAP.
   * **Corto:** Barrido de liquidez sobre el máximo de Londres con rechazo y pérdida de VWAP.
4. **Veto:** Si el precio está enredado sobre VWAP sin volumen ($RVOL < 1.0$), **no operar**.
5. **Mecánica de Peluqueo (Trim 50%):** Al tocar el primer target de M15 (+1.5%), el daemon liquida el 50% a la Bóveda y mueve el Stop Loss del remanente a Breakeven ($0 de riesgo) para permitir que la otra mitad corra la sesión sin riesgo.

#### 3. Rol del Monitor del Mercado (:8520 / :8521)
* **Categorías de Escaneo:** `macro_and_markets` y `global_tech_and_china`.
* **Vigilancia Previa (10:00 ARG):** Revisar si el $Z\text{-Score}$ de `QQQ` o `SPY` está en extremos ($Z \ge +2.0$ euforia o $Z \le -2.0$ pánico) y contrastar con rendimientos de bonos `TLT`.

---

### 🟡 ESTRATEGIA 3: Swing Trend Following & Peluqueo (Hyenuk Chu 1h · 2 a 10 días)
> **Objetivo:** Explotar tendencias alcistas mayores en acciones de crecimiento o cripto (`NVDA`, `TSLA`, `BTC`, `SOL`, `QQQ`) durante 2 a 10 días, eliminando el riesgo con la técnica de Peluqueo (Trim al 50%) en el primer hito.

#### 1. Configuración del Cockpit (Trading Ollama :18767)
* **Navbar Superior:**
  * **Activo Inicial:** `NVDA` *(o `TSLA`, `BTC/USDT`, `QQQ`)*.
  * **Modo de Agente (`#navAgentModeSelect`):** `🧠 Inteligente` o `⚡ Autónomo`.
* **Ajustes de Estrategia:**
  * **Temporalidad (`#timeframeSelect`):** `1h (Swing / Tendencia Mayor)`.
  * **Estrategia de Trading (`#strategyModeSelect`):** `Swing Trend & Trim: Hyenuk Chu (1h · 2 a 10 días)`.
* **Reglas Cuantitativas:**
  * **Filtro Tendencial:** Precio $> \text{EMA200}$ con pendiente positiva y $> \text{SMA20}$.
  * **Filtro Contrario Anti-Euforia:** $RSI \le 75$ (prohibido comprar en techos de consenso).
  * **Volumen:** $RVOL \ge 0.90$.
* **Gestión de Salida Asimétrica (Peluqueo):**
  * **Hito 1 (+3.5%):** El bot liquida el 50% de la posición, asegura la ganancia en la Bóveda y mueve el Stop Loss del remanente al precio de compra (**Breakeven**).
  * **Runner (2 a 10 días):** El 50% restante corre con riesgo cero acompañando la tendencia semanal.
* **Costos:**
  * **Comisión:** Según activo (`0.02%` US, `0.10%` Cripto).
  * **Spread:** `0.02%` a `0.05%`.

---

### 🟣 ESTRATEGIA 4: Swing Cuantitativo Contrarian (Reversión a la Media ATR)
> **Objetivo:** Cazar suelos de capitulación extrema del mercado bajo la Primera Verdad Contraintuitiva (*"Comprar el dolor, vender la euforia"*) con invalidación matemática determinística por volatilidad.

#### 1. Configuración del Cockpit (Trading Ollama :18767)
* **Navbar Superior:**
  * **Activo Inicial:** Activo detectado por el CIO (`CL=F`, `GC=F`, `TLT`, `BABA`, `NVDA`, `GGAL.BA`).
  * **Modo de Agente (`#navAgentModeSelect`):** `🧠 Inteligente (Multi-Activo)`.
* **Ajustes de Estrategia:**
  * **Temporalidad (`#timeframeSelect`):** `15m` *(o `1h` para swing multidiario)*.
  * **Estrategia de Trading (`#strategyModeSelect`):** `Cuantitativa: Reversión a la Media (ATR)`.
  * *Efecto Inmediato:* Se oculta el TP/SL porcentual fijo y se activa el cálculo determinístico:
    $$\text{Target (TP)} = 2.5 \times ATR_{14} \quad | \quad \text{Stop Loss (SL)} = 1.5 \times ATR_{14}$$
* **Gestión de Riesgo Cuantitativo:**
  * **Presupuesto de Riesgo (`#quantRiskBudgetSelect`):** `0.25% (Conservador)` *(máximo `0.50%`)*.
  * *Principio:* El tamaño de posición se auto-calcula dividiendo el presupuesto de riesgo (\$ capital $\times 0.25\%$) por la distancia al Stop ATR.
  * **Beneficio Neto Mínimo (`#minProfitPctInput`):** `0.30%` a `0.50%`.
* **Costos y Comisiones:**
  * **Comisión Broker (`#brokerFeeSelect`):** Según activo (`0.02%` US, `0.10%` Cripto, `0.50%` BYMA).
  * **Spread Estimado (`#spreadInput`):** `0.05%`.
* **Horario de Operación:**
  * **Horario (`#scheduleModeSelect`):** `Rango Horario Específico` alineado al horario oficial del activo (BYMA 11:00-17:00, Wall Street 10:30-17:00, Commodities según futuros).
* **Cerebro y Radar:**
  * **Motor de Análisis (`#engineSelect`):** `🤖 Qwen 2.5 (IA Local)` o `✨ Gemini`.
  * **Filtro Python Primero:** Python valida primero $Z\text{-Score}(20) \le -2.0$, régimen alcista sobre $EMA_{200}$ y absorción de volumen ($RVOL \ge 1.0\text{x}$). La IA solo puede emitir veto defensivo.
  * **Radar de Oportunidades (`#investmentToggle`):** `ON` obligatorio.
  * **Fuente del Radar (`#investmentSourceSelect`):** `🖥️ Monitor del Mercado (:8520)`.

#### 2. Rol del Monitor del Mercado (:8520 / :8521)
* **Categorías de Escaneo:** `commodities_and_energy`, `macro_and_markets`, `argentina_and_latam`.
* **Vigilancia Cuantitativa:** Detección de activos con $Z\text{-Score} \le -2.0$ y $RSI \le 35$ acompañados de titulares de catástrofe temporal.
* **Auto-Inyección:** Publicación vía `POST /api/cio/publish` con `auto_inject: true` para que la directiva entre directamente al buzón del Cockpit con ratio $R/B \ge 1:3$.

---

## 📋 CHECKLIST RÁPIDO DE DESPLIEGUE POR ESTRATEGIA

| Parámetro | Estrategia 1 (Cripto Scalp) | Estrategia 2 (Apertura Nasdaq M15) | Estrategia 3 (Swing Cuantitativo ATR) |
| :--- | :--- | :--- | :--- |
| **Activo Foco** | `BTC-USD`, `ETH-USD`, `SOL-USD` | `QQQ`, `SPY`, `NVDA`, `AAPL` | `TLT`, `CL=F`, `GC=F`, `BABA`, `GGAL.BA` |
| **Modo Navbar** | `🧠 Inteligente` / `⚡ Autónomo` | `⚡ Autónomo` / `🛡️ Copiloto` | `🧠 Inteligente` |
| **Temporalidad** | `5m` (o `1m`) | `15m` | `15m` o `1h` |
| **Estrategia** | `Manual: TP/SL porcentual` | `Manual: TP/SL porcentual` | `Cuantitativa: Reversión ATR` |
| **TP / SL** | `0.8% / -0.5%` (o `0.5% / -0.3%`) | `1.5% / -1.0%` (o manual 1:2) | Dinámico: $TP=2.5 \times ATR$, $SL=1.5 \times ATR$ |
| **Riesgo** | `25%` a `50%` posición | `25%` posición (1 trade/día) | `0.25%` a `0.50%` pérdida presupuestada |
| **Beneficio Mín.** | `0.15%` | `0.20%` | `0.30%` a `0.50%` |
| **Comisión** | `0.10%` (Cripto Spot) | `0.02%` (ETFs US) | Según activo (`0.02%`, `0.10%`, `0.50%`) |
| **Horario** | `24/7 (Libre)` | `Custom: 10:25 a 12:30 ARG` | `Custom` (Alineado a mercado) |
| **Filtro Técnico** | RSI rebote en soporte 5m | M15 + Quiebre Londres + VWAP | $Z \le -2.0$, sobre $EMA_{200}$, $RVOL \ge 1.0$ |
| **Monitor :8520** | `crypto_and_alternatives` | `macro_and_markets` (Pre-Market) | `commodities_and_energy`, `macro` |
