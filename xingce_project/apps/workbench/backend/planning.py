"""Deterministic, explained planning; never a calibrated ability/score model."""
import json
import statistics
from collections import defaultdict
from .coverage import PRIORITY, UNKNOWN

def plan(index, coverage, attempts, exposures, events, due, settings, now, budget=40):
    qs = index['questions']
    seen = {a['question_id'] for a in attempts} | set(exposures)
    # Alias chains must close transitively, including retired IDs.
    changed = True
    while changed:
        changed = False
        for a in index['aliases']:
            old = a.get('old_id') or a.get('from_id') or a.get('source_id')
            new = a.get('new_id') or a.get('to_id') or a.get('target_id')
            if old and new and (old in seen or new in seen) and not {old,new} <= seen:
                seen.update(x for x in (old,new) if x); changed = True
    seen_materials = {qs[i].get('material_id') for i in seen if i in qs}-{None}
    seen_families = {qs[i].get('variant_family_id') for i in seen if i in qs}-{None}
    protected = {mid for q in qs.values() if q.get('holdout_reserved') for mid in
                 [q.get('material_id')]+q.get('candidate_material_ids',[]) if mid}
    eligible = {i:q for i,q in qs.items() if q.get('practice_ready') and q.get('answer_status') == 'verified'
                and not q.get('holdout_reserved') and q.get('material_id') not in protected}
    def novelty(q):
        return not(q['question_id'] in seen or q.get('prior_public_example') or q.get('material_id') in seen_materials
                   or q.get('variant_family_id') in seen_families)
    first = {}
    for a in sorted(attempts,key=lambda a:(a['created'],a['id'])):
        if a['status'] == 'submitted' and a['question_id'] not in first:
            first[a['question_id']] = a
    attempt_counts=defaultdict(int)
    for a in attempts:attempt_counts[(a["session_id"],a["question_id"])]+=1
    times = defaultdict(float)
    for e in events:
        if e['type'] == 'question_time' and e.get('duration'):
            times[(e['session_id'],e['question_id'])] += e['duration']
    evidence = defaultdict(list)
    for qid,a in first.items():
        if qid not in qs: continue
        g = json.loads(a['grade'] or '{}')
        # Retain source-only/unknown as missing evidence rather than false scores.
        if g.get('answer_status') != 'verified' or g.get('correct') is None or g.get('question_revision') != qs[qid].get('revision'): continue
        for cid in qs[qid].get('_base_concept_ids') or [UNKNOWN]: evidence[(qs[qid]['normalized_module'],cid)].append((a,g))
    topic_map = {(r['module'],r['concept_id']):r for r in coverage['topics']}
    def metrics(q):
        rows = [r for cid in q.get('_base_concept_ids') or [UNKNOWN] for r in evidence[(q['normalized_module'],cid)]]
        rows = list({a['id']:(a,g) for a,g in rows}.values())
        n=len(rows); correct=sum(g['correct'] is True for a,g in rows)
        uncertain=sum(bool(a['hint'] or a['guessed']) for a,g in rows)
        durations=[times[(a['session_id'],a['question_id'])] for a,g in rows if not a.get('interrupted') and attempt_counts[(a['session_id'],a['question_id'])]==1 and times[(a['session_id'],a['question_id'])]>0]
        seconds=statistics.median(durations) if durations else None
        freq=max((topic_map.get((q['normalized_module'],cid),{}).get('source_groups',0) for cid in q.get('_base_concept_ids') or [UNKNOWN]),default=0)
        # Small samples are explicitly descriptive, not diagnoses.
        score=(2*(n-correct)/n+uncertain/n if n else 1)+min(freq,100)/100+(0.5 if seconds and seconds>120 else 0)
        return dict(first_count=n,first_correct=correct,first_accuracy=correct/n if n else None,
                    hint_or_guess_count=uncertain,median_question_seconds=seconds,source_groups=freq,
                    rank_score=round(score,3),estimated_seconds=max(60,min(300,seconds or 120)))
    remaining=budget*60*0.8 # explicit review/rest reserve
    items=[]; used=set()
    due_ids=list(dict.fromkeys(r['question_id'] for r in due if r['question_id'] in eligible))
    if due_ids and settings.get('due',{}).get('skip_until',0)<=now:
        selected=[]
        for qid in due_ids[:settings.get('due',{}).get('count',5)]:
            cost=metrics(eligible[qid])['estimated_seconds']
            if cost>remaining: continue
            remaining-=cost;selected.append(qid);used.add(qid)
        if selected: items.append(dict(id='due',title='到期纠错',count=len(selected),question_ids=selected,
                                      available_count=len(due_ids),reason='按你设置的到期日期优先；属于已做复习，不计新迁移',kind='review',estimated_seconds=sum(metrics(eligible[i])['estimated_seconds'] for i in selected)))
    for module in sorted({q['normalized_module'] for q in eligible.values()},key=lambda m:(PRIORITY.get(m,4),m)):
        setting=settings.get('module:'+module,{})
        if setting.get('skip_until',0)>now:continue
        candidates=[q for qid,q in eligible.items() if q['normalized_module']==module and qid not in used]
        candidates.sort(key=lambda q:(not novelty(q),-metrics(q)['rank_score'],q['question_id']))
        selected=[]; costs=0
        for q in candidates:
            cost=metrics(q)['estimated_seconds']
            if cost>remaining:continue
            if len(selected)>=setting.get('count',5):break
            selected.append(q);used.add(q['question_id']);remaining-=cost;costs+=cost
        if not selected:continue
        fresh=sum(novelty(q) for q in selected)
        evidence_rows=[dict(question_id=q['question_id'],concept_ids=q.get('concept_ids',[]),candidate_unseen=novelty(q),**metrics(q)) for q in selected]
        items.append(dict(id='module:'+module,title=module+'专题',module=module,count=len(selected),available_count=len(candidates),
                          question_ids=[q['question_id'] for q in selected],estimated_seconds=costs,candidate_unseen_count=fresh,
                          repeat_count=len(selected)-fresh,evidence=evidence_rows,
                          reason='模块顺序先验 → 未记录曝光候选 → 首次错误/提示猜测、考点覆盖、来源卷组覆盖代理及耗时；同分按身份排序。'+('无该考点首次可判分记录，使用透明冷启动。' if not any(r['first_count'] for r in evidence_rows) else '首次记录为描述性证据，小样本不作能力定论。')))
    return dict(items=items,budget_minutes=budget,estimated_minutes=round((budget*60*0.8-remaining)/60,1),reserve_minutes=budget*0.2,
                due_count=len(due_ids),due_unavailable_count=len({r['question_id'] for r in due}-set(eligible)),
                cold_start=not any(evidence.values()),notice='未建立个人基线时使用模块顺序及覆盖冷启动。耗时缺失按每题120秒计划，预留20%复盘；可调题量/跳过，超时可暂停或结束。未记录曝光候选不保证真正未见；同材料/变式/别名已见不算新迁移。排序分不是官方分值、能力概率或预计涨分。')
