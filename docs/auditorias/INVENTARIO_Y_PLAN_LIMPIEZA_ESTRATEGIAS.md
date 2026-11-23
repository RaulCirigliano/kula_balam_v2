# Inventario Completo, Auditoría Técnica y Plan de Limpieza de `backend/estrategias/`

- **Fecha de corte:** 2026-11-23
- **Directorio auditado (recursivo):** `/home/raul/Escritorio/proyectos/kula_balam/backend/estrategias/`
- **Alcance y restricción:** Auditoría **100% solo lectura** sobre el código fuente, fórmulas, catálogos y `daemon_state.json`. No se borró, movió ni modificó ningún archivo de estrategia ni parámetro de la campaña de prueba vigente.
- **Estado de sintaxis:** 45/45 archivos `.py` compilan sin `SyntaxError` (`ast.parse` OK); 4/4 archivos `.json` son JSON válidos.
- **Dependencia externa aislada:** `scalping_cuantitativo_5m.py:21` es el único archivo del árbol que importa la librería externa `ta` (`ModuleNotFoundError` fuera del entorno virtual `venv/bin/python`).

---

## 1. Barrido Real de Disco y Mapa de Carga del Sistema

### 1.1 Resumen Cuantitativo del Árbol (excluyendo `__pycache__`)

| Carpeta | `.py` | `.json` | `.md` | Total | Estado de carga en vivo |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `backend/estrategias/` (raíz) | 20 | 0 | 0 | 20 | 6 módulos infra + 14 estrategias (4 `OFFICIAL`, 10 `LABORATORY`, 5 clases en 1 archivo `SCALPING`) |
| `backend/estrategias/laboratorio/` | 1 | 0 | 1 | 2 | Solo paquete marcador `__init__.py` y `README.md` informativo |
| `backend/estrategias/catalogo/principal/` | 18 | 1 | 0 | 19 | 16 cargadas por `catalog_adapter.py` + **2 sombreadas/ignoradas** (`donchian_breakout_1h.py`, `squeeze_dual_eth_4h.py`) |
| `backend/estrategias/catalogo/operador_presente/` | 6 | 1 | 0 | 7 | 3 cargadas por `catalog_adapter.py` + **3 sombreadas en `STRATEGY_REGISTRY`** por copias idénticas en `principal/` (aunque visibles en UI vía `catalogo_manager.py`) |
| `backend/estrategias/catalogo/para_testear/ganadoras/` | 0 | 1 | 0 | 1 | Vacía (`metadata.json = {}`); usada como destino temporal por `test_lab_catalogo_dinamico.py` |
| `backend/estrategias/catalogo/para_testear/heredadas/` | 0 | 1 | 0 | 1 | Vacía (`metadata.json = {}`) |
| **Total real en disco** | **45** | **4** | **1** | **50** | **37 IDs en `STRATEGY_REGISTRY`** (18 estáticos + 19 dinámicos); **9 activos en `daemon_state.json`** |

### 1.2 Cómo Carga Realmente el Sistema (`registry.py`, `catalog_adapter.py`, `catalogo_manager.py`, `daemon_state.json`)

1. **Capa estática (`backend/estrategias/registry.py:29-65`):**
   - `OFFICIAL_STRATEGIES` (4): `donchian_breakout_1h`, `squeeze_dual_eth_4h`, `kula_balam_cava_ruiz`, `tres_velas_wyckoff_bulkowski`.
   - `LABORATORY_STRATEGIES` (10, con `donchian_breakout_1h` repetido): `triple_confluencia_4h`, `alex_ruiz_triada_3velas`, `nasdaq_araujo_vwap`, `hyenuk_chu_multibagger`, `trailing_trend_runner`, `trailing_short_runner`, `mean_reversion_atr`, `01_tendencia_institucional_15m`, `02_cazador_rebotes_atr_15m`.
   - `SCALPING_STRATEGIES` (5 clases dentro de `scalping_cuantitativo_5m.py`): `scalping_vwap_2sigma_5m`, `scalping_m5_rsi3_adx5_ema50`, `smc_liquidity_scalper_m5`, `triada_fractal_fibo_ema50_5m`, `donchian_15m_atr_runner`.
2. **Capa dinámica (`backend/estrategias/catalog_adapter.py:564-588`):**
   - Recorre primero `catalogo/principal/*.py` y luego `catalogo/operador_presente/*.py`.
   - **Regla de sombreado (`catalog_adapter.py:579`):** si `strat_id` ya existe en `existing_ids` (capa estática) o en `discovered` (carpeta `principal/`), el archivo posterior es **ignorado silenciosamente** para ejecución en `STRATEGY_REGISTRY`.
   - Esto produce **5 archivos `.py` sombreados en disco** (nunca se ejecutan en `STRATEGY_REGISTRY`):
     1. `catalogo/principal/donchian_breakout_1h.py` (sombreado por `backend/estrategias/donchian_breakout_1h.py`)
     2. `catalogo/principal/squeeze_dual_eth_4h.py` (sombreado por `backend/estrategias/squeeze_dual_eth_4h.py`)
     3. `catalogo/operador_presente/cava_fallo_macd_eurusd_1h.py` (sombreado por `catalogo/principal/cava_fallo_macd_eurusd_1h.py`)
     4. `catalogo/operador_presente/kula_cava_eth_1h.py` (sombreado por `catalogo/principal/kula_cava_eth_1h.py`)
     5. `catalogo/operador_presente/kula_cava_sol_1h.py` (sombreado por `catalogo/principal/kula_cava_sol_1h.py`)
   - *Matiz importante:* `catalogo_manager.py:52-138` sí lee las 3 copias de `operador_presente/` para listarlas en la pestaña UI/API `/api/catalogo_formulas` y en `GET /api/catalogo_formulas/operador_presente/{archivo}`.
3. **Campaña activa (`backend/config/daemon_state.json:5-15`):**
   - `strategy: "auto"`, con `allowed_strategies` = 9 IDs: `kula_balam_cava_ruiz`, `1_donchian_breakout_sol_4h`, `2_squeeze_dual_eth_4h`, `donchian_breakout_1h`, `cava_fallo_macd_eurusd_1h_slot1`, `kula_cava_eth_1h`, `ttm_squeeze_eth_1h`, `ttm_squeeze_sol_4h`, `kula_cava_sol_1h`.
   - Presencial (`backend/config/campaign_config.json` y `catalogo/operador_presente/`): `mtf_presencial_15m`, `mtf_presencial_5m`, `fractal_squeeze_15m` (+ las 3 compartidas de 1H).

### 1.3 Inventario Completo de los 50 Archivos en Disco

| # | Ruta relativa en `backend/estrategias/` | Bytes | Líneas | SHA256 (12) | ID / Clases | Carga efectiva en sistema |
| :-: | :--- | --: | --: | :--- | :--- | :--- |
| 1 | `__init__.py` | 2,671 | 98 | `0bdaf6d6303e` | Infra | Importado como paquete raíz |
| 2 | `base.py` | 1,746 | 52 | `a13c3cb6366e` | `EstrategiaBase` | Clase base de todas las estrategias |
| 3 | `registry.py` | 29,755 | 636 | `125fc70a3617` | Infra | Registro maestro y router `auto` |
| 4 | `catalog_adapter.py` | 26,848 | 588 | `7e4270e5dfc9` | `CatalogFormulaStrategy` | Adaptador dinámico de catálogo |
| 5 | `catalogo_manager.py` | 9,906 | 242 | `45908172039b` | Infra | API CRUD catálogo y `metadata.json` |
| 6 | `config_manager.py` | 30,452 | 689 | `20101e6194d2` | `StrategyConfigManager` | Persistencia `data/strategies_config.json` |
| 7 | `laboratorio/__init__.py` | 146 | 4 | `867cf100868e` | Infra | Paquete vacío |
| 8 | `laboratorio/README.md` | 5,375 | 74 | `53df266c0f51` | Doc | Documentación histórica (desactualizada) |
| 9 | `kula_balam_cava_ruiz.py` | 33,398 | 608 | `b170f3d27e49` | `kula_balam_cava_ruiz` | **ACTIVA en `daemon_state.json`** (`OFFICIAL`) |
| 10 | `donchian_breakout_1h.py` | 29,078 | 561 | `51e8d8136e4c` | `donchian_breakout_1h` | **ACTIVA en `daemon_state.json`** (`OFFICIAL`, sombrea catálogo) |
| 11 | `squeeze_dual_eth_4h.py` | 14,301 | 318 | `21c950ca8d7c` | `squeeze_dual_eth_4h` | Cargada (`OFFICIAL`), NO en `daemon_state.json`; sombrea catálogo |
| 12 | `tres_velas_wyckoff_bulkowski.py` | 22,497 | 441 | `725ca634a169` | `tres_velas_wyckoff_bulkowski` | Cargada (`OFFICIAL`), NO en `daemon_state.json` |
| 13 | `alex_ruiz_triada_3velas.py` | 29,714 | 588 | `bcb91ef4a560` | `alex_ruiz_triada_3velas` | Cargada (`LABORATORY`), inactiva en campaña |
| 14 | `triple_confluencia_4h.py` | 12,230 | 258 | `3ec753cf4ac8` | `triple_confluencia_4h` | Cargada (`LABORATORY`), inactiva en campaña |
| 15 | `nasdaq_araujo_vwap.py` | 23,851 | 445 | `b49d370ffd7b` | `nasdaq_araujo_vwap` | Cargada (`LABORATORY` + `resolve_auto_strategy` TradFi) |
| 16 | `hyenuk_chu_multibagger.py` | 16,181 | 299 | `1c3ff84d1cc9` | `hyenuk_chu_multibagger` | Cargada (`LABORATORY` + `resolve_auto_strategy` TradFi/BYMA) |
| 17 | `trailing_trend_runner.py` | 13,358 | 251 | `a1a54ecab903` | `trailing_trend_runner` | Cargada (`LABORATORY` + fallback `resolve_auto_strategy`) |
| 18 | `trailing_short_runner.py` | 13,281 | 240 | `ad24960b08c3` | `trailing_short_runner` | Cargada (`LABORATORY` + fallback `resolve_auto_strategy`) |
| 19 | `mean_reversion_atr.py` | 10,227 | 197 | `c35fa3044299` | `mean_reversion_atr` | Cargada (`LABORATORY`), **bloqueada** (`long_entries_suspended=True`) |
| 20 | `cazador_rebotes_02.py` | 7,636 | 187 | `d0f328d8cfff` | `02_cazador_rebotes_atr_15m` | Cargada (`LABORATORY`), **bloqueada** (`long_entries_suspended=True`) |
| 21 | `tendencia_institucional_01.py` | 6,113 | 149 | `2b10e9e40eb7` | `01_tendencia_institucional_15m` | Cargada (`LABORATORY`), **R:R roto** (`1.5x < MIN_NET_RR 2.0`) |
| 22 | `scalping_cuantitativo_5m.py` | 27,537 | 602 | `b931f757d3ef` | 5 clases `SCALPING` | Cargada (`SCALPING`), **en cuarentena** (`active=False`, requiere `ta`) |
| 23 | `catalogo/principal/1_donchian_breakout_sol_4h.py` | 6,113 | 136 | `7e2590cb057f` | `1_donchian_breakout_sol_4h` | **ACTIVA en `daemon_state.json`** |
| 24 | `catalogo/principal/2_squeeze_dual_eth_4h.py` | 6,217 | 134 | `98f48c3d3094` | `2_squeeze_dual_eth_4h` | **ACTIVA en `daemon_state.json`** |
| 25 | `catalogo/principal/cava_fallo_macd_eurusd_1h_slot1.py` | 5,388 | 128 | `41b1ebbfbe24` | `cava_fallo_macd_eurusd_1h_slot1` | **ACTIVA en `daemon_state.json`** (SHA256 = #31 y #41) |
| 26 | `catalogo/principal/kula_cava_eth_1h.py` | 6,332 | 174 | `f79eea71bf7c` | `kula_cava_eth_1h` | **ACTIVA en `daemon_state.json`** (SHA256 = #43) |
| 27 | `catalogo/principal/kula_cava_sol_1h.py` | 6,619 | 180 | `70329032223d` | `kula_cava_sol_1h` | **ACTIVA en `daemon_state.json`** (SHA256 = #44) |
| 28 | `catalogo/principal/ttm_squeeze_eth_1h.py` | 5,868 | 155 | `18ca59563f78` | `ttm_squeeze_eth_1h` | **ACTIVA en `daemon_state.json`** |
| 29 | `catalogo/principal/ttm_squeeze_sol_4h.py` | 6,040 | 158 | `a0492c3a2614` | `ttm_squeeze_sol_4h` | **ACTIVA en `daemon_state.json`** |
| 30 | `catalogo/principal/1_donchian_breakout_sol_4h_slot1.py` | 6,902 | 153 | `2222b0eceb09` | `1_donchian_breakout_sol_4h_slot1` | Cargada en `STRATEGY_REGISTRY`, NO usada (clon de #23) |
| 31 | `catalogo/principal/cava_fallo_macd_eurusd_1h.py` | 5,388 | 128 | `41b1ebbfbe24` | `cava_fallo_macd_eurusd_1h` | Cargada en `STRATEGY_REGISTRY`, NO en campaña (**exacto** a #25) |
| 32 | `catalogo/principal/21_donchian_breakout_sol_4h.py` | 6,902 | 153 | `0ca24d0c13a0` | `21_donchian_breakout_sol_4h` | Cargada en `STRATEGY_REGISTRY`, NO usada (**AST idéntico** a #30/#33) |
| 33 | `catalogo/principal/31_donchian_breakout_sol_4h.py` | 6,902 | 153 | `86d4ab2aa148` | `31_donchian_breakout_sol_4h` | Cargada en `STRATEGY_REGISTRY`, NO usada (**AST idéntico** a #30/#32) |
| 34 | `catalogo/principal/donchian_breakout_1h.py` | 7,029 | 174 | `b28030966d79` | `donchian_breakout_1h` | **SOMBREADA / IGNORADA** por #10 en `STRATEGY_REGISTRY` |
| 35 | `catalogo/principal/ensamble_campeon_binance_ETH_USDT_4h.py` | 14,093 | 341 | `013865b4bc0c` | `ensamble_campeon_binance_ETH_USDT_4h` | Cargada en `STRATEGY_REGISTRY`, NO usada (PF 1.29 reprobada) |
| 36 | `catalogo/principal/ensamble_campeon_binance_ETH_USDT_4h_slot1.py` | 9,588 | 220 | `b93f353d3103` | `ensamble_campeon_binance_ETH_USDT_4h_slot1` | Cargada en `STRATEGY_REGISTRY`, NO usada (ensamble 1-sensor de #24) |
| 37 | `catalogo/principal/mejorada_cava_fallo_macd_eurusd_1h.py` | 6,083 | 146 | `2f6e10075099` | `mejorada_cava_fallo_macd_eurusd_1h` | Cargada en `STRATEGY_REGISTRY`, NO usada (lógica idéntica a #25) |
| 38 | `catalogo/principal/squeeze_dual_eth_4h.py` | 7,007 | 171 | `bff2284d865a` | `squeeze_dual_eth_4h` | **SOMBREADA / IGNORADA** por #11 en `STRATEGY_REGISTRY` |
| 39 | `catalogo/principal/squeeze_dual_eth_4h_slot1.py` | 7,431 | 187 | `8fd2259d677a` | `squeeze_dual_eth_4h_slot1` | Cargada en `STRATEGY_REGISTRY`, NO en campaña (clon de #38) |
| 40 | `catalogo/principal/squeeze_dual_eth_fondeo_strict_4h.py` | 6,478 | 166 | `f49c24efcfde` | `squeeze_dual_eth_fondeo_strict_4h` | Cargada en `STRATEGY_REGISTRY`, NO en campaña (variante Fondeo) |
| 41 | `catalogo/operador_presente/cava_fallo_macd_eurusd_1h.py` | 5,388 | 128 | `41b1ebbfbe24` | `cava_fallo_macd_eurusd_1h` | **SOMBREADA** en `REGISTRY` por #31; listada en UI presencial |
| 42 | `catalogo/operador_presente/fractal_squeeze_15m.py` | 6,589 | 161 | `b20942b8401a` | `fractal_squeeze_15m` | **ACTIVA Presencial** (única copia) |
| 43 | `catalogo/operador_presente/kula_cava_eth_1h.py` | 6,332 | 174 | `f79eea71bf7c` | `kula_cava_eth_1h` | **SOMBREADA** en `REGISTRY` por #26; listada en UI presencial |
| 44 | `catalogo/operador_presente/kula_cava_sol_1h.py` | 6,619 | 180 | `70329032223d` | `kula_cava_sol_1h` | **SOMBREADA** en `REGISTRY` por #27; listada en UI presencial |
| 45 | `catalogo/operador_presente/mtf_presencial_15m.py` | 12,950 | 293 | `e545891dac33` | `mtf_presencial_15m` | **ACTIVA Presencial** (única copia) |
| 46 | `catalogo/operador_presente/mtf_presencial_5m.py` | 13,204 | 295 | `89de2c96f373` | `mtf_presencial_5m` | **ACTIVA Presencial** (única copia) |
| 47 | `catalogo/principal/metadata.json` | 9,570 | 200 | `29862ca2825c` | JSON (18 entradas) | Activo (`catalogo_manager.py` y `catalog_adapter.py`) |
| 48 | `catalogo/operador_presente/metadata.json` | 3,806 | 68 | `1701597e40e5` | JSON (6 entradas) | Activo (`catalogo_manager.py` y `catalog_adapter.py`) |
| 49 | `catalogo/para_testear/ganadoras/metadata.json` | 2 | 1 | `44136fa355b3` | JSON (`{}`) | Vacío; requerido por `catalogo_manager.py` y pytest |
| 50 | `catalogo/para_testear/heredadas/metadata.json` | 2 | 1 | `44136fa355b3` | JSON (`{}`) | Vacío; requerido por `catalogo_manager.py` |

---

## 2. Clasificación Técnica de Cada Estrategia

### 2.1 Activas en Campaña (`auto` u `operador_presente`) — 12 estrategias únicas (3 duplicadas en carpeta)

Ya auditadas parámetro por parámetro frente a `trading_guia_maestra` en el informe previo. Resumen de duplicación en disco:

- **Sin duplicado (6):**
  - `kula_balam_cava_ruiz.py` (`auto`)
  - `ttm_squeeze_eth_1h.py` (`auto`)
  - `ttm_squeeze_sol_4h.py` (`auto`)
  - `mtf_presencial_15m.py` (`operador_presente`)
  - `mtf_presencial_5m.py` (`operador_presente`)
  - `fractal_squeeze_15m.py` (`operador_presente`)
- **Con duplicados/clones en disco (6):**
  - `donchian_breakout_1h.py` (`auto`) → tiene copia sombreada divergente en `catalogo/principal/donchian_breakout_1h.py` (`SL 1.40x/TP 3.36x` activa vs `1.60x/4.16x` sombreada).
  - `1_donchian_breakout_sol_4h.py` (`auto`) → tiene **3 clones lógicos** en `principal/`: `1_donchian_breakout_sol_4h_slot1.py`, `21_donchian_breakout_sol_4h.py`, `31_donchian_breakout_sol_4h.py`.
  - `2_squeeze_dual_eth_4h.py` (`auto`) → tiene **4 clones/variantes** en raíz y `principal/`: `squeeze_dual_eth_4h.py` (raíz), `catalogo/principal/squeeze_dual_eth_4h.py`, `squeeze_dual_eth_4h_slot1.py`, `ensamble_campeon_binance_ETH_USDT_4h_slot1.py` (+ 1 variante Fondeo distinta: `squeeze_dual_eth_fondeo_strict_4h.py`).
  - `cava_fallo_macd_eurusd_1h_slot1.py` (`auto`) → tiene **2 copias exactas byte a byte** (`SHA256 41b1ebbfbe24`: `principal/cava_fallo_macd_eurusd_1h.py` y `operador_presente/cava_fallo_macd_eurusd_1h.py`) + **1 clon con lógica idéntica** (`mejorada_cava_fallo_macd_eurusd_1h.py`).
  - `kula_cava_eth_1h.py` (`auto`) → tiene **1 copia exacta byte a byte** (`SHA256 f79eea71bf7c`) en `operador_presente/kula_cava_eth_1h.py`.
  - `kula_cava_sol_1h.py` (`auto`) → tiene **1 copia exacta byte a byte** (`SHA256 70329032223d`) en `operador_presente/kula_cava_sol_1h.py`.

---

### 2.2 Repetidas / Duplicadas — 14 archivos sobrantes detectados por `SHA256` y `AST/diff`

#### A. Idénticas byte a byte (`SHA256` exacto)

| Grupo | Archivo que ejecuta el sistema | Duplicado(s) idéntico(s) en disco | SHA256 | Observación crítica |
| :--- | :--- | :--- | :--- | :--- |
| Cava EURUSD 1H | `catalogo/principal/cava_fallo_macd_eurusd_1h_slot1.py` (`daemon_state.json`) | 1. `catalogo/principal/cava_fallo_macd_eurusd_1h.py`<br>2. `catalogo/operador_presente/cava_fallo_macd_eurusd_1h.py` | `41b1ebbfbe24` | 3 archivos idénticos. El #1 está referenciado por 3 tests (`test_estrategias.py:1955`). El #2 está sombreado en `REGISTRY`. |
| Kula Cava ETH 1H | `catalogo/principal/kula_cava_eth_1h.py` | `catalogo/operador_presente/kula_cava_eth_1h.py` | `f79eea71bf7c` | Sombreado en `REGISTRY`, pero **exigido por `tests/test_lab_catalogo_dinamico.py:49`**. |
| Kula Cava SOL 1H | `catalogo/principal/kula_cava_sol_1h.py` | `catalogo/operador_presente/kula_cava_sol_1h.py` | `70329032223d` | Sombreado en `REGISTRY`; solo sirve para listar en UI `operador_presente`. |

#### B. Clones con AST lógico 100% idéntico (solo difieren fecha/docstrings) o funcionalmente equivalentes

| Familia | Archivo canónico usado en campaña | Clon(es) sobrante(s) | Diferencia real en código |
| :--- | :--- | :--- | :--- |
| Donchian SOL 4H | `catalogo/principal/1_donchian_breakout_sol_4h.py` | 1. `catalogo/principal/1_donchian_breakout_sol_4h_slot1.py`<br>2. `catalogo/principal/21_donchian_breakout_sol_4h.py`<br>3. `catalogo/principal/31_donchian_breakout_sol_4h.py` | Los 3 clones tienen **AST 100% idéntico entre sí** (solo cambia la fecha de promoción del 15-nov-2026) y lógica idéntica a `1_donchian_breakout_sol_4h.py` (solo añaden docstring largo al árbitro). **0 tests dependen de ellos.** |
| Cava EURUSD 1H | `catalogo/principal/cava_fallo_macd_eurusd_1h_slot1.py` | `catalogo/principal/mejorada_cava_fallo_macd_eurusd_1h.py` | `formula_matematica`, `CONFIG_IA`, `arbitro_ia` y `custom_brain_filter` son **100% idénticos**; únicamente cambia el encabezado de métricas y comentarios. **0 tests dependen de ella.** |
| Donchian Estructural | `backend/estrategias/donchian_breakout_1h.py` | `catalogo/principal/donchian_breakout_1h.py` | **Sombreada e ignorada** por `registry.py`. Además tiene desvío `SL 1.60x / TP 4.16x` vs `1.40x / 3.36x` en la clase activa. |
| Squeeze Dual ETH 4H | `catalogo/principal/2_squeeze_dual_eth_4h.py` | 1. `backend/estrategias/squeeze_dual_eth_4h.py`<br>2. `catalogo/principal/squeeze_dual_eth_4h.py`<br>3. `catalogo/principal/squeeze_dual_eth_4h_slot1.py`<br>4. `catalogo/principal/ensamble_campeon_binance_ETH_USDT_4h_slot1.py` | Misma fórmula BB(20,2) + Donchian(20) / Bear BOS(8) + EMA200/EMA50 (`SL 1.4x`, `TP 2.6x`). `#1` es wrapper `EstrategiaBase` (`squeeze_mult 1.25`); `#2` está **sombreada** por `#1`; `#3` es copia de `#2` con claves extra no usadas en `CONFIG_IA` (**pero referenciada por 4 tests y fallback de `daemon.py`/`main.py`**); `#4` es un "ensamble" degenerado con **1 solo sensor** (copia pegada de `2_squeeze_dual_eth_4h` con `RVOL >= 1.15`). |

---

### 2.3 Para Chequear (Aplicar o Descartar Post-Campaña) — 8 estrategias

| Archivo | ID | Fidelidad a `trading_guia_maestra` | Desvíos / Parámetros sin usar / Estado en Lab |
| :--- | :--- | :--- | :--- |
| `catalogo/principal/squeeze_dual_eth_fondeo_strict_4h.py` | `squeeze_dual_eth_fondeo_strict_4h` | Arquitectura de Lab (no literal en guía); respeta `R:R >= 2.0`, `RVOL >= 1.15`, techo `Max DD <= 8%` y `Daily DD <= 4.5%` | **Candidata seria para Fondeo:** añade tope duro `SL <= 2.90%` spot + `RVOL >= 1.15` (reporta PF 2.53, OOS PF 1.80, Max DD 6.50%, Daily DD 2.99%, N=31). Evaluar si reemplaza a `2_squeeze_dual_eth_4h` (MC DD 6.91%) tras la campaña. |
| `triple_confluencia_4h.py` | `triple_confluencia_4h` | **Alta fidelidad** a la estrategia IA ETH 4H de `Guía ia trading notebooklm.txt:79-106`: `EMA 21 / EMA 89`, `ATR(14) > SMA20(ATR)`, `SL 1.5x ATR`, `TP 3.0x ATR` | **Desvíos:** la guía exige `55 <= RSI(14) <= 75`, el código usa `RSI >= 50` sin techo anti-euforia (`línea 187`); `ema_fast_period` y `ema_slow_period` en `parametros_por_defecto` (`líneas 73-74`) están hardcodeados a `21`/`89` en líneas `122-123` sin leerse de `params`; `require_peluqueo` (`línea 103`) se lee pero no altera el retorno. Nunca certificada Walk-Forward en Lab. |
| `tres_velas_wyckoff_bulkowski.py` | `tres_velas_wyckoff_bulkowski` | **Fiel** al benchmark Bulkowski + Wyckoff VPA + VWAP (`01_analisis_tecnico.md` y `04_estrategias_trading.md`): Three White Soldiers, Morning/Evening Star, Engulfing VPA, Hammer, Shooting Star, `SL 1.5x ATR`, `R:R >= 2.0` | **Desvíos:** `min_rvol_threshold = 1.3` vs `RVOL > 1.8` en guía; sin validación Walk-Forward 3Y en Lab; actualmente en `OFFICIAL_STRATEGIES` y usada internamente por `trailing_trend_runner.py:189`. |
| `alex_ruiz_triada_3velas.py` | `alex_ruiz_triada_3velas` | **Alta fidelidad** a Alex Ruiz (`1D -> 1H -> 5M`, `EMA 50`, Fibo `0.50–0.75`, gatillo 3 velas, Shorts blindados `RSI <= 30`, Bear Trap `40%`, Stop -2 ticks, `R:R >= 2.0`) | **Solapamiento:** compite directamente con `kula_balam_cava_ruiz.py` (sin Fallo de MACD ni Clúster Cava). `_calcular_atr` (`línea 94`) declara "Welles Wilder" en docstring pero implementa SMA simple (`rolling(14).mean()`). Sin Walk-Forward en Lab. |
| `nasdaq_araujo_vwap.py` | `nasdaq_araujo_vwap` | **Alta fidelidad** a la estrategia Nasdaq Araujo (`09:35–11:00 NY`, veto primeros 5 min, ruptura Londres + rechazo VWAP `>= 30%`, `RVOL >= 1.2`, veto cripto, `R:R >= 2.0`) | Exclusiva TradFi (`QQQ`, `SPY`, `NQ=F`, acciones/CEDEARs). Nunca certificada en Walk-Forward con datasets `15m` TradFi (solo usada por `resolve_auto_strategy` en horario apertura NY). |
| `hyenuk_chu_multibagger.py` | `hyenuk_chu_multibagger` | **Alta fidelidad** a Hyenuk Chu (`1h` Long-Only, `EMA 200` alcista + `SMA 20`, Vela Elefante `>= 1.0x ATR`, `RVOL >= 1.10`, anti-euforia `RSI <= 75`, Stop al 50%, Peluqueo 50% en `+3.5%`) | Exclusiva TradFi / acciones de crecimiento. Bug menor de copy-paste en línea `132` (`"araujo_inactive"`). Sin Walk-Forward 1H en Lab. |
| `trailing_trend_runner.py` | `trailing_trend_runner` | Implementación propia (3 escalones: BE `+0.40%`, cerrojo `+1.00% -> +0.80%`, trailing libre); `EMA 200`, `SMA 20/50`, `RSI [40, 72]`, `RVOL >= 0.80` | Su mecánica de 3 escalones ya fue absorbida en `backend/daemon.py` (según `laboratorio/README.md:15`). En `15m` cripto el BE `+0.40%` ahoga operaciones; evaluar en `4h/1d` o archivar tras desacoplar `resolve_auto_strategy`. |
| `trailing_short_runner.py` | `trailing_short_runner` | Espejo bajista propio (`EMA 200` pendiente `< -0.005`, cascada `SMA20 <= SMA50 <= EMA200`, `RSI [28, 50]`, `RVOL >= 1.00`, `SL <= 1.50%`) | Sin Walk-Forward en Lab; solo activa vía `resolve_auto_strategy` en Forex/Futuros bajista cuando no se pasan `allowed_strategies`. |

---

### 2.4 Inservibles / Obsoletas / Rotas — 5 archivos

| Archivo | ID(s) | Diagnóstico técnico comprobado en código |
| :--- | :--- | :--- |
| `tendencia_institucional_01.py` | `01_tendencia_institucional_15m` | **Obsoleta + R:R roto:** prototipo Fase 1 (`15m`). Busca `estrategia_01.json` en la raíz del proyecto (**archivo inexistente**). Fija `tp_calc = round(max(3.0, sl_calc * 1.5), 2)` (`línea 86`, R:R bruto `1.5`), por lo que falla sistemáticamente la compuerta `rr_info["net_rr"] < MIN_NET_RR` (`2.0`) en línea `115`. |
| `cazador_rebotes_02.py` | `02_cazador_rebotes_atr_15m` | **Bloqueada + contrato obsoleto:** tiene `long_entries_suspended: bool = True` hardcodeado (`línea 61`), por lo que **nunca emite señales elegibles** (`línea 152`). Busca `estrategia_02.json` inexistente y su función `evaluar_estrategia` valida `rr_neto >= 1.0` (`línea 45`), violando la Regla 3 (`R:R >= 2.0`). |
| `mean_reversion_atr.py` | `mean_reversion_atr` | **Bloqueada en vivo (`long_entries_suspended = True`):** `línea 28` suspende incondicionalmente todas las entradas LONG (`common_failures` en `línea 86`), por lo que **siempre devuelve `candidate_eligible = False`**. Sus constantes de Z-Score (`-2.0`, `[-1.2, -0.4]`) siguen acopladas a `registry.py`, `backtest.py` y 4 tests. |
| `scalping_cuantitativo_5m.py` | 5 IDs en cuarentena (`scalping_vwap_2sigma_5m`, `scalping_m5_rsi3_adx5_ema50`, `smc_liquidity_scalper_m5`, `triada_fractal_fibo_ema50_5m`, `donchian_15m_atr_runner`) | **Reprobada en Lab + dependencia externa + bug matemático:** las 5 clases están marcadas `(Cuarentena Scalping)` con `active: false` en `config_manager.py`, vetadas en cripto por fee drag `0.26%` con SLs fijos de `0.60%–0.85%`. Además: (a) es el **único archivo que importa `ta`** (`línea 21`); (b) `TriadaFractalFibo5M` (`líneas 431-448`) calcula mal Fibonacci (`fibo_618 = l_roll + 0.382 * f_diff`, ignorando `0.75` e invirtiendo la lógica de `disparo_short`); (c) ninguna clase lee `StrategyConfigManager` (ignoran overrides de `strategies_config.json`). |
| `catalogo/principal/ensamble_campeon_binance_ETH_USDT_4h.py` | `ensamble_campeon_binance_ETH_USDT_4h` | **Reprobada por métricas:** ensamble histórico de 2 sensores (`2_squeeze_dual_eth_4h` + `donchian_breakout_1h`) cuyo Profit Factor consolidado se degrada a **1.29** (`< 1.50`), DD sube a **14.04%**, y su `arbitro_ia` (`línea 341`) no aplica sizing fraccional (`return True, 1.0`). Superada ampliamente por `2_squeeze_dual_eth_4h` sola (PF 1.78, DD 10.38%). **0 tests dependen de ella.** |

---

## 3. Plan de Limpieza Preparado (Ejecutar Recién Al Finalizar la Semana de Prueba)

> **Regla #0 (Pre-check obligatorio de dependencias antes de tocar cualquier archivo):**
> Toda acción marcada con ⚠️ exige actualizar previamente las referencias exactas listadas en `tests/` y/o `backend/` y correr `pytest` completo tras cada paso. Las acciones marcadas con 🟢 tienen **cero dependencias en `tests/` y `backend/`** y pueden limpiarse primero sin riesgo de regresión.

### 3.1 Matriz de Acciones por Archivo (50 archivos)

| Archivo (`backend/estrategias/...`) | Categoría | Acción post-campaña | Dependencias Regla #0 (`tests/` y `backend/` críticos) |
| :--- | :--- | :--- | :--- |
| `__init__.py`, `base.py`, `registry.py`, `catalog_adapter.py`, `catalogo_manager.py`, `config_manager.py` | Infraestructura | **CONSERVAR** | Núcleo del sistema (importado por todo `backend/` y `tests/`). Refactorizar solo al migrar estructura (§4). |
| `laboratorio/__init__.py`, `laboratorio/README.md` | Infraestructura / Doc | **ARCHIVAR** | 🟢 0 tests. Actualizar o integrar en nueva carpeta `archivo_descartadas/README.md`. |
| `catalogo/principal/metadata.json`, `catalogo/operador_presente/metadata.json` | Metadatos | **CONSERVAR** | Actualizar sus claves simultáneamente al borrar duplicados del catálogo. |
| `catalogo/para_testear/ganadoras/metadata.json`, `catalogo/para_testear/heredadas/metadata.json` | Metadatos | **CONSERVAR** | ⚠️ `test_lab_catalogo_dinamico.py:21,63-91` usa `GANADORAS_DIR`; `catalogo_manager.py:30-31` requiere ambas carpetas. |
| `kula_balam_cava_ruiz.py` | Activa (`auto`) | **CONSERVAR** | 8 tests (`test_estrategias.py`, `test_friction_and_swap.py`, `test_futures_simulation.py`, etc.), `daemon_state.json`. *(Post-campaña: corregir desvíos Fibo `0.45–0.78` y `atr_noise_mult 1.0`).* |
| `donchian_breakout_1h.py` | Activa (`auto`) | **CONSERVAR** | 7 tests (`test_estrategias.py`, `test_derivatives_flow.py`, etc.), `daemon_state.json`. *(Post-campaña: alinear SL/TP `1.40/3.36` vs `1.60/4.16` del Lab).* |
| `catalogo/principal/1_donchian_breakout_sol_4h.py` | Activa (`auto`) | **CONSERVAR** | 3 tests (`test_daemon_broker.py`, `test_campaign_audit.py`, `test_ledger_sqlite.py`), `daemon_state.json`. |
| `catalogo/principal/2_squeeze_dual_eth_4h.py` | Activa (`auto`) | **CONSERVAR** | 2 tests (`test_daemon_broker.py`, `test_ledger_sqlite.py`), `daemon_state.json`. *(Alinear `rvol_min` docstring vs `0.70`).* |
| `catalogo/principal/cava_fallo_macd_eurusd_1h_slot1.py` | Activa (`auto`) | **CONSERVAR** | 2 tests (`test_daemon_broker.py`, `test_ledger_sqlite.py`), `daemon_state.json`, `contexto_macro.md`. |
| `catalogo/principal/kula_cava_eth_1h.py` | Activa (`auto`) | **CONSERVAR** | 4 tests (`test_health_watchdog.py`, `test_lab_catalogo_dinamico.py`, `test_daemon_broker.py`, `test_ledger_sqlite.py`), `daemon_state.json`. |
| `catalogo/principal/kula_cava_sol_1h.py` | Activa (`auto`) | **CONSERVAR** | 2 tests (`test_daemon_broker.py`, `test_campaign_audit.py`), `daemon_state.json`. |
| `catalogo/principal/ttm_squeeze_eth_1h.py` | Activa (`auto`) | **CONSERVAR** | 3 tests (`test_triada_service.py`, `test_daemon_broker.py`, `test_campaign_audit.py`), `daemon_state.json`. |
| `catalogo/principal/ttm_squeeze_sol_4h.py` | Activa (`auto`) | **CONSERVAR** | 2 tests (`test_daemon_broker.py`, `test_campaign_audit.py`), `daemon_state.json`. |
| `catalogo/operador_presente/mtf_presencial_15m.py` | Activa (Presencial) | **CONSERVAR** | 2 tests (`test_daemon_broker.py`, `test_campaign_audit.py`), `campaign_config.json`, `daemon.py`. |
| `catalogo/operador_presente/mtf_presencial_5m.py` | Activa (Presencial) | **CONSERVAR** | 5 tests (`test_health_watchdog.py`, `test_rfc_2026_11_architecture.py`, `test_daemon_broker.py`, `test_campaign_audit.py`, `test_ledger_sqlite.py`), `campaign_config.json`. |
| `catalogo/operador_presente/fractal_squeeze_15m.py` | Activa (Presencial) | **CONSERVAR** | 2 tests (`test_daemon_broker.py`, `test_campaign_audit.py`), `triada_service.py`, `campaign_config.json`. |
| `catalogo/principal/1_donchian_breakout_sol_4h_slot1.py` | Repetida (AST clon) | **BORRAR DUPLICADO** | 🟢 **0 tests**, 0 imports en `backend/`. Quitar también su entrada en `principal/metadata.json`. |
| `catalogo/principal/21_donchian_breakout_sol_4h.py` | Repetida (AST clon) | **BORRAR DUPLICADO** | 🟢 **0 tests**, 0 imports en `backend/`. Quitar de `principal/metadata.json`. |
| `catalogo/principal/31_donchian_breakout_sol_4h.py` | Repetida (AST clon) | **BORRAR DUPLICADO** | 🟢 **0 tests**, 0 imports en `backend/`. Quitar de `principal/metadata.json`. |
| `catalogo/principal/mejorada_cava_fallo_macd_eurusd_1h.py` | Repetida (lógica idéntica) | **BORRAR DUPLICADO** | 🟢 **0 tests**, 0 imports en `backend/`. Quitar de `principal/metadata.json`. |
| `catalogo/principal/ensamble_campeon_binance_ETH_USDT_4h_slot1.py` | Repetida (1-sensor de #24) | **BORRAR DUPLICADO** | 🟢 **0 tests**, 0 imports en `backend/`. Quitar de `principal/metadata.json`. |
| `catalogo/principal/ensamble_campeon_binance_ETH_USDT_4h.py` | Inservible (PF 1.29) | **DESINFECTAR/ELIMINAR** | 🟢 **0 tests**, 0 imports en `backend/`. Quitar de `principal/metadata.json`. |
| `catalogo/principal/donchian_breakout_1h.py` | Repetida (sombreada) | **BORRAR DUPLICADO** | ⚠️ El ID `donchian_breakout_1h` lo cubre la clase en raíz (`backend/estrategias/donchian_breakout_1h.py`). Borrar esta copia solo tras quitar su entrada de `principal/metadata.json` y confirmar que Lab usa `backtest_lab/estrategias_math/donchian_breakout_1h.py`. |
| `catalogo/principal/squeeze_dual_eth_4h.py` | Repetida (sombreada) | **BORRAR DUPLICADO** | ⚠️ El ID `squeeze_dual_eth_4h` lo cubre `backend/estrategias/squeeze_dual_eth_4h.py` (en `OFFICIAL`). Quitar entrada de `principal/metadata.json`; verificar `test_lab_scaling_audit.py`. |
| `catalogo/principal/cava_fallo_macd_eurusd_1h.py` | Repetida (SHA256 exacto) | **BORRAR DUPLICADO** | ⚠️ **3 tests dependen del ID `cava_fallo_macd_eurusd_1h`** (`test_estrategias.py:1955-1999`, `test_health_watchdog.py`, `test_daemon_broker.py`). Antes de borrar, consolidar el ID canónico (o mantener un único archivo sin sufijo `_slot1` y migrar `daemon_state.json`). |
| `catalogo/principal/squeeze_dual_eth_4h_slot1.py` | Repetida (clon) | **BORRAR DUPLICADO** | ⚠️ **4 tests** (`test_estrategias.py:1954-2009`, `test_regressions.py`, `test_health_watchdog.py`, `test_daemon_broker.py`) + fallbacks en `backend/daemon.py:28,40,83,830`, `backend/main.py:78` y `frontend/js/app.js`. Migrar primero esos fallbacks/tests a `2_squeeze_dual_eth_4h`. |
| `catalogo/operador_presente/kula_cava_eth_1h.py` | Repetida (SHA256 exacto) | **BORRAR DUPLICADO** | ⚠️ **Rompe `tests/test_lab_catalogo_dinamico.py:49`** (`/api/catalogo_formulas/operador_presente/kula_cava_eth_1h.py`). Eliminar solo tras implementar vista por etiquetas/manifest único (§4) y actualizar el test. |
| `catalogo/operador_presente/kula_cava_sol_1h.py` | Repetida (SHA256 exacto) | **BORRAR DUPLICADO** | ⚠️ Listada en UI `operador_presente` vía `catalogo_manager.py`. Eliminar junto al manifest único (§4) para no duplicar `.py`. |
| `catalogo/operador_presente/cava_fallo_macd_eurusd_1h.py` | Repetida (SHA256 exacto) | **BORRAR DUPLICADO** | ⚠️ Sombreada por `principal/cava_fallo_macd_eurusd_1h.py`, pero listada en UI `operador_presente`. Unificar bajo manifest único (§4). |
| `squeeze_dual_eth_4h.py` (raíz) | Repetida (wrapper clase) | **ARCHIVAR** | ⚠️ Importada por `registry.py:20,32`, `config_manager.py`, `daemon.py`, `test_lab_scaling_audit.py`. Mantener hasta migrar `OFFICIAL_STRATEGIES` y `test_lab_scaling_audit.py` a `2_squeeze_dual_eth_4h`. |
| `catalogo/principal/squeeze_dual_eth_fondeo_strict_4h.py` | Para Chequear | **TESTEAR EN LAB** | 0 tests; referenciada en `backend/daemon.py:27,39` y `frontend/js/app.js`. Comparar en Lab (3Y + Rolling WFO + MC DD) contra `2_squeeze_dual_eth_4h`. |
| `triple_confluencia_4h.py` | Para Chequear | **TESTEAR EN LAB** | ⚠️ 2 tests (`test_estrategias.py:1664,1825`, `test_lab_estrategias_heredadas.py`), `registry.py`, `__init__.py`, `config_manager.py`. Corregir `RSI [55,75]` y uso de `params` antes del test Walk-Forward 4H. |
| `tres_velas_wyckoff_bulkowski.py` | Para Chequear | **TESTEAR EN LAB** | ⚠️ 1 test (`test_estrategias.py`), `registry.py:15,34`, `__init__.py`, y **importada por `trailing_trend_runner.py:189`**. Someter a Walk-Forward antes de habilitar en campaña. |
| `alex_ruiz_triada_3velas.py` | Para Chequear | **TESTEAR EN LAB** | ⚠️ 2 tests (`test_estrategias.py:1194-1595`, `test_telegram_notifier.py`), `registry.py`, `__init__.py`, `config_manager.py`. Evaluar si aporta alpha diferencial respecto a `kula_balam_cava_ruiz`; si no, archivar. |
| `nasdaq_araujo_vwap.py` | Para Chequear | **TESTEAR EN LAB** | ⚠️ 4 tests (`test_estrategias.py`, `test_telegram_notifier.py`, `test_lab_estrategias_heredadas.py`, `test_daemon_broker.py`), `registry.py:296,309`. Testear en Lab sobre `QQQ`/`SPY` `15m` antes de decidir producción TradFi. |
| `hyenuk_chu_multibagger.py` | Para Chequear | **TESTEAR EN LAB** | ⚠️ 2 tests (`test_estrategias.py`, `test_lab_estrategias_heredadas.py`), `registry.py:278,316`. Corregir typo `"araujo_inactive"` (`línea 132`) y testear en `1h` acciones US/BYMA. |
| `trailing_trend_runner.py` | Para Chequear | **ARCHIVAR** | ⚠️ 4 tests (`test_estrategias.py`, `test_telegram_notifier.py`, `test_lab_estrategias_heredadas.py`, `test_daemon_broker.py`), `registry.py:268-297`, `daemon.py`, `paper_broker.py`, `ledger.py`. Sus 3 escalones ya están en `daemon.py`; archivar solo tras desacoplar `resolve_auto_strategy`. |
| `trailing_short_runner.py` | Para Chequear | **ARCHIVAR** | ⚠️ 2 tests (`test_estrategias.py`, `test_daemon_broker.py`), `registry.py:258,294`, `daemon.py`, `health_watchdog.py`. Evaluar en 4H o archivar junto a `trailing_trend_runner.py`. |
| `scalping_cuantitativo_5m.py` | Inservible (cuarentena) | **DESINFECTAR/ELIMINAR** | ⚠️ 0 tests directos, pero **importada en `registry.py:21-27,53-57`** y referenciada como fallback en `backend/daemon.py:132,912,1051,2332,2767,2970`, `backend/main.py:3317`, `config_manager.py` y `frontend/js/app.js`. Al retirarla se elimina además la dependencia externa `ta` de `backend/estrategias/`. |
| `tendencia_institucional_01.py` | Inservible (R:R roto) | **DESINFECTAR/ELIMINAR** | ⚠️ `test_estrategias.py:519-527`, `registry.py:13,47`, `backend/daemon.py:2760,2770,2980`, `backend/main.py:445`. Migrar el fallback de `main.py:445` y retirar test heredado antes de eliminar. |
| `cazador_rebotes_02.py` | Inservible (bloqueada) | **DESINFECTAR/ELIMINAR** | ⚠️ `test_estrategias.py:549-555`, `registry.py:14,48,251`, `backend/daemon.py:1160,2760,2770,2980`, `scripts/diagnostico/*_02.py`. Desacoplar `registry.py:251` y `daemon.py` antes de eliminar. |
| `mean_reversion_atr.py` | Inservible (bloqueada) | **ARCHIVAR** | ⚠️ **4 tests** (`test_estrategias.py:43-741`, `test_regressions.py`, `test_backtest.py`, `test_daemon_broker.py`), `registry.py:8,46,199,204,264`, `backend/backtest.py`, `__init__.py`. No borrar sin refactorizar `resolve_auto_strategy` y `backtest.py` (o rehabilitarla tras Walk-Forward 4H). |

### 3.2 Orden Seguro de Limpieza Post-Campaña (3 Olas)

1. **Ola 1 — Cero riesgo (6 archivos, 0 tests, 0 imports en `backend/`):**
   - Borrar `1_donchian_breakout_sol_4h_slot1.py`, `21_donchian_breakout_sol_4h.py`, `31_donchian_breakout_sol_4h.py`, `mejorada_cava_fallo_macd_eurusd_1h.py`, `ensamble_campeon_binance_ETH_USDT_4h_slot1.py`, `ensamble_campeon_binance_ETH_USDT_4h.py` y limpiar sus 6 entradas de `catalogo/principal/metadata.json`.
   - Ejecutar `venv/bin/pytest` → debe pasar al 100% sin tocar ningún test.
2. **Ola 2 — Deduplicación de catálogo + migración de fallbacks (6 archivos):**
   - Unificar `cava_fallo_macd_eurusd_1h_slot1.py` / `cava_fallo_macd_eurusd_1h.py` bajo un solo ID canónico sin `_slot1`.
   - Migrar fallbacks `squeeze_dual_eth_4h_slot1` en `daemon.py`, `main.py` y los 4 tests hacia `2_squeeze_dual_eth_4h` (y borrar `principal/squeeze_dual_eth_4h_slot1.py`, `principal/squeeze_dual_eth_4h.py` y `principal/donchian_breakout_1h.py`).
   - Reemplazar las 3 copias físicas en `operador_presente/` (`kula_cava_eth_1h.py`, `kula_cava_sol_1h.py`, `cava_fallo_macd_eurusd_1h.py`) por un campo `"modos": ["auto", "presencial"]` en un manifest único (§4) y actualizar `test_lab_catalogo_dinamico.py:49`.
3. **Ola 3 — Desinfección de obsoletas/cuarentena y Screening de candidatas:**
   - Retirar `scalping_cuantitativo_5m.py`, `tendencia_institucional_01.py` y `cazador_rebotes_02.py` tras limpiar sus fallbacks en `registry.py`, `daemon.py`, `main.py` y sus tests legacy.
   - Ejecutar Walk-Forward Lab (3Y + OOS 30% + Rolling WFO + MC DD) sobre `squeeze_dual_eth_fondeo_strict_4h`, `triple_confluencia_4h`, `tres_velas_wyckoff_bulkowski`, `nasdaq_araujo_vwap` y `hyenuk_chu_multibagger` para promover o mover a `archivo_descartadas/`.

---

## 4. Propuesta de Orden Futuro de Guardado (Arquitectura SSOT Sin Duplicados)

### 4.1 Estructura de Carpetas Propuesta para `backend/estrategias/`

```text
backend/estrategias/
├── core/                           # Infraestructura pura (cero lógica de señales)
│   ├── base.py                     # EstrategiaBase
│   ├── registry.py                 # Descubrimiento único (prohibido sombrear IDs)
│   ├── catalog_adapter.py          # Adaptador único formula_matematica + arbitro_ia
│   ├── catalog_manifest.json       # SSOT de metadatos, modos ["auto"|"presencial"], slots y estado
│   └── config_manager.py           # Overrides de parámetros en runtime
├── produccion/                     # SOLO estrategias certificadas Walk-Forward + MC DD <= 8%
│   ├── kula_balam_cava_ruiz.py
│   ├── donchian_breakout_sol_4h.py
│   ├── donchian_breakout_multi.py
│   ├── squeeze_dual_eth_4h.py
│   ├── ttm_squeeze_eth_1h.py
│   ├── ttm_squeeze_sol_4h.py
│   ├── kula_cava_sol_1h.py         # Etiquetada modos: ["auto", "presencial"] en manifest (SIN copia física)
│   ├── kula_cava_eth_1h.py         # Etiquetada modos: ["auto", "presencial"] en manifest (SIN copia física)
│   └── cava_fallo_macd_eurusd_1h.py# Etiquetada modos: ["auto", "presencial"] en manifest (SIN copia física)
├── presencial/                     # SOLO estrategias de supervisión humana (NO elegibles por daemon autónomo)
│   ├── mtf_presencial_15m.py
│   ├── mtf_presencial_5m.py
│   └── fractal_squeeze_15m.py
├── en_evaluacion/                  # Candidatas pendientes de certificación Walk-Forward en Lab
│   ├── squeeze_dual_eth_fondeo_strict_4h.py
│   ├── triple_confluencia_4h.py
│   ├── tres_velas_wyckoff_bulkowski.py
│   ├── alex_ruiz_triada_3velas.py
│   ├── nasdaq_araujo_vwap.py
│   └── hyenuk_chu_multibagger.py
└── archivo_descartadas/            # Solo referencia histórica (NO importadas por registry.py)
    ├── README.md                   # Motivo cuantitativo de descarte (PF, DD, fee drag, fecha)
    ├── mean_reversion_atr.py
    ├── trailing_trend_runner.py
    └── trailing_short_runner.py
```

### 4.2 Reglas de Nomenclatura y Gobernanza (Anti-Duplicación)

1. **Formato canónico de archivo e ID:** `<familia>_<activo_o_universo>_<tf>.py` en minúsculas `snake_case`, donde `id == stem` siempre.
   - **Prohibido** incluir prefijos numéricos de orden (`1_`, `21_`, `31_`), adjetivos (`mejorada_`) ni sufijos de asignación temporal (`_slot1`, `_slot2`). El slot asignado vive exclusivamente en `catalog_manifest.json` y `daemon_state.json`.
2. **Un solo archivo físico por estrategia (Cero copias entre `produccion/` y `presencial/`):**
   - Si una estrategia certificada (ej. `kula_cava_eth_1h.py`) puede operar tanto en `auto` como en panel presencial, reside **una sola vez** en `produccion/` y declara `"modos": ["auto", "presencial"]` en `catalog_manifest.json`.
3. **Bloqueo duro contra colisión de IDs en `registry.py`:**
   - En lugar de ignorar/sombrear silenciosamente (`if strat_id in existing_ids: continue`), lanzar `ValueError` en pruebas unitarias si dos archivos `.py` declaran el mismo `id` o el mismo `sha256` normalizado (AST).
4. **Vínculo limpio y unidireccional con `backtest_lab/`:**
   - `backtest_lab/estrategias_math/` + `backtest_lab/estrategias_ia/` = **único taller de investigación y edición** (borradores y pruebas nuevas como `rsi_adx_ema50_pullback.py` o `rvol_tod_breakout_1h.py` viven allí mientras se testean).
   - `backtest_lab/promovidas/` = **bitácora inmutable de snapshots con timestamp** (solo auditoría histórica; el bot nunca la importa).
   - **Promoción atómica (`/api/promover_a_produccion`):** al promover una fórmula con el mismo ID canónico, **sobrescribe en lugar de crear clones `21_`/`31_`/`_slot1`**, guarda snapshot previo en `backtest_lab/promovidas/`, valida que no existan parámetros no usados ni discrepancias `CONFIG_IA` vs docstring, y registra su `sha256` y métricas OOS/WFO/MC DD en `catalog_manifest.json`.
   - `archivo_descartadas/` nunca se carga en `STRATEGY_REGISTRY` y no puede ser seleccionada desde `daemon_state.json`.
