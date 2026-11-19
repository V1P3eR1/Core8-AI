"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, Plus, Sparkles } from "lucide-react";
import { useLoad } from "@/components/social/hooks";
import { useSocialStatus } from "@/components/social/SocialShell";
import { useToast } from "@/components/social/toast";
import { Badge, Banner, Button, Card, DemoBadge, EmptyState, ErrorBox, Field, Input, KV, Loading, Modal, PageHeader, Select, Textarea } from "@/components/social/ui";
import { AUDIENCE_LABELS, FORMAT_LABELS, IDEA_STATUS_LABELS, api, isDemo, type Format, type Idea, type IdeaIn } from "@/lib/social-api";

const EMPTY: IdeaIn = { title: "", pillar: "", audience: "smb", problem: "", core_message: "", desired_action: "", format: "reel", business_goal: "", measurement: "", notes: "" };

export default function IdeasPage() {
  const toast = useToast();
  const router = useRouter();
  const { overview } = useSocialStatus();
  const pillars = overview?.pillars ?? [];
  const pillarLabel = (k: string) => pillars.find((p) => p.key === k)?.label ?? k;
  const { data, loading, error, reload, setData } = useLoad(() => api.ideas.list());
  const [filter, setFilter] = useState("");
  const [generating, setGenerating] = useState(false);
  const [drafting, setDrafting] = useState<string | null>(null);
  const [draftFormat, setDraftFormat] = useState<Record<string, Format | "">>({});
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState<IdeaIn>(EMPTY);
  const [saving, setSaving] = useState(false);

  const items = (data?.items ?? []).filter((i) => !filter || i.status === filter);

  const generate = async () => {
    setGenerating(true);
    try {
      const r = await api.ideas.generate(20);
      toast.success(`נוצרו ${r.created} רעיונות (LLM: ${r.llm_mode})`);
      await reload(true);
    } catch (e) { toast.error(e); } finally { setGenerating(false); }
  };

  const patch = async (idea: Idea, status: string) => {
    try {
      const row = await api.ideas.patch(idea.id, { status: status as Idea["status"] });
      setData((d) => d ? { ...d, items: d.items.map((x) => (x.id === idea.id ? { ...x, ...row } : x)) } : d);
    } catch (e) { toast.error(e); }
  };

  const draft = async (idea: Idea) => {
    setDrafting(idea.id);
    try {
      const item = await api.ideas.draft(idea.id, draftFormat[idea.id] || undefined);
      toast.success("הטיוטה נוצרה — עוברים לעריכה");
      router.push(`/social/content/${item.id}`);
    } catch (e) { toast.error(e); setDrafting(null); }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.ideas.add({ ...form, notes: form.notes || undefined });
      toast.success("הרעיון נוסף");
      setAddOpen(false); setForm(EMPTY); await reload(true);
    } catch (err) { toast.error(err); } finally { setSaving(false); }
  };

  return (
    <>
      <PageHeader
        title="רעיונות לתוכן"
        subtitle="כל רעיון מחובר לעמוד תוכן, קהל, בעיה, מסר, פעולה רצויה, מטרה עסקית ואופן מדידה."
        actions={<>
          <Button variant="ghost" onClick={() => setAddOpen(true)}><Plus size={14} /> הוסף רעיון</Button>
          <Button variant="primary" loading={generating} onClick={generate}><Sparkles size={14} /> צור 20 רעיונות</Button>
        </>}
      />
      {data && data.llm_mode !== "live" && <div className="mb-4"><Banner kind="info">LLM במצב {data.llm_mode} — רעיונות וטיוטות נוצרים מתבניות ללא מודל שפה ומסומנים לעריכה.</Banner></div>}

      <div className="mb-3 flex items-center gap-2">
        <label className="text-xs text-muted-foreground" htmlFor="idea-filter">סטטוס</label>
        <Select id="idea-filter" value={filter} onChange={(e) => setFilter(e.target.value)} className="w-40 py-1">
          <option value="">הכול</option>
          {Object.entries(IDEA_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <span className="text-xs text-muted-foreground">{items.length} רעיונות</span>
      </div>

      {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={() => reload()} /> : items.length === 0 ? (
        <EmptyState title="אין רעיונות עדיין. לחץ 'צור 20 רעיונות' כדי לייצר מהמקורות שנאספו, או הוסף רעיון ידנית." action={<Button variant="primary" size="sm" onClick={generate} loading={generating}>צור 20 רעיונות</Button>} />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {items.map((idea) => (
            <Card key={idea.id} as="article" className="flex flex-col">
              <div className="mb-2 flex flex-wrap items-center gap-1.5">
                <DemoBadge show={isDemo(idea)} />
                <Badge className="border-primary/30 bg-primary/10 text-primary">{pillarLabel(idea.pillar)}</Badge>
                <Badge className="border-border bg-muted">{FORMAT_LABELS[idea.format]}</Badge>
                <Badge className="border-border bg-muted">{AUDIENCE_LABELS[idea.audience] ?? idea.audience}</Badge>
              </div>
              <h3 className="mb-2 font-semibold leading-snug">{idea.title}</h3>
              <dl className="grid flex-1 grid-cols-1 gap-2 text-sm">
                <KV label="הבעיה">{idea.problem}</KV>
                <KV label="המסר המרכזי">{idea.core_message}</KV>
                <KV label="פעולה רצויה">{idea.desired_action}</KV>
                <KV label="מטרה עסקית">{idea.business_goal}</KV>
                <KV label="מדידה">{idea.measurement}</KV>
                {idea.notes && <KV label="הערות">{idea.notes}</KV>}
              </dl>
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
                <Select value={idea.status} onChange={(e) => patch(idea, e.target.value)} aria-label={`סטטוס עבור ${idea.title}`} className="w-32 py-1 text-xs">
                  {Object.entries(IDEA_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select>
                <Select value={draftFormat[idea.id] ?? ""} onChange={(e) => setDraftFormat({ ...draftFormat, [idea.id]: e.target.value as Format | "" })} aria-label="פורמט לטיוטה" className="w-28 py-1 text-xs">
                  <option value="">פורמט הרעיון</option>
                  {Object.entries(FORMAT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select>
                <Button size="sm" variant="primary" className="ms-auto" loading={drafting === idea.id} onClick={() => draft(idea)}><FileText size={13} /> צור טיוטה</Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="הוספת רעיון" wide>
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
          <Field label="כותרת" required className="sm:col-span-2">{(id) => <Input id={id} required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />}</Field>
          <Field label="עמוד תוכן (pillar)" required>{(id) => (
            <Select id={id} required value={form.pillar} onChange={(e) => setForm({ ...form, pillar: e.target.value })}>
              <option value="">בחר…</option>
              {pillars.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
            </Select>
          )}</Field>
          <Field label="קהל יעד" required>{(id) => (
            <Select id={id} value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value as IdeaIn["audience"] })}>
              {Object.entries(AUDIENCE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          )}</Field>
          <Field label="פורמט" required>{(id) => (
            <Select id={id} value={form.format} onChange={(e) => setForm({ ...form, format: e.target.value as Format })}>
              {Object.entries(FORMAT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          )}</Field>
          <Field label="מטרה עסקית" required>{(id) => <Input id={id} required value={form.business_goal} onChange={(e) => setForm({ ...form, business_goal: e.target.value })} />}</Field>
          <Field label="הבעיה" required>{(id) => <Textarea id={id} required value={form.problem} onChange={(e) => setForm({ ...form, problem: e.target.value })} />}</Field>
          <Field label="המסר המרכזי" required>{(id) => <Textarea id={id} required value={form.core_message} onChange={(e) => setForm({ ...form, core_message: e.target.value })} />}</Field>
          <Field label="פעולה רצויה" required>{(id) => <Input id={id} required value={form.desired_action} onChange={(e) => setForm({ ...form, desired_action: e.target.value })} />}</Field>
          <Field label="איך נמדוד" required>{(id) => <Input id={id} required value={form.measurement} onChange={(e) => setForm({ ...form, measurement: e.target.value })} />}</Field>
          <Field label="הערות" className="sm:col-span-2">{(id) => <Textarea id={id} value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} />}</Field>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <Button variant="ghost" onClick={() => setAddOpen(false)}>ביטול</Button>
            <Button variant="primary" type="submit" loading={saving}>שמור רעיון</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
