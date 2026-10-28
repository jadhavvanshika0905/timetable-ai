
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import * as ad from "../api/adminData";
import { useAuth } from "../auth";
import { Alert, Spinner } from "../components/Bits";
import Icon from "../components/Icon";
import { card } from "../lib/ui";
import { CFG, ORDER } from "../lib/adminConfig";

/** Admin landing page (/admin): one tile per kind of data, each with Add / Upload / View. */
const greeting = () => {
  const h = new Date().getHours();
  return h < 12
    ? "Good morning"
    : h < 17
      ? "Good afternoon"
      : "Good evening";
};

export default function AdminHome() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const [s, setS] = useState(null);
  const [err, setErr] = useState("");

  async function handleSignOut() {
    try {
      await signOut();
      navigate("/login", { replace: true });
    } catch (e) {
      setErr(e.message || "Unable to sign out. Please try again.");
    }
  }

  useEffect(() => {
    ad.summary()
      .then(setS)
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="mx-auto max-w-6xl">
      {/* Admin workspace banner */}
      <div className="relative mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand via-brand-dark to-deep p-6 text-white sm:p-8">
        <div
          aria-hidden="true"
          className="blob absolute -right-10 -top-10 h-48 w-48 rounded-full bg-lilac/40 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="blob absolute -bottom-12 left-1/3 h-40 w-40 rounded-full bg-mint/30 blur-3xl"
          style={{ "--d": "-6s" }}
        />

        <div className="relative">
          {/* Top row: workspace label and Sign out */}
          <div className="flex items-center justify-between gap-3">
            <span className="glass-dark inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold">
              <Icon name="grid" size={14} />
              Admin workspace
            </span>

            <button
              type="button"
              onClick={handleSignOut}
              className="glass-dark inline-flex shrink-0 items-center gap-2 rounded-xl border border-white/20 px-3 py-2 text-sm font-semibold text-white transition hover:border-red-200/50 hover:bg-red-500/20"
            >
              <Icon name="logout" size={16} />
              Sign out
            </button>
          </div>

          <h1 className="mt-3 font-display text-2xl font-bold sm:text-3xl">
            {greeting()}, {user.username}
          </h1>

          <p className="mt-1 max-w-xl text-white/75">
            Add your college data below, then build the timetable. Faculty and
            students see it as soon as it is saved.
          </p>

          <div className="mt-5 flex flex-wrap gap-3">
            <a
              href="#data-tiles"
              className="shine inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-brand-dark"
            >
              Add data
            </a>

            <Link
              to="/generate"
              className="glass-dark inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold"
            >
              Generate timetable
              <Icon name="arrow" size={16} />
            </Link>

            <Link
              to="/timetable"
              className="glass-dark inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold"
            >
              View timetable
            </Link>
          </div>
        </div>
      </div>

      {err && <Alert>{err}</Alert>}

      {!s && !err && (
        <p className="flex items-center gap-2 text-sm text-ink-soft">
          <Spinner />
          Loading
        </p>
      )}

      {s && (
        <section
          className={`${card} mb-6 p-5`}
          aria-labelledby="ready-h"
        >
          <h2 id="ready-h" className="font-display text-lg font-semibold">
            Is your data ready?
          </h2>

          <p className="mt-1 text-sm text-ink-soft">
            Active term:{" "}
            <span className="font-medium text-ink">
              {s.active_term?.name || "none yet"}
            </span>
          </p>

          {s.warnings.length > 0 ? (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-bad">
              {s.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : (
            s.ready && (
              <div className="mt-3">
                <Alert kind="success">
                  Data looks complete. You can generate the timetable.
                </Alert>
              </div>
            )
          )}
        </section>
      )}

      <p className="mb-3 text-sm text-ink-soft">
        Set up in this order, top to bottom. Many records? Use "Upload file"
        with an Excel or CSV sheet.
      </p>

      <div
        id="data-tiles"
        className="grid scroll-mt-20 gap-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        {ORDER.map((id) => {
          const c = CFG[id];
          const count = s?.counts?.[id];

          return (
            <div
              key={id}
              className={`${card} flex flex-col p-5`}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-tint text-brand-dark">
                  <Icon name={c.icon} size={20} />
                </span>

                {count != null && (
                  <span className="font-display text-3xl font-bold tabular-nums">
                    {count}
                  </span>
                )}
              </div>

              <h3 className="mt-3 font-display text-lg font-semibold">
                {c.label}
              </h3>

              <p className="mt-1 flex-1 text-sm text-ink-soft">
                {c.blurb}
              </p>

              <div className="mt-4 flex flex-wrap gap-2 text-sm font-medium">
                {!c.uploadOnly && (
                  <Link
                    to={`/admin/${id}?tab=add`}
                    className="rounded-md bg-brand px-3 py-1.5 text-white hover:bg-brand-dark"
                  >
                    Add
                  </Link>
                )}

                <Link
                  to={`/admin/${id}?tab=upload`}
                  className="rounded-md border border-line px-3 py-1.5 hover:bg-paper"
                >
                  Upload file
                </Link>

                {!c.uploadOnly && (
                  <Link
                    to={`/admin/${id}?tab=list`}
                    className="rounded-md border border-line px-3 py-1.5 hover:bg-paper"
                  >
                    View list
                  </Link>
                )}
              </div>
            </div>
          );
        })}

        {/* Logins card */}
        <div className={`${card} flex flex-col p-5`}>
          <h3 className="font-display text-lg font-semibold">
            Logins
          </h3>

          <p className="mt-1 flex-1 text-sm text-ink-soft">
            Give faculty and students a username and password.
          </p>

          <div className="mt-4">
            <Link
              to="/users"
              className="rounded-md border border-line px-3 py-1.5 text-sm font-medium hover:bg-paper"
            >
              Create a login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
