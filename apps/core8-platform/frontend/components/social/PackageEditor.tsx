"use client";

import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Eye, Plus, Trash2 } from "lucide-react";
import { Button, Field, Input, Select, Textarea } from "./ui";
import { useToast } from "./toast";
import { PRODUCTION_LABELS, api, type CarouselTemplates, type Format, type Package } from "@/lib/social-api";

type Setter = (next: Package) => void;

const str = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));
const strList = (v: unknown): string[] => (Array.isArray(v) ? v.map((x) => (typeof x === "string" ? x : JSON.stringify(x))) : []);
const objList = <T extends Record<string, unknown>>(v: unknown): T[] => (Array.isArray(v) ? v.filter((x): x is T => !!x && typeof x === "object") : []);

/** Lines textarea bound to a string[] field. */
export function LinesField({ label, value, onChange, hint }: { label: string; value: string[]; onChange: (v: string[]) => void; hint?: string }) {
  // Local text keeps blank lines while typing; the emitted list drops them.
  const [text, setText] = useState(value.join("\n"));
  return (
    <Field label={label} hint={hint ?? "שורה לכל פריט"}>
      {(id) => <Textarea id={id} value={text} onChange={(e) => { setText(e.target.value); onChange(e.target.value.split("\n").map((l) => l.trim()).filter(Boolean)); }} />}
    </Field>
  );
}

function TextField({ label, value, onChange, multiline, hint }: { label: string; value: string; onChange: (v: string) => void; multiline?: boolean; hint?: string }) {
  return (
    <Field label={label} hint={hint}>
      {(id) => multiline
        ? <Textarea id={id} value={value} onChange={(e) => onChange(e.target.value)} />
        : <Input id={id} value={value} onChange={(e) => onChange(e.target.value)} />}
    </Field>
  );
}

function SourcesEditor({ value, onChange }: { value: { title?: string; url?: string }[]; onChange: (v: { title: string; url: string }[]) => void }) {
  const rows = value.map((s) => ({ title: str(s.title), url: str(s.url) }));
  const set = (i: number, patch: Partial<{ title: string; url: string }>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <fieldset className="rounded-xl border border-border p-3">
      <legend className="px-1 text-xs font-medium">מקורות (רק מקורות שצוטטו — טענה ללא מקור מסומנת)</legend>
      {rows.length === 0 && <p className="text-xs text-muted-foreground">אין מקורות.</p>}
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <Input aria-label={`כותרת מקור ${i + 1}`} placeholder="כותרת" value={r.title} onChange={(e) => set(i, { title: e.target.value })} className="flex-1 min-w-[140px]" />
            <Input aria-label={`URL מקור ${i + 1}`} placeholder="https://…" dir="ltr" value={r.url} onChange={(e) => set(i, { url: e.target.value })} className="flex-[2] min-w-[180px]" />
            <Button size="sm" variant="danger" aria-label="הסר מקור" onClick={() => onChange(rows.filter((_, j) => j !== i))}><Trash2 size={12} /></Button>
          </div>
        ))}
      </div>
      <Button size="sm" variant="ghost" className="mt-2" onClick={() => onChange([...rows, { title: "", url: "" }])}><Plus size={12} /> הוסף מקור</Button>
    </fieldset>
  );
}

export function ProductionStatusField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Field label="סטטוס הפקה">
      {(id) => (
        <Select id={id} value={value || "script_only"} onChange={(e) => onChange(e.target.value)}>
          {Object.entries(PRODUCTION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      )}
    </Field>
  );
}

// ── Carousel slides ──────────────────────────────────────────────────────────

type Slide = { kicker?: string; title?: string; body?: string; [k: string]: unknown };

function SlidePreview({ slide, template, index, total, isDemo }: { slide: Slide; template: string | null; index: number; total: number; isDemo: boolean }) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const toast = useToast();
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  const render = async () => {
    setLoading(true);
    try {
      const blob = await api.carousel.preview({ kicker: slide.kicker, title: slide.title, body: slide.body }, template, index, total, isDemo);
      setUrl(URL.createObjectURL(blob));
    } catch (e) { toast.error(e, "תצוגה מקדימה נכשלה"); } finally { setLoading(false); }
  };
  return (
    <div className="flex flex-col items-center gap-2">
      {url
        // eslint-disable-next-line @next/next/no-img-element
        ? <img src={url} alt={`תצוגה מקדימה שקופית ${index + 1}`} className="w-40 rounded-lg border border-border" />
        : <div className="grid aspect-[4/5] w-40 place-items-center rounded-lg border border-dashed border-border text-[11px] text-muted-foreground">ללא תצוגה</div>}
      <Button size="sm" variant="ghost" loading={loading} onClick={render}><Eye size={12} /> {url ? "רענן תצוגה" : "תצוגה מקדימה"}</Button>
    </div>
  );
}

function SlidesEditor({ slides, onChange, template, isDemo }: { slides: Slide[]; onChange: (s: Slide[]) => void; template: string | null; isDemo: boolean }) {
  const set = (i: number, patch: Slide) => onChange(slides.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= slides.length) return;
    const next = [...slides];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };
  return (
    <fieldset className="rounded-xl border border-border p-3">
      <legend className="px-1 text-xs font-medium">שקופיות ({slides.length}) — קרוסלה דורשת 2–20</legend>
      <div className="space-y-3">
        {slides.map((s, i) => (
          <div key={i} className="flex flex-col gap-3 rounded-lg border border-border/60 bg-background/40 p-3 md:flex-row">
            <div className="flex-1 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-primary">שקופית {i + 1}</span>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" aria-label="הזז למעלה" disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp size={12} /></Button>
                  <Button size="sm" variant="ghost" aria-label="הזז למטה" disabled={i === slides.length - 1} onClick={() => move(i, 1)}><ArrowDown size={12} /></Button>
                  <Button size="sm" variant="danger" aria-label="מחק שקופית" onClick={() => onChange(slides.filter((_, j) => j !== i))}><Trash2 size={12} /></Button>
                </div>
              </div>
              <Input aria-label={`קיקר שקופית ${i + 1}`} placeholder="קיקר (אופציונלי)" value={str(s.kicker)} onChange={(e) => set(i, { kicker: e.target.value })} />
              <Input aria-label={`כותרת שקופית ${i + 1}`} placeholder="כותרת" value={str(s.title)} onChange={(e) => set(i, { title: e.target.value })} />
              <Textarea aria-label={`גוף שקופית ${i + 1}`} placeholder="טקסט" value={str(s.body)} onChange={(e) => set(i, { body: e.target.value })} />
            </div>
            <SlidePreview slide={s} template={template} index={i} total={slides.length} isDemo={isDemo} />
          </div>
        ))}
      </div>
      <Button size="sm" variant="ghost" className="mt-3" onClick={() => onChange([...slides, { title: "", body: "" }])}><Plus size={12} /> הוסף שקופית</Button>
    </fieldset>
  );
}

// ── Main editor ──────────────────────────────────────────────────────────────

export default function PackageEditor({ format, pkg, onChange, templates, isDemo }: { format: Format; pkg: Package; onChange: Setter; templates: CarouselTemplates | null; isDemo: boolean }) {
  const set = (k: string, v: unknown) => onChange({ ...pkg, [k]: v });
  const [rawOpen, setRawOpen] = useState(false);
  const [raw, setRaw] = useState("");
  const [rawErr, setRawErr] = useState<string | null>(null);

  const sources = <SourcesEditor value={objList<{ title?: string; url?: string }>(pkg.sources)} onChange={(v) => set("sources", v)} />;
  const required = <LinesField label="נכסים נדרשים" value={strList(pkg.required_assets)} onChange={(v) => set("required_assets", v)} />;

  return (
    <div className="space-y-4">
      {typeof pkg.origin === "string" && <p className="text-xs text-muted-foreground">מקור החבילה: {pkg.origin === "mock" ? "תבנית ללא LLM (mock) — לעריכה" : pkg.origin}{typeof pkg.label === "string" ? ` · ${pkg.label}` : ""}</p>}

      {format === "reel" && (
        <div className="grid gap-3 md:grid-cols-2">
          <LinesField label="הוקים (פתיחים)" value={strList(pkg.hooks)} onChange={(v) => set("hooks", v)} />
          <LinesField label="טקסט על המסך" value={strList(pkg.on_screen_text)} onChange={(v) => set("on_screen_text", v)} />
          <div className="md:col-span-2">
            <ScriptEditor value={objList<{ t?: string | number; text?: string }>(pkg.script)} onChange={(v) => set("script", v)} />
          </div>
          <LinesField label="Shot list" value={strList(pkg.shot_list)} onChange={(v) => set("shot_list", v)} />
          <div className="space-y-3">
            <TextField label="טקסט כריכה" value={str(pkg.cover_text)} onChange={(v) => set("cover_text", v)} />
            <TextField label="קריאה לפעולה (CTA)" value={str(pkg.cta)} onChange={(v) => set("cta", v)} />
            <TextField label="משך (שניות)" value={str(pkg.duration_s)} onChange={(v) => set("duration_s", v === "" ? null : Number(v) || v)} />
          </div>
          <div className="md:col-span-2">{sources}</div>
          {required}
          <ProductionStatusField value={str(pkg.production_status)} onChange={(v) => set("production_status", v)} />
        </div>
      )}

      {format === "carousel" && (
        <div className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <TextField label="הוק" value={str(pkg.hook)} onChange={(v) => set("hook", v)} />
            <TextField label="מבנה" value={str(pkg.structure)} onChange={(v) => set("structure", v)} />
            <TextField label="כיוון ויזואלי" value={str(pkg.visual_direction)} onChange={(v) => set("visual_direction", v)} multiline />
            <div className="space-y-3">
              <TextField label="קריאה לפעולה (CTA)" value={str(pkg.cta)} onChange={(v) => set("cta", v)} />
              <Field label="תבנית רינדור" hint="ניתן לערוך תבניות בעמוד 'הגדרות מותג'">
                {(id) => (
                  <Select id={id} value={str(pkg.template) || templates?.default || ""} onChange={(e) => set("template", e.target.value || null)}>
                    {!templates && <option value="">טוען תבניות…</option>}
                    {templates && Object.entries(templates.templates).map(([k, t]) => <option key={k} value={k}>{t.label} ({k})</option>)}
                  </Select>
                )}
              </Field>
            </div>
          </div>
          <SlidesEditor slides={objList<Slide>(pkg.slides)} onChange={(v) => set("slides", v)} template={str(pkg.template) || templates?.default || null} isDemo={isDemo} />
          {sources}
          <TextField label="הערות אימות" value={str(pkg.verification_notes)} onChange={(v) => set("verification_notes", v)} multiline />
          <ProductionStatusField value={str(pkg.production_status)} onChange={(v) => set("production_status", v)} />
        </div>
      )}

      {format === "image" && (
        <div className="grid gap-3 md:grid-cols-2">
          <TextField label="כותרת ראשית" value={str(pkg.headline)} onChange={(v) => set("headline", v)} />
          <TextField label="קריאה לפעולה (CTA)" value={str(pkg.cta)} onChange={(v) => set("cta", v)} />
          <TextField label="גוף" value={str(pkg.body)} onChange={(v) => set("body", v)} multiline />
          <TextField label="בריף ויזואלי" value={str(pkg.visual_brief)} onChange={(v) => set("visual_brief", v)} multiline />
          <TextField label="Alt text (≤1000 תווים)" value={str(pkg.alt_text)} onChange={(v) => set("alt_text", v)} multiline />
          {required}
          <div className="md:col-span-2">{sources}</div>
          <ProductionStatusField value={str(pkg.production_status)} onChange={(v) => set("production_status", v)} />
        </div>
      )}

      {format === "story" && (
        <div className="grid gap-3 md:grid-cols-2">
          <div className="md:col-span-2">
            <FramesEditor value={objList<{ text?: string; sticker?: string | null }>(pkg.frames)} onChange={(v) => set("frames", v)} />
          </div>
          <TextField label="טקסט הסטורי" value={str(pkg.story_text)} onChange={(v) => set("story_text", v)} multiline />
          <TextField label="קריאה לפעולה (CTA)" value={str(pkg.cta)} onChange={(v) => set("cta", v)} />
          <TextField label="הערות" value={str(pkg.notes)} onChange={(v) => set("notes", v)} multiline />
          {required}
          <ProductionStatusField value={str(pkg.production_status)} onChange={(v) => set("production_status", v)} />
        </div>
      )}

      {Array.isArray(pkg.production_checklist) && (
        <div className="rounded-xl border border-border/60 bg-background/40 p-3">
          <p className="mb-1 text-xs font-medium">צ&apos;קליסט הפקה</p>
          <ul className="list-disc ps-5 text-xs text-muted-foreground">{strList(pkg.production_checklist).map((c, i) => <li key={i}>{c}</li>)}</ul>
        </div>
      )}

      <div>
        <Button size="sm" variant="ghost" onClick={() => { setRaw(JSON.stringify(pkg, null, 2)); setRawErr(null); setRawOpen(!rawOpen); }}>
          {rawOpen ? "הסתר JSON" : "ערוך JSON גולמי (מתקדם)"}
        </Button>
        {rawOpen && (
          <div className="mt-2 space-y-2">
            <Textarea dir="ltr" aria-label="JSON של החבילה" className="min-h-[220px] font-mono text-xs" value={raw} onChange={(e) => setRaw(e.target.value)} />
            {rawErr && <p className="text-xs text-red-300">{rawErr}</p>}
            <Button size="sm" onClick={() => {
              try { const parsed = JSON.parse(raw); if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("JSON חייב להיות אובייקט"); onChange(parsed as Package); setRawErr(null); setRawOpen(false); }
              catch (e) { setRawErr(e instanceof Error ? e.message : "JSON לא תקין"); }
            }}>החל JSON</Button>
          </div>
        )}
      </div>
    </div>
  );
}

function ScriptEditor({ value, onChange }: { value: { t?: string | number; text?: string }[]; onChange: (v: { t: string; text: string }[]) => void }) {
  const rows = value.map((r) => ({ t: str(r.t), text: str(r.text) }));
  const set = (i: number, p: Partial<{ t: string; text: string }>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  return (
    <fieldset className="rounded-xl border border-border p-3">
      <legend className="px-1 text-xs font-medium">תסריט (זמן + טקסט)</legend>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="flex items-start gap-2">
            <Input aria-label={`זמן שורה ${i + 1}`} placeholder="0-3s" value={r.t} onChange={(e) => set(i, { t: e.target.value })} className="w-24" />
            <Textarea aria-label={`טקסט שורה ${i + 1}`} value={r.text} onChange={(e) => set(i, { text: e.target.value })} className="min-h-[44px] flex-1" />
            <Button size="sm" variant="danger" aria-label="הסר שורה" onClick={() => onChange(rows.filter((_, j) => j !== i))}><Trash2 size={12} /></Button>
          </div>
        ))}
      </div>
      <Button size="sm" variant="ghost" className="mt-2" onClick={() => onChange([...rows, { t: "", text: "" }])}><Plus size={12} /> הוסף שורה</Button>
    </fieldset>
  );
}

function FramesEditor({ value, onChange }: { value: { text?: string; sticker?: string | null }[]; onChange: (v: { text: string; sticker: string | null }[]) => void }) {
  const rows = value.map((r) => ({ text: str(r.text), sticker: r.sticker == null ? null : str(r.sticker) }));
  const set = (i: number, p: Partial<{ text: string; sticker: string | null }>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  return (
    <fieldset className="rounded-xl border border-border p-3">
      <legend className="px-1 text-xs font-medium">פריימים (מדבקות/סקרים — ידנית באפליקציה, לא דרך API)</legend>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="flex items-start gap-2">
            <Textarea aria-label={`טקסט פריים ${i + 1}`} value={r.text} onChange={(e) => set(i, { text: e.target.value })} className="min-h-[44px] flex-1" />
            <Input aria-label={`מדבקה פריים ${i + 1}`} placeholder="מדבקה" value={r.sticker ?? ""} onChange={(e) => set(i, { sticker: e.target.value || null })} className="w-32" />
            <Button size="sm" variant="danger" aria-label="הסר פריים" onClick={() => onChange(rows.filter((_, j) => j !== i))}><Trash2 size={12} /></Button>
          </div>
        ))}
      </div>
      <Button size="sm" variant="ghost" className="mt-2" onClick={() => onChange([...rows, { text: "", sticker: null }])}><Plus size={12} /> הוסף פריים</Button>
    </fieldset>
  );
}
