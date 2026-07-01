// Shared API client / base URL for the backend.
//
// Single source of truth for the backend origin so adding a booking feature
// (or migrating TalkAgent/WhisperAgent later) doesn't keep duplicating the
// hardcoded http://localhost:8000 string across components.
//
// Mirrors the existing hardcoded convention; backed by native fetch.

export const API_BASE = 'http://localhost:8000';
export const API_PREFIX = '/api';

const TOKEN_KEY = 'tta.token';

// --- Auth token storage ------------------------------------------------
// JWT lives in localStorage; sent as `Authorization: Bearer <token>` on every
// request once set. `setToken(null)` clears it (logout / 401).

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

/**
 * Convert the plain fetch helpers below into authenticated ones by injecting
 * the bearer token + Content-Type. Pass through extra headers per call.
 */
function authHeaders(extra = {}) {
  const token = getToken();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

// Thin JSON helpers — return parsed JSON or throw. Callers decide whether a
// specific endpoint needs auth (login is anonymous; admin endpoints are not).
export async function apiGet(path, { params = null, auth = false } = {}) {
  const url = new URL(`${API_BASE}${API_PREFIX}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
    });
  }
  const res = await fetch(url, { headers: auth ? authHeaders() : {} });
  if (!res.ok) {
    const detail = await safeErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}

export async function apiPost(path, body, { auth = false } = {}) {
  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const detail = await safeErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}

export async function apiPatch(path, body, { auth = false } = {}) {
  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    method: 'PATCH',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const detail = await safeErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}

export async function apiPut(path, body, { auth = false } = {}) {
  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    method: 'PUT',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const detail = await safeErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}

export async function apiDelete(path, { auth = false } = {}) {
  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    method: 'DELETE',
    headers: auth ? authHeaders() : {},
  });
  if (!res.ok && res.status !== 204) {
    const detail = await safeErrorDetail(res);
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

async function safeErrorDetail(res) {
  try {
    const data = await res.json();
    return data.detail || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}
