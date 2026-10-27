import sys
"""Regression for independently discovered prose-vs-calculation defects.
Does not claim every prose numeral is mechanically proven.
"""
import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parents[1];path=(Path(sys.argv[1]) if len(sys.argv)>1 else P/'content_review')/'annotations.jsonl';rows={r['qid']:r for r in map(json.loads,path.open())}
expected={'19526212':['103.9'],'19283760':['11.87'],'19283962':['642','54.92'],'5445759':['22.3','2.79'],'19283908':['98.98'],'19526443':['74.44'],'5445854':['150.5'],'19526368':['27.1'],'5445932':['3.15']}
checks={qid:all(x in rows[qid]['explanation'].split('\n')[0] for x in nums) for qid,nums in expected.items()}
checks['5445854_no_false_dispute']=rows['5445854']['answer_status']=='verified' and rows['5445854']['proposed_answer']=='D' and 'A/D多真冲突' not in rows['5445854']['explanation']
out={'annotations_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'questions_at_run':len(rows),'checks':checks,'scope':'全190条首段已由AI逐条比对表达式结果；此脚本仅对已发现文字错误固定回归，非人工审签、非所有语义自动证明'}
(P/'acceptance/explanation_number_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False));raise SystemExit(not all(checks.values()))
