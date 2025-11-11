// Clean implementation; previous chord logic removed.
(function() {
  function ensureStyles(){
    if (document.getElementById('tag-sankey-styles')) return;
    const css = `#tag_transition_chord_chart svg{font-family:system-ui,sans-serif;}\n#tag_transition_chord_chart .sankey-link{fill:none;stroke-opacity:.55;transition:stroke-opacity .18s;}\n#tag_transition_chord_chart .sankey-link:hover{stroke-opacity:.9;}\n#tag_transition_chord_chart .sankey-node rect{cursor:pointer;}\n#tag_transition_chord_chart .sankey-label{font-size:11px;fill:var(--color-fg,currentColor);pointer-events:none;}\n#tag_transition_chord_chart .tooltip-sankey{position:absolute;z-index:120;pointer-events:none;background:var(--popover,#1d1d1d);color:var(--popover-foreground,#fff);font-size:11px;padding:6px 8px;border-radius:6px;border:1px solid var(--border,#333);box-shadow:0 4px 14px rgba(0,0,0,.35);}\n.clepsy-chart-wrapper-fullscreen{display:flex;align-items:center;justify-content:center;}\n.clepsy-chart-wrapper-fullscreen #tag_transition_chord_chart{max-width:none!important;width:100%!important;height:100%!important;margin:0 auto;padding:12px 8px 16px;box-sizing:border-box;}`;
    document.head.insertAdjacentHTML('beforeend', `<style id="tag-sankey-styles">${css}</style>`);
  }
  function colorsForTags(tags){
    const palette=['#4F46E5','#DC2626','#059669','#D97706','#7C3AED','#2563EB','#DB2777','#0D9488','#EA580C','#9333EA'];
    return tags.map((_,i)=>palette[i%palette.length]);
  }
  function formatWindowLabel(startIso,endIso){
    if(!startIso||!endIso) return null;
    const start=new Date(startIso);
    const end=new Date(endIso);
    if(Number.isNaN(start.getTime())||Number.isNaN(end.getTime())) return null;
    const formatter=new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',year:'numeric'});
    return `${formatter.format(start)} – ${formatter.format(end)}`;
  }
  function renderPlaceholder({ container, width, height }, title, windowLabel, message, state, tagLimit){
    const svg=d3.select(container).append('svg').attr('width','100%').attr('height',height).attr('viewBox',`0 0 ${width} ${height}`);
    svg.append('text').attr('x',width/2).attr('y',16).attr('text-anchor','middle').attr('fill','currentColor').style('font-size','14px').style('font-weight',600).text(title);
    if(windowLabel){
      svg.append('text').attr('x',width/2).attr('y',32).attr('text-anchor','middle').attr('fill','var(--color-muted,#888)').style('font-size','11px').text(windowLabel);
    }
    svg.append('text').attr('x',width/2).attr('y',height/2).attr('text-anchor','middle').attr('fill','var(--color-muted,#888)').style('font-size','12px').text(message);
    return { state: Object.assign({}, state, { lastRender: Date.now(), mode:'placeholder', tagLimit }) };
  }
  function pruneZeroFlowTags(tags, matrix){
    if(!Array.isArray(tags)||!Array.isArray(matrix)) return { tags: [], matrix: [] };
    if(!tags.length||!matrix.length) return { tags: [], matrix: [] };
    const keepIdx=[];
    for(let i=0;i<tags.length;i++){
      const row = matrix[i] || [];
      const rowSum = row.reduce((acc,v)=>acc+(Number(v)||0),0);
      let colSum = 0;
      for(let j=0;j<matrix.length;j++) colSum += Number(matrix[j] && matrix[j][i]) || 0;
      if(rowSum + colSum > 0) keepIdx.push(i);
    }
    if(keepIdx.length === tags.length) return { tags, matrix };
    if(!keepIdx.length) return { tags: [], matrix: [] };
    const keptTags = keepIdx.map(i=>tags[i]);
    const keptMatrix = keepIdx.map(i=> keepIdx.map(j=> matrix[i][j] || 0));
    return { tags: keptTags, matrix: keptMatrix };
  }
  function chooseMetricKey(tags){
    if(!tags||!tags.length) return null;
    const candidateKeys=['duration','total_duration','totalDuration','seconds','count','value'];
    for(const k of candidateKeys){ if(tags.some(t=> typeof t[k]==='number')) return k; }
    return null;
  }
  function groupTopTags(tags, matrix, limit){
    if(!Array.isArray(tags)||!Array.isArray(matrix)) return { tags: tags||[], matrix: matrix||[] };
    if(limit<=0||limit>=tags.length) return { tags, matrix };
    const metricKey=chooseMetricKey(tags);
    const weight=(t)=> typeof t[metricKey]==='number'? t[metricKey] : (typeof t.count==='number'? t.count:0);
    const sortedIdx=[...tags.keys()].sort((a,b)=> weight(tags[b]) - weight(tags[a]));
    const keepIdx=new Set(sortedIdx.slice(0,limit));
    const otherIdx=sortedIdx.slice(limit);
    if(!otherIdx.length) return { tags, matrix };
    const newTags=[]; const indexMap=new Map();
    let newIndex=0;
    for(const i of sortedIdx.slice(0,limit)) { newTags.push(tags[i]); indexMap.set(i,newIndex++); }
    // Aggregate 'Other tags'
    const otherTag={ id:'other', name:'Other tags', count: otherIdx.reduce((a,i)=> a + (tags[i].count||0),0) };
    newTags.push(otherTag);
    const otherPos=newTags.length-1;
    // Build new matrix
    const size=newTags.length;
    const newMatrix=Array.from({length:size},()=>Array(size).fill(0));
    function addValue(i,j,v){ if(i===j) return; newMatrix[i][j]+=v; }
    for(let i=0;i<tags.length;i++){
      for(let j=0;j<tags.length;j++){
        const v=matrix[i]&&matrix[i][j]||0; if(!v||i===j) continue;
        const ni= keepIdx.has(i)? indexMap.get(i) : otherPos;
        const nj= keepIdx.has(j)? indexMap.get(j) : otherPos;
        addValue(ni,nj,v);
      }
    }
    return { tags:newTags, matrix:newMatrix };
  }
  function renderSankey(ctx){
    ensureStyles();
    const { container,width,height,data,state } = ctx;
  const title='Tag Transition Flow';
  const windowLabel=formatWindowLabel(data&&data.start_date, data&&data.end_date);
  const rawTags=(data&&data.tags)||[];
  const rawMatrix=(data&&data.matrix)||[];
  const maxDefault=Math.min(10, rawTags.length||10);
  let tagLimit = (state && state.tagLimit) || maxDefault;
  if(tagLimit>maxDefault) tagLimit=maxDefault;
  // Avoid pointless grouping that leaves a single tag in 'Other'
  if(rawTags.length - tagLimit === 1) tagLimit = rawTags.length; // show all instead
    const grouped=groupTopTags(rawTags, rawMatrix, tagLimit);
    let tags=grouped.tags;
    let matrix=grouped.matrix;
    ({ tags, matrix } = pruneZeroFlowTags(tags, matrix));
    if(!tags.length||!matrix.length||tags.length<3){
      return renderPlaceholder({ container,width,height }, title, windowLabel, 'Not enough tagged transitions to build flow.', state, tagLimit);
    }
    const nodes=tags.map(t=>({id:t.name, tagId:t.id, count:t.count}));
    // Build candidate links, then prune any that would introduce a cycle (d3-sankey requires a DAG).
    const candidates=[]; for(let i=0;i<matrix.length;i++){ for(let j=0;j<matrix[i].length;j++){ const v=matrix[i][j]; if(!v||i===j) continue; candidates.push({source:nodes[i].id,target:nodes[j].id,value:v,_si:i,_ti:j}); }}
    // Simple cycle detection (≤10 nodes, brute force is fine)
    const adj=new Map(); nodes.forEach(n=>adj.set(n.id,new Set()));
    function hasPath(src, dst, visited){ if(src===dst) return true; visited=visited||new Set(); if(visited.has(src)) return false; visited.add(src); for(const nxt of adj.get(src)){ if(hasPath(nxt,dst,visited)) return true; } return false; }
    const links=[];
    const participatingNodes=new Set();
    for(const L of candidates){
      // If target can already reach source, adding this edge would create a cycle -> skip.
      if(hasPath(L.target, L.source)) continue;
      links.push(L); adj.get(L.source).add(L.target);
      participatingNodes.add(L.source); participatingNodes.add(L.target);
    }
    if(!links.length || participatingNodes.size < 3){
      return renderPlaceholder({ container,width,height }, title, windowLabel, 'Not enough tagged transitions to build flow.', state, tagLimit);
    }
    const nodePadding=28;
    // Expanded height logic: allow more generous vertical space.
    // perNode can be overridden via data.sankeyPerNode; desired absolute minimum via data.desiredHeight.
    const perNode = (data && Number(data.sankeyPerNode)) || 70; // previous effective per-node was 46 (18 + padding)
    let estHeight = Math.max(height, tags.length * perNode + 60);
    if (data && Number(data.desiredHeight)) {
      estHeight = Math.max(estHeight, Number(data.desiredHeight));
    }
    const svg=d3.select(container).append('svg')
      .attr('width','100%')
      .attr('height',estHeight)
      .attr('viewBox',`0 0 ${width} ${estHeight}`)
      .attr('preserveAspectRatio','xMidYMid meet')
      .style('cursor','zoom-in');
    svg.append('text')
      .attr('x',width/2)
      .attr('y',16)
      .attr('text-anchor','middle')
      .attr('fill','currentColor')
      .style('font-size','14px')
      .style('font-weight',600)
      .text(title);
    if(windowLabel){
      svg.append('text')
        .attr('x',width/2)
        .attr('y',32)
        .attr('text-anchor','middle')
        .attr('fill','var(--color-muted,#888)')
        .style('font-size','11px')
        .text(windowLabel);
    }
    // Layer that will be zoom/panned (title stays fixed)
    const zoomLayer = svg.append('g').attr('class','sankey-zoom-layer');
    const color=d3.scaleOrdinal(tags.map(t=>t.name), colorsForTags(tags));
    if(!d3.sankey || !d3.sankeyLinkHorizontal){
      console.error('d3-sankey plugin not loaded (d3.sankey missing)');
      svg.append('text').attr('x',width/2).attr('y',estHeight/2).attr('text-anchor','middle').attr('fill','tomato').text('Sankey plugin missing');
      return { state:{ lastRender:Date.now(), mode:'sankey-error'} };
    }
  const topInset=windowLabel?48:28;
  const sankey=d3.sankey().nodeId(d=>d.id).nodeWidth(14).nodePadding(nodePadding).extent([[8,topInset],[width-8,estHeight-8]]);
  const graph=sankey({nodes:nodes.map(d=>({...d})), links:links.map(d=>({...d}))});
  const link=zoomLayer.append('g').attr('class','sankey-links').selectAll('path').data(graph.links).enter().append('path')
      .attr('class','sankey-link')
      .attr('d', d3.sankeyLinkHorizontal())
      .attr('stroke', d=>color(d.source.id))
      .attr('stroke-width', d=>Math.max(1,d.width));
  const node=zoomLayer.append('g').attr('class','sankey-nodes').selectAll('g').data(graph.nodes).enter().append('g').attr('class','sankey-node');
    node.append('rect').attr('x',d=>d.x0).attr('y',d=>d.y0).attr('width',d=>d.x1-d.x0).attr('height',d=>Math.max(1,d.y1-d.y0)).attr('fill',d=>color(d.id)).attr('opacity',0.9);
    node.append('text').attr('class','sankey-label').attr('x',d=>d.x0<width/2?d.x1+6:d.x0-6).attr('y',d=>(d.y0+d.y1)/2).attr('dy','0.35em').attr('text-anchor',d=>d.x0<width/2?'start':'end').text(d=>d.id.length>28?d.id.slice(0,27)+'…':d.id);
    const tooltip=d3.select('body').append('div').attr('class','tooltip-sankey').style('opacity',0);
    function move(e){ tooltip.style('left',(e.pageX+14)+'px').style('top',(e.pageY-24)+'px'); }
    function hide(){ tooltip.transition().duration(120).style('opacity',0).on('end',()=>tooltip.remove()); }
    node.on('mouseover',(e,d)=>{ const inflow=d.targetLinks.reduce((a,l)=>a+l.value,0); const outflow=d.sourceLinks.reduce((a,l)=>a+l.value,0); tooltip.html(`<div class='font-semibold text-xs mb-1'>${d.id}</div><div class='text-[11px]'>Total: ${d.value}</div><div class='text-[11px]'>In: ${inflow} · Out: ${outflow}</div>`).style('opacity',1); move(e); }).on('mousemove',move).on('mouseout',hide);
    link.on('mouseover',(e,d)=>{ const totalOut=d.source.sourceLinks.reduce((a,l)=>a+l.value,0); const pct= totalOut? (d.value/totalOut*100).toFixed(1):'0.0'; tooltip.html(`<div class='font-semibold text-xs mb-1'>Flow</div><div class='text-[11px]'><strong>${d.source.id}</strong> → <strong>${d.target.id}</strong></div><div class='text-[11px] mt-1'>Count: ${d.value} (${pct}%)</div>`).style('opacity',1); move(e); }).on('mousemove',move).on('mouseout',hide);
  // Generic zoom handled by wrapper (zoom-layer class used)
  return { state:Object.assign({}, state, { lastRender:Date.now(), mode:'sankey', tagLimit }) };
  }
  window.initTagTransitionChordFromJson=function(payload){
    const el=document.getElementById('tag_transition_chord_chart');
    if(!el) return; if(payload){ try{ el.dataset.tagchord=payload; }catch(_){} }
    if(!el.__clepsyChart){
      el.__clepsyChart=createClepsyChart({
        containerId:'tag_transition_chord_chart',
        wrapperId:'tag-transition-chord-wrapper',
        datasetAttr:'tagchord',
        fullscreen:true,
  render:renderSankey,
  zoom:{ enable:true, selector:'g.sankey-zoom-layer', scaleExtent:[1,6], preserve:true, pan:false },
        settings:{
          preserveOpen:true,
          buildPanel(ctx){
            const panel=document.createElement('div');
            const h=document.createElement('h4'); h.textContent='Tag Limit'; panel.appendChild(h);
            let raw={}; try{ raw=JSON.parse(ctx.container.dataset.tagchord||'{}'); }catch(_){ }
            const rawTagCount=Array.isArray(raw.tags)? raw.tags.length : 0;
            const totalTags=Number.isFinite(raw.total_tag_count)? raw.total_tag_count : rawTagCount;
            const max=Math.min(10, rawTagCount || 10);
            if(!rawTagCount){ panel.innerHTML+='<div class="text-xs opacity-70">No tags</div>'; return panel; }
            if(rawTagCount < 4){
              panel.innerHTML+='<div class="text-xs opacity-70">Not enough tags to group (need ≥4).</div>';
              return panel;
            }
            let current=(ctx.state && ctx.state.tagLimit) || max;
            if(rawTagCount - current === 1) current = rawTagCount; // normalize stored value
            const wrap=document.createElement('div'); wrap.style.display='flex'; wrap.style.flexDirection='column'; wrap.style.gap='6px';
            const valLabel=document.createElement('div'); valLabel.style.fontSize='11px';
            function labelFor(v){
              const groupedSuffix = rawTagCount > v ? ' (others grouped)' : '';
              const coverageSuffix = totalTags > rawTagCount ? ` · top ${rawTagCount} of ${totalTags} total` : '';
              return `Showing top ${v} of ${rawTagCount}${groupedSuffix}${coverageSuffix}`;
            }
            valLabel.textContent=labelFor(current);
            const slider=document.createElement('input'); slider.type='range'; slider.min='2'; slider.max=max.toString(); slider.step='1'; slider.value=current.toString(); slider.style.width='100%';
            slider.addEventListener('input',()=>{
              let v=Number(slider.value);
              if(rawTagCount - v === 1) { // skip N-1 -> jump to N (all)
                v = rawTagCount; slider.value = v.toString();
              }
              valLabel.textContent=labelFor(v);
            });
            slider.addEventListener('change',()=>{
              let v=Number(slider.value);
              if(rawTagCount - v === 1) v = rawTagCount; // enforce rule
              ctx.updateState({ tagLimit: v }); ctx.rerender();
            });
            wrap.appendChild(slider); wrap.appendChild(valLabel); panel.appendChild(wrap);
            const note=document.createElement('div'); note.style.fontSize='10px'; note.style.opacity='0.6'; note.textContent='Ranks by activity duration/count; values that would leave 1 in "Other" are skipped.'; panel.appendChild(note);
            return panel;
          }
        }
      });
    } else { el.__clepsyChart(); }
  };
})();
