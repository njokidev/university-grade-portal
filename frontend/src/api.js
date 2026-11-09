// Small wrapper around fetch. The token is kept in memory only (not
// localStorage), so it disappears when the tab closes and cannot be read
// by a script injected into another page.
let token = null;
let onUnauthorized = () => {};

export function setToken(t) { token = t; }
export function setUnauthorizedHandler(fn) { onUnauthorized = fn; }

export async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`/api${path}`, {
    method, headers, body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (res.status === 401 && token) onUnauthorized(data?.detail);
  return { ok: res.ok, status: res.status, data };
}
