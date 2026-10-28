// One place that decides where each role lands after signing in.
export const ROLE_HOME = {
  ADMIN: "/admin",   // admin workspace
  FACULTY: "/faculty",  // faculty workspace
  STUDENT: "/student",  // student workspace
};

export const roleHome = (role) => ROLE_HOME[role] || "/admin";
export const ROLE_TEXT = { ADMIN: "Admin", FACULTY: "Faculty", STUDENT: "Student" };