import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Waves, LayoutDashboard, CalendarDays, UtensilsCrossed, Settings, LogOut } from 'lucide-react';
import { useAuth } from '../lib/auth';

/**
 * Nav — top-of-page router links. Visible on every route.
 *
 * The "Management" link is only shown when the current user can read agents,
 * which is the minimum scope of the management page. The public demo routes
 * (Talk / Drive-Thru / Bookings) are always available.
 */
const LINKS = [
  { to: '/', label: 'Home', icon: LayoutDashboard, end: true },
  { to: '/bookings', label: 'Bookings', icon: CalendarDays },
  { to: '/drive-thru', label: 'Drive-Thru', icon: UtensilsCrossed },
];

export default function Nav() {
  const { user, logout, hasPermission } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <header className="mb-10 text-center relative z-10">
      <div className="inline-flex items-center justify-center p-3 bg-slate-800/50 rounded-2xl mb-4 border border-slate-700/50 shadow-lg backdrop-blur-sm">
        <Waves className="w-8 h-8 text-blue-400" />
      </div>
      <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
        Talk to AI
      </h1>
      <p className="text-slate-400 font-medium">Pick a voice mode and start talking</p>

      <nav className="mt-6 flex flex-wrap items-center justify-center gap-2">
        {LINKS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all ${
                isActive
                  ? 'bg-slate-700/70 text-white shadow-inner'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}

        {hasPermission('agent:read') && (
          <NavLink
            to="/management"
            className={({ isActive }) =>
              `flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all ${
                isActive
                  ? 'bg-slate-700/70 text-white shadow-inner'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`
            }
          >
            <Settings className="w-4 h-4" />
            Management
          </NavLink>
        )}
      </nav>

      {user && (
        <div className="mt-4 flex items-center justify-center gap-3 text-sm text-slate-400">
          <span className="text-slate-500">
            Signed in as <span className="text-slate-200">{user.email}</span>
          </span>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1 text-slate-300 hover:text-white border border-slate-700 hover:border-slate-600 rounded-lg px-2 py-1 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign out
          </button>
        </div>
      )}
    </header>
  );
}
