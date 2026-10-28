import test from "node:test";
import assert from "node:assert/strict";
import { buildGrid, filterRows, options, courseColor, groupByDay, toCsv, summarize } from "./grid.js";

const rows = [
  { course_id: "1", course_code: "B", course_name: "Beta", faculty_id: "9", faculty_name: "Zed", room_id: "5", room_code: "R1", day: "Tue", period: 2 },
  { course_id: "2", course_code: "A", course_name: 'Al"pha', faculty_id: "8", faculty_name: "Amy", room_id: "6", room_code: "R2", day: "Mon", period: 1 },
  { course_id: "3", course_code: "C", course_name: "Gamma", faculty_id: "8", faculty_name: "Amy", room_id: "5", room_code: "R1", day: "Mon", period: 1 },
];

test("grid orders days, fills periods and stacks same-slot classes", () => {
  const g = buildGrid(rows);
  assert.deepEqual(g.days, ["Mon", "Tue"]);
  assert.deepEqual(g.periods, [1, 2]);
  assert.deepEqual(g.cells["Mon|1"].map((r) => r.course_code), ["A", "C"]);
});

test("empty timetable still gives a Mon-Fri, 6 period skeleton", () => {
  const g = buildGrid([]);
  assert.equal(g.days.length, 5);
  assert.equal(g.periods.length, 6);
});

test("filters combine and ignore empty values", () => {
  assert.equal(filterRows(rows, { faculty_id: "8" }).length, 2);
  assert.equal(filterRows(rows, { faculty_id: "8", room_id: "5" }).length, 1);
  assert.equal(filterRows(rows, { faculty_id: "", room_id: "" }).length, 3);
});

test("options are distinct and sorted by label", () => {
  assert.deepEqual(options(rows, "faculty_id", "faculty_name").map((o) => o.label), ["Amy", "Zed"]);
});

test("course colour is stable", () => {
  assert.deepEqual(courseColor("CS101"), courseColor("CS101"));
  assert.notDeepEqual(courseColor("CS101"), courseColor("CS102"));
});

test("day list and summary", () => {
  assert.deepEqual(groupByDay(rows).map((d) => d.day), ["Mon", "Tue"]);
  assert.deepEqual(summarize(rows), { classes: 3, courses: 3, days: 2 });
});

test("csv escapes quotes and sorts", () => {
  const csv = toCsv(rows).split("\n");
  assert.equal(csv[0], '"Day","Period","Course code","Course","Faculty","Room"');
  assert.ok(csv[1].includes('"Al""pha"'));
  assert.equal(csv.length, 4);
});
