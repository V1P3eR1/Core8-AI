"use client";

import { useState } from "react";
import { CheckCircle2, KeyRound, ShieldCheck, Trash2, XCircle } from "lucide-react";
import { useLoad } from "@/components/social/hooks";
import { useToast } from "@/components/social/toast";
import { Badge, Banner, Button, Card, ConfirmButton, ErrorBox, Field, Input, KV, Loading } from "@/components/social/ui";
import { api, fmtUtc, type SecretName, type SecretStatus, type SecretTestResult } from "@/lib/social-api";

const ORDER: SecretName[] = ["anthropic_api_key", "meta_app_id", "meta_app_secret"];
const SOURCE_LABEL: Record<string, string> = { db: "נשמר בדשבורד (מוצפן)", env: "מהגדרות השרת (.env)" };

/** Operator credentials — entered once in the browser, encrypted at rest, never shown again. */
export function SecretsPanel() {
  const { data, loading, error, reload } = useLoad(() => api.secrets.status());
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox message={error ?? "חסר"} onRetry={() => reload()} />;
  const live = data.llm_mode === "live";
  return (
    <div className="space-y-4">
      <Card title="מפתחות וחיבורים" className={live ? "border-emerald-400/30" : "border-yellow-400/30"}>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Badge className={live ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-200" : "border-yellow-400/50 bg-yellow-400/15 text-yellow-200"}>
            LLM: {live ? "live — הסוכנים עובדים עם Claude" : "mock — אין מפתח Anthropic פעיל"}
          </Badge>
          <Badge className="border-border bg-muted/40 text-muted-foreground"><ShieldCheck size={12} className="inline" /> הצפנה: {data.encryption_ready ? "פעילה" : "חסר IG_TOKEN_ENC_KEY"}</Badge>
        </div>
        {!data.encryption_ready && <div className="mb-3"><Banner kind="danger">השרת ללא מפתח הצפנה (IG_TOKEN_ENC_KEY). לא ניתן לשמור מפתחות עד שהוא מוגדר ב-.env.production.</Banner></div>}
        <Banner kind="info">
          המפתחות נשמרים מוצפנים במסד הנתונים ולא מוצגים שוב — רק 4 התווים האחרונים. הדבקה כאן מחליפה את הצורך לערוך קבצים בשרת. המערכת קולטת שינוי תוך ~20 שניות, גם ב-worker.
        </Banner>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {ORDER.map((name) => <SecretRow key={name} name={name} item={data.items[name]} disabled={!data.encryption_ready} onChanged={() => reload()} />)}
        </div>
      </Card>
    </div>
  );
}

function SecretRow({ name, item, disabled, onChanged }: { name: SecretName; item: SecretStatus; disabled: boolean; onChanged: () => void }) {
  const toast = useToast();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [test, setTest] = useState<SecretTestResult | null>(null);
  const isSecretLike = name !== "meta_app_id";

  const save = async () => {
    if (!value.trim()) return;
    setBusy(true);
    try {
      const r = await api.secrets.set(name, value);
      setValue("");
      toast.success(`${item.label} נשמר (${r.item.hint}) · LLM: ${r.llm_mode}`);
      onChanged();
    } catch (e) { toast.error(e); } finally { setBusy(false); }
  };
  const runTest = async (candidate?: string) => {
    setBusy(true); setTest(null);
    try {
      const r = await api.secrets.testAnthropic(candidate);
      setTest(r);
      if (r.ok) toast.success(`המפתח עובד — ${r.model} ענה "${r.reply}"`);
      else toast.error(r.message ?? "הבדיקה נכשלה");
    } catch (e) { toast.error(e); } finally { setBusy(false); }
  };
  const remove = async () => {
    try { await api.secrets.remove(name); toast.success(`${item.label} הוסר`); onChanged(); }
    catch (e) { toast.error(e); }
  };

  return (
    <div className="rounded-xl border border-border bg-muted/20 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold"><KeyRound size={14} /> {item.label}</h3>
        {item.configured
          ? <Badge className="border-emerald-400/40 bg-emerald-500/15 text-emerald-200"><CheckCircle2 size={12} className="inline" /> מוגדר</Badge>
          : <Badge className="border-red-400/40 bg-red-500/10 text-red-200"><XCircle size={12} className="inline" /> חסר</Badge>}
      </div>
      <p className="mb-3 text-xs text-muted-foreground">{item.help}</p>
      <dl className="mb-3 grid grid-cols-2 gap-2 text-xs">
        <KV label="מקור">{item.source ? SOURCE_LABEL[item.source] : "—"}</KV>
        <KV label="רמז"><span dir="ltr" className="font-mono">{item.hint ?? "—"}</span></KV>
        {item.updated_at && <KV label="עודכן">{fmtUtc(item.updated_at)}</KV>}
        {item.updated_by && <KV label="על-ידי">{item.updated_by}</KV>}
      </dl>
      <Field label={item.configured ? "החלפה — הדבק ערך חדש" : "הדבק ערך"} hint={isSecretLike ? "הערך לא יוצג לאחר השמירה" : undefined}>
        {(id) => (
          <Input id={id} dir="ltr" type={isSecretLike ? "password" : "text"} autoComplete="off" spellCheck={false}
            value={value} onChange={(e) => setValue(e.target.value)} placeholder={name === "anthropic_api_key" ? "sk-ant-api03-…" : name === "meta_app_id" ? "1234567890" : "app secret"} disabled={disabled} />
        )}
      </Field>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="primary" size="sm" loading={busy} disabled={disabled || !value.trim()} onClick={save}>שמור</Button>
        {item.testable && value.trim() && <Button size="sm" loading={busy} disabled={disabled} onClick={() => runTest(value)}>בדוק לפני שמירה</Button>}
        {item.testable && !value.trim() && item.configured && <Button size="sm" loading={busy} onClick={() => runTest()}>בדוק חיבור</Button>}
        {item.source === "db" && (
          <ConfirmButton size="sm" variant="ghost" label={<><Trash2 size={12} /> הסר</>} confirmTitle={`להסיר את ${item.label}?`}
            confirmText="הערך השמור יימחק. אם קיים ערך בהגדרות השרת (.env) הוא יחזור לשימוש; אחרת הרכיב יעבור למצב mock." onConfirm={remove} confirmLabel="הסר" />
        )}
      </div>
      {test && (
        <p className={`mt-2 text-xs ${test.ok ? "text-emerald-200" : "text-red-200"}`}>
          {test.ok ? `✓ ${test.model} ענה: "${test.reply}"` : `✗ ${test.message}`}
        </p>
      )}
    </div>
  );
}
