// One place that describes every kind of data the Admin can add.
// To add a new field to a form, add one line to its `fields` list.
export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const ROOM_TYPES = [["CLASSROOM", "Classroom"], ["LAB", "Laboratory"], ["SEMINAR", "Seminar Hall"]];
const COURSE_TYPES = [["MAJOR", "Major"], ["MINOR", "Minor"], ["SKILL", "Skill-Based"], ["VALUE", "Value-Added"]];

// Field types: text | number | bool | date | time | select (options) | fk (another resource)
export const CFG = {
  terms: {
    label: "Terms", one: "term", imp: "term", icon: "clock", blurb: "Semesters like 2026-ODD. One term is active.",
    show: ["name", "start_date", "end_date", "is_active"], name: (r) => r.name,
    fields: [{ k: "name", t: "text", hint: "e.g. 2026-ODD" }, { k: "start_date", t: "date", opt: 1 },
      { k: "end_date", t: "date", opt: 1 }, { k: "is_active", t: "bool", hint: "The active term is used for generation" }],
  },
  departments: {
    label: "Departments", one: "department", imp: "department", icon: "home", blurb: "Computer Science, Physics and so on.",
    show: ["code", "name"], name: (r) => `${r.code} - ${r.name}`,
    fields: [{ k: "code", t: "text" }, { k: "name", t: "text" }],
  },
  timeslots: {
    label: "Time slots", one: "time slot", imp: "timeslot", icon: "clock", blurb: "Days and periods when classes can run.",
    show: ["day", "period", "start_time", "end_time", "is_break"], name: (r) => `${r.day} P${r.period}`,
    fields: [{ k: "day", t: "select", options: DAYS.map((d) => [d, d]) }, { k: "period", t: "number", d: 1 },
      { k: "start_time", t: "time" }, { k: "end_time", t: "time" }, { k: "is_break", t: "bool", hint: "Lunch etc. No class here" }],
  },
  rooms: {
    label: "Rooms", one: "room", imp: "room", icon: "grid", blurb: "Classrooms, labs and seminar halls.",
    show: ["code", "name", "capacity", "room_type"], name: (r) => r.code,
    fields: [{ k: "code", t: "text" }, { k: "name", t: "text", opt: 1 }, { k: "capacity", t: "number", d: 60 },
      { k: "room_type", t: "select", options: ROOM_TYPES }],
  },
  faculty: {
    label: "Faculty", one: "faculty member", imp: "faculty", icon: "teach", blurb: "Teachers and their weekly hour limit.",
    show: ["employee_id", "name", "department", "max_hours_per_week"], name: (r) => `${r.name} (${r.employee_id})`,
    fields: [{ k: "employee_id", t: "text" }, { k: "name", t: "text" }, { k: "email", t: "text", opt: 1 },
      { k: "department", t: "fk", fk: "departments" }, { k: "max_hours_per_week", t: "number", d: 16 }],
  },
  courses: {
    label: "Courses", one: "course", imp: "course", icon: "book", blurb: "Subjects, hours per week, lab needs.",
    show: ["code", "name", "department", "semester", "hours_per_week", "faculty"], name: (r) => `${r.code} - ${r.name}`,
    fields: [{ k: "code", t: "text" }, { k: "name", t: "text" }, { k: "department", t: "fk", fk: "departments" },
      { k: "course_type", t: "select", options: COURSE_TYPES }, { k: "credits", t: "number", d: 3 },
      { k: "hours_per_week", t: "number", d: 3 }, { k: "requires_lab", t: "bool" },
      { k: "lab_block_size", t: "number", d: 1, hint: "Consecutive periods for a lab (1 = theory)" },
      { k: "semester", t: "number", d: 1 }, { k: "faculty", t: "fk", fk: "faculty", opt: 1 },
      { k: "expected_students", t: "number", d: 0 }],
  },
  students: {
    label: "Students", one: "student", imp: "student", icon: "user", blurb: "Roll numbers, department and semester.",
    show: ["roll_no", "name", "department", "semester"], name: (r) => `${r.roll_no} - ${r.name}`,
    fields: [{ k: "roll_no", t: "text" }, { k: "name", t: "text" }, { k: "email", t: "text", opt: 1 },
      { k: "department", t: "fk", fk: "departments" }, { k: "semester", t: "number", d: 1 }],
  },
  choices: {
    label: "Student choices", one: "choice", imp: "choice", icon: "book", uploadOnly: true, blurb: "Which courses each student picked. Upload only.",
  },
  preferences: {
    label: "Faculty preferences", one: "preference", imp: "preference", icon: "teach", uploadOnly: true, blurb: "Slots faculty prefer or avoid. Upload only.",
  },
};

// Upload in this order: later files refer to earlier ones.
export const ORDER = ["terms", "departments", "timeslots", "rooms", "faculty", "courses", "students", "choices", "preferences"];

export const pretty = (k) => k.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
export const blank = (cfg) => Object.fromEntries((cfg.fields || []).map((f) => [f.k,
  f.t === "bool" ? false : f.t === "number" ? f.d ?? 0 : f.t === "select" ? f.options[0][0] : ""]));