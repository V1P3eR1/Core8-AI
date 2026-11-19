"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { ApiError } from "@/lib/social-api";

type Kind = "success" | "error" | "info";
interface Toast { id: number; kind: Kind; text: string }

interface ToastApi {
  push: (text: string, kind?: Kind) => void;
  success: (text: string) => void;
  error: (err: unknown, fallback?: string) => void;
}

const ToastCtx = createContext<ToastApi | null>(null);

export function errorMessage(err: unknown, fallback = "אירעה שגיאה"): string {
  if (err instanceof ApiError) return err.code ? `${err.message} (${err.code})` : err.message;
  if (err instanceof Error) return err.message || fallback;
  return fallback;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((text: string, kind: Kind = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 7000 : 4000);
  }, []);

  const value = useMemo<ToastApi>(() => ({
    push,
    success: (text) => push(text, "success"),
    error: (err, fallback) => push(errorMessage(err, fallback), "error"),
  }), [push]);

  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 left-4 z-[100] flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite" role="status">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }}
              className={`pointer-events-auto flex items-start gap-2 rounded-xl border px-3 py-2 text-sm shadow-lg backdrop-blur ${
                t.kind === "error" ? "border-red-400/40 bg-red-950/90 text-red-100"
                : t.kind === "success" ? "border-emerald-400/40 bg-emerald-950/90 text-emerald-100"
                : "border-cyan-400/30 bg-[#0d0e1e]/95 text-foreground"
              }`}
            >
              <span className="flex-1 leading-snug">{t.text}</span>
              <button
                type="button" aria-label="סגור הודעה"
                onClick={() => setToasts((all) => all.filter((x) => x.id !== t.id))}
                className="rounded p-0.5 opacity-70 hover:opacity-100"
              ><X size={14} /></button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
