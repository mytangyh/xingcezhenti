#!/usr/bin/env python3
"""Deterministic Markdown/Obsidian export from immutable canonical cards."""
import argparse,hashlib,json,re
from pathlib import Path
from urllib.parse import quote

LABELS={'boundaries':'适用边界','boundary':'适用边界','calculation_expression':'计算式','case':'情形','confusions':'易混点','counterexample':'反例','evidence_qids':'例题编号','exam_method':'考场做法','exercise_id':'练习编号','expected_answer':'答案','id':'编号','origin':'出处','prompt':'题目','qid':'题号','source':'出处','steps':'步骤','text':'说明','title':'标题','trigger':'识别信号'}
STATUS={'evidence_ready_pending_human_and_transfer_validation':'例题证据已整理，待人审与真实迁移验证','needs_evidence':'仍需补充证据','verified':'AI 已核验（非人工审批）','source_only':'仅保留来源答案','disputed':'存在争议','unresolved':'尚未解决'}
BLOCKERS={'cross_source_diversity_missing':'跨来源证据不足','fewer_than_three_verified_independent_questions':'不足三道已核验独立例题','human_card_review_pending':'待人工审卡','independent_visual_or_logic_audit_pending':'待独立图像或逻辑复核','knowledge_reference_not_method_card':'知识参考不等于方法卡','non_induction_transfer_candidate_missing':'缺少未参与归纳的迁移候选','nonblind_evidence_requires_independent_audit':'非盲证据尚需独立复核','real_user_transfer_test_pending':'待真实用户迁移测试','temporal_and_full_answer_review_pending':'待时效及完整答案复核','transfer_candidate_validation_pending':'迁移候选待验证'}
def render_value(v):
 if isinstance(v,str):return {'original_AI_authored':'AI 原创示例（非真题）'}.get(v,v)
 if isinstance(v,list):return '\n'.join('- '+render_value(x).replace('\n','\n  ') for x in v)
 if isinstance(v,dict):return '\n'.join(f'**{LABELS.get(k,k)}**：{render_value(x)}' for k,x in v.items() if k not in ('human_reviewed','user_attempt_status'))
 return str(v)

def group(c):
 i=c['card_id'].split('-')[-1]
 if i.startswith('D'):return '01-资料分析'
 if i.startswith('Q'):return '04-数量关系'
 if i.startswith('K'):return '05-知识参考'
 return '03-言语理解' if int(i[1:])<=8 else '02-判断推理'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--release',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 cards=[json.loads(l) for l in (a.release/'cards.jsonl').read_text().splitlines()]
 m=json.loads((a.release/'manifest.json').read_text());a.output.mkdir(parents=True,exist_ok=True)
 intro=f'''# 行测 50 张参考卡：阅读入口\n\n版本：{m['version']}。直接从最终 cards.jsonl 导出，不另改写方法。\n\n**全部为 AI 整理参考，未通过人工正式审批；正式卡 0，真实用户迁移成绩 0。** 40 张方法参考卡、10 张知识参考卡；知识参考仍需证据补全。仅供私人学习，源题和图片许可未确证。\n\n可用任何 Markdown 阅读器阅读；也可在 Obsidian 中选择“打开文件夹作为仓库”，打开本目录。无需运行工作台。来源链接需联网；正文方法可离线阅读。\n\n“迁移候选”不表示用户未见过或已完成练习；原创迁移示例不是密封真题评测。此包不含个人评测密钥、答案表或父题映射。\n\n'''
 combined=[intro];index=[intro]
 labels={'trigger':'识别信号','steps':'解题步骤','boundary':'适用边界','boundaries':'边界补充','example':'示例','skip':'止损条件','v2_addendum':'补充说明','refinement_notes':'细化说明','counterexamples':'反例','transfer_exercise':'原创迁移练习（非密封测验）'}
 for g in ['01-资料分析','02-判断推理','03-言语理解','04-数量关系','05-知识参考']:
  subset=sorted([c for c in cards if group(c)==g],key=lambda c:c['card_id']);index.append(f'## {g[3:]}（{len(subset)} 张）\n');combined.append(f'\n# {g[3:]}\n')
  for c in subset:
   fn=c['card_id']+'.md';title=c['title'];lines=[f'# {title}\n',f"卡号：{c['card_id']}｜AI 参考，待人工验收｜状态：{STATUS.get(c.get('evidence_readiness'),'待确认')}\n"]
   if c.get('body_markdown'):lines.append(c['body_markdown'])
   for key,label in labels.items():
    if c.get(key):lines += [f'\n## {label}\n',render_value(c[key])]
   lines.append('\n## 已记录例题与来源\n')
   evidence=c.get('review_evidence',[])
   if not evidence:lines.append('本卡暂无满足审核要求的独立例题证据；正文已有来源仅供追溯，不表示证据门槛通过。')
   for e in evidence:
    lines.append(f"- {e['question_id']}：{e.get('stem_preview','')}；答案状态：{STATUS.get(e.get('answer_status'),'待确认')}")
    for r in e.get('source_refs',[]):
     url='https://github.com/mytangyh/xingcezhenti/blob/'+r['source_commit']+'/'+quote(r['source_path'])+'#L'+str(r['source_line'])
     lines.append(f"  - [{r['source_path']} · L{r['source_line']}]({url})")
   lines += ['\n## 迁移与审核说明\n','真实用户迁移测试：未完成；人工正式审批：未完成。候选题是否此前见过未知，不构成成绩。',f"规范数据记录的迁移候选数：{len(c.get('transfer_candidates',[]))}。此阅读版不展开候选答案，不代替工作台测验。",'待完成门槛：'+ '；'.join(BLOCKERS.get(x,x) for x in c.get('promotion_blockers',[]))]
   text=re.sub(r'\n{3,}','\n\n','\n\n'.join(lines)+'\n');folder=a.output/g;folder.mkdir(exist_ok=True);(folder/fn).write_text(text,encoding='utf-8');index.append(f'- [{title}]({g}/{fn})\n');combined.append(text)
 (a.output/'开始阅读.md').write_text(''.join(index),encoding='utf-8')
 (a.output/'行测50张参考卡-合订本.md').write_text(re.sub(r'\n{3,}','\n\n','\n'.join(combined)),encoding='utf-8')
 # Reviewed handoff templates accompany the deterministic content export.
 docs=Path(__file__).resolve().parents[1]/'acceptance/user_docs'
 (a.output/'人工卡审记录.md').unlink(missing_ok=True)
 for name in ('人工卡审表.md','真实迁移测验操作说明.md','当前完成与待办.md'):
  (a.output/name).write_bytes((docs/name).read_bytes())
 record={'release':m['version'],'cards':len(cards),'canonical_cards_sha256':hashlib.sha256((a.release/'cards.jsonl').read_bytes()).hexdigest(),'files':{p.relative_to(a.output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(a.output.rglob('*.md'))}}
 (a.output/'导出校验.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'cards':len(cards),'files':len(record['files'])},ensure_ascii=False))
if __name__=='__main__':main()
