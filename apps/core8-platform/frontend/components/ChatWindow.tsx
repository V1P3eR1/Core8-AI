"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { createWebSocket } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import ApprovalModal from "@/components/ApprovalModal";
import VoiceInput, { speak } from "@/components/VoiceInput";
import { Send, Zap, AlertCircle } from "lucide-react";

const BACKOFF_DELAYS = [2000, 4000, 8000];

interface Message {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

interface ApprovalRequest {
  requestId: string;
  toolName: string;
  toolInput: Record<string, unknown>;
  risk: "LOW" | "HIGH";
}

interface Props {
  agentId: string;
  agentName: string;
  onSessionEnd?: () => void;
}

export default function ChatWindow({ agentId, agentName, onSessionEnd }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<"idle" | "thinking" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [reconnectCountdown, setReconnectCountdown] = useState<number | null>(null);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);
  const [ttsEnabled, setTtsEnabled] = useState(false);

  const attemptRef = useRef(0);
  const wsRef = useRef<WebSocket | null>(null);
  const activeRef = useRef(true);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const messagesRef = useRef<Message[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { messagesRef.current = messages; }, [messages]);

  const clearTimers = () => {
    if (retryTimerRef.current) { clearTimeout(retryTimerRef.current); retryTimerRef.current = null; }
    if (countdownIntervalRef.current) { clearInterval(countdownIntervalRef.current); countdownIntervalRef.current = null; }
  };

  const connect = useCallback(() => {
    if (!activeRef.current) return;
    const ws = createWebSocket(agentId);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!activeRef.current) return;
      attemptRef.current = 0;
      setConnected(true);
      setReconnectCountdown(null);
      setStatus("idle");
      setErrorMsg(null);
      clearTimers();
    };

    ws.onclose = (e) => {
      if (!activeRef.current) return;
      setConnected(false);
      if (messagesRef.current.length > 0) onSessionEnd?.();
      if (e.code === 4001) {
        setStatus("error");
        setErrorMsg("Authentication failed — check your bearer token.");
        return;
      }
      scheduleReconnect();
    };

    ws.onerror = () => {
      if (!activeRef.current) return;
      setErrorMsg("Connection error — retrying...");
    };

    ws.onmessage = (e) => {
      if (!activeRef.current) return;
      const event = JSON.parse(e.data);

      if (event.type === "text_delta") {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.streaming) {
            return [...prev.slice(0, -1), { ...last, content: last.content + event.text }];
          }
          return [...prev, { role: "assistant", content: event.text, streaming: true }];
        });
      } else if (event.type === "done") {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.streaming) {
            const finished = { ...last, streaming: false };
            if (ttsEnabled && finished.role === "assistant") speak(finished.content);
            return [...prev.slice(0, -1), finished];
          }
          return prev;
        });
        setStatus("idle");
      } else if (event.type === "tool_call") {
        setStatus("thinking");
      } else if (event.type === "tool_approval_request") {
        setPendingApproval({
          requestId: event.request_id,
          toolName: event.tool_name,
          toolInput: event.tool_input ?? {},
          risk: event.risk ?? "HIGH",
        });
      } else if (event.type === "tool_blocked") {
        setMessages((prev) => [...prev, { role: "assistant", content: `⊘ Tool "${event.name}" is blocked by security policy.` }]);
      } else if (event.type === "tool_denied") {
        setMessages((prev) => [...prev, { role: "assistant", content: `✕ Tool "${event.name}" was denied.` }]);
        setPendingApproval(null);
      } else if (event.type === "error") {
        setStatus("error");
        setErrorMsg(event.message ?? "Unknown agent error");
      }
    };
  }, [agentId, onSessionEnd, ttsEnabled]);

  const scheduleReconnect = useCallback(() => {
    if (!activeRef.current) return;
    const attempt = attemptRef.current;
    if (attempt >= BACKOFF_DELAYS.length) {
      setStatus("error");
      setErrorMsg("Could not reconnect. Check the backend and click Reconnect.");
      setReconnectCountdown(null);
      return;
    }
    const delay = BACKOFF_DELAYS[attempt];
    const delaySecs = Math.ceil(delay / 1000);
    attemptRef.current = attempt + 1;
    setReconnectCountdown(delaySecs);
    let remaining = delaySecs;
    countdownIntervalRef.current = setInterval(() => {
      remaining -= 1;
      if (remaining > 0) setReconnectCountdown(remaining);
      else { clearInterval(countdownIntervalRef.current!); countdownIntervalRef.current = null; }
    }, 1000);
    retryTimerRef.current = setTimeout(() => { if (activeRef.current) connect(); }, delay);
  }, [connect]);

  const manualReconnect = () => {
    clearTimers(); attemptRef.current = 0;
    setReconnectCountdown(null); setStatus("idle"); setErrorMsg(null);
    connect();
  };

  useEffect(() => {
    activeRef.current = true; attemptRef.current = 0;
    setConnected(false); setStatus("idle"); setErrorMsg(null); setReconnectCountdown(null);
    connect();
    return () => { activeRef.current = false; clearTimers(); wsRef.current?.close(); };
  }, [agentId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    wsRef.current.send(JSON.stringify({ message: msg }));
    setInput("");
    setStatus("thinking");
    setErrorMsg(null);
  };

  const sendApproval = (requestId: string, approved: boolean) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "tool_approval_response", request_id: requestId, approved }));
    }
    setPendingApproval(null);
  };

  const connDot = connected
    ? "bg-[#00ff88] shadow-[0_0_8px_#00ff88]"
    : reconnectCountdown !== null
    ? "bg-yellow-400 shadow-[0_0_8px_rgba(250,204,21,0.8)] animate-pulse"
    : "bg-[#ff4757] shadow-[0_0_8px_#ff4757]";

  return (
    <>
      {pendingApproval && (
        <ApprovalModal
          requestId={pendingApproval.requestId}
          toolName={pendingApproval.toolName}
          toolInput={pendingApproval.toolInput}
          risk={pendingApproval.risk}
          onApprove={(id) => sendApproval(id, true)}
          onDeny={(id) => sendApproval(id, false)}
        />
      )}

      <div className="flex flex-col h-full glass rounded-2xl overflow-hidden glow-blue">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#00d4ff]/10 bg-[#00d4ff]/5">
          <div className="flex items-center gap-3">
            <div className={`w-2.5 h-2.5 rounded-full transition-all ${connDot}`} />
            <span className="font-mono text-sm font-bold tracking-wider gradient-text">{agentName}</span>
          </div>
          <div className="flex items-center gap-2">
            {status === "thinking" && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#7c3aed]/20 border border-[#7c3aed]/30">
                <Zap size={12} className="text-[#7c3aed] animate-pulse" />
                <span className="font-mono text-xs text-[#c4b5fd]">THINKING</span>
              </div>
            )}
            {reconnectCountdown !== null && (
              <span className="font-mono text-xs text-yellow-400 bg-yellow-400/10 border border-yellow-400/30 px-2.5 py-1 rounded-lg">
                RETRY {attemptRef.current}/{BACKOFF_DELAYS.length} · {reconnectCountdown}s
              </span>
            )}
            {status === "error" && reconnectCountdown === null && (
              <span className="font-mono text-xs text-[#ff4757] bg-[#ff4757]/10 border border-[#ff4757]/30 px-2.5 py-1 rounded-lg">
                DISCONNECTED
              </span>
            )}
            <span className="font-mono text-xs text-muted-foreground/50">CORE8 · {agentId.toUpperCase()}</span>
          </div>
        </div>

        {/* Error banner */}
        <AnimatePresence>
          {errorMsg && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="px-5 py-2 bg-[#ff4757]/10 border-b border-[#ff4757]/20 font-mono text-xs text-[#ff4757] flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <AlertCircle size={12} />
                  <span>{errorMsg}</span>
                </div>
                {status === "error" && reconnectCountdown === null && (
                  <motion.button
                    whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                    onClick={manualReconnect}
                    className="shrink-0 px-3 py-1 bg-[#ff4757] text-white rounded-lg font-mono text-xs hover:bg-[#ff4757]/80"
                  >
                    RECONNECT ↺
                  </motion.button>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Messages */}
        <ScrollArea className="flex-1 px-5 py-4">
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center mt-16 select-none"
            >
              <motion.p
                animate={{ rotate: [0, 5, -5, 0] }}
                transition={{ duration: 4, repeat: Infinity }}
                className="text-4xl mb-3 animate-float inline-block"
              >◈</motion.p>
              <p className="font-mono text-sm text-muted-foreground/60">Agent ready. Send a message or tap the mic.</p>
            </motion.div>
          )}

          <div className="space-y-4">
            <AnimatePresence initial={false}>
              {messages.map((msg, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: msg.role === "user" ? 30 : -30, scale: 0.9 }}
                  animate={{ opacity: 1, x: 0, scale: 1 }}
                  transition={{ type: "spring", stiffness: 300, damping: 25 }}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm font-mono whitespace-pre-wrap leading-relaxed ${
                    msg.role === "user"
                      ? "bg-gradient-to-br from-[#00d4ff] to-[#0099bb] text-[#05060f] shadow-[0_4px_20px_rgba(0,212,255,0.3)]"
                      : "glass border border-[#00d4ff]/10 text-foreground shadow-[0_4px_20px_rgba(0,0,0,0.3)]"
                  }`}>
                    {msg.content}
                    {msg.streaming && (
                      <motion.span
                        animate={{ opacity: [1, 0] }}
                        transition={{ duration: 0.6, repeat: Infinity }}
                        className="inline-block w-2 h-4 bg-current ml-1 align-text-bottom rounded-sm"
                      />
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
          <div ref={bottomRef} />
        </ScrollArea>

        {/* Input */}
        <div className="border-t border-[#00d4ff]/10 px-4 py-3 bg-[#00d4ff]/3 flex items-center gap-2">
          <VoiceInput
            onTranscript={(t) => send(t)}
            disabled={!connected}
            ttsEnabled={ttsEnabled}
            onToggleTts={() => setTtsEnabled((v) => !v)}
          />
          <input
            className="flex-1 bg-[#00d4ff]/5 border border-[#00d4ff]/15 rounded-xl px-4 py-2.5 text-sm font-mono outline-none focus:ring-1 focus:ring-[#00d4ff]/50 focus:border-[#00d4ff]/40 placeholder:text-muted-foreground/40 transition-all"
            placeholder={
              connected
                ? "Send a message..."
                : reconnectCountdown !== null
                ? `Reconnecting in ${reconnectCountdown}s...`
                : "Disconnected"
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
            disabled={!connected}
          />
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.92 }}
            onClick={() => send()}
            disabled={!connected || !input.trim()}
            className="p-2.5 bg-gradient-to-br from-[#00d4ff] to-[#0099bb] text-[#05060f] rounded-xl font-medium disabled:opacity-30 transition-all shadow-[0_0_16px_rgba(0,212,255,0.3)] hover:shadow-[0_0_24px_rgba(0,212,255,0.5)]"
          >
            <Send size={16} />
          </motion.button>
        </div>
      </div>
    </>
  );
}
