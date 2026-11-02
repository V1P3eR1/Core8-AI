"use client";

import { useState } from "react";
import Link from "next/link";
import { ExternalLink, FileText, RefreshCw } from "lucide-react";
import { useLoad } from "@/components/social/hooks";
import { useToast } from "@/components/social/toast";
import { Badge, Banner, Button, Card, DemoBadge, EmptyState, ErrorBox, Field, Input, Loading, Modal, PageHeader, Select, Table, Td, Textarea, Th } from "@/components/social/ui";
import { JOB_STATUS_LABELS, PUB_STATE_LABELS, api, fmtLocal, fmtUtc, type MetricRow, type Report } from "@/lib/social-api";

const SOURCE_LABELS: Record<string, string> = { api: "API", manual: "ידני", demo: "demo" };
const MANUAL_METRICS = ["reach", "views", "accounts_engaged", "total_interactions", "profile_views", "likes", "comments", "saved", "shares", "leads", "relevant_replies"];

export default function PerformancePage() {
  const toast = useToast();
  const metricsQ = useLoad(() => api.metrics.get());
  const reportsQ = useLoad(() => api.reports.list());
  const [refreshing, setRefreshing] = useState(false);
  const [building, setBuilding] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [manual, setManual] = useState<{ scope: "account" | "post"; metric: string; value: string; content_item_id: string; period_start: string; period_end: string; note: string }>({ scope: "account", metric: "reach", value: "", content_item_id: "", period_start: "", period_end: "", note: "" });
  const [saving, setSaving] = useState(false);
  const [report, setReport] = useState<Report | null>(null);

  const refresh = async () => {
    setRefreshing(true);
    try { const r = await api.metrics.refresh(); toast.push(r.reason ? r.reason : `נמשכו ${r.fetched} מדדים${r.errors?.length ? ` (${r.errors.length} שגיאות)` : ""}`, r.reason ? "info" : "success"); await metricsQ.reload(true); }
    catch (e) { toast.error(e); } finally { setRefreshing(false); }
  };
  const build = async () => {
    setBuilding(true);
    try { const r = await api.reports.weekly(); toast.success("הדוח השבועי נוצר"); await reportsQ.reload(true); setReport(r); }
    catch (e) { toast.error(e); } finally { setBuilding(false); }
  };
  const saveManual = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.metrics.manual({ scope: manual.scope, metric: manual.metric, value: Number(manual.value), content_item_id: manual.content_item_id || undefined, period_start: manual.period_start || undefined, period_end: manual.period_end || undefined, note: manual.note || undefined });
      toast.success("המדד נרשם"); setManualOpen(false); await metricsQ.reload(true);
    } catch (err) { toast.error(err); } finally { setSaving(false); }
  };

  const m = metricsQ.data;
  const labels = m?.account.labels ?? {};

  return (
    <>
      <PageHeader
        title="ביצועים ודוחות"
        subtitle="רק מדדים שהתקבלו מה-API או הוזנו ידנית. שום דבר לא מוערך או מומצא."
        actions={<>
          <Button variant="ghost" onClick={() => setManualOpen(true)}>הזנת מדד ידנית</Button>
          <Button loading={refreshing} onClick={refresh}><RefreshCw size={14} /> רענן מדדים מה-API</Button>
          <Button variant="primary" loading={building} onClick={build}><FileText size={14} /> צור דוח שבועי</Button>
        </>}
      />
      {m && m.provider_mode !== "live" && <div className="mb-4"><Banner kind="warning">ספק Instagram במצב {m.provider_mode} — לא נמשכים מדדים. ניתן להזין מדדים ידנית.</Banner></div>}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="מדדי חשבון (אחרון לכל מדד)" className="lg:col-span-2">
          {metricsQ.loading ? <Loading /> : metricsQ.error ? <ErrorBox message={metricsQ.error} onRetry={() => metricsQ.reload()} /> : (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
                {Object.entries(m!.account.metrics).map(([k, row]) => (
                  <div key={k} className="rounded-xl border border-border bg-background/40 p-3">
                    <p className="text-[11px] text-muted-foreground">{labels[k] ?? k}</p>
                    <p className="text-2xl font-bold">{row.value}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-1 text-[10px] text-muted-foreground">
                      {row.source === "demo" ? <DemoBadge /> : <Badge className="border-border">{SOURCE_LABELS[row.source] ?? row.source}</Badge>}
                      <span>{fmtUtc(row.fetched_at)}</span>
                    </div>
                  </div>
                ))}
                {m!.account.missing.map((k) => (
                  <div key={k} className="rounded-xl border border-dashed border-border p-3 opacity-80">
                    <p className="text-[11px] text-muted-foreground">{labels[k] ?? k}</p>
                    <p className="text-lg font-semibold text-muted-foreground">חסר</p>
                  </div>
                ))}
              </div>
              {Object.keys(m!.account.metrics).length === 0 && <p className="mt-3 text-xs text-muted-foreground">אין מדדי חשבון. חבר חשבון אמיתי ורענן, או הזן ידנית.</p>}
            </>
          )}
        </Card>

        <Card title="דוחות" actions={<Button size="sm" variant="ghost" onClick={() => reportsQ.reload()}>רענן</Button>}>
          {reportsQ.loading ? <Loading /> : (reportsQ.data?.items.length ?? 0) === 0 ? <EmptyState title="אין דוחות. לחץ 'צור דוח שבועי'." /> : (
            <ul className="divide-y divide-border/60 text-sm">
              {reportsQ.data!.items.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-2 py-2">
                  <span>דוח {r.kind === "weekly" ? "שבועי" : r.kind} · {fmtUtc(r.period_start)} → {fmtUtc(r.period_end)}</span>
                  <Button size="sm" variant="ghost" onClick={() => setReport(r)}>פתח</Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="מדדי פוסטים" className="mt-4">
        {metricsQ.loading ? <Loading /> : (m?.posts.length ?? 0) === 0 ? <EmptyState title="אין מדדי פוסטים. מדדים נמשכים לפוסטים שפורסמו בחשבון אמיתי, או מוזנים ידנית עם מזהה פריט." /> : (
          <Table>
            <thead><tr><Th>פריט</Th><Th>מדד</Th><Th>ערך</Th><Th>מקור</Th><Th>נמדד</Th><Th>הערה</Th></tr></thead>
            <tbody>{m!.posts.map((p: MetricRow, i) => (
              <tr key={p.id ?? i}>
                <Td>{p.content_item_id ? <Link href={`/social/content/${p.content_item_id}`} className="hover:text-primary">{p.title ?? p.content_item_id}</Link> : <span dir="ltr" className="text-xs">{p.provider_media_id ?? "חסר"}</span>}</Td>
                <Td>{labels[p.metric] ?? p.metric}</Td>
                <Td className="font-semibold">{p.value}</Td>
                <Td>{p.source === "demo" ? <DemoBadge /> : SOURCE_LABELS[p.source] ?? p.source}</Td>
                <Td className="text-xs whitespace-nowrap">{fmtUtc(p.fetched_at)}</Td>
                <Td className="text-xs text-muted-foreground">{p.note ?? ""}</Td>
              </tr>
            ))}</tbody>
          </Table>
        )}
      </Card>

      <Modal open={manualOpen} onClose={() => setManualOpen(false)} title="הזנת מדד ידנית">
        <form onSubmit={saveManual} className="grid gap-3">
          <Field label="היקף">{(id) => <Select id={id} value={manual.scope} onChange={(e) => setManual({ ...manual, scope: e.target.value as "account" | "post" })}><option value="account">חשבון</option><option value="post">פוסט</option></Select>}</Field>
          <Field label="מדד">{(id) => <Select id={id} value={manual.metric} onChange={(e) => setManual({ ...manual, metric: e.target.value })}>{MANUAL_METRICS.map((k) => <option key={k} value={k}>{labels[k] ?? k}</option>)}</Select>}</Field>
          <Field label="ערך" required>{(id) => <Input id={id} type="number" step="any" required value={manual.value} onChange={(e) => setManual({ ...manual, value: e.target.value })} />}</Field>
          {manual.scope === "post" && <Field label="מזהה פריט תוכן">{(id) => <Input id={id} dir="ltr" value={manual.content_item_id} onChange={(e) => setManual({ ...manual, content_item_id: e.target.value })} />}</Field>}
          <div className="grid grid-cols-2 gap-3">
            <Field label="תחילת תקופה">{(id) => <Input id={id} type="date" value={manual.period_start} onChange={(e) => setManual({ ...manual, period_start: e.target.value })} />}</Field>
            <Field label="סוף תקופה">{(id) => <Input id={id} type="date" value={manual.period_end} onChange={(e) => setManual({ ...manual, period_end: e.target.value })} />}</Field>
          </div>
          <Field label="הערה (מאיפה הנתון)">{(id) => <Textarea id={id} value={manual.note} onChange={(e) => setManual({ ...manual, note: e.target.value })} />}</Field>
          <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setManualOpen(false)}>ביטול</Button><Button type="submit" variant="primary" loading={saving}>שמור</Button></div>
        </form>
      </Modal>

      <Modal open={!!report} onClose={() => setReport(null)} title={report ? `דוח שבועי · ${fmtLocal(report.content.period.start_local)} → ${fmtLocal(report.content.period.end_local)}` : ""} wide>
        {report && <ReportView r={report} />}
      </Modal>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="rounded-xl border border-border/60 p-3"><h3 className="mb-2 text-sm font-semibold text-primary">{title}</h3>{children}</section>;
}

function ReportView({ r }: { r: Report }) {
  const c = r.content;
  return (
    <div className="space-y-3 text-sm">
      <p className="text-xs text-muted-foreground">רשומות demo {c.include_demo ? "נכללות ומסומנות" : "לא נכללות"}.</p>
      <Section title="עבודה שבוצעה">
        <p>{c.work_completed.drafts} טיוטות · {c.work_completed.approvals} אישורים</p>
        {c.work_completed.jobs.length > 0 && <ul className="mt-1 text-xs text-muted-foreground">{c.work_completed.jobs.map((j, i) => <li key={i}>{j.type}: {JOB_STATUS_LABELS[j.status] ?? j.status} × {j.n}</li>)}</ul>}
      </Section>
      <Section title="מחקר">
        {c.research.length === 0 ? <p className="text-muted-foreground">לא נאספו מקורות בתקופה.</p> : (
          <ul className="space-y-1 text-xs">{c.research.map((s, i) => (
            <li key={i}><a href={s.url} target="_blank" rel="noopener noreferrer" className="text-primary">{s.title} <ExternalLink size={10} className="inline" /></a> <span className="text-muted-foreground">· {s.publisher ?? "מפרסם: חסר"} · {s.source_type} · {s.confidence} · {s.trend_verified ? "טרנד מאומת" : "לא מאומת"}</span></li>
          ))}</ul>
        )}
      </Section>
      <Section title="פרסומים">
        <p className="text-xs">פורסמו: {c.publications.published.length} · נכשלו/דורשים בדיקה: {c.publications.failed.length}</p>
        <ul className="mt-1 space-y-0.5 text-xs">
          {[...c.publications.published, ...c.publications.failed].map((p, i) => (
            <li key={i}>{p.title} · {PUB_STATE_LABELS[p.state] ?? p.state} · {p.mode}{p.is_demo ? " · DEMO" : ""}{p.permalink && <> · <a href={p.permalink} className="text-primary" target="_blank" rel="noopener noreferrer">קישור</a></>}{p.last_error && <span className="text-red-300"> · {p.last_error}</span>}</li>
          ))}
        </ul>
      </Section>
      <Section title="מדדים">
        {c.metrics.length === 0 ? <p className="text-muted-foreground">אין מדדים בתקופה.</p> : <ul className="text-xs">{c.metrics.map((x, i) => <li key={i}>{x.scope} · {x.metric}: {x.value} ({x.source})</li>)}</ul>}
      </Section>
      <Section title="מדדים חסרים">{c.missing_metrics.length ? <ul className="list-disc ps-5 text-xs">{c.missing_metrics.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="text-xs">אין</p>}</Section>
      <Section title="לידים">
        {c.leads.length === 0 ? <p className="text-muted-foreground">אין לידים בתקופה.</p> : <ul className="text-xs">{c.leads.map((l, i) => <li key={i}>{l.name} · {l.source ?? "חסר"} · {l.business_type ?? "חסר"} · {l.status}</li>)}</ul>}
      </Section>
      <div className="grid gap-3 md:grid-cols-2">
        <Section title="תצפיות (מה קרה)"><ul className="list-disc ps-5 text-xs">{c.observations.map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
        <Section title="המלצות (מה לעשות)"><ul className="list-disc ps-5 text-xs">{c.recommendations.map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
      </div>
      <Section title="לקחים לשבוע הבא"><ul className="list-disc ps-5 text-xs">{c.lessons_next_week.map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
      <Section title="הסתייגויות"><ul className="list-disc ps-5 text-xs text-yellow-100">{c.caveats.map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
    </div>
  );
}
