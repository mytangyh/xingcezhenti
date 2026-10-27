import json,sqlite3,hashlib,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));from pipeline.safety import validate_safe_markup
p=P/'assessments/personal-holdout-80-v1';m=json.load((p/'manifest.json').open());H=P/'acceptance/holdout';by={x['id']:x for x in json.load((H/'sealed_assessment/sealed_answers_80.json').open())['questions']};mapping=json.load((H/'verification_parent_mapping.json').open());c=sqlite3.connect('file:'+str(p/'content.sqlite')+'?mode=ro',uri=True);qs={i:json.loads(d) for i,d in c.execute('select id,data from questions')};mats={i:json.loads(d) for i,d in c.execute('select id,data from materials')};checks={};issues=[]
checks['all_manifest_hashes']=all(hashlib.sha256((p/f).read_bytes()).hexdigest()==h for f,h in m['files'].items());checks['exact_inventory']=set(m['files'])=={str(f.relative_to(p)) for f in p.rglob('*') if f.is_file() and f.name!='manifest.json'};checks['80_original_order']=m['question_ids']==[x['question_id'] for x in mapping] and len(qs)==80
for q in qs.values():
 a=by[q['assessment_item_id']];assert q['source_answer'] is None
 if q.get('practice_ready') or not q.get('holdout_reserved'):issues.append([q['question_id'],'production_escape'])
 if a['chosen_label']:
  ids=q['verified_answer']['option_ids'];labels=[o['label'] for o in q['options'] if o['option_id'] in ids]
  if labels!=[a['chosen_label']]:issues.append([q['question_id'],'wrong_key'])
 else:
  if q['verified_answer'] is not None or q['answer_status']!='unresolved' or q['assessment_ready']:issues.append([q['question_id'],'unresolved_key_added'])
 for text in [q['stem_html']]+[o['html'] for o in q['options']]:validate_safe_markup(text,p)
 if q['material_id'] and q['material_id'] not in mats:issues.append([q['question_id'],'missing_material'])
for mt in mats.values():validate_safe_markup(mt['stem_html'],p)
checks['79_scored_1_unscored']=sum(q['assessment_ready'] for q in qs.values())==79;checks['safe_keys_and_refs']=not issues;checks['db_integrity']=c.execute('pragma integrity_check').fetchone()[0]=='ok';c.close();r={'pack_id':m['pack_id'],'checks':checks,'issues':issues,'user_session_created':False,'scope':'isolated pack correctness/inventory/render-safety/key mapping only; API gating separate'};(H/'sealed_assessment/pack_independent_audit.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False));assert all(checks.values())
