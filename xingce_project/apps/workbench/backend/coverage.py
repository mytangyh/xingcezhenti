"""Read-only whole-index coverage. Source groups are NOT independent exams."""
import json
from collections import defaultdict

UNKNOWN = '未知'
PRIORITY = {'资料分析': 0, '判断推理': 1, '言语理解与表达': 2, '言语理解': 2, '数量关系': 3}

def label(value):
    return UNKNOWN if value in (None, '', '未区分', 'unknown', '未知', '未标注') else str(value)

def read_index(c):
    def rows(table):
        if not c.execute('SELECT 1 FROM sqlite_master WHERE name=?', (table,)).fetchone():
            return []
        return [json.loads(r[0]) for r in c.execute('SELECT data FROM '+table)]
    questions = {}
    for data, module in c.execute('SELECT data,module FROM questions'):
        q = json.loads(data)
        q['normalized_module'] = q.get('normalized_module') or module or UNKNOWN
        questions[q['question_id']] = q
    from xingce_project.pipeline.provenance import is_independent_annotation
    annotations=rows('annotations')
    reviewed = {a['question_id'] for a in annotations if is_independent_annotation(a)}
    base={a['question_id']:a.get('concept_ids',[]) for a in annotations if a.get('status')=='reference_not_human_approved'}
    for qid,q in questions.items():q['_base_concept_ids']=base.get(qid,q.get('concept_ids',[]))
    return dict(reviewed=reviewed, questions=questions, papers={p['paper_id']: p for p in rows('papers')},
                occurrences=rows('occurrences'), concepts={p['concept_id']: p for p in rows('concepts')},
                aliases=rows('id_aliases'))

def build_coverage(index, year='', paper_type='', module=''):
    qs, papers = index['questions'], index['papers']
    occurrences = [o for o in index['occurrences'] if o.get('question_id') in qs and
                   (not year or label(papers.get(o.get('paper_id'),{}).get('exam_year_label')) == year) and
                   (not paper_type or label(papers.get(o.get('paper_id'),{}).get('paper_type')) == paper_type)]
    missing=set(qs)-{o['question_id'] for o in index['occurrences']}
    ids = {o['question_id'] for o in occurrences} if year or paper_type else set(qs)
    if year in ('',UNKNOWN) and paper_type in ('',UNKNOWN):ids.update(missing)
    ids = {qid for qid in ids if not module or qs[qid]['normalized_module'] == module}
    occurrences = [o for o in occurrences if o['question_id'] in ids]
    by_q = defaultdict(list)
    for o in occurrences: by_q[o['question_id']].append(o)
    protected = {mid for q in qs.values() if q.get('holdout_reserved') for mid in
                 [q.get('material_id')]+q.get('candidate_material_ids',[]) if mid}
    def ready(q):
        return bool(q.get('practice_ready') and q.get('answer_status') == 'verified' and
                    not q.get('holdout_reserved') and q.get('material_id') not in protected)
    def summarize(qids):
        os = [o for qid in qids for o in by_q[qid]]
        ps = {o.get('paper_id') for o in os if o.get('paper_id') in papers}
        # Multiple files/modules of the same source name cannot increase this proxy.
        groups = {label(papers[p].get('name')) for p in ps}
        verified = sum(qs[i].get('answer_status') == 'verified' for i in qids)
        return dict(identities=len(qids), occurrences=len(os), source_groups=len(groups),
                    missing_source_identities=len(set(qids)&missing),
                    question_source_pairs=len({(o['question_id'], label(papers.get(o.get('paper_id'),{}).get('name'))) for o in os}),
                    tagged=sum(bool(qs[i].get('_base_concept_ids')) for i in qids),
                    deep_reviewed=sum(i in index['reviewed'] for i in qids),
                    deep_tagged=sum(i in index['reviewed'] and bool(qs[i].get('concept_ids')) for i in qids),
                    verified=verified, verified_ratio=verified/len(qids) if qids else None,
                    practice_ready=sum(ready(qs[i]) for i in qids),
                    unknown_year_ratio=sum(label(papers.get(o.get('paper_id'),{}).get('exam_year_label')) == UNKNOWN for o in os)/len(os) if os else None,
                    unknown_type_ratio=sum(label(papers.get(o.get('paper_id'),{}).get('paper_type')) == UNKNOWN for o in os)/len(os) if os else None,
                    unknown_year_occurrences=sum(label(papers.get(o.get('paper_id'),{}).get('exam_year_label')) == UNKNOWN for o in os),
                    unknown_type_occurrences=sum(label(papers.get(o.get('paper_id'),{}).get('paper_type')) == UNKNOWN for o in os))
    topics = defaultdict(set)
    for qid in ids:
        q = qs[qid]
        for cid in q.get('_base_concept_ids') or [UNKNOWN]: topics[(q['normalized_module'],cid)].add(qid)
    topic_rows = []
    for (mod,cid),qids in topics.items():
        row = dict(module=mod, concept_id=cid, name=index['concepts'].get(cid,{}).get('name',cid), **summarize(qids))
        row['gap'] = row['identities']-row['practice_ready']
        row['action'] = ('先核对基础标签及语义归并；当前标签不可练数量不等于同考点真实短缺' if cid==UNKNOWN or '候选' in row['name'] else '核验题面/材料及方法证据；人工审批和真实迁移仍待完成')
        row['representative_ids'] = sorted(i for i in qids if ready(qs[i]))[:3]
        topic_rows.append(row)
    topic_rows.sort(key=lambda r:(PRIORITY.get(r['module'],4),-r['source_groups'],-r['gap'],r['concept_id']))
    slices = defaultdict(set)
    for o in occurrences:
        p = papers.get(o.get('paper_id'),{})
        slices[(label(p.get('exam_year_label')),label(p.get('paper_type')))].add(o['question_id'])
    if ids&missing:slices[(UNKNOWN,UNKNOWN)].update(ids&missing)
    return dict(summary=summarize(ids), topics=topic_rows,
                data_quality_priorities=[{'item':'来源卷型确认','occurrences':summarize(ids)['unknown_type_occurrences'],'action':'按原文件或官方卷名的明确证据建立可追溯映射候选；人工核对后才更新事实，不以NLP推断填充未知。'}, {'item':'基础/细标签语义核对','action':'标签名称相近不自动合并；跨考点行不可相加当身份总数。'}],
                slices=[dict(year=y,paper_type=t,identities=len(qids)) for (y,t),qids in sorted(slices.items())],
                years=sorted({label(p.get('exam_year_label')) for p in papers.values()}|{UNKNOWN},reverse=True),
                paper_types=sorted({label(p.get('paper_type')) for p in papers.values()}|{UNKNOWN}),
                gap_priorities=[r for r in topic_rows if r['gap']],
                basis='source-qid 身份；非语义完全去重。出现次数≠考试频率。来源卷名组仅作覆盖代理，非独立考试数。',
                notice='按原基础标注保持全库可比分母，深加工标签不覆盖基础对比；基础标签可能为规则/AI候选；深加工、答案核验与可练分别计数；核验不等于人工批准。候选标签与语义细标签不自动归并，零可练只指该标签。未知字段不推断。年份/卷型按来源标签筛选，原卷完整性未核实。')
