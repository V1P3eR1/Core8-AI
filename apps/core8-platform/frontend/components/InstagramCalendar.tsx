"use client";

import { useEffect, useState } from "react";
import {
  fetchInstagramAccount, fetchScheduledPosts, fetchInstagramInsights,
  type IGAccount, type IGScheduledPost, type IGInsights,
} from "@/lib/api";

const STATUSES = ["pending", "publishing", "published", "failed", "cancelled"] as const;

export default function InstagramCalendar() {
  const [account, setAccount] = useState<IGAccount | null>(null);
  const [connected, setConnected] = useState(false);
  const [insights, setInsights] = useState<IGInsights | null>(null);
  const [posts, setPosts] = useState<IGScheduledPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [acct, scheduled, ins] = await Promise.all([
        fetchInstagramAccount(),
        fetchScheduledPosts(),
        fetchInstagramInsights(7).catch((e) => (
          { error: e instanceof Error ? e.message : "unavailable" } as IGInsights
        )),
      ]);
      setAccount(acct.account);
      setConnected(acct.connected);
      setPosts(scheduled);
      setInsights(ins);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const byStatus = posts.reduce<Record<string, IGScheduledPost[]>>((m, p) => {
    (m[p.status] ||= []).push(p);
    return m;
  }, {});

  return (
    <div className="flex flex-col h-full border border-border rounded-xl overflow-hidden bg-card">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
        <span className="font-mono text-sm font-bold tracking-wider">INSTAGRAM</span>
        <button
          onClick={load}
          className="font-mono text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          REFRESH ↺
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {loading && (
          <p className="font-mono text-xs text-muted-foreground animate-pulse text-center mt-8">
            Loading...
          </p>
        )}
        {error && (
          <p className="font-mono text-xs text-destructive text-center mt-8">{error}</p>
        )}

        {!loading && !error && (
          <>
            {/* Account */}
            <div className="border border-border rounded-lg p-4">
              <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest mb-1">Account</p>
              {connected && account ? (
                <>
                  <p className="font-mono text-sm font-bold text-[#00d4ff]">
                    @{account.username ?? "(unknown)"}
                  </p>
                  {insights?.account && (
                    <div className="flex gap-4 mt-2 text-xs font-mono">
                      <div>
                        <span className="text-muted-foreground">followers </span>
                        <span className="text-foreground font-bold">
                          {insights.account.followers_count?.toLocaleString() ?? "—"}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">posts </span>
                        <span className="text-foreground font-bold">
                          {insights.account.media_count ?? "—"}
                        </span>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="font-mono text-xs text-muted-foreground">
                  Not connected. Ask the{" "}
                  <span className="text-[#00d4ff]">instagram</span> agent to connect.
                </p>
              )}
            </div>

            {/* Insights */}
            {insights && (
              <div className="border border-border rounded-lg p-4">
                <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest mb-2">
                  Insights — last {insights.insights?.period_days ?? 7}d
                </p>
                {insights.error ? (
                  <p className="font-mono text-xs text-muted-foreground">
                    Unavailable: {insights.error}
                  </p>
                ) : insights.insights ? (
                  <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                    <Stat label="Reach" v={insights.insights.reach} />
                    <Stat label="Engaged" v={insights.insights.accounts_engaged} />
                    <Stat label="Interactions" v={insights.insights.total_interactions} />
                    <Stat label="Profile views" v={insights.insights.profile_views} />
                  </div>
                ) : null}
              </div>
            )}

            {/* Publishing summary */}
            {insights?.publishing && (
              <div className="border border-border rounded-lg p-4">
                <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest mb-2">Queue</p>
                <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                  <Stat label="Pending" v={insights.publishing.queued_pending} />
                  <Stat label="Published" v={insights.publishing.total_published} />
                  <Stat label="Last 24h" v={insights.publishing.published_last_24h} />
                </div>
              </div>
            )}

            {/* Scheduled posts */}
            <div className="border border-border rounded-lg p-4 space-y-3">
              <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest">
                Scheduled posts ({posts.length})
              </p>
              {posts.length === 0 ? (
                <p className="font-mono text-xs text-muted-foreground">No posts queued.</p>
              ) : (
                STATUSES.map((status) => {
                  const list = byStatus[status] || [];
                  if (list.length === 0) return null;
                  return (
                    <div key={status} className="space-y-1.5">
                      <p className="font-mono text-[10px] uppercase tracking-widest text-[#7c3aed]">
                        {status} · {list.length}
                      </p>
                      {list.slice(0, 8).map((p) => (
                        <PostRow key={p.id} p={p} />
                      ))}
                      {list.length > 8 && (
                        <p className="font-mono text-[10px] text-muted-foreground pl-2">
                          + {list.length - 8} more
                        </p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Stat({ label, v }: { label: string; v: number }) {
  return (
    <div>
      <p className="text-muted-foreground">{label}</p>
      <p className="text-foreground font-bold text-sm">{v.toLocaleString()}</p>
    </div>
  );
}

function PostRow({ p }: { p: IGScheduledPost }) {
  const when = p.scheduled_for.replace("T", " ").slice(0, 16);
  const statusColor: Record<string, string> = {
    pending: "text-yellow-400",
    publishing: "text-blue-400",
    published: "text-green-400",
    failed: "text-red-400",
    cancelled: "text-muted-foreground",
  };
  const color = statusColor[p.status] ?? "text-muted-foreground";
  const summary =
    p.post_type === "carousel" && p.media_urls
      ? `carousel · ${p.media_urls.length} items${p.caption ? " · " + p.caption : ""}`
      : (p.caption ?? p.media_url);
  return (
    <div className="flex items-start gap-2 text-xs font-mono pl-2 border-l border-[#00d4ff]/15">
      <span className="text-muted-foreground shrink-0">{when}</span>
      <span className="uppercase text-[#00d4ff]/70 shrink-0">{p.post_type}</span>
      <span className={`${color} shrink-0`}>●</span>
      <span className="text-foreground/80 truncate">{summary}</span>
    </div>
  );
}
