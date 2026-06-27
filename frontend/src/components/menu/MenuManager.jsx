import React, { useEffect, useState, useCallback, useRef } from 'react';
import { UtensilsCrossed, RefreshCw, Loader2 } from 'lucide-react';
import OrderList from './OrderList';
import { apiGet, apiPatch } from '../../lib/api';

/**
 * MenuManager — container for the Drive-Thru tab.
 *
 * Shows the live order dashboard. Polls /api/menu/orders every few seconds so
 * draft orders the voice agent is actively building appear in real time, then
 * slows down when everything is steady-state (no drafts in flight).
 *
 * This component is companion to the Drive-Thru agent: the agent takes the
 * order over the phone (via Deepgram tools) and mutates orders in the DB; the
 * staff see them appear here and can advance/cancel them.
 */
const POLL_WHEN_DRAFT_MS = 3000;
const POLL_STEADY_MS = 15000;

export default function MenuManager() {
  const [orders, setOrders] = useState([]);
  const [menu, setMenu] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const timerRef = useRef(null);

  const fetchOrders = useCallback(async () => {
    setError(null);
    try {
      const data = await apiGet('/menu/orders');
      setOrders(data);
    } catch (err) {
      setError(err.message || 'Failed to load orders');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchMenu = useCallback(async () => {
    try {
      const data = await apiGet('/menu/menu');
      setMenu(data);
    } catch (err) {
      // Non-fatal; the dashboard still works without the menu reference panel.
      console.warn('Failed to load menu', err);
    }
  }, []);

  // Initial fetch + polling loop. Poll cadence adapts: while any order is a
  // live `draft` we poll quickly so the staff sees the in-progress order build;
  // otherwise we back off to a slower refresh.
  useEffect(() => {
    setLoading(true);
    fetchOrders();
    fetchMenu();

    const scheduleNext = () => {
      // Choose cadence based on current state captured in `orders`.
      setOrders((current) => {
        const hasDraft = current.some((o) => o.status === 'draft');
        const delay = hasDraft ? POLL_WHEN_DRAFT_MS : POLL_STEADY_MS;
        timerRef.current = setTimeout(() => {
          fetchOrders().then(scheduleNext);
        }, delay);
        return current;
      });
    };
    scheduleNext();

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [fetchOrders, fetchMenu]);

  const handleAdvance = useCallback(async (orderId, nextStatus) => {
    try {
      const updated = await apiPatch(`/menu/orders/${orderId}/status`, {
        status: nextStatus,
      });
      setOrders((prev) =>
        prev.map((o) => (o.id === orderId ? updated : o))
      );
    } catch (err) {
      setError(err.message || 'Failed to update order');
    }
  }, []);

  const handleCancel = useCallback(async (orderId) => {
    try {
      const updated = await apiPatch(`/menu/orders/${orderId}/status`, {
        status: 'cancelled',
      });
      setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
    } catch (err) {
      setError(err.message || 'Failed to cancel order');
    }
  }, []);

  // Group the menu for the collapsible reference panel.
  const menuByCategory = menu.reduce((acc, item) => {
    (acc[item.category || 'Other'] ||= []).push(item);
    return acc;
  }, {});

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <UtensilsCrossed className="w-6 h-6 text-amber-400" />
          Drive-Thru Orders
        </h2>
        <button
          onClick={() => {
            setLoading(true);
            fetchOrders();
          }}
          disabled={loading}
          className="flex items-center gap-2 text-sm text-slate-300 hover:text-white bg-slate-800/60 hover:bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 transition-colors"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 text-red-200 px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <OrderList
        orders={orders}
        onAdvance={handleAdvance}
        onCancel={handleCancel}
        loading={loading}
      />

      {/* Collapsible menu reference for the staff (read-only in v1). */}
      <div className="glass-panel rounded-2xl">
        <button
          onClick={() => setMenuOpen((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm text-slate-300 hover:text-white"
        >
          <span className="font-medium">{menuOpen ? 'Hide' : 'Show'} menu reference ({menu.length} items)</span>
          <span className="text-slate-500">{menuOpen ? '−' : '+'}</span>
        </button>
        {menuOpen && (
          <div className="px-4 pb-4 pt-1 space-y-3 border-t border-slate-800/70">
            {Object.entries(menuByCategory).map(([cat, items]) => (
              <div key={cat}>
                <div className="text-xs uppercase tracking-wide text-slate-500 mt-3 mb-1">{cat}</div>
                <ul className="space-y-1">
                  {items.map((it) => (
                    <li
                      key={it.id}
                      className="flex items-baseline justify-between gap-2 text-sm text-slate-300"
                    >
                      <span className="truncate">
                        {it.name}
                        {it.description && (
                          <span className="text-slate-500"> — {it.description}</span>
                        )}
                      </span>
                      <span className="text-slate-400 tabular-nums shrink-0">
                        ${(it.price_cents / 100).toFixed(2)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
