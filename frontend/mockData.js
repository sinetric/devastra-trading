(function (global) {
  'use strict';

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rand = mulberry32(20260904);
  const randInt = (min, max) => Math.floor(rand() * (max - min + 1)) + min;
  const pick = (arr) => arr[Math.floor(rand() * arr.length)];
  const round = (n, d) => { const p = Math.pow(10, d); return Math.round(n * p) / p; };

  const SECTORS = ['Technology', 'Semiconductors', 'Energy', 'Financials', 'Healthcare', 'Consumer', 'Industrials', 'Biotech'];
  const STRATEGIES = ['Call', 'Put', 'Call Spread', 'Put Spread', 'Iron Condor', 'Straddle', 'Calendar'];
  const REGIMES = ['Bullish', 'Bearish', 'Range-bound', 'High Volatility', 'Risk-Off'];

  // Candidate seed list (dummy tickers)
  const TICKERS = [
    ['NVDA', 'NVIDIA Corp', 'Semiconductors'],
    ['TSLA', 'Tesla Inc', 'Consumer'],
    ['AMD', 'Advanced Micro Devices', 'Semiconductors'],
    ['AAPL', 'Apple Inc', 'Technology'],
    ['MSFT', 'Microsoft Corp', 'Technology'],
    ['META', 'Meta Platforms', 'Technology'],
    ['AMZN', 'Amazon.com', 'Consumer'],
    ['GOOGL', 'Alphabet Inc', 'Technology'],
    ['SMCI', 'Super Micro Computer', 'Semiconductors'],
    ['PLTR', 'Palantir Technologies', 'Technology'],
    ['COIN', 'Coinbase Global', 'Financials'],
    ['MSTR', 'MicroStrategy', 'Technology'],
    ['AVGO', 'Broadcom Inc', 'Semiconductors'],
    ['MU', 'Micron Technology', 'Semiconductors'],
    ['INTC', 'Intel Corp', 'Semiconductors'],
    ['ORCL', 'Oracle Corp', 'Technology'],
    ['CRM', 'Salesforce Inc', 'Technology'],
    ['NFLX', 'Netflix Inc', 'Consumer'],
    ['XOM', 'Exxon Mobil', 'Energy'],
    ['CVX', 'Chevron Corp', 'Energy'],
    ['LLY', 'Eli Lilly', 'Healthcare'],
    ['UNH', 'UnitedHealth Group', 'Healthcare'],
    ['JPM', 'JPMorgan Chase', 'Financials'],
    ['CAT', 'Caterpillar Inc', 'Industrials'],
    ['BA', 'Boeing Co', 'Industrials']
  ];

  function genSeries(base, n, vol) {
    const out = [];
    let price = base;
    for (let i = 0; i < n; i++) {
      const o = price;
      const drift = (rand() - 0.48) * vol * 2;
      const c = Math.max(1, o + drift);
      const h = Math.max(o, c) + rand() * vol * 0.6;
      const l = Math.max(0.1, Math.min(o, c) - rand() * vol * 0.6);
      out.push({ t: i, o: round(o, 2), h: round(h, 2), l: round(l, 2), c: round(c, 2) });
      price = c;
    }
    return out;
  }

  function genEquityCurve(n, start, drift, vol) {
    const out = [];
    let v = start;
    for (let i = 0; i < n; i++) {
      v = v * (1 + (rand() - 0.5 + drift) * vol);
      out.push(round(v, 0));
    }
    return out;
  }

  function makeCandidate(tickerData, idx) {
    const [sym, name, sector] = tickerData;
    const base = round(40 + rand() * 900, 2);
    const momentum = randInt(35, 99);
    const volume = randInt(2, 48) * 1000000;
    const volumeRatio = round(1 + rand() * 4, 2);
    const volatility = round(0.15 + rand() * 0.75, 2);
    const optionsLiq = randInt(30, 99);
    const risk = randInt(8, 75);
    const confidence = round(0.4 + rand() * 0.59, 2);
    const iv = round(0.25 + rand() * 0.8, 2);
    const changePct = round((rand() - 0.42) * 9, 2);
    const regime = pick(REGIMES);
    const session = idx % 2 === 0 ? 'Pre-Market' : 'Market Open';

    const series = genSeries(base, 60, base * 0.02);

    return {
      id: sym,
      ticker: sym,
      name,
      sector,
      price: round(series[series.length - 1].c, 2),
      changePct,
      volume,
      volumeRatio,
      volatility,
      momentumScore: momentum,
      optionsLiqScore: optionsLiq,
      riskScore: risk,
      confidence,
      impliedVolatility: iv,
      regime,
      session,
      rank: 0,
      decision: confidence > 0.8 ? 'BUY' : confidence > 0.62 ? 'BUY' : confidence > 0.45 ? 'MANUAL REVIEW' : 'NO TRADE',
      series,
      options: genOptions(series[series.length - 1].c, iv)
    };
  }

  function genOptions(spot, iv) {
    const expiries = ['3 DTE', '7 DTE', '14 DTE', '30 DTE', '45 DTE'];
    const strikes = [];
    for (let i = -2; i <= 2; i++) {
      const strike = round(spot * (1 + i * 0.025), 2);
      const vol = randInt(200, 9000);
      const oi = randInt(500, 20000);
      const spread = round(0.02 + rand() * 0.35, 2);
      const delta = round(0.1 + rand() * 0.8, 2);
      const gamma = round(0.01 + rand() * 0.2, 3);
      const vega = round(0.05 + rand() * 0.4, 2);
      const theta = round(-(0.01 + rand() * 0.15), 3);
      strikes.push({ strike, expiry: pick(expiries), iv: round(iv * (0.85 + rand() * 0.4), 2), volume: vol, openInterest: oi, spread, delta, gamma, vega, theta, liquidity: randInt(30, 99) });
    }
    return strikes;
  }


  const candidates = TICKERS.map(makeCandidate).sort((a, b) => b.momentumScore - a.momentumScore);
  candidates.forEach((c, i) => { c.rank = i + 1; });

  const finalists = candidates.slice(0, 12).sort((a, b) => b.confidence - a.confidence);
  const preMarket = candidates.filter(c => c.session === 'Pre-Market');
  const marketOpen = candidates.filter(c => c.session === 'Market Open');


  const positions = [
    { id: 'NVDA', ticker: 'NVDA', name: 'NVIDIA Corp', strategy: 'Call Spread', qty: 4, entry: 3.42, current: 4.85, delta: 0.68, gamma: 0.11, vega: 0.32, theta: -0.05 },
    { id: 'TSLA', ticker: 'TSLA', name: 'Tesla Inc', strategy: 'Put', qty: 6, entry: 2.10, current: 1.62, delta: -0.55, gamma: 0.08, vega: 0.24, theta: -0.03 },
    { id: 'AMD', ticker: 'AMD', name: 'Advanced Micro Devices', strategy: 'Call', qty: 10, entry: 1.85, current: 2.40, delta: 0.71, gamma: 0.13, vega: 0.28, theta: -0.06 },
    { id: 'SMCI', ticker: 'SMCI', name: 'Super Micro Computer', strategy: 'Straddle', qty: 3, entry: 4.20, current: 4.68, delta: 0.02, gamma: 0.09, vega: 0.51, theta: -0.09 },
    { id: 'META', ticker: 'META', name: 'Meta Platforms', strategy: 'Iron Condor', qty: 5, entry: 2.90, current: 2.55, delta: -0.05, gamma: 0.04, vega: -0.18, theta: 0.07 }
  ].map(p => {
    const notional = p.qty * 100 * p.current;
    const pnl = round((p.current - p.entry) * p.qty * 100, 2);
    return { ...p, notional, pnl, pnlPct: round((p.current / p.entry - 1) * 100, 2) };
  });


  const portfolio = {
    totalEquity: 248530,
    dailyPnl: 3420,
    unrealizedPnl: 5120,
    realizedPnl: -840,
    buyingPower: 96180,
    totalExposure: 84210,
    var: 4120,
    exposurePct: 34,
    drawdown: -1.8,
    portfolioDelta: 0.42,
    portfolioGamma: 0.08,
    portfolioVega: 0.21
  };

  // ---- Risk engine ----
  const risk = {
    maxPositionSize: 25000,
    currentMaxPosition: 14900,
    maxDailyLoss: -6000,
    currentDailyLoss: 0,
    maxDrawdownAllowed: -8,
    currentDrawdown: -1.8,
    positionConcentration: 22,
    sectorConcentration: 41,
    liquidityRisk: 'LOW',
    spreadRisk: 'MODERATE',
    limits: [
      { label: 'Maximum Position Size', value: '$25,000', current: '$14,900', pct: 60 },
      { label: 'Portfolio Exposure', value: '$84,210', current: '34%', pct: 34 },
      { label: 'Portfolio Delta', value: '±0.60', current: '0.42', pct: 70 },
      { label: 'Portfolio Gamma', value: '±0.15', current: '0.08', pct: 53 },
      { label: 'Portfolio Vega', value: '±0.40', current: '0.21', pct: 52 },
      { label: 'Maximum Daily Loss', value: '-$6,000', current: '$0', pct: 0 },
      { label: 'Max Drawdown', value: '-8%', current: '-1.8%', pct: 22 },
      { label: 'Position Concentration', value: '25%', current: '22%', pct: 88 },
      { label: 'Sector Concentration', value: '50%', current: '41%', pct: 82 },
      { label: 'Liquidity Risk', value: 'LOW', current: 'LOW', pct: 15 },
      { label: 'Options Spread Risk', value: 'MODERATE', current: 'MODERATE', pct: 55 },
      { label: 'Buying Power Usage', value: '$96,180', current: '62%', pct: 62 }
    ]
  };

  const funnel = [
    { label: 'Total Universe', crit: 'All liquid US equities', count: 5000 },
    { label: 'Initial Screening', crit: 'Price > $5, volume > 500K', count: 1842 },
    { label: 'Market Movement', crit: 'Abnormal volume & momentum', count: 326 },
    { label: 'Options Liquidity', crit: 'OI > 2K, spread < $0.20', count: 88 },
    { label: 'Risk Filtering', crit: 'Risk score & exposure limits', count: 28 },
    { label: 'Finalists', crit: '10–25 qualified candidates', count: 12 },
    { label: 'Best Setups', crit: 'Risk-adjusted trade quality', count: 5 }
  ];

  // ---- Activity feed (seed + dynamic generation) ----
  const feedSeed = [
    ['scan', 'ALG', 'Scanning 4,821 stocks across 8 sectors...'],
    ['scan', 'ALG', 'Feature engineering: momentum, volume anomaly, IV rank...'],
    ['scan', 'ALG', 'Filtering candidates based on abnormal volume...'],
    ['scan', 'ALG', 'Analyzing options liquidity (OI, spread, Greeks)...'],
    ['ai', 'AI', 'Claude Sonnet analyzing 12 finalist candidates...'],
    ['risk', 'RISK', 'Risk engine evaluating proposed NVDA position...'],
    ['risk', 'RISK', 'NVDA rejected — concentration risk exceeds 25% limit...'],
    ['exec', 'EXEC', 'Paper trade executed: TSLA Put x6 @ $2.10'],
    ['ai', 'AI', 'AMD thesis generated — bullish momentum, IV percentile 78'],
    ['risk', 'RISK', 'SMCI straddle flagged — high vega, requires manual review']
  ];


  const perf = {
    equityCurve: genEquityCurve(120, 200000, 0.0016, 0.012),
    dailyPnl: genEquityCurve(40, 0, 0, 1).map(v => round(v * 800, 0)),
    monthlyPnl: [1820, -640, 2410, 3150, -210, 1280, 2940, 3420],
    metrics: {
      sharpe: 1.94,
      sortino: 2.61,
      maxDrawdown: -7.8,
      winRate: 58.4,
      profitFactor: 1.72,
      avgWinner: 1240,
      avgLoser: -720,
      expectancy: 315
    },
    byStrategy: [
      { label: 'Call Spread', value: 6420 },
      { label: 'Call', value: 4180 },
      { label: 'Put', value: -980 },
      { label: 'Straddle', value: 1510 },
      { label: 'Iron Condor', value: -640 }
    ],
    bySector: [
      { label: 'Semiconductors', value: 7120 },
      { label: 'Technology', value: 3840 },
      { label: 'Consumer', value: -1120 },
      { label: 'Financials', value: 860 },
      { label: 'Energy', value: -410 }
    ],
    benchmark: genEquityCurve(120, 200000, 0.0009, 0.01)
  };


  const manualQueue = [
    {
      id: 'MR-1042', ticker: 'SMCI', name: 'Super Micro Computer', time: '09:42',
      situation: 'Elevated IV post-earnings; wide bid-ask in near-dated options.',
      availableData: 'Momentum 88, IV 0.72, volume ratio 3.1x, OI 14.2K',
      uncertainty: 'Claude flags conflicting signals: strong momentum vs. extreme vega risk and low near-term liquidity.',
      strategies: ['Straddle (long vol)', 'Call Spread (limited risk)'],
      risk: 'High vega exposure; potential for IV crush. Concentration 18%.',
      status: 'PENDING'
    },
    {
      id: 'MR-1041', ticker: 'MSTR', name: 'MicroStrategy', time: '09:38',
      situation: 'Correlated with BTC proxy; regime shifted risk-off.',
      availableData: 'Momentum 74, beta 3.1, IV 0.58, spread $0.18',
      uncertainty: 'AI confidence below threshold (0.51); crypto correlation not modeled by quant signals.',
      strategies: ['Put Spread (hedge)', 'No Trade'],
      risk: 'High beta; potential gap risk at open.',
      status: 'PENDING'
    },
    {
      id: 'MR-1040', ticker: 'BA', name: 'Boeing Co', time: '09:31',
      situation: 'News catalyst: delivery guidance; options volume spiking.'
      availableData: 'Momentum 62, volume ratio 2.4x, IV 0.39, OI 8.9K',
      uncertainty: 'Catalyst-driven move; model lacks fundamental/news scoring.',
      strategies: ['Call (directional)', 'Call Spread'],
      risk: 'Event risk; binary outcome around announcement.',
      status: 'PENDING'
    }
  ];

  global.DEV = {
    rand, randInt, pick, round,
    candidates, finalists, preMarket, marketOpen,
    positions, portfolio, risk, funnel, feedSeed,
    perf, manualQueue, REGIMES, STRATEGIES, SECTORS,
    genSeries, genEquityCurve
  };
})(window);
