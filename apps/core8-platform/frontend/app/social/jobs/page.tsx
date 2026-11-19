"use client";

import { useState } from "react";
import { Play, RefreshCw, RotateCcw, Zap } from "lucide-react";
import { useLoad } from "@/components/social/hooks";
import { useSocialStatus } from "@/components/social/SocialShell";
import { useToast } from "@/components/social/toast";
import { Badge, Banner, Button, Card, Checkbox, EmptyState, ErrorBox, Input, Loading, PageHeader, Select, StatusBadge, Table, Td, Th } from "@/components/social/ui";
import { JOB_STATUS_LABELS, WEEKDAY_LABELS, api, fmtLocal, fmtUtc, type Schedule } from "@/lib/social-api";

const RUN_NOW_TYPES = ["research", "ideas", "drafts", "planning", "weekly_report", "metrics", "token_check"] as const;

export default function JobsPage() {
  const toast = useToast();
  const { refresh } = useSocialStatus();
  const [statusFilter, setStatusFilter] = useState("");
  const { data, loading, error, reload } = useLoad(() => api.jobs.list(statusFilter || undefined), [statusFilter]);
  const auditQ = useLoad(() => api.jobs.audit(100));
  const [busy, setBusy] = useState<string | null>(null);

  const act = async (key: string, fn: () => Promise<unknown>, ok: (r: unknown) => string) => {
    setBusy(key);
    try { const r = await fn(); toast.success(ok(r)); await Promise.all([reload(true), auditQ.reload(true)]); refresh(); }
    catch (e) { toast.error(e); } finally { setBusy(null); }
  };

  const w = data?.worker;
  const labels = data?.labels ?? {};

  return (
    <>
      <PageHeader
        title="אוטומציות ולוגים"
        subtitle="ה-worker (תהליך נפרד) מריץ לוחות זמנים, ג'ובים ופרסומים. tick ידני מריץ איטרציה אחת בתוך ה-API."
        actions={<>
          <Button variant="ghost" onClick={() => { reload(); auditQ.reload(); }}><RefreshCw size={14} /> רענן</Button>
          <Button loading={busy === "tick"} onClick={() => act("tick", () => api.jobs.tick(), (r) => { const t = r as { enqueued: number; jobs: string[]; publications: string[] }; return `tick: ${t.enqueued} הוכנסו לתור, ${t.jobs.length} ג'ובים רצו, ${t.publications.length} פרסומים`; })}><Zap size={14} /> הרץ tick</Button>
        </>}
      />

      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={() => reload()} /> : data && (
        <div className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="מצב worker" className={w?.online ? "border-emerald-400/30" : "border-red-400/40"}>
              {!w?.online && <div className="mb-3"><Banner kind="danger">ה-worker לא פעיל — ג&apos;ובים ופרסומים לא ירוצו. הפעל: <code dir="ltr" className="rounded bg-muted px-1 text-xs">python -m social.worker</code></Banner></div>}
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <dt className="text-muted-foreground">מצב</dt><dd className={w?.online ? "text-emerald-200" : "text-red-200"}>{w?.online ? "פעיל" : "לא פעיל"}</dd>
                <dt className="text-muted-foreground">מזהה</dt><dd dir="ltr" className="truncate text-xs">{w?.worker_id ?? "חסר"}</dd>
                <dt className="text-muted-foreground">פעימה אחרונה</dt><dd className="text-xs">{fmtUtc(w?.heartbeat_at)}</dd>
                <dt className="text-muted-foreground">נחשב לא פעיל אחרי</dt><dd className="text-xs">{w?.stale_after_seconds} שניות</dd>
                <dt className="text-muted-foreground">בתוך תהליך ה-API</dt><dd className="text-xs">{w?.inprocess ? "כן" : "לא"}</dd>
              </dl>
            </Card>
            <Card title="הרץ עכשיו" className="lg:col-span-2">
              <p className="mb-2 text-xs text-muted-foreground">מכניס ג&apos;וב לתור ומריץ אותו מיד בתוך ה-API (לא דורש worker).</p>
              <div className="flex flex-wrap gap-2">
                {RUN_NOW_TYPES.map((t) => (
                  <Button key={t} size="sm" loading={busy === `run:${t}`} onClick={() => act(`run:${t}`, () => api.jobs.create(t, true), (r) => `${labels[t] ?? t}: ${JOB_STATUS_LABELS[(r as { status: string }).status] ?? (r as { status: string }).status}`)}>
                    <Play size={12} /> {labels[t] ?? t}
                  </Button>
                ))}
              </div>
            </Card>
          </div>

          <Card title="לוחות זמנים (שעון ישראל)">
            {data.schedules.length === 0 ? <EmptyState title="אין לוחות זמנים. הם נוצרים אוטומטית בטעינה הראשונה." /> : (
              <Table>
                <thead><tr><Th>לוח</Th><Th>סוג</Th><Th>שעה</Th><Th>יום</Th><Th>פעיל</Th><Th>ריצה אחרונה</Th><Th>ריצה הבאה</Th><Th></Th></tr></thead>
                <tbody>{data.schedules.map((s) => <ScheduleRow key={s.key} s={s} onSaved={() => reload(true)} />)}</tbody>
              </Table>
            )}
          </Card>

          <Card title="ג'ובים" actions={
            <label className="flex items-center gap-2 text-xs text-muted-foreground">סטטוס
              <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="סינון ג'ובים לפי סטטוס" className="w-32 py-1">
                <option value="">הכול</option>
                {Object.entries(JOB_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            </label>
          }>
            {data.jobs.length === 0 ? <EmptyState title="אין ג'ובים. הרץ אחד מהכפתורים למעלה או המתן ללוח הזמנים." /> : (
              <Table>
                <thead><tr><Th>סוג</Th><Th>סטטוס</Th><Th>מועד ריצה</Th><Th>ניסיונות</Th><Th>תוצאה / שגיאה</Th><Th></Th></tr></thead>
                <tbody>{data.jobs.map((j) => (
                  <tr key={j.id}>
                    <Td>{j.label}{j.schedule_key && <span className="block text-[10px] text-muted-foreground">{j.schedule_key}</span>}</Td>
                    <Td><StatusBadge status={j.status} labels={JOB_STATUS_LABELS} /></Td>
                    <Td className="text-xs whitespace-nowrap">{fmtLocal(j.run_at_local)}{j.finished_at && <span className="block text-muted-foreground">הסתיים {fmtUtc(j.finished_at)}</span>}</Td>
                    <Td>{j.attempts}/{j.max_attempts}</Td>
                    <Td className="max-w-md text-xs">
                      {j.error && <p className="text-red-300">{j.error}</p>}
                      {j.result != null && <p className="truncate text-muted-foreground" dir="ltr" title={JSON.stringify(j.result)}>{summarise(j.result)}</p>}
                    </Td>
                    <Td>{(j.status === "failed" || j.status === "skipped" || j.status === "cancelled") && <Button size="sm" variant="ghost" loading={busy === `retry:${j.id}`} onClick={() => act(`retry:${j.id}`, () => api.jobs.retry(j.id), () => "הג'וב הוכנס שוב לתור")}><RotateCcw size={12} /> הרץ מחדש</Button>}</Td>
                  </tr>
                ))}</tbody>
              </Table>
            )}
          </Card>

          <Card title="יומן ביקורת (audit)">
            {auditQ.loading ? <Loading /> : auditQ.error ? <ErrorBox message={auditQ.error} /> : (auditQ.data?.items.length ?? 0) === 0 ? <EmptyState title="אין רשומות ביקורת עדיין." /> : (
              <Table>
                <thead><tr><Th>זמן</Th><Th>מבצע</Th><Th>פעולה</Th><Th>ישות</Th><Th>פרטים</Th></tr></thead>
                <tbody>{auditQ.data!.items.map((a) => (
                  <tr key={a.id}>
                    <Td className="text-xs whitespace-nowrap">{fmtUtc(a.created_at)}</Td>
                    <Td className="text-xs">{a.actor}</Td>
                    <Td><Badge className="border-border bg-muted" title={a.action}>{a.action}</Badge></Td>
                    <Td className="text-xs">{a.entity ?? ""}{a.entity_id && <span className="block text-muted-foreground" dir="ltr">{a.entity_id}</span>}</Td>
                    <Td className="max-w-md truncate text-xs text-muted-foreground" dir="ltr" title={a.details ?? ""}>{a.details ?? ""}</Td>
                  </tr>
                ))}</tbody>
              </Table>
            )}
          </Card>
        </div>
      )}
    </>
  );
}

function summarise(result: unknown): string {
  if (typeof result === "string") return result;
  if (result && typeof result === "object") {
    return Object.entries(result as Record<string, unknown>).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ");
  }
  return String(result);
}

function ScheduleRow({ s, onSaved }: { s: Schedule; onSaved: () => void }) {
  const toast = useToast();
  const [hour, setHour] = useState(s.hour);
  const [minute, setMinute] = useState(s.minute);
  const [weekday, setWeekday] = useState<string>(s.weekday == null ? "" : String(s.weekday));
  const [enabled, setEnabled] = useState(s.enabled === 1);
  const [saving, setSaving] = useState(false);
  const dirty = hour !== s.hour || minute !== s.minute || weekday !== (s.weekday == null ? "" : String(s.weekday)) || enabled !== (s.enabled === 1);
  const save = async () => {
    setSaving(true);
    try { await api.jobs.patchSchedule(s.key, { hour, minute, weekday: weekday === "" ? null : Number(weekday), enabled }); toast.success(`לוח "${s.label}" עודכן`); onSaved(); }
    catch (e) { toast.error(e); } finally { setSaving(false); }
  };
  return (
    <tr>
      <Td><span className="font-medium">{s.label}</span><span className="block text-[10px] text-muted-foreground" dir="ltr">{s.key}</span></Td>
      <Td className="text-xs">{s.job_label}</Td>
      <Td><div className="flex items-center gap-1" dir="ltr">
        <Input aria-label={`שעה ${s.label}`} type="number" min={0} max={23} value={hour} onChange={(e) => setHour(Number(e.target.value))} className="w-16 py-1" />:
        <Input aria-label={`דקה ${s.label}`} type="number" min={0} max={59} value={minute} onChange={(e) => setMinute(Number(e.target.value))} className="w-16 py-1" />
      </div></Td>
      <Td>
        <Select aria-label={`יום ${s.label}`} value={weekday} onChange={(e) => setWeekday(e.target.value)} className="w-28 py-1">
          <option value="">כל יום</option>
          {WEEKDAY_LABELS.map((l, i) => <option key={i} value={i}>{l}</option>)}
        </Select>
      </Td>
      <Td><Checkbox label="" aria-label={`פעיל ${s.label}`} checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /></Td>
      <Td className="text-xs whitespace-nowrap">{fmtLocal(s.last_run_at_local)}</Td>
      <Td className="text-xs whitespace-nowrap">{fmtLocal(s.next_run_at_local)}</Td>
      <Td><Button size="sm" variant="primary" disabled={!dirty} loading={saving} onClick={save}>שמור</Button></Td>
    </tr>
  );
}
