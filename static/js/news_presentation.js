/* Pure presentation: never qualifies a relationship or computes an analytical score. */
const labels={general_news:'General News',workforce_reduction:'Workforce / Restructuring',direct_event_subject:'Direct Event Subject',direct_company_subject:'Direct Company Subject',direct_mention:'Mention Only',candidate_requires_review:'Review Candidate',qualified_direct_event_subject:'Direct Event Match',qualified_direct_company_subject:'Direct Company Match',indirect_exposure_match:'Indirect Exposure',advanced_semiconductors:'Advanced Semiconductors',advanced_packaging:'Advanced Packaging'};
export const human=value=>labels[value]||String(value||'Unknown').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
export const policyValue=value=>typeof value==='number'&&Number.isFinite(value)?String(value):'Not assigned';
export function relationshipLabel(t){return !t?'No watchlist match':({qualified:'Qualified',review:'Review',mention:'Mention Only',unknown:'Unknown'}[relationshipState(t)]);}
export function present(e,t=null){
 const subtype=e.event?.event_subtype;
 const classification=human(subtype||e.event?.event_type||e.classification);
 const rel=t?.relationship_type, name=t?.ticker;
 // Modern final-field explanations take precedence over stale legacy prose.
 // In the frozen replay AMZN is qualified but its old `explanation` still says
 // mention-only; retain that legacy text in Audit rather than contradict final status.
 const reasons=[t?.analyst_interpretation,t?.relevance?.reason||t?.relevance?.interpretation,
  e.severity?.reason,t?.evidence_assessment?.reason,t?.financial_materiality?.reason]
  .filter((value,index,items)=>typeof value==='string'&&value.trim()&&items.indexOf(value)===index);
 const why=reasons.join('\n');
 const evidence=[];
 const add=(snippet,source)=>{if(typeof snippet==='string'&&snippet.trim()&&!evidence.some(x=>x.text===snippet))evidence.push({text:snippet,source});};
 add(t?.direct_event_evidence?.evidence,t?.direct_event_evidence?.source_field);
 for(const item of Object.values(t?.article_evidence||{}))add(item?.evidence,item?.source_field);
 for(const c of e.severity?.components||[])add(c.evidence,c.source_field);
 for(const edge of t?.evidence||[])add(`Curated exposure edge ${edge.edge_id}: ${[edge.counterparty,edge.channel_family&&human(edge.channel_family),edge.source_locator].filter(Boolean).join(' · ')}`,edge.source_url);
 add(t?.evidence_strength?.basis||t?.evidence_strength?.note,'Relationship evidence assessment');
 const gaps=(t?.next_questions||[]).filter(value=>typeof value==='string'&&value.trim());
 const paths=[];
 if(relationshipState(t)==='qualified')for(const p of t?.relationship_paths||[])if(p.edge_id!=null&&p.ticker===name)paths.push({label:`Exposure edge ${p.edge_id}`,steps:[e.title,p.counterparty,p.business,p.channel&&human(p.channel),p.ticker].filter(Boolean)});
 const geography=e.geography||{},hist=t?.historical_context;
 const v3=Boolean(e.feed||e.enrichment||t?.quantitative);
 const relevance=t?.quantitative?.relevance;
 const numeric=typeof relevance?.value==='number'&&Number.isFinite(relevance.value)?`${relevance.value.toFixed(2)} heuristic`:'Unavailable';
 const relevanceLabel=t?.relevance?.level||t?.relevance_level||'Unknown';
 return {classification,status:relationshipLabel(t),why,reasons,evidence,gaps,paths,
  metrics:[[t?'RELEVANCE':'WATCHLIST',t?(v3?`${relevanceLabel} / ${numeric}`:relevanceLabel):'No match'],['SEVERITY',e.severity?.level||'Unknown'],['EVIDENCE',t?.evidence_assessment?.level||t?.evidence_strength?.relationship_level||'—'],['PRIORITY',t?.research_priority?.level||e.research_priority?.level||'—']],
  channels:(t?.economic_channels||[]).map(human),impact:t?.financial_materiality?.level||'Unknown',impactReason:t?.financial_materiality?.reason||'',
  location:e.region||'Unknown',locationNote:geography.coordinate_precision?human(geography.coordinate_precision):'Unknown',
  locationBasis:geography.location_basis?human(geography.location_basis):'Unknown',
  history:hist?.available?hist:null,
  scores:[...(v3?[['Quantitative relevance',numeric]]:[['Relationship policy score',policyValue(t?.relevance&&Object.hasOwn(t.relevance,'relationship_score')?t.relevance.relationship_score:t?.relevance_score)]]),['Severity policy score',policyValue(e.severity?.score)],['Priority policy score',policyValue((t?.research_priority||e.research_priority)?.score)]],
  // Existing components are exposed verbatim; future supplied breakdowns need no scoring here.
  components:{relationship:v3?t?.quantitative?.relevance?.contributions:t?.relevance?.components||t?.relevance_components,severity:e.severity?.components,evidence:t?.evidence_assessment?.components,materiality:t?.financial_materiality?.components,priority:t?.research_priority?.components},
 };
}

// Independent presentation dimensions: selection never changes severity or qualification.
export function relationshipState(t){
 if(t?.qualification==='candidate_requires_review')return 'review';
 if(t?.qualification?.startsWith('qualified_')||t?.qualification==='direct_company_subject')return 'qualified';
 if(t?.qualification)return 'unknown';
 if(t?.relationship_type==='direct_company_subject')return 'qualified';
 return t?.relationship_type==='direct_mention'?'mention':'unknown';
}
export function markerPresentation(e,selected=false){
 if(e.content_type==='outlook')return {severity:'N/A — Upcoming',color:'#8197a4',hollow:true,linked:false,selected,tooltipTitle:e.region||'Not resolved',tooltipDetail:`${e.title}\nOutlook / Upcoming`};
 if(e.display_type==='research'||e.gate?.is_event===false)return {severity:'N/A — Not confirmed event',color:'#8197a4',hollow:true,linked:false,selected,tooltipTitle:e.title,tooltipDetail:'Research / Not confirmed as discrete event'};
 const level=e.severity?.level||'Unknown';
 const palette={Critical:'#ff5964',High:'#ff5964',Medium:'#ffb020',Low:'#43d8ff',Unknown:'#8197a4'};
 const severity=Object.hasOwn(palette,level)?level:'Unknown';
 const analyses=e.analyses||[];
 const qualified=analyses.filter(t=>relationshipState(t)==='qualified').map(t=>t.ticker);
 const mentions=analyses.filter(t=>relationshipState(t)==='mention').map(t=>t.ticker);
 const review=analyses.filter(t=>relationshipState(t)==='review').map(t=>t.ticker);
 const watchlist=[qualified.length?qualified.join(' / '):'',mentions.length?`${mentions.join(' / ')} (Mention only)`:'',review.length?`${review.join(' / ')} (Review candidate)`:''].filter(Boolean).join('; ')||'No match';
 return {severity,color:palette[severity],hollow:severity==='Unknown',linked:qualified.length>0,selected,
  tooltipTitle:e.region||'Unknown',tooltipDetail:`${e.title}\nSeverity: ${severity}\nWatchlist: ${watchlist}`};
}

export function presentOutlook(e){
 const o=e.outlook||{};
 return {classification:`${human(o.category||'research')} Watch`,status:'Upcoming',
  catalysts:(o.catalysts||[]).map(c=>c.name),
  timing:o.scheduled_at_utc||`${o.expected_window||'Upcoming'} / Not precisely resolved`,
  tickers:(o.related_tickers||[]).filter(t=>t.relationship==='direct_catalyst_subject').map(t=>t.ticker),
  topics:o.related_macro_topics||[],reasons:o.watch_reasons||[],notice:o.notice||''};
}

// Confidence components are displayed independently; never format the old product.
export function confidenceEvidence(t){
 const c=t?.quantitative?.confidence||{};
 const source=['High','Medium','Low','Unknown'].includes(c.source_quality)?c.source_quality:'Unknown';
 const extraction=typeof c.extraction_self_assessment==='number'&&Number.isFinite(c.extraction_self_assessment)&&c.extraction_self_assessment>=0&&c.extraction_self_assessment<=1?String(c.extraction_self_assessment):'Unavailable';
 const relationship=typeof c.relationship_evidence_quality==='string'?c.relationship_evidence_quality:t?.evidence_assessment?.level||'Unknown';
 return [['Source quality',source],['Extraction confidence (model self-assessment)',extraction],['Relationship evidence',relationship]];
}
