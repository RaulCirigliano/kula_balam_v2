const API_BASE_URL = (window.location.protocol && window.location.hostname)
    ? `${window.location.protocol}//${window.location.hostname}:18767`
    : 'http://127.0.0.1:18767';
const tradingGuards = window.TradingGuards;

function apiAuthHeaders(headers = {}) {
    const token = sessionStorage.getItem('ai_app_token');
    return token ? { ...headers, 'X-API-Token': token } : headers;
}

function parseBrainSelection(value) {
    if (value === 'antigravity_operador') {
        return { engine: 'antigravity_operador', model: 'antigravity_operador' };
    }
    if (value === 'ollama|trader-qwen' || value === 'qwen' || (typeof value === 'string' && value.startsWith('ollama|'))) {
        return { engine: 'ollama', model: 'trader-qwen' };
    }
    if (value === 'ai' || value === 'gemini') {
        return { engine: 'gemini', model: null };
    }
    if (value === 'antigravity_cio') {
        return { engine: 'antigravity_cio', model: 'antigravity_cio' };
    }
    return { engine: 'local', model: null };
}

function brainSelectionValue(brain) {
    if (brain?.engine === 'antigravity_operador') return 'antigravity_operador';
    if (brain?.engine === 'ollama') return 'ollama|trader-qwen';
    if (brain?.engine === 'gemini' || brain?.engine === 'ai') return 'ai';
    if (brain?.engine === 'antigravity_cio') return 'antigravity_cio';
    return 'local';
}

window.updateSystemActiveEngineBadges = function(engineKey) {
    const select = document.getElementById('engineSelect');
    const val = (engineKey || select?.value || 'antigravity_operador').toLowerCase();

    let engineName = '⚡ Antigravity Operador';
    let engineBadgeText = 'WORKER: ⚡ ANTIGRAVITY (PRIORIDAD 1)';
    let engineBadgeClass = 'text-[9px] bg-amber-950 text-amber-300 border border-amber-600/60 px-2 py-0.5 rounded font-mono font-bold';
    let decidingEngineText = '⚡ Antigravity Operador (Coprocesador IA Supervisado)';

    if (val === 'antigravity_cio') {
        engineName = '🛰️ Antigravity CIO';
        engineBadgeText = 'WORKER: 🛰️ ANTIGRAVITY CIO (MONITOR)';
        engineBadgeClass = 'text-[9px] bg-cyan-950 text-cyan-300 border border-cyan-500/60 px-2 py-0.5 rounded font-mono font-bold';
        decidingEngineText = '🛰️ Antigravity CIO (Sondeo Macro / Monitor)';
    } else if (val === 'ai' || val === 'gemini') {
        engineName = '✨ Google Gemini';
        engineBadgeText = 'WORKER: ✨ GOOGLE GEMINI (PRIORIDAD 2)';
        engineBadgeClass = 'text-[9px] bg-blue-950 text-blue-300 border border-blue-500/60 px-2 py-0.5 rounded font-mono font-bold';
        decidingEngineText = '✨ Google Gemini (Coprocesador IA Nube)';
    } else if (val === 'ollama|trader-qwen' || val === 'qwen' || val.includes('qwen') || val.startsWith('ollama|')) {
        engineName = '🤖 Qwen 2.5 (trader-qwen)';
        engineBadgeText = 'WORKER: 🤖 QWEN 2.5 (PRIORIDAD 3)';
        engineBadgeClass = 'text-[9px] bg-emerald-950 text-emerald-300 border border-emerald-500/60 px-2 py-0.5 rounded font-mono font-bold';
        decidingEngineText = '🤖 Qwen 2.5 (Coprocesador Ollama Local)';
    } else if (val === 'local' || val === 'matematico') {
        engineName = '⚙️ Modelo Matemático Determinista';
        engineBadgeText = 'WORKER: ⚙️ MATEMÁTICO DETERMINISTA (PRIORIDAD 4)';
        engineBadgeClass = 'text-[9px] bg-gray-800 text-gray-300 border border-gray-600 px-2 py-0.5 rounded font-mono font-bold';
        decidingEngineText = '⚙️ Modelo Matemático Determinista (Cálculo Python)';
    }

    // 1. Kula Cerebro Header Badge
    const kulaBadgeEl = document.getElementById('kulaCerebroLiveEngineBadge');
    if (kulaBadgeEl) {
        kulaBadgeEl.innerText = engineBadgeText;
        kulaBadgeEl.className = engineBadgeClass;
    }

    // 2. Balam CIO Header Badge
    const balamBadgeEl = document.getElementById('balamCioLiveEngineBadge');
    if (balamBadgeEl) {
        balamBadgeEl.innerText = engineBadgeText;
        balamBadgeEl.className = engineBadgeClass;
    }

    // 3. Radar en Vivo Header
    const radarBadgeEl = document.getElementById('radarLiveLiveEngineBadge');
    if (radarBadgeEl) {
        radarBadgeEl.innerText = engineBadgeText;
        radarBadgeEl.className = engineBadgeClass;
    }

    // 4. Radar Macro Header
    const radarMacroBadgeEl = document.getElementById('radarMacroLiveEngineBadge');
    if (radarMacroBadgeEl) {
        radarMacroBadgeEl.innerText = engineBadgeText;
        radarMacroBadgeEl.className = engineBadgeClass;
    }

    // 5. Strategy Executing Engine Label
    const executingEngineEl = document.getElementById('strategyExecutingEngineLabel');
    if (executingEngineEl) {
        executingEngineEl.innerText = decidingEngineText;
    }

    // 6. Strategy Selected Formula Label
    const mode = typeof getStrategyMode === 'function' ? getStrategyMode() : 'donchian_breakout_1h';
    const info = (typeof STRATEGY_EXPLANATIONS !== 'undefined' && STRATEGY_EXPLANATIONS[mode]) ? STRATEGY_EXPLANATIONS[mode] : null;
    const formulaLabelEl = document.getElementById('strategySelectedFormulaLabel');
    if (formulaLabelEl) {
        formulaLabelEl.innerText = info ? info.title : '🛡️ Donchian Breakout 1H';
    }
};

function setBrainSelectorsValue(value) {
    const select = document.getElementById('engineSelect');
    if (select) {
        if (value === 'antigravity_operador') {
            select.value = 'antigravity_operador';
        } else if (value === 'ollama|trader-qwen' || value === 'qwen' || (typeof value === 'string' && value.startsWith('ollama|'))) {
            select.value = 'ollama|trader-qwen';
        } else if (value === 'ai' || value === 'gemini') {
            select.value = 'ai';
        } else if (value === 'antigravity_cio') {
            select.value = 'antigravity_cio';
        } else {
            select.value = 'local';
        }
    }
    if (window.updateSystemActiveEngineBadges) {
        window.updateSystemActiveEngineBadges(select ? select.value : value);
    }
}

function updateAutoEngineLabel(isAuto) {
    const lbl = document.getElementById('lblAutoEngineStatus');
    if (!lbl) return;
    if (isAuto) {
        lbl.className = 'text-[10px] font-mono font-bold text-purple-300';
        lbl.innerText = '🔄 Cascada Auto (1->2->3->4)';
    } else {
        lbl.className = 'text-[10px] font-mono font-bold text-amber-300';
        lbl.innerText = '🔒 Manual Fijo (Sin Auto-Cambio)';
    }
}
window.updateAutoEngineLabel = updateAutoEngineLabel;

async function refreshBrainModelOptions() {
    const select = document.getElementById('engineSelect');
    if (!select) return;

    select.replaceChildren();
    // Cascada 1-2-3-4 de Coprocesadores de Cómputo (Workers): 1. Antigravity -> 2. Google Gemini -> 3. Qwen 2.5 -> 4. Modelo Matemático Local
    const autoGroup = document.createElement('optgroup');
    autoGroup.label = '⚡ Motor Supervisado Principal';
    const operadorOption = new Option('⚡ Antigravity Operador (Coprocesador IA Supervisado · Prioridad 1)', 'antigravity_operador');
    const cioOption = new Option('🛰️ Antigravity CIO (Sondeo Macro / Monitor)', 'antigravity_cio');
    autoGroup.appendChild(operadorOption);
    autoGroup.appendChild(cioOption);

    const manualGroup = document.createElement('optgroup');
    manualGroup.label = '🛠️ Coprocesadores Alternativos';
    const geminiOption = new Option('✨ Google Gemini (IA Nube · Prioridad 2)', 'ai');
    const qwenOption = new Option('🤖 Qwen 2.5 (IA Local · trader-qwen · Prioridad 3)', 'ollama|trader-qwen');
    const localOption = new Option('⚙️ Modelo Matemático Determinista (Sin IA · Prioridad 4)', 'local');
    manualGroup.appendChild(geminiOption);
    manualGroup.appendChild(qwenOption);
    manualGroup.appendChild(localOption);

    select.appendChild(autoGroup);
    select.appendChild(manualGroup);

    try {
        const brainResponse = await fetch(`${API_BASE_URL}/api/system/brain`, { headers: apiAuthHeaders() });
        if (brainResponse.ok) {
            const brain = await brainResponse.json();
            setBrainSelectorsValue(brainSelectionValue(brain));
            const chk = document.getElementById('chkAutoEngineSelect');
            if (chk) {
                chk.checked = !!brain.auto_engine;
                updateAutoEngineLabel(chk.checked);
            }
        } else {
            select.value = 'antigravity_operador';
            updateAutoEngineLabel(false);
        }
    } catch (_) {
        select.value = 'antigravity_operador';
        updateAutoEngineLabel(false);
    }
}

window.checkEnginesHealth = async function(manualClick = false) {
    const spinner = document.getElementById('healthcheckSpinner');
    const badgeAnti = document.getElementById('healthBadgeAntigravity');
    const badgeGem = document.getElementById('healthBadgeGemini');
    const badgeQwen = document.getElementById('healthBadgeQwen');
    const badgeMat = document.getElementById('healthBadgeMatematico');
    const detailText = document.getElementById('engineHealthDetailText');

    if (spinner) spinner.classList.remove('hidden');

    try {
        const resp = await fetch(`${API_BASE_URL}/api/system/engine-check`, { headers: apiAuthHeaders() });
        if (resp.ok) {
            const data = await resp.json();
            const checks = data.checks || {};

            // 1. Antigravity
            if (badgeAnti) {
                badgeAnti.className = "p-1 rounded bg-amber-950/60 border border-amber-500 text-amber-200 font-bold";
                badgeAnti.innerHTML = `⚡ 1. Antigravity: <span class="text-emerald-400 font-mono">🟢 ACTIVO</span>`;
            }

            // 2. Google Gemini
            if (badgeGem) {
                if (checks.gemini?.available) {
                    badgeGem.className = "p-1 rounded bg-purple-950/60 border border-purple-500 text-purple-200 font-bold";
                    badgeGem.innerHTML = `✨ 2. Google: <span class="text-emerald-400 font-mono">🟢 LISTO</span>`;
                } else {
                    badgeGem.className = "p-1 rounded bg-purple-950/30 border border-purple-800/60 text-purple-300";
                    badgeGem.innerHTML = `✨ 2. Google: <span class="text-amber-400 font-mono">🟡 FALTA KEY</span>`;
                }
            }

            // 3. Qwen 2.5
            if (badgeQwen) {
                if (checks.qwen?.available) {
                    badgeQwen.className = "p-1 rounded bg-emerald-950/60 border border-emerald-500 text-emerald-200 font-bold";
                    badgeQwen.innerHTML = `🤖 3. Qwen: <span class="text-emerald-400 font-mono">🟢 ONLINE</span>`;
                } else {
                    badgeQwen.className = "p-1 rounded bg-gray-900 border border-gray-800 text-gray-400";
                    badgeQwen.innerHTML = `🤖 3. Qwen: <span class="text-slate-500 font-mono">⚪ STANDBY</span>`;
                }
            }

            // 4. Modelo Matemático Cuantitativo Local
            if (badgeMat) {
                badgeMat.className = "p-1 rounded bg-cyan-950/60 border border-cyan-500 text-cyan-200 font-bold";
                badgeMat.innerHTML = `⚙️ 4. Matemático: <span class="text-emerald-400 font-mono">🟢 BASE</span>`;
            }

            // Actualizar texto descriptivo
            const cur = data.active_engine;
            let activeDesc = checks.antigravity?.details || "Antigravity Operador Activo";
            if (cur === 'ai' || cur === 'gemini') {
                activeDesc = checks.gemini?.details || "Google Gemini en Ejecución";
            } else if (cur === 'ollama' || cur?.includes('qwen')) {
                activeDesc = checks.qwen?.details || "Qwen 2.5 en Ejecución";
            } else if (cur === 'local') {
                activeDesc = checks.matematico?.details || "Modelo Matemático Cuantitativo Activo";
            }
            if (detailText) {
                detailText.innerText = activeDesc;
            }

            if (manualClick) {
                logToTerminal?.(`[HEALTHCHECK] Cascada 1-2-3-4: 1. Antigravity (OK) · 2. Gemini (${checks.gemini?.available ? 'OK' : 'Falta Key'}) · 3. Qwen (${checks.qwen?.available ? 'OK' : 'Standby'}) · 4. Matemático (OK)`, 'info');
            }
        }
    } catch (e) {
        if (detailText) detailText.innerText = "Modo autónomo local activo.";
    } finally {
        if (spinner) spinner.classList.add('hidden');
    }
};

async function saveBrainSelection(value, autoEngine) {
    const selected = parseBrainSelection(value);
    const chk = document.getElementById('chkAutoEngineSelect');
    const isAuto = (autoEngine !== undefined) ? !!autoEngine : (chk ? chk.checked : false);
    const payload = {
        engine: selected.engine,
        model: selected.model,
        auto_engine: isAuto
    };
    const response = await fetch(`${API_BASE_URL}/api/system/brain`, {
        method: 'POST',
        headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `HTTP ${response.status} guardando el motor seleccionado.`);
    }
    setBrainSelectorsValue(value);
    if (selected.engine !== 'gemini' && window.dismissFailoverAlert) {
        window.dismissFailoverAlert().catch(() => {});
    }
    if (window.checkEnginesHealth) {
        window.checkEnginesHealth();
    }
}

function startBrainSelectorSync() {
    refreshBrainModelOptions().then(() => {
        if (window.checkEnginesHealth) window.checkEnginesHealth();
    }).catch(error => {
        logToTerminal?.(`No se pudo inicializar la selección de motor: ${error.message}`, 'error');
    });

    const chk = document.getElementById('chkAutoEngineSelect');
    chk?.addEventListener('change', event => {
        const isAuto = event.target.checked;
        updateAutoEngineLabel(isAuto);
        const selVal = document.getElementById('engineSelect')?.value || 'antigravity_operador';
        saveBrainSelection(selVal, isAuto).then(() => {
            if (isAuto) {
                logToTerminal?.('🔄 [Motor IA] Conmutación Automática HABILITADA (Cascada 1-2-3-4 activa).', 'warn');
            } else {
                logToTerminal?.('🔒 [Motor IA] Conmutación Automática DESACTIVADA (Modo Manual Fijo). El motor seleccionado no cambiará por fallos externos.', 'info');
            }
        }).catch(err => {
            logToTerminal?.(`Error guardando estado automático de motor: ${err.message}`, 'error');
        });
    });

    document.getElementById('engineSelect')?.addEventListener('change', event => {
        const value = event.target.value;
        setBrainSelectorsValue(value);
        const chkEl = document.getElementById('chkAutoEngineSelect');
        const isAuto = chkEl ? chkEl.checked : false;
        saveBrainSelection(value, isAuto).then(() => {
            if (window.checkEnginesHealth) window.checkEnginesHealth();
        }).catch(error => {
            logToTerminal?.(`No se pudo guardar la selección de motor: ${error.message}`, 'error');
        });
    });

    setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/system/brain`, { headers: apiAuthHeaders() });
            if (!response.ok) return;
            const brainData = await response.json();
            const chkEl = document.getElementById('chkAutoEngineSelect');
            if (chkEl && brainData.auto_engine !== undefined) {
                chkEl.checked = !!brainData.auto_engine;
                updateAutoEngineLabel(chkEl.checked);
            }
            // En modo manual fijo, no permitimos que una conmutación accidental en backend sobreescriba la UI
            if (brainData.auto_engine) {
                setBrainSelectorsValue(brainSelectionValue(brainData));
            } else {
                const currentSelect = document.getElementById('engineSelect');
                if (currentSelect && document.activeElement !== currentSelect) {
                    setBrainSelectorsValue(brainSelectionValue(brainData));
                }
            }
            if (window.checkFailoverAlertStatus) {
                window.checkFailoverAlertStatus();
            }
        } catch (_) {}
    }, 8000);
    if (window.checkFailoverAlertStatus) {
        window.checkFailoverAlertStatus();
    }
}

// --- PROTOCOLO DE CONMUTACIÓN DE EMERGENCIA A GOOGLE GEMINI ---
window.toggleFailoverDropdown = function() {
    const content = document.getElementById('failover-dropdown-content');
    const btn = document.getElementById('failover-toggle-btn');
    if (!content) return;
    const isHidden = content.classList.contains('hidden');
    if (isHidden) {
        content.classList.remove('hidden');
        if (btn) btn.innerText = '▲ Ocultar Detalle';
    } else {
        content.classList.add('hidden');
        if (btn) btn.innerText = '▼ Ver Detalle';
    }
};

window.checkFailoverAlertStatus = async function() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/system/failover-alert`, { headers: apiAuthHeaders() });
        if (!res.ok) return;
        const alertData = await res.json();
        const bar = document.getElementById('gemini-failover-bar');
        const msgEl = document.getElementById('failover-reason-msg');
        const titleEl = document.getElementById('failover-bar-title');
        if (!bar) return;

        if (alertData && alertData.active && !alertData.dismissed) {
            bar.classList.remove('hidden');
            if (msgEl && alertData.reason) {
                msgEl.innerText = alertData.reason;
            }
            if (titleEl && alertData.source) {
                const srcName = alertData.source.includes('cio') ? 'Director de Inversiones (CIO)' : 'Operador Táctico';
                titleEl.innerText = `Interrupción en ${srcName} · Conmutación Automática a Google Gemini`;
            }
        } else {
            bar.classList.add('hidden');
        }
    } catch (_) {}
};

window.forceSyncGemini = async function() {
    try {
        await fetch(`${API_BASE_URL}/api/system/failover-alert/trigger`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ source: 'usuario', reason: 'Reconfirmación manual de conmutación a Google Gemini' })
        });
        setBrainSelectorsValue('ai');
        logToTerminal?.('Google Gemini sincronizado en CIO y Operador con éxito.', 'success');
    } catch (err) {
        console.error('Error forzando Gemini:', err);
    }
};

window.dismissFailoverAlert = async function() {
    try {
        await fetch(`${API_BASE_URL}/api/system/failover-alert/dismiss`, {
            method: 'POST',
            headers: apiAuthHeaders()
        });
        const bar = document.getElementById('gemini-failover-bar');
        if (bar) bar.classList.add('hidden');
    } catch (err) {
        const bar = document.getElementById('gemini-failover-bar');
        if (bar) bar.classList.add('hidden');
    }
};

// Elementos de UI
const terminal = document.getElementById('terminal');
const agentToggle = document.getElementById('agentToggle');

// Función de sanitización anti-XSS para contenido externo y texto de LLMs
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Diccionario de Metadatos y Clasificación de Activos
const ASSET_METADATA = {
    // 🛢️ Materias Primas y Energía
    'CL=F': { name: 'Petróleo WTI', ticker: 'CL=F', icon: '🛢️', category: 'Materias Primas y Energía' },
    'GC=F': { name: 'Oro', ticker: 'GC=F', icon: '🥇', category: 'Materias Primas y Energía' },
    'SI=F': { name: 'Plata', ticker: 'SI=F', icon: '🥈', category: 'Materias Primas y Energía' },
    'NG=F': { name: 'Gas Natural', ticker: 'NG=F', icon: '🔥', category: 'Materias Primas y Energía' },

    // ⚡ Criptomonedas
    'BTC/USDT': { name: 'Bitcoin', ticker: 'BTC/USDT', icon: '⚡', category: 'Criptomonedas' },
    'BTC-USD': { name: 'Bitcoin', ticker: 'BTC-USD', icon: '⚡', category: 'Criptomonedas' },
    'ETH/USDT': { name: 'Ethereum', ticker: 'ETH/USDT', icon: '⚡', category: 'Criptomonedas' },
    'ETH-USD': { name: 'Ethereum', ticker: 'ETH-USD', icon: '⚡', category: 'Criptomonedas' },
    'SOL/USDT': { name: 'Solana', ticker: 'SOL/USDT', icon: '⚡', category: 'Criptomonedas' },
    'SOL-USD': { name: 'Solana', ticker: 'SOL-USD', icon: '⚡', category: 'Criptomonedas' },
    'BNB/USDT': { name: 'Binance Coin', ticker: 'BNB/USDT', icon: '🟡', category: 'Criptomonedas' },
    'BNB-USD': { name: 'Binance Coin', ticker: 'BNB-USD', icon: '🟡', category: 'Criptomonedas' },
    'XRP/USDT': { name: 'Ripple', ticker: 'XRP/USDT', icon: '🪙', category: 'Criptomonedas' },
    'XRP-USD': { name: 'Ripple', ticker: 'XRP-USD', icon: '🪙', category: 'Criptomonedas' },

    // 🏛️ Bonos e Índices Macro
    'TLT': { name: 'Bonos Tesoro EE.UU. 20+ Años', ticker: 'TLT', icon: '🏛️', category: 'Bonos e Índices Macro' },
    '^GSPC': { name: 'S&P 500 (Índice)', ticker: '^GSPC', icon: '📈', category: 'Bonos e Índices Macro' },
    'SPY': { name: 'S&P 500 (ETF)', ticker: 'SPY', icon: '📊', category: 'Bonos e Índices Macro' },
    'QQQ': { name: 'Nasdaq 100', ticker: 'QQQ', icon: '💻', category: 'Bonos e Índices Macro' },

    // 🏢 Acciones / Empresas Globales
    'BABA': { name: 'Alibaba Group', ticker: 'BABA', icon: '🏢', category: 'Empresas Globales' },
    'NVDA': { name: 'Nvidia Corp.', ticker: 'NVDA', icon: '🤖', category: 'Empresas Globales' },
    'AAPL': { name: 'Apple Inc.', ticker: 'AAPL', icon: '🍎', category: 'Empresas Globales' },
    'AMD': { name: 'Advanced Micro Devices', ticker: 'AMD', icon: '⚡', category: 'Empresas Globales' },
    'AVGO': { name: 'Broadcom Inc.', ticker: 'AVGO', icon: '📡', category: 'Empresas Globales' },
    'META': { name: 'Meta Platforms Inc.', ticker: 'META', icon: '🌐', category: 'Empresas Globales' },
    'TSLA': { name: 'Tesla Inc.', ticker: 'TSLA', icon: '🚗', category: 'Empresas Globales' },
    'MSFT': { name: 'Microsoft Corp.', ticker: 'MSFT', icon: '🪟', category: 'Empresas Globales' },

    // 🇦🇷 Mercado Argentino (Acciones / CEDEARs)
    'GGAL.BA': { name: 'Grupo Fin. Galicia', ticker: 'GGAL', icon: '🇦🇷', category: 'Mercado Argentino' },
    'YPFD.BA': { name: 'YPF / Vaca Muerta', ticker: 'YPFD', icon: '🇦🇷', category: 'Mercado Argentino' },
    'PAMP.BA': { name: 'Pampa Energía', ticker: 'PAMP', icon: '🇦🇷', category: 'Mercado Argentino' },
    'BMA.BA': { name: 'Banco Macro', ticker: 'BMA', icon: '🇦🇷', category: 'Mercado Argentino' },
    'ALUA.BA': { name: 'Aluar Aluminio', ticker: 'ALUA', icon: '🇦🇷', category: 'Mercado Argentino' },
    'TXAR.BA': { name: 'Ternium Argentina', ticker: 'TXAR', icon: '🇦🇷', category: 'Mercado Argentino' },

    // 🌐 ETFs Temáticos y Emergentes
    'MCHI': { name: 'ETF Mercado Chino', ticker: 'MCHI', icon: '🇨🇳', category: 'China y Emergentes' },
    'KWEB': { name: 'ETF Internet China', ticker: 'KWEB', icon: '🇨🇳', category: 'China y Emergentes' },
    'BOTZ': { name: 'ETF Robótica & AI', ticker: 'BOTZ', icon: '🤖', category: 'Inteligencia Artificial' }
};

function getAssetMeta(symbol) {
    if (!symbol) return null;
    const clean = String(symbol).trim();
    if (ASSET_METADATA[clean]) return ASSET_METADATA[clean];
    const slashSym = clean.replace('-', '/');
    if (ASSET_METADATA[slashSym]) return ASSET_METADATA[slashSym];
    const dashSym = clean.replace('/', '-');
    if (ASSET_METADATA[dashSym]) return ASSET_METADATA[dashSym];
    // Coincidencia parcial por ticker base (ej: GGAL)
    for (const k in ASSET_METADATA) {
        if (ASSET_METADATA[k].ticker === clean || clean.startsWith(ASSET_METADATA[k].ticker)) {
            return ASSET_METADATA[k];
        }
    }
    return null;
}

function formatAssetLabel(symbol) {
    if (!symbol) return '';
    const meta = getAssetMeta(symbol);
    if (meta) {
        return `${meta.icon} ${meta.name} (${meta.ticker})`;
    }
    return String(symbol);
}

let _terminalUserScrolledUp = false;

window.syncTerminalSideScrollbar = function() {
    if (!terminal) return;
    const track = document.getElementById('terminalScrollTrack');
    const thumb = document.getElementById('terminalScrollThumb');
    if (!track || !thumb) return;

    const trackH = track.clientHeight || 168;
    const scrollH = terminal.scrollHeight || 1;
    const clientH = terminal.clientHeight || 1;
    const maxScroll = Math.max(0, scrollH - clientH);

    if (maxScroll <= 0) {
        thumb.style.height = Math.max(48, Math.min(trackH - 8, 72)) + 'px';
        thumb.style.top = '0px';
        return;
    }

    const ratio = clientH / scrollH;
    const thumbH = Math.max(36, Math.min(trackH - 8, Math.round(ratio * trackH)));
    const maxThumbTop = Math.max(0, trackH - thumbH);
    const scrollRatio = Math.max(0, Math.min(1, terminal.scrollTop / maxScroll));
    const thumbTop = Math.round(scrollRatio * maxThumbTop);

    thumb.style.height = thumbH + 'px';
    thumb.style.top = thumbTop + 'px';
};

(function initTerminalSideScrollbar() {
    const bindSideScrollbar = () => {
        if (!terminal) return;
        const upBtn = document.getElementById('terminalScrollUpBtn');
        const downBtn = document.getElementById('terminalScrollDownBtn');
        const track = document.getElementById('terminalScrollTrack');
        const thumb = document.getElementById('terminalScrollThumb');
        if (!track || !thumb) return;

        const scrollByStep = (delta) => {
            const maxScroll = Math.max(0, terminal.scrollHeight - terminal.clientHeight);
            terminal.scrollTop = Math.max(0, Math.min(maxScroll, terminal.scrollTop + delta));
            _terminalUserScrolledUp = (terminal.scrollTop < maxScroll - 12);
            window.syncTerminalSideScrollbar();
        };

        // Botones ▲ y ▼ con soporte para clic y mantener presionado
        let holdInterval = null;
        const startHold = (delta) => {
            scrollByStep(delta);
            clearInterval(holdInterval);
            holdInterval = setInterval(() => scrollByStep(delta), 75);
        };
        const stopHold = () => {
            if (holdInterval) {
                clearInterval(holdInterval);
                holdInterval = null;
            }
        };

        if (upBtn) {
            upBtn.addEventListener('mousedown', (e) => { e.preventDefault(); startHold(-44); });
            upBtn.addEventListener('mouseup', stopHold);
            upBtn.addEventListener('mouseleave', stopHold);
        }
        if (downBtn) {
            downBtn.addEventListener('mousedown', (e) => { e.preventDefault(); startHold(44); });
            downBtn.addEventListener('mouseup', stopHold);
            downBtn.addEventListener('mouseleave', stopHold);
        }

        // Arrastre directo de la barra deslizante (#terminalScrollThumb)
        let isDragging = false;
        let dragStartY = 0;
        let dragStartScrollTop = 0;

        thumb.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            isDragging = true;
            dragStartY = e.clientY;
            dragStartScrollTop = terminal.scrollTop;
            thumb.style.cursor = 'grabbing';
            thumb.style.background = 'linear-gradient(180deg, #38bdf8 0%, #0284c7 100%)';
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const trackH = track.clientHeight || 168;
            const thumbH = thumb.offsetHeight || 48;
            const maxThumbTop = Math.max(1, trackH - thumbH);
            const maxScroll = Math.max(0, terminal.scrollHeight - terminal.clientHeight);
            const deltaY = e.clientY - dragStartY;
            const scrollDelta = (deltaY / maxThumbTop) * maxScroll;
            terminal.scrollTop = Math.max(0, Math.min(maxScroll, dragStartScrollTop + scrollDelta));
            _terminalUserScrolledUp = (terminal.scrollTop < maxScroll - 12);
            window.syncTerminalSideScrollbar();
        });

        window.addEventListener('mouseup', () => {
            if (!isDragging) return;
            isDragging = false;
            thumb.style.cursor = 'grab';
            thumb.style.background = 'linear-gradient(180deg, #10b981 0%, #059669 100%)';
        });

        // Clic directo sobre el riel (#terminalScrollTrack)
        track.addEventListener('mousedown', (e) => {
            if (e.target === thumb || thumb.contains(e.target)) return;
            e.preventDefault();
            const rect = track.getBoundingClientRect();
            const clickY = e.clientY - rect.top;
            const trackH = track.clientHeight || 168;
            const thumbH = thumb.offsetHeight || 48;
            const maxThumbTop = Math.max(1, trackH - thumbH);
            const targetTop = Math.max(0, Math.min(maxThumbTop, clickY - thumbH / 2));
            const maxScroll = Math.max(0, terminal.scrollHeight - terminal.clientHeight);
            terminal.scrollTop = Math.round((targetTop / maxThumbTop) * maxScroll);
            _terminalUserScrolledUp = (terminal.scrollTop < maxScroll - 12);
            window.syncTerminalSideScrollbar();
        });

        window.syncTerminalSideScrollbar();
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindSideScrollbar);
    } else {
        setTimeout(bindSideScrollbar, 0);
    }
})();

function logToTerminal(message, type = 'info') {
    if (!terminal) return;
    const time = new Date().toLocaleTimeString();
    const p = document.createElement('p');
    let color = 'text-green-400';
    if (type === 'warn') color = 'text-yellow-400';
    if (type === 'error') color = 'text-red-400';
    if (type === 'action') color = 'text-blue-400';
    
    p.className = color;
    const timeSpan = document.createElement('span');
    timeSpan.className = 'text-gray-500';
    timeSpan.textContent = `[${time}] > `;
    p.appendChild(timeSpan);
    p.appendChild(document.createTextNode(String(message)));
    terminal.appendChild(p);
    // Limitar el buffer del DOM para evitar saturación de RAM en sesiones largas
    while (terminal.children.length > 300) {
        terminal.removeChild(terminal.firstChild);
    }
    if (!_terminalUserScrolledUp) {
        terminal.scrollTop = terminal.scrollHeight;
    }
    if (typeof window.syncTerminalSideScrollbar === 'function') {
        window.syncTerminalSideScrollbar();
    }
}

window.copiarContenidoCerebro = async function(mode = 'todo', btnEl = null) {
    const nowStr = new Date().toLocaleString('es-AR');
    const getText = (id, fallback = '---') => {
        const el = document.getElementById(id);
        return el ? (el.innerText || el.textContent || fallback).trim() : fallback;
    };

    const sym = getText('chartTitleSymbol', currentSymbol || 'BTC/USDT');
    const engine = getText('strategyExecutingEngineLabel', 'Antigravity Operador');
    const formula = getText('strategySelectedFormulaLabel', 'Kula Balam: Cava & Ruiz');
    const tfSummary = getText('activeTimeframeSummary', '5M · 1H · 1D');
    const slSummary = getText('activeStopLossSummary', '1.5×ATR');
    const tpSummary = getText('activeTakeProfitSummary', 'Peluqueo 50% TP1 + Trailing');
    const verdict = getText('operadorSignalBadge', 'ESPERAR / MANTENER');
    const liveReason = getText('operadorLiveActionLog', 'Sin razonamiento adicional');

    const logsEl = document.getElementById('terminal');
    const logsLines = logsEl
        ? Array.from(logsEl.children).map(p => (p.innerText || p.textContent || '').trim()).filter(Boolean).join('\n')
        : '';

    const chatEl = document.getElementById('operadorChatMessages');
    const chatLines = chatEl
        ? Array.from(chatEl.children).map(div => (div.innerText || div.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean).join('\n\n')
        : '';

    let textToCopy = '';
    if (mode === 'logs') {
        textToCopy = [
            `=== 🕯️ KULA CEREBRO (LOGS DE DECISIONES) [${nowStr}] ===`,
            `Activo: ${sym} | Fórmula: ${formula} | Motor: ${engine}`,
            `Parámetros: TF=${tfSummary} | SL=${slSummary} | TP=${tpSummary}`,
            `------------------------------------------------------------`,
            logsLines || '(Sin registros en consola)'
        ].join('\n');
    } else if (mode === 'razonamiento') {
        textToCopy = [
            `=== 🧠 RAZONAMIENTO EN VIVO DE KULA CEREBRO [${nowStr}] ===`,
            `Activo: ${sym} | Último Veredicto: ${verdict}`,
            `Razonamiento: ${liveReason}`
        ].join('\n');
    } else if (mode === 'operador') {
        textToCopy = [
            `=== 🕯️ KULA CEREBRO · TRINCHERA TÁCTICA [${nowStr}] ===`,
            `Activo: ${sym} | Último Veredicto: ${verdict}`,
            `Razonamiento en Vivo: ${liveReason}`,
            `------------------------------------------------------------`,
            `[REPORTES Y CONSOLA DEL OPERADOR]:`,
            chatLines || '(Sin mensajes en el panel del operador)'
        ].join('\n');
    } else {
        textToCopy = [
            `============================================================`,
            `🕯️ REPORTE DE ACTIVIDAD DE KULA CEREBRO [${nowStr}]`,
            `============================================================`,
            `• Activo en foco: ${sym}`,
            `• Coprocesador / Worker: ${engine}`,
            `• Fórmula Táctica Activa: ${formula}`,
            `• Temporalidad: ${tfSummary}`,
            `• Stop Loss: ${slSummary}`,
            `• Take Profit: ${tpSummary}`,
            `• Último Veredicto: ${verdict}`,
            `• Razonamiento en Vivo: ${liveReason}`,
            `------------------------------------------------------------`,
            `[BITÁCORA DE LOGS DE KULA CEREBRO]:`,
            logsLines || '(Sin registros en consola)'
        ].join('\n');
    }

    let copiedOk = false;
    try {
        if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
            await navigator.clipboard.writeText(textToCopy);
            copiedOk = true;
        }
    } catch (_) {}

    if (!copiedOk) {
        try {
            const ta = document.createElement('textarea');
            ta.value = textToCopy;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            copiedOk = document.execCommand('copy');
            document.body.removeChild(ta);
        } catch (_) {}
    }

    if (btnEl) {
        const prevHtml = btnEl.getAttribute('data-orig-html') || btnEl.innerHTML;
        if (!btnEl.getAttribute('data-orig-html')) {
            btnEl.setAttribute('data-orig-html', prevHtml);
        }
        btnEl.innerHTML = '<span>✅</span> ¡Copiado!';
        setTimeout(() => {
            btnEl.innerHTML = prevHtml;
        }, 2000);
    }

    logToTerminal(`📋 Contenido de Kula Cerebro (${mode.toUpperCase()}) copiado al portapapeles.`, 'info');
};

// Capturar errores para verlos en pantalla
window.onerror = function(message, source, lineno, colno, error) {
    logToTerminal(`ERROR CRÍTICO: ${message} (Línea ${lineno})`, 'error');
};
window.addEventListener('unhandledrejection', function(event) {
    logToTerminal(`PROMESA FALLIDA: ${event.reason}`, 'error');
});

// Configuración inicial del Gráfico usando el Motor Centralizado KulaChartEngine (TradingView Pro Oscuro en Cockpit)
const chartOptions = (window.KulaChartEngine && window.KulaChartEngine.getChartThemeOptions)
    ? window.KulaChartEngine.getChartThemeOptions(false)
    : {
        layout: {
            textColor: '#94a3b8',
            background: { type: 'solid', color: 'transparent' },
        },
        localization: {
            dateFormat: 'yyyy-MM-dd',
            timeFormatter: (ts) => {
                if (typeof ts === 'number') {
                    const d = new Date(ts * 1000);
                    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
                }
                return String(ts || '');
            }
        },
        grid: {
            vertLines: { color: 'rgba(30, 41, 59, 0.5)' },
            horzLines: { color: 'rgba(30, 41, 59, 0.5)' },
        },
        rightPriceScale: { borderColor: '#1e293b', scaleMargins: { top: 0.12, bottom: 0.12 }, autoScale: true, alignLabels: true },
        handleScale: {
            axisPressedMouseMove: { time: true, price: true },
            axisDoubleClickReset: { time: true, price: true },
            mouseWheel: true,
            pinch: true,
        },
        handleScroll: {
            mouseWheel: true,
            pressedMouseMove: true,
            horzTouchDrag: true,
            vertTouchDrag: true,
        },
        timeScale: {
            borderColor: '#1e293b',
            timeVisible: true,
            rightOffset: 5,
            barSpacing: 13,
            minBarSpacing: 5,
            tickMarkFormatter: (ts, tickMarkType) => {
                if (typeof ts === 'number') {
                    const d = new Date(ts * 1000);
                    if (tickMarkType === 0) return String(d.getFullYear());
                    if (tickMarkType === 1) return `${d.getDate()}/${d.getMonth() + 1}`;
                    if (tickMarkType === 2) return `${d.getDate()}/${d.getMonth() + 1}`;
                    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
                }
                return null;
            }
        },
    };

const chartContainer = document.getElementById('chart-container');
const chart = LightweightCharts.createChart(chartContainer, {
    ...chartOptions,
    width: chartContainer.clientWidth,
    height: 440,
});

const baseCandleSeriesOpts = (window.KulaChartEngine && window.KulaChartEngine.CANDLE_SERIES_OPTIONS) || {
    upColor: '#089981', downColor: '#f23645',
    borderDownColor: '#f23645', borderUpColor: '#089981',
    wickDownColor: '#f23645', wickUpColor: '#089981',
};

const candleSeries = chart.addCandlestickSeries({
    ...baseCandleSeriesOpts,
    autoscaleInfoProvider: (original) => {
        const res = original();
        if (!res || !res.priceRange) return res;

        // Escalar de forma pura y armónica basándonos en las velas visibles en pantalla
        const cMin = res.priceRange.minValue;
        const cMax = res.priceRange.maxValue;
        const candleRange = Math.max(0.0001, cMax - cMin);

        // Margen del 20% arriba y abajo para que las velas nunca se aplasten ni se deformen
        return {
            priceRange: {
                minValue: cMin - (candleRange * 0.20),
                maxValue: cMax + (candleRange * 0.20),
            },
        };
    },
});

const smaSeries = chart.addLineSeries({
    color: '#3b82f6', // Azul brillante para la SMA 20
    lineWidth: 2,
    crosshairMarkerVisible: false,
    lastValueVisible: false, // Ocultar etiqueta en columna vertical
    priceLineVisible: false, // Ocultar línea de precio actual
});

const vwapSeries = chart.addLineSeries({
    color: '#eab308', // Amarillo para VWAP principal
    lineWidth: 2,
    lineStyle: 0, // Solid
    crosshairMarkerVisible: false,
    lastValueVisible: false,
    priceLineVisible: false,
});

const vwapUpperSeries = chart.addLineSeries({
    color: '#854d0e', // Amarillo oscuro apagado para Banda Superior
    lineWidth: 1,
    lineStyle: 1, // Dotted
    crosshairMarkerVisible: false,
    lastValueVisible: false,
    priceLineVisible: false,
});

const vwapLowerSeries = chart.addLineSeries({
    color: '#854d0e', // Amarillo oscuro apagado para Banda Inferior
    lineWidth: 1,
    lineStyle: 1, // Dotted
    crosshairMarkerVisible: false,
    lastValueVisible: false,
    priceLineVisible: false,
});

// --- SUB-GRÁFICO 1: OSCILADOR RSI (14) ---
const rsiContainer = document.getElementById('rsi-chart-container');
let rsiChart = null;
let rsiSeries = null;

if (rsiContainer && typeof LightweightCharts !== 'undefined') {
    rsiChart = LightweightCharts.createChart(rsiContainer, {
        ...chartOptions,
        width: rsiContainer.clientWidth || chartContainer.clientWidth,
        height: 130,
        rightPriceScale: {
            borderColor: 'rgba(55, 65, 81, 1)',
            scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: {
            borderColor: 'rgba(55, 65, 81, 1)',
            timeVisible: true,
            visible: false,
        },
    });

    rsiSeries = rsiChart.addLineSeries({
        color: '#c084fc', // Púrpura brillante institucional
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
    });

    rsiSeries.createPriceLine({
        price: 70,
        color: '#ef4444',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: '70',
    });
    rsiSeries.createPriceLine({
        price: 50,
        color: '#64748b',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: false,
        title: '50',
    });
    rsiSeries.createPriceLine({
        price: 30,
        color: '#22c55e',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: '30',
    });
}

// --- SUB-GRÁFICO 2: VOLATILIDAD REAL ATR (14) ---
const atrContainer = document.getElementById('atr-chart-container');
let atrChart = null;
let atrSeries = null;

if (atrContainer && typeof LightweightCharts !== 'undefined') {
    atrChart = LightweightCharts.createChart(atrContainer, {
        ...chartOptions,
        width: atrContainer.clientWidth || chartContainer.clientWidth,
        height: 110,
        rightPriceScale: {
            borderColor: 'rgba(55, 65, 81, 1)',
            scaleMargins: { top: 0.15, bottom: 0.05 },
        },
        timeScale: {
            borderColor: 'rgba(55, 65, 81, 1)',
            timeVisible: true,
            visible: true,
        },
    });

    atrSeries = atrChart.addAreaSeries({
        topColor: 'rgba(245, 158, 11, 0.35)',
        bottomColor: 'rgba(245, 158, 11, 0.02)',
        lineColor: '#f59e0b',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
    });
}

// Sincronización bidireccional de desplazamiento y zoom (TimeScale)
let _isSyncingRange = false;
function syncTimeScales(source, targets) {
    if (!source) return;
    source.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (_isSyncingRange || !range) return;
        _isSyncingRange = true;
        try {
            targets.forEach(target => {
                if (target) target.timeScale().setVisibleLogicalRange(range);
            });
        } finally {
            _isSyncingRange = false;
        }
    });
}

if (chart && rsiChart && atrChart) {
    syncTimeScales(chart, [rsiChart, atrChart]);
    syncTimeScales(rsiChart, [chart, atrChart]);
    syncTimeScales(atrChart, [chart, rsiChart]);
}

// Montar Barra Lateral de Herramientas TradingView (44px), Modalidad 1 Vela ↔ 3 Velas y "Clic Patrones"
if (window.KulaChartEngine) {
    window.KulaChartEngine.mountUnifiedChartWorkspace({
        singleWrapperId: 'kula-single-chart-wrapper',
        triadHeight: 380,
        hostChart: chart,
        hostRsiChart: rsiChart,
        hostAtrChart: atrChart,
        getSymbol: () => (typeof currentSymbol !== 'undefined' ? currentSymbol : 'BTCUSDT')
    });

    chart.subscribeClick(param => {
        if (!param || !param.time || !param.seriesData) return;
        const c = param.seriesData.get(candleSeries);
        if (!c) return;
        const arr = typeof currentHistoryData !== 'undefined' && Array.isArray(currentHistoryData) ? currentHistoryData : [];
        const idx = arr.findIndex(it => it.time === param.time);
        const prev = idx > 0 ? arr[idx - 1] : null;
        const prev2 = idx > 1 ? arr[idx - 2] : null;
        const pat = window.KulaChartEngine.formulas.detectCandlePatternDetails(c, prev, prev2);
        window.KulaChartEngine.renderUniversalPatternModal(c, pat, typeof currentTimeframe !== 'undefined' ? currentTimeframe.toUpperCase() : '1M', null);
    });

    window.inspectHostLastCandlePattern = function() {
        const arr = typeof currentHistoryData !== 'undefined' && Array.isArray(currentHistoryData) ? currentHistoryData : [];
        if (!arr.length) return;
        const last = arr[arr.length - 1];
        const prev = arr.length > 1 ? arr[arr.length - 2] : null;
        const prev2 = arr.length > 2 ? arr[arr.length - 3] : null;
        const pat = window.KulaChartEngine.formulas.detectCandlePatternDetails(last, prev, prev2);
        window.KulaChartEngine.renderUniversalPatternModal(last, pat, typeof currentTimeframe !== 'undefined' ? currentTimeframe.toUpperCase() : '1M', null);
    };
}

window.updateRsiBadge = function(val) {
    const el = document.getElementById('rsiLiveValue');
    const badge = document.getElementById('rsiStatusBadge');
    if (el && typeof val === 'number') el.innerText = val.toFixed(2);
    if (badge && typeof val === 'number') {
        if (val >= 70) {
            badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-red-950 text-red-300 border border-red-700 font-bold';
            badge.innerText = '🔴 SOBRECOMPRA (> 70)';
        } else if (val <= 30) {
            badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-600 font-bold animate-pulse';
            badge.innerText = '🟢 SOBREVENTA (< 30)';
        } else {
            badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-gray-800 text-purple-300 border border-gray-700 font-medium';
            badge.innerText = '⚪ ZONA NEUTRAL (30-70)';
        }
    }
};

window.updateAtrBadge = function(val, price) {
    const el = document.getElementById('atrLiveValue');
    const noiseEl = document.getElementById('atrNoiseValue');
    const badge = document.getElementById('atrVolatilityBadge');
    const curr = typeof getCurrency === 'function' ? getCurrency(currentSymbol) : 'USDT';
    const sym = '$';
    if (el && typeof val === 'number') el.innerText = `${sym}${val.toFixed(2)} ${curr}`;
    if (noiseEl && typeof val === 'number') noiseEl.innerText = `${sym}${(val * 1.5).toFixed(2)} ${curr}`;
    if (badge && typeof val === 'number' && price > 0) {
        const pct = (val / price) * 100;
        if (pct >= 1.5) {
            badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-700 font-bold';
            badge.innerText = `⚡ ALTA VOLATILIDAD (${pct.toFixed(2)}%)`;
        } else if (pct <= 0.5) {
            badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-700 font-medium';
            badge.innerText = `🧊 BAJA VOLATILIDAD (${pct.toFixed(2)}%)`;
        } else {
            badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-gray-800 text-amber-300 border border-gray-700 font-medium';
            badge.innerText = `🌊 NORMAL (${pct.toFixed(2)}%)`;
        }
    }
};

// --- CLASIFICADOR CUANTITATIVO DE VELAS JAPONESAS (THOMAS BULKOWSKI BENCHMARK) ---
function detectCandlePatternDetails(candle, prevCandle, prev2Candle, trendContext) {
    if (!candle || candle.high === undefined || candle.low === undefined || candle.open === undefined || candle.close === undefined) {
        return {
            name: "Esperando vela...",
            icon: "🕯️",
            fullName: "🕯️ Esperando vela...",
            badgeClass: "bg-gray-800 text-gray-400 border border-gray-700",
            direction: "neutral"
        };
    }

    const range = Math.max(0.00001, candle.high - candle.low);
    const body = Math.abs(candle.close - candle.open);
    const upperWick = candle.high - Math.max(candle.open, candle.close);
    const lowerWick = Math.min(candle.open, candle.close) - candle.low;

    const bodyRatio = (body / range) * 100;
    const upperRatio = (upperWick / range) * 100;
    const lowerRatio = (lowerWick / range) * 100;
    const isGreen = candle.close >= candle.open;

    // 1. Patrones de 3 velas: Morning Star & Evening Star
    if (prevCandle && prev2Candle) {
        const prevRange = Math.max(0.00001, prevCandle.high - prevCandle.low);
        const prevBody = Math.abs(prevCandle.close - prevCandle.open);
        const prev2Range = Math.max(0.00001, prev2Candle.high - prev2Candle.low);
        const prev2Body = Math.abs(prev2Candle.close - prev2Candle.open);

        // Morning Star (Estrella de la Mañana)
        if (prev2Candle.close < prev2Candle.open && (prev2Body / prev2Range) > 0.40 &&
            (prevBody / prevRange) < 0.35 &&
            candle.close > candle.open && candle.close > (prev2Candle.open + prev2Candle.close) / 2) {
            return {
                name: "Estrella de la Mañana (Morning Star)",
                icon: "🌅",
                fullName: "🌅 Morning Star",
                badgeClass: "bg-emerald-500/25 text-emerald-300 border border-emerald-400/50 font-extrabold",
                direction: "bullish"
            };
        }

        // Evening Star (Estrella del Atardecer)
        if (prev2Candle.close > prev2Candle.open && (prev2Body / prev2Range) > 0.40 &&
            (prevBody / prevRange) < 0.35 &&
            candle.close < candle.open && candle.close < (prev2Candle.open + prev2Candle.close) / 2) {
            return {
                name: "Estrella del Atardecer (Evening Star)",
                icon: "🌆",
                fullName: "🌆 Evening Star",
                badgeClass: "bg-rose-500/25 text-rose-300 border border-rose-400/50 font-extrabold",
                direction: "bearish"
            };
        }

        // Tres Soldados Blancos
        if (candle.close > candle.open && prevCandle.close > prevCandle.open && prev2Candle.close > prev2Candle.open &&
            candle.close > prevCandle.close && prevCandle.close > prev2Candle.close &&
            candle.open > prevCandle.open && prevCandle.open > prev2Candle.open &&
            upperRatio <= 25) {
            return {
                name: "Tres Soldados Blancos (Soldiers)",
                icon: "⚔️",
                fullName: "⚔️ 3 Soldados Blancos",
                badgeClass: "bg-emerald-500/20 text-emerald-300 border border-emerald-400/40",
                direction: "bullish"
            };
        }

        // Tres Cuervos Negros
        if (candle.close < candle.open && prevCandle.close < prevCandle.open && prev2Candle.close < prev2Candle.open &&
            candle.close < prevCandle.close && prevCandle.close < prev2Candle.close &&
            candle.open < prevCandle.open && prevCandle.open < prev2Candle.open &&
            lowerRatio <= 25) {
            return {
                name: "Tres Cuervos Negros (Crows)",
                icon: "🦅",
                fullName: "🦅 3 Cuervos Negros",
                badgeClass: "bg-rose-500/20 text-rose-300 border border-rose-400/40",
                direction: "bearish"
            };
        }
    }

    // 2. Patrones de 2 velas: Envolventes
    if (prevCandle) {
        if (prevCandle.close < prevCandle.open && candle.close > candle.open &&
            candle.close >= prevCandle.open * 0.998 && candle.open <= prevCandle.close * 1.002 &&
            bodyRatio >= 45) {
            return {
                name: "Envolvente Alcista (Bullish Engulfing)",
                icon: "🌊",
                fullName: "🌊 Envolvente Alcista",
                badgeClass: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 font-bold",
                direction: "bullish"
            };
        }
        if (prevCandle.close > prevCandle.open && candle.close < candle.open &&
            candle.close <= prevCandle.open * 1.002 && candle.open >= prevCandle.close * 0.998 &&
            bodyRatio >= 45) {
            return {
                name: "Envolvente Bajista (Bearish Engulfing)",
                icon: "🌧️",
                fullName: "🌧️ Envolvente Bajista",
                badgeClass: "bg-rose-500/20 text-rose-400 border border-rose-500/40 font-bold",
                direction: "bearish"
            };
        }
    }

    // 3. Patrones de 1 vela
    // Doji Libélula
    if (bodyRatio <= 8 && lowerRatio >= 60 && upperRatio <= 12) {
        return {
            name: "Doji Libélula (Dragonfly Doji)",
            icon: "🦎",
            fullName: "🦎 Doji Libélula",
            badgeClass: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40",
            direction: "bullish"
        };
    }

    // Doji Lápida
    if (bodyRatio <= 8 && upperRatio >= 60 && lowerRatio <= 12) {
        return {
            name: "Doji Lápida (Gravestone Doji)",
            icon: "🪦",
            fullName: "🪦 Doji Lápida",
            badgeClass: "bg-rose-500/20 text-rose-300 border border-rose-500/40",
            direction: "bearish"
        };
    }

    // Doji Clásico
    if (bodyRatio <= 8) {
        return {
            name: "Doji Clásico (Indecisión)",
            icon: "⚖️",
            fullName: "⚖️ Doji Clásico",
            badgeClass: "bg-amber-500/20 text-amber-300 border border-amber-500/40",
            direction: "neutral"
        };
    }

    // Martillo Alcista vs Hombre Colgado
    if (lowerRatio >= 55 && upperRatio <= 15) {
        if (trendContext === 'up' && prevCandle && prevCandle.close > prevCandle.open) {
            return {
                name: "Hombre Colgado (Hanging Man)",
                icon: "🪢",
                fullName: "🪢 Hombre Colgado",
                badgeClass: "bg-rose-500/20 text-rose-400 border border-rose-500/30",
                direction: "bearish"
            };
        }
        return {
            name: "Martillo Alcista (Hammer)",
            icon: "🔨",
            fullName: "🔨 Martillo Alcista",
            badgeClass: "bg-emerald-500/25 text-emerald-400 border border-emerald-500/50 font-extrabold",
            direction: "bullish"
        };
    }

    // Estrella Fugaz vs Martillo Invertido
    if (upperRatio >= 55 && lowerRatio <= 15) {
        if (trendContext === 'down' || (prevCandle && prevCandle.close < prevCandle.open)) {
            return {
                name: "Martillo Invertido (Suelo)",
                icon: "🔨",
                fullName: "🔨 Martillo Invertido",
                badgeClass: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
                direction: "bullish"
            };
        }
        return {
            name: "Estrella Fugaz (Shooting Star)",
            icon: "⭐",
            fullName: "⭐ Estrella Fugaz",
            badgeClass: "bg-rose-500/25 text-rose-400 border border-rose-500/50 font-extrabold",
            direction: "bearish"
        };
    }

    // Marubozu Alcista & Bajista
    if (bodyRatio >= 80 && upperRatio <= 8 && lowerRatio <= 8) {
        if (isGreen) {
            return {
                name: "Marubozu Alcista (Control Comprador)",
                icon: "🚀",
                fullName: "🚀 Marubozu Alcista",
                badgeClass: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold",
                direction: "bullish"
            };
        } else {
            return {
                name: "Marubozu Bajista (Presión Vendedora)",
                icon: "💥",
                fullName: "💥 Marubozu Bajista",
                badgeClass: "bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold",
                direction: "bearish"
            };
        }
    }

    // Peonza Indecisión
    if (bodyRatio >= 10 && bodyRatio <= 30 && upperRatio >= 25 && lowerRatio >= 25) {
        return {
            name: "Peonza Indecisión (Spinning Top)",
            icon: "🌀",
            fullName: "🌀 Peonza Indecisión",
            badgeClass: "bg-amber-500/20 text-amber-300 border border-amber-500/30",
            direction: "neutral"
        };
    }

    // Impulso Alcista / Bajista
    if (bodyRatio >= 60) {
        if (isGreen) {
            return {
                name: "Impulso Alcista (Rango Amplio)",
                icon: "📈",
                fullName: "📈 Impulso Alcista",
                badgeClass: "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30",
                direction: "bullish"
            };
        } else {
            return {
                name: "Impulso Bajista (Rango Amplio)",
                icon: "📉",
                fullName: "📉 Impulso Bajista",
                badgeClass: "bg-rose-500/15 text-rose-400 border border-rose-500/30",
                direction: "bearish"
            };
        }
    }

    // Vela Normal
    if (isGreen) {
        return {
            name: "Vela Normal Alcista",
            icon: "🕯️",
            fullName: "🕯️ Vela Normal Alcista",
            badgeClass: "bg-gray-900/90 text-emerald-400 border border-emerald-900/40",
            direction: "bullish"
        };
    } else {
        return {
            name: "Vela Normal Bajista",
            icon: "🕯️",
            fullName: "🕯️ Vela Normal Bajista",
            badgeClass: "bg-gray-900/90 text-rose-400 border border-rose-900/40",
            direction: "bearish"
        };
    }
}

window.detectCandlePatternDetails = detectCandlePatternDetails;

// --- GOBERNANZA Y CONTROL DE MARCADORES DE PATRONES EN EL GRÁFICO ---
window.isCandlePatternMarkersEnabled = function() {
    const chk = document.getElementById('chkShowCandlePatterns');
    if (chk) return chk.checked;
    return localStorage.getItem('ai_show_candle_patterns') === 'true'; // Desmarcado por defecto
};
// Mantener alias para compatibilidad
window.isCandlePatternIndicatorEnabled = window.isCandlePatternMarkersEnabled;

window.toggleCandlePatternIndicator = function(enabled) {
    localStorage.setItem('ai_show_candle_patterns', enabled ? 'true' : 'false');
    const chk = document.getElementById('chkShowCandlePatterns');
    if (chk && chk.checked !== enabled) chk.checked = enabled;

    // Solo actualiza las marcas visuales sobre las velas del gráfico
    if (typeof window.updateChartTradeMarkers === 'function') {
        window.updateChartTradeMarkers();
    }
};

window.syncCandlePatternIndicatorState = function() {
    const isEnabled = window.isCandlePatternMarkersEnabled();
    const chk = document.getElementById('chkShowCandlePatterns');
    if (chk && chk.checked !== isEnabled) chk.checked = isEnabled;
};

window.updateCandlePatternIndicator = function(candle, prevCandle, prev2Candle, trendContext) {
    // La lectura de patrones en el panel superior y en el cursor permanece SIEMPRE activa
    const headerBadge = document.getElementById('chart-pattern-badge-header');
    const legendBadge = document.getElementById('legend-candle-pattern');
    if (headerBadge && headerBadge.classList.contains('hidden')) headerBadge.classList.remove('hidden');
    if (legendBadge && legendBadge.classList.contains('hidden')) legendBadge.classList.remove('hidden');

    const res = detectCandlePatternDetails(candle, prevCandle, prev2Candle, trendContext);
    
    // 1. Badge superior en la cabecera del gráfico (Ancho fijo anti-temblor)
    const headerIcon = document.getElementById('header-candle-icon');
    const headerName = document.getElementById('header-candle-name');
    if (headerIcon && headerName && headerBadge) {
        headerIcon.innerText = res.icon;
        headerName.innerText = res.name;
        headerBadge.className = `inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold shadow cursor-pointer shrink-0 w-[210px] overflow-hidden whitespace-nowrap ${res.badgeClass}`;
    }

    // 2. Badge en la leyenda dinámica de cursor (Ancho acotado anti-temblor)
    const legendIcon = document.getElementById('legend-candle-icon');
    const legendName = document.getElementById('legend-candle-name');
    if (legendIcon && legendName && legendBadge) {
        legendIcon.innerText = res.icon;
        legendName.innerText = res.name;
        legendBadge.className = `inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold shrink-0 max-w-[180px] overflow-hidden whitespace-nowrap ${res.badgeClass}`;
    }
};

// Sincronización inicial del indicador
window.syncCandlePatternIndicatorState();

// Leyenda dinámica al hacer hover (Estabilizada: solo actualiza cuando cambia la vela bajo el cursor)
const legendOhlc = document.getElementById('legend-ohlc');
const legendSma = document.getElementById('legend-sma');
const legendVwap = document.getElementById('legend-vwap');
const legendVwapBands = document.getElementById('legend-vwap-bands');
let _lastCrosshairCandleTime = undefined;

chart.subscribeCrosshairMove((param) => {
    if (!param.point || !param.time || param.point.x < 0 || param.point.x > chartContainer.clientWidth || param.point.y < 0 || param.point.y > chartContainer.clientHeight) {
        if (_lastCrosshairCandleTime !== null) {
            _lastCrosshairCandleTime = null;
            // Fuera del gráfico: restaurar indicador a la última vela disponible
            if (window.lastRawMarketData && window.lastRawMarketData.length > 0) {
                const arr = window.lastRawMarketData;
                const last = arr[arr.length - 1];
                const prev = arr.length > 1 ? arr[arr.length - 2] : null;
                const prev2 = arr.length > 2 ? arr[arr.length - 3] : null;
                window.updateCandlePatternIndicator(last, prev, prev2);
            }
        }
        return; // Fuera del gráfico
    }

    // Evitar repintado DOM redundante si el ratón se mueve dentro de la misma vela
    if (param.time === _lastCrosshairCandleTime) return;
    _lastCrosshairCandleTime = param.time;

    const candleData = param.seriesData.get(candleSeries);
    if (candleData && candleData.close !== undefined) {
        legendOhlc.textContent = `Ape: ${candleData.open.toFixed(2)} | Máx: ${candleData.high.toFixed(2)} | Mín: ${candleData.low.toFixed(2)} | Cierre: ${candleData.close.toFixed(2)}`;
        let color = candleData.close >= candleData.open ? 'text-green-400' : 'text-red-400';
        legendOhlc.className = color;

        // Actualizar indicador dinámico para la vela bajo el cursor
        if (window.lastRawMarketData) {
            const idx = window.lastRawMarketData.findIndex(d => d.time === param.time);
            if (idx >= 0) {
                const cur = window.lastRawMarketData[idx];
                const prev = idx > 0 ? window.lastRawMarketData[idx - 1] : null;
                const prev2 = idx > 1 ? window.lastRawMarketData[idx - 2] : null;
                window.updateCandlePatternIndicator(cur, prev, prev2);
            } else {
                window.updateCandlePatternIndicator(candleData, null, null);
            }
        }
    }
    
    const smaData = param.seriesData.get(smaSeries);
    if (smaData && smaData.value !== undefined) {
        legendSma.textContent = `SMA 20: ${smaData.value.toFixed(2)}`;
    }
    
    const vwapData = param.seriesData.get(vwapSeries);
    if (vwapData && vwapData.value !== undefined) {
        legendVwap.textContent = `VWAP: ${vwapData.value.toFixed(2)}`;
    }
    
    const vwapUpperData = param.seriesData.get(vwapUpperSeries);
    const vwapLowerData = param.seriesData.get(vwapLowerSeries);
    if (vwapUpperData && vwapLowerData && vwapUpperData.value !== undefined && vwapLowerData.value !== undefined) {
        if(legendVwapBands) legendVwapBands.textContent = `Bandas: ${vwapUpperData.value.toFixed(2)} / ${vwapLowerData.value.toFixed(2)}`;
    }

    if (param.time && window.lastRawMarketData) {
        const pt = window.lastRawMarketData.find(d => d.time === param.time);
        if (pt) {
            if (typeof pt.rsi === 'number') window.updateRsiBadge(pt.rsi);
            if (typeof pt.atr === 'number') window.updateAtrBadge(pt.atr, pt.close);
        }
    }
});

const symbolSelect = document.getElementById('symbolSelect');
let currentSymbol = symbolSelect ? symbolSelect.value : 'BTC/USDT';
let currentPrice = 0;
let currentPriceSymbol = currentSymbol;
let currentPriceTs = 0;

// Variables de Simulación (Paper Trading) persistentes en el navegador
let portfolio = JSON.parse(localStorage.getItem('ai_portfolio_v5')) || {
    VAULT: 500.00, // Capital total en la Bóveda del Broker (USD)
    balances: {
        USDT: 100.00, // Cripto con $100 iniciales para operar
        USD: 0.00,  // Wall Street vacía por defecto
        ARS: 0.00   // Local vacía por defecto
    },
    deposits: {
        USDT: 100.00,
        USD: 0.00,
        ARS: 0.00
    },
    ASSET: 0,
    entryPrice: 0
};

// --- SISTEMA DE MARCADORES VISUALES DE OPERACIONES (E / S) Y DEMO TP / SL EN VELAS ---
window.toggleTradeMarkers = function(enabled) {
    localStorage.setItem('ai_show_trade_markers', enabled ? 'true' : 'false');
    const chk = document.getElementById('chkShowTradeMarkers');
    if (chk) chk.checked = enabled;
    window.updateChartTradeMarkers();
};

window.toggleTpSlDemoOverlay = function(enabled) {
    localStorage.setItem('ai_show_tpsl_demo', enabled ? 'true' : 'false');
    const chk = document.getElementById('chkShowTpSlDemo');
    if (chk) chk.checked = enabled;
    if (!enabled) {
        if (window.activeTradePriceLines && candleSeries) {
            window.activeTradePriceLines.forEach(l => {
                try { candleSeries.removePriceLine(l); } catch(e) {}
            });
            window.activeTradePriceLines = [];
        }
        window.activeRrBoxData = null;
        const rrEl = document.getElementById('active-trade-rr-box-overlay');
        if (rrEl) rrEl.innerHTML = '';
    }
    window.updateChartTradeMarkers();
};

window.switchAssetTo = function(sym) {
    const sel = document.getElementById('symbolSelect');
    if (!sel || !sym) return;
    let found = false;
    for (let i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value === sym) {
            sel.selectedIndex = i;
            sel.value = sym;
            sel.dispatchEvent(new Event('change'));
            found = true;
            break;
        }
    }
    if (found) {
        if (typeof window.fetchMicrostructureRadar === 'function') {
            window.fetchMicrostructureRadar();
        }
        const chartBox = document.getElementById('chart-container') || document.getElementById('chartTitleSymbol');
        if (chartBox) {
            chartBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        if (typeof logToTerminal === 'function') {
            logToTerminal(`👁️ Visualizando gráfico de ${sym} cargado desde el Radar de Activos.`, 'info');
        }
    }
};

window.changeTrailingKeyMode = async function(mode) {
    try {
        logToTerminal(`🎚️ Modificando Llave de Trailing Stop a: ${mode.toUpperCase()}...`, 'warn');
        const res = await fetch(`${API_BASE_URL}/api/trailing/key_mode?mode=${encodeURIComponent(mode)}`, {
            method: 'POST',
            headers: apiAuthHeaders()
        });
        if (res.ok) {
            logToTerminal(`✅ Llave de Trailing Stop configurada en: ${mode.toUpperCase()}`, 'info');
            const data = await res.json();
            const sel = document.getElementById('selTrailingKeyMode');
            if (sel && data.trailing_key_mode) sel.value = data.trailing_key_mode;
        }
    } catch (e) {
        console.warn("Error cambiando modo de llave trailing:", e);
    }
};

window.updateChartTradeMarkers = function() {
    if (!candleSeries || typeof candleSeries.setMarkers !== 'function') return;

    const chk = document.getElementById('chkShowTradeMarkers');
    const isTradeMarkersEnabled = chk ? chk.checked : (localStorage.getItem('ai_show_trade_markers') !== 'false');
    if (chk && chk.checked !== isTradeMarkersEnabled) chk.checked = isTradeMarkersEnabled;

    const chkTpSl = document.getElementById('chkShowTpSlDemo');
    const isTpSlDemoEnabled = chkTpSl ? chkTpSl.checked : (localStorage.getItem('ai_show_tpsl_demo') === 'true');
    if (chkTpSl && chkTpSl.checked !== isTpSlDemoEnabled) chkTpSl.checked = isTpSlDemoEnabled;

    const showPatterns = window.isCandlePatternIndicatorEnabled ? window.isCandlePatternIndicatorEnabled() : false;

    if (!isTradeMarkersEnabled && !showPatterns && !isTpSlDemoEnabled) {
        candleSeries.setMarkers([]);
        return;
    }

    const candleData = window.lastRawMarketData;
    if (!Array.isArray(candleData) || candleData.length === 0) {
        candleSeries.setMarkers([]);
        return;
    }

    const firstCandleTime = candleData[0].time;
    const lastCandleTime = candleData[candleData.length - 1].time;

    // Función auxiliar global para convertir fecha a segundos UTC
    window.toUtcSeconds = function(dt) {
        if (!dt) return null;
        if (typeof dt === 'number') {
            return dt > 1e11 ? Math.floor(dt / 1000) : Math.floor(dt);
        }
        if (typeof dt === 'string') {
            const cleanStr = dt.trim();
            const iso = cleanStr.includes('T') ? cleanStr : cleanStr.replace(' ', 'T') + (cleanStr.endsWith('Z') ? '' : 'Z');
            const ms = Date.parse(iso);
            return isNaN(ms) ? null : Math.floor(ms / 1000);
        }
        if (dt instanceof Date) return Math.floor(dt.getTime() / 1000);
        return null;
    };
    const toSeconds = (dt) => window.toUtcSeconds(dt);

    // Función auxiliar global para encontrar la vela exacta que contiene un timestamp
    window.findCandleTimeForTimestamp = function(ts, candles, isOngoing = false) {
        if (!ts || !Array.isArray(candles) || candles.length === 0) return null;
        const firstC = candles[0].time;
        const lastC = candles[candles.length - 1].time;
        if (ts >= lastC) return lastC;
        if (ts < firstC) {
            return isOngoing ? firstC : null;
        }

        // 1. Detección por pertenencia al intervalo temporal [ct, nextCt) de la barra
        const interval = (candles.length >= 2) ? Math.max(60, candles[1].time - candles[0].time) : 300;
        for (let i = candles.length - 1; i >= 0; i--) {
            const ct = candles[i].time;
            const nextCt = (i + 1 < candles.length) ? candles[i + 1].time : (ct + interval);
            if (ts >= ct && ts < nextCt) {
                return ct;
            }
        }

        // 2. Fallback por mínima distancia si hay discontinuidad en la serie
        let bestTime = candles[0].time;
        let minDiff = Infinity;
        for (let i = 0; i < candles.length; i++) {
            const ct = candles[i].time;
            const diff = Math.abs(ct - ts);
            if (diff < minDiff) {
                minDiff = diff;
                bestTime = ct;
            }
        }
        return bestTime;
    };
    const findCandleTime = (ts, isOngoing = false) => window.findCandleTimeForTimestamp(ts, candleData, isOngoing);

    function formatPriceCompact(px) {
        const n = Number(px) || 0;
        if (n >= 10000) return '$' + Math.round(n).toLocaleString('en-US');
        if (n >= 100) return '$' + n.toFixed(1);
        if (n >= 1) return '$' + n.toFixed(2);
        return '$' + n.toFixed(4);
    }

    const markers = [];
    const usedSlots = new Set(); // clave: `${time}_${position}`

    // Limpiar líneas de precio previas de órdenes/trades (salvo que estemos en modo inspección manual de un trade cerrado)
    if (!window.currentlyInspectedTradeId) {
        if (!window.activeTradePriceLines) window.activeTradePriceLines = [];
        window.activeTradePriceLines.forEach(l => {
            try { candleSeries.removePriceLine(l); } catch(e) {}
        });
        window.activeTradePriceLines = [];
        window.activeRrBoxData = null;
        const rrEl = document.getElementById('active-trade-rr-box-overlay');
        if (rrEl) rrEl.innerHTML = '';
    }

    if (isTradeMarkersEnabled || isTpSlDemoEnabled) {
        // 1. Recopilar posiciones abiertas para el símbolo activo
        const openPositions = (window.backendOpenPositions && window.backendOpenPositions.length > 0)
            ? window.backendOpenPositions
            : (portfolio && portfolio.position ? [portfolio.position] : []);

        openPositions.forEach(p => {
            if (!p || (p.symbol !== currentSymbol && p.symbol !== currentSymbol.replace('USDT', '/USDT'))) return;
            const entryPx = Number(p.entry_price || p.entryPrice || 0);
            const openSec = toSeconds(p.opened_at || p.timestamp) || lastCandleTime;
            const isPrior = openSec < firstCandleTime;
            const candleTime = findCandleTime(openSec, true);
            const isShort = (p.side || '').toUpperCase() === 'SHORT';

            if (isTradeMarkersEnabled && candleTime) {
                const markerPos = isShort ? 'aboveBar' : 'belowBar';
                const slotKey = `${candleTime}_${markerPos}`;
                if (!usedSlots.has(slotKey)) {
                    usedSlots.add(slotKey);
                    markers.push({
                        time: candleTime,
                        position: markerPos,
                        color: isShort ? '#f43f5e' : '#10b981',
                        shape: isShort ? 'arrowDown' : 'arrowUp',
                        text: isShort
                            ? (isPrior ? `SHORT: ${formatPriceCompact(entryPx)} (abierta)` : `SHORT: ${formatPriceCompact(entryPx)}`)
                            : (isPrior ? `LONG: ${formatPriceCompact(entryPx)} (abierta)` : `LONG: ${formatPriceCompact(entryPx)}`),
                        size: 1.5,
                    });
                }
            }

            // Trazar líneas de precio vivas y rectángulo R:R de la posición activa en el gráfico (solo si Demo TP/SL está activo)
            if (isTpSlDemoEnabled && !window.currentlyInspectedTradeId && entryPx > 0 && typeof candleSeries.createPriceLine === 'function') {
                const initSlPct = Number(p.initial_sl_pct || p.sl || 0.6);
                const stopNetPct = Number(p.current_stop_net_pct !== undefined ? p.current_stop_net_pct : -initSlPct);
                const isBe = p.be_armed === 1 || stopNetPct >= 0.0;
                const tpPct = Number(p.initial_tp_pct || p.tp || 2.1);

                const initSlPrice = isShort ? entryPx * (1 + initSlPct / 100) : entryPx * (1 - initSlPct / 100);
                const tpPrice = isShort ? entryPx * (1 - tpPct / 100) : entryPx * (1 + tpPct / 100);
                const peakPx = Number(p.peak_price || entryPx);
                const curPx = Number(p.current_price || (candleData[candleData.length - 1] && candleData[candleData.length - 1].close) || entryPx);

                const symTelem = (window.backendTrailingTelemetry && window.backendTrailingTelemetry[p.symbol]) || p.trailing_telemetry || null;
                let activeStopPrice = (symTelem && Number(symTelem.active_stop_price) > 0)
                    ? Number(symTelem.active_stop_price)
                    : (isBe
                        ? (isShort ? entryPx * (1 - 0.00022) : entryPx * (1 + 0.00022))
                        : initSlPrice);

                // 1) Línea de Entrada
                const lEntry = candleSeries.createPriceLine({
                    price: entryPx,
                    color: '#38bdf8',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: ''
                });
                window.activeTradePriceLines.push(lEntry);

                // 2) Línea de Viejo Stop Loss Inicial en ROJO INTENSO
                const lInitSl = candleSeries.createPriceLine({
                    price: initSlPrice,
                    color: '#ef4444',
                    lineWidth: 2,
                    lineStyle: isBe ? LightweightCharts.LineStyle.Dashed : LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: ''
                });
                window.activeTradePriceLines.push(lInitSl);

                // 3) Línea de Candado Breakeven / Trailing Stop Activo (cuando be_armed == 1)
                if (isBe) {
                    const lBe = candleSeries.createPriceLine({
                        price: activeStopPrice,
                        color: '#f59e0b',
                        lineWidth: 2,
                        lineStyle: LightweightCharts.LineStyle.Solid,
                        axisLabelVisible: true,
                        title: ''
                    });
                    window.activeTradePriceLines.push(lBe);
                }

                // 4) Línea de Pico Máximo Alcanzado
                if (peakPx > 0 && Math.abs(peakPx - entryPx) > 0.0001) {
                    const peakPct = isShort ? ((entryPx - peakPx) / entryPx) * 100 : ((peakPx - entryPx) / entryPx) * 100;
                    const lPeak = candleSeries.createPriceLine({
                        price: peakPx,
                        color: '#06b6d4',
                        lineWidth: 1.5,
                        lineStyle: LightweightCharts.LineStyle.Dotted,
                        axisLabelVisible: true,
                        title: ''
                    });
                    window.activeTradePriceLines.push(lPeak);
                }

                // 5) Línea de Take Profit Objetivo
                const lTp = candleSeries.createPriceLine({
                    price: tpPrice,
                    color: '#10b981',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: ''
                });
                window.activeTradePriceLines.push(lTp);

                window.activeRrBoxData = {
                    symbol: p.symbol,
                    side: p.side || 'LONG',
                    isShort,
                    entryPx,
                    initSlPrice,
                    initSlPct,
                    activeStopPrice,
                    isBe,
                    peakPx,
                    curPx,
                    tpPrice,
                    tpPct,
                    startCandleTime: candleTime || firstCandleTime,
                    endCandleTime: lastCandleTime,
                };
                if (typeof window.scheduleActiveTradeRrBoxOverlay === 'function') {
                    window.scheduleActiveTradeRrBoxOverlay();
                }
            }
        });

        // 2. Recopilar operaciones cerradas y trades del broker
        const trades = (window.rawBrokerTrades && window.rawBrokerTrades.length > 0)
            ? window.rawBrokerTrades
            : (Array.isArray(tradeHistoryLog) ? tradeHistoryLog : []);

        // Si no hay posición abierta para el símbolo actual, mostrar automáticamente el último trade realizado o Demo TP/SL (solo si Demo TP/SL está activo)
        const hasOpenForSymbol = openPositions.some(p => p && (p.symbol === currentSymbol || p.symbol === currentSymbol.replace('USDT', '/USDT')));
        if (isTpSlDemoEnabled && !hasOpenForSymbol && !window.currentlyInspectedTradeId) {
            const latestClosedForSymbol = trades.find(t => t && (t.symbol === currentSymbol || t.symbol === currentSymbol.replace('USDT', '/USDT')) && Number(t.entry_price || t.price || 0) > 0);
            if (latestClosedForSymbol && typeof candleSeries.createPriceLine === 'function') {
                const p = latestClosedForSymbol;
                const entryPx = Number(p.entry_price || p.price || 0);
                const isShort = (p.side || '').toUpperCase() === 'SHORT';
                const initSlPct = Number(p.initial_sl_pct || p.sl || 0.6);
                const stopNetPct = Number(p.current_stop_net_pct !== undefined ? p.current_stop_net_pct : 0.15);
                const isBe = p.be_armed === 1 || stopNetPct >= 0.0 || String(p.exit_reason || '').toLowerCase().includes('breakeven');
                const tpPct = Number(p.initial_tp_pct || p.tp || 2.1);

                const initSlPrice = isShort ? entryPx * (1 + initSlPct / 100) : entryPx * (1 - initSlPct / 100);
                const tpPrice = isShort ? entryPx * (1 - tpPct / 100) : entryPx * (1 + tpPct / 100);
                const exitPx = Number(p.exit_price || entryPx);
                const peakPx = Number(p.peak_price || Math.max(entryPx, exitPx, entryPx * 1.0041));
                const fmtDec = (entryPx < 10) ? 4 : 2;

                const openSec = toSeconds(p.opened_at || p.timestamp) || firstCandleTime;
                const closeSec = toSeconds(p.closed_at || p.timestamp) || lastCandleTime;
                const startCandleTime = findCandleTime(openSec, true) || firstCandleTime;
                const endCandleTime = findCandleTime(closeSec, true) || lastCandleTime;

                const isSlActuallyHit = isShort ? (exitPx >= initSlPrice * 0.9995) : (exitPx <= initSlPrice * 1.0005);
                const isProfit = (p.realized_pnl !== undefined ? Number(p.realized_pnl) >= 0 : (isShort ? exitPx <= entryPx : exitPx >= entryPx));
                const pnlVal = Number(p.realized_pnl !== undefined ? p.realized_pnl : (p.pnl || 0));
                const pnlStr = (pnlVal !== 0) ? ` (${pnlVal >= 0 ? '+' : ''}$${pnlVal.toFixed(2)})` : '';
                const exitReasonLabel = p.exit_reason || (isBe ? 'Candado BE' : (isSlActuallyHit ? 'Stop Loss' : 'Cierre'));

                const lEntry = candleSeries.createPriceLine({
                    price: entryPx,
                    color: '#38bdf8',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: ''
                });
                window.activeTradePriceLines.push(lEntry);

                const slStatusTag = isSlActuallyHit ? '[EJECUTADO]' : (isBe ? '[ANULADO POR BE]' : '[NO ALCANZADO]');
                const lInitSl = candleSeries.createPriceLine({
                    price: initSlPrice,
                    color: '#ef4444',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: ''
                });
                window.activeTradePriceLines.push(lInitSl);

                const lExit = candleSeries.createPriceLine({
                    price: exitPx,
                    color: isBe ? '#f59e0b' : (isProfit ? '#10b981' : '#ef4444'),
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: ''
                });
                window.activeTradePriceLines.push(lExit);

                if (peakPx > 0 && Math.abs(peakPx - entryPx) > 0.0001) {
                    const peakPct = isShort ? ((entryPx - peakPx) / entryPx) * 100 : ((peakPx - entryPx) / entryPx) * 100;
                    const lPeak = candleSeries.createPriceLine({
                        price: peakPx,
                        color: '#06b6d4',
                        lineWidth: 1.5,
                        lineStyle: LightweightCharts.LineStyle.Dotted,
                        axisLabelVisible: true,
                        title: ''
                    });
                    window.activeTradePriceLines.push(lPeak);
                }

                const lTp = candleSeries.createPriceLine({
                    price: tpPrice,
                    color: '#10b981',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: ''
                });
                window.activeTradePriceLines.push(lTp);

                window.activeRrBoxData = {
                    symbol: p.symbol,
                    side: p.side || 'LONG',
                    isShort,
                    entryPx,
                    initSlPrice,
                    initSlPct,
                    activeStopPrice: exitPx,
                    isClosed: true,
                    exitPx,
                    exitReason: exitReasonLabel,
                    realizedPnl: pnlVal,
                    isSlActuallyHit,
                    isBe,
                    peakPx,
                    curPx: exitPx,
                    tpPrice,
                    tpPct,
                    startCandleTime,
                    endCandleTime,
                };
                if (typeof window.scheduleActiveTradeRrBoxOverlay === 'function') {
                    window.scheduleActiveTradeRrBoxOverlay();
                }
            } else if (typeof candleSeries.createPriceLine === 'function' && candleData.length >= 2) {
                // Demo TP / SL proyectado sobre las últimas velas cuando el activo no tiene trade abierto ni cerrado
                const startIdx = Math.max(0, candleData.length - 14);
                const startCandleTime = candleData[startIdx].time;
                const endCandleTime = lastCandleTime;
                const entryPx = Number(candleData[startIdx].close || candleData[candleData.length - 1].close || 0);
                if (entryPx > 0) {
                    const isForex = String(currentSymbol || '').toUpperCase().includes('=X');
                    const initSlPct = isForex ? 0.18 : 0.60;
                    const tpPct = isForex ? 0.42 : 2.10;
                    const initSlPrice = entryPx * (1 - initSlPct / 100);
                    const tpPrice = entryPx * (1 + tpPct / 100);
                    const curPx = Number(candleData[candleData.length - 1].close || entryPx);
                    const peakPx = Math.max(entryPx, curPx, entryPx * (1 + (tpPct * 0.25) / 100));

                    const lEntry = candleSeries.createPriceLine({
                        price: entryPx,
                        color: '#38bdf8',
                        lineWidth: 2,
                        lineStyle: LightweightCharts.LineStyle.Dashed,
                        axisLabelVisible: true,
                        title: ''
                    });
                    window.activeTradePriceLines.push(lEntry);

                    const lInitSl = candleSeries.createPriceLine({
                        price: initSlPrice,
                        color: '#ef4444',
                        lineWidth: 2,
                        lineStyle: LightweightCharts.LineStyle.Dashed,
                        axisLabelVisible: true,
                        title: ''
                    });
                    window.activeTradePriceLines.push(lInitSl);

                    const lTp = candleSeries.createPriceLine({
                        price: tpPrice,
                        color: '#10b981',
                        lineWidth: 2,
                        lineStyle: LightweightCharts.LineStyle.Solid,
                        axisLabelVisible: true,
                        title: ''
                    });
                    window.activeTradePriceLines.push(lTp);

                    window.activeRrBoxData = {
                        symbol: currentSymbol,
                        side: 'LONG',
                        isShort: false,
                        entryPx,
                        initSlPrice,
                        initSlPct,
                        activeStopPrice: initSlPrice,
                        isBe: false,
                        peakPx,
                        curPx,
                        tpPrice,
                        tpPct,
                        startCandleTime,
                        endCandleTime,
                        isDemo: true,
                    };
                    if (typeof window.scheduleActiveTradeRrBoxOverlay === 'function') {
                        window.scheduleActiveTradeRrBoxOverlay();
                    }
                }
            }
        }

        if (isTradeMarkersEnabled) {
            trades.forEach(t => {
            if (!t || t.symbol !== currentSymbol) return;

            const isClosed = t.status === 'CLOSED' || t.signal === 'VENDER';
            const openSec = toSeconds(t.opened_at || (t.signal === 'COMPRAR' ? t.timestamp : null));
            const closeSec = toSeconds(t.closed_at || (t.signal === 'VENDER' ? t.timestamp : null));
            const entryPx = Number(t.entry_price || (t.signal === 'COMPRAR' ? t.price : 0));
            const pnl = Number(t.realized_pnl !== undefined ? t.realized_pnl : (t.pnl || 0));

            // Marca de Entrada (solo si no fue marcada previamente)
            if (openSec) {
                const entryTime = findCandleTime(openSec, false);
                const isTradeShort = (t.side || '').toUpperCase() === 'SHORT';
                if (entryTime) {
                    const pos = isTradeShort ? 'aboveBar' : 'belowBar';
                    const slotKey = `${entryTime}_${pos}`;
                    if (!usedSlots.has(slotKey) && !usedSlots.has(`${entryTime}_aboveBar`) && !usedSlots.has(`${entryTime}_belowBar`)) {
                        usedSlots.add(slotKey);
                        markers.push({
                            time: entryTime,
                            position: pos,
                            color: isTradeShort ? '#f43f5e' : '#10b981',
                            shape: isTradeShort ? 'arrowDown' : 'arrowUp',
                            text: isTradeShort ? `SHORT: ${formatPriceCompact(entryPx)}` : `LONG: ${formatPriceCompact(entryPx)}`,
                            size: 1,
                        });
                    }
                }
            }

            // Marca de Salida (S)
            if (isClosed && closeSec) {
                const exitTime = findCandleTime(closeSec, false);
                if (exitTime) {
                    const slotKey = `${exitTime}_aboveBar`;
                    if (!usedSlots.has(slotKey)) {
                        usedSlots.add(slotKey);
                        const isProfit = pnl >= 0;
                        const pnlSign = isProfit ? '+' : '';
                        markers.push({
                            time: exitTime,
                            position: 'aboveBar',
                            color: isProfit ? '#10b981' : '#f43f5e',
                            shape: 'arrowDown',
                            text: `S: ${pnlSign}$${pnl.toFixed(2)}`,
                            size: 1.2,
                        });
                    }
                }
            }
            });
        }
    }

    // 3. Patrones cuantitativos de velas detectados sobre las barras (Bulkowski en todo el historial visible)
    if (showPatterns && Array.isArray(candleData) && candleData.length >= 2) {
        const scanStart = 1;
        for (let i = scanStart; i < candleData.length; i++) {
            const cur = candleData[i];
            const prev = candleData[i - 1];
            const prev2 = i >= 2 ? candleData[i - 2] : null;
            const pat = detectCandlePatternDetails(cur, prev, prev2);
            if (pat && pat.icon && pat.icon !== '🕯️' && pat.name !== 'Vela Normal Alcista' && pat.name !== 'Vela Normal Bajista') {
                const isBull = pat.direction === 'bullish';
                const pos = isBull ? 'belowBar' : 'aboveBar';
                const slotKey = `${cur.time}_${pos}`;
                if (!usedSlots.has(slotKey)) {
                    usedSlots.add(slotKey);
                    markers.push({
                        time: cur.time,
                        position: pos,
                        color: isBull ? '#10b981' : (pat.direction === 'bearish' ? '#f43f5e' : '#f59e0b'),
                        shape: isBull ? 'arrowUp' : (pat.direction === 'bearish' ? 'arrowDown' : 'circle'),
                        text: `${pat.icon} ${pat.name.split(' ')[0]}`,
                        size: 1.1,
                    });
                }
            }
        }
    }

    // 4. Ordenar estrictamente de forma ascendente por `time` (Requisito de Lightweight Charts)
    markers.sort((a, b) => a.time - b.time);

    // 4. Inyectar marcadores en la serie de velas
    try {
        candleSeries.setMarkers(markers);
    } catch (err) {
        console.warn("No se pudieron dibujar marcadores en el gráfico:", err);
    }
};

window.scheduleActiveTradeRrBoxOverlay = function() {
    if (typeof window.renderActiveTradeRrBoxOverlay !== 'function') return;
    if (candleSeries && typeof candleSeries.applyOptions === 'function') {
        try { candleSeries.applyOptions({}); } catch (_) {}
    }
    window.renderActiveTradeRrBoxOverlay();
    if (typeof window.requestAnimationFrame === 'function') {
        window.requestAnimationFrame(() => window.renderActiveTradeRrBoxOverlay());
    }
    setTimeout(() => window.renderActiveTradeRrBoxOverlay(), 90);
};

window.renderActiveTradeRrBoxOverlay = function() {
    const rrEl = document.getElementById('active-trade-rr-box-overlay');
    if (!rrEl) return;
    const d = window.activeRrBoxData;
    if (!d || !candleSeries || !chart || typeof candleSeries.priceToCoordinate !== 'function') {
        rrEl.innerHTML = '';
        return;
    }

    const wContainer = rrEl.clientWidth || 720;
    const hContainer = rrEl.clientHeight || 354;
    const ts = chart.timeScale();

    let x1 = d.startCandleTime && typeof ts.timeToCoordinate === 'function' ? ts.timeToCoordinate(d.startCandleTime) : null;
    let x2 = d.endCandleTime && typeof ts.timeToCoordinate === 'function' ? ts.timeToCoordinate(d.endCandleTime) : null;

    if (x1 === null || !Number.isFinite(x1) || x2 === null || !Number.isFinite(x2)) {
        rrEl.innerHTML = '';
        return;
    }

    // Determinar ancho de barra para enmarcar completamente las velas extremas (Entrada y Salida)
    let barW = 14;
    const rawCandles = window.lastRawMarketData;
    if (Array.isArray(rawCandles) && rawCandles.length >= 2 && typeof ts.timeToCoordinate === 'function') {
        const c0 = ts.timeToCoordinate(rawCandles[rawCandles.length - 1].time);
        const c1 = ts.timeToCoordinate(rawCandles[rawCandles.length - 2].time);
        if (c0 !== null && c1 !== null && Number.isFinite(c0) && Number.isFinite(c1)) {
            barW = Math.max(6, Math.abs(c0 - c1));
        }
    }
    const halfBar = Math.round(barW / 2);

    // Respetar estrictamente desde la vela exacta de Entrada (x1) hasta la vela exacta de Salida/Actual (x2),
    // abrazando la vela completa tanto en la apertura de entrada como en el cierre de salida
    const leftX = Math.round(Math.max(0, Math.min(x1, x2) - halfBar));
    const rightX = Math.round(Math.min(wContainer, Math.max(x1, x2) + halfBar));
    const boxW = Math.max(12, rightX - leftX);

    const yEntryRaw = candleSeries.priceToCoordinate(d.entryPx);
    if (yEntryRaw === null || !Number.isFinite(yEntryRaw)) {
        rrEl.innerHTML = '';
        return;
    }
    const yEntry = Math.round(Math.max(18, Math.min(hContainer - 18, yEntryRaw)));

    const ySlRaw = candleSeries.priceToCoordinate(d.initSlPrice);
    const yTpRaw = candleSeries.priceToCoordinate(d.tpPrice);
    const yPeakRaw = candleSeries.priceToCoordinate(d.peakPx || d.entryPx);
    const yExitRaw = (d.exitPx && Number(d.exitPx) > 0) ? candleSeries.priceToCoordinate(d.exitPx) : null;
    const yBeRaw = candleSeries.priceToCoordinate(d.activeStopPrice || d.entryPx);

    // Zona Verde (Entrada -> Pico alcanzado y proyección hacia TP)
    const yTopTarget = (yTpRaw !== null && Number.isFinite(yTpRaw))
        ? Math.round(Math.max(4, Math.min(hContainer - 16, yTpRaw)))
        : 4;
    const yPeak = (yPeakRaw !== null && Number.isFinite(yPeakRaw))
        ? Math.round(Math.max(4, Math.min(yEntry, yPeakRaw)))
        : Math.max(4, yEntry - 26);

    const greenTop = d.isShort ? yEntry : Math.min(yTopTarget, yPeak);
    const greenBottom = d.isShort ? Math.max(yTopTarget, yPeak) : yEntry;
    const greenH = Math.max(20, greenBottom - greenTop);

    // Zona Roja Intensa del Viejo Stop Loss (Entrada -> SL Inicial exacto)
    let ySlBound = (ySlRaw !== null && Number.isFinite(ySlRaw))
        ? Math.round(Math.max(6, Math.min(hContainer - 2, ySlRaw)))
        : (d.isShort ? Math.max(6, yEntry - 42) : Math.min(hContainer - 2, yEntry + 42));
    if (!d.isShort && ySlBound - yEntry < 22) {
        ySlBound = Math.min(hContainer - 2, yEntry + 26);
    } else if (d.isShort && yEntry - ySlBound < 22) {
        ySlBound = Math.max(6, yEntry - 26);
    }
    const redTop = d.isShort ? ySlBound : yEntry;
    const redBottom = d.isShort ? yEntry : ySlBound;
    const redH = Math.max(22, redBottom - redTop);

    // Sub-caja cian/esmeralda de ganancia ya alcanzada hasta el Pico
    const peakTop = d.isShort ? yEntry : yPeak;
    const peakH = Math.max(4, Math.abs(yEntry - yPeak));

    // Coordenada del Candado Breakeven
    const yBe = (yBeRaw !== null && Number.isFinite(yBeRaw)) ? Math.round(yBeRaw) : yEntry;
    const rrRatio = (d.tpPct / Math.max(0.05, d.initSlPct)).toFixed(2);
    const peakPct = d.isShort
        ? (((d.entryPx - d.peakPx) / d.entryPx) * 100).toFixed(2)
        : (((d.peakPx - d.entryPx) / d.entryPx) * 100).toFixed(2);

    const fmtPx = (val) => {
        const n = Number(val) || 0;
        if (n >= 1000) return '$' + Math.round(n).toLocaleString('en-US');
        if (n >= 10) return '$' + n.toFixed(2);
        if (n >= 1) return '$' + n.toFixed(3);
        return '$' + n.toFixed(4);
    };
    const fmtDiff = (val) => {
        const n = Number(val) || 0;
        if (n >= 10) return '$' + n.toFixed(1);
        if (n >= 1) return '$' + n.toFixed(2);
        return '$' + n.toFixed(4);
    };

    const slBadgeStatus = d.isClosed
        ? (d.isSlActuallyHit ? '[Ejecutado]' : '[No alcanzado]')
        : (d.isBe ? '[Anulado por BE]' : '[Activo]');

    rrEl.innerHTML = `
        <!-- CAJA VERDE TRANSLÚCIDA CON DESENFOQUE (TAKE PROFIT / ZONA GANADORA) -->
        <div style="
            position:absolute;
            left:${leftX}px;
            top:${greenTop}px;
            width:${boxW}px;
            height:${greenH}px;
            background:rgba(16, 185, 129, 0.16);
            border:1.5px solid rgba(16, 185, 129, 0.85);
            border-bottom:none;
            border-radius:4px 4px 0 0;
            backdrop-filter:blur(1.5px);
            -webkit-backdrop-filter:blur(1.5px);
            box-sizing:border-box;
            pointer-events:none;
        "></div>

        <!-- FRANJA CIAN DE GANANCIA RECORRIDA HASTA EL PICO -->
        ${(peakH > 4) ? `
        <div style="
            position:absolute;
            left:${leftX}px;
            top:${peakTop}px;
            width:${boxW}px;
            height:${peakH}px;
            background:rgba(6, 182, 212, 0.18);
            border-top:1.5px dashed #22d3ee;
            box-sizing:border-box;
            pointer-events:none;
        "></div>` : ''}

        <!-- LÍNEA CELESTE DISCONTINUA DE ENTRADA -->
        <div style="
            position:absolute;
            left:${leftX}px;
            top:${yEntry}px;
            width:${boxW}px;
            height:0px;
            border-top:1.5px dashed #38bdf8;
            box-sizing:border-box;
            pointer-events:none;
        "></div>

        <!-- LÍNEA ÁMBAR DEL CANDADO BREAKEVEN -->
        ${d.isBe ? `
        <div style="
            position:absolute;
            left:${leftX}px;
            top:${yBe}px;
            width:${boxW}px;
            height:0px;
            border-top:2px solid #f59e0b;
            pointer-events:none;
        "></div>` : ''}

        <!-- LÍNEA SÓLIDA DE SALIDA REAL EJECUTADA -->
        ${(d.isClosed && yExitRaw !== null && Number.isFinite(yExitRaw)) ? `
        <div style="
            position:absolute;
            left:${leftX}px;
            top:${Math.round(yExitRaw)}px;
            width:${boxW}px;
            height:0px;
            border-top:2px solid ${(d.realizedPnl >= 0 || (d.isShort ? d.exitPx <= d.entryPx : d.exitPx >= d.entryPx)) ? '#10b981' : (d.isBe ? '#f59e0b' : '#ef4444')};
            z-index:5;
            pointer-events:none;
        "></div>` : ''}

        <!-- CAJA ROJA TRANSLÚCIDA CON DESENFOQUE (STOP LOSS INICIAL) -->
        <div style="
            position:absolute;
            left:${leftX}px;
            top:${redTop}px;
            width:${boxW}px;
            height:${redH}px;
            background:rgba(239, 68, 68, 0.20);
            border:1.5px solid rgba(239, 68, 68, 0.85);
            border-top:none;
            border-radius:0 0 4px 4px;
            backdrop-filter:blur(1.5px);
            -webkit-backdrop-filter:blur(1.5px);
            box-sizing:border-box;
            pointer-events:none;
        "></div>
    `;

    // Actualizar la tira de telemetría de parámetros debajo de la ventana (fuera de las velas)
    const elEntry = document.getElementById('tel-entry');
    const elSl = document.getElementById('tel-sl');
    const elTp = document.getElementById('tel-tp');
    const elRr = document.getElementById('tel-rr');
    const elPeak = document.getElementById('tel-peak');
    const elStatus = document.getElementById('tel-status');

    if (elEntry) elEntry.textContent = `🔵 Entrada: ${fmtPx(d.entryPx)}`;
    if (elSl) elSl.textContent = `🛑 ${d.isShort ? 'SL Corto' : 'SL'}: ${fmtPx(d.initSlPrice)} (-${d.initSlPct.toFixed(2)}%)`;
    if (elTp) elTp.textContent = `🎯 TP: +${d.tpPct.toFixed(1)}% (${fmtPx(d.tpPrice)})`;
    if (elRr) elRr.textContent = `⚖️ R:R 1:${rrRatio}`;
    if (elPeak) elPeak.textContent = `🏔️ Pico: ${fmtPx(d.peakPx || d.entryPx)} (+${peakPct}%)`;
    if (elStatus) {
        if (d.isClosed) {
            const isProfit = (d.realizedPnl !== undefined && d.realizedPnl !== null)
                ? Number(d.realizedPnl) >= 0
                : (d.isShort ? d.exitPx <= d.entryPx : d.exitPx >= d.entryPx);
            elStatus.className = isProfit
                ? 'px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700 shrink-0'
                : 'px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-700 shrink-0';
            elStatus.textContent = isProfit ? `🏁 Cerrado TP (+${fmtPx(d.realizedPnl || 0)})` : `🛑 Cerrado SL ${slBadgeStatus}`;
        } else if (d.isBe) {
            elStatus.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-700 shrink-0';
            elStatus.textContent = `🛡️ BE Protegido [${fmtPx(d.activeStopPrice)}]`;
        } else if (d.isDemo) {
            elStatus.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-950 text-indigo-300 border border-indigo-700 shrink-0';
            elStatus.textContent = '🧪 Demo TP/SL Activo';
        } else {
            elStatus.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950 text-sky-300 border border-sky-700 shrink-0';
            elStatus.textContent = `⚡ Posición Activa [${d.side || 'LONG'}]`;
        }
    }
};

if (chart && typeof chart.timeScale === 'function') {
    try {
        chart.timeScale().subscribeVisibleTimeRangeChange(() => {
            if (typeof window.renderActiveTradeRrBoxOverlay === 'function') {
                window.renderActiveTradeRrBoxOverlay();
            }
        });
        chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
            if (typeof window.renderActiveTradeRrBoxOverlay === 'function') {
                window.renderActiveTradeRrBoxOverlay();
            }
        });
    } catch (_) {}
}

window.currentlyInspectedTradeId = null;

window.destildarTradeInspection = function() {
    window.currentlyInspectedTradeId = null;

    // 1. Limpiar líneas anteriores de precio
    if (window.activeTradePriceLines && candleSeries) {
        window.activeTradePriceLines.forEach(l => {
            try { candleSeries.removePriceLine(l); } catch(e) {}
        });
        window.activeTradePriceLines = [];
    }
    window.activeRrBoxData = null;
    const rrEl = document.getElementById('active-trade-rr-box-overlay');
    if (rrEl) rrEl.innerHTML = '';

    const elEntry = document.getElementById('tel-entry');
    const elSl = document.getElementById('tel-sl');
    const elTp = document.getElementById('tel-tp');
    const elRr = document.getElementById('tel-rr');
    const elPeak = document.getElementById('tel-peak');
    const elStatus = document.getElementById('tel-status');
    if (elEntry) elEntry.textContent = '🔵 Entrada: ---';
    if (elSl) elSl.textContent = '🛑 SL: ---';
    if (elTp) elTp.textContent = '🎯 TP: ---';
    if (elRr) elRr.textContent = '⚖️ R:R: ---';
    if (elPeak) elPeak.textContent = '🏔️ Pico: ---';
    if (elStatus) {
        elStatus.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700 shrink-0';
        elStatus.textContent = 'En espera';
    }

    // 2. Restaurar zoom al tiempo real (últimas velas) y redibujar posición activa en vivo si existe
    if (chart && typeof chart.timeScale === 'function') {
        chart.timeScale().resetTimeScale();
    }
    if (typeof window.updateChartTradeMarkers === 'function') {
        window.updateChartTradeMarkers();
    }

    // 3. Quitar blureo de filas de la tabla de operaciones
    const tbody = document.getElementById('tradeHistoryBody');
    if (tbody) {
        Array.from(tbody.children).forEach(tr => {
            tr.style.filter = '';
            tr.style.opacity = '';
            tr.classList.remove('ring-1', 'ring-amber-500/80', 'bg-amber-950/40');
            const btn = tr.querySelector('.btn-inspect-trade');
            if (btn) {
                btn.innerHTML = '🔍 Ver';
                btn.className = 'btn-inspect-trade text-xs text-amber-400 hover:text-amber-300 ml-1.5 px-1.5 py-0.5 rounded hover:bg-slate-800 border border-amber-500/30 font-mono cursor-pointer transition';
                btn.title = 'Auditar recorrido de entrada y salida en el gráfico de velas';
            }
        });
    }

    // 4. Eliminar banner flotante de auditoría si existe
    const banner = document.getElementById('auditBannerFloating');
    if (banner) banner.remove();

    if (typeof logToTerminal === 'function') {
        logToTerminal('↩️ [AUDITORÍA DESMARCADA] Gráfico restablecido al flujo de mercado en vivo.', 'info');
    }
};

window.inspectClosedTradeOnMainChart = function(tradeId) {
    if (!tradeId || !candleSeries) return;

    const cleanId = String(tradeId).replace(/_(buy|sell)$/, '');

    // Si ya estamos viendo este mismo trade, la acción es DESTILDAR (cancelar y volver a live)
    if (window.currentlyInspectedTradeId === cleanId) {
        window.destildarTradeInspection();
        return;
    }

    const trades = (window.rawBrokerTrades && window.rawBrokerTrades.length > 0)
        ? window.rawBrokerTrades
        : (Array.isArray(tradeHistoryLog) ? tradeHistoryLog : []);
    const t = trades.find(x => {
        const id1 = String(x.id || '').replace(/_(buy|sell)$/, '');
        return id1 === cleanId;
    });
    if (!t) return;

    window.currentlyInspectedTradeId = cleanId;

    // 1. Limpiar líneas anteriores
    if (!window.activeTradePriceLines) window.activeTradePriceLines = [];
    window.activeTradePriceLines.forEach(l => {
        try { candleSeries.removePriceLine(l); } catch(e) {}
    });
    window.activeTradePriceLines = [];

    const p0 = Number(t.entry_price || t.price || 0);
    const ps = Number(t.exit_price || 0);
    const pnl = Number(t.realized_pnl !== undefined ? t.realized_pnl : (t.pnl || 0));
    const isShort = String(t.side || '').toUpperCase() === 'SHORT';
    const slPct = Number(t.initial_sl_pct || t.sl || 0.6);
    const tpPct = Number(t.initial_tp_pct || t.tp || 2.1);
    const slPx = p0 > 0 ? (isShort ? p0 * (1 + slPct / 100) : p0 * (1 - slPct / 100)) : 0;
    const tpPx = p0 > 0 ? (isShort ? p0 * (1 - tpPct / 100) : p0 * (1 + tpPct / 100)) : 0;
    const peakPx = Number(t.peak_price || Math.max(p0, ps));
    const isBe = t.be_armed === 1 || String(t.exit_reason || '').toLowerCase().includes('breakeven');

    if (p0 > 0 && typeof candleSeries.createPriceLine === 'function') {
        const fmtDec = (p0 < 10) ? 4 : 2;
        const isSlActuallyHit = isShort ? (ps >= slPx * 0.9995) : (ps <= slPx * 1.0005);
        const slStatusTag = isSlActuallyHit ? '[EJECUTADO]' : (isBe ? '[ANULADO POR BE]' : '[NO ALCANZADO]');

        const lEntry = candleSeries.createPriceLine({
            price: p0,
            color: '#38bdf8',
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: ''
        });
        window.activeTradePriceLines.push(lEntry);

        if (slPx > 0) {
            const lSl = candleSeries.createPriceLine({
                price: slPx,
                color: '#ef4444',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: ''
            });
            window.activeTradePriceLines.push(lSl);
        }

        if (tpPx > 0) {
            const lTp = candleSeries.createPriceLine({
                price: tpPx,
                color: '#10b981',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: true,
                title: ''
            });
            window.activeTradePriceLines.push(lTp);
        }

        if (peakPx > 0 && Math.abs(peakPx - p0) > 0.0001) {
            const peakPct = isShort ? ((p0 - peakPx) / p0) * 100 : ((peakPx - p0) / p0) * 100;
            const lPeak = candleSeries.createPriceLine({
                price: peakPx,
                color: '#06b6d4',
                lineWidth: 1.5,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: true,
                title: ''
            });
            window.activeTradePriceLines.push(lPeak);
        }
    }

    if (ps > 0 && typeof candleSeries.createPriceLine === 'function') {
        const fmtDecExit = (ps < 10) ? 4 : 2;
        const lExit = candleSeries.createPriceLine({
            price: ps,
            color: isBe ? '#f59e0b' : (pnl >= 0 ? '#10b981' : '#ef4444'),
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            axisLabelVisible: true,
            title: ''
        });
        window.activeTradePriceLines.push(lExit);
    }

    // 2. Centrar vista en el rango temporal del trade y dibujar rectángulo R:R
    const toSec = (dt) => (typeof window.toUtcSeconds === 'function') ? window.toUtcSeconds(dt) : null;
    const t0 = toSec(t.opened_at || t.timestamp);
    const t1 = toSec(t.closed_at || t.timestamp);

    const candleData = window.lastRawMarketData || [];
    const firstC = candleData.length > 0 ? candleData[0].time : t0;
    const lastC = candleData.length > 0 ? candleData[candleData.length - 1].time : t1;

    const startCandleTime = (typeof window.findCandleTimeForTimestamp === 'function')
        ? (window.findCandleTimeForTimestamp(t0, candleData, true) || firstC)
        : (t0 || firstC);
    const endCandleTime = (typeof window.findCandleTimeForTimestamp === 'function')
        ? (window.findCandleTimeForTimestamp(t1, candleData, false) || lastC)
        : (t1 || lastC);

    if (chart && typeof chart.timeScale === 'function' && t0 && t1) {
        const pad = Math.max(3600, (t1 - t0) * 0.4);
        chart.timeScale().setVisibleRange({ from: t0 - pad, to: t1 + pad });
    }

    const isSlActuallyHitTrade = isShort ? (ps >= slPx * 0.9995) : (ps <= slPx * 1.0005);
    window.activeRrBoxData = {
        symbol: t.symbol || currentSymbol,
        side: t.side || 'LONG',
        isShort,
        entryPx: p0,
        initSlPrice: slPx,
        initSlPct: slPct,
        activeStopPrice: ps || p0,
        isClosed: true,
        exitPx: ps,
        exitReason: t.exit_reason || 'CIERRE',
        realizedPnl: pnl,
        isSlActuallyHit: isSlActuallyHitTrade,
        isBe,
        peakPx: peakPx || p0,
        curPx: ps || p0,
        tpPrice: tpPx,
        tpPct,
        startCandleTime,
        endCandleTime,
    };
    if (typeof window.scheduleActiveTradeRrBoxOverlay === 'function') {
        window.scheduleActiveTradeRrBoxOverlay();
    }

    // 3. Blurear las demás filas de la tabla de operaciones para destacar la inspeccionada
    const tbody = document.getElementById('tradeHistoryBody');
    if (tbody) {
        Array.from(tbody.children).forEach(tr => {
            const btn = tr.querySelector('.btn-inspect-trade');
            const rowTradeId = btn ? String(btn.getAttribute('data-trade-id') || '').replace(/_(buy|sell)$/, '') : null;
            if (rowTradeId === cleanId) {
                tr.style.filter = 'none';
                tr.style.opacity = '1';
                tr.classList.add('ring-1', 'ring-amber-500/80', 'bg-amber-950/40');
                if (btn) {
                    btn.innerHTML = '✓ Viendo (Destildar)';
                    btn.className = 'btn-inspect-trade text-xs bg-amber-500/30 text-amber-300 font-bold ml-1.5 px-2 py-0.5 rounded border border-amber-400 font-mono cursor-pointer shadow-lg ring-1 ring-amber-400/80 animate-pulse';
                    btn.title = 'Hacer clic para destildar y volver al gráfico en vivo';
                }
            } else {
                tr.style.filter = 'blur(1.5px)';
                tr.style.opacity = '0.35';
                tr.style.transition = 'filter 0.3s ease, opacity 0.3s ease';
                tr.classList.remove('ring-1', 'ring-amber-500/80', 'bg-amber-950/40');
                if (btn) {
                    btn.innerHTML = '🔍 Ver';
                    btn.className = 'btn-inspect-trade text-xs text-amber-400 hover:text-amber-300 ml-1.5 px-1.5 py-0.5 rounded hover:bg-slate-800 border border-amber-500/30 font-mono cursor-pointer transition';
                    btn.title = 'Auditar recorrido de entrada y salida en el gráfico de velas';
                }
            }
        });
    }

    // 4. Banner flotante con botón directo para Destildar
    let banner = document.getElementById('auditBannerFloating');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'auditBannerFloating';
        banner.className = 'fixed top-20 left-1/2 -translate-x-1/2 z-50 bg-amber-950/95 border border-amber-500 text-amber-200 px-4 py-2 rounded-xl shadow-2xl backdrop-blur-md flex items-center gap-3 font-mono text-xs animate-fadeIn';
        document.body.appendChild(banner);
    }
    banner.innerHTML = `
        <span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
        <span>Auditoría de Trade: <strong class="text-white">${t.symbol}</strong> ($${p0} ➜ $${ps})</span>
        <button type="button" onclick="window.destildarTradeInspection()" class="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-2.5 py-0.5 rounded text-xs cursor-pointer shadow transition hover:scale-105">
            ✕ Destildar (Volver a En Vivo)
        </button>
    `;

    if (typeof logToTerminal === 'function') {
        logToTerminal(`🕵️ [AUDITORÍA DE TRADE] ${t.symbol} | Entrada: $${p0} | Salida: $${ps} | PnL: ${pnl >= 0 ? '+' : ''}$${pnl.toFixed(4)} | Haz clic en 'Destildar' para volver a velas en vivo.`, pnl >= 0 ? 'success' : 'warn');
    }
};

function getCurrency(symbol) {
    if (tradingGuards && typeof tradingGuards.getCurrency === 'function') {
        return tradingGuards.getCurrency(symbol);
    }
    if (!symbol) return 'USD';
    if (symbol.includes('USDT')) return 'USDT';
    if (symbol.includes('.BA')) return 'ARS';
    return 'USD';
}

// Resolutor canónico multi-alias para auto-ruteo infalible entre el Monitor y los Tickers del Dashboard
function resolveSymbol(candAsset) {
    if (!candAsset) return null;
    const raw = String(candAsset).trim();
    const upper = raw.toUpperCase();
    const clean = upper.replace(/[^A-Z0-9=^.]/g, '');

    const ALIASES = {
        // Cripto (Normaliza BTCUSD, BTCUSDT, BTC, etc. hacia BTC/USDT)
        'BTCUSD': 'BTC/USDT',
        'BTCUSDT': 'BTC/USDT',
        'BTC': 'BTC/USDT',
        'BITCOIN': 'BTC/USDT',
        'ETHUSD': 'ETH/USDT',
        'ETHUSDT': 'ETH/USDT',
        'ETH': 'ETH/USDT',
        'ETHEREUM': 'ETH/USDT',
        'SOLUSD': 'SOL/USDT',
        'SOLUSDT': 'SOL/USDT',
        'SOL': 'SOL/USDT',
        'SOLANA': 'SOL/USDT',
        'BNBUSD': 'BNB/USDT',
        'BNBUSDT': 'BNB/USDT',
        'BNB': 'BNB/USDT',
        'BINANCE': 'BNB/USDT',
        'BINANCECOIN': 'BNB/USDT',
        'XRPUSD': 'XRP/USDT',
        'XRPUSDT': 'XRP/USDT',
        'XRP': 'XRP/USDT',
        'RIPPLE': 'XRP/USDT',

        // Commodities y Materias Primas
        'GOLD': 'GC=F',
        'ORO': 'GC=F',
        'XAUUSD': 'GC=F',
        'XAU': 'GC=F',
        'GC': 'GC=F',
        'OIL': 'CL=F',
        'PETROLEO': 'CL=F',
        'WTI': 'CL=F',
        'CRUDE': 'CL=F',
        'CL': 'CL=F',
        'SILVER': 'SI=F',
        'PLATA': 'SI=F',
        'XAGUSD': 'SI=F',
        'SI': 'SI=F',
        'GAS': 'NG=F',
        'NATGAS': 'NG=F',
        'NG': 'NG=F',

        // Índices y Bonos Soberanos
        'SP500': 'SPY',
        'SPX': '^GSPC',
        'S&P500': 'SPY',
        'S&P 500': 'SPY',
        'GSPC': '^GSPC',
        '^GSPC': '^GSPC',
        'SPY': 'SPY',
        'NASDAQ': 'QQQ',
        'NAS100': 'QQQ',
        'NDX': 'QQQ',
        'QQQ': 'QQQ',
        'TLT': 'TLT',
        'BONOS': 'TLT',

        // Acciones y Tech
        'ALIBABA': 'BABA',
        'BABA': 'BABA',
        'NVIDIA': 'NVDA',
        'NVDA': 'NVDA',
        'APPLE': 'AAPL',
        'AAPL': 'AAPL',
        'AMD': 'AMD',
        'BROADCOM': 'AVGO',
        'AVGO': 'AVGO',
        'META': 'META',
        'TESLA': 'TSLA',
        'TSLA': 'TSLA',
        'MICROSOFT': 'MSFT',
        'MSFT': 'MSFT',

        // Mercado Argentino
        'GGAL': 'GGAL.BA',
        'GALICIA': 'GGAL.BA',
        'YPF': 'YPFD.BA',
        'YPFD': 'YPFD.BA',
        'PAMP': 'PAMP.BA',
        'PAMPA': 'PAMP.BA',
        'BMA': 'BMA.BA',
        'MACRO': 'BMA.BA',
        'ALUA': 'ALUA.BA',
        'ALUAR': 'ALUA.BA',
        'TXAR': 'TXAR.BA',
        'TERNIUM': 'TXAR.BA'
    };

    if (ALIASES[upper]) return ALIASES[upper];
    if (ALIASES[clean]) return ALIASES[clean];

    // Búsqueda heurística directa en las opciones de symbolSelect
    const selectEl = document.getElementById('symbolSelect');
    if (selectEl) {
        for (const opt of selectEl.options) {
            const optVal = opt.value;
            const optUpper = optVal.toUpperCase();
            const optClean = optVal.replace(/[^A-Z0-9=^.]/g, '').toUpperCase();
            const optBase = optVal.split('/')[0].toUpperCase();

            if (optVal === raw || optUpper === upper) return optVal;
            if (optClean === clean) return optVal;
            if (optBase === clean || optBase === upper) return optVal;
            if (clean.startsWith(optBase) && (clean.endsWith('USD') || clean.endsWith('USDT'))) return optVal;
            if (upper.includes(optBase) && optBase.length >= 3) return optVal;
        }
    }
    return null;
}

// Detección de sesiones bursátiles y horarios de mercado activos
function isAssetMarketOpen(symbol) {
    if (tradingGuards && typeof tradingGuards.isAssetMarketOpenAt === 'function') {
        return tradingGuards.isAssetMarketOpenAt(symbol, new Date());
    }
    return true;
}

// Helpers de Única Fuente de Verdad para la Posición (Bloque 1)
function getOpenPosition() {
    if (portfolio.position && typeof portfolio.position.qty === 'number' && portfolio.position.qty > 0.0001) {
        // Migración a convención stopNetPct firmado neto (Bloque 1)
        if (portfolio.position.stopNetPct === undefined || portfolio.position.stopNetPct === null) {
            if (portfolio.position.beArmed) {
                portfolio.position.stopNetPct = Math.max(-Math.abs(portfolio.position.slEffPct ?? portfolio.position.sl ?? 1.0), +0.05);
            } else {
                portfolio.position.stopNetPct = -Math.abs(portfolio.position.slEffPct ?? portfolio.position.sl ?? 1.0);
            }
            delete portfolio.position.slEffPct;
        }
        return portfolio.position;
    }
    return null;
}

function hasOpenPosition() {
    return !!getOpenPosition();
}

// Matemática unificada de PnL y salida neta (R1)
function netPctAtPrice(pos, price, feeRate) {
    const effectiveFeeRate = (pos && typeof pos.feeRate === 'number')
        ? pos.feeRate
        : (feeRate !== undefined ? feeRate : getBrokerFeeRate(pos ? pos.symbol : ''));
    if (tradingGuards && typeof tradingGuards.netPctAtPrice === 'function') {
        return tradingGuards.netPctAtPrice(pos, price, effectiveFeeRate);
    }
    return 0;
}

// Tests puros de consola para verificación matemática de riesgo (R1 item 6)
window.testRiskMath = function() {
    const feeRate = 0.10;
    const tradeAmount = 100;
    const feeAmount = tradeAmount * (feeRate / 100);
    const capitalNeto = tradeAmount - feeAmount;
    const testPos = {
        qty: capitalNeto / 100, // 0.999
        entryPrice: 100,
        costBasis: tradeAmount, // 100
        feeRate: feeRate,
        tp: 1.5,
        sl: 1.0,
        stopNetPct: -1.0,
        beArmed: false,
        trailActive: false,
        trailPct: 0.5,
        peakPrice: 100
    };

    // Armar BE
    testPos.beArmed = true;
    testPos.stopNetPct = Math.max(testPos.stopNetPct, +0.05);

    // 1. Evaluar a 100.30 tras armar BE
    const netAt100_30 = netPctAtPrice(testPos, 100.30, feeRate);
    const stopsAt100_30 = netAt100_30 <= testPos.stopNetPct;

    // 2. Precio cae a 100.05
    const netAt100_05 = netPctAtPrice(testPos, 100.05, feeRate);
    const stopsAt100_05 = netAt100_05 <= testPos.stopNetPct;

    const pass = !stopsAt100_30 && stopsAt100_05;
    console.log(`[TEST R1] A 100.30: Neto=${netAt100_30.toFixed(4)}% vs Stop=${testPos.stopNetPct}%. ¿Dispara? ${stopsAt100_30} (Esperado: false)`);
    console.log(`[TEST R1] A 100.05: Neto=${netAt100_05.toFixed(4)}% vs Stop=${testPos.stopNetPct}%. ¿Dispara? ${stopsAt100_05} (Esperado: true)`);
    console.log(`[TEST R1] Resultado general: ${pass ? 'PASÓ ✅' : 'FALLÓ ❌'}`);
    return pass;
};

// Mecanismo de Cordura (Sanity Check) para evitar Save Corruption
if (!portfolio.balances) portfolio.balances = { USDT: 0, USD: 0, ARS: 0 };
if (!portfolio.deposits) portfolio.deposits = { USDT: 0, USD: 0, ARS: 0 };
if (!portfolio.vault) portfolio.vault = { USDT: 0.0, USD: 0.0, ARS: 0.0 };
if (typeof portfolio.balances.USDT !== 'number' || isNaN(portfolio.balances.USDT)) portfolio.balances.USDT = 0;
if (typeof portfolio.balances.USD !== 'number' || isNaN(portfolio.balances.USD)) portfolio.balances.USD = 0;
if (typeof portfolio.balances.ARS !== 'number' || isNaN(portfolio.balances.ARS)) portfolio.balances.ARS = 0;
if (typeof portfolio.deposits.USDT !== 'number' || isNaN(portfolio.deposits.USDT)) portfolio.deposits.USDT = 0;
if (typeof portfolio.deposits.USD !== 'number' || isNaN(portfolio.deposits.USD)) portfolio.deposits.USD = 0;
if (typeof portfolio.deposits.ARS !== 'number' || isNaN(portfolio.deposits.ARS)) portfolio.deposits.ARS = 0;
if (typeof portfolio.vault.USDT !== 'number' || isNaN(portfolio.vault.USDT)) portfolio.vault.USDT = 0.0;
if (typeof portfolio.vault.USD !== 'number' || isNaN(portfolio.vault.USD)) portfolio.vault.USD = 0.0;
if (typeof portfolio.vault.ARS !== 'number' || isNaN(portfolio.vault.ARS)) portfolio.vault.ARS = 0.0;
if (typeof portfolio.ASSET !== 'number' || isNaN(portfolio.ASSET)) portfolio.ASSET = 0;
if (typeof portfolio.entryPrice !== 'number' || isNaN(portfolio.entryPrice)) portfolio.entryPrice = 0;
if (typeof portfolio.totalFeesPaid !== 'number' || isNaN(portfolio.totalFeesPaid)) portfolio.totalFeesPaid = 0;

function getVaultBalance(cur = getCurrency(currentSymbol)) {
    return (portfolio.vault && Number.isFinite(portfolio.vault[cur])) ? portfolio.vault[cur] : 0.0;
}

if (!Object.getOwnPropertyDescriptor(portfolio, 'VAULT')) {
    Object.defineProperty(portfolio, 'VAULT', {
        get() { return getVaultBalance(); },
        set(val) {
            if (!portfolio.vault) portfolio.vault = { USDT: 0.0, USD: 0.0, ARS: 0.0 };
            const cur = getCurrency(currentSymbol);
            portfolio.vault[cur] = val;
        },
        configurable: true,
        enumerable: true
    });
}

// Migración y compatibilidad con el Modelo de Posición Estructurado
if (!portfolio.position && portfolio.ASSET > 0.0001) {
    const cur = getCurrency(currentSymbol);
    portfolio.position = {
        symbol: currentSymbol,
        baseCoin: currentSymbol.split('/')[0],
        currency: cur,
        qty: portfolio.ASSET,
        entryPrice: portfolio.entryPrice || 0,
        costBasis: portfolio.ASSET * (portfolio.entryPrice || 0),
        tp: 1.5,
        sl: 1.0,
        openedAt: new Date().toISOString()
    };
}

// Al cargar la página, si existe posición abierta, forzar selector y activo al de la posición (Bloque 1)
const initialOpenPos = getOpenPosition();
if (initialOpenPos && initialOpenPos.symbol) {
    currentSymbol = initialOpenPos.symbol;
    if (symbolSelect) symbolSelect.value = initialOpenPos.symbol;
}

// --- MONITOR DE RIESGO INDEPENDIENTE (R2, R3) ---
window.positionAssetPrice = null;
window.positionAssetPriceTs = 0;
let riskTickInFlight = false;
let manualCloseInFlight = false;
let riskFeedFailures = 0;
let staleFeedStartTime = 0; // ms: inicio de periodo estancado con mercado abierto
let lastMarketClosedLoggedSymbol = ''; // Símbolo para registrar una sola vez aviso de mercado cerrado
let lastRiskStaleLogTs = 0; // ms
let lastRiskFailAlarmTs = 0; // ms
let lastRiskCatchLogTs = 0; // ms
let lastTrailingLogTs = 0; // s
let lastPortfolioSaveTs = 0; // ms

async function riskTick() {
    const pos = getOpenPosition();
    if (!pos) {
        riskFeedFailures = 0;
        staleFeedStartTime = 0;
        return;
    }
    if (isExecutingTrade) return;
    if (riskTickInFlight) return;
    riskTickInFlight = true;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);

    try {
        const res = await fetch(`${API_BASE_URL}/api/market/price?symbol=${encodeURIComponent(pos.symbol)}`, {
            headers: apiAuthHeaders(),
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (!res.ok) {
            riskFeedFailures++;
            throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();

        // 3. riskTick: tras el await del fetch y antes de evaluar, si getOpenPosition() !== pos, abortar el tick
        const currentPos = getOpenPosition();
        if (!currentPos || currentPos !== pos) {
            return;
        }

        const price = Number(data.price);
        if (!Number.isFinite(price) || price <= 0) {
            riskFeedFailures++;
            throw new Error(`Precio inválido recibido: ${data?.price}`);
        }

        // 1. Detección de mercado abierto y umbral por activo (20s cripto, 150s Yahoo)
        const thresholdSec = (typeof data.stale_threshold_s === 'number') ? data.stale_threshold_s : (pos.symbol.includes('/') ? 20 : 150);
        const isMarketOpen = (data.market_open !== undefined) ? Boolean(data.market_open) : (data.quote_age_s !== undefined ? data.quote_age_s < 900 : true);

        // 2. Si market_open es false, loguear UNA vez y no contarlo como falla
        if (!isMarketOpen) {
            if (lastMarketClosedLoggedSymbol !== pos.symbol) {
                logToTerminal(`⏸️ [MERCADO CERRADO] Mercado cerrado para ${pos.symbol}. SL en pausa hasta reapertura.`, 'info');
                lastMarketClosedLoggedSymbol = pos.symbol;
            }
            riskFeedFailures = 0;
            staleFeedStartTime = 0;
            return;
        }

        // Si el mercado está abierto, resetear aviso de mercado cerrado
        lastMarketClosedLoggedSymbol = '';

        // 3. Comprobación de frescura usando quote_age_s
        const nowMs = Date.now();
        const quoteAgeSec = (typeof data.quote_age_s === 'number') ? data.quote_age_s : Math.max(0, Math.floor((nowMs - (data.ts || nowMs)) / 1000));
        const isStale = quoteAgeSec > thresholdSec;

        if (isStale) {
            // Contar tiempo estancado con mercado abierto y emitir alarma crítica tras 5 minutos (300s)
            if (!staleFeedStartTime) staleFeedStartTime = nowMs;
            const staleElapsedSec = Math.floor((nowMs - staleFeedStartTime) / 1000);

            if (nowMs - lastRiskStaleLogTs > 60000) {
                if (data.feed_delayed) {
                    logToTerminal(`⚠️ [FEED CON DELAY] Feed con delay para ${pos.symbol} (latencia ${quoteAgeSec}s > umbral ${thresholdSec}s). Monitoreo pausado.`, 'warn');
                } else {
                    logToTerminal(`⚠️ [RIESGO] SL SIN PRECIO FRESCO (${pos.symbol}, latencia ${quoteAgeSec}s > umbral ${thresholdSec}s). Monitoreo pausado para evitar falsos cierres.`, 'warn');
                }
                lastRiskStaleLogTs = nowMs;
            }

            if (staleElapsedSec >= 300 && (nowMs - lastRiskFailAlarmTs > 30000)) {
                logToTerminal(`🚨 [ALARMA CRÍTICA] Feed estancado durante ${(staleElapsedSec / 60).toFixed(1)} min con mercado abierto para ${pos.symbol}. Considera cerrar manualmente la posición.`, 'error');
                lastRiskFailAlarmTs = nowMs;
            }
            return; // NO evaluar con entryPrice ni publicar precio si no está fresco
        }

        // 4. Publicar window.positionAssetPrice SOLO si el dato es fresco
        riskFeedFailures = 0;
        staleFeedStartTime = 0;
        window.positionAssetPrice = price;
        window.positionAssetPriceTs = nowMs - (quoteAgeSec * 1000);

        // Si la posición es gestionada por el Daemon Python (backendId presente),
        // el Guardián SL/TP/Trailing del servidor es la única autoridad de cierre (evita cierres duplicados/conflictivos en SHORTs y Peluqueos).
        if (pos.backendId) {
            return;
        }

        const evalPrice = window.positionAssetPrice;
        const feeRate = (pos && typeof pos.feeRate === 'number') ? pos.feeRate : getBrokerFeeRate(pos ? pos.symbol : '');
        if (!Number.isFinite(feeRate) || feeRate < 0 || feeRate > 10) {
            logToTerminal(`🛑 [RIESGO] Evaluación de salida pausada: comisión inválida para ${pos.symbol}. Corrige la configuración antes de operar.`, 'error');
            return;
        }
        if (Number.isFinite(pos.spreadRate) && (pos.spreadRate < 0 || pos.spreadRate > 5)) {
            logToTerminal(`🛑 [RIESGO] Evaluación de salida pausada: spread guardado inválido para ${pos.symbol}.`, 'error');
            return;
        }
        const pnlNetPct = netPctAtPrice(pos, evalPrice, feeRate);
        if (!Number.isFinite(pnlNetPct)) {
            logToTerminal(`🛑 [RIESGO] Evaluación de salida pausada: no se pudo calcular el PnL neto de ${pos.symbol}.`, 'error');
            return;
        }

        const isShortPos = String(pos.side || '').toUpperCase() === 'SHORT';
        if (typeof pos.peakPrice !== 'number' || pos.peakPrice <= 0) pos.peakPrice = pos.entryPrice;
        if (typeof pos.stopNetPct !== 'number') pos.stopNetPct = -(pos.slEffPct ?? pos.sl ?? 1.0);
        delete pos.slEffPct;
        if (typeof pos.beArmed !== 'boolean') pos.beArmed = false;
        if (typeof pos.trailActive !== 'boolean') pos.trailActive = false;
        if (typeof pos.trailPct !== 'number') pos.trailPct = 0.5;

        // Trailing peak (máximo para LONG, mínimo para SHORT)
        if (isShortPos) {
            if (evalPrice < pos.peakPrice) pos.peakPrice = evalPrice;
        } else {
            if (evalPrice > pos.peakPrice) pos.peakPrice = evalPrice;
        }

        // 1. Breakeven
        // Auditoría 19-oct-2026: antes armaba a 2*fee+0.1 (=0.3% neto) con stop en +0.05% neto, es decir
        // una salida a cero pagando comisiones completas. Ahora arma recién cuando el trade ya cubre el
        // costo ida/vuelta con margen (>= 0.7% neto) y bloquea una ganancia NETA real de +0.30%.
        const spreadRtPct = Number.isFinite(pos.spreadRate) ? pos.spreadRate * 2.0 : 0.1;
        const BE_ARM_NET = (feeRate * 2.0) + spreadRtPct + 0.4;
        const BE_LOCK_NET = 0.30;
        if (pnlNetPct >= BE_ARM_NET && !pos.beArmed) {
            pos.beArmed = true;
            pos.stopNetPct = Math.max(pos.stopNetPct, +BE_LOCK_NET);
            logToTerminal(`🛡️ [RIESGO] Breakeven armado en ${pos.symbol} (+${pnlNetPct.toFixed(2)}% neto >= ${BE_ARM_NET.toFixed(2)}%). Stop Loss movido a +${BE_LOCK_NET.toFixed(2)}% neto (ganancia asegurada tras costos).`, 'action');
        }

        // 2. Trailing Stop
        // El TP configurado es un movimiento BRUTO de precio; se convierte a su equivalente NETO antes de
        // compararlo con el PnL neto (antes se comparaba bruto vs neto y la salida llegaba ~0.3% tarde).
        const configuredTakeProfitGross = pos.tp !== undefined ? pos.tp : 1.5;
        const tpTargetPrice = isShortPos
            ? pos.entryPrice * (1 - configuredTakeProfitGross / 100)
            : pos.entryPrice * (1 + configuredTakeProfitGross / 100);
        const configuredTakeProfitNet = (pos.entryPrice > 0)
            ? netPctAtPrice(pos, tpTargetPrice, feeRate)
            : configuredTakeProfitGross;
        const configuredTakeProfit = Number.isFinite(configuredTakeProfitNet) ? configuredTakeProfitNet : configuredTakeProfitGross;
        const minimumNetProfit = Number.isFinite(pos.minProfitPct)
            ? pos.minProfitPct
            : getMinimumNetProfitPct();
        const minimumNetProfitIsValid = Number.isFinite(minimumNetProfit)
            && minimumNetProfit >= 0
            && minimumNetProfit <= 5;
        if (!minimumNetProfitIsValid) {
            logToTerminal(`⚠️ [RIESGO] Toma de ganancias bloqueada: umbral de beneficio neto inválido para ${pos.symbol}. Los stops de protección siguen activos.`, 'error');
        }
        const takeProfitLimit = Math.max(configuredTakeProfit, minimumNetProfitIsValid ? minimumNetProfit : 0);
        const effectiveStrategyMode = pos.strategyMode || getStrategyMode();
        const isTrailingRunner = effectiveStrategyMode === 'trailing_trend_runner';
        const isFavorablePrice = isShortPos ? (evalPrice < pos.entryPrice) : (evalPrice > pos.entryPrice);
        const shouldCheckTrailing = (isTrailingRunner && isFavorablePrice) || (pnlNetPct >= (takeProfitLimit * 0.6));
        if (shouldCheckTrailing) {
            pos.trailActive = true;
            const trailPctVal = Number.isFinite(pos.trailPct) && pos.trailPct > 0 ? pos.trailPct : (isTrailingRunner ? (pos.sl || 2.0) : 0.5);
            const trailPrice = isShortPos
                ? pos.peakPrice * (1 + (trailPctVal / 100))
                : pos.peakPrice * (1 - (trailPctVal / 100));
            const trailNet = netPctAtPrice(pos, trailPrice, feeRate);
            if (trailNet > pos.stopNetPct) {
                pos.stopNetPct = trailNet;
                const nowSec = Math.floor(Date.now() / 1000);
                if (nowSec - lastTrailingLogTs > 10) {
                    logToTerminal(`📈 [RIESGO] Trailing Stop actualizado en ${pos.symbol} (Pico: $${pos.peakPrice.toFixed(2)} | Stop Neto: ${pos.stopNetPct >= 0 ? '+' : ''}${pos.stopNetPct.toFixed(2)}%).`, 'info');
                    lastTrailingLogTs = nowSec;
                }
            }
        }

        // Persistencia throttled
        if (nowMs - lastPortfolioSaveTs > 10000) {
            localStorage.setItem('ai_portfolio_v5', JSON.stringify(portfolio));
            lastPortfolioSaveTs = nowMs;
        }

        // 3. Evaluar Stop DESPUÉS de actualizar BE y Trailing
        if (pnlNetPct <= pos.stopNetPct) {
            let exitReason = 'Stop Loss';
            if (pos.stopNetPct < 0) {
                exitReason = 'Stop Loss';
            } else if (pos.beArmed && pos.stopNetPct < 0.5 && !pos.trailActive) {
                exitReason = 'Breakeven';
            } else {
                exitReason = 'Trailing';
            }
            logToTerminal(`⚠️ AGENTE DE RIESGO: ${exitReason} disparado en ${pos.symbol} (${pnlNetPct.toFixed(2)}% neto vs umbral ${pos.stopNetPct >= 0 ? '+' : ''}${pos.stopNetPct.toFixed(2)}% neto). Vendiendo para proteger capital.`, 'error');
            executeTrade('VENDER', pos.symbol, pos.baseCoin, evalPrice, exitReason, { verifiedQuote: true });
        } else if (minimumNetProfitIsValid && pnlNetPct >= takeProfitLimit) {
            if (isTrailingRunner) {
                // Estrategia Raúl: Sin techo de Take Profit rígido; la posición corre protegida por Trailing Stop.
            } else if ((pos.strategyMode === 'hyenuk_chu_multibagger' || pos.strategyMode === 'kula_balam_cava_ruiz' || pos.strategyMode === 'tres_velas_wyckoff_bulkowski') && !pos.trimmed && pos.qty > 0) {
                const posCurrency = pos.currency || getCurrency(pos.symbol);
                const spreadRate = Number.isFinite(pos.spreadRate) ? pos.spreadRate : 0;
                const trimQty = Number((pos.qty * 0.5).toFixed(6));
                const sellFillPrice = evalPrice * (1 - spreadRate / 100);
                const grossProceeds = trimQty * sellFillPrice;
                const exitFee = grossProceeds * (feeRate / 100);
                const netProceeds = grossProceeds - exitFee;
                const fullCostBasis = pos.costBasis || (pos.qty * pos.entryPrice);
                const proportionalCost = fullCostBasis * 0.5;
                const trimPnlNet = netProceeds - proportionalCost;

                if (!portfolio.vault) portfolio.vault = { USDT: 0.0, USD: 0.0, ARS: 0.0 };
                portfolio.vault[posCurrency] = (portfolio.vault[posCurrency] || 0) + netProceeds;
                portfolio.totalFeesPaid = (portfolio.totalFeesPaid || 0) + exitFee;

                pos.qty = Number((pos.qty - trimQty).toFixed(6));
                pos.costBasis = Number((fullCostBasis - proportionalCost).toFixed(2));
                pos.trimmed = true;
                pos.beArmed = true;
                pos.stopNetPct = Math.max(pos.stopNetPct, 0.15);
                pos.tp = 12.0;
                pos.trailPct = 1.5;
                portfolio.ASSET = pos.qty;
                localStorage.setItem('ai_portfolio_v5', JSON.stringify(portfolio));
                updateCapitalDisplay();

                const stratLabel = pos.strategyMode === 'kula_balam_cava_ruiz' ? 'CAVA & RUIZ' : (pos.strategyMode === 'tres_velas_wyckoff_bulkowski' ? 'TRES VELAS' : 'HYENUK CHU');
                logToTerminal(`✂️ [PELUQUEO ${stratLabel}] TP1 alcanzado en ${pos.symbol} (+${pnlNetPct.toFixed(2)}% neto). Liquidado 50% (+$${trimPnlNet.toFixed(2)} neto barridos a Bóveda ${posCurrency}). El 50% restante corre LIBRE DE RIESGO en Breakeven Real (+0.15% neto) con trailing institucional.`, 'action');
                addTradeToHistory('VENDER', pos.symbol, pos.baseCoin, sellFillPrice, 'Ejecutada', `Peluqueo 50% (${stratLabel} TP1)`, exitFee, trimQty);
            } else {
                logToTerminal(`🎯 AGENTE DE RIESGO: Take Profit alcanzado en ${pos.symbol} (+${pnlNetPct.toFixed(2)}% neto vs +${takeProfitLimit}% objetivo). Asegurando ganancias.`, 'action');
                executeTrade('VENDER', pos.symbol, pos.baseCoin, evalPrice, 'Take Profit', { verifiedQuote: true });
            }
        }

    } catch (err) {
        clearTimeout(timeoutId);
        riskFeedFailures++;
        const nowMs = Date.now();
        if (riskFeedFailures >= 5 && (nowMs - lastRiskFailAlarmTs > 30000)) {
            logToTerminal(`🚨 [ALARMA CRÍTICA] Feed de riesgo falló ${riskFeedFailures} veces consecutivas para ${pos.symbol}. Considera cerrar manualmente la posición.`, 'error');
            lastRiskFailAlarmTs = nowMs;
        } else if (nowMs - lastRiskCatchLogTs > 15000) {
            if (err.name !== 'AbortError' || riskFeedFailures >= 3) {
                logToTerminal(`⚠️ [RIESGO] Error consultando precio de posición ${pos.symbol}: ${err.message}`, 'warn');
                lastRiskCatchLogTs = nowMs;
            }
        }
    } finally {
        riskTickInFlight = false;
    }
}

// Iniciar monitor de riesgo independiente cada 2000 ms (R2)
setInterval(riskTick, 2000);

// Notificación de inicio al cargar la página (R2 item 8)
if (hasOpenPosition()) {
    const pInit = getOpenPosition();
    logToTerminal(`🛡️ Posición abierta en ${pInit.symbol}: monitor de riesgo ACTIVO.`, 'action');
}

// --- CIRCUIT BREAKER MULTI-LIBRO PERSISTIDO (Bloque 3 - R4) ---
function localDayKey() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

function getRiskState() {
    const today = localDayKey();
    let state = null;
    try {
        state = JSON.parse(localStorage.getItem('ai_risk_state_v2'));
    } catch (_) {}

    // Migración retrocompatible desde v1
    if (!state) {
        try {
            const v1 = JSON.parse(localStorage.getItem('ai_risk_state_v1'));
            if (v1) {
                state = {
                    books: {},
                    haltedUntil: v1.haltedUntil || null,
                    haltReason: v1.haltedUntil ? 'Migrado de V1' : null
                };
            }
        } catch (_) {}
    }

    if (!state) {
        state = {
            books: {},
            haltedUntil: null,
            haltReason: null
        };
    }
    if (!state.books) state.books = {};

    // Iniciar libros para las monedas soportadas respetando día local
    ['USDT', 'USD', 'ARS'].forEach(currency => {
        const book = state.books[currency];
        if (!book || book.dayKey !== today) {
            let equity = (portfolio.balances && portfolio.balances[currency]) || 0;
            const openPos = getOpenPosition();
            if (openPos && (openPos.currency === currency || getCurrency(openPos.symbol) === currency)) {
                equity += (openPos.costBasis || (openPos.qty * openPos.entryPrice));
            }
            
            const isPlaceholder = (equity <= 0);
            const startEquity = isPlaceholder ? (currency === 'ARS' ? 0 : 100) : equity;

            state.books[currency] = {
                dayKey: today,
                startEquity: startEquity,
                realizedPnl: 0,
                consecLosses: 0,
                placeholder: isPlaceholder
            };
        }
    });

    return state;
}

function saveRiskState(state) {
    try {
        localStorage.setItem('ai_risk_state_v2', JSON.stringify(state));
    } catch (_) {}
}

// Limpieza única automática de bloqueo fantasma previo por desincronización de posición SQLite
try {
    if (!localStorage.getItem('ai_cb_phantom_fix_v2')) {
        localStorage.removeItem('ai_risk_state_v2');
        localStorage.removeItem('ai_cooldown_v1');
        localStorage.setItem('ai_cb_phantom_fix_v2', '1');
    }
} catch (_) {}

function isCircuitBreakerActive() {
    const state = getRiskState();
    return !!(state.haltedUntil && Date.now() < state.haltedUntil);
}

function recordTradeInCircuitBreaker(pnlNeto, currency, posId = null) {
    const cur = currency || getCurrency(currentSymbol);
    const state = getRiskState();
    const today = localDayKey();
    
    if (!state.books[cur] || state.books[cur].dayKey !== today) {
        let equity = (portfolio.balances && portfolio.balances[cur]) || 0;
        const isPlaceholder = (equity <= 0);
        state.books[cur] = {
            dayKey: today,
            startEquity: isPlaceholder ? (cur === 'ARS' ? 0 : 100) : equity,
            realizedPnl: 0,
            consecLosses: 0,
            placeholder: isPlaceholder
        };
    }

    const book = state.books[cur];
    if (posId && book.lastRecordedPosId === posId) {
        return;
    }
    if (posId) {
        book.lastRecordedPosId = posId;
    }

    // Si el libro tiene placeholder:true (primer trade con balance originalmente 0), recalcular startEquity con el equity real previo al trade
    if (book.placeholder) {
        const currentBal = (portfolio.balances && portfolio.balances[cur]) || 0;
        const realPriorEquity = currentBal - pnlNeto;
        if (realPriorEquity > 0) {
            book.startEquity = realPriorEquity;
            book.placeholder = false;
        } else if (currentBal > 0) {
            book.startEquity = currentBal;
            book.placeholder = false;
        }
    }

    book.realizedPnl = (book.realizedPnl || 0) + pnlNeto;
    if (pnlNeto < 0) {
        book.consecLosses = (book.consecLosses || 0) + 1;
    } else if (pnlNeto > 0) {
        book.consecLosses = 0;
    }

    // 1. Regla 3 pérdidas consecutivas en el libro específico
    if (book.consecLosses >= 3) {
        state.haltedUntil = Date.now() + 24 * 60 * 60 * 1000;
        state.haltReason = `3 pérdidas consecutivas en libro ${cur}`;
        logToTerminal(`🛑 [CIRCUIT BREAKER] 3 pérdidas consecutivas detectadas en libro ${cur}. Trading pausado 24h para proteger capital.`, 'error');
        if (typeof stopAgent === 'function') stopAgent('circuit_breaker');
    }

    // 2. Regla Drawdown diario <= -3% en el libro específico
    const startEq = book.startEquity || (cur === 'ARS' ? 0 : 100);
    const drawdownPct = startEq > 0 ? ((book.realizedPnl / startEq) * 100) : 0;
    if (startEq > 0 && drawdownPct <= -3.0) {
        state.haltedUntil = Date.now() + 24 * 60 * 60 * 1000;
        state.haltReason = `Drawdown diario <= -3% en libro ${cur} (${drawdownPct.toFixed(2)}%)`;
        logToTerminal(`🛑 [CIRCUIT BREAKER] Drawdown diario del 3% alcanzado en libro ${cur} (${drawdownPct.toFixed(2)}% PnL: $${book.realizedPnl.toFixed(2)} vs equity inicial $${startEq.toFixed(2)}). Trading pausado 24h.`, 'error');
        if (typeof stopAgent === 'function') stopAgent('circuit_breaker');
    }

    saveRiskState(state);
}

window.resetCircuitBreaker = async function() {
    const ok = window.UIFeedback
        ? await window.UIFeedback.confirm("¿Deseas reiniciar manualmente el Circuit Breaker de todos los libros contables?", { title: "Circuit Breaker", icon: "🔄", confirmText: "Sí, reiniciar" })
        : confirm("¿Deseas reiniciar manualmente el Circuit Breaker de todos los libros contables?");
    if (!ok) return;
    const state = getRiskState();
    state.haltedUntil = null;
    state.haltReason = null;
    ['USDT', 'USD', 'ARS'].forEach(cur => {
        if (state.books[cur]) {
            state.books[cur].consecLosses = 0;
            state.books[cur].realizedPnl = 0;
        }
    });
    saveRiskState(state);
    localStorage.removeItem('ai_cooldown_v1');
    fetch(`${API_BASE_URL}/api/ledger/reset_circuit_breaker`, {
        method: 'POST',
        headers: apiAuthHeaders()
    }).catch(err => console.debug('Aviso reseteando CB en servidor:', err));
    logToTerminal(`🔄 [CIRCUIT BREAKER] Reset manual aplicado por el operador. Límites restaurados.`, 'action');
    if (window.UIFeedback) {
        window.UIFeedback.toast("Circuit Breaker reiniciado en todos los libros contables.", { type: "success", title: "Límites Restaurados" });
    }
};

function getAssetFrictionCosts(symbol = '') {
    const s = String(symbol || (typeof currentSymbol !== 'undefined' ? currentSymbol : '')).toUpperCase();
    if (s.includes('=X')) {
        // Forex spot estándar: Sin comisión por orden, spread ~ 1.2 pips (0.012%)
        return { fee_pct: 0.0, spread_pct: 0.012, asset_class: 'forex' };
    }
    if (s.endsWith('.BA')) {
        // BYMA acciones / CEDEARs: Comisión arancelaria 0.50%, spread 0.10%
        return { fee_pct: 0.50, spread_pct: 0.10, asset_class: 'byma' };
    }
    if (s.includes('=F')) {
        // Futuros / Commodities
        return { fee_pct: 0.0, spread_pct: 0.02, asset_class: 'futures' };
    }
    if (s.includes('/') || s.includes('USDT') || s.includes('BTC') || s.includes('ETH')) {
        // Criptomonedas spot (ej. Binance: 0.10% taker/maker, spread 0.02%)
        return { fee_pct: 0.10, spread_pct: 0.02, asset_class: 'crypto' };
    }
    if (/^[A-Z]{1,5}$/.test(s)) {
        // Acciones / ETFs US (Alpaca / Robinhood Zero Commission, spread 0.010%)
        return { fee_pct: 0.0, spread_pct: 0.010, asset_class: 'us_equity' };
    }
    return { fee_pct: 0.10, spread_pct: 0.02, asset_class: 'generic' };
}

function getBrokerFeeRate(symbol = '') {
    const sym = symbol || (typeof currentSymbol !== 'undefined' ? currentSymbol : '');
    const friction = getAssetFrictionCosts(sym);
    const feeSelect = document.getElementById('brokerFeeSelect');
    if (!feeSelect) return friction.fee_pct;
    if (feeSelect.value === 'custom') {
        const customInput = document.getElementById('customFeeInput');
        const val = parseFloat(customInput?.value);
        return Number.isFinite(val) && val >= 0 && val <= 10 ? val : friction.fee_pct;
    }
    // Si el usuario no forzó 'custom', respetamos el costo intrínseco del activo (ej. Forex = 0.0%)
    if (sym && (sym.includes('=X') || /^[A-Z]{1,5}$/.test(sym.toUpperCase()))) {
        return friction.fee_pct;
    }
    const rate = parseFloat(feeSelect.value);
    return Number.isFinite(rate) && rate >= 0 && rate <= 10 ? rate : friction.fee_pct;
}

function getEstimatedSpreadRate(symbol = '') {
    const sym = symbol || (typeof currentSymbol !== 'undefined' ? currentSymbol : '');
    const friction = getAssetFrictionCosts(sym);
    const spreadInput = document.getElementById('spreadInput');
    // Si el activo es Forex o Acciones y el input no fue modificado manualmente a un valor atípico
    if (sym && sym.includes('=X')) {
        return friction.spread_pct;
    }
    const rate = parseFloat(spreadInput?.value ?? friction.spread_pct);
    return Number.isFinite(rate) && rate >= 0 && rate <= 5 ? rate : friction.spread_pct;
}

function getMinimumNetProfitPct() {
    const input = document.getElementById('minProfitPctInput');
    const rate = parseFloat(input?.value ?? '0.5');
    return Number.isFinite(rate) && rate >= 0 && rate <= 5 ? rate : NaN;
}

function getStrategyMode() {
    return document.getElementById('strategyModeSelect')?.value || 'manual';
}

function isQuantStrategyMode(mode = getStrategyMode()) {
    return mode === 'mean_reversion_atr';
}

function getQuantRiskBudgetPct() {
    const rate = parseFloat(document.getElementById('quantRiskBudgetSelect')?.value ?? '0.25');
    return Number.isFinite(rate) && rate > 0 && rate <= 1 ? rate / 100 : NaN;
}

const STRATEGY_EXPLANATIONS = {
    auto: {
        title: "🤖 Piloto Automático Inteligente (Por Horario y Régimen)",
        type: "Conmutador Dinámico",
        summary: "El orquestador decide por ti en tiempo real según el reloj mundial y los datos técnicos.",
        whenEnters: "Apertura NY (10:25-12:30 ARG) ➔ Francotirador M15. Tarde de rueda ➔ Seguidor de Tendencia 1h. Caída de pánico (Z ≤ -2.0) ➔ Cazador de Rebotes. Fin de semana ➔ Cripto 24/7.",
        howProtects: "Calcula Stop Loss adaptativo por volatilidad (1.5×ATR) fuera del ruido de mercado.",
        whenExits: "Take Profit derivado para asegurar un ratio neto R:R ≥ 2.0 tras comisiones y spread.",
        idealFor: "Operativa integral 24/7 sin necesidad de reconfigurar la pantalla cada hora."
    },
    kula_balam_cava_ruiz: {
        title: "🐅 Kula Balam: Cava & Ruiz (Tríada 1D-1H-5M & Fallo MACD)",
        type: "Fractal Institucional + Doctrina de Parqué",
        summary: "Doctrina cuantitativa institucional: Tríada multitemporal de Alex Ruiz (Tendencia 1D, Zona Dorada Fibonacci 0.50-0.75 y EMA50 en 1H, Gatillo 5M) combinada con la Doctrina de Parqué de José Luis Cava (Clúster de Volumen a la izquierda, Onda C agotada, Fallo MACD y Divergencia RSI con secado de volumen RVOL < 0.85).",
        whenEnters: "Solo con confluencia plena de 4 pasos: Tendencia 1D alcista, retroceso a Zona Dorada Fibonacci (0.50-0.75) y soporte en EMA50 (1H), secado de volumen previo (RVOL < 0.85), y gatillo en 5M por Fallo MACD o divergencia RSI alcista.",
        howProtects: "Stop Loss adaptativo bajo el mínimo de invalidación más margen anti stop-hunting: max(2 ticks, 0.20×ATR, 0.15% precio).",
        whenExits: "Asimetría matemática R:R ≥ 1:2.0 / 1:3.0 obligatoria. Al alcanzar TP1 (+1.50% neto / 1.5×ATR) ejecuta peluqueo del 50% y mueve Stop Loss a Breakeven Real (+0.15% neto). El 50% restante corre con trailing institucional.",
        idealFor: "BTC/USDT, ETH, SOL, Wall Street (SPY, QQQ, NVDA) y activos de alta liquidez institucional."
    },
    nasdaq_araujo_vwap: {
        title: "⏱️ Nasdaq Araujo: Francotirador VWAP Wall Street (LONG & SHORT)",
        type: "Campana Institucional VWAP + Seguros de Parqué",
        summary: "Estrategia determinista especializada en la apertura de Wall Street (QQQ, SPY, NVDA, AAPL, CEDEARs). Opera exclusivamente de 09:35 a 11:00 NY (10:35 a 12:00 ARG) tras neutralizar el ruido de los primeros 5 minutos de la campana.",
        whenEnters: "En LONG: Precio sobre VWAP diario con retroceso testeando el VWAP, rechazo con mecha inferior >= 30% y volumen RVOL >= 1.2. En SHORT: Precio bajo VWAP diario con rebote testeando el nivel, rechazo con mecha superior >= 30%, Veto Bear Trap y Veto Sobreventa RSI <= 30.",
        howProtects: "Stop a Misa ubicado más allá del VWAP con margen anti stop-hunting de 2 ticks o fracción ATR. Candado de reloj que veta operaciones fuera de la ventana matutina.",
        whenExits: "Asimetría obligatoria R:R neto >= 1:2.0 tras comisiones y spread. Peluqueo del 50% en TP1 con pase inmediato de Stop a Breakeven ($0 riesgo) y 50% remanente con trailing en VWAP.",
        idealFor: "QQQ, SPY, NQ=F, NVDA, AAPL, MSFT, TSLA y CEDEARs de BYMA de lunes a viernes."
    },
    hyenuk_chu_multibagger: {
        title: "📈 Seguidor de Tendencia con Ganancia Asegurada (Swing 1h)",
        type: "Trend Following con Peluqueo",
        summary: "Captura tendencias institucionales prolongadas asegurando ganancias y eliminando el riesgo a mitad de camino.",
        whenEnters: "Precio sobre EMA200 y SMA20 en velas de 1h con volumen sano. Filtro anti-euforia estricto (RSI ≤ 70).",
        howProtects: "Stop Loss inicial a -1.5%. Al alcanzar +3.5% de ganancia, liquida el 50% (Peluqueo) y mueve el Stop a Breakeven ($0 riesgo restante).",
        whenExits: "La segunda mitad corre libre de riesgo de 2 a 10 días hasta el agotamiento de la tendencia.",
        idealFor: "NVDA, TSLA, BTC/USDT, SOL/USDT y acciones líderes en impulso."
    },
    mean_reversion_atr: {
        title: "🧯 Cazador de Rebotes tras Caída Fuerte (Capitulación)",
        type: "Reversión Cuantitativa",
        summary: "Especializada en comprar el pánico y las ventas masivas exageradas a favor de la tendencia secular.",
        whenEnters: "Solo cuando el Z-Score cae a sobreventa extrema (≤ -2.0) sobre la EMA200 y aparece mecha inferior de absorción institucional.",
        howProtects: "Stop Loss ubicado determinísticamente a 1.5×ATR de distancia.",
        whenExits: "Take Profit calculado a 4.0×ATR (R:R neto ≥ 1.5) al recuperar la media.",
        idealFor: "Rebotes técnicos limpios en BTC, ETH, SOL y ETFs tras noticias alarmistas temporales."
    },
    trailing_trend_runner: {
        title: "🚀 Rally sin Techo: Ganancias Libres con Stop Móvil",
        type: "Trailing Dinámico (Idea Raúl)",
        summary: "Para capturar rallies explosivos completos sin que un Take Profit prematuro te corte la subida.",
        whenEnters: "Alineación alcista sobre EMA200 y SMA20 con RSI entre 40 y 72.",
        howProtects: "Stop Loss inicial a 1.5×ATR o 2.0%. Al alcanzar +0.40% bruto (+0.15% neto) pasa a Breakeven Real.",
        whenExits: "El Stop sube continuamente a un 2% de distancia del precio máximo alcanzado. Solo sale cuando el mercado retrocede y lo toca.",
        idealFor: "Rallies alcistas en criptomonedas y tecnológicas sin techo a la vista."
    },
    alex_ruiz_triada_3velas: {
        title: "🎯 Alex Ruiz: La Tríada de las 3 Velas (LONG & SHORT)",
        type: "Fractal 1D-1H-5M & Shorts Blindados",
        summary: "Estrategia fractal de Alex Ruiz para capturar giros con confluencia multitemporal (1D Contexto, 1H Zona Dorada 0.50-0.75 y 5M Gatillo 3 Velas) con shorts de seguridad.",
        whenEnters: "LONG: Precio sobre EMA50 + Retroceso Fibo 0.50-0.75 + V3 quiebra V2. SHORT: Precio bajo EMA50 + Rebote Fibo 0.50-0.75 + V3 perfora V2.",
        howProtects: "Shorts Blindados: Veto Bear Trap (mecha inferior < 40%), Veto Sobreventa (RSI > 30), Stop técnico + 2 ticks fuera del ruido y Peluqueo TP1 con R:R ≥ 1:2.0 neto.",
        whenExits: "TP1 al 50% con Breakeven real a costo cero y runner con trailing libre en TP2 (+1.618 extension).",
        idealFor: "Operativa simétrica protegida en Cripto 24/7 y Acciones de Wall Street con stops innegociables."
    },
    trailing_short_runner: {
        title: "🔻 Caída sin Suelo (Venta en Corto): Ganancias Libres con Stop Móvil",
        type: "Trailing Dinámico en Corto (Shorting Raúl)",
        summary: "Para rentabilizar caídas y mercados bajistas sin techo ni suelo fijo, protegiendo con Trailing Stop descendente.",
        whenEnters: "Alineación bajista cotizando bajo la EMA200 y SMA20 con RSI entre 28 y 58.",
        howProtects: "Stop Loss inicial acotado a 1.5×ATR (máximo 1.5%). Al caer +0.30% comprime el Stop un 60%, y a max(0.65%, 1.2×ATR) fija Breakeven Real (+0.15% neto garantizado).",
        whenExits: "El Stop baja persiguiendo los valles (mínimos alcanzados). Solo cierra recomprando cuando el precio rebota y lo toca.",
        idealFor: "Mercados en corrección, fases bajistas o activos con clara tendencia descendente."
    },
    "01_tendencia_institucional_15m": {
        title: "🏛️ Tendencia Institucional 15m (Estrategia Cero)",
        type: "Cuantitativa Auditada (Fase 1 / Fase 3)",
        summary: "Estrategia auditada con Qwen 2.5 basada en cruce de medias EMA200 y SMA20, RSI > 40 y volumen RVOL > 0.8.",
        whenEnters: "Precio de cierre sobre EMA200 y SMA20, RSI > 40 y RVOL > 0.8.",
        howProtects: "Stop Loss a 1.5×ATR o 2.0% fuera del ruido del mercado.",
        whenExits: "Toma de ganancias técnica a +3.0% o salida de protección si el precio cruza bajo la SMA20.",
        idealFor: "Tendencias seguras en 15m auditadas de forma autónoma por la IA."
    },
    "02_cazador_rebotes_atr_15m": {
        title: "🧯 Cazador de Rebotes ATR 15m (Estrategia 02)",
        type: "Reversión a la Media Cuantitativa (Fase 4)",
        summary: "Estrategia matemática pura: Caza rebotes tras caídas extremas (Z-Score ≤ -2.0 o pullback [-1.2, -0.4]) con absorción y RVOL ≥ 0.8.",
        whenEnters: "Z-Score ≤ -2.0 o [-1.2, -0.4], RSI ≤ 35 o mecha ≥ 0.25, y RVOL ≥ 0.8.",
        howProtects: "Stop Loss a 1.5×ATR fuera del ruido de mercado y ratio R:R neto ≥ 1.0 tras costos.",
        whenExits: "Take Profit dinámico a múltiplos ATR o toma de ganancias al acierto de rebote.",
        idealFor: "Mercados en pánico estadístico, capitulación o caídas abruptas hacia soporte."
    },
    tres_velas_wyckoff_bulkowski: {
        title: "🕯️ Tres Velas & Wyckoff VPA (Bulkowski Multitemporal)",
        type: "Acción del Precio Cuantitativa (Bulkowski 4.7M)",
        summary: "Opera con ventaja estadística empírica en 4.7M de velas: Three White Soldiers (82%), Morning Star (78%), Bullish Engulfing (68%) y Hammer en Soporte con RVOL.",
        whenEnters: "Solo cuando se confirma un patrón de 3 o 2 velas con RVOL ≥ 1.3 y confluencia sobre VWAP diario.",
        howProtects: "Stop Loss adaptado a 1.5×ATR fuera del ruido. Peluqueo al 50% (+2.5×ATR) con Breakeven real.",
        whenExits: "Take Profit asimétrico (R:R ≥ 1:2.0) o acompañamiento de trailing hasta agotamiento institucional.",
        idealFor: "Entradas francotirador en el punto exacto de giro y absorción en Cripto y Wall Street."
    },
    donchian_breakout_1h: {
        title: "🛡️ Donchian Breakout Estructural (4H Cripto / 1D Acciones)",
        type: "Ruptura con Squeeze ATR / Régimen Macro",
        summary: "Motor validado en Walk-Forward (70% IS / 30% OOS ciego, 3 a 5 años, 3/3 subperíodos positivos). Opera rupturas causales Donchian (30p en 4H / 20p en 1D) tras compresión relativa de volatilidad.",
        whenEnters: "Ruptura Donchian causal (shift 1) alineada con nivel y pendiente de EMA macro (200 en 4H / 100 en 1D), Squeeze ATR ≤ 1.15× mediana, volumen expansivo causal y vetos de mecha y sobreextensión EMA 50.",
        howProtects: "Stop Loss estructural ATR causal (1.40×ATR en 4H Cripto / 1.10×ATR en 1D Acciones) respetando piso mínimo operativo.",
        whenExits: "Take Profit asimétrico neto R:R ≥ 1:2.0 (3.36×ATR en 4H / 2.42×ATR en 1D) o Stop Loss sin truncamiento prematuro.",
        idealFor: "SOL/USDT y ETH/USDT en 4H (Largo/Corto 24/7) y AAPL, AMD, AVGO, META y MSFT en 1D (Solo Largo)."
    },
    squeeze_dual_eth_4h: {
        title: "🏆 Squeeze Dual BB/Donchian 4H (ETH/USDT)",
        type: "Compresión de Volatilidad y BOS Tendencial",
        summary: "Estrategia validada en Lab (+60.47% Retorno, PF 1.78, Max DD 10.38%). Opera compresión Bollinger/Donchian con Bear BOS bajo EMA 50.",
        whenEnters: "Expansión de ancho de Bollinger tras compresión relativa <= 1.2x mediana y ruptura de Donchian 30 con RVOL >= 1.10.",
        howProtects: "Stop Loss a 1.7x ATR con filtro anti-mechas trampa y salida mid-exit.",
        whenExits: "Take Profit derivado R:R >= 1:2.60.",
        idealFor: "ETH/USDT y Criptoactivos volátiles en marco temporal de 4 Horas."
    },
    manual: {
        title: "🛠️ Manual: Mis Niveles Fijos de Ganancia y Pérdida",
        type: "Discrecional / Panel",
        summary: "Control manual completo con los niveles porcentuales fijos seleccionados por el operador.",
        whenEnters: "A decisión del operador o señales estándar sin restricciones algorítmicas.",
        howProtects: "Stop Loss porcentual fijo configurado en el selector de TP/SL.",
        whenExits: "Take Profit porcentual fijo configurado en el selector.",
        idealFor: "Scalping rápido o pruebas manuales con niveles a medida."
    }
};

window.isMasterAutoMode = function() {
    const saved = localStorage.getItem('ai_master_mode');
    return saved === null || saved === 'auto';
};

window.setMasterStrategyMode = function(isAuto) {
    localStorage.setItem('ai_master_mode', isAuto ? 'auto' : 'manual');
    const btnAuto = document.getElementById('btnMasterAutoMode');
    const btnManual = document.getElementById('btnMasterManualMode');
    if (btnAuto && btnManual) {
        if (isAuto) {
            btnAuto.className = "px-2.5 py-1 text-xs font-bold rounded bg-cyan-600 text-white transition shadow cursor-pointer";
            btnManual.className = "px-2.5 py-1 text-xs font-bold rounded text-gray-400 hover:text-white transition cursor-pointer";
        } else {
            btnAuto.className = "px-2.5 py-1 text-xs font-bold rounded text-gray-400 hover:text-white transition cursor-pointer";
            btnManual.className = "px-2.5 py-1 text-xs font-bold rounded bg-cyan-600 text-white transition shadow cursor-pointer";
        }
    }
    updateStrategySettingsVisibility();
};

window.toggleStrategyExplanation = function(isOpen) {
    const card = document.getElementById('strategyExplanationCard');
    if (!card) return;
    if (isOpen) {
        window.updateStrategyExplanationCard();
        card.classList.remove('hidden');
    } else {
        card.classList.add('hidden');
    }
};

window.updateStrategyExplanationCard = function() {
    const content = document.getElementById('strategyExplanationContent');
    const tag = document.getElementById('strategyTypeTag');
    if (!content) return;
    const allowed = typeof window.getAllowedStrategies === 'function' ? window.getAllowedStrategies() : ALL_TACTICAL_STRATEGIES.map(s => s.id);
    if (tag) tag.innerText = `${allowed.length} Autorizada${allowed.length > 1 ? 's' : ''}`;

    if (allowed.length === 0) {
        content.innerHTML = '<p class="text-amber-400 italic py-2">⚠️ No hay fórmulas autorizadas para Kula. Tilda al menos una casilla en el selector de arriba.</p>';
        return;
    }

    content.innerHTML = allowed.map(id => {
        const info = STRATEGY_EXPLANATIONS[id];
        if (!info) return '';
        return `
            <div class="space-y-1 mb-2.5 p-2 bg-gray-950/80 rounded border border-cyan-800/40">
                <div class="flex items-center justify-between border-b border-gray-700/80 pb-1">
                    <span class="font-bold text-cyan-300 text-xs">${info.title}</span>
                    <span class="text-[9px] bg-cyan-950 text-cyan-300 px-1.5 py-0.5 rounded border border-cyan-800 font-mono">${info.type}</span>
                </div>
                <p class="text-[11px] text-gray-300 leading-snug">${info.summary}</p>
                <div class="grid grid-cols-1 gap-0.5 text-[10.5px] pt-1">
                    <p><strong class="text-emerald-400">🟢 Cuándo entra:</strong> <span class="text-gray-300">${info.whenEnters}</span></p>
                    <p><strong class="text-amber-400">🛡️ Cómo protege:</strong> <span class="text-gray-300">${info.howProtects}</span></p>
                    <p><strong class="text-blue-400">🎯 Cuándo sale:</strong> <span class="text-gray-300">${info.whenExits}</span></p>
                </div>
            </div>
        `;
    }).join('');
};

// Lista blanca de producción autorizada (sin estrategias Forex ni fórmulas no autorizadas)
const PRODUCTION_WHITELIST_DEFAULTS = new Set([
    'kula_balam_cava_ruiz',
    'kula_cava_sol_1h',
    'kula_cava_eth_1h',
    'ttm_squeeze_eth_1h',
    'ttm_squeeze_sol_4h',
    'donchian_breakout_1h',
    'squeeze_dual_eth_fondeo_strict_4h',
    'squeeze_dual_eth_4h_slot1',
]);
const PRODUCTION_EXCLUDED_STRATEGIES = new Set([
    'cava_fallo_macd_eurusd_1h',
    'nasdaq_araujo_vwap',
    'hyenuk_chu_multibagger',
]);

// Estrategias operativas tácticas consolidadas y auditadas en Backtest Lab (Panel Principal Cerebro Kula)
let ALL_TACTICAL_STRATEGIES = [
    {
        id: 'kula_balam_cava_ruiz',
        name: '🐅 Kula Balam: Cava & Ruiz (Tríada 1D-1H-5M & Fallo MACD)',
        sub: 'Tríada 1D-1H-5M, Zona Dorada Fibonacci 0.50-0.75, RVOL y Stop a Misa',
        defaultChecked: true,
        defaultLot: 0.10,
        timeframe: '5m'
    },
    {
        id: 'donchian_breakout_1h',
        name: '🛡️ Donchian Breakout 1H (SOL-ETH 4H / AAPL-AMD-MSFT 1D · PF 1.68)',
        sub: 'Ruptura Donchian 20/30, EMA Trend, Compresión ATR & Mid-Exit causal',
        defaultChecked: true,
        defaultLot: 0.10,
        timeframe: '4h'
    },
    {
        id: 'squeeze_dual_eth_4h_slot1',
        name: '🚀 squeeze_dual_eth_4h.py (ETH/USDT 4H · Slot 1)',
        sub: 'Compresión de volatilidad Bollinger/Donchian + OOS positivo en Cripto',
        defaultChecked: true,
        defaultLot: 0.10,
        timeframe: '4h'
    }
];

window.loadDynamicTacticalStrategies = async function() {
    try {
        const resp = await fetch(`${API_BASE_URL}/api/catalogo_formulas`);
        if (resp.ok) {
            const data = await resp.json();
            const principal = data.panel_principal || [];
            const operador = data.operador_presente || [];
            const allItems = [
                {
                    id: 'kula_balam_cava_ruiz',
                    name: '🐅 Kula Balam: Cava & Ruiz (Tríada 1D-1H-5M & Fallo MACD)',
                    sub: 'Tríada 1D-1H-5M, Zona Dorada Fibonacci 0.50-0.75, RVOL y Stop a Misa',
                    defaultChecked: true,
                    defaultLot: 0.10,
                    timeframe: '5m'
                }
            ];
            const seenIds = new Set(['kula_balam_cava_ruiz']);

            // 1. Panel Principal (Cerebro Kula Autónomo): excluir estrategias retiradas/no autorizadas
            principal.forEach(p => {
                if (!p?.id || PRODUCTION_EXCLUDED_STRATEGIES.has(p.id) || seenIds.has(p.id)) {
                    return;
                }
                seenIds.add(p.id);
                allItems.push({
                    id: p.id,
                    name: p.titulo || p.id,
                    sub: p.subtitulo || p.descripcion,
                    defaultChecked: PRODUCTION_WHITELIST_DEFAULTS.has(p.id),
                    defaultLot: p.lote_sugerido || 0.10,
                    timeframe: p.timeframe || '4h'
                });
            });

            if (allItems.length > 0) {
                ALL_TACTICAL_STRATEGIES = allItems;
                try {
                    const stored = localStorage.getItem('kula_allowed_strategies_v12');
                    let known = [];
                    try {
                        known = JSON.parse(localStorage.getItem('kula_known_strategies_v2') || '[]');
                    } catch (_) { known = []; }
                    const knownSet = new Set(Array.isArray(known) ? known : []);

                    if (stored === null) {
                        const init = allItems.filter(s => s.defaultChecked).map(s => s.id);
                        localStorage.setItem('kula_allowed_strategies_v12', JSON.stringify(init));
                    } else {
                        const parsed = JSON.parse(stored);
                        if (Array.isArray(parsed)) {
                            const validIds = new Set(allItems.map(s => s.id));
                            const newlyPromoted = allItems.filter(s => !knownSet.has(s.id) && s.defaultChecked).map(s => s.id);
                            const cleaned = parsed.filter(id => validIds.has(id) && !PRODUCTION_EXCLUDED_STRATEGIES.has(id));
                            const merged = Array.from(new Set([...cleaned, ...newlyPromoted]));
                            localStorage.setItem('kula_allowed_strategies_v12', JSON.stringify(merged));
                        }
                    }
                    localStorage.setItem('kula_known_strategies_v2', JSON.stringify(allItems.map(s => s.id)));
                } catch (_) {}

                if (typeof window.renderStrategyChecklist === 'function') {
                    window.renderStrategyChecklist();
                }
            }

            // 2. Con Operador Presente: Poblar selector de Trading con Presencia
            const selScalping = document.getElementById('selScalpingStrategy');
            if (selScalping) {
                if (operador.length > 0) {
                    const prevVal = selScalping.value;
                    selScalping.innerHTML = operador.map(op => `
                        <option value="${op.id}" data-timeframe="${op.timeframe || '1h'}" data-activo="${op.activo_default || ''}" ${op.id === prevVal ? 'selected' : ''}>${op.titulo} (${op.subtitulo || op.rendimiento_lab})</option>
                    `).join('');
                    selScalping.disabled = false;
                    const syncPresencialSymbol = () => {
                        const selSym = document.getElementById('selScalpingSymbol');
                        const activeOpt = selScalping.selectedOptions?.[0];
                        const stratId = String(selScalping.value || '');
                        const activo = stratId.startsWith('mtf_presencial_') ? 'MULTI_CRYPTO' : activeOpt?.dataset?.activo;
                        if (selSym && activo && [...selSym.options].some(o => o.value === activo)) {
                            selSym.value = activo;
                        }
                        if (typeof window.updateRiskSlotPreview === 'function') {
                            window.updateRiskSlotPreview();
                        }
                    };
                    if (!selScalping.dataset.syncBound) {
                        selScalping.addEventListener('change', syncPresencialSymbol);
                        selScalping.dataset.syncBound = '1';
                    }
                    if ((!prevVal || !selScalping.dataset.initialSynced) && !window.scalpingSessionState?.active && !window.scalpingSessionState?.draining) {
                        syncPresencialSymbol();
                        selScalping.dataset.initialSynced = '1';
                    }
                } else {
                    selScalping.innerHTML = '<option value="" disabled selected>⚠️ Sin fórmulas autorizadas (en cuarentena)</option>';
                    selScalping.disabled = true;
                }
            }
        }
    } catch (e) {
        console.warn("Uso de estrategias tácticas locales por defecto:", e);
    }
};

// Cargar catálogo dinámico al iniciar
if (typeof window !== 'undefined') {
    window.loadDynamicTacticalStrategies();
}

window.getStrategyRiskPct = function(id) {
    try {
        const stored = localStorage.getItem('kula_strategy_risk_v1');
        if (stored) {
            const map = JSON.parse(stored);
            if (map && map[id] !== undefined && parseFloat(map[id]) > 0) {
                return Math.min(5.0, Math.max(0.1, parseFloat(map[id])));
            }
        }
        // Migración inteligente desde kula_strategy_lots_v1: conservar valores calibrados >= 0.25 (ej. 1.5%)
        const legacy = localStorage.getItem('kula_strategy_lots_v1');
        if (legacy) {
            const lmap = JSON.parse(legacy);
            const lv = parseFloat(lmap?.[id]);
            if (Number.isFinite(lv) && lv >= 0.25 && lv <= 5.0) {
                return lv;
            }
        }
    } catch (_) {}
    const s = ALL_TACTICAL_STRATEGIES.find(st => st.id === id);
    return s?.defaultRiskPct || 1.5;
};

window.saveStrategyRiskPct = function(id, val) {
    try {
        const raw = parseFloat(val);
        if (!Number.isFinite(raw) || raw <= 0) return;
        const num = Math.min(5.0, Math.max(0.1, raw));
        let map = {};
        const stored = localStorage.getItem('kula_strategy_risk_v1');
        if (stored) {
            try { map = JSON.parse(stored) || {}; } catch (_) { map = {}; }
        }
        map[id] = num;
        localStorage.setItem('kula_strategy_risk_v1', JSON.stringify(map));
        if (typeof syncRunningDaemonConfig === 'function') syncRunningDaemonConfig();
    } catch (_) {}
};

window.getAllStrategyRiskPcts = function() {
    const res = {};
    for (const s of ALL_TACTICAL_STRATEGIES) {
        res[s.id] = window.getStrategyRiskPct(s.id);
    }
    return res;
};

// Compatibilidad con scripts legados
window.getStrategyCustomLot = window.getStrategyRiskPct;
window.saveStrategyCustomLot = window.saveStrategyRiskPct;
window.getAllCustomLots = function() { return {}; };

window.getAllowedStrategies = function() {
    try {
        const stored = localStorage.getItem('kula_allowed_strategies_v12');
        if (stored !== null) {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed)) {
                const validIds = new Set(ALL_TACTICAL_STRATEGIES.map(s => s.id));
                return parsed.filter(id => validIds.has(id) && !PRODUCTION_EXCLUDED_STRATEGIES.has(id));
            }
        }
    } catch (_) {}
    return ALL_TACTICAL_STRATEGIES.filter(s => s.defaultChecked).map(s => s.id);
};

window.saveAllowedStrategies = function(list) {
    const clean = (Array.isArray(list) ? list : []).filter(id => !PRODUCTION_EXCLUDED_STRATEGIES.has(id));
    localStorage.setItem('kula_allowed_strategies_v12', JSON.stringify(clean));
    window.renderStrategyChecklist();
    if (typeof syncRunningDaemonConfig === 'function') syncRunningDaemonConfig();
};

window.toggleStrategyChecklistDropdown = function(forceClose) {
    const menu = document.getElementById('strategyDropdownMenu');
    const chevron = document.getElementById('strategyDropdownChevron');
    if (!menu) return;
    const isHidden = menu.classList.contains('hidden');
    if (forceClose === true || !isHidden) {
        menu.classList.add('hidden');
        if (chevron) chevron.style.transform = 'rotate(0deg)';
    } else {
        menu.classList.remove('hidden');
        if (chevron) chevron.style.transform = 'rotate(180deg)';
    }
};

window.renderStrategyChecklist = function() {
    const container = document.getElementById('strategyChecklistItems');
    const summaryEl = document.getElementById('strategyDropdownSummary');
    const badgeEl = document.getElementById('strategyActiveCountBadge');
    const allowed = window.getAllowedStrategies();

    if (badgeEl) {
        if (allowed.length === 0) {
            badgeEl.className = "text-[10px] bg-red-950 text-red-300 px-2 py-0.5 rounded border border-red-700 font-mono font-bold";
            badgeEl.innerText = "0 activas (Kula Pausado)";
        } else {
            badgeEl.className = "text-[10px] bg-cyan-950 text-cyan-300 px-2 py-0.5 rounded border border-cyan-700 font-mono font-bold";
            badgeEl.innerText = `${allowed.length} activa${allowed.length > 1 ? 's' : ''}`;
        }
    }

    if (summaryEl) {
        const names = ALL_TACTICAL_STRATEGIES.filter(s => allowed.includes(s.id)).map(s => s.name.split(' (')[0]);
        if (names.length === 0) {
            summaryEl.innerHTML = '<span class="text-red-400 font-mono italic">⚠️ Ninguna fórmula autorizada (Kula en espera)</span>';
        } else {
            summaryEl.innerText = names.join(', ');
        }
    }

    if (container) {
        container.innerHTML = ALL_TACTICAL_STRATEGIES.map(s => {
            const isChecked = allowed.includes(s.id);
            const cardBg = isChecked 
                ? 'bg-slate-900 border-cyan-500/80 shadow-md shadow-cyan-950/40' 
                : 'bg-slate-950 border-slate-800 hover:border-cyan-700/60 hover:bg-slate-900';
            return `
                <div class="p-2.5 rounded-lg border transition select-none w-full max-w-full min-w-0 box-border ${cardBg}" style="background-color: ${isChecked ? '#0f172a' : '#020617'} !important; box-sizing: border-box !important;">
                    <label class="flex items-start gap-2.5 w-full min-w-0 cursor-pointer">
                        <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="window.onStrategyCheckboxToggle('${s.id}', this.checked)" class="mt-0.5 rounded bg-gray-950 border-gray-600 text-cyan-500 focus:ring-0 w-4 h-4 cursor-pointer shrink-0">
                        <div class="flex-1 min-w-0">
                            <span class="font-bold text-xs ${isChecked ? 'text-cyan-300' : 'text-gray-300'} break-words leading-tight block" title="${s.name}">${s.name}</span>
                            <p class="text-[10px] text-gray-400 truncate mt-0.5 block" title="${s.sub}">${s.sub}</p>
                        </div>
                    </label>
                </div>
            `;
        }).join('');
    }

    const hiddenSelect = document.getElementById('strategyModeSelect');
    if (hiddenSelect) {
        hiddenSelect.value = allowed.length === 1 ? allowed[0] : 'auto';
    }

    const formulaLabelEl = document.getElementById('strategySelectedFormulaLabel');
    if (formulaLabelEl) {
        if (allowed.length === 1) {
            const found = ALL_TACTICAL_STRATEGIES.find(s => s.id === allowed[0]);
            formulaLabelEl.innerText = found ? found.name : allowed[0];
        } else if (allowed.length > 1) {
            formulaLabelEl.innerText = `Orquestación Kula (${allowed.length} fórmulas autorizadas)`;
        } else {
            formulaLabelEl.innerText = 'Ninguna (Kula en Pausa)';
        }
    }

    // Sincronizar temporalidad activa automáticamente según la estrategia seleccionada
    const activeTfEl = document.getElementById('activeTimeframeSummary');
    if (activeTfEl) {
        if (allowed.length === 1) {
            const found = ALL_TACTICAL_STRATEGIES.find(s => s.id === allowed[0]);
            activeTfEl.innerText = found ? `${found.timeframe.toUpperCase()} (Fórmula Titular)` : '5M / 4H';
        } else if (allowed.length > 1) {
            activeTfEl.innerText = 'Multitemporal (5M / 15M / 4H según Fórmula)';
        } else {
            activeTfEl.innerText = 'En Pausa';
        }
    }

    if (typeof window.updateStrategyExplanationCard === 'function') {
        window.updateStrategyExplanationCard();
    }
};

window.onStrategyCheckboxToggle = function(stratId, isChecked) {
    let allowed = window.getAllowedStrategies();
    if (isChecked) {
        if (!allowed.includes(stratId)) allowed.push(stratId);
    } else {
        allowed = allowed.filter(id => id !== stratId);
    }
    window.saveAllowedStrategies(allowed);
};

window.selectAllStrategies = function(all) {
    const list = all ? ALL_TACTICAL_STRATEGIES.map(s => s.id) : [];
    window.saveAllowedStrategies(list);
};

// Cerrar menú al hacer clic fuera del bloque
document.addEventListener('click', (e) => {
    const container = document.getElementById('strategyModeFunctionBlock');
    if (container && !container.contains(e.target)) {
        window.toggleStrategyChecklistDropdown(true);
    }
});

function updateStrategySettingsVisibility() {
    const mode = getStrategyMode();
    const isAuto = window.isMasterAutoMode();
    window.updateStrategyExplanationCard();
    if (typeof window.updateSystemActiveEngineBadges === 'function') {
        window.updateSystemActiveEngineBadges();
    }

    // Actualizar badges del bloque superior
    const autoLabel = document.getElementById('autoActiveStrategyLabel');
    const autoRisk = document.getElementById('autoRiskRulesLabel');
    const autoSession = document.getElementById('autoSessionBadge');
    if (autoLabel && autoRisk) {
        const info = STRATEGY_EXPLANATIONS[mode] || STRATEGY_EXPLANATIONS.auto;
        autoLabel.innerText = info.title;
        if (mode === 'kula_balam_cava_ruiz') {
            autoRisk.innerText = 'SL Inval.+2 Ticks · Peluqueo 50% · R:R ≥ 2.0';
        } else if (mode === 'nasdaq_araujo_vwap') {
            autoRisk.innerText = 'SL Técnico M15 · R:R Neto ≥ 2.0';
        } else if (mode === 'hyenuk_chu_multibagger') {
            autoRisk.innerText = 'SL 1.5% · Trim 50% (+3.5%) · Breakeven';
        } else if (mode === 'mean_reversion_atr') {
            autoRisk.innerText = 'SL 1.5×ATR · TP 4.0×ATR (Neto ≥ 1.5)';
        } else if (mode === 'trailing_trend_runner' || mode === 'trailing_short_runner') {
            autoRisk.innerText = 'SL 1.5×ATR · Breakeven +0.4% · Trailing Móvil';
        } else if (mode === '01_tendencia_institucional_15m') {
            autoRisk.innerText = 'SL 1.5×ATR · TP +3.0% · Salida SMA20';
        } else if (mode === '02_cazador_rebotes_atr_15m') {
            autoRisk.innerText = 'SL 1.5×ATR · TP 2×SL · R:R ≥ 1.0 Neto';
        } else if (mode === 'tres_velas_wyckoff_bulkowski') {
            autoRisk.innerText = 'SL 1.5×ATR · Peluqueo 2.5×ATR · R:R ≥ 2.0';
        } else {
            autoRisk.innerText = 'SL 1.5×ATR · TP Neto ≥ 2.0 (Dinámico)';
        }
    }

    // Actualizar Chips de Parámetros de la Fórmula Táctica (Bloque 3 Informativo)
    const tfSum = document.getElementById('activeTimeframeSummary');
    const slSum = document.getElementById('activeStopLossSummary');
    const tpSum = document.getElementById('activeTakeProfitSummary');
    if (tfSum && slSum && tpSum) {
        if (mode === 'kula_balam_cava_ruiz') {
            tfSum.innerText = '5M (Micro) · 1H / 1D (Contexto)';
            slSum.innerText = 'Invalidación + 2 Ticks (SL a Misa)';
            tpSum.innerText = 'Peluqueo 50% TP1 (+1.5%) + Breakeven';
        } else if (mode === 'tres_velas_wyckoff_bulkowski') {
            tfSum.innerText = '15M / 1H (Patrones Bulkowski)';
            slSum.innerText = '1.5×ATR bajo Mínimo Patrón';
            tpSum.innerText = 'Peluqueo 50% (+2.5×ATR) + Trailing';
        } else if (mode === 'trailing_trend_runner') {
            tfSum.innerText = '15M / 1H (Rally sin Techo)';
            slSum.innerText = '1.5×ATR · Breakeven al +0.4%';
            tpSum.innerText = 'Trailing Stop Móvil al 2% de Máximo';
        } else if (mode === 'trailing_short_runner') {
            tfSum.innerText = '15M / 1H (Caída sin Suelo)';
            slSum.innerText = '1.5×ATR · Breakeven dinámico';
            tpSum.innerText = 'Trailing Stop Móvil en Descenso';
        } else if (mode === '02_cazador_rebotes_atr_15m' || mode === 'mean_reversion_atr') {
            tfSum.innerText = '15M (Capitulación Z ≤ -2.0)';
            slSum.innerText = '1.5×ATR fuera de Ruido';
            tpSum.innerText = '4.0×ATR (Retorno a la Media)';
        } else if (mode === 'nasdaq_araujo_vwap') {
            tfSum.innerText = '15M (Campana Wall Street 10:25)';
            slSum.innerText = 'Extremo Opuesto Vela M15';
            tpSum.innerText = 'R:R Neto ≥ 2.0 (Máx 1 trade/día)';
        } else if (mode === 'hyenuk_chu_multibagger') {
            tfSum.innerText = '1H (Swing Institucional)';
            slSum.innerText = '-1.5% Inicial';
            tpSum.innerText = 'Peluqueo 50% (+3.5%) + Breakeven';
        } else if (mode === '01_tendencia_institucional_15m') {
            tfSum.innerText = '15M (Tendencia EMA200/SMA20)';
            slSum.innerText = '1.5×ATR o 2.0%';
            tpSum.innerText = '+3.0% Técnico o Cruce SMA20';
        } else if (mode === 'manual') {
            tfSum.innerText = 'Libre (Definido por Operador)';
            slSum.innerText = 'Porcentual Fijo del Panel';
            tpSum.innerText = 'Porcentual Fijo del Panel';
        } else {
            tfSum.innerText = 'Dinámico por Horario';
            slSum.innerText = '1.5×ATR Adaptativo';
            tpSum.innerText = 'Derivado Neto R:R ≥ 2.0';
        }
    }
    if (autoSession) {
        const now = new Date();
        const hour = now.getHours();
        const min = now.getMinutes();
        const total = hour * 60 + min;
        const day = now.getDay();
        if (day === 0 || day === 6) {
            autoSession.innerText = '⚡ Cripto 24/7 (Findes)';
            autoSession.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-700';
        } else if (total >= 625 && total <= 750) {
            autoSession.innerText = '🟢 Campana Wall Street (M15)';
            autoSession.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700';
        } else if (total > 750 && total < 1020) {
            autoSession.innerText = '📈 Jornada Regular NY (1h)';
            autoSession.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-700';
        } else {
            autoSession.innerText = '🌙 Fuera de Rueda (Cripto 24/7)';
            autoSession.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-300 border border-gray-700';
        }
    }

    // APLICACIÓN RECURSIVA: Bloqueo selectivo por estrategia
    // 1. Timeframe (bloqueado en Araujo=15m y Chu=1h; libre en ATR, Trailing y Manual)
    const tfWrapper = document.getElementById('timeframeSettingWrapper');
    const tfSelect = document.getElementById('timeframeSelect');
    const tfBadge = document.getElementById('timeframeLockBadge');
    const locksTf = isAuto && (mode === 'nasdaq_araujo_vwap' || mode === 'hyenuk_chu_multibagger' || mode === 'auto');
    if (tfWrapper && tfSelect) {
        tfSelect.disabled = locksTf;
        tfWrapper.classList.remove('opacity-40', 'pointer-events-none', 'filter', 'blur-[0.5px]');
        if (locksTf) {
            if (tfBadge) tfBadge.classList.remove('hidden');
            if (mode === 'nasdaq_araujo_vwap' && tfSelect.value !== '15m') tfSelect.value = '15m';
            if (mode === 'hyenuk_chu_multibagger' && tfSelect.value !== '1h') tfSelect.value = '1h';
        } else {
            if (tfBadge) tfBadge.classList.add('hidden');
        }
        if (mode === 'kula_balam_cava_ruiz' && tfSelect.value !== '5m') {
            tfSelect.value = '5m';
        }
    }

    // 2. TP/SL Porcentual Fijo (bloqueado en todas las cuantitativas automáticas; libre en Manual)
    const tpSlContainer = document.getElementById('manualTpSlSettings');
    const tpSlSelect = document.getElementById('tpSlSelect');
    const tpSlBadge = document.getElementById('tpSlLockBadge');
    const tpSlNotice = document.getElementById('tpSlStrategyNotice');
    const locksTpSl = isAuto && mode !== 'manual';
    if (tpSlContainer && tpSlSelect) {
        tpSlSelect.disabled = locksTpSl;
        if (locksTpSl) {
            tpSlContainer.classList.add('opacity-40', 'pointer-events-none', 'filter', 'blur-[0.5px]');
            if (tpSlBadge) tpSlBadge.classList.remove('hidden');
            if (tpSlNotice) tpSlNotice.innerHTML = '🔒 <span class="text-yellow-400 font-semibold">Gobernado por Algoritmo:</span> Los niveles son calculados dinámicamente por la estrategia.';
        } else {
            tpSlContainer.classList.remove('opacity-40', 'pointer-events-none', 'filter', 'blur-[0.5px]');
            if (tpSlBadge) tpSlBadge.classList.add('hidden');
            if (tpSlNotice) tpSlNotice.innerHTML = '✅ <span class="text-green-400 font-semibold">Activo en Modo Manual:</span> Fija el TP/SL bruto de compras y salidas rápidas.';
        }
    }

    // 3. Tamaño de Posición (Riesgo por Slot) -> SIEMPRE LIBRE para calibración
    const manualRisk = document.getElementById('manualRiskSettings');
    const riskSelect = document.getElementById('riskSelect');
    if (manualRisk && riskSelect) {
        riskSelect.disabled = false;
        manualRisk.classList.remove('opacity-40', 'pointer-events-none', 'filter', 'blur-[0.5px]');
    }

    // 4. Beneficio Neto Mínimo
    const minProfitContainer = document.getElementById('minProfitContainer');
    const minProfitInput = document.getElementById('minProfitPctInput');
    const minProfitNotice = document.getElementById('minProfitNotice');
    if (minProfitContainer && minProfitInput) {
        const locksProfit = isAuto && (mode === 'trailing_trend_runner' || mode === 'trailing_short_runner' || mode === 'mean_reversion_atr');
        minProfitInput.disabled = locksProfit;
        if (locksProfit) {
            minProfitContainer.classList.add('opacity-40', 'pointer-events-none', 'filter', 'blur-[0.5px]');
            if (minProfitNotice) minProfitNotice.innerHTML = '🔒 <span class="text-yellow-400 font-semibold">Regla interna:</span> El límite de toma de ganancias está integrado en la estrategia.';
        } else {
            minProfitContainer.classList.remove('opacity-40', 'pointer-events-none', 'filter', 'blur-[0.5px]');
            if (minProfitNotice) minProfitNotice.innerHTML = 'Se exige sobre el PnL neto tras comisión y spread. No bloquea Stop Loss ni cierre manual.';
        }
    }
}

function updateBrokerFeeDisplay() {
    const rate = getBrokerFeeRate();
    const spread = getEstimatedSpreadRate();
    const badge = document.getElementById('roundTripBadge');
    if (badge) {
        badge.innerText = Number.isFinite(rate) && Number.isFinite(spread)
            ? `Costos ida/vuelta: ${((rate + spread) * 2).toFixed(2)}%`
            : 'Costo inválido';
    }
}

const spreadInput = document.getElementById('spreadInput');
const savedSpreadRaw = localStorage.getItem('ai_spread_estimate_v1');
const savedSpread = Number(savedSpreadRaw);
if (spreadInput && savedSpreadRaw !== null && Number.isFinite(savedSpread) && savedSpread >= 0 && savedSpread <= 5) {
    spreadInput.value = String(savedSpread);
}
spreadInput?.addEventListener('input', () => {
    localStorage.setItem('ai_spread_estimate_v1', spreadInput.value);
    updateBrokerFeeDisplay();
});

const minProfitPctInput = document.getElementById('minProfitPctInput');
const savedMinimumNetProfitRaw = localStorage.getItem('ai_minimum_net_profit_v2');
const savedMinimumNetProfit = Number(savedMinimumNetProfitRaw);
if (
    minProfitPctInput
    && savedMinimumNetProfitRaw !== null
    && Number.isFinite(savedMinimumNetProfit)
    && savedMinimumNetProfit >= 0
    && savedMinimumNetProfit <= 5
) {
    minProfitPctInput.value = String(savedMinimumNetProfit);
}
minProfitPctInput?.addEventListener('change', () => {
    const minimumNetProfit = getMinimumNetProfitPct();
    if (!Number.isFinite(minimumNetProfit)) {
        logToTerminal('⚠️ Beneficio neto mínimo inválido; usa un valor entre 0 y 5%.', 'error');
        return;
    }
    localStorage.setItem('ai_minimum_net_profit_v2', String(minimumNetProfit));
    logToTerminal(`🎯 Beneficio neto mínimo para toma de ganancias: ${minimumNetProfit.toFixed(2)}%. Se aplicará a las próximas posiciones.`, 'info');
});

const strategyModeSelect = document.getElementById('strategyModeSelect');
const savedStrategyMode = localStorage.getItem('ai_strategy_mode_v1');
const validStrategyModes = [
    'donchian_breakout_1h',
    'kula_balam_cava_ruiz',
    'tres_velas_wyckoff_bulkowski',
    'trailing_trend_runner',
    'triple_confluencia_4h',
    'alex_ruiz_triada_3velas',
    'nasdaq_araujo_vwap',
    'hyenuk_chu_multibagger',
    'auto',
    'manual'
];
if (strategyModeSelect) {
    if (savedStrategyMode && validStrategyModes.includes(savedStrategyMode) && savedStrategyMode !== 'auto') {
        strategyModeSelect.value = savedStrategyMode;
    } else {
        strategyModeSelect.value = 'donchian_breakout_1h';
        localStorage.setItem('ai_strategy_mode_v1', 'donchian_breakout_1h');
    }
}
strategyModeSelect?.addEventListener('change', () => {
    const mode = getStrategyMode();
    localStorage.setItem('ai_strategy_mode_v1', mode);
    updateStrategySettingsVisibility();

    // Si el usuario elige manualmente una estrategia fija (no 'auto'), desactivar auto-adaptación para respetar su decisión
    if (mode !== 'auto') {
        const chk = document.getElementById('chkAutoAdaptRegime');
        if (chk && chk.checked) {
            chk.checked = false;
            window.toggleAutoAdaptRegime(false);
            logToTerminal('🔒 Auto-adaptación pausada: el sistema respetará tu modelo matemático elegido.', 'info');
        }
    } else {
        const chk = document.getElementById('chkAutoAdaptRegime');
        if (chk && !chk.checked) {
            chk.checked = true;
            window.toggleAutoAdaptRegime(true);
            logToTerminal('🤖 Piloto Automático activado: auto-adaptación de estrategia reanudada.', 'info');
        }
    }
    if (mode === 'auto') {
        logToTerminal('🔄 Piloto Automático activo: Sincronización continua según sesión horaria y estado del mercado.', 'info');
    } else if (mode === '01_tendencia_institucional_15m') {
        const tfSelect = document.getElementById('timeframeSelect');
        if (tfSelect && tfSelect.value !== '15m') {
            tfSelect.value = '15m';
            tfSelect.dispatchEvent(new Event('change'));
            logToTerminal('🏛️ Tendencia Institucional 15m exige velas de 15m. Ajustando automáticamente.', 'info');
        }
        logToTerminal('🏛️ Tendencia Institucional 15m (Estrategia Cero) activa.', 'info');
        logToTerminal('🔥 Pre-calentando modelo Qwen en Ollama en segundo plano para asegurar respuesta rápida...', 'action');
        fetch(`${API_BASE_URL}/api/ollama/warmup?model=qwen2.5-coder:7b`, { method: 'POST', headers: apiAuthHeaders() }).catch(() => {});
    } else if (mode === 'mean_reversion_atr') {
        const tfSelect = document.getElementById('timeframeSelect');
        if (tfSelect && !tradingGuards.isAllowedAtrTimeframe(tfSelect.value)) {
            tfSelect.value = '15m';
            tfSelect.dispatchEvent(new Event('change'));
            logToTerminal('ℹ️ La estrategia ATR requiere temporalidad de 15m o 1h. Ajustando automáticamente a 15m.', 'info');
        }
        logToTerminal('🧮 Estrategia cuantitativa ATR seleccionada para las próximas posiciones.', 'info');
    } else if (mode === 'nasdaq_araujo_vwap') {
        const tfSelect = document.getElementById('timeframeSelect');
        if (tfSelect && tfSelect.value !== '15m') {
            tfSelect.value = '15m';
            tfSelect.dispatchEvent(new Event('change'));
            logToTerminal('🏛️ La estrategia Nasdaq Araujo exige temporalidad de 15m. Ajustando automáticamente a 15m.', 'info');
        }
        logToTerminal('🏛️ Estrategia Nasdaq Araujo (M15 + VWAP + Sesión Londres) seleccionada: 1 trade/día.', 'info');
    } else if (mode === 'hyenuk_chu_multibagger') {
        const tfSelect = document.getElementById('timeframeSelect');
        if (tfSelect && tfSelect.value !== '1h') {
            tfSelect.value = '1h';
            tfSelect.dispatchEvent(new Event('change'));
            logToTerminal('📈 La estrategia Hyenuk Chu opera en temporalidad de 1h. Ajustando automáticamente a 1h.', 'info');
        }
        logToTerminal('📈 Estrategia Hyenuk Chu (1h · Trend Following + Peluqueo 50% y Runner 2 a 10 días) seleccionada.', 'info');
    } else if (mode === 'trailing_trend_runner') {
        const tfSelect = document.getElementById('timeframeSelect');
        if (tfSelect && !['5m', '15m', '1h', '4h'].includes(tfSelect.value)) {
            tfSelect.value = '15m';
            tfSelect.dispatchEvent(new Event('change'));
            logToTerminal('ℹ️ La estrategia Trailing Dinámico opera en 5m, 15m, 1h o 4h. Ajustando automáticamente a 15m.', 'info');
        }
        logToTerminal('🚀 Estrategia Trailing Dinámico: Tendencia sin Techo (Idea Raúl) seleccionada: Stop dinámico móvil sin TP rígido.', 'info');
    } else if (mode === 'trailing_short_runner') {
        const tfSelect = document.getElementById('timeframeSelect');
        if (tfSelect && !['5m', '15m', '1h', '4h'].includes(tfSelect.value)) {
            tfSelect.value = '15m';
            tfSelect.dispatchEvent(new Event('change'));
            logToTerminal('ℹ️ La estrategia Trailing en Corto opera en 5m, 15m, 1h o 4h. Ajustando automáticamente a 15m.', 'info');
        }
        logToTerminal('🔻 Estrategia Trailing en Corto: Caída sin Suelo (Shorting Raúl) seleccionada: Venta en corto con stop dinámico móvil.', 'info');
    } else if (mode === 'kula_balam_cava_ruiz') {
        const tfSelect = document.getElementById('timeframeSelect');
        if (tfSelect && !['5m', '15m', '1h', '1d'].includes(tfSelect.value)) {
            tfSelect.value = '5m';
            tfSelect.dispatchEvent(new Event('change'));
            logToTerminal('🐅 Kula Balam Cava & Ruiz opera en gatillo 5m con contexto 1D y 1H. Sincronizando visualización a 5m.', 'info');
        }
        logToTerminal('🐅 Estrategia Maestra Kula Balam: Cava & Ruiz (Tríada 1D-1H-5M & Fallo MACD) seleccionada.', 'info');
    } else if (mode === 'tres_velas_wyckoff_bulkowski') {
        logToTerminal('🕯️ Estrategia Tres Velas & Wyckoff VPA (Bulkowski & Proporción Áurea Φ) seleccionada.', 'info');
    } else {
        logToTerminal('⚙️ Estrategia manual seleccionada: TP/SL del panel.', 'info');
    }
    if (portfolio && portfolio.position) {
        portfolio.position.strategyMode = mode;
        if (mode === 'trailing_trend_runner' || mode === 'trailing_short_runner') {
            portfolio.position.trailPct = portfolio.position.sl || 1.5;
        }
        localStorage.setItem('ai_portfolio_v5', JSON.stringify(portfolio));
    }
    if (typeof syncRunningDaemonConfig === 'function') syncRunningDaemonConfig();
});
updateStrategySettingsVisibility();
setInterval(updateStrategySettingsVisibility, 30000); // Actualizar reloj de sesión bursátil en vivo cada 30 segundos

// Inicializar el switch maestro de modo de estrategia
window.setMasterStrategyMode(window.isMasterAutoMode());

// --- ESCÁNER RÁPIDO DE MERCADO CON INYECCIÓN INMEDIATA (:8520 -> :18767) ---
window.triggerQuickMarketScan = async function() {
    const categorySelect = document.getElementById('quickMarketCategory');
    const category = categorySelect ? categorySelect.value : '';
    const statusLabel = document.getElementById('quickScanStatus');
    const spinner = document.getElementById('quickScanSpinner');
    const btn = document.getElementById('btnQuickMarketScan');

    if (spinner) spinner.classList.remove('hidden');
    if (statusLabel) statusLabel.innerText = 'Escaneando...';
    if (btn) btn.disabled = true;

    try {
        logToTerminal(`📡 Consultando Monitor del Mercado (:8520) [Categoría: ${category || 'Todas'}]...`, 'info');
        const url = `http://127.0.0.1:8520/api/cio/candidates?limit=5${category ? '&category=' + encodeURIComponent(category) : ''}`;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);

        const res = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!res.ok) {
            throw new Error(`Monitor respondió con status ${res.status}`);
        }
        const data = await res.json();
        const news = data.news || [];
        const tickers = data.tickers || [];

        if (news.length === 0 && tickers.length === 0) {
            if (statusLabel) statusLabel.innerText = 'Sin candidatos';
            logToTerminal('ℹ️ El Monitor no detectó candidatos de capitulación en esta categoría en este momento.', 'info');
            return;
        }

        // Inyectar el mejor candidato al instante
        const firstNews = news[0] || {};
        const asset = tickers[0] || firstNews.ticker || 'QQQ';
        const text = firstNews.title ? `${firstNews.title}. ${firstNews.summary || ''}` : `Oportunidad asimétrica detectada en ${asset}.`;
        
        logToTerminal(`⚡ Inyectando directiva inmediata de ${asset} a Kula Balam...`, 'info');
        const injectRes = await fetch(`${API_BASE_URL}/api/macro/inject`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                asset: asset,
                text: text,
                confidence: 85,
                type: 'Oportunidad',
                source: 'Escaneo Rápido de Mercado'
            })
        });

        if (injectRes.ok) {
            if (statusLabel) statusLabel.innerText = `Inyectado: ${asset}`;
            logToTerminal(`✅ Oportunidad en ${asset} inyectada al momento en el buzón radar del bot.`, 'success');
            if (typeof updateMacroRadar === 'function') updateMacroRadar();
        } else {
            if (statusLabel) statusLabel.innerText = 'Fallo inyección';
            logToTerminal('⚠️ Error al registrar en buzón radar.', 'warning');
        }
    } catch (err) {
        if (statusLabel) statusLabel.innerText = 'Monitor desconectado';
        logToTerminal(`⚠️ Monitor del Mercado (puerto 8520) no responde: ${err.message || err}. Verifica que esté iniciado.`, 'warning');
    } finally {
        if (spinner) spinner.classList.add('hidden');
        if (btn) btn.disabled = false;
        setTimeout(() => { if (statusLabel) statusLabel.innerText = 'Listo'; }, 4000);
    }
};

// --- ADAPTADOR DE RÉGIMEN DE MERCADO (100% CÓDIGO DETERMINISTA - 0 TOKENS) ---
const REGIME_STRATEGY_MAP = {
    'TORO': {
        id: 'hyenuk_chu_multibagger',
        label: '📈 Seguidor de Tendencia con Ganancia Asegurada',
        badgeClass: 'text-emerald-400 font-bold',
        badgeText: '🐂 ALCISTA (Toro / Tendencia)'
    },
    'OSO': {
        id: 'mean_reversion_atr',
        label: '🧯 Cazador de Rebotes tras Caída Fuerte',
        badgeClass: 'text-red-400 font-bold',
        badgeText: '🐻 BAJISTA (Oso / Capitulación)'
    },
    'LATERAL': {
        id: 'nasdaq_araujo_vwap',
        label: '🎯 Francotirador de Apertura de Bolsa (Rango)',
        badgeClass: 'text-yellow-400 font-bold',
        badgeText: '↔️ LATERAL (Rango / Consolidación)'
    }
};

window.currentSuggestedRegimeStrategy = 'auto';

window.isAutoAdaptRegime = function() {
    const saved = localStorage.getItem('auto_adapt_regime_active');
    return saved !== null ? saved === 'true' : true;
};

window.initMarketRegimeCard = function() {
    const chk = document.getElementById('chkAutoAdaptRegime');
    const isAuto = window.isAutoAdaptRegime();
    if (chk) chk.checked = isAuto;
    const btnApply = document.getElementById('btnApplyRegimeSuggestion');
    if (btnApply) {
        if (isAuto) btnApply.classList.add('hidden');
        else btnApply.classList.remove('hidden');
    }
    if (typeof window.updateAutoAdaptBanner === 'function') {
        window.updateAutoAdaptBanner(isAuto);
    }
};

window.classifyMarketRegime = function(data) {
    if (!data) return 'LATERAL';
    const text = ((data.text || '') + ' ' + (data.asset || '') + ' ' + (data.type || '') + ' ' + (data.source || '')).toLowerCase();

    // 1. Detección de pánico / capitulación / oso (Bear)
    if (text.includes('bajista') || text.includes('oso') || text.includes('bear') || 
        text.includes('pánico') || text.includes('panico') || text.includes('capitulación') ||
        text.includes('capitulacion') || text.includes('desplome') || text.includes('sobreventa') ||
        text.includes('peligro') || text.includes('caída fuerte') || text.includes('caida')) {
        return 'OSO';
    }

    // 2. Detección de tendencia alcista / toro (Bull)
    if (text.includes('alcista') || text.includes('toro') || text.includes('bull') ||
        text.includes('máximos') || text.includes('maximos') || text.includes('rally') ||
        text.includes('multibagger') || text.includes('suba sostenida') || text.includes('expansión')) {
        return 'TORO';
    }

    // 3. Indicadores numéricos en el texto (ej. RSI o Z-Score)
    const zMatch = text.match(/z-score:\s*(-?[\d.]+)/);
    if (zMatch && parseFloat(zMatch[1]) <= -1.8) return 'OSO';
    if (zMatch && parseFloat(zMatch[1]) >= 1.8) return 'TORO';

    const rsiMatch = text.match(/rsi:\s*([\d.]+)/);
    if (rsiMatch && parseFloat(rsiMatch[1]) <= 30) return 'OSO';
    if (rsiMatch && parseFloat(rsiMatch[1]) >= 70) return 'TORO';

    if ((data.type || '').toUpperCase() === 'PELIGRO') return 'OSO';

    return 'LATERAL';
};

window.syncMarketRegimeFromData = function(data) {
    if (!data) return;
    const regimeKey = window.classifyMarketRegime(data);
    const regimeConfig = REGIME_STRATEGY_MAP[regimeKey] || REGIME_STRATEGY_MAP['LATERAL'];
    window.currentSuggestedRegimeStrategy = regimeConfig.id;

    const badge = document.getElementById('marketRegimeBadge');
    const source = document.getElementById('marketRegimeSource');
    const suggestion = document.getElementById('marketRegimeSuggestion');
    const btnApply = document.getElementById('btnApplyRegimeSuggestion');
    const chk = document.getElementById('chkAutoAdaptRegime');

    if (badge) {
        badge.className = `text-xs ${regimeConfig.badgeClass}`;
        badge.innerText = regimeConfig.badgeText;
    }
    if (source) {
        let timeStr = 'Reciente';
        if (data.timestamp) {
            try {
                timeStr = new Date(data.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } catch (e) {}
        }
        const sourceName = data.source || 'Monitor del Mercado';
        source.innerText = `${sourceName} (${timeStr})`;
    }
    if (suggestion) {
        suggestion.innerText = regimeConfig.label;
    }

    const autoAdapt = window.isAutoAdaptRegime();
    if (chk) chk.checked = autoAdapt;
    if (typeof window.updateAutoAdaptBanner === 'function') {
        window.updateAutoAdaptBanner(autoAdapt);
    }

    if (autoAdapt) {
        if (btnApply) btnApply.classList.add('hidden');
        const stratSelect = document.getElementById('strategyModeSelect');
        if (stratSelect && stratSelect.value !== regimeConfig.id) {
            stratSelect.value = regimeConfig.id;
            stratSelect.dispatchEvent(new Event('change'));
            if (typeof window.updateSelectiveBlur === 'function') {
                window.updateSelectiveBlur(regimeConfig.id);
            }
            logToTerminal(`⚡ [RÉGIMEN ${regimeKey}] Estrategia adaptada automáticamente a: ${regimeConfig.label}`, 'action');
        }
    } else {
        if (btnApply) btnApply.classList.remove('hidden');
    }
};

window.toggleAutoAdaptRegime = function(checked) {
    localStorage.setItem('auto_adapt_regime_active', checked ? 'true' : 'false');
    const btnApply = document.getElementById('btnApplyRegimeSuggestion');
    if (checked) {
        if (btnApply) btnApply.classList.add('hidden');
        window.applyMarketRegimeSuggestion();
    } else {
        if (btnApply) btnApply.classList.remove('hidden');
        logToTerminal('🛠️ Auto-adaptación de régimen desactivada. Estrategia bajo control manual.', 'info');
    }
    if (typeof window.updateAutoAdaptBanner === 'function') {
        window.updateAutoAdaptBanner(checked);
    }
};

window.toggleAutoAdaptFromBanner = function() {
    const chk = document.getElementById('chkAutoAdaptRegime');
    const isAutoNow = window.isAutoAdaptRegime();
    const nextState = !isAutoNow;
    if (chk) chk.checked = nextState;
    window.toggleAutoAdaptRegime(nextState);
};

window.selectManualStrategyDirect = function(stratId) {
    const stratSelect = document.getElementById('strategyModeSelect');
    if (stratSelect) {
        stratSelect.value = stratId;
        stratSelect.dispatchEvent(new Event('change'));
    }
    const chk = document.getElementById('chkAutoAdaptRegime');
    if (chk && chk.checked) {
        chk.checked = false;
        window.toggleAutoAdaptRegime(false);
    }
    window.updateAutoAdaptBanner(false, stratId);
    logToTerminal(`👤 [CONTROL MANUAL] Modelo seleccionado: ${stratId}.`, 'action');
};

window.updateAutoAdaptBanner = function(isAuto, currentStrat) {
    const banner = document.getElementById('autoAdaptBannerCard');
    const heading = document.getElementById('autoAdaptHeadingText');
    const subtext = document.getElementById('autoAdaptSubText');
    const icon = document.getElementById('autoAdaptIcon');
    const btnText = document.getElementById('btnToggleAutoAdaptBannerText');
    const btn = document.getElementById('btnToggleAutoAdaptBanner');
    const manualPicker = document.getElementById('autoAdaptManualPicker');

    if (!banner) return;

    if (isAuto) {
        banner.className = 'bg-gradient-to-r from-emerald-950/80 via-gray-900 to-emerald-950/50 border border-emerald-500/60 rounded-xl p-3.5 shadow-xl transition-all duration-300';
        if (icon) icon.innerText = '🤖';
        if (heading) heading.innerText = 'Piloto Inteligente: AUTO-ADAPTACIÓN ACTIVA';
        if (subtext) subtext.innerText = 'El bot cambia de estrategia solo según la hora, volatilidad y régimen de mercado.';
        if (btn) btn.className = 'px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white border border-emerald-400 shadow cursor-pointer transition whitespace-nowrap flex items-center gap-1.5';
        if (btnText) btnText.innerText = 'ACTIVO';
        if (manualPicker) manualPicker.classList.add('hidden');
    } else {
        banner.className = 'bg-gradient-to-r from-amber-950/80 via-gray-900 to-amber-950/50 border border-amber-500/60 rounded-xl p-3.5 shadow-xl transition-all duration-300';
        if (icon) icon.innerText = '👤';
        if (heading) heading.innerText = 'Control Manual: AUTO-ADAPTACIÓN PAUSADA';
        if (subtext) subtext.innerText = 'El bot respetará estrictamente el modelo matemático que elijas sin intervenir.';
        if (btn) btn.className = 'px-3 py-1 rounded-full text-[11px] font-bold bg-amber-600 hover:bg-amber-500 text-white border border-amber-400 shadow cursor-pointer transition whitespace-nowrap flex items-center gap-1.5';
        if (btnText) btnText.innerText = 'PAUSADO';
        if (manualPicker) manualPicker.classList.remove('hidden');
    }
};

window.applyMarketRegimeSuggestion = function() {
    if (!window.currentSuggestedRegimeStrategy) return;
    const stratSelect = document.getElementById('strategyModeSelect');
    if (stratSelect && stratSelect.value !== window.currentSuggestedRegimeStrategy) {
        stratSelect.value = window.currentSuggestedRegimeStrategy;
        stratSelect.dispatchEvent(new Event('change'));
        if (typeof window.updateSelectiveBlur === 'function') {
            window.updateSelectiveBlur(window.currentSuggestedRegimeStrategy);
        }
        logToTerminal(`⚡ Estrategia fijada a: ${stratSelect.options[stratSelect.selectedIndex].text} según el régimen del mercado.`, 'action');
    }
};

// --- COPILOTO ASESOR DE ESTRATEGIA (CHAT AL PIE) ---
window.sendAdvisorMessage = async function() {
    const input = document.getElementById('advisorInputText');
    const container = document.getElementById('advisorChatMessages');
    const spinner = document.getElementById('advisorSpinner');
    const btn = document.getElementById('btnSendAdvisorPrompt');
    if (!input || !container) return;

    const userText = input.value.trim();
    if (!userText) return;

    // Agregar mensaje del usuario al chat
    const userMsg = document.createElement('div');
    userMsg.className = 'bg-cyan-950/60 p-2 rounded border border-cyan-800 text-cyan-200 text-right';
    userMsg.innerHTML = `<span class="font-bold block text-[10px] text-cyan-400">👤 Vos:</span> ${escapeHtml(userText)}`;
    container.appendChild(userMsg);
    input.value = '';
    container.scrollTop = container.scrollHeight;

    if (spinner) spinner.classList.remove('hidden');
    if (btn) btn.disabled = true;

    try {
        const symbol = typeof currentSymbol !== 'undefined' ? currentSymbol : 'BTC/USDT';
        const currentStrat = getStrategyMode();
        const res = await fetch(`${API_BASE_URL}/api/strategy/advisor`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                user_prompt: userText,
                symbol: symbol,
                current_strategy: currentStrat
            })
        });

        const data = await res.json();
        const recId = data.recommended_strategy_id || 'auto';
        const recName = data.recommended_strategy_name || 'Piloto Automático';
        const reason = data.reason || 'Recomendación analizada.';
        const actionPlan = data.action_plan || '';

        const botMsg = document.createElement('div');
        botMsg.className = 'bg-gray-800 p-2.5 rounded border border-cyan-500/50 text-gray-200 shadow-md space-y-1.5';
        botMsg.innerHTML = `
            <div class="flex items-center justify-between border-b border-gray-700/80 pb-1">
                <span class="text-cyan-400 font-bold text-[11px]">🤖 Copiloto Asesor:</span>
                <span class="text-[9px] bg-cyan-900/60 text-cyan-300 px-1 rounded font-mono">RECOMENDACIÓN</span>
            </div>
            <p class="text-[11px] leading-snug"><strong class="text-white">Estrategia recomendada:</strong> <span class="text-emerald-400 font-bold">${escapeHtml(recName)}</span></p>
            <p class="text-[10.5px] text-gray-300 leading-snug">${escapeHtml(reason)}</p>
            <p class="text-[10px] text-gray-400 italic">Plan: ${escapeHtml(actionPlan)}</p>
            <div class="pt-1">
                <button type="button" onclick="window.applyStrategyFromAdvisor('${escapeHtml(recId)}')" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-1 px-2 rounded text-xs transition shadow flex items-center justify-center gap-1 cursor-pointer">
                    <span>⚡</span> Aplicar "${escapeHtml(recName)}" Ahora
                </button>
            </div>
        `;
        container.appendChild(botMsg);
        container.scrollTop = container.scrollHeight;
    } catch (err) {
        const errMsg = document.createElement('div');
        errMsg.className = 'bg-red-900/40 p-2 rounded border border-red-700 text-red-200';
        errMsg.innerHTML = `⚠️ No se pudo consultar al asesor: ${escapeHtml(err.message || err)}`;
        container.appendChild(errMsg);
        container.scrollTop = container.scrollHeight;
    } finally {
        if (spinner) spinner.classList.add('hidden');
        if (btn) btn.disabled = false;
    }
};

window.applyStrategyFromAdvisor = function(strategyId) {
    const select = document.getElementById('strategyModeSelect');
    if (!select) return;
    select.value = strategyId;
    select.dispatchEvent(new Event('change'));
    window.setMasterStrategyMode(true);
    logToTerminal(`⚡ Estrategia '${strategyId}' aplicada automáticamente desde el Copiloto Asesor.`, 'success');

    // Confirmación en el chat
    const container = document.getElementById('advisorChatMessages');
    if (container) {
        const conf = document.createElement('div');
        conf.className = 'p-1.5 rounded bg-emerald-950/60 border border-emerald-700/60 text-[10.5px] text-emerald-300 flex items-center gap-1';
        conf.innerHTML = `<span>✅</span> <strong>Estrategia aplicada con éxito.</strong> Los parámetros de riesgo se calibraron para este modelo.`;
        container.appendChild(conf);
        container.scrollTop = container.scrollHeight;
    }
};


const quantRiskBudgetSelect = document.getElementById('quantRiskBudgetSelect');
const savedQuantRiskBudget = Number(localStorage.getItem('ai_quant_risk_budget_v1'));
if (quantRiskBudgetSelect && [0.25, 0.5, 1].includes(savedQuantRiskBudget)) {
    quantRiskBudgetSelect.value = String(savedQuantRiskBudget);
}
quantRiskBudgetSelect?.addEventListener('change', () => {
    const budget = getQuantRiskBudgetPct();
    if (!Number.isFinite(budget)) {
        logToTerminal('⚠️ Presupuesto de riesgo inválido; selecciona un valor mayor que 0 y hasta 1%.', 'error');
        return;
    }
    localStorage.setItem('ai_quant_risk_budget_v1', quantRiskBudgetSelect.value);
});

let tradeHistoryLog = JSON.parse(localStorage.getItem('ai_trade_history_v2')) || [];
if (!Array.isArray(tradeHistoryLog)) tradeHistoryLog = [];

// --- GESTIÓN DE SESIONES OPERATIVAS ---
// Permite distinguir visualmente las operaciones realizadas antes y después de suspender el agente
let currentSessionId = parseInt(localStorage.getItem('ai_current_session_id') || '1');
if (isNaN(currentSessionId) || currentSessionId < 1) currentSessionId = 1;

// Sincronizar sessionId con el máximo registrado en el log histórico
const maxSessionInLog = tradeHistoryLog.reduce((max, t) => Math.max(max, t.sessionId || 1), 1);
if (currentSessionId < maxSessionInLog) {
    currentSessionId = maxSessionInLog;
}

// Banderas para detectar cuando el agente fue suspendido y se reanuda
let agentWasSuspended = tradeHistoryLog.length > 0;
let isCopilotApprovalPause = false;

// --- GESTIÓN DE CAPITAL: INGRESAR Y LIMPIAR FONDOS ---
// --- ESTACIÓN INSTITUCIONAL DE GESTIÓN DE CAPITAL (BROKER & TRADING DESK) ---

// Variable reactiva en memoria para Dinero para Operar
window.currentOperatingCapital = window.currentOperatingCapital || { USDT: 0.0, USD: 0.0, ARS: 0.0 };

window.updateRiskSlotPreview = function() {
    const cur = typeof getCurrency === 'function' ? getCurrency(currentSymbol) : 'USDT';
    const riskSelect = document.getElementById('riskSelect');
    const slotText = document.getElementById('riskSlotAmountText');
    if (!riskSelect || !slotText) return;

    const riskFrac = parseFloat(riskSelect.value) || 0.25;
    const totalEq = Number(window.currentTotalEquity?.[cur] ?? (Number(portfolio?.vault?.[cur] || 0) + Number(portfolio?.balances?.[cur] || 0)));
    const rawOp = window.currentOperatingCapital?.[cur];
    const opCap = Math.max(0.0, Math.min(totalEq, (rawOp !== undefined && Number.isFinite(Number(rawOp))) ? Number(rawOp) : totalEq));
    const slotAmt = opCap * riskFrac;
    const slotsCount = Math.max(1, Math.round(1 / riskFrac));

    if (opCap <= 0) {
        slotText.innerText = `$0.00 ${cur} (${Math.round(riskFrac * 100)}% · Sin capital para operar)`;
    } else {
        slotText.innerText = `$${slotAmt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${cur} (${Math.round(riskFrac * 100)}% · 1/${slotsCount} slots)`;
    }

    const selScalpingSlot = document.getElementById('selScalpingSlot');
    const txtScalpingSlotUsd = document.getElementById('txtScalpingSlotUsd');
    if (selScalpingSlot && !selScalpingSlot.disabled && [...selScalpingSlot.options].some(o => o.value === riskSelect.value)) {
        selScalpingSlot.value = riskSelect.value;
    }
    if (txtScalpingSlotUsd) {
        const rawScalpSym = document.getElementById('selScalpingSymbol')?.value || currentSymbol;
        const scalpSym = rawScalpSym === 'MULTI_CRYPTO' ? 'ETH/USDT' : rawScalpSym;
        const scalpCur = typeof getCurrency === 'function' ? getCurrency(scalpSym) : cur;
        const scalpTotEq = Number(window.currentTotalEquity?.[scalpCur] ?? (Number(portfolio?.vault?.[scalpCur] || 0) + Number(portfolio?.balances?.[scalpCur] || 0)));
        const scalpRawOp = window.currentOperatingCapital?.[scalpCur];
        const scalpOpCap = Math.max(0.0, Math.min(scalpTotEq, (scalpRawOp !== undefined && Number.isFinite(Number(scalpRawOp))) ? Number(scalpRawOp) : scalpTotEq));
        const effFrac = riskFrac >= 0.99 ? 0.95 : riskFrac;
        const scalpAmt = scalpOpCap * effFrac;
        txtScalpingSlotUsd.innerText = scalpOpCap <= 0
            ? `$0 ${scalpCur}`
            : `≤ $${scalpAmt.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${scalpCur}`;
    }

    if (typeof window.updateVaultSlotsThermometer === 'function') {
        window.updateVaultSlotsThermometer(null, cur);
    }
};

window.ingresarAlBrokerModal = async function() {
    const cur = getCurrency(currentSymbol);
    let input;
    if (window.UIFeedback) {
        input = await window.UIFeedback.prompt(
            `Indica el monto a depositar en la Bóveda del Broker (${cur}):\nEste ingreso afecta únicamente al dinero real/paper del Broker (no modifica el libro de inversores).`,
            "500",
            {
                title: `Ingresar Fondos al Broker (${cur})`,
                icon: "🏛️",
                placeholder: "Ej: 100, 500, 1000",
                inputType: "number"
            }
        );
    } else {
        input = prompt(`Ingresar dinero al Broker (${cur}):\n(Independiente del libro de inversores)\n\nIndica el monto a depositar:`, "500");
    }
    if (!input) return;
    const amount = parseFloat(input);
    if (!Number.isFinite(amount) || amount <= 0) {
        const msg = "Por favor ingresa un monto numérico positivo.";
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "warning", title: "Monto Inválido" });
        else alert(msg);
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/broker/deposit`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ amount: amount, currency: cur })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.vault) {
                portfolio.vault = {
                    USDT: Number(data.vault.USDT) || 0,
                    USD: Number(data.vault.USD) || 0,
                    ARS: Number(data.vault.ARS) || 0,
                };
            }
            if (data.operating_capital !== undefined) {
                const newEq = Number(data.total_equity?.[cur] ?? (Number(data.vault?.[cur] || 0) + Number(portfolio?.balances?.[cur] || 0)));
                const cleanOp = Number(data.operating_capital);
                window.currentOperatingCapital[cur] = (Number.isFinite(cleanOp) && cleanOp > 0) ? Math.min(cleanOp, newEq) : 0.0;
            }
            localStorage.setItem('ai_portfolio_v5', JSON.stringify(portfolio));
            await updateCapitalDisplay();
            if (investorsView && !investorsView.classList.contains('hidden')) {
                await fetchInvestorsData();
            }
            logToTerminal(`🏛️ [DEPÓSITO BROKER] Se ingresaron $${amount.toFixed(2)} ${cur} a la Bóveda del Broker (libro de inversores independiente).`, 'success');
            if (window.UIFeedback) {
                window.UIFeedback.toast(`Se ingresaron $${amount.toFixed(2)} ${cur} al Broker.`, { type: "success", title: "Depósito en Broker Exitoso" });
            }
        } else {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Error en el servidor");
        }
    } catch (e) {
        logToTerminal(`⚠️ Error depositando en Broker: ${e.message}`, 'error');
        if (window.UIFeedback) window.UIFeedback.toast(e.message, { type: "error", title: "Error en Depósito" });
    }
};

window.ingresarDineroModal = window.ingresarAlBrokerModal;

window.retirarDelBrokerModal = async function() {
    const cur = getCurrency(currentSymbol);
    const available = Number(portfolio?.vault?.[cur] || 0);

    if (available <= 0) {
        const msg = `No hay efectivo libre en la Bóveda del Broker (${cur}) para retirar. Cierra posiciones activas si necesitas liberar efectivo.`;
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "warning", title: "Sin Efectivo Libre" });
        else alert(msg);
        return;
    }

    let input;
    if (window.UIFeedback) {
        input = await window.UIFeedback.prompt(
            `Efectivo libre en la Bóveda del Broker: $${available.toFixed(2)} ${cur}.\nEste retiro afecta únicamente al Broker (el libro de inversores es independiente).\n\nIndica el monto a retirar:`,
            String(available.toFixed(2)),
            {
                title: `Retirar Fondos del Broker (${cur})`,
                icon: "🏦",
                placeholder: `Monto hasta ${available.toFixed(2)}`,
                inputType: "number"
            }
        );
    } else {
        input = prompt(`Retirar dinero del Broker (${cur}):\nEfectivo disponible en Bóveda: $${available.toFixed(2)} ${cur}\n\nIndica el monto a retirar:`, String(available.toFixed(2)));
    }
    if (!input) return;
    const amount = parseFloat(input);
    if (!Number.isFinite(amount) || amount <= 0) {
        const msg = "Por favor ingresa un monto numérico positivo.";
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "warning", title: "Monto Inválido" });
        else alert(msg);
        return;
    }
    if (amount > available) {
        const msg = `El monto excede el efectivo libre en Bóveda ($${available.toFixed(2)} ${cur}).`;
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "error", title: "Efectivo Insuficiente" });
        else alert(msg);
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/broker/withdraw`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ amount: amount, currency: cur })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.vault) {
                portfolio.vault = {
                    USDT: Number(data.vault.USDT) || 0,
                    USD: Number(data.vault.USD) || 0,
                    ARS: Number(data.vault.ARS) || 0,
                };
            }
            if (data.operating_capital !== undefined) {
                const newEq = Number(data.total_equity?.[cur] ?? (Number(data.vault?.[cur] || 0) + Number(portfolio?.balances?.[cur] || 0)));
                const cleanOp = Number(data.operating_capital);
                window.currentOperatingCapital[cur] = (Number.isFinite(cleanOp) && cleanOp > 0) ? Math.min(cleanOp, newEq) : 0.0;
            }
            localStorage.setItem('ai_portfolio_v5', JSON.stringify(portfolio));
            await updateCapitalDisplay();
            if (investorsView && !investorsView.classList.contains('hidden')) {
                await fetchInvestorsData();
            }
            logToTerminal(`🏦 [RETIRO BROKER] Se retiraron $${amount.toFixed(2)} ${cur} de la Bóveda del Broker (libro de inversores independiente).`, 'info');
            if (window.UIFeedback) {
                window.UIFeedback.toast(`Se retiraron $${amount.toFixed(2)} ${cur} del Broker con éxito.`, { type: "success", title: "Retiro Exitoso" });
            }
        } else {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Error en el servidor");
        }
    } catch (e) {
        logToTerminal(`⚠️ Error retirando de Broker: ${e.message}`, 'error');
        if (window.UIFeedback) window.UIFeedback.toast(e.message, { type: "error", title: "Error en Retiro" });
    }
};

window.retirarDineroModal = window.retirarDelBrokerModal;

window.asignarCapitalOperarModal = async function() {
    const cur = getCurrency(currentSymbol);
    const vaultBal = Number(portfolio?.vault?.[cur] || 0);
    const usedBal = Number(window.currentOperationalUsed?.[cur] || portfolio?.balances?.[cur] || 0);
    const totalEquity = Math.max(0.0, Number(window.currentTotalEquity?.[cur] ?? (vaultBal + usedBal)));
    const rawOp = window.currentOperatingCapital?.[cur];
    const curOp = Math.max(0.0, Math.min(totalEquity, (rawOp !== undefined && Number.isFinite(Number(rawOp))) ? Number(rawOp) : totalEquity));

    if (totalEquity <= 0) {
        const msg = `El Broker no tiene fondos en ${cur} ($0.00). Primero ingresa dinero a la Bóveda del Broker antes de asignar cupo para operar.`;
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "warning", title: "Sin Fondos en Broker" });
        else alert(msg);
        return;
    }

    let input;
    if (window.UIFeedback) {
        input = await window.UIFeedback.prompt(
            `Patrimonio Total en el Broker: $${totalEquity.toFixed(2)} ${cur} (Bóveda: $${vaultBal.toFixed(2)} + En Activos: $${usedBal.toFixed(2)}).\nCupo actual asignado para operar: $${curOp.toFixed(2)} ${cur}.\n\nIndica el cupo TOTAL que deseas asignar para operar (mínimo en uso: $${usedBal.toFixed(2)}, máximo: $${totalEquity.toFixed(2)}):`,
            String(totalEquity > 0 ? Math.min(curOp || totalEquity, totalEquity).toFixed(2) : "0.00"),
            {
                title: `Asignar Dinero para Operar (${cur})`,
                icon: "⚡",
                placeholder: `Hasta $${totalEquity.toFixed(2)}`,
                inputType: "number"
            }
        );
    } else {
        input = prompt(`Asignar Dinero para Operar (${cur}):\nPatrimonio Total Broker: $${totalEquity.toFixed(2)}\nCupo Actual: $${curOp.toFixed(2)}\n\nIngresa el monto para operar:`, String(totalEquity > 0 ? Math.min(curOp || totalEquity, totalEquity).toFixed(2) : "0.00"));
    }
    if (!input) return;
    const amount = parseFloat(input);
    if (!Number.isFinite(amount) || amount <= 0) {
        const msg = "Por favor ingresa un monto numérico positivo.";
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "warning", title: "Monto Inválido" });
        else alert(msg);
        return;
    }
    if (amount > totalEquity + 0.01) {
        const msg = `El capital para operar no puede superar el Patrimonio Total del Broker ($${totalEquity.toFixed(2)} ${cur}).`;
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "error", title: "Excede Patrimonio Broker" });
        else alert(msg);
        return;
    }
    if (amount + 0.01 < usedBal) {
        const msg = `Actualmente tienes $${usedBal.toFixed(2)} ${cur} invertidos en activos abiertos. El cupo para operar no puede ser menor a ese monto.`;
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "warning", title: "Capital en Uso" });
        else alert(msg);
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/broker/operating-capital`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ action: "set", amount: amount, currency: cur })
        });
        if (res.ok) {
            const data = await res.json();
            const opVal = Number(data.operating_capital);
            window.currentOperatingCapital[cur] = (Number.isFinite(opVal) && opVal >= 0) ? Math.min(opVal, totalEquity) : amount;
            await updateCapitalDisplay();
            logToTerminal(`⚡ [CAPITAL ASIGNADO] Cupo de Dinero para Operar actualizado a $${amount.toFixed(2)} ${cur}. El resto queda en Reserva Protegida.`, 'action');
            if (window.UIFeedback) {
                window.UIFeedback.toast(`Dinero para operar fijado en $${amount.toFixed(2)} ${cur}.`, { type: "success", title: "Trading Desk Configurado" });
            }
        } else {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Error configurando capital para operar");
        }
    } catch (e) {
        logToTerminal(`⚠️ Error asignando capital: ${e.message}`, 'error');
        if (window.UIFeedback) window.UIFeedback.toast(e.message, { type: "error", title: "Error" });
    }
};

window.devolverAlBrokerModal = async function() {
    const cur = getCurrency(currentSymbol);
    const totalEquity = Math.max(0.0, Number(window.currentTotalEquity?.[cur] ?? ((Number(portfolio?.vault?.[cur] || 0)) + (Number(window.currentOperationalUsed?.[cur] || 0)))));
    const rawOp = window.currentOperatingCapital?.[cur];
    const curOp = Math.max(0.0, Math.min(totalEquity, (rawOp !== undefined && Number.isFinite(Number(rawOp))) ? Number(rawOp) : 0.0));
    const usedBal = Number(window.currentOperationalUsed?.[cur] || portfolio?.balances?.[cur] || 0);
    const maxReturnable = Math.max(0.0, curOp - usedBal);

    if (maxReturnable <= 0) {
        const msg = `No hay cupo libre en la mesa de operaciones para devolver (Cupo: $${curOp.toFixed(2)} ${cur}, en activos abiertos: $${usedBal.toFixed(2)} ${cur}).`;
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "warning", title: "Sin Cupo Libre" });
        else alert(msg);
        return;
    }

    let input;
    if (window.UIFeedback) {
        input = await window.UIFeedback.prompt(
            `Cupo total para operar: $${curOp.toFixed(2)} ${cur} (En activos: $${usedBal.toFixed(2)} | Libre para devolver: $${maxReturnable.toFixed(2)} ${cur}).\n\nIndica el importe que deseas reintegrar a la Reserva Protegida del Broker:`,
            String(maxReturnable.toFixed(2)),
            {
                title: `Devolver Capital al Broker (${cur})`,
                icon: "🏛️",
                placeholder: `Monto hasta $${maxReturnable.toFixed(2)}`,
                inputType: "number"
            }
        );
    } else {
        input = prompt(`Devolver Capital al Broker (${cur}):\nLibre para devolver: $${maxReturnable.toFixed(2)}\n\nIndica el importe a devolver:`, String(maxReturnable.toFixed(2)));
    }
    if (!input) return;
    const amount = parseFloat(input);
    if (!Number.isFinite(amount) || amount <= 0) {
        const msg = "Por favor ingresa un monto numérico positivo.";
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "warning", title: "Monto Inválido" });
        else alert(msg);
        return;
    }
    if (amount > maxReturnable + 0.01) {
        const msg = `Solo puedes devolver hasta el cupo libre no invertido ($${maxReturnable.toFixed(2)} ${cur}).`;
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "error", title: "Monto Excesivo" });
        else alert(msg);
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/broker/operating-capital`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ action: "return", amount: amount, currency: cur })
        });
        if (res.ok) {
            const data = await res.json();
            const opVal = Number(data.operating_capital);
            window.currentOperatingCapital[cur] = (Number.isFinite(opVal) && opVal >= 0) ? Math.min(opVal, totalEquity) : Math.max(usedBal, curOp - amount);
            await updateCapitalDisplay();
            logToTerminal(`🏛️ [DEVOLUCIÓN A RESERVA] Se reintegraron $${amount.toFixed(2)} ${cur} a la Reserva Protegida del Broker. Cupo para operar restante: $${window.currentOperatingCapital[cur].toFixed(2)} ${cur}.`, 'info');
            if (window.UIFeedback) {
                window.UIFeedback.toast(`Se reintegraron $${amount.toFixed(2)} ${cur} a la Reserva Protegida del Broker.`, { type: "success", title: "Reintegro Exitoso" });
            }
        } else {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Error al devolver capital");
        }
    } catch (e) {
        logToTerminal(`⚠️ Error devolviendo fondos: ${e.message}`, 'error');
        if (window.UIFeedback) window.UIFeedback.toast(e.message, { type: "error", title: "Error" });
    }
};

window.limpiarCuentaModal = async function() {
    const confirmed = window.UIFeedback
        ? await window.UIFeedback.confirm("¿Deseas reiniciar la cuenta del Broker a $500 iniciales, conciliar inversores 50/50 y vaciar el historial de operaciones?", {
            title: "Reiniciar Cuenta del Broker",
            icon: "⚠️",
            isDestructive: true,
            confirmText: "Sí, reiniciar cuenta"
        })
        : confirm("¿Deseas reiniciar la cuenta del Broker a $500 iniciales y limpiar el historial de operaciones?");

    if (!confirmed) return;
    try {
        await fetch(`${API_BASE_URL}/api/broker/reset`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ initial_amount: 500.0 })
        });
    } catch (e) {
        console.warn("Error comunicando reset con el servidor:", e);
    }
    localStorage.removeItem('ai_portfolio_v5');
    localStorage.removeItem('ai_risk_state_v2');
    localStorage.removeItem('ai_cooldown_v1');
    localStorage.removeItem('ai_trade_history_v2');
    tradeHistoryLog = [];
    renderTradeHistory();
    portfolio.vault = { USDT: 500.0, USD: 500.0, ARS: 500000.0 };
    window.currentOperatingCapital = { USDT: 500.0, USD: 500.0, ARS: 500000.0 };
    portfolio.balances = { USDT: 0.0, USD: 0.0, ARS: 0.0 };
    portfolio.deposits = { USDT: 0.0, USD: 0.0, ARS: 0.0 };
    portfolio.position = null;
    portfolio.ASSET = 0;
    portfolio.entryPrice = 0;
    localStorage.setItem('ai_portfolio_v5', JSON.stringify(portfolio));
    await updateCapitalDisplay();
    logToTerminal('🧹 [CUENTA REINICIADA] Saldo del Broker restablecido a $500.00, inversores en 50/50 y memoria limpia.', 'action');
    if (window.UIFeedback) {
        window.UIFeedback.toast("Cuenta restablecida a $500.00 iniciales e inversores conciliados.", { type: "info", title: "Cuenta Reiniciada" });
    }
};

async function updateCapitalDisplay() {
    let currency = getCurrency(currentSymbol);

    // 1. Consultar saldos segregados del broker y capital de operar desde el backend
    try {
        const balRes = await fetch(`${API_BASE_URL}/api/broker/balances`, { headers: apiAuthHeaders() });
        if (balRes.ok) {
            const balData = await balRes.json();
            if (balData.vault) {
                portfolio.vault = {
                    USDT: Number(balData.vault.USDT) || 0,
                    USD: Number(balData.vault.USD) || 0,
                    ARS: Number(balData.vault.ARS) || 0,
                };
            }
            if (balData.operational) {
                window.currentOperationalUsed = {
                    USDT: Number(balData.operational.USDT) || 0,
                    USD: Number(balData.operational.USD) || 0,
                    ARS: Number(balData.operational.ARS) || 0,
                };
                portfolio.balances = { ...window.currentOperationalUsed };
            }
            if (balData.total_equity) {
                window.currentTotalEquity = {
                    USDT: Number(balData.total_equity.USDT) || 0,
                    USD: Number(balData.total_equity.USD) || 0,
                    ARS: Number(balData.total_equity.ARS) || 0,
                };
            }
            if (balData.operating_capital) {
                const parseCleanOp = (val, maxEq) => {
                    const num = Number(val);
                    if (!Number.isFinite(num) || num <= 0 || maxEq <= 0) return 0.0;
                    return Math.min(num, maxEq);
                };
                const eqUSDT = Number(balData.total_equity?.USDT ?? 0);
                const eqUSD = Number(balData.total_equity?.USD ?? 0);
                const eqARS = Number(balData.total_equity?.ARS ?? 0);

                window.currentOperatingCapital = {
                    USDT: parseCleanOp(balData.operating_capital.USDT, eqUSDT),
                    USD: parseCleanOp(balData.operating_capital.USD, eqUSD),
                    ARS: parseCleanOp(balData.operating_capital.ARS, eqARS),
                };
            }
            if (balData.operating_available) {
                window.currentOperatingAvailable = {
                    USDT: Number(balData.operating_available.USDT) || 0,
                    USD: Number(balData.operating_available.USD) || 0,
                    ARS: Number(balData.operating_available.ARS) || 0,
                };
            }
            if (balData.safe_profit_wallet) {
                window.currentSafeProfitWallet = {
                    USDT: Number(balData.safe_profit_wallet.USDT) || 0,
                    USD: Number(balData.safe_profit_wallet.USD) || 0,
                    ARS: Number(balData.safe_profit_wallet.ARS) || 0,
                };
            }
            if (balData.safe_profit_injected) {
                window.currentSafeProfitInjected = {
                    USDT: Number(balData.safe_profit_injected.USDT) || 0,
                    USD: Number(balData.safe_profit_injected.USD) || 0,
                    ARS: Number(balData.safe_profit_injected.ARS) || 0,
                };
            }
            if (balData.broker_idle) {
                window.currentBrokerIdle = {
                    USDT: Number(balData.broker_idle.USDT) || 0,
                    USD: Number(balData.broker_idle.USD) || 0,
                    ARS: Number(balData.broker_idle.ARS) || 0,
                };
            }
            if (balData.fees_paid && balData.fees_paid[currency] !== undefined) {
                portfolio.totalFeesPaid = Number(balData.fees_paid[currency]) || 0;
            }
        }
    } catch (_) {}

    const vaultCashAmt = Number(portfolio?.vault?.[currency] || 0.0);
    const inPositionsCost = Number(window.currentOperationalUsed?.[currency] || portfolio?.balances?.[currency] || 0.0);
    const totalEquityAmt = Math.max(0.0, Number(window.currentTotalEquity?.[currency] ?? (vaultCashAmt + inPositionsCost)));
    const rawCurrentOp = window.currentOperatingCapital?.[currency];
    const opAmt = totalEquityAmt <= 0.009 ? 0.0 : Math.max(0.0, Math.min(totalEquityAmt, (rawCurrentOp !== undefined && Number.isFinite(Number(rawCurrentOp))) ? Number(rawCurrentOp) : totalEquityAmt));
    const opAvailAmt = totalEquityAmt <= 0.009 ? 0.0 : Number(
        window.currentOperatingAvailable?.[currency] !== undefined
            ? Math.min(window.currentOperatingAvailable[currency], opAmt)
            : Math.max(0.0, opAmt - inPositionsCost)
    );
    const idleAmt = totalEquityAmt <= 0.009 ? 0.0 : Number(
        window.currentBrokerIdle?.[currency] !== undefined
            ? Math.min(window.currentBrokerIdle[currency], totalEquityAmt)
            : Math.max(0.0, totalEquityAmt - opAmt)
    );

    const fmtMoney = (v) => `$${(Number(v) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;

    // 2. Actualizar tarjetas institucionales en UI (Broker & Dinero para Operar)
    const brokerTotalBalElem = document.getElementById('brokerTotalBalanceDisplay');
    if (brokerTotalBalElem) {
        brokerTotalBalElem.innerText = fmtMoney(totalEquityAmt);
    }
    const brokerVaultCashElem = document.getElementById('brokerVaultCashDisplay');
    if (brokerVaultCashElem) {
        brokerVaultCashElem.innerText = fmtMoney(vaultCashAmt);
    }
    const brokerInPosElem = document.getElementById('brokerInPositionsDisplay');
    if (brokerInPosElem) {
        brokerInPosElem.innerText = fmtMoney(inPositionsCost);
    }

    const operatingCapElem = document.getElementById('operatingCapitalDisplay');
    if (operatingCapElem) {
        operatingCapElem.innerText = fmtMoney(opAmt);
    }
    const operatingUsedElem = document.getElementById('operatingUsedDisplay');
    if (operatingUsedElem) {
        operatingUsedElem.innerText = fmtMoney(inPositionsCost);
    }
    const operatingAvailElem = document.getElementById('operatingAvailableDisplay');
    if (operatingAvailElem) {
        operatingAvailElem.innerText = fmtMoney(opAvailAmt);
    }

    const brokerIdleElem = document.getElementById('brokerIdleDisplay');
    if (brokerIdleElem) {
        brokerIdleElem.innerText = `${fmtMoney(idleAmt)} (Intocable)`;
    }

    const safeWalletAmt = Number(window.currentSafeProfitWallet?.[currency] || 0.0);
    const safeInjectedAmt = Number(window.currentSafeProfitInjected?.[currency] || 0.0);
    const safeWalletElem = document.getElementById('safeProfitWalletDisplay');
    if (safeWalletElem) {
        safeWalletElem.innerText = fmtMoney(safeWalletAmt);
    }
    const safeInjectedElem = document.getElementById('safeProfitInjectedDisplay');
    if (safeInjectedElem) {
        safeInjectedElem.innerText = fmtMoney(safeInjectedAmt);
    }
    const safeOpAvailRefElem = document.getElementById('safeProfitOpAvailRef');
    if (safeOpAvailRefElem) {
        safeOpAvailRefElem.innerText = fmtMoney(opAvailAmt);
    }

    // Compatibilidad retroactiva con elementos legacy
    const legacyBal = document.getElementById('accountBalanceDisplay');
    if (legacyBal) {
        legacyBal.innerText = fmtMoney(opAmt);
    }

    // 3. Consultar datos del Libro de Inversores (informativo, sin mezclar con el Broker)
    try {
        const invRes = await fetch(`${API_BASE_URL}/api/investors?currency=${currency}`, { headers: apiAuthHeaders() });
        if (invRes.ok) {
            const invData = await invRes.json();
            const invTotal = Number(invData?.reconciliation?.investors_total ?? invData?.total_investors_balance ?? 0);
            const diff = Number(invData?.reconciliation?.difference ?? (totalEquityAmt - invTotal));
            const isMatched = Math.abs(diff) < 0.01;

            const invTotElem = document.getElementById('brokerInvestorsTotalDisplay');
            if (invTotElem) {
                invTotElem.innerText = fmtMoney(invTotal);
            }
            const invDiffElem = document.getElementById('brokerInvestorsDiffDisplay');
            if (invDiffElem) {
                if (isMatched) {
                    invDiffElem.className = "font-bold text-emerald-400";
                    invDiffElem.innerText = "Dif: $0.00 (Ajustado)";
                } else {
                    const sign = diff > 0 ? "+" : "-";
                    invDiffElem.className = "font-bold text-amber-400";
                    invDiffElem.innerText = `Dif: ${sign}$${Math.abs(diff).toFixed(2)} ${currency}`;
                }
            }

            const badgeElem = document.getElementById('brokerReconcileBadge');
            if (badgeElem) {
                if (isMatched) {
                    badgeElem.className = "text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-500/50 px-2.5 py-0.5 rounded-full font-mono font-bold flex items-center gap-1 shadow-sm";
                    badgeElem.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> AJUSTADO CON INVERSORES';
                } else {
                    const sign = diff > 0 ? "+" : "-";
                    badgeElem.className = "text-[10px] bg-amber-950 text-amber-300 border border-amber-500/50 px-2.5 py-0.5 rounded-full font-mono font-bold flex items-center gap-1 shadow-sm";
                    badgeElem.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span> DIF. ${sign}$${Math.abs(diff).toFixed(2)}`;
                }
            }
        }
    } catch (_) {}

    // 4. Actualizar el preview dinámico del slot de riesgo
    window.updateRiskSlotPreview();

    // 5. Actualizar indicador superior "Patrimonio Broker" (Efectivo en Bóveda + Valor en Activos)
    let posValue = 0;
    const allPositions = (window.backendOpenPositions && window.backendOpenPositions.length > 0)
        ? window.backendOpenPositions
        : (getOpenPosition() ? [getOpenPosition()] : []);

    for (const p of allPositions) {
        const pCurrency = p.currency || getCurrency(p.symbol);
        if (pCurrency === currency) {
            const isSame = (p.symbol === currentSymbol && currentPriceSymbol === currentSymbol && currentPrice > 0);
            const evalPx = isSame ? currentPrice : Number(p.current_price || p.currentPrice || window.positionAssetPrice || p.entry_price || p.entryPrice || 0);
            const q = Number(p.qty || 0);
            posValue += q * evalPx;
        }
    }

    const activePosVal = posValue > 0 ? posValue : inPositionsCost;
    const totalLiveBroker = vaultCashAmt + activePosVal;
    const currencySymbols = { 'USDT': 'USDT', 'USD': 'USD', 'ARS': 'ARS' };
    const curSym = currencySymbols[currency] || '$';
    const capDisp = document.getElementById('capitalDisplay');
    if (capDisp) {
        capDisp.innerText = `$${totalLiveBroker.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${curSym} (Bóveda: $${vaultCashAmt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} | Activos: $${activePosVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })})`;
    }

    const feesDisp = document.getElementById('totalFeesDisplay');
    if (feesDisp) {
        feesDisp.innerText = `$${(portfolio.totalFeesPaid || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    const pnlDisplay = document.getElementById('pnlDisplay');
    if (pnlDisplay) {
        const base = (portfolio.deposits && portfolio.deposits[currency] > 0) ? portfolio.deposits[currency] : 0;
        if (base === 0) {
            pnlDisplay.className = 'font-bold text-gray-400';
            pnlDisplay.innerText = '$0.00 (0.00%)';
        } else {
            const total = totalLiveBroker;
            const diff = total - base;
            const percent = (diff / base) * 100;
            const isProfit = diff > 0.005;
            const isLoss = diff < -0.005;
            const sign = isProfit ? '+' : (isLoss ? '-' : '');
            const color = isProfit ? 'text-green-400 font-bold' : (isLoss ? 'text-red-400 font-bold' : 'text-gray-400 font-bold');
            pnlDisplay.className = color;
            pnlDisplay.innerText = `${sign}${currency === 'ARS' ? '$' : ''}${Math.abs(diff).toFixed(2)} ${currency} (${sign}${Math.abs(percent).toFixed(2)}%)`;
        }
    }

    // Actualizar Tabla y Tarjetas de Posiciones Activas (Soporte Multi-Posición)
    const activeBody = document.getElementById('activePositionsBody');
    const cardsContainer = document.getElementById('activePositionsCardsGrid');
    const statusBadge = document.getElementById('posGracefulStatus');

    if (allPositions.length === 0) {
        isStopAfterCloseArmed = false;
        localStorage.removeItem('ai_stop_after_close');
        if (statusBadge) statusBadge.classList.add('hidden');
        if (activeBody) {
            activeBody.innerHTML = `<tr id="emptyPositionsRow"><td colspan="8" class="px-4 py-4 text-center text-gray-600 italic">No tienes posiciones activas (100% liquidez en ${currency}).</td></tr>`;
        }
        if (cardsContainer) {
            cardsContainer.innerHTML = `
                <div class="bg-gradient-to-r from-gray-900 via-slate-900 to-gray-900 border border-gray-700/80 rounded-xl p-4 text-center shadow-inner">
                    <div class="flex items-center justify-center gap-2 text-emerald-400 font-bold text-sm mb-1">
                        <span>🛡️</span> 0 de 4 Ranuras Ocupadas · 100% Capital en Custodia en Bóveda
                    </div>
                    <p class="text-xs text-gray-400 max-w-xl mx-auto">
                        El tigre táctico <strong>Balam</strong> se mantiene en reposo vigilante en liquidez, aguardando confluencia multitemporal y asimetría matemática $R:R \\ge 1:2$.
                    </p>
                </div>
            `;
        }
    } else {
        if (statusBadge) {
            if (isStopAfterCloseArmed) {
                statusBadge.classList.remove('hidden');
            } else {
                statusBadge.classList.add('hidden');
            }
        }

        let rowsHtml = '';
        const isSinglePos = allPositions.length === 1;
        let cardsHtml = `<div class="grid grid-cols-1 ${isSinglePos ? '' : 'md:grid-cols-2'} gap-4 w-full">`;

        for (let idx = 0; idx < allPositions.length; idx++) {
            const currentPos = allPositions[idx];
            const sym = currentPos.symbol;
            const isSameSymbol = (sym === currentSymbol && currentPriceSymbol === currentSymbol && currentPrice > 0);
            const entryPx = Number(currentPos.entry_price || currentPos.entryPrice || 0);
            const qtyVal = Number(currentPos.qty || 0);
            const activePrice = isSameSymbol ? currentPrice : Number(currentPos.current_price || currentPos.currentPrice || window.positionAssetPrice || entryPx);
            const costBasis = Number(currentPos.cost_basis || currentPos.costBasis || (entryPx * qtyVal)) || 0;
            
            const side = String(currentPos.side || 'LONG').toUpperCase();
            const isShort = side === 'SHORT';

            // 1. PnL Bruto de Mercado
            const grossPnl = isShort ? (entryPx - activePrice) * qtyVal : (activePrice - entryPx) * qtyVal;
            const grossPct = costBasis > 0 ? (grossPnl / costBasis) * 100 : (entryPx > 0 ? ((activePrice - entryPx) / entryPx) * 100 : 0);

            // 2. Fricción de Comisiones (Entrada ya registrada en ledger + Salida estimada)
            const feeRate = Number(currentPos.feeRate ?? (typeof getBrokerFeeRate === 'function' ? getBrokerFeeRate() : 0.10));
            const entryFee = Number(currentPos.total_fees !== undefined && currentPos.total_fees !== null ? currentPos.total_fees : (costBasis * (feeRate / 100)));
            const estExitFee = (qtyVal * activePrice) * (feeRate / 100);
            const totalFees = entryFee + estExitFee;

            // 3. PnL Neto Real (lo que realmente impacta la bóveda al liquidar)
            const netPnl = grossPnl - totalFees;
            const netPct = costBasis > 0 ? (netPnl / costBasis) * 100 : 0;
            
            const isProfit = netPnl > 0.005;
            const isLoss = netPnl < -0.005;
            const pnlColor = isProfit ? 'text-emerald-400 font-bold' : (isLoss ? 'text-rose-400 font-bold' : 'text-gray-400 font-bold');
            const pnlSign = isProfit ? '+' : (isLoss ? '-' : '');
            const formattedGain = `${pnlSign}$${Math.abs(netPnl).toFixed(2)}`;
            const formattedPct = `${pnlSign}${Math.abs(netPct).toFixed(2)}%`;

            const grossSign = grossPnl >= 0 ? '+' : '-';
            const formattedGrossGain = `${grossSign}$${Math.abs(grossPnl).toFixed(2)}`;
            const formattedGrossPct = `${grossSign}${Math.abs(grossPct).toFixed(2)}%`;

            const entryPxStr = entryPx < 10.0
                ? `$${entryPx.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 4})}`
                : `$${entryPx.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            const activePxStr = activePrice < 10.0
                ? `$${activePrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 4})}`
                : `$${activePrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            const costStr = `$${costBasis.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

            const meta = getAssetMeta(sym);
            const baseCoin = sym.split('/')[0];
            const coinName = meta ? `${meta.icon} ${meta.name}` : baseCoin;
            const strat = currentPos.strategy || 'trailing_trend_runner';
            const eng = currentPos.engine || 'antigravity_operador';
            const form = currentPos.formula || 'Quant Risk ATR';
            const stratBadge = `<span class="text-[9px] text-cyan-300 bg-cyan-950/70 px-1 py-0.5 rounded border border-cyan-800/60 ml-1 font-mono" title="Estrategia: ${escapeHtml(strat)} | Agente: ${escapeHtml(eng)} | Fórmula: ${escapeHtml(form)}">${escapeHtml(strat)}</span>`;
            const tMode = currentPos.trailing_mode || (currentPos.trailing_telemetry?.active_mode) || 'Auto';
            const tBadge = `<span class="text-[9px] text-amber-300 bg-amber-950/70 px-1 py-0.5 rounded border border-amber-800/60 ml-1 font-mono" title="Llave Trailing Stop: ${escapeHtml(tMode)}">🎚️ ${escapeHtml(tMode)}</span>`;
            
            const openedAtStr = currentPos.opened_at || currentPos.timestamp || '';
            let hoursOpen = Number(currentPos.time_decay_hours || currentPos.time_decay?.elapsed_hours || 0);
            if (!hoursOpen && openedAtStr) {
                const d = new Date(openedAtStr.replace(' ', 'T') + (openedAtStr.includes('Z') ? '' : 'Z'));
                if (!isNaN(d.getTime())) {
                    hoursOpen = Math.max(0, (Date.now() - d.getTime()) / 3600000);
                }
            }
            const decayStatus = currentPos.time_decay_status || currentPos.time_decay?.status || (hoursOpen >= 16 ? 'TIGHTENING_16H' : (hoursOpen >= 8 ? 'TIGHTENING_8H' : 'NORMAL'));
            const decaySugg = currentPos.time_decay_suggestion || currentPos.time_decay?.suggestion || '';
            const decayTitle = `⏳ ${hoursOpen.toFixed(1)}h de vida | Mecánica: ${decayStatus}${decaySugg ? ' | ' + decaySugg : ''}`;
            const decayColor = hoursOpen >= 16 
                ? 'text-rose-300 bg-rose-950/70 border-rose-800/60' 
                : (hoursOpen >= 8 ? 'text-purple-300 bg-purple-950/70 border-purple-800/60' : 'text-slate-300 bg-slate-900/70 border-slate-700/60');
            const timeBadge = `<span class="text-[9px] ${decayColor} px-1 py-0.5 rounded border ml-1 font-mono cursor-help" title="${escapeHtml(decayTitle)}">⏳ ${hoursOpen.toFixed(1)}h [B]</span>`;

            const viewBtn = !isSameSymbol
                ? `<button onclick="window.switchAssetTo('${escapeHtml(sym)}')" class="text-[10px] bg-indigo-900/70 hover:bg-indigo-700 text-indigo-200 border border-indigo-600/50 px-1.5 py-0.5 rounded ml-1.5 font-mono cursor-pointer transition shadow" title="Ver gráfico de ${escapeHtml(sym)}">👁️ Ver</button>`
                : '';
            const symbolIndicator = isSameSymbol 
                ? `<span class="font-bold text-white">${escapeHtml(coinName)}</span> <span class="text-[10px] text-gray-400">(${escapeHtml(sym)})</span>${stratBadge}${tBadge}${timeBadge}`
                : `<span class="font-bold text-white">${escapeHtml(coinName)}</span> <span class="text-[10px] text-yellow-400 bg-yellow-950/60 px-1.5 py-0.5 rounded border border-yellow-700/50">Segundo plano: ${escapeHtml(sym)}</span>${stratBadge}${tBadge}${timeBadge}${viewBtn}`;

            const scaleInEnabled = window.enableScaleInFeature !== false;
            const rotationEnabled = window.enableRotationFeature !== false;
            const canScaleInSafe = netPct >= 0.20;
            const canRotateSafe = netPct > 0.0;

            const scaleInBtn = scaleInEnabled
                ? `<button onclick="window.potenciarPosicionModal('${escapeHtml(sym)}', ${entryPx}, ${activePrice}, ${costBasis}, ${netPct})" class="text-[11px] ${canScaleInSafe ? 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-400' : 'bg-gray-800 hover:bg-gray-700 text-gray-400 border-gray-600'} px-2 py-1 rounded font-bold shadow transition border cursor-pointer mr-1" title="${canScaleInSafe ? 'Inyectar más capital a esta operación ganadora neta (con Candado de Ganancia Segura)' : 'Candado de Ganancia Segura: requiere al menos +0.20% de ganancia neta libre de comisiones'}">🚀 +Capital</button>`
                : '';

            const rotateBtn = (rotationEnabled && allPositions.length > 1)
                ? `<button onclick="window.rotarPosicionModal('${escapeHtml(sym)}', ${activePrice}, ${costBasis}, ${netPct})" class="text-[11px] ${canRotateSafe ? 'bg-cyan-700 hover:bg-cyan-600 text-white border-cyan-500' : 'bg-gray-800 hover:bg-gray-700 text-gray-500 border-gray-700'} px-2 py-1 rounded font-bold shadow transition border cursor-pointer mr-1" title="${canRotateSafe ? `Cerrar esta operación lenta en positivo neto (+${netPct.toFixed(2)}%) y pasar su capital ($${costBasis.toFixed(2)}) a una operación más vigorosa` : 'Protección activa: Nunca se cierran posiciones en negativo neto para rotar (solo posiciones que ya hayan superado las comisiones)'}">🔄 Rotar</button>`
                : '';

            const netTooltip = `Neto real tras comisiones (~$${totalFees.toFixed(2)}): ${formattedGain} (${formattedPct}) | Bruto de mercado: ${formattedGrossGain} (${formattedGrossPct})`;

            rowsHtml += `
                <tr class="border-b border-gray-700/50 bg-blue-900/10 hover:bg-blue-900/20 transition">
                    <td class="px-2.5 py-2 font-bold text-white">${symbolIndicator}</td>
                    <td class="px-2.5 py-2 font-mono text-gray-200">${qtyVal.toFixed(6)}</td>
                    <td class="px-2.5 py-2 font-mono text-gray-300">${entryPxStr}</td>
                    <td class="px-2.5 py-2 font-mono text-white">${activePxStr}</td>
                    <td class="px-2.5 py-2 font-mono text-cyan-300 font-semibold">${costStr}</td>
                    <td class="px-2.5 py-2 font-mono ${pnlColor}" title="${escapeHtml(netTooltip)}">
                        ${formattedGain}
                        <div class="text-[9px] text-gray-400 font-normal">Bruto: ${formattedGrossGain}</div>
                    </td>
                    <td class="px-2.5 py-2 font-mono ${pnlColor}" title="${escapeHtml(netTooltip)}">
                        ${formattedPct}
                        <div class="text-[9px] text-gray-400 font-normal">Bruto: ${formattedGrossPct}</div>
                    </td>
                    <td class="px-2.5 py-2 text-right whitespace-nowrap">
                        ${scaleInBtn}${rotateBtn}<button onclick="window.forceClosePosition(event, '${escapeHtml(sym)}')" class="text-xs bg-red-600 hover:bg-red-700 text-white px-2.5 py-1 rounded font-bold shadow-lg transition duration-200 ease-in-out transform hover:scale-105 border border-red-500 cursor-pointer" title="Cerrar posición en ${escapeHtml(sym)} inmediatamente y reintegrar a la Bóveda">✖ CERRAR</button>
                    </td>
                </tr>
            `;

            // Stop Loss dinámico según telemetría del servidor y estado del Breakeven/Trailing
            const symTelem = (window.backendTrailingTelemetry && window.backendTrailingTelemetry[sym]) || currentPos.trailing_telemetry || null;
            const isBeArmed = currentPos.be_armed === 1 || (symTelem && symTelem.be_armed === 1);
            const isTrailActive = currentPos.trail_active === 1 || (symTelem && symTelem.active_mode && symTelem.active_mode !== 'Auto');
            const initSlPct = Number(currentPos.initial_sl_pct || currentPos.sl || 0.6);
            let activeStopPx = (symTelem && Number(symTelem.active_stop_price) > 0)
                ? Number(symTelem.active_stop_price)
                : (isShort ? entryPx * (1 + initSlPct / 100) : entryPx * (1 - initSlPct / 100));

            const slPxStr = activeStopPx < 10.0 ? `$${activeStopPx.toFixed(4)}` : `$${activeStopPx.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

            // Riesgo monetario real en SL (diferencial de precio por cantidad, NO el capital total de la posición)
            const lossPerUnit = isShort ? Math.max(0, activeStopPx - entryPx) : Math.max(0, entryPx - activeStopPx);
            const actualRiskUsd = isBeArmed ? 0.0 : (lossPerUnit * qtyVal);
            const riskOfEquityPct = totalEquityAmt > 0 ? (actualRiskUsd / totalEquityAmt) * 100 : 0;

            // Breakeven target a +0.40%
            const beTargetPct = 0.40;
            const isBeActive = isBeArmed || netPct >= beTargetPct;
            const beProgressPct = isBeArmed ? 100 : Math.max(0, Math.min(100, (netPct / beTargetPct) * 100));

            cardsHtml += `
                <div class="bg-gradient-to-br from-gray-900 via-gray-850 to-gray-900 border ${isProfit ? 'border-emerald-500/70' : (isLoss ? 'border-rose-500/60' : 'border-gray-700')} rounded-xl p-4 shadow-xl space-y-3 w-full">
                    <div class="flex justify-between items-center border-b border-gray-800 pb-2.5">
                        <div class="flex items-center gap-2.5">
                            <span class="text-2xl">${meta?.icon || '🪙'}</span>
                            <div>
                                <h3 class="font-bold text-white text-base flex items-center gap-2">
                                    ${escapeHtml(coinName)}
                                    <span class="text-xs text-gray-400 font-mono">(${escapeHtml(sym)})</span>
                                </h3>
                                <div class="flex items-center gap-1.5 mt-0.5 flex-wrap">
                                    <span class="px-1.5 py-0.2 rounded text-[9.5px] font-bold font-mono ${isShort ? 'bg-rose-950 text-rose-300 border border-rose-700' : 'bg-emerald-950 text-emerald-300 border border-emerald-700'}">${side}</span>
                                    <span class="text-[9.5px] text-cyan-300 bg-cyan-950/60 px-1.5 py-0.2 rounded border border-cyan-800 font-mono">Slot ${idx + 1}/4</span>
                                    ${timeBadge}
                                </div>
                            </div>
                        </div>
                        <div class="text-right">
                            <span class="text-[9px] uppercase font-bold text-gray-400 block tracking-wider">PnL Neto Real</span>
                            <span class="text-lg font-black font-mono ${pnlColor} drop-shadow-sm">${formattedGain}</span>
                            <span class="text-xs font-bold font-mono ${pnlColor} block">${formattedPct}</span>
                        </div>
                    </div>

                    <!-- Métricas de Cotización y Asimetría en Ancho Completo -->
                    <div class="grid grid-cols-2 ${isSinglePos ? 'sm:grid-cols-4' : ''} gap-3 text-xs font-mono bg-black/50 p-3 rounded-lg border border-gray-800">
                        <div>
                            <span class="text-gray-400 text-[10px] block uppercase">Precio Entrada:</span>
                            <span class="font-bold text-gray-200 text-sm">${entryPxStr}</span>
                        </div>
                        <div>
                            <span class="text-gray-400 text-[10px] block uppercase">Precio Vivo:</span>
                            <span class="font-bold text-white text-sm animate-pulse">${activePxStr}</span>
                        </div>
                        <div class="${isSinglePos ? '' : 'border-t sm:border-t-0 border-gray-800/80 pt-1 sm:pt-0'}">
                            <span class="text-gray-400 text-[10px] block uppercase">${isBeArmed ? '🛡️ Stop BE (Blindado):' : (isTrailActive ? '🎚️ Trailing Stop:' : `Stop Loss (-${initSlPct.toFixed(2)}%):`)}</span>
                            <span class="font-bold ${isBeArmed ? 'text-amber-400' : 'text-rose-400'} text-sm">${slPxStr}</span>
                        </div>
                        <div class="${isSinglePos ? 'text-right' : 'border-t sm:border-t-0 border-gray-800/80 pt-1 sm:pt-0 text-right'}">
                            <span class="text-gray-400 text-[10px] block uppercase" title="Pérdida monetaria máxima si el precio toca el Stop Loss actual">Riesgo Real en SL:</span>
                            <span class="font-bold ${isBeArmed ? 'text-emerald-400' : 'text-rose-300'} text-sm">${isBeArmed ? '$0.00 (Blindado)' : `-$${actualRiskUsd.toFixed(2)} (${riskOfEquityPct.toFixed(2)}%)`}</span>
                            <div class="text-[9px] text-gray-400 font-mono">Posición: ${costStr}</div>
                        </div>
                    </div>

                    <!-- Termómetro de Breakeven (+0.40%) -->
                    <div class="space-y-1">
                        <div class="flex justify-between text-[10px] font-mono">
                            <span class="text-gray-400">Gatillo de Breakeven (+0.40%):</span>
                            <span class="${isBeActive ? 'text-emerald-400 font-bold' : 'text-cyan-400'}">
                                ${isBeActive ? '🛡️ PROTEGIDO (Stop a Entrada / Riesgo $0)' : `Faltan +${(beTargetPct - netPct).toFixed(2)}%`}
                            </span>
                        </div>
                        <div class="w-full bg-gray-950 rounded-full h-1.5 overflow-hidden flex border border-gray-800">
                            <div class="${isBeActive ? 'bg-emerald-500' : 'bg-cyan-500'} h-full transition-all duration-300" style="width: ${beProgressPct}%;"></div>
                        </div>
                    </div>

                    <!-- Barra de Acciones Tácticas -->
                    <div class="flex items-center justify-between pt-1 gap-2">
                        <button onclick="window.switchAssetTo('${escapeHtml(sym)}')" class="text-[11px] bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 px-2.5 py-1.5 rounded-lg font-mono transition cursor-pointer" title="Ver gráfico">
                            👁️ Gráfico
                        </button>
                        <div class="flex items-center gap-1.5">
                            ${scaleInBtn}
                            ${rotateBtn}
                            <button onclick="window.forceClosePosition(event, '${escapeHtml(sym)}')" class="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold text-xs shadow transition flex items-center gap-1.5 cursor-pointer border border-red-400" title="Cerrar de inmediato y transferir los fondos a la Bóveda">
                                <span>🔴</span> Cerrar (Sweep-Back)
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }

        cardsHtml += '</div>';
        if (activeBody) activeBody.innerHTML = rowsHtml;
        if (cardsContainer) cardsContainer.innerHTML = cardsHtml;
        if (typeof window.updateChartTradeMarkers === 'function') {
            window.updateChartTradeMarkers();
        }
    }

    // Actualizar Termómetro de Bóveda & 4 Ranuras
    if (typeof window.updateVaultSlotsThermometer === 'function') {
        window.updateVaultSlotsThermometer(allPositions, currency);
    }
}

// --- TERMÓMETRO VISUAL DE BÓVEDA & MULTI-SLOT DINÁMICO ---
window.updateVaultSlotsThermometer = function(allPositions = null, currency = null) {
    const thermoOccupancy = document.getElementById('vaultThermometerOccupancy');
    const thermoSubtitle = document.getElementById('vaultThermometerSubtitle');
    const gridContainer = document.getElementById('vaultSlotsGrid');
    const thermoVaultPct = document.getElementById('thermoVaultPctText');
    const thermoInPlayPct = document.getElementById('thermoInPlayPctText');
    const thermoVaultBar = document.getElementById('thermoVaultBar');
    const thermoInPlayBar = document.getElementById('thermoInPlayBar');
    const thermoInPlayDollars = document.getElementById('thermoInPlayDollars');
    const thermoVaultDollars = document.getElementById('thermoVaultDollars');

    // 1. Divisa consultada
    const cur = currency || (typeof getCurrency === 'function' ? getCurrency(currentSymbol) : 'USDT');

    // 2. Extraer posiciones del broker activas y filtrar estrictamente por la divisa consultada
    const rawPositions = Array.isArray(allPositions)
        ? allPositions
        : ((window.backendOpenPositions && window.backendOpenPositions.length > 0)
            ? window.backendOpenPositions
            : (typeof getOpenPosition === 'function' && getOpenPosition() ? [getOpenPosition()] : []));

    const positions = rawPositions.filter(p => {
        if (!p) return false;
        const pCur = p.currency || (typeof getCurrency === 'function' ? getCurrency(p.symbol) : 'USDT');
        return pCur === cur;
    });
    const occupiedCount = positions.length;

    // 3. Costo devengado en posiciones activas en esta divisa
    let inPositionsCost = 0;
    positions.forEach(p => {
        const entryPx = Number(p.entry_price || p.entryPrice || 0);
        const qty = Number(p.qty || 0);
        const cost = Number(p.cost_basis || p.costBasis || (entryPx * qty)) || 0;
        inPositionsCost += cost;
    });

    // 4. Balances reales del Ledger Omnibus y Portafolio (sin fallbacks fantasma de 500)
    const vaultCash = Number(portfolio?.vault?.[cur] || 0.0);
    const totalEquity = Math.max(0.0, Number(window.currentTotalEquity?.[cur] ?? (vaultCash + inPositionsCost)));
    const rawOp = window.currentOperatingCapital?.[cur];
    const opCap = totalEquity <= 0.009 ? 0.0 : Math.max(0.0, Math.min(totalEquity, (rawOp !== undefined && Number.isFinite(Number(rawOp))) ? Number(rawOp) : totalEquity));

    // 5. Proporción real de Bóveda vs Capital en Juego (base = totalEquity)
    const inPlayPct = totalEquity > 0 ? Math.min(100, (inPositionsCost / totalEquity) * 100) : 0;
    const vaultPct = totalEquity > 0 ? Math.max(0, 100 - inPlayPct) : 100;

    // 6. Configuración de Ranuras desde riskSelect (% sobre Dinero para Operar)
    const riskSelect = document.getElementById('riskSelect');
    const riskFrac = parseFloat(riskSelect?.value) || 0.25;
    const configuredSlots = Math.max(1, Math.round(1 / riskFrac));
    const totalSlots = Math.max(configuredSlots, occupiedCount);
    const slotPct = Math.round(riskFrac * 100);
    const slotCapacity = opCap > 0 ? (opCap * riskFrac) : 0.0;

    // 7. Actualizar Textos y Barra de Progreso
    if (thermoOccupancy) {
        thermoOccupancy.innerText = `${occupiedCount}/${configuredSlots} Ranuras`;
        if (occupiedCount === 0) {
            thermoOccupancy.className = 'text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-500/60 shadow-sm';
        } else if (occupiedCount < configuredSlots) {
            thermoOccupancy.className = 'text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-500/60 shadow-sm';
        } else {
            thermoOccupancy.className = 'text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-500/60 shadow-sm';
        }
    }

    if (thermoSubtitle) {
        thermoSubtitle.innerText = `${configuredSlots} Slot${configuredSlots > 1 ? 's' : ''} de ${slotPct}% c/u sobre Dinero para Operar vs Reserva Protegida`;
    }

    if (thermoVaultPct) thermoVaultPct.innerText = `${vaultPct.toFixed(1)}%`;
    if (thermoInPlayPct) thermoInPlayPct.innerText = `${inPlayPct.toFixed(1)}%`;
    if (thermoVaultBar) thermoVaultBar.style.width = `${vaultPct.toFixed(1)}%`;
    if (thermoInPlayBar) thermoInPlayBar.style.width = `${inPlayPct.toFixed(1)}%`;
    if (thermoInPlayDollars) thermoInPlayDollars.innerText = `$${inPositionsCost.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} ${cur}`;
    if (thermoVaultDollars) thermoVaultDollars.innerText = `$${vaultCash.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} ${cur}`;

    // 8. Re-renderizado Dinámico de las Ranuras Visuales
    if (gridContainer) {
        let gridCols = 'grid-cols-1';
        if (totalSlots === 2) gridCols = 'grid-cols-2';
        else if (totalSlots >= 3) gridCols = 'grid-cols-2 sm:grid-cols-4';
        gridContainer.className = `grid ${gridCols} gap-2 text-center font-mono text-[11px]`;

        let slotsHtml = '';
        for (let i = 1; i <= totalSlots; i++) {
            const pos = positions[i - 1];
            if (pos) {
                const sym = pos.symbol || '';
                const coin = sym.split('/')[0] || sym;
                const cost = Number(pos.cost_basis || pos.costBasis || (Number(pos.entry_price || pos.entryPrice || 0) * Number(pos.qty || 0))) || 0;
                const maxRisk = (cost * 0.02).toFixed(2);
                slotsHtml += `
                    <div id="slotPill${i}" class="p-2 rounded-lg bg-cyan-950/70 border-2 border-cyan-500/80 text-cyan-200 transition shadow-md">
                        <span class="block text-[9px] uppercase font-bold text-cyan-400">Ranura ${i} (${slotPct}%)</span>
                        <span class="slot-status font-bold text-white block my-0.5">⚡ ${escapeHtml(coin)}</span>
                        <span class="slot-detail block text-[9.5px] text-cyan-300">$${cost.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} (SL -$${maxRisk})</span>
                    </div>
                `;
            } else {
                slotsHtml += `
                    <div id="slotPill${i}" class="p-2 rounded-lg bg-gray-950 border border-gray-800 text-gray-400 transition">
                        <span class="block text-[9px] uppercase font-bold text-gray-500">Ranura ${i} (${slotPct}%)</span>
                        <span class="slot-status font-bold text-emerald-400 block my-0.5">🟢 LIBRE</span>
                        <span class="slot-detail block text-[9.5px] text-gray-400">$${slotCapacity.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                    </div>
                `;
            }
        }
        gridContainer.innerHTML = slotsHtml;
    }
};

// --- RADAR DE MICROESTRUCTURA DE MERCADO EN VIVO (5 ACTIVOS CLAVE) ---
window.fetchMicrostructureRadar = async function(isManual = false) {
    const body = document.getElementById('microstructureRadarBody');
    if (!body) return;
    try {
        const url = isManual ? `${API_BASE_URL}/api/market/radar-overview?force=true` : `${API_BASE_URL}/api/market/radar-overview`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        if (!data || !Array.isArray(data.items)) return;

        let rowsHtml = '';
        data.items.forEach(item => {
            const sym = item.symbol;
            const coin = sym.split('/')[0];
            const px = Number(item.price || 0);
            const pxStr = px < 10.0 ? `$${px.toFixed(4)}` : `$${px.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            const chg = Number(item.change_24h || 0);
            const chgColor = chg >= 0 ? 'text-emerald-400' : 'text-rose-400';
            const chgSign = chg >= 0 ? '+' : '';
            const chgStr = `${chgSign}${chg.toFixed(2)}%`;

            const regimeColor = item.regime === 'ALCISTA' 
                ? 'text-emerald-300 bg-emerald-950/80 border-emerald-600/60' 
                : (item.regime === 'BAJISTA' ? 'text-rose-300 bg-rose-950/80 border-rose-600/60' : 'text-yellow-300 bg-yellow-950/80 border-yellow-600/60');
            const regimeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold border ${regimeColor}">${item.regime}</span>`;

            const rsi = Number(item.rsi || 50);
            const rsiColor = rsi >= 70 ? 'text-amber-400 font-bold' : (rsi <= 30 ? 'text-yellow-400 font-bold' : 'text-gray-300');

            const rvol = Number(item.rvol || 1.0);
            const rvolColor = rvol >= 1.0 ? 'text-emerald-400 font-bold' : 'text-gray-400';

            const isCurrent = (sym === currentSymbol);
            const activeRowClass = isCurrent ? 'bg-cyan-950/40 font-bold border-l-2 border-cyan-400' : 'hover:bg-gray-700/30 transition';

            const viewBtn = isCurrent
                ? `<span class="text-[10px] text-emerald-400 font-bold px-1.5 py-0.5 bg-emerald-950/60 rounded border border-emerald-700/60">ACTIVO</span>`
                : `<button onclick="window.switchAssetTo('${escapeHtml(sym)}')" class="text-[10px] bg-cyan-900/70 hover:bg-cyan-700 text-cyan-200 border border-cyan-600/50 px-2 py-0.5 rounded transition cursor-pointer" title="Ver gráfico de ${escapeHtml(sym)}">👁️ Ver</button>`;

            rowsHtml += `
                <tr class="${activeRowClass} border-b border-gray-800">
                    <td class="px-2.5 py-2 text-white font-bold cursor-pointer" onclick="window.switchAssetTo('${escapeHtml(sym)}')">
                        <span>⚡ ${escapeHtml(coin)}</span>
                        <span class="text-[9.5px] text-gray-500 block font-normal font-mono">${escapeHtml(sym)}</span>
                    </td>
                    <td class="px-2.5 py-2 font-mono text-white">${pxStr}</td>
                    <td class="px-2.5 py-2 font-mono ${chgColor}">${chgStr}</td>
                    <td class="px-2.5 py-2">${regimeBadge}</td>
                    <td class="px-2.5 py-2 text-center font-mono ${rsiColor}">${rsi.toFixed(1)}</td>
                    <td class="px-2.5 py-2 text-center font-mono ${rvolColor}">${rvol.toFixed(2)}</td>
                    <td class="px-2.5 py-2 text-[11px] text-gray-300">${escapeHtml(item.reason || '')}</td>
                    <td class="px-2.5 py-2 text-right">${viewBtn}</td>
                </tr>
            `;
        });
        body.innerHTML = rowsHtml;

        if (isManual) {
            logToTerminal('📡 Radar de Activos actualizado desde Binance Spot.', 'info');
        }
    } catch (_) {}
};

// Polling periódico del radar de microestructura (cada 8 segundos)
setInterval(() => {
    if (typeof window.fetchMicrostructureRadar === 'function') {
        window.fetchMicrostructureRadar();
    }
}, 8000);

// Ticks fluidos de reloj en vivo (cada 1 segundo sin tocar F5)
setInterval(() => {
    const clock = document.getElementById('liveClockDisplay');
    if (clock) {
        clock.innerText = new Date().toLocaleTimeString('es-AR') + ' ART';
    }
}, 1000);

// --- TILDES Y MODALES DE PIRAMIDACIÓN (POTENCIAR GANADORA) Y ROTACIÓN TÁCTICA ---
window.enableScaleInFeature = localStorage.getItem('ai_enable_scale_in') !== 'false';
window.enableRotationFeature = localStorage.getItem('ai_enable_rotation') !== 'false';

document.addEventListener('DOMContentLoaded', () => {
    const chkScale = document.getElementById('chkEnableScaleIn');
    if (chkScale) chkScale.checked = window.enableScaleInFeature;
    const chkRot = document.getElementById('chkEnableRotation');
    if (chkRot) chkRot.checked = window.enableRotationFeature;
});

window.toggleScaleInFeature = function(enabled) {
    window.enableScaleInFeature = Boolean(enabled);
    localStorage.setItem('ai_enable_scale_in', String(window.enableScaleInFeature));
    updateCapitalDisplay();
    logToTerminal(
        window.enableScaleInFeature
            ? '🚀 [GESTIÓN ACTIVA] Función "Potenciar Ganadora (+Capital)" ACTIVADA.'
            : '⏸️ [GESTIÓN ACTIVA] Función "Potenciar Ganadora (+Capital)" DESACTIVADA.',
        'info'
    );
};

window.toggleRotationFeature = function(enabled) {
    window.enableRotationFeature = Boolean(enabled);
    localStorage.setItem('ai_enable_rotation', String(window.enableRotationFeature));
    updateCapitalDisplay();
    logToTerminal(
        window.enableRotationFeature
            ? '🔄 [GESTIÓN ACTIVA] Función "Rotar Lentas a Vigorosa" ACTIVADA.'
            : '⏸️ [GESTIÓN ACTIVA] Función "Rotar Lentas a Vigorosa" DESACTIVADA.',
        'info'
    );
};

window.cargarBilleteraGananciaModal = async function() {
    const cur = getCurrency(currentSymbol);
    const opAvail = Number(window.currentOperatingAvailable?.[cur] || 0);
    const swAvail = Number(window.currentSafeProfitWallet?.[cur] || 0);

    if (opAvail <= 0.01) {
        const msg = `No tienes saldo libre en Dinero para Operar ($${opAvail.toFixed(2)} ${cur}). Libera capital o asigna más fondos a Dinero para Operar primero.`;
        window.UIFeedback ? window.UIFeedback.toast(msg, { type: 'warning', title: 'Sin saldo libre en Operar' }) : alert(msg);
        return;
    }

    const defaultAmt = Math.min(50, opAvail).toFixed(2);
    const promptText =
        `🚀 Cargar Billetera de Uso por Ganancia Segura (${cur}):\n` +
        `• Disponible libre en Dinero para Operar: $${opAvail.toFixed(2)} ${cur}\n` +
        `• Saldo actual en Billetera de Ganancia Segura: $${swAvail.toFixed(2)} ${cur}\n\n` +
        `El monto que ingreses se descontará de "Dinero para Operar" y quedará guardado exclusivamente en esta Billetera para potenciar operaciones ganadoras.\n` +
        `Ingresa el monto en ${cur} a transferir:`;

    let input = window.UIFeedback
        ? await window.UIFeedback.prompt(promptText, String(defaultAmt), {
              title: '➕ Ingresar a Billetera de Ganancia Segura',
              icon: '🚀',
              placeholder: `Monto en ${cur}`,
              inputType: 'number'
          })
        : prompt(promptText, String(defaultAmt));

    if (!input) return;
    const amount = parseFloat(input);
    if (!Number.isFinite(amount) || amount <= 0) return;

    try {
        const res = await fetch(`${API_BASE_URL}/api/broker/safe-profit-wallet`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ currency: cur, amount: amount, direction: 'FROM_OPERATING' })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al cargar la Billetera de Ganancia Segura');

        logToTerminal(
            `🚀 [BILLETERA GANANCIA SEGURA] Se transfirieron +$${amount.toFixed(2)} ${cur} desde Dinero para Operar. ` +
            `Disponible en Billetera: $${Number(data.safe_profit_wallet || 0).toFixed(2)} ${cur} | Nuevo Cupo Operar: $${Number(data.operating_capital || 0).toFixed(2)} ${cur}.`,
            'action'
        );
        window.UIFeedback?.toast(
            `Se guardaron $${amount.toFixed(2)} ${cur} en la Billetera de Uso por Ganancia Segura.`,
            { type: 'success', title: 'Billetera Cargada' }
        );
        await updateCapitalDisplay();
    } catch (e) {
        logToTerminal(`⚠️ Error en Billetera de Ganancia Segura: ${e.message}`, 'error');
        window.UIFeedback ? window.UIFeedback.toast(e.message, { type: 'error' }) : alert(e.message);
    }
};

window.devolverBilleteraGananciaModal = async function() {
    const cur = getCurrency(currentSymbol);
    const swAvail = Number(window.currentSafeProfitWallet?.[cur] || 0);

    if (swAvail <= 0.01) {
        const msg = `La Billetera de Uso por Ganancia Segura está en $0.00 ${cur}.`;
        window.UIFeedback ? window.UIFeedback.toast(msg, { type: 'info', title: 'Billetera vacía' }) : alert(msg);
        return;
    }

    const promptText =
        `➖ Devolver fondos desde la Billetera de Ganancia Segura hacia Dinero para Operar (${cur}):\n` +
        `• Disponible en Billetera de Ganancia Segura: $${swAvail.toFixed(2)} ${cur}\n\n` +
        `Ingresa el monto en ${cur} a devolver a Dinero para Operar:`;

    let input = window.UIFeedback
        ? await window.UIFeedback.prompt(promptText, String(swAvail.toFixed(2)), {
              title: '➖ Devolver a Dinero para Operar',
              icon: '↩️',
              placeholder: `Monto en ${cur}`,
              inputType: 'number'
          })
        : prompt(promptText, String(swAvail.toFixed(2)));

    if (!input) return;
    const amount = parseFloat(input);
    if (!Number.isFinite(amount) || amount <= 0) return;

    try {
        const res = await fetch(`${API_BASE_URL}/api/broker/safe-profit-wallet`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ currency: cur, amount: amount, direction: 'TO_OPERATING' })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al devolver fondos a Dinero para Operar');

        logToTerminal(
            `↩️ [BILLETERA GANANCIA SEGURA] Se devolvieron $${amount.toFixed(2)} ${cur} hacia Dinero para Operar. ` +
            `Disponible en Billetera: $${Number(data.safe_profit_wallet || 0).toFixed(2)} ${cur} | Nuevo Cupo Operar: $${Number(data.operating_capital || 0).toFixed(2)} ${cur}.`,
            'action'
        );
        window.UIFeedback?.toast(
            `Se devolvieron $${amount.toFixed(2)} ${cur} a Dinero para Operar.`,
            { type: 'success', title: 'Transferencia Completada' }
        );
        await updateCapitalDisplay();
    } catch (e) {
        logToTerminal(`⚠️ Error devolviendo de Billetera de Ganancia Segura: ${e.message}`, 'error');
        window.UIFeedback ? window.UIFeedback.toast(e.message, { type: 'error' }) : alert(e.message);
    }
};

window.potenciarPosicionModal = async function(symbol, entryPrice, activePrice, costBasis, pnlPct) {
    const cur = getCurrency(symbol);
    const swAvail = Number(window.currentSafeProfitWallet?.[cur] || 0);
    const opAvail = Number(window.currentOperatingAvailable?.[cur] || 0);

    if (pnlPct < 0.20) {
        const warnMsg = `🔒 Candado de Ganancia Segura: ${symbol} tiene actualmente ${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%.\n\nPor seguridad matemática, solo se debe inyectar más dinero cuando la posición ya está en ganancia (≥ +0.20%) para no empeorar tu precio promedio de entrada en una operación que aún no despegó.`;
        if (window.UIFeedback) {
            window.UIFeedback.toast(warnMsg, { type: 'warning', title: 'Candado de Ganancia Segura' });
        } else {
            alert(warnMsg);
        }
        return;
    }

    if (swAvail <= 0.05 && opAvail <= 0.05) {
        const emptyMsg = `Tu Billetera de Uso por Ganancia Segura está en $0.00 ${cur} y no hay saldo libre en Dinero para Operar.\n\nPrimero ingresa fondos en la tarjeta "🚀 Billetera de Uso por Ganancia Segura" o usa "🔄 Rotar" en una posición lenta.`;
        window.UIFeedback ? window.UIFeedback.toast(emptyMsg, { type: 'warning', title: 'Sin fondos en Billetera de Ganancia Segura' }) : alert(emptyMsg);
        return;
    }

    const defaultAdd = (swAvail > 0.05 ? Math.min(50, swAvail) : Math.min(50, opAvail)).toFixed(2);
    const promptText =
        `Potenciar operación ganadora en ${symbol} (PnL actual: +${pnlPct.toFixed(2)}%):\n` +
        `• Inversión actual: $${costBasis.toFixed(2)} ${cur} @ $${entryPrice.toFixed(2)}\n` +
        `• Precio actual: $${activePrice.toFixed(2)}\n` +
        `• Disponible en 🚀 Billetera de Ganancia Segura: $${swAvail.toFixed(2)} ${cur}\n` +
        `• Disponible en ⚡ Cupo Libre de Operar: $${opAvail.toFixed(2)} ${cur}\n\n` +
        `🔒 Se usará primero tu Billetera de Uso por Ganancia Segura y se blindará el Stop Loss en ganancia neta.\n` +
        `Ingresa el monto en ${cur} a inyectar:`;

    let input;
    if (window.UIFeedback) {
        input = await window.UIFeedback.prompt(promptText, String(defaultAdd), {
            title: `🚀 Potenciar ${symbol} (+Capital Seguro)`,
            icon: '🚀',
            placeholder: `Monto en ${cur}`,
            inputType: 'number'
        });
    } else {
        input = prompt(promptText, String(defaultAdd));
    }
    if (!input) return;
    const amount = parseFloat(input);
    if (!Number.isFinite(amount) || amount <= 0) {
        window.UIFeedback?.toast('Ingresa un monto numérico mayor a cero.', { type: 'warning' });
        return;
    }

    const sourceMode = swAvail >= (amount - 0.05) ? 'SAFE_PROFIT_WALLET' : 'OPERATING_POOL';
    const sourceLabel = sourceMode === 'SAFE_PROFIT_WALLET' ? 'Billetera de Uso por Ganancia Segura' : 'Cupo Libre de Operar';

    try {
        const res = await fetch(`${API_BASE_URL}/api/broker/scale-in`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                symbol: symbol,
                amount: amount,
                current_price: activePrice,
                source_mode: sourceMode,
                enforce_safe_profit_lock: true
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al potenciar la posición');

        const r = data.result || {};
        logToTerminal(
            `🚀 [POTENCIAR GANADORA] Se inyectaron +$${amount.toFixed(2)} ${cur} en ${symbol} desde ${sourceLabel}. ` +
            `Inversión total: $${Number(r.new_cost_basis || 0).toFixed(2)} ${cur} | Nuevo Precio Promedio: $${Number(r.new_entry_price || 0).toFixed(4)} | Stop asegurado en +${Number(r.safe_stop_net_pct || 0.25).toFixed(2)}%.`,
            'action'
        );
        if (window.UIFeedback) {
            window.UIFeedback.toast(
                `Se sumaron +$${amount.toFixed(2)} ${cur} a ${symbol} (${sourceLabel}). Stop blindado en ganancia.`,
                { type: 'success', title: 'Posición Potenciada' }
            );
        }
        await window.syncBrokerStateFromBackend?.();
        await updateCapitalDisplay();
    } catch (e) {
        logToTerminal(`⚠️ Error potenciando ${symbol}: ${e.message}`, 'error');
        if (window.UIFeedback) {
            window.UIFeedback.toast(e.message, { type: 'error', title: 'No se pudo potenciar' });
        } else {
            alert(e.message);
        }
    }
};

window.rotarPosicionModal = async function(fromSymbol, fromPrice, fromCostBasis, fromPnlPct) {
    const cur = getCurrency(fromSymbol);

    // Regla estricta: NUNCA cerrar posiciones en negativo para rotar
    if (fromPnlPct <= 0.0) {
        const blockMsg = `🛡️ Regla de Rotación sin Pérdida: ${fromSymbol} está en ${fromPnlPct.toFixed(2)}%.\n\nEl sistema NUNCA cierra posiciones en negativo para rotar (para no cristalizar pérdidas). Solo permite rotar posiciones que ya estén en positivo pero vayan lentas hacia otra operación que vaya volando con más fuerza.`;
        if (window.UIFeedback) {
            window.UIFeedback.toast(blockMsg, { type: 'warning', title: 'Nunca se rota en negativo' });
        } else {
            alert(blockMsg);
        }
        return;
    }

    const allPositions = (window.backendOpenPositions && window.backendOpenPositions.length > 0)
        ? window.backendOpenPositions
        : [];

    // Buscar posiciones candidatas del mismo libro de moneda que estén en mayor ganancia (>= +0.20% y > fromPnlPct)
    const winners = allPositions.filter(p => {
        if (p.symbol === fromSymbol) return false;
        if ((p.currency || getCurrency(p.symbol)) !== cur) return false;
        const ePx = Number(p.entry_price || p.entryPrice || 0);
        const cPx = (p.symbol === currentSymbol && currentPriceSymbol === currentSymbol && currentPrice > 0)
            ? currentPrice
            : Number(p.current_price || p.currentPrice || ePx);
        const pct = ePx > 0 ? ((cPx - ePx) / ePx) * 100.0 : 0.0;
        return pct >= 0.20 && pct > fromPnlPct;
    });

    if (winners.length === 0) {
        const msg = `Para rotar el capital de ${fromSymbol} (+${fromPnlPct.toFixed(2)}%), debe existir otra posición abierta en ${cur} que esté ganando más fuerte (> +${Math.max(0.20, fromPnlPct).toFixed(2)}%) con Candado de Ganancia Segura.`;
        if (window.UIFeedback) {
            window.UIFeedback.toast(msg, { type: 'warning', title: 'Sin Ganadora Más Fuerte' });
        } else {
            alert(msg);
        }
        return;
    }

    // Ordenar candidatas de mayor a menor ganancia porcentual
    winners.sort((a, b) => Number(b.unrealized_pnl_pct || 0) - Number(a.unrealized_pnl_pct || 0));
    const bestWinner = winners[0];
    const candidateListStr = winners.map(w => {
        const ePx = Number(w.entry_price || 0);
        const cPx = Number(w.current_price || ePx);
        const pct = ePx > 0 ? ((cPx - ePx) / ePx) * 100.0 : 0.0;
        return `• ${w.symbol} (+${pct.toFixed(2)}%)`;
    }).join('\n');

    const promptText =
        `🔄 Rotar Capital de operación tranquila (${fromSymbol}, PnL ${fromPnlPct >= 0 ? '+' : ''}${fromPnlPct.toFixed(2)}%):\n` +
        `Se cerrará ${fromSymbol} liberando $${fromCostBasis.toFixed(2)} ${cur} y se inyectará ese capital en la operación ganadora.\n\n` +
        `Operaciones vigorosas disponibles (con Candado de Ganancia Segura):\n${candidateListStr}\n\n` +
        `Confirma o escribe el símbolo de la ganadora destino:`;

    let targetSym;
    if (window.UIFeedback) {
        targetSym = await window.UIFeedback.prompt(promptText, bestWinner.symbol, {
            title: `🔄 Rotar de ${fromSymbol} a Ganadora`,
            icon: '🔄',
            placeholder: bestWinner.symbol
        });
    } else {
        targetSym = prompt(promptText, bestWinner.symbol);
    }
    if (!targetSym) return;
    const cleanTarget = targetSym.trim().toUpperCase();
    const chosenWinner = winners.find(w => w.symbol.toUpperCase() === cleanTarget || w.symbol.split('/')[0].toUpperCase() === cleanTarget);
    if (!chosenWinner) {
        window.UIFeedback?.toast(`El activo destino "${cleanTarget}" no está en la lista de ganadoras activas.`, { type: 'warning' });
        return;
    }

    const toPx = (chosenWinner.symbol === currentSymbol && currentPriceSymbol === currentSymbol && currentPrice > 0)
        ? currentPrice
        : Number(chosenWinner.current_price || chosenWinner.entry_price || 0);

    try {
        const res = await fetch(`${API_BASE_URL}/api/broker/rotate-position`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                from_symbol: fromSymbol,
                to_symbol: chosenWinner.symbol,
                amount: fromCostBasis,
                from_price: fromPrice,
                to_price: toPx,
                enforce_safe_profit_lock: true
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al rotar la posición');

        const s = data.scaled_into || {};
        logToTerminal(
            `🔄 [ROTACIÓN TÁCTICA] Se cerró la operación tranquila ${fromSymbol} y se inyectaron $${Number(s.added_amount || fromCostBasis).toFixed(2)} ${cur} en la ganadora ${chosenWinner.symbol}. ` +
            `Nuevo total en ${chosenWinner.symbol}: $${Number(s.new_cost_basis || 0).toFixed(2)} ${cur} | Stop blindado en +${Number(s.safe_stop_net_pct || 0.25).toFixed(2)}%.`,
            'action'
        );
        if (window.UIFeedback) {
            window.UIFeedback.toast(
                `Rotación completada: ${fromSymbol} cerrada -> +$${Number(s.added_amount || fromCostBasis).toFixed(2)} ${cur} sumados a ${chosenWinner.symbol}.`,
                { type: 'success', title: 'Rotación Exitosa' }
            );
        }
        await window.syncBrokerStateFromBackend?.();
        await updateCapitalDisplay();
    } catch (e) {
        logToTerminal(`⚠️ Error en rotación ${fromSymbol} -> ${chosenWinner.symbol}: ${e.message}`, 'error');
        if (window.UIFeedback) {
            window.UIFeedback.toast(e.message, { type: 'error', title: 'Error en Rotación' });
        } else {
            alert(e.message);
        }
    }
};

symbolSelect.addEventListener('change', () => {
    currentSymbol = symbolSelect.value;
    logToTerminal(`Cambiando activo a ${currentSymbol}...`, 'warn');
    
    // Invalidad precio en pantalla y estado de activo para prevenir órdenes con precios desfasados
    currentPrice = 0;
    currentPriceSymbol = '';
    currentPriceTs = 0;
    const currentPriceElement = document.getElementById('currentPrice');
    if (currentPriceElement) currentPriceElement.innerText = '$--.---';
    updateChartHeaderTitles();

    // R2 item 5: Limpiar precio en segundo plano al cambiar de símbolo
    window.positionAssetPrice = null;
    window.positionAssetPriceTs = 0;

    // Si hay una posición abierta en otro activo, alertar y ejecutar riskTick de inmediato
    const pos = getOpenPosition();
    if (pos && pos.symbol !== currentSymbol) {
        logToTerminal(`ℹ️ Posición activa en ${pos.symbol}. El Agente de Riesgo continúa monitoreando tu posición de fondo mientras visualizas ${currentSymbol}.`, 'info');
        riskTick();
    }
    
    // Auto-ajustar sugerencia de broker fee y spread según activo (si no está en modo personalizado)
    const feeSelect = document.getElementById('brokerFeeSelect');
    const spreadEl = document.getElementById('spreadInput');
    if (feeSelect && feeSelect.value !== 'custom') {
        if (currentSymbol.includes('.BA')) {
            feeSelect.value = "0.50";
            if (spreadEl) spreadEl.value = "0.15";
        } else if (!currentSymbol.includes('/')) {
            // Acciones y ETFs EE.UU. / Wall Street (IBKR Tiered / Discount: 0.02% orden, spread 0.02%)
            feeSelect.value = "0.02";
            if (spreadEl) spreadEl.value = "0.02";
        } else {
            // Cripto Spot estándar (Binance / Bybit: 0.10% orden, spread 0.05%)
            feeSelect.value = "0.10";
            if (spreadEl) spreadEl.value = "0.05";
        }
        if (spreadEl) localStorage.setItem('ai_spread_estimate_v1', spreadEl.value);
        updateBrokerFeeDisplay();
    }
    
    candleSeries.setData([]); // Limpiar gráfico
    smaSeries.setData([]);
    vwapSeries.setData([]);
    vwapUpperSeries.setData([]);
    vwapLowerSeries.setData([]);
    if (rsiSeries) rsiSeries.setData([]);
    if (atrSeries) atrSeries.setData([]);
    fetchMarketData();
    updateSentiment();
    if (typeof updateCapitalDisplay === 'function') updateCapitalDisplay();
});

// --- SINCRONIZACIÓN DE SALDOS REALES DEL BROKER ---
window.syncBrokerBalances = async function() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/broker/balances`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === 'ok' && data.vault) {
            portfolio.vault = {
                USDT: Number(data.vault.USDT) || 0,
                USD: Number(data.vault.USD) || 0,
                ARS: Number(data.vault.ARS) || 0,
            };
            if (data.operational) {
                portfolio.balances = {
                    USDT: Number(data.operational.USDT) || 0,
                    USD: Number(data.operational.USD) || 0,
                    ARS: Number(data.operational.ARS) || 0,
                };
            }
            const activeCurr = getCurrency(currentSymbol);
            if (data.fees_paid && data.fees_paid[activeCurr] !== undefined) {
                portfolio.totalFeesPaid = Number(data.fees_paid[activeCurr]) || 0;
            }
            localStorage.setItem('ai_portfolio_v5', JSON.stringify(portfolio));
            updateCapitalDisplay();
        }
    } catch (e) {
        console.warn('Error sincronizando saldos de broker:', e);
    }
};

// Sincronización inicial y periódica con el backend
syncBrokerBalances();
setInterval(syncBrokerBalances, 15000);

// Obtener datos reales del motor Python (con protección contra respuestas tardías)
async function fetchMarketData() {
    const reqSymbol = currentSymbol;
    try {
        logToTerminal(`Conectando al motor Python para obtener velas de ${reqSymbol}...`, 'info');
        const tfVal = document.getElementById('timeframeSelect')?.value || '5m';
        const response = await fetch(`${API_BASE_URL}/api/market/history?symbol=${encodeURIComponent(reqSymbol)}&timeframe=${tfVal}&limit=300`, {
            headers: apiAuthHeaders()
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        if (reqSymbol !== currentSymbol) return; // Descartar si el usuario cambió de símbolo durante la petición
        
        if (data && !data.error) {
            try {
                window.lastRawMarketData = data;
                const cleanCandleData = data.map(d => ({time: d.time, open: d.open, high: d.high, low: d.low, close: d.close}));
                candleSeries.setData(cleanCandleData);
                
                // Actualizar indicador visual de tipo de vela con la vela más reciente
                if (data.length > 0 && typeof window.updateCandlePatternIndicator === 'function') {
                    const lastC = data[data.length - 1];
                    const prevC = data.length > 1 ? data[data.length - 2] : null;
                    const prev2C = data.length > 2 ? data[data.length - 3] : null;
                    window.updateCandlePatternIndicator(lastC, prevC, prev2C);
                }
                
                const smaData = data.filter(d => typeof d.sma_20 === 'number' && !isNaN(d.sma_20)).map(d => ({ time: d.time, value: d.sma_20 }));
                if (smaData.length > 0) smaSeries.setData(smaData);
                
                const vwapData = data.filter(d => typeof d.vwap === 'number' && !isNaN(d.vwap)).map(d => ({ time: d.time, value: d.vwap }));
                if (vwapData.length > 0) vwapSeries.setData(vwapData);
                
                const vwapUpperData = data.filter(d => typeof d.vwap_upper === 'number' && !isNaN(d.vwap_upper)).map(d => ({ time: d.time, value: d.vwap_upper }));
                if (vwapUpperData.length > 0) vwapUpperSeries.setData(vwapUpperData);
                
                const vwapLowerData = data.filter(d => typeof d.vwap_lower === 'number' && !isNaN(d.vwap_lower)).map(d => ({ time: d.time, value: d.vwap_lower }));
                if (vwapLowerData.length > 0) vwapLowerSeries.setData(vwapLowerData);

                // --- ACTUALIZACIÓN DE RSI (14) Y ATR (14) ---
                const rsiData = data.filter(d => typeof d.rsi === 'number' && !isNaN(d.rsi)).map(d => ({ time: d.time, value: d.rsi }));
                if (rsiSeries && rsiData.length > 0) {
                    rsiSeries.setData(rsiData);
                    window.updateRsiBadge(rsiData[rsiData.length - 1].value);
                }

                const atrData = data.filter(d => typeof d.atr === 'number' && !isNaN(d.atr) && d.atr > 0).map(d => ({ time: d.time, value: d.atr }));
                if (atrSeries && atrData.length > 0) {
                    atrSeries.setData(atrData);
                    const lastClose = cleanCandleData[cleanCandleData.length - 1]?.close || 0;
                    window.updateAtrBadge(atrData[atrData.length - 1].value, lastClose);
                }

                // Inyectar marcas visuales de operaciones (E / S) en el gráfico
                if (typeof window.updateChartTradeMarkers === 'function') {
                    window.updateChartTradeMarkers();
                }
            } catch(e) {
                logToTerminal("ERROR GRÁFICO: " + e.message, "error");
            }
            const currentPriceElement = document.getElementById('currentPrice');
            currentPrice = data[data.length - 1].close; 
            currentPriceSymbol = reqSymbol;
            currentPriceTs = Date.now();
            currentPriceElement.innerText = `$${currentPrice.toLocaleString()}`;
            updateCapitalDisplay();
            updateChartHeaderTitles();
            logToTerminal('Gráfico actualizado con datos reales.', 'action');
        } else {
            logToTerminal('Error de datos: ' + (data?.error || 'Sin datos'), 'error');
        }
    } catch (error) {
        logToTerminal(`Fallo al conectar con FastAPI: ${error.message}`, 'error');
    }
}

function updateChartHeaderTitles() {
    const titleSym = document.getElementById('chartTitleSymbol');
    if (titleSym) {
        const meta = getAssetMeta(currentSymbol);
        if (meta) {
            titleSym.innerHTML = `<span class="mr-1">${meta.icon}</span><span class="text-white">${escapeHtml(meta.name)}</span> <span class="text-xs text-blue-400 font-mono font-normal">(${escapeHtml(currentSymbol)})</span>`;
        } else {
            titleSym.innerText = currentSymbol;
        }
    }
    const titleTf = document.getElementById('chartTitleTf');
    if (titleTf) {
        const tfVal = document.getElementById('timeframeSelect')?.value || '5m';
        const tfLabels = {
            '1m': '1 Minuto',
            '5m': '5 Minutos',
            '15m': '15 Minutos',
            '1h': '1 Hora',
            '4h': '4 Horas',
            '1d': '1 Día'
        };
        titleTf.innerText = tfLabels[tfVal] || tfVal;
    }
    if (typeof window.updateQuickTimeframeButtons === 'function') {
        window.updateQuickTimeframeButtons(document.getElementById('timeframeSelect')?.value || '5m');
    }
}

window.updateQuickTimeframeButtons = function(activeTf) {
    const bar = document.getElementById('ku-quick-tf-bar');
    if (!bar) return;
    const btns = bar.querySelectorAll('.ku-tf-btn');
    btns.forEach(btn => {
        const tf = btn.getAttribute('data-tf');
        if (tf === activeTf) {
            btn.className = 'ku-tf-btn px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/25 text-emerald-300 border border-emerald-500/50 cursor-pointer transition shadow-sm';
        } else {
            btn.className = 'ku-tf-btn px-1.5 py-0.5 rounded text-[10px] font-bold text-slate-400 hover:text-white cursor-pointer transition';
        }
    });
};

window.setChartTimeframe = function(tf) {
    const sel = document.getElementById('timeframeSelect');
    if (sel && sel.value !== tf) {
        sel.value = tf;
        sel.dispatchEvent(new Event('change'));
    } else {
        window.updateQuickTimeframeButtons(tf);
        updateChartHeaderTitles();
    }
};

// Cargar datos al iniciar
fetchMarketData();
updateChartHeaderTitles();

window.addEventListener('resize', () => {
    if (chart && chartContainer) chart.applyOptions({ width: chartContainer.clientWidth });
    if (rsiChart && rsiContainer) rsiChart.applyOptions({ width: rsiContainer.clientWidth });
    if (atrChart && atrContainer) atrChart.applyOptions({ width: atrContainer.clientWidth });
});

// Ciclo de IA (Bloque 4: Ciclo de vida idempotente y gestión de señales)
let isAgentActive = false;
let copilotState = 'idle'; // 'idle' | 'awaiting'
let simulateInterval = null;
let cycleInFlight = false; // Mutex para evitar análisis concurrentes en vuelo
let cycleStartedAt = 0; // Timestamp de inicio para watchdog
let activeAnalysisController = null;
let analysisAbortReason = null;
let isExecutingTrade = false; // Mutex para evitar ejecuciones concurrentes de órdenes
let lastHandledCandle = { symbol: '', candleTs: 0 };
let copilotExpiryTimer = null;
let isStopAfterCloseArmed = localStorage.getItem('ai_stop_after_close') === 'true'; // Graceful Shutdown post-trade

function scheduleNext(delayMs) {
    if (simulateInterval) clearTimeout(simulateInterval);
    if (isAgentActive) {
        simulateInterval = setTimeout(ejecutarAnalisis, delayMs);
    }
}

function getExecutionMode() {
    return document.getElementById('navAgentModeSelect')?.value || 'smart';
}

function isSmartMode() {
    return getExecutionMode() === 'smart';
}

function updateAgentButtonState() {
    if (copilotState === 'awaiting') {
        agentToggle.innerText = 'Esperando decisión…';
        agentToggle.disabled = true;
        agentToggle.className = 'bg-yellow-600 opacity-75 cursor-not-allowed px-4 py-2 rounded font-semibold transition';
        return;
    }
    agentToggle.disabled = false;
    if (isAgentActive) {
        agentToggle.innerText = 'Detener Agente (Kill Switch)';
        agentToggle.className = 'bg-red-600 hover:bg-red-700 px-4 py-2 rounded font-semibold transition';
    } else {
        const mode = getExecutionMode();
        if (mode === 'smart') {
            agentToggle.innerText = 'Activar Modo Inteligente';
            agentToggle.className = 'bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded font-semibold transition shadow-[0_0_12px_rgba(168,85,247,0.4)]';
        } else if (mode === 'auto') {
            agentToggle.innerText = 'Activar Trading Autónomo';
            agentToggle.className = 'bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded font-semibold transition';
        } else {
            agentToggle.innerText = 'Activar Modo Copiloto';
            agentToggle.className = 'bg-emerald-600 hover:bg-emerald-700 px-4 py-2 rounded font-semibold transition';
        }
    }
}

function syncAgentModes(source) {
    const navEl = document.getElementById('navAgentModeSelect');
    const execEl = document.getElementById('executionModeSelect');
    const badgeEl = document.getElementById('smartRoutingBadge');
    const modalBadge = document.getElementById('settingsActiveModeBadge');
    
    const mode = navEl?.value || 'smart';
    if (execEl) execEl.value = mode;

    const isSmart = (mode === 'smart');
    if (badgeEl) badgeEl.classList.toggle('hidden', !isSmart);

    if (modalBadge) {
        if (mode === 'smart') {
            modalBadge.innerText = '🧠 Inteligente';
            modalBadge.className = 'text-xs font-mono font-bold px-2 py-0.5 bg-purple-900/60 text-purple-300 rounded border border-purple-500/50';
        } else if (mode === 'auto') {
            modalBadge.innerText = '⚡ Autónomo';
            modalBadge.className = 'text-xs font-mono font-bold px-2 py-0.5 bg-blue-900/60 text-blue-300 rounded border border-blue-500/50';
        } else {
            modalBadge.innerText = '🛡️ Copiloto';
            modalBadge.className = 'text-xs font-mono font-bold px-2 py-0.5 bg-emerald-900/60 text-emerald-300 rounded border border-emerald-500/50';
        }
    }

    if (source === 'user') {
        localStorage.setItem('ai_execution_mode_v1', mode);
        if (mode === 'smart') {
            logToTerminal('🧠 Modo Inteligente ACTIVADO: Auto-ruteo multi-activo según directivas y señales aprobadas.', 'info');
        } else if (mode === 'auto') {
            logToTerminal('⚡ Modo Autónomo Fijo ACTIVADO: Ejecución directa en el símbolo actual sin confirmación manual.', 'info');
        } else {
            logToTerminal('🛡️ Modo Copiloto ACTIVADO: Cada orden solicitará confirmación manual previa.', 'info');
        }
    }

    updateAgentButtonState();
}

document.getElementById('navAgentModeSelect')?.addEventListener('change', () => syncAgentModes('user'));

const savedExecutionMode = localStorage.getItem('ai_execution_mode_v1');
if (savedExecutionMode && ['smart', 'auto', 'copilot'].includes(savedExecutionMode)) {
    const navEl = document.getElementById('navAgentModeSelect');
    if (navEl) navEl.value = savedExecutionMode;
}
syncAgentModes('init');

function startAgent(reason = 'user') {
    if (isCircuitBreakerActive()) {
        const state = getRiskState();
        logToTerminal(`🛑 No se puede activar el agente: Circuit Breaker activo (${state.haltReason || 'Pausa 24h'}).`, 'error');
        return;
    }
    if (isAgentActive) return;
    userExplicitlyStopped = false;
    isAgentActive = true;
    copilotState = 'idle';

    updateAgentButtonState();

    // Distinguir sesión si el agente estuvo suspendido
    if (agentWasSuspended && !isCopilotApprovalPause) {
        const hasTradesInCurrentSession = tradeHistoryLog.some(t => (t.sessionId || 1) === currentSessionId);
        if (hasTradesInCurrentSession) {
            currentSessionId += 1;
            localStorage.setItem('ai_current_session_id', currentSessionId.toString());
            logToTerminal(`🔄 Reanudando agente: Nueva sesión iniciada (#${currentSessionId}).`, 'info');
        }
        agentWasSuspended = false;
        renderTradeHistory();
        if (typeof window.updateChartTradeMarkers === 'function') {
            window.updateChartTradeMarkers();
        }
    }
    isCopilotApprovalPause = false;

    const smartSuffix = isSmartMode() ? ' en Modo Inteligente (Multi-Activo)' : '';
    logToTerminal(`Agente activado${smartSuffix} (Motivo: ${reason}). Iniciando análisis cuantitativo.`, 'info');
    ejecutarAnalisis();

    const isExplicitUserStart = (reason === 'user' || reason === 'manual_user');
    syncRunningDaemonConfig({ syncSymbol: isExplicitUserStart, syncTimeframe: isExplicitUserStart });
}

function syncRunningDaemonConfig(options = {}) {
    if (!isAgentActive) return;
    if (window.scalpingSessionState && (window.scalpingSessionState.active || window.scalpingSessionState.draining)) {
        // 5m y el ciclo presencial son exclusivos de Sesión Presencial; no pisar con config de fondo ni grabar 5m en daemon_state.json
        return;
    }
    try {
        const { syncSymbol = false, syncTimeframe = false } = options || {};
        const srv = window.serverDaemonConfig || {};
        const targetStrategy = document.getElementById('strategyModeSelect')?.value || 'auto';
        const targetDaemonSymbol = (!syncSymbol && srv.symbol) ? srv.symbol : currentSymbol;
        const rawDaemonTimeframe = (!syncTimeframe && srv.timeframe)
            ? srv.timeframe
            : (document.getElementById('timeframeSelect')?.value || '4h');
        const targetDaemonTimeframe = (typeof tradingGuards !== 'undefined' && typeof tradingGuards.resolveBackgroundDaemonTimeframe === 'function')
            ? tradingGuards.resolveBackgroundDaemonTimeframe(targetStrategy, rawDaemonTimeframe)
            : (targetStrategy === 'auto' ? '4h' : rawDaemonTimeframe);
        const targetAllowed = typeof window.getAllowedStrategies === 'function'
            ? window.getAllowedStrategies()
            : ALL_TACTICAL_STRATEGIES.map(s => s.id);

        const brainParsed = parseBrainSelection(document.getElementById('engineSelect')?.value || 'local');
        const tpSlVal = document.getElementById('tpSlSelect')?.value || "2.1|-0.6";
        const [tpStr, slStr] = tpSlVal.split('|');
        const tpVal = Math.abs(parseFloat(tpStr)) || 1.0;
        const slVal = Math.abs(parseFloat(slStr)) || 0.5;
        const riskSlotFrac = parseFloat(document.getElementById('riskSelect')?.value || '0.25') || 0.25;
        const maxPosFromSlot = riskSlotFrac >= 0.99 ? 1 : (riskSlotFrac >= 0.49 ? 2 : 4);
        const slotAllocPct = Math.round(riskSlotFrac * 100);
        window.serverDaemonConfig = {
            ...srv,
            symbol: targetDaemonSymbol,
            timeframe: targetDaemonTimeframe,
            strategy: targetStrategy,
            allowed_strategies: targetAllowed,
        };
        fetch(`${API_BASE_URL}/api/daemon/start`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                symbol: targetDaemonSymbol,
                timeframe: targetDaemonTimeframe,
                strategy: targetStrategy,
                allowed_strategies: targetAllowed,
                slot_alloc_pct: slotAllocPct,
                max_positions: maxPosFromSlot,
                engine: brainParsed.engine,
                model: brainParsed.model,
                tp: tpVal,
                sl: slVal,
                mode: isSmartMode() ? 'smart' : 'fixed'
            })
        }).catch(err => console.debug('Aviso notificando daemon:', err));
    } catch (_) {}
}

let userExplicitlyStopped = false;

function stopAgent(reason = 'user', { copilotPause = false } = {}) {
    if (!copilotPause) {
        userExplicitlyStopped = true;
    }
    if (simulateInterval) {
        clearTimeout(simulateInterval);
        simulateInterval = null;
    }
    if (activeAnalysisController && !activeAnalysisController.signal.aborted) {
        analysisAbortReason = reason === 'circuit_breaker' ? 'circuit_breaker' : 'stopped';
        activeAnalysisController.abort();
    }

    // Notificar al worker autónomo en Python para detenerse
    fetch(`${API_BASE_URL}/api/daemon/stop`, {
        method: 'POST',
        headers: apiAuthHeaders()
    }).catch(err => console.debug('Aviso deteniendo daemon:', err));

    if (copilotPause) {
        copilotState = 'awaiting';
        isCopilotApprovalPause = true;
        isAgentActive = false;
        updateAgentButtonState();
    } else {
        const wasActive = isAgentActive;
        copilotState = 'idle';
        isCopilotApprovalPause = false;
        isAgentActive = false;
        updateAgentButtonState();

        if (copilotExpiryTimer) {
            clearInterval(copilotExpiryTimer);
            copilotExpiryTimer = null;
        }
        if (modal && !modal.classList.contains('hidden')) {
            modal.classList.add('hidden');
            pendingTrade = null;
        }

        if (wasActive && reason !== 'circuit_breaker') {
            agentWasSuspended = true;
            renderTradeHistory();
        if (typeof window.updateChartTradeMarkers === 'function') {
            window.updateChartTradeMarkers();
        }
        }
        logToTerminal(`Agente detenido (Motivo: ${reason}).`, 'warn');
    }
}

let lastLoggedDaemonCycle = 0;
let lastLoggedDaemonReason = '';
let lastClosedBackendPosId = null;

async function checkDaemonServerStatus() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/daemon/status`, { headers: apiAuthHeaders() });
        if (!res.ok) return;
        const data = await res.json();
        if (data) {
            window.lastDaemonReason = data.last_reason || '';
            const qcReasonEl = document.getElementById('kula-qc-reason');
            if (qcReasonEl && data.last_reason) {
                qcReasonEl.textContent = `Último motivo: ${data.last_reason}`;
                qcReasonEl.title = data.last_reason;
            }
            window.serverDaemonConfig = {
                symbol: data.symbol || currentSymbol,
                timeframe: data.timeframe || '15m',
                strategy: data.strategy || 'auto',
                allowed_strategies: Array.isArray(data.allowed_strategies) ? data.allowed_strategies : null,
            };
        }
        if (data && data.is_running && userExplicitlyStopped) {
            fetch(`${API_BASE_URL}/api/daemon/stop`, {
                method: 'POST',
                headers: apiAuthHeaders()
            }).catch(() => {});
            return;
        }
        if (data && Number(data.cycle_count) < lastLoggedDaemonCycle) {
            lastLoggedDaemonCycle = 0;
            lastLoggedDaemonReason = '';
        }
        if (data && data.is_running && !isAgentActive && !userExplicitlyStopped) {
            isAgentActive = true;
            updateAgentButtonState();
            lastLoggedDaemonCycle = Number(data.cycle_count) || 0;
            lastLoggedDaemonReason = data.last_reason || '';
            const cycleSymbol = data.active_symbol || data.symbol;
            logToTerminal(`🟢 [SERVIDOR ACTIVO] Agente autónomo detectado operando en segundo plano en ${cycleSymbol} (Ciclo #${data.cycle_count}).`, 'action');
            if (data.last_signal) {
                logToTerminal(`🤖 [CICLO #${data.cycle_count} · ${cycleSymbol} · ${data.timeframe}] [${data.last_signal}] ${data.last_reason || ''}`, 'info');
            }
        } else if (data && data.is_running && (
            Number(data.cycle_count) > lastLoggedDaemonCycle ||
            (data.scalping && data.scalping.active && data.last_reason && data.last_reason !== lastLoggedDaemonReason)
        )) {
            lastLoggedDaemonCycle = Number(data.cycle_count) || lastLoggedDaemonCycle;
            lastLoggedDaemonReason = data.last_reason || '';
            const cycleSymbol = data.active_symbol || data.symbol;
            if (data.last_signal) {
                logToTerminal(`🤖 [CICLO #${data.cycle_count} · ${cycleSymbol} · ${data.timeframe}] [${data.last_signal}] ${data.last_reason || ''}`, 'info');
            }
        }

        // Sincronizar Cooldown desde el servidor hacia el navegador
        if (data && Number(data.cooldown_remaining_s) > 0) {
            const serverCooldownUntil = Date.now() + Number(data.cooldown_remaining_s) * 1000;
            const currentCooldownUntil = Number(localStorage.getItem('ai_cooldown_v1')) || 0;
            if (serverCooldownUntil > currentCooldownUntil + 2000) {
                localStorage.setItem('ai_cooldown_v1', String(Math.round(serverCooldownUntil)));
            }
        }

        // Sincronizar estado de Scalping Presencial (Trading con Presencia)
        if (data && data.scalping) {
            updateScalpingUIState(data.scalping);
        }

        // Sincronizar posiciones abiertas desde el servidor Python al Cockpit visual
        if (data && data.trailing_telemetry) {
            window.backendTrailingTelemetry = data.trailing_telemetry;
        }
        if (data && Array.isArray(data.open_positions) && data.open_positions.length > 0) {
            window.backendOpenPositions = data.open_positions;
            const backendPos = data.open_positions[0];
            if (backendPos.id && backendPos.id === lastClosedBackendPosId) {
                // Posición recién cerrada desde el navegador; esperar a que finalice /api/broker/flatten
            } else if (!portfolio.position || portfolio.position.symbol !== backendPos.symbol || !portfolio.position.backendId) {
                const currency = backendPos.currency || getCurrency(backendPos.symbol);
                const slGross = Number(backendPos.initial_sl_pct || 0.5);
                const tpGross = Number(backendPos.initial_tp_pct || 0.8);
                const feeR = 0.1;
                const spreadR = 0.05;
                const stopNet = tradingGuards.netReturnAfterCosts(-slGross, feeR, spreadR);
                const tpNet = tradingGuards.netReturnAfterCosts(tpGross, feeR, spreadR);
                const activeStrategyMode = getStrategyMode();
                portfolio.position = {
                    backendId: backendPos.id || null,
                    side: String(backendPos.side || 'LONG').toUpperCase(),
                    symbol: backendPos.symbol,
                    baseCoin: backendPos.symbol.split('/')[0],
                    currency: currency,
                    qty: Number(backendPos.qty),
                    entryPrice: Number(backendPos.entry_price),
                    costBasis: Number(backendPos.cost_basis),
                    sl: slGross,
                    tp: Number.isFinite(tpNet) && tpNet > 0 ? tpNet : tpGross,
                    stopNetPct: backendPos.current_stop_net_pct !== undefined ? Number(backendPos.current_stop_net_pct) : (Number.isFinite(stopNet) ? stopNet : -(slGross + 0.3)),
                    beArmed: Boolean(backendPos.be_armed),
                    trailActive: Boolean(backendPos.trail_active),
                    peakPrice: Number(backendPos.peak_price || backendPos.entry_price),
                    feeRate: feeR,
                    spreadRate: spreadR,
                    jitAllocated: true,
                    strategyMode: activeStrategyMode,
                    trailPct: activeStrategyMode === 'trailing_trend_runner' ? (slGross || 2.0) : 0.5
                };
            } else if (portfolio.position && portfolio.position.backendId === backendPos.id) {
                portfolio.position.side = String(backendPos.side || portfolio.position.side || 'LONG').toUpperCase();
                portfolio.position.qty = Number(backendPos.qty);
                if (backendPos.current_stop_net_pct !== undefined) {
                    portfolio.position.stopNetPct = Number(backendPos.current_stop_net_pct);
                }
                portfolio.position.beArmed = Boolean(backendPos.be_armed);
                portfolio.position.trailActive = Boolean(backendPos.trail_active);
                if (backendPos.peak_price) {
                    portfolio.position.peakPrice = Number(backendPos.peak_price);
                }
            }
            updateCapitalDisplay();
        } else if (data && data.open_positions_count === 0 && data.is_running) {
            window.backendOpenPositions = [];
            if (portfolio.position && portfolio.position.backendId) {
                portfolio.position = null;
                const tfSecMap = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '1d': 86400 };
                const tfVal = document.getElementById('timeframeSelect')?.value || '15m';
                const cooldownMs = Math.max(300000, 3 * (tfSecMap[tfVal] || 900) * 1000);
                localStorage.setItem('ai_cooldown_v1', String(Date.now() + cooldownMs));
            }
            updateCapitalDisplay();
        }
        await syncBrokerTrades();
    } catch (_) {}
}

window.scalpingSessionState = {
    active: false,
    draining: false,
    symbol: 'ETH/USDT',
    strategy: 'scalping_vwap_2sigma_5m',
    timeframe: '5m',
    elapsed_minutes: 0.0,
    open_scalp_positions: 0
};

function updateScalpingUIState(scalp) {
    window.scalpingSessionState = scalp;
    const badgeState = document.getElementById('badgeScalpingState');
    const btnToggle = document.getElementById('btnScalpingToggle');
    const btnIcon = document.getElementById('scalpingBtnIcon');
    const btnText = document.getElementById('scalpingBtnText');
    const txtTelemetry = document.getElementById('txtScalpingTelemetry');
    const selStrategy = document.getElementById('selScalpingStrategy');
    const selSymbol = document.getElementById('selScalpingSymbol');
    const selSlot = document.getElementById('selScalpingSlot');

    if (!badgeState || !btnToggle) return;

    if (scalp.draining) {
        badgeState.className = 'text-[10px] font-mono px-2 py-0.5 rounded font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse';
        badgeState.innerText = 'DRENANDO POSICIONES';
        btnToggle.className = 'px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 cursor-not-allowed bg-amber-600/60 text-white border border-amber-500/40 opacity-90';
        btnToggle.disabled = true;
        if (btnIcon) btnIcon.innerText = '⏳';
        if (btnText) btnText.innerText = `Drenando trades (${scalp.open_scalp_positions} abiertas)`;
        if (txtTelemetry) {
            txtTelemetry.classList.remove('hidden');
            txtTelemetry.innerText = `[Drenado activo: cerrando con guardián matemático]`;
        }
        if (selStrategy) selStrategy.disabled = true;
        if (selSymbol) selSymbol.disabled = true;
        if (selSlot) selSlot.disabled = true;
    } else if (scalp.active) {
        badgeState.className = 'text-[10px] font-mono px-2 py-0.5 rounded font-bold bg-red-500/20 text-red-300 border border-red-500/40 animate-pulse';
        badgeState.innerText = '🔴 EN VIVO (PRESENCIAL)';
        btnToggle.className = 'px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 cursor-pointer bg-red-600 hover:bg-red-500 text-white shadow-lg shadow-red-900/30';
        btnToggle.disabled = false;
        if (btnIcon) btnIcon.innerText = '⏹️';
        if (btnText) btnText.innerText = 'Terminar Sesión (Drenar y Volver a Auto)';
        if (txtTelemetry) {
            txtTelemetry.classList.remove('hidden');
            const slotTxt = scalp.slot_alloc_pct ? ` · Slot ${Math.round(Number(scalp.slot_alloc_pct))}%` : '';
            txtTelemetry.innerText = `[${scalp.symbol} · ${scalp.timeframe}${slotTxt} · ${scalp.elapsed_minutes} min]`;
            txtTelemetry.title = window.lastDaemonReason || '';
        }
        if (selStrategy) {
            selStrategy.value = scalp.strategy;
            selStrategy.disabled = true;
        }
        if (selSymbol) {
            selSymbol.value = scalp.symbol;
            selSymbol.disabled = true;
        }
        if (selSlot) {
            if (scalp.slot_alloc_pct) {
                const normVal = (Number(scalp.slot_alloc_pct) / 100).toFixed(2);
                if ([...selSlot.options].some(o => o.value === normVal)) selSlot.value = normVal;
            }
            selSlot.disabled = true;
        }
    } else {
        badgeState.className = 'text-[10px] font-mono px-2 py-0.5 rounded font-bold bg-slate-800 text-slate-400 border border-slate-700';
        badgeState.innerText = 'INACTIVO';
        btnToggle.className = 'px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 cursor-pointer bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/30';
        btnToggle.disabled = false;
        if (btnIcon) btnIcon.innerText = '⚡';
        if (btnText) btnText.innerText = 'Iniciar Sesión Presencial';
        if (txtTelemetry) {
            txtTelemetry.classList.add('hidden');
        }
        if (selStrategy) selStrategy.disabled = false;
        if (selSymbol) selSymbol.disabled = false;
        if (selSlot) selSlot.disabled = false;
    }
}

window.toggleScalpingSession = async function() {
    const isCurrentlyActive = window.scalpingSessionState && (window.scalpingSessionState.active || window.scalpingSessionState.draining);
    const selStrategy = document.getElementById('selScalpingStrategy')?.value || '';
    const selSymbol = document.getElementById('selScalpingSymbol')?.value || 'ETH/USDT';
    const selSlotFrac = parseFloat(document.getElementById('selScalpingSlot')?.value || document.getElementById('riskSelect')?.value || '0.25') || 0.25;
    const selSlotPct = Math.round(selSlotFrac * 100);
    const selOpt = document.getElementById('selScalpingStrategy')?.selectedOptions?.[0];
    const tf = selOpt?.dataset?.timeframe || (selStrategy.includes('15m') ? '15m' : (selStrategy.includes('1h') ? '1h' : '5m'));

    if (!isCurrentlyActive && (!selStrategy || selStrategy === '')) {
        logToTerminal(`⚠️ [SCALPING BLOQUEADO] Sin fórmulas en catalogo/operador_presente/. Las 5 estrategias están en cuarentena por fallar la auditoría temporal.`, 'warn');
        alert('⚠️ Scalping Bloqueado: No hay fórmulas autorizadas en operador_presente/. Las estrategias fallaron la auditoría temporal de consistencia y fueron archivadas en heredadas.');
        return;
    }

    if (isCurrentlyActive) {
        logToTerminal(`⏹️ [SCALPING] Finalizando sesión presencial. Activando Drenado Elegante...`, 'warn');
        try {
            const res = await fetch(`${API_BASE_URL}/api/daemon/scalping/stop`, {
                method: 'POST',
                headers: apiAuthHeaders()
            });
            const data = await res.json();
            if (data && data.config) {
                updateScalpingUIState(data.config);
            }
            logToTerminal(`🛡️ [SCALPING] ${data.message}`, 'info');
        } catch (err) {
            logToTerminal(`❌ Error al detener scalping: ${err.message}`, 'error');
        }
    } else {
        logToTerminal(`⚡ [SCALPING] Iniciando sesión presencial en ${selSymbol} [${tf}] con ${selStrategy} (Slot: ${selSlotPct}%)...`, 'action');
        try {
            const res = await fetch(`${API_BASE_URL}/api/daemon/scalping/start`, {
                method: 'POST',
                headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({
                    symbol: selSymbol,
                    strategy: selStrategy,
                    timeframe: tf,
                    slot_alloc_pct: selSlotPct
                })
            });
            const data = await res.json();
            if (data && data.active) {
                updateScalpingUIState(data);
                logToTerminal(`🟢 [SCALPING EN VIVO] Sesión presencial activa. Árbitro IA supervisando velas de ${tf} (Slot: ${selSlotPct}%).`, 'action');
            }
        } catch (err) {
            logToTerminal(`❌ Error al iniciar scalping: ${err.message}`, 'error');
        }
    }
};

agentToggle.addEventListener('click', () => {
    if (copilotState === 'awaiting') return;
    if (isAgentActive) {
        stopAgent('manual_user');
    } else {
        startAgent('manual_user');
    }
});
checkDaemonServerStatus();
syncBrokerTrades();
setInterval(checkDaemonServerStatus, 10000);
if (typeof checkKulaSemaforo === 'function') {
    checkKulaSemaforo(false);
    setInterval(() => checkKulaSemaforo(false), 30000);
}

async function fetchFreshExecutionQuote(symbol, parentSignal = null, allowStaleOrClosed = false) {
    const controller = new AbortController();
    let timedOut = false;
    const abortFromParent = () => controller.abort();
    parentSignal?.addEventListener('abort', abortFromParent, { once: true });
    const timeoutId = setTimeout(() => {
        timedOut = true;
        controller.abort();
    }, 5000);
    try {
        const response = await fetch(
            `${API_BASE_URL}/api/market/price?symbol=${encodeURIComponent(symbol)}`,
            { headers: apiAuthHeaders(), signal: controller.signal }
        );
        if (!response.ok) throw new Error(`HTTP ${response.status} al consultar precio de ejecución.`);
        const quote = await response.json();
        if (!tradingGuards.isFreshQuote(quote)) {
            if (allowStaleOrClosed && Number.isFinite(Number(quote.price)) && Number(quote.price) > 0) {
                return Number(quote.price);
            }
            throw new Error(`Cotización no ejecutable: mercado cerrado o dato vencido (${quote.quote_age_s ?? 'N/A'}s; umbral ${quote.stale_threshold_s ?? 'N/A'}s).`);
        }
        return Number(quote.price);
    } catch (err) {
        if (timedOut && !parentSignal?.aborted) {
            throw new Error('Timeout de 5 segundos consultando el precio de ejecución.');
        }
        throw err;
    } finally {
        clearTimeout(timeoutId);
        parentSignal?.removeEventListener('abort', abortFromParent);
    }
}

const ejecutarAnalisis = async () => {
    if (!isAgentActive) return;

    // 1. Verificación del Circuit Breaker (Bloque 3)
    if (isCircuitBreakerActive()) {
        const state = getRiskState();
        const hoursLeft = state.haltedUntil ? ((state.haltedUntil - Date.now()) / (1000 * 60 * 60)).toFixed(1) : 0;
        logToTerminal(`🛑 [CIRCUIT BREAKER] Agente en pausa preventiva (${hoursLeft}h restantes. Motivo: ${state.haltReason || 'Riesgo'}).`, 'error');
        stopAgent('circuit_breaker');
        return;
    }

    // 2. Watchdog: cancelar el análisis activo si supera los 130 segundos.
    const nowMs = Date.now();
    if (cycleInFlight && (nowMs - cycleStartedAt > 130000)) {
        logToTerminal('⚠️ [WATCHDOG] Ciclo de análisis excedió el tiempo límite. Cancelando la petición activa sin liberar el mutex antes de que termine.', 'warn');
        if (activeAnalysisController && !activeAnalysisController.signal.aborted) {
            analysisAbortReason = 'watchdog';
            activeAnalysisController.abort();
        }
    }

    if (cycleInFlight) {
        logToTerminal('⏳ Análisis previo aún en curso. Esperando liberación de recursos...', 'warn');
        scheduleNext(5000);
        return;
    }

    cycleInFlight = true;
    cycleStartedAt = nowMs;
    let rescheduled = false;
    let timeoutId = null;
    let controller = null;

    const brain = parseBrainSelection(document.getElementById('engineSelect')?.value || 'local');
    const engine = brain.engine === 'gemini' ? 'ai' : brain.engine;
    try {
        // Verificar si estamos dentro del horario de operación
        const scheduleMode = document.getElementById('scheduleModeSelect')?.value || 'libre';
        if (scheduleMode === 'custom') {
            const startTime = document.getElementById('timeStart').value;
            const endTime = document.getElementById('timeEnd').value;
            const now = new Date();
            const currentMinutes = now.getHours() * 60 + now.getMinutes();
            
            const [startH, startM] = startTime.split(':').map(Number);
            const [endH, endM] = endTime.split(':').map(Number);
            const startMinutes = startH * 60 + startM;
            const endMinutes = endH * 60 + endM;

            let isDentroDeHorario = false;
            if (startMinutes <= endMinutes) {
                isDentroDeHorario = currentMinutes >= startMinutes && currentMinutes <= endMinutes;
            } else {
                isDentroDeHorario = currentMinutes >= startMinutes || currentMinutes <= endMinutes;
            }

            if (!isDentroDeHorario) {
                logToTerminal(`⏳ Fuera de horario operativo (${startTime} - ${endTime}). Análisis pausado...`, 'warn');
                rescheduled = true;
                scheduleNext(60000);
                return;
            }
        }

        // 3. Resolución de activo objetivo (Modo autónomo/smart: visor UI estrictamente solo lectura)
        const executionModeAtCycle = getExecutionMode();
        const isServerManagedMode = (executionModeAtCycle === 'auto' || executionModeAtCycle === 'smart');
        const openPos = getOpenPosition();
        const hasPosition = !!openPos;
        let targetSymbol = currentSymbol;
        let entryPrice = 0;

        if (openPos) {
            if (!isAssetMarketOpen(openPos.symbol)) {
                logToTerminal(`⏸️ [SWING EN ESPERA] Posición activa en ${openPos.symbol} (2 a 10 días) protegida en espera: su mercado está cerrado. Sin cierres falsos hasta la reapertura.`, 'info');
                rescheduled = true;
                scheduleNext(60000);
                return;
            }
            targetSymbol = openPos.symbol;
            entryPrice = openPos.entryPrice || 0;
            if (openPos.symbol !== currentSymbol) {
                logToTerminal(`ℹ️ Posición activa en ${openPos.symbol}. Priorizando análisis para salida en cartera en lugar de ${currentSymbol}.`, 'info');
            }
        } else if (!isServerManagedMode && isSmartMode() && window.currentInjectedMacro) {
            const directive = window.currentInjectedMacro;
            if (!tradingGuards.isEligibleMacroDirective(directive)) {
                window.currentInjectedMacro = null;
                const macroBox = document.getElementById('macroContext');
                if (macroBox && lastAutoInjectedText && macroBox.value === lastAutoInjectedText) macroBox.value = '';
                lastAutoInjectedText = null;
            }
            const matchedSymbol = window.currentInjectedMacro && symbolSelect
                ? tradingGuards.matchDirectiveSymbol(directive.asset, Array.from(symbolSelect.options, option => option.value))
                : null;
            if (matchedSymbol) {
                if (!isAssetMarketOpen(matchedSymbol)) {
                    logToTerminal(`⏸️ [MODO INTELIGENTE] Directiva para ${matchedSymbol} en espera: mercado cerrado por horario/fin de semana. Manteniendo operativa en ${targetSymbol}.`, 'warn');
                } else {
                    const candCur = getCurrency(matchedSymbol);
                    const candVault = getVaultBalance(candCur);
                    const hasCapital = (portfolio.balances[candCur] >= 5 || candVault >= 5);
                    if (hasCapital) {
                        if (targetSymbol !== matchedSymbol) {
                            logToTerminal(`⚡ [MODO INTELIGENTE] Auto-ruteando a ${matchedSymbol} por directiva del Monitor del Mercado.`, 'action');
                            targetSymbol = matchedSymbol;
                            currentSymbol = matchedSymbol;
                            if (symbolSelect) {
                                symbolSelect.value = matchedSymbol;
                                symbolSelect.dispatchEvent(new Event('change'));
                            }
                            if (directive.text) {
                                const macroBox = document.getElementById('macroContext');
                                if (macroBox) {
                                    macroBox.value = directive.text;
                                    lastAutoInjectedText = directive.text;
                                }
                            }
                        }
                    } else {
                        logToTerminal(`⚠️ [MODO INTELIGENTE] Oportunidad en ${matchedSymbol} pausada: saldo en ${candCur} ($${portfolio.balances[candCur].toFixed(2)}) y Bóveda ($${candVault.toFixed(2)} ${candCur}) menor al mínimo de $5.`, 'warn');
                    }
                }
            }
        }

        // Si no hay posición abierta y el activo actual está con el mercado cerrado, conmutar solo en copiloto UI
        if (!isServerManagedMode && !hasPosition && (getStrategyMode() === 'auto' || isSmartMode()) && !isAssetMarketOpen(targetSymbol)) {
            const closedSymbol = targetSymbol;
            targetSymbol = 'BTC/USDT';
            currentSymbol = 'BTC/USDT';
            if (symbolSelect) {
                symbolSelect.value = 'BTC/USDT';
                symbolSelect.dispatchEvent(new Event('change'));
            }
            logToTerminal(`🌙 [AUTO-ORQUESTADOR] Mercado de ${closedSymbol} cerrado por horario. Conmutando automáticamente a BTC/USDT para operar Cripto 24/7.`, 'action');
        }

        const strategyMode = hasPosition && openPos.strategyMode
            ? openPos.strategyMode
            : getStrategyMode();

        const tfSelect = document.getElementById('timeframeSelect');
        if (!isServerManagedMode && strategyMode === 'auto' && tfSelect) {
            const argDate = new Date(Date.now() - 3 * 3600 * 1000);
            const day = argDate.getUTCDay();
            const totalMin = argDate.getUTCHours() * 60 + argDate.getUTCMinutes();
            let autoTf = tfSelect.value;
            if (day >= 1 && day <= 5 && totalMin >= 625 && totalMin <= 750) {
                autoTf = '15m';
            } else if (day >= 1 && day <= 5 && totalMin >= 751 && totalMin <= 1020) {
                autoTf = '1h';
            } else if (tfSelect.value === '15m' || tfSelect.value === '1h') {
                autoTf = '5m';
            }
            if (tfSelect.value !== autoTf) {
                tfSelect.value = autoTf;
                updateChartHeaderTitles();
                fetchMarketData();
                logToTerminal(`🔄 [AUTO-ORQUESTADOR] Temporalidad sincronizada automáticamente a ${autoTf} según horario operativo.`, 'action');
            }
        }

        const tf = tfSelect?.value || '1m';
        const tpSlVal = document.getElementById('tpSlSelect')?.value || "2.1|-0.6";
        const [tpStr, slStr] = tpSlVal.split('|');
        const tpVal = Math.abs(parseFloat(tpStr)) || 1.0;
        const slVal = Math.abs(parseFloat(slStr)) || 0.5;
        const feeRate = getBrokerFeeRate();
        const spreadRate = getEstimatedSpreadRate();
        const minProfitPct = hasPosition && Number.isFinite(openPos.minProfitPct)
            ? openPos.minProfitPct
            : getMinimumNetProfitPct();
        if (!Number.isFinite(feeRate)) {
            logToTerminal('⚠️ [FILTRO VIABILIDAD] La comisión configurada no es válida (rango 0–10%).', 'warn');
            return;
        }
        if (!Number.isFinite(minProfitPct) || minProfitPct < 0 || minProfitPct > 5) {
            logToTerminal('⚠️ [FILTRO VIABILIDAD] El beneficio neto mínimo no es válido (rango 0–5%).', 'warn');
            return;
        }
        const netTp = tradingGuards.netReturnAfterCosts(tpVal, feeRate, spreadRate);

        if (strategyMode === 'mean_reversion_atr' && !tradingGuards.isAllowedAtrTimeframe(tf)) {
            logToTerminal(`⚠️ [FILTRO ATR] La estrategia cuantitativa ATR solo admite temporalidades de 15m o 1h (actual: ${tf}). Cambia la temporalidad o la estrategia.`, 'warn');
            return;
        }

        if (
            !Number.isFinite(spreadRate)
            || (strategyMode === 'manual' && !Number.isFinite(netTp))
            || (!hasPosition && strategyMode === 'manual' && netTp < minProfitPct)
        ) {

            logToTerminal(`⚠️ [FILTRO VIABILIDAD] Ganancia neta estimada del TP (+${Number.isFinite(netTp) ? netTp.toFixed(3) : 'inválida'}%) no alcanza el margen neto mínimo (${minProfitPct.toFixed(3)}%). Revisa comisión, spread y TP.`, 'warn');
            return;
        }

        const riskVal = document.getElementById('riskSelect')?.value || "0.25";
        const macroContextText = document.getElementById('macroContext')?.value || '';
        
        // Auto-detección de Apagado Programado en el prompt del trader
        if (macroContextText && /deten(er|te|te\s+el\s+agente)?(\s+al|\s+tras|\s+despu[eé]s\s+de)\s+cerrar|stop\s+after\s+close/i.test(macroContextText)) {
            if (!isStopAfterCloseArmed && hasPosition) {
                isStopAfterCloseArmed = true;
                localStorage.setItem('ai_stop_after_close', 'true');
                logToTerminal(`🛑 [APAGADO PROGRAMADO] Detectada directiva en el prompt: El agente se detendrá automáticamente al cerrar ${targetSymbol}.`, 'action');
                updateCapitalDisplay();
            }
        }

        const sentScore = window.currentSentimentScore || 0;
        const modelParam = brain.model ? `&model=${encodeURIComponent(brain.model)}` : '';
        const url = `${API_BASE_URL}/api/market/analysis?symbol=${encodeURIComponent(targetSymbol)}&timeframe=${tf}&engine=${engine}${modelParam}&strategy=${strategyMode}&tp=${tpVal}&sl=${slVal}&risk=${riskVal}&sentiment=${sentScore}&macro=${encodeURIComponent(macroContextText)}&fee=${feeRate}&spread=${spreadRate}&min_profit_pct=${minProfitPct}&has_position=${hasPosition}&entry_price=${entryPrice}`;
        
        // Timeout que cubre cuerpo y conexión (Bloque 4 item 5)
        const timeoutMs = (engine === 'deepseek' || engine === 'ollama') ? 165000 : 45000;
        controller = new AbortController();
        activeAnalysisController = controller;
        analysisAbortReason = null;
        timeoutId = setTimeout(() => {
            analysisAbortReason = 'timeout';
            controller.abort();
        }, timeoutMs);

        logToTerminal(`Consultando Orquestador (${targetSymbol}) vía ${engine.toUpperCase()}...`, 'info');
        const response = await fetch(url, { headers: apiAuthHeaders(), signal: controller.signal });

        // R6: Validación HTTP antes de leer datos
        if (!response.ok) {
            const errObj = await response.json().catch(() => ({}));
            throw new Error(errObj.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();
        clearTimeout(timeoutId);
        timeoutId = null;

        if (!isAgentActive || controller.signal.aborted) return;
        if (typeof data?.signal !== 'string') {
            throw new Error('Respuesta inválida: falta propiedad signal de tipo string.');
        }

        // R7: Deduplicación por vela
        const signalCandleTs = Number(data.signal_candle_ts) || 0;
        if (signalCandleTs > 0 && lastHandledCandle.symbol === targetSymbol && lastHandledCandle.candleTs === signalCandleTs) {
            logToTerminal(`⏳ Señal de ${data.signal} ignorada: vela ${signalCandleTs} ya fue gestionada.`, 'info');
            return;
        }

        const feeStr = data.fee_info
            ? ` | Comisión RT: ${data.fee_info.round_trip_fee}% | Spread est. RT: ${data.fee_info.round_trip_spread}% | TP neto est.: +${data.fee_info.net_tp}% | Mínimo neto: ${data.fee_info.min_profit_pct ?? minProfitPct}%`
            : '';
        const strategyMetrics = data.strategy_metrics;
        let strategyStr = '';
        if (strategyMetrics?.mode === 'kula_balam_cava_ruiz') {
            strategyStr = ` | Cava & Ruiz | Tríada: ${strategyMetrics.triad_ok ? 'OK' : 'NO'} | Fibo: ${strategyMetrics.fibo_level ?? 'N/A'} | Gatillo 5M: ${strategyMetrics.trigger_type ?? 'N/A'} | SL Inval.+2 Ticks: -${strategyMetrics.sl_gross_pct ?? 'N/A'}% | TP1: +${strategyMetrics.tp_gross_pct ?? 'N/A'}%`;
        } else if (strategyMetrics?.mode === 'tres_velas_wyckoff_bulkowski') {
            strategyStr = ` | Tres Velas & Wyckoff | Patrón: ${strategyMetrics.candlestick_pattern ?? 'N/A'} | Fiabilidad: ${strategyMetrics.pattern_reliability ?? 'N/A'}% | RVOL: ${strategyMetrics.relative_volume ?? 'N/A'}`;
        } else if (strategyMetrics?.mode === 'mean_reversion_atr') {
            strategyStr = ` | Z: ${strategyMetrics.z_score ?? 'N/A'} | ATR14: ${strategyMetrics.atr_14 ?? 'N/A'} | RVOL: ${strategyMetrics.relative_volume ?? 'N/A'} | Mecha: ${strategyMetrics.lower_wick_ratio ?? 'N/A'} | TP/SL bruto: +${strategyMetrics.tp_gross_pct ?? 'N/A'}%/-${strategyMetrics.sl_gross_pct ?? 'N/A'}%`;
        } else if (strategyMetrics?.mode === 'hyenuk_chu_multibagger') {
            strategyStr = ` | Swing Hyenuk Chu (1h) | EMA200: ${strategyMetrics.ema_200 ?? 'N/A'} | RVOL: ${strategyMetrics.relative_volume ?? 'N/A'} | TP1 Peluqueo 50%: +${strategyMetrics.tp_gross_pct ?? 3.5}% / SL: -${strategyMetrics.sl_gross_pct ?? 1.75}% (Runner 2-10 días)`;
        } else if (strategyMetrics?.mode === 'trailing_trend_runner') {
            strategyStr = ` | Trailing sin Techo (Idea Raúl) | EMA200: ${strategyMetrics.ema_200 ?? 'N/A'} | RVOL: ${strategyMetrics.relative_volume ?? 'N/A'} | SL inicial: -${strategyMetrics.sl_gross_pct ?? 1.5}% | Trailing dinámico activo tras breakeven (sin techo TP)`;
        } else if (strategyMetrics?.mode === 'trailing_short_runner') {
            strategyStr = ` | Trailing en Corto (Shorting Raúl) | EMA200: ${strategyMetrics.ema_200 ?? 'N/A'} | RVOL: ${strategyMetrics.relative_volume ?? 'N/A'} | SL inicial: +${strategyMetrics.sl_gross_pct ?? 1.5}% | Trailing dinámico descendente activo tras breakeven (sin suelo TP)`;
        } else if (strategyMetrics?.mode === 'nasdaq_araujo_vwap') {
            strategyStr = ` | Apertura Araujo (M15) | VWAP: ${strategyMetrics.vwap ?? 'N/A'} | Máx Londres: ${strategyMetrics.london_high ?? 'N/A'} | TP/SL técnico: +${strategyMetrics.tp_gross_pct ?? 'N/A'}%/-${strategyMetrics.sl_gross_pct ?? 'N/A'}%`;
        }
        const rsiDisp = data.indicators?.rsi !== undefined && data.indicators?.rsi !== null ? data.indicators.rsi : '-';
        const smaDisp = data.indicators?.sma_20 !== undefined && data.indicators?.sma_20 !== null ? data.indicators.sma_20 : '-';
        const logType = data.signal === 'COMPRAR' ? 'action' : (data.signal === 'VENDER' ? 'error' : 'info');
        logToTerminal(`[${data.signal}] RSI: ${rsiDisp} | SMA20: ${smaDisp}${feeStr}${strategyStr}`, 'warn');
        logToTerminal(`Razonamiento: ${data.reason}`, logType);

        const baseCoin = targetSymbol.split('/')[0];

        const isBuyable = data.signal === 'COMPRAR' && !hasPosition;
        const isSellable = data.signal === 'VENDER' && hasPosition;

        // R8: Comprobar cooldown post-cierre al intentar comprar
        if (isBuyable) {
            const savedCooldown = Number(localStorage.getItem('ai_cooldown_v1')) || 0;
            if (Date.now() < savedCooldown) {
                const minLeft = ((savedCooldown - Date.now()) / 60000).toFixed(1);
                logToTerminal(`⏳ [COOLDOWN ACTIVO] Nueva compra bloqueada. Restan ${minLeft} min tras el último cierre.`, 'warn');
                if (signalCandleTs > 0) lastHandledCandle = { symbol: targetSymbol, candleTs: signalCandleTs };
                return;
            }
        }

        if (data.signal === 'COMPRAR' && hasPosition) {
            logToTerminal(`ℹ️ Ya tienes una posición abierta en ${openPos ? openPos.baseCoin : baseCoin}. Re-compra bloqueada.`, 'warn');
        }

        if (isBuyable || isSellable) {
            const signalPrice = Number(data.indicators?.current_price);
            if (!Number.isFinite(signalPrice) || signalPrice <= 0) {
                logToTerminal(`⚠️ [SEGURIDAD] Orden abortada: el análisis no devolvió un precio de referencia válido para ${targetSymbol}.`, 'error');
                return;
            }
            const execPrice = await fetchFreshExecutionQuote(targetSymbol, controller.signal);
            if (!isAgentActive || controller.signal.aborted) return;
            const withinSlippage = tradingGuards.isWithinSlippage(signalPrice, execPrice, 1);
            if (isBuyable && !withinSlippage) {
                logToTerminal(`🛑 [SLIPPAGE] Compra abortada: el precio varió más de 1% desde el análisis (${signalPrice} → ${execPrice}). Espera una señal nueva.`, 'error');
                if (signalCandleTs > 0) lastHandledCandle = { symbol: targetSymbol, candleTs: signalCandleTs };
                return;
            }
            if (isSellable && !withinSlippage) {
                logToTerminal(`⚠️ [SLIPPAGE] La salida se ejecutará al precio fresco actual pese a una variación superior a 1% (${signalPrice} → ${execPrice}).`, 'warn');
            }

            const executionMode = getExecutionMode();
            if (executionMode === 'auto' || executionMode === 'smart') {
                if (signalCandleTs > 0) lastHandledCandle = { symbol: targetSymbol, candleTs: signalCandleTs };
                logToTerminal(`📡 [VISOR SOLO LECTURA · ${targetSymbol}] Señal ${data.signal} observada en UI; la ejecución autónoma al cierre de vela pertenece al Daemon del servidor.`, 'info');
            } else {
                stopAgent('copilot_awaiting', { copilotPause: true });
                showCopilotModal(
                    data.signal,
                    targetSymbol,
                    data.reason,
                    baseCoin,
                    execPrice,
                    signalCandleTs,
                    signalPrice,
                    { strategyMode: data.strategy || strategyMode, strategyMetrics: data.strategy_metrics || null }
                );
            }
        }
    } catch (err) {
        if (err.name === 'AbortError') {
            if (analysisAbortReason === 'stopped' || analysisAbortReason === 'circuit_breaker') {
                logToTerminal('⏹️ Análisis cancelado; no se procesará ninguna señal tardía.', 'info');
            } else if (analysisAbortReason === 'watchdog') {
                logToTerminal('⏳ Análisis cancelado por exceder el tiempo máximo del ciclo.', 'warn');
            } else {
                logToTerminal(`⏳ Timeout de análisis agotado en motor ${engine.toUpperCase()}. El servidor tardó demasiado.`, 'warn');
            }
        } else {
            logToTerminal('Fallo en análisis: ' + err.message, 'error');
        }
    } finally {
        if (timeoutId) clearTimeout(timeoutId);
        if (activeAnalysisController && activeAnalysisController === controller) {
            activeAnalysisController = null;
            analysisAbortReason = null;
        }
        cycleInFlight = false;

        // Reprogramar deterministamente si no se reprogramó expresamente arriba
        if (isAgentActive && !rescheduled) {
            const tf = document.getElementById('timeframeSelect')?.value || '1m';
            let delayMs = 60000;
            if (tf === '5m') delayMs = 300000;
            if (tf === '15m') delayMs = 900000;
            if (tf === '1h') delayMs = 3600000;
            if (engine === 'local') delayMs = 15000;


            scheduleNext(delayMs);
        }
    }
};

// Ciclo de Gráfico en Vivo (Cada 2 segundos) aislado exclusivamente para renderizado visual (Bloque 2)
let chartInFlight = false;
let lastChartErrorLogTs = 0;
setInterval(async () => {
    if (chartInFlight) return;
    chartInFlight = true;
    const reqSymbol = currentSymbol;
    try {
        const tfVal = document.getElementById('timeframeSelect')?.value || '5m';
        const response = await fetch(`${API_BASE_URL}/api/market/history?symbol=${encodeURIComponent(reqSymbol)}&timeframe=${tfVal}&limit=300`, {
            headers: apiAuthHeaders()
        });
        if (!response.ok) {
            const now = Date.now();
            if (now - lastChartErrorLogTs > 30000) {
                logToTerminal(`⚠️ [GRÁFICO] Error actualizando velas de ${reqSymbol}: HTTP ${response.status}`, 'warn');
                lastChartErrorLogTs = now;
            }
            return;
        }
        const data = await response.json();
        if (reqSymbol !== currentSymbol) return; // Descartar respuesta tardía si el usuario cambió de símbolo
        
        if (data && data.length > 0) {
            const latest_candle = data[data.length - 1];
            try {
                candleSeries.update(latest_candle);
                if (typeof window.updateCandlePatternIndicator === 'function') {
                    const arr = window.lastRawMarketData || [];
                    const prevC = arr.length > 1 ? arr[arr.length - 2] : null;
                    const prev2C = arr.length > 2 ? arr[arr.length - 3] : null;
                    window.updateCandlePatternIndicator(latest_candle, prevC, prev2C);
                }
                
                if (latest_candle.sma_20 !== undefined) {
                    smaSeries.update({ time: latest_candle.time, value: latest_candle.sma_20 });
                }
                if (latest_candle.vwap !== undefined) {
                    vwapSeries.update({ time: latest_candle.time, value: latest_candle.vwap });
                }
                if (latest_candle.vwap_upper !== undefined) {
                    vwapUpperSeries.update({ time: latest_candle.time, value: latest_candle.vwap_upper });
                }
                if (latest_candle.vwap_lower !== undefined) {
                    vwapLowerSeries.update({ time: latest_candle.time, value: latest_candle.vwap_lower });
                }
            } catch (renderMismatchErr) {
                // Si Lightweight Charts detecta un salto de temporalidad o vela más antigua, recargar limpio el dataset
                fetchMarketData();
                return;
            }
            
            const currentPriceElement = document.getElementById('currentPrice');
            currentPrice = latest_candle.close;
            currentPriceSymbol = reqSymbol;
            currentPriceTs = Date.now();
            currentPriceElement.innerText = `$${currentPrice.toLocaleString()}`;
            updateCapitalDisplay();
        }
    } catch (err) {
        const now = Date.now();
        if (now - lastChartErrorLogTs > 30000) {
            const isConnRefused = err.message && err.message.includes('Failed to fetch');
            const msg = isConnRefused
                ? `Backend Kula Balam (:18767) desconectado o no responde. Verifica que el servidor Python esté iniciado.`
                : err.message;
            logToTerminal(`⚠️ [GRÁFICO] Fallo en renderizado de velas para ${reqSymbol}: ${msg}`, 'warn');
            lastChartErrorLogTs = now;
        }
    } finally {
        chartInFlight = false;
    }
}, 2000);

// Agente Sentimiento (Cada 60 segundos)
async function updateSentiment() {
    const sentimentToggle = document.getElementById('sentimentToggle');
    if (sentimentToggle && !sentimentToggle.checked) {
        window.currentSentimentScore = 0;
        const badge = document.getElementById('sentimentScoreBadge');
        const container = document.getElementById('sentimentNewsContainer');
        if (badge) {
            badge.innerText = 'OFF (0)';
            badge.className = 'text-xs bg-gray-900 text-gray-400 px-2 py-1 rounded font-bold';
        }
        if (container) container.innerHTML = '<p class="text-xs text-gray-500">Consultas de sentimiento desactivadas.</p>';
        return;
    }

    try {
        const source = document.getElementById('newsSourceSelect')?.value || 'coindesk';
        const response = await fetch(`${API_BASE_URL}/api/market/sentiment?symbol=${encodeURIComponent(currentSymbol)}&source=${source}`, {
            headers: apiAuthHeaders()
        });
        if (!response.ok) throw new Error(`HTTP ${response.status} consultando sentimiento.`);
        const data = await response.json();
        if (data && !data.error) {
            window.currentSentimentScore = data.score;
            const badge = document.getElementById('sentimentScoreBadge');
            const container = document.getElementById('sentimentNewsContainer');
            
            badge.innerText = `${data.score} (${data.estado})`;
            
            const needle = document.getElementById('sentimentNeedle');
            if (needle) {
                const percent = ((data.score + 1) / 2) * 100;
                needle.style.left = `${Math.max(0, Math.min(100, percent))}%`;
            }
            
            if (data.estado === 'BULLISH') {
                badge.className = 'text-xs bg-green-900 text-green-400 px-2 py-1 rounded font-bold';
            } else if (data.estado === 'BEARISH') {
                badge.className = 'text-xs bg-red-900 text-red-400 px-2 py-1 rounded font-bold';
            } else {
                badge.className = 'text-xs bg-gray-900 text-gray-400 px-2 py-1 rounded font-bold';
            }
            
            container.innerHTML = '';
            data.noticias.forEach(news => {
                let colorClass = 'border-gray-500';
                if (news.score > 0) colorClass = 'border-green-500';
                if (news.score < 0) colorClass = 'border-red-500';
                
                const div = document.createElement('div');
                div.className = `bg-gray-900 p-2 rounded border-l-2 ${colorClass}`;
                div.innerHTML = `
                    <p class="text-[10px] text-gray-400 flex justify-between">
                        <span>📰 ${escapeHtml(data.fuente || 'Noticias')}</span>
                        <span>Score: ${Number(news.score) || 0}</span>
                    </p>
                    <p class="text-xs text-gray-200 mt-1">${escapeHtml(news.title)}</p>
                `;
                container.appendChild(div);
            });
        }
    } catch (err) {
        console.error("Fallo el Agente de Sentimiento", err);
    }
}
updateSentiment();
setInterval(updateSentiment, 60000);

const newsSourceSelect = document.getElementById('newsSourceSelect');
document.getElementById('sentimentToggle')?.addEventListener('change', (event) => {
    if (!event.target.checked) {
        window.currentSentimentScore = 0;
        logToTerminal('📰 Agente de Sentimiento desactivado; no se consultarán noticias y se enviará puntaje cero.', 'info');
    } else {
        logToTerminal('📰 Agente de Sentimiento activado.', 'info');
    }
    updateSentiment();
});

if (newsSourceSelect) {
    newsSourceSelect.addEventListener('change', () => {
        logToTerminal(`Cambiando fuente de sentimiento a ${newsSourceSelect.value}...`, 'info');
        updateSentiment();
    });
}

// --- PUENTE CON MONITOR DEL MERCADO Y AGENTE DE INVERSIONES ---
let lastInjectedTs = null;
let lastAutoInjectedText = null;
let lastMacroPollErrorTs = 0;
window.currentInjectedMacro = null;

async function checkInjectedMacro() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/macro/current_injected`, {
            headers: apiAuthHeaders()
        });
        if (!res.ok) throw new Error(`HTTP ${res.status} consultando la directiva macro.`);
        const data = await res.json();
        if (data && data.text) {
            if (data.timestamp && data.timestamp !== lastInjectedTs) {
                lastInjectedTs = data.timestamp;
                if (typeof window.syncMarketRegimeFromData === 'function') {
                    window.syncMarketRegimeFromData(data);
                }
                const eligible = tradingGuards.isEligibleMacroDirective(data);
                window.currentInjectedMacro = eligible ? data : null;
                const macroInput = document.getElementById('macroContext');
                if (!eligible) {
                    // Directiva fuera de ventana estática: no bloquear ni borrar contexto manual; el arbitraje informativo evalúa on-demand
                    console.debug(`[DIRECTIVA MACRO] Antigüedad >24h o no elegible estáticamente; Kula evalúa noticias on-demand.`);
                    updateMacroRadar();
                    return;
                }
            
            // 1. Bitácora en el terminal
            const sourceLabel = data.source || 'Monitor del Mercado';
            logToTerminal(`🌐 [${sourceLabel.toUpperCase()}] Directiva recibida para ${data.asset} (${Number(data.confidence)}% conf).`, 'action');
            logToTerminal(`🧠 [CEREBRO DEL BOT] Tesis: "${String(data.text || '').substring(0, 90)}..."`, 'info');
            logToTerminal(`🎯 [PREPARADO] Directiva válida; el Modo Inteligente autoriza el auto-ruteo, no la compra.`, 'warn');
            
            // 2. Si estamos en Modo Inteligente y no hay posición activa, aplicar y auto-rutear automáticamente
            if (isSmartMode() && !hasOpenPosition()) {
                const matchedSymbol = symbolSelect
                    ? tradingGuards.matchDirectiveSymbol(data.asset, Array.from(symbolSelect.options, option => option.value))
                    : null;

                if (matchedSymbol && !isAssetMarketOpen(matchedSymbol)) {
                    logToTerminal(`⏸️ [MODO INTELIGENTE] Directiva de ${matchedSymbol} registrada en buzón, pero su mercado está CERRADO por horario/fin de semana. Manteniendo operativa activa en ${symbolSelect ? symbolSelect.value : currentSymbol}.`, 'warn');
                } else {
                    if (macroInput) {
                        macroInput.value = data.text;
                        lastAutoInjectedText = data.text;
                        macroInput.classList.add('border-purple-500', 'bg-purple-950/30');
                        setTimeout(() => macroInput.classList.remove('border-purple-500', 'bg-purple-950/30'), 3000);
                    }
                    logToTerminal(`⚡ [MODO INTELIGENTE] Contexto Macro actualizado automáticamente con tesis de ${data.asset}.`, 'action');

                    // Auto-ruteo inmediato de activo
                    if (matchedSymbol && symbolSelect.value !== matchedSymbol) {
                        const candCur = getCurrency(matchedSymbol);
                        const candVault = getVaultBalance(candCur);
                        const hasCapital = (portfolio.balances[candCur] >= 5 || candVault >= 5);
                        if (hasCapital) {
                            symbolSelect.value = matchedSymbol;
                            symbolSelect.dispatchEvent(new Event('change'));
                            logToTerminal(`⚡ [MODO INTELIGENTE] Auto-ruteando a ${matchedSymbol} de forma inmediata.`, 'action');
                        } else {
                            logToTerminal(`⚠️ [MODO INTELIGENTE] Oportunidad en ${matchedSymbol} pausada: saldo en ${candCur} ($${portfolio.balances[candCur].toFixed(2)}) y Bóveda ($${candVault.toFixed(2)} ${candCur}) menor al mínimo de $5.`, 'warn');
                        }
                    }

                    // Disparo inmediato de análisis cuantitativo con Qwen
                    if (isAgentActive && !cycleInFlight) {
                        logToTerminal(`⚡ [MODO INTELIGENTE] Disparando análisis cuantitativo inmediato para ${data.asset}...`, 'info');
                        if (simulateInterval) clearTimeout(simulateInterval);
                        simulateInterval = setTimeout(ejecutarAnalisis, 600);
                    }
                }
            }
            
            // 3. Refrescar radar para reflejar la tarjeta de inmediato
            updateMacroRadar();
            } else if (!window.hasInitializedRegimeCard && typeof window.syncMarketRegimeFromData === 'function') {
                window.hasInitializedRegimeCard = true;
                window.syncMarketRegimeFromData(data);
            }
        }
    } catch (err) {
        const now = Date.now();
        if (now - lastMacroPollErrorTs > 30000) {
            const isConnRefused = err.message && err.message.includes('Failed to fetch');
            const msg = isConnRefused
                ? `Backend Kula Balam (:18767) desconectado o no responde.`
                : err.message;
            logToTerminal(`⚠️ Error consultando directiva macro: ${msg}`, 'warn');
            lastMacroPollErrorTs = now;
        }
    }
}
setInterval(checkInjectedMacro, 3000); // Polling cada 3 segundos

window.applyMacroContext = function(asset, text) {
    const macroInput = document.getElementById('macroContext');
    if (macroInput) {
        macroInput.value = text || '';
        macroInput.classList.add('border-green-500', 'bg-green-950/40');
        setTimeout(() => macroInput.classList.remove('border-green-500', 'bg-green-950/40'), 2500);
    }
    
    const openPos = getOpenPosition();
    if (asset && !openPos) {
        const cleanSym = String(asset).trim();
        let matchedSymbol = null;
        if (symbolSelect) {
            for (const opt of symbolSelect.options) {
                if (opt.value === cleanSym || opt.value.split('/')[0] === cleanSym || cleanSym.includes(opt.value)) {
                    matchedSymbol = opt.value;
                    break;
                }
            }
        }
        if (matchedSymbol && symbolSelect.value !== matchedSymbol) {
            symbolSelect.value = matchedSymbol;
            symbolSelect.dispatchEvent(new Event('change'));
            logToTerminal(`📥 [CONTEXTO MACRO] Tesis aplicada y gráfico cambiado a ${matchedSymbol}.`, 'action');
        } else {
            logToTerminal(`📥 [CONTEXTO MACRO] Tesis aplicada al Cuadro de Contexto Macro.`, 'action');
        }
    } else if (openPos) {
        logToTerminal(`📥 [CONTEXTO MACRO] Tesis aplicada. (El gráfico se mantiene en ${openPos.symbol} por posición abierta).`, 'info');
    }
};

window.copyMacroText = function(text, btnElement) {
    const cleanText = text || '';
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(cleanText).then(() => {
            if (btnElement) {
                const prev = btnElement.innerText;
                btnElement.innerText = '✅ Copiado';
                setTimeout(() => { btnElement.innerText = prev; }, 1500);
            }
            logToTerminal(`📋 Tesis copiada al portapapeles.`, 'info');
        }).catch(() => {
            fallbackCopy(cleanText, btnElement);
        });
    } else {
        fallbackCopy(cleanText, btnElement);
    }
};

function fallbackCopy(text, btnElement) {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        if (btnElement) {
            const prev = btnElement.innerText;
            btnElement.innerText = '✅ Copiado';
            setTimeout(() => { btnElement.innerText = prev; }, 1500);
        }
        logToTerminal(`📋 Tesis copiada al portapapeles.`, 'info');
    } catch (_) {}
    document.body.removeChild(ta);
}

// --- Radar Macro de Oportunidades ---
async function updateMacroRadar() {
    const toggle = document.getElementById('investmentToggle');
    const container = document.getElementById('macroOpportunitiesContainer');
    if (!container) return;

    const isEnabled = toggle && toggle.checked;
    if (!isEnabled) {
        container.innerHTML = '<p class="text-xs text-gray-500 text-center py-2">Radar Desactivado.</p>';
        return;
    }

    const brain = parseBrainSelection(document.getElementById('engineSelect')?.value || 'local');
    const engine = brain.engine === 'gemini' ? 'ai' : brain.engine;
    const modelParam = brain.model ? `&model=${encodeURIComponent(brain.model)}` : '';
    const source = document.getElementById('investmentSourceSelect')?.value || 'monitor';
    container.innerHTML = `<p class="text-xs text-yellow-500 text-center py-2 animate-pulse">Consultando radar (${source})...</p>`;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/macro/radar?engine=${engine}&source=${source}${modelParam}`, {
            headers: apiAuthHeaders()
        });
        const data = await response.json();
        
        container.innerHTML = '';
        if (Array.isArray(data) && data.length > 0) {
            data.forEach((item) => {
                const isOp = item.type === 'Oportunidad';
                const colorClass = isOp ? 'text-green-400 bg-green-400/10' : 'text-red-400 bg-red-400/10';
                const typeColor = isOp ? 'text-green-400' : 'text-red-400';
                const itemSource = item.source || (item.injected ? 'monitor' : 'native');
                const sourceBadge = (itemSource === 'monitor')
                    ? '<span class="text-[9px] bg-cyan-900/60 text-cyan-300 border border-cyan-600/50 px-1.5 py-0.5 rounded font-mono">🖥️ Monitor</span>'
                    : '<span class="text-[9px] bg-yellow-900/60 text-yellow-300 border border-yellow-600/50 px-1.5 py-0.5 rounded font-mono">🌐 Nativo</span>';
                
                const safeAsset = escapeHtml(item.asset || 'N/A');
                const safeReason = escapeHtml(item.reason || '');
                const rawReason = String(item.reason || '');
                const rawAsset = String(item.asset || '');
                
                const div = document.createElement('div');
                div.className = 'bg-gray-800 p-2.5 rounded border border-gray-600 mb-2 shadow-sm';
                div.innerHTML = `
                    <div class="flex justify-between items-center mb-1">
                        <div class="flex items-center gap-1.5">
                            <span class="text-xs font-bold text-white">${safeAsset}</span>
                            ${sourceBadge}
                        </div>
                        <span class="text-[10px] ${colorClass} font-bold px-1 rounded">${Number(item.confidence) || 0}% Conf.</span>
                    </div>
                    <p class="text-[10px] text-gray-300 leading-tight mb-2"><span class="font-bold ${typeColor}">${escapeHtml(item.type || 'Análisis')}:</span> ${safeReason}</p>
                    <div class="flex items-center justify-between pt-1 border-t border-gray-700/60 text-[10px]">
                        <span class="text-gray-500 text-[9px]">⏳ ${escapeHtml(item.schedule || 'Inmediato')}</span>
                        <div class="flex items-center gap-1.5">
                            <button class="macro-apply-context bg-blue-600 hover:bg-blue-500 text-white px-2 py-0.5 rounded text-[10px] font-semibold transition flex items-center gap-1 shadow cursor-pointer" title="Cargar tesis en Contexto Macro">
                                <span>📥</span> Aplicar a Macro
                            </button>
                            <button class="macro-copy-text bg-gray-700 hover:bg-gray-600 text-gray-200 px-1.5 py-0.5 rounded text-[10px] transition cursor-pointer" title="Copiar tesis">
                                📋 Copiar
                            </button>
                        </div>
                    </div>
                `;
                div.querySelector('.macro-apply-context').addEventListener('click', () => {
                    window.applyMacroContext(rawAsset, rawReason);
                });
                div.querySelector('.macro-copy-text').addEventListener('click', (event) => {
                    window.copyMacroText(rawReason, event.currentTarget);
                });
                container.appendChild(div);
            });
        } else {
            container.innerHTML = `<p class="text-xs text-gray-500 text-center py-2">Sin hallazgos en radar (${source}).</p>`;
        }
    } catch (err) {
        console.error("Fallo el Radar de Oportunidades", err);
        container.innerHTML = '<p class="text-xs text-red-500 text-center py-2">Error de conexión.</p>';
    }
}
updateMacroRadar();
setInterval(updateMacroRadar, 120000); // 2 minutos

// Estado de Radar de Oportunidades
function setInvestmentAgentState(isChecked) {
    const invToggle = document.getElementById('investmentToggle');
    if (invToggle && invToggle.checked !== isChecked) invToggle.checked = isChecked;

    const badge = document.getElementById('radarLiveStatus');
    if (badge) {
        if (isChecked) {
            badge.innerText = "EN VIVO";
            badge.className = "text-[10px] bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded border border-yellow-500/50 transition-colors";
        } else {
            badge.innerText = "OFF";
            badge.className = "text-[10px] bg-gray-500/20 text-gray-400 px-2 py-0.5 rounded border border-gray-500/50 transition-colors";
        }
    }
    logToTerminal(isChecked ? "🔭 Radar de Oportunidades ACTIVADO" : "Radar de Oportunidades DESACTIVADO", "info");
    updateMacroRadar();
}

document.getElementById('investmentToggle')?.addEventListener('change', (e) => {
    setInvestmentAgentState(e.target.checked);
});

document.getElementById('investmentSourceSelect')?.addEventListener('change', () => {
    const src = document.getElementById('investmentSourceSelect')?.value || 'monitor';
    logToTerminal(`Fuente de Radar cambiada a: ${src}`, 'info');
    updateMacroRadar();
});

document.getElementById('clearLogs')?.addEventListener('click', () => {
    terminal.innerHTML = '';
    _terminalUserScrolledUp = false;
    if (typeof window.syncTerminalSideScrollbar === 'function') {
        window.syncTerminalSideScrollbar();
    }
});

// -- Funciones de Trading y Copiloto --

let isTradeHistoryExpanded = false;

window.toggleTradeHistory = function() {
    isTradeHistoryExpanded = !isTradeHistoryExpanded;
    renderTradeHistory();
};

function renderTradeHistory() {
    const tbody = document.getElementById('tradeHistoryBody');
    const toggleBtn = document.getElementById('btnToggleHistory');
    const toggleIcon = document.getElementById('btnToggleHistoryIcon');
    const toggleText = document.getElementById('btnToggleHistoryText');
    const footer = document.getElementById('historyPaginationFooter');
    const countNotice = document.getElementById('historyCountNotice');
    const footerBtn = document.getElementById('btnToggleHistoryFooter');

    if (!tbody) return;
    tbody.innerHTML = '';

    if (!Array.isArray(tradeHistoryLog) || tradeHistoryLog.length === 0) {
        tbody.innerHTML = `<tr id="emptyHistoryRow"><td colspan="8" class="px-4 py-4 text-center text-gray-500 italic">No hay operaciones registradas aún.</td></tr>`;
        if (toggleBtn) toggleBtn.classList.add('hidden');
        if (footer) footer.classList.add('hidden');
        return;
    }

    const totalTrades = tradeHistoryLog.length;
    const limit = 5;

    // Si hay un trade siendo auditado en el gráfico que esté fuera de los 5 primeros, expandir automáticamente
    if (window.currentlyInspectedTradeId && !isTradeHistoryExpanded) {
        const inspectedIdx = tradeHistoryLog.findIndex(t => String(t.id || '').replace(/_(buy|sell)$/, '') === window.currentlyInspectedTradeId);
        if (inspectedIdx >= limit) {
            isTradeHistoryExpanded = true;
        }
    }

    // Control de visibilidad y textos de los botones de despliegue
    if (totalTrades > limit) {
        if (toggleBtn) {
            toggleBtn.classList.remove('hidden');
            if (toggleIcon) toggleIcon.innerText = isTradeHistoryExpanded ? '▲' : '▼';
            if (toggleText) toggleText.innerText = isTradeHistoryExpanded ? 'Mostrar solo 5' : `Ver todas (${totalTrades})`;
            toggleBtn.title = isTradeHistoryExpanded ? 'Plegar para ver solo las 5 más recientes' : `Desplegar las ${totalTrades} operaciones completas`;
        }
        if (footer) {
            footer.classList.remove('hidden');
            if (countNotice) {
                countNotice.innerText = isTradeHistoryExpanded
                    ? `Mostrando las ${totalTrades} operaciones del historial`
                    : `Mostrando las 5 operaciones más recientes de ${totalTrades}`;
            }
            if (footerBtn) {
                footerBtn.innerHTML = isTradeHistoryExpanded
                    ? `▲ Plegar a 5 operaciones`
                    : `▼ Desplegar historial completo (${totalTrades - limit} más)`;
            }
        }
    } else {
        if (toggleBtn) toggleBtn.classList.add('hidden');
        if (footer) footer.classList.add('hidden');
    }

    const tradesToRender = (isTradeHistoryExpanded || totalTrades <= limit)
        ? tradeHistoryLog
        : tradeHistoryLog.slice(0, limit);

    tradesToRender.forEach((trade) => {
        const isBuy = trade.signal === 'COMPRAR';
        const typeBadge = isBuy
            ? `<span class="bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded text-xs font-semibold font-mono">COMPRA</span>`
            : `<span class="bg-rose-500/15 text-rose-400 border border-rose-500/30 px-2 py-0.5 rounded text-xs font-semibold font-mono">VENTA</span>`;

        const cost = Number(trade.costBasis) || (Number(trade.qty || 0) * Number(trade.price || 0)) || 0;
        const costStr = cost > 0 
            ? `$${cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` 
            : `<span class="text-gray-500 font-mono">-</span>`;

        let pnlCell = `<span class="text-gray-500 font-mono">-</span>`;
        if (!isBuy && trade.pnl !== null && trade.pnl !== undefined) {
            const pnlNum = Number(trade.pnl);
            const absPnl = Math.abs(pnlNum);
            const pnlDecimals = absPnl < 1.0 ? 4 : 2;
            if (pnlNum > 0.0001) {
                pnlCell = `<span class="text-emerald-400 font-bold font-mono">+$${pnlNum.toFixed(pnlDecimals)}</span>`;
            } else if (pnlNum < -0.0001) {
                pnlCell = `<span class="text-rose-400 font-bold font-mono">-$${absPnl.toFixed(pnlDecimals)}</span>`;
            } else {
                pnlCell = `<span class="text-gray-400 font-bold font-mono">$0.00</span>`;
            }
        }

        const balNum = Number(trade.balance);
        const balCell = Number.isFinite(balNum)
            ? `<span class="font-mono text-gray-200">$${balNum.toFixed(2)}</span>`
            : `<span class="font-mono text-gray-500">-</span>`;

        const priceNum = Number(trade.price) || 0;
        const priceStr = priceNum < 10.0
            ? `$${priceNum.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`
            : `$${priceNum.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        const displaySymbol = escapeHtml(trade.symbol || (trade.baseCoin ? trade.baseCoin + '/USDT' : 'N/A'));
        const stratStr = trade.strategy || 'trailing_trend_runner';
        const engStr = trade.engine || 'antigravity_operador';
        const formStr = trade.formula || 'Quant Risk ATR';
        const cleanId = (trade.id || '').replace('_sell', '');
        const isCurrentlyAudited = window.currentlyInspectedTradeId && window.currentlyInspectedTradeId === cleanId;
        const isAnyAudited = !!window.currentlyInspectedTradeId;

        const inspectBtnClass = isCurrentlyAudited
            ? 'btn-inspect-trade text-xs bg-amber-500/30 text-amber-300 font-bold ml-1.5 px-2 py-0.5 rounded border border-amber-400 font-mono cursor-pointer shadow-lg ring-1 ring-amber-400/80 animate-pulse'
            : 'btn-inspect-trade text-xs text-amber-400 hover:text-amber-300 ml-1.5 px-1.5 py-0.5 rounded hover:bg-slate-800 border border-amber-500/30 font-mono cursor-pointer transition';

        const inspectBtnText = isCurrentlyAudited ? '✓ Viendo (Destildar)' : '🔍 Ver';
        const inspectBtnTitle = isCurrentlyAudited ? 'Hacer clic para destildar y volver al gráfico en vivo' : 'Auditar recorrido de entrada y salida en el gráfico de velas';

        const modeBadge = `<span class="text-xs text-gray-200" title="Agente: ${escapeHtml(engStr)} | Fórmula: ${escapeHtml(formStr)}">${escapeHtml(trade.mode || 'Auto')}</span> <span class="text-[10px] text-cyan-400 bg-cyan-950/70 border border-cyan-800/60 px-1 py-0.5 rounded font-mono ml-1" title="Estrategia: ${escapeHtml(stratStr)}">${escapeHtml(stratStr)}</span> <button type="button" data-trade-id="${escapeHtml(cleanId)}" onclick="event.stopPropagation(); window.inspectClosedTradeOnMainChart('${escapeHtml(cleanId)}')" class="${inspectBtnClass}" title="${inspectBtnTitle}">${inspectBtnText}</button>`;

        const tr = document.createElement('tr');
        let baseClass = isBuy 
            ? 'border-b border-gray-800 bg-gray-900/30 hover:bg-gray-800/40 transition-colors' 
            : 'border-b border-gray-800 bg-gray-950/50 hover:bg-gray-800/40 transition-colors';
        if (isCurrentlyAudited) {
            baseClass += ' ring-1 ring-amber-500/80 bg-amber-950/40';
        }
        tr.className = baseClass;
        if (isAnyAudited) {
            if (isCurrentlyAudited) {
                tr.style.filter = 'none';
                tr.style.opacity = '1';
            } else {
                tr.style.filter = 'blur(1.5px)';
                tr.style.opacity = '0.35';
                tr.style.transition = 'filter 0.3s ease, opacity 0.3s ease';
            }
        }

        tr.innerHTML = `
            <td class="px-3 py-2.5 whitespace-nowrap font-mono text-xs text-gray-300">${escapeHtml(trade.timeString || '')}</td>
            <td class="px-3 py-2.5 font-bold text-white">${displaySymbol}</td>
            <td class="px-3 py-2.5">${typeBadge}</td>
            <td class="px-3 py-2.5 font-mono text-white text-xs">${priceStr}</td>
            <td class="px-3 py-2.5 font-mono text-cyan-300 font-semibold text-xs">${costStr}</td>
            <td class="px-3 py-2.5 font-mono">${pnlCell}</td>
            <td class="px-3 py-2.5">${balCell}</td>
            <td class="px-3 py-2.5 whitespace-nowrap">${modeBadge}</td>
        `;
        tbody.appendChild(tr);
    });
}

function addTradeToHistory(signal, symbol, baseCoin, price, status, mode, fee = 0, qty = 0, pnl = null, balance = null, costBasis = null) {
    // Normalización defensiva retrocompatible
    if (typeof price === 'string' && (price === 'Ejecutada' || price === 'Rechazada' || price === 'Expirada')) {
        qty = fee || 0;
        fee = mode || 0;
        mode = status;
        status = price;
        price = baseCoin;
        baseCoin = symbol;
        symbol = baseCoin ? (baseCoin.includes('/') ? baseCoin : baseCoin + '/USDT') : currentSymbol;
    }

    const now = new Date();
    const timeString = now.toLocaleTimeString();
    const timestamp = now.toISOString();
    const effectiveSymbol = symbol || (baseCoin ? baseCoin + '/USDT' : currentSymbol);
    const effectiveQty = Number(qty) || 0;
    const effectivePrice = Number(price) || 0;
    const effectiveCost = Number(costBasis) || (effectiveQty > 0 && effectivePrice > 0 ? effectiveQty * effectivePrice : 0);

    tradeHistoryLog.unshift({ 
        timeString, 
        timestamp, 
        signal, 
        symbol: effectiveSymbol,
        baseCoin, 
        price: effectivePrice, 
        qty: Number(effectiveQty.toFixed(6)),
        costBasis: effectiveCost,
        status, 
        mode, 
        fee: Number(Number(fee).toFixed(2)),
        pnl: pnl !== null && pnl !== undefined ? Number(pnl) : null,
        balance: balance !== null && balance !== undefined ? Number(balance) : null,
        sessionId: currentSessionId
    });
    
    localStorage.setItem('ai_trade_history_v2', JSON.stringify(tradeHistoryLog));
    
    // Guardar en backend CSV incluyendo X-API-Token si existe
    const headers = apiAuthHeaders({ 'Content-Type': 'application/json' });

    fetch(`${API_BASE_URL}/api/log_trade`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ 
            timeString, 
            symbol: effectiveSymbol, 
            signal, 
            price: Number(price) || 0, 
            status, 
            mode,
            qty: Number(Number(qty || 0).toFixed(6)),
            fee: Number(Number(fee || 0).toFixed(2)),
            session_id: currentSessionId 
        })
    }).catch(err => console.error('Error guardando en archivo CSV:', err));
    
    renderTradeHistory();
}

function executeTrade(
    signal,
    symbol,
    baseCoin,
    price,
    mode = 'Automático',
    { verifiedQuote = false, strategyMode = 'manual', strategyMetrics = null } = {}
) {
    // Soporte retrocompatible de 4 argumentos
    if (typeof baseCoin === 'number') {
        mode = price || 'Automático';
        price = baseCoin;
        baseCoin = symbol ? symbol.split('/')[0] : 'BTC';
        symbol = symbol ? (symbol.includes('/') ? symbol : symbol + '/USDT') : currentSymbol;
    }

    if (signal !== 'COMPRAR' && signal !== 'VENDER') {
        logToTerminal(`⚠️ Ejecución abortada: señal no reconocida (${signal}).`, 'error');
        return;
    }
    if (isExecutingTrade) {
        logToTerminal('⚠️ Operación en curso. Ignorando solicitud concurrente.', 'warn');
        return;
    }
    if (!Number.isFinite(price) || price <= 0) {
        logToTerminal(`⚠️ Ejecución abortada: precio inválido o no numérico ($${price}).`, 'error');
        return;
    }

    const effectiveSymbol = symbol || currentSymbol;
    const currency = getCurrency(effectiveSymbol);
    if (!Number.isFinite(portfolio.balances[currency])) {
        logToTerminal(`⚠️ Ejecución abortada: balance no numérico en moneda ${currency}.`, 'error');
        return;
    }

    // R10: Validación de consistencia de precio en órdenes de COMPRA
    if (signal === 'COMPRAR') {
        if (currentPriceSymbol === effectiveSymbol && currentPrice > 0) {
            const ratio = price / currentPrice;
            if (ratio < 0.5 || ratio > 2.0) {
                logToTerminal(`🛑 [SEGURIDAD] Compra abortada: discrepancia severa de precio para ${effectiveSymbol} (orden: $${price} vs mercado: $${currentPrice}). Desincronización prevenida.`, 'error');
                return;
            }
        }
    }

    isExecutingTrade = true;
    try {
        const openPos = getOpenPosition();
        const hasPosition = !!openPos;

        if (signal === 'COMPRAR' && hasPosition) {
            logToTerminal(`⚠️ Compra bloqueada: ya existe una posición activa en ${openPos.baseCoin}.`, 'warn');
            return;
        }
        if (signal === 'VENDER' && !hasPosition) {
            logToTerminal(`⚠️ Venta ignorada: no hay posición abierta que cerrar.`, 'warn');
            return;
        }
        const configuredFeeRate = getBrokerFeeRate(effectiveSymbol);
        const feeRate = signal === 'VENDER' && openPos.feeRate !== undefined
            ? openPos.feeRate
            : configuredFeeRate;
        if (!Number.isFinite(feeRate) || feeRate < 0 || feeRate > 10) {
            logToTerminal('⚠️ Ejecución abortada: la comisión guardada en la posición es inválida.', 'error');
            return;
        }
        if (signal === 'COMPRAR') {
            // R4: Bloqueo de compra por Circuit Breaker
            if (isCircuitBreakerActive()) {
                const rState = getRiskState();
                logToTerminal(`🛑 [CIRCUIT BREAKER] Compra abortada en ${effectiveSymbol}. Motivo: ${rState.haltReason || 'Pausado'}`, 'error');
                return;
            }

            // R8: Bloqueo de compra por Cooldown post-cierre
            const savedCooldown = Number(localStorage.getItem('ai_cooldown_v1')) || 0;
            if (Date.now() < savedCooldown) {
                const minLeft = ((savedCooldown - Date.now()) / 60000).toFixed(1);
                logToTerminal(`⏳ [COOLDOWN ACTIVO] Compra abortada en ${effectiveSymbol}. Restan ${minLeft} min tras el último cierre.`, 'warn');
                return;
            }

            const riskFactor = parseFloat(document.getElementById('riskSelect')?.value || "0.25");
            if (!Number.isFinite(riskFactor) || riskFactor <= 0 || riskFactor > 1) {
                logToTerminal('⚠️ Ejecución abortada: nivel de riesgo inválido; usa un valor mayor que 0 y hasta 100%.', 'error');
                return;
            }
            const resolvedStrategyMode = strategyMetrics?.mode || strategyMetrics?.auto_orchestrator?.selected_strategy || strategyMode;
            const tradeStrategyMode = ['kula_balam_cava_ruiz', 'tres_velas_wyckoff_bulkowski', 'mean_reversion_atr', 'nasdaq_araujo_vwap', 'hyenuk_chu_multibagger', 'trailing_trend_runner', 'trailing_short_runner', '01_tendencia_institucional_15m', '02_cazador_rebotes_atr_15m'].includes(resolvedStrategyMode)
                ? resolvedStrategyMode
                : 'manual';
            const spreadRate = getEstimatedSpreadRate();
            if (!Number.isFinite(spreadRate)) {
                logToTerminal('⚠️ Ejecución abortada: spread estimado inválido; usa un valor entre 0 y 5%.', 'error');
                return;
            }
            const minProfitPct = getMinimumNetProfitPct();
            if (!Number.isFinite(minProfitPct)) {
                logToTerminal('⚠️ Ejecución abortada: beneficio neto mínimo inválido; usa un valor entre 0 y 5%.', 'error');
                return;
            }
            let tpLimit;
            let slLimit;
            if (tradeStrategyMode === 'mean_reversion_atr') {
                if (
                    !strategyMetrics
                    || strategyMetrics.mode !== 'mean_reversion_atr'
                    || strategyMetrics.candidate_eligible !== true
                    || !Number.isFinite(strategyMetrics.atr_14)
                    || strategyMetrics.atr_14 <= 0
                ) {
                    logToTerminal('🛑 Compra ATR abortada: faltan métricas cuantitativas válidas y aprobadas por el backend.', 'error');
                    return;
                }
                tpLimit = (4.0 * strategyMetrics.atr_14 / price) * 100;
                slLimit = (1.5 * strategyMetrics.atr_14 / price) * 100;
            } else if (tradeStrategyMode === 'kula_balam_cava_ruiz') {
                tpLimit = Number(strategyMetrics?.tp_gross_pct) || 3.0;
                slLimit = Number(strategyMetrics?.sl_gross_pct) || 1.2;
            } else if (tradeStrategyMode === 'tres_velas_wyckoff_bulkowski') {
                tpLimit = Number(strategyMetrics?.tp_gross_pct) || 3.0;
                slLimit = Number(strategyMetrics?.sl_gross_pct) || 1.5;
            } else if (tradeStrategyMode === 'trailing_trend_runner' || tradeStrategyMode === 'trailing_short_runner') {
                tpLimit = Number(strategyMetrics?.tp_gross_pct) || 6.0;
                slLimit = Number(strategyMetrics?.sl_gross_pct) || 1.5;
            } else if (tradeStrategyMode === 'hyenuk_chu_multibagger') {
                tpLimit = Number(strategyMetrics?.tp_gross_pct) || 3.5;
                slLimit = Number(strategyMetrics?.sl_gross_pct) || 1.75;
            } else if (tradeStrategyMode === 'nasdaq_araujo_vwap') {
                tpLimit = Number(strategyMetrics?.tp_gross_pct) || 1.2;
                slLimit = Number(strategyMetrics?.sl_gross_pct) || 0.8;
            } else {
                const tpSlVal = document.getElementById('tpSlSelect')?.value || "2.1|-0.6";
                const [tpStr, slStr] = tpSlVal.split('|');
                tpLimit = Math.abs(parseFloat(tpStr)) || 1.0;
                slLimit = Math.abs(parseFloat(slStr)) || 0.5;
            }
            const tpNet = tradingGuards.netReturnAfterCosts(tpLimit, feeRate, spreadRate);
            const slNet = tradingGuards.netReturnAfterCosts(-slLimit, feeRate, spreadRate);
            const requiredNetTp = tradeStrategyMode === 'mean_reversion_atr'
                ? Math.max(0.5, minProfitPct)
                : minProfitPct;
            const roundTripCost = 2 * (feeRate + spreadRate);
            const atrCostHurdleFails = tradeStrategyMode === 'mean_reversion_atr'
                && tpLimit < roundTripCost * 3.5;
            if (atrCostHurdleFails) {
                logToTerminal('🛑 Compra ATR abortada: el TP bruto actualizado no cubre 3.5 veces el costo ida/vuelta estimado.', 'error');
                return;
            }
            if (!Number.isFinite(tpNet) || !Number.isFinite(slNet) || tpNet < requiredNetTp) {
                logToTerminal(`🛑 Compra abortada: TP neto estimado (${Number.isFinite(tpNet) ? tpNet.toFixed(3) : 'inválido'}%) inferior al mínimo requerido (${requiredNetTp.toFixed(3)}%).`, 'error');
                return;
            }
            const executedStrategyMetrics = tradeStrategyMode !== 'manual'
                ? { ...(strategyMetrics || {}), mode: tradeStrategyMode, tp_gross_pct: tpLimit, sl_gross_pct: slLimit, tp_net_pct: tpNet, sl_net_pct: slNet }
                : null;
            
            let isJitAllocated = false;
            let jitTradeAmount = 0;
            let tradeAmount;
            if (tradeStrategyMode === 'mean_reversion_atr') {
                const riskBudgetPct = getQuantRiskBudgetPct();
                if (!Number.isFinite(riskBudgetPct)) {
                    logToTerminal('🛑 Compra ATR abortada: presupuesto de riesgo inválido.', 'error');
                    return;
                }
                const availableVault = (portfolio.vault && Number.isFinite(portfolio.vault[currency]))
                    ? portfolio.vault[currency]
                    : 0.0;
                const walletBalance = (portfolio.balances && Number.isFinite(portfolio.balances[currency]))
                    ? portfolio.balances[currency]
                    : 0;
                const accountEquity = walletBalance + availableVault;
                tradeAmount = tradingGuards.positionSizeForRiskBudget(
                    accountEquity,
                    slNet,
                    riskBudgetPct,
                    riskFactor,
                    accountEquity
                );
                if (!Number.isFinite(tradeAmount)) {
                    logToTerminal('🛑 Compra ATR abortada: no se pudo calcular un tamaño de posición seguro.', 'error');
                    return;
                }
                if (tradeAmount < 5) {
                    logToTerminal('⚠️ Saldo insuficiente: el tamaño calculado por presupuesto de riesgo es menor al mínimo de $5.', 'error');
                    return;
                }
                if (tradeAmount > walletBalance && availableVault > 0) {
                    const vaultContribution = Math.min(tradeAmount - walletBalance, availableVault);
                    portfolio.vault[currency] = Math.max(0, availableVault - vaultContribution);
                    portfolio.balances[currency] = walletBalance + vaultContribution;
                    jitTradeAmount = vaultContribution;
                    isJitAllocated = vaultContribution > 0;
                    logToTerminal(`🏦 [JIT FUNDING] Asignados $${vaultContribution.toFixed(2)} ${currency} desde la Bóveda para cubrir la operación ATR.`, 'action');
                }
            } else {
                const availableVault = (portfolio.vault && Number.isFinite(portfolio.vault[currency]))
                    ? portfolio.vault[currency]
                    : 0.0;
                const walletBalance = (portfolio.balances && Number.isFinite(portfolio.balances[currency]))
                    ? portfolio.balances[currency]
                    : 0;
                if (walletBalance < 5 && availableVault >= 5) {
                    const vaultAlloc = availableVault * riskFactor;
                    const safeAlloc = Math.min(availableVault, vaultAlloc);
                    if (safeAlloc >= 5.0) {
                        portfolio.vault[currency] = Math.max(0, availableVault - safeAlloc);
                        portfolio.balances[currency] = walletBalance + safeAlloc;
                        jitTradeAmount = safeAlloc;
                        isJitAllocated = true;
                        logToTerminal(`🏦 [JIT FUNDING] Asignados $${safeAlloc.toFixed(2)} ${currency} desde la Bóveda para ejecutar la oportunidad.`, 'action');
                    }
                }
                tradeAmount = isJitAllocated ? jitTradeAmount : portfolio.balances[currency] * riskFactor;
            }
            
            if (tradeAmount < 5) {
                logToTerminal('⚠️ Saldo insuficiente para abrir nueva posición (mínimo $5).', 'error');
                return;
            }

            const buyFillPrice = price * (1 + spreadRate / 100);
            const cantidadAComprar = tradeAmount / (buyFillPrice * (1 + feeRate / 100));
            const feeAmount = cantidadAComprar * buyFillPrice * (feeRate / 100);

            portfolio.position = {
                symbol: effectiveSymbol,
                baseCoin: baseCoin,
                currency: currency,
                qty: cantidadAComprar,
                entryPrice: buyFillPrice,
                costBasis: tradeAmount,
                feeRate: feeRate,
                spreadRate: spreadRate,
                minProfitPct: minProfitPct,
                tp: tpNet,
                sl: slLimit,
                stopNetPct: slNet,
                strategyMode: tradeStrategyMode,
                strategyMetrics: executedStrategyMetrics,
                riskBudgetPct: tradeStrategyMode === 'mean_reversion_atr' ? getQuantRiskBudgetPct() : null,
                peakPrice: buyFillPrice,
                beArmed: false,
                trailActive: false,
                trailPct: (tradeStrategyMode === 'trailing_trend_runner' || tradeStrategyMode === 'trailing_short_runner') ? slLimit : ((tradeStrategyMode === 'hyenuk_chu_multibagger' || tradeStrategyMode === 'kula_balam_cava_ruiz' || tradeStrategyMode === 'tres_velas_wyckoff_bulkowski') ? 1.5 : 0.5),
                trimmed: false,
                openedAt: new Date().toISOString(),
                jitAllocated: isJitAllocated
            };
            
            // Espejo retrocompatible
            portfolio.ASSET = cantidadAComprar;
            portfolio.entryPrice = price;
            portfolio.balances[currency] -= tradeAmount;
            portfolio.totalFeesPaid = (portfolio.totalFeesPaid || 0) + feeAmount;
            
            // R2 item 5: Limpiar variables de precio de fondo al abrir nueva posición
            window.positionAssetPrice = null;
            window.positionAssetPriceTs = 0;
            
            logToTerminal(`💰 SIMULACIÓN: COMPRADO ${cantidadAComprar.toFixed(4)} ${baseCoin} (${effectiveSymbol}) a $${buyFillPrice.toLocaleString()} (mercado: $${price.toLocaleString()} | spread estimado: ${spreadRate}% | inversión total: $${tradeAmount.toFixed(2)} | fee: $${feeAmount.toFixed(2)} | TP neto: +${tpNet.toFixed(3)}% | SL neto: ${slNet.toFixed(3)}%)`, 'action');
            addTradeToHistory(signal, effectiveSymbol, baseCoin, buyFillPrice, 'Ejecutada', mode, feeAmount, cantidadAComprar);
            fetch(`${API_BASE_URL}/api/broker/entry`, {
                method: 'POST',
                headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({
                    symbol: effectiveSymbol,
                    qty: cantidadAComprar,
                    price: buyFillPrice,
                    tp_pct: tpLimit,
                    sl_pct: slLimit
                })
            })
                .then(r => r.ok ? r.json() : null)
                .then(entryRes => {
                    const posId = entryRes?.result?.position?.id || entryRes?.position?.id;
                    if (posId && portfolio.position && portfolio.position.symbol === effectiveSymbol) {
                        portfolio.position.backendId = posId;
                        localStorage.setItem('ai_portfolio_v5', JSON.stringify(portfolio));
                    }
                })
                .catch(err => console.debug('Aviso sincronizando apertura con broker SQLite:', err));
        } else if (signal === 'VENDER') {
            // VENDER siempre usa los datos reales de la posición (Bloque 1 item 5)
            const pos = openPos;
            const sellSymbol = pos.symbol;
            const sellCoin = pos.baseCoin;
            const sellCurrency = pos.currency || getCurrency(sellSymbol);
            if (sellSymbol !== effectiveSymbol || !Number.isFinite(portfolio.balances[sellCurrency])) {
                logToTerminal(`⚠️ Ejecución abortada: activo o saldo de billetera no coincide con la posición ${sellSymbol}.`, 'error');
                return;
            }
            const posQty = pos.qty;
            const feeRate = (pos && typeof pos.feeRate === 'number') ? pos.feeRate : getBrokerFeeRate(sellSymbol);

            // Validación de frescura en milisegundos para ventas si no está en pantalla (Bloque 1 y 2)
            let execSellPrice = price;
            if (sellSymbol !== currentSymbol && !verifiedQuote) {
                const nowMs = Date.now();
                const ageMs = nowMs - (window.positionAssetPriceTs || 0);
                const thresholdMs = sellSymbol.includes('/') ? 20000 : 150000;
                if (!window.positionAssetPrice || ageMs > thresholdMs) {
                    logToTerminal(`⚠️ [VENTA ABORTADA] No hay precio fresco (< ${thresholdMs / 1000}s) de segundo plano para ${sellSymbol}. Cambia al activo en pantalla o espera respuesta del feed.`, 'error');
                    return;
                }
                execSellPrice = window.positionAssetPrice;
            }

            const spreadRate = Number.isFinite(pos.spreadRate) ? pos.spreadRate : 0;
            if (spreadRate < 0 || spreadRate > 5) {
                logToTerminal('⚠️ Ejecución abortada: spread guardado en la posición inválido.', 'error');
                return;
            }
            const minProfitPct = Number.isFinite(pos.minProfitPct)
                ? pos.minProfitPct
                : getMinimumNetProfitPct();
            if (!Number.isFinite(minProfitPct) || minProfitPct < 0 || minProfitPct > 5) {
                logToTerminal('⚠️ Venta de estrategia bloqueada: beneficio neto mínimo inválido; corrige el parámetro en Ajustes.', 'error');
                return;
            }
            const strategyProfitExit = ['Copiloto', 'Inteligente', 'Automático', 'Take Profit'].includes(mode);
            if (strategyProfitExit) {
                const netProfitPct = netPctAtPrice(pos, execSellPrice, feeRate);
                if (tradingGuards.shouldBlockProfitTakingExit(netProfitPct, minProfitPct)) {
                    logToTerminal(`🛑 Venta de estrategia bloqueada: PnL neto estimado ${Number.isFinite(netProfitPct) ? netProfitPct.toFixed(3) : 'inválido'}%, por debajo del mínimo ${minProfitPct.toFixed(3)}%. Los cierres Stop Loss, breakeven, trailing y manual siguen permitidos.`, 'warn');
                    return;
                }
            }
            const isShortSell = String(pos.side || '').toUpperCase() === 'SHORT';
            const sellFillPrice = isShortSell
                ? execSellPrice * (1 + spreadRate / 100)
                : execSellPrice * (1 - spreadRate / 100);
            const dolaresObtenidosBruto = posQty * sellFillPrice;
            const feeAmount = dolaresObtenidosBruto * (feeRate / 100);
            const costBasis = pos.costBasis || (posQty * pos.entryPrice);
            const pnlNeto = isShortSell
                ? (costBasis - dolaresObtenidosBruto - feeAmount)
                : ((dolaresObtenidosBruto - feeAmount) - costBasis);
            const dolaresNetos = isShortSell
                ? Math.max(0, costBasis + pnlNeto)
                : (dolaresObtenidosBruto - feeAmount);
            
            const closedPosId = (pos && (pos.backendId || pos.openedAt)) || null;
            if (pos && pos.backendId) {
                lastClosedBackendPosId = pos.backendId;
            }
            portfolio.balances[sellCurrency] += dolaresNetos;
            if (pos && pos.jitAllocated) {
                // Sweep-Back: Retornar capital base + resultado neto directamente a la Bóveda del Broker
                const sweepAmount = dolaresNetos;
                portfolio.balances[sellCurrency] = Math.max(0, portfolio.balances[sellCurrency] - sweepAmount);
                if (!portfolio.vault) portfolio.vault = { USDT: 0.0, USD: 0.0, ARS: 0.0 };
                portfolio.vault[sellCurrency] = (portfolio.vault[sellCurrency] || 0) + sweepAmount;
                logToTerminal(`🧹 [SWEEP-BACK] Trade JIT cerrado. $${sweepAmount.toFixed(2)} ${sellCurrency} devueltos íntegramente a la Bóveda (Saldo Bóveda: $${portfolio.vault[sellCurrency].toFixed(2)} ${sellCurrency}).`, 'action');
            }
            portfolio.position = null;
            portfolio.ASSET = 0;
            portfolio.entryPrice = 0;
            // R2 item 5: Limpiar positionAssetPrice y timestamp al cerrar posición
            window.positionAssetPrice = null;
            window.positionAssetPriceTs = 0;
            portfolio.totalFeesPaid = (portfolio.totalFeesPaid || 0) + feeAmount;
            
            // Actualizar Circuit Breaker diario por libro (Bloque 3 - R4)
            recordTradeInCircuitBreaker(pnlNeto, sellCurrency, closedPosId);

            // R8: Cooldown post-cierre al cerrar posición (manual, SL o TP)
            const tfSecMap = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '1d': 86400 };
            const tfVal = document.getElementById('timeframeSelect')?.value || '1m';
            const tfSec = tfSecMap[tfVal] || 60;

            const cooldownMs = Math.max(300000, 3 * tfSec * 1000);
            const cooldownUntil = Date.now() + cooldownMs;
            localStorage.setItem('ai_cooldown_v1', String(cooldownUntil));
            logToTerminal(`⏳ [COOLDOWN INICIADO] Pausa de ${(cooldownMs / 60000).toFixed(1)} min para nuevas compras tras cierre de posición.`, 'info');

            logToTerminal(`💵 SIMULACIÓN: VENDIDO ${sellCoin} (${sellSymbol}) a $${sellFillPrice.toLocaleString()} (mercado: $${execSellPrice.toLocaleString()} | spread estimado: ${spreadRate}% | bruto: $${dolaresObtenidosBruto.toFixed(2)} | fee: $${feeAmount.toFixed(2)} | neto: $${dolaresNetos.toFixed(2)} | PnL: ${pnlNeto >= 0 ? '+' : ''}$${pnlNeto.toFixed(2)}). Saldo ${sellCurrency}: $${portfolio.balances[sellCurrency].toFixed(2)}`, 'error');
            
            // Graceful Shutdown: Apagado programado post-cierre
            if (isStopAfterCloseArmed) {
                isStopAfterCloseArmed = false;
                localStorage.removeItem('ai_stop_after_close');
                if (isAgentActive) {
                    stopAgent('post_trade_closure');
                    logToTerminal(`🛡️ [APAGADO PROGRAMADO] Posición en ${sellSymbol} cerrada con éxito. Agente detenido automáticamente como ordenaste.`, 'action');
                }
            }
            addTradeToHistory(signal, sellSymbol, sellCoin, sellFillPrice, 'Ejecutada', mode, feeAmount, posQty);
            if (pos && pos.backendId) {
                fetch(`${API_BASE_URL}/api/broker/flatten`, {
                    method: 'POST',
                    headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({
                        symbol: sellSymbol,
                        price: execSellPrice,
                        reason: mode,
                        skip_csv_log: true
                    })
                }).catch(err => console.debug('Aviso sincronizando cierre con broker SQLite:', err));
            }
        }
        
        localStorage.setItem('ai_portfolio_v5', JSON.stringify(portfolio));
        updateCapitalDisplay();
    } finally {
        isExecutingTrade = false;
    }
}

let pendingTrade = null;
const modal = document.getElementById('copilotModal');

function showCopilotModal(
    signal,
    symbol,
    reason,
    baseCoin,
    price,
    candleTs = 0,
    signalPrice = price,
    tradeSettings = {}
) {
    if (copilotExpiryTimer) {
        clearInterval(copilotExpiryTimer);
        copilotExpiryTimer = null;
    }
    document.getElementById('copilotMessage').innerText = `El Agente recomienda ${signal} ${baseCoin} (${symbol}) a $${price.toLocaleString()}`;
    document.getElementById('copilotReason').innerText = `Razonamiento: ${reason}`;
    modal.classList.remove('hidden');
    pendingTrade = {
        signal,
        symbol,
        baseCoin,
        price,
        signalPrice,
        candleTs: Number(candleTs) || 0,
        openedAt: Date.now(),
        strategyMode: tradeSettings.strategyMode || 'manual',
        strategyMetrics: tradeSettings.strategyMetrics || null
    };

    let timeLeft = 120;
    copilotExpiryTimer = setInterval(() => {
        timeLeft--;
        if (timeLeft <= 0) {
            clearInterval(copilotExpiryTimer);
            copilotExpiryTimer = null;
            if (pendingTrade && !modal.classList.contains('hidden')) {
                modal.classList.add('hidden');
                logToTerminal(`⌛ [COPILOTO] Orden expirada tras 120s sin confirmación (${pendingTrade.signal} ${pendingTrade.symbol}).`, 'warn');
                addTradeToHistory(pendingTrade.signal, pendingTrade.symbol, pendingTrade.baseCoin, pendingTrade.signalPrice, 'Expirada', 'Copiloto', 0, 0);
                if (pendingTrade.candleTs > 0) {
                    lastHandledCandle = { symbol: pendingTrade.symbol, candleTs: pendingTrade.candleTs };
                }
                pendingTrade = null;
                copilotState = 'idle';
                startAgent('copilot_expired');
                scheduleNext(15000);
            }
        }
    }, 1000);
}

// Tecla ESC para rechazar orden en modal copiloto (Bloque 3 item 3)
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && !modal.classList.contains('hidden')) {
        document.getElementById('btnReject')?.click();
    }
});

document.getElementById('btnReject').addEventListener('click', () => {
    if (copilotExpiryTimer) {
        clearInterval(copilotExpiryTimer);
        copilotExpiryTimer = null;
    }
    modal.classList.add('hidden');
    if (pendingTrade) {
        logToTerminal('❌ Operación rechazada por el usuario.', 'warn');
        addTradeToHistory(pendingTrade.signal, pendingTrade.symbol, pendingTrade.baseCoin, pendingTrade.signalPrice, 'Rechazada', 'Copiloto');
        if (pendingTrade.candleTs > 0) {
            lastHandledCandle = { symbol: pendingTrade.symbol, candleTs: pendingTrade.candleTs };
        }
        // Cooldown tras rechazar para no reabrir el modal inmediatamente (Bloque 4)
        const tfSecMap = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '1d': 86400 };
        const tfVal = document.getElementById('timeframeSelect')?.value || '1m';
        const tfSec = tfSecMap[tfVal] || 60;

        const cooldownMs = Math.max(300000, 3 * tfSec * 1000);
        const cooldownUntil = Date.now() + cooldownMs;
        localStorage.setItem('ai_cooldown_v1', String(cooldownUntil));
        logToTerminal(`⏳ [COOLDOWN INICIADO] Pausa de ${(cooldownMs / 60000).toFixed(1)} min tras rechazar operación.`, 'info');
        pendingTrade = null;
    }
    copilotState = 'idle';
    startAgent('copilot_rejected');
    scheduleNext(15000);
});

document.getElementById('btnApprove').addEventListener('click', async () => {
    if (copilotExpiryTimer) {
        clearInterval(copilotExpiryTimer);
        copilotExpiryTimer = null;
    }
    modal.classList.add('hidden');
    if (pendingTrade) {
        const openPos = getOpenPosition();
        const hasPos = !!openPos;
        const tradeSymbol = pendingTrade.symbol || currentSymbol;
        const candleTs = pendingTrade.candleTs || 0;

        // R4: Si se bloquea en btnApprove por Circuit Breaker, descarta y registra como 'Rechazada' con motivo 'Circuit Breaker'
        if (pendingTrade.signal === 'COMPRAR' && isCircuitBreakerActive()) {
            const state = getRiskState();
            logToTerminal(`🛑 [CIRCUIT BREAKER] Compra descartada por Circuit Breaker (${state.haltReason}).`, 'error');
            addTradeToHistory('COMPRAR', tradeSymbol, pendingTrade.baseCoin, pendingTrade.signalPrice, 'Rechazada', 'Circuit Breaker');
            if (candleTs > 0) lastHandledCandle = { symbol: tradeSymbol, candleTs };
            pendingTrade = null;
            copilotState = 'idle';
            stopAgent('circuit_breaker');
            return;
        }

        // 1. Revalidar estado antes de ejecutar
        if (pendingTrade.signal === 'COMPRAR') {
            if (hasPos) {
                logToTerminal('⚠️ Orden descartada: ya tienes una posición abierta mientras decidías.', 'warn');
                if (candleTs > 0) lastHandledCandle = { symbol: tradeSymbol, candleTs };
                pendingTrade = null;
                copilotState = 'idle';
                startAgent('copilot_discarded');
                scheduleNext(15000);
                return;
            }
            if (currentSymbol !== pendingTrade.symbol) {
                logToTerminal(`⚠️ Orden de compra descartada: cambiaste de activo en pantalla (${currentSymbol} != ${pendingTrade.symbol}).`, 'warn');
                if (candleTs > 0) lastHandledCandle = { symbol: tradeSymbol, candleTs };
                pendingTrade = null;
                copilotState = 'idle';
                startAgent('copilot_discarded');
                scheduleNext(15000);
                return;
            }
            const savedCooldown = Number(localStorage.getItem('ai_cooldown_v1')) || 0;
            if (Date.now() < savedCooldown) {
                const minLeft = ((savedCooldown - Date.now()) / 60000).toFixed(1);
                logToTerminal(`⏳ [COOLDOWN ACTIVO] Orden de compra descartada. Restan ${minLeft} min tras el último cierre.`, 'warn');
                if (candleTs > 0) lastHandledCandle = { symbol: tradeSymbol, candleTs };
                pendingTrade = null;
                copilotState = 'idle';
                startAgent('copilot_discarded');
                scheduleNext(15000);
                return;
            }
        }
        if (pendingTrade.signal === 'VENDER') {
            if (!hasPos) {
                logToTerminal('⚠️ Orden descartada: la posición ya fue cerrada previamente (ej. Stop Loss).', 'warn');
                if (candleTs > 0) lastHandledCandle = { symbol: tradeSymbol, candleTs };
                pendingTrade = null;
                copilotState = 'idle';
                startAgent('copilot_discarded');
                scheduleNext(15000);
                return;
            }
        }

        let evalCurrentPrice;
        try {
            evalCurrentPrice = await fetchFreshExecutionQuote(tradeSymbol);
        } catch (err) {
            logToTerminal(`⚠️ [APROBACIÓN ABORTADA] No se obtuvo un precio fresco y ejecutable: ${err.message}`, 'error');
            pendingTrade = null;
            copilotState = 'idle';
            startAgent('copilot_discarded');
            scheduleNext(15000);
            return;
        }
        if (!pendingTrade) return;

        const refreshedPos = getOpenPosition();
        if (
            (pendingTrade.signal === 'COMPRAR' && refreshedPos)
            || (pendingTrade.signal === 'VENDER' && (!refreshedPos || refreshedPos.symbol !== tradeSymbol))
        ) {
            logToTerminal('⚠️ Orden descartada: el estado de la posición cambió durante la verificación del precio.', 'warn');
            pendingTrade = null;
            copilotState = 'idle';
            startAgent('copilot_discarded');
            scheduleNext(15000);
            return;
        }

        const withinSlippage = tradingGuards.isWithinSlippage(pendingTrade.signalPrice, evalCurrentPrice, 1);
        if (pendingTrade.signal === 'COMPRAR' && !withinSlippage) {
            logToTerminal(`🛑 [SLIPPAGE] Compra no aprobada: el precio varió más de 1% desde la señal (${pendingTrade.signalPrice} → ${evalCurrentPrice}).`, 'error');
            if (candleTs > 0) lastHandledCandle = { symbol: tradeSymbol, candleTs };
            pendingTrade = null;
            copilotState = 'idle';
            startAgent('copilot_discarded');
            scheduleNext(15000);
            return;
        }
        if (pendingTrade.signal === 'VENDER' && !withinSlippage) {
            logToTerminal(`⚠️ [SLIPPAGE] Salida autorizada al precio fresco actual pese a una variación superior a 1% (${pendingTrade.signalPrice} → ${evalCurrentPrice}).`, 'warn');
        }

        if (candleTs > 0) {
            lastHandledCandle = { symbol: tradeSymbol, candleTs };
        }

        logToTerminal('✅ Operación aprobada por el usuario.', 'action');
        executeTrade(
            pendingTrade.signal,
            tradeSymbol,
            pendingTrade.baseCoin,
            evalCurrentPrice,
            'Copiloto',
            {
                verifiedQuote: true,
                strategyMode: pendingTrade.strategyMode,
                strategyMetrics: pendingTrade.strategyMetrics
            }
        );
        pendingTrade = null;
    }
    copilotState = 'idle';
    startAgent('copilot_approved');
    scheduleNext(15000);
});

// Cierre Manual de Emergencia (Bloque 1 item 6, Bloque 4 item 3, Soporte Multi-Posición)
window.forceClosePosition = async function(event, targetSymbol) {
    if (event) {
        event.stopPropagation?.();
        event.preventDefault?.();
    }
    const allPos = (window.backendOpenPositions && window.backendOpenPositions.length > 0)
        ? window.backendOpenPositions
        : (getOpenPosition() ? [getOpenPosition()] : []);

    const pos = (targetSymbol && allPos.length > 0)
        ? (allPos.find(p => p.symbol === targetSymbol) || getOpenPosition())
        : getOpenPosition();

    if (!pos) {
        logToTerminal(`ℹ️ No hay posición abierta que cerrar.`, 'info');
        return;
    }
    const sym = targetSymbol || pos.symbol;
    if (manualCloseInFlight || isExecutingTrade) {
        logToTerminal('⚠️ Cierre manual no iniciado: ya hay una operación en curso.', 'warn');
        return;
    }

    manualCloseInFlight = true;
    try {
        logToTerminal(`⚠️ CIERRE MANUAL: Solicitando cotización fresca para cerrar ${sym}.`, 'error');
        if (modal && !modal.classList.contains('hidden')) {
            if (copilotExpiryTimer) {
                clearInterval(copilotExpiryTimer);
                copilotExpiryTimer = null;
            }
            modal.classList.add('hidden');
            pendingTrade = null;
        }
        copilotState = 'idle';
        isCopilotApprovalPause = false;

        let freshPrice;
        let isClosedMarket = false;
        try {
            freshPrice = await fetchFreshExecutionQuote(sym, null, true);
        } catch (quoteErr) {
            freshPrice = Number(pos.current_price || pos.currentPrice || pos.entry_price || pos.entryPrice || 0);
            isClosedMarket = true;
            logToTerminal(`ℹ️ Mercado cerrado o sin feed activo: usando último precio disponible ($${freshPrice}) para liquidación forzada.`, 'warn');
        }

        const reason = isClosedMarket ? 'Manual Flatten (Mercado Cerrado)' : 'Manual Flatten Operador';
        const baseCoin = sym.split('/')[0];
        executeTrade('VENDER', sym, baseCoin, freshPrice, 'Manual', { verifiedQuote: true });
        await fetch(`${API_BASE_URL}/api/broker/flatten`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ symbol: sym, price: freshPrice, reason: reason })
        }).catch(err => console.debug('Aviso notificando flatten:', err));

        if (window.UIFeedback) {
            window.UIFeedback.toast(`Posición en ${sym} liquidada exitosamente a $${freshPrice.toFixed(2)}.`, { type: 'success', title: 'Posición Cerrada' });
        }
        if (portfolio.position && portfolio.position.symbol === sym) {
            portfolio.position = null;
        }
        if (window.backendOpenPositions) {
            window.backendOpenPositions = window.backendOpenPositions.filter(p => p.symbol !== sym);
        }
        updateCapitalDisplay();
        await checkDaemonServerStatus();
    } catch (err) {
        logToTerminal(`🛑 Cierre manual falló para ${sym}: ${err.message}`, 'error');
    } finally {
        manualCloseInFlight = false;
    }
};
window.cerrarPosicion = window.forceClosePosition;

function _applyKulaSemPill(elemId, lightData) {
    const el = document.getElementById(elemId);
    if (!el || !lightData) return;
    const st = String(lightData.status || 'YELLOW').toUpperCase();
    el.classList.remove('sem-green', 'sem-yellow', 'sem-red', 'sem-cyan');
    const cls = st === 'GREEN'
        ? 'sem-green'
        : (st === 'RED' ? 'sem-red' : (st === 'CYAN' ? 'sem-cyan' : 'sem-yellow'));
    el.classList.add(cls);
    el.title = lightData.detail || '';
    const lblSpan = el.querySelector('span:last-child');
    if (lblSpan) lblSpan.textContent = lightData.label || '--';
}

async function checkKulaSemaforo(forceProbe = false) {
    const btn = document.getElementById('btnKulaWatchdogProbe');
    if (forceProbe && btn) {
        btn.disabled = true;
        btn.textContent = '⏳ Probando...';
    }
    try {
        const res = await fetch(`${API_BASE_URL}/api/health/semaforo?probe=${forceProbe ? 'true' : 'false'}`, {
            headers: apiAuthHeaders()
        });
        if (!res.ok) return;
        const data = await res.json();
        const lights = data.lights || {};
        _applyKulaSemPill('kula-sem-motor', lights.kula_motor);
        _applyKulaSemPill('kula-sem-guardian', lights.guardian_sl);
        _applyKulaSemPill('kula-sem-formulas', lights.formulas_sintetico);
        _applyKulaSemPill('kula-sem-balam', lights.balam_puente);

        const qc = data.quick_check || null;
        if (qc) {
            const isOk = qc.binary_status === 'OK';
            _applyKulaSemPill('kula-qc-binary', {
                status: isOk ? 'GREEN' : (data.status === 'RED' ? 'RED' : 'YELLOW'),
                label: isOk ? '✅ 100% OK' : '⚠️ FALTA / ALERTA',
                detail: qc.binary_label || '',
            });

            const cov = qc.assets_coverage || {};
            const covMissing = Array.isArray(cov.missing) && cov.missing.length > 0;
            const covStatus = !cov.known ? 'YELLOW' : (covMissing ? 'RED' : 'GREEN');
            const covShort = cov.known ? `Activos: ${cov.reviewed}/${cov.expected}` : 'Activos: s/barrido';
            _applyKulaSemPill('kula-qc-coverage', {
                status: covStatus,
                label: covShort,
                detail: cov.label || '',
            });

            const tfBadgeData = (typeof tradingGuards !== 'undefined' && typeof tradingGuards.formatSemaforoTimeframeBadge === 'function')
                ? tradingGuards.formatSemaforoTimeframeBadge(qc)
                : {
                    status: (qc.active_mode_summary?.tf_alert ? 'RED' : (qc.presencial_active ? 'CYAN' : 'GREEN')),
                    label: `${qc.presencial_active ? 'Presencial' : 'TF'}: ${qc.timeframe || qc.active_mode_summary?.timeframe || '--'}`,
                    detail: qc.active_mode_summary?.text || '',
                };
            _applyKulaSemPill('kula-qc-timeframe', tfBadgeData);

            const modeEl = document.getElementById('kula-qc-mode');
            const ams = qc.active_mode_summary || {};
            if (modeEl) {
                const fList = Array.isArray(ams.formulas) && ams.formulas.length > 0 ? ams.formulas.join(', ') : 's/fórmula';
                modeEl.textContent = `[${ams.mode || 'MODO'}] ${ams.objective || ''} · Fórmula: ${fList} · TF real: ${ams.timeframe || 'n/d'}`;
                modeEl.title = ams.text || '';
            }

            const tfAlertEl = document.getElementById('kula-qc-tf-alert');
            if (tfAlertEl) {
                if (ams.tf_alert && Array.isArray(ams.forced_tf_warnings) && ams.forced_tf_warnings.length > 0) {
                    tfAlertEl.textContent = `⚠️ TF forzada (${ams.forced_tf_warnings[0]})`;
                    tfAlertEl.title = ams.forced_tf_warnings.join(' | ');
                    tfAlertEl.classList.remove('hidden');
                } else {
                    tfAlertEl.classList.add('hidden');
                    tfAlertEl.textContent = '';
                }
            }

            const triadEl = document.getElementById('kula-qc-triad');
            const tr = qc.triad_state || {};
            if (triadEl) {
                const iconFor = (st) => (st === 'GREEN' ? '🟢' : (st === 'RED' ? '🔴' : '🟡'));
                const c = tr.cerebro || {};
                const b = tr.balam || {};
                const k = tr.kula || {};
                triadEl.textContent = `${iconFor(c.status)} ${c.label || 'Cerebro'} · ${iconFor(b.status)} ${b.label || 'Balam'} · ${iconFor(k.status)} ${k.label || 'Kula'}`;
                triadEl.title = `${c.label || ''} | ${b.label || ''} | ${k.label || ''}`;
            }

            const reasonEl = document.getElementById('kula-qc-reason');
            if (reasonEl) {
                const rText = qc.last_no_trade_reason || window.lastDaemonReason || 'Sin evaluaciones aún';
                reasonEl.textContent = `Último motivo: ${rText}`;
                reasonEl.title = qc.last_no_trade_reason_full || rText;
            }
        }

        const alertBox = document.getElementById('kula-semaforo-alert');
        if (alertBox) {
            if (qc && qc.binary_status !== 'OK' && qc.binary_label) {
                alertBox.textContent = qc.binary_label;
                alertBox.classList.remove('hidden');
            } else {
                const reds = Object.values(lights).filter(l => l && l.status === 'RED' && l.detail);
                if (reds.length > 0) {
                    alertBox.textContent = `🚨 Alerta Watchdog (0 tokens): ${reds.map(r => `${r.label}: ${r.detail}`).join(' | ')}`;
                    alertBox.classList.remove('hidden');
                } else {
                    alertBox.classList.add('hidden');
                    alertBox.textContent = '';
                }
            }
        }
    } catch (err) {
        console.debug('Aviso consultando semáforo Kula:', err);
    } finally {
        if (forceProbe && btn) {
            btn.disabled = false;
            btn.textContent = '🔄 Auto-Check';
        }
    }
}
window.checkKulaSemaforo = checkKulaSemaforo;

// Control de Apagado Programado (Graceful Shutdown)
window.toggleStopAfterClose = function() {
    const pos = getOpenPosition();
    if (!pos) {
        logToTerminal('ℹ️ No hay posición abierta sobre la cual programar el apagado.', 'info');
        return;
    }
    isStopAfterCloseArmed = !isStopAfterCloseArmed;
    if (isStopAfterCloseArmed) {
        localStorage.setItem('ai_stop_after_close', 'true');
        logToTerminal(`🛑 [APAGADO PROGRAMADO] Activado: El agente gestionará la salida óptima de ${pos.symbol} (TP/Breakeven/Trailing/SL) y se detendrá automáticamente al cerrar el trade.`, 'action');
    } else {
        localStorage.removeItem('ai_stop_after_close');
        logToTerminal(`ℹ️ [APAGADO PROGRAMADO] Cancelado: El agente continuará operando normalmente tras el cierre de ${pos.symbol}.`, 'info');
    }
    updateCapitalDisplay();
};

// Al cargar la página, restaurar el historial visual e inicializar componentes modernos
document.addEventListener('DOMContentLoaded', () => {
    renderTradeHistory();
    if (typeof window.initTradingCustomSelects === 'function') {
        window.initTradingCustomSelects();
    }
    if (typeof window.initMarketRegimeCard === 'function') {
        window.initMarketRegimeCard();
    }
    if (typeof window.fetchMicrostructureRadar === 'function') {
        window.fetchMicrostructureRadar();
    }
    if (typeof window.syncCandlePatternIndicatorState === 'function') {
        window.syncCandlePatternIndicatorState();
    }
    if (typeof window.renderStrategyChecklist === 'function') {
        window.renderStrategyChecklist();
    }
});

// Funciones interactivas de la Bóveda
window.inyectarCapital = function(amount) {
    const cur = getCurrency(currentSymbol);
    portfolio.balances[cur] += amount;
    portfolio.deposits[cur] = (portfolio.deposits[cur] || 0) + amount;
    
    // Al primer fondeo con placeholder, recalcular startEquity; si no-placeholder, ajustar startEquity en el mismo monto
    const rState = getRiskState();
    if (rState.books && rState.books[cur]) {
        if (rState.books[cur].placeholder) {
            let actualEquity = portfolio.balances[cur] || 0;
            const openPos = getOpenPosition();
            if (openPos && (openPos.currency === cur || getCurrency(openPos.symbol) === cur)) {
                actualEquity += (openPos.costBasis || (openPos.qty * openPos.entryPrice));
            }
            rState.books[cur].startEquity = actualEquity;
            rState.books[cur].placeholder = false;
        } else {
            rState.books[cur].startEquity = (rState.books[cur].startEquity || 0) + amount;
        }
        saveRiskState(rState);
    }

    localStorage.setItem('ai_portfolio_v5', JSON.stringify(portfolio));
    logToTerminal(`💸 DEPÓSITO: Se han inyectado $${amount} ${cur} de liquidez a la billetera operativa.`, 'action');
    updateCapitalDisplay();
};


// Listeners de la nueva UI de Configuración
document.getElementById('saveApiKeyBtn')?.addEventListener('click', async () => {
    const key = document.getElementById('apiKeyInput').value;
    if(!key) return;
    try {
        const response = await fetch(`${API_BASE_URL}/api/config/gemini`, {
            method: 'POST',
            headers: apiAuthHeaders({'Content-Type': 'application/json'}),
            body: JSON.stringify({api_key: key})
        });
        const data = await response.json();
        logToTerminal(data.message || data.detail || 'Configuración de API Key procesada.', response.ok ? 'action' : 'error');
        const status = document.getElementById('apiKeyStatus');
        if (status && response.ok) {
            status.classList.remove('hidden');
            setTimeout(() => status.classList.add('hidden'), 3000);
        }
    } catch(err) {
        logToTerminal('Error al guardar API Key en el backend.', 'error');
    }
});

const appTokenInput = document.getElementById('appTokenInput');
if (appTokenInput) {
    appTokenInput.value = sessionStorage.getItem('ai_app_token') || '';
}
document.getElementById('saveAppTokenBtn')?.addEventListener('click', () => {
    const token = appTokenInput?.value.trim() || '';
    if (token) {
        sessionStorage.setItem('ai_app_token', token);
        logToTerminal('Token local de API guardado en esta sesión del navegador.', 'success');
    } else {
        sessionStorage.removeItem('ai_app_token');
        logToTerminal('Token local borrado del navegador.', 'warn');
    }
});

document.getElementById('timeframeSelect')?.addEventListener('change', () => {
    const sel = document.getElementById('timeframeSelect');
    if (getStrategyMode() === 'mean_reversion_atr' && !tradingGuards.isAllowedAtrTimeframe(sel.value)) {
        logToTerminal(`⚠️ La estrategia cuantitativa ATR solo admite temporalidades de 15m o 1h. Ajustando a 15m.`, 'warn');
        sel.value = '15m';
    }
    logToTerminal(`Cambiando temporalidad a ${sel.value}...`, 'warn');
    candleSeries.setData([]);
    smaSeries.setData([]);
    vwapSeries.setData([]);
    vwapUpperSeries.setData([]);
    vwapLowerSeries.setData([]);
    if (rsiSeries) rsiSeries.setData([]);
    if (atrSeries) atrSeries.setData([]);
    if (typeof window.updateQuickTimeframeButtons === 'function') {
        window.updateQuickTimeframeButtons(sel.value);
    }
    if (typeof updateChartHeaderTitles === 'function') {
        updateChartHeaderTitles();
    }
    fetchMarketData();
    const shouldSyncTfToDaemon = (typeof tradingGuards !== 'undefined' && typeof tradingGuards.shouldSyncChartTimeframeToDaemon === 'function')
        ? tradingGuards.shouldSyncChartTimeframeToDaemon(getStrategyMode(), window.scalpingSessionState)
        : (getStrategyMode() !== 'auto' && !(window.scalpingSessionState && (window.scalpingSessionState.active || window.scalpingSessionState.draining)));
    if (shouldSyncTfToDaemon && typeof syncRunningDaemonConfig === 'function') {
        syncRunningDaemonConfig({ syncSymbol: false, syncTimeframe: true });
    }
});


document.getElementById('riskSelect')?.addEventListener('change', () => {
    logToTerminal(`Riesgo actualizado a: ${document.getElementById('riskSelect').options[document.getElementById('riskSelect').selectedIndex].text}`, 'info');
    if (typeof syncRunningDaemonConfig === 'function') syncRunningDaemonConfig();
});

document.getElementById('selScalpingSlot')?.addEventListener('change', (e) => {
    const riskSel = document.getElementById('riskSelect');
    if (riskSel && [...riskSel.options].some(o => o.value === e.target.value)) {
        riskSel.value = e.target.value;
        if (typeof window.updateRiskSlotPreview === 'function') window.updateRiskSlotPreview();
        riskSel.dispatchEvent(new Event('change'));
    }
});

document.getElementById('selScalpingSymbol')?.addEventListener('change', () => {
    if (typeof window.updateRiskSlotPreview === 'function') window.updateRiskSlotPreview();
});

document.getElementById('tpSlSelect')?.addEventListener('change', () => {
    logToTerminal(`Límites de ganancia/pérdida actualizados a: ${document.getElementById('tpSlSelect').options[document.getElementById('tpSlSelect').selectedIndex].text}`, 'info');
    if (typeof syncRunningDaemonConfig === 'function') syncRunningDaemonConfig();
});

const brokerFeeSelect = document.getElementById('brokerFeeSelect');
const customFeeWrapper = document.getElementById('customFeeWrapper');
const customFeeInput = document.getElementById('customFeeInput');

brokerFeeSelect?.addEventListener('change', () => {
    if (brokerFeeSelect.value === 'custom') {
        customFeeWrapper?.classList.remove('hidden');
    } else {
        customFeeWrapper?.classList.add('hidden');
    }
    updateBrokerFeeDisplay();
    logToTerminal(`Comisión del Broker fijada en: ${getBrokerFeeRate()}% por orden (Round-Trip: ${(getBrokerFeeRate() * 2).toFixed(2)}%)`, 'info');
});

customFeeInput?.addEventListener('input', () => {
    updateBrokerFeeDisplay();
});

setTimeout(updateBrokerFeeDisplay, 300);

function updateBrainBadge() {
    const engineSelect = document.getElementById('engineSelect');
    if (!engineSelect) return;
    
    // Reset classes
    engineSelect.className = "w-full bg-gray-900 text-white text-sm rounded p-1.5 border border-gray-700 cursor-pointer relative z-20 mb-3 ";
}

document.getElementById('engineSelect')?.addEventListener('change', () => {
    updateBrainBadge();
    if (typeof window.updateSystemActiveEngineBadges === 'function') {
        window.updateSystemActiveEngineBadges();
    }
    logToTerminal(`Motor de Análisis cambiado a: ${document.getElementById('engineSelect').options[document.getElementById('engineSelect').selectedIndex].text}`, 'warn');
    if (typeof window.purgarMemoriaIA === 'function') {
        window.purgarMemoriaIA(true);
    }
    if (typeof syncRunningDaemonConfig === 'function') syncRunningDaemonConfig();
});

// Inicializar el estilo al cargar la página
setTimeout(() => {
    updateBrainBadge();
    if (typeof window.updateSystemActiveEngineBadges === 'function') {
        window.updateSystemActiveEngineBadges();
    }
}, 500);




// --- SINCRONIZACIÓN DE HISTORIAL DE OPERACIONES DESDE EL BROKER SQLITE ---

async function syncBrokerTrades() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/broker/trades`, { headers: apiAuthHeaders() });
        if (!res.ok) return;
        const data = await res.json();
        if (!data || !Array.isArray(data.trades)) return;
        window.rawBrokerTrades = data.trades;

        const serverTrades = [];
        const vaultUSDT = Number(data.vault_balances?.USDT ?? portfolio?.vault?.USDT ?? 0.0);

        data.trades.forEach(t => {
            const openDate = t.opened_at ? new Date(t.opened_at.endsWith('Z') ? t.opened_at : t.opened_at + 'Z') : new Date();
            const closeDate = t.closed_at ? new Date(t.closed_at.endsWith('Z') ? t.closed_at : t.closed_at + 'Z') : null;
            const pnl = Number(t.realized_pnl) || 0;
            const fee = Number(t.total_fees) || 0;

            const costBasis = Number(t.cost_basis) || (Number(t.qty || 0) * Number(t.entry_price || 0));

            // 1. Evento de COMPRA
            serverTrades.push({
                id: `${t.id}_buy`,
                timeString: openDate.toLocaleTimeString(),
                timestamp: openDate.toISOString(),
                signal: 'COMPRAR',
                symbol: t.symbol,
                baseCoin: t.symbol.split('/')[0],
                price: Number(t.entry_price),
                qty: Number(t.qty),
                costBasis: costBasis,
                strategy: t.strategy || 'trailing_trend_runner',
                engine: t.engine || 'antigravity_operador',
                formula: t.formula || 'Quant Risk ATR',
                status: 'Ejecutada',
                mode: 'Auto (Daemon)',
                fee: fee / 2,
                pnl: null,
                balance: t.status === 'CLOSED' ? (vaultUSDT - pnl) : (vaultUSDT - (t.cost_basis || 0)),
                sessionId: 1
            });

            // 2. Evento de VENTA (si el trade está cerrado)
            if (t.status === 'CLOSED' && closeDate) {
                const exitReasonMap = {
                    'EMERGENCY_FLATTEN': 'Manual Flatten',
                    'Take Profit': 'Take Profit',
                    'Stop Loss': 'Stop Loss'
                };
                const displayReason = exitReasonMap[t.exit_reason] || t.exit_reason || 'Cierre';
                const sellValue = Number(t.cost_basis) || (Number(t.qty || 0) * Number(t.exit_price || 0));

                serverTrades.push({
                    id: `${t.id}_sell`,
                    timeString: closeDate.toLocaleTimeString(),
                    timestamp: closeDate.toISOString(),
                    signal: 'VENDER',
                    symbol: t.symbol,
                    baseCoin: t.symbol.split('/')[0],
                    price: Number(t.exit_price),
                    qty: Number(t.qty),
                    costBasis: sellValue,
                    strategy: t.strategy || 'trailing_trend_runner',
                    engine: t.engine || 'antigravity_operador',
                    formula: t.formula || 'Quant Risk ATR',
                    status: 'Ejecutada',
                    mode: displayReason,
                    fee: fee / 2,
                    pnl: pnl,
                    balance: vaultUSDT,
                    sessionId: 1
                });
            }
        });

        // Ordenar de más reciente a más antiguo
        serverTrades.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        tradeHistoryLog = serverTrades;
        localStorage.setItem('ai_trade_history_v2', JSON.stringify(tradeHistoryLog));
        renderTradeHistory();
        if (typeof window.updateChartTradeMarkers === 'function') {
            window.updateChartTradeMarkers();
        }
    } catch (err) {
        console.debug('Error sincronizando historial del broker:', err);
    }
}

// --- PROTOCOLO DE PURGA Y CONTROL DE MEMORIA RAM DE OLLAMA ---
window.purgarMemoriaIA = async function(silent = false) {
    if (!silent) logToTerminal("🧹 [PURGA RAM] Desalojando modelos y cancelando tareas en Ollama...", "warn");
    const lobbyReportBox = document.getElementById("lobbyReportBox");
    try {
        const res = await fetch(`${API_BASE_URL}/api/ollama/purge`, {
            method: "POST",
            headers: apiAuthHeaders()
        });
        const data = await res.json();
        const modelsList = (data.unloaded_models && data.unloaded_models.length > 0)
            ? data.unloaded_models.join(", ")
            : "Ninguno en ejecución";
        if (!silent) {
            logToTerminal(`✅ [PURGA RAM] Memoria liberada. Modelos purgados de RAM: ${modelsList}`, "success");
            if (lobbyReportBox) {
                lobbyReportBox.innerHTML = `<span class="text-green-400 font-bold">✅ Memoria RAM liberada con éxito. Modelos desalojados de Ollama: <strong>${escapeHtml(modelsList)}</strong></span>`;
            }
        } else {
            logToTerminal(`🔄 [AUTO-PURGA] Memoria de Ollama liberada para el nuevo motor (${modelsList}).`, "info");
        }
    } catch (err) {
        if (!silent) {
            logToTerminal(`⚠️ [PURGA RAM] Error de conexión al purgar Ollama: ${err.message}`, "error");
            if (lobbyReportBox) {
                lobbyReportBox.innerHTML = `<span class="text-red-400 font-bold">⚠️ Error al purgar memoria: ${escapeHtml(err.message)}</span>`;
            }
        }
    }
};

// --- PRE-MARKET DIGEST LOGIC ---
let premarketAbortController = null;

async function abortPremarketProcess(source = 'lobby') {
    if (premarketAbortController) {
        try {
            premarketAbortController.abort();
        } catch (_) {}
        premarketAbortController = null;
    }
    logToTerminal("🛑 Abortando consulta Pre-Market y liberando memoria RAM...", "warn");
    
    document.getElementById("btnCancelLobbyPremarket")?.classList.add("hidden");
    document.getElementById("btnCancelPremarket")?.classList.add("hidden");

    const btnLobby = document.getElementById("btnLobbyPremarket");
    if (btnLobby) {
        btnLobby.innerHTML = '<span class="animate-pulse">🧠</span> Generar Consenso del Cerebro';
        btnLobby.disabled = false;
    }
    const btnPremkt = document.getElementById("btnPremarket");
    if (btnPremkt) {
        btnPremkt.innerText = "Despertar Cerebro (Pre-Market)";
        btnPremkt.disabled = false;
    }

    const lobbyReportBox = document.getElementById("lobbyReportBox");
    if (lobbyReportBox && source === 'lobby') {
        lobbyReportBox.innerHTML = '<span class="text-red-400 font-bold">🛑 Cancelando proceso y liberando memoria RAM...</span>';
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/macro/premarket/cancel`, {
            method: "POST",
            headers: apiAuthHeaders()
        });
        const data = await res.json();
        logToTerminal(`✅ Pre-Market: ${data.message || 'Memoria RAM liberada'}`, "success");
        if (lobbyReportBox && source === 'lobby') {
            lobbyReportBox.innerHTML = '<span class="text-yellow-400 font-bold">✅ Proceso cancelado. Memoria RAM liberada y modelos descargados con éxito.</span>';
        }
    } catch (e) {
        logToTerminal(`Aviso al cancelar Pre-Market: ${e.message}`, "warn");
    }
}




// Prevenir cambio accidental de selectores (ej. Motor IA) al hacer scroll con la rueda del ratón
document.addEventListener('wheel', (e) => {
    if (document.activeElement && document.activeElement.tagName === 'SELECT') {
        document.activeElement.blur();
    }
}, { passive: true });

// ==============================================================================
// --- MÓDULO DE GESTIÓN DE INVERSORES (CUOTAPARTES NAV EN ARS) ---
// ==============================================================================

const navTradingBtn = document.getElementById('navTradingBtn');
const navInvestorsBtn = document.getElementById('navInvestorsBtn');
const tradingView = document.getElementById('tradingView');
const investorsView = document.getElementById('investorsView');

function formatCurrencyUSD(num) {
    const val = Number(num) || 0.0;
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(val);
}

function showTradingView() {
    if (tradingView) tradingView.classList.remove('hidden');
    if (investorsView) investorsView.classList.add('hidden');
    navTradingBtn?.classList.remove('text-gray-400');
    navTradingBtn?.classList.add('bg-blue-600', 'text-white');
    navInvestorsBtn?.classList.remove('bg-blue-600', 'text-white');
    navInvestorsBtn?.classList.add('text-gray-400');
}

function showInvestorsView() {
    if (tradingView) tradingView.classList.add('hidden');
    if (investorsView) investorsView.classList.remove('hidden');
    navInvestorsBtn?.classList.remove('text-gray-400');
    navInvestorsBtn?.classList.add('bg-blue-600', 'text-white');
    navTradingBtn?.classList.remove('bg-blue-600', 'text-white');
    navTradingBtn?.classList.add('text-gray-400');
    fetchInvestorsData();
}

navTradingBtn?.addEventListener('click', showTradingView);
navInvestorsBtn?.addEventListener('click', showInvestorsView);

async function fetchInvestorsData() {
    const curSelect = document.getElementById('investorCurrencySelect');
    const cur = curSelect ? curSelect.value : (typeof getCurrency === 'function' ? getCurrency(currentSymbol) : 'USDT');
    try {
        const res = await fetch(`${API_BASE_URL}/api/investors?currency=${cur}`, {
            headers: apiAuthHeaders()
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderInvestorsUI(data);
    } catch (err) {
        logToTerminal(`⚠️ Error consultando estado de inversores: ${err.message}`, 'error');
        if (window.UIFeedback) {
            window.UIFeedback.toast(`Error al cargar datos de inversores: ${err.message}`, { type: 'error' });
        }
    }
}

function renderInvestorsUI(data) {
    if (!data) return;
    const cur = data.currency || 'USDT';

    // Métricas en la divisa consultada (USDT / USD / ARS)
    const totalInvestorsDisplay = document.getElementById('invTotalInvestorsDisplay');
    const aumDisplay = document.getElementById('invAumDisplay');
    const brokerBreakdownDisplay = document.getElementById('invBrokerBreakdownDisplay');
    const expensesDisplay = document.getElementById('invExpensesDisplay');
    const netDistDisplay = document.getElementById('invNetDistributableDisplay');
    const sharesDisplay = document.getElementById('invTotalSharesDisplay');
    const navDisplay = document.getElementById('invNavDisplay');
    const reconStatus = document.getElementById('invReconStatus');
    const reconDot = document.getElementById('invReconDot');
    const reconText = document.getElementById('invReconText');
    const reconDiff = document.getElementById('invReconDiff');
    const feeDisplay = document.getElementById('invOperatorFeeDisplay');
    const rateLbl = document.getElementById('lblUsdtArsRate');
    const tbody = document.getElementById('investorsTableBody');
    const expensesTbody = document.getElementById('expensesTableBody');

    const fmtCur = (val) => `$${(Number(val) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${cur}`;

    // Actualizar etiquetas del selector de divisa con el patrimonio real del broker
    const curSelect = document.getElementById('investorCurrencySelect');
    if (curSelect && data.vault_balances) {
        const vb = data.vault_balances;
        for (const opt of curSelect.options) {
            if (opt.value === 'USDT' && vb.USDT !== undefined) {
                opt.textContent = `Divisa: USDT (Broker: $${Number(vb.USDT).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })})`;
            } else if (opt.value === 'USD' && vb.USD !== undefined) {
                opt.textContent = `Divisa: USD (Broker: $${Number(vb.USD).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })})`;
            } else if (opt.value === 'ARS' && vb.ARS !== undefined) {
                opt.textContent = `Divisa: ARS (Broker: $${Number(vb.ARS).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })})`;
            }
        }
    }

    const invTotVal = Number(data.total_investors_balance ?? data?.reconciliation?.investors_total ?? 0);
    const brokerTotVal = Number(data.total_aum ?? data?.reconciliation?.vault_total ?? 0);
    const expensesTotVal = Number(data.total_expenses_usd || 0);
    const netRetirableTotVal = Math.max(0.0, invTotVal - expensesTotVal);

    if (totalInvestorsDisplay) totalInvestorsDisplay.textContent = fmtCur(invTotVal);
    if (aumDisplay) aumDisplay.textContent = fmtCur(brokerTotVal);
    if (brokerBreakdownDisplay) {
        const vCash = Number(data.vault_cash ?? brokerTotVal);
        const vPos = Number(data.in_positions ?? 0);
        brokerBreakdownDisplay.textContent = `Bóveda: $${vCash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} | Activos: $${vPos.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    if (expensesDisplay) expensesDisplay.textContent = `-${fmtCur(expensesTotVal)}`;
    if (netDistDisplay) netDistDisplay.textContent = fmtCur(netRetirableTotVal);
    if (sharesDisplay) sharesDisplay.textContent = fmtCur(data.total_deposited ?? invTotVal);
    if (navDisplay) navDisplay.textContent = `${fmtCur(data.nav || 1.0)} / cuota`;
    if (feeDisplay) feeDisplay.textContent = `${(Number(data.operator_fee_pct) || 0).toFixed(1)}%`;
    if (rateLbl) rateLbl.textContent = (Number(data.usdt_ars_rate) || 1250).toLocaleString('en-US');

    // Guardar tasa global en cache window
    window._currentUsdtArsRate = Number(data.usdt_ars_rate) || 1250;

    // Aviso informativo de Diferencia entre Broker e Inversores (sin mezclar finanzas)
    const recon = data.reconciliation || {};
    const vaultTot = Number(recon.vault_total ?? brokerTotVal) || 0;
    const invTot = Number(recon.investors_total ?? invTotVal) || 0;
    const diff = vaultTot - invTot;

    if (reconStatus && reconText) {
        if (Math.abs(diff) < 0.01) {
            if (reconDot) {
                reconDot.className = 'inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]';
            }
            reconText.textContent = `✅ AJUSTADO 100% ($0.00 dif.)`;
            reconText.className = 'text-xs font-bold text-emerald-400 font-mono';
            if (reconDiff) {
                reconDiff.textContent = `Broker (${fmtCur(vaultTot)}) = Inversores (${fmtCur(invTot)})`;
            }
        } else if (diff > 0) {
            if (reconDot) {
                reconDot.className = 'inline-block w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse';
            }
            reconText.textContent = `ℹ️ BROKER TIENE +${fmtCur(diff)} MÁS`;
            reconText.className = 'text-xs font-bold text-amber-300 font-mono';
            if (reconDiff) {
                reconDiff.textContent = `Suma +${fmtCur(diff)} manualmente a los inversores para igualar`;
            }
        } else {
            if (reconDot) {
                reconDot.className = 'inline-block w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse';
            }
            reconText.textContent = `⚠️ INVERSORES TIENEN +${fmtCur(Math.abs(diff))} MÁS`;
            reconText.className = 'text-xs font-bold text-rose-400 font-mono';
            if (reconDiff) {
                reconDiff.textContent = `Quita/retira ${fmtCur(Math.abs(diff))} manualmente de inversores para igualar`;
            }
        }
    }

    // Renderizar Filas de la Tabla de Inversores (7 columnas claras)
    if (tbody) {
        const investors = data.investors || [];
        if (investors.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="p-6 text-center text-gray-500 font-sans">No hay inversores registrados. Usa "+ Nuevo Inversor" para agregar uno.</td></tr>`;
        } else {
            tbody.innerHTML = investors.map(inv => {
                const netDep = Number(inv.net_deposited ?? inv.total_deposited ?? 0);
                const curBal = Number(inv.current_balance ?? 0);
                const pnlAmt = Number(inv.pnl_amount ?? (curBal - netDep));
                const pnlPct = Number(inv.pnl_pct ?? (netDep > 0 ? (pnlAmt / netDep) * 100 : 0));
                const allocExp = Number(inv.allocated_expenses ?? 0);
                const netRet = Number(inv.net_retirable_balance ?? Math.max(0, curBal - allocExp));
                const safeName = escapeHtml(inv.name).replace(/'/g, "\\'");

                // Estilo y signo de Rendimiento (Verde si gana, Rojo si pierde, Gris si es cero)
                let pnlColor = "text-gray-300";
                let pnlPrefix = "";
                let pnlBadge = "bg-gray-800 text-gray-300 border-gray-700";
                if (pnlAmt > 0.005) {
                    pnlColor = "text-emerald-400";
                    pnlPrefix = "+";
                    pnlBadge = "bg-emerald-950/80 text-emerald-300 border-emerald-600/60";
                } else if (pnlAmt < -0.005) {
                    pnlColor = "text-rose-400";
                    pnlPrefix = "-";
                    pnlBadge = "bg-rose-950/80 text-rose-300 border-rose-600/60";
                }

                return `
                    <tr class="hover:bg-gray-800/80 transition-colors">
                        <td class="p-3 font-sans">
                            <div class="font-bold text-white text-xs">${escapeHtml(inv.name)}</div>
                            <div class="text-[10px] text-gray-400 font-mono">${escapeHtml(inv.alias || inv.name)} · <span class="text-emerald-400 font-bold">${cur}</span></div>
                        </td>
                        <td class="p-3 text-right font-mono">
                            <div class="${pnlColor} font-black text-sm drop-shadow-sm">
                                ${pnlPrefix}${fmtCur(Math.abs(pnlAmt))}
                            </div>
                            <div class="inline-flex items-center gap-1 text-[10px] mt-0.5 px-1.5 py-0.5 rounded border ${pnlBadge} font-bold">
                                <span>${pnlPrefix}${Math.abs(pnlPct).toFixed(2)}%</span>
                            </div>
                            <div class="text-[9px] text-gray-400 mt-0.5" title="Capital base aportado en neto">Base: ${fmtCur(netDep)}</div>
                        </td>
                        <td class="p-3 text-center font-mono">
                            <div class="inline-flex items-center gap-1.5">
                                <div class="w-12 bg-gray-700 rounded-full h-1.5 overflow-hidden">
                                    <div class="bg-blue-500 h-1.5 rounded-full" style="width: ${Math.min(100, inv.share_pct || 0)}%;"></div>
                                </div>
                                <span class="text-xs text-blue-300 font-bold">${(Number(inv.share_pct) || 0).toFixed(1)}%</span>
                            </div>
                        </td>
                        <td class="p-3 text-right font-mono font-extrabold text-cyan-300 text-sm">
                            ${fmtCur(curBal)}
                        </td>
                        <td class="p-3 text-right font-mono font-bold text-rose-400">
                            -${fmtCur(allocExp)}
                        </td>
                        <td class="p-3 text-right font-mono">
                            <div class="font-extrabold text-emerald-400 text-sm">${fmtCur(netRet)}</div>
                            <div class="text-[10px] text-gray-400">${allocExp > 0 ? 'Saldo - Gastos' : '100% del Saldo Actual'}</div>
                        </td>
                        <td class="p-3 text-center">
                            <div class="inline-flex flex-wrap items-center justify-center gap-1.5 font-sans">
                                <button onclick="window.handleInvestorDeposit('${inv.id}', '${safeName}')" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-2 py-1 rounded text-[11px] transition cursor-pointer shadow flex items-center gap-1" title="Ingresar / sumar dinero a este inversor">
                                    <span>➕</span> Ingresar
                                </button>
                                <button onclick="window.handleInvestorWithdrawal('${inv.id}', '${safeName}', ${netRet}, ${curBal}, ${allocExp})" class="bg-amber-600 hover:bg-amber-500 text-white font-bold px-2 py-1 rounded text-[11px] transition cursor-pointer shadow flex items-center gap-1" title="Retirar todo o parte del dinero de este inversor (descontando gastos)">
                                    <span>➖</span> Retirar
                                </button>
                                <button onclick="window.ajustarAporteInversor('${inv.id}', '${safeName}', ${curBal})" class="bg-blue-600 hover:bg-blue-500 text-white font-bold px-2 py-1 rounded text-[11px] transition cursor-pointer shadow flex items-center gap-1" title="Fijar directamente el saldo actual de este inversor">
                                    <span>✏️</span> Fijar
                                </button>
                                <button onclick="window.handleDeleteInvestor('${inv.id}', '${safeName}')" class="bg-rose-700 hover:bg-rose-600 text-white font-bold px-2 py-1 rounded text-[11px] transition cursor-pointer shadow flex items-center gap-1" title="Quitar / eliminar este inversor de la lista">
                                    <span>🗑️</span> Quitar
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        }
    }

    // Renderizar Filas de Gastos Generales & Operativos
    if (expensesTbody) {
        const expenses = data.expenses || [];
        if (expenses.length === 0) {
            expensesTbody.innerHTML = `<tr><td colspan="7" class="p-5 text-center text-gray-500 font-sans">No hay gastos operativos registrados. Utilice el botón "+ Registrar Gasto" para imputar costos de IA, internet, APIs o servidores.</td></tr>`;
        } else {
            const catBadges = {
                'IA': '<span class="bg-purple-950/80 text-purple-300 border border-purple-700/60 px-2 py-0.5 rounded text-[10px] font-bold">🤖 IA</span>',
                'INTERNET': '<span class="bg-cyan-950/80 text-cyan-300 border border-cyan-700/60 px-2 py-0.5 rounded text-[10px] font-bold">🌐 Internet</span>',
                'API': '<span class="bg-amber-950/80 text-amber-300 border border-amber-700/60 px-2 py-0.5 rounded text-[10px] font-bold">🔌 API</span>',
                'SERVIDOR': '<span class="bg-blue-950/80 text-blue-300 border border-blue-700/60 px-2 py-0.5 rounded text-[10px] font-bold">🖥️ VPS</span>',
                'GENERAL': '<span class="bg-gray-800 text-gray-300 border border-gray-600 px-2 py-0.5 rounded text-[10px] font-bold">📁 General</span>',
            };

            expensesTbody.innerHTML = expenses.map(exp => {
                const dateStr = exp.created_at ? new Date(exp.created_at).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' }) : '-';
                const origMontoStr = exp.currency === 'ARS'
                    ? `$${Number(exp.amount).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ARS`
                    : formatCurrencyUSD(exp.amount);
                const rateStr = exp.currency === 'ARS'
                    ? `${(Number(exp.rate_to_usd) || 1250).toFixed(0)} ARS/USD`
                    : '1.0 (Nativo)';
                const badge = catBadges[exp.category] || catBadges['GENERAL'];

                return `
                    <tr class="hover:bg-gray-800/80 transition-colors">
                        <td class="p-3 text-gray-400 text-[11px] whitespace-nowrap">${dateStr}</td>
                        <td class="p-3 font-sans">
                            <div class="font-bold text-white text-xs">${escapeHtml(exp.description)}</div>
                            ${exp.notes ? `<div class="text-[10px] text-gray-400 font-mono">${escapeHtml(exp.notes)}</div>` : ''}
                        </td>
                        <td class="p-3 text-center">${badge}</td>
                        <td class="p-3 text-right font-mono text-gray-300 font-semibold">${origMontoStr}</td>
                        <td class="p-3 text-right font-mono text-gray-400 text-[11px]">${rateStr}</td>
                        <td class="p-3 text-right font-mono font-bold text-rose-400">-${formatCurrencyUSD(exp.amount_usd)}</td>
                        <td class="p-3 text-center">
                            <button onclick="handleDeleteExpense('${exp.id}', '${escapeHtml(exp.description)}')" class="text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 p-1 rounded transition cursor-pointer" title="Eliminar gasto">
                                🗑️
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
        }
    }
}

// Fijar directamente el saldo contable de un inversor (100% independiente del broker)
window.ajustarAporteInversor = async function(investorId, investorName, currentAmount) {
    const curSelect = document.getElementById('investorCurrencySelect');
    const cur = curSelect ? curSelect.value : (typeof getCurrency === 'function' ? getCurrency(currentSymbol) : 'USDT');

    let input;
    if (window.UIFeedback) {
        input = await window.UIFeedback.prompt(
            `Fijar el Dinero Actual que tiene ${investorName} (${cur}):\nEste registro es contable e independiente de las finanzas reales del Broker.`,
            String(Number(currentAmount || 0).toFixed(2)),
            {
                title: `Fijar Saldo de ${investorName} (${cur})`,
                icon: "✏️",
                placeholder: `Monto en ${cur}`,
                inputType: "number"
            }
        );
    } else {
        input = prompt(`Fijar Dinero Actual de ${investorName} (${cur}):`, String(Number(currentAmount || 0).toFixed(2)));
    }
    if (input === null || input === undefined) return;
    const amount = parseFloat(input);
    if (!Number.isFinite(amount) || amount < 0) {
        const msg = "Por favor ingresa un monto numérico mayor o igual a cero.";
        if (window.UIFeedback) window.UIFeedback.toast(msg, { type: "warning" });
        else alert(msg);
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/investors/${investorId}/set-capital`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ amount: amount, currency: cur })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Error al fijar saldo del inversor");

        if (window.UIFeedback) {
            window.UIFeedback.toast(`Saldo de ${investorName} fijado en $${amount.toFixed(2)} ${cur}.`, { type: "success" });
        }
        logToTerminal(`🏛️ [INVERSORES] Saldo contable de ${investorName} fijado en $${amount.toFixed(2)} ${cur}.`, 'action');
        await fetchInvestorsData();
        await updateCapitalDisplay();
    } catch (e) {
        if (window.UIFeedback) {
            window.UIFeedback.toast(e.message, { type: "error", title: "Error al Fijar Saldo" });
        } else {
            alert(e.message);
        }
    }
};

// Ingresar / sumar dinero a un inversor en la divisa seleccionada (independiente del broker)
window.handleInvestorDeposit = async function(investorId, investorName) {
    const curSelect = document.getElementById('investorCurrencySelect');
    const cur = curSelect ? curSelect.value : (typeof getCurrency === 'function' ? getCurrency(currentSymbol) : 'USDT');

    let input;
    if (window.UIFeedback) {
        input = await window.UIFeedback.prompt(
            `Ingresa el monto en ${cur} a sumar al saldo de ${investorName}:\n(No afecta ni mueve el dinero real del Broker).`,
            '100',
            { title: `Ingresar Dinero a ${investorName} (${cur})`, icon: '➕', inputType: 'number', placeholder: `Monto en ${cur}` }
        );
    } else {
        input = prompt(`Ingresa el monto en ${cur} a sumar a ${investorName}:`, '100');
    }
    if (!input) return;
    const amount = parseFloat(input);
    if (isNaN(amount) || amount <= 0) {
        window.UIFeedback?.toast('El monto debe ser un número positivo.', { type: 'warning' });
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/investors/${investorId}/deposit`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ amount: amount, currency: cur, notes: `Ingreso manual en ${cur}` })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al registrar ingreso');

        window.UIFeedback?.toast(`✅ Se sumaron $${amount.toFixed(2)} ${cur} a ${investorName}.`, { type: 'success' });
        logToTerminal(`🏛️ [INVERSORES] ${investorName} ingresó +$${amount.toFixed(2)} ${cur}.`, 'action');
        await fetchInvestorsData();
        await updateCapitalDisplay();
    } catch (e) {
        window.UIFeedback?.toast(`Error en el ingreso: ${e.message}`, { type: 'error' });
    }
};

// Retirar todo o parte del dinero de un inversor (solo descuenta gastos operativos)
window.handleInvestorWithdrawal = async function(investorId, investorName, maxRetirable, currentBalance, allocatedExpenses) {
    const curSelect = document.getElementById('investorCurrencySelect');
    const cur = curSelect ? curSelect.value : (typeof getCurrency === 'function' ? getCurrency(currentSymbol) : 'USDT');
    const curBal = Number(currentBalance ?? maxRetirable ?? 0);
    const expAmt = Number(allocatedExpenses ?? 0);
    const maxNet = Number(maxRetirable ?? Math.max(0, curBal - expAmt));

    if (maxNet <= 0) {
        window.UIFeedback?.toast(`${investorName} no tiene saldo disponible para retirar en ${cur}.`, { type: 'warning' });
        return;
    }

    const defAmount = maxNet.toFixed(2);
    let input;
    if (window.UIFeedback) {
        input = await window.UIFeedback.prompt(
            `Retirar dinero de ${investorName} (${cur}):\n` +
            `• Dinero Actual: $${curBal.toFixed(2)} ${cur}\n` +
            `• Gastos a descontar: -$${expAmt.toFixed(2)} ${cur}\n` +
            `• Máximo para retirar hoy (100% - gastos): $${maxNet.toFixed(2)} ${cur}\n\n` +
            `Deja $${defAmount} para retirar TODO su dinero disponible (su saldo quedará en $0.00), o escribe un monto menor para un retiro parcial:`,
            defAmount,
            { title: `Retirar Dinero de ${investorName} (${cur})`, icon: '➖', inputType: 'number', placeholder: `Hasta ${defAmount} ${cur}` }
        );
    } else {
        input = prompt(`Retirar dinero de ${investorName} (${cur}). Máximo disponible (descontando gastos): $${defAmount}`, defAmount);
    }
    if (!input) return;
    const amount = parseFloat(input);
    if (isNaN(amount) || amount <= 0) {
        window.UIFeedback?.toast('El monto debe ser un número positivo.', { type: 'warning' });
        return;
    }
    if (amount > (maxNet + 0.05)) {
        window.UIFeedback?.toast(`El monto solicitado supera el máximo retirable descontando gastos ($${maxNet.toFixed(2)} ${cur}).`, { type: 'warning' });
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/investors/${investorId}/withdraw`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ amount: amount, currency: cur, notes: `Retiro manual en ${cur}` })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al procesar retiro');

        const msgExtra = data.is_full_withdrawal ? ' (Retiro total completado: saldo en $0.00)' : '';
        window.UIFeedback?.toast(`✅ Retiro de $${amount.toFixed(2)} ${cur} registrado para ${investorName}${msgExtra}.`, { type: 'success' });
        logToTerminal(`🏛️ [INVERSORES] ${investorName} retiró -$${amount.toFixed(2)} ${cur}${msgExtra}.`, 'warn');
        await fetchInvestorsData();
        await updateCapitalDisplay();
    } catch (e) {
        window.UIFeedback?.toast(`Error en el retiro: ${e.message}`, { type: 'error' });
    }
};

// Quitar / Eliminar un Inversor
window.handleDeleteInvestor = async function(investorId, investorName) {
    let ok = false;
    if (window.UIFeedback) {
        ok = await window.UIFeedback.confirm(
            `¿Estás seguro de quitar al inversor "${investorName}" de la lista?\nSe eliminarán su registro y sus movimientos contables (el dinero del Broker no se toca).`,
            { title: `Quitar Inversor: ${investorName}`, icon: '🗑️', confirmText: 'Sí, quitar inversor', isDestructive: true }
        );
    } else {
        ok = confirm(`¿Seguro que deseas quitar al inversor "${investorName}"?`);
    }
    if (!ok) return;

    try {
        const res = await fetch(`${API_BASE_URL}/api/investors/${investorId}`, {
            method: 'DELETE',
            headers: apiAuthHeaders()
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al quitar inversor');

        window.UIFeedback?.toast(`Inversor ${investorName} eliminado de la nómina.`, { type: 'success' });
        logToTerminal(`🏛️ [INVERSORES] Inversor eliminado: ${investorName}.`, 'warn');
        await fetchInvestorsData();
        await updateCapitalDisplay();
    } catch (e) {
        window.UIFeedback?.toast(`Error al eliminar inversor: ${e.message}`, { type: 'error' });
    }
};

// Eliminar Gasto Operativo
window.handleDeleteExpense = async function(expenseId, description) {
    if (!window.UIFeedback) return;
    const ok = await window.UIFeedback.confirm(
        `¿Está seguro de eliminar el gasto "${description}"?\nSe recalcularán inmediatamente los saldos retirables de los inversores.`,
        { title: 'Eliminar Gasto Operativo', icon: '🗑️', confirmText: 'Eliminar', isDestructive: true }
    );
    if (!ok) return;

    try {
        const res = await fetch(`${API_BASE_URL}/api/investors/expenses/${expenseId}`, {
            method: 'DELETE',
            headers: apiAuthHeaders()
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al eliminar gasto');

        window.UIFeedback.toast('Gasto operativo eliminado.', { type: 'success' });
        logToTerminal(`💸 Gasto eliminado: ${description}.`, 'action');
        fetchInvestorsData();
    } catch (e) {
        window.UIFeedback.toast(`Error: ${e.message}`, { type: 'error' });
    }
};

// Control del Modal de Gastos Operativos
const modalExpense = document.getElementById('modalAddExpense');
const btnAddExpense = document.getElementById('btnAddExpense');
const btnCloseExpenseModal = document.getElementById('btnCloseExpenseModal');
const btnCancelExpense = document.getElementById('btnCancelExpense');
const btnSubmitExpense = document.getElementById('btnSubmitExpense');
const inputExpenseAmount = document.getElementById('inputExpenseAmount');
const selectExpenseCurrency = document.getElementById('selectExpenseCurrency');
const inputExpenseRate = document.getElementById('inputExpenseRate');
const containerExpenseRate = document.getElementById('containerExpenseRate');
const previewExpenseUsd = document.getElementById('previewExpenseUsd');

function updateExpensePreview() {
    const amt = parseFloat(inputExpenseAmount?.value || 0);
    const curr = selectExpenseCurrency?.value || 'USD';
    const rate = parseFloat(inputExpenseRate?.value || window._currentUsdtArsRate || 1250);
    if (containerExpenseRate) {
        containerExpenseRate.style.display = curr === 'ARS' ? 'block' : 'none';
    }
    let usd = 0;
    if (curr === 'USD') {
        usd = amt;
    } else {
        usd = rate > 0 ? amt / rate : 0;
    }
    if (previewExpenseUsd) previewExpenseUsd.textContent = `-${formatCurrencyUSD(usd)}`;
}

btnAddExpense?.addEventListener('click', () => {
    if (!modalExpense) return;
    const descInput = document.getElementById('inputExpenseDesc');
    const notesInput = document.getElementById('inputExpenseNotes');
    if (descInput) descInput.value = '';
    if (inputExpenseAmount) inputExpenseAmount.value = '';
    if (notesInput) notesInput.value = '';
    if (selectExpenseCurrency) selectExpenseCurrency.value = 'USD';
    if (inputExpenseRate) inputExpenseRate.value = window._currentUsdtArsRate || 1250;
    updateExpensePreview();
    modalExpense.classList.remove('hidden');
    descInput?.focus();
});

const closeExpenseModal = () => {
    if (modalExpense) modalExpense.classList.add('hidden');
};

btnCloseExpenseModal?.addEventListener('click', closeExpenseModal);
btnCancelExpense?.addEventListener('click', closeExpenseModal);
inputExpenseAmount?.addEventListener('input', updateExpensePreview);
selectExpenseCurrency?.addEventListener('change', updateExpensePreview);
inputExpenseRate?.addEventListener('input', updateExpensePreview);

btnSubmitExpense?.addEventListener('click', async () => {
    const desc = document.getElementById('inputExpenseDesc')?.value?.trim();
    const cat = document.getElementById('selectExpenseCategory')?.value || 'GENERAL';
    const curr = document.getElementById('selectExpenseCurrency')?.value || 'USD';
    const amt = parseFloat(document.getElementById('inputExpenseAmount')?.value || 0);
    const rate = parseFloat(document.getElementById('inputExpenseRate')?.value || 1250);
    const notes = document.getElementById('inputExpenseNotes')?.value?.trim() || '';

    if (!desc) {
        window.UIFeedback?.toast('Por favor ingrese el concepto o descripción del gasto.', { type: 'warning' });
        return;
    }
    if (isNaN(amt) || amt <= 0) {
        window.UIFeedback?.toast('El monto debe ser un número mayor a cero.', { type: 'warning' });
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/investors/expenses`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                description: desc,
                category: cat,
                currency: curr,
                amount: amt,
                rate_to_usd: curr === 'ARS' ? rate : 1.0,
                notes: notes
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al guardar gasto');

        closeExpenseModal();
        window.UIFeedback?.toast(`✅ Gasto registrado: ${desc} (-${formatCurrencyUSD(data.amount_usd)}).`, { type: 'success' });
        logToTerminal(`💸 Gasto Operativo Registrado: ${desc} (${curr} ${amt}) -> -${formatCurrencyUSD(data.amount_usd)}.`, 'warn');
        fetchInvestorsData();
    } catch (e) {
        window.UIFeedback?.toast(`Error: ${e.message}`, { type: 'error' });
    }
});

// Botón Tasa ARS/USD
document.getElementById('btnSetExchangeRate')?.addEventListener('click', async () => {
    if (!window.UIFeedback) return;
    const currentRate = (window._currentUsdtArsRate || 1250).toString();
    const rateStr = await window.UIFeedback.prompt(
        'Modificar tipo de cambio de referencia para gastos en Pesos Argentinos (ARS por cada USD):\n(Ej: 1250 o 1300)',
        currentRate,
        { title: 'Tasa ARS / USD', icon: '💱', inputType: 'number', placeholder: '1250.0' }
    );
    if (!rateStr) return;
    const newRate = parseFloat(rateStr);
    if (isNaN(newRate) || newRate <= 0) {
        window.UIFeedback.toast('La tasa debe ser mayor a cero.', { type: 'warning' });
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/investors/config`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ usdt_ars_rate: newRate })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al guardar tasa');

        window._currentUsdtArsRate = newRate;
        window.UIFeedback.toast(`Tasa ARS/USD actualizada a $${newRate.toLocaleString('es-AR')}.`, { type: 'success' });
        fetchInvestorsData();
    } catch (e) {
        window.UIFeedback.toast(`Error: ${e.message}`, { type: 'error' });
    }
});

// Botón Nuevo Inversor
document.getElementById('btnNewInvestor')?.addEventListener('click', async () => {
    if (!window.UIFeedback) return;
    const name = await window.UIFeedback.prompt('Ingrese el Nombre y Apellido del nuevo inversor:', '', {
        title: 'Crear Inversor',
        icon: '👤',
        placeholder: 'Ej: Carlos Pérez'
    });
    if (!name || !name.trim()) return;

    try {
        const res = await fetch(`${API_BASE_URL}/api/investors`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ name: name.trim(), alias: name.trim() })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al crear inversor');

        window.UIFeedback.toast(`Inversor ${name.trim()} registrado exitosamente.`, { type: 'success' });
        fetchInvestorsData();
    } catch (e) {
        window.UIFeedback.toast(`Error: ${e.message}`, { type: 'error' });
    }
});

// Botón Editar Comisión de Operador
document.getElementById('btnEditOperatorFee')?.addEventListener('click', async () => {
    if (!window.UIFeedback) return;
    const feeStr = await window.UIFeedback.prompt(
        'Modificar porcentaje de Comisión del Operador (Performance Fee) sobre ganancias netas:\n(Ingrese 0 para dejar en 0.0% sin comisiones)',
        '0.0',
        { title: 'Comisión del Operador (%)', icon: '⚙️', inputType: 'number', placeholder: '0.0 a 50.0' }
    );
    if (feeStr === null || feeStr === undefined) return;
    const fee = parseFloat(feeStr);
    if (isNaN(fee) || fee < 0 || fee > 50) {
        window.UIFeedback.toast('La comisión debe ser entre 0% y 50%.', { type: 'warning' });
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/investors/config`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ operator_fee_pct: fee })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al guardar configuración');

        window.UIFeedback.toast(`Comisión de operador configurada en ${fee.toFixed(1)}%.`, { type: 'success' });
        fetchInvestorsData();
    } catch (e) {
        window.UIFeedback.toast(`Error: ${e.message}`, { type: 'error' });
    }
});

document.getElementById('btnRefreshInvestors')?.addEventListener('click', fetchInvestorsData);
document.getElementById('investorModeSelect')?.addEventListener('change', fetchInvestorsData);

document.addEventListener('DOMContentLoaded', () => {
    startBrainSelectorSync();
    // Resolver dinámicamente el host para los enlaces hacia Monitor del Mercado (:8520)
    const host = window.location.hostname || 'localhost';
    document.querySelectorAll('a[href*=":8520"]').forEach((link) => {
        try {
            const url = new URL(link.href, window.location.origin);
            url.hostname = host;
            link.href = url.toString();
        } catch (_) {}
    });
}, { once: true });

// ==============================================================================
// 🎛️ GESTOR TÁCTICO DE ESTRATEGIAS & SUBMÓDULOS (VENTANA Y FEATURE TOGGLES)
// ==============================================================================

window.openStrategyManagerModal = function() {
    const modal = document.getElementById('strategyManagerModal');
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.style.display = 'flex';
    const container = document.getElementById('strategyManagerContainer');
    if (container) container.scrollTop = 0;
    window.loadStrategyManagerConfigs();
};

window.closeStrategyManagerModal = function() {
    const modal = document.getElementById('strategyManagerModal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.style.display = 'none';
};

// Cerrar modal al presionar tecla Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' || e.key === 'Esc') {
        const modal = document.getElementById('strategyManagerModal');
        if (modal && (!modal.classList.contains('hidden') || modal.style.display === 'flex')) {
            window.closeStrategyManagerModal();
        }
    }
});

window.loadStrategyManagerConfigs = async function() {
    const container = document.getElementById('strategyManagerContainer');
    if (!container) return;

    try {
        const res = await fetch(`${API_BASE_URL}/api/estrategias/config`, {
            headers: apiAuthHeaders()
        });
        if (!res.ok) throw new Error('No se pudo cargar la configuración de estrategias');
        const data = await res.json();
        window.renderStrategyManagerCards(data);
    } catch (err) {
        container.innerHTML = `
            <div class="p-4 bg-red-950/60 border border-red-800 rounded-xl text-red-300">
                ⚠️ Error al consultar el gestor de estrategias: ${err.message}
            </div>
        `;
    }
};

const PARAM_HUMAN_LABELS = {
    min_rr_ratio: "R:R Mínimo Neto",
    min_rvol: "RVOL Mín. Institucional",
    fibo_golden_zone_min: "Fibo Zona Dorada Mín.",
    fibo_golden_zone_max: "Fibo Zona Dorada Máx.",
    peluqueo_partial_pct: "Peluqueo TP1 (%)",
    atr_multiplier_sl: "Mult. ATR Stop Loss",
    bear_trap_wick_max: "Mecha Máx. Bear Trap (%)",
    bull_trap_wick_max: "Mecha Máx. Bull Trap (%)",
    rsi_oversold_short_veto: "Veto Sobreventa RSI Cortos",
    rsi_overbought_long_veto: "Veto Sobrecompra RSI Largos",
    factor_atr_stop: "Holgura ATR Stop Loss",
    ticks_seguridad: "Margen Stop (Ticks)",
    tick_size: "Tamaño de Tick ($)",
    min_rejection_wick: "Mecha Mín. Rechazo VWAP (%)",
    vwap_tolerance_pct: "Tolerancia Testeo VWAP (%)",
    first_tp_trim_pct: "Hito Peluqueo TP1 (%)",
    sl_fallback_pct: "Stop Loss Fallback (%)",
    max_rsi_euphoria: "Techo Euforia RSI",
    min_rsi: "Impulso Mín. RSI",
    max_bullish_rsi: "Techo Euforia RSI Compras",
    min_bearish_rsi: "Suelo Sobreventa RSI Cortos",
    elephant_atr_multiplier: "Mult. ATR Vela Elefante",
    max_upper_wick: "Mecha Sup. Máx. Elefante (%)",
    breakeven_trigger_pct: "Disparador Breakeven (%)",
    trailing_dist_pct: "Distancia Trailing (%)",
    donchian_period: "Período Canal Donchian (4H)",
    donchian_period_1d: "Período Canal Donchian (1D)",
    ema_trend_period: "EMA Régimen Macro (4H)",
    ema_trend_period_1d: "EMA Régimen Macro (1D)",
    ema_slope_bars: "Velas Pendiente EMA",
    compression_atr_mult: "Techo Ancho Canal (x ATR)",
    rel_squeeze_mult: "Factor Squeeze vs Mediana 60p",
    volume_ma_mult: "Expansión Volumen Mín. (4H)",
    volume_ma_mult_1d: "Expansión Volumen Mín. (1D)",
    max_wick_pct: "Mecha Contraria Máx. (%)",
    max_bar_atr_mult: "Rango Máx. Vela Climática (x ATR)",
    max_dist_ema50_atr: "Distancia Máx. EMA 50 (x ATR)",
    atr_sl_mult: "Stop Loss 4H Cripto (x ATR)",
    target_tp_atr_mult: "Take Profit 4H Cripto (x ATR)",
    atr_sl_mult_1d: "Stop Loss 1D Acciones (x ATR)",
    target_tp_atr_mult_1d: "Take Profit 1D Acciones (x ATR)",
};

const STRATEGY_PARAM_BINDINGS = {
    donchian_breakout_1h: {
        operar_long: ["donchian_period", "donchian_period_1d"],
        filtro_ema100: ["ema_trend_period", "ema_trend_period_1d"],
        filtro_pendiente_ema: ["ema_slope_bars"],
        filtro_compresion_atr: ["compression_atr_mult", "rel_squeeze_mult"],
        filtro_volumen_expansion: ["volume_ma_mult", "volume_ma_mult_1d"],
        filtro_anti_trampa_mecha: ["max_wick_pct", "max_bar_atr_mult"],
        filtro_no_sobreextension: ["max_dist_ema50_atr"],
    },
    kula_balam_cava_ruiz: {
        operar_long: ["atr_multiplier_sl"],
        fibo_golden_zone: ["fibo_golden_zone_min", "fibo_golden_zone_max"],
        peluqueo_tp1: ["min_rr_ratio", "peluqueo_partial_pct"],
    },
    tres_velas_wyckoff_bulkowski: {
        wyckoff_vpa_volume: ["min_rvol"],
        veto_bull_trap: ["bull_trap_wick_max", "max_bullish_rsi"],
        veto_bear_trap: ["bear_trap_wick_max", "min_bearish_rsi"],
    },
    alex_ruiz_triada_3velas: {
        gatillo_3velas: ["factor_atr_stop", "ticks_seguridad"],
        veto_bear_trap: ["bear_trap_wick_max"],
        veto_bull_trap: ["bull_trap_wick_max"],
        veto_rsi_oversold: ["rsi_oversold_short_veto"],
        veto_cohete_alcista: ["rsi_overbought_long_veto"],
        peluqueo_tp1: ["min_rr_ratio"],
    },
    nasdaq_araujo_vwap: {
        operar_long: ["factor_atr_stop", "ticks_seguridad", "tick_size"],
        filtro_rechazo_vwap: ["min_rejection_wick"],
        filtro_rvol_institucional: ["min_rvol"],
        veto_bear_trap: ["bear_trap_wick_max"],
        veto_rsi_oversold: ["rsi_oversold_short_veto"],
        peluqueo_tp1: ["min_rr_ratio"],
    },
    hyenuk_chu_multibagger: {
        filtro_vela_elefante: ["elephant_atr_multiplier", "max_upper_wick"],
        filtro_rvol_institucional: ["min_rvol"],
        filtro_anti_euforia_rsi: ["max_rsi_euphoria", "min_rsi"],
        stop_estructural_50pct: ["factor_atr_stop", "ticks_seguridad", "tick_size", "sl_fallback_pct"],
        peluqueo_tp1: ["first_tp_trim_pct", "min_rr_ratio"],
    }
};

function formatParamClean(val) {
    if (val === undefined || val === null || val === '') return '';
    if (typeof val === 'number') {
        const rounded = Math.round(val * 10000) / 10000;
        return Number.isInteger(rounded) ? String(rounded) : String(rounded);
    }
    return String(val).trim().replace(',', '.');
}

window.renderStrategyManagerCards = function(configs) {
    const container = document.getElementById('strategyManagerContainer');
    if (!container) return;

    const entries = Object.entries(configs).filter(([sId]) => ALL_TACTICAL_STRATEGIES.some(s => s.id === sId));
    if (entries.length === 0) {
        container.innerHTML = '<p class="text-gray-400 py-4">No hay estrategias configuradas.</p>';
        return;
    }

    const allowedList = typeof window.getAllowedStrategies === 'function' 
        ? window.getAllowedStrategies() 
        : ALL_TACTICAL_STRATEGIES.map(s => s.id);

    container.innerHTML = entries.map(([sId, cfg]) => {
        const isActive = cfg.active !== false;
        const isLiveRunning = allowedList.includes(sId);
        const subList = Object.entries(cfg.sub_strategies || {});
        const paramList = Object.entries(cfg.parameters || {});

        const isLongEnabled = Boolean(cfg.sub_strategies?.operar_long?.enabled ?? cfg.sub_strategies?.operar_long);
        const isShortEnabled = Boolean(cfg.sub_strategies?.operar_short?.enabled ?? cfg.sub_strategies?.operar_short);

        // Estado visual del badge
        let badgeHtml = '';
        if (isLiveRunning) {
            badgeHtml = `<span class="text-[10px] px-2.5 py-0.5 rounded-full font-mono font-bold bg-cyan-950 text-cyan-300 border border-cyan-500 shadow-sm animate-pulse">⚡ OPERANDO EN VIVO</span>`;
        } else if (isActive) {
            badgeHtml = `<span class="text-[10px] px-2 py-0.5 rounded-full font-mono font-bold bg-gray-800 text-gray-300 border border-gray-700">⚪ DISPONIBLE (EN BANCO)</span>`;
        } else {
            badgeHtml = `<span class="text-[10px] px-2 py-0.5 rounded-full font-mono font-bold bg-amber-950/80 text-amber-400 border border-amber-800">📦 ARCHIVADA</span>`;
        }

        const borderStyle = isLiveRunning 
            ? 'border-2 border-cyan-500/80 bg-gray-950/95 shadow-cyan-950/50 shadow-lg' 
            : (isActive ? 'border border-gray-800 bg-gray-900/90' : 'border border-gray-900 bg-gray-950/60 opacity-60');

        const renderedParamKeys = new Set();

        return `
            <div class="${borderStyle} rounded-xl p-3.5 transition space-y-3" id="stratCard_${sId}">
                <!-- Encabezado Acordeón de la estrategia -->
                <div class="flex items-center justify-between flex-wrap gap-2 cursor-pointer select-none" onclick="window.toggleStrategyCardBody('${sId}')">
                    <div class="flex items-center gap-2.5 flex-wrap">
                        <span id="stratChevron_${sId}" class="text-cyan-400 text-xs font-mono transition-transform duration-200">▼</span>
                        <span class="font-bold text-sm text-white hover:text-cyan-300 transition">${cfg.nombre || sId}</span>
                        ${badgeHtml}
                    </div>
                    <div class="flex items-center gap-3" onclick="event.stopPropagation()">
                        <label class="inline-flex items-center gap-1.5 text-xs text-gray-300 cursor-pointer">
                            <input type="checkbox" ${isActive ? 'checked' : ''} onchange="window.toggleStrategyActive('${sId}', this.checked)" class="rounded bg-gray-950 border-gray-700 text-cyan-500 focus:ring-0 w-3.5 h-3.5 cursor-pointer">
                            <span>${isActive ? 'Habilitada' : 'Archivada'}</span>
                        </label>
                    </div>
                </div>

                <!-- Cuerpo Desplegable (Subestrategias y Parámetros Incrustados) -->
                <div id="stratBody_${sId}" class="space-y-3 pt-2 border-t border-gray-800/80">
                    <!-- Barra de Control de Subestrategias y Botones de Acción -->
                    <div class="flex items-center justify-between flex-wrap gap-2 mb-2">
                        <h4 class="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-1.5">
                            <span>🧩</span> Subestrategias & Parámetros Cuantitativos:
                        </h4>
                        <div class="flex items-center gap-2">
                            <button type="button" onclick="window.resetStrategyParams('${sId}')" class="px-2.5 py-1 text-[11px] font-semibold rounded bg-gray-900 hover:bg-gray-800 text-gray-300 hover:text-white transition shadow border border-gray-700 cursor-pointer flex items-center gap-1" title="Restablecer parámetros de fábrica">
                                <span>🔄</span> Reset Fábrica
                            </button>
                            <button type="button" onclick="window.saveStrategyParams('${sId}')" class="px-3 py-1 text-[11px] font-bold rounded bg-cyan-700 hover:bg-cyan-600 text-white transition shadow cursor-pointer flex items-center gap-1">
                                <span>💾</span> Guardar Parámetros
                            </button>
                        </div>
                    </div>

                    <!-- Cuadrícula de Subestrategias con Parámetros Incrustados -->
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                        ${subList.map(([subId, subData]) => {
                            const isSubEnabled = typeof subData === 'object' ? subData.enabled : Boolean(subData);
                            const name = typeof subData === 'object' ? subData.name : subId;
                            const desc = typeof subData === 'object' ? subData.description : '';
                            const boundParams = STRATEGY_PARAM_BINDINGS[sId]?.[subId] || [];

                            boundParams.forEach(k => renderedParamKeys.add(k));

                            let noteHtml = '';
                            if (sId === 'kula_balam_cava_ruiz' && subId === 'operar_long') {
                                noteHtml = '<div class="text-[10px] text-amber-400/90 mt-1 flex items-center gap-1 font-mono"><span>🛡️</span><span>Protección SL (compartida con Operar en Corto):</span></div>';
                            } else if (sId === 'kula_balam_cava_ruiz' && subId === 'operar_short') {
                                noteHtml = '<div class="text-[10px] text-cyan-400/80 mt-1 flex items-center gap-1 font-mono"><span>🛡️</span><span>Protección regulada por Mult. ATR Stop Loss en Operar en Largo</span></div>';
                            } else if (sId === 'nasdaq_araujo_vwap' && subId === 'operar_long') {
                                noteHtml = '<div class="text-[10px] text-amber-400/90 mt-1 flex items-center gap-1 font-mono"><span>🛡️</span><span>Protección y Ticks (compartidos con Operar en Corto):</span></div>';
                            } else if (sId === 'nasdaq_araujo_vwap' && subId === 'operar_short') {
                                noteHtml = '<div class="text-[10px] text-cyan-400/80 mt-1 flex items-center gap-1 font-mono"><span>🛡️</span><span>Protección y Ticks regulados en Operar en Largo</span></div>';
                            } else if (sId === 'donchian_breakout_1h' && subId === 'operar_long') {
                                noteHtml = '<div class="text-[10px] text-amber-400/90 mt-1 flex items-center gap-1 font-mono"><span>📐</span><span>Ventana de canal compartida con Operar en Corto:</span></div>';
                            } else if (sId === 'donchian_breakout_1h' && subId === 'operar_short') {
                                noteHtml = '<div class="text-[10px] text-cyan-400/80 mt-1 flex items-center gap-1 font-mono"><span>📐</span><span>Ventana Donchian regulada en Operar en Largo (solo activa en Cripto &lt;1D)</span></div>';
                            }

                            const isBoxActive = ((sId === 'kula_balam_cava_ruiz' || sId === 'nasdaq_araujo_vwap' || sId === 'donchian_breakout_1h') && subId === 'operar_long')
                                ? (isLongEnabled || isShortEnabled)
                                : isSubEnabled;

                            let subParamsHtml = '';
                            if (boundParams.length > 0) {
                                const gridCols = boundParams.length > 1 ? 'grid-cols-2' : 'grid-cols-1';
                                subParamsHtml = `
                                    <div id="subParamsBox_${sId}_${subId}" class="mt-2.5 pt-2 border-t border-gray-800/80 grid ${gridCols} gap-2 transition-all duration-200 ${isBoxActive ? 'opacity-100' : 'opacity-40 pointer-events-none'}">
                                        ${boundParams.map(pKey => {
                                            const pVal = cfg.parameters?.[pKey] !== undefined ? cfg.parameters[pKey] : '';
                                            const label = PARAM_HUMAN_LABELS[pKey] || pKey;
                                            return `
                                                <div class="bg-gray-900/90 p-1.5 rounded border border-gray-800 focus-within:border-cyan-600 transition">
                                                    <label class="block text-[10px] text-gray-300 font-medium mb-1 truncate" title="${label} (${pKey})">
                                                        ${label}:
                                                    </label>
                                                    <input type="text" inputmode="decimal" id="param_${sId}_${pKey}" value="${formatParamClean(pVal)}" ${!isBoxActive ? 'disabled' : ''} class="w-full bg-gray-950 text-cyan-300 font-mono text-xs px-2 py-1 rounded border border-gray-700 focus:border-cyan-400 focus:outline-none transition disabled:text-gray-500 disabled:bg-gray-900/60">
                                                </div>
                                            `;
                                        }).join('')}
                                    </div>
                                `;
                            }

                            return `
                                <div class="p-3 bg-gray-950/90 border border-gray-800/90 rounded-lg hover:border-gray-700 transition flex flex-col justify-between" id="subCard_${sId}_${subId}">
                                    <div>
                                        <div class="flex items-start gap-2.5">
                                            <input type="checkbox" id="sub_${sId}_${subId}" ${isSubEnabled ? 'checked' : ''} onchange="window.toggleSubStrategy('${sId}', '${subId}', this.checked)" class="mt-0.5 rounded bg-gray-900 border-gray-600 text-cyan-500 focus:ring-0 w-4 h-4 cursor-pointer">
                                            <div class="flex-1 min-w-0">
                                                <div class="flex items-center justify-between gap-2">
                                                    <label for="sub_${sId}_${subId}" class="cursor-pointer select-none font-semibold text-xs text-gray-200 hover:text-cyan-300 transition">
                                                        ${name}
                                                    </label>
                                                    <span id="badge_status_${sId}_${subId}" class="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border transition-colors ${isSubEnabled ? 'bg-cyan-950 text-cyan-300 border-cyan-800' : 'bg-gray-900 text-gray-500 border-gray-800'}">
                                                        ${isSubEnabled ? 'ACTIVO' : 'INACTIVO'}
                                                    </span>
                                                </div>
                                                ${desc ? `<div class="text-[10.5px] text-gray-400 leading-tight mt-1 select-none">${desc}</div>` : ''}
                                                ${noteHtml}
                                            </div>
                                        </div>
                                    </div>
                                    ${subParamsHtml}
                                </div>
                            `;
                        }).join('')}
                    </div>

                    <!-- Parámetros Generales de la Estrategia (si no están mapeados a una subestrategia específica) -->
                    ${(() => {
                        const unmappedParams = paramList.filter(([pKey]) => !renderedParamKeys.has(pKey));
                        if (unmappedParams.length === 0) return '';
                        return `
                            <div class="pt-2.5 border-t border-gray-800/80">
                                <h5 class="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                    <span>⚙️</span> Parámetros Generales de la Estrategia:
                                </h5>
                                <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                                    ${unmappedParams.map(([pKey, pVal]) => `
                                        <div class="bg-gray-950 p-2 rounded border border-gray-800 hover:border-gray-700 transition">
                                            <label class="block text-[10px] text-gray-300 font-medium mb-1 truncate" title="${PARAM_HUMAN_LABELS[pKey] || pKey} (${pKey})">
                                                ${PARAM_HUMAN_LABELS[pKey] || pKey}:
                                            </label>
                                            <input type="text" inputmode="decimal" id="param_${sId}_${pKey}" value="${formatParamClean(pVal)}" class="w-full bg-gray-900 text-cyan-300 font-mono text-xs p-1 rounded border border-gray-700 focus:border-cyan-400 focus:outline-none">
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `;
                    })()}
                </div>
            </div>
        `;
    }).join('');
};

window.toggleStrategyCardBody = function(strategyId) {
    const body = document.getElementById(`stratBody_${strategyId}`);
    const chevron = document.getElementById(`stratChevron_${strategyId}`);
    if (!body) return;
    if (body.classList.contains('hidden')) {
        body.classList.remove('hidden');
        if (chevron) chevron.innerText = '▼';
    } else {
        body.classList.add('hidden');
        if (chevron) chevron.innerText = '▶';
    }
};

window.toggleMarketIntelBody = function() {
    const body = document.getElementById('marketIntelBody');
    const btn = document.getElementById('btnToggleMarketIntel');
    if (!body) return;

    if (body.classList.contains('hidden')) {
        body.classList.remove('hidden');
        if (btn) btn.innerText = '✕ Ocultar';
    } else {
        body.classList.add('hidden');
        if (btn) btn.innerText = '👁️ Mostrar';
    }
};

window.toggleSubStrategy = async function(strategyId, subId, isChecked) {
    // Actualización inmediata visual en el DOM para respuesta instantánea (optimistic UI)
    const badge = document.getElementById(`badge_status_${strategyId}_${subId}`);
    if (badge) {
        if (isChecked) {
            badge.className = 'text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border transition-colors bg-cyan-950 text-cyan-300 border-cyan-800';
            badge.innerText = 'ACTIVO';
        } else {
            badge.className = 'text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border transition-colors bg-gray-900 text-gray-500 border-gray-800';
            badge.innerText = 'INACTIVO';
        }
    }

    // Manejo de parámetros incrustados dependientes
    if ((strategyId === 'kula_balam_cava_ruiz' || strategyId === 'nasdaq_araujo_vwap' || strategyId === 'donchian_breakout_1h') && (subId === 'operar_long' || subId === 'operar_short')) {
        const longChecked = subId === 'operar_long' ? isChecked : Boolean(document.getElementById(`sub_${strategyId}_operar_long`)?.checked);
        const shortChecked = subId === 'operar_short' ? isChecked : Boolean(document.getElementById(`sub_${strategyId}_operar_short`)?.checked);
        const slBox = document.getElementById(`subParamsBox_${strategyId}_operar_long`);
        if (slBox) {
            const shouldBeActive = longChecked || shortChecked;
            if (shouldBeActive) {
                slBox.classList.remove('opacity-40', 'pointer-events-none');
                slBox.classList.add('opacity-100');
                slBox.querySelectorAll('input').forEach(inp => inp.disabled = false);
            } else {
                slBox.classList.remove('opacity-100');
                slBox.classList.add('opacity-40', 'pointer-events-none');
                slBox.querySelectorAll('input').forEach(inp => inp.disabled = true);
            }
        }
    } else {
        const pBox = document.getElementById(`subParamsBox_${strategyId}_${subId}`);
        if (pBox) {
            if (isChecked) {
                pBox.classList.remove('opacity-40', 'pointer-events-none');
                pBox.classList.add('opacity-100');
                pBox.querySelectorAll('input').forEach(inp => inp.disabled = false);
            } else {
                pBox.classList.remove('opacity-100');
                pBox.classList.add('opacity-40', 'pointer-events-none');
                pBox.querySelectorAll('input').forEach(inp => inp.disabled = true);
            }
        }
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/estrategias/toggle_sub`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ strategy_id: strategyId, sub_id: subId, enabled: isChecked })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al conmutar subestrategia');
        
        const stateText = isChecked ? 'activada' : 'desactivada';
        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast(`Subestrategia '${subId}' ${stateText} en ${strategyId}.`, { type: 'success' });
        }
    } catch (e) {
        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast(`Error: ${e.message}`, { type: 'error' });
        }
    }
};

window.saveStrategyParams = async function(strategyId) {
    const inputs = document.querySelectorAll(`[id^="param_${strategyId}_"]`);
    const params = {};
    inputs.forEach(input => {
        const pKey = input.id.replace(`param_${strategyId}_`, '');
        const cleanVal = String(input.value || '').trim().replace(',', '.');
        const val = parseFloat(cleanVal);
        params[pKey] = isNaN(val) ? cleanVal : val;
    });

    try {
        const res = await fetch(`${API_BASE_URL}/api/estrategias/update_params`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ strategy_id: strategyId, parameters: params })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al guardar parámetros');

        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast(`Parámetros de ${strategyId} guardados correctamente.`, { type: 'success' });
        }
    } catch (e) {
        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast(`Error: ${e.message}`, { type: 'error' });
        }
    }
};

window.resetStrategyParams = async function(strategyId) {
    if (!confirm(`¿Restablecer los parámetros y submódulos de "${strategyId}" a los valores originales de fábrica?`)) return;
    try {
        const res = await fetch(`${API_BASE_URL}/api/estrategias/reset_defaults`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ strategy_id: strategyId })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al restablecer valores');

        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast(`Estrategia ${strategyId} restablecida a valores de fábrica.`, { type: 'success' });
        }
        await window.loadStrategyManagerConfigs();
    } catch (e) {
        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast(`Error: ${e.message}`, { type: 'error' });
        }
    }
};

window.toggleStrategyActive = async function(strategyId, isChecked) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/estrategias/toggle_active`, {
            method: 'POST',
            headers: apiAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ strategy_id: strategyId, active: isChecked })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al modificar estado de estrategia');

        const stateText = isChecked ? 'habilitada' : 'archivada';
        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast(`Estrategia ${strategyId} ${stateText}.`, { type: 'info' });
        }
        window.loadStrategyManagerConfigs();
    } catch (e) {
        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast(`Error: ${e.message}`, { type: 'error' });
        }
    }
};

// ==============================================================================
// 📊 AUDITORÍA DE CAMPAÑA (2–4 SEMANAS: AUTO vs OPERADOR PRESENTE)
// ==============================================================================
window._lastCampaignAuditText = '';

function _campaignVerdictBadge(verdict) {
    const v = String(verdict || 'MUESTRA_INSUFICIENTE').toUpperCase();
    if (v === 'CONSERVAR') return '<span class="campaign-verdict-pill campaign-verdict-conservar">CONSERVAR</span>';
    if (v === 'CALIBRAR') return '<span class="campaign-verdict-pill campaign-verdict-calibrar">CALIBRAR</span>';
    if (v === 'PODAR') return '<span class="campaign-verdict-pill campaign-verdict-podar">PODAR</span>';
    return '<span class="campaign-verdict-pill campaign-verdict-muestra">EN MUESTRA</span>';
}

function _renderCampaignTableRows(rows) {
    if (!Array.isArray(rows) || rows.length === 0) {
        return '<tr><td colspan="11" style="text-align:center;color:#94a3b8;">Sin estrategias registradas en este bloque</td></tr>';
    }
    return rows.map((r) => {
        const pnl = Number(r.net_pnl_usd || 0);
        const edge = Number(r.net_arbiter_edge_usd || 0);
        const pnlColor = pnl > 0 ? '#34d399' : (pnl < 0 ? '#f87171' : '#cbd5e1');
        const edgeColor = edge > 0 ? '#34d399' : (edge < 0 ? '#f87171' : '#cbd5e1');
        const pnlTxt = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
        const edgeTxt = `${edge >= 0 ? '+' : ''}$${edge.toFixed(2)}`;
        const titleReason = escapeHtml(r.verdict_reason || '');
        const tfTag = r.timeframe ? `<span style="color:#64748b;">[${escapeHtml(r.timeframe)}]</span>` : '';
        return `
            <tr title="${titleReason}">
                <td style="font-weight:700;color:#f8fafc;">${escapeHtml(r.strategy_id)} ${tfTag}</td>
                <td>${Number(r.evals || 0)}</td>
                <td>${Number(r.raw_fired || 0)}</td>
                <td>${Number(r.eligible || 0)}</td>
                <td>${Number(r.trades_closed || 0)} <span style="color:#64748b;">(${Number(r.trades_open || 0)} ab.)</span></td>
                <td>${Number(r.win_rate_pct || 0).toFixed(1)}%</td>
                <td>${Number(r.profit_factor || 0).toFixed(2)}</td>
                <td>${Number(r.realized_rr || 0).toFixed(2)}</td>
                <td style="color:${pnlColor};font-weight:700;">${pnlTxt}</td>
                <td style="color:${edgeColor};font-weight:700;">${edgeTxt}</td>
                <td>${_campaignVerdictBadge(r.verdict)}</td>
            </tr>
        `;
    }).join('');
}

window.renderCampaignAuditModal = function(data) {
    const container = document.getElementById('campaignAuditContent');
    if (!container) return;
    const report = data?.report || {};
    const camp = report.campaign || {};
    const summ = report.summary || {};
    const sh = summ.shadow || {};
    const infra = report.infrastructure || {};
    const exits = summ.exit_reasons || {};
    const sinceInput = document.getElementById('campaignSinceInput');
    if (sinceInput && !sinceInput.value && camp.since_iso) {
        sinceInput.value = String(camp.since_iso).slice(0, 10);
    }

    const days = Number(summ.days_elapsed || 0);
    const targetDays = Number(summ.target_days || 28);
    const resolved = Number(summ.resolved_events || 0);
    const minRes = Number(summ.min_resolved_events || 15);
    const pct = Math.min(100, Math.max(0, Number(summ.progress_pct || 0)));
    const netPnl = Number(summ.net_pnl_usd || 0);
    const edgeIa = Number(sh.net_arbiter_edge_usd || 0);
    const riskEvCount = Object.values(infra.risk_events || {}).reduce((a, b) => a + Number(b || 0), 0);
    const forcedCount = Number(infra.forced_tf_alerts_count || 0);

    const exitSummary = ['TP', 'SL', 'BREAKEVEN', 'TRAILING', 'TIME_MANUAL'].map((k) => {
        const it = exits[k] || {};
        const val = Number(it.net_pnl_usd || 0);
        return `${k}: ${Number(it.count || 0)} (${val >= 0 ? '+' : ''}$${val.toFixed(2)})`;
    }).join(' · ');

    const shadowRowsHtml = (report.shadow_by_reason || []).slice(0, 8).map((sr) => {
        const ed = Number(sr.edge_usd || 0);
        return `<div class="campaign-snapshot-item">
            <span>${escapeHtml(sr.reason)}</span>
            <span>${Number(sr.vetoed || 0)} vetos · SL=${Number(sr.saved_sl || 0)} / TP=${Number(sr.missed_tp || 0)} / Exp=${Number(sr.expired || 0)} · Edge: <strong style="color:${ed >= 0 ? '#34d399' : '#f87171'}">${ed >= 0 ? '+' : ''}$${ed.toFixed(2)}</strong></span>
        </div>`;
    }).join('');

    container.innerHTML = `
        <div class="campaign-meta-bar">
            <div>
                <div style="font-weight:800;color:#67e8f9;font-size:12px;">${escapeHtml(camp.name || 'Campaña de Enfriamiento')}</div>
                <div style="font-size:10.5px;color:#94a3b8;margin-top:2px;">Desde ${escapeHtml(camp.since_iso || '')} · Modo daemon: ${escapeHtml(camp.daemon_mode || 'auto')} [${escapeHtml(camp.daemon_timeframe || '4h')}] · Regla de enfriamiento ${summ.cooling_complete ? 'COMPLETA' : 'ACTIVA'}</div>
            </div>
            <div style="min-width:210px;flex:0 1 260px;">
                <div style="display:flex;justify-content:space-between;font-size:10.5px;color:#cbd5e1;font-weight:700;">
                    <span>Día ${days.toFixed(1)} / ${targetDays}</span>
                    <span>Eventos resueltos: ${resolved} / ${minRes} (${pct.toFixed(0)}%)</span>
                </div>
                <div class="campaign-progress-track"><div class="campaign-progress-fill" style="width:${pct}%"></div></div>
            </div>
        </div>

        <div class="campaign-summary-grid">
            <div class="campaign-kpi-card">
                <div class="campaign-kpi-label">PnL Neto Campaña</div>
                <div class="campaign-kpi-value" style="color:${netPnl >= 0 ? '#34d399' : '#f87171'};">${netPnl >= 0 ? '+' : ''}$${netPnl.toFixed(2)} USD</div>
                <div class="campaign-kpi-sub">${Number(summ.trades_closed || 0)} cerrados · PF ${Number(summ.profit_factor || 0).toFixed(2)} · WR ${Number(summ.win_rate_pct || 0).toFixed(1)}%</div>
            </div>
            <div class="campaign-kpi-card">
                <div class="campaign-kpi-label">Edge Árbitro IA (Shadow)</div>
                <div class="campaign-kpi-value" style="color:${edgeIa >= 0 ? '#34d399' : '#f87171'};">${edgeIa >= 0 ? '+' : ''}$${edgeIa.toFixed(2)} USD</div>
                <div class="campaign-kpi-sub">${Number(sh.vetoed_total || 0)} vetos (${Number(sh.saved_sl || 0)} SL ahorrados / ${Number(sh.missed_tp || 0)} TP)</div>
            </div>
            <div class="campaign-kpi-card">
                <div class="campaign-kpi-label">Puntos de Fuga (Salidas)</div>
                <div class="campaign-kpi-value" style="font-size:12px;">${Number(summ.total_fees_usd || 0) > 0 ? `Fees $${Number(summ.total_fees_usd).toFixed(2)}` : 'Sin salidas aún'}</div>
                <div class="campaign-kpi-sub">${escapeHtml(exitSummary)}</div>
            </div>
            <div class="campaign-kpi-card">
                <div class="campaign-kpi-label">Salud Infraestructura</div>
                <div class="campaign-kpi-value" style="color:${forcedCount === 0 && riskEvCount === 0 ? '#34d399' : '#fcd34d'};">${forcedCount === 0 && riskEvCount === 0 ? 'OK · Sin alertas' : `${forcedCount} TF / ${riskEvCount} Risk`}</div>
                <div class="campaign-kpi-sub">Alertas TF forzada: ${forcedCount} · RiskEvents: ${riskEvCount}</div>
            </div>
        </div>

        <div>
            <div class="campaign-section-title"><span>⚡ Bloque Auto [${escapeHtml(camp.daemon_timeframe || '4h')}] (Fórmulas Autónomas)</span><span style="font-size:10px;color:#94a3b8;">${(report.auto_strategies || []).length} fórmulas</span></div>
            <div class="campaign-table-wrap">
                <table class="campaign-table">
                    <thead><tr><th>Estrategia</th><th>Velas</th><th>Crudas</th><th>Cand.</th><th>Trades</th><th>WR</th><th>PF</th><th>R:R</th><th>PnL Neto</th><th>Edge IA</th><th>Dictamen</th></tr></thead>
                    <tbody>${_renderCampaignTableRows(report.auto_strategies || [])}</tbody>
                </table>
            </div>
        </div>

        <div>
            <div class="campaign-section-title"><span>🎯 Bloque Presencial (catalogo/operador_presente/)</span><span style="font-size:10px;color:#94a3b8;">${(report.presencial_strategies || []).length} fórmulas</span></div>
            <div class="campaign-table-wrap">
                <table class="campaign-table">
                    <thead><tr><th>Estrategia</th><th>Velas</th><th>Crudas</th><th>Cand.</th><th>Trades</th><th>WR</th><th>PF</th><th>R:R</th><th>PnL Neto</th><th>Edge IA</th><th>Dictamen</th></tr></thead>
                    <tbody>${_renderCampaignTableRows(report.presencial_strategies || [])}</tbody>
                </table>
            </div>
        </div>

        ${shadowRowsHtml ? `<div><div class="campaign-section-title"><span>👻 Desglose Shadow Testing por Motivo de Veto</span></div><div style="display:flex;flex-direction:column;gap:5px;">${shadowRowsHtml}</div></div>` : ''}

        <div>
            <div class="campaign-section-title"><span>📸 Snapshots Históricos Guardados (data/audit_snapshots/)</span></div>
            <div id="campaignSnapshotsList" style="display:flex;flex-direction:column;gap:5px;">
                <div style="color:#94a3b8;font-size:11px;">Cargando historial de snapshots...</div>
            </div>
        </div>
    `;
};

window.renderCampaignSnapshotsList = function(snapshots) {
    const listEl = document.getElementById('campaignSnapshotsList');
    if (!listEl) return;
    if (!Array.isArray(snapshots) || snapshots.length === 0) {
        listEl.innerHTML = '<div class="campaign-snapshot-item"><span>Aún no hay snapshots guardados. Hacé clic en "💾 Guardar Snapshot" cada domingo.</span></div>';
        return;
    }
    listEl.innerHTML = snapshots.slice(0, 10).map((s) => {
        const pnl = Number(s.net_pnl_usd || 0);
        const edge = Number(s.net_arbiter_edge_usd || 0);
        return `<div class="campaign-snapshot-item">
            <span><strong>${escapeHtml(s.filename)}</strong> (${escapeHtml(s.trigger || 'manual')})</span>
            <span>Día ${Number(s.days_elapsed || 0).toFixed(1)} · Resueltos=${Number(s.resolved_events || 0)} · PnL=${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)} · Edge IA=${edge >= 0 ? '+' : ''}$${edge.toFixed(2)}</span>
        </div>`;
    }).join('');
};

window.refreshCampaignAudit = async function() {
    const container = document.getElementById('campaignAuditContent');
    const sinceInput = document.getElementById('campaignSinceInput');
    const sinceVal = sinceInput && sinceInput.value ? sinceInput.value.trim() : '';
    const qs = sinceVal ? `?since=${encodeURIComponent(sinceVal)}` : '';
    try {
        const [repRes, snapRes] = await Promise.all([
            fetch(`${API_BASE_URL}/api/audit/campaign${qs}`),
            fetch(`${API_BASE_URL}/api/audit/campaign/snapshots`),
        ]);
        if (!repRes.ok) throw new Error('Error consultando /api/audit/campaign');
        const repData = await repRes.json();
        window._lastCampaignAuditText = String(repData.text_summary || '');
        window.renderCampaignAuditModal(repData);
        if (snapRes.ok) {
            const snapData = await snapRes.json();
            window.renderCampaignSnapshotsList(snapData.snapshots || []);
        }
    } catch (err) {
        if (container) {
            container.innerHTML = `<div style="padding:12px;border:1px solid #ef4444;border-radius:8px;color:#fecaca;">⚠️ ${escapeHtml(err.message)}</div>`;
        }
    }
};

window.saveCampaignSnapshotNow = async function() {
    const sinceInput = document.getElementById('campaignSinceInput');
    const sinceVal = sinceInput && sinceInput.value ? sinceInput.value.trim() : '';
    const qs = sinceVal ? `?since=${encodeURIComponent(sinceVal)}` : '';
    try {
        const res = await fetch(`${API_BASE_URL}/api/audit/campaign/snapshot${qs}`, {
            method: 'POST',
            headers: apiAuthHeaders(),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'No se pudo guardar el snapshot');
        window.renderCampaignSnapshotsList(data.snapshots || []);
        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast(`Snapshot guardado: ${data.snapshot?.filename_json || 'OK'}`, { type: 'success' });
        }
    } catch (err) {
        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast(`Error snapshot: ${err.message}`, { type: 'error' });
        }
    }
};

window.copyCampaignAuditSummary = async function() {
    const txt = window._lastCampaignAuditText || '';
    if (!txt) return;
    try {
        await navigator.clipboard.writeText(txt);
        if (window.UIFeedback && typeof window.UIFeedback.toast === 'function') {
            window.UIFeedback.toast('Resumen de campaña copiado al portapapeles.', { type: 'success' });
        }
    } catch (_) {}
};

window.openCampaignAuditModal = function() {
    const modal = document.getElementById('campaignAuditModal');
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.style.display = 'flex';
    window.refreshCampaignAudit();
};

window.closeCampaignAuditModal = function() {
    const modal = document.getElementById('campaignAuditModal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.style.display = 'none';
};

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' || e.key === 'Esc') {
        const campModal = document.getElementById('campaignAuditModal');
        if (campModal && (!campModal.classList.contains('hidden') || campModal.style.display === 'flex')) {
            window.closeCampaignAuditModal();
        }
    }
});

// ==============================================================================
// // TODO(FASE5):
// - Slippage dinámico y spread en Paper Trading: simular peor ejecución en órdenes de mercado (0.05% de slippage mínimo + spread del orderbook).
// - Soporte multi-posición: transicionar portfolio.position a portfolio.positions (array indexado por symbol) con límites de exposición por activo y global.
// - Event ledger inmutable: migrar historial_trades.csv a SQLite con checksum sha256 encadenado por fila para auditoría de live trading.
// ==============================================================================
