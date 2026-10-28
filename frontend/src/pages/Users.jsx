import { useEffect, useState } from "react";
import * as api from "../api/client";
import { Alert, PageHeader, Spinner } from "../components/Bits";
import { btnPrimary, card, input, label } from "../lib/ui";

const ROLES = [["FACULTY", "Faculty"], ["STUDENT", "Student"], ["ADMIN", "Admin"]];

export default function Users() {
  const [role, setRole] = useState("FACULTY");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [facultyId, setFacultyId] = useState("");
  const [query, setQuery] = useState("");
  const [students, setStudents] = useState([]);
  const [studentId, setStudentId] = useState("");
  const [faculty, setFaculty] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  const loadFaculty = () => api.getLookups().then((d) => setFaculty(d.faculty)).catch((e) => setError(e.message));
  useEffect(() => { loadFaculty(); }, []);

  useEffect(() => {
    if (role !== "STUDENT" || query.trim().length < 2) { setStudents([]); return; }
    const t = setTimeout(() => {
      api.searchStudents(query.trim()).then(setStudents).catch((e) => setError(e.message));
    }, 300);
    return () => clearTimeout(t);
  }, [query, role]);

  const free = faculty.filter((f) => !f.has_login);

  async function submit(e) {
    e.preventDefault();
    setError(""); setDone(""); setBusy(true);
    const body = { username: username.trim(), password, role };
    if (role === "FACULTY") body.faculty_id = Number(facultyId);
    if (role === "STUDENT") body.student_id = Number(studentId);
    try {
      const u = await api.createUser(body);
      setDone(`Login "${u.username}" created. They can sign in now.`);
      setUsername(""); setPassword(""); setFacultyId(""); setStudentId(""); setQuery(""); setStudents([]);
      loadFaculty();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const needsLink = (role === "FACULTY" && !facultyId) || (role === "STUDENT" && !studentId);

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader title="Create a login" />
      <form onSubmit={submit} className={`${card} space-y-4 p-5`}>
        {error && <Alert>{error}</Alert>}
        {done && <Alert kind="success">{done}</Alert>}

        <fieldset>
          <legend className={label}>Who is this login for?</legend>
          <div className="flex gap-2">
            {ROLES.map(([id, text]) => (
              <label key={id} className={`flex-1 cursor-pointer rounded-md border px-3 py-2 text-center text-sm font-medium ${role === id ? "border-brand bg-brand-tint text-brand-dark" : "border-line bg-surface"}`}>
                <input type="radio" name="role" value={id} checked={role === id} className="sr-only"
                  onChange={() => { setRole(id); setFacultyId(""); setStudentId(""); }} />
                {text}
              </label>
            ))}
          </div>
        </fieldset>

        {role === "FACULTY" && (
          <div>
            <label htmlFor="fac" className={label}>Faculty member</label>
            <select id="fac" className={input} value={facultyId} onChange={(e) => setFacultyId(e.target.value)}>
              <option value="">Choose a faculty member</option>
              {free.map((f) => <option key={f.id} value={f.id}>{f.name} ({f.employee_id})</option>)}
            </select>
            {!free.length && <p className="mt-1 text-xs text-ink-soft">Every faculty member already has a login.</p>}
          </div>
        )}

        {role === "STUDENT" && (
          <div>
            <label htmlFor="stu" className={label}>Find the student</label>
            <input id="stu" className={input} placeholder="Roll number or name, at least 2 letters" value={query}
              onChange={(e) => { setQuery(e.target.value); setStudentId(""); }} />
            {students.length > 0 && (
              <ul className="mt-2 max-h-48 overflow-auto rounded-md border border-line">
                {students.map((s) => (
                  <li key={s.id} className="border-b border-line last:border-0">
                    <label className={`flex items-center gap-2 px-3 py-2 text-sm ${s.has_login ? "opacity-50" : "cursor-pointer hover:bg-paper"}`}>
                      <input type="radio" name="student" disabled={s.has_login} checked={String(studentId) === String(s.id)}
                        onChange={() => setStudentId(String(s.id))} className="accent-brand" />
                      <span className="font-medium">{s.roll_no}</span> <span>{s.name}</span>
                      {s.has_login && <span className="ml-auto text-xs">Has a login</span>}
                    </label>
                  </li>
                ))}
              </ul>
            )}
            {query.trim().length >= 2 && students.length === 0 && <p className="mt-1 text-xs text-ink-soft">No students found.</p>}
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="u" className={label}>Username</label>
            <input id="u" className={input} autoComplete="off" required value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <label htmlFor="p" className={label}>Password</label>
            <input id="p" type="password" className={input} autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
        </div>
        <p className="-mt-2 text-xs text-ink-soft">Use at least 8 characters. Avoid common passwords and all-number passwords.</p>

        <button type="submit" className={btnPrimary} disabled={busy || !username || !password || needsLink}>
          {busy && <Spinner />} Create login
        </button>
      </form>
    </div>
  );
}
