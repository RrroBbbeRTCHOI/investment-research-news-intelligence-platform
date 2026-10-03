/* Pure display/state arithmetic. Relationship decisions remain backend-owned. */
export const PORTFOLIO_KEY='news_positions_v1';
export function validPosition(p){return p&&/^[A-Z0-9.^-]{1,12}$/.test(p.ticker)&&Number.isFinite(p.shares)&&p.shares>=0&&Number.isFinite(p.cost)&&p.cost>=0&&Number.isFinite(p.shares*p.cost);}
export function loadPositions(storage){try{const p=JSON.parse(storage.getItem(PORTFOLIO_KEY)||'[]');return Array.isArray(p)?p.filter(validPosition).slice(0,30):[];}catch{return [];}}
export function savePositions(storage,positions){try{storage.setItem(PORTFOLIO_KEY,JSON.stringify(positions.filter(validPosition).slice(0,30)));return true;}catch{return false;}}
export function portfolioTotals(positions,quotes){
 let basis=0,value=0,missing=0,stale=false;
 for(const p of positions.filter(validPosition)){
  basis+=p.shares*p.cost;if(!p.shares)continue;
  const q=quotes[p.ticker];
  if(!q||q.currency!=='USD'||typeof q.value!=='number'||!Number.isFinite(q.value)||q.value<=0){missing++;continue;}
  value+=p.shares*q.value;stale||=q.status==='stale';
 }
 const usable=!missing&&Number.isFinite(value)&&Number.isFinite(basis);
 return {basis:Number.isFinite(basis)?basis:null,value:usable?value:null,pnl:usable?value-basis:null,percent:usable&&basis>0?(value-basis)/basis*100:null,missing,stale};
}
export function portfolioMatches(event,positions){
 const owned=new Set(positions.filter(p=>validPosition(p)&&p.shares>0).map(p=>p.ticker));
 return (event.analyses||[]).filter(t=>owned.has(t.ticker)&&(t.qualification?.startsWith('qualified_')||t.qualification==='direct_company_subject')).map(t=>t.ticker);
}
export function retainedSelection(events,id){return id&&events.some(e=>e.id===id)?id:null;}
export function scoreText(score){return typeof score?.score==='number'&&Number.isFinite(score.score)?`${score.score.toFixed(1)} / 100 · ${score.level}`:score?.level||'Unknown';}
export function snapshotIdentity(payload){return JSON.stringify([payload.generated_at,payload.articles]);}
export function markerIdentity(events){return JSON.stringify(events.map(e=>[e.id,e.title,e.region,e.latitude,e.longitude,e.severity,e.analyses?.map(t=>[t.ticker,t.qualification])]));}
