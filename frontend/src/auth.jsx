import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as api from "./api/client";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => api.loadAuth()?.user || null);
  const [checking, setChecking] = useState(() => Boolean(api.loadAuth()));

  const signOut = useCallback(() => {
    api.clearAuth();
    setUser(null);
  }, []);

  useEffect(() => {
    api.setOnSessionEnd(() => setUser(null));
    if (!api.loadAuth()) return;
    // A stored session may be stale: ask the server who we are.
    api.me()
      .then((fresh) => {
        api.saveAuth({ ...api.loadAuth(), user: fresh });
        setUser(fresh);
      })
      .catch((err) => { if (err.status === 401 || err.status === 403) signOut(); })
      .finally(() => setChecking(false));
  }, [signOut]);

  const signIn = useCallback(async (username, password) => {
    const u = await api.login(username, password);
    setUser(u);
    return u;
  }, []);

  const value = useMemo(() => ({ user, checking, signIn, signOut }), [user, checking, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
