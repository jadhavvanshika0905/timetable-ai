import { buildGrid, cellKey, courseColor, groupByDay } from "../lib/grid";

function Entry({ row, showFaculty }) {
  return (
    <div className="rounded border-l-4 px-2 py-1 text-xs leading-snug" style={courseColor(row.course_code)}>
      <div className="font-semibold">{row.course_code}</div>
      <div className="truncate opacity-80" title={row.course_name}>{row.course_name}</div>
      <div className="mt-0.5 flex flex-wrap gap-x-2 opacity-90">
        <span>Room {row.room_code}</span>
        {showFaculty && <span>{row.faculty_name}</span>}
      </div>
    </div>
  );
}

export function WeekGrid({ rows, showFaculty }) {
  const { days, periods, cells } = buildGrid(rows);
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full min-w-[720px] border-collapse text-left">
        <caption className="sr-only">Weekly timetable</caption>
        <thead>
          <tr className="bg-paper">
            <th scope="col" className="w-20 border-b border-line px-3 py-2 text-sm font-medium text-ink-soft">Period</th>
            {days.map((d) => (
              <th key={d} scope="col" className="border-b border-l border-line px-3 py-2 text-sm font-semibold">{d}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {periods.map((p) => (
            <tr key={p}>
              <th scope="row" className="border-t border-line bg-paper px-3 py-2 align-top text-sm font-medium text-ink-soft">{p}</th>
              {days.map((d) => {
                const list = cells[cellKey(d, p)] || [];
                return (
                  <td key={d} className="min-w-36 border-l border-t border-line p-1.5 align-top">
                    <div className="flex flex-col gap-1">
                      {list.map((r, i) => <Entry key={`${r.course_id}-${i}`} row={r} showFaculty={showFaculty} />)}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DayList({ rows, showFaculty }) {
  const groups = groupByDay(rows);
  return (
    <div className="space-y-4">
      {groups.map(({ day, items }) => (
        <section key={day} className="rounded-lg border border-line bg-surface">
          <h3 className="border-b border-line bg-paper px-4 py-2 font-display text-base font-semibold">{day}</h3>
          <ul className="divide-y divide-line">
            {items.map((r, i) => (
              <li key={`${r.course_id}-${r.period}-${i}`} className="flex items-start gap-3 px-4 py-2.5">
                <span className="w-16 shrink-0 pt-0.5 text-sm text-ink-soft">Period {r.period}</span>
                <div className="min-w-0 flex-1 rounded border-l-4 px-2 py-1 text-sm" style={courseColor(r.course_code)}>
                  <div className="font-semibold">{r.course_code} <span className="font-normal">{r.course_name}</span></div>
                  <div className="opacity-90">Room {r.room_code}{showFaculty ? `, ${r.faculty_name}` : ""}</div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
