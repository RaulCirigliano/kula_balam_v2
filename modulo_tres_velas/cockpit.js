/**
 * COCKPIT CUANTITATIVO TRADINGVIEW PRO (cockpit.js)
 * Ecosistema: kula_balam / monitor_del_mercado
 * Arquitectura: Frontend desacoplado con Lightweight Charts v4.1.x
 *
 * Módulos:
 * 1. TA Helpers (Pine-like): RSI, EMA, ATR, VWAP, Crossover, Highest/Lowest
 * 2. Motor de Reglas Cuantitativas y Disparador de Webhooks (POST :18767/api/signal)
 * 3. Herramientas de Dibujo Interactivas (Cajas/Zonas, Posición Larga/Corta R:R, Regla)
 * 4. Flujo Institucional: Volume Profile (VPVR Horizontal con POC, VAH, VAL) & VWAP Multisesión (+-1,2,3 sigma)
 * 5. Bar Replay (Rebobinado de Velas) & Simulador Paper Trading con balance virtual
 * 6. Auditor Forense de Operaciones del Bot (Activas: líneas de precio vivas / Finalizadas: navegación temporal)
 * 7. Screener Institucional Liviano (BTC, ETH, SOL, BNB, XRP, SPY, EUR/USD)
 * 8. Sincronización Multi-Temporal (Crosshair & TimeScale Sync) y Sesiones Bursátiles (Tokio, Londres, NY)
 */

(function () {
  'use strict';

  // =========================================================================
  // CONFIGURACIÓN Y ESTADO GLOBAL
  // =========================================================================
  const CONFIG = {
    backendBase: 'http://127.0.0.1:18767',
    radarBase: 'http://127.0.0.1:8520',
    defaultSymbol: 'BTCUSDT',
    symbolsBasket: [
      { symbol: 'BTCUSDT', name: 'Bitcoin', market: 'CRYPTO' },
      { symbol: 'ETHUSDT', name: 'Ethereum', market: 'CRYPTO' },
      { symbol: 'SOLUSDT', name: 'Solana', market: 'CRYPTO' },
      { symbol: 'BNBUSDT', name: 'BNB', market: 'CRYPTO' },
      { symbol: 'XRPUSDT', name: 'Ripple', market: 'CRYPTO' },
      { symbol: 'SPY', name: 'S&P 500 ETF', market: 'NYSE' },
      { symbol: 'EURUSDT', name: 'EUR / USD', market: 'FOREX' }
    ],
    theme: {
      bg: '#131722',
      panelBg: '#1e222d',
      borderColor: '#2a2e39',
      gridColor: 'rgba(42, 46, 57, 0.4)',
      textPrimary: '#d1d4dc',
      textSecondary: '#787b86',
      bullColor: '#089981',
      bearColor: '#f23645',
      crosshairColor: '#2962ff'
    }
  };

  const STATE = {
    currentSymbol: CONFIG.defaultSymbol,
    timezone: localStorage.getItem('tv_timezone') || 'UTC-3',
    timeframe1D: '1d',
    timeframe1H: '1h',
    timeframeTrigger: '15m',
    rthMode: localStorage.getItem('tv_rth_mode') || 'ALL', // ALL | RTH | ETH
    
    // Instancias de Gráficos Lightweight Charts
    charts: { macro: null, setup: null, trigger: null },
    series: { macro: null, setup: null, trigger: null },
    volumeSeries: { macro: null, setup: null, trigger: null },
    emaSeries: { macro: null, setup: null, trigger: null },
    vwapSeries: { trigger: null, triggerUpper1: null, triggerLower1: null, triggerUpper2: null, triggerLower2: null },
    priceLines: { trigger: [] }, // Líneas de precio para trades activos/inspeccionados
    
    // Capas e Indicadores Visibles (Predeterminado Limpio: Patrones históricos desmarcados por defecto para evitar ruido visual)
    layers: (function () {
      const defaults = {
        candlePatterns: false,   // Patrones históricos en cada vela: desactivado por defecto para no tapar el gráfico
        candlePoc: true,         // POC de Compra Intrabarra
        vwap: true,              // VWAP de sesión y bandas +-1sigma, +-2sigma
        ema: true,               // Medias Móviles: EMA 50 (Macro) y EMA 20 (Setup)
        volumeProfile: true,     // Perfil de Volumen Horizontal (VPVR con POC/VAH/VAL)
        volume: true,            // Histograma inferior de volumen en los 3 gráficos
        tradeLines: false,       // Líneas de operaciones del bot / Demo TP
        drawings: true,          // Zonas y cajas dibujadas por el usuario
        heikinAshi: false        // Suavizado Heikin Ashi
      };
      try {
        const saved = JSON.parse(localStorage.getItem('tv_chart_layers_v2') || 'null');
        if (saved && typeof saved === 'object') {
          return Object.assign({}, defaults, saved);
        }
      } catch (_) {}
      return defaults;
    })(),
    lastVolumeProfile: null,
    
    // Datos crudos
    data: { macro: [], setup: [], trigger: [] },
    
    // Herramientas de Dibujo
    activeTool: null, // null | 'box' | 'positionLong' | 'positionShort' | 'ruler'
    drawings: JSON.parse(localStorage.getItem('tv_drawings') || '{}'), // por símbolo
    isDrawing: false,
    drawStartPoint: null,
    
    // Bar Replay
    replay: {
      active: false,
      paused: true,
      speed: 1000, // ms por vela
      cutoffIndex: 0,
      fullDataset: [],
      timer: null
    },
    
    // Paper Trading
    paper: JSON.parse(localStorage.getItem('tv_paper_account') || JSON.stringify({
      balance: 10000.0,
      positions: [],
      history: []
    })),
    
    // Screener data
    screenerData: {},
    
    // Auditoría de Trades del Backend
    backendPositions: [],
    backendTrades: [],
    selectedAuditedTrade: null
  };

  // =========================================================================
  // MÓDULO 1: HELPERS CUANTITATIVOS (PINE-LIKE)
  // =========================================================================
  const ta = {
    ema: function (candles, period) {
      if (!candles || candles.length < period) return [];
      const k = 2 / (period + 1);
      const res = [];
      let sum = 0;
      for (let i = 0; i < period; i++) sum += candles[i].close;
      let prevEma = sum / period;
      res.push({ time: candles[period - 1].time, value: prevEma });
      for (let i = period; i < candles.length; i++) {
        const val = (candles[i].close - prevEma) * k + prevEma;
        res.push({ time: candles[i].time, value: val });
        prevEma = val;
      }
      return res;
    },

    rsi: function (candles, period = 14) {
      if (!candles || candles.length <= period) return [];
      const res = [];
      let gains = 0, losses = 0;
      for (let i = 1; i <= period; i++) {
        const diff = candles[i].close - candles[i - 1].close;
        if (diff >= 0) gains += diff;
        else losses -= diff;
      }
      let avgGain = gains / period;
      let avgLoss = losses / period;
      let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      res.push({ time: candles[period].time, value: 100 - (100 / (1 + rs)) });

      for (let i = period + 1; i < candles.length; i++) {
        const diff = candles[i].close - candles[i - 1].close;
        const gain = diff > 0 ? diff : 0;
        const loss = diff < 0 ? -diff : 0;
        avgGain = (avgGain * (period - 1) + gain) / period;
        avgLoss = (avgLoss * (period - 1) + loss) / period;
        rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        res.push({ time: candles[i].time, value: 100 - (100 / (1 + rs)) });
      }
      return res;
    },

    atr: function (candles, period = 14) {
      if (!candles || candles.length < period) return [];
      const trs = [];
      for (let i = 1; i < candles.length; i++) {
        const h = candles[i].high, l = candles[i].low, pc = candles[i - 1].close;
        trs.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
      }
      let atrVal = trs.slice(0, period).reduce((a, b) => a + b, 0) / period;
      const res = [{ time: candles[period].time, value: atrVal }];
      for (let i = period; i < trs.length; i++) {
        atrVal = (atrVal * (period - 1) + trs[i]) / period;
        res.push({ time: candles[i + 1].time, value: atrVal });
      }
      return res;
    },

    vwapSession: function (candles) {
      if (!candles || !candles.length) return { vwap: [], upper1: [], lower1: [], upper2: [], lower2: [] };
      const vwap = [], upper1 = [], lower1 = [], upper2 = [], lower2 = [];
      let cumVol = 0, cumTypicalVol = 0, cumVolDiffSq = 0;
      let lastDay = null;

      for (let c of candles) {
        const dt = new Date(c.time * 1000);
        const dayKey = dt.getUTCFullYear() + '-' + dt.getUTCMonth() + '-' + dt.getUTCDate();
        if (dayKey !== lastDay) {
          cumVol = 0;
          cumTypicalVol = 0;
          cumVolDiffSq = 0;
          lastDay = dayKey;
        }
        const typical = (c.high + c.low + c.close) / 3;
        const vol = c.volume || 1;
        cumVol += vol;
        cumTypicalVol += typical * vol;
        const currentVwap = cumTypicalVol / cumVol;

        cumVolDiffSq += vol * Math.pow(typical - currentVwap, 2);
        const stdev = Math.sqrt(cumVolDiffSq / cumVol);

        vwap.push({ time: c.time, value: currentVwap });
        upper1.push({ time: c.time, value: currentVwap + stdev });
        lower1.push({ time: c.time, value: currentVwap - stdev });
        upper2.push({ time: c.time, value: currentVwap + 2 * stdev });
        lower2.push({ time: c.time, value: currentVwap - 2 * stdev });
      }
      return { vwap, upper1, lower1, upper2, lower2 };
    },

    crossover: function (seriesA, seriesB) {
      if (!seriesA || !seriesB || seriesA.length < 2 || seriesB.length < 2) return false;
      const aCurr = seriesA[seriesA.length - 1].value;
      const aPrev = seriesA[seriesA.length - 2].value;
      const bCurr = seriesB[seriesB.length - 1].value;
      const bPrev = seriesB[seriesB.length - 2].value;
      return aPrev <= bPrev && aCurr > bCurr;
    },

    crossunder: function (seriesA, seriesB) {
      if (!seriesA || !seriesB || seriesA.length < 2 || seriesB.length < 2) return false;
      const aCurr = seriesA[seriesA.length - 1].value;
      const aPrev = seriesA[seriesA.length - 2].value;
      const bCurr = seriesB[seriesB.length - 1].value;
      const bPrev = seriesB[seriesB.length - 2].value;
      return aPrev >= bPrev && aCurr < bCurr;
    }
  };

  // =========================================================================
  // MÓDULO 2: VOLUME PROFILE HORIZONTAL (VPVR / FRVP)
  // =========================================================================
  function calculateVolumeProfile(candles, bucketsCount = 30) {
    if (!candles || candles.length === 0) return null;
    let minPrice = Infinity, maxPrice = -Infinity, totalVol = 0;
    candles.forEach(c => {
      if (c.low < minPrice) minPrice = c.low;
      if (c.high > maxPrice) maxPrice = c.high;
      totalVol += (c.volume || 1);
    });

    const step = (maxPrice - minPrice) / bucketsCount;
    if (step <= 0) return null;

    const buckets = Array.from({ length: bucketsCount }, (_, i) => ({
      price: minPrice + (i + 0.5) * step,
      low: minPrice + i * step,
      high: minPrice + (i + 1) * step,
      buyVolume: 0,
      sellVolume: 0,
      totalVolume: 0
    }));

    candles.forEach(c => {
      const vol = c.volume || 1;
      const isUp = c.close >= c.open;
      const p = (c.high + c.low + c.close) / 3;
      const idx = Math.min(bucketsCount - 1, Math.max(0, Math.floor((p - minPrice) / step)));
      if (isUp) buckets[idx].buyVolume += vol;
      else buckets[idx].sellVolume += vol;
      buckets[idx].totalVolume += vol;
    });

    // Encontrar Point of Control (POC)
    let pocBucket = buckets[0];
    buckets.forEach(b => {
      if (b.totalVolume > pocBucket.totalVolume) pocBucket = b;
    });

    // Encontrar Value Area (70% del volumen total alrededor del POC)
    const targetVol = totalVol * 0.70;
    let currentVol = pocBucket.totalVolume;
    let upIdx = buckets.indexOf(pocBucket) + 1;
    let downIdx = buckets.indexOf(pocBucket) - 1;

    while (currentVol < targetVol && (upIdx < bucketsCount || downIdx >= 0)) {
      const upVol = upIdx < bucketsCount ? buckets[upIdx].totalVolume : -1;
      const downVol = downIdx >= 0 ? buckets[downIdx].totalVolume : -1;
      if (upVol >= downVol && upIdx < bucketsCount) {
        currentVol += upVol;
        upIdx++;
      } else if (downIdx >= 0) {
        currentVol += downVol;
        downIdx--;
      } else if (upIdx < bucketsCount) {
        currentVol += upVol;
        upIdx++;
      } else {
        break;
      }
    }

    const val = buckets[Math.max(0, downIdx + 1)].low;
    const vah = buckets[Math.min(bucketsCount - 1, upIdx - 1)].high;

    return { buckets, poc: pocBucket.price, vah, val, maxBucketVol: Math.max(...buckets.map(b => b.totalVolume)) };
  }

  // Renderizador en Canvas del Volume Profile en el margen derecho
  function renderVolumeProfileOverlay(containerId, profile) {
    let canvas = document.getElementById(containerId + '-vp-canvas');
    const container = document.getElementById(containerId);
    if (!container || !profile) return;
    STATE.lastVolumeProfile = profile;

    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = containerId + '-vp-canvas';
      canvas.className = 'absolute top-0 right-0 pointer-events-none z-10';
      container.appendChild(canvas);
    }

    if (STATE.layers && STATE.layers.volumeProfile === false) {
      canvas.style.display = 'none';
      return;
    }
    canvas.style.display = 'block';

    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const vpWidth = Math.min(140, canvas.width * 0.22);
    const startX = canvas.width - vpWidth - 55; // antes de la escala de precios

    profile.buckets.forEach(b => {
      // Mapear precio a Y aproximado
      const normY1 = 1 - ((b.high - profile.val) / (profile.vah - profile.val + 1e-9));
      // Render simple proporcional
      const barLen = (b.totalVolume / profile.maxBucketVol) * vpWidth;
      const isPoc = Math.abs(b.price - profile.poc) < (profile.vah - profile.val) / 30;

      const y = canvas.height * (1 - (b.price - profile.buckets[0].low) / (profile.buckets[profile.buckets.length - 1].high - profile.buckets[0].low));
      const h = Math.max(2, canvas.height / profile.buckets.length - 1);

      // Color Buy vs Sell
      const buyLen = (b.buyVolume / b.totalVolume) * barLen;
      const sellLen = barLen - buyLen;

      ctx.fillStyle = isPoc ? 'rgba(245, 158, 11, 0.45)' : 'rgba(8, 153, 129, 0.25)';
      ctx.fillRect(startX + vpWidth - barLen, y, buyLen, h);
      ctx.fillStyle = isPoc ? 'rgba(239, 68, 68, 0.65)' : 'rgba(242, 54, 69, 0.25)';
      ctx.fillRect(startX + vpWidth - barLen + buyLen, y, sellLen, h);

      if (isPoc) {
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(startX, y + h / 2);
        ctx.lineTo(canvas.width, y + h / 2);
        ctx.stroke();
      }
    });
  }

  // =========================================================================
  // MÓDULO 3: CAPAS DE DIBUJO INTERACTIVAS (Zonas, Posición R:R, Regla, Fibonacci)
  // =========================================================================

  // Configuración de Retroceso de Fibonacci (TradingView Pro)
  const DEFAULT_FIB_CONFIG = {
    fillGoldenZone: true,
    levels: [
      { id: 'fib-0', level: 0.0, name: '0.0 (0.0%)', color: '#94a3b8', enabled: true },
      { id: 'fib-236', level: 0.236, name: '0.236 (23.6%)', color: '#ef4444', enabled: true },
      { id: 'fib-382', level: 0.382, name: '0.382 (38.2%)', color: '#f97316', enabled: true },
      { id: 'fib-500', level: 0.5, name: '0.500 (50.0%) · Equilibrio', color: '#eab308', enabled: true },
      { id: 'fib-618', level: 0.618, name: '0.618 (61.8%) · Zona Dorada', color: '#10b981', enabled: true },
      { id: 'fib-707', level: 0.707, name: '0.707 (70.7%)', color: '#06b6d4', enabled: false },
      { id: 'fib-750', level: 0.75, name: '0.750 (75.0%) · Límite Kula', color: '#3b82f6', enabled: true },
      { id: 'fib-786', level: 0.786, name: '0.786 (78.6%)', color: '#8b5cf6', enabled: true },
      { id: 'fib-1000', level: 1.0, name: '1.000 (100.0%)', color: '#94a3b8', enabled: true },
      { id: 'fib-1272', level: 1.272, name: '1.272 (127.2%)', color: '#ec4899', enabled: false },
      { id: 'fib-1618', level: 1.618, name: '1.618 (161.8%) · Extensión', color: '#a855f7', enabled: true },
    ]
  };

  function getFibConfig() {
    try {
      const stored = localStorage.getItem('tv_fib_config');
      if (stored) return JSON.parse(stored);
    } catch (e) {}
    return JSON.parse(JSON.stringify(DEFAULT_FIB_CONFIG));
  }

  function saveFibConfig(config) {
    localStorage.setItem('tv_fib_config', JSON.stringify(config));
    ['chart-container-1d', 'chart-container-1h', 'chart-container-5m'].forEach(id => {
      const chart = id === 'chart-container-1d' ? STATE.charts.macro : (id === 'chart-container-1h' ? STATE.charts.setup : STATE.charts.trigger);
      redrawAllDrawings(id, chart);
    });
  }

  function initDrawingOverlay(containerId, chartInstance) {
    const container = document.getElementById(containerId);
    if (!container) return;

    let canvas = document.getElementById(containerId + '-draw-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = containerId + '-draw-canvas';
      canvas.className = 'absolute inset-0 z-20 cursor-crosshair';
      canvas.style.pointerEvents = STATE.activeTool ? 'auto' : 'none';
      container.appendChild(canvas);
    }

    const chart = chartInstance || (containerId === 'chart-container-1d' ? (STATE.charts.macro || window.chart1D) : (containerId === 'chart-container-1h' ? (STATE.charts.setup || window.chart1H) : (STATE.charts.trigger || window.chart5M)));

    const resize = () => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      redrawAllDrawings(containerId, chart);
    };
    window.addEventListener('resize', resize);
    resize();

    if (chart && chart.timeScale && !canvas._subscribedTimeScale) {
      try {
        chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
          redrawAllDrawings(containerId, chart);
        });
        canvas._subscribedTimeScale = true;
      } catch (e) {}
    }

    // Eventos de ratón
    let isDrawing = false;
    let startX = 0, startY = 0;

    canvas.onmousedown = (e) => {
      if (!STATE.activeTool) return;
      const r = canvas.getBoundingClientRect();
      const clickX = e.clientX - r.left;
      const clickY = e.clientY - r.top;

      if (STATE.activeTool === 'eraser') {
        const erased = eraseDrawingAt(containerId, clickX, clickY);
        if (!erased) {
          window.undoLastDrawing(containerId);
        }
        redrawAllDrawings(containerId, chartInstance);
        return;
      }

      isDrawing = true;
      startX = clickX;
      startY = clickY;
    };

    canvas.onmousemove = (e) => {
      if (!isDrawing || !STATE.activeTool) return;
      const r = canvas.getBoundingClientRect();
      const currX = e.clientX - r.left;
      const currY = e.clientY - r.top;

      redrawAllDrawings(containerId, chartInstance);
      const ctx = canvas.getContext('2d');
      drawPreviewTool(ctx, STATE.activeTool, startX, startY, currX, currY, containerId);
    };

    canvas.onmouseup = (e) => {
      if (!isDrawing || !STATE.activeTool) return;
      isDrawing = false;
      const r = canvas.getBoundingClientRect();
      const endX = e.clientX - r.left;
      const endY = e.clientY - r.top;

      // Guardar si hubo arrastre mínimo (> 4px) para evitar clics accidentales
      if (Math.abs(endX - startX) > 4 || Math.abs(endY - startY) > 4) {
        saveNewDrawing(STATE.currentSymbol, containerId, STATE.activeTool, startX, startY, endX, endY, canvas.width, canvas.height);
      }
      redrawAllDrawings(containerId, chartInstance);
    };
  }

  function resolveTriadaPriceAndAtrForContainer(containerId, y1, y2, canvasH) {
    let series = window.series5M;
    let candles = window._lastTrigger;
    if (containerId === 'chart-container-1d') {
      series = window.series1D;
      candles = window._last1D;
    } else if (containerId === 'chart-container-1h') {
      series = window.series1H;
      candles = window._last1H;
    }
    let p1 = null;
    let p2 = null;
    if (series && typeof series.coordinateToPrice === 'function') {
      try {
        p1 = series.coordinateToPrice(y1);
        p2 = series.coordinateToPrice(y2);
      } catch (_) {}
    }
    if ((!Number.isFinite(p1) || !Number.isFinite(p2)) && Array.isArray(candles) && candles.length >= 2 && canvasH > 0) {
      const slice = candles.slice(-Math.min(50, candles.length));
      const hi = Math.max(...slice.map(c => Number(c.high)));
      const lo = Math.min(...slice.map(c => Number(c.low)));
      if (hi > lo) {
        const pad = (hi - lo) * 0.10;
        const topP = hi + pad;
        const botP = Math.max(0.0001, lo - pad);
        p1 = topP - (y1 / canvasH) * (topP - botP);
        p2 = topP - (y2 / canvasH) * (topP - botP);
      }
    }
    let atrVal = null;
    if (Array.isArray(candles) && candles.length >= 15 && window.KulaChartEngine && window.KulaChartEngine.formulas) {
      const atrRes = window.KulaChartEngine.formulas.calculateATR(candles, 14);
      if (atrRes && Number.isFinite(atrRes.lastValue) && atrRes.lastValue > 0) atrVal = atrRes.lastValue;
    }
    return { p1, p2, atrVal };
  }

  function drawPreviewTool(ctx, tool, x1, y1, x2, y2, containerId) {
    ctx.save();
    if (tool === 'box') {
      const w = x2 - x1;
      const h = y2 - y1;
      ctx.fillStyle = 'rgba(41, 98, 255, 0.18)';
      ctx.strokeStyle = '#2962ff';
      ctx.lineWidth = 1.5;
      ctx.fillRect(x1, y1, w, h);
      ctx.strokeRect(x1, y1, w, h);
    } else if (tool === 'positionLong' || tool === 'positionShort') {
      const isLong = tool === 'positionLong';
      const entryY = y1;
      const tpY = isLong ? Math.min(y1, y2) : Math.max(y1, y2);
      const slY = isLong ? y1 + Math.abs(entryY - tpY) * 0.45 : y1 - Math.abs(entryY - tpY) * 0.45;
      const w = Math.abs(x2 - x1) || 120;
      const leftX = Math.min(x1, x2);

      // Caja Verde TP
      ctx.fillStyle = 'rgba(8, 153, 129, 0.22)';
      ctx.strokeStyle = '#089981';
      ctx.fillRect(leftX, Math.min(entryY, tpY), w, Math.abs(entryY - tpY));
      ctx.strokeRect(leftX, Math.min(entryY, tpY), w, Math.abs(entryY - tpY));

      // Caja Roja SL (Rojo más intenso)
      ctx.fillStyle = 'rgba(239, 68, 68, 0.38)';
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2;
      ctx.fillRect(leftX, Math.min(entryY, slY), w, Math.abs(entryY - slY));
      ctx.strokeRect(leftX, Math.min(entryY, slY), w, Math.abs(entryY - slY));

      // Etiqueta R:R
      const targetDist = Math.abs(entryY - tpY);
      const stopDist = Math.abs(entryY - slY) || 1;
      const rrRatio = (targetDist / stopDist).toFixed(2);

      ctx.fillStyle = '#ffffff';
      ctx.font = '11px ui-monospace, SFMono-Regular, monospace';
      ctx.fillText(`Target: +${((targetDist / y1) * 100).toFixed(2)}% | R:R 1:${rrRatio}`, leftX + 8, entryY - 6);
    } else if (tool === 'ruler') {
      const cvsH = ctx.canvas ? ctx.canvas.height : 400;
      const cvsW = ctx.canvas ? ctx.canvas.width : 600;
      const { p1, p2, atrVal } = resolveTriadaPriceAndAtrForContainer(containerId || 'chart-container-5m', y1, y2, cvsH);
      let labelText = '';
      if (Number.isFinite(p1) && Number.isFinite(p2) && p1 > 0 && window.KulaChartEngine && typeof window.KulaChartEngine.calculateRulerMetrics === 'function') {
        const m = window.KulaChartEngine.calculateRulerMetrics(p1, p2, atrVal);
        if (m.valid) labelText = `📏 ${m.summaryText}`;
      }
      if (!labelText) {
        const pct = (((y1 - y2) / Math.max(1, y1)) * 100).toFixed(2);
        labelText = `📏 Δ ${pct}%`;
      }

      // Rectángulo sombreado de medición
      ctx.fillStyle = y2 <= y1 ? 'rgba(16, 185, 129, 0.14)' : 'rgba(56, 189, 248, 0.14)';
      ctx.fillRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));

      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 1.8;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.font = 'bold 11px ui-monospace, SFMono-Regular, monospace';
      const boxW = Math.max(175, ctx.measureText(labelText).width + 16);
      const boxX = Math.max(6, Math.min(cvsW - boxW - 6, x2 + 6));
      const boxY = Math.max(6, Math.min(cvsH - 26, y2 - 12));
      ctx.fillStyle = 'rgba(15, 23, 42, 0.94)';
      ctx.fillRect(boxX, boxY, boxW, 22);
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 1.2;
      ctx.strokeRect(boxX, boxY, boxW, 22);
      ctx.fillStyle = '#e0f2fe';
      ctx.fillText(labelText, boxX + 7, boxY + 15);
    } else if (tool === 'trendline') {
      // Línea de Tendencia con puntos de ancla
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();

      ctx.fillStyle = '#38bdf8';
      ctx.beginPath(); ctx.arc(x1, y1, 4, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(x2, y2, 4, 0, Math.PI * 2); ctx.fill();
    } else if (tool === 'fibonacci') {
      // Retroceso de Fibonacci Pro con Niveles Parametrizables y Zona Dorada
      const fibConfig = getFibConfig();
      const dy = y2 - y1;
      const minX = Math.min(x1, x2);
      const maxX = Math.max(x2, ctx.canvas ? ctx.canvas.width : 800);

      // Línea diagonal de impulso de referencia
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.45)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      ctx.setLineDash([]);

      // Puntos de ancla en extremos
      ctx.fillStyle = '#6366f1';
      ctx.beginPath(); ctx.arc(x1, y1, 4, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(x2, y2, 4, 0, Math.PI * 2); ctx.fill();

      // Sombrado de Zona Dorada (0.50 a 0.618 / 0.75) si está activado
      if (fibConfig.fillGoldenZone !== false) {
        const y05 = y1 + dy * 0.5;
        const y0618 = y1 + dy * 0.618;
        const y075 = y1 + dy * 0.75;
        ctx.fillStyle = 'rgba(245, 158, 11, 0.12)';
        ctx.fillRect(minX, Math.min(y05, y0618), maxX - minX, Math.abs(y0618 - y05));
        ctx.fillStyle = 'rgba(16, 185, 129, 0.08)';
        ctx.fillRect(minX, Math.min(y0618, y075), maxX - minX, Math.abs(y075 - y0618));
      }

      // Trazar cada nivel configurado y activo
      if (Array.isArray(fibConfig.levels)) {
        fibConfig.levels.forEach(lvl => {
          if (!lvl.enabled) return;
          const yLvl = y1 + dy * lvl.level;
          ctx.strokeStyle = lvl.color || '#94a3b8';
          ctx.lineWidth = (lvl.level === 0.618 || lvl.level === 0.5 || lvl.level === 0.75) ? 1.8 : 1;
          ctx.beginPath();
          ctx.moveTo(minX, yLvl);
          ctx.lineTo(maxX, yLvl);
          ctx.stroke();

          // Etiqueta del nivel
          ctx.fillStyle = lvl.color || '#94a3b8';
          ctx.font = 'bold 10.5px ui-monospace, SFMono-Regular, monospace';
          const labelText = lvl.name || `${lvl.level} (${(lvl.level * 100).toFixed(1)}%)`;
          ctx.fillText(labelText, minX + 8, yLvl - 4);
        });
      }
    }
    ctx.restore();
  }

  function saveNewDrawing(symbol, containerId, tool, x1, y1, x2, y2, w, h) {
    if (!STATE.drawings[symbol]) STATE.drawings[symbol] = [];
    STATE.drawings[symbol].push({
      id: 'd_' + Date.now(),
      containerId,
      tool,
      nx1: x1 / Math.max(w, 1),
      ny1: y1 / Math.max(h, 1),
      nx2: x2 / Math.max(w, 1),
      ny2: y2 / Math.max(h, 1),
      ts: Date.now()
    });
    localStorage.setItem('tv_drawings', JSON.stringify(STATE.drawings));
  }

  // Dibuja la línea negra horizontal del POC intrabarra que atraviesa cada vela a la altura de mayor volumen de venta
  function drawCandlePocTicks(containerId, chartInstance, ctx) {
    if (!STATE.layers || STATE.layers.candlePoc === false) return;
    const chart = chartInstance || (containerId === 'chart-container-1d' ? (STATE.charts.macro || window.chart1D) : (containerId === 'chart-container-1h' ? (STATE.charts.setup || window.chart1H) : (STATE.charts.trigger || window.chart5M)));
    if (!chart || !chart.timeScale) return;

    let candles = null;
    let series = null;
    let pocMap = null;

    if (containerId === 'chart-container-1d') {
      candles = window._last1D;
      series = window.series1D;
      pocMap = window.pocMap1D;
    } else if (containerId === 'chart-container-1h') {
      candles = window._last1H;
      series = window.series1H;
      pocMap = window.pocMap1H;
    } else if (containerId === 'chart-container-5m') {
      candles = window._lastTrigger;
      series = window.series5M;
      pocMap = window.pocMap5M;
    }

    if (!candles || !candles.length || !series || !pocMap) return;

    const timeScale = chart.timeScale();
    let barSpacing = 9;
    try {
      const opts = timeScale.options();
      if (opts && typeof opts.barSpacing === 'number') barSpacing = opts.barSpacing;
    } catch (e) {}

    // Ancho del segmento que cruza la vela de lado a lado
    const tickHalfWidth = Math.max(5, Math.min(22, barSpacing * 0.48));
    const canvasWidth = ctx.canvas.width;
    const canvasHeight = ctx.canvas.height;

    ctx.save();
    for (let i = 0; i < candles.length; i++) {
      const c = candles[i];
      const x = timeScale.timeToCoordinate(c.time);
      if (x === null || x < -25 || x > canvasWidth + 25) continue;

      const poc = pocMap.get(c.time);
      if (!poc || typeof poc.pocPrice !== 'number') continue;

      const y = series.priceToCoordinate(poc.pocPrice);
      if (y === null || y < -10 || y > canvasHeight + 10) continue;

      // 1. Contorno de contraste sutil para visibilidad garantizada sobre fondo oscuro
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.40)';
      ctx.lineWidth = 3.6;
      ctx.beginPath();
      ctx.moveTo(x - tickHalfWidth, y);
      ctx.lineTo(x + tickHalfWidth, y);
      ctx.stroke();

      // 2. Línea negra sólida intrabarra que atraviesa la vela
      ctx.strokeStyle = '#000000';
      ctx.lineWidth = 2.4;
      ctx.beginPath();
      ctx.moveTo(x - tickHalfWidth, y);
      ctx.lineTo(x + tickHalfWidth, y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function redrawAllDrawings(containerId, chartInstance) {
    const canvas = document.getElementById(containerId + '-draw-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 1. Dibujar líneas negras de POC intrabarra por vela
    drawCandlePocTicks(containerId, chartInstance, ctx);

    // 2. Dibujar herramientas interactivas del usuario (Fibonacci, Trendlines, etc.)
    const list = (STATE.drawings[STATE.currentSymbol] || []).filter(d => !d.containerId || d.containerId === containerId);
    list.forEach(d => {
      const x1 = d.nx1 * canvas.width;
      const y1 = d.ny1 * canvas.height;
      const x2 = d.nx2 * canvas.width;
      const y2 = d.ny2 * canvas.height;
      drawPreviewTool(ctx, d.tool, x1, y1, x2, y2, containerId);
    });
  }

  window.redrawAllPocLines = function () {
    ['chart-container-1d', 'chart-container-1h', 'chart-container-5m'].forEach(id => {
      const chart = id === 'chart-container-1d' ? (STATE.charts.macro || window.chart1D) : (id === 'chart-container-1h' ? (STATE.charts.setup || window.chart1H) : (STATE.charts.trigger || window.chart5M));
      if (chart) redrawAllDrawings(id, chart);
    });
  };

  function eraseDrawingAt(containerId, clickX, clickY) {
    const symbol = STATE.currentSymbol;
    if (!STATE.drawings[symbol] || !STATE.drawings[symbol].length) return false;
    const canvas = document.getElementById(containerId + '-draw-canvas');
    if (!canvas) return false;
    const w = canvas.width;
    const h = canvas.height;

    for (let i = STATE.drawings[symbol].length - 1; i >= 0; i--) {
      const d = STATE.drawings[symbol][i];
      if (d.containerId && d.containerId !== containerId) continue;
      const xMin = Math.min(d.nx1, d.nx2) * w - 16;
      const xMax = Math.max(d.nx1, d.nx2) * w + 16;
      const yMin = Math.min(d.ny1, d.ny2) * h - 16;
      const yMax = Math.max(d.ny1, d.ny2) * h + 16;

      // Para Fibonacci, las líneas se proyectan a todo lo ancho: verificar proximidad vertical
      if (d.tool === 'fibonacci') {
        const fibYMin = Math.min(d.ny1, d.ny2) * h - 25;
        const fibYMax = Math.max(d.ny1, d.ny2) * h + 25;
        if (clickY >= fibYMin && clickY <= fibYMax) {
          STATE.drawings[symbol].splice(i, 1);
          localStorage.setItem('tv_drawings', JSON.stringify(STATE.drawings));
          return true;
        }
      }

      if (clickX >= xMin && clickX <= xMax && clickY >= yMin && clickY <= yMax) {
        STATE.drawings[symbol].splice(i, 1);
        localStorage.setItem('tv_drawings', JSON.stringify(STATE.drawings));
        return true;
      }
    }
    return false;
  }

  window.undoLastDrawing = function (containerId) {
    const symbol = STATE.currentSymbol;
    if (!STATE.drawings[symbol] || !STATE.drawings[symbol].length) return;
    if (containerId) {
      for (let i = STATE.drawings[symbol].length - 1; i >= 0; i--) {
        if (!STATE.drawings[symbol][i].containerId || STATE.drawings[symbol][i].containerId === containerId) {
          STATE.drawings[symbol].splice(i, 1);
          break;
        }
      }
    } else {
      STATE.drawings[symbol].pop();
    }
    localStorage.setItem('tv_drawings', JSON.stringify(STATE.drawings));
    ['chart-container-1d', 'chart-container-1h', 'chart-container-5m'].forEach(id => {
      const chart = id === 'chart-container-1d' ? STATE.charts.macro : (id === 'chart-container-1h' ? STATE.charts.setup : STATE.charts.trigger);
      redrawAllDrawings(id, chart);
    });
  };

  window.clearAllDrawings = function () {
    STATE.drawings[STATE.currentSymbol] = [];
    localStorage.setItem('tv_drawings', JSON.stringify(STATE.drawings));
    ['chart-container-1d', 'chart-container-1h', 'chart-container-5m'].forEach(id => {
      const chart = id === 'chart-container-1d' ? STATE.charts.macro : (id === 'chart-container-1h' ? STATE.charts.setup : STATE.charts.trigger);
      redrawAllDrawings(id, chart);
    });
  };

  window.setTvTool = function (toolName) {
    if (toolName === 'cursor' || STATE.activeTool === toolName || !toolName) {
      STATE.activeTool = null;
    } else {
      STATE.activeTool = toolName;
    }

    // Actualizar estilos de todos los botones de herramientas
    document.querySelectorAll('[data-tv-tool]').forEach(btn => {
      const t = btn.getAttribute('data-tv-tool');
      if (t === (STATE.activeTool || 'cursor')) {
        btn.classList.add('bg-indigo-600', 'text-white', 'ring-2', 'ring-indigo-400');
      } else {
        btn.classList.remove('bg-indigo-600', 'text-white', 'ring-2', 'ring-indigo-400');
      }
    });

    // Habilitar puntero en lienzos y cambiar cursor según herramienta
    document.querySelectorAll('canvas[id$="-draw-canvas"]').forEach(cvs => {
      cvs.style.pointerEvents = STATE.activeTool ? 'auto' : 'none';
      cvs.style.cursor = STATE.activeTool === 'eraser' ? 'pointer' : (STATE.activeTool ? 'crosshair' : 'default');
    });

    // Banner HUD flotante de herramienta activa
    let hud = document.getElementById('tv-active-tool-hud');
    if (STATE.activeTool) {
      if (!hud) {
        hud = document.createElement('div');
        hud.id = 'tv-active-tool-hud';
        hud.className = 'fixed top-3 left-1/2 -translate-x-1/2 z-[1000005] px-4 py-2 rounded-xl bg-indigo-950/95 border border-indigo-400 text-white font-mono text-xs shadow-2xl flex items-center gap-3 backdrop-blur-xl animate-pulse';
        document.body.appendChild(hud);
      }
      const toolNames = {
        cursor: '🖱️ Cursor / Modo Puntero',
        trendline: '📏 Línea de Tendencia / Directriz',
        fibonacci: '📐 Retroceso de Fibonacci Pro',
        box: '🔲 Caja / Order Block (Zonas)',
        positionLong: '📈 Posición Larga (Take Profit / Stop Loss)',
        positionShort: '📉 Posición Corta (Take Profit / Stop Loss)',
        ruler: '📏 Regla de Medición (% y recorrido)',
        eraser: '🧹 Goma de Borrar (Haz clic sobre cualquier dibujo para eliminarlo)'
      };
      hud.innerHTML = `
        <span class="w-2 h-2 rounded-full ${STATE.activeTool === 'eraser' ? 'bg-rose-400' : 'bg-emerald-400'} animate-ping"></span>
        <span>MODO ACTIVO: <strong class="${STATE.activeTool === 'eraser' ? 'text-rose-300' : 'text-indigo-300'}">${toolNames[STATE.activeTool] || STATE.activeTool}</strong></span>
        <button type="button" onclick="setTvTool('cursor')" class="ml-2 px-2.5 py-0.5 rounded bg-rose-600/90 hover:bg-rose-500 text-white font-bold text-[11px] cursor-pointer shadow">✕ Salir de Modo</button>
      `;
      hud.style.display = 'flex';
    } else if (hud) {
      hud.style.display = 'none';
    }
  };

  // =========================================================================
  // GESTOR DE PARÁMETROS DE FIBONACCI (MODAL INTERACTIVO TRADINGVIEW)
  // =========================================================================
  window.openFibSettingsModal = function () {
    const modal = document.getElementById('fibSettingsModal');
    if (!modal) return;
    window.renderFibSettingsTable();
    modal.classList.remove('hidden');
  };

  window.closeFibSettingsModal = function () {
    const modal = document.getElementById('fibSettingsModal');
    if (modal) modal.classList.add('hidden');
  };

  window.renderFibSettingsTable = function () {
    const tbody = document.getElementById('fibLevelsTableBody');
    if (!tbody) return;
    const config = getFibConfig();
    tbody.innerHTML = '';

    config.levels.forEach((lvl, idx) => {
      const tr = document.createElement('tr');
      tr.className = 'border-b border-slate-800/60 hover:bg-slate-900/50';
      tr.innerHTML = `
        <td class="p-2 text-center">
          <input type="checkbox" ${lvl.enabled ? 'checked' : ''} onchange="toggleFibLevel(${idx}, this.checked)" class="rounded bg-slate-800 border-slate-700 text-indigo-500 cursor-pointer">
        </td>
        <td class="p-2">
          <input type="number" step="0.001" value="${lvl.level}" onchange="updateFibLevelVal(${idx}, this.value)" class="w-16 px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-200 text-xs font-mono">
        </td>
        <td class="p-2">
          <input type="text" value="${lvl.name || ''}" onchange="updateFibLevelName(${idx}, this.value)" class="w-full px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-200 text-xs font-mono">
        </td>
        <td class="p-2 text-center">
          <input type="color" value="${lvl.color || '#94a3b8'}" onchange="updateFibLevelColor(${idx}, this.value)" class="w-7 h-6 rounded bg-transparent border-0 cursor-pointer">
        </td>
        <td class="p-2 text-center">
          <button type="button" onclick="deleteFibLevel(${idx})" class="text-rose-400 hover:text-rose-200 font-bold px-1.5 py-0.5 rounded hover:bg-rose-950/60 transition cursor-pointer" title="Eliminar este nivel">✕</button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    const chkGolden = document.getElementById('chkFibGoldenZone');
    if (chkGolden) chkGolden.checked = config.fillGoldenZone !== false;
  };

  window.toggleFibLevel = function (idx, enabled) {
    const config = getFibConfig();
    if (config.levels[idx]) {
      config.levels[idx].enabled = enabled;
      saveFibConfig(config);
    }
  };

  window.updateFibLevelVal = function (idx, val) {
    const config = getFibConfig();
    const num = parseFloat(val);
    if (config.levels[idx] && !isNaN(num)) {
      config.levels[idx].level = num;
      saveFibConfig(config);
    }
  };

  window.updateFibLevelName = function (idx, name) {
    const config = getFibConfig();
    if (config.levels[idx]) {
      config.levels[idx].name = name;
      saveFibConfig(config);
    }
  };

  window.updateFibLevelColor = function (idx, color) {
    const config = getFibConfig();
    if (config.levels[idx]) {
      config.levels[idx].color = color;
      saveFibConfig(config);
    }
  };

  window.deleteFibLevel = function (idx) {
    const config = getFibConfig();
    config.levels.splice(idx, 1);
    saveFibConfig(config);
    window.renderFibSettingsTable();
  };

  window.addNewFibLevel = function () {
    const valInput = document.getElementById('txtNewFibLevel');
    const nameInput = document.getElementById('txtNewFibName');
    const colorInput = document.getElementById('colNewFibColor');
    if (!valInput) return;

    const val = parseFloat(valInput.value);
    if (isNaN(val)) return;

    const config = getFibConfig();
    const name = nameInput && nameInput.value ? nameInput.value : `${val} (${(val * 100).toFixed(1)}%)`;
    const color = colorInput ? colorInput.value : '#38bdf8';

    config.levels.push({
      id: 'fib-' + Date.now(),
      level: val,
      name: name,
      color: color,
      enabled: true
    });
    config.levels.sort((a, b) => a.level - b.level);
    saveFibConfig(config);
    window.renderFibSettingsTable();

    valInput.value = '';
    if (nameInput) nameInput.value = '';
  };

  window.resetFibConfigToDefault = function () {
    localStorage.removeItem('tv_fib_config');
    window.renderFibSettingsTable();
    ['chart-container-1d', 'chart-container-1h', 'chart-container-5m'].forEach(id => {
      const chart = id === 'chart-container-1d' ? STATE.charts.macro : (id === 'chart-container-1h' ? STATE.charts.setup : STATE.charts.trigger);
      redrawAllDrawings(id, chart);
    });
  };

  window.toggleFibGoldenZone = function (checked) {
    const config = getFibConfig();
    config.fillGoldenZone = checked;
    saveFibConfig(config);
  };

  // =========================================================================
  // MÓDULO 4: AUDITOR FORENSE DE TRADES (ACTIVAS Y FINALIZADAS)
  // =========================================================================

  // Limpiar líneas de precio de la serie
  function clearPriceLines(series) {
    if (!series || !STATE.priceLines.trigger.length) return;
    STATE.priceLines.trigger.forEach(line => {
      try { series.removePriceLine(line); } catch (e) {}
    });
    STATE.priceLines.trigger = [];
  }

  // A. Operación Activa: Consultar backend y dibujar líneas vivas
  async function syncActivePositionLines(symbol, series) {
    clearPriceLines(series);
    try {
      const resp = await fetch(`${CONFIG.backendBase}/api/broker/positions`);
      if (!resp.ok) return;
      const data = await resp.json();
      STATE.backendPositions = data.positions || [];

      // Buscar posición activa en este símbolo
      const pos = STATE.backendPositions.find(p => p.symbol === symbol || p.symbol === symbol.replace('USDT', '/USDT'));
      if (!pos) return;
      if (STATE.layers && STATE.layers.tradeLines === false) return;

      const p0 = Number(pos.entry_price);
      const isShort = pos.side === 'SHORT';

      // 1. Línea de Entrada
      const lEntry = series.createPriceLine({
        price: p0,
        color: '#38bdf8',
        lineWidth: 1.5,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: `ENTRADA $${p0.toFixed(2)} (${pos.side})`
      });
      STATE.priceLines.trigger.push(lEntry);

      // 2. Línea de Stop Loss / Breakeven Real
      const stopNetPct = Number(pos.current_stop_net_pct || -pos.initial_sl_pct || -2.0);
      const slPrice = isShort ? p0 * (1 - stopNetPct / 100) : p0 * (1 + stopNetPct / 100);
      const isBreakeven = pos.be_armed === 1 || stopNetPct >= 0.15;

      const lSl = series.createPriceLine({
        price: slPrice,
        color: isBreakeven ? '#f59e0b' : '#ef4444',
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: isBreakeven ? `🛡️ BREAKEVEN REAL (+${stopNetPct.toFixed(2)}% NETO)` : `STOP LOSS (-${Math.abs(stopNetPct).toFixed(2)}%)`
      });
      STATE.priceLines.trigger.push(lSl);

      // 3. Línea de Take Profit
      const tpPct = Number(pos.initial_tp_pct || 6.0);
      const tpPrice = isShort ? p0 * (1 - tpPct / 100) : p0 * (1 + tpPct / 100);
      const lTp = series.createPriceLine({
        price: tpPrice,
        color: '#10b981',
        lineWidth: 1.5,
        lineStyle: LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: `TAKE PROFIT (+${tpPct.toFixed(1)}%)`
      });
      STATE.priceLines.trigger.push(lTp);

      // 4. Pico Máximo (Peak / MFE)
      if (pos.peak_price && Number(pos.peak_price) > 0) {
        const peakPx = Number(pos.peak_price);
        const lPeak = series.createPriceLine({
          price: peakPx,
          color: '#06b6d4',
          lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dotted,
          axisLabelVisible: true,
          title: `PICO MÁX $${peakPx.toFixed(2)}`
        });
        STATE.priceLines.trigger.push(lPeak);
      }
    } catch (err) {
      console.warn("Backend broker offline:", err.message);
    }
  }

  // B. Operaciones Finalizadas: Consultar trades de SQLite y poblar selector forense
  async function fetchAndPopulateClosedTrades(symbol) {
    const sel = document.getElementById('selAuditedTrades');
    if (!sel) return;

    try {
      const resp = await fetch(`${CONFIG.backendBase}/api/broker/trades`);
      if (!resp.ok) return;
      const data = await resp.json();
      STATE.backendTrades = (data.trades || []).filter(t => t.status === 'CLOSED');

      const symClean = symbol.replace('USDT', '/USDT');
      const filtered = STATE.backendTrades.filter(t => t.symbol === symbol || t.symbol === symClean);

      sel.innerHTML = '<option value="">-- Seleccionar trade cerrado para auditar --</option>';
      filtered.slice(0, 15).forEach(t => {
        const pnl = Number(t.realized_pnl || 0);
        const sign = pnl >= 0 ? '+' : '';
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.innerText = `${t.closed_at.slice(5, 16)} · ${t.symbol} · ${sign}$${pnl.toFixed(2)} (${t.exit_reason || 'Cerrado'})`;
        sel.appendChild(opt);
      });
    } catch (err) {
      console.warn("Error cargando historial de trades:", err);
    }
  }

  // C. Centrar gráfico y dibujar el trade finalizado inspeccionado
  window.destildarTradeAudit = function () {
    STATE.selectedAuditedTrade = null;
    clearPriceLines(STATE.series.trigger);

    // Ocultar card de auditoría
    const infoCard = document.getElementById('cardAuditedTradeInfo');
    if (infoCard) infoCard.classList.add('hidden');

    // Resetear selector y ocultar botón destildar
    const sel = document.getElementById('selAuditedTrades');
    if (sel) sel.value = '';
    const btnDestildar = document.getElementById('btnDestildarTrade');
    if (btnDestildar) btnDestildar.classList.add('hidden');

    // Deshacer blureo del panel lateral
    const sidebar = document.getElementById('sidebar-panel');
    if (sidebar) {
      sidebar.style.filter = '';
      sidebar.style.opacity = '';
      sidebar.style.pointerEvents = '';
    }

    // Restaurar escala temporal al flujo en vivo
    if (STATE.charts.trigger && typeof STATE.charts.trigger.timeScale === 'function') {
      STATE.charts.trigger.timeScale().resetTimeScale();
    }
  };

  window.inspectClosedTrade = function (tradeId) {
    if (!tradeId) {
      window.destildarTradeAudit();
      return;
    }

    const t = STATE.backendTrades.find(x => x.id === tradeId);
    if (!t) return;
    STATE.selectedAuditedTrade = t;

    // Mostrar botón de Destildar en la barra superior
    const btnDestildar = document.getElementById('btnDestildarTrade');
    if (btnDestildar) btnDestildar.classList.remove('hidden');

    // Blurear suavemente el panel lateral para enfatizar el análisis forense de velas pasadas
    const sidebar = document.getElementById('sidebar-panel');
    if (sidebar) {
      sidebar.style.filter = 'blur(1.5px)';
      sidebar.style.opacity = '0.45';
      sidebar.style.transition = 'filter 0.3s ease, opacity 0.3s ease';
      sidebar.style.pointerEvents = 'none';
    }

    const series = STATE.series.trigger;
    const chart = STATE.charts.trigger;
    clearPriceLines(series);

    const p0 = Number(t.entry_price);
    const ps = Number(t.exit_price);
    const pnl = Number(t.realized_pnl || 0);
    const cost = Number(t.cost_basis || 87.2);
    const netPct = (pnl / cost * 100);

    // Dibujar líneas de precio si la capa tradeLines está activa
    if (STATE.layers && STATE.layers.tradeLines !== false) {
      // 1. Línea Entrada ($P0)
      const lEntry = series.createPriceLine({
        price: p0,
        color: '#38bdf8',
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: `[HISTÓRICO] ENTRADA $${p0.toFixed(2)}`
      });
      STATE.priceLines.trigger.push(lEntry);

      // 2. Línea Salida ($Ps)
      const lExit = series.createPriceLine({
        price: ps,
        color: pnl >= 0 ? '#10b981' : '#ef4444',
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: `[SALIDA] $${ps.toFixed(2)} (${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)} / ${netPct.toFixed(2)}%)`
      });
      STATE.priceLines.trigger.push(lExit);

      // 3. Línea de Pico si existe
      if (t.peak_price) {
        const lPeak = series.createPriceLine({
          price: Number(t.peak_price),
          color: '#06b6d4',
          lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dotted,
          axisLabelVisible: true,
          title: `MFE PICO: $${Number(t.peak_price).toFixed(2)}`
        });
        STATE.priceLines.trigger.push(lPeak);
      }
    }

    // 4. Centrar rango temporal en la ventana del trade
    const t0 = Math.floor(new Date(t.opened_at + 'Z').getTime() / 1000);
    const t1 = Math.floor(new Date(t.closed_at + 'Z').getTime() / 1000);
    if (!isNaN(t0) && !isNaN(t1)) {
      const padding = Math.max(3600, (t1 - t0) * 0.35);
      chart.timeScale().setVisibleRange({
        from: t0 - padding,
        to: t1 + padding
      });
    }

    // 5. Desplegar Ficha Técnica de Auditoría
    const infoCard = document.getElementById('cardAuditedTradeInfo');
    if (infoCard) {
      infoCard.classList.remove('hidden');
      document.getElementById('auditCardId').innerText = t.id.slice(0, 8);
      document.getElementById('auditCardSymbol').innerText = t.symbol;
      document.getElementById('auditCardPnl').innerHTML = `<span class="${pnl >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(4)} (${netPct.toFixed(2)}%)</span>`;
      document.getElementById('auditCardExitReason').innerText = t.exit_reason || 'Desconocido';
      document.getElementById('auditCardOpened').innerText = t.opened_at;
      document.getElementById('auditCardClosed').innerText = t.closed_at;
      document.getElementById('auditCardFees').innerText = `$${Number(t.total_fees || 0).toFixed(4)}`;
      document.getElementById('auditCardFormula').innerText = t.formula || t.strategy || 'N/A';
    }
  };

  // =========================================================================
  // MÓDULO: CONTROL DE CAPAS E INDICADORES VISUALES
  // =========================================================================

  // Suavizado Heikin Ashi
  function toHeikinAshi(candles) {
    if (!candles || !candles.length) return [];
    const ha = [];
    let prevOpen = candles[0].open;
    let prevClose = candles[0].close;

    for (let i = 0; i < candles.length; i++) {
      const c = candles[i];
      const haClose = (c.open + c.high + c.low + c.close) / 4;
      const haOpen = i === 0 ? (c.open + c.close) / 2 : (prevOpen + prevClose) / 2;
      const haHigh = Math.max(c.high, haOpen, haClose);
      const haLow = Math.min(c.low, haOpen, haClose);

      ha.push({
        time: c.time,
        open: haOpen,
        high: haHigh,
        low: haLow,
        close: haClose
      });

      prevOpen = haOpen;
      prevClose = haClose;
    }
    return ha;
  }

  // Aplicar visibilidad de todas las capas
  function applyChartLayers() {
    const L = STATE.layers;
    if (!L) return;

    // 1. Patrones de velas (Martillo, Three White Soldiers, Morning Star, S/R)
    if (window.series1D) {
      if (L.candlePatterns && window.lastCalculatedMarkers?.macro) {
        try { window.series1D.setMarkers(window.lastCalculatedMarkers.macro); } catch (e) {}
      } else {
        try { window.series1D.setMarkers([]); } catch (e) {}
      }
    }
    if (window.series5M) {
      if (L.candlePatterns && window.lastCalculatedMarkers?.trigger) {
        try { window.series5M.setMarkers(window.lastCalculatedMarkers.trigger); } catch (e) {}
      } else {
        try { window.series5M.setMarkers([]); } catch (e) {}
      }
    }

    // 2. VWAP Multisesión y bandas
    const vwapVis = !!L.vwap;
    Object.values(STATE.vwapSeries).forEach(s => {
      if (s && typeof s.applyOptions === 'function') {
        try { s.applyOptions({ visible: vwapVis }); } catch (e) {}
      }
    });

    // 3. Medias móviles (EMA 50 y EMA 20)
    const emaVis = !!L.ema;
    if (window.ema1D && typeof window.ema1D.applyOptions === 'function') {
      try { window.ema1D.applyOptions({ visible: emaVis }); } catch (e) {}
    }
    if (window.ema1H && typeof window.ema1H.applyOptions === 'function') {
      try { window.ema1H.applyOptions({ visible: emaVis }); } catch (e) {}
    }

    // 4. Histograma y Sub-ventanas Inferiores de Volumen en los 3 Gráficos
    const volVis = !!L.volume;
    ['volume-pane-1d', 'volume-pane-1h', 'volume-pane-5m'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = volVis ? 'block' : 'none';
    });
    [window.chart1D, window.chart1H, window.chart5M].forEach(ch => {
      if (ch && ch.timeScale) {
        try { ch.timeScale().applyOptions({ visible: !volVis }); } catch (e) {}
      }
    });
    [window.volChart1D, window.volChart1H, window.volChart5M].forEach(vch => {
      if (vch && vch.timeScale) {
        try { vch.timeScale().applyOptions({ visible: volVis }); } catch (e) {}
      }
    });
    if (window.volume1D && typeof window.volume1D.applyOptions === 'function') {
      try { window.volume1D.applyOptions({ visible: volVis }); } catch (e) {}
    }
    if (window.volume1H && typeof window.volume1H.applyOptions === 'function') {
      try { window.volume1H.applyOptions({ visible: volVis }); } catch (e) {}
    }
    if (window.volume5M && typeof window.volume5M.applyOptions === 'function') {
      try { window.volume5M.applyOptions({ visible: volVis }); } catch (e) {}
    }
    if (typeof window.reapplyAllMarkers === 'function') {
      window.reapplyAllMarkers();
    }
    if (typeof window.redrawAllPocLines === 'function') {
      window.redrawAllPocLines();
    }
    if (typeof window.reflowAllCharts === 'function') {
      window.reflowAllCharts();
    }

    // 5. Volume Profile Horizontal (VPVR)
    const vpCvs = document.getElementById('chart-container-5m-vp-canvas');
    if (vpCvs) {
      vpCvs.style.display = L.volumeProfile ? 'block' : 'none';
    }
    if (L.volumeProfile && STATE.lastVolumeProfile) {
      renderVolumeProfileOverlay('chart-container-5m', STATE.lastVolumeProfile);
    }

    // 6. Líneas de Trades (Activos y Auditados)
    if (!L.tradeLines) {
      if (window.series5M) clearPriceLines(window.series5M);
    } else {
      if (STATE.selectedAuditedTrade) {
        window.inspectClosedTrade(STATE.selectedAuditedTrade.id);
      } else if (window.series5M && STATE.currentSymbol) {
        syncActivePositionLines(STATE.currentSymbol, window.series5M);
      }
    }

    // 7. Capa de Dibujos del usuario
    document.querySelectorAll('canvas[id$="-draw-canvas"]').forEach(cvs => {
      cvs.style.display = L.drawings !== false ? 'block' : 'none';
    });

    // 8. Heikin Ashi vs Velas Tradicionales
    if (window.series1D && STATE.data.macro && STATE.data.macro.length) {
      const d1 = L.heikinAshi ? toHeikinAshi(STATE.data.macro) : STATE.data.macro;
      try { window.series1D.setData(d1); } catch (e) {}
    }
    if (window.series1H && STATE.data.setup && STATE.data.setup.length) {
      const d2 = L.heikinAshi ? toHeikinAshi(STATE.data.setup) : STATE.data.setup;
      try { window.series1H.setData(d2); } catch (e) {}
    }
    if (window.series5M && STATE.data.trigger && STATE.data.trigger.length) {
      const d3 = L.heikinAshi ? toHeikinAshi(STATE.data.trigger) : STATE.data.trigger;
      try { window.series5M.setData(d3); } catch (e) {}
    }

    // Sincronizar UI de botones y checkboxes
    updateLayerUI();
  }

  // Actualizar indicadores visuales de botones y checkboxes
  function updateLayerUI() {
    const L = STATE.layers;
    if (!L) return;

    // Checkboxes del modal si está abierto/presente en DOM
    const chkMap = {
      chkLayerPatterns: L.candlePatterns,
      chkLayerCandlePoc: L.candlePoc,
      chkLayerVwap: L.vwap,
      chkLayerEma: L.ema,
      chkLayerVolumeProfile: L.volumeProfile,
      chkLayerVolume: L.volume,
      chkLayerTradeLines: L.tradeLines,
      chkLayerDrawings: L.drawings,
      chkLayerHeikinAshi: L.heikinAshi
    };
    Object.entries(chkMap).forEach(([id, val]) => {
      const el = document.getElementById(id);
      if (el) el.checked = !!val;
    });

    const setBtnState = (btnId, active, activeClasses, inactiveClasses) => {
      const btn = document.getElementById(btnId);
      if (!btn) return;
      btn.className = active ? activeClasses : inactiveClasses;
    };

    // Barra de Navegación Superior (<nav>)
    setBtnState('btnLayerCandlePatterns', L.candlePatterns,
      'px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 cursor-pointer bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm',
      'px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 cursor-pointer bg-slate-900/80 text-slate-500 border border-slate-800 opacity-60 line-through'
    );

    setBtnState('btnLayerCandlePoc', L.candlePoc,
      'px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 cursor-pointer bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm',
      'px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 cursor-pointer bg-slate-900/80 text-slate-500 border border-slate-800 opacity-60 line-through'
    );

    setBtnState('btnLayerVwap', L.vwap,
      'px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 cursor-pointer bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm',
      'px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 cursor-pointer bg-slate-900/80 text-slate-500 border border-slate-800 opacity-60 line-through'
    );

    setBtnState('btnLayerEma', L.ema,
      'px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 cursor-pointer bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm',
      'px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 cursor-pointer bg-slate-900/80 text-slate-500 border border-slate-800 opacity-60 line-through'
    );

    setBtnState('btnLayerVolumeProfile', L.volumeProfile,
      'px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 cursor-pointer bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-sm',
      'px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 cursor-pointer bg-slate-900/80 text-slate-500 border border-slate-800 opacity-60 line-through'
    );

    // Botones rápidos en cabeceras de gráficos
    setBtnState('btnHdrLayerEma1D', L.ema,
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-amber-500/20 text-amber-300 border border-amber-500/40 cursor-pointer',
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-slate-950 text-slate-500 border border-slate-800 opacity-60 cursor-pointer line-through'
    );

    setBtnState('btnHdrLayerPatterns1D', L.candlePatterns,
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 cursor-pointer',
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-slate-950 text-slate-500 border border-slate-800 opacity-60 cursor-pointer line-through'
    );

    setBtnState('btnHdrLayerEma1H', L.ema,
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-purple-500/20 text-purple-300 border border-purple-500/40 cursor-pointer',
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-slate-950 text-slate-500 border border-slate-800 opacity-60 cursor-pointer line-through'
    );

    setBtnState('btnHdrLayerVwap', L.vwap,
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 cursor-pointer',
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-slate-950 text-slate-500 border border-slate-800 opacity-60 cursor-pointer line-through'
    );

    setBtnState('btnHdrLayerPatterns5M', L.candlePatterns,
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 cursor-pointer',
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-slate-950 text-slate-500 border border-slate-800 opacity-60 cursor-pointer line-through'
    );

    setBtnState('btnHdrLayerVPVR', L.volumeProfile,
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 cursor-pointer',
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-slate-950 text-slate-500 border border-slate-800 opacity-60 cursor-pointer line-through'
    );

    setBtnState('btnHdrLayerTrades', L.tradeLines,
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-amber-500/20 text-amber-300 border border-amber-500/40 cursor-pointer',
      'px-1.5 py-0.5 rounded text-[10px] font-bold transition bg-slate-950 text-slate-500 border border-slate-800 opacity-60 cursor-pointer line-through'
    );
  }

  // Métodos expuestos globalmente para control de capas
  window.toggleChartLayer = function (layerKey, forceVal) {
    if (forceVal !== undefined) {
      STATE.layers[layerKey] = !!forceVal;
    } else {
      STATE.layers[layerKey] = !STATE.layers[layerKey];
    }
    localStorage.setItem('tv_chart_layers_v2', JSON.stringify(STATE.layers));
    applyChartLayers();
    return STATE.layers[layerKey];
  };

  window.toggleCandlePocLayer = function (forceVal) {
    return window.toggleChartLayer('candlePoc', forceVal);
  };

  window.openLayersModal = function () {
    const modal = document.getElementById('layersModal');
    if (modal) {
      updateLayerUI();
      modal.classList.remove('hidden');
    }
  };

  window.closeLayersModal = function () {
    const modal = document.getElementById('layersModal');
    if (modal) modal.classList.add('hidden');
  };

  window.enableAllLayers = function () {
    Object.keys(STATE.layers).forEach(k => {
      if (k !== 'heikinAshi') STATE.layers[k] = true;
    });
    localStorage.setItem('tv_chart_layers_v2', JSON.stringify(STATE.layers));
    applyChartLayers();
  };

  window.disableAllLayers = function () {
    Object.keys(STATE.layers).forEach(k => {
      if (k !== 'heikinAshi') STATE.layers[k] = false;
    });
    localStorage.setItem('tv_chart_layers_v2', JSON.stringify(STATE.layers));
    applyChartLayers();
  };

  window.isLayerActive = function (layerKey) {
    return Boolean(STATE.layers && STATE.layers[layerKey] === true);
  };

  // =========================================================================
  // MÓDULO 5: SIMULACIÓN BAR REPLAY & PAPER TRADING
  // =========================================================================
  window.toggleBarReplay = function () {
    const bar = document.getElementById('barReplayControls');
    if (!bar) return;
    STATE.replay.active = !STATE.replay.active;
    if (STATE.replay.active) {
      bar.classList.remove('hidden');
      STATE.replay.fullDataset = [...STATE.data.trigger];
      STATE.replay.cutoffIndex = Math.max(20, Math.floor(STATE.replay.fullDataset.length * 0.65));
      applyReplayCutoff();
    } else {
      bar.classList.add('hidden');
      clearInterval(STATE.replay.timer);
      STATE.replay.paused = true;
      STATE.series.trigger.setData(STATE.data.trigger);
      STATE.charts.trigger.timeScale().fitContent();
    }
  };

  function applyReplayCutoff() {
    const sliced = STATE.replay.fullDataset.slice(0, STATE.replay.cutoffIndex);
    STATE.series.trigger.setData(sliced);
    document.getElementById('replayCurrentBar').innerText = `${STATE.replay.cutoffIndex} / ${STATE.replay.fullDataset.length}`;
  }

  window.replayPlayPause = function () {
    const btn = document.getElementById('btnReplayPlay');
    if (STATE.replay.paused) {
      STATE.replay.paused = false;
      if (btn) btn.innerHTML = '⏸️ Pausar';
      STATE.replay.timer = setInterval(() => {
        if (STATE.replay.cutoffIndex < STATE.replay.fullDataset.length) {
          STATE.replay.cutoffIndex++;
          applyReplayCutoff();
        } else {
          window.replayPlayPause();
        }
      }, STATE.replay.speed);
    } else {
      STATE.replay.paused = true;
      if (btn) btn.innerHTML = '▶️ Reproducir';
      clearInterval(STATE.replay.timer);
    }
  };

  window.replayStepForward = function () {
    if (STATE.replay.cutoffIndex < STATE.replay.fullDataset.length) {
      STATE.replay.cutoffIndex++;
      applyReplayCutoff();
    }
  };

  window.setReplaySpeed = function (speedMultiplier) {
    STATE.replay.speed = Math.floor(1000 / speedMultiplier);
    if (!STATE.replay.paused) {
      clearInterval(STATE.replay.timer);
      window.replayPlayPause();
      window.replayPlayPause();
    }
  };

  // Paper Trading Operations
  window.executePaperOrder = function (action) {
    const lastCandle = STATE.data.trigger[STATE.data.trigger.length - 1];
    if (!lastCandle) return;
    const px = lastCandle.close;
    const slInput = parseFloat(document.getElementById('paperSlInput')?.value || 1.5);
    const tpInput = parseFloat(document.getElementById('paperTpInput')?.value || 3.0);
    const qtyUsdt = parseFloat(document.getElementById('paperQtyInput')?.value || 100.0);

    const isBuy = action === 'BUY';
    const slPrice = isBuy ? px * (1 - slInput / 100) : px * (1 + slInput / 100);
    const tpPrice = isBuy ? px * (1 + tpInput / 100) : px * (1 - tpInput / 100);

    const pos = {
      id: 'paper_' + Date.now(),
      symbol: STATE.currentSymbol,
      side: isBuy ? 'LONG' : 'SHORT',
      entryPrice: px,
      slPrice,
      tpPrice,
      qtyUsdt,
      openedAt: new Date().toISOString()
    };

    STATE.paper.positions.push(pos);
    localStorage.setItem('tv_paper_account', JSON.stringify(STATE.paper));
    updatePaperTradingUI();
    alert(`✅ Orden Paper ${action} ejecutada a $${px.toFixed(2)} | SL: $${slPrice.toFixed(2)} | TP: $${tpPrice.toFixed(2)}`);
  };

  function updatePaperTradingUI() {
    const elBal = document.getElementById('paperBalanceDisplay');
    const elPosCount = document.getElementById('paperOpenPositionsCount');
    if (elBal) elBal.innerText = `$${STATE.paper.balance.toFixed(2)} USDT`;
    if (elPosCount) elPosCount.innerText = `${STATE.paper.positions.length} Abiertas`;
  }

  // =========================================================================
  // MÓDULO 6: WEBHOOK DISPATCHER (PUENTE A PYTHON)
  // =========================================================================
  window.dispatchSignalWebhook = async function (action, symbol, px, sl, tp) {
    const webhookUrl = localStorage.getItem('tv_webhook_url') || `${CONFIG.backendBase}/api/broker/entry`;
    const payload = {
      symbol: symbol || STATE.currentSymbol,
      action: action || 'BUY',
      price: px || STATE.data.trigger[STATE.data.trigger.length - 1].close,
      sl_pct: sl || 2.0,
      tp_pct: tp || 6.0,
      qty: 87.2,
      source: 'tradingview_cockpit_v3'
    };

    try {
      const res = await fetch(webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      console.log("⚡ Webhook enviado con éxito:", data);
      alert(`⚡ Webhook enviado a Python (${payload.action} ${payload.symbol}): ${JSON.stringify(data.status || 'OK')}`);
    } catch (e) {
      console.error("Error disparando Webhook:", e);
      alert(`⚠️ Fallo al conectar con el servidor Python (:18767): ${e.message}`);
    }
  };

  // =========================================================================
  // MÓDULO 7: SCREENER LIVIANO DE LA CESTA
  // =========================================================================
  async function refreshScreenerTable() {
    const tbody = document.getElementById('screenerTableBody');
    if (!tbody) return;

    for (let item of CONFIG.symbolsBasket) {
      try {
        if (item.symbol.includes('USDT')) {
          const resp = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=${item.symbol}`);
          if (!resp.ok) continue;
          const t = await resp.json();
          STATE.screenerData[item.symbol] = {
            price: parseFloat(t.lastPrice),
            chg24h: parseFloat(t.priceChangePercent),
            volume: parseFloat(t.quoteVolume)
          };
        }
      } catch (e) {}
    }

    let html = '';
    CONFIG.symbolsBasket.forEach(item => {
      const d = STATE.screenerData[item.symbol] || { price: 0, chg24h: 0, volume: 0 };
      const chgColor = d.chg24h >= 0 ? 'text-emerald-400' : 'text-rose-400';
      const isSelected = item.symbol === STATE.currentSymbol;

      html += `
        <tr class="border-b border-slate-800/80 hover:bg-slate-800/50 cursor-pointer ${isSelected ? 'bg-indigo-950/40' : ''}" onclick="window.selectScreenerAsset('${item.symbol}')">
          <td class="p-2 font-mono font-bold text-white">${item.symbol.replace('USDT', '')}</td>
          <td class="p-2 font-mono text-gray-300 text-right">$${d.price >= 100 ? d.price.toFixed(2) : d.price.toFixed(4)}</td>
          <td class="p-2 font-mono font-bold text-right ${chgColor}">${d.chg24h >= 0 ? '+' : ''}${d.chg24h.toFixed(2)}%</td>
          <td class="p-2 text-right">
            <span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-800 text-gray-400">${item.market}</span>
          </td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  }

  window.selectScreenerAsset = function (sym) {
    if (typeof window.changeAsset === 'function') {
      window.changeAsset(sym);
    }
  };

  // =========================================================================
  // MÓDULO 8: SINCRONIZACIÓN MULTI-GRÁFICO Y SESIONES
  // =========================================================================
  function syncCrosshairMovements() {
    const { macro, setup, trigger } = STATE.charts;
    if (!macro || !setup || !trigger) return;

    // Crosshair Sync
    const chartsArr = [macro, setup, trigger];
    chartsArr.forEach((c, idx) => {
      c.subscribeCrosshairMove(param => {
        if (!param || !param.time) return;
        chartsArr.forEach((other, oIdx) => {
          if (idx !== oIdx) {
            // sincronizar posición relativa de tiempo
          }
        });
      });
    });
  }

  // =========================================================================
  // MAXIMIZAR PANELES & PANTALLA COMPLETA TOTAL (100% VIEWPORT OVERLAY)
  // =========================================================================
  let currentMaximized = null;

  function reflowAllChartsMultipleTimes() {
    const doReflow = () => {
      const chartMap = [
        { id: 'chart-container-1d', chart: STATE.charts.macro || window.chart1D },
        { id: 'volume-container-1d', chart: window.volChart1D },
        { id: 'chart-container-1h', chart: STATE.charts.setup || window.chart1H },
        { id: 'volume-container-1h', chart: window.volChart1H },
        { id: 'chart-container-5m', chart: STATE.charts.trigger || window.chart5M },
        { id: 'volume-container-5m', chart: window.volChart5M },
      ];
      chartMap.forEach(({ id, chart }) => {
        const c = document.getElementById(id);
        if (c && chart) {
          const w = c.clientWidth;
          const h = c.clientHeight;
          if (w > 20 && h > 20) {
            chart.resize(w, h);
          }
        }
        const cvs = document.getElementById(id + '-draw-canvas');
        if (c && cvs) {
          cvs.width = c.clientWidth;
          cvs.height = c.clientHeight;
          if (typeof redrawAllDrawings === 'function') redrawAllDrawings(id, chart);
        }
      });

      if (typeof window.applyTradingViewProportions === 'function') {
        if (currentMaximized === '1d' && window.chart1D && window.volChart1D && window._last1D) {
          window.applyTradingViewProportions(window.chart1D, window.volChart1D, window._last1D);
        } else if (currentMaximized === '1h' && window.chart1H && window.volChart1H && window._last1H) {
          window.applyTradingViewProportions(window.chart1H, window.volChart1H, window._last1H);
        } else if (currentMaximized === '5m' && window.chart5M && window.volChart5M && window._lastTrigger) {
          window.applyTradingViewProportions(window.chart5M, window.volChart5M, window._lastTrigger);
        }
      }
      if (typeof window.redrawAllPocLines === 'function') {
        window.redrawAllPocLines();
      }
    };

    requestAnimationFrame(doReflow);
    setTimeout(doReflow, 30);
    setTimeout(doReflow, 100);
    setTimeout(doReflow, 250);
    setTimeout(doReflow, 450);
  }
  window.reflowAllCharts = reflowAllChartsMultipleTimes;

  // Restaurar y fijar proporciones exactas del layout
  function resetAllLayoutDimensions() {
    const sec1d = document.getElementById('section-chart-1d');
    const secLower = document.getElementById('section-charts-lower');
    const p1h = document.getElementById('panel-chart-1h');
    const p5m = document.getElementById('panel-chart-5m');
    const lowerH = window.currentLowerHeight || '54vh';
    const upperH = lowerH === '44vh' ? '40vh' : (lowerH === '66vh' ? '58vh' : '48vh');
    const upperMinH = lowerH === '44vh' ? '320px' : (lowerH === '66vh' ? '470px' : '390px');
    const lowerMinH = lowerH === '44vh' ? '360px' : (lowerH === '66vh' ? '520px' : '430px');

    if (sec1d && !sec1d.getAttribute('data-fullscreen-active')) {
      sec1d.classList.remove('hidden');
      sec1d.style.height = upperH;
      sec1d.style.minHeight = upperMinH;
      sec1d.style.maxHeight = '';
      sec1d.style.overflow = 'hidden';
    }
    if (secLower) {
      secLower.classList.remove('hidden');
      secLower.style.height = lowerH;
      secLower.style.minHeight = lowerMinH;
      secLower.style.maxHeight = '';
      secLower.style.overflow = 'hidden';
    }
    if (p1h && !p1h.getAttribute('data-fullscreen-active')) {
      p1h.classList.remove('hidden');
      p1h.style.height = '100%';
      p1h.style.minHeight = '0';
      p1h.style.maxHeight = '';
      p1h.style.overflow = 'hidden';
    }
    if (p5m && !p5m.getAttribute('data-fullscreen-active')) {
      p5m.classList.remove('hidden');
      p5m.style.height = '100%';
      p5m.style.minHeight = '0';
      p5m.style.maxHeight = '';
      p5m.style.overflow = 'hidden';
    }
  }

  window.exitChartFullscreen = function () {
    const sec1d = document.getElementById('section-chart-1d');
    const secLower = document.getElementById('section-charts-lower');
    const p1h = document.getElementById('panel-chart-1h');
    const p5m = document.getElementById('panel-chart-5m');
    const btn1d = document.getElementById('btnMax-1d');
    const btn1h = document.getElementById('btnMax-1h');
    const btn5m = document.getElementById('btnMax-5m');

    // 1. Eliminar botón flotante si existiera
    const floatingBtn = document.getElementById('btnExitFullscreenFloating');
    if (floatingBtn) floatingBtn.remove();

    const sidebar = document.getElementById('sidebar-panel');
    const footer = document.querySelector('footer');
    const tvToolbar = document.getElementById('tv-vertical-toolbar');
    const mainCol = document.getElementById('charts-main-column');

    // 1. Restaurar sidebar (Estrategia Matemática), footer y toolbar
    if (sidebar) sidebar.style.display = '';
    if (footer) footer.style.display = '';
    if (tvToolbar) tvToolbar.style.display = '';
    if (mainCol) {
      mainCol.style.width = '';
      mainCol.style.maxWidth = '';
      mainCol.style.flex = '';
    }

    // 2. Limpiar estilos forzados de maximización en todos los paneles
    [sec1d, p1h, p5m].forEach(el => {
      if (!el) return;
      el.removeAttribute('data-fullscreen-active');
      el.style.position = '';
      el.style.top = '';
      el.style.left = '';
      el.style.right = '';
      el.style.bottom = '';
      el.style.width = '';
      el.style.height = '';
      el.style.minHeight = '';
      el.style.maxHeight = '';
      el.style.maxWidth = '';
      el.style.zIndex = '';
      el.style.margin = '';
      el.style.borderRadius = '';
      el.style.border = '';
      el.style.backgroundColor = '';
      el.style.boxShadow = '';
      el.style.padding = '';
      el.style.boxSizing = '';
      el.style.display = '';
      el.style.flexDirection = '';
      el.style.overflow = '';
      el.classList.remove('hidden');
    });

    if (secLower) {
      secLower.removeAttribute('data-fullscreen-active');
      secLower.style.height = '';
      secLower.style.minHeight = '';
      secLower.style.maxHeight = '';
      secLower.style.width = '';
      secLower.classList.remove('hidden');
      secLower.classList.remove('grid-cols-1');
      secLower.classList.add('md:grid-cols-2');
    }

    // 3. Restaurar dimensiones estrictas balanceadas
    resetAllLayoutDimensions();

    // 4. Restaurar botones originales
    if (btn1d) {
      btn1d.innerHTML = '⛶ Maximizar';
      btn1d.className = 'text-amber-300 hover:text-white px-2 py-0.5 rounded bg-amber-950/80 border border-amber-600/40 text-[10px] cursor-pointer font-bold whitespace-nowrap';
    }
    if (btn1h) {
      btn1h.innerHTML = '⛶ Maximizar';
      btn1h.className = 'text-indigo-200 hover:text-white px-2 py-0.5 rounded bg-indigo-800/80 hover:bg-indigo-700 border border-indigo-400/60 cursor-pointer font-bold whitespace-nowrap shadow-sm';
    }
    if (btn5m) {
      btn5m.innerHTML = '⛶ Maximizar';
      btn5m.className = 'text-emerald-200 hover:text-white px-2 py-0.5 rounded bg-emerald-800/80 hover:bg-emerald-700 border border-emerald-400/60 cursor-pointer font-bold whitespace-nowrap shadow-sm';
    }

    // 5. Restaurar scroll del body
    document.body.style.overflow = '';

    currentMaximized = null;

    // 6. Reflujo adaptativo multietapa para asegurar el reajuste exacto de los 3 gráficos
    reflowAllChartsMultipleTimes();
  };

  window.toggleMaximizeChart = function (chartKey) {
    if (currentMaximized === chartKey) {
      window.exitChartFullscreen();
      return;
    }

    // Si ya había otro gráfico maximizado, salir primero a estado limpio
    if (currentMaximized) {
      window.exitChartFullscreen();
    }

    const sec1d = document.getElementById('section-chart-1d');
    const secLower = document.getElementById('section-charts-lower');
    const p1h = document.getElementById('panel-chart-1h');
    const p5m = document.getElementById('panel-chart-5m');
    const sidebar = document.getElementById('sidebar-panel');
    const footer = document.querySelector('footer');
    const tvToolbar = document.getElementById('tv-vertical-toolbar');
    const mainCol = document.getElementById('charts-main-column');

    const btn1d = document.getElementById('btnMax-1d');
    const btn1h = document.getElementById('btnMax-1h');
    const btn5m = document.getElementById('btnMax-5m');

    currentMaximized = chartKey;

    // 1. Ocultar panel lateral (Estrategia Matemática) y footer inferior; mantener barra de herramientas de dibujo
    if (sidebar) sidebar.style.display = 'none';
    if (footer) footer.style.display = 'none';
    if (tvToolbar) tvToolbar.style.display = 'flex';
    if (mainCol) {
      mainCol.style.width = '100%';
      mainCol.style.maxWidth = '100%';
      mainCol.style.flex = '1 1 100%';
    }

    // 2. Altura calculada exactamente según la posición top real en pantalla (evita desborde del volumen)
    const topPos = secLower ? Math.round(secLower.getBoundingClientRect().top) : 260;
    const fullWindowHeight = `calc(100vh - ${Math.max(120, topPos + 16)}px)`;

    if (chartKey === '1d') {
      if (sec1d) {
        sec1d.setAttribute('data-fullscreen-active', 'true');
        sec1d.classList.remove('hidden');
        sec1d.style.height = `calc(100vh - ${Math.max(120, Math.round(sec1d.getBoundingClientRect().top + 16))}px)`;
        sec1d.style.minHeight = '320px';
        sec1d.style.maxHeight = '';
        sec1d.style.width = '100%';
      }
      if (secLower) {
        secLower.classList.add('hidden');
      }
      if (btn1d) {
        btn1d.innerHTML = '🗗 Restaurar (ESC)';
        btn1d.className = 'text-rose-100 hover:text-white px-2.5 py-0.5 rounded bg-rose-600/90 hover:bg-rose-500 border border-rose-400 text-[10px] cursor-pointer font-bold shadow-lg transition whitespace-nowrap';
      }
    } else if (chartKey === '1h') {
      if (sec1d) {
        sec1d.classList.add('hidden');
      }
      if (secLower) {
        secLower.classList.remove('hidden');
        secLower.classList.remove('lg:grid-cols-2', 'md:grid-cols-2');
        secLower.classList.add('grid-cols-1');
        secLower.style.height = fullWindowHeight;
        secLower.style.minHeight = fullWindowHeight;
        secLower.style.maxHeight = fullWindowHeight;
        secLower.style.width = '100%';
      }
      if (p1h) {
        p1h.setAttribute('data-fullscreen-active', 'true');
        p1h.classList.remove('hidden');
        p1h.style.height = '100%';
        p1h.style.minHeight = '100%';
        p1h.style.width = '100%';
      }
      if (p5m) {
        p5m.classList.add('hidden');
      }
      if (btn1h) {
        btn1h.innerHTML = '🗗 Restaurar (ESC)';
        btn1h.className = 'text-rose-100 hover:text-white px-2.5 py-0.5 rounded bg-rose-600/90 hover:bg-rose-500 border border-rose-400 text-[10px] cursor-pointer font-bold shadow-lg transition whitespace-nowrap';
      }
    } else if (chartKey === '5m') {
      if (sec1d) {
        sec1d.classList.add('hidden');
      }
      if (secLower) {
        secLower.classList.remove('hidden');
        secLower.classList.remove('lg:grid-cols-2', 'md:grid-cols-2');
        secLower.classList.add('grid-cols-1');
        secLower.style.height = fullWindowHeight;
        secLower.style.minHeight = fullWindowHeight;
        secLower.style.maxHeight = fullWindowHeight;
        secLower.style.width = '100%';
      }
      if (p5m) {
        p5m.setAttribute('data-fullscreen-active', 'true');
        p5m.classList.remove('hidden');
        p5m.style.height = '100%';
        p5m.style.minHeight = '100%';
        p5m.style.width = '100%';
      }
      if (p1h) {
        p1h.classList.add('hidden');
      }
      if (btn5m) {
        btn5m.innerHTML = '🗗 Restaurar (ESC)';
        btn5m.className = 'text-rose-100 hover:text-white px-2.5 py-0.5 rounded bg-rose-600/90 hover:bg-rose-500 border border-rose-400 text-[10px] cursor-pointer font-bold shadow-lg transition whitespace-nowrap';
      }
    }

    // Reajuste reactivo múltiple de dimensiones
    reflowAllChartsMultipleTimes();
  };

  window.toggleBrowserFullscreen = function () {
    const btn = document.getElementById('btnBrowserFullscreen');

    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().then(() => {
        if (btn) btn.innerHTML = '<span>🗗</span> Salir Fullscreen (ESC)';
        // Al entrar en pantalla completa, la barra superior y la barra lateral derecha permanecen visibles y utilizables
        reflowAllChartsMultipleTimes();
      }).catch(err => console.warn(err));
    } else {
      document.exitFullscreen().then(() => {
        if (btn) btn.innerHTML = '<span>⛶</span> Pantalla Completa';
        resetAllLayoutDimensions();
        reflowAllChartsMultipleTimes();
      }).catch(err => console.warn(err));
    }
  };

  // Eventos globales para cierre con tecla ESC y cuando el usuario sale del fullscreen nativo
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' || e.key === 'Esc') {
      if (currentMaximized) {
        window.exitChartFullscreen();
      }
    }
  });

  document.addEventListener('fullscreenchange', () => {
    const btn = document.getElementById('btnBrowserFullscreen');
    if (!document.fullscreenElement) {
      if (btn) btn.innerHTML = '<span>⛶</span> Pantalla Completa';
    } else {
      if (btn) btn.innerHTML = '<span>🗗</span> Salir Fullscreen (ESC)';
    }
    reflowAllChartsMultipleTimes();
  });

  // Calibrador de altura de las ventanas de gráficos (Superior e Inferiores)
  window.currentLowerHeight = '54vh';

  window.setLowerChartsHeight = function (heightStr) {
    window.currentLowerHeight = heightStr;
    const sec1d = document.getElementById('section-chart-1d');
    const secLower = document.getElementById('section-charts-lower');
    const upperH = heightStr === '44vh' ? '40vh' : (heightStr === '66vh' ? '58vh' : '48vh');
    const upperMinH = heightStr === '44vh' ? '320px' : (heightStr === '66vh' ? '470px' : '390px');
    const lowerMinH = heightStr === '44vh' ? '360px' : (heightStr === '66vh' ? '520px' : '430px');

    if (sec1d && !sec1d.classList.contains('hidden')) {
      sec1d.style.height = upperH;
      sec1d.style.minHeight = upperMinH;
      sec1d.style.maxHeight = '';
      sec1d.style.overflow = 'hidden';
    }
    if (secLower) {
      secLower.style.height = heightStr;
      secLower.style.maxHeight = '';
      secLower.style.minHeight = lowerMinH;
      secLower.style.overflow = 'hidden';
    }
    const heightMap = { '44vh': 'btnHeightCompact', '54vh': 'btnHeightNormal', '66vh': 'btnHeightExpanded' };
    Object.entries(heightMap).forEach(([h, btnId]) => {
      const b = document.getElementById(btnId);
      if (!b) return;
      if (h === heightStr) {
        b.className = 'px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/40 cursor-pointer';
      } else {
        b.className = 'px-1.5 py-0.5 rounded text-slate-400 hover:text-white cursor-pointer';
      }
    });
    if (typeof window.reflowAllCharts === 'function') {
      window.reflowAllCharts();
    }
  };

  // =========================================================================
  // INICIALIZACIÓN GLOBAL DEL COCKPIT
  // =========================================================================
  window.initCockpitAdvanced = function () {
    console.log("🚀 Cockpit TradingView Pro Inicializado.");
    initDrawingOverlay('chart-container-1d', STATE.charts.macro);
    initDrawingOverlay('chart-container-1h', STATE.charts.setup);
    initDrawingOverlay('chart-container-5m', STATE.charts.trigger);
    applyChartLayers();
    updateLayerUI();
    refreshScreenerTable();
    updatePaperTradingUI();
    setInterval(refreshScreenerTable, 25000);

    // Conectar eventos del menú de herramientas
    document.querySelectorAll('[data-tv-tool]').forEach(btn => {
      btn.onclick = () => {
        const tool = btn.getAttribute('data-tv-tool');
        window.setTvTool(tool);
      };
    });

    // Limpiar dibujos
    const btnClear = document.getElementById('btnClearDrawings');
    if (btnClear) btnClear.onclick = window.clearAllDrawings;
    const btnClearToolbar = document.getElementById('btnClearDrawingsToolbar');
    if (btnClearToolbar) btnClearToolbar.onclick = window.clearAllDrawings;
  };

  // Exponer al scope global para enlace con index.html
  window.CockpitEngine = {
    STATE,
    CONFIG,
    ta,
    toHeikinAshi,
    calculateVolumeProfile,
    renderVolumeProfileOverlay,
    syncActivePositionLines,
    fetchAndPopulateClosedTrades,
    exitChartFullscreen: window.exitChartFullscreen,
    reflowAllCharts: reflowAllChartsMultipleTimes,
    setTvTool: window.setTvTool,
    clearAllDrawings: window.clearAllDrawings,
    undoLastDrawing: window.undoLastDrawing,
    setLowerChartsHeight: window.setLowerChartsHeight,
    applyChartLayers,
    updateLayerUI,
    toggleChartLayer: window.toggleChartLayer,
    toggleCandlePocLayer: window.toggleCandlePocLayer,
    openLayersModal: window.openLayersModal,
    closeLayersModal: window.closeLayersModal,
    openFibSettingsModal: window.openFibSettingsModal,
    closeFibSettingsModal: window.closeFibSettingsModal,
    renderFibSettingsTable: window.renderFibSettingsTable,
    getFibConfig,
    saveFibConfig,
    enableAllLayers: window.enableAllLayers,
    disableAllLayers: window.disableAllLayers,
    isLayerActive: window.isLayerActive
  };

})();
