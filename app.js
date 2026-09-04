(function () {
  'use strict';

  const D = window.DEV;
  const C = window.Charts;
  const main = document.getElementById('main');
  const modal = document.getElementById('modal');
  const $ = (s, p) => (p || document).querySelector(s);

  let currentView = 'dashboard';
  let scannerTab = 'pre-market';
  let feed = [];
  let simClock = new Date(2026, 8, 4, 9, 41, 22);
  const activeCandidates = D.candidates.slice();
  const reviewQueue = D.manualQueue.map(q => Object.assign({}, q));


  const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const money = (n) => (n < 0 ? '-$' : '$') + Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
  const sign = (n) => (n >= 0 ? '+' : '') + n;
  const pct = (n) => (n >= 0 ? '+' : '') + n.toFixed(2) + '%';

  function scoreClass(v, isRisk) {
    if (isRisk) return v <= 30 ? 'hi' : v <= 55 ? 'mid' : 'lo';
    return v >= 70 ? 'hi' : v >= 45 ? 'mid' : 'lo';
  }
  function scoreBadge(v, isRisk) {
    return '<span class="score ' + scoreClass(v, isRisk) + '">' + v + '</span>';
  }
  function meter(v, color) {
    return '<span class="meter ' + (color || '') + '"><i style="width:' + Math.min(100, v) + '%"></i></span>';
  }

  function thesisFor(c) {
    const bull = c.momentumScore >= 70;
    const strong = c.optionsLiqScore >= 65;
    const risky = c.riskScore >= 55;
    let decision, strategy, thesis, risks = [], factors = [];

    if (bull && strong && !risky) {
      decision = 'BUY';
      strategy = c.volatility > 0.6 ? 'Call Spread (limited risk)' : 'Call (directional)';
      thesis = c.ticker + ' shows strong momentum (' + c.momentumScore + ') with liquid options (liquidity ' + c.optionsLiqScore + ') and controlled risk (' + c.riskScore + '). Volume anomaly of ' + c.volumeRatio + 'x confirms institutional participation. Favorable risk/reward for a directional long with defined risk.';
      factors = ['Momentum score ' + c.momentumScore + ' (strong)', 'Options liquidity ' + c.optionsLiqScore + ' (healthy)', 'Volume anomaly ' + c.volumeRatio + 'x', 'Market regime: ' + c.regime];
      risks = ['IV percentile elevated at ' + Math.round(c.impliedVolatility * 100) + '%', 'Gap risk if momentum fades'];
    } else if (bull && risky) {
      decision = 'MANUAL REVIEW';
      strategy = 'Bull Call Spread (reduced vega)';
      thesis = 'Bullish momentum is present, but elevated risk (' + c.riskScore + ') from high implied volatility (' + c.impliedVolatility.toFixed(2) + ') requires human oversight. Recommend a defined-risk structure with reduced vega exposure.';
      factors = ['Momentum score ' + c.momentumScore, 'Volume anomaly ' + c.volumeRatio + 'x'];
      risks = ['Risk score ' + c.riskScore + ' exceeds comfort threshold', 'Potential IV crush', 'Concentration considerations'];
    } else if (c.momentumScore < 45) {
      decision = 'NO TRADE';
      strategy = 'None';
      thesis = 'Momentum is insufficient (' + c.momentumScore + ') and the setup does not clear the quantitative bar. Recommend passing — there is no edge in forcing this trade.';
      factors = ['Below-threshold momentum'];
      risks = ['Low conviction', 'Whipsaw risk'];
    } else {
      decision = 'BUY';
      strategy = 'Call';
      thesis = 'Moderate but constructive setup with acceptable risk (' + c.riskScore + ') and improving momentum (' + c.momentumScore + '). Monitor for confirmation before sizing.';
      factors = ['Momentum score ' + c.momentumScore, 'Options liquidity ' + c.optionsLiqScore];
      risks = ['Moderate conviction', 'Wider spread in near-term strikes'];
    }
    return { decision, confidence: c.confidence, thesis, factors, risks, strategy, invalidations: ['Close below 20-day VWAP', 'Volume ratio < 1.5x', 'IV rank < 40'] };
  }

  function decisionBadge(d) {
    const map = { 'BUY': 'ok', 'MANUAL REVIEW': 'warn', 'NO TRADE': 'danger' };
    return '<span class="badge ' + (map[d] || 'warn') + '">' + d + '</span>';
  }

  // ---- Toast ----
  function toast(msg) {
    let t = $('.toast');
    if (!t) {
      t = document.createElement('div');
      t.className = 'toast';
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove('show'), 2400);
  }



  function renderDashboard() {
    const p = D.portfolio;
    const best = D.finalists.slice(0, 5).map(thesisFor);
    main.innerHTML = `
      <div class="view-head">
        <div><div class="view-title">Dashboard</div><div class="view-desc">Quantitative signal overview &amp; live portfolio snapshot</div></div>
        <div class="view-actions">
          <button class="btn primary" data-action="scan">▶ Run Market Scan</button>
          <button class="btn" data-action="candidates">View Candidates</button>
          <button class="btn ai" data-action="analyze">◈ Analyze with AI</button>
        </div>
      </div>

      <div class="grid summary-grid" style="margin-bottom:14px">
        <div class="card summary-card"><span class="lbl">TOTAL EQUITY</span><span class="val mono">${money(p.totalEquity)}</span><span class="delta pos">${pct(p.dailyPnl / p.totalEquity * 100)} today</span></div>
        <div class="card summary-card"><span class="lbl">DAILY P&amp;L</span><span class="val mono pos">${money(p.dailyPnl)}</span><span class="delta muted">unrealized ${money(p.unrealizedPnl)}</span></div>
        <div class="card summary-card"><span class="lbl">BUYING POWER</span><span class="val mono">${money(p.buyingPower)}</span><span class="delta muted">62% available</span></div>
        <div class="card summary-card"><span class="lbl">EXPOSURE</span><span class="val mono">${money(p.totalExposure)}</span><span class="delta muted">${p.exposurePct}% of equity</span></div>
        <div class="card summary-card"><span class="lbl">VaR (1D)</span><span class="val mono warn">${money(p.var)}</span><span class="delta muted">95% confidence</span></div>
      </div>

      <div class="grid" style="grid-template-columns: 1.4fr 1fr">
        <div class="card">
          <div class="card-head"><span class="card-title">Algorithm Funnel</span><span class="card-sub">live narrowing</span></div>
          <div class="funnel" id="dash-funnel"></div>
        </div>
        <div class="card">
          <div class="card-head"><span class="card-title">Best Risk-Adjusted Setups</span><span class="card-sub">top 5 of ${D.finalists.length}</span></div>
          <div id="dash-best"></div>
        </div>
      </div>
    `;

    renderFunnel($('#dash-funnel'), D.funnel);
    $('#dash-best').innerHTML = best.map((t, i) => {
      const c = D.finalists[i];
      return `<div class="setup-row" data-open="${c.id}">
        <div class="setup-rank">${i + 1}</div>
        <div class="setup-main">
          <div><span class="ticker">${c.ticker}</span> <span class="sym">${c.name}</span></div>
          <div class="faint" style="font-size:11px">${t.strategy}</div>
        </div>
        <div class="setup-metrics mono">
          <span class="pos">${c.momentumScore}</span>
          <span class="faint">risk ${c.riskScore}</span>
        </div>
        ${decisionBadge(t.decision)}
      </div>`;
    }).join('');
  }

  function renderFunnel(node, funnel) {
    const max = funnel[0].count;
    node.innerHTML = funnel.map(f => `
      <div class="funnel-stage">
        <div class="funnel-label">${f.label}</div>
        <div class="funnel-bar" style="width:${Math.max(6, f.count / max * 100)}%">${f.count.toLocaleString()}</div>
        <div class="funnel-crit">${f.crit}</div>
      </div>`).join('');
  }

  function renderScanner() {
    main.innerHTML = `
      <div class="view-head">
        <div><div class="view-title">Market Scanner</div><div class="view-desc">Structured algorithm funnel from 5,000+ equities to qualified finalists</div></div>
        <div class="view-actions"><button class="btn primary" data-action="scan">▶ Re-Run Scan</button></div>
      </div>

      <div class="card" style="margin-bottom:14px">
        <div class="card-head"><span class="card-title">Funnel Pipeline</span><span class="card-sub">quantitative narrowing</span></div>
        <div class="funnel" id="scanner-funnel"></div>
      </div>

      <div class="card">
        <div class="tabs">
          <button class="tab ${scannerTab === 'pre-market' ? 'active' : ''}" data-tab="pre-market">Pre-Market<span class="count">${D.preMarket.length}</span></button>
          <button class="tab ${scannerTab === 'market-open' ? 'active' : ''}" data-tab="market-open">Market Open<span class="count">${D.marketOpen.length}</span></button>
          <button class="tab ${scannerTab === 'options' ? 'active' : ''}" data-tab="options">Options Data</button>
          <button class="tab ${scannerTab === 'final' ? 'active' : ''}" data-tab="final">Final Candidates<span class="count">${D.finalists.length}</span></button>
        </div>
        <div id="scanner-body"></div>
      </div>
    `;
    renderFunnel($('#scanner-funnel'), D.funnel);
    renderScannerBody();
  }

  function renderScannerBody() {
    const node = $('#scanner-body');
    if (scannerTab === 'pre-market' || scannerTab === 'market-open') {
      const list = scannerTab === 'pre-market' ? D.preMarket : D.marketOpen;
      node.innerHTML = `<div class="table-wrap"><table>
        <thead><tr><th>Ticker</th><th>Price</th><th class="th-r">Change</th><th class="th-r">Volume</th><th class="th-r">Vol Ratio</th><th class="th-r">Volatility</th><th class="th-r">Momentum</th><th class="th-r">Risk</th><th></th></tr></thead>
        <tbody>${list.map(c => `
          <tr class="clickable" data-open="${c.id}">
            <td><span class="ticker">${c.ticker}</span> <span class="sym">${c.name}</span></td>
            <td class="mono">$${c.price.toFixed(2)}</td>
            <td class="td-r mono ${c.changePct >= 0 ? 'pos' : 'neg'}">${pct(c.changePct)}</td>
            <td class="td-r mono">${C.fmt(c.volume)}</td>
            <td class="td-r mono">${c.volumeRatio}x</td>
            <td class="td-r mono">${(c.volatility * 100).toFixed(0)}%</td>
            <td class="td-r">${scoreBadge(c.momentumScore)}</td>
            <td class="td-r">${scoreBadge(c.riskScore, true)}</td>
            <td class="td-r"><button class="btn small" data-open="${c.id}">View</button></td>
          </tr>`).join('')}</tbody>
      </table></div>`;
    } else if (scannerTab === 'options') {
      const c = D.finalists[0];
      node.innerHTML = optionsTable(c);
    } else {
      node.innerHTML = `<div class="table-wrap"><table>
        <thead><tr><th>#</th><th>Ticker</th><th class="th-r">Price</th><th class="th-r">Momentum</th><th class="th-r">Opt Liq</th><th class="th-r">Risk</th><th class="th-r">Confidence</th><th>Decision</th><th></th></tr></thead>
        <tbody>${D.finalists.map((c, i) => {
          const t = thesisFor(c);
          return `<tr class="clickable" data-open="${c.id}">
            <td class="faint mono">${i + 1}</td>
            <td><span class="ticker">${c.ticker}</span> <span class="sym">${c.name}</span></td>
            <td class="td-r mono">$${c.price.toFixed(2)}</td>
            <td class="td-r">${scoreBadge(c.momentumScore)}</td>
            <td class="td-r">${scoreBadge(c.optionsLiqScore)}</td>
            <td class="td-r">${scoreBadge(c.riskScore, true)}</td>
            <td class="td-r mono">${(c.confidence * 100).toFixed(0)}%</td>
            <td>${decisionBadge(t.decision)}</td>
            <td class="td-r"><button class="btn small" data-open="${c.id}">Detail</button></td>
          </tr>`;
        }).join('')}</tbody>
      </table></div>`;
    }
  }

  function optionsTable(c) {
    return `<div class="legend" style="margin-bottom:10px">
      <span><b class="ticker">${c.ticker}</b> ${c.name}</span>
      <span>Spot <b class="mono">$${c.price.toFixed(2)}</b></span>
      <span>IV <b class="mono">${(c.impliedVolatility * 100).toFixed(0)}%</b></span>
      <span>Regime <b>${c.regime}</b></span>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Strike</th><th>Expiry</th><th class="th-r">IV</th><th class="th-r">Volume</th><th class="th-r">Open Int</th><th class="th-r">Spread</th><th class="th-r">Delta</th><th class="th-r">Gamma</th><th class="th-r">Vega</th><th class="th-r">Theta</th><th class="th-r">Liquidity</th></tr></thead>
      <tbody>${c.options.map(o => `
        <tr>
          <td class="mono">$${o.strike.toFixed(2)}</td>
          <td class="mono">${o.expiry}</td>
          <td class="td-r mono">${(o.iv * 100).toFixed(0)}%</td>
          <td class="td-r mono">${C.fmt(o.volume)}</td>
          <td class="td-r mono">${C.fmt(o.openInterest)}</td>
          <td class="td-r mono">$${o.spread.toFixed(2)}</td>
          <td class="td-r mono">${o.delta.toFixed(2)}</td>
          <td class="td-r mono">${o.gamma.toFixed(3)}</td>
          <td class="td-r mono">${o.vega.toFixed(2)}</td>
          <td class="td-r mono">${o.theta.toFixed(3)}</td>
          <td class="td-r">${scoreBadge(o.liquidity)}</td>
        </tr>`).join('')}</tbody>
    </table></div>`;
  }

  function renderCandidates() {
    main.innerHTML = `
      <div class="view-head">
        <div><div class="view-title">Candidate Leaderboard</div><div class="view-desc">Strongest stock candidates ranked by quantitative score</div></div>
      </div>
      <div class="card">
        <div class="table-wrap"><table>
          <thead><tr><th>#</th><th>Ticker</th><th class="th-r">Price</th><th class="th-r">Momentum</th><th class="th-r">Volume</th><th class="th-r">Volatility</th><th class="th-r">Opt Liq</th><th class="th-r">Risk</th><th class="th-r">AI Confidence</th><th></th></tr></thead>
          <tbody>${activeCandidates.map(c => `
            <tr class="clickable" data-open="${c.id}">
              <td class="faint mono">${c.rank}</td>
              <td><span class="ticker">${c.ticker}</span> <span class="sym">${c.name}</span></td>
              <td class="td-r mono">$${c.price.toFixed(2)}</td>
              <td class="td-r">${scoreBadge(c.momentumScore)} ${meter(c.momentumScore)}</td>
              <td class="td-r mono">${C.fmt(c.volume)}</td>
              <td class="td-r mono">${(c.volatility * 100).toFixed(0)}%</td>
              <td class="td-r">${scoreBadge(c.optionsLiqScore)}</td>
              <td class="td-r">${scoreBadge(c.riskScore, true)}</td>
              <td class="td-r mono">${(c.confidence * 100).toFixed(0)}%</td>
              <td class="td-r"><button class="btn small" data-open="${c.id}">Details</button> <button class="btn small ai" data-analyze="${c.id}">Analyze</button></td>
            </tr>`).join('')}</tbody>
        </table></div>
      </div>`;
  }

  function renderActivity() {
    main.innerHTML = `
      <div class="view-head">
        <div><div class="view-title">AI Activity Feed</div><div class="view-desc">Real-time algorithm &amp; reasoning log (auditable)</div></div>
        <div class="view-actions"><button class="btn ghost" data-action="clear-feed">Clear</button></div>
      </div>
      <div class="card"><div class="feed" id="feed-box"></div></div>`;
    renderFeed();
  }

  function renderFeed() {
    const box = $('#feed-box');
    if (!box) return;
    box.innerHTML = feed.slice().reverse().map(f => `
      <div class="feed-item ${f.type}">
        <span class="t">${f.time}</span>
        <span class="msg">${esc(f.msg)} <span class="tag ${f.type === 'ai' ? 'ai' : f.type === 'risk' ? 'risk' : f.type === 'exec' ? 'exec' : 'alg'}">${f.tag}</span></span>
      </div>`).join('');
  }

  function renderPositions() {
    const p = D.portfolio;
    main.innerHTML = `
      <div class="view-head"><div><div class="view-title">Open Positions</div><div class="view-desc">Real-time portfolio exposure</div></div></div>

      <div class="grid" style="grid-template-columns:repeat(7,1fr);margin-bottom:14px">
        <div class="card summary-card"><span class="lbl">EQUITY</span><span class="val mono">${money(p.totalEquity)}</span></div>
        <div class="card summary-card"><span class="lbl">DAILY P&amp;L</span><span class="val mono pos">${money(p.dailyPnl)}</span></div>
        <div class="card summary-card"><span class="lbl">UNREALIZED</span><span class="val mono pos">${money(p.unrealizedPnl)}</span></div>
        <div class="card summary-card"><span class="lbl">REALIZED</span><span class="val mono neg">${money(p.realizedPnl)}</span></div>
        <div class="card summary-card"><span class="lbl">EXPOSURE</span><span class="val mono">${money(p.totalExposure)}</span></div>
        <div class="card summary-card"><span class="lbl">VaR</span><span class="val mono warn">${money(p.var)}</span></div>
        <div class="card summary-card"><span class="lbl">BUYING POWER</span><span class="val mono">${money(p.buyingPower)}</span></div>
      </div>

      <div class="card">
        <div class="card-head"><span class="card-title">Current Positions</span><span class="card-sub">${D.positions.length} open</span></div>
        <div class="table-wrap"><table>
          <thead><tr><th>Ticker</th><th>Strategy</th><th class="th-r">Qty</th><th class="th-r">Entry</th><th class="th-r">Current</th><th class="th-r">Value</th><th class="th-r">P&amp;L</th><th class="th-r">Delta</th><th class="th-r">Gamma</th><th class="th-r">Vega</th></tr></thead>
          <tbody>${D.positions.map(pos => `
            <tr class="clickable" data-open="${pos.id}">
              <td><span class="ticker">${pos.ticker}</span> <span class="sym">${pos.name}</span></td>
              <td><span class="tag-strategy">${pos.strategy}</span></td>
              <td class="td-r mono">${pos.qty}</td>
              <td class="td-r mono">$${pos.entry.toFixed(2)}</td>
              <td class="td-r mono">$${pos.current.toFixed(2)}</td>
              <td class="td-r mono">${money(pos.notional)}</td>
              <td class="td-r"><span class="pnl ${pos.pnl >= 0 ? 'pos' : 'neg'}">${money(pos.pnl)}</span> <span class="faint">(${pct(pos.pnlPct)})</span></td>
              <td class="td-r mono">${pos.delta.toFixed(2)}</td>
              <td class="td-r mono">${pos.gamma.toFixed(2)}</td>
              <td class="td-r mono">${pos.vega.toFixed(2)}</td>
            </tr>`).join('')}</tbody>
        </table></div>
      </div>`;
  }

  function renderRisk() {
    const r = D.risk;
    main.innerHTML = `
      <div class="view-head"><div><div class="view-title">Risk Engine</div><div class="view-desc">Hard validation layer — AI cannot bypass limits</div></div></div>

      <div class="card" style="margin-bottom:14px">
        <div class="card-head"><span class="card-title">Validation Pipeline</span></div>
        <div class="pipeline">
          <span class="pipe-node done">Signal Generated</span><span class="pipe-arrow">→</span>
          <span class="pipe-node done">AI Analysis</span><span class="pipe-arrow">→</span>
          <span class="pipe-node ok">Risk Validation</span><span class="pipe-arrow">→</span>
          <span class="pipe-node warn">Approved / Rejected / Review</span><span class="pipe-arrow">→</span>
          <span class="pipe-node">Execution</span>
        </div>
      </div>

      <div class="risk-metrics" style="margin-bottom:14px">
        ${r.limits.map(l => `
          <div class="risk-metric">
            <div class="lbl">${l.label}</div>
            <div class="val">${l.current}</div>
            <div class="lim">limit <span>${l.value}</span></div>
            ${meter(l.pct, l.pct > 80 ? 'red' : l.pct > 60 ? 'amber' : 'green')}
          </div>`).join('')}
      </div>

      <div class="card">
        <div class="card-head"><span class="card-title">Risk Enforcements</span><span class="card-sub">recent decisions</span></div>
        <div class="table-wrap"><table>
          <thead><tr><th>Time</th><th>Action</th><th>Result</th><th>Reason</th></tr></thead>
          <tbody>
            <tr><td class="mono faint">09:38</td><td>NVDA position</td><td><span class="badge danger">REJECTED</span></td><td>Concentration risk exceeds 25%</td></tr>
            <tr><td class="mono faint">09:35</td><td>TSLA Put x6</td><td><span class="badge ok">APPROVED</span></td><td>Within exposure &amp; delta limits</td></tr>
            <tr><td class="mono faint">09:31</td><td>AMD Call x10</td><td><span class="badge ok">APPROVED</span></td><td>Liquidity sufficient</td></tr>
            <tr><td class="mono faint">09:27</td><td>SMCI Straddle</td><td><span class="badge warn">MANUAL</span></td><td>High vega — human review</td></tr>
          </tbody>
        </table></div>
      </div>`;
  }

  function renderManual() {
    const pending = reviewQueue.filter(q => q.status === 'PENDING').length;
    const approved = reviewQueue.filter(q => q.status === 'APPROVED').length;
    const rejected = reviewQueue.filter(q => q.status === 'REJECTED').length;
    const analyzing = reviewQueue.filter(q => q.status === 'IN ANALYSIS').length;

    main.innerHTML = `
      <div class="view-head">
        <div><div class="view-title">Manual Review</div><div class="view-desc">Decisions the algorithm &amp; AI lack confidence to make automatically</div></div>
        <div class="view-actions"><button class="btn" data-action="activity">View Decision Log</button></div>
      </div>

      <div class="grid summary-grid" style="margin-bottom:14px">
        <div class="card summary-card"><span class="lbl">PENDING</span><span class="val mono warn">${pending}</span></div>
        <div class="card summary-card"><span class="lbl">APPROVED</span><span class="val mono pos">${approved}</span></div>
        <div class="card summary-card"><span class="lbl">REJECTED</span><span class="val mono neg">${rejected}</span></div>
        <div class="card summary-card"><span class="lbl">IN ANALYSIS</span><span class="val mono accent">${analyzing}</span></div>
        <div class="card summary-card"><span class="lbl">QUEUE SIZE</span><span class="val mono">${reviewQueue.length}</span></div>
      </div>

      <div class="review-list">
        ${reviewQueue.map(q => {
          const statusBadge = q.status === 'APPROVED' ? '<span class="badge ok">APPROVED</span>'
            : q.status === 'REJECTED' ? '<span class="badge danger">REJECTED</span>'
            : q.status === 'IN ANALYSIS' ? '<span class="badge info">IN ANALYSIS</span>'
            : '<span class="badge warn">PENDING</span>';
          const isClosed = q.status === 'APPROVED' || q.status === 'REJECTED';
          const showActions = q.status === 'PENDING';
          const note = q.status === 'IN ANALYSIS' ? 'Additional analysis in progress...'
            : q.status === 'APPROVED' ? 'Approved — paper trade queued'
            : q.status === 'REJECTED' ? 'Rejected — logged to audit trail'
            : '';
          const cls = isClosed ? 'resolved' : (q.status === 'IN ANALYSIS' ? 'analyzing' : '');
          return `
          <div class="review-item ${cls}">
            <div class="review-item-head">
              <span class="ticker" style="font-size:15px">${q.ticker}</span>
              <span class="faint">${q.name}</span>
              <span class="mono faint">${q.id}</span>
              ${statusBadge}
              <span class="mono faint" style="margin-left:auto">${q.time}</span>
            </div>
            <div class="review-grid">
              <div class="review-field"><div class="lbl">Market Situation</div><div class="txt">${esc(q.situation)}</div></div>
              <div class="review-field"><div class="lbl">Available Data</div><div class="txt mono">${esc(q.availableData)}</div></div>
              <div class="review-field"><div class="lbl">AI Uncertainty</div><div class="txt">${esc(q.uncertainty)}</div></div>
              <div class="review-field"><div class="lbl">Risk Analysis</div><div class="txt">${esc(q.risk)}</div></div>
            </div>
            <div class="review-field" style="margin-bottom:10px">
              <div class="lbl">Potential Strategies</div>
              <div class="txt">${q.strategies.map(s => '<span class="tag-strategy">' + esc(s) + '</span>').join(' ')}</div>
            </div>
            ${note ? '<div class="faint" style="font-size:11px">' + note + '</div>' : ''}
            ${showActions ? `<div class="review-actions">
              <button class="btn small primary" data-review-action="approve" data-review-id="${q.id}">Approve</button>
              <button class="btn small danger" data-review-action="reject" data-review-id="${q.id}">Reject</button>
              <button class="btn small" data-review-action="modify" data-review-id="${q.id}">Modify</button>
              <button class="btn small ai" data-review-action="analyze" data-review-id="${q.id}">Request Analysis</button>
            </div>` : ''}
          </div>`;
        }).join('')}
      </div>`;
  }

  function renderPerformance() {
    const m = D.perf;
    main.innerHTML = `
      <div class="view-head"><div><div class="view-title">Performance Analytics</div><div class="view-desc">Risk-adjusted returns &amp; attribution</div></div></div>

      <div class="grid" style="grid-template-columns:1fr 1fr;margin-bottom:14px">
        <div class="card"><div class="card-head"><span class="card-title">Equity Curve</span></div><div class="chart" id="ch-equity"></div></div>
        <div class="card"><div class="card-head"><span class="card-title">Daily P&amp;L</span></div><div class="chart" id="ch-daily"></div></div>
      </div>

      <div class="grid" style="grid-template-columns:repeat(8,1fr);margin-bottom:14px">
        <div class="card summary-card"><span class="lbl">SHARPE</span><span class="val mono">${m.metrics.sharpe.toFixed(2)}</span></div>
        <div class="card summary-card"><span class="lbl">SORTINO</span><span class="val mono">${m.metrics.sortino.toFixed(2)}</span></div>
        <div class="card summary-card"><span class="lbl">MAX DD</span><span class="val mono neg">${m.metrics.maxDrawdown}%</span></div>
        <div class="card summary-card"><span class="lbl">WIN RATE</span><span class="val mono pos">${m.metrics.winRate}%</span></div>
        <div class="card summary-card"><span class="lbl">PROFIT FACTOR</span><span class="val mono">${m.metrics.profitFactor.toFixed(2)}</span></div>
        <div class="card summary-card"><span class="lbl">AVG WIN</span><span class="val mono pos">${money(m.metrics.avgWinner)}</span></div>
        <div class="card summary-card"><span class="lbl">AVG LOSS</span><span class="val mono neg">${money(m.metrics.avgLoser)}</span></div>
        <div class="card summary-card"><span class="lbl">EXPECTANCY</span><span class="val mono pos">${money(m.metrics.expectancy)}</span></div>
      </div>

      <div class="grid" style="grid-template-columns:1fr 1fr 1fr">
        <div class="card"><div class="card-head"><span class="card-title">P&amp;L by Strategy</span></div><div id="ch-strategy"></div></div>
        <div class="card"><div class="card-head"><span class="card-title">P&amp;L by Sector</span></div><div id="ch-sector"></div></div>
        <div class="card"><div class="card-head"><span class="card-title">Performance vs Benchmark</span></div><div class="chart" id="ch-bench"></div></div>
      </div>`;

    C.line($('#ch-equity'), m.equityCurve, { area: true });
    C.line($('#ch-daily'), m.dailyPnl, { color: '#37c7b8' });
    C.hbar($('#ch-strategy'), m.byStrategy);
    C.hbar($('#ch-sector'), m.bySector);
    renderBenchmark($('#ch-bench'), m.equityCurve, m.benchmark);
  }

  function renderBenchmark(container, eq, bench) {
    container.innerHTML = '';
    const W = 500, H = 260, pad = { l: 44, r: 12, t: 14, b: 22 };
    const all = eq.concat(bench);
    const lo = Math.min(...all), hi = Math.max(...all), range = hi - lo || 1;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('preserveAspectRatio', 'none');
    container.appendChild(svg);
    const mk = (n, a, p) => { const e = document.createElementNS('http://www.w3.org/2000/svg', n); for (const k in a) e.setAttribute(k, a[k]); (p || svg).appendChild(e); return e; };
    const x = i => pad.l + i / (eq.length - 1) * (W - pad.l - pad.r);
    const y = v => pad.t + (hi - v) / range * (H - pad.t - pad.b);
    for (let g = 0; g <= 4; g++) { const v = lo + range * g / 4; mk('line', { x1: pad.l, y1: y(v), x2: W - pad.r, y2: y(v), stroke: '#1f2733' }); }
    const mkPath = (data, color) => { const pts = data.map((v, i) => x(i) + ',' + y(v)).join(' '); mk('polyline', { points: pts, fill: 'none', stroke: color, 'stroke-width': 1.8 }); };
    mkPath(bench, '#5c6a7c');
    mkPath(eq, '#4c8dff');
    const legend = document.createElement('div');
    legend.className = 'legend';
    legend.innerHTML = '<span><span class="sw" style="background:#4c8dff"></span>Portfolio</span><span><span class="sw" style="background:#5c6a7c"></span>Benchmark</span>';
    container.appendChild(legend);
  }

  // ============================================================
  //  CANDIDATE DETAIL MODAL
  // ============================================================

  function openDetail(id) {
    const c = activeCandidates.find(x => x.id === id);
    if (!c) return;
    const t = thesisFor(c);
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <span class="ticker" style="font-size:17px">${c.ticker}</span>
          <span class="faint">${c.name} · ${c.sector}</span>
          <span class="mono" style="margin-left:8px">$${c.price.toFixed(2)}</span>
          <span class="mono ${c.changePct >= 0 ? 'pos' : 'neg'}">${pct(c.changePct)}</span>
          <button class="modal-close" data-close>✕</button>
        </div>
        <div class="modal-body">
          <div class="card-head"><span class="card-title">Price Chart</span></div>
          <div class="chart" id="m-chart" style="margin-bottom:16px"></div>

          <div class="kv">
            <div class="kv-item"><div class="lbl">Momentum</div><div class="val">${c.momentumScore}</div></div>
            <div class="kv-item"><div class="lbl">Volume</div><div class="val">${C.fmt(c.volume)}</div></div>
            <div class="kv-item"><div class="lbl">Vol Ratio</div><div class="val">${c.volumeRatio}x</div></div>
            <div class="kv-item"><div class="lbl">Volatility</div><div class="val">${(c.volatility * 100).toFixed(0)}%</div></div>
            <div class="kv-item"><div class="lbl">IV</div><div class="val">${(c.impliedVolatility * 100).toFixed(0)}%</div></div>
            <div class="kv-item"><div class="lbl">Options Liq</div><div class="val">${c.optionsLiqScore}</div></div>
            <div class="kv-item"><div class="lbl">Risk Score</div><div class="val">${c.riskScore}</div></div>
            <div class="kv-item"><div class="lbl">Regime</div><div class="val" style="font-size:12px">${c.regime}</div></div>
          </div>

          <div class="section-gap">
            <div class="card-head"><span class="card-title">Options Chain</span></div>
            ${optionsTable(c)}
          </div>

          <div class="section-gap">
            <div class="card-head"><span class="card-title">Claude Sonnet Thesis</span> ${decisionBadge(t.decision)} <span class="faint mono">confidence ${(t.confidence * 100).toFixed(0)}%</span></div>
            <div class="thesis">
              <div class="t-title">AI REASONING</div>
              <p>${esc(t.thesis)}</p>
              <div style="margin-top:10px"><b class="ai">Supporting factors</b><ul class="factor-list">${t.factors.map(f => '<li>' + esc(f) + '</li>').join('')}</ul></div>
              <div style="margin-top:6px"><b class="warn">Risks</b><ul class="factor-list">${t.risks.map(f => '<li>' + esc(f) + '</li>').join('')}</ul></div>
              <div style="margin-top:6px"><b class="muted">Proposed strategy</b>: ${esc(t.strategy)}</div>
              <div style="margin-top:4px"><b class="muted">Invalidations</b>: ${t.invalidations.map(esc).join(' · ')}</div>
            </div>
          </div>

          <div class="view-actions" style="margin-top:16px">
            <button class="btn ai" data-action="analyze-one">◈ Analyze with AI</button>
            <button class="btn" data-action="watchlist">+ Add to Watchlist</button>
            <button class="btn primary" data-action="paper">Paper Trade</button>
          </div>
        </div>
      </div>`;
    modal.hidden = false;
    C.candlestick($('#m-chart'), c.series);
    modal.dataset.id = id;
  }

  function closeDetail() { modal.hidden = true; modal.innerHTML = ''; }


  const msgPool = {
    scan: [
      ['scan', 'ALG', 'Scanning {n} stocks across {sec} sectors...'],
      ['scan', 'ALG', 'Computing momentum & volume anomaly features...'],
      ['scan', 'ALG', 'Filtering candidates by abnormal volume...'],
      ['scan', 'ALG', 'Ranking by options liquidity and spread...'],
      ['scan', 'ALG', 'Applying risk filters (concentration, exposure)...']
    ],
    ai: [
      ['ai', 'AI', 'Claude Sonnet analyzing {n} finalist candidates...'],
      ['ai', 'AI', '{t} thesis generated — {d} ({c}% confidence)'],
      ['ai', 'AI', 'Comparing options structures for {t}...'],
      ['ai', 'AI', 'Flagging contradictory signal on {t}...']
    ],
    risk: [
      ['risk', 'RISK', 'Risk engine evaluating proposed {t} position...'],
      ['risk', 'RISK', '{t} requires manual review — high vega...'],
      ['risk', 'RISK', 'Portfolio delta re-balanced to {d}...']
    ],
    exec: [
      ['exec', 'EXEC', 'Paper trade executed: {t} {s} x{q} @ ${p}'],
      ['exec', 'EXEC', 'Entry criteria met for {t} — position opened.']
    ],
    reject: [
      ['reject', 'RISK', 'Trade rejected: {t} exceeds concentration limit...']
    ]
  };

  function pushFeed(type, tag, msg) {
    feed.push({ type, tag, msg, time: fmtTime() });
    if (feed.length > 120) feed = feed.slice(-120);
    const box = $('#feed-box');
    if (box) renderFeed();
  }

  function addFeed(type) {
    const m = D.pick(msgPool[type]);
    const c = D.pick(D.candidates);
    const msg = m[2]
      .replace('{n}', D.randInt(4000, 4900))
      .replace('{sec}', D.pick(D.SECTORS))
      .replace('{t}', c.ticker)
      .replace('{d}', D.pick(D.REGIMES))
      .replace('{c}', Math.round(c.confidence * 100))
      .replace('{s}', D.pick(D.STRATEGIES))
      .replace('{q}', D.randInt(2, 12))
      .replace('{p}', (c.price * 0.03).toFixed(2));
    pushFeed(m[0], m[1], msg);
  }

  function fmtTime() {
    return simClock.toTimeString().slice(0, 8);
  }

  function seedFeed() {
    feed = D.feedSeed.map(f => ({ type: f[0], tag: f[1], msg: f[2], time: fmtTime() }));
  }

  function tickClock() {
    simClock.setSeconds(simClock.getSeconds() + 1);
    const el = document.getElementById('session-clock');
    if (el) el.textContent = fmtTime();
  }

  function tickMarket() {
    // jitter candidate prices
    activeCandidates.forEach(c => {
      const drift = (D.rand() - 0.5) * c.price * 0.004;
      c.price = Math.max(1, +(c.price + drift).toFixed(2));
      c.changePct = +(c.changePct + (D.rand() - 0.5) * 0.15).toFixed(2);
    });
    // jitter portfolio P&L
    D.portfolio.dailyPnl += D.randInt(-120, 220);
    const el = document.getElementById('top-pnl');
    if (el) { el.textContent = (D.portfolio.dailyPnl >= 0 ? '+' : '-') + '$' + Math.abs(D.portfolio.dailyPnl).toLocaleString(); el.className = 'val mono ' + (D.portfolio.dailyPnl >= 0 ? 'pos' : 'neg'); }
  }

  // ============================================================
  //  NAVIGATION & EVENTS
  // ============================================================

  function setView(v) {
    currentView = v;
    document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === v));
    const renderers = { dashboard: renderDashboard, scanner: renderScanner, candidates: renderCandidates, activity: renderActivity, positions: renderPositions, risk: renderRisk, manual: renderManual, performance: renderPerformance };
    (renderers[v] || renderDashboard)();
  }

  function bindGlobalEvents() {
    document.querySelectorAll('.nav-item').forEach(n => n.addEventListener('click', () => setView(n.dataset.view)));

    // event delegation for main
    main.addEventListener('click', (e) => {
      const analyze = e.target.closest('[data-analyze]');
      const tab = e.target.closest('[data-tab]');
      const review = e.target.closest('[data-review-action]');
      const open = e.target.closest('[data-open]');
      const action = e.target.closest('[data-action]');
      if (analyze) { toast('Analyzing ' + analyze.dataset.analyze + ' with Claude Sonnet...'); addFeed('ai'); }
      else if (tab) { scannerTab = tab.dataset.tab; renderScanner(); }
      else if (review) { handleReview(review.dataset.reviewAction, review.dataset.reviewId); }
      else if (open) openDetail(open.dataset.open);
      else if (action) handleAction(action.dataset.action);
    });

    modal.addEventListener('click', (e) => {
      if (e.target.closest('[data-close]')) closeDetail();
      const a = e.target.closest('[data-action]');
      if (a) handleModalAction(a.dataset.action);
    });

    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDetail(); });
  }

  function handleAction(a) {
    if (a === 'candidates') setView('candidates');
    else if (a === 'analyze') { setView('activity'); addFeed('ai'); addFeed('ai'); }
    else if (a === 'scan') { runScan(); }
    else if (a === 'clear-feed') { feed = []; renderFeed(); }
    else if (a === 'activity') setView('activity');
  }

  function handleModalAction(a) {
    const id = modal.dataset.id;
    if (a === 'analyze-one') { toast('Analyzing ' + id + ' with Claude Sonnet...'); addFeed('ai'); }
    else if (a === 'watchlist') toast(id + ' added to watchlist');
    else if (a === 'paper') { toast('Paper trade queued for ' + id); addFeed('exec'); }
  }

  function handleReview(action, id) {
    const item = reviewQueue.find(q => q.id === id);
    if (!item) return;
    if (action === 'approve') {
      item.status = 'APPROVED';
      pushFeed('exec', 'ADMIN', 'Manual review: ' + item.ticker + ' approved — paper trade queued');
      toast(item.ticker + ' approved');
    } else if (action === 'reject') {
      item.status = 'REJECTED';
      pushFeed('reject', 'RISK', 'Manual review: ' + item.ticker + ' rejected — no trade');
      toast(item.ticker + ' rejected');
    } else if (action === 'modify') {
      pushFeed('risk', 'RISK', 'Manual review: ' + item.ticker + ' parameters modified — re-validation queued');
      toast(item.ticker + ' parameters modified (dummy)');
    } else if (action === 'analyze') {
      item.status = 'IN ANALYSIS';
      pushFeed('ai', 'AI', 'Claude Sonnet re-analyzing ' + item.ticker + ' (additional analysis requested)');
      toast('Additional analysis requested for ' + item.ticker);
      setTimeout(() => {
        item.status = 'PENDING';
        item.uncertainty = 'Additional analysis complete — updated risk view attached.';
        if (currentView === 'manual') renderManual();
      }, 2500);
    }
    renderManual();
  }

  function runScan() {
    toast('Market scan running...');
    const seq = ['scan', 'scan', 'scan', 'scan', 'ai', 'risk'];
    seq.forEach((t, i) => setTimeout(() => addFeed(t), i * 450));
    setTimeout(() => { toast('Scan complete — 12 finalists identified'); addFeed('exec'); }, seq.length * 450 + 200);
  }

  
  seedFeed();
  setView('dashboard');
  bindGlobalEvents();

  setInterval(tickClock, 1000);
  setInterval(tickMarket, 3000);
  setInterval(() => {
    const types = ['scan', 'ai', 'risk', 'exec', 'reject'];
    addFeed(D.pick(types));
  }, 6000);

  // expose for debugging
  window.DEV.app = { setView, openDetail };
})();
