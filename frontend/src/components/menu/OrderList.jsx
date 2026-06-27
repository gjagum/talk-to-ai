import React from 'react';
import { Receipt, Trash2 } from 'lucide-react';

const STATUS_STYLES = {
  draft: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  received: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  in_progress: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  ready: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  completed: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
  cancelled: 'bg-red-500/15 text-red-300 border-red-500/30',
};

// Linear advance order: received → in_progress → ready → completed.
// `draft` and `cancelled` are terminal here (draft auto-finalizes via the
// voice agent; cancelled is the end of the line).
const NEXT_STATUSES = {
  draft: null,
  received: 'in_progress',
  in_progress: 'ready',
  ready: 'completed',
  completed: null,
  cancelled: null,
};

function formatCents(cents) {
  if (cents == null) return '$0.00';
  return `$${(cents / 100).toFixed(2)}`;
}

function formatTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

export default function OrderList({ orders, onAdvance, onCancel, loading }) {
  if (loading && orders.length === 0) {
    return (
      <div className="glass-panel rounded-2xl p-8 text-center text-slate-400">
        Loading orders…
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <div className="glass-panel rounded-2xl p-8 text-center text-slate-500">
        No orders yet. Start a Drive-Thru call to take one.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {orders.map((o) => {
        const next = NEXT_STATUSES[o.status];
        const isDraft = o.status === 'draft';
        return (
          <div
            key={o.id}
            className="glass-panel rounded-2xl p-4 hover:border-slate-700 transition-colors"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <Receipt className="w-4 h-4 text-amber-400" />
                  <span className="text-slate-100 font-semibold">#{o.id}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full border font-medium capitalize ${STATUS_STYLES[o.status] || STATUS_STYLES.draft}`}
                  >
                    {o.status.replace('_', ' ')}
                  </span>
                  <span className="text-xs text-slate-500 capitalize">{o.order_type.replace('_', '-')}</span>
                  <span className="text-xs text-slate-600">· {formatTime(o.created_at)}</span>
                  {isDraft && (
                    <span className="text-[10px] uppercase tracking-wide text-amber-400/80 animate-pulse">
                      live
                    </span>
                  )}
                </div>

                <ul className="mt-2 space-y-1 text-sm text-slate-300">
                  {o.items.length === 0 && (
                    <li className="text-slate-500 italic">No items yet…</li>
                  )}
                  {o.items.map((it) => (
                    <li key={it.id} className="flex items-baseline justify-between gap-2">
                      <span className="truncate">
                        <span className="text-slate-400">{it.quantity}×</span>{' '}
                        {it.name_snapshot}
                        {it.notes && (
                          <span className="text-slate-500"> · {it.notes}</span>
                        )}
                      </span>
                      <span className="text-slate-400 tabular-nums shrink-0">
                        {formatCents(it.unit_price_cents * it.quantity)}
                      </span>
                    </li>
                  ))}
                </ul>

                <div className="mt-2 pt-2 border-t border-slate-800/70 flex items-center justify-between">
                  <span className="text-xs text-slate-500">
                    {o.customer_name || 'Walk-in'}
                  </span>
                  <span className="text-slate-100 font-bold tabular-nums">
                    {formatCents(o.total_cents)}
                  </span>
                </div>
              </div>

              <div className="flex flex-col gap-1 items-end">
                {next && (
                  <button
                    onClick={() => onAdvance(o.id, next)}
                    className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors whitespace-nowrap"
                  >
                    Mark {next.replace('_', ' ')}
                  </button>
                )}
                {o.status !== 'cancelled' && o.status !== 'completed' && (
                  <button
                    onClick={() => onCancel(o.id)}
                    className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-lg text-red-300 hover:text-red-200 border border-transparent hover:border-red-500/30 transition-colors"
                  >
                    <Trash2 className="w-3 h-3" />
                    Cancel
                  </button>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
