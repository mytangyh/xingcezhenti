import React, {useEffect, useState} from 'react';
import {api, list, type Data} from './api';
import {safeImage,sourceLink} from './logic.mjs';

export function Coverage() {
  const [data,setData]=useState<Data>({}), [year,setYear]=useState(''), [paper,setPaper]=useState(''),
    [module,setModule]=useState(''), [error,setError]=useState(''), [evidence,setEvidence]=useState<Data|null>(null);
  useEffect(()=>{let active=true; setError('');setEvidence(null);
    api(`/coverage?${new URLSearchParams({year,paper_type:paper,module})}`).then(d=>{if(active)setData(d)}).catch(e=>{if(active)setError(e.message)});
    return ()=>{active=false};
  },[year,paper,module]);
  return <section className="panel">
    <h1>高频考点与覆盖地图</h1>
    <p>{data.basis}</p><p className="muted">{data.notice}</p>
    <div className="row">
      <label>年份<select value={year} onChange={e=>setYear(e.target.value)}><option value="">全部年份</option>{(data.years||[]).map((s:string)=><option key={s}>{s}</option>)}</select></label>
      <label>考试/卷型来源标签<select value={paper} onChange={e=>setPaper(e.target.value)}><option value="">全部卷型</option>{(data.paper_types||[]).map((s:string)=><option key={s}>{s}</option>)}</select></label>
      <label>模块<select value={module} onChange={e=>setModule(e.target.value)}><option value="">全部模块</option>{['资料分析','判断推理','言语理解与表达','数量关系','政治理论','常识判断','未知'].map(s=><option key={s}>{s}</option>)}</select></label>
    </div>
    {error && <p role="alert">{error}</p>}
    <p>版本：{data.release || '加载中'}</p>
    {data.summary && <div className="coverage-summary">
      <p>全库筛选范围：{data.summary.identities} 个 source-qid 身份 · {data.summary.occurrences} 次出现 · {data.summary.source_groups} 个来源卷名组</p>
      <p>有基础标签 {data.summary.tagged} · AI 深加工 {data.summary.deep_reviewed} · 答案已核验 {data.summary.verified} · 可练 {data.summary.practice_ready}</p>
      <p>答案核验比例 {data.summary.verified_ratio===null?'无分母':(data.summary.verified_ratio*100).toFixed(1)+'%'}；未知年份出现 {data.summary.unknown_year_occurrences} · 未知卷型出现 {data.summary.unknown_type_occurrences}（{data.summary.unknown_type_ratio===null?'无分母':(data.summary.unknown_type_ratio*100).toFixed(2)+'%'}，分母为当前筛选出现次数） · 无来源记录身份 {data.summary.missing_source_identities}</p>
    </div>}
    <h2>基于当前覆盖的补强优先清单</h2>
    {list(data.data_quality_priorities).map((x:Data)=><p key={x.item}><b>{x.item}</b>：{x.action}</p>)}
    <p>先按目标模块顺序，再按来源卷组覆盖和不可练缺口排序；不推断官方考频或涨分。</p>
    <ol>{list(data.gap_priorities).slice(0,10).map((t:Data)=><li key={t.module+t.concept_id}>{t.module} / {t.name}：基础身份 {t.identities}，可练 {t.practice_ready}，缺口 {t.gap}。{t.action}</li>)}</ol>
    <h2>考点覆盖</h2>
    <div style={{overflowX:'auto'}}><table className="coverage-table"><thead><tr><th>模块 / 标签</th><th>身份 / 出现</th><th>来源卷组</th><th>深加工 / 核验 / 可练</th><th>已核验代表题</th></tr></thead><tbody>
      {list(data.topics).map((t:Data)=><tr key={t.module+t.concept_id}><td>{t.module} / {t.name}</td><td>{t.identities} / {t.occurrences}</td><td>{t.source_groups}</td><td>{t.deep_reviewed} / {t.verified} / {t.practice_ready}</td><td>{(t.representative_ids||[]).map((id:string)=><button key={id} onClick={async()=>{try{setError('');setEvidence(await api('/coverage/evidence/'+encodeURIComponent(id)))}catch(e){setError((e as Error).message)}}}>查看 {id}（记曝光）</button>)}{!t.representative_ids?.length && '尚无可公开给练习端的核验代表'}</td></tr>)}
    </tbody></table></div>
    <details><summary>年份 × 卷型身份分布（跨行不可相加为去重总量）</summary>{list(data.slices).map((s:Data)=><p key={s.year+s.paper_type}>{s.year} / {s.paper_type}：{s.identities}</p>)}</details>
    {evidence && <section className="panel"><h2>代表题与原始证据定位</h2><p>{evidence.notice}</p><p>{evidence.question?.stem}</p>
      {list(evidence.question?.assets).map((a:Data)=><img key={a.url} src={safeImage(a.url)} alt="代表题题图" style={{maxWidth:'100%'}}/>)}
      {evidence.question?.material && <p>{evidence.question.material.text}</p>}
      {list(evidence.question?.material?.assets).map((a:Data)=><img key={a.url} src={safeImage(a.url)} alt="材料图" style={{maxWidth:'100%'}}/>)}
      {list(evidence.question?.options).map((o:Data)=><div key={o.option_id}>{o.label}：{o.text}{list(o.assets).map((a:Data)=><img key={a.url} src={safeImage(a.url)} alt="选项图" style={{maxWidth:'100%'}}/>)}</div>)}
      {list(evidence.sources).map((s:Data,i:number)=><p key={i}><code>{s.source_path}:{s.source_line}</code> {s.raw_link_allowed && sourceLink(s) && <a href={sourceLink(s)} target="_blank" rel="noreferrer">查看原始来源（可能含解析）</a>} · commit {s.source_commit} · 卷组 {s.paper_id}</p>)}
    </section>}
  </section>
}
