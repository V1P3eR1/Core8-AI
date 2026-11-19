/**
 * Core8AI Social Manager — typed API client for /api/social/*.
 * Every call goes through `apiFetch` (JWT + auto-refresh).
 * Error responses are `{detail: string | {code, message} | ValidationError[]}` and are
 * normalised into `ApiError` so the UI can show them in a toast.
 */
import { apiFetch } from "@/lib/auth";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const S = `${API_BASE}/api/social`;

// ── Error handling ───────────────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type DetailObj = { code?: string; message?: string; msg?: string; loc?: unknown[] };

function detailToMessage(detail: unknown, status: number): { message: string; code?: string } {
  if (typeof detail === "string") return { message: detail };
  if (Array.isArray(detail)) {
    const parts = detail.map((d: DetailObj) => {
      const loc = Array.isArray(d.loc) ? d.loc.filter((x) => x !== "body").join(".") : "";
      return loc ? `${loc}: ${d.msg ?? d.message ?? ""}` : d.msg ?? d.message ?? "";
    });
    return { message: parts.filter(Boolean).join(" | ") || `שגיאת אימות (${status})` };
  }
  if (detail && typeof detail === "object") {
    const d = detail as DetailObj;
    return { message: d.message ?? d.msg ?? JSON.stringify(detail), code: d.code };
  }
  return { message: `שגיאה (${status})` };
}

async function toError(res: Response): Promise<ApiError> {
  let detail: unknown = null;
  try {
    const body = await res.json();
    detail = body?.detail ?? body;
  } catch {
    detail = null;
  }
  const { message, code } = detailToMessage(detail, res.status);
  return new ApiError(message || `שגיאה (${res.status})`, res.status, code);
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = typeof FormData !== "undefined" && init.body instanceof FormData;
  const headers: Record<string, string> = { ...((init.headers as Record<string, string>) || {}) };
  if (!isForm && init.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await apiFetch(`${S}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("אין חיבור לשרת — ודא שה-backend רץ", 0);
  }
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const headers: Record<string, string> = { ...((init.headers as Record<string, string>) || {}) };
  if (init.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const res = await apiFetch(`${S}${path}`, { ...init, headers });
  if (!res.ok) throw await toError(res);
  return res.blob();
}

const json = (body: unknown) => JSON.stringify(body);

// ── Formatting helpers ───────────────────────────────────────────────────────

export const MISSING = "חסר";

const dtFmt = new Intl.DateTimeFormat("he-IL", {
  timeZone: "Asia/Jerusalem",
  dateStyle: "short",
  timeStyle: "short",
});
const dFmt = new Intl.DateTimeFormat("he-IL", { timeZone: "Asia/Jerusalem", dateStyle: "short" });

/** Format an ISO string (local `*_local` fields or anything with an offset). */
export function fmtLocal(iso?: string | null): string {
  if (!iso) return MISSING;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return dtFmt.format(d);
}

/** Format a backend UTC string ('YYYY-MM-DD HH:MM:SS') in Asia/Jerusalem. */
export function fmtUtc(s?: string | null): string {
  if (!s) return MISSING;
  let v = s.trim().replace(" ", "T");
  if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(v)) v += "Z";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return s;
  return dtFmt.format(d);
}

export function fmtDate(iso?: string | null): string {
  if (!iso) return MISSING;
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return dFmt.format(d);
}

/** `*_local` ISO ('2026-11-02T18:00:00+02:00') → datetime-local input value ('2026-11-02T18:00'). */
export function toInputDateTime(localIso?: string | null): string {
  if (!localIso) return "";
  return localIso.slice(0, 16);
}

export function isDemo(r: { is_demo?: number | boolean | null; source?: string | null; mode?: string | null }): boolean {
  return r.is_demo === 1 || r.is_demo === true || r.source === "demo" || r.mode === "mock";
}

// ── Types ────────────────────────────────────────────────────────────────────

export type ProviderMode = "live" | "mock" | string;
export type Format = "reel" | "carousel" | "image" | "story";
export type ItemStatus =
  | "draft" | "needs_review" | "approved" | "scheduled" | "publishing" | "published"
  | "failed" | "needs_manual_review" | "rejected" | "paused";

export interface Pillar { key: string; label: string }

export interface Account {
  ig_user_id?: string;
  username?: string;
  fb_page_id?: string;
  token_expires_at?: string | null;
  connected_at?: string | null;
  account_type?: string;
  mock?: boolean;
}

export interface TokenStatus { ok: boolean; reason?: string; label: string; expires_at?: string | null }

export interface WorkerStatus {
  online: boolean;
  worker_id: string | null;
  heartbeat_at: string | null;
  stale_after_seconds: number;
  inprocess: boolean;
}

export interface AutoSettings {
  allowed_categories: string[];
  allowed_account_id: string | null;
  max_posts_per_day: number;
  window_start: string;
  window_end: string;
  review_topics: string[];
}

export interface PublishingSettings {
  mode: "draft_only" | "approval_required" | "automatic";
  emergency_pause: boolean;
  auto: AutoSettings;
  demo_mode: boolean;
}

export interface Overview {
  modes: { instagram: ProviderMode; llm: ProviderMode; research: ProviderMode; notify: ProviderMode };
  publishing: PublishingSettings;
  account: Account | null;
  token: TokenStatus;
  worker: WorkerStatus;
  counts: Record<string, number>;
  upcoming: { id: string; title: string; format: Format; status: ItemStatus; scheduled_for: string | null; scheduled_for_local?: string | null; is_demo: number }[];
  timezone: string;
  pillars: Pillar[];
}

export interface Source {
  id: string; title: string; url: string; publisher: string | null;
  published_at: string | null; published_at_local?: string | null;
  event_at: string | null; event_at_local?: string | null;
  discovered_at: string; discovered_at_local?: string | null;
  summary: string | null; relevance: string | null; unknowns: string | null;
  source_type: string; confidence: "low" | "medium" | "high"; trend_verified: number;
  angle: string | null; topic: string | null;
  status: "new" | "reviewed" | "used" | "dismissed"; is_demo: number; provider: string | null;
}

export interface SourceIn {
  title: string; url: string; publisher?: string; published_at?: string; event_at?: string;
  summary?: string; relevance?: string; unknowns?: string;
  source_type: "official" | "reporting" | "opinion" | "inference" | "benchmark";
  confidence: "low" | "medium" | "high"; angle?: string; topic?: string;
}

export interface Idea {
  id: string; title: string; pillar: string; audience: string; problem: string; core_message: string;
  desired_action: string; format: Format; business_goal: string; measurement: string;
  source_ids: string[]; notes: string | null;
  status: "new" | "shortlisted" | "drafted" | "rejected"; is_demo: number; created_at: string;
}

export interface IdeaIn {
  title: string; pillar: string; audience: "smb" | "enterprise" | "founders"; problem: string;
  core_message: string; desired_action: string; format: Format; business_goal: string;
  measurement: string; source_ids?: string[]; notes?: string;
}

export interface SpecCheck { ok: boolean; problems: string[]; warnings: string[] }

export interface Asset {
  id: string; filename: string; original_name: string | null; media_type: "image" | "video"; mime: string;
  bytes: number; width: number | null; height: number | null; duration_s: number | null; sha256: string;
  ownership: string; permission_note: string | null; alt_text: string | null; caption: string | null;
  brief: string | null; spec_check: SpecCheck | null; is_demo: number; created_at: string;
}

export interface FactFinding { flag: string; label: string; excerpt: string }
export interface FactCheck { flags: string[]; findings: FactFinding[]; ok_for_auto: boolean }

export type Package = Record<string, unknown>;

export interface Publication {
  id: string; content_item_id: string; approval_id: string | null; account_id: string; mode: "live" | "mock";
  state: string; scheduled_for: string; scheduled_for_local?: string | null; container_id: string | null;
  provider_media_id: string | null; permalink: string | null; attempts: number; last_error: string | null;
  error_class: string | null; published_at: string | null; published_at_local?: string | null;
  publish_requested_at?: string | null; publish_requested_at_local?: string | null;
  log: { at: string; event: string; detail?: unknown }[]; title?: string; format?: Format; is_demo?: number;
  updated_at: string;
}

export interface ContentItem {
  id: string; idea_id: string | null; format: Format; title: string; pillar: string | null; audience: string | null;
  status: ItemStatus; package: Package; caption: string; asset_ids: string[]; cover_asset_id: string | null;
  scheduled_for: string | null; scheduled_for_local?: string | null; account_id: string | null;
  sensitive_flags: string[]; fact_check: FactCheck | null; production_status: string;
  review_notes: string | null; version: number; is_demo: number; created_at: string; updated_at: string;
  // detail only
  assets?: Asset[]; cover_asset?: Asset | null;
  approval?: { valid: boolean; reason: string; approval: Record<string, unknown> | null };
  publications?: Publication[];
}

export interface GateCheck { code: string; ok: boolean; label: string; detail?: unknown }
export interface GateReport { ok: boolean; checks: GateCheck[]; provider_mode: ProviderMode }

export interface CarouselTemplate {
  label: string; bg: string; bg_accent: string; accent: string; title_color: string; body_color: string;
  muted: string; title_size: number; body_size: number; footer_size: number; margin: number; footer: string;
  show_counter: boolean; demo_watermark: boolean;
}
export interface CarouselTemplates { default: string; templates: Record<string, CarouselTemplate> }

export interface CalendarSlot {
  local: string; date: string; format: Format; pillar_hint: string; occupied: boolean; note: string;
}
export interface ContentMix {
  note?: string; reels_per_week: number; carousels_per_week: number; story_days_per_week: number;
  slot_hours?: Record<string, string>; days?: Record<string, number[]>;
}

export interface InstagramStatus {
  provider_mode: ProviderMode; demo_mode: boolean; account: Account | null; token: TokenStatus;
  login_path: string; scopes: string[]; permissions_status: string;
  supported_formats: { format: string; label: string; api: boolean | string; notes: string }[];
  publishing_limit: Record<string, unknown> | null; publishing_limit_error?: string;
  published_24h: number | null; app_configured: boolean; media_base_url: string; media_url_ttl_seconds: number;
}

export interface HistoryRow {
  id: string; mode: string; state: string; container_id: string | null; provider_media_id: string | null;
  permalink: string | null; published_at: string | null; published_at_local?: string | null;
  last_error: string | null; title: string; format: Format;
}

export interface Inbound {
  id: string; kind: "comment" | "dm"; provider_id: string | null; author: string | null; text: string;
  received_at: string; draft_reply: string | null;
  reply_status: "draft_only" | "approved_not_sent" | "sent" | "dismissed";
  flagged: number; flag_reasons: string | null; is_demo: number;
}

export interface Lead {
  id: string; name: string; handle: string | null; lead_date: string | null; source: string | null;
  business_type: string | null; need: string | null; status: string; next_action: string | null;
  notes: string | null; consent_note: string | null; is_demo: number; created_at: string; updated_at: string;
}
export type LeadIn = Omit<Lead, "id" | "is_demo" | "created_at" | "updated_at">;

export interface MetricRow {
  id?: string; metric: string; value: number; source: "api" | "manual" | "demo"; fetched_at: string;
  period_start: string | null; period_end: string | null; note: string | null;
  content_item_id?: string | null; provider_media_id?: string | null; title?: string | null; scope?: string;
}
export interface MetricsResponse {
  provider_mode: ProviderMode;
  account: { metrics: Record<string, MetricRow>; missing: string[]; labels: Record<string, string> };
  posts: MetricRow[];
}

export interface ReportContent {
  period: { start_local: string; end_local: string };
  include_demo: boolean;
  work_completed: { jobs: { type: string; status: string; n: number }[]; drafts: number; approvals: number };
  research: { title: string; url: string; publisher: string | null; source_type: string; confidence: string; relevance: string | null; trend_verified: number }[];
  publications: { published: Publication[]; failed: Publication[] };
  metrics: { scope: string; metric: string; value: number; source: string; content_item_id: string | null }[];
  missing_metrics: string[];
  leads: { name: string; source: string | null; business_type: string | null; status: string; lead_date: string | null }[];
  observations: string[]; recommendations: string[]; lessons_next_week: string[]; caveats: string[];
}
export interface Report { id: string; kind: string; period_start: string; period_end: string; content: ReportContent; created_at?: string }

export interface Schedule {
  key: string; job_type: string; hour: number; minute: number; weekday: number | null; enabled: number;
  last_run_at: string | null; last_run_at_local: string | null; next_run_at: string | null; next_run_at_local: string | null;
  label: string; job_label: string;
}
export interface Job {
  id: string; type: string; schedule_key: string | null; run_at: string; run_at_local: string | null;
  status: "pending" | "running" | "succeeded" | "failed" | "skipped" | "cancelled";
  attempts: number; max_attempts: number; payload: Record<string, unknown>; result: unknown; error: string | null;
  started_at: string | null; finished_at: string | null; label: string;
}
export interface JobsResponse { worker: WorkerStatus; schedules: Schedule[]; jobs: Job[]; labels: Record<string, string> }
export interface AuditRow { id: string; actor: string; action: string; entity: string | null; entity_id: string | null; details: string | null; created_at: string }

export interface BrandSettings {
  brand_name: string; owner_name: string; website: string; market: string; language: string; timezone: string;
  description: string; positioning: string;
  approved_services: { name: string; status: string }[];
  services_in_development: unknown[];
  target_audiences: { key: string; label: string }[];
  tone_of_voice: string[]; approved_claims: string[]; prohibited_claims: string[]; approved_links: string[];
  contact_details: Record<string, string>; topics_to_cover: string[]; topics_to_avoid: string[]; assumptions: string[];
  [k: string]: unknown;
}

// ── Endpoints ────────────────────────────────────────────────────────────────

export const api = {
  overview: () => apiJson<Overview>("/overview"),
  emergencyPause: (active: boolean) => apiJson<PublishingSettings>("/settings/emergency-pause", { method: "POST", body: json({ active }) }),
  demoSeed: () => apiJson<Record<string, number>>("/demo/seed", { method: "POST" }),
  demoClear: () => apiJson<Record<string, number>>("/demo/clear", { method: "POST" }),

  settings: {
    get: <T>(key: "brand" | "publishing" | "content_mix") => apiJson<T>(`/settings/${key}`),
    put: <T>(key: "brand" | "publishing" | "content_mix", value: unknown) =>
      apiJson<T>(`/settings/${key}`, { method: "PUT", body: json({ value }) }),
  },

  sources: {
    list: (status?: string) =>
      apiJson<{ provider_mode: ProviderMode; llm_mode: ProviderMode; feeds: unknown[]; items: Source[] }>(`/sources${status ? `?status=${status}` : ""}`),
    add: (body: SourceIn) => apiJson<{ created: boolean; source: Source }>("/sources", { method: "POST", body: json(body) }),
    patch: (id: string, body: Partial<Source>) => apiJson<Source>(`/sources/${id}`, { method: "PATCH", body: json(body) }),
    run: () => apiJson<{ job: Job; provider_mode: ProviderMode }>("/research/run", { method: "POST" }),
  },

  ideas: {
    list: () => apiJson<{ llm_mode: ProviderMode; items: Idea[] }>("/ideas"),
    add: (body: IdeaIn) => apiJson<Idea>("/ideas", { method: "POST", body: json(body) }),
    patch: (id: string, body: Partial<Idea>) => apiJson<Idea>(`/ideas/${id}`, { method: "PATCH", body: json(body) }),
    generate: (count = 20) => apiJson<{ llm_mode: ProviderMode; created: number; items: Idea[] }>(`/ideas/generate?count=${count}`, { method: "POST" }),
    draft: (id: string, format?: Format) => apiJson<ContentItem>(`/ideas/${id}/draft`, { method: "POST", body: json({ format: format ?? null }) }),
  },

  items: {
    list: (q?: { status?: string; format?: string }) => {
      const p = new URLSearchParams();
      if (q?.status) p.set("status", q.status);
      if (q?.format) p.set("format", q.format);
      const qs = p.toString();
      return apiJson<{ items: ContentItem[] }>(`/items${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => apiJson<ContentItem>(`/items/${id}`),
    create: (body: { format: Format; title: string; pillar?: string; audience?: string; caption?: string; package?: Package; idea_id?: string }) =>
      apiJson<ContentItem>("/items", { method: "POST", body: json(body) }),
    patch: (id: string, body: Partial<Pick<ContentItem, "title" | "pillar" | "audience" | "package" | "caption" | "asset_ids" | "cover_asset_id" | "scheduled_for" | "format" | "production_status" | "review_notes">>) =>
      apiJson<ContentItem>(`/items/${id}`, { method: "PATCH", body: json(body) }),
    delete: (id: string) => apiJson<{ deleted: boolean }>(`/items/${id}`, { method: "DELETE" }),
    status: (id: string, status: "draft" | "needs_review" | "rejected" | "paused", note?: string) =>
      apiJson<ContentItem>(`/items/${id}/status`, { method: "POST", body: json({ status, note: note ?? null }) }),
    gates: (id: string, forAuto = false) => apiJson<GateReport>(`/items/${id}/gates${forAuto ? "?for_auto=true" : ""}`),
    approve: (id: string) => apiJson<Record<string, unknown>>(`/items/${id}/approve`, { method: "POST" }),
    schedule: (id: string, scheduled_for?: string) =>
      apiJson<Publication>(`/items/${id}/schedule`, { method: "POST", body: json({ scheduled_for: scheduled_for ?? null }) }),
    renderCarousel: (id: string, template?: string | null) =>
      apiJson<{ assets: Asset[]; item: ContentItem; raqm: boolean }>(`/items/${id}/render-carousel`, { method: "POST", body: json({ template: template ?? null }) }),
  },

  carousel: {
    templates: () => apiJson<CarouselTemplates>("/carousel/templates"),
    saveTemplates: (body: CarouselTemplates) => apiJson<CarouselTemplates>("/carousel/templates", { method: "PUT", body: json(body) }),
    preview: (slide: Record<string, unknown>, template: string | null, index: number, total: number, is_demo: boolean) =>
      apiBlob("/carousel/preview", { method: "POST", body: json({ slide, template, index, total, is_demo }) }),
  },

  assets: {
    list: () => apiJson<{ items: Asset[]; allowed_mime: string[]; max_upload_mb: number }>("/assets"),
    upload: (form: FormData) => apiJson<Asset>("/assets", { method: "POST", body: form }),
    patch: (id: string, body: Partial<Pick<Asset, "alt_text" | "caption" | "brief" | "permission_note" | "ownership">>) =>
      apiJson<Asset>(`/assets/${id}`, { method: "PATCH", body: json(body) }),
    delete: (id: string) => apiJson<{ deleted: boolean }>(`/assets/${id}`, { method: "DELETE" }),
    file: (id: string) => apiBlob(`/assets/${id}/file`),
    check: (id: string, usage: string) => apiJson<SpecCheck>(`/assets/${id}/check?usage=${usage}`),
  },

  publications: {
    list: () => apiJson<{ provider_mode: ProviderMode; items: Publication[] }>("/publications"),
    cancel: (id: string) => apiJson<Publication>(`/publications/${id}/cancel`, { method: "POST" }),
    reconcile: (id: string) => apiJson<Publication>(`/publications/${id}/reconcile`, { method: "POST" }),
    resolve: (id: string, body: { outcome: "published" | "failed"; provider_media_id?: string; note?: string }) =>
      apiJson<Publication>(`/publications/${id}/resolve`, { method: "POST", body: json(body) }),
  },

  calendar: (days = 30) => apiJson<{ items: ContentItem[]; proposals: CalendarSlot[]; content_mix: ContentMix }>(`/calendar?days=${days}`),

  instagram: {
    status: () => apiJson<InstagramStatus>("/instagram/status"),
    connectUrl: () => apiJson<{ connect_url: string }>("/instagram/connect-url", { method: "POST" }),
    history: () => apiJson<{ items: HistoryRow[] }>("/instagram/history"),
  },

  inbound: {
    list: () => apiJson<{ outbound_enabled: boolean; permissions: string; items: Inbound[] }>("/inbound"),
    add: (body: { kind: "comment" | "dm"; author?: string; text: string; provider_id?: string }) =>
      apiJson<Inbound>("/inbound", { method: "POST", body: json(body) }),
    draftReply: (id: string) =>
      apiJson<{ llm_mode: ProviderMode; draft: { reply?: string; is_lead?: boolean; flagged?: boolean }; sent: boolean; note: string }>(`/inbound/${id}/draft-reply`, { method: "POST" }),
    patch: (id: string, body: { reply_status: "draft_only" | "approved_not_sent" | "dismissed"; draft_reply?: string }) =>
      apiJson<Inbound>(`/inbound/${id}`, { method: "PATCH", body: json(body) }),
  },

  metrics: {
    get: () => apiJson<MetricsResponse>("/metrics"),
    manual: (body: { scope: "account" | "post"; metric: string; value: number; content_item_id?: string; period_start?: string; period_end?: string; note?: string }) =>
      apiJson<MetricRow>("/metrics/manual", { method: "POST", body: json(body) }),
    refresh: () => apiJson<{ fetched: number; reason?: string; errors?: string[] }>("/metrics/refresh", { method: "POST" }),
  },

  reports: {
    list: () => apiJson<{ items: Report[] }>("/reports"),
    get: (id: string) => apiJson<Report>(`/reports/${id}`),
    weekly: () => apiJson<Report>("/reports/weekly", { method: "POST" }),
  },

  jobs: {
    list: (status?: string) => apiJson<JobsResponse>(`/jobs${status ? `?status=${status}` : ""}`),
    create: (type: string, run_now = true, payload: Record<string, unknown> = {}) =>
      apiJson<Job>("/jobs", { method: "POST", body: json({ type, run_now, payload }) }),
    retry: (id: string) => apiJson<Job>(`/jobs/${id}/retry`, { method: "POST" }),
    patchSchedule: (key: string, body: { hour: number; minute: number; weekday: number | null; enabled: boolean }) =>
      apiJson<Schedule>(`/schedules/${key}`, { method: "PATCH", body: json(body) }),
    tick: () => apiJson<{ enqueued: number; jobs: string[]; publications: string[] }>("/worker/tick", { method: "POST" }),
    audit: (limit = 100) => apiJson<{ items: AuditRow[] }>(`/audit?limit=${limit}`),
  },

  leads: {
    list: () => apiJson<{ items: Lead[]; statuses: string[] }>("/leads"),
    add: (body: Partial<LeadIn> & { name: string }) => apiJson<Lead>("/leads", { method: "POST", body: json(body) }),
    patch: (id: string, body: Partial<LeadIn>) => apiJson<Lead>(`/leads/${id}`, { method: "PATCH", body: json(body) }),
    delete: (id: string) => apiJson<{ deleted: boolean }>(`/leads/${id}`, { method: "DELETE" }),
    purge: (days: number) => apiJson<{ deleted: number }>("/leads/purge", { method: "POST", body: json({ days }) }),
  },
};

// ── Labels ───────────────────────────────────────────────────────────────────

export const FORMAT_LABELS: Record<string, string> = { reel: "רילס", carousel: "קרוסלה", image: "תמונה", story: "סטורי" };
export const AUDIENCE_LABELS: Record<string, string> = { smb: "עסקים קטנים ובינוניים", enterprise: "הנהלה וחברות גדולות", founders: "מייסדים ויזמים" };
export const ITEM_STATUS_LABELS: Record<string, string> = {
  draft: "טיוטה", needs_review: "ממתין לסקירה", approved: "מאושר", scheduled: "מתוזמן", publishing: "בפרסום",
  published: "פורסם", failed: "נכשל", needs_manual_review: "דורש בדיקה ידנית", rejected: "נדחה", paused: "מושהה",
};
export const ITEM_STATUS_ORDER: ItemStatus[] = [
  "draft", "needs_review", "approved", "scheduled", "publishing", "published", "failed", "needs_manual_review", "rejected", "paused",
];
export const PUB_STATE_LABELS: Record<string, string> = {
  queued: "בתור", claimed: "נתפס", container_created: "קונטיינר נוצר", container_ready: "קונטיינר מוכן",
  publish_requested: "בקשת פרסום נשלחה", published: "פורסם", failed: "נכשל", needs_manual_review: "דורש בדיקה ידנית", cancelled: "בוטל",
};
export const SOURCE_STATUS_LABELS: Record<string, string> = { new: "חדש", reviewed: "נסקר", used: "בשימוש", dismissed: "נדחה" };
export const IDEA_STATUS_LABELS: Record<string, string> = { new: "חדש", shortlisted: "ברשימה קצרה", drafted: "נוצרה טיוטה", rejected: "נדחה" };
export const SOURCE_TYPE_LABELS: Record<string, string> = { official: "רשמי", reporting: "דיווח", opinion: "דעה", inference: "הסקה", benchmark: "בנצ'מרק", demo: "demo" };
export const CONFIDENCE_LABELS: Record<string, string> = { low: "נמוך", medium: "בינוני", high: "גבוה" };
export const LEAD_STATUS_LABELS: Record<string, string> = { new: "חדש", contacted: "נוצר קשר", qualified: "מתאים", proposal: "הצעה", won: "נסגר", lost: "אבד", archived: "בארכיון" };
export const JOB_STATUS_LABELS: Record<string, string> = { pending: "ממתין", running: "רץ", succeeded: "הצליח", failed: "נכשל", skipped: "דולג", cancelled: "בוטל" };
export const OWNERSHIP_LABELS: Record<string, string> = { owner_upload: "העלאה של הבעלים", rendered: "רונדר במערכת", generated: "נוצר אוטומטית", third_party: "צד שלישי" };
export const PRODUCTION_LABELS: Record<string, string> = { script_only: "תסריט בלבד", assets_missing: "חסרים נכסים", ready_to_publish: "מוכן לפרסום" };
export const WEEKDAY_LABELS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]; // 0=Mon … 6=Sun

export const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-500/20 text-slate-200 border-slate-400/30",
  needs_review: "bg-amber-500/20 text-amber-200 border-amber-400/40",
  approved: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
  scheduled: "bg-cyan-500/20 text-cyan-200 border-cyan-400/40",
  publishing: "bg-violet-500/20 text-violet-200 border-violet-400/40",
  published: "bg-green-500/25 text-green-200 border-green-400/40",
  failed: "bg-red-500/20 text-red-200 border-red-400/40",
  needs_manual_review: "bg-orange-500/20 text-orange-200 border-orange-400/40",
  rejected: "bg-rose-500/20 text-rose-200 border-rose-400/40",
  paused: "bg-zinc-500/20 text-zinc-200 border-zinc-400/40",
  queued: "bg-cyan-500/20 text-cyan-200 border-cyan-400/40",
  cancelled: "bg-zinc-500/20 text-zinc-200 border-zinc-400/30",
  pending: "bg-slate-500/20 text-slate-200 border-slate-400/30",
  running: "bg-violet-500/20 text-violet-200 border-violet-400/40",
  succeeded: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
  skipped: "bg-zinc-500/20 text-zinc-200 border-zinc-400/30",
};
