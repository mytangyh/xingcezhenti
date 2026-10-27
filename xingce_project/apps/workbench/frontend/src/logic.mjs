export const STATUS_LABELS = {
  source_only: "来源资料 · 待核验",
  verified: "已核验",
  disputed: "有争议 · 暂停评分",
  unresolved: "未决 · 不评分",
};
export const ERROR_KINDS = [
  "看漏条件",
  "模型识别错误",
  "规则错误",
  "计算错误",
  "选项辨析错误",
  "时间分配失当",
  "猜对不确定",
  "数据疑点",
];
export function formatTime(seconds) {
  const t = Math.max(0, Math.floor(Number(seconds) || 0));
  return `${Math.floor(t / 60)
    .toString()
    .padStart(2, "0")}:${(t % 60).toString().padStart(2, "0")}`;
}
export function safeImage(url) {
  if (typeof url !== "string") return "";
  try {
    const decoded = decodeURIComponent(url);
    if (
      decoded.includes("..") ||
      decoded.includes("\\") ||
      /[\x00-\x1f]/.test(decoded)
    )
      return "";
  } catch {
    return "";
  }
  if (/^\/api\/assets\/[a-zA-Z0-9_./%-]+$/.test(url) && !url.includes(".."))
    return url;
  if (/^\/assets\/content\/[a-zA-Z0-9_./%-]+$/.test(url) && !url.includes(".."))
    return url;
  return "";
}
export function safeLink(url) {
  try {
    const u = new URL(url);
    return ["https:", "http:"].includes(u.protocol) ? u.href : "";
  } catch {
    return "";
  }
}
export function sourceLink(source) {
  if (!source || typeof source !== "object") return "";
  if (source.url) return safeLink(source.url);
  const commit = source.source_commit;
  const path = source.source_path;
  if (!/^[a-f0-9]{40}$/.test(String(commit)) || typeof path !== "string" || !path.endsWith(".md")) return "";
  if (path.startsWith("/") || path.split("/").some(p => p === ".." || p === ".") || /[\\\x00-\x1f]/.test(path)) return "";
  const line = Number(source.source_line);
  return `https://github.com/mytangyh/xingcezhenti/blob/${commit}/${path.split("/").map(encodeURIComponent).join("/")}${Number.isInteger(line) && line > 0 ? `#L${line}` : ""}`;
}
export function canPause(mode) {
  return !["simulation", "mock", "exam"].includes(mode);
}
export function visibleElapsed(start, pausedMs, pausedAt, now = Date.now()) {
  if (!start) return 0;
  return Math.max(
    0,
    ((pausedAt || now) - new Date(start).getTime() - (pausedMs || 0)) / 1000,
  );
}
export function statusLabel(status) {
  return STATUS_LABELS[status] || "核验状态未提供";
}
export function optionLabels(ids, options) {
  if (!Array.isArray(ids)) return "";
  return ids.map(id => {
    const option = (Array.isArray(options) ? options : []).find(o => (o.option_id || o.id || o.label) === id);
    return option?.label || (/^[A-H]$/.test(String(id)) ? String(id) : "选项映射待核对");
  }).join("、");
}

export function buildSearchQuery({kind="cards",q="",module="",year="",paper_type="",concept_id="",allow_source_only=false}={}) {
  if (!["cards","questions","materials"].includes(kind)) throw new Error("不支持的检索对象");
  const p = new URLSearchParams({kind,q,module,limit:kind === "cards" ? "100" : "20"});
  if(kind !== "cards") {p.set("year",year);p.set("paper_type",paper_type);p.set("concept_id",concept_id);p.set("allow_source_only",String(allow_source_only === true));}
  return p.toString();
}
