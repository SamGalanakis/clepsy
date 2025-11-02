/* Reusable Clepsy chart wrapper: createClepsyChart(config)
 * Minimal factory to standardize: sizing, rerender triggers (resize, theme, fullscreen, host resize),
 * dataset parsing, fullscreen button, basic guard flags, debouncing, and state persistence.
 * No global manager; each invocation installs listeners scoped to this chart.
 */

(function() {
  function defaultTheme() {
    return (typeof getTimelineColors === 'function' && getTimelineColors()) || {
      chartBackground: 'transparent',
      grid: '#666',
      muted: '#999',
      text: '#ddd',
      productivity: {
        very_productive: '#4ade80',
        productive: '#22c55e',
        neutral: '#a3a3a3',
        distracting: '#f59e0b',
        very_distracting: '#ef4444'
      }
    };
  }

  function safeParse(json) {
    if (!json) return null;
    try { return JSON.parse(json); } catch (_) { return null; }
  }

  function getHostSize(el, opts) {
    if (window.chartUtils && typeof window.chartUtils.getHostSize === 'function') {
      return window.chartUtils.getHostSize(el, opts || {});
    }
    const rect = el.getBoundingClientRect();
    // No enforced internal min height; rely on CSS (min-height on container) to give rect.height > 0.
    // Provide a tiny safety fallback only if zero to avoid 0-height SVG edge cases.
    const fallbackH = (opts && opts.defaultHeight) || 200;
    const h = rect.height && rect.height > 0 ? rect.height : fallbackH;
    return { width: rect.width || (opts && opts.defaultWidth) || 800, height: h };
  }

  function injectSettingsStylesOnce() {
    if (document.getElementById('clepsy-chart-settings-styles')) return;
    const css = `
  .clepsy-chart-controls { position:absolute; top:6px; right:8px; display:flex; gap:10px; z-index:6; }
  .clepsy-chart-controls .clepsy-chart-btn { display:flex; align-items:center; justify-content:center; cursor:pointer; background:transparent; border:none; box-shadow:none; width:24px; height:24px; padding:2px; color: var(--panel-fg,#bbb); transition: color .12s, background-color .12s; border-radius:4px; }
  .clepsy-chart-controls .clepsy-chart-btn:hover { background: rgba(255,255,255,0.10); color: var(--panel-fg,#eee); }
  .clepsy-chart-controls .clepsy-chart-btn:active { background: rgba(255,255,255,0.18); }
  .clepsy-chart-controls .clepsy-chart-btn:focus-visible { outline:2px solid rgba(255,255,255,0.4); outline-offset:2px; }
    .clepsy-chart-settings-panel { position:absolute; top:36px; right:0; z-index:7; min-width:220px; max-width:320px; background: var(--panel-bg, rgba(30,30,34,0.95)); color: var(--panel-fg, #ddd); border:1px solid var(--border-color, #555); border-radius:8px; box-shadow:0 4px 18px -2px rgba(0,0,0,0.45); padding:10px 12px; font-size:12px; line-height:1.4; backdrop-filter:blur(6px); }
    .clepsy-chart-settings-panel h4 { margin:0 0 4px; font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; opacity:0.85; }
    .clepsy-chart-settings-close { position:absolute; top:6px; right:6px; cursor:pointer; opacity:0.65; }
    .clepsy-chart-settings-close:hover { opacity:1; }
  .clepsy-chart-controls .clepsy-chart-btn svg { width:18px; height:18px; stroke: currentColor; }
  .clepsy-chart-fs-overlay { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; background:rgba(0,0,0,0.18); backdrop-filter:blur(2px); z-index:5; opacity:0; animation:clepsyFadeIn .18s forwards; }
  .clepsy-chart-fs-overlay .clepsy-spinner { width:34px; height:34px; border:3px solid rgba(255,255,255,0.25); border-top-color:rgba(255,255,255,0.85); border-radius:50%; animation: clepsySpin .8s linear infinite; }
  @keyframes clepsySpin { to { transform: rotate(360deg);} }
  @keyframes clepsyFadeIn { to { opacity:1; } }
    `;
    const style = document.createElement('style');
    style.id = 'clepsy-chart-settings-styles';
    style.textContent = css;
    document.head.appendChild(style);
  }

  function createClepsyChart(cfg) {
    const config = Object.assign({
      containerId: null,
      wrapperId: null,
      datasetAttr: 'insights',
      fullscreen: true,
      resizeDebounceMs: 200,
      fullscreenEvents: ['fullscreenchange','webkitfullscreenchange','mozfullscreenchange','MSFullscreenChange'],
      render: null,
      parseData: null, // optional transform hook(parsedRaw) => data
      onError: null, // optional (error, container)
  settings: null, // { buildPanel: (ctx)=>HTMLElement|string, preserveOpen: true|false, icon?: (theme)=>string|HTMLElement, title?: string }
  autoBandZoom: true, // if render returns bandZoom config, apply band zoom automatically
  // Generic zoom/pan (independent of band zoom):
  // zoom: { enable:true, selector:'g.zoom-layer', scaleExtent:[0.8,8], wheel:true, pan:true, preserve:true, doubleClickReset:true }
  // Added options for auto-fit at initial render (acts as maximum zoom-out):
  //   fitToContent: true (default) => compute scale to contain target contents within svg (no enlarge if smaller)
  //   fitPadding: 12 (px padding inside container when fitting)
  //   lockMinFit: true (default) => enforce the computed fit scale as the minimum (cannot zoom out further)
  // Added axis controls:
  //   axis: 'xy' | 'x' | 'y' (default 'xy') -> which axes to scale when zooming
  //   panAxis: 'xy' | 'x' | 'y' (default follows axis) -> which axes allow panning translation
  zoom: null
    }, cfg || {});

    if (!config.containerId) throw new Error('createClepsyChart: containerId required');
    if (typeof config.render !== 'function') throw new Error('createClepsyChart: render function required');

  const container = document.getElementById(config.containerId);
    if (!container) {
      console.warn('createClepsyChart: container not found:', config.containerId);
      return () => {};
    }
  const wrapperEl = config.wrapperId ? document.getElementById(config.wrapperId) : null;
  let wasFullscreen = false;
  let enteringFullscreenRequested = false;
  let manualFullscreenHeight = null; // extra height to accommodate overflow (fullscreen only)
  let fullscreenAdjustAttempted = false; // prevent infinite adjustment loops

    // State kept in closure
    let prevState = undefined;
    let resizeTimeout = null;
    let ro = null;
    let isRendering = false;

    function loadData() {
      const raw = container.dataset[config.datasetAttr];
      const parsed = safeParse(raw);
      return config.parseData ? config.parseData(parsed) : parsed;
    }

    function removeOldSettings(container) {
      const oldBtn = container.querySelector(':scope .clepsy-chart-settings-btn');
      if (oldBtn) oldBtn.remove();
      const oldPanel = container.querySelector(':scope > .clepsy-chart-settings-panel');
      if (oldPanel) oldPanel.remove();
    }

    function ensureControlsContainer() {
      let controls = container.querySelector(':scope > .clepsy-chart-controls');
      if (!controls) {
        controls = document.createElement('div');
        controls.className = 'clepsy-chart-controls';
        const cs = window.getComputedStyle(container);
        if (cs.position === 'static') container.style.position = 'relative';
        container.appendChild(controls);
      }
      return controls;
    }

    function buildSettingsUI(theme, controlsEl) {
      if (!config.settings || typeof config.settings.buildPanel !== 'function') return;
      injectSettingsStylesOnce();
      const btn = document.createElement('div');
      btn.className = 'clepsy-chart-btn clepsy-chart-settings-btn';
      let iconHTML;
      if (config.settings.icon) {
        if (typeof config.settings.icon === 'function') iconHTML = config.settings.icon(theme);
        else iconHTML = config.settings.icon;
      }
      if (!iconHTML) {
        iconHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9.4 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09c.7 0 1.31-.4 1.51-1a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06c.46.46 1.12.61 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09c0 .7.4 1.31 1 1.51.7.28 1.36.13 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06c-.46.46-.61 1.12-.33 1.82V9c.2.6.81 1 1.51 1H21a2 2 0 0 1 0 4h-.09c-.7 0-1.31.4-1.51 1Z"/></svg>`;
      }
      btn.innerHTML = iconHTML;
      controlsEl.appendChild(btn);

      const openInitially = !!(prevState && prevState.__settingsOpen && config.settings.preserveOpen);
      let panel = null;
      function closePanel() {
        if (panel) { panel.remove(); panel = null; }
        if (!prevState) prevState = {}; prevState.__settingsOpen = false;
      }
      function openPanel() {
        if (panel) return; // already
        panel = document.createElement('div');
        panel.className = 'clepsy-chart-settings-panel';
        const content = config.settings.buildPanel({
          container,
          theme,
          state: prevState,
          updateState: (mut) => { prevState = Object.assign({}, prevState, mut); },
          rerender: debouncedRender
        });
        if (typeof content === 'string') panel.innerHTML = content; else if (content instanceof HTMLElement) panel.appendChild(content); else panel.innerHTML = '<em>No settings</em>';
        const close = document.createElement('div');
        close.className = 'clepsy-chart-settings-close';
        close.innerHTML = '&#10005;';
        close.addEventListener('click', (e) => { e.stopPropagation(); closePanel(); });
        panel.appendChild(close);
        container.appendChild(panel);
        if (!prevState) prevState = {}; prevState.__settingsOpen = true;
        if (config.settings.onOpen) { try { config.settings.onOpen(panel); } catch(_){} }
      }
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (panel) closePanel(); else openPanel();
      });
      document.addEventListener('click', (e) => {
        if (!panel) return;
        if (!container.contains(e.target)) closePanel();
      }, { capture: true, passive: true });
      if (openInitially) openPanel();
    }

    function doRender() {
          if (isRendering) return;
          isRendering = true;
          try {
            if (!isWrapperFullscreen() && !enteringFullscreenRequested && container.style.height) container.style.height='';
            // Determine size: if entering or in fullscreen, use window size fallback
            // Size purely from container (CSS governs min-height)
            let size = getHostSize(container, { defaultWidth: 800, defaultHeight: 260 });
            if (isWrapperFullscreen()) {
              const fsWidth = window.innerWidth || document.documentElement.clientWidth;
              const rawH = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0);
              const baseH = rawH; // fullscreen height from viewport
              size = { width: fsWidth, height: manualFullscreenHeight ? Math.max(baseH, manualFullscreenHeight) : baseH };
            } else if (enteringFullscreenRequested) {
              // Pre-fullscreen estimate: use physical screen dimensions to minimize jump
              const estW = (screen && screen.width) ? screen.width : (window.innerWidth || document.documentElement.clientWidth);
              const estH = (screen && screen.height) ? screen.height : (window.innerHeight || document.documentElement.clientHeight || 0);
              size = { width: estW, height: estH };
            }
            const theme = defaultTheme();
            const data = loadData();
            d3.select(container).selectAll('*').remove();
            const result = config.render({
              container,
              wrapper: wrapperEl,
              width: size.width,
              height: size.height,
              data,
              theme,
              state: prevState,
              config
            }) || {};
            prevState = result.state !== undefined ? result.state : prevState;
            // Optional band zoom handling (render can return result.bandZoom descriptor)
            if (config.autoBandZoom && result.bandZoom && window.chartUtils && typeof window.chartUtils.bandZoomBarsAxis === 'function') {
              try { window.chartUtils.bandZoomBarsAxis(result.bandZoom); } catch(err) { console.warn('Band zoom init failed', err); }
            }
            const controlsEl = ensureControlsContainer();
            if (isWrapperFullscreen() || enteringFullscreenRequested) {
              container.style.height = size.height + 'px';
              // Post-render overflow detection (especially for long / rotated axis labels)
              // Strategy: measure bottom of all SVG text nodes vs allocated height. If clipped, increase height once and re-render.
              requestAnimationFrame(() => {
                try {
                  if (!(isWrapperFullscreen() || enteringFullscreenRequested)) return;
                  if (fullscreenAdjustAttempted) return;
                  const svg = container.querySelector('svg');
                  if (!svg) return;
                  const contRect = container.getBoundingClientRect();
                  let maxBottom = 0;
                  svg.querySelectorAll('text').forEach(t => {
                    try { const r = t.getBoundingClientRect(); maxBottom = Math.max(maxBottom, r.bottom - contRect.top); } catch(_) {}
                  });
                  const allocated = size.height;
                  if (maxBottom > allocated - 2) {
                    const extra = Math.min(400, Math.round(maxBottom - allocated + 10));
                    if (extra > 6) {
                      manualFullscreenHeight = allocated + extra;
                      fullscreenAdjustAttempted = true;
                      // Trigger a single re-render with the enlarged manual height.
                      requestAnimationFrame(() => { doRender(); });
                    }
                  }
                } catch(_) {}
              });
            } else if (container.style.height) {
              container.style.height='';
            }
            controlsEl.querySelectorAll(':scope > .clepsy-chart-btn').forEach(b=>b.remove());
            if (config.fullscreen && wrapperEl) {
              const fsBtn = document.createElement('div');
              fsBtn.className='clepsy-chart-btn clepsy-chart-fs-btn';
              const updateIcon=()=>{ fsBtn.textContent = isWrapperFullscreen()? '🗗':'⛶'; };
              updateIcon();
                fsBtn.addEventListener('click',(e)=>{
                  e.stopPropagation();
                  if (isWrapperFullscreen()) {
                    document.exitFullscreen?.();
                  } else {
                    enteringFullscreenRequested = true;
                    // pre-render at fullscreen size
                    try { doRender(); } catch(_){}
                    requestAnimationFrame(()=> wrapperEl.requestFullscreen?.());
                  }
                });
              controlsEl.appendChild(fsBtn);
            }
            if (config.settings) { removeOldSettings(container); buildSettingsUI(theme, controlsEl); }
            // Generic zoom feature (runs after chart render & controls build)
            if (config.zoom && config.zoom.enable) {
              try {
                const svg = container.querySelector('svg');
                if (svg) {
                  const selector = config.zoom.selector || 'g.zoom-layer, g.sankey-zoom-layer, svg > g';
                  let target = svg.querySelector(selector);
                  if (!target) target = svg.querySelector('g');
                  if (target) {
                    const d3Svg = d3.select(svg);
                    const d3Target = d3.select(target);
        const scaleExtent = (config.zoom.scaleExtent && config.zoom.scaleExtent.length===2)? config.zoom.scaleExtent.slice() : [0.8,8];
                    const allowWheel = config.zoom.wheel !== false; // default true
                    const allowPan = config.zoom.pan !== false; // default true
        const axisMode = (config.zoom.axis === 'x' || config.zoom.axis === 'y') ? config.zoom.axis : 'xy';
        const panAxisMode = (config.zoom.panAxis === 'x' || config.zoom.panAxis === 'y' || config.zoom.panAxis === 'xy') ? config.zoom.panAxis : axisMode;
                    let stored = (prevState && prevState.__zoom && config.zoom.preserve!==false)? prevState.__zoom : null;
                    // Auto-fit computation only on first render (no stored zoom)
                    let fitTransform = null;
                    if (!stored && (config.zoom.fitToContent !== false)) {
                      try {
                        const bbox = target.getBBox();
                        const pad = (typeof config.zoom.fitPadding === 'number')? config.zoom.fitPadding : 12;
                        const svgW = svg.clientWidth || +svg.getAttribute('width') || container.clientWidth || 800;
                        const svgH = svg.clientHeight || +svg.getAttribute('height') || container.clientHeight || 400;
                        if (bbox && bbox.width > 0 && bbox.height > 0 && svgW>0 && svgH>0) {
          const scaleX = (svgW - pad*2) / bbox.width;
          const scaleY = (svgH - pad*2) / bbox.height;
          let fitScale;
          if (axisMode === 'x') fitScale = scaleX; else if (axisMode === 'y') fitScale = scaleY; else fitScale = Math.min(scaleX, scaleY);
                          if (!isFinite(fitScale) || fitScale <= 0) fitScale = 1;
                          // Do not enlarge if content already smaller than container
                          if (fitScale > 1) fitScale = 1;
                          // Center content
          const tx = (svgW - bbox.width * (axisMode==='y'?1:fitScale))/2 - bbox.x * (axisMode==='y'?1:fitScale);
          const ty = (svgH - bbox.height * (axisMode==='x'?1:fitScale))/2 - bbox.y * (axisMode==='x'?1:fitScale);
                          fitTransform = { k: fitScale, x: tx, y: ty };
                          // Adjust scaleExtent min if locking min to fit (prevents zooming further out)
                          if (config.zoom.lockMinFit !== false) {
                            if (fitScale > scaleExtent[0]) {
                              scaleExtent[0] = fitScale; // raise min to fitScale
                              if (scaleExtent[1] < scaleExtent[0]) scaleExtent[1] = scaleExtent[0] * 4; // ensure max > min
                            }
                          }
                        }
                      } catch(fErr) { /* ignore fit errors */ }
                    }
                    if (!stored) stored = fitTransform || {k:1,x:0,y:0};
                    const zoomBehavior = d3.zoom()
                      .scaleExtent(scaleExtent)
                      .filter(ev => {
                        if (ev.type === 'wheel') return allowWheel;
                        if (ev.type === 'mousedown' || ev.type==='mousemove' || ev.type==='touchstart') return allowPan;
                        return true;
                      })
                      .on('zoom', ev => {
                        // Constrain transform based on axis & panAxis settings
                        let k = ev.transform.k;
                        let xT = ev.transform.x;
                        let yT = ev.transform.y;
                        if (axisMode === 'x') {
                          // Scale only X; Y scale stays 1
                          if (panAxisMode === 'x') { yT = 0; }
                          else if (panAxisMode === 'y') { xT = 0; }
                          else { yT = 0; } // default no vertical pan for x-only scaling
                          d3Target.attr('transform', `translate(${xT},${yT}) scale(${k},1)`);
                        } else if (axisMode === 'y') {
                          if (panAxisMode === 'y') { xT = 0; }
                          else if (panAxisMode === 'x') { yT = 0; }
                          else { xT = 0; } // default no horizontal pan for y-only scaling
                          d3Target.attr('transform', `translate(${xT},${yT}) scale(1,${k})`);
                        } else { // xy
                          if (panAxisMode === 'x') yT = 0; else if (panAxisMode === 'y') xT = 0; // restrict one axis if requested
                          d3Target.attr('transform', `translate(${xT},${yT}) scale(${k})`);
                        }
                        stored = {k, x: xT, y: yT, axis: axisMode};
                        if (!prevState) prevState={}; prevState.__zoom = stored;
                      });
                    d3Svg.call(zoomBehavior);
                    // Apply existing (or computed fit) transform
                    if (stored) {
                      const t = d3.zoomIdentity.translate(stored.x||0, stored.y||0).scale(stored.k||1);
                      d3Svg.call(zoomBehavior.transform, t);
                    }
                    if (config.zoom.doubleClickReset !== false) {
                      d3Svg.on('dblclick.zoomReset', ev => {
                        ev.preventDefault();
                        const t = d3.zoomIdentity;
                        d3Svg.transition().duration(300).call(zoomBehavior.transform, t);
                      });
                    }
                    // Expose lightweight helpers on container for advanced charts (optional)
                    container.__clepsyZoom = {
                      reset: () => d3Svg.call(zoomBehavior.transform, d3.zoomIdentity),
                      get: () => stored,
                      set: (k,x,y) => {
                        const t = d3.zoomIdentity.translate(x||0,y||0).scale(k||1);
                        d3Svg.call(zoomBehavior.transform, t);
                      }
                    };
                  }
                }
              } catch(zErr) { console.warn('Generic zoom init failed', zErr); }
            }
          } catch(e) {
            console.error('Clepsy chart render error:', e);
            if (typeof config.onError==='function') { try { config.onError(e, container); } catch(_){} } else container.textContent='Chart error (see console).';
          } finally {
            isRendering=false;
            if (isWrapperFullscreen() && enteringFullscreenRequested) {
              enteringFullscreenRequested=false;
              setTimeout(()=>debouncedRender(),20);
            }
          }
    }

    function debouncedRender() {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(doRender, config.resizeDebounceMs);
    }

    // Install listeners (per chart)
    window.addEventListener('resize', debouncedRender, { passive: true });
    document.addEventListener('theme_changed', debouncedRender, { passive: true });
    function isWrapperFullscreen() {
      if (!wrapperEl) return false;
      const fsEl = document.fullscreenElement;
      if (!fsEl) return false;
      return fsEl === wrapperEl || wrapperEl.contains(fsEl);
    }
    function onFsEvent() {
      const nowFull = isWrapperFullscreen();
  if (wasFullscreen && !nowFull) {
        // Exiting fullscreen: clear current content first so container shrinks
        try { d3.select(container).selectAll('*').remove(); } catch(_){}
  // Remove explicit height so next render recomputes natural layout
  if (container.style.height) container.style.height = '';
    manualFullscreenHeight = null;
    fullscreenAdjustAttempted = false;
        // Use a short timeout to allow layout to settle before re-measuring
        setTimeout(() => { debouncedRender(); }, 30);
      } else {
        debouncedRender();
      }
      if (wrapperEl) {
        if (nowFull) wrapperEl.classList.add('clepsy-chart-wrapper-fullscreen');
        else wrapperEl.classList.remove('clepsy-chart-wrapper-fullscreen');
      }
      wasFullscreen = nowFull;
    }
    if (config.fullscreen) {
      config.fullscreenEvents.forEach(evt => document.addEventListener(evt, onFsEvent, { passive: true }));
    }
    if ('ResizeObserver' in window) {
      ro = new ResizeObserver(() => debouncedRender());
      ro.observe(container);
    }

    // Initial render
    doRender();

    // Return an API for optional external control
    function api(jsonString) {
      if (jsonString) {
        // allow explicit dataset update
        try { container.dataset[config.datasetAttr] = jsonString; } catch (_) {}
      }
      doRender();
    }
    api.rerender = doRender;
    api.getState = () => prevState;
    api.setState = (s) => { prevState = s; debouncedRender(); };
    api.destroy = () => {
      window.removeEventListener('resize', debouncedRender);
      document.removeEventListener('theme_changed', debouncedRender);
  if (config.fullscreen) config.fullscreenEvents.forEach(evt => document.removeEventListener(evt, onFsEvent));
      if (ro) try { ro.disconnect(); } catch (_) {}
    };
    return api;
  }

  // Expose globally
  window.createClepsyChart = createClepsyChart;
})();
