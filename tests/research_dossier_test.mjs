import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const source = fs.readFileSync(new URL('../static/js/research_dossier.js', import.meta.url),'utf8');

class Element {
  constructor(tag='div', data={}, text='') { this.tag=tag; this.dataset=data; this.textContent=text; this.attrs={}; this.children=[]; this.events={}; this.hidden=false; this.style={}; this.classList={add(){},remove(){}}; }
  setAttribute(k,v){this.attrs[k]=String(v);}
  getAttribute(k){return this.attrs[k]??null;}
  removeAttribute(k){delete this.attrs[k];}
  addEventListener(k,fn){this.events[k]=fn;}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=[...items];}
  focus(){this.focused=true;}
  scrollIntoView(){this.scrolled=true;}
  getBoundingClientRect(){return {top:1000};}
  closest(){return null;}
  fire(name, event={}){this.events[name]?.({preventDefault(){},...event});}
}
function setup({missing=false,hash=''}={}) {
  const ids={}, selectors={}, listeners={};
  const sections=['overview','financials','valuation','historical-trends','earnings-quality','financial-health','sec-filings','relevant-events'].map(id=>{const s=new Element();s.id=id;return s;});
  const links=sections.map(s=>new Element('a',{sectionLink:s.id}));
  selectors['[data-research-section]']=sections;
  selectors['[data-section-link]']=selectors['.research-navigation [data-section-link]']=links;
  const modes=['income','cash','balance'].map(k=>new Element('button',{statementTarget:k}));
  const panels=modes.map(b=>new Element('div',{statementPanel:b.dataset.statementTarget}));
  selectors['#financials .segmented [data-statement-target]']=modes;
  selectors['#financials > .statement-panel']=panels;
  const benchmarks=['company','market','tech'].map(k=>{const b=new Element('button',{benchmark:k},k);b.setAttribute('aria-pressed','true');return b;});
  selectors['[data-benchmark]']=benchmarks;
  const trends=['revenue_growth','eps_growth','roe','roic'].map(k=>new Element('button',{trend:k},k));
  selectors['[data-trend]']=trends;
  for(const id of ['theme-toggle','health-chart','relativePerformanceChart','fundamentalTrendChart','trend-label'])ids[id]=new Element();
  const points=missing?[]:[{period:'2024',value:100},{period:'2025',value:120}];
  const payload={financials:modes.map(b=>({key:b.dataset.statementTarget,series:[{label:'Real source',points}]})),
    historical:{market_relative_performance:{normalized_history:missing?[]:[{date:'2024',company:100,market:100,tech:100},{date:'2025',company:120,market:110,tech:115}]},
    financials:{revenue_growth:[{year:'2024',revenue_growth:.1},{year:'2025',revenue_growth:.2}],eps_growth:[{year:'2024',eps_growth:-.1},{year:'2025',eps_growth:.3}],roic:[{year:'2024',roic:.25}]}},health:{cash:{history:points},debt:{history:points}}};
  ids['research-chart-data']=new Element('script',{},JSON.stringify(payload));
  const charts={};
  for(const mode of modes) {
    const key=mode.dataset.statementTarget;charts[key]=new Element();selectors['[data-chart-mode="'+key+'"]']=[charts[key]];
  }
  const hiddenTab=new Element();selectors['.company-switch input[name="tab"]']=[hiddenTab];
  const document={documentElement:{dataset:{}},body:{dataset:{initialSection:'valuation'}},
    getElementById:id=>ids[id]||null,querySelectorAll:s=>selectors[s]||[],querySelector:s=>(selectors[s]||[])[0]||null,
    createElementNS:(_ns,tag)=>new Element(tag),createElement:tag=>new Element(tag)};
  const location={href:'http://localhost/research?ticker=NVDA&event=real-event'+hash,hash};
  const history={entries:[],pushState(_state,_title,url){this.entries.push(String(url));location.href=String(url);location.hash=url.hash;}};
  const preferences = {};
  vm.runInNewContext(source,{document,location,history,URL,localStorage:{getItem(key){assert.equal(key,'research-platform-theme');return null;},setItem(key,value){preferences[key]=value;}},
    matchMedia:()=>({matches:true}),requestAnimationFrame:fn=>fn(),addEventListener:(name,fn)=>listeners[name]=fn,console});
  return {ids,sections,links,modes,panels,benchmarks,trends,charts,history,location,listeners,document,preferences};
}
function descendants(root,tag){return root.children.flatMap(c=>[...(c.tag===tag?[c]:[]),...descendants(c,tag)]);}
test('legacy tab targets valuation while all sections remain in the document',()=>{
  const ui=setup(); assert.equal(ui.sections.length,8);assert.equal(ui.sections[2].scrolled,true);assert.equal(ui.sections[2].focused,true);
});
test('section navigation preserves ticker/event and uses history instead of reload',()=>{
  const ui=setup();ui.links[6].fire('click');
  const url=new URL(ui.history.entries[0]);assert.equal(url.searchParams.get('ticker'),'NVDA');assert.equal(url.searchParams.get('event'),'real-event');
  assert.equal(url.searchParams.get('tab'),'sec-filing');assert.equal(url.hash,'#sec-filings');
  assert.equal(ui.sections[6].focused,true);assert.equal(ui.links[6].getAttribute('aria-current'),'location');
});
test('three modes switch real panels and support arrow-key navigation',()=>{
  const ui=setup();ui.modes[1].fire('click');assert.deepEqual(ui.panels.map(p=>p.hidden),[true,false,true]);
  ui.modes[1].fire('keydown',{key:'ArrowRight'});assert.deepEqual(ui.panels.map(p=>p.hidden),[true,true,false]);
  assert.equal(ui.modes[2].getAttribute('aria-selected'),'true');
});
test('charts render source values rather than hardcoded Figma series',()=>{
  const ui=setup();const titles=descendants(ui.charts.income,'title').map(n=>n.textContent);
  assert.deepEqual(titles,['Real source · 2024: 100','Real source · 2025: 120']);
  assert.equal(descendants(ui.ids.relativePerformanceChart,'path').length,3);
});
test('benchmark toggles actually remove the selected plotted series',()=>{
  const ui=setup();ui.benchmarks[1].fire('click');const paths=descendants(ui.ids.relativePerformanceChart,'path');
  assert.equal(paths[1].getAttribute('d'),'');assert.notEqual(paths[0].getAttribute('d'),'');
});
test('historical selector changes chart and unavailable ROE never invents values',()=>{
  const ui=setup();const initial=descendants(ui.ids.fundamentalTrendChart,'path')[0].getAttribute('d');
  ui.trends[1].fire('click');assert.notEqual(descendants(ui.ids.fundamentalTrendChart,'path')[0].getAttribute('d'),initial);
  ui.trends[2].fire('click');assert.match(ui.ids.fundamentalTrendChart.textContent,/No values inferred/);assert.equal(ui.ids.fundamentalTrendChart.children.length,0);
  ui.trends[3].fire('click');assert.equal(descendants(ui.ids.fundamentalTrendChart,'circle').filter(node=>node.getAttribute('class')!=='chart-highlight').length,1);
  ui.ids.fundamentalTrendChart.clientWidth=360;
  ui.listeners.resize();
  assert.equal(descendants(ui.ids.fundamentalTrendChart,'svg')[0].getAttribute('viewBox'),'0 0 360 280');
});
test('line charts expose exact nearest-period hover values and annual labels',()=>{
  const ui=setup();
  const hit=descendants(ui.ids.relativePerformanceChart,'rect').at(-1);hit.fire('mousemove',{offsetX:884});
  const tooltip=ui.ids.relativePerformanceChart.children.at(-1);
  assert.equal(tooltip.hidden,false);
  assert.deepEqual(tooltip.children.map(node=>node.textContent),['2025','company: 120.00','market: 110.00','tech: 115.00']);
  assert.ok(descendants(ui.ids.fundamentalTrendChart,'text').some(node=>node.textContent==='2024'));
  assert.ok(descendants(ui.ids.fundamentalTrendChart,'text').some(node=>node.textContent==='2025'));
});
test('empty financial and market histories stay visibly unavailable',()=>{
  const ui=setup({missing:true});assert.match(ui.charts.income.textContent,/unavailable/);assert.equal(ui.charts.income.children.length,0);
  assert.match(ui.ids.relativePerformanceChart.textContent,/unavailable/);
});
test('hash overrides legacy tab and theme toggle is functional',()=>{
  const ui=setup({hash:'#financials'});assert.equal(ui.sections[1].focused,true);
  ui.ids['theme-toggle'].fire('click');assert.equal(ui.document.documentElement.dataset.theme,'dark');
  assert.equal(ui.preferences['research-platform-theme'],'dark');
});

const eventsSource = fs.readFileSync(new URL('../static/js/research_events.js', import.meta.url),'utf8');
test('Research events render backend timestamp, relevance and ticker/event links safely',async()=>{
  const root=new Element('div',{ticker:'NVDA'});
  const articles=[{article_id:'real / event',headline:'<script>not markup</script>',published_at:'2026-09-30T09:00:00Z',
    source:'Source',ticker_analysis:[{ticker:'NVDA',qualification:'direct_mention',explanation:'Backend relevance explanation'}]},
    {article_id:'other',headline:'Other company',ticker_analysis:[{ticker:'AAPL'}]}];
  vm.runInNewContext(eventsSource,{document:{getElementById:()=>root,createElement:tag=>new Element(tag)},
    fetch:async()=>({ok:true,json:async()=>({articles})}),encodeURIComponent});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(descendants(root,'article').length,1);
  assert.equal(descendants(root,'h3')[0].textContent,'<script>not markup</script>');
  assert.equal(descendants(root,'time')[0].textContent,'2026-09-30T09:00:00Z');
  assert.ok(descendants(root,'p').some(p=>p.textContent==='Backend relevance explanation'));
  assert.equal(descendants(root,'a')[0].href,'/news?ticker=NVDA&event=real%20%2F%20event');
});
test('News failure remains isolated from Research',async()=>{
  const root=new Element('div',{ticker:'AAPL'});
  vm.runInNewContext(eventsSource,{document:{getElementById:()=>root,createElement:tag=>new Element(tag)},
    fetch:async()=>({ok:false}),encodeURIComponent});
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(root.children[0].textContent,/Research data is unchanged/);
});
