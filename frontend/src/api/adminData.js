// API helper for the admin "Data setup" pages.
// Uses the same base URL and login token as api/client.js, so it always talks to Django (not to Vite).
import { authedFetch } from "./client";

const PREFIX = "/admin-data";

function explain(d) {
  if (!d || typeof d !== "object") return "";
  return Object.entries(d)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : v}`)
    .join(" | ");
}

async function call(path, { method = "GET", body } = {}) {
  const isForm = body instanceof FormData;
  const res = await authedFetch(PREFIX + path, {
    method,
    headers: body && !isForm ? { "Content-Type": "application/json" } : {},
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (res.status === 404 && !data?.errors) {
    throw new Error(`Backend route not found (404): ${method} /api${PREFIX}${path}`);
  }
  if (!res.ok) {
    const e = new Error(data?.detail || explain(data) || `Request failed (${res.status})`);
    e.data = data;
    e.status = res.status;
    throw e;
  }
  return data;
}

export const list = (resource, { q = "", limit = 200 } = {}) =>
  call(`/${resource}/?limit=${limit}&q=${encodeURIComponent(q)}`);
export const create = (resource, body) => call(`/${resource}/`, { method: "POST", body });
export const remove = (resource, id) => call(`/${resource}/${id}/`, { method: "DELETE" });
export const summary = () => call("/summary/");
export const generateSlots = (body) => call("/slots/generate/", { method: "POST", body });

export function importFile(file, entity, dryRun = false) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("entity", entity);
  if (dryRun) fd.append("dry_run", "true");
  return call("/import/", { method: "POST", body: fd });
}

export async function downloadTemplate(entity) {
  const res = await authedFetch(`${PREFIX}/templates/${entity}/`);
  if (!res.ok) throw new Error("Could not download the template.");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${entity}_template.xlsx`;
  a.click();
  URL.revokeObjectURL(a.href);
}