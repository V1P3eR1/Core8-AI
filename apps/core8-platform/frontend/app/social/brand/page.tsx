"use client";

import { useState } from "react";
import { Eye, Plus, Save, Trash2 } from "lucide-react";
import { useLoad } from "@/components/social/hooks";
import { useSocialStatus } from "@/components/social/SocialShell";
import { useToast } from "@/components/social/toast";
import { Banner, Button, Card, Checkbox, ErrorBox, Field, Input, Loading, PageHeader, Select, Tabs, Textarea } from "@/components/social/ui";
import { api, type BrandSettings, type CarouselTemplate, type CarouselTemplates, type PublishingSettings } from "@/lib/social-api";

export default function BrandPage() {
  const [tab, setTab] = useState<"brand" | "publishing" | "templates">("brand");
  return (
    <>
      <PageHeader title="הגדרות מותג" subtitle="ידע המותג שמזין את הסוכנים, מדיניות הפרסום, ותבניות הקרוסלה." />
      <div className="mb-4"><Tabs value={tab} onChange={setTab} options={[{ value: "brand", label: "מותג" }, { value: "publishing", label: "מדיניות פרסום" }, { value: "templates", label: "תבניות קרוסלה" }]} /></div>
      {tab === "brand" && <BrandTab />}
      {tab === "publishing" && <PublishingTab />}
      {tab === "templates" && <TemplatesTab />}
    </>
  );
}

// ── Brand ────────────────────────────────────────────────────────────────────

const TEXT_FIELDS: { key: keyof BrandSettings & string; label: string; multiline?: boolean }[] = [
  { key: "brand_name", label: "שם המותג" }, { key: "owner_name", label: "שם הבעלים" }, { key: "website", label: "אתר" },
  { key: "market", label: "שוק" }, { key: "language", label: "שפה" }, { key: "timezone", label: "אזור זמן" },
  { key: "description", label: "תיאור", multiline: true }, { key: "positioning", label: "מיצוב", multiline: true },
];
const LIST_FIELDS: { key: keyof BrandSettings & string; label: string }[] = [
  { key: "tone_of_voice", label: "טון דיבור" }, { key: "approved_claims", label: "טענות מאושרות" }, { key: "prohibited_claims", label: "טענות אסורות" },
  { key: "approved_links", label: "קישורים מאושרים" }, { key: "topics_to_cover", label: "נושאים לכסות" }, { key: "topics_to_avoid", label: "נושאים להימנע" },
  { key: "assumptions", label: "הנחות (מה לא ידוע)" },
];

function LinesBox({ id, value, onChange }: { id: string; value: string[]; onChange: (v: string[]) => void }) {
  const [text, setText] = useState(value.join("\n"));
  return <Textarea id={id} value={text} onChange={(e) => { setText(e.target.value); onChange(e.target.value.split("\n").map((l) => l.trim()).filter(Boolean)); }} />;
}

function BrandTab() {
  const toast = useToast();
  const { data, loading, error, reload } = useLoad(() => api.settings.get<BrandSettings>("brand"));
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox message={error ?? "חסר"} onRetry={() => reload()} />;
  return <BrandForm key={JSON.stringify(data)} initial={data} onSaved={() => { toast.success("הגדרות המותג נשמרו"); reload(true); }} />;
}

function BrandForm({ initial, onSaved }: { initial: BrandSettings; onSaved: () => void }) {
  const toast = useToast();
  const [b, setB] = useState<BrandSettings>(initial);
  const [saving, setSaving] = useState(false);
  const str = (k: string) => (typeof b[k] === "string" ? (b[k] as string) : "");
  const list = (k: string) => (Array.isArray(b[k]) ? (b[k] as unknown[]).map(String) : []);
  const services = Array.isArray(b.approved_services) ? b.approved_services : [];
  const audiences = Array.isArray(b.target_audiences) ? b.target_audiences : [];
  const contact = b.contact_details && typeof b.contact_details === "object" ? b.contact_details : {};
  const save = async () => {
    setSaving(true);
    try { await api.settings.put("brand", b); onSaved(); } catch (e) { toast.error(e); } finally { setSaving(false); }
  };
  return (
    <div className="space-y-4">
      <Card title="פרטי מותג" actions={<Button variant="primary" loading={saving} onClick={save}><Save size={14} /> שמור</Button>}>
        <div className="grid gap-3 md:grid-cols-2">
          {TEXT_FIELDS.map((f) => (
            <Field key={f.key} label={f.label} className={f.multiline ? "md:col-span-2" : ""}>
              {(id) => f.multiline ? <Textarea id={id} value={str(f.key)} onChange={(e) => setB({ ...b, [f.key]: e.target.value })} /> : <Input id={id} value={str(f.key)} onChange={(e) => setB({ ...b, [f.key]: e.target.value })} />}
            </Field>
          ))}
        </div>
      </Card>
      <Card title="שירותים מאושרים (שם + סטטוס זמינות)">
        <div className="space-y-2">
          {services.map((s, i) => (
            <div key={i} className="flex flex-wrap gap-2">
              <Input aria-label={`שם שירות ${i + 1}`} value={s.name} onChange={(e) => setB({ ...b, approved_services: services.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)) })} className="flex-1 min-w-[160px]" />
              <Input aria-label={`סטטוס שירות ${i + 1}`} value={s.status} onChange={(e) => setB({ ...b, approved_services: services.map((x, j) => (j === i ? { ...x, status: e.target.value } : x)) })} className="flex-[2] min-w-[200px]" />
              <Button size="sm" variant="danger" aria-label="הסר שירות" onClick={() => setB({ ...b, approved_services: services.filter((_, j) => j !== i) })}><Trash2 size={12} /></Button>
            </div>
          ))}
          <Button size="sm" variant="ghost" onClick={() => setB({ ...b, approved_services: [...services, { name: "", status: "לא אושר עדיין — דורש אישור" }] })}><Plus size={12} /> הוסף שירות</Button>
        </div>
      </Card>
      <Card title="קהלי יעד">
        <div className="space-y-2">
          {audiences.map((a, i) => (
            <div key={i} className="flex flex-wrap gap-2">
              <Input aria-label={`מפתח קהל ${i + 1}`} dir="ltr" value={a.key} onChange={(e) => setB({ ...b, target_audiences: audiences.map((x, j) => (j === i ? { ...x, key: e.target.value } : x)) })} className="w-36" />
              <Input aria-label={`תווית קהל ${i + 1}`} value={a.label} onChange={(e) => setB({ ...b, target_audiences: audiences.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)) })} className="flex-1 min-w-[200px]" />
              <Button size="sm" variant="danger" aria-label="הסר קהל" onClick={() => setB({ ...b, target_audiences: audiences.filter((_, j) => j !== i) })}><Trash2 size={12} /></Button>
            </div>
          ))}
          <Button size="sm" variant="ghost" onClick={() => setB({ ...b, target_audiences: [...audiences, { key: "", label: "" }] })}><Plus size={12} /> הוסף קהל</Button>
        </div>
      </Card>
      <Card title="רשימות (שורה לכל פריט)">
        <div className="grid gap-3 md:grid-cols-2">
          {LIST_FIELDS.map((f) => <Field key={f.key} label={f.label}>{(id) => <LinesBox id={id} value={list(f.key)} onChange={(v) => setB({ ...b, [f.key]: v })} />}</Field>)}
          <Field label="שירותים בפיתוח">{(id) => <LinesBox id={id} value={list("services_in_development")} onChange={(v) => setB({ ...b, services_in_development: v })} />}</Field>
          <Field label="פרטי קשר (הערה)">{(id) => <Textarea id={id} value={String(contact.note ?? "")} onChange={(e) => setB({ ...b, contact_details: { ...contact, note: e.target.value } })} />}</Field>
        </div>
      </Card>
      <div className="flex justify-end"><Button variant="primary" loading={saving} onClick={save}><Save size={14} /> שמור הגדרות מותג</Button></div>
    </div>
  );
}

// ── Publishing ───────────────────────────────────────────────────────────────

const MODE_HELP: Record<PublishingSettings["mode"], string> = {
  draft_only: "המערכת רק מייצרת טיוטות. לא ניתן לתזמן או לפרסם.",
  approval_required: "כל פריט חייב אישור אנושי לפני תזמון. האישור נקשר לגרסה המדויקת.",
  automatic: "פריטים מאושרים בקטגוריות מותרות ובחלון זמן מותר מתפרסמים ללא אישור נוסף. דורש אישור מפורש.",
};
const REVIEW_TOPICS: Record<string, string> = { customers: "לקוחות/תוצאות", prices: "מחירים", personal: "מידע אישי", legal_medical_financial: "משפטי/רפואי/פיננסי", availability: "זמינות", likeness: "דמות/פנים/קול", controversial: "שנוי במחלוקת", numbers: "מספרים/אחוזים", unsourced_claim: "טענה ללא מקור" };

function PublishingTab() {
  const toast = useToast();
  const { data, loading, error, reload } = useLoad(() => api.settings.get<PublishingSettings>("publishing"));
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox message={error ?? "חסר"} onRetry={() => reload()} />;
  return <PublishingForm key={JSON.stringify(data)} initial={data} onSaved={() => { toast.success("מדיניות הפרסום נשמרה"); reload(true); }} />;
}

function PublishingForm({ initial, onSaved }: { initial: PublishingSettings; onSaved: () => void }) {
  const toast = useToast();
  const { overview, refresh } = useSocialStatus();
  const [p, setP] = useState<PublishingSettings>(initial);
  const [confirm, setConfirm] = useState(false);
  const [saving, setSaving] = useState(false);
  const pillars = overview?.pillars ?? [];
  const setAuto = (patch: Partial<PublishingSettings["auto"]>) => setP({ ...p, auto: { ...p.auto, ...patch } });
  const toggle = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
  const save = async () => {
    setSaving(true);
    try {
      const body: PublishingSettings & { confirm_automatic?: boolean } = { ...p };
      if (p.mode === "automatic") body.confirm_automatic = confirm;
      await api.settings.put("publishing", body);
      onSaved(); refresh();
    } catch (e) { toast.error(e); } finally { setSaving(false); }
  };
  return (
    <div className="space-y-4">
      <Card title="מצב פרסום" actions={<Button variant="primary" loading={saving} onClick={save}><Save size={14} /> שמור</Button>}>
        <fieldset className="space-y-2">
          <legend className="sr-only">מצב פרסום</legend>
          {(Object.keys(MODE_HELP) as PublishingSettings["mode"][]).map((m) => (
            <label key={m} className={`flex cursor-pointer items-start gap-2 rounded-lg border p-3 ${p.mode === m ? "border-primary/50 bg-primary/10" : "border-border"}`}>
              <input type="radio" name="mode" className="mt-1 accent-cyan-400" checked={p.mode === m} onChange={() => setP({ ...p, mode: m })} />
              <span><span className="block font-medium">{{ draft_only: "טיוטות בלבד", approval_required: "דורש אישור", automatic: "אוטומטי" }[m]}</span><span className="text-xs text-muted-foreground">{MODE_HELP[m]}</span></span>
            </label>
          ))}
        </fieldset>
        <div className="mt-4">
          <Checkbox label="מצב demo (רשומות הדגמה מוצגות; פרסום לחשבון אמיתי חסום)" checked={p.demo_mode} onChange={(e) => setP({ ...p, demo_mode: e.target.checked })} />
          <p className="mt-1 text-xs text-muted-foreground">השהיית חירום: {p.emergency_pause ? "פעילה" : "כבויה"} — משתנה רק מעמוד הסקירה.</p>
        </div>
      </Card>

      {p.mode === "automatic" && (
        <Card title="גבולות הפרסום האוטומטי">
          <div className="mb-3"><Banner kind="warning">פרסום אוטומטי מפרסם לחשבון אמיתי ללא אישור לכל פריט. הגדר קטגוריות, חשבון, מכסה וחלון זמן, ואשר במפורש.</Banner></div>
          <div className="grid gap-3 md:grid-cols-2">
            <fieldset className="md:col-span-2">
              <legend className="mb-1 text-xs font-medium">קטגוריות (עמודי תוכן) מותרות</legend>
              <div className="flex flex-wrap gap-2">
                {pillars.map((pl) => <Checkbox key={pl.key} label={pl.label} checked={p.auto.allowed_categories.includes(pl.key)} onChange={() => setAuto({ allowed_categories: toggle(p.auto.allowed_categories, pl.key) })} />)}
              </div>
            </fieldset>
            <Field label="חשבון מאושר (ig_user_id)" hint={overview?.account?.ig_user_id ? `חשבון מחובר: ${overview.account.ig_user_id}` : "אין חשבון מחובר"}>
              {(id) => <div className="flex gap-2"><Input id={id} dir="ltr" value={p.auto.allowed_account_id ?? ""} onChange={(e) => setAuto({ allowed_account_id: e.target.value || null })} />{overview?.account?.ig_user_id && <Button size="sm" variant="ghost" onClick={() => setAuto({ allowed_account_id: overview.account!.ig_user_id! })}>מלא מהחשבון</Button>}</div>}
            </Field>
            <Field label="מקסימום פוסטים ביום">{(id) => <Input id={id} type="number" min={1} max={100} value={p.auto.max_posts_per_day} onChange={(e) => setAuto({ max_posts_per_day: Number(e.target.value) })} />}</Field>
            <Field label="חלון זמן — התחלה (שעון ישראל)">{(id) => <Input id={id} type="time" dir="ltr" value={p.auto.window_start} onChange={(e) => setAuto({ window_start: e.target.value })} />}</Field>
            <Field label="חלון זמן — סיום">{(id) => <Input id={id} type="time" dir="ltr" value={p.auto.window_end} onChange={(e) => setAuto({ window_end: e.target.value })} />}</Field>
            <fieldset className="md:col-span-2">
              <legend className="mb-1 text-xs font-medium">נושאים שדורשים סקירה ידנית (חוסמים פרסום אוטומטי)</legend>
              <div className="flex flex-wrap gap-2">
                {Object.entries(REVIEW_TOPICS).map(([k, v]) => <Checkbox key={k} label={v} checked={p.auto.review_topics.includes(k)} onChange={() => setAuto({ review_topics: toggle(p.auto.review_topics, k) })} />)}
              </div>
            </fieldset>
            <div className="md:col-span-2 rounded-lg border border-red-400/40 bg-red-500/10 p-3">
              <Checkbox label="אני מאשר/ת הפעלת פרסום אוטומטי בגבולות שהוגדרו (confirm_automatic)" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
            </div>
          </div>
        </Card>
      )}
      <div className="flex justify-end"><Button variant="primary" loading={saving} disabled={p.mode === "automatic" && !confirm} onClick={save}><Save size={14} /> שמור מדיניות פרסום</Button></div>
    </div>
  );
}

// ── Carousel templates ───────────────────────────────────────────────────────

const COLOR_KEYS: (keyof CarouselTemplate)[] = ["bg", "bg_accent", "accent", "title_color", "body_color", "muted"];
const NUM_KEYS: (keyof CarouselTemplate)[] = ["title_size", "body_size", "footer_size", "margin"];

function TemplatesTab() {
  const toast = useToast();
  const { data, loading, error, reload } = useLoad(() => api.carousel.templates());
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox message={error ?? "חסר"} onRetry={() => reload()} />;
  return <TemplatesForm key={JSON.stringify(data)} initial={data} onSaved={() => { toast.success("התבניות נשמרו"); reload(true); }} />;
}

function TemplatesForm({ initial, onSaved }: { initial: CarouselTemplates; onSaved: () => void }) {
  const toast = useToast();
  const [t, setT] = useState<CarouselTemplates>(initial);
  const [sel, setSel] = useState(initial.default);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [newKey, setNewKey] = useState("");
  const cur = t.templates[sel];
  const setCur = (patch: Partial<CarouselTemplate>) => setT({ ...t, templates: { ...t.templates, [sel]: { ...cur, ...patch } } });
  const save = async () => {
    setSaving(true);
    try { await api.carousel.saveTemplates(t); onSaved(); } catch (e) { toast.error(e); } finally { setSaving(false); }
  };
  const doPreview = async () => {
    setPreviewing(true);
    try {
      // Preview uses the saved template by name — save first for unsaved edits to show.
      const blob = await api.carousel.preview({ kicker: "דוגמה", title: "כותרת לדוגמה בעברית", body: "טקסט גוף קצר שמדגים את התבנית, הצבעים והריווח." }, sel, 0, 3, true);
      if (preview) URL.revokeObjectURL(preview);
      setPreview(URL.createObjectURL(blob));
    } catch (e) { toast.error(e, "תצוגה מקדימה נכשלה"); } finally { setPreviewing(false); }
  };
  const addTemplate = () => {
    const k = newKey.trim().replace(/[^a-z0-9_]/gi, "_").toLowerCase();
    if (!k || t.templates[k]) { toast.error(new Error("מפתח ריק או קיים")); return; }
    setT({ ...t, templates: { ...t.templates, [k]: { ...cur, label: newKey } } }); setSel(k); setNewKey("");
  };
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card title="תבניות" className="lg:col-span-2" actions={<Button variant="primary" loading={saving} onClick={save}><Save size={14} /> שמור תבניות</Button>}>
        <div className="mb-3 flex flex-wrap items-end gap-2">
          <Field label="תבנית לעריכה">{(id) => <Select id={id} value={sel} onChange={(e) => setSel(e.target.value)} className="w-56">{Object.entries(t.templates).map(([k, v]) => <option key={k} value={k}>{v.label} ({k})</option>)}</Select>}</Field>
          <Field label="ברירת מחדל">{(id) => <Select id={id} value={t.default} onChange={(e) => setT({ ...t, default: e.target.value })} className="w-56">{Object.keys(t.templates).map((k) => <option key={k} value={k}>{k}</option>)}</Select>}</Field>
          <Field label="תבנית חדשה (שכפול הנוכחית)">{(id) => <div className="flex gap-1"><Input id={id} placeholder="שם" value={newKey} onChange={(e) => setNewKey(e.target.value)} className="w-40" /><Button size="sm" variant="ghost" onClick={addTemplate}><Plus size={12} /></Button></div>}</Field>
          {Object.keys(t.templates).length > 1 && <Button size="sm" variant="danger" onClick={() => { const next = { ...t.templates }; delete next[sel]; const first = Object.keys(next)[0]; setT({ default: t.default === sel ? first : t.default, templates: next }); setSel(first); }}><Trash2 size={12} /> מחק תבנית</Button>}
        </div>
        {cur && (
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
            <Field label="תווית">{(id) => <Input id={id} value={cur.label} onChange={(e) => setCur({ label: e.target.value })} />}</Field>
            <Field label="כותרת תחתונה (footer)">{(id) => <Input id={id} value={cur.footer} onChange={(e) => setCur({ footer: e.target.value })} />}</Field>
            <div className="flex flex-col gap-2 pt-5">
              <Checkbox label="הצג מונה שקופיות" checked={cur.show_counter} onChange={(e) => setCur({ show_counter: e.target.checked })} />
              <Checkbox label="סימן מים DEMO לרשומות הדגמה" checked={cur.demo_watermark} onChange={(e) => setCur({ demo_watermark: e.target.checked })} />
            </div>
            {COLOR_KEYS.map((k) => (
              <Field key={k} label={k}>{(id) => <div className="flex items-center gap-2"><input id={id} type="color" value={String(cur[k])} onChange={(e) => setCur({ [k]: e.target.value } as Partial<CarouselTemplate>)} className="h-9 w-12 cursor-pointer rounded border border-border bg-transparent" /><Input aria-label={`${k} hex`} dir="ltr" value={String(cur[k])} onChange={(e) => setCur({ [k]: e.target.value } as Partial<CarouselTemplate>)} /></div>}</Field>
            ))}
            {NUM_KEYS.map((k) => (
              <Field key={k} label={k}>{(id) => <Input id={id} type="number" value={Number(cur[k])} onChange={(e) => setCur({ [k]: Number(e.target.value) } as Partial<CarouselTemplate>)} />}</Field>
            ))}
          </div>
        )}
      </Card>
      <Card title="תצוגה מקדימה" actions={<Button size="sm" loading={previewing} onClick={doPreview}><Eye size={12} /> רנדר</Button>}>
        <p className="mb-2 text-xs text-muted-foreground">התצוגה משתמשת בתבנית השמורה — שמור לפני רינדור כדי לראות שינויים.</p>
        {preview
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={preview} alt="תצוגה מקדימה של התבנית" className="w-full rounded-lg border border-border" />
          : <div className="grid aspect-[4/5] place-items-center rounded-lg border border-dashed border-border text-xs text-muted-foreground">אין תצוגה עדיין</div>}
      </Card>
    </div>
  );
}
