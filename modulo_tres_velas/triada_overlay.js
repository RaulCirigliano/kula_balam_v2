/* ============================================================================
 * KULA BALAM · MOTOR DE OVERLAYS (5 PUNTOS DE LA TRÍADA) & EJECUCIÓN ASISTIDA
 * Compatible con navegador (window.TriadaOverlayEngine) y Node.js (module.exports)
 * ============================================================================ */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.TriadaOverlayEngine = api;
  }
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  function normalizeTriadaSymbol(raw) {
    const s = String(raw || '').trim().toUpperCase();
    if (!s) return 'BTC/USDT';
    if (s.includes('/')) return s.replace(/\/+/g, '/');
    if (s.endsWith('USDT') && s.length > 4) {
      return s.slice(0, -4) + '/USDT';
    }
    return s;
  }

  function formatPx(val, pxDec) {
    const num = Number(val);
    if (!Number.isFinite(num)) return '--';
    const dec = Number.isInteger(pxDec) ? pxDec : (Math.abs(num) < 10 ? 5 : 2);
    return num.toLocaleString('en-US', {
      minimumFractionDigits: dec,
      maximumFractionDigits: dec,
    });
  }

  function escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /**
   * Calcula la geometría vertical (top, height) de la franja Fibonacci 0.50–0.75
   * a partir de coordenadas de píxeles de LightweightCharts.
   */
  function computeFiboBandGeometry(coordA, coordB, containerHeight) {
    if (
      typeof coordA !== 'number' ||
      typeof coordB !== 'number' ||
      !Number.isFinite(coordA) ||
      !Number.isFinite(coordB) ||
      !(containerHeight > 0)
    ) {
      return { visible: false, top: 0, height: 0 };
    }
    const rawTop = Math.min(coordA, coordB);
    const rawBottom = Math.max(coordA, coordB);
    const clampedTop = Math.max(0, Math.min(containerHeight, rawTop));
    const clampedBottom = Math.max(0, Math.min(containerHeight, rawBottom));
    const height = Math.max(0, clampedBottom - clampedTop);
    if (height < 1) {
      return { visible: false, top: clampedTop, height: 0 };
    }
    return {
      visible: true,
      top: Math.round(clampedTop * 10) / 10,
      height: Math.round(height * 10) / 10,
    };
  }

  /**
   * Transforma la respuesta de GET /api/triada/evaluate en descriptores puros y testeables
   * para los 5 puntos sobre velas y la tarjeta de ejecución asistida.
   */
  function buildTriadaOverlayDescriptors(snapshot) {
    if (!snapshot || snapshot.status !== 'ok') {
      return {
        valid: false,
        lines1D: [],
        lines1H: [],
        lines5M: [],
        fiboBand: null,
        atrBadge: null,
        candleMarker: null,
        legend1HText: '',
        executionCard: {
          canExecute: false,
          blockReasons: [snapshot && snapshot.error ? snapshot.error : 'Sin evaluación de Tríada.'],
          plan: null,
          simLines: [],
        },
      };
    }

    const ov = snapshot.overlays || {};
    const pxDec = Number.isInteger(snapshot.px_dec) ? snapshot.px_dec : 2;
    const r0 = ov.rule0_macro_1d || {};
    const r12 = ov.rules12_structure_1h || {};
    const r3 = ov.rule3_fibo_golden_zone || {};
    const r4 = ov.rule4_atr_switch || {};
    const r5 = ov.rule5_wick_and_candlestick || {};

    const lines1D = [];
    if (Number.isFinite(Number(r0.ema50_1d)) && Number(r0.ema50_1d) > 0) {
      lines1D.push({
        price: Number(r0.ema50_1d),
        color: r0.ok ? '#10b981' : '#ef4444',
        lineWidth: 2,
        lineStyle: 'dashed',
        title: r0.label || (r0.ok ? 'EMA50 1D (✅)' : 'EMA50 1D (❌)'),
      });
    }

    const lines1H = [];
    if (Number.isFinite(Number(r12.ema50_1h)) && Number(r12.ema50_1h) > 0) {
      lines1H.push({
        price: Number(r12.ema50_1h),
        color: r12.rule1_ok ? '#f59e0b' : '#f43f5e',
        lineWidth: 1.5,
        lineStyle: 'dashed',
        title: `EMA50 1H (${r12.rule1_ok ? '✅' : '❌'})`,
      });
    }

    const fiboLines = [];
    if (Number.isFinite(Number(r3.swing_high)) && Number(r3.swing_high) > 0) {
      fiboLines.push({
        price: Number(r3.swing_high),
        color: '#94a3b8',
        lineWidth: 1,
        lineStyle: 'dotted',
        title: `Swing High $${formatPx(r3.swing_high, pxDec)}`,
      });
    }
    if (Number.isFinite(Number(r3.swing_low)) && Number(r3.swing_low) > 0) {
      fiboLines.push({
        price: Number(r3.swing_low),
        color: '#94a3b8',
        lineWidth: 1,
        lineStyle: 'dotted',
        title: `Swing Low $${formatPx(r3.swing_low, pxDec)}`,
      });
    }
    if (Number.isFinite(Number(r3.fibo_50)) && Number(r3.fibo_50) > 0) {
      fiboLines.push({
        price: Number(r3.fibo_50),
        color: '#f59e0b',
        lineWidth: 1.5,
        lineStyle: 'dashed',
        title: `Fibo 0.50 Zona Dorada (${r3.ok ? '✅' : '•'})`,
      });
    }
    if (Number.isFinite(Number(r3.fibo_75)) && Number(r3.fibo_75) > 0) {
      fiboLines.push({
        price: Number(r3.fibo_75),
        color: '#ef4444',
        lineWidth: 2,
        lineStyle: 'dotted',
        title: 'Fibo 0.75 INVALIDACIÓN',
      });
    }

    lines1H.push(...fiboLines);
    const lines5M = fiboLines.filter((x) => x.title.startsWith('Fibo'));

    const fiboBand =
      Number.isFinite(Number(r3.zone_min)) &&
      Number.isFinite(Number(r3.zone_max)) &&
      Number(r3.zone_max) > Number(r3.zone_min)
        ? {
            zoneMin: Number(r3.zone_min),
            zoneMax: Number(r3.zone_max),
            ok: Boolean(r3.ok),
            label: `Zona Dorada Fibo 0.50–0.75 (${r3.ok ? 'ACTIVA ✅' : 'FUERA'})`,
          }
        : null;

    const isExp = String(r4.regime || '').toUpperCase() === 'EXPANSION';
    const atrBadge = {
      regime: isExp ? 'EXPANSION' : 'COMPRESSION',
      text: r4.badge_text || (isExp ? 'EXPANSION (Retroceso)' : 'COMPRESSION (Ruptura)'),
      ok: Boolean(r4.ok),
      atr: Number(r4.atr_tactical || 0),
      atrSma: Number(r4.atr_sma_tactical || 0),
    };

    const isWickVeto = Boolean(r5.wick_veto_active);
    const candleMarker = {
      time: Number(r5.last_candle_ts || 0),
      wickVetoActive: isWickVeto,
      wickVetoReason: r5.wick_veto_reason || null,
      position: isWickVeto ? 'aboveBar' : (snapshot.evaluated_side === 'SHORT' ? 'aboveBar' : 'belowBar'),
      color: isWickVeto ? '#ef4444' : '#38bdf8',
      shape: isWickVeto ? 'arrowDown' : 'circle',
      text: r5.marker_text || (isWickVeto ? '⚠️ VETO MECHA >= 50%' : `${r5.pattern_name || 'Vela'} · RVOL ${Number(r5.rvol || 1).toFixed(2)}x`),
      size: isWickVeto ? 1.5 : 1.2,
    };

    const plan = snapshot.execution_plan || null;
    const sim = plan && plan.active_manual_sim ? plan.active_manual_sim : null;
    const simLines = [];
    if (sim && Number(sim.entry_price) > 0) {
      simLines.push({
        price: Number(sim.entry_price),
        color: '#38bdf8',
        lineWidth: 2,
        lineStyle: 'dashed',
        title: `⚡ SIM ENTRADA (${sim.side}) $${formatPx(sim.entry_price, pxDec)}`,
      });
      if (Number(sim.sl_price) > 0) {
        simLines.push({
          price: Number(sim.sl_price),
          color: '#ef4444',
          lineWidth: 2,
          lineStyle: 'solid',
          title: `🛑 SIM SL (-${Number(sim.initial_sl_pct || 0).toFixed(2)}%) $${formatPx(sim.sl_price, pxDec)}`,
        });
      }
      if (Number(sim.tp_price) > 0) {
        simLines.push({
          price: Number(sim.tp_price),
          color: '#10b981',
          lineWidth: 2,
          lineStyle: 'solid',
          title: `🎯 SIM TP (+${Number(sim.initial_tp_pct || 0).toFixed(2)}%) $${formatPx(sim.tp_price, pxDec)}`,
        });
      }
    }

    return {
      valid: true,
      lines1D,
      lines1H,
      lines5M,
      fiboBand,
      atrBadge,
      candleMarker,
      legend1HText: r12.label || '',
      series1H: {
        ema50: Array.isArray(r12.series_ema50) ? r12.series_ema50 : [],
        ema21: Array.isArray(r12.series_ema21) ? r12.series_ema21 : [],
        ema89: Array.isArray(r12.series_ema89) ? r12.series_ema89 : [],
      },
      executionCard: {
        canExecute: Boolean(plan && plan.can_execute),
        blockReasons: Array.isArray(plan && plan.block_reasons) ? plan.block_reasons : [],
        plan,
        simLines,
      },
    };
  }

  // ==========================================================================
  // Controlador DOM / LightweightCharts (solo activo en navegador)
  // ==========================================================================
  const state = {
    visible: true,
    lastSnapshot: null,
    lastDescriptors: null,
    ctx: null,
    priceLines: { s1D: [], s1H: [], s5M: [] },
    simPriceLines: { s1D: [], s1H: [], s5M: [] },
    emaSeries1H: { ema50: null, ema21: null, ema89: null },
    boundCharts: false,
  };

  function toLwLineStyle(styleName) {
    if (typeof LightweightCharts === 'undefined' || !LightweightCharts.LineStyle) return 0;
    if (styleName === 'dashed') return LightweightCharts.LineStyle.Dashed;
    if (styleName === 'dotted') return LightweightCharts.LineStyle.Dotted;
    return LightweightCharts.LineStyle.Solid;
  }

  function clearLineGroup(groupObj, ctx) {
    if (!ctx) return;
    [
      { k: 's1D', s: ctx.series1D },
      { k: 's1H', s: ctx.series1H },
      { k: 's5M', s: ctx.series5M },
    ].forEach(({ k, s }) => {
      if (!s) return;
      (groupObj[k] || []).forEach((line) => {
        try {
          s.removePriceLine(line);
        } catch (_) {}
      });
      groupObj[k] = [];
    });
  }

  function ensureEmaSeries1H(chart1H) {
    if (!chart1H || typeof chart1H.addLineSeries !== 'function') return;
    if (!state.emaSeries1H.ema50) {
      state.emaSeries1H.ema50 = chart1H.addLineSeries({
        color: '#f59e0b',
        lineWidth: 2,
        title: 'EMA 50 (1H)',
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    if (!state.emaSeries1H.ema21) {
      state.emaSeries1H.ema21 = chart1H.addLineSeries({
        color: '#22d3ee',
        lineWidth: 1.5,
        title: 'EMA 21 (1H)',
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    if (!state.emaSeries1H.ema89) {
      state.emaSeries1H.ema89 = chart1H.addLineSeries({
        color: '#e879f9',
        lineWidth: 1.5,
        lineStyle: toLwLineStyle('dashed'),
        title: 'EMA 89 (1H)',
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
  }

  function ensureOverlayEl(containerId, overlayId, className) {
    if (typeof document === 'undefined') return null;
    const container = document.getElementById(containerId);
    if (!container) return null;
    let el = document.getElementById(overlayId);
    if (!el) {
      el = document.createElement('div');
      el.id = overlayId;
      el.className = className;
      container.appendChild(el);
    }
    return el;
  }

  function updateFiboBandOverlay(containerId, overlayId, series, fiboBand) {
    const el = ensureOverlayEl(
      containerId,
      overlayId,
      'pointer-events-none absolute left-0 right-[68px] z-[4] border-y border-amber-400/60 transition-opacity'
    );
    if (!el) return;
    if (!state.visible || !fiboBand || !series || typeof series.priceToCoordinate !== 'function') {
      el.style.display = 'none';
      return;
    }
    const container = document.getElementById(containerId);
    const h = container ? container.clientHeight : 0;
    const yTop = series.priceToCoordinate(fiboBand.zoneMax);
    const yBot = series.priceToCoordinate(fiboBand.zoneMin);
    const geom = computeFiboBandGeometry(yTop, yBot, h);
    if (!geom.visible) {
      el.style.display = 'none';
      return;
    }
    el.style.display = 'block';
    el.style.top = `${geom.top}px`;
    el.style.height = `${geom.height}px`;
    el.style.background = fiboBand.ok
      ? 'rgba(16, 185, 129, 0.14)'
      : 'rgba(245, 158, 11, 0.14)';
    el.style.borderColor = fiboBand.ok
      ? 'rgba(16, 185, 129, 0.55)'
      : 'rgba(245, 158, 11, 0.50)';
    el.innerHTML = `<span style="position:absolute;right:6px;top:2px;font-size:9px;font-family:monospace;font-weight:700;color:${fiboBand.ok ? '#34d399' : '#fbbf24'};background:rgba(15,23,42,0.75);padding:1px 5px;border-radius:4px;">${escapeHtml(fiboBand.label)}</span>`;
  }

  function updateAtrAndWickBadges(desc) {
    const badgeEl = ensureOverlayEl(
      'chart-container-5m',
      'triada-atr-badge-5m',
      'pointer-events-none absolute top-2 right-[76px] z-[6] flex flex-col items-end gap-1'
    );
    if (!badgeEl) return;
    if (!state.visible || !desc || !desc.valid) {
      badgeEl.style.display = 'none';
      return;
    }
    badgeEl.style.display = 'flex';
    const atr = desc.atrBadge;
    const mk = desc.candleMarker;
    const isExp = atr && atr.regime === 'EXPANSION';
    const atrHtml = atr
      ? `<div title="ATR táctico: ${atr.atr} vs SMA20: ${atr.atrSma}" style="font-size:10px;font-family:monospace;font-weight:800;padding:2px 7px;border-radius:6px;border:1px solid ${isExp ? 'rgba(16,185,129,0.6)' : 'rgba(245,158,11,0.6)'};background:${isExp ? 'rgba(6,78,59,0.88)' : 'rgba(120,53,15,0.88)'};color:${isExp ? '#6ee7b7' : '#fcd34d'};">${isExp ? '🟢' : '🟠'} R4: ${escapeHtml(atr.text)}</div>`
      : '';
    const wickHtml =
      mk && mk.wickVetoActive
        ? `<div title="${escapeHtml(mk.wickVetoReason || '')}" style="font-size:10px;font-family:monospace;font-weight:800;padding:2px 7px;border-radius:6px;border:1px solid rgba(239,68,68,0.8);background:rgba(127,29,29,0.92);color:#fecaca;">⚠️ VETO MECHA >= 50%</div>`
        : mk
          ? `<div style="font-size:9.5px;font-family:monospace;font-weight:700;padding:2px 6px;border-radius:6px;border:1px solid rgba(56,189,248,0.45);background:rgba(15,23,42,0.86);color:#bae6fd;">🕯️ ${escapeHtml(mk.text)}</div>`
          : '';
    badgeEl.innerHTML = atrHtml + wickHtml;
  }

  function applyTriadaMarkerOn5M(desc, ctx) {
    if (!ctx || !ctx.series5M || typeof ctx.series5M.setMarkers !== 'function') return;
    const rawBase =
      typeof window !== 'undefined' && window.lastCalculatedMarkers
        ? window.lastCalculatedMarkers.trigger
        : null;
    const baseMarkers = Array.isArray(rawBase) ? rawBase.slice() : [];

    if (!state.visible || !desc || !desc.valid || !desc.candleMarker) {
      try {
        ctx.series5M.setMarkers(baseMarkers);
      } catch (_) {}
      return;
    }

    // Anclar al tiempo real de la última vela visible del gráfico 5M para garantizar render exacto
    let anchorTime = desc.candleMarker.time;
    const candles5m = typeof window !== 'undefined' && Array.isArray(window._lastTrigger) ? window._lastTrigger : [];
    if (candles5m.length > 0) {
      anchorTime = candles5m[candles5m.length - 1].time;
    }
    if (!anchorTime) return;

    const merged = baseMarkers.concat([
      {
        time: anchorTime,
        position: desc.candleMarker.position,
        color: desc.candleMarker.color,
        shape: desc.candleMarker.shape,
        text: desc.candleMarker.text,
        size: desc.candleMarker.size,
      },
    ]);
    merged.sort((a, b) => Number(a.time) - Number(b.time));
    try {
      ctx.series5M.setMarkers(merged);
    } catch (_) {}
  }

  function drawSimLines(simLines, ctx) {
    clearLineGroup(state.simPriceLines, ctx);
    if (!ctx || !Array.isArray(simLines) || !simLines.length) return;
    [
      { k: 's1D', s: ctx.series1D },
      { k: 's1H', s: ctx.series1H },
      { k: 's5M', s: ctx.series5M },
    ].forEach(({ k, s }) => {
      if (!s || typeof s.createPriceLine !== 'function') return;
      simLines.forEach((cfg) => {
        const line = s.createPriceLine({
          price: cfg.price,
          color: cfg.color,
          lineWidth: cfg.lineWidth,
          lineStyle: toLwLineStyle(cfg.lineStyle),
          axisLabelVisible: true,
          title: cfg.title,
        });
        state.simPriceLines[k].push(line);
      });
    });
  }

  function renderExecutionCard(snapshot, desc) {
    if (typeof document === 'undefined') return;
    const card = document.getElementById('triadaExecCard');
    if (!card) return;

    const badgeEl = document.getElementById('triadaExecStatusBadge');
    const dirEl = document.getElementById('triadaExecSide');
    const entryEl = document.getElementById('triadaExecEntry');
    const slEl = document.getElementById('triadaExecSl');
    const tpEl = document.getElementById('triadaExecTp');
    const qtyEl = document.getElementById('triadaExecQty');
    const riskEl = document.getElementById('triadaExecRisk');
    const btnEl = document.getElementById('btnExecuteTriadaSim');
    const reasonsEl = document.getElementById('triadaExecBlockReasons');
    const rulesRowEl = document.getElementById('triadaRulesSummaryPills');

    if (!desc || !desc.valid || !desc.executionCard.plan) {
      if (badgeEl) badgeEl.innerText = 'SIN DATOS';
      if (btnEl) btnEl.disabled = true;
      if (reasonsEl) {
        reasonsEl.classList.remove('hidden');
        reasonsEl.innerText = (desc && desc.executionCard.blockReasons[0]) || 'Presiona Evaluar Gatillo para calcular niveles.';
      }
      return;
    }

    const pxDec = Number.isInteger(snapshot.px_dec) ? snapshot.px_dec : 2;
    const plan = desc.executionCard.plan;
    const ov = snapshot.overlays || {};
    const isLong = plan.side === 'LONG';

    if (rulesRowEl) {
      const pills = [
        { k: 'R0 1D', ok: Boolean(ov.rule0_macro_1d && ov.rule0_macro_1d.ok) },
        { k: 'R1 EMA50', ok: Boolean(ov.rules12_structure_1h && ov.rules12_structure_1h.rule1_ok) },
        { k: 'R2 21/89', ok: Boolean(ov.rules12_structure_1h && ov.rules12_structure_1h.rule2_ok) },
        { k: 'R3 Fibo', ok: Boolean(ov.rule3_fibo_golden_zone && ov.rule3_fibo_golden_zone.ok) },
        { k: 'R4 ATR', ok: Boolean(ov.rule4_atr_switch && ov.rule4_atr_switch.ok) },
        { k: 'Mecha', ok: !(ov.rule5_wick_and_candlestick && ov.rule5_wick_and_candlestick.wick_veto_active) },
      ];
      rulesRowEl.innerHTML = pills
        .map(
          (p) =>
            `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold border ${
              p.ok
                ? 'bg-emerald-950/80 text-emerald-300 border-emerald-600/60'
                : 'bg-rose-950/70 text-rose-300 border-rose-600/50'
            }">${p.ok ? '✅' : '❌'} ${p.k}</span>`
        )
        .join('');
    }

    if (dirEl) {
      dirEl.innerText = isLong ? '🟢 LONG' : '🔻 SHORT';
      dirEl.className = isLong ? 'font-mono font-black text-emerald-400' : 'font-mono font-black text-rose-400';
    }
    if (entryEl) entryEl.innerText = `$${formatPx(plan.entry_price, pxDec)}`;
    if (slEl) slEl.innerText = `$${formatPx(plan.sl_price, pxDec)} (-${Number(plan.sl_gross_pct).toFixed(2)}%)`;
    if (tpEl) tpEl.innerText = `$${formatPx(plan.tp_price, pxDec)} (+${Number(plan.tp_gross_pct).toFixed(2)}% · R:R 1:${Number(plan.net_rr).toFixed(2)})`;
    if (qtyEl) qtyEl.innerText = `${plan.qty} (~$${Number(plan.notional_usd).toFixed(2)})`;
    if (riskEl) riskEl.innerText = `${Number(plan.risk_pct).toFixed(2)}% ($${Number(plan.risk_budget_usd).toFixed(2)} ${plan.currency})`;

    const hasActiveSim = Boolean(plan.active_manual_sim);
    if (badgeEl) {
      if (hasActiveSim) {
        badgeEl.innerText = 'SIM ACTIVA';
        badgeEl.className = 'text-[9px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-500 font-bold';
      } else if (desc.executionCard.canExecute) {
        badgeEl.innerText = 'LUZ VERDE';
        badgeEl.className = 'text-[9px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500 font-bold';
      } else {
        badgeEl.innerText = 'BLOQUEADO';
        badgeEl.className = 'text-[9px] font-mono px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-600 font-bold';
      }
    }

    if (btnEl) {
      btnEl.disabled = !desc.executionCard.canExecute;
      btnEl.className = desc.executionCard.canExecute
        ? 'w-full py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition flex items-center justify-center gap-2 shadow-lg shadow-emerald-950/50 cursor-pointer'
        : 'w-full py-2 px-3 rounded-lg bg-slate-800 text-slate-500 border border-slate-700 font-bold text-xs flex items-center justify-center gap-2 cursor-not-allowed';
      btnEl.innerHTML = hasActiveSim
        ? '<span>✅</span> Simulación Activa en Gráfico (MANUAL_TRIADA)'
        : '<span>⚡</span> Ejecutar Gatillo (Simulación)';
    }

    if (reasonsEl) {
      if (desc.executionCard.blockReasons.length > 0) {
        reasonsEl.classList.remove('hidden');
        reasonsEl.innerHTML = desc.executionCard.blockReasons
          .map((r) => `<div>• ${escapeHtml(r)}</div>`)
          .join('');
      } else {
        reasonsEl.classList.add('hidden');
        reasonsEl.innerHTML = '';
      }
    }
  }

  function redrawBands() {
    if (!state.ctx || !state.lastDescriptors) return;
    const fb = state.lastDescriptors.fiboBand;
    updateFiboBandOverlay('chart-container-1h', 'triada-fibo-band-1h', state.ctx.series1H, fb);
    updateFiboBandOverlay('chart-container-5m', 'triada-fibo-band-5m', state.ctx.series5M, fb);
  }

  function bindChartEvents(ctx) {
    if (state.boundCharts || !ctx) return;
    [ctx.chart1H, ctx.chart5M].forEach((ch) => {
      if (ch && typeof ch.timeScale === 'function') {
        try {
          ch.timeScale().subscribeVisibleLogicalRangeChange(() => redrawBands());
        } catch (_) {}
      }
    });
    state.boundCharts = true;
  }

  function applyChartOverlays() {
    const ctx = state.ctx;
    const desc = state.lastDescriptors;
    if (!ctx) return;

    clearLineGroup(state.priceLines, ctx);

    const legend1HEl = typeof document !== 'undefined' ? document.getElementById('legend-triada-1h') : null;
    if (!state.visible || !desc || !desc.valid) {
      if (state.emaSeries1H.ema50) state.emaSeries1H.ema50.applyOptions({ visible: false });
      if (state.emaSeries1H.ema21) state.emaSeries1H.ema21.applyOptions({ visible: false });
      if (state.emaSeries1H.ema89) state.emaSeries1H.ema89.applyOptions({ visible: false });
      if (legend1HEl) legend1HEl.innerText = '';
      redrawBands();
      updateAtrAndWickBadges(desc);
      applyTriadaMarkerOn5M(desc, ctx);
      return;
    }

    ensureEmaSeries1H(ctx.chart1H);
    if (state.emaSeries1H.ema50) {
      state.emaSeries1H.ema50.setData(desc.series1H.ema50);
      state.emaSeries1H.ema50.applyOptions({ visible: true });
    }
    if (state.emaSeries1H.ema21) {
      state.emaSeries1H.ema21.setData(desc.series1H.ema21);
      state.emaSeries1H.ema21.applyOptions({ visible: true });
    }
    if (state.emaSeries1H.ema89) {
      state.emaSeries1H.ema89.setData(desc.series1H.ema89);
      state.emaSeries1H.ema89.applyOptions({ visible: true });
    }
    if (legend1HEl) {
      legend1HEl.innerText = desc.legend1HText ? `| ${desc.legend1HText}` : '';
    }

    const addLines = (series, list, bucketKey) => {
      if (!series || typeof series.createPriceLine !== 'function') return;
      (list || []).forEach((cfg) => {
        const line = series.createPriceLine({
          price: cfg.price,
          color: cfg.color,
          lineWidth: cfg.lineWidth,
          lineStyle: toLwLineStyle(cfg.lineStyle),
          axisLabelVisible: true,
          title: cfg.title,
        });
        state.priceLines[bucketKey].push(line);
      });
    };

    addLines(ctx.series1D, desc.lines1D, 's1D');
    addLines(ctx.series1H, desc.lines1H, 's1H');
    addLines(ctx.series5M, desc.lines5M, 's5M');

    redrawBands();
    updateAtrAndWickBadges(desc);
    applyTriadaMarkerOn5M(desc, ctx);
  }

  function renderAll(snapshot, ctx) {
    state.ctx = ctx || state.ctx;
    state.lastSnapshot = snapshot;
    state.lastDescriptors = buildTriadaOverlayDescriptors(snapshot);
    bindChartEvents(state.ctx);
    applyChartOverlays();
    renderExecutionCard(snapshot, state.lastDescriptors);
    drawSimLines(state.lastDescriptors.executionCard.simLines, state.ctx);
  }

  function setVisible(visible) {
    state.visible = Boolean(visible);
    applyChartOverlays();
  }

  async function executeSimulatedTrigger(backendBase) {
    const snap = state.lastSnapshot;
    const btn = typeof document !== 'undefined' ? document.getElementById('btnExecuteTriadaSim') : null;
    const reasonsEl = typeof document !== 'undefined' ? document.getElementById('triadaExecBlockReasons') : null;
    if (!snap || snap.status !== 'ok') return null;

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span> Registrando simulación aislada...';
    }
    try {
      const rrInput = typeof document !== 'undefined' ? document.getElementById('inputRr') : null;
      const targetRr = rrInput ? Math.max(2.0, parseFloat(rrInput.value) || 2.0) : 2.0;
      const dirSel = typeof document !== 'undefined' ? document.getElementById('directionModeSelect') : null;
      const dirMode = dirSel ? dirSel.value : snap.direction_mode || 'dual';

      const resp = await fetch(`${backendBase}/api/triada/execute-sim`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: snap.symbol,
          timeframe: snap.timeframe,
          direction_mode: dirMode,
          risk_pct: 0.5,
          target_rr: targetRr,
        }),
      });
      const data = await resp.json();
      if (data && data.snapshot) {
        renderAll(data.snapshot, state.ctx);
      }
      if (!data || !data.executed) {
        if (reasonsEl) {
          reasonsEl.classList.remove('hidden');
          reasonsEl.innerHTML = (data && data.reasons ? data.reasons : ['Ejecución bloqueada por seguridad.'])
            .map((r) => `<div>• ${escapeHtml(r)}</div>`)
            .join('');
        }
      }
      return data;
    } catch (err) {
      if (reasonsEl) {
        reasonsEl.classList.remove('hidden');
        reasonsEl.innerText = `Error conectando con /api/triada/execute-sim: ${err.message}`;
      }
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span>⚡</span> Ejecutar Gatillo (Simulación)';
      }
      return null;
    }
  }

  return {
    normalizeTriadaSymbol,
    computeFiboBandGeometry,
    buildTriadaOverlayDescriptors,
    renderAll,
    setVisible,
    redrawBands,
    executeSimulatedTrigger,
  };
});
