import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../static/js/news_presentation.js',import.meta.url),'utf8');
const {markerPresentation,relationshipState,present,policyValue}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const base={title:'Test event',region:'Japan',analyses:[],severity:{level:'Unknown'}};
const qualified={ticker:'NVDA',qualification:'qualified_direct_company_subject',relationship_type:'direct_company_subject',relevance:{level:'High'}};
const mention={ticker:'AAPL',qualification:'candidate_requires_review',relationship_type:'direct_mention',relevance:{level:'Mention only'}};
assert.equal(markerPresentation(base).hollow,true);
assert.equal(markerPresentation({...base,severity:{level:'Low'}}).hollow,false);
assert.notEqual(markerPresentation(base).color,markerPresentation({...base,severity:{level:'Low'}}).color);
for(const level of ['Critical','High','Medium','Low','Unknown']){
 const plain=markerPresentation({...base,severity:{level}});
 const linked=markerPresentation({...base,severity:{level},analyses:[qualified]});
 assert.equal(plain.color,linked.color);assert.equal(linked.linked,true);assert.equal(plain.linked,false);
 const selected=markerPresentation({...base,severity:{level}},true);
 assert.equal(selected.color,plain.color);assert.equal(selected.hollow,plain.hollow);assert.equal(selected.selected,true);
}
assert.equal(markerPresentation({...base,analyses:[mention]}).linked,false);
assert.match(markerPresentation({...base,analyses:[mention]}).tooltipDetail,/AAPL \(Review candidate\)/);
assert.notEqual(relationshipState(qualified),relationshipState(mention));
assert.match(markerPresentation(base).tooltipDetail,/Severity: Unknown\nWatchlist: No match/);
assert.equal(present(base).metrics[0][0],'WATCHLIST');assert.equal(policyValue(null),'Not assigned');assert.equal(policyValue(0),'0');
assert.ok(Object.values(present(base).components).every(v=>v===undefined));
const inputs={...base,event:{event_subtype:'workforce_reduction'}};assert.equal(present(inputs).gaps.length,0);
assert.equal(present({...base,event:{event_subtype:'general_news'}}).gaps.length,0);
const multi={...base,analyses:[qualified,mention]};assert.match(markerPresentation(multi).tooltipDetail,/NVDA; AAPL \(Review candidate\)/);
console.log('PASS: independent severity / qualification / selection, hollow Unknown, mention distinction, human tooltip, missing/zero scores, deterministic checklist and no invented components.');
