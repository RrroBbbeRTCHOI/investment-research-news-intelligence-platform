/* Research-only interactions. Values come exclusively from the dossier JSON. */
(() => {
  'use strict';
  const all = selector => Array.from(document.querySelectorAll(selector));
  const byId = id => document.getElementById(id);
  try { document.documentElement.dataset.theme = localStorage.getItem('research-platform-theme') || 'light'; } catch (_) {}
  byId('theme-toggle')?.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('research-platform-theme', theme); } catch (_) {}
  });
  const sections = all('[data-research-section]');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reducedMotion && typeof IntersectionObserver === 'function') {
    sections.forEach(section=>section.classList.add('reveal-pending'));
    const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{
      if (!entry.isIntersecting) return;
      entry.target.classList.remove('reveal-pending');entry.target.classList.add('reveal-visible');observer.unobserve(entry.target);
    }),{threshold:.08});
    sections.forEach(section=>observer.observe(section));
  }
  const animateNumber = node => {
    const original=node.textContent, match=original.match(/-?\d+(?:,\d{3})*(?:\.\d+)?/);
    if (!match) return;
    const target=Number(match[0].replaceAll(',','')), decimals=(match[0].split('.')[1]||'').length;
    const started=performance.now(), duration=720;
    const frame=now=>{
      const progress=Math.min(1,(now-started)/duration), eased=1-Math.pow(1-progress,3);
      const value=(target*eased).toLocaleString(undefined,{minimumFractionDigits:decimals,maximumFractionDigits:decimals});
      node.textContent=original.slice(0,match.index)+value+original.slice(match.index+match[0].length);
      if(progress<1) requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  };
  if (!reducedMotion) {
    const numbers=all('[data-countup]');
    if (typeof IntersectionObserver === 'function') {
      const numberObserver=new IntersectionObserver(entries=>entries.forEach(entry=>{
        if(entry.isIntersecting){animateNumber(entry.target);numberObserver.unobserve(entry.target);}
      }),{threshold:.35});
      numbers.forEach(node=>numberObserver.observe(node));
    } else numbers.forEach(animateNumber);
  }
  const sectionKey = section => section.dataset.sectionId || section.id;
  const activate = id => all('.research-navigation [data-section-link]').forEach(link => {
    if (link.dataset.sectionLink === id) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  const target = id => sections.find(section => sectionKey(section) === id);
  const move = (id, smooth) => {
    const section = target(id);
    if (!section) return;
    section.scrollIntoView({ behavior: smooth && !matchMedia('(prefers-reduced-motion: reduce)').matches ? 'smooth' : 'instant', block: 'start' });
    section.focus({ preventScroll: true });
    activate(id);
  };
  all('[data-section-link]').forEach(link => link.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const id = link.dataset.sectionLink;
    const url = new URL(location.href);
    url.searchParams.set('tab', id === 'sec-filings' ? 'sec-filing' : id);
    url.hash = id;
    history.pushState(null, '', url);
    const tab = document.querySelector('.company-switch input[name="tab"]');
    if (tab) tab.value = url.searchParams.get('tab');
    move(id, true);
  }));
  const initial = () => move(location.hash.slice(1) || document.body.dataset.initialSection || 'overview', false);
  addEventListener('popstate', () => move(location.hash.slice(1) || new URL(location.href).searchParams.get('tab')?.replace('sec-filing', 'sec-filings') || 'overview', false));
  requestAnimationFrame(initial);
  let queued = false;
  addEventListener('scroll', () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      const section = sections.filter(s => s.getBoundingClientRect().top <= 150).pop();
      if (section) activate(sectionKey(section));
      queued = false;
    });
  }, { passive: true });
  const tabs = all('#financials .segmented [data-statement-target]');
  const selectMode = button => {
    tabs.forEach(tab => { const selected = tab === button; tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1; });
    all('#financials > .statement-panel').forEach(panel => { panel.hidden = panel.dataset.statementPanel !== button.dataset.statementTarget; });
  };
  tabs.forEach((button, index) => {
    button.addEventListener('click', () => selectMode(button));
    button.addEventListener('keydown', event => {
      if (!['ArrowRight','ArrowLeft','Home','End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length;
      selectMode(tabs[next]); tabs[next].focus();
    });
  });
  if (tabs[0]) selectMode(tabs[0]);
  let payload;
  try { payload = JSON.parse(byId('research-chart-data')?.textContent || '{}'); } catch (_) { return; }
  for (const mode of payload.financials || []) {
    const rows=all('[data-statement-panel="'+mode.key+'"] .compact-table tbody tr');
    rows.forEach((row,index)=>row.lastElementChild?.classList.add(mode.rows[index]?.direction || 'neutral'));
  }
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const svgNode = (tag, attrs = {}, text = '') => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key,value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    node.textContent = text; return node;
  };
  const colors = ['var(--accent)', 'var(--chart2)', 'var(--chart3)'];
  const compact = n => {
    for (const [scale, suffix] of [[1e12,'T'],[1e9,'B'],[1e6,'M']]) if (Math.abs(n) >= scale) return (n/scale).toFixed(1) + suffix;
    return n.toFixed(1);
  };
  const chart = (root, series, bars = false, percent = false) => {
    if (!root) return;
    root.replaceChildren();
    const points = series.flatMap(s => s.points).filter(p => finite(p.value));
    if (!points.length) { root.textContent = 'Data temporarily unavailable. No values inferred.'; root.classList.add('unavailable'); return; }
    root.classList.remove('unavailable');
    const labels = [...new Set(series.flatMap(s => s.points.map(p => p.period)))].sort();
    const width = bars ? 440 : Math.max(320, root.clientWidth || 900), height = bars ? 290 : 280, left = 56, right = width-16, top = 18, bottom = height-32;
    const low = Math.min(0, ...points.map(p => p.value)), high = Math.max(0,...points.map(p => p.value));
    const span = high - low || 1;
    const x = index => left + (right-left) * (index + (bars ? .5 : 0)) / Math.max(1,labels.length - (bars ? 0 : 1));
    const y = value => bottom - (value-low) / span * (bottom-top);
    const svg = svgNode('svg', {viewBox: '0 0 ' + width + ' ' + height, 'aria-hidden':'true'});
    for (let i=0;i<=4;i++) {
      const value=low+span*i/4, yy=y(value);
      svg.append(svgNode('line',{x1:left,x2:right,y1:yy,y2:yy,class:'chart-grid'}), svgNode('text',{x:left-9,y:yy+3,'text-anchor':'end',class:'chart-label'}, percent ? (value*100).toFixed(0)+'%' : compact(value)));
    }
    const labelIndexes = new Set(labels.length <= 8 ? labels.map((_label,index)=>index) : [0,Math.floor((labels.length-1)/2),labels.length-1]);
    labels.forEach((label,i) => { if (bars || labelIndexes.has(i)) svg.append(svgNode('text',{x:x(i),y:height-9,'text-anchor':'middle',class:'chart-label'}, String(label).slice(0,10))); });
    const hoverSeries=[];
    series.forEach((s,si) => {
      if (bars) {
        const unit=(right-left)/Math.max(1,labels.length), bw=Math.min(24,unit/(series.length+1));
        s.points.filter(p=>finite(p.value)).forEach(p => {
          const index=labels.indexOf(p.period);
          const color=s.color || colors[si%3];
          const rect=svgNode('rect',{x:x(index)+(si-series.length/2)*bw,y:Math.min(y(p.value),y(0)),width:bw-2,height:Math.max(1,Math.abs(y(p.value)-y(0))),fill:color,rx:2,tabindex:0,class:'chart-bar'});
          rect.append(svgNode('title',{},s.label+' · '+p.period+': '+p.value.toLocaleString()));
          const highlight = active => root.closest('.statement-panel')?.querySelectorAll('[data-period]').forEach(cell => {
            if (active && cell.dataset.period === String(p.period)) cell.setAttribute('data-highlight','');
            else cell.removeAttribute('data-highlight');
          });
          rect.addEventListener('mouseenter',()=>highlight(true));rect.addEventListener('mouseleave',()=>highlight(false));
          rect.addEventListener('focus',()=>highlight(true));rect.addEventListener('blur',()=>highlight(false));
          svg.append(rect);
        });
      } else {
        let path='',open=false;
        s.points.forEach(p=>{
          if (!finite(p.value)) { open=false; return; }
          path+=(open?' L':' M')+x(labels.indexOf(p.period)).toFixed(2)+' '+y(p.value).toFixed(2);open=true;
        });
        const color=s.color || colors[si%3];
        svg.append(svgNode('path',{d:path,fill:'none',stroke:color,'stroke-width':2.2,class:'chart-series','pathLength':1}));
        hoverSeries.push({series:s,color});
        if (s.points.length <= 20) s.points.filter(p=>finite(p.value)).forEach(p=>{
          const dot=svgNode('circle',{cx:x(labels.indexOf(p.period)),cy:y(p.value),r:3,fill:color,class:'chart-dot'});
          dot.append(svgNode('title',{},s.label+' · '+p.period+': '+(percent ? (p.value*100).toFixed(2)+'%' : p.value)));
          svg.append(dot);
        });
      }
    });
    if (!bars && hoverSeries.length) {
      const guide=svgNode('line',{x1:left,x2:left,y1:top,y2:bottom,class:'chart-guide',visibility:'hidden'});
      const highlights=hoverSeries.map((item,si)=>{
        const node=svgNode('circle',{cx:left,cy:top,r:4.5,fill:item.color,class:'chart-highlight',visibility:'hidden'});
        svg.append(node); return node;
      });
      const hit=svgNode('rect',{x:left,y:top,width:right-left,height:bottom-top,fill:'transparent',tabindex:0,'aria-label':'Explore exact chart values'});
      svg.append(guide,hit);
      const tooltip=document.createElement('div'); tooltip.className='chart-tooltip'; tooltip.hidden=true;
      const showAt=index=>{
        index=Math.max(0,Math.min(labels.length-1,index)); const label=labels[index],xx=x(index);
        guide.setAttribute('x1',xx);guide.setAttribute('x2',xx);guide.setAttribute('visibility','visible');
        tooltip.replaceChildren();
        const heading=document.createElement('strong');heading.textContent=String(label);tooltip.append(heading);
        hoverSeries.forEach((item,si)=>{
          const point=item.series.points.find(p=>p.period===label && finite(p.value));
          if (!point) { highlights[si].setAttribute('visibility','hidden'); return; }
          highlights[si].setAttribute('cx',xx);highlights[si].setAttribute('cy',y(point.value));highlights[si].setAttribute('visibility','visible');
          const row=document.createElement('span');
          row.textContent=item.series.label+': '+(percent ? (point.value*100).toFixed(2)+'%' : point.value.toFixed(2));tooltip.append(row);
        });
        tooltip.style.left=(xx/width*100)+'%';tooltip.hidden=false;
      };
      const hide=()=>{guide.setAttribute('visibility','hidden');highlights.forEach(n=>n.setAttribute('visibility','hidden'));tooltip.hidden=true;};
      hit.addEventListener('mousemove',event=>showAt(Math.round((event.offsetX-left)/(right-left)*Math.max(1,labels.length-1))));
      hit.addEventListener('mouseleave',hide);hit.addEventListener('focus',()=>showAt(0));hit.addEventListener('blur',hide);
      hit.addEventListener('keydown',event=>{
        if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
        event.preventDefault(); const current=Number(hit.dataset.index || 0);
        const next=event.key==='Home'?0:event.key==='End'?labels.length-1:Math.max(0,Math.min(labels.length-1,current+(event.key==='ArrowRight'?1:-1)));
        hit.dataset.index=String(next);showAt(next);
      });
      root.append(svg,tooltip);
    } else root.append(svg);
    if (!reducedMotion) {
      root.classList.remove('chart-ready');
      requestAnimationFrame(()=>root.classList.add('chart-ready'));
    }
  };
  for (const mode of payload.financials || []) chart(document.querySelector('[data-chart-mode="'+mode.key+'"]'), mode.series, true);
  chart(byId('health-chart'), ['cash','debt'].map(key=>({label:key,points:payload.health?.[key]?.history || [],
    color:key==='cash'?'var(--positive)':'var(--debt)'})),true);
  const market = payload.historical?.market_relative_performance?.normalized_history || [];
  const drawMarket = () => chart(byId('relativePerformanceChart'), all('[data-benchmark]').map(button=>({
    label:button.textContent,points:market.map(row=>({period:row.date,value:button.getAttribute('aria-pressed')==='true'?row[button.dataset.benchmark]:null}))
  })));
  all('[data-benchmark]').forEach(button=>button.addEventListener('click',()=>{
    button.setAttribute('aria-pressed',String(button.getAttribute('aria-pressed')!=='true'));drawMarket();
  }));
  drawMarket();
  const drawTrend = button => {
    all('[data-trend]').forEach(other=>other.setAttribute('aria-pressed',String(other===button)));
    byId('trend-label').textContent=button.textContent;
    const key=button.dataset.trend, rows=payload.historical?.financials?.[key] || [];
    chart(byId('fundamentalTrendChart'),[{label:button.textContent,points:rows.map(row=>({period:row.year,value:row[key]}))}],false,true);
  };
  all('[data-trend]').forEach(button=>button.addEventListener('click',()=>drawTrend(button)));
  const first=document.querySelector('[data-trend]'); if(first) drawTrend(first);
  addEventListener('resize', () => {
    drawMarket();
    const selected = all('[data-trend]').find(button => button.getAttribute('aria-pressed') === 'true');
    if (selected) drawTrend(selected);
  });
})();
