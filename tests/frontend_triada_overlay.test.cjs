const test = require('node:test');
const assert = require('node:assert/strict');

const triada = require('../frontend/triada_overlay.js');

test('normalizeTriadaSymbol normalizes compact crypto, slash crypto, and forex/equities safely', () => {
  assert.equal(triada.normalizeTriadaSymbol('ethusdt'), 'ETH/USDT');
  assert.equal(triada.normalizeTriadaSymbol('ETH/USDT'), 'ETH/USDT');
  assert.equal(triada.normalizeTriadaSymbol('EURUSD=X'), 'EURUSD=X');
  assert.equal(triada.normalizeTriadaSymbol('NVDA'), 'NVDA');
});

test('computeFiboBandGeometry clamps band inside chart viewport and hides out-of-range', () => {
  const g1 = triada.computeFiboBandGeometry(120, 190, 400);
  assert.equal(g1.visible, true);
  assert.equal(g1.top, 120);
  assert.equal(g1.height, 70);

  const g2 = triada.computeFiboBandGeometry(-20, 50, 400);
  assert.equal(g2.visible, true);
  assert.equal(g2.top, 0);
  assert.equal(g2.height, 50);

  const g3 = triada.computeFiboBandGeometry(null, 100, 400);
  assert.equal(g3.visible, false);
});

test('buildTriadaOverlayDescriptors maps all 5 points, red dotted Fibo 0.75 invalidation, and wick veto', () => {
  const snapshot = {
    status: 'ok',
    symbol: 'ETH/USDT',
    timeframe: '5m',
    evaluated_side: 'LONG',
    px_dec: 2,
    overlays: {
      rule0_macro_1d: { ok: true, ema50_1d: 1920.5, label: 'EMA50 1D (✅)' },
      rules12_structure_1h: {
        rule1_ok: true,
        rule2_ok: false,
        ema50_1h: 1950.0,
        ema21_1h: 1945.0,
        ema89_1h: 1960.0,
        label: 'EMA50 1H (✅) · Abanico 21/89 (❌)',
        series_ema50: [{ time: 1, value: 1950 }],
        series_ema21: [{ time: 1, value: 1945 }],
        series_ema89: [{ time: 1, value: 1960 }],
      },
      rule3_fibo_golden_zone: {
        ok: true,
        swing_high: 2100.0,
        swing_low: 1800.0,
        fibo_50: 1950.0,
        fibo_75: 1875.0,
        zone_min: 1875.0,
        zone_max: 1950.0,
      },
      rule4_atr_switch: {
        ok: true,
        regime: 'EXPANSION',
        badge_text: 'EXPANSION (Retroceso)',
        atr_tactical: 12.4,
        atr_sma_tactical: 8.2,
      },
      rule5_wick_and_candlestick: {
        wick_veto_active: true,
        wick_veto_reason: 'Mecha superior >= 50%',
        last_candle_ts: 1795200000,
        marker_text: '⚠️ VETO MECHA >= 50%',
      },
    },
    execution_plan: {
      can_execute: false,
      block_reasons: ['Mecha superior >= 50%'],
      side: 'LONG',
      entry_price: 1960.0,
      sl_price: 1930.0,
      tp_price: 2025.0,
      sl_gross_pct: 1.53,
      tp_gross_pct: 3.32,
      net_rr: 2.02,
      risk_pct: 0.5,
      risk_budget_usd: 2.5,
      currency: 'USDT',
      qty: 0.08,
      notional_usd: 156.8,
      active_manual_sim: {
        side: 'LONG',
        entry_price: 1960.0,
        sl_price: 1930.0,
        tp_price: 2025.0,
        initial_sl_pct: 1.53,
        initial_tp_pct: 3.32,
      },
    },
  };

  const desc = triada.buildTriadaOverlayDescriptors(snapshot);
  assert.equal(desc.valid, true);
  assert.equal(desc.lines1D.length, 1);
  assert.equal(desc.lines1D[0].title, 'EMA50 1D (✅)');

  const fiboInv = desc.lines1H.find((x) => x.title.includes('INVALIDACIÓN'));
  assert.ok(fiboInv);
  assert.equal(fiboInv.color, '#ef4444');
  assert.equal(fiboInv.lineStyle, 'dotted');
  assert.equal(fiboInv.price, 1875.0);

  assert.equal(desc.fiboBand.zoneMin, 1875.0);
  assert.equal(desc.fiboBand.zoneMax, 1950.0);
  assert.equal(desc.atrBadge.text, 'EXPANSION (Retroceso)');
  assert.equal(desc.candleMarker.wickVetoActive, true);
  assert.equal(desc.candleMarker.text, '⚠️ VETO MECHA >= 50%');

  assert.equal(desc.executionCard.canExecute, false);
  assert.equal(desc.executionCard.simLines.length, 3);
});

test('buildTriadaOverlayDescriptors maps 5-step Presencial Protocol (Setup A/B, RVOL bipolar, session window, daily quota)', () => {
  const snapshot = {
    status: 'ok',
    symbol: 'ETH/USDT',
    timeframe: '15m',
    evaluated_side: 'LONG',
    px_dec: 2,
    presencial_protocol: {
      active_setup: 'SETUP_A_SQUEEZE',
      active_setup_label: 'Setup A (Ruptura Compresión 1H→15M)',
      setup_triggered: true,
      setup_a_squeeze: { triggered: true },
      rvol_gate: {
        rvol_tod: 2.15,
        min_required: 1.8,
        ok: true,
        label: '2.15x / req ≥ 1.80x (Verde)',
      },
      session_guard: {
        window_label: 'Londres / NY AM (09:30–13:30 ART)',
        is_blackout: false,
        tf_floor_ok: true,
      },
      daily_limits: {
        daily_trades_count: 1,
        max_daily_trades: 2,
        daily_sl_count: 0,
        max_daily_sl: 2,
        ok: true,
      },
    },
    overlays: {},
    execution_plan: {
      can_execute: true,
      block_reasons: [],
      side: 'LONG',
      entry_price: 2010.0,
      sl_price: 1985.88,
      tp_price: 2065.0,
      sl_gross_pct: 1.2,
      tp_gross_pct: 2.74,
      net_rr: 2.01,
    },
  };

  const desc = triada.buildTriadaOverlayDescriptors(snapshot);
  assert.equal(desc.valid, true);
  assert.equal(desc.presencialProtocol.activeSetup, 'SETUP_A_SQUEEZE');
  assert.equal(desc.presencialProtocol.setupATriggered, true);
  assert.equal(desc.presencialProtocol.rvolTod, 2.15);
  assert.equal(desc.presencialProtocol.rvolOk, true);
  assert.equal(desc.presencialProtocol.sessionBlackout, false);
  assert.equal(desc.presencialProtocol.dailyQuotaText, '1/2 ops · 0/2 SL');
});
