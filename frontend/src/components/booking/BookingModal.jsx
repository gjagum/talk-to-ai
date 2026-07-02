import React, { useState, useEffect } from 'react';
import { format, parseISO } from 'date-fns';
import { Send, Loader2, Clock, CalendarDays } from 'lucide-react';
import { apiPost } from '../../lib/api';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';

const EMPTY = {
  full_name: '',
  email: '',
  phone: '',
  timezone: 'Asia/Manila',
  city: '',
  duration_minutes: 30,
  title: '',
  notes: '',
};

function inputCls() {
  return 'w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500/40 transition-colors';
}

/**
 * BookingModal — Dialog-based booking form opened from the calendar.
 *
 * Receives { date, slot } from BookingCalendar, pre-fills the datetime field,
 * and submits to POST /booking/.
 */
export default function BookingModal({ open, onOpenChange, booking, onCreated }) {
  const [form, setForm] = useState(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Pre-fill the form when a new slot is selected.
  useEffect(() => {
    if (booking?.slot?.start) {
      setForm({
        ...EMPTY,
        requested_at_local: format(parseISO(booking.slot.start), "yyyy-MM-dd'T'HH:mm"),
        timezone: 'Asia/Manila',
      });
    }
    setError(null);
  }, [booking]);

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!form.full_name.trim() || !form.email.trim() || !form.requested_at_local) {
      setError('Name, email, and time are required.');
      return;
    }

    const tz = form.timezone || 'UTC';
    let requested_at_iso;
    try {
      requested_at_iso = localToZoneAwareIso(form.requested_at_local, tz);
    } catch {
      setError('Invalid date/time format.');
      return;
    }

    setSubmitting(true);
    try {
      const created = await apiPost('/booking/', {
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || null,
        timezone: form.timezone || null,
        city: form.city.trim() || null,
        requested_at: requested_at_iso,
        duration_minutes: Number(form.duration_minutes) || 30,
        title: form.title.trim() || null,
        notes: form.notes.trim() || null,
      });
      setForm(EMPTY);
      onCreated?.(created);
      onOpenChange(false);
    } catch (err) {
      setError(err.message || 'Failed to create booking');
    } finally {
      setSubmitting(false);
    }
  };

  const selectedDate = booking?.date;
  const selectedSlot = booking?.slot;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg bg-slate-900 border-slate-700 text-slate-100">
        <DialogHeader>
          <DialogTitle className="text-slate-100 flex items-center gap-2">
            <CalendarDays className="w-5 h-5 text-amber-400" />
            New Booking
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            {selectedDate && selectedSlot ? (
              <span className="flex items-center gap-2 mt-1">
                <Clock className="w-4 h-4 text-emerald-400" />
                {format(selectedDate, 'EEEE, MMMM d, yyyy')} at{' '}
                {format(parseISO(selectedSlot.start), 'h:mm a')} –{' '}
                {format(parseISO(selectedSlot.end), 'h:mm a')}
              </span>
            ) : (
              'Fill in the details below to schedule a consultation.'
            )}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="space-y-1">
              <span className="text-xs text-slate-400">Full name *</span>
              <input
                type="text"
                value={form.full_name}
                onChange={(e) => setField('full_name', e.target.value)}
                className={inputCls()}
                placeholder="Jane Doe"
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-400">Email *</span>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setField('email', e.target.value)}
                className={inputCls()}
                placeholder="jane@example.com"
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-400">Phone</span>
              <input
                type="tel"
                value={form.phone}
                onChange={(e) => setField('phone', e.target.value)}
                className={inputCls()}
                placeholder="+1 555 000 1234"
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-400">City</span>
              <input
                type="text"
                value={form.city}
                onChange={(e) => setField('city', e.target.value)}
                className={inputCls()}
                placeholder="New York"
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-400">Timezone</span>
              <input
                type="text"
                value={form.timezone}
                onChange={(e) => setField('timezone', e.target.value)}
                className={inputCls()}
                placeholder="Asia/Manila"
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-400">Duration (min)</span>
              <select
                value={form.duration_minutes}
                onChange={(e) => setField('duration_minutes', e.target.value)}
                className={inputCls()}
              >
                <option value={15}>15</option>
                <option value={30}>30</option>
                <option value={45}>45</option>
                <option value={60}>60</option>
              </select>
            </label>
          </div>

          <label className="space-y-1 block">
            <span className="text-xs text-slate-400">Title</span>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setField('title', e.target.value)}
              className={inputCls()}
              placeholder="Discovery / preso call"
            />
          </label>
          <label className="space-y-1 block">
            <span className="text-xs text-slate-400">Notes</span>
            <textarea
              value={form.notes}
              onChange={(e) => setField('notes', e.target.value)}
              className={`${inputCls()} resize-none`}
              rows={2}
              placeholder="Optional notes"
            />
          </label>

          {error && (
            <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="flex items-center gap-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-60 text-white px-5 py-2.5 rounded-xl font-semibold shadow-lg shadow-amber-600/20 transition-all w-full justify-center"
          >
            {submitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            Create Booking
          </button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Timezone helpers (shared with BookingForm) ─────────────────────────────

function localToZoneAwareIso(localValue, timezone) {
  const [datePart, timePart] = localValue.split('T');
  const [y, mo, d] = datePart.split('-').map(Number);
  const [h, mi] = (timePart || '00:00').split(':').map(Number);
  const probe = Date.UTC(y, mo - 1, d, h, mi);
  const utcOffsetMinutes = timeZoneOffsetMinutes(timezone, probe);
  const instant = probe - utcOffsetMinutes * 60 * 1000;
  return new Date(instant).toISOString();
}

function timeZoneOffsetMinutes(timeZone, epochMs) {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  const parts = dtf.formatToParts(new Date(epochMs));
  const get = (t) => Number(parts.find((p) => p.type === t)?.value ?? 0);
  const wallEpoch = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'));
  return (wallEpoch - epochMs) / 60000;
}
