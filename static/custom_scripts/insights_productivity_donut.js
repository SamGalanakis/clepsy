/* Productivity Donut Breakdown Chart
 * Aggregates active time by productivity level over the provided window.
 * Method matches productivity time slice logic: at any moment, productivity = max productivity among concurrently open activities.
 */
(function(){
  const DEBUG_DONUT = true; // set false to silence logs
  const dbg = (...args)=>{ if(DEBUG_DONUT) console.log('[ProductivityDonut]', ...args); };
  const PRODUCTIVITY_ORDER = [
    'very_productive',
    'productive',
    'neutral',
    'distracting',
    'very_distracting'
  ];
  const PRODUCTIVITY_MAP = {
    very_productive: 1.0,
    productive: 0.8,
    neutral: 0.6,
    distracting: 0.4,
    very_distracting: 0.2
  };

  function buildIntervals(spec, windowStart, windowEnd){
    const events = (spec.events||[]).slice().sort((a,b)=> new Date(a.event_time)-new Date(b.event_time));
    if(!events.length) return [];
    const startBound = windowStart ? new Date(windowStart).getTime() : -Infinity;
    const endBound = windowEnd ? new Date(windowEnd).getTime() : Infinity;
    const intervals = [];
    let openTime = null;
    for(const ev of events){
      if(ev.event_type==='open') {
        openTime = new Date(ev.event_time);
      } else if(ev.event_type==='close' && openTime){
        const closeTime = new Date(ev.event_time);
        const startMs = Math.max(openTime.getTime(), startBound);
        const endMs = Math.min(closeTime.getTime(), endBound);
        if(endMs > startMs) intervals.push({start: new Date(startMs), end: new Date(endMs)});
        openTime = null;
      }
    }
    // If activity still open at end of window, count it up to windowEnd
    if(openTime){
      const end = windowEnd ? new Date(windowEnd) : null;
      if(end){
        const startMs = Math.max(openTime.getTime(), startBound);
        const endMs = Math.min(end.getTime(), endBound);
        if(endMs > startMs) intervals.push({start: new Date(startMs), end: new Date(endMs)});
      }
    }
    return intervals;
  }

  function clampInterval(intv, start, end){
    const s = intv.start < start ? start : intv.start;
    const e = intv.end > end ? end : intv.end;
    if(e<=s) return null; return {start:s,end:e};
  }

  function computeDistribution(specs, windowStart, windowEnd){
    dbg('computeDistribution start', {specCount: specs.length, windowStart, windowEnd});
    // Event sweep same as time slice logic, but accumulate by productivity key of max active.
    const events = [];
    let specIdx = 0;
    for(const spec of specs){
      const prodKey = (spec.activity && (spec.activity.productivity_level || spec.activity.app_productivity)) || 'neutral';
      const prodVal = PRODUCTIVITY_MAP[prodKey] ?? 0.6;
      const rawEventsLen = (spec.events||[]).length;
  const intervals = buildIntervals(spec, windowStart, windowEnd);
      let usedIntervals = 0;
      for(const base of intervals){
        const c = clampInterval(base, windowStart, windowEnd); if(!c) continue;
        usedIntervals++;
        events.push({t:c.start, type:'open', key:prodKey, v:prodVal});
        events.push({t:c.end, type:'close', key:prodKey, v:prodVal});
      }
      dbg('spec', specIdx++, {prodKey, rawEventsLen, intervalsBuilt: intervals.length, intervalsUsed: usedIntervals});
    }
    if(!events.length){
      const emptySegs = PRODUCTIVITY_ORDER.map(k=>({ key:k, seconds:0, pct:0 }));
      dbg('no events after processing; returning zeros');
      return { segments: emptySegs, totalSeconds: 0 };
    }
    events.sort((a,b)=> a.t - b.t || (a.type==='close'?-1:1));
    const active = new Map(); // key -> count
    function currentMaxKey(){
      // Among active, choose key with highest numeric value
      let bestKey=null, bestVal=-Infinity;
      for(const [k,c] of active.entries()){
        if(c>0){
          const v = PRODUCTIVITY_MAP[k] ?? 0;
            if(v>bestVal){ bestVal=v; bestKey=k; }
        }
      }
      return bestKey;
    }
    let prevTime = null;
    const acc = new Map(); // key -> seconds
    for(const ev of events){
      if(prevTime && ev.t>prevTime){
        const activeKey = currentMaxKey();
        if(activeKey){
          const dur = (ev.t - prevTime)/1000; if(dur>0){
            acc.set(activeKey, (acc.get(activeKey)||0)+dur);
          }
        }
      }
      if(ev.type==='open') active.set(ev.key, (active.get(ev.key)||0)+1);
      else { const c=(active.get(ev.key)||0)-1; if(c>0) active.set(ev.key,c); else active.delete(ev.key); }
      prevTime = ev.t;
    }
  const list = PRODUCTIVITY_ORDER.map(k=>({ key:k, seconds: acc.get(k)||0 }));
  const total = list.reduce((s,d)=>s+d.seconds,0);
  list.forEach(d=>{ d.pct = total? d.seconds/total : 0; });
  dbg('distribution complete', {totalSeconds: total, segments: list});
  return { segments:list, totalSeconds: total };
  }

  function formatDuration(totalSeconds){
    if(!totalSeconds) return '0m';
    const h = Math.floor(totalSeconds/3600);
    const m = Math.floor((totalSeconds%3600)/60);
    if(h>0) return `${h}h${m>0? ' '+m+'m':''}`; return m+'m';
  }

  function renderDonut(ctx){
    const { container, width, height, data, theme } = ctx;
    const minSide = Math.min(width, height);
    const outerR = Math.max(40, minSide/2 - 8);
    const innerR = outerR * 0.55;
    const titleSize = 14;
    const svg = d3.select(container).append('svg')
      .attr('width','100%')
      .attr('height', height)
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio','xMidYMid meet');

    if(!data){
      svg.append('text').attr('x', width/2).attr('y', height/2)
        .attr('text-anchor','middle').attr('fill','var(--color-muted,#888)')
        .style('font-size','12px').text('No data');
      return {};
    }
  const windowStart = new Date(data.start_time || data.start_date);
  const windowEnd = new Date(data.end_time || data.end_date);
  dbg('renderDonut window', {windowStart, windowEnd});
    const specs = data.activity_specs || [];
  const dist = computeDistribution(specs, windowStart, windowEnd) || { segments: [], totalSeconds: 0 };
  const segments = (dist.segments||[]).filter(s=>s.seconds>0);
  dbg('post-compute', {filteredSegments: segments.length});
    const pie = d3.pie().value(d=>d.seconds).sort(null);
    const arcs = pie(segments);
    const g = svg.append('g').attr('transform', `translate(${width/2},${height/2 + 6})`);
    const arcGen = d3.arc().innerRadius(innerR).outerRadius(outerR).cornerRadius(4);

    function prodColor(key){
      return (theme.productivity && theme.productivity[key]) || '#999';
    }

    g.selectAll('path.slice').data(arcs).enter().append('path')
      .attr('class','slice')
      .attr('d', arcGen)
      .attr('fill', d=>prodColor(d.data.key))
      .attr('stroke','var(--color-bg,#111)')
      .attr('stroke-width',1);

    // Labels (percentage) only if slice big enough
    g.selectAll('text.slice-label').data(arcs.filter(a=>a.data.pct>0.04)).enter().append('text')
      .attr('class','slice-label')
      .attr('transform', d=>`translate(${arcGen.centroid(d)})`)
      .attr('text-anchor','middle')
      .attr('fill','#fff')
      .style('font-size','10px')
      .style('pointer-events','none')
      .text(d=> Math.round(d.data.pct*100)+'%');

    // Center text
    const center = svg.append('g').attr('transform',`translate(${width/2},${height/2 + 6})`);
    center.append('text')
      .attr('text-anchor','middle')
      .attr('y', -4)
      .attr('fill','var(--color-fg,#eee)')
      .style('font-size', titleSize+'px')
      .style('font-weight',600)
      .text('Productivity');
    center.append('text')
      .attr('text-anchor','middle')
      .attr('y', 14)
      .attr('fill','var(--color-muted,#aaa)')
      .style('font-size','11px')
      .text(formatDuration(dist.totalSeconds));

    // Legend (inline bottom)
    const legend = svg.append('g').attr('transform', `translate(12,${height-18})`);
    const legItems = PRODUCTIVITY_ORDER.filter(k=>dist.segments.some(s=>s.key===k && s.seconds>0));
    let lx=0;
    legItems.forEach(k=>{
      const group = legend.append('g').attr('transform',`translate(${lx},0)`);
      group.append('rect').attr('width',10).attr('height',10).attr('rx',2).attr('fill',prodColor(k));
      group.append('text').attr('x',14).attr('y',9).attr('fill','var(--color-fg,#ddd)')
        .style('font-size','10px').text(k.replace(/_/g,' '));
      const w = group.node().getBBox().width + 10;
      lx += w;
    });

    return { state: Object.assign({}, ctx.state, { lastRender: Date.now(), totalSeconds: dist.totalSeconds }) };
  }

  window.initInsightsProductivityDonutFromJson = function(raw){
    const el = document.getElementById('productivity_donut_chart');
    if(!el) return;
    try { if(raw) el.dataset.productivity = typeof raw==='string'? raw : JSON.stringify(raw); } catch(_){ }
    if(!el.__clepsyChart){
      el.__clepsyChart = createClepsyChart({
        containerId: 'productivity_donut_chart',
        wrapperId: 'productivity-donut-wrapper',
        datasetAttr: 'productivity',
        fullscreen: true,
        autoBandZoom: false,
        zoom: null, // no zoom; donut static
        render: renderDonut
      });
    } else {
      el.__clepsyChart();
    }
  };
})();
