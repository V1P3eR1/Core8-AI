"use client";

import { useEffect, useState } from "react";
import { fetchSecurityStatus, setKillSwitch, type SecurityStatus } from "@/lib/api";

export default function SecurityDashboard() {
  const [status, setStatus] = useState<SecurityStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    fetchSecurityStatus()
      .then(setStatus)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const toggleKillSwitch = async () => {
    if (!status) return;
    setToggling(true);
    try {
      const res = await setKillSwitch(!status.kill_switch);
      setStatus((s) => s ? { ...s, kill_switch: res.kill_switch } : s);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setToggling(false);
    }
  };

  const modeColor = (mode: string) => {
    if (mode === "manual") return "text-red-400";
    if (mode === "smart") return "text-yellow-400";
    return "text-green-400";
  };

  return (
    <div className="flex flex-col h-full border border-border rounded-xl overflow-hidden bg-card">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
        <span className="font-mono text-sm font-bold tracking-wider">SECURITY SHIELD</span>
        <button
          onClick={load}
          className="font-mono text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          REFRESH ↺
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {loading && (
          <p className="font-mono text-xs text-muted-foreground animate-pulse text-center mt-8">
            Loading security status...
          </p>
        )}
        {error && (
          <p className="font-mono text-xs text-destructive text-center mt-8">{error}</p>
        )}

        {status && (
          <>
            {/* Kill Switch */}
            <div className="border border-border rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest mb-0.5">Kill Switch</p>
                  <p className={`font-mono text-sm font-bold ${status.kill_switch ? "text-red-500" : "text-green-500"}`}>
                    {status.kill_switch ? "● ACTIVE — agents paused" : "● INACTIVE — agents running"}
                  </p>
                </div>
                <button
                  onClick={toggleKillSwitch}
                  disabled={toggling}
                  className={`px-4 py-1.5 rounded-lg font-mono text-xs font-medium transition-colors disabled:opacity-50
                    ${status.kill_switch
                      ? "bg-green-600 text-white hover:bg-green-500"
                      : "bg-red-600 text-white hover:bg-red-500"
                    }`}
                >
                  {toggling ? "..." : status.kill_switch ? "RESUME" : "KILL"}
                </button>
              </div>
            </div>

            {/* Approval Mode */}
            <div className="border border-border rounded-lg p-4">
              <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest mb-1">Approval Mode</p>
              <p className={`font-mono text-sm font-bold uppercase ${modeColor(status.approval_mode)}`}>
                {status.approval_mode}
              </p>
              <p className="font-mono text-xs text-muted-foreground mt-1">
                {status.approval_mode === "off" && "All tools run without approval"}
                {status.approval_mode === "smart" && "High-risk tools require approval"}
                {status.approval_mode === "manual" && "Every tool requires approval"}
              </p>
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-2 gap-3">
              <div className="border border-border rounded-lg p-3">
                <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest mb-1">Agents</p>
                <p className="font-mono text-lg font-bold">{status.agent_count}</p>
              </div>
              <div className="border border-border rounded-lg p-3">
                <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest mb-1">Token Rotation</p>
                <p className={`font-mono text-sm font-bold ${status.bearer_rotation_active ? "text-yellow-400" : "text-muted-foreground"}`}>
                  {status.bearer_rotation_active ? "ACTIVE" : "IDLE"}
                </p>
              </div>
            </div>

            {/* Blocklist */}
            <div className="border border-border rounded-lg p-4">
              <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest mb-2">Tool Blocklist</p>
              {status.tool_blocklist.length === 0 ? (
                <p className="font-mono text-xs text-muted-foreground">No tools blocked</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {status.tool_blocklist.map((t) => (
                    <span key={t} className="font-mono text-xs px-2 py-0.5 bg-destructive/10 text-destructive border border-destructive/30 rounded">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
