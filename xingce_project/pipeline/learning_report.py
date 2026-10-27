"""Private evidence inventory. Reuses frozen annotations; no new approval/review."""
import argparse,json,sqlite3
from pathlib import Path
from xingce_project.apps.workbench.backend.coverage import read_index,build_coverage
from .provenance import is_independent_annotation
from .release import validate_release,digest

def report(release):
 release=Path(release);manifest=validate_release(release)
 with sqlite3.connect((release/'content.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as c:
  index=read_index(c);coverage=build_coverage(index)
  annotations=[json.loads(r[0]) for r in c.execute('SELECT data FROM annotations')]
  annotations={a['question_id']:a for a in annotations if is_independent_annotation(a)}
 evidence=[]
 for topic in coverage['gap_priorities']:
  candidates=[]
  for qid in topic['representative_ids']:
   q=index['questions'][qid];a=annotations.get(qid,{})
   candidates.append(dict(question_id=qid,revision=q['revision'],source_refs=q.get('source_refs',[]),
     annotation_id=a.get('annotation_id'),method_card_ids=a.get('method_card_ids',[]),
     method_evidence={k:a[k] for k in ('steps','expressions','minimal_exam_route','reasoning_steps','evidence_refs','variable_sources','review_scope') if a.get(k)},
     transfer_candidate=not q.get('prior_public_example'),exposure_status=q.get('exposure_status','not_assessed'),
     notice='复用既有AI证据；非本轮新增核验。未接入真实个人曝光历史，不宣称真正未见。'))
  evidence.append(dict(module=topic['module'],concept_id=topic['concept_id'],name=topic['name'],gap=topic['gap'],candidates=candidates))
 return dict(release=manifest['version'],manifest_sha256=digest(release/'manifest.json'),coverage=coverage,
             evidence_inventory=evidence,new_reviewed_identities=0,new_cards=0,human_approvals=0,
             limitations=['来源卷名组不是独立考试频率','候选引用来自已有冻结输入；未新增题目判断或批准','实际用户迁移作答未完成','本轮没有对图片内容进行新核验；不得把资产可加载当作图像语义复核'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('xingce_project/pipeline/runtime/learning_gap_report.json'));a=p.parse_args()
 result=report(a.release);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'output':str(a.output),'summary':result['coverage']['summary'],'new_reviewed_identities':0},ensure_ascii=False))
