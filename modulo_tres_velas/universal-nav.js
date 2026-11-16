/**
 * KULA · BALAM — UNIVERSAL ECOSYSTEM NAVIGATION (MINIMALISTA)
 * Menú desplegable compacto estilo TradingView Pro para las 6 terminales.
 * Vanilla JS puro (cero dependencias).
 */

(function () {
  'use strict';

  function initUniversalEcosystemNav() {
    const hostname = window.location.hostname || '127.0.0.1';
    const currentPort = window.location.port || '';
    const currentPath = window.location.pathname || '';

    const PORT_KULA = '18087';
    const PORT_MONITOR = '8520';

    const isKulaHost = currentPort === PORT_KULA;
    const isMonitorHost = currentPort === PORT_MONITOR;

    const urls = {
      cockpit: isKulaHost ? '/index.html' : `http://${hostname}:${PORT_KULA}/index.html`,
      tresVelas: isKulaHost ? '/terminal_tres_velas.html' : `http://${hostname}:${PORT_KULA}/terminal_tres_velas.html`,
      monitor: isMonitorHost ? '/index.html' : `http://${hostname}:${PORT_MONITOR}/index.html`,
      cioVelas: isMonitorHost ? '/terminal_velas_cio.html' : (isKulaHost ? '/terminal_velas_cio.html' : `http://${hostname}:${PORT_MONITOR}/terminal_velas_cio.html`),
      estudioVelas: isMonitorHost ? '/velas_japonesas.html' : (isKulaHost ? '/velas_japonesas.html' : `http://${hostname}:${PORT_MONITOR}/velas_japonesas.html`),
      auditor: isKulaHost ? '/auditor_visual.html' : `http://${hostname}:${PORT_KULA}/auditor_visual.html`
    };

    function getActiveKey() {
      if (currentPath.includes('terminal_tres_velas') || currentPath.includes('modulo_tres_velas')) return 'tresVelas';
      if (currentPath.includes('terminal_velas_cio')) return 'cioVelas';
      if (currentPath.includes('velas_japonesas')) return 'estudioVelas';
      if (currentPath.includes('auditor_visual')) return 'auditor';
      if (isMonitorHost && (currentPath === '/' || currentPath.endsWith('index.html'))) return 'monitor';
      if (isKulaHost && (currentPath === '/' || currentPath.endsWith('index.html'))) return 'cockpit';
      return '';
    }

    const activeKey = getActiveKey();

    // Catálogo exacto de las 6 páginas respetando títulos y pestañas
    const items = [
      {
        key: 'cockpit',
        icon: '📈',
        name: 'Kula Balam',
        subtitle: 'Dashboard Cuantitativo',
        badge: ':18087',
        url: urls.cockpit
      },
      {
        key: 'tresVelas',
        icon: '🕯️',
        name: 'La Tríada Multitemporal',
        subtitle: 'Kula Balam: Los tres tiempos y el tigre agazapado',
        badge: 'Tríada',
        url: urls.tresVelas
      },
      {
        key: 'monitor',
        icon: '🖥️',
        name: 'Monitor del Mercado',
        subtitle: 'Balam recorre los mercados en busca de su presa',
        badge: ':8520',
        url: urls.monitor
      },
      {
        key: 'cioVelas',
        icon: '⚡',
        name: 'Terminal del CIO',
        subtitle: 'Balam, auditor cuantitativo de las tres velas',
        badge: 'CIO',
        url: urls.cioVelas
      },
      {
        key: 'estudioVelas',
        icon: '📊',
        name: 'Atlas Cuantitativo de Velas Japonesas',
        subtitle: 'Estudio de Velas',
        badge: 'Atlas',
        url: urls.estudioVelas
      },
      {
        key: 'auditor',
        icon: '🏛️',
        name: 'Auditor Visual de Bóveda',
        subtitle: 'Ledger SQLite',
        badge: 'SQLite',
        url: urls.auditor
      }
    ];

    function renderMenuItems() {
      return items.map(item => {
        const isActive = activeKey === item.key;
        return `
          <a href="${item.url}" target="${isActive ? '_self' : '_blank'}"
             class="flex items-center justify-between px-2 py-1.5 rounded transition text-xs select-none ${
               isActive
                 ? 'bg-indigo-600/25 text-white font-bold border border-indigo-500/40'
                 : 'text-slate-300 hover:text-white hover:bg-slate-800/80 border border-transparent'
             }">
            <div class="flex items-center gap-2 min-w-0">
              <span class="text-sm shrink-0">${item.icon}</span>
              <div class="truncate">
                <span class="${isActive ? 'text-indigo-300' : 'text-slate-200'} font-semibold">${item.name}</span>
                <span class="text-[10px] text-slate-500 ml-1">(${item.subtitle})</span>
              </div>
            </div>
            <span class="text-[9.5px] font-mono shrink-0 ml-2 px-1.5 py-0.2 rounded ${
              isActive
                ? 'bg-indigo-500/30 text-indigo-200 font-bold'
                : 'bg-slate-800 text-slate-400'
            }">${isActive ? 'Activo' : item.badge}</span>
          </a>
        `;
      }).join('');
    }

    // Si existe el contenedor universal (#navEcosystemContainer)
    const container = document.getElementById('navEcosystemContainer');
    if (container && !document.getElementById('navEcosystemDropdownWrapper')) {
      container.innerHTML = `
        <div class="relative inline-block text-left" id="navEcosystemDropdownWrapper">
          <button id="navEcosystemBtn" type="button"
                  class="px-2.5 py-1 text-xs font-semibold rounded-md bg-slate-800/90 hover:bg-slate-700 text-slate-200 hover:text-white border border-slate-700/80 transition flex items-center gap-1.5 cursor-pointer shadow-sm select-none"
                  title="Terminales y Páginas del Proyecto (Clic para fijar)">
            <span>🗂️</span>
            <span>Terminales & Páginas</span>
            <span class="text-[9px] text-slate-400 transition-transform duration-200" id="navEcosystemArrow">▼</span>
          </button>

          <div id="navEcosystemMenu"
               class="hidden absolute left-0 top-full pt-1 w-80 z-[1000]">
            <div class="bg-[#0b0f19] border border-slate-800 rounded-lg shadow-2xl p-1.5 space-y-0.5 text-left backdrop-blur-md">
              <div class="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800/80 mb-1 flex justify-between items-center">
                <span>Ecosistema Kula Balam</span>
                <span class="font-mono text-slate-400 text-[9px]">6 Vistas</span>
              </div>
              <div class="space-y-0.5">
                ${renderMenuItems()}
              </div>
            </div>
          </div>
        </div>
      `;
    } else {
      // Si ya existía el menú nativo en Kula Balam Cockpit (#navEcosystemMenu), reemplazar su contenido por el minimalista
      const existingMenu = document.getElementById('navEcosystemMenu');
      if (existingMenu) {
        existingMenu.className = 'hidden absolute left-0 top-full pt-1 w-80 z-[1000]';
        existingMenu.innerHTML = `
          <div class="bg-[#0b0f19] border border-slate-800 rounded-lg shadow-2xl p-1.5 space-y-0.5 text-left backdrop-blur-md">
            <div class="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800/80 mb-1 flex justify-between items-center">
              <span>Ecosistema Kula Balam</span>
              <span class="font-mono text-slate-400 text-[9px]">6 Vistas</span>
            </div>
            <div class="space-y-0.5">
              ${renderMenuItems()}
            </div>
          </div>
        `;
      }
    }

    // Controlador Interactivo
    const btn = document.getElementById('navEcosystemBtn');
    const menu = document.getElementById('navEcosystemMenu');
    const arrow = document.getElementById('navEcosystemArrow');
    const wrapper = document.getElementById('navEcosystemDropdownWrapper');

    if (!btn || !menu || !wrapper) return;

    let isOpen = false;
    let isPinnedByClick = false;
    let closeTimer = null;

    function openMenu() {
      if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
      }
      isOpen = true;
      menu.classList.remove('hidden');
      if (arrow) arrow.style.transform = 'rotate(180deg)';
    }

    function closeMenu(force = false) {
      if (isPinnedByClick && !force) return;
      if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
      }
      isOpen = false;
      isPinnedByClick = false;
      menu.classList.add('hidden');
      if (arrow) arrow.style.transform = 'rotate(0deg)';
    }

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (isOpen && isPinnedByClick) {
        closeMenu(true);
      } else {
        isPinnedByClick = true;
        openMenu();
      }
    });

    wrapper.addEventListener('mouseenter', () => {
      if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
      }
      openMenu();
    });

    wrapper.addEventListener('mouseleave', () => {
      if (isPinnedByClick) return;
      closeTimer = setTimeout(() => {
        closeMenu(false);
      }, 350);
    });

    menu.addEventListener('click', (e) => {
      if (e.target.closest('a')) {
        closeMenu(true);
      }
    });

    document.addEventListener('click', (e) => {
      if (!wrapper.contains(e.target)) {
        closeMenu(true);
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && isOpen) {
        closeMenu(true);
      }
    });
  }

  /**
   * PROTOCOLO UNIVERSAL DE AUTO-ENVOLTURA Y ELEVACIÓN DE DESPLEGABLES
   * 1. Si un control, título, casilla de verificación o badge no cabe, salta de fila (no se corta).
   * 2. Ningún desplegable (<select> o menú flotante) queda tapado o cortado por ventanas inferiores.
   */
  function initUniversalDropdownAndWrapWatcher() {
    // Elevador Dinámico Universal de Stacking Context para Selectores y Menús
    document.addEventListener('focusin', function (e) {
      if (e.target && e.target.matches && e.target.matches('select, [data-dropdown], .dropdown-trigger')) {
        let parentCard = e.target.closest('.bg-gray-800, .bg-gray-900, .bg-slate-900, .bg-slate-950, section, .card, .panel, [class*="rounded"]');
        if (parentCard && !parentCard.id.includes('chart-container')) {
          parentCard.dataset.prevZIndex = parentCard.style.zIndex || '';
          parentCard.dataset.prevOverflow = parentCard.style.overflow || '';
          parentCard.style.zIndex = '99999';
          if (parentCard.style.overflow === 'hidden' && !parentCard.id.includes('canvas')) {
            parentCard.style.overflow = 'visible';
          }
        }
      }
    }, true);

    document.addEventListener('focusout', function (e) {
      if (e.target && e.target.matches && e.target.matches('select, [data-dropdown], .dropdown-trigger')) {
        let parentCard = e.target.closest('.bg-gray-800, .bg-gray-900, .bg-slate-900, .bg-slate-950, section, .card, .panel, [class*="rounded"]');
        if (parentCard && !parentCard.id.includes('chart-container')) {
          parentCard.style.zIndex = parentCard.dataset.prevZIndex || '';
          if (parentCard.dataset.prevOverflow !== undefined) {
            parentCard.style.overflow = parentCard.dataset.prevOverflow;
          }
        }
      }
    }, true);

    // Desbloqueo de flex-wrap en barras de controles para prevenir corte u ocultamiento
    function ensureHeadersWrap() {
      const bars = document.querySelectorAll('.chart-header-row, #kula-chart-header, #chart-legend, .legend-overlay');
      bars.forEach(bar => {
        if (bar.style.flexWrap === 'nowrap') {
          bar.style.flexWrap = 'wrap';
        }
        if (bar.style.maxHeight && bar.style.maxHeight !== 'none') {
          bar.style.maxHeight = 'none';
        }
        if (bar.style.overflow === 'hidden' && !bar.id.includes('canvas') && !bar.id.includes('chart-container')) {
          bar.style.overflow = 'visible';
        }
      });
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', ensureHeadersWrap);
    } else {
      ensureHeadersWrap();
    }
    window.addEventListener('resize', ensureHeadersWrap);
  }

  /**
   * REFERENCIA Y MOTOR DE DISEÑO CANÓNICO DE VENTANAS (ECOSYSTEM DESIGN SYSTEM)
   * Proporciona acceso programático y automático a las métricas del sistema:
   * - Borde: Marco blanco sólido (1.5px solid #ffffff)
   * - Border radius: 14px (0.875rem)
   * - Padding: 20px (1.25rem)
   * - Margin-bottom: 18px (1.125rem)
   * - Sombra: 0 6px 20px rgba(0, 0, 0, 0.4)
   */
  window.EcosystemDesignSystem = {
    tokens: {
      border: '1.5px solid #ffffff',
      borderThick: '2px solid #ffffff',
      borderRadius: '0.875rem',
      subRadius: '0.75rem',
      padding: '1.25rem',
      subPadding: '1.125rem',
      marginBottom: '1.125rem',
      shadow: '0 6px 20px rgba(0, 0, 0, 0.4)',
      hoverShadow: '0 8px 24px rgba(255, 255, 255, 0.16)',
      bgWindow: 'rgba(15, 23, 42, 0.70)',
      bgSubwindow: 'rgba(15, 23, 42, 0.88)'
    },
    applyWindow(el) {
      if (!el) return;
      el.classList.add('ecosystem-window');
    },
    applySubwindow(el) {
      if (!el) return;
      el.classList.add('ecosystem-subwindow');
    },
    applyChartCard(el) {
      if (!el) return;
      el.classList.add('ecosystem-chart-card');
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initUniversalEcosystemNav();
      initUniversalDropdownAndWrapWatcher();
    });
  } else {
    initUniversalEcosystemNav();
    initUniversalDropdownAndWrapWatcher();
  }
})();
