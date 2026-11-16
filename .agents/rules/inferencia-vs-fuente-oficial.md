# Protocolo de Transparencia Epistémica: Inferencia vs. Afirmación Contrastada con Fuentes Oficiales

Toda interacción de cualquier Inteligencia Artificial (Antigravity, Claude, Cursor, Copilot, ChatGPT, Ollama u otros LLMs) que opere, audite, responda o sugiera cambios en este proyecto está estrictamente sujeta a este mandato inquebrantable:

## 1. Distinción Obligatoria entre Afirmar e Inferir
Siempre que el usuario, el equipo o un auditor plantee una pregunta, cuestione un comportamiento, solicite una explicación o reciba una sugerencia:

### A. Afirmación Categórica (Solo con Contraste Oficial Directo)
- La IA **SOLO** puede afirmar de manera categórica (ej: *"esto funciona así"*, *"el sistema ejecuta X"*, *"el broker permite Y"*) si lo ha **contrastado y verificado directamente contra**:
  1. **Código fuente real inspeccionado en el proyecto:** Citando archivo y rango de líneas exacto (ej. `[backend/daemon.py#L285-L310](file:///...)`).
  2. **Fuentes o reglamentaciones oficiales del mercado/broker:** Documentación oficial de APIs (Interactive Brokers, Alpaca, Binance, BYMA), reglamentos bursátiles oficiales (horarios de sesión de NYSE/NASDAQ/SEC) o documentación técnica de librerías.
  3. **Tests unitarios o de integración ejecutados y verificados** en la terminal.
- Debe citar la fuente, comando o archivo exacto en el que se basa la afirmación.

### B. Inferencia Explícita (Obligatorio Etiquetarla)
- Siempre que la IA exponga una hipótesis, deducción, extrapolación teórica, interpretación probabilística o suposición no contrastada directamente con el código o fuente oficial:
  - **DEBE DECLARARLO EXPLÍCITAMENTE AL MARGEN O AL INICIO** usando una de las siguientes marcas claras:
    - `[Inferencia]` ...
    - `Aviso de Inferencia: Basado en deducción / hipótesis no verificada en fuente oficial...`
    - `"Infiero que..."` / `"Nuestra inferencia técnica es..."`
- **Queda terminantemente prohibido:**
  - Disfrazar una inferencia de hecho técnico demostrado.
  - Asumir o responder pasivamente sin haber verificado en el código si la función realmente hace lo que se cree.
  - Presentar capacidades teóricas de software como si fueran operaciones de mercado real (ej: confundir un cierre contable en una base de datos local SQLite con la ejecución de una orden en una bolsa con rueda cerrada).

## 2. Protocolo de Respuesta ante Cuestionamientos o Sugerencias
Cuando el usuario cuestione o sugiera algo sobre la arquitectura, la respuesta debe estructurarse con total honestidad intelectual:
1. **Hecho Contrastado (Código / Fuente Oficial):** Lo que está efectivamente escrito y comprobado.
2. **Inferencia / Hipótesis:** Lo que la IA deduce o propone como posible explicación o alternativa, indicando su grado de certeza.
3. **Acción / Solución Verificada:** La comprobación empírica en el código o tests.
