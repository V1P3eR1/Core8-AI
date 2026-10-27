"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { useLoad } from "@/components/social/hooks";
import { useSocialStatus } from "@/components/social/SocialShell";
import { useToast } from "@/components/social/toast";
import { Badge, Button, Card, DemoBadge, EmptyState, ErrorBox, Field, Input, Loading, Modal, PageHeader, Select, StatusBadge } from "@/components/social/ui";
import { FORMAT_LABELS, ITEM_STATUS_LABELS, ITEM_STATUS_ORDER, PRODUCTION_LABELS, api, fmtLocal, fmtUtc, isDemo, type ContentItem, type Format } from "@/lib/social-api";

export default function ContentPage() {
  const toast = useToast();
  const router = useRouter();
  const { overview } = useSocialStatus();
  const [status, setStatus] = useState("");
  const [format, setFormat] = useState("");
  const { data, loading, error, reload } = useLoad(() => api.items.list({ status: status || undefined, format: format || undefined }), [status, format]);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<{ format: Format; title: string; pillar: string; caption: string }>({ format: "reel", title: "", pillar: "", caption: "" });
  const [saving, setSaving] = useState(false);

  const items = data?.items ?? [];
  const groups = ITEM_STATUS_ORDER.map((s) => ({ status: s, items: items.filter((i) => i.status === s) })).filter((g) => g.items.length);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const item = await api.items.create({ format: form.format, title: form.title, pillar: form.pillar || undefined, caption: form.caption });
      toast.success("הפריט נוצר");
      router.push(`/social/content/${item.id}`);
    } catch (err) { toast.error(err); setSaving(false); }
  };

  return (
    <>
      <PageHeader
        title="יצירת תוכן"
        subtitle="פריטי תוכן מקובצים לפי סטטוס. לחץ על פריט לעריכת החבילה, הנכסים, התזמון והאישור."
        actions={<Button variant="primary" onClick={() => setCreateOpen(true)}><Plus size={14} /> פריט חדש</Button>}
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Field label="סטטוס">{(id) => (
          <Select id={id} value={status} onChange={(e) => setStatus(e.target.value)} className="w-44 py-1">
            <option value="">הכול</option>
            {ITEM_STATUS_ORDER.map((s) => <option key={s} value={s}>{ITEM_STATUS_LABELS[s]}</option>)}
          </Select>
        )}</Field>
        <Field label="פורמט">{(id) => (
          <Select id={id} value={format} onChange={(e) => setFormat(e.target.value)} className="w-36 py-1">
            <option value="">הכול</option>
            {Object.entries(FORMAT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        )}</Field>
        <span className="self-end pb-2 text-xs text-muted-foreground">{items.length} פריטים</span>
      </div>

      {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={() => reload()} /> : items.length === 0 ? (
        <EmptyState title="אין פריטי תוכן. צור טיוטה מרעיון בעמוד 'רעיונות לתוכן' או צור פריט חדש ידנית." action={<Link href="/social/ideas" className="text-sm text-primary underline">לרעיונות</Link>} />
      ) : (
        <div className="space-y-5">
          {groups.map((g) => (
            <Card key={g.status} title={<span className="flex items-center gap-2"><StatusBadge status={g.status} labels={ITEM_STATUS_LABELS} /><span className="text-xs text-muted-foreground">{g.items.length}</span></span>}>
              <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {g.items.map((it) => <ItemRow key={it.id} item={it} pillarLabel={overview?.pillars.find((p) => p.key === it.pillar)?.label} />)}
              </ul>
            </Card>
          ))}
        </div>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="פריט תוכן חדש">
        <form onSubmit={create} className="grid gap-3">
          <Field label="כותרת" required>{(id) => <Input id={id} required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />}</Field>
          <Field label="פורמט" required>{(id) => (
            <Select id={id} value={form.format} onChange={(e) => setForm({ ...form, format: e.target.value as Format })}>
              {Object.entries(FORMAT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          )}</Field>
          <Field label="עמוד תוכן">{(id) => (
            <Select id={id} value={form.pillar} onChange={(e) => setForm({ ...form, pillar: e.target.value })}>
              <option value="">ללא</option>
              {(overview?.pillars ?? []).map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
            </Select>
          )}</Field>
          <Field label="כיתוב ראשוני">{(id) => <Input id={id} value={form.caption} onChange={(e) => setForm({ ...form, caption: e.target.value })} />}</Field>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>ביטול</Button>
            <Button variant="primary" type="submit" loading={saving}>צור</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

function ItemRow({ item, pillarLabel }: { item: ContentItem; pillarLabel?: string }) {
  return (
    <li>
      <Link href={`/social/content/${item.id}`} className="block rounded-xl border border-border bg-background/40 p-3 transition-colors hover:border-primary/40">
        <div className="mb-1 flex flex-wrap items-center gap-1.5">
          <DemoBadge show={isDemo(item)} />
          <Badge className="border-border bg-muted">{FORMAT_LABELS[item.format]}</Badge>
          {pillarLabel && <Badge className="border-primary/30 bg-primary/10 text-primary">{pillarLabel}</Badge>}
          <Badge className="border-border bg-muted text-muted-foreground">{PRODUCTION_LABELS[item.production_status] ?? item.production_status}</Badge>
          {item.sensitive_flags?.length > 0 && <Badge className="border-orange-400/40 bg-orange-500/15 text-orange-200">{item.sensitive_flags.length} דגלים</Badge>}
        </div>
        <p className="font-medium">{item.title}</p>
        <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.caption || "ללא כיתוב"}</p>
        <p className="mt-2 text-[11px] text-muted-foreground">
          {item.scheduled_for ? `מתוזמן: ${fmtLocal(item.scheduled_for_local)}` : `עודכן: ${fmtUtc(item.updated_at)}`} · גרסה {item.version}
        </p>
      </Link>
    </li>
  );
}
