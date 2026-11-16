---
name: kula-balam-cava-ruiz
description: >-
  Protocolo de Inteligencia Táctica Cuantitativa: Módulo Kula & Rol Balam.
  Fusión fractal de Alex Ruiz (Tríada 1D-1H-5M, Zona Dorada Fibonacci 0.50-0.75 y EMA 50)
  con la doctrina de parqué de José Luis Cava (Clúster de Volumen Horizontal, Agotamiento Onda C,
  Fallo de MACD, secado de volumen RVOL < 0.85, Stop a Misa con margen de 2 ticks y Peluqueo TP1).
---

# Kula Balam: Protocolo Táctico Cava & Ruiz

Este agente ejecuta la doctrina oficial del **Cuaderno Maestro de Trading**:
1. **La Estructura Fractal de Alex Ruiz (Módulo Kula)**: Jerarquía de tres temporalidades (1D $\rightarrow$ 1H $\rightarrow$ 5M), retrocesos en la Zona Dorada de Fibonacci (0.50 a 0.75) y quiebre binario de la $\text{EMA}_{50}$.
2. **La Lectura de Liquidez y Parqué de José Luis Cava**: Identificación de Clústeres de Volumen Horizontal a la izquierda, agotamiento de la Onda C de Elliott, gatillo de Fallo de MACD, divergencia de RSI con secado de volumen ($\text{RVOL} < 0.85$), Stop Loss con margen de 2 ticks adaptativos contra *Stop Hunting* y la regla innegociable: *"Si no veo lo que quiero ver, NO VOY"*.

---

## 🧭 Embudo Operativo en 4 Fases

1. **Fase 1 (Contexto 1D):** Filtro direccional por $\text{EMA}_{50}$. Si el mercado corta erráticamente la media, inacción obligatoria (`[MANTENER]`).
2. **Fase 2 (Zona de Descuento 1H):**
   - Retroceso en Zona Dorada de Fibonacci ($0.50 - 0.75$). Abortar si perfora $> 0.75$.
   - Coincidencia con Clúster de Volumen Horizontal a la izquierda (nodo de alta densidad).
   - Fin de Onda C (quiebre de directriz 2-4 y entrada en micro-quinta onda).
3. **Fase 3 (Gatillo 5M / 1M):**
   - Fallo de MACD: Mínimo en precio pero suelo creciente en histograma/líneas (absorción de venta).
   - Secado de volumen previo ($\text{RVOL} < 0.85$).
   - Cierre de vela con cuerpo sobre la $\text{EMA}_{50}$.
4. **Fase 4 (Gestión de Riesgo & Salida):**
   - Stop Loss inamovible en el mínimo $-2$ ticks adaptativos ($\max(2 \times \text{Tick}, 0.2 \times \text{ATR}, 0.15\% \times \text{Precio})$).
   - Peluqueo: Liquidación del 50% en TP1 ($R:R \ge 1:2.0$) trasladando el SL a Breakeven.
   - Remanente (50% restante): Trailing libre hasta cruce inverso de MACD o perforación de $RSI = 50$.

---

## 🛑 Las 5 Compuertas de Veto

- **Veto 1:** Vela Viva (solo entrar en segundo cero tras cierre).
- **Veto 2:** Cuchillo Cayendo (velas rojas sin mecha de absorción $< 15\%$).
- **Veto 3:** Bull Trap / Falsa Ruptura (mecha superior $\ge 50\%$).
- **Veto 4:** Ruido ATR ($SL < 1.5 \times \text{ATR}$).
- **Veto 5:** "No voy" de Cava: Si el precio llega sin fallo de MACD ni absorción, abstención obligatoria.
