# Módulo Cuantitativo: Estrategia de Tres Velas, Wyckoff & Bulkowski (Multi-Timeframe)

Esta carpeta contiene la implementación completa, aislada y modular del sistema **"Tres Velas & Multi-Temporalidad"**, diseñada para operar de forma 100% autónoma o integrarse en el ecosistema de `trading_ollama`.

---

## 📁 Estructura del Módulo

```
modulo_tres_velas/
├── index.html                   # Cockpit interactivo con 3 gráficos sincronizados (1D, 1H, 15m/5m)
├── estrategia_tres_velas.py     # Estrategia modular en Python (hereda de EstrategiaBase)
└── GUIA_EXPORTACION_GIT.md      # Instrucciones paso a paso para clonar/exportar a la máquina de Ubuntu
```

---

## ⚡ Componentes Clave

1. **Interfaz Web Cuantitativa (`index.html`):**
   * **3 Gráficos Sincronizados en Tiempo Real (Lightweight Charts):**
     * **Gráfico 1 (Macro - 1D):** Filtro tendencial, VWAP Anclado Mayor y retrocesos de Fibonacci (38.2%, 50%, 61.8%).
     * **Gráfico 2 (Setup - 1H):** Leyes de Wyckoff, volumen relativo (VPA), Esfuerzo vs. Resultado y Ondas de Elliott (1-5, ABC).
     * **Gráfico 3 (Gatillo - 15m / 5m):** Formaciones de velas con cajas de detección, zonas de Stop Loss ($1.5 \times ATR$), Take Profit ($R:R \ge 1:2.0$) y nivel de Peluqueo (TP1 al 50% + Breakeven real).
   * **Selector de 3 Variantes de Velas (Benchmark Thomas Bulkowski):**
     * **Variante A (Complejos - 3+ Velas):** Three White Soldiers (82%), Morning Star (78%), Rising Three Methods (74%), Evening Star (72%).
     * **Variante B (Reversión - 2 Velas):** Bullish & Bearish Engulfing (63%).
     * **Variante C (Rechazo de Mecha - 1 Vela con confirmación):** Martillo (60%), Estrella Fugaz (59%), Doji Libélula / Lápida (51%).
   * **Matriz de Control Cuantitativo (Entry Gate):**
     * Filtro Direccional VWAP diario.
     * Opening Blackout de 15 minutos en Wall Street.
     * Gestión de riesgo determinista ($SL \ge 1.5 \times ATR$, $R:R \ge 1:2.0$).

2. **Estrategia Modular en Python (`estrategia_tres_velas.py`):**
   * Cumple con la interfaz abstracta `EstrategiaBase` del proyecto.
   * Lista para conectarse al `STRATEGY_REGISTRY` en `backend/estrategias/registry.py`.
   * Procesa series OHLCV multitemporales y emite señales con métricas numéricas exactas y sin sesgo de anticipación (*no look-ahead bias*).

---

## 🚀 Cómo exportar o sincronizar hacia la PC con Ubuntu

Consulta el archivo [GUIA_EXPORTACION_GIT.md](file:///c:/Users/raulc/Desktop/proyectos/trading_ollama/modulo_tres_velas/GUIA_EXPORTACION_GIT.md) para ver los comandos Git listos para copiar y pegar desde tu terminal.
