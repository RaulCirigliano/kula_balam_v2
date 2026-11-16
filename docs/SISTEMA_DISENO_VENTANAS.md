# Sistema Canónico de Diseño y Formato de Ventanas del Ecosistema

**Ecosistema Unificado:** KULA · BALAM & MONITOR DEL MERCADO  
**Hoja Maestra Centralizada:** `ecosystem-theme.css`  
**Helper Global en JavaScript:** `window.EcosystemDesignSystem`

---

## 1. Justificación y Propósito Arquitectónico

Para erradicar la dispersión visual, asimetrías de espaciado o ventanas sin el marco institucional blanco sólido, todo componente visual (pantallas completas, widgets, paneles de gráficos o sub-bloques interactivos) debe regirse por los **Tokens Canónicos** declarados a continuación.

---

## 2. Matriz de Tokens de Diseño (CSS Custom Properties)

| Token CSS | Valor Estándar | Propósito y Aplicación |
| :--- | :--- | :--- |
| `--eco-window-border` | `1.5px solid #ffffff` | **Marco blanco sólido canónico** para ventanas y tarjetas. |
| `--eco-window-border-thick` | `2px solid #ffffff` | Borde blanco reforzado para bloques maestros o de alto impacto. |
| `--eco-window-radius` | `0.875rem` (14px) | Radio de redondeo para esquinas de ventanas principales y gráficos. |
| `--eco-subwindow-radius` | `0.75rem` (12px) | Radio de redondeo para sub-ventanas y tarjetas internas. |
| `--eco-window-padding` | `1.25rem` (20px) | Relleno interior uniforme para tarjetas y ventanas principales. |
| `--eco-subwindow-padding` | `1.125rem` (18px) | Relleno interior para sub-secciones funcionales. |
| `--eco-window-margin-bottom` | `1.125rem` (18px) | Separación vertical simétrica entre ventanas sucesivas. |
| `--eco-window-bg` | `rgba(15, 23, 42, 0.88)` | Fondo oscuro slate de alta legibilidad para sub-bloques. |
| `--eco-window-bg-card` | `rgba(15, 23, 42, 0.70)` | Fondo translúcido con efecto glassmorphism para ventanas. |
| `--eco-window-shadow` | `0 6px 20px rgba(0, 0, 0, 0.4)` | Sombra base con profundidad tridimensional. |
| `--eco-window-hover-shadow` | `0 8px 24px rgba(255, 255, 255, 0.16)` | Sombra y halo de iluminación al posar el cursor (*hover*). |

---

## 3. Clases CSS Canónicas para Maquetación

### A. Ventana Principal o Sector Funcional
Para cualquier ventana principal, tarjeta del dashboard o panel informativo:
```html
<div class="ecosystem-window">
    <div class="ecosystem-window-header flex justify-between items-center mb-3">
        <h3 class="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <span>⚙️</span> Título de la Ventana
        </h3>
        <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-600/70">
            ESTADO
        </span>
    </div>
    <!-- Contenido con padding uniforme garantizado -->
</div>
```

### B. Sub-Ventana o Función Individual (Anidada)
Para sub-bloques que viven dentro de una ventana principal:
```html
<div class="ecosystem-subwindow">
    <label class="block text-xs font-bold text-white mb-1.5">Parámetro / Control:</label>
    <!-- Inputs, botones o selectores -->
</div>
```

### C. Paneles de Gráficos (Tríada de Tres Velas y Gráfico Principal)
Para contenedores de canvas TradingView / LightweightCharts:
```html
<div class="ecosystem-chart-card bg-[#0b0e14] rounded-xl overflow-hidden p-2.5">
    <!-- Header de telemetría y canvas -->
</div>
```

---

## 4. Helper Programático en JavaScript

El script [universal-nav.js](file:///home/raul/Escritorio/proyectos/kula_balam/frontend/js/universal-nav.js) expone la utilidad global `window.EcosystemDesignSystem`:

```javascript
// Obtener tokens en tiempo de ejecución
const tokens = window.EcosystemDesignSystem.tokens;

// Aplicar estilos canónicos a un elemento DOM generado dinámicamente
window.EcosystemDesignSystem.applyWindow(miElementoDiv);
window.EcosystemDesignSystem.applySubwindow(miSubElementoDiv);
window.EcosystemDesignSystem.applyChartCard(miPanelGraficoDiv);
```
