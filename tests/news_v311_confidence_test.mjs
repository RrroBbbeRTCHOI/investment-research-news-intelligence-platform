import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../static/js/news_presentation.js',import.meta.url),'utf8');
const {confidenceEvidence}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const ticker={quantitative:{confidence:{value:.5985,source_quality:'High',extraction_self_assessment:.95,relationship_evidence_quality:'Moderate'}}};
assert.deepEqual(confidenceEvidence(ticker),[
 ['Source quality','High'],['Extraction confidence (model self-assessment)','0.95'],['Relationship evidence','Moderate']
]);
assert.ok(!JSON.stringify(confidenceEvidence(ticker)).match(/0\.5985|59\.85|%/));
assert.equal(confidenceEvidence({quantitative:{confidence:{value:.5985,source_quality:.9}}})[0][1],'Unknown');
assert.equal(confidenceEvidence(null)[1][1],'Unavailable');
const ui=await readFile(new URL('../static/js/news_ui.js',import.meta.url),'utf8');
assert.ok(ui.includes('Confidence evidence'));
assert.ok(!ui.includes('confidence.value'));
assert.ok(ui.includes('Components are not combined into a score.'));
console.log('PASS qualitative confidence components, legacy product hidden, unknowns and no percentage display.');
