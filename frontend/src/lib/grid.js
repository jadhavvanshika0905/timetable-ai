// Pure helpers for the weekly grid (no React, easy to test).
export const DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DEFAULT_DAYS = DAY_ORDER.slice(0, 5);

export const cellKey = (day, period) => `${day}|${period}`;

/** rows -> { days, periods, cells } where cells[day|period] = [row, ...] */
export function buildGrid(rows) {
  const cells = {};
  const seenDays = new Set();
  let maxPeriod = 0;
  for (const row of rows) {
    seenDays.add(row.day);
    maxPeriod = Math.max(maxPeriod, row.period);
    (cells[cellKey(row.day, row.period)] ||= []).push(row);
  }
  const days = rows.length
    ? DAY_ORDER.filter((d) => seenDays.has(d)).concat([...seenDays].filter((d) => !DAY_ORDER.includes(d)))
    : DEFAULT_DAYS;
  const last = rows.length ? maxPeriod : 6;
  const periods = Array.from({ length: last }, (_, i) => i + 1);
  for (const list of Object.values(cells)) {
    list.sort((a, b) => String(a.course_code).localeCompare(String(b.course_code)));
  }
  return { days, periods, cells };
}

/** Keep rows matching every non-empty filter ({faculty_id, room_id, course_id}). */
export function filterRows(rows, filters) {
  return rows.filter((r) =>
    Object.entries(filters).every(([key, value]) => !value || String(r[key]) === String(value)));
}

/** Distinct { value, label } pairs for a filter dropdown. */
export function options(rows, idKey, labelKey) {
  const seen = new Map();
  for (const r of rows) {
    if (r[idKey] != null && !seen.has(String(r[idKey]))) {
      seen.set(String(r[idKey]), r[labelKey] || String(r[idKey]));
    }
  }
  return [...seen].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label));
}

/** Same course -> same colour everywhere. */
export function courseColor(code) {
  let h = 0;
  for (const ch of String(code)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const hue = (h * 47) % 360;
  return {
    background: `hsl(${hue} 55% 93%)`,
    borderColor: `hsl(${hue} 50% 42%)`,
    color: `hsl(${hue} 45% 18%)`,
  };
}

export function summarize(rows) {
  return {
    classes: rows.length,
    courses: new Set(rows.map((r) => r.course_id)).size,
    days: new Set(rows.map((r) => r.day)).size,
  };
}

/** rows -> [{day, items:[...]}] sorted by day then period (for the list view). */
export function groupByDay(rows) {
  const byDay = {};
  for (const r of rows) (byDay[r.day] ||= []).push(r);
  return DAY_ORDER.filter((d) => byDay[d]).map((day) => ({
    day,
    items: byDay[day].sort((a, b) => a.period - b.period),
  }));
}

export function toCsv(rows) {
  const head = ["Day", "Period", "Course code", "Course", "Faculty", "Room"];
  const esc = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  const lines = [...rows]
    .sort((a, b) => DAY_ORDER.indexOf(a.day) - DAY_ORDER.indexOf(b.day) || a.period - b.period)
    .map((r) => [r.day, r.period, r.course_code, r.course_name, r.faculty_name, r.room_code].map(esc).join(","));
  return [head.map(esc).join(","), ...lines].join("\n");
}
