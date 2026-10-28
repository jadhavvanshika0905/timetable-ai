import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import Icon from "../components/Icon";
import Logo from "../components/Logo";
import { roleHome } from "../lib/roles";

/* ------------------------------------------------------------------ data */
const NAV = [
  ["Home", "top"],
  ["Features", "features"],
  ["How it works", "how"],
  ["Roles", "roles"],
];

const FEATURES = [
  { icon: "shield", h: 172, t: "Clash-free by design", d: "A constraint solver places every class so no teacher, room or student group is ever double-booked." },
  { icon: "chart", h: 262, t: "Demand forecasting", d: "ML estimates next term's enrolment from past terms, so rooms are sized before the rush, not after." },
  { icon: "scale", h: 24, t: "Faculty workload balance", d: "Flags overloaded teachers early with a LOW / MEDIUM / HIGH risk score and spreads the load fairly." },
  { icon: "flask", h: 340, t: "Labs in consecutive blocks", d: "Lab courses get back-to-back periods in the right kind of room, automatically." },
  { icon: "clock", h: 205, t: "Availability & preferences", d: "Mark slots as unavailable, avoid or preferred. Hard rules come first, soft wishes are honoured where possible." },
  { icon: "eye", h: 48, t: "Your own view, anytime", d: "Admins see everything. Faculty and students see only their own week, with CSV download." },
];

const STEPS = [
  { n: "01", t: "Add your institution", d: "Departments, faculty, rooms, courses and student choices. NEP 2020 course types are built in." },
  { n: "02", t: "Generate with AI", d: "Pick a term and press Generate. ML hints guide the solver towards a balanced, clash-free week." },
  { n: "03", t: "Everyone sees their week", d: "Faculty and students sign in to their own page. Admins review, filter and export the full timetable." },
];

const ROLES = [
  { icon: "grid", name: "Admin", color: "#0e5d63", points: ["Generate timetables per term", "Review the full grid, filter by faculty, room or course", "Create logins for faculty and students"] },
  { icon: "teach", name: "Faculty", color: "#7c6cf0", points: ["See only your own classes", "Week grid or day-by-day list", "Download your schedule as CSV"] },
  { icon: "book", name: "Student", color: "#f0645a", points: ["See only the courses you enrolled in", "Clean weekly view on any device", "Always the latest published timetable"] },
];

const TAGS = ["Major", "Minor", "Skill-Based", "Value-Added", "Lab blocks", "Room capacity", "Faculty preferences",
  "Workload risk", "Demand forecast", "No double-booking", "CSV export", "Role-based access"];

// A sample week for the hero card. d = day (0 Mon), p = period (0 first), s = rows spanned.
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const BLOCKS = [
  { d: 0, p: 0, c: "CS101", h: 172 }, { d: 0, p: 2, c: "MA201", h: 262 },
  { d: 1, p: 1, c: "PHY Lab", h: 24, s: 2 }, { d: 1, p: 4, c: "EN105", h: 340 },
  { d: 2, p: 0, c: "CS101", h: 172 }, { d: 2, p: 3, c: "DS301", h: 205 },
  { d: 3, p: 0, c: "MA201", h: 262 }, { d: 3, p: 2, c: "CS Lab", h: 48, s: 2 },
  { d: 4, p: 1, c: "DS301", h: 205 }, { d: 4, p: 3, c: "EN105", h: 340 },
  { d: 5, p: 0, c: "PHY", h: 24 }, { d: 5, p: 2, c: "CS101", h: 172 },
];

/* ----------------------------------------------------------------- hooks */
function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll("[data-reveal],[data-line]");
    if (!("IntersectionObserver" in window)) { els.forEach((e) => e.classList.add("is-in")); return; }
    const io = new IntersectionObserver((entries) => entries.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); }
    }), { threshold: 0.15 });
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, []);
}

function useActiveSection(ids) {
  const [active, setActive] = useState(ids[0]);
  useEffect(() => {
    const io = new IntersectionObserver((entries) => entries.forEach((en) => {
      if (en.isIntersecting) setActive(en.target.id);
    }), { rootMargin: "-40% 0px -55% 0px" });
    ids.forEach((id) => { const el = document.getElementById(id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, [ids]);
  return active;
}

function Counter({ to, suffix = "" }) {
  const ref = useRef(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    const el = ref.current;
    let raf;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const t0 = performance.now();
      const tick = (t) => {
        const p = Math.min(1, (t - t0) / 1300);
        setN(Math.round(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }, { threshold: 0.6 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [to]);
  return <span ref={ref}>{n}{suffix}</span>;
}

/* ---------------------------------------------------------------- navbar */
function Navbar() {
  const { user } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const active = useActiveSection(NAV.map(([, id]) => id));

  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 24);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);

  const cta = user
    ? <Link to={roleHome(user.role)} className="shine rounded-full bg-brand px-5 py-2 text-sm font-semibold text-white transition hover:bg-brand-dark">Open dashboard</Link>
    : <Link to="/login" className="shine inline-flex items-center gap-1.5 rounded-full bg-brand px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:-translate-y-0.5 hover:bg-brand-dark">
        Login <Icon name="arrow" size={16} />
      </Link>;

  return (
    <header className="fixed inset-x-0 top-4 z-50 flex justify-center px-4">
      <div className="w-full max-w-3xl">
        <nav aria-label="Primary"
          className={`glass flex items-center justify-between rounded-full py-2 pl-5 pr-2 transition-all duration-500 ${scrolled ? "shadow-2xl shadow-brand/15" : "shadow-lg shadow-brand/5"}`}>
          <a href="#top" aria-label="Timetable home"><Logo size={28} /></a>
          <ul className="hidden items-center gap-1 md:flex">
            {NAV.map(([text, id]) => (
              <li key={id}>
                <a href={`#${id}`}
                  className={`rounded-full px-3.5 py-2 text-sm font-medium transition ${active === id ? "bg-brand-tint text-brand" : "text-ink-soft hover:text-brand"}`}>
                  {text}
                </a>
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2">
            {cta}
            <button type="button" className="rounded-full p-2 text-ink md:hidden" aria-label="Menu" aria-expanded={open}
              onClick={() => setOpen((v) => !v)}>
              <Icon name={open ? "close" : "menu"} />
            </button>
          </div>
        </nav>
        {open && (
          <div className="glass rise mt-2 rounded-3xl p-3 shadow-xl md:hidden">
            {NAV.map(([text, id]) => (
              <a key={id} href={`#${id}`} onClick={() => setOpen(false)}
                className="block rounded-2xl px-4 py-3 text-sm font-medium text-ink hover:bg-brand-tint">{text}</a>
            ))}
          </div>
        )}
      </div>
    </header>
  );
}

/* ------------------------------------------------------------- hero card */
function TimetableMock() {
  return (
    <div className="glass relative rounded-3xl p-4 shadow-2xl shadow-brand/20 sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          <span className="relative flex h-2.5 w-2.5">
            <span className="ring absolute inline-flex h-full w-full rounded-full bg-mint" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-mint" />
          </span>
          Sample week
        </div>
        <span className="rounded-full bg-good-tint px-2.5 py-1 text-xs font-semibold text-good">OPTIMAL</span>
      </div>
      <div className="grid gap-1.5" style={{ gridTemplateColumns: "1.6rem repeat(6, minmax(0, 1fr))", gridTemplateRows: "1.4rem repeat(5, 2.5rem)" }}>
        {DAYS.map((d, i) => (
          <div key={d} style={{ gridColumn: i + 2, gridRow: 1 }} className="text-center text-[10px] font-semibold uppercase tracking-wide text-ink-soft">{d}</div>
        ))}
        {[1, 2, 3, 4, 5].map((p) => (
          <div key={p} style={{ gridColumn: 1, gridRow: p + 1 }} className="flex items-center text-[10px] font-medium text-ink-soft">P{p}</div>
        ))}
        {DAYS.flatMap((_, d) => [0, 1, 2, 3, 4].map((p) => (
          <div key={`${d}-${p}`} style={{ gridColumn: d + 2, gridRow: p + 2 }} className="rounded-md bg-brand/[0.045]" />
        )))}
        {BLOCKS.map((b, i) => (
          <div key={i} className="pop flex items-center justify-center rounded-md px-1 text-center text-[10px] font-semibold leading-tight sm:text-[11px]"
            style={{
              "--i": i, gridColumn: b.d + 2, gridRow: `${b.p + 2} / span ${b.s || 1}`,
              background: `hsl(${b.h} 62% 90%)`, color: `hsl(${b.h} 55% 24%)`, borderLeft: `3px solid hsl(${b.h} 55% 45%)`,
            }}>
            {b.c}
          </div>
        ))}
      </div>
    </div>
  );
}

function Chip({ children, className = "", delay = "0s", icon = "check", tone = "text-mint" }) {
  return (
    <div className={`float glass absolute flex items-center gap-2 rounded-2xl px-3.5 py-2.5 text-xs font-semibold text-ink shadow-xl shadow-brand/10 ${className}`}
      style={{ "--d": delay }}>
      <span className={`flex h-6 w-6 items-center justify-center rounded-full bg-white ${tone}`}><Icon name={icon} size={14} stroke={2.4} /></span>
      {children}
    </div>
  );
}

function Hero() {
  const ref = useRef(null);
  const { user } = useAuth();
  const move = (e) => {
    const r = ref.current.getBoundingClientRect();
    ref.current.style.setProperty("--mx", ((e.clientX - r.left) / r.width - 0.5).toFixed(3));
    ref.current.style.setProperty("--my", ((e.clientY - r.top) / r.height - 0.5).toFixed(3));
  };
  const par = (k) => ({ transform: `translate(calc(var(--mx, 0) * ${k}px), calc(var(--my, 0) * ${k}px))`, transition: "transform .25s ease-out" });
  const words = ["Timetables", "that"];
  const words2 = ["build", "themselves."];

  return (
    <section id="top" ref={ref} onMouseMove={move} className="relative isolate overflow-hidden px-5 pb-24 pt-36 sm:pt-40">
      {/* animated background */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-[#eaf6f6] via-paper to-paper" />
      <div aria-hidden="true" className="dots pointer-events-none absolute inset-0 -z-10" />
      <div aria-hidden="true" className="blob pointer-events-none absolute -left-24 top-10 -z-10 h-80 w-80 rounded-full bg-mint/30 blur-3xl" />
      <div aria-hidden="true" className="blob pointer-events-none absolute right-0 top-0 -z-10 h-96 w-96 rounded-full bg-lilac/25 blur-3xl" style={{ "--d": "-6s" }} />
      <div aria-hidden="true" className="blob pointer-events-none absolute bottom-0 left-1/3 -z-10 h-72 w-72 rounded-full bg-sun/25 blur-3xl" style={{ "--d": "-11s" }} />

      <div className="mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-[1.05fr_1fr]">
        <div>
          <div className="rise glass inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-semibold text-brand" style={{ "--i": 0 }}>
            <Icon name="spark" size={14} /> AI-powered scheduling for NEP 2020 campuses
          </div>
          <h1 className="mt-6 font-display text-5xl font-bold leading-[1.05] tracking-tight text-ink sm:text-6xl lg:text-7xl">
            <span className="block">
              {words.map((w, i) => <span key={w} className="rise mr-3 inline-block" style={{ "--i": i + 1 }}>{w}</span>)}
            </span>
            <span className="block">
              {words2.map((w, i) => <span key={w} className={`rise mr-3 inline-block ${i ? "text-gradient" : ""}`} style={{ "--i": i + 3 }}>{w}</span>)}
            </span>
          </h1>
          <p className="rise mt-6 max-w-xl text-lg leading-relaxed text-ink-soft" style={{ "--i": 5 }}>
            Add your faculty, rooms and courses. A constraint solver and ML models craft a clash-free week for every
            teacher and every student, without the spreadsheet marathon.
          </p>
          <div className="rise mt-9 flex flex-wrap items-center gap-3" style={{ "--i": 6 }}>
            <Link to={user ? roleHome(user.role) : "/login"}
              className="shine inline-flex items-center gap-2 rounded-full bg-brand px-7 py-3.5 font-semibold text-white shadow-xl shadow-brand/30 transition hover:-translate-y-0.5 hover:bg-brand-dark">
              {user ? "Open dashboard" : "Get started"} <Icon name="arrow" size={18} />
            </Link>
            <a href="#how" className="glass inline-flex items-center gap-2 rounded-full px-7 py-3.5 font-semibold text-ink transition hover:-translate-y-0.5">
              See how it works
            </a>
          </div>
          <div className="rise mt-10 flex items-center gap-4 text-sm text-ink-soft" style={{ "--i": 7 }}>
            <div className="flex -space-x-2" aria-hidden="true">
              {["#0e5d63", "#7c6cf0", "#f0645a"].map((c) => <span key={c} className="h-8 w-8 rounded-full border-2 border-white" style={{ background: c }} />)}
            </div>
            One platform, three portals: Admin, Faculty and Student.
          </div>
        </div>

        <div className="relative mx-auto w-full max-w-xl pb-6 pt-4">
          <div style={par(-14)}><div className="float-slow"><TimetableMock /></div></div>
          <div style={par(22)} className="absolute -left-3 top-2 sm:-left-8"><Chip delay="-1s">0 clashes</Chip></div>
          <div style={par(30)} className="absolute -right-2 top-1/3 sm:-right-8"><Chip delay="-3s" icon="chart" tone="text-lilac">Demand forecast ready</Chip></div>
          <div style={par(18)} className="absolute -bottom-2 left-6 sm:left-2"><Chip delay="-2s" icon="scale" tone="text-sun">Faculty load balanced</Chip></div>
        </div>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- sections */
function Marquee() {
  const items = [...TAGS, ...TAGS];
  return (
    <div className="marquee overflow-hidden border-y border-line bg-surface py-4" aria-hidden="true">
      <div className="marquee-track">
        {items.map((t, i) => (
          <span key={i} className="mx-6 inline-flex items-center gap-6 whitespace-nowrap font-display text-lg font-semibold text-ink-soft">
            {t} <span className="h-1.5 w-1.5 rounded-full bg-sun" />
          </span>
        ))}
      </div>
    </div>
  );
}

function Stats() {
  const items = [
    { to: 0, label: "Faculty or room clashes" },
    { to: 3, label: "Role-based portals" },
    { to: 4, label: "NEP 2020 course types" },
    { to: 6, label: "Day teaching week" },
  ];
  return (
    <section className="mx-auto grid max-w-6xl grid-cols-2 gap-4 px-5 py-16 md:grid-cols-4">
      {items.map((s, i) => (
        <div key={s.label} data-reveal style={{ "--i": i }} className="rounded-2xl border border-line bg-surface p-6 text-center">
          <div className="font-display text-5xl font-bold text-brand"><Counter to={s.to} /></div>
          <div className="mt-2 text-sm text-ink-soft">{s.label}</div>
        </div>
      ))}
    </section>
  );
}

function SectionHead({ kicker, title, sub }) {
  return (
    <div data-reveal className="mx-auto mb-14 max-w-2xl text-center">
      <div className="text-sm font-semibold uppercase tracking-[0.18em] text-brand">{kicker}</div>
      <h2 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">{title}</h2>
      {sub && <p className="mt-4 text-lg text-ink-soft">{sub}</p>}
    </div>
  );
}

function Features() {
  return (
    <section id="features" className="mx-auto max-w-6xl px-5 py-20">
      <SectionHead kicker="Features" title="Everything a timetable needs, handled."
        sub="Built around how real campuses work: shared labs, busy faculty and elective-heavy student choices." />
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f, i) => (
          <article key={f.t} data-reveal style={{ "--i": i % 3 }} className="lift group rounded-2xl border border-line bg-surface p-7">
            <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl transition-transform duration-500 group-hover:rotate-6 group-hover:scale-110"
              style={{ background: `hsl(${f.h} 62% 91%)`, color: `hsl(${f.h} 55% 32%)` }}>
              <Icon name={f.icon} size={24} />
            </div>
            <h3 className="font-display text-xl font-bold">{f.t}</h3>
            <p className="mt-2 leading-relaxed text-ink-soft">{f.d}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function How() {
  return (
    <section id="how" className="relative overflow-hidden bg-deep px-5 py-24 text-white">
      <div aria-hidden="true" className="blob pointer-events-none absolute -right-20 -top-20 h-96 w-96 rounded-full bg-mint/20 blur-3xl" />
      <div aria-hidden="true" className="blob pointer-events-none absolute -bottom-24 -left-16 h-96 w-96 rounded-full bg-lilac/25 blur-3xl" style={{ "--d": "-8s" }} />
      <div className="relative mx-auto max-w-6xl">
        <div data-reveal className="mx-auto mb-16 max-w-2xl text-center">
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-mint">How it works</div>
          <h2 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">From raw data to a finished week in three steps.</h2>
        </div>
        <div className="relative grid gap-6 md:grid-cols-3">
          <div data-line aria-hidden="true" className="absolute left-[16%] right-[16%] top-8 hidden h-px bg-gradient-to-r from-mint via-lilac to-coral md:block" />
          {STEPS.map((s, i) => (
            <div key={s.n} data-reveal style={{ "--i": i }} className="glass-dark relative rounded-2xl p-7">
              <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-white font-display text-2xl font-bold text-brand shadow-lg">{s.n}</div>
              <h3 className="font-display text-xl font-bold">{s.t}</h3>
              <p className="mt-2 leading-relaxed text-white/75">{s.d}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Roles() {
  return (
    <section id="roles" className="mx-auto max-w-6xl px-5 py-24">
      <SectionHead kicker="Roles" title="One login, the right workspace."
        sub="Sign in once and you land on the page made for you. Nobody sees more than they should." />
      <div className="grid gap-5 md:grid-cols-3">
        {ROLES.map((r, i) => (
          <article key={r.name} data-reveal style={{ "--i": i }} className="lift relative overflow-hidden rounded-2xl border border-line bg-surface p-7">
            <div aria-hidden="true" className="absolute -right-10 -top-10 h-32 w-32 rounded-full opacity-15 blur-2xl" style={{ background: r.color }} />
            <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl text-white" style={{ background: r.color }}><Icon name={r.icon} size={24} /></div>
            <h3 className="font-display text-2xl font-bold">{r.name}</h3>
            <ul className="mt-4 space-y-2.5">
              {r.points.map((p) => (
                <li key={p} className="flex gap-2.5 text-ink-soft">
                  <span className="mt-0.5 shrink-0" style={{ color: r.color }}><Icon name="check" size={18} stroke={2.6} /></span>{p}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}

function Cta() {
  const { user } = useAuth();
  return (
    <section className="px-5 pb-24">
      <div data-reveal className="relative mx-auto max-w-6xl overflow-hidden rounded-3xl bg-gradient-to-br from-brand via-brand-dark to-deep px-8 py-16 text-center text-white">
        <div aria-hidden="true" className="blob absolute -left-10 top-0 h-60 w-60 rounded-full bg-mint/30 blur-3xl" />
        <div aria-hidden="true" className="blob absolute -right-10 bottom-0 h-60 w-60 rounded-full bg-lilac/40 blur-3xl" style={{ "--d": "-7s" }} />
        <div className="relative">
          <h2 className="mx-auto max-w-2xl font-display text-4xl font-bold tracking-tight sm:text-5xl">Ready to retire the timetable spreadsheet?</h2>
          <p className="mx-auto mt-4 max-w-xl text-lg text-white/80">Sign in with the login your admin created for you.</p>
          <Link to={user ? roleHome(user.role) : "/login"}
            className="shine mt-8 inline-flex items-center gap-2 rounded-full bg-white px-8 py-3.5 font-semibold text-brand shadow-xl transition hover:-translate-y-0.5">
            {user ? "Open dashboard" : "Login to continue"} <Icon name="arrow" size={18} />
          </Link>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-line bg-surface px-5 py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
        <Logo size={26} />
        <nav aria-label="Footer" className="flex gap-6 text-sm text-ink-soft">
          {NAV.map(([t, id]) => <a key={id} href={`#${id}`} className="hover:text-brand">{t}</a>)}
          <Link to="/login" className="hover:text-brand">Login</Link>
        </nav>
        <p className="text-sm text-ink-soft">&copy; {new Date().getFullYear()} Timetable. Built for institutions.</p>
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------------- page */
export default function Landing() {
  useReveal();
  return (
    <div className="min-h-full overflow-x-hidden">
      <Navbar />
      <main>
        <Hero />
        <Marquee />
        <Stats />
        <Features />
        <How />
        <Roles />
        <Cta />
      </main>
      <Footer />
    </div>
  );
}