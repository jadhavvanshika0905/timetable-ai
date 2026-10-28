import { label as labelCls, input } from "../lib/ui";

export function Spinner({ size = 16 }) {
  return (
    <svg className="spinner" width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Alert({ kind = "error", children }) {
  const style = {
    error: "border-bad/30 bg-bad-tint text-bad",
    success: "border-good/30 bg-good-tint text-good",
    info: "border-brand/30 bg-brand-tint text-brand-dark",
  }[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`rounded-md border px-3 py-2 text-sm ${style}`}>
      {children}
    </div>
  );
}

export function PageHeader({ title, children }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <h1 className="font-display text-2xl font-bold tracking-tight">{title}</h1>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

export function Empty({ title, children }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-surface px-6 py-10 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-2 text-sm text-ink-soft">{children}</div>}
    </div>
  );
}

const RISK = {
  HIGH: "bg-bad-tint text-bad",
  MEDIUM: "bg-warn-tint text-warn",
  LOW: "bg-good-tint text-good",
};
export function RiskBadge({ level }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${RISK[level] || "bg-paper text-ink-soft"}`}>
      {level === "HIGH" ? "High" : level === "MEDIUM" ? "Medium" : level === "LOW" ? "Low" : level}
    </span>
  );
}

export function StatusChip({ status }) {
  const ok = status === "OPTIMAL" || status === "FEASIBLE";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${ok ? "bg-good-tint text-good" : "bg-bad-tint text-bad"}`}>
      {status === "OPTIMAL" ? "Best possible" : status === "FEASIBLE" ? "Valid timetable" : status === "INFEASIBLE" ? "Cannot be scheduled" : "No answer in time"}
    </span>
  );
}

export function TermSelect({ terms, value, onChange, disabled }) {
  return (
    <div className="min-w-48">
      <label htmlFor="term" className={labelCls}>Term</label>
      <select id="term" className={input} value={value} disabled={disabled || !terms.length}
        onChange={(e) => onChange(e.target.value)}>
        {!terms.length && <option value="">No terms found</option>}
        {terms.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>
    </div>
  );
}

export function FilterSelect({ id, text, value, onChange, items }) {
  return (
    <div className="min-w-40">
      <label htmlFor={id} className={labelCls}>{text}</label>
      <select id={id} className={input} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {items.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}
