/**
 * Auth token management.
 * Access token: in-memory only (not persisted — lost on refresh, re-fetched via refresh token).
 * Refresh token: localStorage (survives page refresh).
 */

const REFRESH_KEY = "core8_refresh_token";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let _accessToken: string | null = null;

export function getAccessToken(): string | null {
  return _accessToken;
}

export function setAccessToken(token: string | null) {
  _accessToken = token;
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setRefreshToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem(REFRESH_KEY, token);
  } else {
    localStorage.removeItem(REFRESH_KEY);
  }
}

export function clearTokens() {
  _accessToken = null;
  setRefreshToken(null);
}

export async function attemptTokenRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      clearTokens();
      return false;
    }
    const data = await res.json();
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAccessToken();
  const headers = {
    ...(options.headers as Record<string, string> || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  let res = await fetch(url, { ...options, headers });

  // Auto-refresh on 401
  if (res.status === 401) {
    const refreshed = await attemptTokenRefresh();
    if (refreshed) {
      const newToken = getAccessToken();
      res = await fetch(url, {
        ...options,
        headers: { ...(options.headers as Record<string, string> || {}), Authorization: `Bearer ${newToken}` },
      });
    }
  }
  return res;
}
