import {present,presentOutlook,confidenceEvidence,human,relationshipLabel,relationshipState,markerPresentation} from './news_presentation.js';
import {loadPositions,savePositions,portfolioTotals,portfolioMatches,retainedSelection,scoreText,snapshotIdentity,markerIdentity} from './news_product.js';
import {adaptIntelligence,hasCoordinates,mapArticles,MARKETS,positionValue,ageLabel,matchesEvent,visibleArticles} from './news_model.js';
const $ = id=>document.getElementById(id);
let events=[];
let selected=null, globe=null;
let positions=[],quotes={},marketRows=[],operational={},snapshotKey=null,mapKey=null,loaded=false;
try{positions=loadPositions(localStorage);}catch{}
const workspace=$('workspace');
const text=(tag,value,className='')=>{const e=document.createElement(tag);e.textContent=value;if(className)e.className=className;return e;};
const pageParams=new URLSearchParams(location.search);
function applyTheme(theme){
 const light=theme==='light';document.body.classList.toggle('light-theme',light);
 $('theme-toggle')?.setAttribute('aria-pressed',String(light));if($('theme-toggle'))$('theme-toggle').textContent=light?'☾':'☼';
 try{localStorage.setItem('research-platform-theme',theme);}catch{}
}
let theme='dark';try{theme=localStorage.getItem('research-platform-theme')||'dark';}catch{}
applyTheme(theme);$('theme-toggle')?.addEventListener('click',()=>{theme=document.body.classList.contains('light-theme')?'dark':'light';applyTheme(theme);});
function renderList(){
 const filtered=visibleArticles(events,$('news-view')?.value||'surface').filter(e=>matchesEvent(e,$('news-search').value));
 $('news-list').replaceChildren();$('news-count').textContent=String(filtered.length).padStart(2,'0');$('empty-news').hidden=filtered.length!==0;
 for(const e of filtered){
  const button=text('button','', 'news-item');button.type='button';button.dataset.eventId=e.id;button.setAttribute('aria-label',e.title);button.setAttribute('aria-pressed',String(e.id===selected?.id));button.title=e.title;
  const meta=text('div','','news-meta');meta.append(text('i','',`event-dot ${markerPresentation(e).severity.toLowerCase()}`),text('span',`${e.feed&&e.region==='Unknown'?'':e.region+' · '}${e.source||'Source unavailable'}`,'region-name'));
  const age=text('time',ageLabel(e.time));age.dateTime=e.time;meta.append(age);
  const badges=text('div','','feed-badges');
  badges.append(text('span',e.display_type==='research'?'RESEARCH':e.content_type==='outlook'?'OUTLOOK':'EVENT','content-type-badge'));
  if(e.content_type==='outlook')badges.append(text('span',presentOutlook(e).classification,'feed-event-type'));
  else if(e.display_type==='research')badges.append(text('span','Not confirmed event','feed-event-type'));
  else{const severity=markerPresentation(e).severity;const severityBadge=text('span',severity,'feed-severity');severityBadge.dataset.severity=severity.toLowerCase();badges.append(severityBadge,text('span',present(e).classification,'feed-event-type'));}
  for(const t of e.analyses){
   const badge=text('span','','feed-relationship');badge.dataset.relationship=relationshipState(t);
   badge.append(text('strong',t.ticker),text('span',relationshipLabel(t)));
   badge.title=human(t.relationship_type);badges.append(badge);
  }
  if(!e.analyses.length&&!e.feed)badges.append(text('span','No watchlist match','feed-no-match'));
  button.append(text('h3',e.title),meta,badges);
  if(e.feed?.state)button.append(text('span',human(e.feed.state),'feed-state'));
  const matched=portfolioMatches(e,positions);if(matched.length)button.append(text('span',`PORTFOLIO MATCH · ${matched.join(' / ')}`,'portfolio-match'));
  button.addEventListener('click',()=>selectEvent(e.id,true));
  const card=text('article','','news-card');card.append(button);if(e.article_url){const original=safeLink(e.article_url,'↗ Original');original.className='original-link';card.append(original);}$('news-list').append(card);
 }
}
function section(title){const node=text('section','','analysis-section');node.append(text('h3',title));return node;}
function safeLink(url,label){
 const node=text('a',label);try{const u=new URL(url);if(!['https:','http:'].includes(u.protocol))throw Error();node.href=u.href;node.target='_blank';node.rel='noopener noreferrer';}catch{node.removeAttribute('href');}return node;
}
function disclosure(title){const d=text('details','','analyst-details');d.append(text('summary',title));return d;}
function bullets(items){const ul=text('ul','','analyst-bullets');for(const item of items)ul.append(text('li',item));return ul;}
function matchStateLabel(t){
 return ({qualified_direct_company_subject:'Direct Company Match',qualified_direct_event_subject:'Direct Event Match',indirect_exposure_match:'Indirect Exposure',direct_mention:'Mention Only',candidate_requires_review:'Review Candidate'})[t?.qualification]
  || ({direct_company_subject:'Direct Company Match',direct_event_subject:'Direct Event Match',direct_mention:'Mention Only'})[t?.relationship_type]
  || relationshipLabel(t);
}
function rows(parent,values){for(const [label,value] of values){const row=text('div','','exposure-row');row.append(text('span',label),text('span',value??'Unknown'));parent.append(row);}}
function renderOutlook(e,box){
 const p=presentOutlook(e);
 box.append(text('div','OUTLOOK / UPCOMING','event-kicker'),text('h3',e.title,'analysis-title'));
 const meta=text('div','','analysis-location');meta.append(safeLink(e.article_url,e.source||'Source unavailable'),text('span',` · ${ageLabel(e.time)}`));meta.title=e.time||'Published time unavailable';box.append(meta);
 const strip=text('div','','analyst-metrics product-score-strip');
 for(const [label,value] of [['RELEVANCE',scoreText(e.product_scores?.relevance)],['WATCH PRIORITY',scoreText(e.product_scores?.watch_priority)],['STATUS',p.status]]){const cell=text('div','','analyst-metric');cell.append(text('span',label),text('strong',value));strip.append(cell);}box.append(strip);
 box.append(text('p','Severity: N/A — Upcoming. Research attention scores are not probabilities, financial impact or price direction.','analysis-note'));
 for(const [title,items] of [['CATALYSTS',p.catalysts],['TIMING',[p.timing]],['RELATED ASSETS',[...p.tickers.map(t=>`${t} · Direct catalyst subject / Watchlist match`),...p.topics]],['WHY WATCH',p.reasons]]){const s=section(title);s.dataset.section=title.toLowerCase().replaceAll(' ','-');s.append(items.length?bullets(items):text('p','Not identified in source.','analysis-note'));box.append(s);}
 const owned=p.tickers.filter(t=>positions.some(position=>position.ticker===t&&position.shares>0));
 if(owned.length)box.append(text('p',`PORTFOLIO CATALYST MATCH · ${owned.join(' / ')}`,'portfolio-match'));
 box.append(text('p',p.notice,'analysis-note'));
 const evidence=disclosure('Source Evidence');for(const b of e.outlook?.source_basis||[])evidence.append(text('p',`${human(b.source_field)}: ${b.quote}`));box.append(evidence);
 const method=disclosure('Product Score Methods');method.append(text('pre',JSON.stringify(e.product_scores||{},null,2),'audit-data'));box.append(method);
 const audit=disclosure('Audit Details');const operations=text('pre',JSON.stringify(operational,null,2),'audit-data');operations.id='operational-audit';audit.append(operations,text('pre',JSON.stringify(e,null,2),'audit-data'));box.append(audit);
}
function renderAnalysis(e){
 $('analysis-heading').textContent=e?.display_type==='research'?'RESEARCH':e?.content_type==='outlook'?'RESEARCH OUTLOOK':'EVENT INTELLIGENCE';
 const box=$('analysis');box.replaceChildren();if(!e){delete box.dataset.eventId;box.append(text('p','No article selected.','muted'));return;}
 box.dataset.eventId=e.id;document.querySelector('.analysis-content').scrollTop=0;
 if(e.content_type==='outlook'){renderOutlook(e,box);return;}
 const research=e.display_type==='research';
 const header=present(e,e.analyses[0]);
 const kicker=text('div','','event-kicker');kicker.append(text('span',header.classification),text('span',e.analyses.length>1?`${e.analyses.length} ticker relationships`:header.status));
 box.append(kicker,text('h3',e.title,'analysis-title'));
 const meta=text('div',`${e.region} · `,'analysis-location');meta.append(safeLink(e.article_url,e.source||'Source unavailable'),text('span',` · ${ageLabel(e.time)}`));meta.title=e.time||'Published time unavailable';box.append(meta);if(e.article_url)box.append(safeLink(e.article_url,'↗ Original'));
 const happened=section('WHAT HAPPENED');happened.dataset.section='what-happened';
 happened.append(text('p',e.article_summary?.summary_full||e.event?.event_summary||'No backend summary is available. Open the original source for full context.','explanation'));box.append(happened);
 const severity=section('EVENT SEVERITY');severity.dataset.section='severity';
 rows(severity,[['Level',research?'N/A — Not confirmed event':e.severity?.level||'Unknown'],['Type',human(e.event?.event_type)],['Subtype',human(e.event?.event_subtype)]]);
 if(research)rows(severity,[['EVENT STATUS','Not confirmed as discrete event']]);
 severity.append(text('p','Severity describes event seriousness. It is not company match strength, evidence quality, financial impact, or price direction.','analysis-note'));box.append(severity);
 const relationships=section('COMPANY RELATIONSHIP / MATCH');relationships.dataset.section='relationships';
 if(!e.analyses.length)relationships.append(text('p','No watchlist ticker relationship supplied.','analysis-note'));
 for(const t of e.analyses){const state=relationshipState(t),group=text('div','','relationship-group');group.dataset.status=state;group.append(text('h4',`${t.ticker} · ${matchStateLabel(t)}`),text('p',human(t.relationship_type),'explanation'));relationships.append(group);}
 box.append(relationships);
 const owned=portfolioMatches(e,positions);if(owned.length)box.append(text('p',`PORTFOLIO MATCH · ${owned.join(' / ')}`,'portfolio-match'));
 for(const t of e.analyses.length?e.analyses:[null]){
  const p=present(e,t),group=text('section','','ticker-analysis');
  if(t){group.dataset.ticker=t.ticker;group.dataset.qualification=t.qualification||'';const chips=text('div','','chips');chips.append(text('span',t.ticker,'chip'),text('span',matchStateLabel(t),'chip theme-chip'));group.append(chips);}
  const why=section('WHY IT MATTERS');const reasons=p.reasons.filter(r=>!research||r!==e.severity?.reason);why.append(reasons.length?bullets(reasons):text('p','The backend has not supplied a company-specific interpretation.','analysis-note'));group.append(why);
  const paths=section('EXPOSURE PATH');
  if(p.paths.length){for(const path of p.paths){paths.append(text('p',path.label,'analysis-note'));const ol=text('ol','','impact-chain');path.steps.forEach(step=>ol.append(text('li',step)));paths.append(ol);}}
  else paths.append(text('p','No validated multi-step exposure path supplied.','analysis-note'));
  if(p.channels.length){const chips=text('div','','chips');p.channels.forEach(c=>chips.append(text('span',c,'chip theme-chip')));paths.append(chips);}group.append(paths);
  const evidence=section('EVIDENCE ASSESSMENT');
  if(t?.quantitative){const confidence=disclosure('Confidence evidence');rows(confidence,confidenceEvidence(t));confidence.append(text('p','Qualitative source-quality policy tier; not a calibrated probability or factual accuracy estimate. Extraction confidence is model self-assessment. Components are not combined into a score.','analysis-note'));evidence.append(confidence);}
  else rows(evidence,[['Relationship evidence',t?.evidence_assessment?.level||t?.evidence_strength?.relationship_level||'Unknown']]);
  if(p.evidence.length)evidence.append(bullets(p.evidence.map(item=>item.text===e.title?'The article headline is the supporting evidence.':item.text)));else evidence.append(text('p','No additional relationship evidence identified.','analysis-note'));
  evidence.append(text('p','Evidence quality is displayed independently from event severity and match type.','analysis-note'));group.append(evidence);
  if(e.feed||t?.quantitative)group.append(text('p','Research relevance is a normalized heuristic based on supported relationship terms. Not P(relevant), expected return, or financial impact.','analysis-note'));
  if(t){const open=text('a',`Open ${t.ticker} in Research →`,'open-research');open.href=`/research?ticker=${encodeURIComponent(t.ticker)}&tab=overview&event=${encodeURIComponent(e.id)}`;group.append(open);}
  const deep=disclosure('DEEP RESEARCH');deep.classList.add('deep-research');
  const status=disclosure('Research Status');status.append(text('p',`Financial impact: ${p.impact}`,'impact-value'),text('p',`Direction: ${t?.direction||e.direction||'Unknown'}`,'analysis-note'));if(p.impactReason)status.append(text('p',p.impactReason,'analysis-note'));deep.append(status);
  if(p.gaps.length){const gaps=disclosure('Next Research Questions');gaps.append(bullets(p.gaps));deep.append(gaps);}
  const scores=disclosure('Score Details');rows(scores,p.scores.filter(([label])=>!research||!['Severity policy score','Priority policy score'].includes(label)));scores.append(text('p','Policy scores are internal ordinal / rule-based signals, not probabilities or expected returns.','analysis-note'));deep.append(scores);
  if(p.history){const history=disclosure('Historical Context');history.append(text('p',p.history.disclosure||'Retrospective context only; not a direction forecast.','analysis-note'),text('pre',JSON.stringify(p.history.details||{},null,2),'audit-data'));deep.append(history);}
  if(t?.quantitative){const methodology=disclosure('Research Methodology');methodology.append(text('pre',JSON.stringify(t.quantitative,null,2),'audit-data'));deep.append(methodology);}
  group.append(deep);
  box.append(group);
 }
 if(!research){
 const location=disclosure('Event Location');location.append(text('p',header.location,'explanation'),text('p',header.locationNote,'analysis-note'));
 if(hasCoordinates(e)){const locate=text('button','Locate on globe','locate-event');locate.type='button';locate.addEventListener('click',()=>globe?.selectEvent(e,true));location.append(locate);}box.append(location);
 }
 const audit=disclosure('Audit Details');const operations=text('pre',JSON.stringify(operational,null,2),'audit-data');operations.id='operational-audit';audit.append(operations,text('pre',JSON.stringify(e,null,2),'audit-data'));box.append(audit);
}
function selectEvent(id,focus=false){
 if(id===null){selected=null;document.querySelectorAll('.news-item').forEach(b=>b.setAttribute('aria-pressed','false'));renderAnalysis(null);globe?.selectEvent(null,false);return;}
 const event=events.find(e=>e.id===id);if(!event)return;selected=event;
 // A globe selection must reveal its corresponding list item, even after filtering.
 if(event.feed&&event.feed.state!=='surface'&&$('news-view')){$('news-view').value='all';renderList();}
 if(!visibleArticles(events,$('news-view')?.value).some(e=>e.id===id)){$('news-view').value='surface';renderList();}
 if(!matchesEvent(event,$('news-search').value)){$('news-search').value='';renderList();}
 document.querySelectorAll('.news-item').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.eventId===id)));
 renderAnalysis(event);globe?.selectEvent(event,focus&&hasCoordinates(event));
 const item=[...document.querySelectorAll('.news-item')].find(b=>b.dataset.eventId===id);
 item?.scrollIntoView({block:'nearest',behavior:'auto'});
}
$('news-search').addEventListener('input',renderList);
$('news-view')?.addEventListener('change',()=>{renderList();const visible=visibleArticles(events,$('news-view').value);if(!visible.some(e=>e.id===selected?.id))selectEvent(visible[0]?.id??null);});
function setCollapsed(collapsed){workspace.classList.toggle('news-collapsed',collapsed);$('collapse-news').setAttribute('aria-expanded',String(!collapsed));$('collapse-news').setAttribute('aria-label',collapsed?'Expand news list':'Collapse news list');$('collapse-news').textContent=collapsed?'›':'‹';}
$('collapse-news').addEventListener('click',()=>setCollapsed(!workspace.classList.contains('news-collapsed')));
if(matchMedia('(max-width:720px)').matches)setCollapsed(true);
function updateClocks(){const date=new Date();document.querySelectorAll('[data-zone]').forEach(el=>{el.textContent=new Intl.DateTimeFormat('en-GB',{timeZone:el.dataset.zone,hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(date);el.dateTime=date.toISOString();});$('utc-clock').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(date)+' UTC';}
updateClocks();setInterval(updateClocks,1000);
setInterval(()=>{document.querySelectorAll('.news-item time').forEach(el=>el.textContent=ageLabel(el.dateTime));},60000);
const signed=(value,prefix='')=>`${value>=0?'+':'−'}${prefix}${Math.abs(value).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
function renderPortfolio(){
 const totals=portfolioTotals(positions,quotes);
 $('position-symbol').textContent='PORTFOLIO';
 $('position-price').textContent=totals.value===null?'Value unavailable':'$'+totals.value.toFixed(2);
 $('position-summary').textContent=positions.length+' positions';
 $('position-pnl').textContent=totals.pnl===null?'P&L unavailable':signed(totals.pnl,'$');
 $('position-percent').textContent=totals.percent===null?'N/M':signed(totals.percent)+'%';
 for(const id of ['position-pnl','position-percent'])$(id).className=totals.pnl===null||totals.pnl===0?'neutral':totals.pnl>0?'positive':'negative';
 document.querySelector('.demo-label').textContent=!positions.length?'EMPTY':totals.missing?'NO QUOTE':totals.stale?'STALE':'DELAYED';
 $('position-toggle').title='USD positions · Latest available quotes; no FX conversion. Cost basis: '+totals.basis;
 $('positions-list').replaceChildren();
 for(const p of positions){const row=text('div','','position-row');row.append(text('span',p.ticker+' · '+p.shares+' shares · $'+p.cost+' cost'));
 const remove=text('button','Remove');remove.type='button';remove.addEventListener('click',()=>{positions=positions.filter(x=>x.ticker!==p.ticker);persistPortfolio();});row.append(remove);$('positions-list').append(row);}
}
function persistPortfolio(){
 let saved=false;try{saved=savePositions(localStorage,positions);}catch{}
 $('position-feedback').textContent=saved?'Saved in this browser.':'Browser storage unavailable; positions are session-only.';
 renderPortfolio();renderList();if(selected)renderAnalysis(selected);
}
function applyPosition(){
 const value=positionValue($('position-ticker').value,$('position-cost').value,$('position-quantity').value);
 if(value.error){$('position-feedback').textContent=value.error;return false;}
 if(positions.length>=30&&!positions.some(p=>p.ticker===value.ticker)){$('position-feedback').textContent='Maximum 30 positions.';return false;}
 positions=positions.filter(p=>p.ticker!==value.ticker);
 positions.push({ticker:value.ticker,shares:value.quantity,cost:value.cost});persistPortfolio();return true;
}
function showPosition(show){$('position-editor').hidden=!show;$('position-toggle').setAttribute('aria-expanded',String(show));if(show)$('position-ticker').focus();}
$('position-toggle').addEventListener('click',()=>showPosition($('position-editor').hidden));$('position-close').addEventListener('click',()=>showPosition(false));$('position-editor').addEventListener('submit',e=>{e.preventDefault();if(applyPosition())showPosition(false);});document.addEventListener('keydown',e=>{if(e.key==='Escape')showPosition(false);});renderPortfolio();
function renderMarkets(markets){
 const group=text('div','','tape-group');
 for(const q of markets){const item=text('span','','market-item');item.append(text('span',q.name,'market-name'),text('span',Number.isFinite(q.value)?q.value.toLocaleString('en-US',{maximumFractionDigits:2}):'Unavailable'),text('span',Number.isFinite(q.change)?signed(q.change):'—'),text('span',Number.isFinite(q.change_percent)?signed(q.change_percent)+'%':'—'),text('small',q.status||'unavailable'));
 item.title=(q.timestamp||'Timestamp unavailable')+' · '+(q.currency||'')+' · '+(q.definition||'');group.append(item);}
 const duplicate=group.cloneNode(true);duplicate.setAttribute('aria-hidden','true');$('market-tape').replaceChildren(group,duplicate);
}
async function loadMarkets(){
 let delay=180000;
 try{const response=await fetch('/api/news/markets',{cache:'no-store'});if(!response.ok)throw Error();const payload=await response.json();quotes=payload.quotes||{};marketRows=payload.markets||[];renderMarkets(marketRows);renderPortfolio();document.querySelector('.tape-label small').textContent=payload.status.toUpperCase();delay=Math.max(60,payload.poll_seconds||180)*1000;}
 catch{document.querySelector('.tape-label small').textContent='UNAVAILABLE';for(const q of Object.values(quotes))q.status='stale';marketRows=marketRows.map(q=>({...q,status:q.value==null?'unavailable':'stale'}));renderMarkets(marketRows);renderPortfolio();}
 setTimeout(loadMarkets,delay);
}
loadMarkets();
let paused=matchMedia('(prefers-reduced-motion:reduce)').matches;
function tapeState(){ $('market-tape').classList.toggle('paused',paused);$('tape-toggle').textContent=paused?'▷':'Ⅱ';$('tape-toggle').setAttribute('aria-label',paused?'Resume market tape':'Pause market tape');$('tape-toggle').setAttribute('aria-pressed',String(paused));}
$('tape-toggle').addEventListener('click',()=>{paused=!paused;tapeState();});tapeState();
let videoTimeout;
function videoFallback(){
 clearTimeout(videoTimeout);
 const placeholder=text('div','','video-placeholder');placeholder.append(text('span','▷','broadcast-icon'),text('strong','Watch the live broadcast'),text('span','If embedding is blocked, open YouTube.'));
 const link=text('a','WATCH LIVE ↗','primary-button');link.href='https://www.youtube.com/watch?v=QB5BNdBFujE';link.target='_blank';link.rel='noopener noreferrer';placeholder.append(link);
 $('video-frame').replaceChildren(placeholder);$('video-status').textContent='External playback available';$('video-fallback').hidden=true;
}
$('video-fallback').addEventListener('click',videoFallback);
$('load-live').addEventListener('click',()=>{
 const iframe=document.createElement('iframe');iframe.title='Bloomberg Business News Live';iframe.src='https://www.youtube.com/embed/QB5BNdBFujE?autoplay=0&mute=1&playsinline=1';iframe.allow='encrypted-media; picture-in-picture; fullscreen';iframe.allowFullscreen=true;iframe.referrerPolicy='strict-origin-when-cross-origin';
 // A load event cannot establish playback success across origins. Keep both
 // a persistent external link and a user-operated placeholder fallback.
 iframe.addEventListener('load',()=>clearTimeout(videoTimeout));iframe.addEventListener('error',videoFallback);
 $('video-frame').replaceChildren(iframe);$('video-status').textContent='If blocked, use Watch live →';$('video-fallback').hidden=false;
 videoTimeout=setTimeout(videoFallback,12000);
});

function feedState(message){$('empty-news').textContent=message;$('empty-news').hidden=false;$('analysis').replaceChildren(text('p',message,'muted'));}
async function syncGlobe(){
 const marked=mapArticles(events),key=markerIdentity(marked);if(key===mapKey)return;
 try{
  if(globe)globe.setEvents(marked);
  else{const {createGlobe}=await import('./news_globe.js');globe=await createGlobe($('globe'),marked,id=>selectEvent(id));}
  mapKey=key;if(selected)globe.selectEvent(selected,false);$('globe-state').hidden=true;
 }catch{$('globe-state').textContent='3D map unavailable. Select articles from the feed.';}
}
async function loadIntelligence(){
 let delay=45000;
 if(!loaded)feedState('Loading News Intelligence…');
 try{
  const response=await fetch('/api/news/intelligence',{cache:'no-store'});
  if(!response.ok)throw Error();
  const payload=await response.json();const next=adaptIntelligence(payload);operational=payload.operational||{};
  if($('operational-audit'))$('operational-audit').textContent=JSON.stringify(operational,null,2);
  delay=Math.max(30,payload.poll_seconds||45)*1000;
  document.querySelector('.header-mode').textContent=(operational.pipeline_status||'demo').toUpperCase();
  document.querySelector('.header-mode').title=operational.reason||'';
  document.querySelector('.feed-footer').textContent=(operational.reason||'Backend snapshot')+' · Updated '+ageLabel(operational.generated_at_utc||payload.generated_at)+' ago';
  const key=snapshotIdentity(payload);
  if(key!==snapshotKey){
   const requestedEvent=pageParams.get('event'),requestedTicker=pageParams.get('ticker')?.toUpperCase();
   const contextual=next.find(e=>e.id===requestedEvent)||next.find(e=>requestedTicker&&e.analyses.some(t=>t.ticker===requestedTicker));
   const id=loaded?retainedSelection(next,selected?.id):(contextual?.id??visibleArticles(next)[0]?.id??null);
   events=next;snapshotKey=key;renderList();selectEvent(id);await syncGlobe();
   $('empty-news').textContent=events.length?'No matching articles.':'No articles in this snapshot.';
  }
  loaded=true;
 }catch{
  document.querySelector('.header-mode').textContent='DEGRADED';
  document.querySelector('.feed-footer').textContent='Backend unavailable · showing last loaded results';
  if(!loaded)feedState('News Intelligence unavailable. Waiting for a valid snapshot.');
 }
 setTimeout(loadIntelligence,delay);
}
loadIntelligence();
