/* Productivity Time Slice Chart
   Renders average productivity by selected slice (time-of-day hour, day-of-week, day-of-month)
   Depends on createClepsyChart (clepsy_chart.js) and utils/chart_utils support
*/

/**
 * Productivity Time Slice Chart
 * Uses createClepsyChart wrapper.
 * Dataset stored in data-productivity (JSON) with keys: activity_specs, start_date, end_date, current_time, view_mode
 */
(function(){
  const PRODUCTIVITY_MAP = {
    very_productive: 1.0,
    productive: 0.8,
    neutral: 0.6,
    distracting: 0.4,
    very_distracting: 0.2,
  };

  function allowedSliceTypesForViewMode(viewMode){
    switch(viewMode){
      case 'daily':
        return ['time_of_day'];
      case 'weekly':
        return ['day_of_week','time_of_day'];
      case 'monthly':
        return ['day_of_month','day_of_week','time_of_day'];
      default:
        return ['time_of_day'];
    }
  }
  function buildIntervals(spec, windowStart, windowEnd){
    const startMsBound = windowStart?.getTime();
    const endMsBound = windowEnd?.getTime();
    if(!Number.isFinite(startMsBound) || !Number.isFinite(endMsBound) || endMsBound <= startMsBound){
      throw new Error('Productivity slice requires valid window bounds');
    }
    const events = (spec.events||[]).slice().sort((a,b)=> new Date(a.event_time)-new Date(b.event_time));
    if(!events.length) return [];
    const intervals = [];
    let openTime = null;
    for(const ev of events){
      if(ev.event_type === 'open'){
        openTime = new Date(ev.event_time);
      } else if(ev.event_type === 'close' && openTime){
        const closeTime = new Date(ev.event_time);
        const startMs = Math.max(openTime.getTime(), startMsBound);
        const endMs = Math.min(closeTime.getTime(), endMsBound);
        if(endMs > startMs){
          intervals.push({start: new Date(startMs), end: new Date(endMs)});
        }
        openTime = null;
      }
    }
    if(openTime){
      const startMs = Math.max(openTime.getTime(), startMsBound);
      if(endMsBound > startMs){
        intervals.push({start: new Date(startMs), end: new Date(endMsBound)});
      }
    }
    return intervals;
  }

  function splitIntervalByBoundary(intv, boundaryFn){
    const parts = [];
    let cursor = intv.start instanceof Date ? intv.start : new Date(intv.start);
    const end = intv.end instanceof Date ? intv.end : new Date(intv.end);
    while(cursor.getTime() < end.getTime()){
      const boundary = boundaryFn(cursor);
      const boundaryDate = boundary instanceof Date ? boundary : new Date(boundary);
      const segmentEnd = boundaryDate.getTime() < end.getTime() ? boundaryDate : end;
      parts.push({ start: cursor, end: segmentEnd });
      if (segmentEnd.getTime() === cursor.getTime()) break; // safety
      cursor = segmentEnd;
    }
    return parts;
  }

  function getNextHour(d){
    const n = new Date(d.getTime());
    n.setMinutes(0,0,0);
    n.setHours(n.getHours()+1);
    return n;
  }
  function getNextDay(d){
    const n = new Date(d.getTime());
    n.setHours(0,0,0,0);
    n.setDate(n.getDate()+1);
    return n;
  }
  function getNextMonthDay(d){
    // day-of-month boundaries same as next day
    return getNextDay(d);
  }

  function bucketKey(sliceType, dt){
    if(sliceType==='time_of_day'){ return dt.getHours(); }
    if(sliceType==='day_of_week'){ return dt.getDay(); }
    if(sliceType==='day_of_month'){ return dt.getDate(); }
    return dt.getHours();
  }

  function bucketDomain(sliceType, start, end){
    if(sliceType==='time_of_day') return Array.from({length:24},(_,i)=>i);
    if(sliceType==='day_of_week') return [0,1,2,3,4,5,6];
    if(sliceType==='day_of_month'){
      const days = new Set();
      for(let d=new Date(start.getTime()); d<=end; d.setDate(d.getDate()+1)){
        days.add(d.getDate());
      }
      return Array.from(days).sort((a,b)=>a-b);
    }
    return [];
  }

  function formatLabel(sliceType, key){
    if(sliceType==='time_of_day') return key+':00';
    if(sliceType==='day_of_week') return ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][key];
    return String(key);
  }

  function computeProductivity(specs, windowStart, windowEnd, sliceType){
    // New approach: pointwise productivity = max productivity among concurrently open activities.
    // 1. Collect open/close events from all intervals.
    const events = [];
    for (const spec of specs) {
      const prodKey = (spec.activity && (spec.activity.productivity_level || spec.activity.app_productivity)) || 'neutral';
      const prodVal = PRODUCTIVITY_MAP[prodKey] ?? 0.6;
      for (const intv of buildIntervals(spec, windowStart, windowEnd)) {
        events.push({ t: intv.start, type: 'open', v: prodVal });
        events.push({ t: intv.end, type: 'close', v: prodVal });
      }
    }
    if (!events.length) {
      return bucketDomain(sliceType, windowStart, windowEnd).map(k=>({ key:k, avg:null }));
    }
    events.sort((a,b)=> a.t - b.t || (a.type==='close'? -1:1)); // close before open if same time
    const active = new Map(); // prodVal -> count
    function currentMax(){
      let m = 0; active.forEach((cnt,val)=>{ if(cnt>0 && val>m) m=val; }); return m; }
    const segments = []; // {start, end, v}
    let prevTime = null;
    for (const ev of events) {
      if (prevTime && ev.t > prevTime) {
        const v = currentMax();
        if (v>0) segments.push({ start: prevTime, end: ev.t, v });
      }
      if (ev.type === 'open') {
        active.set(ev.v, (active.get(ev.v)||0)+1);
      } else { // close
        const c = (active.get(ev.v)||0)-1; if (c>0) active.set(ev.v,c); else active.delete(ev.v);
      }
      prevTime = ev.t;
    }
    // No further segment after last event end (we don't extend beyond last close)
    const totals = new Map(); // key -> {dur, weighted}
    const boundaryFn = (d)=> (sliceType==='time_of_day'? getNextHour(d): getNextDay(d));
    for (const seg of segments) {
      // Split segment across slice boundaries
      const parts = splitIntervalByBoundary(seg, boundaryFn);
      for (const p of parts) {
        const key = bucketKey(sliceType, p.start);
        const dur = (p.end - p.start)/1000; if (dur<=0) continue;
        const entry = totals.get(key) || { dur:0, weighted:0 };
        entry.dur += dur;
        entry.weighted += seg.v * dur;
        totals.set(key, entry);
      }
    }
    const domain = bucketDomain(sliceType, windowStart, windowEnd);
    return domain.map(k=>{ const e = totals.get(k)||{dur:0,weighted:0}; return { key:k, avg: e.dur? e.weighted/e.dur : null }; });
  }

  function renderProductivitySlice(ctx){
    const { container, width, height, data, state } = ctx;
    const viewMode = (data && data.view_mode) || 'daily';
    const allowed = allowedSliceTypesForViewMode(viewMode);
    let sliceType = (state && state.sliceType) || allowed[0] || 'time_of_day';
    if(!allowed.includes(sliceType)) {
      sliceType = allowed[0];
    }
    const title = 'Average Productivity';
    const titleFontSize = 14;
    if(!data){
      const svg = d3.select(container).append('svg')
        .attr('width','100%')
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio','xMidYMid meet');
      svg.append('text')
        .attr('x', width/2)
        .attr('y', titleFontSize + 2)
        .attr('text-anchor','middle')
        .attr('fill','var(--color-fg,#ddd)')
        .style('font-size', titleFontSize + 'px')
        .style('font-weight',600)
        .text(title);
      svg.append('text')
        .attr('x', width/2)
        .attr('y', height/2)
        .attr('text-anchor','middle')
        .attr('fill','var(--color-muted,#888)')
        .style('font-size','12px')
        .text('No data');
      return { state };
    }
    const windowStart = new Date(data.start_time || data.start_date);
    const windowEnd = new Date(data.end_time || data.end_date);
    const specs = data.activity_specs || [];
    const rows = computeProductivity(specs, windowStart, windowEnd, sliceType);

  // title vars already declared above
  const titleGap = 6;
  const margin = {top:titleFontSize + titleGap + 6, right:10, bottom:30, left:40};
    const innerW = Math.max(0, width - margin.left - margin.right);
    const innerH = Math.max(0, height - margin.top - margin.bottom);

    const svgW = width;
    const svgH = height;
    const svg = d3.select(container).append('svg')
      .attr('width', '100%')
      .attr('height', svgH)
      .attr('viewBox', `0 0 ${svgW} ${svgH}`)
      .attr('preserveAspectRatio','xMidYMid meet')
      .style('overflow','hidden');
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', titleFontSize + 2)
      .attr('text-anchor','middle')
      .attr('fill','var(--color-fg,#ddd)')
      .style('font-size', titleFontSize + 'px')
      .style('font-weight',600)
      .text(title + ' (' + (sliceType==='time_of_day'?'Hour of Day': sliceType==='day_of_week'?'Day of Week':'Day of Month') + ')');

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const valid = rows.filter(r=>r.avg!==null);
    const x = d3.scaleBand().domain(rows.map(r=>r.key)).range([0, innerW]).padding(0.12);
    const y = d3.scaleLinear().domain([0,1]).range([innerH,0]).nice();

    const xAxis = g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(x).tickFormat(k=>formatLabel(sliceType,k)));
    xAxis.selectAll('text').style('font-size','10px');
    g.append('g').call(d3.axisLeft(y).ticks(5));

    const color = d3.scaleSequential(d3.interpolateRdYlGn).domain([0.2,1.0]);
    g.selectAll('rect.bar').data(valid).enter().append('rect')
      .attr('class','bar')
      .attr('x',d=>x(d.key))
      .attr('y',d=>y(d.avg))
      .attr('width',x.bandwidth())
      .attr('height',d=>innerH - y(d.avg))
      .attr('rx',3)
      .attr('fill',d=>color(d.avg));

    g.append('line')
      .attr('x1',0).attr('x2',innerW)
      .attr('y1', y(0.6)).attr('y2', y(0.6))
      .attr('stroke','var(--color-border)')
      .attr('stroke-dasharray','4,4');

    // Provide band zoom descriptor (logical horizontal zoom without stretching text)
    const maxZoom = Math.max(2, Math.min(8, Math.ceil(rows.length / 8)));
    return {
      state: Object.assign({}, state, { sliceType, lastRender: Date.now() }),
      bandZoom: {
        g,
        x,
        innerW,
        innerH,
        maxZoom,
        bars: () => g.selectAll('rect.bar'),
        xAxisSel: xAxis,
        xAxisGen: d3.axisBottom(x).tickFormat(k=>formatLabel(sliceType,k)),
        valueAccessor: d => d.key
      }
    };
  }

  window.initInsightsProductivityTimeSliceFromJson = function(raw){
    const el = document.getElementById('productivity_time_slice_chart');
    if(!el) return;
    // Ensure dataset attr correct
    try { if (raw) el.dataset.productivity = typeof raw === 'string'? raw : JSON.stringify(raw); } catch(_){ }
    if(!el.__clepsyChart){
      el.__clepsyChart = createClepsyChart({
        containerId: 'productivity_time_slice_chart',
        wrapperId: 'productivity-time-slice-wrapper',
        datasetAttr: 'productivity',
        fullscreen: true,
        autoBandZoom: true,
        render: renderProductivitySlice,
        placeholder: ({ data }) => {
          const hasEvents = Array.isArray(data?.activity_specs) && data.activity_specs.some(s => Array.isArray(s?.events) && s.events.length > 0);
          if (!data || !hasEvents) {
            return { title: 'Average Productivity', message: 'Not enough data to render.' };
          }
          return null;
        },
        settings: {
          preserveOpen: true,
          buildPanel(ctx){
            const panel = document.createElement('div');
            const label = document.createElement('h4');
            label.textContent = 'Slice';
            panel.appendChild(label);
            const select = document.createElement('select');
            select.className = 'select select-sm w-full';
            // Determine allowed slice types from current dataset's view_mode
            let payloadRaw = null, viewMode = 'daily';
            try { payloadRaw = JSON.parse(ctx.container.dataset.productivity || '{}'); viewMode = payloadRaw.view_mode || 'daily'; } catch(_){}
            const allowed = allowedSliceTypesForViewMode(viewMode);
            const labelMap = {
              time_of_day: 'Hour of Day',
              day_of_week: 'Day of Week',
              day_of_month: 'Day of Month'
            };
            const opts = allowed.map(v=>({v, l: labelMap[v]||v}));
            const current = (ctx.state && ctx.state.sliceType) || 'time_of_day';
            opts.forEach(o=>{
              const opt = document.createElement('option');
              opt.value = o.v; opt.textContent = o.l; if(o.v===current) opt.selected = true; select.appendChild(opt);
            });
            select.addEventListener('change', ()=>{
              ctx.updateState({ sliceType: select.value });
              ctx.rerender();
            });
            panel.appendChild(select);
            return panel;
          }
        }
      });
    } else {
      el.__clepsyChart();
    }
  };
})();
