"use client";

import { motion, AnimatePresence } from "framer-motion";
import CreateAgentDialog from "@/components/CreateAgentDialog";
import ConversationList from "@/components/ConversationList";

interface Agent { id: string; name: string; description: string; }

interface Props {
  agents: Agent[];
  selectedAgentId: string | null;
  selectedConversationId: string | null;
  conversationRefreshKey: number;
  onSelectAgent: (id: string) => void;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onAgentCreated: (agent: Agent) => void;
}

const AGENT_COLORS: Record<string, string> = {
  general:  "#00d4ff",
  leads:    "#00ff88",
  calendar: "#7c3aed",
  design:   "#ff6b9d",
};

function agentColor(id: string) {
  return AGENT_COLORS[id] ?? "#ffa742";
}

export default function AgentSidebar({
  agents, selectedAgentId, selectedConversationId,
  conversationRefreshKey, onSelectAgent, onSelectConversation, onNewChat, onAgentCreated,
}: Props) {
  return (
    <aside className="w-64 flex flex-col border-r border-[#00d4ff]/10 bg-[#080914]/95 backdrop-blur-xl relative z-10">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-[#00d4ff]/10">
        <motion.div
          className="flex items-center gap-3"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
        >
          <motion.span
            className="text-2xl select-none"
            animate={{ rotate: [0, 360] }}
            transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          >◈</motion.span>
          <div>
            <p className="font-mono font-bold text-sm tracking-[0.25em] gradient-text">CORE8-AI</p>
            <p className="font-mono text-[10px] text-muted-foreground/50 tracking-widest mt-0.5">AGENT CONTROL</p>
          </div>
        </motion.div>
      </div>

      {/* Agents list */}
      <div className="flex-1 overflow-y-auto py-2">
        <p className="font-mono text-[10px] text-muted-foreground/40 px-5 pt-3 pb-2 uppercase tracking-[0.2em]">
          Agents
        </p>

        {agents.map((agent, i) => {
          const color = agentColor(agent.id);
          const isSelected = selectedAgentId === agent.id && selectedConversationId === null;
          return (
            <motion.div
              key={agent.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.07 }}
            >
              <button
                onClick={() => onSelectAgent(agent.id)}
                className={`w-full text-left px-5 py-3 transition-all group relative overflow-hidden ${
                  isSelected ? "bg-white/5" : "hover:bg-white/[0.03]"
                }`}
              >
                {isSelected && (
                  <motion.div
                    layoutId="agent-indicator"
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-8 rounded-r"
                    style={{ background: color, boxShadow: `0 0 8px ${color}` }}
                  />
                )}
                <div className="flex items-center gap-3">
                  <div
                    className="w-2 h-2 rounded-full flex-shrink-0 transition-all"
                    style={{ background: color, boxShadow: isSelected ? `0 0 8px ${color}` : "none" }}
                  />
                  <div className="min-w-0">
                    <p className={`font-mono text-sm font-medium truncate transition-colors ${
                      isSelected ? "text-white" : "text-foreground/70 group-hover:text-foreground"
                    }`}>{agent.name}</p>
                    <p className="font-mono text-[11px] text-muted-foreground/40 truncate mt-0.5">
                      {agent.description}
                    </p>
                  </div>
                </div>
              </button>

              <AnimatePresence>
                {selectedAgentId === agent.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="pl-4 border-l border-[#00d4ff]/10 ml-5">
                      <ConversationList
                        agentId={agent.id}
                        selectedConversationId={selectedConversationId}
                        onSelect={onSelectConversation}
                        onNewChat={onNewChat}
                        refreshKey={conversationRefreshKey}
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </div>

      {/* New agent */}
      <div className="border-t border-[#00d4ff]/10 p-4">
        <CreateAgentDialog onCreated={(agent) => { onAgentCreated(agent); onSelectAgent(agent.id); }} />
      </div>

      <div className="px-5 py-3 border-t border-[#00d4ff]/10">
        <p className="font-mono text-[10px] text-muted-foreground/30 tracking-widest">
          PRECISION · AUTOMATION · GROWTH
        </p>
      </div>
    </aside>
  );
}
