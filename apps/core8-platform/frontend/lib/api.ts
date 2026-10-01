import { apiFetch, getAccessToken } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchAgents() {
  const res = await apiFetch(`${API_BASE}/api/agents`);
  if (!res.ok) throw new Error("Failed to fetch agents");
  return res.json() as Promise<{ id: string; name: string; description: string }[]>;
}

export interface CreateAgentPayload {
  name: string;
  description: string;
  system_prompt: string;
  model: string;
}

export async function createAgent(payload: CreateAgentPayload) {
  const res = await apiFetch(`${API_BASE}/api/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Failed to create agent");
  }
  return res.json() as Promise<{ id: string; name: string }>;
}

export interface Conversation {
  id: string;
  created_at: string;
  message_count: number;
  last_message_at: string;
  preview: string | null;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  created_at: string;
}

export async function fetchConversations(agentId: string): Promise<Conversation[]> {
  const res = await apiFetch(`${API_BASE}/api/agents/${agentId}/conversations`);
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

export async function fetchMessages(conversationId: string): Promise<Message[]> {
  const res = await apiFetch(`${API_BASE}/api/conversations/${conversationId}/messages`);
  if (!res.ok) throw new Error("Failed to fetch messages");
  return res.json();
}

export function createWebSocket(agentId: string): WebSocket {
  const wsBase = API_BASE.replace(/^http/, "ws");
  const token = getAccessToken() || process.env.NEXT_PUBLIC_BEARER_TOKEN || "";
  return new WebSocket(`${wsBase}/ws/${agentId}?token=${encodeURIComponent(token)}`);
}

export interface SecurityStatus {
  kill_switch: boolean;
  approval_mode: string;
  tool_blocklist: string[];
  agent_count: number;
  bearer_rotation_active: boolean;
}

export async function fetchSecurityStatus(): Promise<SecurityStatus> {
  const res = await apiFetch(`${API_BASE}/api/admin/security-status`);
  if (!res.ok) throw new Error("Failed to fetch security status");
  return res.json();
}

export async function setKillSwitch(active: boolean): Promise<{ kill_switch: boolean }> {
  const res = await apiFetch(`${API_BASE}/api/admin/kill-switch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active }),
  });
  if (!res.ok) throw new Error("Failed to update kill switch");
  return res.json();
}

export async function login(email: string, password: string) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Login failed");
  }
  return res.json() as Promise<{
    access_token: string;
    refresh_token: string;
    user: { id: string; email: string; role: string };
  }>;
}

export async function setupFirstUser(email: string, password: string) {
  const res = await fetch(`${API_BASE}/api/auth/setup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Setup failed");
  }
  return res.json() as Promise<{
    access_token: string;
    refresh_token: string;
    user: { id: string; email: string; role: string };
  }>;
}

export async function logoutApi() {
  await apiFetch(`${API_BASE}/api/auth/logout`, { method: "POST" }).catch(() => {});
}

// ── Instagram ───────────────────────────────────────────────────────────────

export interface IGAccount {
  ig_user_id: string;
  fb_page_id: string;
  username: string | null;
  token_expires_at: string | null;
  connected_at: string;
}

export interface IGAccountResponse {
  connected: boolean;
  account: IGAccount | null;
}

export interface IGScheduledPost {
  id: string;
  plan_id: string | null;
  post_type: "image" | "reel" | "carousel";
  media_url: string;
  media_urls: string[] | null;
  caption: string | null;
  scheduled_for: string;
  status: "pending" | "publishing" | "published" | "failed" | "cancelled";
  ig_media_id: string | null;
  attempts: number;
  last_error: string | null;
}

export interface IGInsights {
  account?: { username: string; followers_count: number; media_count: number };
  insights?: {
    period_days: number;
    reach: number;
    accounts_engaged: number;
    total_interactions: number;
    profile_views: number;
  };
  publishing?: { queued_pending: number; total_published: number; published_last_24h: number };
  error?: string;
}

export async function fetchInstagramAccount(): Promise<IGAccountResponse> {
  const res = await apiFetch(`${API_BASE}/api/instagram/account`);
  if (!res.ok) throw new Error("Failed to fetch Instagram account");
  return res.json();
}

export async function fetchScheduledPosts(status?: string): Promise<IGScheduledPost[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  const res = await apiFetch(`${API_BASE}/api/instagram/scheduled-posts${q}`);
  if (!res.ok) throw new Error("Failed to fetch scheduled posts");
  return res.json();
}

export async function fetchInstagramInsights(days = 7): Promise<IGInsights> {
  const res = await apiFetch(`${API_BASE}/api/instagram/insights?days=${days}`);
  if (!res.ok) throw new Error("Failed to fetch insights");
  return res.json();
}
