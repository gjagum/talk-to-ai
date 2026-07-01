import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiGet, apiPost, getToken, setToken } from './api';

/**
 * AuthContext — thin wrapper around the JWT stored in localStorage.
 *
 * On mount, if a token exists we probe `/api/auth/me` to (a) validate it and
 * (b) load the user's flattened permissions. A 401 clears the token, so a
 * stale/expired JWT degrades gracefully to the logged-out state without
 * trapping the user on a broken page.
 *
 * Components consume via `useAuth()`:
 *   const { user, permissions, login, logout, authedFetch } = useAuth();
 * `hasPermission('agent:update')` covers the RBAC gate inside protected pages.
 */

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [loading, setLoading] = useState(true);

  // Hydrate from a stored token on first paint. We don't block the whole app,
  // but `loading` lets ProtectedRoute show a spinner instead of flapping route.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = getToken();
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const me = await apiGet('/auth/me', { auth: true });
        if (cancelled) return;
        setUser(me);
        setPermissions(me.permissions || []);
      } catch {
        if (cancelled) return;
        setToken(null);
        setUser(null);
        setPermissions([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const { access_token, user: u } = await apiPost('/auth/login', { email, password });
    setToken(access_token);
    setUser(u);
    setPermissions(u.permissions || []);
    return u;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setPermissions([]);
  }, []);

  const hasPermission = useCallback(
    (perm) => {
      if (!user) return false;
      if (user.is_superuser) return true;
      return permissions.includes(perm);
    },
    [user, permissions]
  );

  const value = useMemo(
    () => ({ user, permissions, loading, login, logout, hasPermission }),
    [user, permissions, loading, login, logout, hasPermission]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}

/**
 * Hook for permission scoping in a page. Returns true while we know the user
 * lacks the permission (so a page can render an "access denied" panel without
 * a flicker once `loading` flips).
 */
export function useCan(permission) {
  const { hasPermission, loading } = useAuth();
  return { can: hasPermission(permission), loading };
}
