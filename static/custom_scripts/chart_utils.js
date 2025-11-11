/* ---------- Reusable chart utilities (layout, measurement, observers) ---------- */

(function () {
  const RO_POOL_KEY = '__chartROPool';
  if (!window[RO_POOL_KEY]) window[RO_POOL_KEY] = new Map();

  function getEl(elOrId) {
    if (!elOrId) return null;
    if (typeof elOrId === 'string') return document.getElementById(elOrId);
    return elOrId;
  }

  function ensureOverflowVisible(host) {
    const el = getEl(host);
    if (el) el.style.overflow = 'visible';
    return el;
  }

  function getHostSize(host, { minHeight = 320, defaultWidth = 800 } = {}) {
    const el = getEl(host);
    if (!el) return { width: defaultWidth, height: minHeight };
    const rect = el.getBoundingClientRect();
    let width = Math.floor(rect.width || 0);
    let height = Math.floor(rect.height || 0);
    if (!width) width = el.clientWidth || el.offsetWidth || defaultWidth;
    if (!height || height < 120) height = Math.max(el.clientHeight || 0, minHeight);
    return { width, height };
  }

  function installResizeObserver(host, callback, key) {
    const el = getEl(host);
    if (!el || typeof callback !== 'function' || !('ResizeObserver' in window)) return null;
    const pool = window[RO_POOL_KEY];
    const k = key || (el.id || Math.random().toString(36).slice(2));
    if (pool.has(k)) return pool.get(k);
    const ro = new ResizeObserver(() => {
      try { callback(); } catch (_) { /* no-op */ }
    });
    ro.observe(el);
    pool.set(k, ro);
    return ro;
  }

  // Measure bottom axis tick height by drawing a scratch axis and reading its bbox
  function measureBottomAxisTickHeight(host, W, H, scale, { rotateDeg = 0, textClass = '', textFill = '#999', pad = 10, marginLeft = 56, marginTop = 10 } = {}) {
    const el = getEl(host);
    if (!el || !scale) return 56; // fallback
    const tmpSvg = d3.select(el).append('svg')
      .attr('width', W)
      .attr('height', H)
      .attr('viewBox', `0 0 ${W} ${H}`)
      .style('overflow', 'visible');
    const g0 = tmpSvg.append('g').attr('transform', `translate(${marginLeft},${marginTop})`);
    const scratch = g0.append('g').attr('transform', `translate(0,0)`).call(d3.axisBottom(scale));
    const texts = scratch.selectAll('text');
    if (textClass) texts.attr('class', textClass);
    if (rotateDeg) texts.attr('transform', `rotate(${rotateDeg})`).style('text-anchor', 'end');
    if (textFill) texts.style('fill', textFill);
    let h = 56;
    try {
      const bbox = scratch.node().getBBox();
      h = Math.max(56, Math.ceil(bbox.height) + pad);
    } catch (_) { /* fallback */ }
    tmpSvg.remove();
    return h;
  }

  function supportsSmallViewportUnits() {
    try { return typeof CSS !== 'undefined' && CSS.supports && CSS.supports('height: 100svh'); } catch (_) { return false; }
  }

  // Install zoom/pan for a band scale inside a plotting group.
  // - g: a translated group at (margin.left, margin.top)
  // - x: a d3.scaleBand used for the x-axis
  // - innerW/H: plot size in the group's local coordinates
  // - onZoom: callback invoked after x.range is updated; use it to redraw bars/axis
  // Returns { zoom, reset() }
  function installBandZoom({ g, x, innerW, innerH, maxZoom = 8, onZoom }) {
    if (!g || !x || !innerW || !innerH) return { zoom: null, reset: () => {} };

    // Capture interactions only within the plotting area using an invisible overlay
    const overlay = g.append('rect')
      .attr('class', 'zoom-overlay')
      .attr('x', 0)
      .attr('y', 0)
      .attr('width', innerW)
      .attr('height', innerH)
      .style('fill', 'none')
      .style('pointer-events', 'all');

    const zoom = d3.zoom()
      .scaleExtent([1, Math.max(1, maxZoom)])
      .translateExtent([[0, 0], [innerW, innerH]])
      .extent([[0, 0], [innerW, innerH]])
      .on('zoom', (event) => {
        const newRange = [0, innerW].map(d => event.transform.applyX(d));
        x.range(newRange);
        if (typeof onZoom === 'function') onZoom(event);
      });

    overlay.call(zoom);
    overlay.on('dblclick.zoomReset', () => overlay.transition().duration(200).call(zoom.transform, d3.zoomIdentity));

    return {
      zoom,
      reset: () => overlay.call(zoom.transform, d3.zoomIdentity),
    };
  }

  // Minimal alias with a friendlier name for general use.
  // Usage: chartUtils.bandZoom({ g, x, innerW, innerH, maxZoom, onZoom })
  const bandZoom = installBandZoom;

  // Convenience: wire band zoom to update a bar selection and an x-axis selection.
  // bars can be a selection or a function returning a selection; x items are optional.
  function bandZoomBarsAxis({ g, x, innerW, innerH, maxZoom = 8, bars, xAxisSel, xAxisGen, valueAccessor }) {
    const getVal = typeof valueAccessor === 'function' ? valueAccessor : (d => (d && (d.name !== undefined ? d.name : d.key !== undefined ? d.key : d)));
    return installBandZoom({
      g, x, innerW, innerH, maxZoom,
      onZoom: () => {
        try {
          const sel = typeof bars === 'function' ? bars() : bars;
          if (sel && sel.size && sel.size() >= 0) {
            sel.attr('x', d => x(getVal(d))).attr('width', x.bandwidth());
          }
          if (xAxisSel && xAxisGen) xAxisSel.call(xAxisGen);
        } catch (_) { /* no-op */ }
      }
    });
  }

  // --- Continuous/time-scale zoom helpers ---
  function installTimeZoom({ g, x, innerW, innerH, maxZoom = 8, onZoom, attachTo = 'overlay', target = null }) {
    if (!g || !x || !innerW || !innerH) return { zoom: null, reset: () => {} };
    const x0 = x.copy();
    let overlay = null;
    if (attachTo === 'overlay') {
      overlay = g.append('rect')
        .attr('class', 'zoom-overlay')
        .attr('x', 0).attr('y', 0)
        .attr('width', innerW).attr('height', innerH)
        .style('fill', 'none').style('pointer-events', 'all');
    }

    const zoom = d3.zoom()
      .scaleExtent([1, Math.max(1, maxZoom)])
      .translateExtent([[0, 0], [innerW, innerH]])
      .extent([[0, 0], [innerW, innerH]])
      .on('zoom', (event) => {
        const zx = event.transform.rescaleX(x0);
        if (typeof onZoom === 'function') onZoom(zx, event);
      });

  const tSel = target ? d3.select(target) : (attachTo === 'overlay' ? overlay : g);
  tSel.call(zoom);
  tSel.on('dblclick.zoomReset', () => tSel.transition().duration(200).call(zoom.transform, d3.zoomIdentity));
  return { zoom, reset: () => tSel.call(zoom.transform, d3.zoomIdentity) };
  }

  function timeZoomRectsAxis({ g, x, innerW, innerH, maxZoom = 8, rects, getStart, getEnd, xAxisSel, xAxisGen, attachTo = 'overlay', target = null }) {
    return installTimeZoom({
      g, x, innerW, innerH, maxZoom, attachTo, target,
      onZoom: (zx) => {
        try {
          const sel = typeof rects === 'function' ? rects() : rects;
          if (sel && sel.size && sel.size() >= 0) {
            sel.attr('x', d => zx(getStart(d)))
               .attr('width', d => Math.max(1, zx(getEnd(d)) - zx(getStart(d))));
          }
          if (xAxisSel && xAxisGen) xAxisSel.call(xAxisGen.scale(zx));
        } catch (_) { /* no-op */ }
      }
    });
  }

  // Reusable hover-corner fullscreen button overlay inside an SVG
  // Appears only when mouse is within hoverZonePx of the chosen corner
  function addFullscreenHoverButton(svg, { W, H, wrapperId, corner = 'top-right', pad = 6, iconSize = 18, hoverZonePx = 48, boxFill = 'rgba(255,255,255,0.85)', boxStroke = '#ccc', textColor = '#666' } = {}) {
    try {
      const wrap = typeof wrapperId === 'string' ? document.getElementById(wrapperId) : wrapperId;
      if (!svg || !svg.node()) return null;

      // Position by corner
      let tx = pad, ty = pad;
      if (corner.includes('right')) tx = Math.max(pad, (W || 0) - iconSize - pad);
      if (corner.includes('bottom')) ty = Math.max(pad, (H || 0) - iconSize - pad);

      const g = svg.append('g')
        .attr('class', 'fs-hover-toggle')
        .attr('transform', `translate(${tx}, ${ty})`)
        .style('cursor', 'pointer')
        .style('user-select', 'none')
        .style('color', textColor)
        .style('opacity', 0)
        .style('transition', 'opacity 120ms ease')
        .style('pointer-events', 'none')

      g.append('rect')
        .attr('width', iconSize)
        .attr('height', iconSize)
        .attr('rx', 4)
        .attr('ry', 4)
        .attr('fill', boxFill)
        .attr('stroke', boxStroke);

      const label = g.append('text')
        .attr('x', iconSize / 2)
        .attr('y', iconSize / 2 + 1)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('font-size', 12)
        .attr('fill', 'currentColor')
        .text(document.fullscreenElement && wrap && (document.fullscreenElement === wrap || document.fullscreenElement.contains?.(wrap)) ? '🗗' : '⛶');

      function updateIcon() {
        try {
          label.text(document.fullscreenElement && wrap && (document.fullscreenElement === wrap || document.fullscreenElement.contains?.(wrap)) ? '🗗' : '⛶');
        } catch (_) {}
      }

      g.on('click', () => {
        if (!wrap) return;
        if (document.fullscreenElement === wrap) document.exitFullscreen?.();
        else wrap.requestFullscreen?.();
      });

      // Reveal when mouse is near the corner; hide otherwise
      const svgNode = svg.node();
      function onMove(e) {
        const rect = svgNode.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const nearRight = mx > rect.width - hoverZonePx;
        const nearLeft = mx < hoverZonePx;
        const nearTop = my < hoverZonePx;
        const nearBottom = my > rect.height - hoverZonePx;
        let show = false;
        if (corner === 'top-right') show = nearRight && nearTop;
        else if (corner === 'top-left') show = nearLeft && nearTop;
        else if (corner === 'bottom-right') show = nearRight && nearBottom;
        else if (corner === 'bottom-left') show = nearLeft && nearBottom;
        g.style('opacity', show ? 1 : 0).style('pointer-events', show ? 'auto' : 'none');
      }
      function onLeave() {
        g.style('opacity', 0).style('pointer-events', 'none');
      }

      svg.on('mousemove.fsHover', onMove);
      svg.on('mouseleave.fsHover', onLeave);
      ['fullscreenchange','webkitfullscreenchange','mozfullscreenchange','MSFullscreenChange']
        .forEach(evt => document.addEventListener(evt, updateIcon, { passive: true }));

      return g;
    } catch (_) {
      return null;
    }
  }

  window.chartUtils = {
    ensureOverflowVisible,
    getHostSize,
    installResizeObserver,
    measureBottomAxisTickHeight,
    supportsSmallViewportUnits,
  installBandZoom,
  bandZoom,
  bandZoomBarsAxis,
  installTimeZoom,
  timeZoomRectsAxis,
  addFullscreenHoverButton,
  };
})();
