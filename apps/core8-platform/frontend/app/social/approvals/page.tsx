"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, X } from "lucide-react";
import AssetThumb from "@/components/social/AssetThumb";
import { useLoad } from "@/components/social/hooks";
import { useSocialStatus } from "@/components/social/SocialShell";
import { useToast } from "@/components/social/toast";
import { Badge, Button, Card, DemoBadge, EmptyState, ErrorBox, Field, Input, Loading, PageHeader, StatusBadge, Tabs } from "@/components/social/ui";
import { FORMAT_LABELS, ITEM_STATUS_LABELS, api, fmtLocal, isDemo, toInputDateTime, type Asset, type ContentItem, type GateReport } from "@/lib/social-api";

const STATUSES = ["needs_review", "approved", "needs_manual_review"] as const;
type S = (typeof STATUSES)[number];

export default function ApprovalsPage() {
  const [tab, setTab] = useState<S>("needs_review");
  const { data, loading, error, reload } = useLoad(async () => {
    const [items, assets] = await Promise.all([api.items.list(), api.assets.list()]);
    return { items: items.items, assets: assets.items };
  });
  const items = (data?.items ?? []).filter((i) => i.status === tab);
  const counts = Object.fromEntries(STATUSES.map((s) => [s, (data?.items ?? []).filter((i) => i.status === s).length])) as Record<S, number>;

  return (
    <>
      <PageHeader title="אישורים" subtitle="סקירה אנושית לפני פרסום. אישור נקשר לגרסה המדויקת (כיתוב, נכסים, תזמון, חשבון) — כל שינוי מבטל אותו." />
      <div className="mb-4">
        <Tabs value={tab} onChange={setTab} options={STATUSES.map((s) => ({ value: s, label: ITEM_STATUS_LABELS[s], count: counts[s] }))} />
      </div>
      {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={() => reload()} /> : items.length === 0 ? (
        <EmptyState title={
          tab === "needs_review" ? "אין פריטים הממתינים לסקירה. שלח פריט לסקירה מעמוד הפריט ב'יצירת תוכן'."
          : tab === "approved" ? "אין פריטים מאושרים שטרם תוזמנו. אשר פריט בלשונית 'ממתין לסקירה'."
          : "אין פריטים הדורשים בדיקה ידנית — מצב טוב."
        } action={<Link href="/social/content" className="text-sm text-primary underline">ליצירת תוכן</Link>} />
      ) : (
        <div className="space-y-4">
          {items.map((it) => <ApprovalCard key={it.id} item={it} assets={data?.assets ?? []} onChanged={() => reload(true)} />)}
        </div>
      )}
    </>
  );
}

function ApprovalCard({ item, assets, onChanged }: { item: ContentItem; assets: Asset[]; onChanged: () => void }) {
  const toast = useToast();
  const { overview, refresh } = useSocialStatus();
  const gates = useLoad<GateReport>(() => api.items.gates(item.id), [item.id, item.version]);
  const [schedule, setSchedule] = useState(toInputDateTime(item.scheduled_for_local));
  const [busy, setBusy] = useState<string | null>(null);
  const itemAssets = item.asset_ids.map((id) => assets.find((a) => a.id === id)).filter((a): a is Asset => !!a);
  const act = async (key: string, fn: () => Promise<void>, ok: string) => {
    setBusy(key);
    try { await fn(); toast.success(ok); onChanged(); refresh(); } catch (e) { toast.error(e); } finally { setBusy(null); }
  };
  return (
    <Card as="article">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <DemoBadge show={isDemo(item)} />
            <StatusBadge status={item.status} labels={ITEM_STATUS_LABELS} />
            <Badge className="border-border bg-muted">{FORMAT_LABELS[item.format]}</Badge>
            <Badge className="border-primary/30 bg-primary/10 text-primary">{overview?.pillars.find((p) => p.key === item.pillar)?.label ?? item.pillar ?? "ללא עמוד"}</Badge>
            {item.sensitive_flags.length > 0 && <Badge className="border-orange-400/40 bg-orange-500/15 text-orange-200">דגלים: {item.sensitive_flags.join(", ")}</Badge>}
          </div>
          <Link href={`/social/content/${item.id}`} className="text-lg font-semibold hover:text-primary">{item.title}</Link>
          <p className="mt-2 whitespace-pre-wrap rounded-lg border border-border/60 bg-background/40 p-3 text-sm leading-relaxed">{item.caption || <span className="text-muted-foreground">ללא כיתוב</span>}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {itemAssets.length === 0 ? <p className="text-xs text-muted-foreground">אין נכסים משויכים.</p> : itemAssets.map((a) => <AssetThumb key={a.id} asset={a} />)}
          </div>
          {item.review_notes && <p className="mt-2 text-xs text-muted-foreground">הערות: {item.review_notes}</p>}
          {item.fact_check?.findings?.length ? (
            <ul className="mt-2 space-y-1 text-xs">
              {item.fact_check.findings.map((f, i) => <li key={i} className="text-orange-200">• {f.label}: <span className="text-muted-foreground">…{f.excerpt}…</span></li>)}
            </ul>
          ) : null}
        </div>
        <div className="space-y-3">
          <div className="rounded-lg border border-border/60 p-3 text-xs">
            <p className="mb-1 font-medium">שערי פרסום</p>
            {gates.loading ? <Loading label="בודק…" /> : gates.data ? (
              <ul className="space-y-0.5">{gates.data.checks.map((c) => <li key={c.code} className={c.ok ? "text-emerald-200" : "text-red-200"}>{c.ok ? "✓" : "✗"} {c.label}</li>)}</ul>
            ) : <span className="text-muted-foreground">חסר</span>}
          </div>
          <Field label="תזמון (שעון ישראל)">{(id) => <Input id={id} type="datetime-local" dir="ltr" value={schedule} onChange={(e) => setSchedule(e.target.value)} />}</Field>
          <p className="text-[11px] text-muted-foreground">מתוזמן כעת: {item.scheduled_for ? fmtLocal(item.scheduled_for_local) : "חסר"}</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="success" size="sm" loading={busy === "approve"} onClick={() => act("approve", async () => { await api.items.approve(item.id); }, "אושר")}><Check size={13} /> אשר</Button>
            <Button variant="primary" size="sm" disabled={!schedule} loading={busy === "schedule"} onClick={() => act("schedule", async () => { await api.items.schedule(item.id, schedule); }, "תוזמן והוכנס לתור")}>תזמן</Button>
            <Button variant="danger" size="sm" loading={busy === "reject"} onClick={() => act("reject", async () => { await api.items.status(item.id, "rejected"); }, "נדחה")}><X size={13} /> דחה</Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
