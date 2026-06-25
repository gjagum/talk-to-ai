import React from 'react';
import { Trash2, Clock, Mail, Phone, MapPin, User, Tag } from 'lucide-react';

const STATUS_STYLES = {
  pending: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  confirmed: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  cancelled: 'bg-red-500/15 text-red-300 border-red-500/30',
  completed: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
};

const NEXT_STATUSES = {
  pending: 'confirmed',
  confirmed: 'completed',
  completed: null,
  cancelled: null,
};

function formatLocal(iso, timezone) {
  try {
    const dt = new Date(iso);
    return dt.toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: timezone || undefined,
    });
  } catch {
    return iso;
  }
}

export default function BookingList({ bookings, onAdvance, loading }) {
  if (loading && bookings.length === 0) {
    return (
      <div className="glass-panel rounded-2xl p-8 text-center text-slate-400">
        Loading bookings…
      </div>
    );
  }

  if (bookings.length === 0) {
    return (
      <div className="glass-panel rounded-2xl p-8 text-center text-slate-500">
        No bookings yet. Create one above.
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-2xl p-4 sm:p-6 space-y-3">
      {bookings.map((b) => {
        const next = NEXT_STATUSES[b.status];
        return (
          <div
            key={b.id}
            className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 hover:border-slate-700 transition-colors"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  {b.title && (
                    <span className="text-slate-100 font-semibold truncate">{b.title}</span>
                  )}
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full border font-medium capitalize ${STATUS_STYLES[b.status] || STATUS_STYLES.pending}`}
                  >
                    {b.status}
                  </span>
                </div>
                <div className="text-sm text-slate-300 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-slate-500" />
                  {formatLocal(b.requested_at, b.contact?.timezone)}
                  <span className="text-slate-500">· {b.duration_minutes}m</span>
                </div>
              </div>

              {next && (
                <button
                  onClick={() => onAdvance(b.id, next)}
                  className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
                >
                  Mark {next}
                </button>
              )}
            </div>

            {b.contact && (
              <div className="mt-3 pt-3 border-t border-slate-800/70 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 text-xs text-slate-400">
                <span className="flex items-center gap-2 truncate">
                  <User className="w-3.5 h-3.5 text-slate-500" />
                  {b.contact.full_name}
                </span>
                <span className="flex items-center gap-2 truncate">
                  <Mail className="w-3.5 h-3.5 text-slate-500" />
                  {b.contact.email}
                </span>
                {b.contact.phone && (
                  <span className="flex items-center gap-2 truncate">
                    <Phone className="w-3.5 h-3.5 text-slate-500" />
                    {b.contact.phone}
                  </span>
                )}
                {b.contact.timezone && (
                  <span className="flex items-center gap-2 truncate">
                    <MapPin className="w-3.5 h-3.5 text-slate-500" />
                    {b.contact.timezone}
                    {b.contact.city ? ` · ${b.contact.city}` : ''}
                  </span>
                )}
              </div>
            )}

            {b.notes && (
              <div className="mt-3 text-xs text-slate-400 flex items-start gap-2">
                <Tag className="w-3.5 h-3.5 text-slate-500 mt-0.5 flex-shrink-0" />
                <span className="italic">{b.notes}</span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
