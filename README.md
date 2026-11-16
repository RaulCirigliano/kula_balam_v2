# 🐅 KULA · BALAM

### Ecosistema Integral de Inteligencia de Mercado, Análisis Cuantitativo y Arbitraje Institucional

```
                 K U L A   ·   B A L A M                  
      La Tríada de los Tres Tiempos & El Jaguar Agazapado          
   [Módulo Kula: Riesgo y Asimetría] ── [Motor Balam: Músculo Matemático]
                 │                           │
                 └─────────► [CIO: Árbitro IA] ◄────────┘
```

---

## 1. La Jerarquía de Roles (Arquitectura Canónica)

El sistema opera bajo una separación estricta de responsabilidades para erradicar el sesgo emocional, el sobreajuste y el gasto innecesario de tokens:

1. **BALAM (Músculo Matemático Puro):**  
   * Motor determinista en Python.
   * Procesa series temporales OHLCV (`data/datos_historicos/`) sin sesgo de futuro (*no lookahead bias*).
   * Calcula indicadores matriciales en NumPy/Pandas: ATR, medias móviles, canales Donchian, retrocesos Fibonacci y volumen relativo ($RVOL$).
   * Si la matemática no genera una señal objetiva, el ciclo termina sin consultar a la IA.

2. **KULA (Gestor de Capital y Asimetría):**  
   * Custodio numérico de la tesorería y el riesgo.
   * Modula el tamaño de posición (*sizing*) y exige una asimetría mínima estricta de **$R:R \ge 1:2.0$** (óptimo $1:3.0$).
   * Aplica la deducción obligatoria de fricción institucional real (comisiones + slippage) antes de validar cualquier viabilidad.

3. **ANTIGRAVITY CIO (Árbitro Heurístico de Veto):**  
   * Comité de control de calidad institucional.
   * Opera bajo el **Principio de Veto Negativo**: no genera señales de compra o venta, únicamente rechaza operaciones de baja calidad o trampas de mercado.
   * Filtra absorción de mechas Wyckoff ($> 35\%$), sobreextensión de la media ($> 3.0$ ATRs) y secado de liquidez institucional ($RVOL < 1.15$).

---

## 2. Estructura del Repositorio

```text
kula_balam/
├── AGENTS.md                 # Directrices canónicas e inviolables para cualquier IA
├── README.md                 # Documentación ejecutiva del ecosistema
├── trading_ledger.sqlite3    # Bóveda transaccional contable de doble partida (SQLite)
├── historial_trades.csv      # Registro plano sincronizado de operaciones
├── backend/                  # Servidor FastAPI, daemon autónomo y gestión de órdenes
│   ├── main.py               # API REST principal (puerto 18087)
│   ├── entry_gate.py         # Filtro de entrada y compuerta de validación
│   ├── quant_risk.py         # Algoritmos cuantitativos de riesgo
│   └── db/ledger.py          # Conector a la bóveda SQLite
├── frontend/                 # Cockpit visual de trading y terminales HTML
│   ├── index.html            # Cockpit principal
│   └── terminal_tres_velas.html
├── backtest_lab/             # Laboratorio Cuantitativo Modular (Arquitectura Dual)
│   ├── server.py             # Servidor sandbox local (puerto 8000)
│   ├── core/metrics.py       # Auditor estricto de fricción, Drawdown y asimetría
│   ├── web/index.html        # UI dual (Ventana 1: Árbitro IA / Ventana 2: Matemática)
│   ├── estrategias_ia/       # Biblioteca de filtros institucionales de IA
│   ├── estrategias_math/     # Biblioteca de fórmulas matemáticas puras
│   └── data/datos_historicos/# Series temporales consolidadas en formato Parquet
└── tests/                    # Suite completa de tests unitarios y de integración
```

---

## 3. Puesta en Marcha

### A. Laboratorio Cuantitativo (`backtest_lab`)
Diseñado para auditar estrategias y contrastar la fórmula pura frente al filtro de IA a **coste cero de tokens**:

```bash
cd backtest_lab
./lanzar_lab.sh
# O manualmente:
python server.py
```
Acceder en el navegador a: `http://127.0.0.1:8000`

### B. Sistema Completo / Bot en Vivo (Paper Trading)
```bash
./lanzar_todo.sh
```
Inicia el backend FastAPI en el puerto `18087` y abre el Cockpit de Trading en el navegador.

---

## 4. Reglas Inviolables para Agentes de IA

Todas las directrices operativas, límites de riesgo y protocolos de transparencia epistémica están centralizados en [AGENTS.md](AGENTS.md):
1. **La IA nunca calcula indicadores:** La IA solo recibe la fila puntual precalculada por Balam.
2. **Veto Negativo:** La IA no busca operaciones; únicamente veta las trampas del mercado.
3. **Persistencia Acumulativa:** Toda descarga de datos enriquece el histórico sin borrar registros previos.
4. **Sobriedad Técnica:** Prohibición absoluta de halagos o sesgos de validación artificial; evaluación objetiva de asimetría $R:R$.
