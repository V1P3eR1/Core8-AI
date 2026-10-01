"use client";

import { useEffect, useState } from "react";
import { fetchAgents, logoutApi } from "@/lib/api";
import { getAccessToken, clearTokens, attemptTokenRefresh } from "@/lib/auth";
import { motion, AnimatePresence } from "framer-motion";
import AgentSidebar from "@/components/AgentSidebar";
import ChatWindow from "@/components/ChatWindow";
import HistoryView from "@/components/HistoryView";
import SecurityDashboard from "@/components/SecurityDashboard";
import InstagramCalendar from "@/components/InstagramCalendar";
import LoginPage from "@/components/LoginPage";
import ParticleBackground from "@/components/ParticleBackground";

interface Agent {
  id: string;
  name: string;
  description: string;
}

interface AuthUser {
  id: string;
  email: string;
  role: string;
}

// null = unknown, false = not authed, object = authed user
type AuthState = null | false | AuthUser;

export default function Home() {
  const [auth, setAuth] = useState<AuthState>(null);
  const [isSetup, setIsSetup] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [conversationRefreshKey, setConversationRefreshKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [rightPanel, setRightPanel] = useState<"security" | "instagram" | null>(null);

  // On mount: try to restore session via refresh token
  useEffect(() => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const restore = async () => {
      if (getAccessToken()) { return; }
      const ok = await attemptTokenRefresh();
      if (!ok) {
        // Check if this is a fresh install (no users yet)
        try {
          const res = await fetch(`${API_BASE}/api/health`);
          if (res.ok) {
            // Try hitting a protected route — 401 means server up but no session
            const probe = await fetch(`${API_BASE}/api/agents`, {
              headers: { Authorization: "Bearer probe" },
            });
            if (probe.status === 422 || probe.status === 401) {
              // Check setup endpoint by trying to register with empty creds (will 422/403)
              const setupProbe = await fetch(`${API_BASE}/api/auth/setup`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: "", password: "" }),
              });
              // 422 = validation error (endpoint active, no users yet)
              // 403 = setup already done
              setIsSetup(setupProbe.status !== 403);
            }
          }
        } catch { /* backend down */ }
        setAuth(false);
        return;
      }
      // Fetch user info
      try {
        const token = getAccessToken();
        const res = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const user = await res.json();
          setAuth(user);
        } else {
          setAuth(false);
        }
      } catch {
        setAuth(false);
      }
    };
    restore();
  }, []);

  const handleLoginSuccess = (user: AuthUser) => {
    setAuth(user);
    setIsSetup(false);
  };

  const handleLogout = async () => {
    await logoutApi();
    clearTokens();
    setAuth(false);
    setAgents([]);
    setSelectedAgentId(null);
  };

  useEffect(() => {
    if (!auth) return;
    fetchAgents()
      .then((data) => {
        setAgents(data);
        if (data.length > 0) setSelectedAgentId(data[0].id);
      })
      .catch((e) => setError(e.message));
  }, [auth]);

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? null;

  const handleSelectAgent = (id: string) => {
    setSelectedAgentId(id);
    setSelectedConversationId(null); // always open new chat when switching agents
  };

  const handleNewChat = () => {
    setSelectedConversationId(null);
  };

  const handleConversationEnded = () => {
    // Refresh the conversation list so the just-finished session appears
    setConversationRefreshKey((k) => k + 1);
  };

  // Auth loading
  if (auth === null) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: "#05060f" }}>
        <ParticleBackground />
        <div className="text-center font-mono relative z-10">
          <motion.p
            animate={{ rotate: 360 }}
            transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
            className="text-5xl mb-4 inline-block"
          >◈</motion.p>
          <p className="text-xs gradient-text tracking-widest">INITIALIZING...</p>
        </div>
      </div>
    );
  }

  // Not authenticated
  if (auth === false) {
    return (
      <>
        <ParticleBackground />
        <div className="relative z-10">
          <LoginPage isSetup={isSetup} onSuccess={handleLoginSuccess} />
        </div>
      </>
    );
  }

  const user = auth as AuthUser;

  return (
    <div className="flex h-screen overflow-hidden relative">
      <ParticleBackground />

      <AgentSidebar
        agents={agents}
        selectedAgentId={selectedAgentId}
        selectedConversationId={selectedConversationId}
        conversationRefreshKey={conversationRefreshKey}
        onSelectAgent={handleSelectAgent}
        onSelectConversation={setSelectedConversationId}
        onNewChat={handleNewChat}
        onAgentCreated={(agent) => {
          setAgents((prev) => [...prev, agent]);
          setSelectedAgentId(agent.id);
          setSelectedConversationId(null);
        }}
      />

      <main className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Top bar */}
        <div className="flex items-center justify-between px-5 py-2.5 border-b border-[#00d4ff]/10 bg-[#080914]/80 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[#00d4ff]/50">{user.email}</span>
            {user.role === "admin" && (
              <span className="font-mono text-[10px] px-1.5 py-0.5 bg-[#00d4ff]/10 text-[#00d4ff] rounded border border-[#00d4ff]/20">
                ADMIN
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <motion.button
              whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
              onClick={() => setRightPanel((p) => p === "instagram" ? null : "instagram")}
              className={`font-mono text-xs px-3 py-1.5 rounded-lg border transition-all ${
                rightPanel === "instagram"
                  ? "bg-[#00d4ff]/15 text-[#67e8f9] border-[#00d4ff]/40 shadow-[0_0_12px_rgba(0,212,255,0.3)]"
                  : "border-[#00d4ff]/15 text-muted-foreground hover:text-[#00d4ff] hover:border-[#00d4ff]/30"
              }`}
            >
              ▣ FEED
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
              onClick={() => setRightPanel((p) => p === "security" ? null : "security")}
              className={`font-mono text-xs px-3 py-1.5 rounded-lg border transition-all ${
                rightPanel === "security"
                  ? "bg-[#7c3aed]/20 text-[#c4b5fd] border-[#7c3aed]/40 shadow-[0_0_12px_rgba(124,58,237,0.3)]"
                  : "border-[#00d4ff]/15 text-muted-foreground hover:text-[#00d4ff] hover:border-[#00d4ff]/30"
              }`}
            >
              ⊕ SHIELD
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
              onClick={handleLogout}
              className="font-mono text-xs px-3 py-1.5 rounded-lg border border-[#00d4ff]/10 text-muted-foreground hover:text-[#ff4757] hover:border-[#ff4757]/30 transition-all"
            >
              SIGN OUT
            </motion.button>
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 flex flex-col overflow-hidden">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
                className="m-4 p-3 bg-[#ff4757]/10 border border-[#ff4757]/30 rounded-xl font-mono text-sm text-[#ff4757]"
              >
                {error} — make sure the backend is running at localhost:8000
              </motion.div>
            )}

            <AnimatePresence mode="wait">
              {!selectedAgent ? (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="flex-1 flex items-center justify-center"
                >
                  <div className="text-center">
                    <motion.p
                      className="text-6xl mb-6 inline-block"
                      animate={{ rotate: [0, 5, -5, 0], scale: [1, 1.05, 1] }}
                      transition={{ duration: 4, repeat: Infinity }}
                    >◈</motion.p>
                    <p className="font-mono text-sm gradient-text tracking-wider">Select an agent to begin</p>
                  </div>
                </motion.div>
              ) : selectedConversationId ? (
                <motion.div
                  key={`hist-${selectedConversationId}`}
                  initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.2 }}
                  className="flex-1 p-4 overflow-hidden"
                >
                  <HistoryView conversationId={selectedConversationId} agentName={selectedAgent.name} />
                </motion.div>
              ) : (
                <motion.div
                  key={`chat-${selectedAgent.id}`}
                  initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.2 }}
                  className="flex-1 p-4 overflow-hidden"
                >
                  <ChatWindow
                    agentId={selectedAgent.id}
                    agentName={selectedAgent.name}
                    onSessionEnd={handleConversationEnded}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Right panel — SHIELD or FEED, one at a time */}
          <AnimatePresence>
            {rightPanel && (
              <motion.div
                key={rightPanel}
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 288, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={{ duration: 0.25 }}
                className={`border-l overflow-hidden flex-shrink-0 ${
                  rightPanel === "security"
                    ? "border-[#7c3aed]/20"
                    : "border-[#00d4ff]/20"
                }`}
              >
                <div className="w-72 p-4 h-full">
                  {rightPanel === "security" ? <SecurityDashboard /> : <InstagramCalendar />}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
