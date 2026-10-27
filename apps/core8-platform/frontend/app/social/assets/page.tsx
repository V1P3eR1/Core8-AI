"use client";

import { useState } from "react";
import { Pencil, Trash2, Upload } from "lucide-react";
import AssetThumb from "@/components/social/AssetThumb";
import { useLoad } from "@/components/social/hooks";
import { useToast } from "@/components/social/toast";
import { Badge, Button, Card, ConfirmButton, DemoBadge, EmptyState, ErrorBox, Field, Input, Loading, Modal, PageHeader, Select, Textarea } from "@/components/social/ui";
import { OWNERSHIP_LABELS, api, fmtUtc, isDemo, type Asset } from "@/lib/social-api";

type Meta = { ownership: string; permission_note: string; alt_text: string; caption: string; brief: string };
const EMPTY: Meta = { ownership: "owner_upload", permission_note: "", alt_text: "", caption: "", brief: "" };

export default function AssetsPage() {
  const toast = useToast();
  const { data, loading, error, reload, setData } = useLoad(() => api.assets.list());
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState<Meta>(EMPTY);
  const [uploading, setUploading] = useState(false);
  const [edit, setEdit] = useState<Asset | null>(null);
  const [editMeta, setEditMeta] = useState<Meta>(EMPTY);
  const [saving, setSaving] = useState(false);

  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("ownership", meta.ownership);
      if (meta.permission_note) fd.append("permission_note", meta.permission_note);
      if (meta.alt_text) fd.append("alt_text", meta.alt_text);
      if (meta.caption) fd.append("caption", meta.caption);
      if (meta.brief) fd.append("brief", meta.brief);
      const a = await api.assets.upload(fd);
      toast.success(a.spec_check?.ok === false ? "הועלה — אך לא עומד במפרט Instagram (ראה בדיקה)" : "הנכס הועלה");
      setFile(null); setMeta(EMPTY);
      (e.target as HTMLFormElement).reset();
      await reload(true);
    } catch (err) { toast.error(err); } finally { setUploading(false); }
  };

  const openEdit = (a: Asset) => {
    setEdit(a);
    setEditMeta({ ownership: a.ownership, permission_note: a.permission_note ?? "", alt_text: a.alt_text ?? "", caption: a.caption ?? "", brief: a.brief ?? "" });
  };
  const saveEdit = async () => {
    if (!edit) return;
    setSaving(true);
    try {
      const row = await api.assets.patch(edit.id, editMeta);
      setData((d) => d ? { ...d, items: d.items.map((x) => (x.id === row.id ? row : x)) } : d);
      toast.success("הנכס עודכן"); setEdit(null);
    } catch (err) { toast.error(err); } finally { setSaving(false); }
  };
  const remove = async (a: Asset) => {
    try { await api.assets.delete(a.id); toast.success("הנכס נמחק"); await reload(true); } catch (err) { toast.error(err); }
  };

  const metaFields = (m: Meta, set: (m: Meta) => void) => (
    <>
      <Field label="בעלות">{(id) => (
        <Select id={id} value={m.ownership} onChange={(e) => set({ ...m, ownership: e.target.value })}>
          {Object.entries(OWNERSHIP_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      )}</Field>
      <Field label="הערת הרשאה" hint="מי נתן רשות לשימוש (חובה לחומר של צד שלישי)">{(id) => <Input id={id} value={m.permission_note} onChange={(e) => set({ ...m, permission_note: e.target.value })} />}</Field>
      <Field label="Alt text" hint="≤1000 תווים">{(id) => <Input id={id} maxLength={1000} value={m.alt_text} onChange={(e) => set({ ...m, alt_text: e.target.value })} />}</Field>
      <Field label="כיתוב">{(id) => <Input id={id} value={m.caption} onChange={(e) => set({ ...m, caption: e.target.value })} />}</Field>
      <Field label="בריף" className="sm:col-span-2">{(id) => <Textarea id={id} value={m.brief} onChange={(e) => set({ ...m, brief: e.target.value })} />}</Field>
    </>
  );

  return (
    <>
      <PageHeader title="נכסים וקבצים" subtitle={data ? `מותר: ${data.allowed_mime.join(", ")} · עד ${data.max_upload_mb}MB לקובץ` : undefined} />
      <Card title="העלאת נכס" className="mb-5">
        <form onSubmit={upload} className="grid gap-3 sm:grid-cols-2">
          <Field label="קובץ" required className="sm:col-span-2">{(id) => <Input id={id} type="file" required accept={data?.allowed_mime.join(",")} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}</Field>
          {metaFields(meta, setMeta)}
          <div className="sm:col-span-2"><Button type="submit" variant="primary" loading={uploading} disabled={!file}><Upload size={14} /> העלה</Button></div>
        </form>
      </Card>

      {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={() => reload()} /> : (data?.items.length ?? 0) === 0 ? (
        <EmptyState title="אין נכסים עדיין. העלה תמונה (JPEG) או וידאו (MP4) בטופס למעלה, או רנדר קרוסלה מפריט תוכן." />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {data!.items.map((a) => (
            <Card key={a.id} as="article" className="flex flex-col gap-2 p-3">
              <AssetThumb asset={a} size="lg" className="h-40" />
              <div className="flex flex-wrap gap-1">
                <DemoBadge show={isDemo(a)} />
                <Badge className="border-border bg-muted">{OWNERSHIP_LABELS[a.ownership] ?? a.ownership}</Badge>
                {a.spec_check ? (
                  <Badge className={a.spec_check.ok ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-200" : "border-red-400/40 bg-red-500/15 text-red-200"} title={[...a.spec_check.problems, ...a.spec_check.warnings].join("\n") || "עומד במפרט"}>
                    {a.spec_check.ok ? "מפרט ✓" : `מפרט ✗ (${a.spec_check.problems.length})`}
                  </Badge>
                ) : <Badge className="border-border text-muted-foreground">מפרט: חסר</Badge>}
                {a.spec_check?.warnings.length ? <Badge className="border-yellow-400/40 text-yellow-200" title={a.spec_check.warnings.join("\n")}>{a.spec_check.warnings.length} אזהרות</Badge> : null}
              </div>
              <p className="truncate text-sm font-medium" title={a.original_name ?? a.filename}>{a.original_name ?? a.filename}</p>
              <p className="text-[11px] text-muted-foreground" dir="ltr">
                {a.mime} · {(a.bytes / 1024 / 1024).toFixed(2)}MB{a.width && a.height ? ` · ${a.width}×${a.height}` : ""}{a.duration_s ? ` · ${a.duration_s.toFixed(0)}s` : ""}
              </p>
              {a.spec_check && !a.spec_check.ok && <ul className="text-[11px] text-red-300">{a.spec_check.problems.map((p, i) => <li key={i}>• {p}</li>)}</ul>}
              <p className="text-[11px] text-muted-foreground">alt: {a.alt_text || "חסר"} · {fmtUtc(a.created_at)}</p>
              <div className="mt-auto flex gap-1">
                <Button size="sm" variant="ghost" onClick={() => openEdit(a)}><Pencil size={12} /> ערוך</Button>
                <ConfirmButton label={<><Trash2 size={12} /> מחק</>} size="sm" confirmTitle="מחיקת נכס" confirmText="הקובץ יימחק מהשרת. נכס המשויך לפריט מתוזמן לא יימחק." onConfirm={() => remove(a)} />
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={!!edit} onClose={() => setEdit(null)} title="עריכת נכס" footer={<><Button variant="ghost" onClick={() => setEdit(null)}>ביטול</Button><Button variant="primary" loading={saving} onClick={saveEdit}>שמור</Button></>}>
        <div className="grid gap-3 sm:grid-cols-2">{metaFields(editMeta, setEditMeta)}</div>
      </Modal>
    </>
  );
}
