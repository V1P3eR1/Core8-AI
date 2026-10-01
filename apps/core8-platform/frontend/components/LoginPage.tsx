"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { login, setupFirstUser } from "@/lib/api";
import { setAccessToken, setRefreshToken } from "@/lib/auth";

interface Props {
  isSetup?: boolean;
  onSuccess: (user: { id: string; email: string; role: string }) => void;
}

export default function LoginPage({ isSetup = false, onSuccess }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    setError(null);
    try {
      const fn = isSetup ? setupFirstUser : login;
      const data = await fn(email, password);
      setAccessToken(data.access_token);
      setRefreshToken(data.refresh_token);
      onSuccess(data.user);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, type: "spring", stiffness: 200 }}
        className="w-full max-w-sm"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <motion.p
            className="text-5xl mb-3 inline-block"
            animate={{ rotate: [0, 360] }}
            transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
          >◈</motion.p>
          <p className="font-mono font-bold text-lg tracking-[0.3em] gradient-text">CORE8-AI</p>
          <p className="font-mono text-xs text-muted-foreground/60 mt-1 tracking-widest">
            {isSetup ? "FIRST-TIME SETUP" : "AGENT CONTROL · SIGN IN"}
          </p>
        </div>

        {/* Card */}
        <div className="glass rounded-2xl overflow-hidden glow-blue">
          {isSetup && (
            <div className="px-6 py-3 bg-yellow-500/10 border-b border-yellow-500/30">
              <p className="font-mono text-xs text-yellow-500 text-center">
                No users found — create the first admin account
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="px-6 py-6 space-y-4">
            <div>
              <label className="font-mono text-xs text-muted-foreground uppercase tracking-widest block mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm font-mono outline-none focus:ring-1 focus:ring-primary"
                placeholder="you@company.com"
              />
            </div>
            <div>
              <label className="font-mono text-xs text-muted-foreground uppercase tracking-widest block mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={isSetup ? "new-password" : "current-password"}
                required
                minLength={isSetup ? 8 : 1}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm font-mono outline-none focus:ring-1 focus:ring-primary"
                placeholder={isSetup ? "Minimum 8 characters" : "••••••••"}
              />
            </div>

            {error && (
              <p className="font-mono text-xs text-destructive bg-destructive/10 border border-destructive/30 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <motion.button
              type="submit"
              disabled={loading || !email || !password}
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              className="w-full py-2.5 bg-gradient-to-r from-[#00d4ff] to-[#0099bb] text-[#05060f] rounded-xl font-mono text-sm font-bold disabled:opacity-40 transition-all shadow-[0_0_20px_rgba(0,212,255,0.3)] hover:shadow-[0_0_30px_rgba(0,212,255,0.5)]"
            >
              {loading ? "..." : isSetup ? "CREATE ACCOUNT →" : "SIGN IN →"}
            </motion.button>
          </form>
        </div>

        <p className="font-mono text-xs text-muted-foreground/30 text-center mt-6 tracking-widest">
          PRECISION · AUTOMATION · GROWTH
        </p>
      </motion.div>
    </div>
  );
}
