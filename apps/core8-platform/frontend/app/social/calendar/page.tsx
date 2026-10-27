"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useLoad } from "@/components/social/hooks";
import { useSocialStatus } from "@/components/social/SocialShell";
import { useToast } from "@/components/social/toast";
import { Button, Card, EmptyState, ErrorBox, Field, Input, Loading, PageHeader, Tabs } from "@/components/social/ui";
import { FORMAT_LABELS, ITEM_STATUS_LABELS, STATUS_COLORS, api, type CalendarSlot, type ContentItem, type ContentMix } from "@/lib/social-api";
import { cn } from "@/lib/utils";

const DAY_NAMES = ["א׳", "ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳"]; // Sunday-first, Israel

function localDateKey(iso: string): string {
  // `*_local` ISO strings carry the Asia/Jerusalem offset; the first 10 chars are the local date.
  return iso.slice(0, 10);
}
function localTime(iso: string): string {
  return iso.slice(11, 16);
}
function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function CalendarPage() {
  const toast = useToast();
  const { overview } = useSocialStatus();
  const { data, loading, error, reload, setData } = useLoad(() => api.calendar(90));
  const [view, setView] = useState<"month" | "week">("month");
  const [cursor, setCursor] = useState(() => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; });
  const [mix, setMix] = useState<ContentMix | null>(null);
  const [saving, setSaving] = useState(false);

  const effectiveMix = mix ?? data?.content_mix ?? null;

  const byDay = useMemo(() => {
    const map = new Map<string, { items: ContentItem[]; slots: CalendarSlot[] }>();
    const get = (k: string) => { if (!map.has(k)) map.set(k, { items: [], slots: [] }); return map.get(k)!; };
    for (const it of data?.items ?? []) if (it.scheduled_for_local) get(localDateKey(it.scheduled_for_local)).items.push(it);
    for (const s of data?.proposals ?? []) get(s.date).slots.push(s);
    return map;
  }, [data]);

  const days = useMemo(() => {
    const out: Date[] = [];
    if (view === "week") {
      const start = new Date(cursor); start.setDate(cursor.getDate() - cursor.getDay());
      for (let i = 0; i < 7; i++) { const d = new Date(start); d.setDate(start.getDate() + i); out.push(d); }
    } else {
      const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
      const start = new Date(first); start.setDate(1 - first.getDay());
      for (let i = 0; i < 42; i++) { const d = new Date(start); d.setDate(start.getDate() + i); out.push(d); }
    }
    return out;
  }, [cursor, view]);

  const move = (dir: -1 | 1) => {
    const d = new Date(cursor);
    if (view === "week") d.setDate(d.getDate() + 7 * dir); else d.setMonth(d.getMonth() + dir);
    setCursor(d);
  };
  const title = view === "week"
    ? `שבוע של ${new Intl.DateTimeFormat("he-IL", { dateStyle: "medium" }).format(days[0])}`
    : new Intl.DateTimeFormat("he-IL", { month: "long", year: "numeric" }).format(cursor);
  const todayKey = ymd(new Date());

  const saveMix = async () => {
    if (!effectiveMix) return;
    setSaving(true);
    try {
      const saved = await api.settings.put<ContentMix>("content_mix", effectiveMix);
      setMix(null);
      setData((d) => d ? { ...d, content_mix: saved } : d);
      toast.success("תמהיל התוכן נשמר — ההצעות יתעדכנו ברענון");
      await reload(true);
    } catch (e) { toast.error(e); } finally { setSaving(false); }
  };

  return (
    <>
      <PageHeader title="לוח פרסומים" subtitle="פריטים מתוזמנים לפי סטטוס, והצעות משבצות (מקווקו) — היפותזה לעריכה, לא הבטחת חשיפה." />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Tabs value={view} onChange={setView} options={[{ value: "month", label: "חודש" }, { value: "week", label: "שבוע" }]} />
        <div className="ms-auto flex items-center gap-1">
          <Button size="sm" variant="ghost" aria-label="קודם" onClick={() => move(-1)}><ChevronRight size={14} /></Button>
          <span className="min-w-[160px] text-center text-sm font-medium">{title}</span>
          <Button size="sm" variant="ghost" aria-label="הבא" onClick={() => move(1)}><ChevronLeft size={14} /></Button>
          <Button size="sm" variant="ghost" onClick={() => { const d = new Date(); d.setHours(0, 0, 0, 0); setCursor(d); }}>היום</Button>
        </div>
      </div>

      {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={() => reload()} /> : (
        <>
          {(data?.items.length ?? 0) === 0 && (data?.proposals.length ?? 0) === 0 && (
            <div className="mb-3"><EmptyState title="אין פריטים מתוזמנים ואין הצעות. תזמן פריט מעמוד הפריט, או הגדר תמהיל תוכן למטה כדי לקבל הצעות משבצות." /></div>
          )}
          <div className="grid grid-cols-7 gap-1 rounded-2xl border border-border bg-card p-2">
            {DAY_NAMES.map((n) => <div key={n} className="py-1 text-center text-[11px] font-semibold text-muted-foreground">{n}</div>)}
            {days.map((d) => {
              const key = ymd(d);
              const cell = byDay.get(key);
              const inMonth = d.getMonth() === cursor.getMonth();
              return (
                <div key={key} className={cn("min-h-[92px] rounded-lg border border-border/50 p-1 text-[11px]", view === "week" && "min-h-[160px]", !inMonth && view === "month" && "opacity-40", key === todayKey && "border-primary/60 bg-primary/5")}>
                  <div className="mb-1 text-muted-foreground">{d.getDate()}</div>
                  <div className="space-y-1">
                    {cell?.items.map((it) => (
                      <Link key={it.id} href={`/social/content/${it.id}`} title={`${it.title} — ${ITEM_STATUS_LABELS[it.status]}`}
                        className={cn("block truncate rounded border px-1 py-0.5 hover:brightness-125", STATUS_COLORS[it.status] ?? "border-border bg-muted")}>
                        {it.scheduled_for_local ? localTime(it.scheduled_for_local) : ""} {FORMAT_LABELS[it.format]} · {it.title}{it.is_demo === 1 ? " (DEMO)" : ""}
                      </Link>
                    ))}
                    {cell?.slots.map((s, i) => (
                      <div key={i} title={`${s.note} · עמוד: ${overview?.pillars.find((p) => p.key === s.pillar_hint)?.label ?? s.pillar_hint}${s.occupied ? " · היום כבר תפוס" : ""}`}
                        className={cn("truncate rounded border border-dashed px-1 py-0.5 text-muted-foreground", s.occupied ? "border-border/40 line-through" : "border-primary/40")}>
                        {localTime(s.local)} {FORMAT_LABELS[s.format]} — הצעה
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">מקרא: צבע מלא = פריט לפי סטטוס · מקווקו = &quot;הצעה — היפותזה&quot; (לא פריט אמיתי) · קו חוצה = היום כבר תפוס.</p>
        </>
      )}

      {effectiveMix && (
        <Card title="תמהיל תוכן שבועי (היפותזה לעריכה)" className="mt-5" actions={<Button variant="primary" size="sm" loading={saving} disabled={!mix} onClick={saveMix}>שמור תמהיל</Button>}>
          <p className="mb-3 text-xs text-muted-foreground">{effectiveMix.note ?? "לא התחייבות אלגוריתמית ולא הבטחת חשיפה."}</p>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="רילס בשבוע">{(id) => <Input id={id} type="number" min={0} max={7} value={effectiveMix.reels_per_week} onChange={(e) => setMix({ ...effectiveMix, reels_per_week: Number(e.target.value) })} />}</Field>
            <Field label="קרוסלות בשבוע">{(id) => <Input id={id} type="number" min={0} max={7} value={effectiveMix.carousels_per_week} onChange={(e) => setMix({ ...effectiveMix, carousels_per_week: Number(e.target.value) })} />}</Field>
            <Field label="ימי סטורי בשבוע">{(id) => <Input id={id} type="number" min={0} max={7} value={effectiveMix.story_days_per_week} onChange={(e) => setMix({ ...effectiveMix, story_days_per_week: Number(e.target.value) })} />}</Field>
          </div>
        </Card>
      )}
    </>
  );
}
