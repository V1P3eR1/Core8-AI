"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, Inbox, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { STATUS_COLORS } from "@/lib/social-api";

// ── Buttons ──────────────────────────────────────────────────────────────────

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-primary text-primary-foreground hover:bg-primary/85 border-transparent font-semibold shadow-[0_0_14px_rgba(0,212,255,0.25)]",
  secondary: "bg-accent text-accent-foreground hover:bg-primary/20 border-primary/25",
  ghost: "bg-transparent text-foreground/80 hover:bg-muted border-border",
  danger: "bg-destructive/15 text-red-200 hover:bg-destructive/30 border-destructive/40",
  success: "bg-emerald-500/15 text-emerald-200 hover:bg-emerald-500/30 border-emerald-400/40",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
  loading?: boolean;
}

export function Button({ variant = "secondary", size = "md", loading, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-lg border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-2 text-sm",
        VARIANTS[variant], className,
      )}
    >
      {loading && <Loader2 size={14} className="animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

// ── Layout ───────────────────────────────────────────────────────────────────

export function Card({ className, children, title, actions, as: Tag = "section" }: { className?: string; children: ReactNode; title?: ReactNode; actions?: ReactNode; as?: "section" | "div" | "article" }) {
  return (
    <Tag className={cn("rounded-2xl border border-border bg-card p-4 shadow-[0_8px_30px_rgba(0,0,0,0.25)] backdrop-blur-sm", className)}>
      {(title || actions) && (
        <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-base font-semibold text-foreground">{title}</h2>}
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </Tag>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function KV({ label, children, className }: { label: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-0.5", className)}>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm text-foreground break-words">{children ?? "חסר"}</dd>
    </div>
  );
}

// ── Badges ───────────────────────────────────────────────────────────────────

export function Badge({ children, className, title }: { children: ReactNode; className?: string; title?: string }) {
  return (
    <span title={title} className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-tight whitespace-nowrap", className)}>
      {children}
    </span>
  );
}

export function DemoBadge({ show = true }: { show?: boolean }) {
  if (!show) return null;
  return (
    <Badge className="border-yellow-400/60 bg-yellow-400/20 text-yellow-200 font-bold tracking-wider" title="רשומת הדגמה — לא נתון אמיתי">
      DEMO
    </Badge>
  );
}

export function StatusBadge({ status, labels }: { status: string; labels: Record<string, string> }) {
  return <Badge className={STATUS_COLORS[status] ?? "border-border bg-muted text-foreground"}>{labels[status] ?? status}</Badge>;
}

export function ModeBadge({ label, mode }: { label: string; mode: string }) {
  const live = mode === "live";
  return (
    <Badge
      className={live ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-200" : "border-yellow-400/40 bg-yellow-400/10 text-yellow-200"}
      title={live ? "ספק אמיתי מחובר" : "ספק בסימולציה — אין נתונים אמיתיים"}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", live ? "bg-emerald-400" : "bg-yellow-300")} aria-hidden />
      {label}: {live ? "live" : mode}
    </Badge>
  );
}

// ── Form controls ────────────────────────────────────────────────────────────

const control = "w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";

export function Field({ label, hint, children, className, required }: { label: ReactNode; hint?: ReactNode; children: (id: string) => ReactNode; className?: string; required?: boolean }) {
  const id = useId();
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <label htmlFor={id} className="text-xs font-medium text-foreground/85">
        {label}{required && <span className="text-destructive"> *</span>}
      </label>
      {children(id)}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(control, props.className)} />;
}
export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(control, "min-h-[80px] leading-relaxed", props.className)} />;
}
export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn(control, "bg-[#0d0e1e]", props.className)} />;
}
export function Checkbox({ label, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }) {
  const id = useId();
  return (
    <label htmlFor={id} className="inline-flex cursor-pointer items-center gap-2 text-sm">
      <input id={id} type="checkbox" {...props} className="h-4 w-4 rounded border-border accent-cyan-400" />
      <span>{label}</span>
    </label>
  );
}

// ── States ───────────────────────────────────────────────────────────────────

export function EmptyState({ title, action, icon }: { title: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border px-4 py-10 text-center">
      <span className="text-muted-foreground">{icon ?? <Inbox size={28} />}</span>
      <p className="max-w-md text-sm text-muted-foreground">{title}</p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

export function Loading({ label = "טוען…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground" role="status">
      <Loader2 className="animate-spin" size={16} /> {label}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-red-100">
      <AlertTriangle size={16} />
      <span className="flex-1">{message}</span>
      {onRetry && <Button size="sm" variant="ghost" onClick={onRetry}>נסה שוב</Button>}
    </div>
  );
}

export function Banner({ kind = "warning", children }: { kind?: "warning" | "danger" | "info"; children: ReactNode }) {
  const styles = {
    danger: "border-red-500/50 bg-red-600/20 text-red-100",
    warning: "border-yellow-400/50 bg-yellow-400/15 text-yellow-100",
    info: "border-cyan-400/40 bg-cyan-400/10 text-cyan-100",
  }[kind];
  return (
    <div role={kind === "danger" ? "alert" : "status"} className={cn("flex items-start gap-2 rounded-xl border px-3 py-2 text-sm", styles)}>
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <div className="flex-1">{children}</div>
    </div>
  );
}

// ── Table ────────────────────────────────────────────────────────────────────

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-x-auto rounded-xl border border-border", className)}>
      <table className="w-full min-w-[640px] border-collapse text-sm">{children}</table>
    </div>
  );
}
export function Th({ children, className }: { children?: ReactNode; className?: string }) {
  return <th scope="col" className={cn("sticky top-0 bg-[#0b0c1a] px-3 py-2 text-start text-[11px] font-semibold uppercase tracking-wide text-muted-foreground", className)}>{children}</th>;
}
export function Td({ children, className, ...rest }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td {...rest} className={cn("border-t border-border/60 px-3 py-2 align-top", className)}>{children}</td>;
}

// ── Modal / confirm ──────────────────────────────────────────────────────────

export function Modal({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const focusables = () => Array.from(node?.querySelectorAll<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])") ?? []).filter((el) => !el.hasAttribute("disabled"));
    focusables()[0]?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); }
      if (e.key === "Tab") {
        const f = focusables();
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      prev?.focus();
    };
  }, [open, onClose]);
  if (!open || typeof document === "undefined") return null;
  return createPortal(
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div
        ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} dir="rtl"
        className={cn("max-h-[90vh] w-full overflow-y-auto rounded-2xl border border-border bg-[#0d0e1e] p-5 shadow-2xl", wide ? "max-w-4xl" : "max-w-lg")}
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 id={titleId} className="text-lg font-semibold">{title}</h2>
          <button type="button" onClick={onClose} aria-label="סגור" className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"><X size={18} /></button>
        </div>
        <div className="space-y-3">{children}</div>
        {footer && <div className="mt-4 flex flex-wrap justify-end gap-2">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export function ConfirmButton({ label, confirmTitle, confirmText, onConfirm, variant = "danger", size, disabled, loading, confirmLabel }: {
  label: ReactNode; confirmTitle: string; confirmText: ReactNode; onConfirm: () => Promise<void> | void;
  variant?: Variant; size?: "sm" | "md"; disabled?: boolean; loading?: boolean; confirmLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Button variant={variant} size={size} onClick={() => setOpen(true)} disabled={disabled} loading={loading}>{label}</Button>
      <Modal
        open={open} onClose={() => setOpen(false)} title={confirmTitle}
        footer={<>
          <Button variant="ghost" onClick={() => setOpen(false)}>ביטול</Button>
          <Button variant={variant} loading={busy} onClick={async () => { setBusy(true); try { await onConfirm(); setOpen(false); } finally { setBusy(false); } }}>
            {confirmLabel ?? "אישור"}
          </Button>
        </>}
      >
        <p className="text-sm text-foreground/85">{confirmText}</p>
      </Modal>
    </>
  );
}

export function Tabs<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; count?: number }[] }) {
  return (
    <div role="tablist" className="flex flex-wrap gap-1 rounded-xl border border-border bg-muted/40 p-1">
      {options.map((o) => (
        <button
          key={o.value} role="tab" type="button" aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn("rounded-lg px-3 py-1.5 text-xs font-medium transition-colors", value === o.value ? "bg-primary/20 text-primary" : "text-muted-foreground hover:text-foreground")}
        >
          {o.label}{typeof o.count === "number" && <span className="ms-1 text-[10px] opacity-70">({o.count})</span>}
        </button>
      ))}
    </div>
  );
}
