"""Freeze candidate identities without exposing question/answer payload.
Material binding/answer quality still must be checked before a real blind test.
"""
import json,re,hashlib,collections
from pathlib import Path
P=Path(__file__).resolve().parents[1];A=P.parent/'xingce_analysis'
def h(s):return hashlib.sha256(re.sub(r'\s+','',s).encode()).hexdigest()
records=collections.defaultdict(list)
for l in (A/'records.jsonl').open():
 r=json.loads(l);records[r['qid']].append(r)
materials={(r['source_path'],r['source_material_number']):h(r['raw_text']) for r in map(json.loads,(A/'materials_candidates.jsonl').open())}
excluded=set()
for file in [A/'deliverables/行测高收益知识与解题方法手册_20261026.md',A/'quant_methods.md',A/'reasoning_language.md']:
 if file.exists():excluded.update(re.findall(r'\b\d{6,9}\b',file.read_text()))
for file in [P/'content_review/questions.jsonl']:
 if file.exists():excluded.update(r['question_id'].removeprefix('q-') for r in map(json.loads,file.open()))
# These reviewed candidates may have entered generation, so reserve different identities conservatively.
for r in map(json.loads,(A/'v2/index/canonical_topic_index.jsonl').open()):
 if r.get('status')=='semantic_reviewed':excluded.add(r['qid'])
# Conservative cluster closure: candidate overlap may over-exclude but must not leak holdout.
cluster_file=P/'releases/content-v1-reviewed/duplicate_candidates.jsonl'
cluster_groups=[{x.removeprefix('q-') for x in r['question_ids']} for r in map(json.loads,cluster_file.open())] if cluster_file.exists() else []
changed=True
while changed:
 before=len(excluded)
 for ids in cluster_groups:
  if ids & excluded:excluded.update(ids)
 changed=len(excluded)!=before
matkeys={qid:{materials[(r['source_path'],r['candidate_material_number'])] for r in rs if (r['source_path'],r['candidate_material_number']) in materials} for qid,rs in records.items()}
fp={qid:h(json.dumps([rs[0]['stem'],rs[0]['options']],ensure_ascii=False,sort_keys=True)) for qid,rs in records.items()}
excluded_mat=set().union(*(matkeys[q] for q in excluded if q in matkeys));excluded_fp={fp[q] for q in excluded if q in fp}
blocked={q for q in records if q in excluded or matkeys[q]&excluded_mat or fp[q] in excluded_fp}
quota={'资料分析':35,'判断推理':25,'言语理解与表达':15,'数量关系':5};selected=[];group_taken=set();fp_taken=set();available=collections.Counter()
def rank(q):
 r=sorted(records[q],key=lambda r:(not r['is_national'],-(r['year'] or 0),r['source_path']))[0]
 return (not r['is_national'],-(r['year'] or 0),r['paper_type']!='行政执法',q)
for module,n in quota.items():
 candidates=[q for q,rs in records.items() if q not in blocked and rs[0]['module']==module and len(rs[0]['options'])==4]
 available[module]=len(candidates);chosen=[]
 for q in sorted(candidates,key=rank):
  if q in chosen or fp[q] in fp_taken:continue
  # Reserve complete candidate group; ambiguous oversized groups not selected.
  siblings={x for x in candidates if matkeys[q] and matkeys[x]&matkeys[q]} if matkeys[q] else {q}
  if any(x in blocked for x in siblings) or len(chosen)+len(siblings)>n:continue
  if matkeys[q]&group_taken:continue
  for x in sorted(siblings):
   if fp[x] in fp_taken:continue
   chosen.append(x);fp_taken.add(fp[x]);group_taken.update(matkeys[x])
  if len(chosen)==n:break
 selected.extend({'question_id':'q-'+q,'source_qid':q,'module':module,'fingerprint':fp[q],'material_fingerprints':sorted(matkeys[q]),'year':records[q][0]['year'],'paper_type':records[q][0]['paper_type'],'status':'frozen_candidate_not_yet_validated','holdout_reserved':True} for q in chosen)
counts=collections.Counter(x['module'] for x in selected)
out=P/'acceptance/holdout';out.mkdir(exist_ok=True)
(out/'reserved_ids.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in selected))
(out/'questions.jsonl').write_text(''.join(json.dumps({'question_id':x['question_id'],'holdout_reserved':True,'holdout_status':'frozen_candidate_not_yet_validated'},ensure_ascii=False)+'\n' for x in selected))
report={'status':'candidate_freeze_not_personal_test_complete','target':quota,'actual':dict(counts),'count':len(selected),'excluded_direct_count':len(excluded),'excluded_by_material_or_exact_stem_options_count':len(blocked),'candidate_pool':dict(available),'cluster_source':str(cluster_file.relative_to(P)),'checks':{'no_candidate_cluster_overlap':not any(ids & {x['source_qid'] for x in selected} and ids & excluded for ids in cluster_groups),'counts_match':dict(counts)==quota,'no_direct_overlap':not any(x['source_qid'] in excluded for x in selected),'no_material_overlap':not any(set(x['material_fingerprints'])&excluded_mat for x in selected),'no_exact_prompt_overlap':not any(x['fingerprint'] in excluded_fp for x in selected)},'limitations':['未做用户首次作答，未声称从未被用户在外部看过','材料候选等价采用空白归一正文指纹；语义近似簇待pipeline进一步确认','题面完整性、材料绑定和答案必须在测试前单独验收；当前只冻结身份，不发布练习','不得用这些题归纳卡片/提示示例；后台需排除默认推荐和导出']}
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
