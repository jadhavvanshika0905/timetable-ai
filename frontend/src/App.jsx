import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import { Spinner } from "./components/Bits";
import { roleHome } from "./lib/roles";
import Generate from "./pages/Generate";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import RoleHome from "./pages/RoleHome";
import TimetableView from "./pages/TimetableView";
import Users from "./pages/Users";
import AdminHome from "./pages/AdminHome";
import AdminEntity from "./pages/AdminEntity";



/** Only let the listed roles in; everyone else goes to their own home. */
function Guard({ roles, children }) {
  const { user, checking } = useAuth();
  if (checking) return <div className="flex h-full items-center justify-center text-ink-soft"><Spinner size={24} /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={roleHome(user.role)} replace />;
  return children;
}

/** Old /my links keep working: send the user to their own role page. */
function MyRedirect() {
  const { user } = useAuth();
  return <Navigate to={roleHome(user.role)} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route element={<Guard roles={["ADMIN", "FACULTY", "STUDENT"]}><Layout /></Guard>}>
        {/* Admin */}
        <Route path="/generate" element={<Guard roles={["ADMIN"]}><Generate /></Guard>} />
        <Route path="/timetable" element={<Guard roles={["ADMIN"]}><TimetableView mode="all" /></Guard>} />
        <Route path="/users" element={<Guard roles={["ADMIN"]}><Users /></Guard>} />
        {/* Faculty + Student each get their own page */}
        <Route path="/faculty" element={<Guard roles={["FACULTY"]}><RoleHome /></Guard>} />
        <Route path="/student" element={<Guard roles={["STUDENT"]}><RoleHome /></Guard>} />
        <Route path="/my" element={<MyRedirect />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
      <Route path="/admin" element={<Guard roles={["ADMIN"]}><AdminHome /></Guard>} />
      <Route path="/admin/:resource" element={<Guard roles={["ADMIN"]}><AdminEntity /></Guard>} />
    </Routes>
  );
}