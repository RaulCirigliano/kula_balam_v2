/**
 * UI Components Profesionales para Trading Ollama
 * - CustomSelect: Dropdowns customizados en DOM puro (cero recortes por GTK/SO, con búsqueda integrada).
 * - UIFeedback: Sistema no bloqueante de Notificaciones Toast y Modales interactivos (reemplaza alert/confirm/prompt).
 */

(function (window, document) {
    'use strict';

    // =========================================================================
    // 1. SISTEMA DE TOASTS Y MODALES (UIFeedback)
    // =========================================================================
    const UIFeedback = {
        _toastContainer: null,

        _getToastContainer() {
            if (!this._toastContainer || !document.body.contains(this._toastContainer)) {
                this._toastContainer = document.createElement('div');
                this._toastContainer.id = 'ui-toast-container';
                this._toastContainer.className = 'fixed top-5 right-5 z-[9999] flex flex-col gap-2.5 max-w-sm w-full pointer-events-none';
                document.body.appendChild(this._toastContainer);
            }
            return this._toastContainer;
        },

        toast(message, { type = 'info', duration = 4000, title = null } = {}) {
            const container = this._getToastContainer();
            const toast = document.createElement('div');
            toast.className = `ui-toast ui-toast-${type} pointer-events-auto transform transition-all duration-300 ease-out translate-x-full opacity-0 flex items-start gap-3 p-3.5 rounded-xl border shadow-2xl backdrop-blur-md`;

            // Configuración de colores e iconos por tipo
            const configs = {
                info: {
                    border: 'border-cyan-500/30',
                    bg: 'bg-slate-900/95',
                    icon: 'ℹ️',
                    bar: 'bg-cyan-500',
                    textColor: 'text-cyan-300'
                },
                success: {
                    border: 'border-emerald-500/40',
                    bg: 'bg-slate-900/95',
                    icon: '✅',
                    bar: 'bg-emerald-500',
                    textColor: 'text-emerald-300'
                },
                warning: {
                    border: 'border-amber-500/40',
                    bg: 'bg-slate-900/95',
                    icon: '⚠️',
                    bar: 'bg-amber-500',
                    textColor: 'text-amber-300'
                },
                error: {
                    border: 'border-rose-500/50',
                    bg: 'bg-slate-900/95',
                    icon: '🚨',
                    bar: 'bg-rose-500',
                    textColor: 'text-rose-300'
                }
            };
            const cfg = configs[type] || configs.info;
            toast.classList.add(cfg.border, cfg.bg);

            toast.innerHTML = `
                <div class="text-lg flex-shrink-0 select-none">${cfg.icon}</div>
                <div class="flex-1 min-w-0">
                    ${title ? `<div class="text-xs font-bold ${cfg.textColor} tracking-wide uppercase mb-0.5">${escapeHtml(title)}</div>` : ''}
                    <div class="text-xs text-slate-200 leading-relaxed break-words font-medium">${escapeHtml(message)}</div>
                </div>
                <button type="button" class="text-slate-400 hover:text-white text-base leading-none p-1 flex-shrink-0 cursor-pointer transition-colors" aria-label="Cerrar">×</button>
                <div class="ui-toast-progress absolute bottom-0 left-0 h-0.5 ${cfg.bar} rounded-b-xl transition-all linear" style="width: 100%;"></div>
            `;

            container.appendChild(toast);

            // Animar entrada
            requestAnimationFrame(() => {
                toast.classList.remove('translate-x-full', 'opacity-0');
            });

            const closeBtn = toast.querySelector('button');
            const progressBar = toast.querySelector('.ui-toast-progress');

            let timerId = null;
            let startTime = Date.now();
            let remaining = duration;

            const removeToast = () => {
                if (timerId) clearTimeout(timerId);
                toast.classList.add('translate-x-full', 'opacity-0');
                setTimeout(() => {
                    if (toast.parentElement) toast.parentElement.removeChild(toast);
                }, 300);
            };

            closeBtn.addEventListener('click', removeToast);

            if (duration > 0) {
                progressBar.style.transition = `width ${duration}ms linear`;
                requestAnimationFrame(() => {
                    progressBar.style.width = '0%';
                });

                timerId = setTimeout(removeToast, duration);

                // Pausar al hacer hover
                toast.addEventListener('mouseenter', () => {
                    clearTimeout(timerId);
                    progressBar.style.transition = 'none';
                });
                toast.addEventListener('mouseleave', () => {
                    progressBar.style.transition = `width ${remaining}ms linear`;
                    timerId = setTimeout(removeToast, remaining);
                });
            } else {
                progressBar.style.display = 'none';
            }

            return { close: removeToast };
        },

        // Modal de Alerta estilizado (no bloqueante para el hilo)
        alert(message, { title = 'Aviso del Sistema', icon = 'ℹ️' } = {}) {
            return new Promise((resolve) => {
                const backdrop = document.createElement('div');
                backdrop.className = 'fixed inset-0 z-[10000] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 transition-opacity duration-200 opacity-0';
                backdrop.innerHTML = `
                    <div class="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-md w-full p-6 shadow-2xl transform scale-95 transition-transform duration-200">
                        <div class="flex items-center gap-3 mb-3">
                            <span class="text-2xl">${icon}</span>
                            <h3 class="text-base font-bold text-white tracking-wide">${escapeHtml(title)}</h3>
                        </div>
                        <p class="text-xs text-slate-300 leading-relaxed mb-6 font-medium whitespace-pre-line">${escapeHtml(message)}</p>
                        <div class="flex justify-end">
                            <button type="button" class="btn-confirm px-5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs tracking-wider transition-colors cursor-pointer shadow-lg shadow-cyan-900/30">
                                Entendido
                            </button>
                        </div>
                    </div>
                `;

                document.body.appendChild(backdrop);
                requestAnimationFrame(() => {
                    backdrop.classList.remove('opacity-0');
                    backdrop.querySelector('div').classList.remove('scale-95');
                });

                const close = () => {
                    backdrop.classList.add('opacity-0');
                    backdrop.querySelector('div').classList.add('scale-95');
                    setTimeout(() => {
                        backdrop.remove();
                        resolve();
                    }, 200);
                };

                const btn = backdrop.querySelector('.btn-confirm');
                btn.addEventListener('click', close);
                btn.focus();

                const onKey = (e) => {
                    if (e.key === 'Escape' || e.key === 'Enter') {
                        document.removeEventListener('keydown', onKey);
                        close();
                    }
                };
                document.addEventListener('keydown', onKey);
            });
        },

        // Modal de Confirmación estilizado
        confirm(message, { title = 'Confirmar Acción', icon = '❓', confirmText = 'Aceptar', cancelText = 'Cancelar', isDestructive = false } = {}) {
            return new Promise((resolve) => {
                const backdrop = document.createElement('div');
                backdrop.className = 'fixed inset-0 z-[10000] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 transition-opacity duration-200 opacity-0';
                const confirmBtnClass = isDestructive
                    ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-900/30'
                    : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-cyan-900/30';

                backdrop.innerHTML = `
                    <div class="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-md w-full p-6 shadow-2xl transform scale-95 transition-transform duration-200">
                        <div class="flex items-center gap-3 mb-3">
                            <span class="text-2xl">${icon}</span>
                            <h3 class="text-base font-bold text-white tracking-wide">${escapeHtml(title)}</h3>
                        </div>
                        <p class="text-xs text-slate-300 leading-relaxed mb-6 font-medium whitespace-pre-line">${escapeHtml(message)}</p>
                        <div class="flex justify-end gap-3">
                            <button type="button" class="btn-cancel px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs tracking-wider transition-colors cursor-pointer border border-slate-700">
                                ${escapeHtml(cancelText)}
                            </button>
                            <button type="button" class="btn-confirm px-5 py-2 rounded-lg ${confirmBtnClass} font-bold text-xs tracking-wider transition-colors cursor-pointer shadow-lg">
                                ${escapeHtml(confirmText)}
                            </button>
                        </div>
                    </div>
                `;

                document.body.appendChild(backdrop);
                requestAnimationFrame(() => {
                    backdrop.classList.remove('opacity-0');
                    backdrop.querySelector('div').classList.remove('scale-95');
                });

                const close = (result) => {
                    backdrop.classList.add('opacity-0');
                    backdrop.querySelector('div').classList.add('scale-95');
                    setTimeout(() => {
                        backdrop.remove();
                        resolve(result);
                    }, 200);
                };

                backdrop.querySelector('.btn-cancel').addEventListener('click', () => close(false));
                backdrop.querySelector('.btn-confirm').addEventListener('click', () => close(true));
                backdrop.addEventListener('click', (e) => {
                    if (e.target === backdrop) close(false);
                });

                const onKey = (e) => {
                    if (e.key === 'Escape') {
                        document.removeEventListener('keydown', onKey);
                        close(false);
                    }
                };
                document.addEventListener('keydown', onKey);
            });
        },

        // Modal de Prompt / Entrada de datos estilizado
        prompt(message, defaultValue = '', { title = 'Ingresar Valor', icon = '✏️', confirmText = 'Aceptar', cancelText = 'Cancelar', inputType = 'text', placeholder = '' } = {}) {
            return new Promise((resolve) => {
                const backdrop = document.createElement('div');
                backdrop.className = 'fixed inset-0 z-[10000] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 transition-opacity duration-200 opacity-0';
                backdrop.innerHTML = `
                    <div class="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-md w-full p-6 shadow-2xl transform scale-95 transition-transform duration-200">
                        <div class="flex items-center gap-3 mb-3">
                            <span class="text-2xl">${icon}</span>
                            <h3 class="text-base font-bold text-white tracking-wide">${escapeHtml(title)}</h3>
                        </div>
                        <p class="text-xs text-slate-300 leading-relaxed mb-4 font-medium whitespace-pre-line">${escapeHtml(message)}</p>
                        <div class="mb-5">
                            <input type="${inputType}" class="prompt-input w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-700 text-white text-xs font-mono focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition" value="${escapeHtml(defaultValue)}" placeholder="${escapeHtml(placeholder)}">
                        </div>
                        <div class="flex justify-end gap-3">
                            <button type="button" class="btn-cancel px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs tracking-wider transition-colors cursor-pointer border border-slate-700">
                                ${escapeHtml(cancelText)}
                            </button>
                            <button type="button" class="btn-confirm px-5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs tracking-wider transition-colors cursor-pointer shadow-lg shadow-cyan-900/30">
                                ${escapeHtml(confirmText)}
                            </button>
                        </div>
                    </div>
                `;

                document.body.appendChild(backdrop);
                const input = backdrop.querySelector('.prompt-input');

                requestAnimationFrame(() => {
                    backdrop.classList.remove('opacity-0');
                    backdrop.querySelector('div').classList.remove('scale-95');
                    input.focus();
                    input.select();
                });

                const close = (val) => {
                    backdrop.classList.add('opacity-0');
                    backdrop.querySelector('div').classList.add('scale-95');
                    setTimeout(() => {
                        backdrop.remove();
                        resolve(val);
                    }, 200);
                };

                backdrop.querySelector('.btn-cancel').addEventListener('click', () => close(null));
                backdrop.querySelector('.btn-confirm').addEventListener('click', () => close(input.value));
                backdrop.addEventListener('click', (e) => {
                    if (e.target === backdrop) close(null);
                });

                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        close(input.value);
                    } else if (e.key === 'Escape') {
                        e.preventDefault();
                        close(null);
                    }
                });
            });
        }
    };

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // =========================================================================
    // 2. COMPONENTE DE MENÚ DESPLEGABLE MODERNO (CustomSelect)
    // =========================================================================
    class CustomSelect {
        constructor(selectElement, options = {}) {
            if (!selectElement || selectElement._customSelectInstance) return;
            this.nativeSelect = selectElement;
            this.nativeSelect._customSelectInstance = this;
            this.options = Object.assign({
                searchable: selectElement.options.length > 7 || selectElement.id === 'symbolSelect',
                searchPlaceholder: 'Buscar opción...',
                maxHeight: '340px',
                compact: false
            }, options);

            this.isOpen = false;
            this.wrapper = null;
            this.trigger = null;
            this.dropdown = null;
            this.searchInput = null;
            this.optionsContainer = null;
            this.activeIndex = -1;

            this._init();
        }

        _init() {
            // Ocultar select nativo pero mantenerlo accesible para formularios y lectores
            this.nativeSelect.style.position = 'absolute';
            this.nativeSelect.style.opacity = '0';
            this.nativeSelect.style.pointerEvents = 'none';
            this.nativeSelect.style.height = '0';
            this.nativeSelect.style.width = '0';
            this.nativeSelect.style.overflow = 'hidden';
            this.nativeSelect.setAttribute('tabindex', '-1');

            // Interceptar setter de .value para sincronizar cuando Python/JS modifique el valor programáticamente
            try {
                const proto = HTMLSelectElement.prototype;
                const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                if (descriptor && descriptor.set) {
                    const self = this;
                    Object.defineProperty(this.nativeSelect, 'value', {
                        get() {
                            return descriptor.get.call(self.nativeSelect);
                        },
                        set(val) {
                            descriptor.set.call(self.nativeSelect, val);
                            self.syncFromNative();
                        },
                        configurable: true
                    });
                }
            } catch (_) {}

            const isCompact = this.options.compact;

            // Crear contenedor del componente
            this.wrapper = document.createElement('div');
            this.wrapper.className = `custom-select-wrapper relative inline-block ${isCompact ? 'w-auto min-w-[130px]' : 'w-full'}`;
            this.wrapper.setAttribute('data-target-id', this.nativeSelect.id || '');

            // Botón disparador (Trigger)
            this.trigger = document.createElement('button');
            this.trigger.type = 'button';
            const triggerHeight = isCompact ? 'h-[32px] px-2.5 py-1 text-xs' : 'h-[38px] px-3.5 py-1.5 text-xs';
            this.trigger.className = `custom-select-trigger flex items-center justify-between w-full ${triggerHeight} rounded-lg bg-[#0f172a] border border-slate-700 hover:border-slate-500 text-slate-100 font-semibold tracking-wide transition-all duration-150 cursor-pointer shadow-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/50`;
            this.trigger.setAttribute('aria-haspopup', 'listbox');
            this.trigger.setAttribute('aria-expanded', 'false');

            this.triggerLabel = document.createElement('span');
            this.triggerLabel.className = 'custom-select-label truncate flex items-center gap-2';

            const arrow = document.createElement('span');
            arrow.className = 'custom-select-arrow ml-2 text-slate-400 transition-transform duration-200 text-[10px] flex-shrink-0';
            arrow.innerHTML = '▼';

            this.trigger.appendChild(this.triggerLabel);
            this.trigger.appendChild(arrow);

            // Menú desplegable (Dropdown flotante)
            this.dropdown = document.createElement('div');
            this.dropdown.className = 'custom-select-dropdown hidden absolute left-0 z-[9999] mt-1.5 rounded-xl bg-[#0b1322] border border-slate-700/80 shadow-2xl backdrop-blur-xl overflow-hidden flex flex-col transition-all duration-150 transform scale-95 opacity-0';
            this.dropdown.style.minWidth = '100%';
            this.dropdown.style.maxWidth = 'min(420px, 95vw)';
            this.dropdown.style.width = 'max-content';

            // Buscador integrado (si aplica)
            if (this.options.searchable) {
                const searchWrap = document.createElement('div');
                searchWrap.className = 'p-2 border-b border-slate-800 bg-[#080d18] sticky top-0 z-10';
                this.searchInput = document.createElement('input');
                this.searchInput.type = 'text';
                this.searchInput.className = 'w-full px-2.5 py-1.5 rounded-md bg-slate-900 border border-slate-700 text-slate-100 placeholder-slate-500 text-xs outline-none focus:border-cyan-500 transition-colors font-sans';
                this.searchInput.placeholder = this.options.searchPlaceholder;
                searchWrap.appendChild(this.searchInput);
                this.dropdown.appendChild(searchWrap);

                this.searchInput.addEventListener('input', () => this._filterOptions(this.searchInput.value));
                this.searchInput.addEventListener('keydown', (e) => this._handleKeydown(e));
            }

            // Contenedor de opciones con scroll
            this.optionsContainer = document.createElement('div');
            this.optionsContainer.className = 'custom-select-options overflow-y-auto p-1.5 flex flex-col gap-0.5 custom-scrollbar';
            this.optionsContainer.style.maxHeight = this.options.maxHeight;
            this.dropdown.appendChild(this.optionsContainer);

            // Construir árbol de opciones
            this.renderOptions();

            // Insertar en el DOM
            this.nativeSelect.parentNode.insertBefore(this.wrapper, this.nativeSelect);
            this.wrapper.appendChild(this.nativeSelect);
            this.wrapper.appendChild(this.trigger);
            this.wrapper.appendChild(this.dropdown);

            // Escuchadores de eventos
            this.trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggle();
            });

            this.trigger.addEventListener('keydown', (e) => this._handleKeydown(e));

            // Sincronización cuando el valor del select nativo cambie por script o evento
            this.nativeSelect.addEventListener('change', () => this.syncFromNative());

            // Observador de mutaciones para re-renderizar si las opciones cambian dinámicamente
            this.observer = new MutationObserver(() => {
                this.renderOptions();
                this.syncFromNative();
            });
            this.observer.observe(this.nativeSelect, { childList: true, subtree: true, attributes: true });

            // Inicializar valor visible
            this.syncFromNative();
        }

        renderOptions() {
            this.optionsContainer.innerHTML = '';
            const children = Array.from(this.nativeSelect.children);

            if (children.length === 0) {
                const empty = document.createElement('div');
                empty.className = 'px-3 py-2 text-xs text-slate-500 italic text-center';
                empty.textContent = 'Sin opciones disponibles';
                this.optionsContainer.appendChild(empty);
                return;
            }

            children.forEach(child => {
                if (child.tagName === 'OPTGROUP') {
                    const groupTitle = document.createElement('div');
                    groupTitle.className = 'px-3 pt-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 select-none flex items-center gap-1.5';
                    groupTitle.textContent = child.label;
                    this.optionsContainer.appendChild(groupTitle);

                    Array.from(child.children).forEach(option => {
                        this._createOptionItem(option, true);
                    });
                } else if (child.tagName === 'OPTION') {
                    this._createOptionItem(child, false);
                }
            });
        }

        _createOptionItem(option, isChildOfGroup = false) {
            const item = document.createElement('div');
            item.className = `custom-select-option px-3 py-2 rounded-lg text-xs font-medium cursor-pointer transition-colors flex items-center justify-between gap-2 select-none ${
                isChildOfGroup ? 'pl-4' : ''
            }`;
            item.setAttribute('data-value', option.value);

            const isSelected = option.selected;
            if (isSelected) {
                item.classList.add('bg-cyan-500/15', 'text-cyan-300', 'font-semibold');
            } else {
                item.classList.add('text-slate-200', 'hover:bg-slate-800/80', 'hover:text-white');
            }

            item.innerHTML = `
                <span class="truncate">${option.textContent}</span>
                ${isSelected ? '<span class="text-cyan-400 text-xs flex-shrink-0">✓</span>' : ''}
            `;

            item.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectValue(option.value);
            });

            this.optionsContainer.appendChild(item);
        }

        _filterOptions(query) {
            const cleanQuery = query.toLowerCase().trim();
            const items = this.optionsContainer.querySelectorAll('.custom-select-option');
            let anyVisible = false;

            items.forEach(item => {
                const text = item.textContent.toLowerCase();
                const val = (item.getAttribute('data-value') || '').toLowerCase();
                const matches = text.includes(cleanQuery) || val.includes(cleanQuery);
                item.style.display = matches ? 'flex' : 'none';
                if (matches) anyVisible = true;
            });

            // Ocultar títulos de optgroups que no tengan hijos visibles
            const groups = this.optionsContainer.querySelectorAll('div:not(.custom-select-option)');
            groups.forEach(g => {
                let next = g.nextElementSibling;
                let hasVisible = false;
                while (next && next.classList.contains('custom-select-option')) {
                    if (next.style.display !== 'none') hasVisible = true;
                    next = next.nextElementSibling;
                }
                g.style.display = hasVisible ? 'block' : 'none';
            });
        }

        syncFromNative() {
            const selectedOpt = this.nativeSelect.selectedOptions[0] || this.nativeSelect.options[0];
            if (selectedOpt) {
                this.triggerLabel.textContent = selectedOpt.textContent;
            } else {
                this.triggerLabel.textContent = 'Seleccionar...';
            }

            // Actualizar estilo en la lista
            const currentVal = this.nativeSelect.value;
            const items = this.optionsContainer.querySelectorAll('.custom-select-option');
            items.forEach(item => {
                const val = item.getAttribute('data-value');
                if (val === currentVal) {
                    item.className = 'custom-select-option px-3 py-2 rounded-lg text-xs font-semibold cursor-pointer transition-colors flex items-center justify-between gap-2 select-none bg-cyan-500/15 text-cyan-300';
                    item.innerHTML = `<span class="truncate">${item.querySelector('span').textContent}</span><span class="text-cyan-400 text-xs flex-shrink-0">✓</span>`;
                } else {
                    item.className = 'custom-select-option px-3 py-2 rounded-lg text-xs font-medium cursor-pointer transition-colors flex items-center justify-between gap-2 select-none text-slate-200 hover:bg-slate-800/80 hover:text-white';
                    item.innerHTML = `<span class="truncate">${item.querySelector('span').textContent}</span>`;
                }
            });
        }

        selectValue(value) {
            if (this.nativeSelect.value !== value) {
                this.nativeSelect.value = value;
                this.nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));
                this.nativeSelect.dispatchEvent(new Event('input', { bubbles: true }));
                if (typeof this.nativeSelect.onchange === 'function') {
                    try { this.nativeSelect.onchange.call(this.nativeSelect, new Event('change')); } catch (e) { console.error(e); }
                }
            }
            this.syncFromNative();
            this.close();
            this.trigger.focus();
        }

        open() {
            // Cerrar cualquier otro dropdown abierto en la página
            document.querySelectorAll('.custom-select-dropdown').forEach(d => {
                if (d !== this.dropdown) {
                    d.classList.add('hidden', 'scale-95', 'opacity-0');
                    d.classList.remove('scale-100', 'opacity-100');
                    const trig = d.parentElement?.querySelector('.custom-select-trigger');
                    if (trig) trig.setAttribute('aria-expanded', 'false');
                }
            });

            this.isOpen = true;
            this.dropdown.classList.remove('hidden');
            this.trigger.setAttribute('aria-expanded', 'true');
            const arrow = this.trigger.querySelector('.custom-select-arrow');
            if (arrow) arrow.style.transform = 'rotate(180deg)';

            requestAnimationFrame(() => {
                this.dropdown.classList.remove('scale-95', 'opacity-0');
                this.dropdown.classList.add('scale-100', 'opacity-100');
            });

            if (this.searchInput) {
                this.searchInput.value = '';
                this._filterOptions('');
                setTimeout(() => this.searchInput.focus(), 50);
            }

            // Scroll a la opción activa
            const active = this.optionsContainer.querySelector('.bg-cyan-500\\/15');
            if (active) {
                active.scrollIntoView({ block: 'nearest' });
            }
        }

        close() {
            if (!this.isOpen) return;
            this.isOpen = false;
            this.trigger.setAttribute('aria-expanded', 'false');
            const arrow = this.trigger.querySelector('.custom-select-arrow');
            if (arrow) arrow.style.transform = 'rotate(0deg)';

            this.dropdown.classList.add('scale-95', 'opacity-0');
            this.dropdown.classList.remove('scale-100', 'opacity-100');

            setTimeout(() => {
                if (!this.isOpen) this.dropdown.classList.add('hidden');
            }, 150);
        }

        toggle() {
            if (this.isOpen) this.close();
            else this.open();
        }

        _handleKeydown(e) {
            if (e.key === 'Escape') {
                this.close();
                this.trigger.focus();
                return;
            }

            if (!this.isOpen && (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ')) {
                e.preventDefault();
                this.open();
                return;
            }

            if (this.isOpen) {
                const visibleItems = Array.from(this.optionsContainer.querySelectorAll('.custom-select-option'))
                    .filter(item => item.style.display !== 'none');
                if (visibleItems.length === 0) return;

                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    this.activeIndex = (this.activeIndex + 1) % visibleItems.length;
                    this._highlightItem(visibleItems[this.activeIndex]);
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    this.activeIndex = (this.activeIndex - 1 + visibleItems.length) % visibleItems.length;
                    this._highlightItem(visibleItems[this.activeIndex]);
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    if (this.activeIndex >= 0 && this.activeIndex < visibleItems.length) {
                        const val = visibleItems[this.activeIndex].getAttribute('data-value');
                        this.selectValue(val);
                    }
                }
            }
        }

        _highlightItem(item) {
            this.optionsContainer.querySelectorAll('.custom-select-option').forEach(el => el.classList.remove('ring-1', 'ring-cyan-500'));
            if (item) {
                item.classList.add('ring-1', 'ring-cyan-500');
                item.scrollIntoView({ block: 'nearest' });
            }
        }
    }

    // Cerrar dropdowns al hacer clic fuera
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-select-wrapper')) {
            document.querySelectorAll('.custom-select-dropdown').forEach(d => {
                d.classList.add('hidden', 'scale-95', 'opacity-0');
                d.classList.remove('scale-100', 'opacity-100');
                const trig = d.parentElement?.querySelector('.custom-select-trigger');
                if (trig) {
                    trig.setAttribute('aria-expanded', 'false');
                    const arrow = trig.querySelector('.custom-select-arrow');
                    if (arrow) arrow.style.transform = 'rotate(0deg)';
                }
            });
        }
    });

    // =========================================================================
    // 3. PAGE VISIBILITY API (Gestor inteligente de recursos en segundo plano)
    // =========================================================================
    const PageVisibility = {
        isTabActive: !document.hidden,
        _listeners: [],

        onChange(callback) {
            if (typeof callback === 'function') {
                this._listeners.push(callback);
            }
        },

        _init() {
            document.addEventListener('visibilitychange', () => {
                this.isTabActive = !document.hidden;
                this._listeners.forEach(fn => {
                    try { fn(this.isTabActive); } catch (e) { console.error('Error en listener de visibilidad:', e); }
                });
            });
        }
    };
    PageVisibility._init();

    // Exportar al ámbito global de la ventana
    window.UIFeedback = UIFeedback;
    window.CustomSelect = CustomSelect;
    window.PageVisibility = PageVisibility;

    // Inicializador universal y exhaustivo para TODOS los selectores del dashboard
    window.initTradingCustomSelects = function () {
        const selects = document.querySelectorAll('select');
        selects.forEach(el => {
            if (el && !el._customSelectInstance && !el.classList.contains('no-custom-select')) {
                const isNav = el.id === 'navAgentModeSelect' || Boolean(el.closest('nav'));
                const isSmall = isNav || el.id === 'investmentSourceSelect';
                new CustomSelect(el, {
                    searchable: el.id === 'symbolSelect' || el.options.length > 7,
                    searchPlaceholder: el.id === 'symbolSelect' ? '🔍 Buscar activo por ticker o nombre...' : '🔍 Buscar...',
                    maxHeight: '360px',
                    compact: Boolean(isSmall)
                });
            }
        });
    };

    // Auto-observador del DOM: si se inyectan nuevos selects o modales dinámicamente, convertirlos al instante
    const domObserver = new MutationObserver(() => {
        window.initTradingCustomSelects();
    });
    if (document.body) {
        domObserver.observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            domObserver.observe(document.body, { childList: true, subtree: true });
        });
    }

})(window, document);
