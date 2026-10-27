"""Read-only full release accounting and known regression checks."""
import json,sqlite3,sys,collections
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from pipeline.release import validate_release
version=sys.argv[1] if len(sys.argv)>1 else 'content-v1-base';path=P/'releases'/version
manifest=validate_release(path);c=sqlite3.connect('file:'+str(path/'content.sqlite')+'?mode=ro',uri=True)
qs={row[0]:json.loads(row[1]) for row in c.execute('select id,data from questions')};occ=[json.loads(r[0]) for r in c.execute('select data from occurrences')]
checks={'full_questions':len(qs)==27473,'full_occurrences':len(occ)==58890,'no_occurrence_loss':len({r['occurrence_id'] for r in occ})==58890,'misclassified_5893530':qs['q-5893530']['normalized_module']=='数量关系','misclassified_5445878':qs['q-5445878']['normalized_module']=='数量关系','no_fake_formal_cards':all(not json.loads(r[0]).get('is_official') for r in c.execute('select data from cards'))}
known=json.loads((P/'acceptance/baseline_audit.json').read_text())['special_regression_source_records'];post5=[r for r in known if r['module']=='判断推理' and r['source_local_number']>5]
checks['no_false_doubles_binding_after_five']=all(not qs['q-'+r['qid']]['material_id'] for r in post5)
checks['unverified_binding_not_trainable']=all(not q['practice_ready'] for q in qs.values() if q['material_binding_status']!='verified')
checks['no_checkmark_in_prompt']=all('✅' not in q['stem_html']+''.join(o['html'] for o in q['options']) for q in qs.values())
heldout={q['question_id'] for q in qs.values() if q.get('holdout_reserved')}
checks['holdout80_reserved']=len(heldout)==80 if version!='content-v1-base' and version!='content-v1-reviewed' else True
checks['holdout_not_trainable']=all(not qs[x]['practice_ready'] for x in heldout)
practice_file=path/'practice/questions.jsonl'
if practice_file.exists():
 practice=[json.loads(l) for l in practice_file.open()];checks['practice_no_holdout']=not {x['id'] for x in practice}&heldout;checks['practice_exact_ready_set']={x['id'] for x in practice}=={q['question_id'] for q in qs.values() if q['practice_ready']}
 checks['practice_no_answer_fields']=all(not set(x)&{'source_answer','verified_answer','explanation','concept_ids','method_ids'} for x in practice)
counts=collections.Counter(r['source_module'] for r in occ)
checks['module_counts_preserved']=dict(counts)=={'政治理论':2305,'常识判断':9163,'言语理解与表达':16000,'数量关系':6448,'判断推理':16859,'资料分析':8115}
out={'release':version,'checks':checks,'scope':'accounting, contract and specific regressions only; not full semantic/solution/human acceptance','reference_cards':c.execute('select count(*) from cards').fetchone()[0],'practice_ready':sum(q['practice_ready'] for q in qs.values()),'ready_by_module':dict(collections.Counter(q['normalized_module'] for q in qs.values() if q['practice_ready'])),'reserved_holdout':len(heldout),'module_counts':dict(counts),'question_count':len(qs),'occurrences':len(occ),'known_independent_after_doubles_count':len(post5)}
(P/'acceptance'/('release_audit_'+version+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False));raise SystemExit(not all(checks.values()))
