"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, Check, ExternalLink, Save, ShieldAlert, X } from "lucide-react";
import AssetThumb from "@/components/social/AssetThumb";
import PackageEditor from "@/components/social/PackageEditor";
import { useLoad } from "@/components/social/hooks";
import { useSocialStatus } from "@/components/social/SocialShell";
import { useToast } from "@/components/social/toast";
import { Badge, Banner, Button, Card, ConfirmButton, DemoBadge, EmptyState, ErrorBox, Field, Input, KV, Loading, PageHeader, Select, StatusBadge, Textarea } from "@/components/social/ui";
import {
  AUDIENCE_LABELS, FORMAT_LABELS, ITEM_STATUS_LABELS, PRODUCTION_LABELS, PUB_STATE_LABELS, api, fmtLocal, fmtUtc, isDemo, toInputDateTime,
  type Asset, type ContentItem, type GateReport, type Package,
} from "@/lib/social-api";

const APPROVAL_REASONS: Record<string, string> = {
  ok: "אישור פעיל תואם לגרסה הנוכחית",
  no_active_approval: "אין אישור פעיל",
};
function approvalReason(r: string): string {
  if (APPROVAL_REASONS[r]) return APPROVAL_REASONS[r];
  if (r.startsWith("changed:")) {
    const map: Record<string, string> = { caption_hash: "כיתוב", assets_hash: "נכסים", scheduled_for: "תזמון", account_id: "חשבון", format: "פורמט", settings_hash: "הגדרות" };
    return "האישור בוטל — השתנו: " + r.slice(8).split(",").map((k) => map[k] ?? k).join(", ");
  }
  return r;
}

export default function ItemPage() {
  const { id } = useParams<{ id: string }>();
  const { data: item, loading, error, reload } = useLoad(() => api.items.get(id), [id]);
  if (loading) return <Loading label="טוען פריט…" />;
  if (error || !item) return <ErrorBox message={error ?? "הפריט לא נמצא"} onRetry={() => reload()} />;
  // Remount the editor whenever the server version changes so draft state starts fresh.
  return <ItemEditor key={`${item.version}:${item.updated_at}`} item={item} reload={reload} />;
}

function ItemEditor({ item, reload }: { item: ContentItem; reload: (silent?: boolean) => Promise<void> }) {
  const router = useRouter();
  const toast = useToast();
  const { overview, refresh } = useSocialStatus();
  const id = item.id;

  const gatesQ = useLoad(() => api.items.gates(id), [id]);
  const assetsQ = useLoad(() => api.assets.list());
  const templatesQ = useLoad(() => api.carousel.templates());

  // Editable draft state (initialised from the server item; component is keyed on version)
  const [title, setTitle] = useState(item.title);
  const [caption, setCaption] = useState(item.caption);
  const [pkg, setPkg] = useState<Package>(item.package);
  const [assetIds, setAssetIds] = useState<string[]>(item.asset_ids);
  const [cover, setCover] = useState<string | null>(item.cover_asset_id);
  const [schedule, setSchedule] = useState(toInputDateTime(item.scheduled_for_local));
  const [reviewNotes, setReviewNotes] = useState(item.review_notes ?? "");
  const [busy, setBusy] = useState<string | null>(null);

  const dirty = useMemo(() => {
    return title !== item.title || caption !== item.caption || JSON.stringify(pkg) !== JSON.stringify(item.package)
      || JSON.stringify(assetIds) !== JSON.stringify(item.asset_ids) || cover !== item.cover_asset_id
      || schedule !== toInputDateTime(item.scheduled_for_local) || reviewNotes !== (item.review_notes ?? "");
  }, [item, title, caption, pkg, assetIds, cover, schedule, reviewNotes]);

  // PATCH/status responses lack approval/publications/assets — always re-read the full item.
  const afterChange = async () => {
    await reload(true);
    await gatesQ.reload(true);
    refresh();
  };

  const act = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    try { await fn(); } catch (e) { toast.error(e); } finally { setBusy(null); }
  };

  const save = () => act("save", async () => {
    const body: Parameters<typeof api.items.patch>[1] = {};
    if (title !== item.title) body.title = title;
    if (caption !== item.caption) body.caption = caption;
    if (JSON.stringify(pkg) !== JSON.stringify(item.package)) body.package = pkg;
    if (JSON.stringify(assetIds) !== JSON.stringify(item.asset_ids)) body.asset_ids = assetIds;
    if (cover !== item.cover_asset_id) body.cover_asset_id = cover;
    if (schedule !== toInputDateTime(item.scheduled_for_local)) body.scheduled_for = schedule || null;
    if (reviewNotes !== (item.review_notes ?? "")) body.review_notes = reviewNotes;
    if (typeof pkg.production_status === "string" && pkg.production_status !== item.production_status) body.production_status = pkg.production_status;
    await api.items.patch(item.id, body);
    toast.success("נשמר" + (item.approval?.valid && ("caption" in body || "asset_ids" in body || "scheduled_for" in body || "cover_asset_id" in body) ? " — האישור הקודם בוטל, נדרש אישור מחדש" : ""));
    await afterChange();
  });

  const pillarLabel = overview?.pillars.find((p) => p.key === item.pillar)?.label ?? item.pillar ?? "ללא";
  const assets = assetsQ.data?.items ?? [];
  const selectedAssets = assetIds.map((aid) => assets.find((a) => a.id === aid)).filter((a): a is Asset => !!a);
  const locked = item.status === "publishing" || item.status === "published";
  const findings = item.fact_check?.findings ?? [];

  return (
    <>
      <PageHeader
        title={item.title}
        subtitle={<span className="flex flex-wrap items-center gap-1.5">
          <DemoBadge show={isDemo(item)} />
          <StatusBadge status={item.status} labels={ITEM_STATUS_LABELS} />
          <Badge className="border-border bg-muted">{FORMAT_LABELS[item.format]}</Badge>
          <Badge className="border-primary/30 bg-primary/10 text-primary">{pillarLabel}</Badge>
          {item.audience && <Badge className="border-border bg-muted">{AUDIENCE_LABELS[item.audience] ?? item.audience}</Badge>}
          <Badge className="border-border bg-muted text-muted-foreground">{PRODUCTION_LABELS[item.production_status] ?? item.production_status}</Badge>
          <span className="text-xs">גרסה {item.version} · עודכן {fmtUtc(item.updated_at)}</span>
        </span>}
        actions={<>
          <Link href="/social/content" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowRight size={14} /> לרשימה</Link>
          <Button variant="primary" loading={busy === "save"} disabled={!dirty || locked} onClick={save}><Save size={14} /> שמור שינויים</Button>
        </>}
      />

      {locked && <div className="mb-4"><Banner kind="info">הפריט פורסם או בתהליך פרסום — לא ניתן לערוך או לשנות סטטוס.</Banner></div>}
      {!locked && item.approval?.valid && <div className="mb-4"><Banner kind="warning">לפריט יש אישור פעיל. עריכת כיתוב, נכסים, תזמון או חשבון תבטל את האישור ותחזיר את הפריט לסקירה.</Banner></div>}
      {dirty && <div className="mb-4"><Banner kind="info">יש שינויים שלא נשמרו.</Banner></div>}

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Card title="כותרת וכיתוב">
            <div className="grid gap-3">
              <Field label="כותרת">{(fid) => <Input id={fid} value={title} disabled={locked} onChange={(e) => setTitle(e.target.value)} />}</Field>
              <Field label="כיתוב" hint={`${caption.length}/2200 תווים · ${(caption.match(/#\S+/g) ?? []).length}/30 האשטגים`}>
                {(fid) => <Textarea id={fid} className="min-h-[140px]" value={caption} disabled={locked} onChange={(e) => setCaption(e.target.value)} />}
              </Field>
              <Field label="הערות סקירה">{(fid) => <Textarea id={fid} value={reviewNotes} disabled={locked} onChange={(e) => setReviewNotes(e.target.value)} />}</Field>
            </div>
          </Card>

          <Card title={`חבילת הפקה — ${FORMAT_LABELS[item.format]}`} actions={item.format === "carousel" && (
            <Button
              variant="secondary" size="sm" loading={busy === "render"} disabled={locked || dirty}
              title={dirty ? "שמור שינויים לפני רינדור" : undefined}
              onClick={() => act("render", async () => {
                const r = await api.items.renderCarousel(item.id, typeof pkg.template === "string" ? pkg.template : null);
                toast.success(`נרנדרו ${r.assets.length} שקופיות${r.raqm ? "" : " (ללא raqm — עיצוב RTL עלול להיות חלקי)"}`);
                await afterChange();
                await assetsQ.reload(true);
              })}
            >רנדר קרוסלה</Button>
          )}>
            <PackageEditor format={item.format} pkg={pkg} onChange={setPkg} templates={templatesQ.data} isDemo={isDemo(item)} />
          </Card>

          <Card title="נכסים משויכים" actions={<Link href="/social/assets" className="text-xs text-primary underline">העלאת נכסים</Link>}>
            {assetsQ.loading ? <Loading /> : assets.length === 0 ? (
              <EmptyState title="אין נכסים בספרייה. העלה תמונות/וידאו בעמוד 'נכסים וקבצים' או רנדר קרוסלה." />
            ) : (
              <>
                {selectedAssets.length > 0 && (
                  <div className="mb-3">
                    <p className="mb-1 text-xs text-muted-foreground">נבחרו (לפי סדר):</p>
                    <div className="flex flex-wrap gap-2">
                      {selectedAssets.map((a, i) => (
                        <div key={a.id} className="flex flex-col items-center gap-1">
                          <AssetThumb asset={a} size="md" />
                          <span className="text-[10px] text-muted-foreground">{i + 1}{a.id === cover ? " · כריכה" : ""}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="grid max-h-72 grid-cols-2 gap-2 overflow-y-auto rounded-xl border border-border p-2 sm:grid-cols-3 md:grid-cols-4">
                  {assets.map((a) => {
                    const checked = assetIds.includes(a.id);
                    return (
                      <label key={a.id} className={`flex cursor-pointer flex-col gap-1 rounded-lg border p-2 text-xs ${checked ? "border-primary/50 bg-primary/10" : "border-border"}`}>
                        <div className="flex items-start gap-2">
                          <input type="checkbox" className="mt-1 accent-cyan-400" checked={checked} disabled={locked}
                            onChange={(e) => {
                              const next = e.target.checked ? [...assetIds, a.id] : assetIds.filter((x) => x !== a.id);
                              setAssetIds(next);
                              if (!e.target.checked && cover === a.id) setCover(null);
                            }} aria-label={`בחר נכס ${a.original_name ?? a.id}`} />
                          <AssetThumb asset={a} size="sm" />
                        </div>
                        <span className="truncate" title={a.original_name ?? a.filename}>{a.original_name ?? a.filename}</span>
                        <span className="flex gap-1"><DemoBadge show={isDemo(a)} />{a.spec_check && !a.spec_check.ok && <Badge className="border-red-400/40 bg-red-500/15 text-red-200">לא עומד במפרט</Badge>}</span>
                      </label>
                    );
                  })}
                </div>
                {(item.format === "reel" || item.format === "story") && (
                  <Field label="נכס כריכה" className="mt-3">
                    {(fid) => (
                      <Select id={fid} value={cover ?? ""} disabled={locked} onChange={(e) => setCover(e.target.value || null)}>
                        <option value="">ללא</option>
                        {assets.filter((a) => a.media_type === "image").map((a) => <option key={a.id} value={a.id}>{a.original_name ?? a.filename}</option>)}
                      </Select>
                    )}
                  </Field>
                )}
              </>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="פעולות">
            <div className="grid gap-3">
              <Field label="תזמון (שעון ישראל)" hint="תזמון שומר, מאשר ומכניס לתור בפעולה אחת.">
                {(fid) => <Input id={fid} type="datetime-local" dir="ltr" value={schedule} disabled={locked} onChange={(e) => setSchedule(e.target.value)} />}
              </Field>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" disabled={locked} loading={busy === "review"} onClick={() => act("review", async () => { toast.success("נשלח לסקירה"); await api.items.status(item.id, "needs_review"); await afterChange(); })}>שלח לסקירה</Button>
                <Button size="sm" variant="success" disabled={locked || dirty} title={dirty ? "שמור שינויים לפני אישור" : undefined} loading={busy === "approve"}
                  onClick={() => act("approve", async () => { await api.items.approve(item.id); toast.success("הפריט אושר"); await afterChange(); })}><Check size={13} /> אשר</Button>
                <Button size="sm" variant="primary" disabled={locked || dirty || !schedule} title={!schedule ? "בחר מועד" : dirty ? "שמור שינויים לפני תזמון" : undefined} loading={busy === "schedule"}
                  onClick={() => act("schedule", async () => { const pub = await api.items.schedule(item.id, schedule); toast.success(`תוזמן ל-${fmtLocal(pub.scheduled_for_local)} (${pub.mode})`); await afterChange(); })}>תזמן</Button>
                <Button size="sm" variant="danger" disabled={locked} loading={busy === "reject"} onClick={() => act("reject", async () => { await api.items.status(item.id, "rejected"); await afterChange(); toast.success("הפריט נדחה"); })}><X size={13} /> דחה</Button>
                <Button size="sm" variant="ghost" disabled={locked} loading={busy === "pause"} onClick={() => act("pause", async () => { await api.items.status(item.id, "paused"); await afterChange(); toast.success("הפריט הושהה ופרסומים בתור בוטלו"); })}>השהה</Button>
                <Button size="sm" variant="ghost" disabled={locked} loading={busy === "draft"} onClick={() => act("draft", async () => { await api.items.status(item.id, "draft"); await afterChange(); })}>החזר לטיוטה</Button>
                <ConfirmButton label="מחק" size="sm" disabled={locked} confirmTitle="מחיקת פריט" confirmText="הפריט יימחק ופרסומים בתור יבוטלו. להמשיך?"
                  onConfirm={async () => { try { await api.items.delete(item.id); toast.success("הפריט נמחק"); router.push("/social/content"); } catch (e) { toast.error(e); } }} />
              </div>
            </div>
          </Card>

          <Card title="סטטוס אישור">
            {item.approval ? (
              <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${item.approval.valid ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100" : "border-yellow-400/40 bg-yellow-400/10 text-yellow-100"}`}>
                {item.approval.valid ? <Check size={16} /> : <ShieldAlert size={16} />}
                <div>
                  <p>{approvalReason(item.approval.reason)}</p>
                  {item.approval.approval && <p className="mt-1 text-xs opacity-80">אושר ע&quot;י {String(item.approval.approval.approved_by ?? "")} · {fmtUtc(String(item.approval.approval.approved_at ?? ""))}</p>}
                </div>
              </div>
            ) : <p className="text-sm text-muted-foreground">חסר</p>}
            <dl className="mt-3 grid grid-cols-2 gap-2">
              <KV label="חשבון יעד">{item.account_id ?? "לא נקבע (נקבע באישור)"}</KV>
              <KV label="מתוזמן ל">{item.scheduled_for ? fmtLocal(item.scheduled_for_local) : "חסר"}</KV>
            </dl>
          </Card>

          <Card title="שערי פרסום (gates)" actions={<Button size="sm" variant="ghost" onClick={() => gatesQ.reload()}>רענן</Button>}>
            {gatesQ.loading ? <Loading /> : gatesQ.error ? <ErrorBox message={gatesQ.error} /> : <Gates report={gatesQ.data} />}
          </Card>

          <Card title="בדיקת עובדות ודגלי רגישות">
            {item.sensitive_flags.length === 0 && findings.length === 0 ? (
              <p className="text-sm text-emerald-200">לא נמצאו דגלים. (בדיקה אוטומטית — אינה תחליף לסקירה אנושית)</p>
            ) : (
              <>
                <div className="mb-2 flex flex-wrap gap-1">{item.sensitive_flags.map((f) => <Badge key={f} className="border-orange-400/40 bg-orange-500/15 text-orange-200">{f}</Badge>)}</div>
                <ul className="space-y-2 text-xs">
                  {findings.map((f, i) => (
                    <li key={i} className="rounded-lg border border-border/60 bg-background/40 p-2">
                      <p className="font-medium text-orange-200">{f.label}</p>
                      <p className="mt-0.5 text-muted-foreground">…{f.excerpt}…</p>
                    </li>
                  ))}
                </ul>
                {item.fact_check && <p className="mt-2 text-[11px] text-muted-foreground">מתאים לפרסום אוטומטי: {item.fact_check.ok_for_auto ? "כן" : "לא — דורש סקירה אנושית"}</p>}
              </>
            )}
          </Card>

          <Card title="פרסומים">
            {(item.publications ?? []).length === 0 ? <p className="text-sm text-muted-foreground">אין פרסומים לפריט. תזמן אותו כדי ליצור פרסום.</p> : (
              <ul className="space-y-2 text-xs">
                {item.publications!.map((p) => (
                  <li key={p.id} className="rounded-lg border border-border/60 bg-background/40 p-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <StatusBadge status={p.state} labels={PUB_STATE_LABELS} />
                      <Badge className={p.mode === "live" ? "border-emerald-400/40 text-emerald-200" : "border-yellow-400/40 text-yellow-200"}>{p.mode}</Badge>
                      <span className="text-muted-foreground">{fmtLocal(p.scheduled_for_local)}</span>
                    </div>
                    {p.permalink && <a href={p.permalink} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-primary">קישור לפוסט <ExternalLink size={10} /></a>}
                    {p.provider_media_id && <p className="mt-1 text-muted-foreground" dir="ltr">media: {p.provider_media_id}</p>}
                    {p.last_error && <p className="mt-1 text-red-300">{p.last_error}</p>}
                    <p className="mt-1 text-muted-foreground">ניסיונות: {p.attempts}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}

function Gates({ report }: { report: GateReport | null }) {
  if (!report) return <p className="text-sm text-muted-foreground">חסר</p>;
  return (
    <>
      <p className={`mb-2 text-sm font-medium ${report.ok ? "text-emerald-200" : "text-red-200"}`}>{report.ok ? "כל השערים עוברים" : "יש שערים שלא עוברים"} · ספק: {report.provider_mode}</p>
      <ul className="space-y-1 text-xs">
        {report.checks.map((c) => (
          <li key={c.code} className="flex items-start gap-2">
            <span className={`mt-0.5 ${c.ok ? "text-emerald-300" : "text-red-300"}`} aria-label={c.ok ? "עובר" : "נכשל"}>{c.ok ? "✓" : "✗"}</span>
            <span>
              {c.label}
              {c.detail != null && c.detail !== "" && <span className="text-muted-foreground" dir="auto"> — {typeof c.detail === "string" ? c.detail : JSON.stringify(c.detail)}</span>}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}
