"use client";

import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useLoad } from "@/components/social/hooks";
import { useToast } from "@/components/social/toast";
import { Button, Card, ConfirmButton, DemoBadge, EmptyState, ErrorBox, Field, Input, Loading, Modal, PageHeader, Select, StatusBadge, Table, Td, Textarea, Th } from "@/components/social/ui";
import { LEAD_STATUS_LABELS, api, fmtDate, fmtUtc, isDemo, type Lead, type LeadIn } from "@/lib/social-api";

const EMPTY: LeadIn = { name: "", handle: "", lead_date: "", source: "", business_type: "", need: "", status: "new", next_action: "", notes: "", consent_note: "" };
const LEAD_COLORS: Record<string, string> = { new: "pending", contacted: "running", qualified: "approved", proposal: "scheduled", won: "published", lost: "failed", archived: "cancelled" };

export default function LeadsPage() {
  const toast = useToast();
  const { data, loading, error, reload } = useLoad(() => api.leads.list());
  const [editing, setEditing] = useState<Lead | "new" | null>(null);
  const [form, setForm] = useState<LeadIn>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [purgeDays, setPurgeDays] = useState(365);

  const open = (l: Lead | "new") => {
    setEditing(l);
    setForm(l === "new" ? EMPTY : { name: l.name, handle: l.handle ?? "", lead_date: l.lead_date ?? "", source: l.source ?? "", business_type: l.business_type ?? "", need: l.need ?? "", status: l.status, next_action: l.next_action ?? "", notes: l.notes ?? "", consent_note: l.consent_note ?? "" });
  };
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v === "" ? null : v])) as Partial<LeadIn> & { name: string };
      if (editing === "new") await api.leads.add(body); else if (editing) await api.leads.patch(editing.id, body);
      toast.success("הליד נשמר"); setEditing(null); await reload(true);
    } catch (err) { toast.error(err); } finally { setSaving(false); }
  };
  const statuses = data?.statuses ?? Object.keys(LEAD_STATUS_LABELS);

  return (
    <>
      <PageHeader
        title="פניות ולידים"
        subtitle="רישום ידני של פניות שהתקבלו כדין (ללא שליחת הודעות). שמור הערת הסכמה לכל ליד."
        actions={<>
          <div className="flex items-center gap-1">
            <label htmlFor="purge-days" className="text-xs text-muted-foreground">מחק ישנים מ-</label>
            <Input id="purge-days" type="number" min={1} max={3650} value={purgeDays} onChange={(e) => setPurgeDays(Number(e.target.value))} className="w-20 py-1" />
            <span className="text-xs text-muted-foreground">ימים</span>
            <ConfirmButton label="נקה" size="sm" confirmTitle="מחיקת לידים ישנים" confirmText={`כל הלידים שנוצרו לפני יותר מ-${purgeDays} ימים יימחקו לצמיתות. להמשיך?`}
              onConfirm={async () => { try { const r = await api.leads.purge(purgeDays); toast.success(`נמחקו ${r.deleted} לידים`); await reload(true); } catch (e) { toast.error(e); } }} />
          </div>
          <Button variant="primary" onClick={() => open("new")}><Plus size={14} /> ליד חדש</Button>
        </>}
      />
      {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={() => reload()} /> : (data?.items.length ?? 0) === 0 ? (
        <EmptyState title="אין לידים. הוסף פנייה שהתקבלה (תגובה, הודעה, טופס) עם הערת הסכמה." action={<Button size="sm" variant="primary" onClick={() => open("new")}>ליד חדש</Button>} />
      ) : (
        <Card>
          <Table>
            <thead><tr><Th>שם</Th><Th>תאריך</Th><Th>מקור</Th><Th>סוג עסק</Th><Th>צורך</Th><Th>סטטוס</Th><Th>פעולה הבאה</Th><Th>הסכמה</Th><Th></Th></tr></thead>
            <tbody>{data!.items.map((l) => (
              <tr key={l.id}>
                <Td><div className="flex flex-wrap items-center gap-1"><span className="font-medium">{l.name}</span><DemoBadge show={isDemo(l)} /></div>{l.handle && <span className="text-xs text-muted-foreground" dir="ltr">{l.handle}</span>}</Td>
                <Td className="text-xs whitespace-nowrap">{l.lead_date ? fmtDate(l.lead_date) : fmtUtc(l.created_at)}</Td>
                <Td className="text-xs">{l.source ?? "חסר"}</Td>
                <Td className="text-xs">{l.business_type ?? "חסר"}</Td>
                <Td className="max-w-xs text-xs">{l.need ?? "חסר"}</Td>
                <Td><StatusBadge status={LEAD_COLORS[l.status] ?? l.status} labels={{ [LEAD_COLORS[l.status] ?? l.status]: LEAD_STATUS_LABELS[l.status] ?? l.status }} /></Td>
                <Td className="max-w-xs text-xs">{l.next_action ?? "חסר"}</Td>
                <Td className="max-w-[160px] text-xs text-muted-foreground">{l.consent_note ?? "חסר"}</Td>
                <Td><div className="flex gap-1">
                  <Button size="sm" variant="ghost" aria-label="ערוך" onClick={() => open(l)}><Pencil size={12} /></Button>
                  <ConfirmButton label={<Trash2 size={12} />} size="sm" confirmTitle="מחיקת ליד" confirmText={`למחוק את "${l.name}"?`} onConfirm={async () => { try { await api.leads.delete(l.id); toast.success("נמחק"); await reload(true); } catch (e) { toast.error(e); } }} />
                </div></Td>
              </tr>
            ))}</tbody>
          </Table>
        </Card>
      )}

      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing === "new" ? "ליד חדש" : "עריכת ליד"} wide>
        <form onSubmit={save} className="grid gap-3 sm:grid-cols-2">
          <Field label="שם" required>{(id) => <Input id={id} required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}</Field>
          <Field label="מזהה חשבון (handle)">{(id) => <Input id={id} dir="ltr" value={form.handle ?? ""} onChange={(e) => setForm({ ...form, handle: e.target.value })} />}</Field>
          <Field label="תאריך הפנייה">{(id) => <Input id={id} type="date" value={form.lead_date ?? ""} onChange={(e) => setForm({ ...form, lead_date: e.target.value })} />}</Field>
          <Field label="מקור">{(id) => <Input id={id} placeholder="תגובה / הודעה / טופס / המלצה" value={form.source ?? ""} onChange={(e) => setForm({ ...form, source: e.target.value })} />}</Field>
          <Field label="סוג עסק">{(id) => <Input id={id} value={form.business_type ?? ""} onChange={(e) => setForm({ ...form, business_type: e.target.value })} />}</Field>
          <Field label="סטטוס">{(id) => <Select id={id} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>{statuses.map((s) => <option key={s} value={s}>{LEAD_STATUS_LABELS[s] ?? s}</option>)}</Select>}</Field>
          <Field label="הצורך">{(id) => <Textarea id={id} value={form.need ?? ""} onChange={(e) => setForm({ ...form, need: e.target.value })} />}</Field>
          <Field label="פעולה הבאה">{(id) => <Textarea id={id} value={form.next_action ?? ""} onChange={(e) => setForm({ ...form, next_action: e.target.value })} />}</Field>
          <Field label="הערות">{(id) => <Textarea id={id} value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} />}</Field>
          <Field label="הערת הסכמה" hint="איך ומתי הסכים/ה ליצירת קשר">{(id) => <Textarea id={id} value={form.consent_note ?? ""} onChange={(e) => setForm({ ...form, consent_note: e.target.value })} />}</Field>
          <div className="flex justify-end gap-2 sm:col-span-2"><Button variant="ghost" onClick={() => setEditing(null)}>ביטול</Button><Button type="submit" variant="primary" loading={saving}>שמור</Button></div>
        </form>
      </Modal>
    </>
  );
}
