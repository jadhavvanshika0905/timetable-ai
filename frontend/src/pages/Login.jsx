import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Alert, Spinner } from "../components/Bits";
import Icon from "../components/Icon";
import Logo from "../components/Logo";
import { roleHome } from "../lib/roles";

const HUES = [172, 24, 262, 340, 205, 48];
// Decorative mini week (0 = empty). The cells "breathe" in a wave.
const SAMPLE = [1, 0, 2, 0, 3, 0, 4, 0, 1, 0, 2, 0, 5, 0, 4, 0, 3, 0, 2, 0, 5, 0, 1, 0, 3];

const field =
  "w-full rounded-xl border border-line bg-white py-3 pl-11 pr-4 text-[15px] text-ink shadow-sm transition placeholder:text-ink-soft/60 focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/15";

export default function Login() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Already signed in? Go straight to the workspace for this role.
  if (user) return <Navigate to={roleHome(user.role)} replace />;

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const u = await signIn(username.trim(), password);
      navigate(roleHome(u.role), { replace: true }); // ADMIN / FACULTY / STUDENT each get their own page
    } catch (err) {
      setError(err.status === 401 ? "Wrong username or password." : err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-full lg:grid-cols-[1.05fr_1fr]">
      {/* ---------- left: animated brand panel ---------- */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-brand via-brand-dark to-deep px-14 py-14 text-white lg:flex">
        <div aria-hidden="true" className="blob absolute -left-20 top-1/4 h-80 w-80 rounded-full bg-mint/30 blur-3xl" />
        <div aria-hidden="true" className="blob absolute -right-16 bottom-10 h-96 w-96 rounded-full bg-lilac/35 blur-3xl" style={{ "--d": "-9s" }} />
        <div aria-hidden="true" className="blob absolute bottom-1/3 left-1/3 h-48 w-48 rounded-full bg-sun/25 blur-3xl" style={{ "--d": "-4s" }} />

        <Link to="/" className="relative w-fit" aria-label="Back to home"><Logo light /></Link>

        <div className="relative">
          <div aria-hidden="true" className="float-slow glass-dark mb-10 grid w-72 grid-cols-5 gap-2 rounded-3xl p-4">
            {SAMPLE.map((n, i) => (
              <div key={i} className="wave h-9 rounded-lg" style={{
                "--i": i, background: n ? `hsl(${HUES[n]} 62% 86%)` : "rgb(255 255 255 / 0.14)" }} />
            ))}
          </div>
          <h2 className="rise font-display text-4xl font-bold leading-tight" style={{ "--i": 1 }}>
            Every class in its place,<br />no clashes.
          </h2>
          <p className="rise mt-4 max-w-md text-lg text-white/75" style={{ "--i": 2 }}>
            Sign in to see your week, or to build the next term's timetable.
          </p>
          <div className="rise mt-8 flex flex-wrap gap-2" style={{ "--i": 3 }}>
            {[["grid", "Admin"], ["teach", "Faculty"], ["book", "Student"]].map(([ic, t]) => (
              <span key={t} className="glass-dark inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium">
                <Icon name={ic} size={16} /> {t}
              </span>
            ))}
          </div>
        </div>
        <div className="relative text-sm text-white/50">&copy; {new Date().getFullYear()} Timetable</div>
      </div>

      {/* ---------- right: form ---------- */}
      <div className="relative flex flex-col bg-gradient-to-b from-[#eef7f7] to-paper px-6 py-8 sm:px-12">
        <div aria-hidden="true" className="blob pointer-events-none absolute right-0 top-0 h-64 w-64 rounded-full bg-mint/20 blur-3xl lg:hidden" />
        <div className="relative flex items-center justify-between">
          <Link to="/" className="lg:hidden" aria-label="Back to home"><Logo size={28} /></Link>
          <Link to="/" className="ml-auto inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft transition hover:text-brand">
            <Icon name="home" size={16} /> Back to home
          </Link>
        </div>

        <div className="relative flex flex-1 items-center justify-center py-10">
          <form onSubmit={submit} noValidate
            className="rise glass w-full max-w-md space-y-5 rounded-3xl p-8 shadow-2xl shadow-brand/10 sm:p-10">
            <div>
              <h1 className="font-display text-3xl font-bold tracking-tight">Welcome back</h1>
              <p className="mt-1.5 text-ink-soft">Sign in to open your workspace.</p>
            </div>

            {error && <Alert>{error}</Alert>}

            <div>
              <label htmlFor="username" className="mb-1.5 block text-sm font-medium">Username</label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-soft"><Icon name="user" size={18} /></span>
                <input id="username" className={field} placeholder="Enter your username" autoComplete="username" autoFocus required
                  value={username} onChange={(e) => setUsername(e.target.value)} />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium">Password</label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-soft"><Icon name="lock" size={18} /></span>
                <input id="password" type={show ? "text" : "password"} className={`${field} pr-12`} placeholder="Enter your password"
                  autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
                <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? "Hide password" : "Show password"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-2 text-ink-soft transition hover:bg-brand-tint hover:text-brand">
                  <Icon name={show ? "eyeOff" : "eye"} size={18} />
                </button>
              </div>
            </div>

            <button type="submit" disabled={busy || !username || !password}
              className="shine inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3.5 font-semibold text-white shadow-lg shadow-brand/30 transition hover:-translate-y-0.5 hover:bg-brand-dark disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60">
              {busy ? <><Spinner /> Signing in</> : <>Sign in <Icon name="arrow" size={18} /></>}
            </button>

            <p className="text-center text-sm text-ink-soft">
              You'll land on your Admin, Faculty or Student page automatically.<br />
              Forgot your password? Ask an Admin to create a new login.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}