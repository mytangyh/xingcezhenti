export const STATUS_LABELS: Record<string, string>;
export const ERROR_KINDS: string[];
export function formatTime(seconds: number): string;
export function safeImage(url: unknown): string;
export function safeLink(url: string): string;
export function sourceLink(source: unknown): string;
export function canPause(mode: string): boolean;
export function visibleElapsed(
  start: string | number,
  pausedMs: number,
  pausedAt: number | null,
  now?: number,
): number;
export function statusLabel(status: string): string;
export function optionLabels(ids:unknown,options:unknown):string;
export function buildSearchQuery(options?:{kind?:string,q?:string,module?:string,year?:string,paper_type?:string,concept_id?:string,allow_source_only?:boolean}):string;
