"use client";

import Link from "next/link";
import { useState } from "react";
import { Pause, Play, RefreshCw } from "lucide-react";
import { useSocialStatus } from "@/components/social/SocialShell";
import { useToast } from "@/components/social/toast";
import { Badge, Button, Card, ConfirmButton, DemoBadge, EmptyState, KV, Loading, PageHeader, StatusBadge } from "@/components/social/ui";
import { FORMAT_LABELS, ITEM_STATUS_LABELS, api, fmtLocal, fmtUtc } from "@/lib/social-api";

const COUNT_CARDS: { key: string; label: string; href: string }[] = [
  { key: "sources_new", label: "מקורות חדשים", href: "/social/research" },
  { key: "ideas_new", label: "רעיונות פתוחים", href: "/social/ideas" },
  { key: "items_needs_review", label: "ממתינים לסקירה", href: "/social/approvals" },
  { key: "items_scheduled", label: "מתוזמנים", href: "/social/calendar" },
  { key: "items_manual_review", label: "דורשים בדיקה ידנית", href: "/social/approvals" },
  { key: "publications_failed", label: "פרסומים שנכשלו", href: "/social/instagram" },
  { key: "leads_open", label: "לידים פתוחים", href: "/social/leads" },
  { key: "jobs_failed", label: "ג'ובים שנכשלו", href: "/social/jobs" },
  { key: "demo_records", label: "רשומות DEMO", href: "/social/brand" },
];

export default function OverviewPage() {
  const { overview, refresh } = useSocialStatus();
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  if (!overview) return <Loading label="טוען סקירה…" />;

  const act = async (key: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(key);
    try { await fn(); await refresh(); toast.success(ok); } catch (e) { toast.error(e); } finally { setBusy(null); }
  };
  const paused = overview.publishing.emergency_pause;

  return (
    <>
      <PageHeader
        title="סקירה כללית"
        subtitle={`אזור זמן: ${overview.timezone} · מצב פרסום: ${{ draft_only: "טיוטות בלבד", approval_required: "דורש אישור", automatic: "אוטומטי" }[overview.publishing.mode]}`}
        actions={<Button variant="ghost" size="sm" onClick={() => refresh()}><RefreshCw size={14} /> רענן</Button>}
      />

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {COUNT_CARDS.map((c) => (
          <Link key={c.key} href={c.href} className="rounded-2xl border border-border bg-card p-3 transition-colors hover:border-primary/40">
            <p className="text-[11px] text-muted-foreground">{c.label}</p>
            <p className={`mt-1 text-2xl font-bold ${c.key === "demo_records" ? "text-yellow-200" : "text-foreground"}`}>{overview.counts[c.key] ?? "חסר"}</p>
          </Link>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="פרסומים קרובים" className="lg:col-span-2">
          {overview.upcoming.length === 0 ? (
            <EmptyState title="אין פריטים מאושרים או מתוזמנים. אשר פריט בעמוד 'אישורים' או תזמן אותו מעמוד הפריט." action={<Link href="/social/approvals" className="text-sm text-primary underline">לאישורים</Link>} />
          ) : (
            <ul className="divide-y divide-border/60">
              {overview.upcoming.map((u) => (
                <li key={u.id} className="flex flex-wrap items-center gap-2 py-2">
                  <Link href={`/social/content/${u.id}`} className="font-medium hover:text-primary">{u.title}</Link>
                  <DemoBadge show={u.is_demo === 1} />
                  <Badge className="border-border bg-muted">{FORMAT_LABELS[u.format] ?? u.format}</Badge>
                  <StatusBadge status={u.status} labels={ITEM_STATUS_LABELS} />
                  <span className="ms-auto text-xs text-muted-foreground">{fmtLocal(u.scheduled_for_local)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-4">
          <Card title="בקרת חירום">
            <p className="mb-3 text-sm text-muted-foreground">
              {paused ? "השהיית החירום פעילה — שום פרסום לא ייצא." : "השהיית חירום עוצרת מיד כל פרסום מתוזמן או אוטומטי."}
            </p>
            <Button
              variant={paused ? "success" : "danger"} loading={busy === "pause"}
              onClick={() => act("pause", () => api.emergencyPause(!paused), paused ? "ההשהיה בוטלה" : "השהיית חירום הופעלה")}
            >
              {paused ? <><Play size={14} /> בטל השהיית חירום</> : <><Pause size={14} /> הפעל השהיית חירום</>}
            </Button>
          </Card>

          <Card title="חשבון ו-worker">
            <dl className="grid grid-cols-2 gap-3">
              <KV label="חשבון">{overview.account?.username ? `@${overview.account.username}` : "אין חשבון מחובר"}</KV>
              <KV label="טוקן"><span className={overview.token.ok ? "text-emerald-200" : "text-red-200"}>{overview.token.label}</span></KV>
              <KV label="worker">{overview.worker.online ? "פעיל" : "לא פעיל"}{overview.worker.inprocess ? " (בתהליך ה-API)" : ""}</KV>
              <KV label="פעימה אחרונה">{fmtUtc(overview.worker.heartbeat_at)}</KV>
              <KV label="התראות">{overview.modes.notify}</KV>
            </dl>
          </Card>

          <Card title="נתוני הדגמה">
            <p className="mb-3 text-xs text-muted-foreground">
              רשומות DEMO מסומנות בצהוב ואינן נתונים אמיתיים. {overview.publishing.demo_mode ? "מצב demo פעיל — הן מוצגות בכל העמודים." : "מצב demo כבוי — הן מוסתרות (ניתן לשנות בהגדרות מותג)."}
            </p>
            <div className="flex flex-wrap gap-2">
              <ConfirmButton
                label="זרע נתוני demo" variant="secondary" size="sm" confirmTitle="זריעת נתוני הדגמה"
                confirmText="ייווצרו מקורות, רעיונות, פריטים, לידים ומדדים לדוגמה, כולם מסומנים DEMO. להמשיך?"
                onConfirm={() => act("seed", () => api.demoSeed(), "נתוני ההדגמה נזרעו")}
              />
              <ConfirmButton
                label="נקה נתוני demo" variant="danger" size="sm" confirmTitle="מחיקת נתוני הדגמה"
                confirmText="כל הרשומות המסומנות DEMO יימחקו לצמיתות. נתונים אמיתיים לא ייפגעו. להמשיך?"
                onConfirm={() => act("clear", () => api.demoClear(), "נתוני ההדגמה נמחקו")}
              />
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
