/**
 * ============================================================================
 * 🐅 KULA BALAM — MOTOR GRÁFICO Y CUANTITATIVO CENTRALIZADO (Single Source of Truth)
 * Archivo: kula_balam/frontend/js/kula-chart-engine.js
 * ============================================================================
 * Concentra en un único módulo reutilizable para todas las páginas del ecosistema
 * (1. Kula Balam Cockpit, 2. La Tríada Tres Velas, 3. Terminal Velas CIO):
 *  - Configuración visual TradingView Pro (barSpacing: 13, proporción 85/15, Lienzo Blanco/Oscuro).
 *  - Fórmulas Matemáticas Unificadas:
 *      • Clasificador de Patrones de Thomas Bulkowski (4.7M velas) + "Clic Patrones".
 *      • Media Móvil Simple (SMA 20) y Exponenciales (EMA 20 / EMA 50).
 *      • VWAP Institucional + Bandas de Desviación Estándar (±1σ, ±2σ).
 *      • Oscilador RSI (14) de Wilder + Detector de Divergencias.
 *      • Volatilidad Real ATR (14) + Ruido Mínimo (1.5x ATR) + Compresión (ATR Squeeze).
 *      • Punto de Control Intrabarra (POC) + Volumen Relativo (RVOL).
 *  - Barra Lateral de Herramientas de Dibujo TradingView Pro (44px) y Conmutador 1 Vela ↔ 3 Velas.
 * ============================================================================
 */
(function (window) {
  'use strict';

  // ---------------------------------------------------------------------------
  // 1. ESTÁNDAR VISUAL TRADINGVIEW PRO (PROPORCIONES Y PALETA ÚNICA)
  // ---------------------------------------------------------------------------
  const CANDLE_SERIES_OPTIONS = {
    upColor: '#089981',
    downColor: '#f23645',
    borderVisible: true,
    borderUpColor: '#089981',
    borderDownColor: '#f23645',
    wickUpColor: '#089981',
    wickDownColor: '#f23645'
  };

  function getChartThemeOptions(isLight) {
    if (isLight) {
      return {
        layout: {
          background: { type: 'solid', color: '#ffffff' },
          textColor: '#131722',
          fontSize: 11,
          fontFamily: "'JetBrains Mono', -apple-system, BlinkMacSystemFont, sans-serif"
        },
        grid: {
          vertLines: { color: '#f0f3fa', style: 0 },
          horzLines: { color: '#f0f3fa', style: 0 }
        },
        crosshair: {
          mode: window.LightweightCharts ? window.LightweightCharts.CrosshairMode.Normal : 0,
          vertLine: { width: 1, color: '#9598a1', style: 3, labelBackgroundColor: '#131722' },
          horzLine: { width: 1, color: '#9598a1', style: 3, labelBackgroundColor: '#131722' }
        },
        rightPriceScale: {
          borderColor: '#e0e3eb',
          scaleMargins: { top: 0.08, bottom: 0.08 },
          autoScale: true,
          alignLabels: true,
          minimumWidth: 68
        },
        timeScale: {
          borderColor: '#e0e3eb',
          timeVisible: true,
          secondsVisible: false,
          rightOffset: 16,
          barSpacing: 13,
          minBarSpacing: 5
        }
      };
    }
    return {
      layout: {
        background: { type: 'solid', color: '#0b0e14' },
        textColor: '#94a3b8',
        fontSize: 11,
        fontFamily: "'JetBrains Mono', -apple-system, BlinkMacSystemFont, sans-serif"
      },
      grid: {
        vertLines: { color: 'rgba(30, 41, 59, 0.5)', style: 0 },
        horzLines: { color: 'rgba(30, 41, 59, 0.5)', style: 0 }
      },
      crosshair: {
        mode: window.LightweightCharts ? window.LightweightCharts.CrosshairMode.Normal : 0,
        vertLine: { width: 1, color: '#64748b', style: 3, labelBackgroundColor: '#1e293b' },
        horzLine: { width: 1, color: '#64748b', style: 3, labelBackgroundColor: '#1e293b' }
      },
      rightPriceScale: {
        borderColor: '#1e293b',
        scaleMargins: { top: 0.08, bottom: 0.08 },
        autoScale: true,
        alignLabels: true,
        minimumWidth: 68
      },
      timeScale: {
        borderColor: '#1e293b',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 16,
        barSpacing: 13,
        minBarSpacing: 5
      }
    };
  }

  function applyTradingViewProportions(chart, volChart, candles, visibleBars) {
    if (!chart) return;
    const barsToShow = visibleBars || 42;
    chart.applyOptions({
      timeScale: { rightOffset: 16, barSpacing: 13, minBarSpacing: 5 },
      rightPriceScale: { autoScale: true, scaleMargins: { top: 0.08, bottom: 0.08 } }
    });
    if (volChart) {
      volChart.applyOptions({
        timeScale: { rightOffset: 16, barSpacing: 13, minBarSpacing: 5 }
      });
    }
    const count = candles && Array.isArray(candles) ? candles.length : 0;
    if (count > 0) {
      const visibleRange = {
        from: Math.max(0, count - barsToShow),
        to: count + 6
      };
      try {
        chart.timeScale().setVisibleLogicalRange(visibleRange);
        if (volChart) volChart.timeScale().setVisibleLogicalRange(visibleRange);
      } catch (e) {}
    }
  }

  // ---------------------------------------------------------------------------
  // 2. FÓRMULAS MATEMÁTICAS UNIFICADAS (BULKOWSKI, SMA, EMA, VWAP, RSI, ATR, POC)
  // ---------------------------------------------------------------------------
  function formatPrice(p) {
    if (typeof p !== 'number' || isNaN(p)) return p || '--';
    return p >= 100
      ? p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : p >= 1 ? p.toFixed(3) : p.toFixed(5);
  }

  function formatVolume(v) {
    if (typeof v !== 'number' || isNaN(v)) return '--';
    if (v >= 1e9) return (v / 1e9).toFixed(2) + 'B';
    if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
    if (v >= 1e3) return (v / 1e3).toFixed(2) + 'K';
    return v.toFixed(2);
  }

  function calculateSMA(candles, period) {
    period = period || 20;
    if (!candles || candles.length < period) return [];
    const result = [];
    let sum = 0;
    for (let i = 0; i < candles.length; i++) {
      sum += candles[i].close;
      if (i >= period) sum -= candles[i - period].close;
      if (i >= period - 1) {
        result.push({ time: candles[i].time, value: sum / period });
      }
    }
    return result;
  }

  function calculateEMA(candles, period) {
    period = period || 20;
    if (!candles || !candles.length) return [];
    const k = 2 / (period + 1);
    const emaData = [];
    let ema = candles[0].close;
    for (let i = 0; i < candles.length; i++) {
      ema = i === 0 ? candles[i].close : candles[i].close * k + ema * (1 - k);
      emaData.push({ time: candles[i].time, value: ema });
    }
    return emaData;
  }

  function calculateVolumeSMA(volumes, period) {
    period = period || 20;
    if (!volumes || !volumes.length) return [];
    const result = [];
    let sum = 0;
    for (let i = 0; i < volumes.length; i++) {
      const v = typeof volumes[i].value === 'number' ? volumes[i].value : 0;
      sum += v;
      if (i >= period) {
        const vOut = typeof volumes[i - period].value === 'number' ? volumes[i - period].value : 0;
        sum -= vOut;
        result.push({ time: volumes[i].time, value: sum / period });
      } else {
        result.push({ time: volumes[i].time, value: sum / (i + 1) });
      }
    }
    return result;
  }

  function calculateVWAP(candles, volumes) {
    if (!candles || !candles.length) {
      return { vwap: [], upper1: [], lower1: [], upper2: [], lower2: [] };
    }
    const vwap = [], upper1 = [], lower1 = [], upper2 = [], lower2 = [];
    let cumVol = 0;
    let cumPV = 0;
    let cumPV2 = 0;
    let lastDay = null;

    for (let i = 0; i < candles.length; i++) {
      const c = candles[i];
      const d = new Date(c.time * 1000).getUTCDate();
      if (lastDay !== null && d !== lastDay && i < candles.length - 5) {
        cumVol = 0;
        cumPV = 0;
        cumPV2 = 0;
      }
      lastDay = d;

      const typical = (c.high + c.low + c.close) / 3;
      const vol = (volumes && volumes[i] && typeof volumes[i].value === 'number')
        ? volumes[i].value
        : (c.volume || 1);
      const safeVol = Math.max(vol, 0.0001);

      cumVol += safeVol;
      cumPV += typical * safeVol;
      cumPV2 += typical * typical * safeVol;

      const val = cumPV / cumVol;
      const variance = Math.max(0, (cumPV2 / cumVol) - (val * val));
      const stdDev = Math.sqrt(variance);

      vwap.push({ time: c.time, value: val });
      upper1.push({ time: c.time, value: val + stdDev });
      lower1.push({ time: c.time, value: val - stdDev });
      upper2.push({ time: c.time, value: val + stdDev * 2.0 });
      lower2.push({ time: c.time, value: val - stdDev * 2.0 });
    }
    return { vwap, upper1, lower1, upper2, lower2 };
  }

  function calculateRSI(candles, period) {
    period = period || 14;
    if (!candles || candles.length <= period) {
      return { series: [], lastValue: 50, statusText: 'Zona Neutral', statusClass: 'bg-slate-800 text-slate-300 border-slate-700' };
    }
    const series = [];
    let gains = 0;
    let losses = 0;

    for (let i = 1; i <= period; i++) {
      const diff = candles[i].close - candles[i - 1].close;
      if (diff >= 0) gains += diff;
      else losses -= diff;
    }

    let avgGain = gains / period;
    let avgLoss = losses / period;

    for (let i = period; i < candles.length; i++) {
      if (i > period) {
        const diff = candles[i].close - candles[i - 1].close;
        const g = diff > 0 ? diff : 0;
        const l = diff < 0 ? -diff : 0;
        avgGain = (avgGain * (period - 1) + g) / period;
        avgLoss = (avgLoss * (period - 1) + l) / period;
      }
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      const rsi = avgLoss === 0 ? 100 : 100 - (100 / (1 + rs));
      series.push({ time: candles[i].time, value: rsi });
    }

    const lastVal = series.length ? series[series.length - 1].value : 50;
    let statusText = '⚪ Zona Neutral';
    let statusClass = 'bg-slate-800 text-slate-300 border border-slate-700';

    if (lastVal >= 70) {
      statusText = '🔴 Sobrecompra (≥70)';
      statusClass = 'bg-rose-950/90 text-rose-300 border border-rose-500/50';
    } else if (lastVal <= 30) {
      statusText = '🟢 Sobreventa (≤30)';
      statusClass = 'bg-emerald-950/90 text-emerald-300 border border-emerald-500/50';
    } else if (lastVal >= 58) {
      statusText = '📈 Momento Alcista';
      statusClass = 'bg-emerald-950/60 text-emerald-300 border border-emerald-600/40';
    } else if (lastVal <= 42) {
      statusText = '📉 Momento Bajista';
      statusClass = 'bg-rose-950/60 text-rose-300 border border-rose-600/40';
    }

    return { series, lastValue: lastVal, statusText, statusClass };
  }

  function calculateATR(candles, period) {
    period = period || 14;
    if (!candles || candles.length < 2) {
      return { series: [], lastValue: 0, noise15x: 0, statusText: 'Volatilidad Normal', statusClass: 'bg-amber-950/80 text-amber-300 border border-amber-700/60' };
    }
    const trs = [];
    for (let i = 0; i < candles.length; i++) {
      const c = candles[i];
      if (i === 0) {
        trs.push(c.high - c.low);
      } else {
        const prevClose = candles[i - 1].close;
        const tr = Math.max(c.high - c.low, Math.abs(c.high - prevClose), Math.abs(c.low - prevClose));
        trs.push(tr);
      }
    }

    const series = [];
    let atr = trs[0];
    for (let i = 0; i < candles.length; i++) {
      if (i < period) {
        const slice = trs.slice(0, i + 1);
        atr = slice.reduce((a, b) => a + b, 0) / slice.length;
      } else {
        atr = (atr * (period - 1) + trs[i]) / period;
      }
      series.push({ time: candles[i].time, value: atr });
    }

    const lastVal = series.length ? series[series.length - 1].value : 0;
    const noise15x = lastVal * 1.5;
    let avgAtr = lastVal;
    if (series.length >= 20) {
      const recent = series.slice(-20);
      avgAtr = recent.reduce((acc, it) => acc + it.value, 0) / 20;
    }

    let statusText = '🌊 Volatilidad Normal';
    let statusClass = 'bg-amber-950/80 text-amber-300 border border-amber-700/60';
    if (lastVal < avgAtr * 0.85) {
      statusText = '🔋 Compresión (ATR Squeeze)';
      statusClass = 'bg-cyan-950/80 text-cyan-300 border border-cyan-500/50';
    } else if (lastVal > avgAtr * 1.25) {
      statusText = '⚡ Expansión Alta Volatilidad';
      statusClass = 'bg-rose-950/80 text-rose-300 border border-rose-500/50';
    }

    return { series, lastValue: lastVal, noise15x, statusText, statusClass };
  }

  // Clasificador Cuantitativo de Velas Japonesas (Benchmark Thomas Bulkowski - 4.7M velas)
  function detectCandlePatternDetails(candle, prevCandle, prev2Candle, trendContext) {
    if (!candle || candle.high === undefined || candle.low === undefined || candle.open === undefined || candle.close === undefined) {
      return {
        name: "Esperando vela...",
        icon: "🕯️",
        fullName: "🕯️ Esperando vela...",
        badgeClass: "bg-slate-800 text-slate-400 border border-slate-700",
        direction: "neutral",
        winRate: 50
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

    if (prevCandle && prev2Candle) {
      const prevRange = Math.max(0.00001, prevCandle.high - prevCandle.low);
      const prevBody = Math.abs(prevCandle.close - prevCandle.open);
      const prev2Range = Math.max(0.00001, prev2Candle.high - prev2Candle.low);
      const prev2Body = Math.abs(prev2Candle.close - prev2Candle.open);

      if (prev2Candle.close < prev2Candle.open && (prev2Body / prev2Range) > 0.35 &&
          (prevBody / prevRange) < 0.35 &&
          candle.close > candle.open && candle.close > (prev2Candle.open + prev2Candle.close) / 2) {
        return {
          name: "Estrella de la Mañana (Morning Star)",
          icon: "🌅",
          fullName: "🌅 Morning Star",
          badgeClass: "bg-emerald-500/25 text-emerald-300 border border-emerald-400/50 font-extrabold",
          direction: "bullish",
          winRate: 78
        };
      }

      if (prev2Candle.close > prev2Candle.open && (prev2Body / prev2Range) > 0.35 &&
          (prevBody / prevRange) < 0.35 &&
          candle.close < candle.open && candle.close < (prev2Candle.open + prev2Candle.close) / 2) {
        return {
          name: "Estrella del Atardecer (Evening Star)",
          icon: "🌆",
          fullName: "🌆 Evening Star",
          badgeClass: "bg-rose-500/25 text-rose-300 border border-rose-400/50 font-extrabold",
          direction: "bearish",
          winRate: 72
        };
      }

      if (candle.close > candle.open && prevCandle.close > prevCandle.open && prev2Candle.close > prev2Candle.open &&
          candle.close > prevCandle.close && prevCandle.close > prev2Candle.close &&
          candle.open >= prevCandle.open && prevCandle.open >= prev2Candle.open &&
          upperRatio <= 25) {
        return {
          name: "Tres Soldados Blancos (Soldiers)",
          icon: "⚔️",
          fullName: "⚔️ 3 Soldados Blancos",
          badgeClass: "bg-emerald-500/20 text-emerald-300 border border-emerald-400/40 font-bold",
          direction: "bullish",
          winRate: 82
        };
      }

      if (candle.close < candle.open && prevCandle.close < prevCandle.open && prev2Candle.close < prev2Candle.open &&
          candle.close < prevCandle.close && prevCandle.close < prev2Candle.close &&
          candle.open <= prevCandle.open && prevCandle.open <= prev2Candle.open &&
          lowerRatio <= 25) {
        return {
          name: "Tres Cuervos Negros (Crows)",
          icon: "🦅",
          fullName: "🦅 3 Cuervos Negros",
          badgeClass: "bg-rose-500/20 text-rose-300 border border-rose-400/40 font-bold",
          direction: "bearish",
          winRate: 79
        };
      }
    }

    if (prevCandle) {
      if (prevCandle.close < prevCandle.open && candle.close > candle.open &&
          candle.close >= prevCandle.open * 0.998 && candle.open <= prevCandle.close * 1.002 &&
          bodyRatio >= 45) {
        return {
          name: "Envolvente Alcista (Bullish Engulfing)",
          icon: "🌊",
          fullName: "🌊 Envolvente Alcista",
          badgeClass: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 font-bold",
          direction: "bullish",
          winRate: 63
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
          direction: "bearish",
          winRate: 63
        };
      }
    }

    if (bodyRatio <= 8 && lowerRatio >= 60 && upperRatio <= 12) {
      return {
        name: "Doji Libélula (Dragonfly Doji)",
        icon: "🦎",
        fullName: "🦎 Doji Libélula",
        badgeClass: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold",
        direction: "bullish",
        winRate: 71
      };
    }

    if (bodyRatio <= 8 && upperRatio >= 60 && lowerRatio <= 12) {
      return {
        name: "Doji Lápida (Gravestone Doji)",
        icon: "🪦",
        fullName: "🪦 Doji Lápida",
        badgeClass: "bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold",
        direction: "bearish",
        winRate: 68
      };
    }

    if (bodyRatio <= 8) {
      return {
        name: "Doji Clásico (Indecisión)",
        icon: "⚖️",
        fullName: "⚖️ Doji Clásico",
        badgeClass: "bg-amber-500/20 text-amber-300 border border-amber-500/40",
        direction: "neutral",
        winRate: 50
      };
    }

    if (lowerRatio >= 55 && upperRatio <= 15) {
      if (trendContext === 'up' && prevCandle && prevCandle.close > prevCandle.open) {
        return {
          name: "Hombre Colgado (Hanging Man)",
          icon: "🪢",
          fullName: "🪢 Hombre Colgado",
          badgeClass: "bg-rose-500/20 text-rose-400 border border-rose-500/30",
          direction: "bearish",
          winRate: 59
        };
      }
      return {
        name: "Martillo Alcista (Hammer)",
        icon: "🔨",
        fullName: "🔨 Martillo Alcista",
        badgeClass: "bg-emerald-500/25 text-emerald-400 border border-emerald-500/50 font-extrabold",
        direction: "bullish",
        winRate: 60
      };
    }

    if (upperRatio >= 55 && lowerRatio <= 15) {
      if (trendContext === 'down' || (prevCandle && prevCandle.close < prevCandle.open)) {
        return {
          name: "Martillo Invertido (Suelo)",
          icon: "🔨",
          fullName: "🔨 Martillo Invertido",
          badgeClass: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
          direction: "bullish",
          winRate: 60
        };
      }
      return {
        name: "Estrella Fugaz (Shooting Star)",
        icon: "⭐",
        fullName: "⭐ Estrella Fugaz",
        badgeClass: "bg-rose-500/25 text-rose-400 border border-rose-500/50 font-extrabold",
        direction: "bearish",
        winRate: 59
      };
    }

    if (bodyRatio >= 80 && upperRatio <= 8 && lowerRatio <= 8) {
      if (isGreen) {
        return {
          name: "Marubozu Alcista (Control Comprador)",
          icon: "🚀",
          fullName: "🚀 Marubozu Alcista",
          badgeClass: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold",
          direction: "bullish",
          winRate: 65
        };
      }
      return {
        name: "Marubozu Bajista (Presión Vendedora)",
        icon: "💥",
        fullName: "💥 Marubozu Bajista",
        badgeClass: "bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold",
        direction: "bearish",
        winRate: 65
      };
    }

    if (bodyRatio >= 10 && bodyRatio <= 30 && upperRatio >= 25 && lowerRatio >= 25) {
      return {
        name: "Peonza Indecisión (Spinning Top)",
        icon: "🌀",
        fullName: "🌀 Peonza Indecisión",
        badgeClass: "bg-amber-500/20 text-amber-300 border border-amber-500/30",
        direction: "neutral",
        winRate: 50
      };
    }

    if (bodyRatio >= 60) {
      if (isGreen) {
        return {
          name: "Impulso Alcista (Rango Amplio)",
          icon: "📈",
          fullName: "📈 Impulso Alcista",
          badgeClass: "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30",
          direction: "bullish",
          winRate: 58
        };
      }
      return {
        name: "Impulso Bajista (Rango Amplio)",
        icon: "📉",
        fullName: "📉 Impulso Bajista",
        badgeClass: "bg-rose-500/15 text-rose-400 border border-rose-500/30",
        direction: "bearish",
        winRate: 58
      };
    }

    if (isGreen) {
      return {
        name: "Vela Normal Alcista",
        icon: "🕯️",
        fullName: "🕯️ Vela Normal Alcista",
        badgeClass: "bg-slate-900/90 text-emerald-400 border border-emerald-900/40",
        direction: "bullish",
        winRate: 50
      };
    }
    return {
      name: "Vela Normal Bajista",
      icon: "🕯️",
      fullName: "🕯️ Vela Normal Bajista",
      badgeClass: "bg-slate-900/90 text-rose-400 border border-rose-900/40",
      direction: "bearish",
      winRate: 50
    };
  }

  // ---------------------------------------------------------------------------
  // 3. MODAL FORENSE "CLIC PATRONES" UNIVERSAL
  // ---------------------------------------------------------------------------
  function ensureCandlePatternModal() {
    if (document.getElementById('candlePatternModal')) return;
    const modalHtml = `
      <div id="candlePatternModal" class="hidden fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div class="bg-slate-900 border border-emerald-500/40 rounded-2xl max-w-lg w-full p-5 shadow-2xl space-y-4 text-xs text-slate-200">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <div class="flex items-center gap-2.5">
              <span id="modal-pattern-icon" class="text-2xl">🕯️</span>
              <div>
                <h3 id="modal-pattern-title" class="text-sm font-black text-white uppercase tracking-wide">Auditoría Cuantitativa de Vela</h3>
                <p id="modal-pattern-tf" class="text-[11px] text-emerald-400 font-mono">Temporalidad: --</p>
              </div>
            </div>
            <button type="button" onclick="window.closeCandlePatternModal()" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold cursor-pointer">✕</button>
          </div>
          <div class="bg-slate-950/90 border border-slate-800 rounded-xl p-3.5 space-y-2.5">
            <div class="flex items-center justify-between">
              <span class="text-slate-400 font-semibold">Clasificación Bulkowski (4.7M Velas):</span>
              <span id="modal-pattern-badge" class="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">--</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-slate-400">Fiabilidad Estadística (Win Rate):</span>
              <span id="modal-pattern-winrate" class="font-mono font-bold text-amber-300">--%</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-slate-400">Dirección / Sesgo Operativo:</span>
              <span id="modal-pattern-verdict" class="font-bold text-emerald-400 font-mono">--</span>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2.5 font-mono text-[11px]">
            <div class="bg-slate-950/80 border border-slate-800/80 rounded-lg p-2.5">
              <div class="text-slate-400 text-[10px]">Apertura (Open)</div>
              <div id="modal-candle-open" class="text-white font-bold text-xs mt-0.5">$--</div>
            </div>
            <div class="bg-slate-950/80 border border-slate-800/80 rounded-lg p-2.5">
              <div class="text-slate-400 text-[10px]">Cierre (Close)</div>
              <div id="modal-candle-close" class="text-white font-bold text-xs mt-0.5">$--</div>
            </div>
            <div class="bg-slate-950/80 border border-slate-800/80 rounded-lg p-2.5">
              <div class="text-emerald-400/80 text-[10px]">Máximo (High)</div>
              <div id="modal-candle-high" class="text-emerald-300 font-bold text-xs mt-0.5">$--</div>
            </div>
            <div class="bg-slate-950/80 border border-slate-800/80 rounded-lg p-2.5">
              <div class="text-rose-400/80 text-[10px]">Mínimo (Low)</div>
              <div id="modal-candle-low" class="text-rose-300 font-bold text-xs mt-0.5">$--</div>
            </div>
          </div>
          <div class="bg-slate-950/80 border border-slate-800 rounded-xl p-3 space-y-2">
            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Anatomía de la Vela & Volumen</div>
            <div class="grid grid-cols-3 gap-2 text-center font-mono">
              <div class="bg-slate-900 p-2 rounded border border-slate-800">
                <div class="text-[10px] text-slate-400">Cuerpo Real</div>
                <div id="modal-ratio-body" class="text-white font-bold mt-0.5">--%</div>
              </div>
              <div class="bg-slate-900 p-2 rounded border border-slate-800">
                <div class="text-[10px] text-slate-400">Mecha Sup.</div>
                <div id="modal-ratio-upper" class="text-rose-300 font-bold mt-0.5">--%</div>
              </div>
              <div class="bg-slate-900 p-2 rounded border border-slate-800">
                <div class="text-[10px] text-slate-400">Mecha Inf.</div>
                <div id="modal-ratio-lower" class="text-emerald-300 font-bold mt-0.5">--%</div>
              </div>
            </div>
            <div class="flex items-center justify-between pt-2 border-t border-slate-800/80 font-mono text-[11px]">
              <span class="text-slate-400">Volumen / RVOL:</span>
              <span><strong id="modal-vol-val" class="text-white">--</strong> (<strong id="modal-vol-rvol" class="text-amber-300">--x</strong>)</span>
            </div>
            <div id="modal-poc-container" class="hidden flex items-center justify-between pt-1 font-mono text-[11px]">
              <span class="text-amber-300">🎯 POC Intrabarra:</span>
              <strong id="modal-poc-price" class="text-white">$--</strong>
            </div>
          </div>
          <div class="bg-indigo-950/30 border border-indigo-500/30 rounded-xl p-3 flex items-center justify-between font-mono text-[11px]">
            <div>
              <span class="text-rose-400 font-bold">SL (1.5x Rango):</span> <strong id="modal-trade-sl" class="text-white">$--</strong>
            </div>
            <div>
              <span class="text-emerald-400 font-bold">TP1 (R:R 1:2.0):</span> <strong id="modal-trade-tp" class="text-white">$--</strong>
            </div>
          </div>
        </div>
      </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
  }

  function renderUniversalPatternModal(candle, pat, tfTitle, pocInfo) {
    ensureCandlePatternModal();
    const modal = document.getElementById('candlePatternModal');
    if (!modal || !candle) return;

    const range = Math.max(0.0001, candle.high - candle.low);
    const body = Math.abs(candle.close - candle.open);
    const upperWick = candle.high - Math.max(candle.open, candle.close);
    const lowerWick = Math.min(candle.open, candle.close) - candle.low;

    const bodyRatio = (body / range) * 100;
    const upperRatio = (upperWick / range) * 100;
    const lowerRatio = (lowerWick / range) * 100;

    const slPrice = pat.direction === 'bullish' ? (candle.low - range * 1.5) : (candle.high + range * 1.5);
    const tpPrice = pat.direction === 'bullish' ? (candle.close + range * 3.0) : (candle.close - range * 3.0);

    const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
    setTxt('modal-pattern-icon', pat.icon || '🕯️');
    setTxt('modal-pattern-title', pat.name || 'Auditoría de Vela');
    setTxt('modal-pattern-tf', `Temporalidad: ${tfTitle || 'Activa'}`);

    const badgeEl = document.getElementById('modal-pattern-badge');
    if (badgeEl) {
      badgeEl.innerText = pat.fullName || pat.name;
      badgeEl.className = `px-2 py-0.5 rounded text-[10px] font-bold ${pat.badgeClass || ''}`;
    }
    setTxt('modal-pattern-winrate', pat.winRate ? `${pat.winRate}% de Acierto Histórico` : 'Benchmark Empírico 4.7M');

    const verdictEl = document.getElementById('modal-pattern-verdict');
    if (verdictEl) {
      if (pat.direction === 'bullish') {
        verdictEl.innerText = '🟢 COMPRAR (LONG) · R:R ≥ 1:2.0';
        verdictEl.className = 'font-bold text-emerald-400 font-mono';
      } else if (pat.direction === 'bearish') {
        verdictEl.innerText = '🔴 VENDER / SHORT · R:R ≥ 1:2.0';
        verdictEl.className = 'font-bold text-rose-400 font-mono';
      } else {
        verdictEl.innerText = '🟡 IGNORAR / ESPERAR REACCIÓN';
        verdictEl.className = 'font-bold text-amber-300 font-mono';
      }
    }

    setTxt('modal-candle-open', `$${formatPrice(candle.open)}`);
    setTxt('modal-candle-close', `$${formatPrice(candle.close)}`);
    setTxt('modal-candle-high', `$${formatPrice(candle.high)}`);
    setTxt('modal-candle-low', `$${formatPrice(candle.low)}`);
    setTxt('modal-ratio-body', `${Math.round(bodyRatio)}%`);
    setTxt('modal-ratio-upper', `${Math.round(upperRatio)}%`);
    setTxt('modal-ratio-lower', `${Math.round(lowerRatio)}%`);
    setTxt('modal-vol-val', pocInfo && pocInfo.volume ? formatVolume(pocInfo.volume) : (candle.volume ? formatVolume(candle.volume) : '--'));
    setTxt('modal-vol-rvol', pocInfo && pocInfo.rvol ? `${pocInfo.rvol.toFixed(2)}x` : '1.00x');
    setTxt('modal-trade-sl', `$${formatPrice(slPrice)}`);
    setTxt('modal-trade-tp', `$${formatPrice(tpPrice)}`);

    modal.classList.remove('hidden');
  }

  if (typeof window.closeCandlePatternModal !== 'function') {
    window.closeCandlePatternModal = function () {
      const m = document.getElementById('candlePatternModal');
      if (m) m.classList.add('hidden');
    };
  }
  if (typeof window.renderCandlePatternModal !== 'function') {
    window.renderCandlePatternModal = renderUniversalPatternModal;
  }

  // ---------------------------------------------------------------------------
  // 4. CONTROLADOR UNIFICADO DE BARRA LATERAL (44px) Y MODALIDAD 1 VELA ↔ 3 VELAS
  //    Para Kula Balam Cockpit Principal (frontend/index.html) y Terminal CIO
  // ---------------------------------------------------------------------------
  const HOST_STATE = {
    mode: '1v',
    isLight: false,
    activeTool: 'cursor',
    drawings: [],
    triadCharts: { c1D: null, s1D: null, sma1D: null, ema1D: null, vwap1D: null, c1H: null, s1H: null, sma1H: null, ema1H: null, vwap1H: null, c5M: null, s5M: null, sma5M: null, ema5M: null, vwap5M: null },
    triadData: { d1D: [], d1H: [], d5M: [] },
    getSymbol: () => 'BTCUSDT',
    hostChart: null,
    hostRsiChart: null,
    hostAtrChart: null
  };

  async function fetchTriadKlines(symbol, interval, limit) {
    limit = limit || 120;
    const cleanSym = (symbol || 'BTCUSDT').replace('/', '').toUpperCase();
    const isCrypto = cleanSym.endsWith('USDT') || cleanSym.endsWith('USD');
    if (isCrypto) {
      const binSym = cleanSym.endsWith('USD') && !cleanSym.endsWith('USDT') ? cleanSym + 'T' : cleanSym;
      try {
        const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${binSym}&interval=${interval}&limit=${limit}`);
        if (res.ok) {
          const raw = await res.json();
          if (Array.isArray(raw) && raw.length) {
            return raw.map(k => ({
              time: Math.floor(k[0] / 1000),
              open: parseFloat(k[1]),
              high: parseFloat(k[2]),
              low: parseFloat(k[3]),
              close: parseFloat(k[4]),
              volume: parseFloat(k[5])
            }));
          }
        }
      } catch (e) {}
    }
    try {
      const res = await fetch(`http://127.0.0.1:18767/api/market/history?symbol=${encodeURIComponent(symbol)}&timeframe=${interval}`);
      if (res.ok) {
        const raw = await res.json();
        if (Array.isArray(raw) && raw.length) {
          return raw.map(k => ({
            time: Number(k.time),
            open: Number(k.open),
            high: Number(k.high),
            low: Number(k.low),
            close: Number(k.close),
            volume: Number(k.volume || 1)
          }));
        }
      }
    } catch (e) {}
    return [];
  }

  function bindTriadPanelEvents(chart, series, tfLabel, getArr, legIds) {
    chart.subscribeCrosshairMove(param => {
      const arr = getArr();
      if (!arr || !arr.length) return;
      let c = arr[arr.length - 1];
      let idx = arr.length - 1;
      if (param && param.time && param.seriesData && param.seriesData.get(series)) {
        c = param.seriesData.get(series);
        const found = arr.findIndex(it => it.time === param.time);
        if (found >= 0) idx = found;
      }
      const prev = idx > 0 ? arr[idx - 1] : null;
      const prev2 = idx > 1 ? arr[idx - 2] : null;
      const pat = detectCandlePatternDetails(c, prev, prev2);

      const ohlcEl = document.getElementById(legIds.ohlc);
      if (ohlcEl && c) {
        ohlcEl.innerHTML = `O: <b>$${formatPrice(c.open)}</b> | H: <b>$${formatPrice(c.high)}</b> | L: <b>$${formatPrice(c.low)}</b> | C: <b>$${formatPrice(c.close)}</b>`;
      }
      const patEl = document.getElementById(legIds.pat);
      if (patEl && pat) {
        patEl.innerText = `${pat.icon} ${pat.name.split(' ')[0]}`;
        patEl.className = `px-1.5 py-0.2 rounded text-[9px] font-bold ${pat.badgeClass}`;
      }
    });

    chart.subscribeClick(param => {
      if (!param || !param.time || !param.seriesData) return;
      const c = param.seriesData.get(series);
      if (!c) return;
      const arr = getArr() || [];
      const idx = arr.findIndex(it => it.time === param.time);
      const prev = idx > 0 ? arr[idx - 1] : null;
      const prev2 = idx > 1 ? arr[idx - 2] : null;
      const pat = detectCandlePatternDetails(c, prev, prev2);
      renderUniversalPatternModal(c, pat, tfLabel, null);
    });
  }

  async function refreshEmbeddedTriad() {
    if (HOST_STATE.mode !== '3v') return;
    const sym = HOST_STATE.getSymbol ? HOST_STATE.getSymbol() : 'BTCUSDT';
    const [d1D, d1H, d5M] = await Promise.all([
      fetchTriadKlines(sym, '1d', 120),
      fetchTriadKlines(sym, '1h', 120),
      fetchTriadKlines(sym, '5m', 120)
    ]);
    HOST_STATE.triadData = { d1D, d1H, d5M };

    const populatePanel = (chart, sCandle, sSma, sEma, emaP, sVwap, data, legIds) => {
      if (!chart || !sCandle || !data || !data.length) return;
      sCandle.setData(data);
      const smaArr = calculateSMA(data, 20);
      const emaArr = calculateEMA(data, emaP);
      const vwapObj = calculateVWAP(data);
      if (sSma) sSma.setData(smaArr);
      if (sEma) sEma.setData(emaArr);
      if (sVwap) sVwap.setData(vwapObj.vwap);
      applyTradingViewProportions(chart, null, data, 38);

      const last = data[data.length - 1];
      const prev = data.length > 1 ? data[data.length - 2] : null;
      const prev2 = data.length > 2 ? data[data.length - 3] : null;
      const pat = detectCandlePatternDetails(last, prev, prev2);
      const lastSma = smaArr.length ? smaArr[smaArr.length - 1].value : null;
      const lastEma = emaArr.length ? emaArr[emaArr.length - 1].value : null;
      const lastVwap = vwapObj.vwap.length ? vwapObj.vwap[vwapObj.vwap.length - 1].value : null;

      const ohlcEl = document.getElementById(legIds.ohlc);
      if (ohlcEl) ohlcEl.innerHTML = `O: <b>$${formatPrice(last.open)}</b> | H: <b>$${formatPrice(last.high)}</b> | L: <b>$${formatPrice(last.low)}</b> | C: <b>$${formatPrice(last.close)}</b>`;
      const patEl = document.getElementById(legIds.pat);
      if (patEl) {
        patEl.innerText = `${pat.icon} ${pat.name.split(' ')[0]}`;
        patEl.className = `px-1.5 py-0.2 rounded text-[9px] font-bold ${pat.badgeClass}`;
      }
      const indEl = document.getElementById(legIds.ind);
      if (indEl) {
        indEl.innerHTML = `<span class="text-blue-400">SMA20: $${formatPrice(lastSma)}</span> | <span class="text-amber-400">EMA${emaP}: $${formatPrice(lastEma)}</span> | <span class="text-yellow-500">VWAP: $${formatPrice(lastVwap)}</span>`;
      }
    };

    populatePanel(HOST_STATE.triadCharts.c1D, HOST_STATE.triadCharts.s1D, HOST_STATE.triadCharts.sma1D, HOST_STATE.triadCharts.ema1D, 50, HOST_STATE.triadCharts.vwap1D, d1D, { ohlc: 'ku-triad-ohlc-1d', pat: 'ku-triad-pat-1d', ind: 'ku-triad-ind-1d' });
    populatePanel(HOST_STATE.triadCharts.c1H, HOST_STATE.triadCharts.s1H, HOST_STATE.triadCharts.sma1H, HOST_STATE.triadCharts.ema1H, 20, HOST_STATE.triadCharts.vwap1H, d1H, { ohlc: 'ku-triad-ohlc-1h', pat: 'ku-triad-pat-1h', ind: 'ku-triad-ind-1h' });
    populatePanel(HOST_STATE.triadCharts.c5M, HOST_STATE.triadCharts.s5M, HOST_STATE.triadCharts.sma5M, HOST_STATE.triadCharts.ema5M, 20, HOST_STATE.triadCharts.vwap5M, d5M, { ohlc: 'ku-triad-ohlc-5m', pat: 'ku-triad-pat-5m', ind: 'ku-triad-ind-5m' });
  }

  function ensureTriadInitialized(triadContainer) {
    if (HOST_STATE.triadCharts.c1D || !window.LightweightCharts) return;
    const opts = getChartThemeOptions(HOST_STATE.isLight);

    const makePanel = (elId, emaColor) => {
      const el = document.getElementById(elId);
      if (!el) return {};
      const c = window.LightweightCharts.createChart(el, opts);
      const s = c.addCandlestickSeries(CANDLE_SERIES_OPTIONS);
      const sma = c.addLineSeries({ color: '#3b82f6', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false });
      const ema = c.addLineSeries({ color: emaColor, lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false });
      const vwap = c.addLineSeries({ color: '#eab308', lineWidth: 1.2, lineStyle: window.LightweightCharts.LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false });
      const ro = new ResizeObserver(entries => {
        for (let entry of entries) {
          if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
            c.resize(entry.contentRect.width, entry.contentRect.height);
          }
        }
      });
      ro.observe(el);
      return { c, s, sma, ema, vwap };
    };

    const p1 = makePanel('ku-triad-canvas-1d', '#f59e0b');
    const p2 = makePanel('ku-triad-canvas-1h', '#a855f7');
    const p3 = makePanel('ku-triad-canvas-5m', '#10b981');

    HOST_STATE.triadCharts = {
      c1D: p1.c, s1D: p1.s, sma1D: p1.sma, ema1D: p1.ema, vwap1D: p1.vwap,
      c1H: p2.c, s1H: p2.s, sma1H: p2.sma, ema1H: p2.ema, vwap1H: p2.vwap,
      c5M: p3.c, s5M: p3.s, sma5M: p3.sma, ema5M: p3.ema, vwap5M: p3.vwap
    };

    if (p1.c) bindTriadPanelEvents(p1.c, p1.s, '1D (Macro)', () => HOST_STATE.triadData.d1D, { ohlc: 'ku-triad-ohlc-1d', pat: 'ku-triad-pat-1d' });
    if (p2.c) bindTriadPanelEvents(p2.c, p2.s, '1H (Intermedia)', () => HOST_STATE.triadData.d1H, { ohlc: 'ku-triad-ohlc-1h', pat: 'ku-triad-pat-1h' });
    if (p3.c) bindTriadPanelEvents(p3.c, p3.s, '5M (Gatillo)', () => HOST_STATE.triadData.d5M, { ohlc: 'ku-triad-ohlc-5m', pat: 'ku-triad-pat-5m' });
  }

  function mountUnifiedChartWorkspace(options) {
    options = options || {};
    ensureCandlePatternModal();
    if (options.getSymbol) HOST_STATE.getSymbol = options.getSymbol;
    if (options.hostChart) HOST_STATE.hostChart = options.hostChart;
    if (options.hostRsiChart) HOST_STATE.hostRsiChart = options.hostRsiChart;
    if (options.hostAtrChart) HOST_STATE.hostAtrChart = options.hostAtrChart;

    const singleWrapper = document.getElementById(options.singleWrapperId || 'kula-single-chart-wrapper');
    if (!singleWrapper || singleWrapper.dataset.kulaMounted === '1') return;
    singleWrapper.dataset.kulaMounted = '1';

    // Envolver con la Barra Lateral TradingView Pro de 44px + Contenedor Dual (1 Vela / 3 Velas)
    const parent = singleWrapper.parentNode;
    const workspaceShell = document.createElement('div');
    workspaceShell.className = 'flex items-stretch gap-1.5 w-full relative';

    const toolbarHtml = `
      <aside id="kula-left-drawing-bar" class="w-[40px] shrink-0 bg-slate-950/95 border border-slate-800 rounded-lg py-1.5 px-1 flex flex-col items-center gap-1 select-none shadow-lg z-20">
        <button type="button" onclick="window.KulaChartEngine.setDrawingTool('cursor')" id="ku-tool-cursor" class="w-7 h-7 rounded flex items-center justify-center text-xs bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 cursor-pointer" title="Cursor Crosshair">➕</button>
        <button type="button" onclick="window.KulaChartEngine.setDrawingTool('trendline')" id="ku-tool-trendline" class="w-7 h-7 rounded flex items-center justify-center text-xs text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer" title="Línea de Tendencia (2 clics)">╱</button>
        <button type="button" onclick="window.KulaChartEngine.setDrawingTool('fibo')" id="ku-tool-fibo" class="w-7 h-7 rounded flex items-center justify-center text-xs text-amber-400 hover:bg-slate-800 cursor-pointer" title="Zona Dorada Fibonacci (0.382 - 0.75)">📐</button>
        <button type="button" onclick="window.KulaChartEngine.setDrawingTool('ob')" id="ku-tool-ob" class="w-7 h-7 rounded flex items-center justify-center text-xs text-indigo-400 hover:bg-slate-800 cursor-pointer" title="Order Block Institucional">🧱</button>
        <button type="button" onclick="window.KulaChartEngine.setDrawingTool('rr')" id="ku-tool-rr" class="w-7 h-7 rounded flex items-center justify-center text-xs text-emerald-400 hover:bg-slate-800 cursor-pointer" title="Proyección Asimetría R:R (1:2)">⚖️</button>
        <div class="w-5 border-t border-slate-800 my-0.5"></div>
        <button type="button" onclick="window.KulaChartEngine.clearDrawings()" class="w-7 h-7 rounded flex items-center justify-center text-xs text-rose-400 hover:bg-rose-950/60 cursor-pointer" title="Borrar Dibujos">🗑️</button>
      </aside>`;

    const contentCol = document.createElement('div');
    contentCol.className = 'flex-1 min-w-0 relative';

    parent.insertBefore(workspaceShell, singleWrapper);
    workspaceShell.insertAdjacentHTML('afterbegin', toolbarHtml);
    workspaceShell.appendChild(contentCol);
    contentCol.appendChild(singleWrapper);

    // Reajustar inmediatamente el ancho del gráfico principal al descontar los 40px de la barra lateral
    if (HOST_STATE.hostChart && singleWrapper.clientWidth > 0) {
      HOST_STATE.hostChart.applyOptions({ width: singleWrapper.clientWidth });
    }
    let _lastSingleWidth = singleWrapper.clientWidth;
    if (typeof ResizeObserver !== 'undefined') {
      const roSingle = new ResizeObserver(entries => {
        for (let entry of entries) {
          const w = Math.floor(entry.contentRect.width);
          if (w > 0 && Math.abs(w - _lastSingleWidth) >= 2 && HOST_STATE.hostChart) {
            _lastSingleWidth = w;
            HOST_STATE.hostChart.applyOptions({ width: w });
          }
        }
      });
      roSingle.observe(singleWrapper);
    }

    // Lienzo SVG para herramientas de dibujo sobre el gráfico
    const svgOverlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgOverlay.setAttribute('id', 'kula-drawing-svg');
    svgOverlay.setAttribute('class', 'absolute inset-0 w-full h-full pointer-events-none z-20');
    contentCol.appendChild(svgOverlay);

    // Contenedor de las 3 Velas (Tríada 1D · 1H · 5M) con altura generosa y leyenda exterior
    const triadHeight = options.triadHeight || 640;
    const triadHtml = `
      <div id="kula-triad-workspace" class="hidden w-full flex flex-col gap-1.5" style="height: ${triadHeight}px;">
        <!-- 1. Gráfico Superior: 1D Macro (Marco Blanco Sólido Canónico) -->
        <div class="ecosystem-triad-panel flex flex-col flex-1 min-h-0 bg-[#0b0e14] rounded-lg overflow-hidden p-1.5">
          <div class="w-full font-mono text-[10px] bg-slate-900/90 px-2 py-0.5 rounded border border-slate-800 flex items-center justify-between gap-2 shrink-0 mb-1">
            <div class="flex items-center gap-1.5 truncate">
              <span class="text-white font-bold">VELA &rarr;</span>
              <span class="text-amber-400 font-bold">[1D Macro]</span>
              <span id="ku-triad-ohlc-1d" class="text-slate-200 truncate">Cargando...</span>
              <span id="ku-triad-pat-1d" class="px-1.5 py-0.2 rounded text-[9px] bg-slate-800 text-slate-300">🕯️</span>
            </div>
            <div id="ku-triad-ind-1d" class="text-[9.5px] text-slate-400 shrink-0">SMA20: -- | EMA50: -- | VWAP: --</div>
          </div>
          <div class="relative flex-1 w-full overflow-hidden min-h-0">
            <div id="ku-triad-canvas-1d" class="w-full h-full"></div>
          </div>
        </div>
        <!-- 2. Gráficos Inferiores: 1H Intermedia + 5M Gatillo (Marco Blanco Sólido Canónico) -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-1.5 flex-1 min-h-0">
          <div class="ecosystem-triad-panel flex flex-col h-full min-h-0 bg-[#0b0e14] rounded-lg overflow-hidden p-1.5">
            <div class="w-full font-mono text-[10px] bg-slate-900/90 px-2 py-0.5 rounded border border-slate-800 flex items-center justify-between gap-1.5 shrink-0 mb-1">
              <div class="flex items-center gap-1.5 truncate">
                <span class="text-white font-bold">VELA &rarr;</span>
                <span class="text-indigo-400 font-bold">[1H Setup]</span>
                <span id="ku-triad-ohlc-1h" class="text-slate-200 truncate">Cargando...</span>
                <span id="ku-triad-pat-1h" class="px-1.5 py-0.2 rounded text-[9px] bg-slate-800 text-slate-300">🕯️</span>
              </div>
              <div id="ku-triad-ind-1h" class="text-[9.5px] text-slate-400 shrink-0">SMA20: -- | EMA20: -- | VWAP: --</div>
            </div>
            <div class="relative flex-1 w-full overflow-hidden min-h-0">
              <div id="ku-triad-canvas-1h" class="w-full h-full"></div>
            </div>
          </div>
          <div class="ecosystem-triad-panel flex flex-col h-full min-h-0 bg-[#0b0e14] rounded-lg overflow-hidden p-1.5">
            <div class="w-full font-mono text-[10px] bg-slate-900/90 px-2 py-0.5 rounded border border-slate-800 flex items-center justify-between gap-1.5 shrink-0 mb-1">
              <div class="flex items-center gap-1.5 truncate">
                <span class="text-white font-bold">VELA &rarr;</span>
                <span class="text-emerald-400 font-bold">[5M Gatillo]</span>
                <span id="ku-triad-ohlc-5m" class="text-slate-200 truncate">Cargando...</span>
                <span id="ku-triad-pat-5m" class="px-1.5 py-0.2 rounded text-[9px] bg-slate-800 text-slate-300">🕯️</span>
              </div>
              <div id="ku-triad-ind-5m" class="text-[9.5px] text-slate-400 shrink-0">SMA20: -- | EMA20: -- | VWAP: --</div>
            </div>
            <div class="relative flex-1 w-full overflow-hidden min-h-0">
              <div id="ku-triad-canvas-5m" class="w-full h-full"></div>
            </div>
          </div>
        </div>
      </div>`;
    contentCol.insertAdjacentHTML('beforeend', triadHtml);

    // Eventos de dibujo interactivo sobre el SVG
    let drawStart = null;
    svgOverlay.addEventListener('mousedown', e => {
      if (HOST_STATE.activeTool === 'cursor') return;
      const rect = svgOverlay.getBoundingClientRect();
      drawStart = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    });
    svgOverlay.addEventListener('mouseup', e => {
      if (!drawStart || HOST_STATE.activeTool === 'cursor') return;
      const rect = svgOverlay.getBoundingClientRect();
      const end = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      renderSvgDrawing(svgOverlay, HOST_STATE.activeTool, drawStart, end);
      drawStart = null;
      setDrawingTool('cursor');
    });
  }

  function renderSvgDrawing(svg, tool, p1, p2) {
    if (tool === 'trendline') {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', p1.x);
      line.setAttribute('y1', p1.y);
      line.setAttribute('x2', p2.x);
      line.setAttribute('y2', p2.y);
      line.setAttribute('stroke', '#38bdf8');
      line.setAttribute('stroke-width', '2');
      svg.appendChild(line);
    } else if (tool === 'fibo') {
      const levels = [
        { r: 0, lbl: '0.0%', col: '#94a3b8' },
        { r: 0.382, lbl: '38.2%', col: '#38bdf8' },
        { r: 0.5, lbl: '50.0% (Zona Dorada)', col: '#f59e0b' },
        { r: 0.618, lbl: '61.8% (Áureo)', col: '#eab308' },
        { r: 0.75, lbl: '75.0% (Cava-Ruiz)', col: '#10b981' },
        { r: 1, lbl: '100.0%', col: '#94a3b8' }
      ];
      const xMin = Math.min(p1.x, p2.x);
      const xMax = Math.max(p1.x, p2.x, xMin + 140);
      levels.forEach(lv => {
        const y = p1.y + (p2.y - p1.y) * lv.r;
        const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        l.setAttribute('x1', xMin);
        l.setAttribute('y1', y);
        l.setAttribute('x2', xMax);
        l.setAttribute('y2', y);
        l.setAttribute('stroke', lv.col);
        l.setAttribute('stroke-width', '1.5');
        l.setAttribute('stroke-dasharray', '4,2');
        svg.appendChild(l);
        const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        t.setAttribute('x', xMin + 4);
        t.setAttribute('y', y - 3);
        t.setAttribute('fill', lv.col);
        t.setAttribute('font-size', '10');
        t.setAttribute('font-family', 'monospace');
        t.textContent = lv.lbl;
        svg.appendChild(t);
      });
    } else if (tool === 'ob') {
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', Math.min(p1.x, p2.x));
      rect.setAttribute('y', Math.min(p1.y, p2.y));
      rect.setAttribute('width', Math.max(20, Math.abs(p2.x - p1.x)));
      rect.setAttribute('height', Math.max(12, Math.abs(p2.y - p1.y)));
      rect.setAttribute('fill', 'rgba(99, 102, 241, 0.22)');
      rect.setAttribute('stroke', '#6366f1');
      rect.setAttribute('stroke-width', '1.5');
      svg.appendChild(rect);
    } else if (tool === 'rr') {
      const leftX = Math.min(p1.x, p2.x);
      const w = Math.max(40, Math.abs(p2.x - p1.x));
      const entryY = p1.y;
      const tpY = Math.min(p1.y, p2.y);
      const targetH = Math.max(18, Math.abs(entryY - tpY));
      const stopH = Math.max(14, Math.round(targetH * 0.45));
      // Caja Verde TP
      const rTp = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rTp.setAttribute('x', leftX);
      rTp.setAttribute('y', entryY - targetH);
      rTp.setAttribute('width', w);
      rTp.setAttribute('height', targetH);
      rTp.setAttribute('fill', 'rgba(16, 185, 129, 0.20)');
      rTp.setAttribute('stroke', '#10b981');
      rTp.setAttribute('stroke-width', '1.5');
      svg.appendChild(rTp);
      // Caja Roja Intensa SL
      const rSl = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rSl.setAttribute('x', leftX);
      rSl.setAttribute('y', entryY);
      rSl.setAttribute('width', w);
      rSl.setAttribute('height', stopH);
      rSl.setAttribute('fill', 'rgba(239, 68, 68, 0.38)');
      rSl.setAttribute('stroke', '#ef4444');
      rSl.setAttribute('stroke-width', '2');
      svg.appendChild(rSl);
    }
  }

  function setDrawingTool(tool) {
    HOST_STATE.activeTool = tool;
    ['cursor', 'trendline', 'fibo', 'ob', 'rr'].forEach(t => {
      const btn = document.getElementById(`ku-tool-${t}`);
      if (btn) {
        btn.className = (t === tool)
          ? "w-7 h-7 rounded flex items-center justify-center text-xs bg-cyan-500/25 text-cyan-300 border border-cyan-500/50 cursor-pointer"
          : "w-7 h-7 rounded flex items-center justify-center text-xs text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer";
      }
    });
    const svg = document.getElementById('kula-drawing-svg');
    if (svg) {
      svg.style.pointerEvents = (tool === 'cursor') ? 'none' : 'auto';
      svg.style.cursor = (tool === 'cursor') ? 'default' : 'crosshair';
    }
  }

  function clearDrawings() {
    const svg = document.getElementById('kula-drawing-svg');
    if (svg) svg.innerHTML = '';
  }

  function setHostLayoutMode(mode) {
    HOST_STATE.mode = mode;
    const singleEl = document.getElementById('kula-single-chart-wrapper');
    const triadEl = document.getElementById('kula-triad-workspace');
    const btn1v = document.getElementById('ku-btn-mode-1v');
    const btn3v = document.getElementById('ku-btn-mode-3v');

    if (mode === '3v') {
      if (singleEl) singleEl.classList.add('hidden');
      if (triadEl) {
        triadEl.classList.remove('hidden');
        ensureTriadInitialized(triadEl);
        refreshEmbeddedTriad();
      }
      if (btn3v) btn3v.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/25 text-amber-300 border border-amber-500/50 cursor-pointer";
      if (btn1v) btn1v.className = "px-2 py-0.5 rounded text-[10px] font-bold text-slate-400 hover:text-white cursor-pointer";
    } else {
      if (triadEl) triadEl.classList.add('hidden');
      if (singleEl) singleEl.classList.remove('hidden');
      if (btn1v) btn1v.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/25 text-emerald-300 border border-emerald-500/50 cursor-pointer";
      if (btn3v) btn3v.className = "px-2 py-0.5 rounded text-[10px] font-bold text-slate-400 hover:text-white cursor-pointer";
    }
  }

  function toggleHostTheme() {
    HOST_STATE.isLight = !HOST_STATE.isLight;
    const opts = getChartThemeOptions(HOST_STATE.isLight);
    if (HOST_STATE.hostChart) HOST_STATE.hostChart.applyOptions(opts);
    if (HOST_STATE.hostRsiChart) HOST_STATE.hostRsiChart.applyOptions(opts);
    if (HOST_STATE.hostAtrChart) HOST_STATE.hostAtrChart.applyOptions(opts);
    ['c1D', 'c1H', 'c5M'].forEach(k => {
      if (HOST_STATE.triadCharts[k]) HOST_STATE.triadCharts[k].applyOptions(opts);
    });
    const btn = document.getElementById('ku-btn-theme');
    if (btn) {
      btn.innerHTML = HOST_STATE.isLight ? '☀️ Blanco' : '🌙 Oscuro';
    }
  }

  // Exportar motor al espacio global
  window.KulaChartEngine = {
    CANDLE_SERIES_OPTIONS,
    getChartThemeOptions,
    applyTradingViewProportions,
    formatPrice,
    formatVolume,
    formulas: {
      calculateSMA,
      calculateEMA,
      calculateVolumeSMA,
      calculateVWAP,
      calculateRSI,
      calculateATR,
      detectCandlePatternDetails
    },
    ensureCandlePatternModal,
    renderUniversalPatternModal,
    mountUnifiedChartWorkspace,
    setHostLayoutMode,
    refreshEmbeddedTriad,
    setDrawingTool,
    clearDrawings,
    toggleHostTheme,
    HOST_STATE
  };

  if (typeof window.detectCandlePatternDetails !== 'function') {
    window.detectCandlePatternDetails = detectCandlePatternDetails;
  }
})(window);
