"use client";

import { useEffect, useState } from "react";
import { fetchMessages, type Message } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";

interface Props {
  conversationId: string;
  agentName: string;
}

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString(undefined, {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function HistoryView({ conversationId, agentName }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchMessages(conversationId)
      .then(setMessages)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [conversationId]);

  return (
    <div className="flex flex-col h-full border border-border rounded-xl overflow-hidden bg-card">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium">{agentName}</span>
        </div>
        <span className="font-mono text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
          HISTORY — READ ONLY
        </span>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 px-4 py-4">
        {loading && (
          <div className="text-center text-muted-foreground font-mono text-sm mt-12 animate-pulse">
            Loading conversation...
          </div>
        )}
        {error && (
          <div className="text-center text-destructive font-mono text-sm mt-12">{error}</div>
        )}
        {!loading && !error && messages.length === 0 && (
          <div className="text-center text-muted-foreground font-mono text-sm mt-12">
            No messages in this conversation.
          </div>
        )}
        <div className="space-y-4">
          {messages
            .filter((m) => m.role === "user" || m.role === "assistant")
            .map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[75%] rounded-lg px-4 py-3 text-sm font-mono whitespace-pre-wrap
                    ${msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted border border-border"
                    }`}
                >
                  {msg.content}
                </div>
                <span className="font-mono text-xs text-muted-foreground/50 px-1">
                  {formatTime(msg.created_at)}
                </span>
              </div>
            ))}
        </div>
      </ScrollArea>

      {/* Footer hint */}
      <div className="border-t border-border px-4 py-3 bg-muted/20">
        <p className="font-mono text-xs text-muted-foreground text-center">
          Select NEW CHAT in the sidebar to start a new conversation
        </p>
      </div>
    </div>
  );
}
