import { useAuth } from "../auth";
import Icon from "../components/Icon";
import { ROLE_TEXT } from "../lib/roles";
import TimetableView from "./TimetableView";

const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
};

/** Landing page for Faculty (/faculty) and Student (/student): a welcome banner + their own timetable. */
export default function RoleHome() {
  const { user } = useAuth();
  const isFaculty = user.role === "FACULTY";
  return (
    <div className="mx-auto max-w-6xl">
      <div className="rise relative mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand via-brand-dark to-deep p-6 text-white sm:p-8">
        <div aria-hidden="true" className="blob absolute -right-10 -top-10 h-48 w-48 rounded-full bg-lilac/40 blur-3xl" />
        <div aria-hidden="true" className="blob absolute -bottom-12 left-1/3 h-40 w-40 rounded-full bg-mint/30 blur-3xl" style={{ "--d": "-6s" }} />
        <div className="relative flex items-center justify-between gap-4">
          <div>
            <span className="glass-dark inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold">
              <Icon name={isFaculty ? "teach" : "book"} size={14} /> {ROLE_TEXT[user.role]} workspace
            </span>
            <h1 className="mt-3 font-display text-2xl font-bold sm:text-3xl">{greeting()}, {user.username}</h1>
            <p className="mt-1 text-white/75">
              {isFaculty ? "Here are the classes you teach this term." : "Here are the courses you are enrolled in this term."}
            </p>
          </div>
          <div aria-hidden="true" className="float hidden h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-white/15 sm:flex">
            <Icon name="clock" size={30} />
          </div>
        </div>
      </div>
      <TimetableView mode="mine" />
    </div>
  );
}