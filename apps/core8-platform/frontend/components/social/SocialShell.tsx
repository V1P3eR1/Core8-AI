"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity, BarChart3, CalendarDays, CheckSquare, FileImage, Camera, Lightbulb, Loader2,
  LogOut, Menu, PenSquare, Search, Settings2, Users, LayoutDashboard, X, ArrowLeft,
} from "lucide-react";
import LoginPage from "@/components/LoginPage";
import { API_BASE, api, type Overview } from "@/lib/social-api";
import { attemptTokenRefresh, clearTokens, getAccessToken } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { ToastProvider } from "./toast";
import { Banner, ModeBadge } from "./ui";

interface AuthUser { id: string; email: string; role: string }

// ── Status context (overview polled every 60s; pages can refresh after actions) ──

interface StatusCtx { overview: Overview | null; refresh: () => Promise<void>; user: AuthUser }
const Ctx = createContext<StatusCtx | null>(null);
export function useSocialStatus(): StatusCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useSocialStatus outside SocialShell");
  return c;
}

export const NAV: { href: string; label: string; icon: React.ComponentType<{ size?: number; className?: string }> }[] = [
  { href: "/social", label: "סקירה כללית", icon: LayoutDashboard },
  { href: "/social/research", label: "מחקר ומגמות", icon: Search },
  { href: "/social/ideas", label: "רעיונות לתוכן", icon: Lightbulb },
  { href: "/social/content", label: "יצירת תוכן", icon: PenSquare },
  { href: "/social/calendar", label: "לוח פרסומים", icon: CalendarDays },
  { href: "/social/approvals", label: "אישורים", icon: CheckSquare },
  { href: "/social/assets", label: "נכסים וקבצים", icon: FileImage },
  { href: "/social/instagram", label: "אינסטגרם וחיבורים", icon: Camera },
  { href: "/social/leads", label: "פניות ולידים", icon: Users },
  { href: "/social/performance", label: "ביצועים ודוחות", icon: BarChart3 },
  { href: "/social/brand", label: "הגדרות מותג", icon: Settings2 },
  { href: "/social/jobs", label: "אוטומציות ולוגים", icon: Activity },
];

type AuthState = null | false | AuthUser;

export default function SocialShell({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>(null);
  const [isSetup, setIsSetup] = useState(false);

  useEffect(() => {
    const restore = async () => {
      const haveToken = !!getAccessToken() || (await attemptTokenRefresh());
      if (!haveToken) {
        try {
          // 403 = setup already done; anything else (422) = fresh install → setup form
          const probe = await fetch(`${API_BASE}/api/auth/setup`, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "", password: "" }),
          });
          setIsSetup(probe.status !== 403);
        } catch { /* backend down — show login anyway */ }
        setAuth(false);
        return;
      }
      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, { headers: { Authorization: `Bearer ${getAccessToken()}` } });
        setAuth(res.ok ? await res.json() : false);
      } catch { setAuth(false); }
    };
    restore();
  }, []);

  if (auth === null) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        <Loader2 className="animate-spin" size={18} /><span className="ms-2 text-sm">מאמת חיבור…</span>
      </div>
    );
  }
  if (auth === false) {
    return (
      <div dir="ltr" className="relative z-10">
        <LoginPage isSetup={isSetup} onSuccess={(u) => { setAuth(u); setIsSetup(false); }} />
      </div>
    );
  }
  return (
    <ToastProvider>
      <Frame user={auth} onLogout={() => { clearTokens(); setAuth(false); }}>{children}</Frame>
    </ToastProvider>
  );
}

function Frame({ user, onLogout, children }: { user: AuthUser; onLogout: () => void; children: React.ReactNode }) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [drawer, setDrawer] = useState(false);
  const pathname = usePathname();

  const refresh = useCallback(async () => {
    try { setOverview(await api.overview()); } catch { /* header shows unknown */ }
  }, []);
  useEffect(() => {
    let active = true;
    api.overview().then((o) => { if (active) setOverview(o); }).catch(() => {});
    const t = window.setInterval(refresh, 60_000);
    return () => { active = false; window.clearInterval(t); };
  }, [refresh]);

  const nav = (
    <nav aria-label="ניווט ראשי" className="flex flex-col gap-0.5">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = href === "/social" ? pathname === "/social" : pathname.startsWith(href);
        return (
          <Link
            key={href} href={href} aria-current={active ? "page" : undefined} onClick={() => setDrawer(false)}
            className={cn("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
              active ? "bg-primary/15 text-primary font-semibold" : "text-foreground/75 hover:bg-muted hover:text-foreground")}
          >
            <Icon size={16} className="shrink-0" /><span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );

  const workerOffline = overview ? overview.worker.online === false : false;
  const paused = overview?.publishing.emergency_pause === true;

  return (
    <Ctx.Provider value={{ overview, refresh, user }}>
      <div className="flex min-h-screen bg-background text-foreground">
        {/* Desktop sidebar */}
        <aside className="hidden w-60 shrink-0 flex-col border-e border-border bg-sidebar p-3 lg:flex lg:sticky lg:top-0 lg:h-screen">
          <Brand />
          <div className="mt-4 flex-1 overflow-y-auto">{nav}</div>
          <footer className="mt-3 border-t border-border pt-3 text-xs text-muted-foreground">
            <p className="truncate" title={user.email}>{user.email}</p>
            <div className="mt-2 flex items-center justify-between gap-2">
              <Link href="/" className="inline-flex items-center gap-1 hover:text-foreground"><ArrowLeft size={12} /> לפלטפורמה</Link>
              <button type="button" onClick={onLogout} className="inline-flex items-center gap-1 hover:text-destructive"><LogOut size={12} /> התנתק</button>
            </div>
          </footer>
        </aside>

        {/* Mobile drawer */}
        <AnimatePresence>
          {drawer && (
            <motion.div className="fixed inset-0 z-50 flex lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <div className="absolute inset-0 bg-black/70" onClick={() => setDrawer(false)} aria-hidden />
              <motion.div
                initial={{ x: 40 }} animate={{ x: 0 }} exit={{ x: 40 }}
                className="relative ms-auto flex h-full w-72 max-w-[85vw] flex-col border-s border-border bg-[#0b0c1a] p-3"
                role="dialog" aria-label="תפריט ניווט"
              >
                <div className="mb-3 flex items-center justify-between"><Brand /><button type="button" aria-label="סגור תפריט" onClick={() => setDrawer(false)} className="rounded-md p-1 hover:bg-muted"><X size={18} /></button></div>
                <div className="flex-1 overflow-y-auto">{nav}</div>
                <button type="button" onClick={onLogout} className="mt-3 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive"><LogOut size={12} /> התנתק</button>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-40 border-b border-border bg-[#080914]/85 backdrop-blur">
            <div className="flex flex-wrap items-center gap-2 px-4 py-2">
              <button type="button" className="rounded-md p-1.5 hover:bg-muted lg:hidden" aria-label="פתח תפריט" onClick={() => setDrawer(true)}><Menu size={20} /></button>
              <span className="font-semibold lg:hidden">Core8AI Social</span>
              <div className="ms-auto flex flex-wrap items-center gap-1.5" aria-label="מצב ספקים">
                {overview ? (
                  <>
                    <ModeBadge label="Instagram" mode={overview.modes.instagram} />
                    <ModeBadge label="LLM" mode={overview.modes.llm} />
                    <ModeBadge label="מחקר" mode={overview.modes.research} />
                    {overview.publishing.demo_mode && (
                      <span className="rounded-md border border-yellow-400/50 bg-yellow-400/15 px-1.5 py-0.5 text-[11px] font-bold text-yellow-200" title="מצב demo — רשומות הדגמה מוצגות ופרסום אמיתי חסום">מצב DEMO</span>
                    )}
                    <span className={cn("rounded-md border px-1.5 py-0.5 text-[11px]", overview.worker.online ? "border-emerald-400/40 text-emerald-200" : "border-red-400/50 bg-red-500/15 text-red-200")}>
                      worker: {overview.worker.online ? "פעיל" : "לא פעיל"}
                    </span>
                  </>
                ) : <span className="text-xs text-muted-foreground">מצב ספקים לא ידוע</span>}
              </div>
            </div>
            {(workerOffline || paused) && (
              <div className="flex flex-col gap-1 px-4 pb-2">
                {workerOffline && <Banner kind="danger">ה-worker לא פעיל — ג&apos;ובים ופרסומים לא ירוצו. ניתן להריץ tick ידני בעמוד &quot;אוטומציות ולוגים&quot;.</Banner>}
                {paused && <Banner kind="danger">השהיית חירום פעילה — כל הפרסומים מושהים עד לביטול ההשהיה בעמוד הסקירה.</Banner>}
              </div>
            )}
          </header>
          <main className="flex-1 px-4 py-5 sm:px-6">
            <div className="mx-auto w-full max-w-7xl">{children}</div>
          </main>
        </div>
      </div>
    </Ctx.Provider>
  );
}

function Brand() {
  return (
    <Link href="/social" className="flex items-center gap-2 px-2">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/15 text-primary font-black">8</span>
      <span className="leading-tight">
        <span className="block text-sm font-bold">Core8AI Social</span>
        <span className="block text-[10px] text-muted-foreground">ניהול אינסטגרם</span>
      </span>
    </Link>
  );
}
