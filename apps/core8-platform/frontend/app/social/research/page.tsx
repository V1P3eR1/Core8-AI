"use client";

import { useState } from "react";
import { ExternalLink, Plus, Search } from "lucide-react";
import { useLoad } from "@/components/social/hooks";
import { useToast } from "@/components/social/toast";
import { Badge, Banner, Button, Card, DemoBadge, EmptyState, ErrorBox, Field, Input, Loading, Modal, PageHeader, Select, Table, Td, Textarea, Th } from "@/components/social/ui";
import { CONFIDENCE_LABELS, SOURCE_STATUS_LABELS, SOURCE_TYPE_LABELS, api, fmtLocal, fmtDate, isDemo, type Source, type SourceIn } from "@/lib/social-api";

const EMPTY: SourceIn = { title: "", url: "", publisher: "", summary: "", relevance: "", unknowns: "", angle: "", topic: "", published_at: "", event_at: "", source_type: "reporting", confidence: "medium" };

export default function ResearchPage() {
  const toast = useToast();
  const { data, loading, error, reload, setData } = useLoad(() => api.sources.list());
  const [filter, setFilter] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState<SourceIn>(EMPTY);
  const [saving, setSaving] = useState(false);

  const items = (data?.items ?? []).filter((s) => !filter || s.status === filter);
  const live = data?.provider_mode === "live";

  const runResearch = async () => {
    setRunning(true);
    try {
      const r = await api.sources.run();
      toast.success(`ג'וב מחקר ${r.job.status === "succeeded" ? "הסתיים" : `במצב ${r.job.status}`} (ספק: ${r.provider_mode})`);
      await reload(true);
    } catch (e) { toast.error(e); } finally { setRunning(false); }
  };

  const patchStatus = async (s: Source, status: string) => {
    try {
      const row = await api.sources.patch(s.id, { status: status as Source["status"] });
      setData((d) => d ? { ...d, items: d.items.map((x) => (x.id === s.id ? { ...x, ...row } : x)) } : d);
    } catch (e) { toast.error(e); }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const body: SourceIn = { ...form };
      (Object.keys(body) as (keyof SourceIn)[]).forEach((k) => { if (body[k] === "") delete body[k]; });
      const r = await api.sources.add(body);
      toast.success(r.created ? "המקור נוסף" : "המקור כבר קיים (זוהה כפילות לפי URL)");
      setAddOpen(false); setForm(EMPTY); await reload(true);
    } catch (err) { toast.error(err); } finally { setSaving(false); }
  };

  return (
    <>
      <PageHeader
        title="מחקר ומגמות"
        subtitle="מקורות שנאספו אוטומטית או ידנית. 'טרנד מאומת' מסומן רק כשיש ראיה נגישה."
        actions={<>
          <Button variant="ghost" onClick={() => setAddOpen(true)}><Plus size={14} /> הוסף מקור ידנית</Button>
          <Button variant="primary" loading={running} onClick={runResearch}><Search size={14} /> הרץ מחקר עכשיו</Button>
        </>}
      />
      {data && !live && <div className="mb-4"><Banner kind="warning">ספק מחקר לא מחובר ({data.provider_mode}) — מוצגות רשומות demo בלבד. ניתן להוסיף מקורות ידנית.</Banner></div>}

      <Card
        title={`מקורות (${items.length})`}
        actions={
          <label className="flex items-center gap-2 text-xs text-muted-foreground">סטטוס
            <Select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="סינון לפי סטטוס" className="w-36 py-1">
              <option value="">הכול</option>
              {Object.entries(SOURCE_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </label>
        }
      >
        {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={() => reload()} /> : items.length === 0 ? (
          <EmptyState title={filter ? "אין מקורות בסטטוס הזה." : "אין מקורות עדיין. הרץ מחקר עכשיו (או ודא שה-worker פעיל למחקר היומי) או הוסף מקור ידנית."} action={<Button variant="primary" size="sm" onClick={runResearch} loading={running}>הרץ מחקר עכשיו</Button>} />
        ) : (
          <Table>
            <thead><tr>
              <Th>מקור</Th><Th>פורסם / אירוע</Th><Th>נאסף</Th><Th>סיכום ורלוונטיות</Th><Th>סוג / ביטחון</Th><Th>טרנד</Th><Th>זווית</Th><Th>סטטוס</Th>
            </tr></thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id} className="hover:bg-muted/40">
                  <Td className="min-w-[200px]">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <a href={s.url} target="_blank" rel="noopener noreferrer" className="font-medium text-foreground hover:text-primary">{s.title} <ExternalLink size={11} className="inline" /></a>
                      <DemoBadge show={isDemo(s) || s.source_type === "demo"} />
                    </div>
                    <p className="text-xs text-muted-foreground">{s.publisher ?? "מפרסם: חסר"}{s.topic ? ` · ${s.topic}` : ""}</p>
                  </Td>
                  <Td className="whitespace-nowrap text-xs">
                    <div>פורסם: {fmtLocal(s.published_at_local)}</div>
                    <div className="text-muted-foreground">אירוע: {s.event_at ? fmtDate(s.event_at_local ?? s.event_at) : "חסר"}</div>
                  </Td>
                  <Td className="whitespace-nowrap text-xs">{fmtLocal(s.discovered_at_local)}</Td>
                  <Td className="min-w-[240px] max-w-md text-xs">
                    <p>{s.summary ?? <span className="text-muted-foreground">סיכום: חסר</span>}</p>
                    {s.relevance && <p className="mt-1 text-primary/90">למה רלוונטי: {s.relevance}</p>}
                    {s.unknowns && <p className="mt-1 text-muted-foreground">לא ידוע: {s.unknowns}</p>}
                  </Td>
                  <Td className="text-xs whitespace-nowrap">
                    <div>{SOURCE_TYPE_LABELS[s.source_type] ?? s.source_type}</div>
                    <div className="text-muted-foreground">ביטחון: {CONFIDENCE_LABELS[s.confidence] ?? s.confidence}</div>
                  </Td>
                  <Td>
                    {s.trend_verified === 1
                      ? <Badge className="border-emerald-400/40 bg-emerald-500/15 text-emerald-200">טרנד מאומת</Badge>
                      : <Badge className="border-border bg-muted text-muted-foreground" title="אין ראיה נגישה לטרנד">נושא רלוונטי — טרנד לא מאומת</Badge>}
                  </Td>
                  <Td className="max-w-xs text-xs">{s.angle ?? <span className="text-muted-foreground">חסר</span>}</Td>
                  <Td>
                    <Select value={s.status} onChange={(e) => patchStatus(s, e.target.value)} aria-label={`סטטוס עבור ${s.title}`} className="w-28 py-1 text-xs">
                      {Object.entries(SOURCE_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </Select>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="הוספת מקור ידנית" wide>
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
          <Field label="כותרת" required>{(id) => <Input id={id} required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />}</Field>
          <Field label="URL" required hint="חייב להתחיל ב-http:// או https://">{(id) => <Input id={id} required type="url" dir="ltr" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />}</Field>
          <Field label="מפרסם">{(id) => <Input id={id} value={form.publisher} onChange={(e) => setForm({ ...form, publisher: e.target.value })} />}</Field>
          <Field label="נושא">{(id) => <Input id={id} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} />}</Field>
          <Field label="תאריך פרסום">{(id) => <Input id={id} type="date" value={form.published_at} onChange={(e) => setForm({ ...form, published_at: e.target.value })} />}</Field>
          <Field label="תאריך אירוע">{(id) => <Input id={id} type="date" value={form.event_at} onChange={(e) => setForm({ ...form, event_at: e.target.value })} />}</Field>
          <Field label="סוג מקור">{(id) => (
            <Select id={id} value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value as SourceIn["source_type"] })}>
              {(["official", "reporting", "opinion", "inference", "benchmark"] as const).map((k) => <option key={k} value={k}>{SOURCE_TYPE_LABELS[k]}</option>)}
            </Select>
          )}</Field>
          <Field label="רמת ביטחון">{(id) => (
            <Select id={id} value={form.confidence} onChange={(e) => setForm({ ...form, confidence: e.target.value as SourceIn["confidence"] })}>
              {(["low", "medium", "high"] as const).map((k) => <option key={k} value={k}>{CONFIDENCE_LABELS[k]}</option>)}
            </Select>
          )}</Field>
          <Field label="סיכום" className="sm:col-span-2">{(id) => <Textarea id={id} value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} />}</Field>
          <Field label="למה זה רלוונטי ל-Core8AI">{(id) => <Textarea id={id} value={form.relevance} onChange={(e) => setForm({ ...form, relevance: e.target.value })} />}</Field>
          <Field label="מה לא ידוע">{(id) => <Textarea id={id} value={form.unknowns} onChange={(e) => setForm({ ...form, unknowns: e.target.value })} />}</Field>
          <Field label="זווית תוכן מקורית" className="sm:col-span-2">{(id) => <Input id={id} value={form.angle} onChange={(e) => setForm({ ...form, angle: e.target.value })} />}</Field>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <Button variant="ghost" onClick={() => setAddOpen(false)}>ביטול</Button>
            <Button variant="primary" type="submit" loading={saving}>שמור מקור</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
