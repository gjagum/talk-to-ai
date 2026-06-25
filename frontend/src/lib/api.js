// Shared API client / base URL for the backend.
//
// Single source of truth for the backend origin so adding a booking feature
// (or migrating TalkAgent/WhisperAgent later) doesn't keep duplicating the
// hardcoded http://localhost:8000 string across components.
//
// Mirrors the existing hardcoded convention; backed by native fetch.

export const API_BASE = 'http://localhost:8000';
export const API_PREFIX = '/api';

// Thin JSON helpers — return parsed JSON or throw.
export async function apiGet(path, { params = null } = {}) {
  const url = new URL(`${API_BASE}${API_PREFIX}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
    });
  }
  const res = await fetch(url);
  if (!res.ok) {
    const detail = await safeErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}

export async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const detail = await safeErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}

export async function apiPatch(path, body) {
  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const detail = await safeErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}

async function safeErrorDetail(res) {
  try {
    const data = await res.json();
    return data.detail || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}
