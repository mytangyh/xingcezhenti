import json,re,hashlib,collections
from pathlib import Path
P=Path(__file__).resolve().parents[1];A=P.parent/'xingce_analysis'
def h(s):return hashlib.sha256(re.sub(r'\s+','',s).encode()).hexdigest()
groups=json.load((P/'content_review/extension_plan/groups24.json').open());selected={q for g in groups for q in g['question_ids']};hold=list(map(json.loads,(P/'acceptance/holdout/reserved_ids.jsonl').open()));hids={q['question_id'] for q in hold};hfp={q['fingerprint'] for q in hold};hm={v for q in hold for v in q['material_fingerprints']};closure=set(hids)
clusters=[set(x['question_ids']) for x in map(json.loads,(P/'releases/content-v6-reviewed550/duplicate_candidates.jsonl').open())]
while True:
 old=len(closure)
 for g in clusters:
  if g&closure:closure.update(g)
 if old==len(closure):break
mat={(x['source_path'],x['source_material_number']):h(x['raw_text']) for x in map(json.loads,(A/'materials_candidates.jsonl').open())};rows=collections.defaultdict(list)
for r in map(json.loads,(A/'records.jsonl').open()):
 if 'q-'+r['qid'] in selected:rows['q-'+r['qid']].append(r)
issues=[]
for q in selected:
 if q in closure:issues.append([q,'direct_or_duplicate_cluster'])
 rs=rows[q];f=h(json.dumps([rs[0]['stem'],rs[0]['options']],ensure_ascii=False,sort_keys=True))
 if f in hfp:issues.append([q,'exact_prompt'])
 for r in rs:
  key=(r['source_path'],r['candidate_material_number'])
  if mat.get(key) in hm:issues.append([q,'same_material'])
rep={'planned_groups':len(groups),'unique_questions':len(selected),'holdout_count':len(hids),'holdout_cluster_closure_size':len(closure),'issues':issues,'all_pass':not issues,'scope':'direct qid, existing exact/near candidate transitive closure, whitespace-normalized material, exact stem+options; not proof of all latent semantic variants'};(P/'acceptance/extension_holdout_audit.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2));print(json.dumps(rep,ensure_ascii=False));assert not issues
