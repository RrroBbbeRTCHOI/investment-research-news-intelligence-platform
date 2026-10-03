/* Presentation only: backend qualification, scores and direction are never computed here. */
export const MARKETS = ['HANG SENG','SHANGHAI','NIKKEI 225','S&P 500','NASDAQ','DOW JONES','BRENT','WTI','GOLD','DOLLAR INDEX','BITCOIN'].map(name=>[name,null,null]);
export function hasCoordinates(e) {
 return typeof e.latitude==='number' && Number.isFinite(e.latitude) && Math.abs(e.latitude)<=90 && typeof e.longitude==='number' && Number.isFinite(e.longitude) && Math.abs(e.longitude)<=180;
}
export function adaptIntelligence(payload) {
 if(!payload || !['news_ui_v1','news_ui_v2','news_ui_v3'].includes(payload.schema_version) || !Array.isArray(payload.articles) || !Array.isArray(payload.queue))throw Error('Malformed intelligence response');
 return payload.articles.map(a=>{
  if(!a || typeof a.article_id!=='string' || typeof a.headline!=='string' || !Array.isArray(a.ticker_analysis))throw Error('Malformed article');
  const e=a.event||{}, analyses=a.ticker_analysis;
  const geo=a.geography&&typeof a.geography==='object'?a.geography:null;
  const first=analyses[0];
  const level=a.research_priority?.level||first?.research_priority?.level||'Unavailable';
  const sev=a.severity?.level||'Unknown';
  return {...a,display_type:a.content_type==='outlook'?'outlook':a.gate?.is_event===false?'research':a.gate?.is_event===true?'event':a.display_type||'event',id:a.article_id,title:a.headline,time:a.published_at||e.published_at_first||null,
   isV3:payload.schema_version==='news_ui_v3',
   region:geo?(geo.event_city||geo.event_region||geo.event_country||'Unknown'):(e.city||e.region||e.country||e.location_name||e.primary_country||'Unknown'),
   category:a.content_type==='outlook'?a.outlook?.category||'Research Outlook':e.event_type||a.classification||'Unknown',
   latitude:geo?(geo.latitude??null):(e.latitude??null),longitude:geo?(geo.longitude??null):(e.longitude??null),
   urgency:sev==='Critical'?'urgent':sev==='High'?'high':sev==='Medium'?'medium':sev==='Low'?'low':'unknown',priority_label:level,
   relevance:first?.relevance?.level||first?.relevance_level||'Unknown',
   affected_tickers:a.content_type==='outlook'?(a.outlook?.related_tickers||[]).map(t=>t.ticker):analyses.map(t=>t.ticker),themes:[...new Set(analyses.flatMap(t=>t.economic_channels||[]))],
   analyses,event_id:e.event_id||null};
 }).sort(compareArticles);
}
// Display ordering only; no score or qualification is computed from these ranks.
const FEED_ORDER={surface:0,background:1,reject:2};
const SEVERITY_ORDER={Critical:0,High:1,Medium:2,Low:3,Unknown:4};
const PRIORITY_ORDER={Urgent:0,High:1,Medium:2,Review:3,Low:4};
export function compareArticles(a,b){
 const feed=e=>FEED_ORDER[e.feed?.state]??(!e.isV3&&!e.feed?0:3);
 const date=e=>Number.isFinite(Date.parse(e.time))?Date.parse(e.time):-Infinity;
 return feed(a)-feed(b)
  ||Number(a.content_type==='outlook')-Number(b.content_type==='outlook')
  ||(SEVERITY_ORDER[a.severity?.level]??4)-(SEVERITY_ORDER[b.severity?.level]??4)
  ||(PRIORITY_ORDER[a.research_priority?.level]??5)-(PRIORITY_ORDER[b.research_priority?.level]??5)
  ||(date(a)===date(b)?0:date(a)>date(b)?-1:1)
  ||a.id.localeCompare(b.id);
}
export function positionValue(ticker, cost, quantity, quotes={}) {
 const symbol=String(ticker).trim().toUpperCase();
 if(!/^[A-Z0-9.^-]{1,12}$/.test(symbol)||cost===''||quantity===''||!Number.isFinite(Number(cost))||!Number.isFinite(Number(quantity))||Number(cost)<0||Number(quantity)<0) return {error:'Enter a valid ticker, non-negative cost and quantity.'};
 const c=Number(cost),q=Number(quantity),price=quotes[symbol];
 const basis=c*q;
 if(!Number.isFinite(basis)||(Number.isFinite(price)&&!Number.isFinite((price-c)*q)))return {error:'Position values exceed the supported numeric range.'};
 return {ticker:symbol,cost:c,quantity:q,price:Number.isFinite(price)?price:null,basis,pnl:Number.isFinite(price)?(price-c)*q:null,percent:Number.isFinite(price)&&basis>0?(price-c)/c*100:null};
}
export function ageLabel(iso,now=Date.now()) {if(!iso||!Number.isFinite(Date.parse(iso)))return "Unavailable";const mins=Math.max(0,Math.floor((now-Date.parse(iso))/60000));return mins<60?`${mins} min`:`${Math.floor(mins/60)}h ${mins%60}m`;}
export function matchesEvent(event, query) {return [event.title,event.region,event.category,event.event?.event_subtype,...event.affected_tickers,...event.themes].join(' ').toLowerCase().includes(query.trim().toLowerCase());}

export function visibleArticles(events,view='surface'){return events.filter(e=>e.content_type!=='skip'&&(view==='all'||e.feed?.state==='surface'||!e.isV3&&!e.feed)&&(view!=='outlook'||e.content_type==='outlook')&&(view!=='events'||(e.content_type!=='outlook'&&e.display_type!=='research'&&e.gate?.is_event!==false)));}
export function mapArticles(events){return events.filter(e=>e.content_type!=='skip'&&e.display_type!=='research'&&e.gate?.is_event!==false&&e.usable!==false&&e.feed?.state!=='reject'&&hasCoordinates(e));}
