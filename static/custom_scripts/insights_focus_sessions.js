/* Focus Sessions: calendar grid + session length histogram
 * Client-side extraction of focus sessions from activity specs so thresholds can be tuned live.
 */
(function(){
  const DEFAULTS = {
    minDurationMin: 20,
    prodThreshold: 0.8, // 'productive' or better (see map)
    maxSingleInterruptionSec: 120,
    maxDisruptionPct: 0.10
  };
  const PRODUCTIVITY_WEIGHTS = {
    very_productive: 1.0,
    productive: 0.8,
    neutral: 0.6,
    distracting: 0.4,
    very_distracting: 0.2
  };
  function clamp(v,min,max){ return v<min?min: v>max?max: v; }
  function parseDataset(el){ try {return JSON.parse(el.dataset.focus||'{}');} catch(_){ return null; } }
  // Build intervals per activity (open-close)
  function buildIntervals(spec, windowStart, windowEnd){
    const startMsBound = windowStart?.getTime();
    const endMsBound = windowEnd?.getTime();
    if(!Number.isFinite(startMsBound) || !Number.isFinite(endMsBound) || endMsBound <= startMsBound){
      throw new Error('Focus sessions requires valid window bounds');
    }
    const events = (spec.events||[]).slice().sort((a,b)=> new Date(a.event_time)-new Date(b.event_time));
    if(!events.length) return [];
    const startBound = startMsBound;
    const endBound = endMsBound;
    const out=[]; let open=null;
    for(const ev of events){
      if(ev.event_type==='open') {
        open=new Date(ev.event_time);
      }
      else if(ev.event_type==='close' && open){
        const close=new Date(ev.event_time);
        const startMs = Math.max(open.getTime(), startBound);
        const endMs = Math.min(close.getTime(), endBound);
        if(endMs > startMs) out.push({start:new Date(startMs), end:new Date(endMs)});
        open=null;
      }
    }
    if(open){
      const startMs = Math.max(open.getTime(), startBound);
      if(endBound > startMs) out.push({start:new Date(startMs), end:new Date(endBound)});
    }
    return out;
  }
  function extractFocusSessions(specs, windowStart, windowEnd, opts){
    const cfg = Object.assign({}, DEFAULTS, opts||{});
    const sessions=[];
    // Merge all intervals across activities treated as focused if productivity >= threshold
    // We'll treat gaps below threshold as disruptions.
    const events=[];
    for(const spec of specs){
      const level = (spec.activity && (spec.activity.productivity_level || spec.activity.app_productivity)) || 'neutral';
      const weight = PRODUCTIVITY_WEIGHTS[level] ?? 0.6;
      for(const raw of buildIntervals(spec, windowStart, windowEnd)){
        const s = raw.start < windowStart ? windowStart : raw.start;
        const e = raw.end > windowEnd ? windowEnd : raw.end;
        if(e<=s) continue;
        events.push({t:s, type:'open', w:weight});
        events.push({t:e, type:'close', w:weight});
      }
    }
    if(!events.length) return [];
    events.sort((a,b)=> a.t-b.t || (a.type==='close'?-1:1));
    const activeWeights=new Map();
    function currentMax(){ let m=0; activeWeights.forEach((c,w)=>{ if(c>0 && w>m) m=w; }); return m; }
    let segStart=null, lastTime=null; // tracking continuous segment of above/below threshold to build sessions
    let currentSession=null; // {start,end,disruptedSec,segments:[{s,e,weight}]}
    function endSession(reason){ if(!currentSession) return; currentSession.end=lastTime; const totalSec=(currentSession.end-currentSession.start)/1000; if(totalSec/60 >= cfg.minDurationMin){ const disruptionPct=currentSession.disruptedSec/Math.max(1,(totalSec)); if(disruptionPct<=cfg.maxDisruptionPct){ sessions.push({ start: currentSession.start, end: currentSession.end, durationSec: totalSec, disruptedSec: currentSession.disruptedSec, disruptionPct, segments: currentSession.segments }); } } currentSession=null; }
    for(const ev of events){
      if(lastTime && ev.t>lastTime){
        const maxw=currentMax();
        const intervalSec=(ev.t-lastTime)/1000;
        const isFocused = maxw >= cfg.prodThreshold;
        if(isFocused){
          if(!currentSession){ currentSession={ start:lastTime, end:null, disruptedSec:0, segments:[] }; }
          currentSession.segments.push({s:lastTime,e:ev.t,weight:maxw});
        } else if(currentSession){
          // treat as disruption chunk
          currentSession.disruptedSec += intervalSec;
          // if single disruption exceeds threshold OR total pct too large end session
          if(intervalSec > cfg.maxSingleInterruptionSec) { endSession('single_interruption'); }
          else if(currentSession.disruptedSec/( (ev.t-currentSession.start)/1000 ) > cfg.maxDisruptionPct){ endSession('pct'); }
        }
      }
      if(ev.type==='open') activeWeights.set(ev.w,(activeWeights.get(ev.w)||0)+1); else { const c=(activeWeights.get(ev.w)||0)-1; if(c>0) activeWeights.set(ev.w,c); else activeWeights.delete(ev.w); }
      lastTime=ev.t;
    }
    // close trailing
    if(currentSession) endSession('end');
    return sessions;
  }

  // ---------- Calendar (days x time of day) ----------
  function renderCalendar(ctx){
    const { container, width, height, data, state } = ctx;
  if(!data){ d3.select(container).append('div').text('No data'); return {}; }
    const ws=new Date(data.start_date); const we=new Date(data.end_date);
    const specs=data.activity_specs||[];
    const opts=Object.assign({}, state?.focusCfg||{}, {});
    const sessions=extractFocusSessions(specs, ws, we, opts);
    const dayCount = Math.max(1, Math.round((we - ws) / 86400000)+1);
  // Slightly larger margins to accommodate axis labels (Y rotated, X below)
  const margin={top:10,right:8,bottom:36,left:46};
    const innerW=width - margin.left - margin.right;
    const innerH=height - margin.top - margin.bottom;
    const colW=innerW/dayCount;
  const svg=d3.select(container).append('svg').attr('width','100%').attr('height',height).attr('viewBox',`0 0 ${width} ${height}`).attr('preserveAspectRatio','xMidYMid meet');
    const g=svg.append('g').attr('transform',`translate(${margin.left},${margin.top})`);
    const y=d3.scaleLinear().domain([0,24]).range([0,innerH]);
    const dayFormat = dayCount<=14? d=> (new Date(ws.getTime()+d*86400000)).getDate() : d=> (new Date(ws.getTime()+d*86400000)).getDate();
    for(let d=0; d<dayCount; d++){
      g.append('text').attr('x', d*colW + colW/2).attr('y', -4).attr('text-anchor','middle').attr('fill','var(--color-fg,#aaa)').style('font-size','10px').text(dayFormat(d));
      g.append('rect').attr('x', d*colW).attr('y',0).attr('width',colW).attr('height',innerH).attr('fill','none').attr('stroke','var(--color-border,#333)').attr('stroke-width',0.4);
    }
    // horizontal hour lines every 3h
    for(let h=0; h<=24; h+=3){ const yPos=y(h); g.append('line').attr('x1',0).attr('x2',innerW).attr('y1',yPos).attr('y2',yPos).attr('stroke','var(--color-border,#333)').attr('stroke-width',0.4); g.append('text').attr('x',-8).attr('y',yPos+3).attr('text-anchor','end').attr('fill','var(--color-fg,#777)').style('font-size','9px').text(h); }
    // Axis labels
    svg.append('text')
      .attr('x', margin.left + innerW/2)
      .attr('y', height - 6)
      .attr('text-anchor','middle')
      .attr('fill','var(--color-fg,#888)')
      .style('font-size','10px')
      .text('Day Index');
    svg.append('text')
      .attr('transform',`translate(12,${margin.top + innerH/2}) rotate(-90)`)
      .attr('text-anchor','middle')
      .attr('fill','var(--color-fg,#888)')
      .style('font-size','10px')
      .text('Hour of Day');
    function disruptionColor(pct){ if(pct<=0.03) return '#16a34a'; if(pct<=0.07) return '#4ade80'; if(pct<=0.12) return '#f59e0b'; return '#ef4444'; }
    sessions.forEach(s=>{ const dayIndex=Math.floor((s.start - ws)/86400000); if(dayIndex<0||dayIndex>=dayCount) return; const startH=s.start.getHours() + s.start.getMinutes()/60; const endH=s.end.getHours()+ s.end.getMinutes()/60; const colX = dayIndex*colW; const rectY = y(startH); const rectH = Math.max(2, y(endH)-y(startH)); g.append('rect').attr('x',colX+1).attr('y',rectY).attr('width',Math.max(2,colW-2)).attr('height',rectH).attr('rx',3).attr('fill',disruptionColor(s.disruptionPct)).attr('opacity',0.9).append('title').text(()=>{ const mins=Math.round(s.durationSec/60); return `Duration ${mins}m\nDisruption ${(s.disruptionPct*100).toFixed(1)}%`; }); });
    return { state: Object.assign({}, state, { focusCfg: opts, sessionCount: sessions.length }) };
  }

  // ---------- Histogram ----------
  function renderHistogram(ctx){
    const { container, width, height, data, state } = ctx;
    if(!data){ d3.select(container).append('div').text('No data'); return {}; }
    const ws=new Date(data.start_date); const we=new Date(data.end_date); const specs=data.activity_specs||[]; const opts=Object.assign({}, state?.focusCfg||{}); const sessions=extractFocusSessions(specs, ws, we, opts);
  // Basic stats used only for state propagation (KPI panel handles display)
  const totalFocusSec = sessions.reduce((s,x)=>s+x.durationSec,0);
    const rawBins = [
      {key:'<20m', lower:0, upper:20},
      {key:'20–40m', lower:20, upper:40},
      {key:'40–60m', lower:40, upper:60},
      {key:'60–90m', lower:60, upper:90},
      {key:'90m+', lower:90, upper: Infinity}
    ];
    const minDur = opts.minDurationMin || DEFAULTS.minDurationMin;
    // Rule: hide any bin whose lower bound is below the current minimum duration threshold
    // (example: threshold 50m -> display only bins starting at 60 (60–90m, 90m+)).
    const bins = rawBins.filter(b=> b.lower >= minDur);
    // Fallback: if all bins filtered (e.g. extremely high threshold), keep last bin.
    const finalBins = bins.length? bins : [rawBins[rawBins.length-1]];
    finalBins.forEach(b=>{ b.count = sessions.filter(d=>{ const m = d.durationSec/60; return m>=b.lower && m < b.upper; }).length; });
  const svg=d3.select(container).append('svg').attr('width','100%').attr('height',height).attr('viewBox',`0 0 ${width} ${height}`).attr('preserveAspectRatio','xMidYMid meet');
  const titleG = svg.append('g');
  titleG.append('text').attr('x',width/2).attr('y',20).attr('text-anchor','middle').attr('fill','var(--color-fg,#ddd)').style('font-size','14px').style('font-weight',600).text('Session Length Distribution');
  const margin={top:40,right:12,bottom:40,left:40}; const innerW=width-margin.left-margin.right; const innerH=height-margin.top-margin.bottom; const g=svg.append('g').attr('transform',`translate(${margin.left},${margin.top})`);
  const x=d3.scaleBand().domain(finalBins.map(b=>b.key)).range([0,innerW]).padding(0.25); const y=d3.scaleLinear().domain([0,d3.max(finalBins,b=>b.count)||1]).nice().range([innerH,0]);
  const colorScale=d3.scaleLinear().domain([0,finalBins.length-1]).range(['#4ade80','#166534']);
    g.append('g').attr('transform',`translate(0,${innerH})`).call(d3.axisBottom(x)).selectAll('text').style('font-size','10px');
    g.append('g').call(d3.axisLeft(y).ticks(4)).selectAll('text').style('font-size','10px');
  g.selectAll('rect').data(finalBins).enter().append('rect').attr('x',d=>x(d.key)).attr('y',d=>y(d.count)).attr('width',x.bandwidth()).attr('height',d=>innerH - y(d.count)).attr('fill',(d,i)=>colorScale(i)).attr('stroke','#0f172a').attr('stroke-width',0.6).append('title').text(d=>`${d.key}: ${d.count} sessions (${sessions.length? (d.count/sessions.length*100).toFixed(1):'0'}%)`);
    return { state: Object.assign({}, state, { focusCfg: opts, totalFocusSec, sessionCount: sessions.length }) };
  }

  // ---------- Stats Panel (standalone) ----------
  function renderStats(ctx){
    const { container, data, state } = ctx; if(!data){ return {}; }
    const ws=new Date(data.start_date); const we=new Date(data.end_date); const specs=data.activity_specs||[]; const opts=Object.assign({}, state?.focusCfg||{}); const sessions=extractFocusSessions(specs, ws, we, opts);
    const totalFocusSec = sessions.reduce((s,x)=>s+x.durationSec,0);
    const avgSec = sessions.length? totalFocusSec / sessions.length : 0;
    const longestSec = sessions.reduce((m,x)=> Math.max(m,x.durationSec),0);
    // Layout: simple flex boxes
  const root=d3.select(container).append('div').attr('class','flex flex-wrap gap-8 w-full sm:w-auto');
    const items=[
      {label:'Total Focus', value: formatDuration(totalFocusSec)},
      {label:'Avg Length', value: formatDuration(avgSec)},
      {label:'Longest', value: formatDuration(longestSec)},
      {label:'# Sessions', value: sessions.length+''}
    ];
    items.forEach(it=>{ const box=root.append('div').attr('class','flex flex-col'); box.append('div').attr('class','text-xs uppercase opacity-60 tracking-wide').text(it.label); box.append('div').attr('class','text-base font-semibold').text(it.value); });
    return { state: Object.assign({}, state, { focusCfg: opts, totalFocusSec, sessionCount: sessions.length }) };
  }

  function formatDuration(sec){ if(!sec) return '0m'; const m=Math.round(sec/60); if(m<60) return m+'m'; const h=Math.floor(m/60); const rm=m%60; return h+'h'+(rm? ' '+rm+'m':''); }

  // Settings (shared) - attach to calendar chart for now
  // (legacy buildSettingsPanel removed; using shared HTML controls instead)
  // Shared HTML-driven settings panel (outside charts). We store current config globally.
  let sharedFocusConfig = Object.assign({}, DEFAULTS);
  function readSharedConfig(){
    const minDur = parseFloat(document.getElementById('fs-min-duration')?.value)||sharedFocusConfig.minDurationMin;
    const prod = parseFloat(document.getElementById('fs-prod-threshold')?.value)||sharedFocusConfig.prodThreshold;
    const maxI = parseFloat(document.getElementById('fs-max-interruption')?.value)||sharedFocusConfig.maxSingleInterruptionSec;
    const maxD = parseFloat(document.getElementById('fs-max-disruption')?.value)||sharedFocusConfig.maxDisruptionPct;
    sharedFocusConfig={ minDurationMin:minDur, prodThreshold:prod, maxSingleInterruptionSec:maxI, maxDisruptionPct:maxD };
    return sharedFocusConfig;
  }
  function installSharedSettingsListeners(){
    const inputs=document.querySelectorAll('#focus-sessions-settings .focus-session-setting');
    inputs.forEach(inp=>{
      inp.addEventListener('change',()=>{
        readSharedConfig();
        // Rerender all three components
        ['focus_sessions_calendar_chart','focus_sessions_histogram_chart','focus_sessions_stats_panel'].forEach(id=>{ const el=document.getElementById(id); if(el && el.__clepsyChart) el.__clepsyChart.rerender(); });
      });
    });
  }
  document.addEventListener('DOMContentLoaded', installSharedSettingsListeners);

  window.initInsightsFocusSessionsCalendarFromJson = function(raw){
    const el=document.getElementById('focus_sessions_calendar_chart'); if(!el) return; try { if(raw) el.dataset.focus = typeof raw==='string'? raw: JSON.stringify(raw); } catch(_){ }
    if(!el.__clepsyChart){
      el.__clepsyChart = createClepsyChart({
        containerId:'focus_sessions_calendar_chart',
        wrapperId:'focus-sessions-calendar-wrapper',
        datasetAttr:'focus',
        fullscreen:true,
        autoBandZoom:false,
        zoom:null,
  render: (ctx)=>{ ctx.state = Object.assign({}, ctx.state, { focusCfg: readSharedConfig() }); return renderCalendar(ctx); }
      });
    } else { el.__clepsyChart(); }
  };

  window.initInsightsFocusSessionsHistogramFromJson = function(raw){
    const el=document.getElementById('focus_sessions_histogram_chart'); if(!el) return; try { if(raw) el.dataset.focus = typeof raw==='string'? raw: JSON.stringify(raw); } catch(_){ }
    if(!el.__clepsyChart){
      el.__clepsyChart = createClepsyChart({
        containerId:'focus_sessions_histogram_chart',
        wrapperId:'focus-sessions-histogram-wrapper',
        datasetAttr:'focus',
        fullscreen:true,
        autoBandZoom:false,
        zoom:null,
  render: (ctx)=>{ ctx.state = Object.assign({}, ctx.state, { focusCfg: readSharedConfig() }); return renderHistogram(ctx); }
      });
    } else { el.__clepsyChart(); }
  };

  window.initInsightsFocusSessionsStatsFromJson = function(raw){
    const el=document.getElementById('focus_sessions_stats_panel'); if(!el) return; try { if(raw) el.dataset.focus = typeof raw==='string'? raw: JSON.stringify(raw); } catch(_){ }
    if(!el.__clepsyChart){
      el.__clepsyChart = createClepsyChart({
        containerId:'focus_sessions_stats_panel',
        wrapperId:'focus-sessions-stats-wrapper',
        datasetAttr:'focus',
        fullscreen:false,
        autoBandZoom:false,
        zoom:null,
  render: (ctx)=>{ ctx.state = Object.assign({}, ctx.state, { focusCfg: readSharedConfig() }); return renderStats(ctx); },
        settings: { attachToWrapper:false }
      });
    } else { el.__clepsyChart(); }
  };
})();
