import test from 'node:test';
import assert from 'node:assert/strict';
import {buildSearchQuery} from '../src/logic.mjs';
import {readFileSync} from 'node:fs';
test('question search defaults to verified and encodes all structured filters',()=>{
 const p=new URLSearchParams(buildSearchQuery({kind:'questions',q:'增长率 & x',module:'资料分析',year:'2025',paper_type:'行政执法',concept_id:'c-1'}));
 assert.equal(p.get('q'),'增长率 & x');assert.equal(p.get('allow_source_only'),'false');assert.equal(p.get('year'),'2025');assert.equal(p.get('paper_type'),'行政执法');assert.equal(p.get('concept_id'),'c-1');assert.equal(p.get('limit'),'20');
});
test('source-only needs explicit true and cards retain their independent module filter',()=>{
 assert.equal(new URLSearchParams(buildSearchQuery({kind:'materials',allow_source_only:true})).get('allow_source_only'),'true');
 const p=new URLSearchParams(buildSearchQuery({kind:'cards',module:'言语理解',year:'2025'}));assert.equal(p.get('module'),'言语理解');assert.equal(p.has('year'),false);assert.equal(p.get('limit'),'100');
 assert.throws(()=>buildSearchQuery({kind:'answers'}));
});
test('search renderer only uses safe prompt fields and explicit single-question start',()=>{
 const source=readFileSync(new URL('../src/main.tsx',import.meta.url),'utf8');
 const renderer=source.slice(source.indexOf('function searchQuestion'),source.indexOf('const cardList'));
 assert.doesNotMatch(renderer,/source_answer|verified_answer|explanation|dangerouslySetInnerHTML/);
 assert.match(renderer,/start\(\[x.question_id\],\s*\{mode:"practice"/);
 assert.match(source,/\[searchAllowSource,\s*setSearchAllowSource\]\s*=\s*useState\(false\)/);
});
test('assessment start requires explicit personal confirmation and declares seen/hint use',()=>{
 const s=readFileSync(new URL('../src/main.tsx',import.meta.url),'utf8');
 assert.match(s,/\[assessmentConfirm,\s*setAssessmentConfirm\]\s*=\s*useState\(false\)/);
 assert.match(s,/disabled=\{busy \|\| !assessmentConfirm\}/);
 assert.match(s,/confirm:assessmentConfirm,seen_before:assessmentSeen,hint_used:assessmentHint/);
 assert.match(s,/非原卷、非考分预测/);
});
