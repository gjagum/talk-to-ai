import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Loader2, Lock } from 'lucide-react';
import { useAuth } from '../lib/auth';

/**
 * LoginPage — email + password form posting to /api/auth/login via the
 * AuthProvider. Redirects back to the route the user was trying to reach
 * (ProtectedRoute passes `state.from`). Public route.
 */
export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || '/management';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="w-full max-w-md">
      <form onSubmit={onSubmit} className="glass-panel rounded-3xl p-8">
        <h2 className="text-xl font-bold text-slate-100 mb-1 flex items-center gap-2">
          <Lock className="w-5 h-5 text-blue-400" />
          Sign in
        </h2>
        <p className="text-slate-400 text-sm mb-6">
          Admin access required for Agent &amp; Tool management.
        </p>

        <label className="block text-slate-300 font-medium mb-2 text-sm" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="w-full bg-slate-800/50 border border-slate-700 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all mb-4"
          placeholder="you@example.com"
        />

        <label className="block text-slate-300 font-medium mb-2 text-sm" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="w-full bg-slate-800/50 border border-slate-700 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all mb-6"
          placeholder="••••••••"
        />

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 text-red-200 px-4 py-3 text-sm mb-4">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white font-medium rounded-xl py-3 transition-colors"
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
