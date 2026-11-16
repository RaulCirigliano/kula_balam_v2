# 🧪 Caja de Buenas Ideas & Laboratorio Cuantitativo (Kula Balam)

Este repositorio contiene las fórmulas tácticas, módulos y algoritmos experimentales archivados. Su función es preservar los aciertos matemáticos y hallazgos tácticos de cada desarrollo para consulta del Cerebro de Inteligencia Artificial (Antigravity Operador / Qwen / Gemini) y pruebas en el entorno de simulación, **sin sobrecargar el selector de estrategias activas en la interfaz operativa**.

---

## 🧭 Mapa de Ideas Archivadas y sus Aciertos Técnicos

### 1. `trailing_trend_runner` (Fórmula de Doble Escalón - Idea Raúl)
* **Archivo:** [`backend/estrategias/trailing_trend_runner.py`](../trailing_trend_runner.py)
* **Acierto Matemático Principal:** 
  * **Escalón 1:** Paso inmediato a riesgo cero (`be_armed`) al alcanzar `+0.40%` bruto (`+0.15%` neto garantizado).
  * **Escalón 2:** Cerrojo de Scalping: al tocar `+1.00%` bruto, el Stop Loss se ancla de forma innegociable en un piso mínimo de `+0.80%` bruto (`+0.50%` neto en mano).
  * **Escalón 3:** Trailing Stop Adaptativo ("Llave IA"): alterna entre modo *Holgado* (1.2%-1.5%) y modo *Comprimido* (0.8%-1.0% si RSI > 70) persiguiendo el precio máximo (`peak_price`).
* **Estado en Kula Balam:** Sus 3 escalones de gestión dinámica fueron **absorbidos íntegramente** dentro de [`backend/daemon.py`](../../daemon.py) para gobernar el 50% remanente de Kula Balam tras el Peluqueo de TP1.

---

### 2. `trailing_short_runner` (Caída sin Suelo - Shorting Simétrico)
* **Archivo:** [`backend/estrategias/trailing_short_runner.py`](../trailing_short_runner.py)
* **Acierto Matemático Principal:**
  * Simetría cuantitativa para mercados bajistas en futuros/margen: cálculo de PnL invertido `(entry - current) / entry`, pre-breakeven al caer 0.30% y compresión del stop persiguiendo valles decrecientes.
* **Estado en Kula Balam:** Integrado en la arquitectura bidireccional de Kula Balam (soporte nativo de posiciones `LONG` y `SHORT`).

---

### 3. `mean_reversion_atr` (Reversión Estadística & Capitulación Z-Score)
* **Archivo:** [`backend/estrategias/mean_reversion_atr.py`](../mean_reversion_atr.py)
* **Acierto Matemático Principal:**
  * Doble camino estadístico:
    * **Camino 1 (Pullback en Tendencia):** Precio sobre EMA 200 con retroceso técnico ($Z\text{-Score} \in [-1.2, -0.4]$).
    * **Camino 2 (Capitulación Extrema):** Pánico vendedor institucional ($Z\text{-Score} \le -2.0$) con mecha de absorción inferior ($\ge 25\%$).
* **Uso Recomendado:** Módulo especialista para activación ante noticias de alto impacto (crashes, pánico geopolítico o liquidaciones en cascada).

---

### 4. `nasdaq_araujo_vwap` (Francotirador de Apertura Wall Street)
* **Archivo:** [`backend/estrategias/nasdaq_araujo_vwap.py`](../nasdaq_araujo_vwap.py)
* **Acierto Matemático Principal:**
  * Delimitación del rango de la sesión europea (Londres) entre las 04:00 y 09:00 NY como zonas de soporte/resistencia institucionales.
  * Gatillo en la campana de Wall Street (09:30 NY / 10:30 ARG) por quiebre de la primera vela M15 en confluencia con el VWAP diario.
* **Uso Recomendado:** Módulo especialista para índices bursátiles (QQQ, SPY, DIA) exclusivamente de 10:30 a 12:30 ARG.

---

### 5. `hyenuk_chu_multibagger` (Swing Trading Tendencial en Acciones)
* **Archivo:** [`backend/estrategias/hyenuk_chu_multibagger.py`](../hyenuk_chu_multibagger.py)
* **Acierto Matemático Principal:**
  * Seguimiento de tendencia multisesión (2 a 10 días) en temporalidad 1H, con toma de beneficios en TP1 (+3.5%) y trailing de amplitud controlada para acciones de alta beta (NVDA, TSLA, AAPL).

---

### 6. `alex_ruiz_triada_3velas` (La Tríada de las 3 Velas con Shorts Blindados)
* **Archivo:** [`backend/estrategias/alex_ruiz_triada_3velas.py`](../alex_ruiz_triada_3velas.py)
* **Acierto Matemático Principal:**
  * Metodología multitemporal de Alex Ruiz (1D Contexto EMA 50 -> 1H Zona Dorada Fibo 0.50-0.75 -> 5M Gatillo 3 Velas).
  * **Shorts de Seguridad Reforzados:** Veto Bear Trap (mecha inferior >= 40%), Veto de Sobreventa (RSI <= 30 no vender), Veto Cohete sin rechazo, Stop a Misa con holgura adaptativa de 2 ticks y Peluqueo TP1 con R:R >= 1:2.0 neto tras comisiones y spread.
* **Estado en Kula Balam:** Disponible en el catálogo para ser testeada o activada por el operador cuando lo requiera.

---

### 7. `tendencia_institucional_01` & `cazador_rebotes_02` (Prototipos Históricos Archivados)
* **Archivos:** [`backend/estrategias/tendencia_institucional_01.py`](../tendencia_institucional_01.py) y [`backend/estrategias/cazador_rebotes_02.py`](../cazador_rebotes_02.py)
* **Diagnóstico:** Prototipos preliminares con cruces simples de medias y rebotes en 15m. Sus conceptos fueron refinados y superados por la Tríada Fractal de Kula Balam.

---

## 🎯 Estrategias Titulares Oficiales Activas

En la interfaz operativa y en el motor del daemon quedan activas únicamente las **4 fórmulas sólidas**:
1. 🐅 **`kula_balam_cava_ruiz`**: Estrategia Maestra Oficial 24/7 (Alex Ruiz + José Luis Cava).
2. 🕯️ **`tres_velas_wyckoff_bulkowski`**: Acción del precio, patrones de 3 velas de Bulkowski y volumen Wyckoff VPA.
3. 🤖 **`auto`**: Orquestador autónomo por horario mundial y régimen macro.
4. 🛠️ **`manual`**: Operativa discrecional con niveles propios del operador.
