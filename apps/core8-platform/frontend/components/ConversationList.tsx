"use client";

import { useEffect, useState } from "react";
import { fetchConversations, type Conversation } from "@/lib/api";

interface Props {
  agentId: string;
  selectedConversationId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  refreshKey: number;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function ConversationList({
  agentId,
  selectedConversationId,
  onSelect,
  onNewChat,
  refreshKey,
}: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchConversations(agentId)
      .then(setConversations)
      .catch(() => setConversations([]))
      .finally(() => setLoading(false));
  }, [agentId, refreshKey]);

  return (
    <div className="flex flex-col">
      {/* New Chat button */}
      <button
        onClick={onNewChat}
        className={`w-full text-left px-4 py-2.5 font-mono text-xs flex items-center gap-2 transition-colors
          ${selectedConversationId === null
            ? "bg-muted border-r-2 border-primary text-foreground"
            : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
          }`}
      >
        <span className="text-base leading-none">◈</span> NEW CHAT
      </button>

      {/* History label */}
      {conversations.length > 0 && (
        <p className="font-mono text-xs text-muted-foreground/60 px-4 pt-3 pb-1 uppercase tracking-widest">
          History
        </p>
      )}

      {/* Past conversations */}
      {loading ? (
        <p className="font-mono text-xs text-muted-foreground px-4 py-2 animate-pulse">Loading...</p>
      ) : (
        conversations.map((conv) => (
          <button
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className={`w-full text-left px-4 py-2.5 transition-colors hover:bg-muted/50
              ${selectedConversationId === conv.id ? "bg-muted border-r-2 border-primary" : ""}`}
          >
            <p className="font-mono text-xs truncate text-foreground/80">
              {conv.preview ?? "Empty conversation"}
            </p>
            <p className="font-mono text-xs text-muted-foreground/60 mt-0.5">
              {timeAgo(conv.last_message_at)} · {conv.message_count} msg
            </p>
          </button>
        ))
      )}
    </div>
  );
}
