"""Independent read-only baseline audit; output only under acceptance/."""
import collections, hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'xingce_project'; A=ROOT/'xingce_analysis'
expected={'政治理论':2305,'常识判断':9163,'言语理解与表达':16000,'数量关系':6448,'判断推理':16859,'资料分析':8115}
counts=collections.Counter(); ids=set(); qids=set(); special=[]; errors=[]; n=0
for line in (A/'records.jsonl').open():
 r=json.loads(line);n+=1;counts[r['module']]+=1;qids.add(r['qid'])
 if r['occurrence_id'] in ids:errors.append('duplicate_occurrence:'+r['occurrence_id'])
 ids.add(r['occurrence_id'])
 if r['qid'] in ('5445878','5893530') or (r['year']==2026 and r['paper_type']=='地市' and r['module']=='判断推理' and r['is_national']):
  special.append({k:r.get(k) for k in ('qid','source_local_number','source_path','source_line','module','material_binding_status','candidate_material_number')})
 if not r.get('source_path') or not r.get('source_line') or r.get('source_commit')!='278984401124db40da5163a31275b8deb9c282f4':errors.append('source_missing:'+r['occurrence_id'])
summary=json.loads((A/'v2/index/coverage_summary.json').read_text())
checks={'occurrences_58890':n==58890,'source_qids_27473':len(qids)==27473,'module_counts':dict(counts)==expected,'occurrence_unique':len(ids)==n,'source_locator':not errors,'status_sum':sum(summary['qid_status'].values())==27473}
git=subprocess.run(['git','status','--porcelain'],cwd=ROOT/'repos/xingcezhenti',capture_output=True,text=True)
checks['source_repo_clean']=git.returncode==0 and not git.stdout.strip()
out={'scope':'read-only structural/source audit, not semantic/answer/human acceptance','checks':checks,'module_counts':dict(counts),'occurrences':n,'qids':len(qids),'special_regression_source_records':special,'errors':errors,'records_sha256':hashlib.sha256((A/'records.jsonl').read_bytes()).hexdigest(),'classification_not_deep_count':summary['qid_status'],'formal_human_approved_cards_evidenced':0,'user_transfer_attempts_evidenced':0}
(P/'acceptance/baseline_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'checks':checks,'special_cases':len(special)},ensure_ascii=False))
raise SystemExit(0 if all(checks.values()) else 1)
