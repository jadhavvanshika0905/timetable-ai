import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../api/client";
import * as ad from "../api/adminData";
import { Alert, Empty, PageHeader, RiskBadge, Spinner, StatusChip, TermSelect } from "../components/Bits";
import { btnGhost, btnPrimary, card, label } from "../lib/ui";
import { useTermChoice } from "../lib/useTermChoice";

const METRIC_TEXT = {
  student_idle_gaps_total: "Free periods between classes (all students)",
  students_with_gaps: "Students with at least one gap",
  faculty_overload_periods: "Faculty classes beyond their daily share",
  avoid_violations: "Classes placed in slots faculty wanted to avoid",
  prefer_hits: "Classes placed in preferred slots",
  solve_seconds: "Time taken (seconds)",
};
const RISK_ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 };
const PRESETS = [[30, "Quick", "Small data, a first try"], [90, "Balanced", "Most colleges"], [240, "Thorough", "Large data, best quality"]];
const COUNTS = [["faculty", "Faculty"], ["courses", "Courses"], ["rooms", "Rooms"], ["students", "Students"], ["timeslots", "Time slots"]];

const Stat = ({ value, text, bad }) => (
  <div className="rounded-xl border border-line px-4 py-3">
    <div className={`font-display text-2xl font-bold tabular-nums ${bad ? "text-bad" : ""}`}>{value}</div>
    <div className="text-xs text-ink-soft">{text}</div>
  </div>
);

export default function Generate() {
  const { terms, termId, setTermId, error: termError, loading } = useTermChoice();
  const [seconds, setSeconds] = useState(90);
  const [useMl, setUseMl] = useState(true);
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [lookups, setLookups] = useState({ faculty: [], courses: [] });
  const [data, setData] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    api.getLookups().then(setLookups).catch(() => {});
    ad.summary().then(setData).catch(() => {});
    return () => clearInterval(timer.current);
  }, []);

  async function run() {
    setError(""); setResult(null); setElapsed(0); setRunning(true);
    const started = Date.now();
    timer.current = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 500);
    try {
      setResult(await api.generateTimetable({ term_id: Number(termId), max_time_seconds: seconds, use_ml: useMl }));
    } catch (err) {
      setError(err.message);
    } finally {
      clearInterval(timer.current);
      setRunning(false);
    }
  }

  const notReady = data && data.ready === false;
  const facultyName = (id) => lookups.faculty.find((f) => String(f.id) === String(id))?.name || `Faculty ${id}`;
  const course = (id) => lookups.courses.find((c) => String(c.id) === String(id));
  const hints = result?.ml_hints;
  const risks = hints ? Object.entries(hints.faculty_risk).sort((a, b) => RISK_ORDER[a[1]] - RISK_ORDER[b[1]]) : [];
  const metrics = result ? Object.entries(METRIC_TEXT).filter(([k]) => result.metrics?.[k] != null) : [];
  const termName = terms?.find((t) => String(t.id) === String(termId))?.name;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Generate timetable">
        <Link to="/admin" className={btnGhost}>Edit data</Link>
      </PageHeader>

      {/* 1. data check */}
      <section className={`${card} mb-5 p-5`} aria-labelledby="chk-h">
        <h2 id="chk-h" className="font-display text-lg font-semibold">1. Your data</h2>
        {!data ? <p className="mt-2 flex items-center gap-2 text-sm text-ink-soft"><Spinner /> Checking</p> : (
          <>
            <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
              {COUNTS.map(([k, t]) => (
                <div key={k} className="rounded-md border border-line px-3 py-2">
                  <dt className="text-xs text-ink-soft">{t}</dt><dd className="text-lg font-semibold tabular-nums">{data.counts?.[k] ?? 0}</dd>
                </div>
              ))}
            </dl>
            {data.warnings?.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-bad">{data.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
            {notReady
              ? <p className="mt-3 text-sm">Fix this first: <Link className="font-medium text-brand underline" to="/admin">go to Data setup</Link>.</p>
              : <p className="mt-3 text-sm text-ink-soft">Looks complete. Active term: <span className="font-medium text-ink">{data.active_term?.name || "none"}</span>.</p>}
          </>
        )}
      </section>

      {/* 2. settings */}
      <section className={`${card} p-5`} aria-labelledby="set-h">
        <h2 id="set-h" className="font-display text-lg font-semibold">2. Choose settings</h2>
        {termError && <div className="mt-3"><Alert>{termError}</Alert></div>}
        <div className="mt-3"><TermSelect terms={terms} value={termId} onChange={setTermId} disabled={running || loading} /></div>

        <fieldset className="mt-5" disabled={running}>
          <legend className={label}>How long may the solver think?</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {PRESETS.map(([s, name, hint]) => (
              <button key={s} type="button" aria-pressed={seconds === s} onClick={() => setSeconds(s)}
                className={`rounded-xl border px-4 py-3 text-left transition ${seconds === s ? "border-brand bg-brand-tint" : "border-line bg-surface hover:bg-paper"}`}>
                <span className="block font-semibold">{name} <span className="font-normal text-ink-soft">({s}s)</span></span>
                <span className="block text-xs text-ink-soft">{hint}</span>
              </button>
            ))}
          </div>
          <label htmlFor="secs" className="mt-3 block text-xs text-ink-soft">Or set it yourself: {seconds} seconds. The solver stops early if it finds the best answer.</label>
          <input id="secs" type="range" min="10" max="300" step="5" value={seconds}
            onChange={(e) => setSeconds(Number(e.target.value))} className="w-full accent-brand" />
        </fieldset>

        <label className="mt-4 flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5 accent-brand" checked={useMl} disabled={running} onChange={(e) => setUseMl(e.target.checked)} />
          <span>
            <span className="font-medium">Use ML hints</span>
            <span className="block text-ink-soft">Forecasts class sizes from past terms and eases the load on busy faculty.</span>
          </span>
        </label>
      </section>

      {/* 3. run */}
      <section className={`${card} mt-5 p-5`} aria-labelledby="run-h">
        <h2 id="run-h" className="font-display text-lg font-semibold">3. Generate</h2>
        <p className="mt-1 text-sm text-ink-soft">
          {termName ? <>This builds the timetable for <span className="font-medium text-ink">{termName}</span> and replaces the saved one if it succeeds.</> : "Pick a term first."}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button type="button" className={btnPrimary} onClick={run} disabled={running || !termId || notReady}>
            {running && <Spinner />} {running ? "Generating" : result ? "Generate again" : "Generate timetable"}
          </button>
          {running && <span role="status" className="text-sm text-ink-soft">Solving, {elapsed}s of up to {seconds}s. Keep this page open.</span>}
        </div>
        {running && (
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-brand-tint" role="progressbar" aria-valuemin={0} aria-valuemax={seconds} aria-valuenow={Math.min(elapsed, seconds)}>
            <div className="h-full rounded-full bg-brand transition-all duration-500" style={{ width: `${Math.min(100, (elapsed / seconds) * 100)}%` }} />
          </div>
        )}
      </section>

      {error && <div className="mt-4"><Alert>{error}</Alert></div>}

      {result && (
        <div className="mt-6 space-y-6">
          <section className={`${card} p-5`} aria-labelledby="res-h">
            <div className="flex flex-wrap items-center gap-3">
              <h2 id="res-h" className="font-display text-lg font-semibold">Result</h2>
              <StatusChip status={result.status} />
            </div>
            {result.saved ? (
              <>
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Stat value={result.rows} text="Classes placed" />
                  <Stat value={result.metrics?.students_with_gaps ?? "-"} text="Students with gaps" />
                  <Stat value={result.metrics?.avoid_violations ?? "-"} text="Avoid-slot clashes" bad={result.metrics?.avoid_violations > 0} />
                  <Stat value={result.metrics?.solve_seconds != null ? `${result.metrics.solve_seconds}s` : "-"} text="Time taken" />
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link to="/timetable" className={btnPrimary}>Open the full timetable</Link>
                  <Link to="/users" className={btnGhost}>Create logins for faculty and students</Link>
                </div>
              </>
            ) : (
              <p className="mt-2 text-sm text-bad">No timetable was saved. The previous one for this term is unchanged.</p>
            )}
            {metrics.length > 0 && (
              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-medium">All numbers</summary>
                <dl className="mt-2 grid gap-x-8 gap-y-2 sm:grid-cols-2">
                  {metrics.map(([k, text]) => (
                    <div key={k} className="flex items-baseline justify-between gap-3 border-b border-line py-1.5">
                      <dt className="text-sm text-ink-soft">{text}</dt>
                      <dd className="font-semibold tabular-nums">{result.metrics[k]}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            )}
            {result.infeasibility_reasons?.length > 0 && (
              <div className="mt-4">
                <p className="mb-1 text-sm font-medium">Why it could not be scheduled</p>
                <ul className="list-disc space-y-1 pl-5 text-sm">{result.infeasibility_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
                <p className="mt-2 text-sm text-ink-soft">
                  <Link className="font-medium text-brand underline" to="/admin">Fix the data</Link>, or give the solver more time, then generate again.
                </p>
              </div>
            )}
          </section>

          {hints && (
            <section className={`${card} p-5`} aria-labelledby="ml-h">
              <h2 id="ml-h" className="font-display text-lg font-semibold">What the ML hints said</h2>
              <div className="mt-4 grid gap-6 md:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Faculty workload</h3>
                  {risks.length ? (
                    <table className="w-full text-sm"><tbody>
                      {risks.map(([id, level]) => (
                        <tr key={id} className="border-b border-line">
                          <td className="py-1.5 pr-3">{facultyName(id)}</td>
                          <td className="py-1.5 text-right"><RiskBadge level={level} /></td>
                        </tr>
                      ))}
                    </tbody></table>
                  ) : <p className="text-sm text-ink-soft">No faculty were scored.</p>}
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Classes expected to be bigger</h3>
                  {Object.keys(hints.predicted_demand).length ? (
                    <table className="w-full text-sm"><tbody>
                      {Object.entries(hints.predicted_demand).map(([id, n]) => (
                        <tr key={id} className="border-b border-line">
                          <td className="py-1.5 pr-3">{course(id) ? `${course(id).code} ${course(id).name}` : `Course ${id}`}</td>
                          <td className="py-1.5 text-right tabular-nums">{n} students</td>
                        </tr>
                      ))}
                    </tbody></table>
                  ) : <p className="text-sm text-ink-soft">No growth predicted. This also happens when the database has fewer than 3 past terms.</p>}
                  <h3 className="mb-1 mt-5 text-sm font-semibold">Solver priorities</h3>
                  <p className="text-sm text-ink-soft">
                    {Object.keys(hints.weights).length
                      ? Object.entries(hints.weights).map(([k, v]) => `${k.replaceAll("_", " ")} set to ${v}`).join(", ")
                      : "Unchanged from the defaults."}
                  </p>
                </div>
              </div>
            </section>
          )}
          {!hints && result.saved && <Empty title="ML hints were switched off for this run." />}
        </div>
      )}
    </div>
  );
}