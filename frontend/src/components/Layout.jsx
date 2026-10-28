import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { roleHome, ROLE_TEXT } from "../lib/roles";
import Logo from "./Logo";

const ADMIN_NAV = [
  { to: "/admin", text: "Data setup" },
  { to: "/generate", text: "Generate" },
  { to: "/timetable", text: "Full timetable" },
  { to: "/users", text: "Logins" },
];

/** Top navbar for every role: logo, page links, who is signed in, Sign out. */
export default function Layout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const nav = user.role === "ADMIN" ? ADMIN_NAV : [{ to: roleHome(user.role), text: "My timetable" }];
  const link = ({ isActive }) =>
    `whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition ${isActive ? "bg-brand text-white shadow-sm" : "text-ink hover:bg-brand-tint"}`;

  function leave() {
    signOut();
    navigate("/", { replace: true });
  }

  return (
    <div className="min-h-full bg-paper">
      <header className="sticky top-0 z-20 border-b border-line bg-surface/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <Link to={roleHome(user.role)} aria-label="Home"><Logo size={26} /></Link>
          <nav aria-label="Main" className="ml-4 hidden gap-1 md:flex">
            {nav.map((n) => <NavLink key={n.to} to={n.to} className={link}>{n.text}</NavLink>)}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <div className="max-w-40 truncate text-sm font-medium">{user.username}</div>
              <div className="text-xs text-ink-soft">{ROLE_TEXT[user.role]}</div>
            </div>
            <span aria-hidden="true" className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-tint font-semibold uppercase text-brand-dark">
              {user.username?.[0]}
            </span>
            <button type="button" onClick={leave}
              className="rounded-md border border-line px-3 py-2 text-sm font-medium transition hover:border-bad hover:text-bad">Sign out</button>
          </div>
        </div>
        <nav aria-label="Main (mobile)" className="flex gap-1 overflow-x-auto px-3 pb-2 md:hidden">
          {nav.map((n) => <NavLink key={n.to} to={n.to} className={link}>{n.text}</NavLink>)}
        </nav>
      </header>
      <main className="min-w-0 p-4 md:p-8"><Outlet /></main>
    </div>
  );
}