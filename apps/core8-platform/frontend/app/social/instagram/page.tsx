"use client";

import { useState } from "react";
import Link from "next/link";
import { ExternalLink, Link2, Plus } from "lucide-react";
import { useLoad } from "@/components/social/hooks";
import { useToast } from "@/components/social/toast";
import { Badge, Banner, Button, Card, ConfirmButton, DemoBadge, EmptyState, ErrorBox, Field, Input, KV, Loading, Modal, PageHeader, Select, StatusBadge, Table, Tabs, Td, Textarea, Th } from "@/components/social/ui";
import { FORMAT_LABELS, PUB_STATE_LABELS, api, fmtLocal, fmtUtc, isDemo, type Inbound, type Publication } from "@/lib/social-api";

const SCOPE_HELP: Record<string, string> = {
  instagram_basic: "קריאת פרופיל ומדיה בסיסית",
  instagram_content_publish: "פרסום תוכן (תמונות, קרוסלות, רילס, סטורי)",
  instagram_manage_insights: "קריאת מדדים (insights)",
  pages_show_list: "רשימת דפי פייסבוק המקושרים",
  pages_read_engagement: "קריאת מעורבות בדף",
  business_management: "ניהול נכסי Business Manager",
};
const REPLY_LABELS: Record<string, string> = { draft_only: "טיוטה בלבד", approved_not_sent: "אושר — לא נשלח", sent: "נשלח", dismissed: "נדחה" };

export default function InstagramPage() {
  const [tab, setTab] = useState<"status" | "history" | "publications" | "inbound">("status");
  return (
    <>
      <PageHeader title="אינסטגרם וחיבורים" subtitle="מצב החיבור, היסטוריית פרסומים, תור הפרסומים והודעות נכנסות (טיוטות בלבד)." />
      <div className="mb-4"><Tabs value={tab} onChange={setTab} options={[{ value: "status", label: "חיבור" }, { value: "history", label: "היסטוריה" }, { value: "publications", label: "פרסומים" }, { value: "inbound", label: "הודעות נכנסות" }]} /></div>
      {tab === "status" && <StatusTab />}
      {tab === "history" && <HistoryTab />}
      {tab === "publications" && <PublicationsTab />}
      {tab === "inbound" && <InboundTab />}
    </>
  );
}

function StatusTab() {
  const toast = useToast();
  const { data, loading, error, reload } = useLoad(() => api.instagram.status());
  const [connecting, setConnecting] = useState(false);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox message={error ?? "חסר"} onRetry={() => reload()} />;
  const live = data.provider_mode === "live";
  const connect = async () => {
    setConnecting(true);
    try { const r = await api.instagram.connectUrl(); window.open(r.connect_url, "_blank", "noopener"); toast.success("נפתח חלון התחברות של Meta"); }
    catch (e) { toast.error(e); } finally { setConnecting(false); }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="מצב הספק" className={live ? "border-emerald-400/30" : "border-yellow-400/30"}>
        <div className="mb-3 flex flex-wrap gap-2">
          <Badge className={live ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-200" : "border-yellow-400/50 bg-yellow-400/15 text-yellow-200"}>{live ? "LIVE — חשבון אמיתי" : `MOCK — סימולציה (${data.provider_mode})`}</Badge>
          {data.demo_mode && <Badge className="border-yellow-400/50 bg-yellow-400/15 text-yellow-200">מצב DEMO — פרסום אמיתי חסום</Badge>}
        </div>
        {!live && <div className="mb-3"><Banner kind="warning">הספק בסימולציה: אין חיבור לאינסטגרם, לא נשלח דבר ל-Meta, ואין נתונים אמיתיים. להפעלה: Meta App + SOCIAL_INSTAGRAM_MODE=live.</Banner></div>}
        <dl className="grid grid-cols-2 gap-3">
          <KV label="חשבון">{data.account?.username ? `@${data.account.username}` : "אין חשבון מחובר"}</KV>
          <KV label="ig_user_id"><span dir="ltr">{data.account?.ig_user_id ?? "חסר"}</span></KV>
          <KV label="סוג חשבון">{data.account?.account_type ?? "חסר"}</KV>
          <KV label="טוקן"><span className={data.token.ok ? "text-emerald-200" : "text-red-200"}>{data.token.label}</span>{data.token.expires_at && <span className="block text-xs text-muted-foreground">פג: {fmtUtc(data.token.expires_at)}</span>}</KV>
          <KV label="נתיב התחברות">{data.login_path}</KV>
          <KV label="מצב הרשאות">{data.permissions_status}</KV>
          <KV label="פורסמו ב-24 שעות">{data.published_24h ?? "חסר"}</KV>
          <KV label="מגבלת פרסום (Meta)">{data.publishing_limit ? <span dir="ltr" className="font-mono text-xs">{JSON.stringify(data.publishing_limit)}</span> : data.publishing_limit_error ? `שגיאה: ${data.publishing_limit_error}` : "חסר (זמין רק ב-live)"}</KV>
          <KV label="כתובת מדיה ציבורית"><span dir="ltr" className="text-xs">{data.media_base_url || "חסר"}</span></KV>
          <KV label="תוקף קישור מדיה">{data.media_url_ttl_seconds} שניות</KV>
        </dl>
        <div className="mt-4">
          <Button variant="primary" loading={connecting} disabled={!data.app_configured} onClick={connect}><Link2 size={14} /> התחבר לאינסטגרם</Button>
          {!data.app_configured && <p className="mt-2 text-xs text-muted-foreground">הכפתור מושבת: META_APP_ID לא מוגדר בשרת. הגדר Meta App (ראה docs/social-manager/META_SETUP) כדי לאפשר התחברות.</p>}
        </div>
      </Card>
      <div className="space-y-4">
        <Card title="הרשאות (scopes) מבוקשות">
          <ul className="space-y-1 text-sm">
            {data.scopes.map((s) => <li key={s} className="flex flex-wrap gap-2"><code className="rounded bg-muted px-1 text-xs" dir="ltr">{s}</code><span className="text-muted-foreground">{SCOPE_HELP[s] ?? ""}</span></li>)}
          </ul>
          <p className="mt-2 text-xs text-muted-foreground">הרשאות תגובות/הודעות (instagram_manage_comments / messages) אינן מבוקשות — אין תשובות יוצאות.</p>
        </Card>
        <Card title="פורמטים נתמכים">
          <Table>
            <thead><tr><Th>פורמט</Th><Th>API</Th><Th>הערות</Th></tr></thead>
            <tbody>{data.supported_formats.map((f) => (
              <tr key={f.format}><Td>{f.label}</Td><Td>{f.api === true ? "כן" : f.api === "business_only" ? "חשבון עסקי בלבד" : "לא"}</Td><Td className="text-xs text-muted-foreground">{f.notes}</Td></tr>
            ))}</tbody>
          </Table>
        </Card>
      </div>
    </div>
  );
}

function HistoryTab() {
  const { data, loading, error, reload } = useLoad(() => api.instagram.history());
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={() => reload()} />;
  const items = data?.items ?? [];
  if (items.length === 0) return <EmptyState title="אין היסטוריית פרסומים (פורסם / נכשל / דורש בדיקה). פרסומים יופיעו כאן אחרי שה-worker יריץ פרסום מתוזמן." />;
  return (
    <Table>
      <thead><tr><Th>פריט</Th><Th>מצב</Th><Th>פורסם</Th><Th>מזהי ספק</Th><Th>שגיאה</Th></tr></thead>
      <tbody>{items.map((h) => (
        <tr key={h.id}>
          <Td>{h.title} <span className="text-xs text-muted-foreground">({FORMAT_LABELS[h.format]})</span></Td>
          <Td><div className="flex gap-1"><StatusBadge status={h.state} labels={PUB_STATE_LABELS} /><DemoBadge show={h.mode === "mock"} /></div></Td>
          <Td className="text-xs whitespace-nowrap">{fmtLocal(h.published_at_local)}</Td>
          <Td className="text-xs" dir="ltr">
            {h.provider_media_id ? <div>media: {h.provider_media_id}</div> : null}
            {h.container_id ? <div className="text-muted-foreground">container: {h.container_id}</div> : null}
            {h.permalink ? <a href={h.permalink} target="_blank" rel="noopener noreferrer" className="text-primary">permalink <ExternalLink size={10} className="inline" /></a> : null}
            {!h.provider_media_id && !h.container_id && !h.permalink && "חסר"}
          </Td>
          <Td className="text-xs text-red-300">{h.last_error ?? ""}</Td>
        </tr>
      ))}</tbody>
    </Table>
  );
}

function PublicationsTab() {
  const toast = useToast();
  const { data, loading, error, reload } = useLoad(() => api.publications.list());
  const [resolve, setResolve] = useState<Publication | null>(null);
  const [res, setRes] = useState<{ outcome: "published" | "failed"; provider_media_id: string; note: string }>({ outcome: "published", provider_media_id: "", note: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const act = async (key: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(key);
    try { await fn(); toast.success(ok); await reload(true); } catch (e) { toast.error(e); } finally { setBusy(null); }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={() => reload()} />;
  const items = data?.items ?? [];
  return (
    <>
      <p className="mb-2 text-xs text-muted-foreground">ספק: {data?.provider_mode}. פרסום במצב לא ודאי (publish_requested / needs_manual_review) ניתן ל&quot;התאמה&quot; מול הספק או לפתרון ידני — לעולם לא לניסיון חוזר עיוור.</p>
      {items.length === 0 ? <EmptyState title="אין פרסומים בתור. תזמן פריט מאושר כדי ליצור פרסום." action={<Link href="/social/approvals" className="text-sm text-primary underline">לאישורים</Link>} /> : (
        <Table>
          <thead><tr><Th>פריט</Th><Th>מצב</Th><Th>מתוזמן</Th><Th>ניסיונות</Th><Th>שגיאה אחרונה</Th><Th>פעולות</Th></tr></thead>
          <tbody>{items.map((p) => {
            const uncertain = p.state === "needs_manual_review" || p.state === "publish_requested";
            return (
              <tr key={p.id}>
                <Td><Link href={`/social/content/${p.content_item_id}`} className="hover:text-primary">{p.title ?? p.content_item_id}</Link> <DemoBadge show={isDemo({ is_demo: p.is_demo, mode: p.mode })} /></Td>
                <Td><div className="flex flex-col gap-1"><StatusBadge status={p.state} labels={PUB_STATE_LABELS} /><span className="text-[10px] text-muted-foreground">{p.mode}</span></div></Td>
                <Td className="text-xs whitespace-nowrap">{fmtLocal(p.scheduled_for_local)}{p.published_at_local && <div className="text-emerald-200">פורסם {fmtLocal(p.published_at_local)}</div>}</Td>
                <Td>{p.attempts}</Td>
                <Td className="max-w-xs text-xs text-red-300">{p.last_error ?? ""}{p.error_class && <span className="block text-muted-foreground">{p.error_class}</span>}</Td>
                <Td>
                  <div className="flex flex-wrap gap-1">
                    {(p.state === "queued" || p.state === "claimed") && <ConfirmButton label="בטל" size="sm" confirmTitle="ביטול פרסום" confirmText="הפרסום יוסר מהתור. להמשיך?" onConfirm={() => act(`c${p.id}`, () => api.publications.cancel(p.id), "הפרסום בוטל")} />}
                    {uncertain && <Button size="sm" loading={busy === `r${p.id}`} onClick={() => act(`r${p.id}`, () => api.publications.reconcile(p.id), "בוצעה התאמה מול הספק")}>התאמה</Button>}
                    {uncertain && <Button size="sm" variant="ghost" onClick={() => { setResolve(p); setRes({ outcome: "published", provider_media_id: "", note: "" }); }}>פתור ידנית</Button>}
                    {p.permalink && <a href={p.permalink} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-primary">פוסט <ExternalLink size={10} /></a>}
                  </div>
                </Td>
              </tr>
            );
          })}</tbody>
        </Table>
      )}
      <Modal open={!!resolve} onClose={() => setResolve(null)} title="פתרון ידני של פרסום" footer={<><Button variant="ghost" onClick={() => setResolve(null)}>ביטול</Button><Button variant="primary" loading={busy === "resolve"} onClick={() => resolve && act("resolve", () => api.publications.resolve(resolve.id, { outcome: res.outcome, provider_media_id: res.provider_media_id || undefined, note: res.note || undefined }), "הפרסום נפתר").then(() => setResolve(null))}>שמור</Button></>}>
        <p className="text-xs text-muted-foreground">השתמש רק אחרי שבדקת באפליקציית אינסטגרם מה קרה בפועל.</p>
        <Field label="תוצאה">{(id) => <Select id={id} value={res.outcome} onChange={(e) => setRes({ ...res, outcome: e.target.value as "published" | "failed" })}><option value="published">פורסם בפועל</option><option value="failed">נכשל</option></Select>}</Field>
        <Field label="מזהה מדיה בספק (אם פורסם)">{(id) => <Input id={id} dir="ltr" value={res.provider_media_id} onChange={(e) => setRes({ ...res, provider_media_id: e.target.value })} />}</Field>
        <Field label="הערה">{(id) => <Textarea id={id} value={res.note} onChange={(e) => setRes({ ...res, note: e.target.value })} />}</Field>
      </Modal>
    </>
  );
}

function InboundTab() {
  const toast = useToast();
  const { data, loading, error, reload, setData } = useLoad(() => api.inbound.list());
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState<{ kind: "comment" | "dm"; author: string; text: string; provider_id: string }>({ kind: "comment", author: "", text: "", provider_id: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const update = (row: Inbound) => setData((d) => d ? { ...d, items: d.items.map((x) => (x.id === row.id ? row : x)) } : d);
  const draft = async (m: Inbound) => {
    setBusy(m.id);
    try { const r = await api.inbound.draftReply(m.id); toast.success(`${r.note} (LLM: ${r.llm_mode})`); await reload(true); } catch (e) { toast.error(e); } finally { setBusy(null); }
  };
  const setStatus = async (m: Inbound, reply_status: "draft_only" | "approved_not_sent" | "dismissed") => {
    try { update(await api.inbound.patch(m.id, { reply_status })); } catch (e) { toast.error(e); }
  };
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy("add");
    try { await api.inbound.add({ kind: form.kind, text: form.text, author: form.author || undefined, provider_id: form.provider_id || undefined }); toast.success("ההודעה יובאה"); setAddOpen(false); setForm({ kind: "comment", author: "", text: "", provider_id: "" }); await reload(true); }
    catch (err) { toast.error(err); } finally { setBusy(null); }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={() => reload()} />;
  const items = data?.items ?? [];
  return (
    <>
      <div className="mb-3"><Banner kind="danger">תשובות יוצאות מושבתות — המערכת רק מנסחת טיוטות. {data?.permissions}</Banner></div>
      <div className="mb-3 flex justify-end"><Button variant="ghost" onClick={() => setAddOpen(true)}><Plus size={14} /> ייבוא ידני של הודעה</Button></div>
      {items.length === 0 ? <EmptyState title="אין הודעות נכנסות. ייבא תגובה/הודעה ידנית כדי לקבל טיוטת תשובה (לא נשלחת)." /> : (
        <ul className="space-y-2">
          {items.map((m) => (
            <li key={m.id} className="rounded-xl border border-border bg-card p-3 text-sm">
              <div className="mb-1 flex flex-wrap items-center gap-1.5 text-xs">
                <DemoBadge show={isDemo(m)} />
                <Badge className="border-border bg-muted">{m.kind === "dm" ? "הודעה פרטית" : "תגובה"}</Badge>
                <span className="text-muted-foreground">{m.author ?? "אנונימי"} · {fmtUtc(m.received_at)}</span>
                {m.flagged === 1 && <Badge className="border-orange-400/40 bg-orange-500/15 text-orange-200" title={m.flag_reasons ?? ""}>סומן: {m.flag_reasons ?? "חשד להזרקה"}</Badge>}
                <Badge className="border-border text-muted-foreground">{REPLY_LABELS[m.reply_status] ?? m.reply_status}</Badge>
              </div>
              <p className="whitespace-pre-wrap rounded-lg border border-border/40 bg-background/40 p-2" dir="auto">{m.text}</p>
              {m.draft_reply && <p className="mt-2 rounded-lg border border-primary/20 bg-primary/5 p-2 text-xs"><span className="font-medium text-primary">טיוטת תשובה (לא נשלחה): </span>{m.draft_reply}</p>}
              <div className="mt-2 flex flex-wrap gap-1">
                <Button size="sm" loading={busy === m.id} onClick={() => draft(m)}>נסח טיוטה</Button>
                <Button size="sm" variant="success" disabled={!m.draft_reply || m.reply_status === "approved_not_sent"} onClick={() => setStatus(m, "approved_not_sent")}>אשר טיוטה (לא נשלח)</Button>
                <Button size="sm" variant="ghost" disabled={m.reply_status === "dismissed"} onClick={() => setStatus(m, "dismissed")}>דחה</Button>
                {m.reply_status !== "draft_only" && <Button size="sm" variant="ghost" onClick={() => setStatus(m, "draft_only")}>החזר לטיוטה</Button>}
              </div>
            </li>
          ))}
        </ul>
      )}
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="ייבוא ידני של הודעה נכנסת">
        <form onSubmit={add} className="grid gap-3">
          <Field label="סוג">{(id) => <Select id={id} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as "comment" | "dm" })}><option value="comment">תגובה</option><option value="dm">הודעה פרטית</option></Select>}</Field>
          <Field label="מחבר">{(id) => <Input id={id} value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} />}</Field>
          <Field label="מזהה בספק">{(id) => <Input id={id} dir="ltr" value={form.provider_id} onChange={(e) => setForm({ ...form, provider_id: e.target.value })} />}</Field>
          <Field label="טקסט" required hint="הטקסט מטופל כנתון לא מהימן ונסרק לדפוסי הזרקה">{(id) => <Textarea id={id} required value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />}</Field>
          <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setAddOpen(false)}>ביטול</Button><Button type="submit" variant="primary" loading={busy === "add"}>ייבא</Button></div>
        </form>
      </Modal>
    </>
  );
}
