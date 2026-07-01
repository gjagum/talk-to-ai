import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../lib/auth';

/**
 * ProtectedRoute — gate a route element behind authentication (and optionally
 * an RBAC permission). While auth state is still hydrating we render a small
 * spinner instead of redirecting, otherwise a hard refresh on /management
 * with a valid token in localStorage would flash the login page.
 *
 * Unauthorized (logged in but missing the permission) renders an inline
 * "access denied" card rather than bouncing to /login — the user IS signed in,
 * they just can't see this page.
 */
export default function ProtectedRoute({ children, permission = null }) {
  const { user, loading, hasPermission } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        Checking session…
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (permission && !hasPermission(permission)) {
    return (
      <div className="glass-panel rounded-2xl p-8 text-center">
        <h2 className="text-xl font-bold text-slate-100 mb-2">Access denied</h2>
        <p className="text-slate-400 text-sm">
          Your account doesn&apos;t have the <code className="text-amber-300">{permission}</code> permission.
        </p>
      </div>
    );
  }

  return children;
}
