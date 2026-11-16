/**
 * cio_cockpit.js — Telemetría en Vivo, Detección de Desconexión y Chat Interactivo con Antigravity CIO.
 */

(function () {
    const API_BASE = (window.location.protocol && window.location.hostname)
        ? `${window.location.protocol}//${window.location.hostname}:18767`
        : 'http://127.0.0.1:18767';

    let isConnected = true;
    let pollTimer = null;

    function getAuthHeaders() {
        const token = sessionStorage.getItem('ai_app_token');
        return token ? { 'Content-Type': 'application/json', 'X-API-Token': token } : { 'Content-Type': 'application/json' };
    }

    // Formateador simple de Markdown para el chat
    function formatMarkdown(text) {
        if (!text) return '';
        let escaped = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
        
        // Negritas
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Cursivas
        escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');
        // Código inline
        escaped = escaped.replace(/`([^`]+)`/g, '<code class="bg-gray-900 text-cyan-300 px-1 py-0.5 rounded font-mono text-[11px]">$1</code>');
        // Citas (blockquote)
        escaped = escaped.replace(/^>\s*(.*?)$/gm, '<blockquote class="border-l-2 border-cyan-500 pl-2 my-1 text-cyan-200 italic bg-cyan-950/20 py-0.5 rounded-r">$1</blockquote>');
        // Saltos de línea
        escaped = escaped.replace(/\n/g, '<br>');
        return escaped;
    }

    async function fetchCioTelemetry() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 4000);

            const res = await fetch(`${API_BASE}/api/agent/live-status`, {
                headers: getAuthHeaders(),
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }

            const data = await res.json();
            updateCioUI(data);
            setConnectionStatus(true);
        } catch (err) {
            console.warn('[CIO Cockpit] Error de conexión:', err);
            setConnectionStatus(false, err.message);
        }
    }

    function setConnectionStatus(connected, errorMsg = '') {
        isConnected = connected;
        const banner = document.getElementById('cioDisconnectedBanner');
        const dot = document.getElementById('cioStatusDot');
        const text = document.getElementById('cioStatusText');
        const badge = document.getElementById('cioLivenessBadge');

        if (connected) {
            if (banner) banner.classList.add('hidden');
            if (dot) {
                dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse';
            }
            if (text) {
                text.className = 'font-mono text-emerald-400 font-bold tracking-wider';
                text.textContent = 'CONECTADO';
            }
            if (badge) {
                badge.className = 'flex items-center space-x-2 bg-gray-900 px-3 py-1.5 rounded-md border border-emerald-700/60 text-xs';
            }
        } else {
            // MOSTRAR ALERTA DE DESCONEXIÓN
            if (banner) banner.classList.remove('hidden');
            if (dot) {
                dot.className = 'w-2.5 h-2.5 rounded-full bg-red-500 animate-ping';
            }
            if (text) {
                text.className = 'font-mono text-red-400 font-bold tracking-wider';
                text.textContent = 'DESCONECTADO';
            }
            if (badge) {
                badge.className = 'flex items-center space-x-2 bg-red-950/60 px-3 py-1.5 rounded-md border border-red-700/80 text-xs';
            }
            const engineState = document.getElementById('cioEngineState');
            if (engineState) engineState.textContent = 'Sin enlace';
        }
    }

    function updateCioUI(data) {
        if (!data) return;

        // 1. Estado y Ciclo
        const engineState = document.getElementById('cioEngineState');
        if (engineState) {
            if (data.paused) {
                engineState.textContent = 'Pausado por Operador';
                engineState.className = 'text-sm font-bold text-amber-400';
            } else if (data.is_running) {
                engineState.textContent = 'Vigilancia Activa';
                engineState.className = 'text-sm font-bold text-emerald-400';
            } else {
                engineState.textContent = 'En Pausa / Reposo';
                engineState.className = 'text-sm font-bold text-gray-400';
            }
        }

        const cyclePill = document.getElementById('cioCyclePill');
        if (cyclePill) {
            cyclePill.textContent = `Ciclo #${data.cycle_count || 0}`;
        }

        // 2. Sesión
        const sessionName = document.getElementById('cioSessionName');
        if (sessionName && data.session) {
            sessionName.textContent = data.session.name || 'Sesión no especificada';
            if (data.session.blackout_active) {
                sessionName.className = 'text-[11px] text-amber-400 font-semibold block mt-1 truncate';
            } else {
                sessionName.className = 'text-[11px] text-gray-300 block mt-1 truncate';
            }
        }

        // 3. Bóvedas y Slots
        const vaultsDisplay = document.getElementById('cioVaultsDisplay');
        if (vaultsDisplay && data.vaults) {
            const usdt = Number(data.vaults.USDT || 0).toFixed(2);
            vaultsDisplay.textContent = `${usdt} USDT`;
        }

        const slotsDisplay = document.getElementById('cioSlotsDisplay');
        if (slotsDisplay) {
            slotsDisplay.textContent = `${data.open_positions_count || 0}/4 Slots`;
        }

        // 4. Estrategia y Cerebro Activo
        const strategyDisplay = document.getElementById('cioStrategyDisplay');
        if (strategyDisplay) {
            strategyDisplay.textContent = data.strategy || 'donchian_breakout_1h';
        }

        const brainBadge = document.getElementById('cioBrainBadge');
        if (brainBadge) {
            const eng = data.engine || 'antigravity_operador';
            if (eng === 'antigravity_operador') {
                brainBadge.textContent = '⚡ Operador Nube';
                brainBadge.className = 'text-[9px] bg-amber-950 text-amber-300 border border-amber-800 px-1.5 py-0.5 rounded font-mono font-bold truncate';
            } else if (eng === 'antigravity_cio') {
                brainBadge.textContent = '🛰️ Antigravity CIO';
                brainBadge.className = 'text-[9px] bg-amber-950 text-amber-300 border border-amber-800 px-1.5 py-0.5 rounded font-mono font-bold truncate';
            } else if (eng === 'ollama' || eng === 'qwen') {
                brainBadge.textContent = '🤖 Qwen 2.5';
                brainBadge.className = 'text-[9px] bg-emerald-950 text-emerald-300 border border-emerald-800 px-1.5 py-0.5 rounded font-mono font-bold truncate';
            } else if (eng === 'gemini' || eng === 'ai') {
                brainBadge.textContent = '✨ Gemini Nube';
                brainBadge.className = 'text-[9px] bg-purple-950 text-purple-300 border border-purple-800 px-1.5 py-0.5 rounded font-mono font-bold truncate';
            } else {
                brainBadge.textContent = '⚙️ Modelo Local';
                brainBadge.className = 'text-[9px] bg-gray-800 text-gray-300 border border-gray-700 px-1.5 py-0.5 rounded font-mono font-bold truncate';
            }
        }

        // 5. Próximo hito
        const nextMilestone = document.getElementById('cioNextMilestone');
        if (nextMilestone && data.session) {
            nextMilestone.textContent = data.session.next_milestone || 'En evaluación';
        }

        // 6. Bitácora de acción en tiempo real
        const liveActionLog = document.getElementById('cioLiveActionLog');
        if (liveActionLog) {
            liveActionLog.textContent = data.last_reason || 'Vigilancia continua de microestructura.';
        }

        const lastEvalTime = document.getElementById('cioLastEvalTime');
        if (lastEvalTime) {
            lastEvalTime.textContent = data.time_art || new Date().toLocaleTimeString();
        }

        // 7. Bitácora de pensamiento del Operador Táctico
        const opLog = document.getElementById('operadorLiveActionLog');
        if (opLog) {
            opLog.textContent = `[Ciclo #${data.cycle_count || 0} en ${data.symbol || 'BTC/USDT'}]: ${data.last_signal || 'MANTENER'} → ${data.last_reason || 'Esperando confluencia matemática en velas'}`;
        }
        const opTime = document.getElementById('operadorLiveEvalTime');
        if (opTime) {
            opTime.textContent = data.time_art || new Date().toLocaleTimeString();
        }
    }

    // Envío de mensaje en el chat
    window.sendQuickPrompt = function (text) {
        window.sendCioChatMessage(text);
    };

    window.sendCioChatMessage = async function (explicitText) {
        const input = document.getElementById('cioChatInput');
        const sendBtn = document.getElementById('cioChatSendBtn');
        const container = document.getElementById('cioChatMessages');
        if (!container) return;

        const text = (explicitText || (input ? input.value : '') || 'Generar Reporte CIO').trim();
        if (!text) return;

        // 1. Mostrar mensaje del usuario
        const userMsgDiv = document.createElement('div');
        userMsgDiv.className = 'flex items-start justify-end space-x-2';
        userMsgDiv.innerHTML = `
            <div class="bg-cyan-900/60 text-cyan-100 p-2.5 rounded-lg border border-cyan-700/60 max-w-[85%] leading-relaxed shadow">
                <p class="font-semibold text-cyan-300 text-[10px] mb-0.5">Operador (Tú)</p>
                <div>${formatMarkdown(text)}</div>
            </div>
            <div class="w-6 h-6 rounded-full bg-gray-700 flex items-center justify-center shrink-0 text-white font-bold text-[10px]">TÚ</div>
        `;
        container.appendChild(userMsgDiv);
        container.scrollTop = container.scrollHeight;

        if (input) input.value = '';
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.classList.add('opacity-50');
            sendBtn.innerHTML = '<span>Consultando...</span>';
        }

        // Placeholder de respuesta de la IA
        const typingDiv = document.createElement('div');
        typingDiv.className = 'flex items-start space-x-2';
        typingDiv.id = 'cioTypingPlaceholder';
        typingDiv.innerHTML = `
            <div class="w-6 h-6 rounded-full bg-cyan-600 flex items-center justify-center shrink-0 text-white font-bold text-[10px]">CIO</div>
            <div class="bg-gray-800 text-gray-400 p-2.5 rounded-lg border border-gray-700 max-w-[85%] leading-relaxed flex items-center gap-2 italic">
                <span class="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping"></span> Obteniendo telemetría estratégica y libro contable...
            </div>
        `;
        container.appendChild(typingDiv);
        container.scrollTop = container.scrollHeight;

        try {
            const res = await fetch(`${API_BASE}/api/agent/chat`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ message: text })
            });

            const placeholder = document.getElementById('cioTypingPlaceholder');
            if (placeholder) placeholder.remove();

            if (!res.ok) {
                throw new Error(`Error en el servidor: HTTP ${res.status}`);
            }

            const data = await res.json();

            // Mensaje de respuesta del Agente
            const agentMsgDiv = document.createElement('div');
            agentMsgDiv.className = 'flex items-start space-x-2';
            agentMsgDiv.innerHTML = `
                <div class="w-6 h-6 rounded-full bg-cyan-600 flex items-center justify-center shrink-0 text-white font-bold text-[10px]">CIO</div>
                <div class="bg-gray-800 text-gray-200 p-2.5 rounded-lg border border-gray-700 max-w-[85%] leading-relaxed shadow">
                    <div class="flex items-center justify-between mb-1">
                        <p class="font-semibold text-cyan-400 text-[11px]">CIO</p>
                        <span class="text-[9px] text-gray-500 font-mono">${new Date().toLocaleTimeString()}</span>
                    </div>
                    <div class="text-xs text-gray-300 leading-relaxed">${formatMarkdown(data.reply || '')}</div>
                </div>
            `;
            container.appendChild(agentMsgDiv);
            container.scrollTop = container.scrollHeight;
            if (['PAUSE', 'RESUME', 'DIRECTIVE_INJECTED'].includes(data.action)) {
                fetchCioTelemetry();
            }
        } catch (err) {
            const placeholder = document.getElementById('cioTypingPlaceholder');
            if (placeholder) placeholder.remove();

            const errDiv = document.createElement('div');
            errDiv.className = 'p-2 bg-red-950/60 border border-red-700 rounded text-red-300 text-xs';
            errDiv.innerHTML = `⚠️ No se pudo comunicar con el CIO: ${formatMarkdown(err.message)}`;
            container.appendChild(errDiv);
            container.scrollTop = container.scrollHeight;
        } finally {
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.classList.remove('opacity-50');
                sendBtn.innerHTML = '<span>📋 Generar Reporte CIO</span>';
            }
        }
    };

    // --- OPERACIONES DEL CEREBRO OPERADOR TÁCTICO (NUEVA VENTANA SUPERIOR) ---
    window.clearOperadorChat = function () {
        const container = document.getElementById('operadorChatMessages');
        if (container) {
            container.innerHTML = `
                <div class="flex items-start space-x-2">
                    <div class="w-6 h-6 rounded-full bg-amber-600 flex items-center justify-center shrink-0 text-white font-bold text-[10px]">OP</div>
                    <div class="bg-gray-800 text-gray-200 p-2.5 rounded-lg border border-gray-700 max-w-[85%] leading-relaxed shadow">
                        <p class="font-semibold text-amber-400 text-[11px] mb-1">Operador · Trinchera Cuantitativa</p>
                        ¡Historial reseteado! Estoy vigilando la vela actual con 0% de uso de CPU local. Escríbeme tu consulta u orden.
                    </div>
                </div>
            `;
        }
    };

    window.sendOperadorQuickPrompt = function (text) {
        window.sendOperadorChatMessage(text);
    };

    window.sendOperadorChatMessage = async function (explicitText) {
        const input = document.getElementById('operadorChatInput');
        const sendBtn = document.getElementById('operadorChatSendBtn');
        const container = document.getElementById('operadorChatMessages');
        if (!container) return;

        const text = (explicitText || (input ? input.value : '') || 'Generar Reporte de Estado').trim();
        if (!text) return;

        // 1. Mostrar solicitud
        const userMsgDiv = document.createElement('div');
        userMsgDiv.className = 'flex items-start justify-end space-x-2';
        userMsgDiv.innerHTML = `
            <div class="bg-amber-950/60 text-amber-100 p-2.5 rounded-lg border border-amber-700/60 max-w-[85%] leading-relaxed shadow">
                <p class="font-semibold text-amber-300 text-[10px] mb-0.5">Operador (Tú)</p>
                <div>${formatMarkdown(text)}</div>
            </div>
            <div class="w-6 h-6 rounded-full bg-gray-700 flex items-center justify-center shrink-0 text-white font-bold text-[10px]">TÚ</div>
        `;
        container.appendChild(userMsgDiv);
        container.scrollTop = container.scrollHeight;

        if (input) input.value = '';
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.classList.add('opacity-50');
            sendBtn.innerHTML = '<span>Consultando...</span>';
        }

        // Placeholder animado
        const typingDiv = document.createElement('div');
        typingDiv.className = 'flex items-start space-x-2';
        typingDiv.id = 'operadorTypingPlaceholder';
        typingDiv.innerHTML = `
            <div class="w-6 h-6 rounded-full bg-amber-600 flex items-center justify-center shrink-0 text-white font-bold text-[10px]">OP</div>
            <div class="bg-gray-800 text-gray-400 p-2.5 rounded-lg border border-gray-700 max-w-[85%] leading-relaxed flex items-center gap-2 italic">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping"></span> Obteniendo estado y telemetría de patrullaje en vivo...
            </div>
        `;
        container.appendChild(typingDiv);
        container.scrollTop = container.scrollHeight;

        try {
            const res = await fetch(`${API_BASE}/api/agent/chat`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ message: text })
            });

            const placeholder = document.getElementById('operadorTypingPlaceholder');
            if (placeholder) placeholder.remove();

            if (!res.ok) {
                throw new Error(`Error en el servidor: HTTP ${res.status}`);
            }

            const data = await res.json();

            const agentMsgDiv = document.createElement('div');
            agentMsgDiv.className = 'flex items-start space-x-2';
            agentMsgDiv.innerHTML = `
                <div class="w-6 h-6 rounded-full bg-amber-600 flex items-center justify-center shrink-0 text-white font-bold text-[10px]">OP</div>
                <div class="bg-gray-800 text-gray-200 p-2.5 rounded-lg border border-gray-700 max-w-[85%] leading-relaxed shadow">
                    <div class="flex items-center justify-between mb-1">
                        <p class="font-semibold text-amber-400 text-[11px]">Operador</p>
                        <span class="text-[9px] text-gray-500 font-mono">${new Date().toLocaleTimeString()}</span>
                    </div>
                    <div class="text-xs text-gray-300 leading-relaxed">${formatMarkdown(data.reply || '')}</div>
                </div>
            `;
            container.appendChild(agentMsgDiv);
            container.scrollTop = container.scrollHeight;
            if (['PAUSE', 'RESUME', 'DIRECTIVE_INJECTED'].includes(data.action)) {
                fetchCioTelemetry();
            }
        } catch (err) {
            const placeholder = document.getElementById('operadorTypingPlaceholder');
            if (placeholder) placeholder.remove();

            const errDiv = document.createElement('div');
            errDiv.className = 'p-2 bg-red-950/60 border border-red-700 rounded text-red-300 text-xs';
            errDiv.innerHTML = `⚠️ No se pudo comunicar con el Operador: ${formatMarkdown(err.message)}`;
            container.appendChild(errDiv);
            container.scrollTop = container.scrollHeight;
        } finally {
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.classList.remove('opacity-50');
                sendBtn.innerHTML = '<span>📋 Generar Reporte de Estado</span>';
            }
        }
    };

    window.reconnectCio = function () {
        fetchCioTelemetry();
    };

    window.refreshCioTelemetry = function () {
        fetchCioTelemetry();
    };

    // Iniciar polling al cargar
    document.addEventListener('DOMContentLoaded', () => {
        fetchCioTelemetry();
        pollTimer = setInterval(fetchCioTelemetry, 3500);
    });

    // Si ya cargó el DOM
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        fetchCioTelemetry();
        if (!pollTimer) {
            pollTimer = setInterval(fetchCioTelemetry, 3500);
        }
    }
})();
