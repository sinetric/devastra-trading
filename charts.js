(function (global) {
  'use strict';

  const NS = 'http://www.w3.org/2000/svg';
  const UP = '#2fb56b';
  const DOWN = '#f0524f';

  function el(name, attrs, parent) {
    const e = document.createElementNS(NS, name);
    if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  function fmt(n) {
    if (Math.abs(n) >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(Math.round(n));
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  // ---- Candlestick chart ----
  function candlestick(container, data, opts) {
    opts = opts || {};
    const W = opts.width || 1000;
    const H = opts.height || 280;
    const pad = { l: 44, r: 12, t: 12, b: 22 };
    clear(container);
    const svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none' });
    container.appendChild(svg);

    const xs = data.map(d => d.t);
    const lo = Math.min(...data.map(d => d.l));
    const hi = Math.max(...data.map(d => d.h));
    const range = hi - lo || 1;
    const iw = (W - pad.l - pad.r) / data.length;
    const bw = Math.max(2, iw * 0.6);

    const x = i => pad.l + iw * i + iw / 2;
    const y = v => pad.t + (hi - v) / range * (H - pad.t - pad.b);

    // gridlines + y labels
    for (let g = 0; g <= 4; g++) {
      const val = lo + range * g / 4;
      const gy = y(val);
      el('line', { x1: pad.l, y1: gy, x2: W - pad.r, y2: gy, stroke: '#1f2733', 'stroke-width': 1 }, svg);
      const t = el('text', { x: pad.l - 6, y: gy + 3, 'text-anchor': 'end', fill: '#5c6a7c', 'font-size': 10 }, svg);
      t.textContent = val.toFixed(1);
    }

    data.forEach((d, i) => {
      const cx = x(i);
      const up = d.c >= d.o;
      const col = up ? UP : DOWN;
      // wick
      el('line', { x1: cx, y1: y(d.h), x2: cx, y2: y(d.l), stroke: col, 'stroke-width': 1 }, svg);
      // body
      const y1 = y(d.o), y2 = y(d.c);
      el('rect', { x: cx - bw / 2, y: Math.min(y1, y2), width: bw, height: Math.max(1, Math.abs(y2 - y1)), fill: col }, svg);
    });

    // x labels
    const step = Math.ceil(data.length / 6);
    for (let i = 0; i < data.length; i += step) {
      const t = el('text', { x: x(i), y: H - 6, 'text-anchor': 'middle', fill: '#5c6a7c', 'font-size': 9 }, svg);
      t.textContent = 't' + (data[i].t + 1);
    }
  }

  // ---- Line / area chart ----
  function line(container, data, opts) {
    opts = opts || {};
    const W = opts.width || 1000;
    const H = opts.height || 260;
    const pad = { l: 44, r: 12, t: 14, b: 22 };
    clear(container);
    const svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none' });
    container.appendChild(svg);

    const lo = Math.min(...data);
    const hi = Math.max(...data);
    const range = hi - lo || 1;
    const x = i => pad.l + i / (data.length - 1) * (W - pad.l - pad.r);
    const y = v => pad.t + (hi - v) / range * (H - pad.t - pad.b);

    for (let g = 0; g <= 4; g++) {
      const val = lo + range * g / 4;
      const gy = y(val);
      el('line', { x1: pad.l, y1: gy, x2: W - pad.r, y2: gy, stroke: '#1f2733' }, svg);
      const t = el('text', { x: pad.l - 6, y: gy + 3, 'text-anchor': 'end', fill: '#5c6a7c', 'font-size': 10 }, svg);
      t.textContent = fmt(val);
    }

    const pts = data.map((v, i) => x(i) + ',' + y(v)).join(' ');

    if (opts.area) {
      const areaPath = 'M ' + x(0) + ' ' + y(lo) + ' L ' + pts.split(' ').join(' L ') + ' L ' + x(data.length - 1) + ' ' + y(lo) + ' Z';
      el('path', { d: areaPath, fill: 'rgba(76,141,255,0.10)' }, svg);
    }
    el('polyline', { points: pts, fill: 'none', stroke: opts.color || '#4c8dff', 'stroke-width': 1.8 }, svg);

    // last point dot
    const lx = x(data.length - 1), ly = y(data[data.length - 1]);
    el('circle', { cx: lx, cy: ly, r: 3, fill: opts.color || '#4c8dff' }, svg);
  }

  // ---- Bar chart (horizontal for breakdowns) ----
  function hbar(container, items) {
    clear(container);
    const max = Math.max(...items.map(i => Math.abs(i.value))) || 1;
    items.forEach(item => {
      const row = document.createElement('div');
      row.className = 'hbar-row';
      const w = Math.max(4, Math.abs(item.value) / max * 100);
      const cls = item.value >= 0 ? 'pos' : 'neg';
      row.innerHTML =
        '<div class="hbar-label"><span>' + item.label + '</span><span class="mono ' + cls + '">' + (item.value >= 0 ? '+' : '') + fmt(item.value) + '</span></div>' +
        '<div class="hbar-track"><i class="' + cls + '" style="width:' + w + '%"></i></div>';
      container.appendChild(row);
    });
  }

  // ---- Donut chart ----
  function donut(container, items) {
    clear(container);
    const total = items.reduce((s, i) => s + i.value, 0) || 1;
    const W = 200, H = 200, cx = 100, cy = 100, r = 72;
    const svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H });
    container.appendChild(svg);

    const colors = ['#4c8dff', '#37c7b8', '#8a7cf0', '#e8a13c', '#f0524f', '#2fb56b'];
    let angle = -90;
    items.forEach((item, i) => {
      const sweep = item.value / total * 360;
      const large = sweep > 180 ? 1 : 0;
      const a1 = angle * Math.PI / 180;
      const a2 = (angle + sweep) * Math.PI / 180;
      const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
      const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
      const d = 'M ' + cx + ' ' + cy + ' L ' + x1 + ' ' + y1 + ' A ' + r + ' ' + r + ' 0 ' + large + ' 1 ' + x2 + ' ' + y2 + ' Z';
      el('path', { d, fill: colors[i % colors.length], opacity: 0.85 }, svg);
      angle += sweep;
    });
    el('circle', { cx, cy, r: r - 26, fill: '#0e1218' }, svg);
    const t = el('text', { x: cx, y: cy - 2, 'text-anchor': 'middle', fill: '#e6edf3', 'font-size': 16, 'font-weight': 700 }, svg);
    t.textContent = fmt(total);
    const s = el('text', { x: cx, y: cy + 14, 'text-anchor': 'middle', fill: '#5c6a7c', 'font-size': 9 }, svg);
    s.textContent = 'TOTAL';
  }

  global.Charts = { candlestick, line, hbar, donut, fmt };
})(window);
