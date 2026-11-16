# Protocolo de Contraste Activo y Asimetría Matemática

Toda interacción de cualquier agente en este espacio de trabajo está sujeta a esta regla obligatoria:

## 1. Prohibido responder teoría sin auditar el código
- Cuando el usuario o el equipo presente una hipótesis, tabla de riesgo/beneficio, ratio R:R o captura visual:
  1. **NUNCA** responder de forma pasiva o puramente teórica ("sí, conceptualmente es así").
  2. **SIEMPRE** abrir e inspeccionar inmediatamente los archivos de código fuente correspondientes (`backend/main.py`, `backend/daemon.py`, `backend/quant_analysis.py`, SQLite `trading_ledger`).
  3. Verificar si el comportamiento del software actualmente en ejecución coincide o discrepa con la hipótesis planteada.
  4. Si existe una contradicción, desajuste o fuga de capital (ej. Take Profits prematuros cortando ganancias en centavos frente a Stop Losses más amplios), **alertarlo proactivamente y plantear la corrección con análisis de costo/beneficio**.

## 2. Soberanía de Asimetría Matemática
- Todo trade o estrategia ejecutada debe mantener un ratio de beneficio/riesgo neto $R:R \ge 1:2$ o $1:3$.
- Queda vetado cualquier cierre prematuro que invierta la esperanza matemática de la cuenta.

## 3. Transparencia Epistémica: Inferencia vs. Afirmación Oficial
- Cuando se cuestione o sugiera algo, la IA debe declarar explícitamente si su respuesta es una **afirmación contrastada** (con archivo, línea o documentación oficial de broker/bolsa) o una **inferencia**.
- Siempre que la IA infiera o elabore una hipótesis, **debe mencionarlo explícitamente** con el prefijo `[Inferencia]`. Prohibido presentar suposiciones o capacidades teóricas como hechos consumados del mercado real.

