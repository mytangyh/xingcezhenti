import { Coverage } from './Coverage';
import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, list, type Data } from "./api";
import {
  ERROR_KINDS,
  formatTime,
  safeImage,
  safeLink,
  sourceLink,
  statusLabel,
  canPause,
  optionLabels,
  buildSearchQuery,
} from "./logic.mjs";
import "./style.css";

const NAV = [
  ["today", "今日精练"],
  ["coverage", "全库覆盖"],
  ["train", "继续训练"],
  ["cards", "方法 / 题库"],
  ["assessment", "个人迁移测验"],
  ["due", "错题复习"],
  ["data", "进度与数据"],
];
function Status({ value }: { value?: string }) {
  if (value && !["source_only", "verified", "disputed", "unresolved"].includes(value))
    value = "source_only";
  return (
    <span
      className={`badge ${value === "verified" ? "good" : value === "disputed" ? "bad" : ""}`}
    >
      {statusLabel(value || "source_only")}
    </span>
  );
}
function Text({ value }: { value: any }) {
  return (
    <div className="prose">
      {typeof value === "string"
        ? value
        : value
          ? JSON.stringify(value, null, 2)
          : "暂无内容"}
    </div>
  );
}
function Images({
  items,
  onZoom,
}: {
  items: any;
  onZoom: (s: string) => void;
}) {
  return (
    <div className="images">
      {list(items).map((a, i) => {
        const src = safeImage(a.url);
        return src ? (
          <button
            className="image-button"
            key={i}
            onClick={() => onZoom(src)}
            title="放大原图"
          >
            <img
              src={src}
              alt={a.alt || a.role || `题目图片 ${i + 1}`}
              loading="lazy"
            />
            <span>点击放大</span>
          </button>
        ) : (
          <p className="muted" key={i}>
            图片资源未提供安全的本地地址
          </p>
        );
      })}
    </div>
  );
}

function CardBody({ card }: { card: Data }) {
  const fields = [
    ["触发条件", card.trigger],
    ["解题步骤", card.steps || card.method],
    ["适用边界", card.boundary],
    ["辨析示例", card.example],
    ["何时暂时跳过", card.skip],
    ["补充辨析", card.v2_addendum?.text],
  ];
  return (
    <>
      {fields.some(([, v]) => v) ? (
        fields
          .filter(([, v]) => v)
          .map(([k, v]) => (
            <section key={k}>
              <h3>{k}</h3>
              <Text value={v} />
            </section>
          ))
      ) : (
        <Text
          value={
            card.content ||
            card.body ||
            card.markdown ||
            card.summary ||
            "内容尚未提供"
          }
        />
      )}
      <p className="muted">
        {card.approval_status === "ai_reference_pending_human"
          ? "AI 辅助方法草稿 · 待人工验收；不属于正式已核验方法。"
          : card.status}
      </p>
      {Array.isArray(card.source_files) && (
        <>
          <h3>来源定位</h3>
          <ul>
            {card.source_files.map((s: string) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function App() {
  const [budget,setBudget]=useState(40), [planInfo,setPlanInfo]=useState<Data>({});
  const budgetRef=useRef(budget);budgetRef.current=budget;
  useEffect(()=>{let active=true;api(`/today?budget_minutes=${budget}`).then(p=>{if(active){setPlanInfo(p);setTodayTasks(list(p.items));}}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[budget]);
  const [page, setPage] = useState("today"),
    [catalog, setCatalog] = useState<Data>({}),
    [sessions, setSessions] = useState<Data[]>([]),
    [due, setDue] = useState<Data[]>([]),
    [stats, setStats] = useState<Data>({}),
    [todayTasks, setTodayTasks] = useState<Data[]>([]);
  const [session, setSession] = useState<Data | null>(null),
    [items, setItems] = useState<Data[]>([]),
    [attempts, setAttempts] = useState<Data[]>([]),
    [index, setIndex] = useState(0),
    [review, setReview] = useState<Data | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [zoom, setZoom] = useState(""),
    [module, setModule] = useState("资料分析"),
    [mode, setMode] = useState("group"),
    [count, setCount] = useState(5),
    [allowSource, setAllowSource] = useState(false);
  const [cards, setCards] = useState<Data[]>([]),
    [query, setQuery] = useState(""),
    [cardModule, setCardModule] = useState(""),
    [statusFilter, setStatusFilter] = useState(""),
    [selectedCard, setSelectedCard] = useState<Data | null>(null);
  const [assessmentPacks, setAssessmentPacks] = useState<Data[]>([]),
    [assessmentConfirm, setAssessmentConfirm] = useState(false),
    [assessmentSeen, setAssessmentSeen] = useState(false),
    [assessmentHint, setAssessmentHint] = useState(false);
  const [searchObject, setSearchObject] = useState("cards"),
    [searchYear, setSearchYear] = useState(""),
    [searchPaperType, setSearchPaperType] = useState(""),
    [searchConcept, setSearchConcept] = useState(""),
    [searchAllowSource, setSearchAllowSource] = useState(false),
    [searchFilters, setSearchFilters] = useState<Data>({}),
    [questionResults, setQuestionResults] = useState<Data[]>([]),
    [searchTotal, setSearchTotal] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0),
    [paused, setPaused] = useState(false),
    [flags, setFlags] = useState<string[]>([]),
    [errorKind, setErrorKind] = useState(ERROR_KINDS[0]),
    [notes, setNotes] = useState(""),
    [interval, setIntervalDays] = useState(1),
    [guessed, setGuessed] = useState(false),
    [hint, setHint] = useState(false);
  const [importPath, setImportPath] = useState(""),
    [userdataPath, setUserdataPath] = useState(""),
    [restorePath, setRestorePath] = useState(""),
    [backups, setBackups] = useState<Data[]>([]),
    [releases, setReleases] = useState<Data[]>([]),
    [reading, setReading] = useState(true);
  const activeRef = useRef({ base: 0, at: Date.now(), paused: false }),
    busyRef = useRef(false),
    saveQueue = useRef(Promise.resolve()),
    sessionRef = useRef<Data | null>(null),
    indexRef = useRef(0),
    itemsRef = useRef<Data[]>([]),
    readingRef = useRef(true),
    lastBeat = useRef(Date.now());
  const current = items[index],
    attempt =
      attempts.find((a) => a.question_id === current?.question_id) || {},
    isSubmitted = attempt?.status === "submitted";
  const modules = (catalog.modules || [])
    .map((m: any) => (typeof m === "string" ? m : m.name || m.module || m.id))
    .filter(Boolean);
  async function work(fn: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  async function refresh() {
    const [c, s, d, st] = await Promise.all([
      api("/catalog"),
      api("/sessions"),
      api("/reviews/due"),
      api("/stats"),
    ]);
    setCatalog(c);
    setSessions(list(s.items));
    setDue(list(d.items));
    setStats(st);
    try {
      const requestedBudget=budgetRef.current;const p=await api(`/today?budget_minutes=${requestedBudget}`);if(requestedBudget===budgetRef.current){setPlanInfo(p);setTodayTasks(list(p.items));}
    } catch (e) {
      setTodayTasks([]);setError((e as Error).message);
    }
  }
  async function loadSession(id: string) {
    const data = await api(`/sessions/${encodeURIComponent(id)}/items`);
    const s =
      data.session || (await api(`/sessions/${encodeURIComponent(id)}`));
    setSession(s);
    sessionRef.current = s;
    setItems(list(data.items));
    itemsRef.current = list(data.items);
    setAttempts(list(data.attempts || s.attempts));
    const restoredIndex = Math.max(
      0,
      Math.min(
        list(data.items).length - 1,
        Number(localStorage.getItem(`xingce.index.${id}`) || 0),
      ),
    );
    setIndex(restoredIndex);
    indexRef.current = restoredIndex;
    const restoredAttempt = list(data.attempts || s.attempts).find(
      (a) => a.question_id === data.items?.[restoredIndex]?.question_id,
    );
    setGuessed(Boolean(restoredAttempt?.guessed));
    setHint(Boolean(restoredAttempt?.hint));
    setReview(null);
    setPage("train");
    localStorage.setItem("xingce.lastSession", id);
    let saved: Data = {};
    try {
      saved = JSON.parse(localStorage.getItem(`xingce.timer.${id}`) || "{}");
    } catch {}
    const serverPaused = Boolean(s.paused) || s.status === "paused";
    const base = Number(
      s.active_seconds ?? s.elapsed_seconds ?? saved.seconds ?? 0,
    );
    activeRef.current = { base, at: Date.now(), paused: serverPaused };
    setElapsed(base);
    setPaused(serverPaused);
    lastBeat.current = Date.now();
    let fs: string[] = [];
    try {
      fs = JSON.parse(localStorage.getItem(`xingce.flags.${id}`) || "[]");
    } catch {}
    setFlags(Array.isArray(fs) ? fs : []);
    const readingNow = Boolean(data.items?.[restoredIndex]?.material) && !list(s.events).some(e=>e.type==='question_time');
    setReading(readingNow);
    readingRef.current = readingNow;
  }
  useEffect(() => {
    work(async () => {
      await refresh();
      const id = localStorage.getItem("xingce.lastSession");
      if (id) {
        try {
          await loadSession(id);
          setPage("today");
        } catch {
          localStorage.removeItem("xingce.lastSession");
        }
      }
    });
  }, []);
  useEffect(() => {
    const timer = window.setInterval(() => {
      const s = sessionRef.current;
      if (!s || ["submitted", "abandoned"].includes(s.status)) return;
      const clock = activeRef.current;
      const seconds =
        clock.base + (clock.paused ? 0 : (Date.now() - clock.at) / 1000);
      setElapsed(seconds);
      localStorage.setItem(
        `xingce.timer.${s.id}`,
        JSON.stringify({ seconds, savedAt: Date.now() }),
      );
      if (Date.now() - lastBeat.current >= 15000 && !clock.paused) {
        const delta = (Date.now() - lastBeat.current) / 1000;
        lastBeat.current = Date.now();
        api(`/sessions/${s.id}/events`, {
          type: readingRef.current ? "reading" : "question_time",
          question_id: readingRef.current
            ? undefined
            : itemsRef.current[indexRef.current]?.question_id,
          duration_seconds: delta,
        }).catch(() =>
          setNotice("计时同步暂未成功；本机已保留计时，作答前请检查连接。"),
        );
      }
    }, 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    function exit() {
      const s = sessionRef.current;
      if (s && !["submitted", "abandoned"].includes(s.status))
        fetch(`/api/sessions/${s.id}/events`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ type: "interrupt" }),
          keepalive: true,
        }).catch(() => {});
    }
    window.addEventListener("pagehide", exit);
    return () => window.removeEventListener("pagehide", exit);
  }, []);
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setZoom("");
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  async function start(ids?: string[], override?: Data) {
    await work(async () => {
      const s = await api("/sessions", {
        mode,
        question_ids: ids,
        module: ids ? undefined : module,
        count,
        allow_source_only: allowSource,
        ...override,
      });
      await loadSession(s.id);
      await refresh();
    });
  }
  function select(option: string) {
    if (
      !attempt.attempt_id ||
      isSubmitted ||
      session?.status === "abandoned" ||
      paused ||
      busy
    )
      return;
    const before = attempt.selected_option_ids || [];
    setAttempts((prev) =>
      prev.map((a) =>
        a.attempt_id === attempt.attempt_id
          ? { ...a, selected_option_ids: [option] }
          : a,
      ),
    );
    const payload = {
      session_id: session!.id,
      question_id: current.question_id,
      attempt_id: attempt.attempt_id,
      selected_option_ids: [option],
      action: "save",
      guessed,
      hint_used: hint,
    };
    saveQueue.current = saveQueue.current
      .then(async () => {
        try {
          await api("/attempts", payload);
          setNotice("选择已保存");
        } catch (e) {
          setAttempts((prev) =>
            prev.map((a) =>
              a.attempt_id === attempt.attempt_id
                ? { ...a, selected_option_ids: before }
                : a,
            ),
          );
          setError(`选择保存失败：${(e as Error).message}`);
          throw e;
        }
      })
      .catch(() => {});
  }
  function markMeta(guess: boolean, usedHint: boolean) {
    setGuessed(guess);
    setHint(usedHint);
    if (!attempt.attempt_id || isSubmitted) return;
    setAttempts((prev) =>
      prev.map((a) =>
        a.attempt_id === attempt.attempt_id
          ? { ...a, guessed: guess, hint: usedHint }
          : a,
      ),
    );
    saveQueue.current = saveQueue.current.then(async () => {
      try {
        await api("/attempts", {
          session_id: session!.id,
          question_id: current.question_id,
          attempt_id: attempt.attempt_id,
          selected_option_ids: attempt.selected_option_ids || [],
          action: "save",
          guessed: guess,
          hint_used: usedHint,
        });
      } catch (e) {
        setError(`标记未保存：${(e as Error).message}`);
      }
    });
  }
  async function flushTime() {
    const s = sessionRef.current;
    if (
      !s ||
      activeRef.current.paused ||
      ["submitted", "abandoned"].includes(s.status)
    )
      return;
    const seconds = (Date.now() - lastBeat.current) / 1000;
    lastBeat.current = Date.now();
    if (seconds > 0)
      await api(`/sessions/${s.id}/events`, {
        type: readingRef.current ? "reading" : "question_time",
        question_id: readingRef.current
          ? undefined
          : itemsRef.current[indexRef.current]?.question_id,
        duration_seconds: seconds,
      });
  }
  async function submit() {
    await work(async () => {
      await flushTime();
      await saveQueue.current;
      if (session!.mode === "practice") {
        const result = await api("/attempts", {
          session_id: session!.id,
          question_id: current.question_id,
          attempt_id: attempt.attempt_id,
          selected_option_ids: attempt.selected_option_ids || [],
          action: "submit",
          guessed,
          hint_used: hint,
        });
        const updated = await api(`/sessions/${session!.id}/items`);
        setAttempts(list(updated.attempts || updated.session?.attempts));
        if (updated.session) {
          setSession(updated.session);
          sessionRef.current = updated.session;
          setElapsed(updated.session.active_seconds || 0);
        }
        if (result.review_available !== false)
          setReview(await api(`/attempts/${attempt.attempt_id}/review`));
      } else {
        const result = await api(`/sessions/${session!.id}/submit`, {});
        sessionRef.current = result;
        setSession(result);
        setElapsed(result.active_seconds || 0);
        const updated = await api(`/sessions/${session!.id}/items`);
        setAttempts(list(updated.attempts || result.attempts));
        setReview(await api(`/attempts/${attempt.attempt_id}/review`));
      }
      await refresh();
      setNotice("已提交，评分以来源及核验状态为准；不是折算分值。");
    });
  }
  async function togglePause() {
    await work(async () => {
      await flushTime();
      const result = await api(`/sessions/${session!.id}/events`, {
        type: paused ? "resume" : "pause",
      });
      const clock = activeRef.current;
      const base =
        clock.base + (clock.paused ? 0 : (Date.now() - clock.at) / 1000);
      activeRef.current = { base, at: Date.now(), paused: !paused };
      setPaused(!paused);
      setSession({ ...session, ...result });
      sessionRef.current = { ...session, ...result };
      lastBeat.current = Date.now();
    });
  }
  function move(i: number) {
    flushTime().catch((e) => setError(`计时未同步：${e.message}`));
    if (session) localStorage.setItem(`xingce.index.${session.id}`, String(i));
    setIndex(i);
    indexRef.current = i;
    setReview(null);
    const a = attempts.find((a) => a.question_id === items[i]?.question_id);
    setGuessed(Boolean(a?.guessed));
    setHint(Boolean(a?.hint));
    if (!items[i]?.material) {
      setReading(false);
      readingRef.current = false;
    }
  }
  async function fetchCards() {
    await work(async () => {
      const parameters = buildSearchQuery({kind:searchObject,q:query,module:cardModule,year:searchYear,paper_type:searchPaperType,concept_id:searchConcept,allow_source_only:searchAllowSource});
      const d = await api(`/search?${parameters}`);
      if (searchObject === "cards") setCards(list(d.items));
      else { setQuestionResults(list(d.items)); setSearchTotal(Number(d.total || 0)); }
      setSelectedCard(null);
    });
  }
  async function navigate(target: string) {
    setPage(target);
    setError("");
    if (target === "cards")
      await work(async () => {
        const d = await api(`/cards?module=${encodeURIComponent(cardModule)}`);
        setCards(list(d.items));
        setSearchFilters(await api("/search/filters"));
      });
    if (target === "assessment") await work(async () => {
      setAssessmentPacks(list((await api("/assessments")).items));
      setStats(await api("/stats"));
      setAssessmentConfirm(false);
    });
    if (target === "due" || target === "today") await work(refresh);
    if (target === "data")
      await work(async () => {
        await refresh();
        setReleases(list((await api("/releases")).items));
      });
  }
  function flag() {
    const id = current.question_id;
    const next = flags.includes(id)
      ? flags.filter((x) => x !== id)
      : [...flags, id];
    setFlags(next);
    localStorage.setItem(`xingce.flags.${session!.id}`, JSON.stringify(next));
  }
  function searchQuestion(x: Data, showMaterial = true) {
    return <section className="panel" key={x.question_id}>
      <div className="row"><b>{x.question_id}</b><Status value={x.answer_status} /></div>
      <p className="muted">{list(x.source_papers).map(p => `${p.year || "年份未标"} · ${p.paper_type || "卷型未标"} · ${p.name || ""}`).join("；") || "来源卷标签未提供"}</p>
      {showMaterial && x.material && <div className="panel"><h3>共用材料</h3><p style={{whiteSpace:"pre-wrap"}}>{x.material.text}</p><Images items={x.material.assets} onZoom={setZoom} /></div>}
      <p style={{whiteSpace:"pre-wrap"}}>{x.stem}</p>
      <Images items={list(x.assets).filter(a => a.role !== "option")} onZoom={setZoom} />
      {list(x.options).map(o => <div className="panel" key={o.option_id}><b>{o.label}</b> {o.text}<Images items={o.assets} onZoom={setZoom} /></div>)}
      <p className="muted">{x.verification_notice} · 本题面已记为阅览，不再声称完全未见。</p>
      <button className="primary" disabled={busy} onClick={() => start([x.question_id], {mode:"practice", allow_source_only:searchAllowSource})}>开始单题练习</button>
    </section>;
  }
  const cardList = cards.filter(
    (c) =>
      !statusFilter ||
      (["verified", "disputed"].includes(c.status)
        ? c.status
        : "source_only") === statusFilter,
  );
  return (
    <>
      <header>
        <div className="brand">
          <span className="brand-icon">精</span>
          <div>
            <b>行测 · 今日精练</b>
            <small>先把会拿的分拿稳</small>
          </div>
        </div>
        <span className="offline">个人离线工作台</span>
      </header>
      <div className="shell">
        <aside className="sidebar">
          <nav aria-label="主导航">
            {NAV.map(([id, label]) => (
              <button
                className={page === id ? "active" : ""}
                key={id}
                onClick={() => navigate(id)}
              >
                {label}
                {id === "due" && due.length > 0 && (
                  <span className="nav-count">{due.length}</span>
                )}
              </button>
            ))}
          </nav>
          <p className="sidebar-note">
            训练 → 找错因 → 方法辨析 → 未见题迁移
            <br />
            不把重复刷对当成掌握。
          </p>
          <small className="version">
            内容版本
            <br />
            {catalog.release || "等待内容库"}
          </small>
        </aside>
        <main>
          <div aria-live="polite">
            {error && (
              <div className="alert error" role="alert">
                {error}
                <button onClick={() => setError("")} aria-label="关闭错误">
                  ×
                </button>
              </div>
            )}
            {notice && (
              <div className="alert notice">
                {notice}
                <button onClick={() => setNotice("")} aria-label="关闭通知">
                  ×
                </button>
              </div>
            )}
          </div>
          {page === "assessment" && <>
            <div className="page-title"><div><h1>个人迁移测验</h1><p>独立保留题包；非原卷、非考分预测，不并入日常训练正确率。</p></div></div>
            <section className="panel"><p>只在你明确启动后才展示题面并记录曝光。开始、放弃和重做均不能恢复为“未见”。完成整卷后才显示解析；未决题不纳入准确率分母。</p>
              <label><input type="checkbox" checked={assessmentSeen} onChange={e=>setAssessmentSeen(e.target.checked)} />我此前见过其中部分或全部题（保守标记整次测验为已见）</label><br />
              <label><input type="checkbox" checked={assessmentHint} onChange={e=>setAssessmentHint(e.target.checked)} />本次会使用提示/参考资料（答题中也可逐题标提示）</label><br />
              <label><input type="checkbox" checked={assessmentConfirm} onChange={e=>setAssessmentConfirm(e.target.checked)} />我确认由我本人开始作答，并理解开始即记录曝光</label>
            </section>
            {!assessmentPacks.length && <section className="panel empty">尚无通过完整性校验的评测包；不会用示例题或未核密钥代替。</section>}
            {assessmentPacks.map(p=><section className="panel" key={p.pack_id}><h2>{p.title}</h2><p>{p.question_count} 道题面 · {p.scorable_count} 道可评分 · {p.unscored_count} 道未决不评分</p><p>{p.previous_starts ? `已有 ${p.previous_starts} 次启动，本次属于重做/再次启动。` : "此前未在本工作台启动；不保证你在其他地方没见过。"}</p><small>固定版本：{p.pack_id}</small><p><button className="primary" disabled={busy || !assessmentConfirm} onClick={()=>work(async()=>{
              const started=await api(`/assessments/${encodeURIComponent(p.pack_id)}/start`,{confirm:assessmentConfirm,seen_before:assessmentSeen,hint_used:assessmentHint});
              setAssessmentConfirm(false);await loadSession(started.id);await refresh();
            })}>{p.previous_starts ? "确认再次开始（重做）" : "确认开始个人测验"}</button></p></section>)}
            <section className="panel"><h2>个人测验记录（独立统计）</h2>{!list(stats.assessment_sessions).length && <p>尚无用户作答记录。</p>}{list(stats.assessment_sessions).map(a=><div className="release-row" key={a.session_id}><div><b>{a.assessment?.attempt_label}</b><p>{a.status === "active" ? "进行中：整卷提交后才评分" : `已评分 ${a.scored_count} 题，答对 ${a.correct_count} 题，未评分 ${a.ungraded_count} 题`}</p>{a.status === "abandoned" && <p>本轮已放弃/中断，不能作为完整能力评估。</p>}</div><button onClick={()=>work(()=>loadSession(a.session_id))}>打开记录</button></div>)}</section>
          </>}
          {page === "coverage" && <Coverage />}
          {page === "today" && (
            <>
              <div className="page-title">
                <div>
                  <span className="eyebrow">小步完成，及时复盘</span>
                  <h1>今天，先练一个专题</h1>
                  <p>目标是提高真实的正确率与速度，不承诺进面分数。</p>
                </div>
              </div>
              <section className="hero">
                <div>
                  <span className="eyebrow">重点任务</span>
                  <h2>先做一组，再带着错题查方法</h2>
                  <p>
                    资料分析作为默认入口；可按你实际薄弱项调整。推荐依据是你确定的备考优先级，并非已测出的能力诊断。
                  </p>
                </div>
                <div className="training-config">
                  <label>
                    重点模块
                    <select
                      value={module}
                      onChange={(e) => setModule(e.target.value)}
                    >
                      {(modules.length
                        ? modules
                        : [
                            "资料分析",
                            "判断推理",
                            "言语理解与表达",
                            "数量关系",
                            "政治理论",
                            "常识判断",
                          ]
                      ).map((m: string) => (
                        <option key={m}>{m}</option>
                      ))}
                    </select>
                  </label>
                  <div className="row">
                    <label>
                      训练方式
                      <select
                        value={mode}
                        onChange={(e) => setMode(e.target.value)}
                      >
                        <option value="group">组练 · 全组提交后复盘</option>
                        <option value="practice">单题练 · 逐题提交</option>
                        <option value="mock">专题模拟 · 持续计时</option>
                      </select>
                    </label>
                    <label>
                      题数
                      <input
                        type="number"
                        min="1"
                        max="50"
                        value={count}
                        onChange={(e) =>
                          setCount(
                            Math.max(
                              1,
                              Math.min(50, Number(e.target.value) || 1),
                            ),
                          )
                        }
                      />
                    </label>
                  </div>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={allowSource}
                      onChange={(e) => setAllowSource(e.target.checked)}
                    />
                    包含来源资料题（未独立核验，不作为已核验能力结论）
                  </label>
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => start()}
                  >
                    {busy ? "正在准备…" : "开始精练"} →
                  </button>
                  <small>
                    实际题量与完整材料组由内容库决定；预计约 {count * 2}–
                    {count * 3} 分钟，仅为计划预算。专题模拟不是原卷模考。
                  </small>
                </div>
              </section>
              {(

                <section className="panel">
                  <h2>今天的短路线</h2>
                  <label>计划预算<select aria-label="计划预算" value={budget} onChange={e=>setBudget(Number(e.target.value))}><option value={20}>20分钟</option><option value={40}>40分钟</option></select></label>
                  <p>{planInfo.notice}</p><p>不适用于当前掌握的历史首次记录：{planInfo.excluded_first_count || 0}。</p><p>计划作答约 {planInfo.estimated_minutes} 分钟，另留 {planInfo.reserve_minutes} 分钟复盘。到期 {planInfo.due_count} 题，当前不可安排 {planInfo.due_unavailable_count} 题。</p>
                  {!todayTasks.length && <p>当前没有可安排任务；可调整预算或等待跳过期限结束，缺少内容时请查看数据诊断。</p>}
                  {todayTasks.map((t) => (
                    <div className="today-task" key={t.id}>
                      <div>
                        <h3>{t.title}</h3>
                        <p>{t.reason}</p>
                        <details><summary>查看选题依据</summary>{list(t.evidence).map((e:Data)=><p key={e.question_id}>{e.question_id}：首次 {e.first_correct}/{e.first_count}；提示/猜测 {e.hint_or_guess_count}；题目计时中位数 {e.median_question_seconds ?? "暂无"} 秒；来源卷组覆盖 {e.source_groups}；排序权重 {e.rank_score}（非考分）</p>)}</details>
                        <small>
                          计划 {t.count} 题 · 可选 {t.available_count} 题 · 约 {Math.ceil(t.estimated_seconds/60)} 分钟；未记录曝光候选 {t.candidate_unseen_count || 0} / 重复 {t.repeat_count || (t.kind==="review"?t.count:0)}
                        </small>
                      </div>
                      <div className="row">
                        <button
                          disabled={busy || planInfo.budget_minutes !== budget}
                          onClick={() =>
                            start(t.question_ids, {
                              count: t.count,
                              mode: "practice",
                              planned_release: planInfo.release,
                              allow_source_only: false,
                            })
                          }
                        >
                          开始
                        </button>
                        <button
                          className="small"
                          disabled={busy}
                          onClick={() =>
                            work(async () => {
                              await api(`/today/${encodeURIComponent(t.id)}`, {
                                count,
                              });
                              await refresh();
                              setNotice(`该任务已调整为 ${count} 题`);
                            })
                          }
                        >
                          按上方题量调整
                        </button>
                        <button
                          className="small"
                          disabled={busy}
                          onClick={() =>
                            work(async () => {
                              await api(`/today/${encodeURIComponent(t.id)}`, {
                                skip: true,
                              });
                              await refresh();
                            })
                          }
                        >
                          今天跳过
                        </button>
                      </div>
                    </div>
                  ))}
                </section>
              )}
              <div className="grid two">
                <section className="panel">
                  <h2>
                    到期复习 <span className="count">{due.length}</span>
                  </h2>
                  <p>
                    先纠错，再做未见同类题。1 / 3 / 7
                    天是可调整复习规则，不代表最优间隔。
                  </p>
                  {due.length ? (
                    <button onClick={() => navigate("due")}>
                      查看复习队列 →
                    </button>
                  ) : (
                    <p className="muted">
                      暂无到期项目。提交后记录错因，即可安排复习。
                    </p>
                  )}
                </section>
                <section className="panel">
                  <h2>接着上次练</h2>
                  {session ? (
                    <>
                      <p>
                        {session.mode === "mock"
                          ? "专题模拟"
                          : session.mode === "group"
                            ? "组练"
                            : "单题练"}{" "}
                        · {items.length} 题 ·{" "}
                        {session.status === "submitted" ? "已提交" : "未完成"}
                      </p>
                      <button onClick={() => setPage("train")}>
                        回到训练 →
                      </button>
                    </>
                  ) : (
                    <p className="muted">
                      还没有恢复中的训练，从一个专题开始。
                    </p>
                  )}
                  {sessions
                    .filter((s) => s.id !== session?.id)
                    .slice(0, 3)
                    .map((s) => (
                      <button
                        className="list-button"
                        key={s.id}
                        onClick={() => work(() => loadSession(s.id))}
                      >
                        {s.mode === "mock" ? "专题模拟" : "训练"} ·{" "}
                        {s.question_ids?.length || "?"} 题{" "}
                        <small>
                          {s.status === "submitted" ? "已提交" : "草稿"}
                        </small>
                      </button>
                    ))}
                </section>
              </div>
              <div className="quality-note">
                <Status value="source_only" />
                <p>
                  {catalog.quality_notice ||
                    "原仓库资料并不等于已核验答案；有争议或答案缺失的题不会自动判分。方法卡状态单独展示。"}
                </p>
              </div>
            </>
          )}
          {page === "train" &&
            (!session || !current ? (
              <section className="panel empty">
                <h1>还没有进行中的训练</h1>
                <p>先选择一个模块，完成少量练习。</p>
                <button className="primary" onClick={() => setPage("today")}>
                  去今日精练
                </button>
              </section>
            ) : (
              <>
                <div className="page-title">
                  <div>
                    <span className="eyebrow">
                      {session.mode === "mock"
                        ? "专题模拟 · 不是原卷模考"
                        : session.mode === "group"
                          ? "材料组练习"
                          : "单题练习"}{" "}
                      / 版本 {session.release}
                    </span>
                    <h1>
                      第 {index + 1} / {items.length} 题
                    </h1>
                    <Status value={current.answer_status} />
                    {session.selection_notice && <p className="muted">{session.selection_notice}</p>}
                    {current.verification_notice && <p className="muted">{current.verification_notice}</p>}
                  </div>
                  <div className="timer">
                    <b>{formatTime(elapsed)}</b>
                    <small>
                      {session.status === "abandoned"
                        ? "本轮已结束"
                        : session.status === "submitted"
                          ? "已提交 · 计时停止"
                          : paused
                        ? "已主动暂停"
                        : session.mode === "mock"
                          ? "持续计时 · 后台不停"
                          : "有效练习时间"}
                    </small>
                    {canPause(session.mode) &&
                      !["submitted", "abandoned"].includes(session.status) && (
                        <button disabled={busy} onClick={togglePause}>
                          {paused ? "继续" : "暂停"}
                        </button>
                      )}
                  </div>
                </div>
                {!["submitted", "abandoned"].includes(session.status) && (
                  <div className="session-controls">
                    <button
                      className="small"
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "结束本轮并保留当前记录？未提交题不会获得评分。",
                          )
                        )
                          work(async () => {
                            const result = await api(
                              `/sessions/${session.id}/abandon`,
                              {},
                            );
                            setSession(result);
                            sessionRef.current = result;
                            setPaused(false);
                            setNotice(
                              "本轮已结束；可以浏览方法库或创建新练习。",
                            );
                            await refresh();
                          });
                      }}
                    >
                      结束本轮（保留历史）
                    </button>
                  </div>
                )}
                <div className="question-nav" aria-label="组题导航">
                  {items.map((q, i) => {
                    const a = attempts.find(
                      (a) => a.question_id === q.question_id,
                    );
                    return (
                      <button
                        key={q.question_id}
                        className={`${i === index ? "active" : ""} ${a?.selected_option_ids?.length ? "answered" : ""}`}
                        onClick={() => move(i)}
                        aria-label={`第${i + 1}题${flags.includes(q.question_id) ? "已标记" : ""}`}
                      >
                        {i + 1}
                        {flags.includes(q.question_id) && "·"}
                      </button>
                    );
                  })}
                </div>
                {paused ? (
                  <section className="panel empty">
                    <h2>练习已暂停</h2>
                    <p>题面暂时隐藏。模拟训练不提供暂停功能。</p>
                    <button className="primary" onClick={togglePause}>
                      继续练习
                    </button>
                  </section>
                ) : (
                  <div className="training-grid">
                    <section className="panel material">
                      <h2>{current.material ? "共用材料" : "题面与图示"}</h2>
                      {current.material ? (
                        <>
                          <Text
                            value={
                              current.material.text || current.material.content
                            }
                          />
                          <Images
                            items={current.material.assets}
                            onZoom={setZoom}
                          />
                          {reading &&
                            !["submitted", "abandoned"].includes(
                              session.status,
                            ) && (
                              <button
                                onClick={() => {
                                  flushTime().catch((e) =>
                                    setError(`计时未同步：${e.message}`),
                                  );
                                  setReading(false);
                                  readingRef.current = false;
                                  setNotice(
                                    "开始计入当前小题用时；材料阅读用时独立保留。",
                                  );
                                }}
                              >
                                读完材料，开始答题 →
                              </button>
                            )}
                        </>
                      ) : (
                        <p className="muted">
                          本题无独立共用材料，请阅读右侧题干。图片仅按已登记本地资产展示。
                        </p>
                      )}
                      <Images
                        items={list(current.assets).filter(
                          (a) => !a.option_id && a.role !== "option",
                        )}
                        onZoom={setZoom}
                      />
                    </section>
                    <section className="panel question">
                      <div className="row spread">
                        <small>{current.assessment_item_id ? `${current.assessment_item_id} · ` : ""}{current.question_id}</small>
                        <button className="small" onClick={flag}>
                          {flags.includes(current.question_id)
                            ? "★ 已标记"
                            : "☆ 标记稍后检查"}
                        </button>
                      </div>
                      <Text value={current.stem} />
                      <fieldset
                        disabled={
                          isSubmitted ||
                          session.status === "abandoned" ||
                          busy ||
                          paused
                        }
                      >
                        <legend className="sr-only">选择答案</legend>
                        {list(current.options).map((o, i) => {
                          const id =
                            o.option_id || o.id || o.label || String(i);
                          return (
                            <label
                              className={`option ${(attempt?.selected_option_ids || []).includes(id) ? "selected" : ""}`}
                              key={id}
                            >
                              <input
                                type="radio"
                                name={`q-${current.question_id}`}
                                value={id}
                                checked={(
                                  attempt?.selected_option_ids || []
                                ).includes(id)}
                                onChange={() => select(id)}
                              />
                              <b>{o.label || String.fromCharCode(65 + i)}</b>
                              <span>{o.text}</span>
                              {o.assets && (
                                <Images items={o.assets} onZoom={setZoom} />
                              )}
                            </label>
                          );
                        })}
                      </fieldset>
                      {!isSubmitted && session.status !== "abandoned" && (
                        <div className="row checks">
                          <label>
                            <input
                              type="checkbox"
                              checked={guessed}
                              onChange={(e) => markMeta(e.target.checked, hint)}
                            />
                            猜测 / 不确定
                          </label>
                          <label>
                            <input
                              type="checkbox"
                              checked={hint}
                              onChange={(e) =>
                                markMeta(guessed, e.target.checked)
                              }
                            />
                            使用过提示
                          </label>
                        </div>
                      )}
                      <div className="row question-actions">
                        <button
                          disabled={index === 0}
                          onClick={() => move(index - 1)}
                        >
                          上一题
                        </button>
                        <button
                          disabled={index === items.length - 1}
                          onClick={() => move(index + 1)}
                        >
                          下一题
                        </button>
                        {session.status === "abandoned" ? (
                          <span className="muted">
                            本轮已结束，作答记录保留
                          </span>
                        ) : isSubmitted ? (
                          <button
                            className="primary"
                            disabled={busy}
                            onClick={() =>
                              work(async () =>
                                setReview(
                                  await api(
                                    `/attempts/${attempt.attempt_id}/review`,
                                  ),
                                ),
                              )
                            }
                          >
                            查看复盘
                          </button>
                        ) : (
                          <button
                            className="primary"
                            disabled={busy}
                            onClick={submit}
                          >
                            {busy
                              ? "处理中…"
                              : session.mode === "practice"
                                ? "提交本题"
                                : "提交整组"}
                          </button>
                        )}
                      </div>
                      <p className="muted">
                        {session.mode === "practice"
                          ? "提交当前题后才读取答案及解析。"
                          : "全组 / 全卷提交前，不请求任何答案或解析。"}{" "}
                        未作答题保持未作答，不自动猜选项。
                      </p>
                    </section>
                  </div>
                )}
                {review && (
                  <section className="panel review">
                    <span className="eyebrow">作答复盘</span>
                    <h2>
                      {review.attempt?.grade?.correct === true ||
                      review.attempt?.is_correct === true
                        ? review.attempt?.grade?.answer_status === "source_only"
                          ? "与来源参考答案一致"
                          : "本题作答正确"
                        : review.attempt?.grade?.correct === false ||
                            review.attempt?.is_correct === false
                          ? "本题需要纠错"
                          : "查看评分与依据"}
                    </h2>
                    <div className="quality-note">
                      <Status
                        value={
                          review.answer?.status ||
                          review.question?.answer_status
                        }
                      />
                      <p>
                        你的选择：
                        {optionLabels(
                          review.attempt?.selected_option_ids ||
                          attempt?.selected_option_ids ||
                          [], review.question?.options || current.options
                        ) || "未作答"}
                        　参考答案：
                        {Array.isArray(review.answer)
                          ? optionLabels(review.answer,review.question?.options || current.options)
                          : typeof review.answer === "string"
                            ? review.answer
                            : optionLabels(review.answer?.option_ids || [],review.question?.options || current.options) ||
                              "暂无可评分答案"}
                      </p>
                    </div>
                    <h3>{review.explanation_kind==='ai_independent'||review.question?.review_status==='ai_verified_not_human'?'AI 独立复算 / 推导（非人工审批）':review.explanation_kind==='source_reference'?'来源解析（未宣称全文核验）':'解析与核验说明（类型待载入）'}</h3>
                    {review.explanation_notice && <p className="muted">{review.explanation_notice}</p>}
                    {review.question?.verification_notice && <p className="muted">{review.question.verification_notice}</p>}
                    <Text value={review.explanation} />
                    <h3>来源与证据</h3>
                    <ul>
                      {list(review.source_refs).map((s, i) => (
                        <li key={i}>
                          {typeof s === "string"
                            ? s
                            : s.title ||
                              s.source_path ||
                              s.paper_name ||
                              s.path ||
                              JSON.stringify(s)}{" "}
                          {sourceLink(s) && (
                            <a
                              href={sourceLink(s)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              查看固定版本原题 ↗
                            </a>
                          )}
                        </li>
                      ))}
                    </ul>
                    <h3>方法与边界</h3>
                    {list(review.cards).length ? (
                      list(review.cards).map((c) => (
                        <article
                          className="card-preview"
                          key={c.card_id || c.id}
                        >
                          <Status value={c.status || c.verification_status} />
                          <h4>{c.title}</h4>
                          <CardBody card={c} />
                        </article>
                      ))
                    ) : (
                      <p className="muted">
                        暂无关联的已登记方法卡，不自动编造解题方法。
                      </p>
                    )}
                    <div className="review-form">
                      <h3>把错因留下，而不只是看懂答案</h3>
                      <div className="row">
                        <label>
                          错因 / 复测原因
                          <select
                            value={errorKind}
                            onChange={(e) => setErrorKind(e.target.value)}
                          >
                            {ERROR_KINDS.map((k) => (
                              <option key={k}>{k}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          复习间隔
                          <select
                            value={interval}
                            onChange={(e) =>
                              setIntervalDays(Number(e.target.value))
                            }
                          >
                            {[1, 3, 7].map((n) => (
                              <option key={n} value={n}>
                                {n} 天后
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <label>
                        一句话复盘
                        <textarea
                          value={notes}
                          onChange={(e) => setNotes(e.target.value)}
                          placeholder="我漏看了哪个条件？下次第一步先检查什么？"
                        />
                      </label>
                      <button
                        disabled={busy}
                        onClick={() =>
                          work(async () => {
                            await api(
                              `/attempts/${attempt.attempt_id}/review`,
                              {
                                error_type: errorKind,
                                notes,
                                interval_days: interval,
                                guessed,
                                hint_used: hint,
                              },
                            );
                            setNotice("错因与复习计划已保存");
                            await refresh();
                          })
                        }
                      >
                        保存错因与复习计划
                      </button>
                    </div>
                    <h3>下一道迁移练习</h3>
                    {list(review.transfer).length ? (
                      list(review.transfer).map((t) => (
                        <button
                          className="list-button"
                          key={t.question_id || t.id}
                          onClick={() => start([t.question_id || t.id])}
                        >
                          {t.stem || t.title || t.question_id}
                          <small>
                            {t.reason || "候选同类题；未见状态由个人记录核对"}
                          </small>
                        </button>
                      ))
                    ) : (
                      <p className="muted">
                        没有符合条件的未见迁移题；不拿已做题伪装迁移。
                      </p>
                    )}
                  </section>
                )}
              </>
            ))}
          {page === "cards" && (
            <>
              <div className="page-title">
                <div>
                  <span className="eyebrow">先识别条件，再选择方法</span>
                  <h1>方法 / 题库检索</h1>
                  <p>来源总结与已核验方法分别标识，不以“AI 生成”代替核验。</p>
                </div>
              </div>
              <form
                className="panel searchbar"
                onSubmit={(e) => {
                  e.preventDefault();
                  fetchCards();
                }}
              >
                <label>检索对象<select value={searchObject} onChange={e => {setSearchObject(e.target.value);setQuestionResults([]);setSearchTotal(null);setSelectedCard(null);}}><option value="cards">方法卡</option><option value="questions">可练题目</option><option value="materials">可练材料组</option></select></label>
                <label>
                  中文关键词 / 题号
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="关键词，或完整 qid / 数字题号"
                  />
                </label>
                <label>
                  模块
                  <select
                    value={cardModule}
                    onChange={(e) => setCardModule(e.target.value)}
                  >
                    <option value="">全部模块</option>
                    {modules.map((m: string) => (
                      <option key={m}>{m}</option>
                    ))}
                  </select>
                </label>
                {searchObject === "cards" && <label>
                  核验状态
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="">全部状态</option>
                    <option value="verified">已核验</option>
                    <option value="source_only">来源资料 · 待核验</option>
                    <option value="disputed">有争议</option>
                  </select>
                </label>
                }
                {searchObject !== "cards" && <>
                  <label>来源年度<select value={searchYear} onChange={e=>setSearchYear(e.target.value)}><option value="">全部年度</option>{(searchFilters.years || []).map((y:string)=><option key={y}>{y}</option>)}</select></label>
                  <label>来源卷型<select value={searchPaperType} onChange={e=>setSearchPaperType(e.target.value)}><option value="">全部卷型</option>{(searchFilters.paper_types || []).map((t:string)=><option key={t}>{t}</option>)}</select></label>
                  <label>考点<select value={searchConcept} onChange={e=>setSearchConcept(e.target.value)}><option value="">全部考点</option>{list(searchFilters.concepts).map(c=><option value={c.concept_id} key={c.concept_id}>{c.name || c.concept_id}</option>)}</select></label>
                  <label><input type="checkbox" checked={searchAllowSource} onChange={e=>setSearchAllowSource(e.target.checked)} />同时查看来源答案题（source_only，未独立核答案）</label>
                </>}
                <button className="primary" disabled={busy}>
                  检索
                </button>
              </form>
              {searchObject !== "cards" && <>
                <p className="muted">仅展示题面已核准的可练内容；默认答案已核对但非人工审批。显示即记录已阅；留出题及关联材料不开放。来源卷型/年份不表示原卷顺序与完整性已核。每次最多展示 20 条。</p>
                {searchTotal !== null && <p>匹配 {searchTotal} 条，当前展示 {questionResults.length} 条。</p>}
                {questionResults.map(x => searchObject === "questions" ? searchQuestion(x) : <section key={x.id}><div className="panel"><h2>共用材料</h2><p style={{whiteSpace:"pre-wrap"}}>{x.text}</p><Images items={x.assets} onZoom={setZoom} /></div>{list(x.questions).map(item => searchQuestion(item,false))}</section>)}
                {searchTotal === 0 && <section className="panel empty">没有匹配的可练内容。可以清除年度、卷型或考点筛选；未核题不会用演示数据填充。</section>}
              </>}
              {searchObject === "cards" && <><div className="grid two">
                {cardList.map((c, i) => (
                  <button
                    className="panel card-tile"
                    key={c.card_id || c.id || i}
                    onClick={() =>
                      work(async () => {
                        // Never render a summary as if the gated full method had loaded.
                        setSelectedCard(null);
                        if (c.card_id || c.id)
                          setSelectedCard(
                            await api(
                              `/cards/${encodeURIComponent(c.card_id || c.id)}`,
                            ),
                          );
                      })
                    }
                  >
                    <Status value={c.status || c.verification_status} />
                    <h2>{c.title || c.name || "方法卡"}</h2>
                    <p>
                      {c.summary ||
                        c.module ||
                        "查看触发条件、方法与适用边界 →"}
                    </p>
                  </button>
                ))}
              </div>
              {!cardList.length && (
                <section className="panel empty">
                  <p>暂无匹配方法卡。可换用更短关键词，或清除模块筛选。</p>
                </section>
              )}
              {selectedCard && (
                <section className="panel">
                  <Status
                    value={
                      selectedCard.status || selectedCard.verification_status
                    }
                  />
                  <h2>{selectedCard.title}</h2>
                  <CardBody card={selectedCard} />
                </section>
              )}
              </>}
            </>
          )}
          {page === "due" && (
            <>
              <div className="page-title">
                <div>
                  <span className="eyebrow">纠错，不是刷熟答案</span>
                  <h1>错题复习</h1>
                  <p>
                    猜对、提示后答对不直接算掌握；完成原题后，继续做未见题迁移。
                  </p>
                </div>
              </div>
              {due.length ? (
                due.map((d, i) => (
                  <section
                    className="panel due-item"
                    key={d.id || d.attempt_id || i}
                  >
                    <div>
                      <span className="eyebrow">
                        {d.error_type || "到期复测"}
                      </span>
                      <h2>{d.stem || d.question?.stem || d.question_id}</h2>
                      <p>
                        {d.reason || d.notes || "按你保存的复习时间进入队列"}
                      </p>
                      <small>
                        到期：
                        {d.due_at
                          ? new Date(
                              typeof d.due_at === "number"
                                ? d.due_at * 1000
                                : d.due_at,
                            ).toLocaleString("zh-CN")
                          : "时间未提供"}
                      </small>
                    </div>
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() => start([d.question_id])}
                    >
                      重做原题
                    </button>
                  </section>
                ))
              ) : (
                <section className="panel empty">
                  <h2>暂无到期复习</h2>
                  <p>训练后提交错因与复习计划，这里会保留下一次复测入口。</p>
                  <button onClick={() => setPage("today")}>开始一组练习</button>
                </section>
              )}
            </>
          )}
          {page === "data" && (
            <>
              <div className="page-title">
                <div>
                  <span className="eyebrow">个人记录与内容版本分开保存</span>
                  <h1>进度与数据</h1>
                  <p>只展示实际作答记录；正确题数不折算成行测分值。</p>
                </div>
              </div>
              <div className="grid three">
                {[
                  ["已提交作答", stats.total_submitted],
                  ["已核验题作答", stats.verified?.count],
                  ["不可评分作答", stats.ungraded?.count],
                ].map(([l, v]) => (
                  <section className="panel metric" key={l}>
                    <span>{l}</span>
                    <strong>{typeof v === "number" ? v : "—"}</strong>
                  </section>
                ))}
              </div>
              <section className="panel">
                <h2>真实学习记录</h2>
                <p>
                  首次题表现与掌握证据由后端个人记录计算。中断练习不应用来判断正常答题速度。
                </p>
                <div className="stats-summary">
                  <p>
                    首次作答：{list(stats.first_attempt).length}{" "}
                    题；按来源参考答案答对：
                    {
                      list(stats.first_attempt).filter(
                        (a) =>
                          a.correct === true &&
                          a.answer_status === "source_only",
                      ).length
                    }{" "}
                    题；按已核验答案答对：
                    {
                      list(stats.first_attempt).filter(
                        (a) =>
                          a.correct === true && a.answer_status === "verified",
                      ).length
                    }{" "}
                    题。
                  </p>
                  <p>
                    猜测标记：{stats.guessed_count || 0} 次；提示标记：
                    {stats.hint_count || 0} 次；重做：{stats.redo_count || 0}{" "}
                    次。
                  </p>
                  <p>
                    中断记录：{stats.speed_excluded_interrupted || 0}{" "}
                    条，排除正常速度统计。初步掌握标签仍需未见题迁移验证。
                  </p>
                  {list(stats.first_attempt)
                    .slice(-10)
                    .map((a, i) => (
                      <div className="release-row" key={i}>
                        <code>{a.question_id}</code>
                        <Status value={a.answer_status} />
                        <span>
                          {a.correct === true
                            ? "正确"
                            : a.correct === false
                              ? "需纠错"
                              : "不可评分"}
                          {a.interrupted ? " · 已中断" : ""}
                        </span>
                      </div>
                    ))}
                </div>
              </section>
              <section className="panel">
                <h2>导出与恢复</h2>
                <p>
                  先导出个人记录或一致性 SQLite
                  备份。内容库更新不应覆盖个人记录。下载文件保存在浏览器下载目录。
                </p>
                <div className="row">
                  <a
                    className="button primary"
                    href="/api/exports?format=json"
                    download
                  >
                    导出个人记录 JSON
                  </a>
                  <a
                    className="button"
                    href="/api/exports?format=sqlite"
                    download
                  >
                    导出 SQLite 备份
                  </a>
                </div>
                <button disabled={busy} onClick={() => work(async () => {
                  const result = await api("/backups");
                  setBackups(list(result.items));
                  setNotice(result.items?.length ? "请选择需要恢复的备份；选择不会自动恢复。" : "暂无 SQLite 备份，请先导出一份。");
                })}>刷新可恢复备份</button>
                {backups.length > 0 && <label>
                  选择已有备份
                  <select value={restorePath} onChange={(e) => setRestorePath(e.target.value)}>
                    <option value="">请选择；不会自动恢复</option>
                    {backups.map((b) => <option key={b.name} value={b.name}>{b.name} · {Math.round(Number(b.size_bytes || 0) / 1024)} KB</option>)}
                  </select>
                </label>}
                <label>
                  服务端 exports 目录中的备份文件名
                  <input
                    value={restorePath}
                    onChange={(e) => setRestorePath(e.target.value)}
                    placeholder="例如 personal-….sqlite；不是电脑上的任意路径"
                  />
                </label>
                <button
                  disabled={busy || !restorePath.trim()}
                  onClick={() => {
                    if (
                      window.confirm(
                        "恢复将替换当前个人记录。请先导出备份；确认使用这个备份恢复？",
                      )
                    )
                      work(async () => {
                        await api("/restore", { path: restorePath });
                        await refresh();
                        setNotice("备份已恢复。重新进入训练以读取最新状态。");
                        setSession(null);
                        sessionRef.current = null;
                        localStorage.removeItem("xingce.lastSession");
                      });
                  }}
                >
                  验证并恢复备份
                </button>
              </section>
              <section className="panel">
                <h2>内容版本与数据导入</h2>
                <p>
                  当前：<code>{catalog.release || "尚未载入"}</code>
                  。进行中会话使用创建时锁定的版本。
                </p>
                <label>
                  服务端 imports 目录中的 release 文件夹名
                  <input
                    value={importPath}
                    onChange={(e) => setImportPath(e.target.value)}
                    placeholder="先将数据包置于服务端 userdata/imports，再输入文件夹名"
                  />
                </label>
                <button
                  disabled={busy || !importPath.trim()}
                  onClick={() =>
                    work(async () => {
                      const r = await api("/imports", { path: importPath });
                      setNotice(`校验并导入成功：${r.release || "新版本"}`);
                      await refresh();
                      setReleases(list((await api("/releases")).items));
                    })
                  }
                >
                  校验并导入
                </button>
                <p className="muted">
                  这不是上传你电脑的任意文件：路径指运行服务的机器。格式、哈希与引用验证失败不得改变当前内容。
                </p>
                <h3>一期个人作答记录导入</h3>
                <label>
                  imports 目录中的一期 JSONL 文件名
                  <input
                    value={userdataPath}
                    onChange={(e) => setUserdataPath(e.target.value)}
                    placeholder="文件须先放入服务端允许目录"
                  />
                </label>
                <button
                  disabled={busy || !userdataPath.trim()}
                  onClick={() =>
                    work(async () => {
                      const r = await api("/imports", {
                        path: userdataPath,
                        kind: "attempts_jsonl",
                      });
                      await refresh();
                      setNotice(
                        `个人记录导入完成：${r.imported ?? r.count ?? "请查看进度统计"}`,
                      );
                    })
                  }
                >
                  校验并导入个人记录
                </button>
                {releases.map((r, i) => {
                  const id =
                    typeof r === "string" ? r : r.release || r.version || r.id;
                  return (
                    <div className="release-row" key={id || i}>
                      <code>{id}</code>
                      <button
                        disabled={busy || id === catalog.release}
                        onClick={() =>
                          work(async () => {
                            await api(
                              `/releases/${encodeURIComponent(id)}/activate`,
                              {},
                            );
                            await refresh();
                            setNotice(
                              "当前内容版本已切换；既有训练保持原版本。",
                            );
                          })
                        }
                      >
                        {id === catalog.release ? "当前版本" : "切换到此版本"}
                      </button>
                    </div>
                  );
                })}
              </section>
            </>
          )}
        </main>
      </div>
      <footer>
        个人学习工具 · 原始资料与核验结论分开 · 不把来源回忆版包装成完整原卷
      </footer>
      {zoom && (
        <div
          className="modal"
          role="dialog"
          aria-modal="true"
          aria-label="原图放大"
          onClick={() => setZoom("")}
        >
          <button className="modal-close" onClick={() => setZoom("")} autoFocus>
            关闭 ×
          </button>
          <img
            src={zoom}
            alt="放大的题目原图"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
