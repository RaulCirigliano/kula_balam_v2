# 📋 Tareas Pendientes: Escalado Cuantitativo por Slots en Kula Balam

> **Fecha de Creación:** 08-Nov-2026  
> **Estado:** Guardado para implementación futura  
> **Origen:** Iniciativa de escalado basada en rankings positivos y auditorías del Backtest Lab  

---

## 1. Fundamento Matemático y Filosofía del Escalado

El escalado de riesgo no debe ejecutarse de forma arbitraria ni por salto manual sin respaldo de caja. Se rige por el principio de **Anti-Martingala con Trinquete de Capital Semilla**:
- **Capital Semilla de la Ranura:** **$25.00 USD** (1 slot de los 4 que componen la cuenta de $100 USD).
- **Riesgo Base (Nivel 1):** **$0.50 USD de pérdida máxima en Stop Loss** (2.0% del slot / 0.50% de la cuenta consolidada).
- **Riesgo Escalado (Nivel 2):** **$1.00 USD de pérdida máxima en Stop Loss** (4.0% del slot / 1.00% de la cuenta consolidada).
- **Regla de Oro:** Jamás se arriesga $1.00 USD con el capital inicial de $25 USD. El escalado solo se financia con **ganancias acumuladas del propio mercado**.

---

## 2. Requisitos Previos Obligatorios (Compuerta del Lab)

Para que el Daemon de Kula Balam autorice el escalado en un activo y estrategia, la auditoría en el Backtest Lab debe arrojar:
1. **Ratio R:R Realizado Neto $\ge 2.10$** en simulación con comisiones ($0.26\%$ en cripto).
2. **Esperanza Matemática Positiva en Tramo Ciego (OOS 30%):** $E = (WR \times R:R) - (1 - WR) > 0$.
3. **Máximo Drawdown Histórico $\le 15.0\%$**.
4. **Resistencia a Rachas Adversas:** El slot debe soportar un mínimo de **12 pérdidas consecutivas** sin que el saldo caiga por debajo de $18.00 USD.

---

## 3. Lógica a Implementar en Kula Balam (`backend/daemon.py`)

Cuando se decida activar en el motor operativo:

### A. Seguimiento de PnL y Saldo por Ranura (`Slot Equity Tracker`)
- Cada ranura operativa llevará un registro de su saldo dinámico:
  $$\text{Saldo Slot} = \$25.00\text{ USD} + \sum \text{PnL Neto Cerrado}$$

### B. Gatillo de Escalado ($0.50 $\rightarrow$ $1.00 USD)
- Cuando el saldo del slot alcance **$\ge \$35.00\text{ USD}$** (+$10.00 USD de beneficio neto acumulado):
  - El Daemon eleva el presupuesto de riesgo por Stop Loss de **$0.50 USD a $1.00 USD**.
  - Si la posición con SL 1.8% requiere $48.54 USD de nocional:
    - En **Spot puro**: Toma temporalmente $13.54 USD de liquidez de una ranura hermana desocupada de la Bóveda (o espera a que el slot acumule $48.54 USD).
    - En **Futuros/Margen**: Aplica un apalancamiento mínimo de $1.38x$ sobre los $35 USD del slot.

### C. Trinquete de Seguridad y Desescalado Automático
- Si tras escalar a $1.00 USD sobreviene una racha adversa y el saldo del slot retrocede a **$< \$30.00\text{ USD}$**:
  - El Daemon **desescala inmediatamente el riesgo a $0.50 USD**.
  - Se protege de forma absoluta el capital inicial de $25.00 USD.

---

## 4. Lista de Tareas de Implementación en Kula Balam

- [ ] **Daemon (`backend/daemon.py`):**
  - [ ] Añadir campo `slot_realized_pnl` en el seguimiento de posiciones del `TraderDaemon`.
  - [ ] Implementar la función `check_slot_scaling_threshold(slot_balance)`.
  - [ ] Aplicar el trinquete dinámico: si `slot_balance >= 35.0` $\rightarrow$ `risk_usd = 1.00`; si `slot_balance < 30.0` $\rightarrow$ `risk_usd = 0.50`.
- [ ] **Frontend (`frontend/index.html` y `frontend/js/app.js`):**
  - [ ] Reflejar en el termómetro de ranuras el estado del slot: `[Nivel Base: $0.50 USD / SL]` o `[Nivel Escalado: $1.00 USD / SL]`.
  - [ ] Mostrar el progreso hacia los $35.00 USD (barra de progreso de ganancia acumulada del slot).
- [ ] **Base de Datos / Ledger (`backend/ledger.py`):**
  - [ ] Guardar el estado de escalado alcanzado por cada ranura para persistencia ante reinicios del daemon.
