// All backend calls live here. One place to change the base URL, tokens, errors.
const BASE = (import.meta.env?.VITE_API_URL || "http://127.0.0.1:8000/api").replace(/\/$/, "");
const KEY = "tt_auth";

const store = () => (typeof localStorage !== "undefined" ? localStorage : null);

export const apiBase = BASE;
export function loadAuth() {
  try { return JSON.parse(store()?.getItem(KEY) || "null"); } catch { return null; }
}
export function saveAuth(auth) { store()?.setItem(KEY, JSON.stringify(auth)); }
export function clearAuth() { store()?.removeItem(KEY); }

let onSessionEnd = () => {};
export function setOnSessionEnd(fn) { onSessionEnd = fn; }

export class ApiError extends Error {
  constructor(status, data, message) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

/** Turn any DRF error body into one readable sentence. */
export function errorMessage(data) {
  if (!data) return "";
  if (typeof data === "string") return data.length > 200 ? "" : data;
  if (Array.isArray(data)) return data.map(errorMessage).filter(Boolean).join(" ");
  if (typeof data.detail === "string") return data.detail;
  return Object.entries(data)
    .map(([field, value]) => {
      const text = errorMessage(value);
      return field === "non_field_errors" || field === "detail" ? text : `${field}: ${text}`;
    })
    .filter(Boolean)
    .join(" ");
}

async function send(path, { method = "GET", body, token } = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, null, `Cannot reach the server at ${BASE}. Is the backend running?`);
  }
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }
  if (!res.ok) {
    throw new ApiError(res.status, data, errorMessage(data) || `Request failed (${res.status}).`);
  }
  return data;
}

let refreshing = null;
function refreshAccess() {
  if (!refreshing) {
    const auth = loadAuth();
    refreshing = send("/auth/refresh/", { method: "POST", body: { refresh: auth?.refresh } })
      .then((data) => {
        saveAuth({ ...auth, access: data.access, refresh: data.refresh || auth.refresh });
        return data.access;
      })
      .finally(() => { refreshing = null; });
  }
  return refreshing;
}

/** Authenticated request. On 401 it refreshes the token once and retries. */
async function authed(path, opts = {}) {
  const auth = loadAuth();
  try {
    return await send(path, { ...opts, token: auth?.access });
  } catch (err) {
    if (err.status !== 401 || !auth?.refresh) throw err;
    let access;
    try {
      access = await refreshAccess();
    } catch {
      clearAuth();
      onSessionEnd();
      throw new ApiError(401, null, "Your session expired. Please sign in again.");
    }
    return send(path, { ...opts, token: access });
  }
}

/** Like fetch(), but adds the login token and retries once after refreshing it. Used for file uploads/downloads. */
export async function authedFetch(path, init = {}) {
  const run = (token) => fetch(BASE + path, {
    ...init,
    headers: { ...(init.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  const auth = loadAuth();
  let res;
  try { res = await run(auth?.access); }
  catch { throw new ApiError(0, null, `Cannot reach the server at ${BASE}. Is the backend running?`); }
  if (res.status === 401 && auth?.refresh) {
    try { res = await run(await refreshAccess()); }
    catch { clearAuth(); onSessionEnd(); throw new ApiError(401, null, "Your session expired. Please sign in again."); }
  }
  return res;
}

// ---- endpoints -----------------------------------------------------------
export async function login(username, password) {
  const data = await send("/auth/login/", { method: "POST", body: { username, password } });
  saveAuth({ access: data.access, refresh: data.refresh, user: data.user });
  return data.user;
}
export const me = () => authed("/auth/me/");
export const getTerms = () => authed("/terms/");
export const getLookups = () => authed("/lookups/");
export const searchStudents = (q) => authed(`/lookups/students/?q=${encodeURIComponent(q)}`);
export const createUser = (body) => authed("/auth/users/", { method: "POST", body });
export const generateTimetable = (body) => authed("/timetable/generate/", { method: "POST", body });
export const getFullTimetable = (termId) => authed(`/timetable/?term_id=${termId}`);
export const getMyTimetable = (termId) => authed(`/timetable/mine/?term_id=${termId}`);