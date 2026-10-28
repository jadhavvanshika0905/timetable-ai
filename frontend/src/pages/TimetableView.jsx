import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../api/client";
import { DayList, WeekGrid } from "../components/TimetableGrid";
import { Alert, Empty, FilterSelect, PageHeader, Spinner, TermSelect } from "../components/Bits";
import { btnGhost } from "../lib/ui";
import { filterRows, options, summarize, toCsv } from "../lib/grid";
import { useTermChoice } from "../lib/useTermChoice";

// Section is the last part of the course code: "CS301-A" -> "A".
const sectionOf = (r) => (String(r.course_code || "").match(/-([A-Za-z0-9]+)$/) || [])[1] || "Other";

/** One screen used twice: Admin sees every class (mode="all"), others see their own (mode="mine"). */
export default function TimetableView({ mode }) {
  const isAll = mode === "all";
  const { terms, termId, setTermId, error: termError, loading: termsLoading } = useTermChoice();
  const [rows, setRows] = useState([]);
  const [state, setState] = useState("idle"); // idle | loading | ready | empty | error
  const [error, setError] = useState("");
  const [view, setView] = useState("week");
  const [filters, setFilters] = useState({ faculty_id: "", room_id: "", course_id: "" });
  const [section, setSection] = useState(""); // "" = every section

  useEffect(() => {
    if (!termId) return;
    let cancelled = false;
    setState("loading");
    (isAll ? api.getFullTimetable(termId) : api.getMyTimetable(termId))
      .then((data) => { if (!cancelled) { setRows(data.timetable); setState("ready"); } })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 404) { setRows([]); setState("empty"); }
        else { setError(err.message); setState("error"); }
      });
    return () => { cancelled = true; };
  }, [termId, isAll]);

  const sections = useMemo(() => [...new Set(rows.map(sectionOf))].sort(), [rows]);
  const shown = useMemo(
    () => filterRows(rows.filter((r) => !section || sectionOf(r) === section), filters),
    [rows, filters, section]);
  const stats = summarize(shown);
  // Admin looking at "All sections": show one grid per section instead of one crowded grid.
  const groups = isAll && !section && sections.length > 1
    ? sections.map((sec) => [sec, shown.filter((r) => sectionOf(r) === sec)]).filter(([, rs]) => rs.length)
    : null;
  const draw = (rs) => (view === "week" ? <WeekGrid rows={rs} showFaculty /> : <DayList rows={rs} showFaculty />);

  function download() {
    const blob = new Blob([toCsv(shown)], { type: "text/csv" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `timetable-term-${termId}${section ? `-section-${section}` : ""}.csv` });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title={isAll ? "Full timetable" : "My timetable"}>
        <div className="inline-flex overflow-hidden rounded-md border border-line" role="group" aria-label="View">
          {[["week", "Week"], ["day", "By day"]].map(([id, text]) => (
            <button key={id} type="button" aria-pressed={view === id} onClick={() => setView(id)}
              className={`px-3 py-2 text-sm font-medium ${view === id ? "bg-brand text-white" : "bg-surface hover:bg-paper"}`}>{text}</button>
          ))}
        </div>
        <button type="button" className={btnGhost} onClick={download} disabled={!shown.length}>Download CSV</button>
      </PageHeader>

      <div className="mb-5 flex flex-wrap items-end gap-4">
        <TermSelect terms={terms} value={termId} onChange={setTermId} disabled={termsLoading} />
        {isAll && state === "ready" && (
          <>
            <FilterSelect id="f-fac" text="Faculty" value={filters.faculty_id} items={options(rows, "faculty_id", "faculty_name")}
              onChange={(v) => setFilters((f) => ({ ...f, faculty_id: v }))} />
            <FilterSelect id="f-room" text="Room" value={filters.room_id} items={options(rows, "room_id", "room_code")}
              onChange={(v) => setFilters((f) => ({ ...f, room_id: v }))} />
            <FilterSelect id="f-course" text="Course" value={filters.course_id} items={options(rows, "course_id", "course_code")}
              onChange={(v) => setFilters((f) => ({ ...f, course_id: v }))} />
          </>
        )}
      </div>

      {isAll && state === "ready" && sections.length > 1 && (
        <div className="mb-5 flex flex-wrap items-center gap-2" role="group" aria-label="Section">
          {[["", "All sections"], ...sections.map((x) => [x, x === "Other" ? "Other" : `Section ${x}`])].map(([id, text]) => (
            <button key={id || "all"} type="button" aria-pressed={section === id} onClick={() => setSection(id)}
              className={`rounded-full border px-4 py-1.5 text-sm font-medium transition ${section === id ? "border-brand bg-brand text-white shadow-sm" : "border-line bg-surface hover:bg-brand-tint"}`}>
              {text}
            </button>
          ))}
        </div>
      )}

      {termError && <Alert>{termError}</Alert>}
      {state === "loading" && <p className="flex items-center gap-2 text-sm text-ink-soft"><Spinner /> Loading timetable</p>}
      {state === "error" && <Alert>{error}</Alert>}
      {state === "empty" && (
        <Empty title="No timetable for this term yet.">
          {isAll
            ? <>Go to <Link className="font-medium text-brand underline" to="/generate">Generate</Link> to create one.</>
            : "Your Admin has not generated it yet. Check back later."}
        </Empty>
      )}
      {state === "ready" && (
        <>
          <p className="mb-3 text-sm text-ink-soft">
            {stats.classes} {stats.classes === 1 ? "class" : "classes"} a week across {stats.courses} {stats.courses === 1 ? "course" : "courses"}.
          </p>
          {shown.length === 0
            ? <Empty title={isAll ? "Nothing matches these filters." : "You have no classes in this term."} />
            : groups
              ? groups.map(([sec, rs]) => (
                  <section key={sec} className="mb-8" aria-label={`Section ${sec}`}>
                    <h2 className="mb-2 font-display text-lg font-semibold">
                      {sec === "Other" ? "Other classes" : `Section ${sec}`}
                      <span className="ml-2 text-sm font-normal text-ink-soft">{rs.length} {rs.length === 1 ? "class" : "classes"} a week</span>
                    </h2>
                    {draw(rs)}
                  </section>
                ))
              : draw(shown)}
        </>
      )}
    </div>
  );
}