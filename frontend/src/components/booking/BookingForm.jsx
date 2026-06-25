import React, { useState } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { apiPost } from '../../lib/api';

const EMPTY = {
  full_name: '',
  email: '',
  phone: '',
  timezone: 'Asia/Manila',
  city: '',
  // datetime-local is naive; we treat it as the requester's `timezone`.
  requested_at_local: '',
  duration_minutes: 30,
  title: '',
  notes: '',
};

export default function BookingForm({ onCreated }) {
  const [form, setForm] = useState(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!form.full_name.trim() || !form.email.trim() || !form.requested_at_local) {
      setError('Name, email, and requested time are required.');
      return;
    }

    // Convert the naive datetime-local value into a timezone-aware ISO string
    // in the requester's tz so the backend stores unambiguous UTC.
    const tz = form.timezone || 'UTC';
    let requested_at_iso;
    try {
      // `new Date('YYYY-MM-DDTHH:mm')` parses as local browser time. We instead
      // explicitly attach the selected tz by feeding it through Date with the
      // assumption the value is "wall clock in selected tz".
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
    } catch (err) {
      setError(err.message || 'Failed to create booking');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="glass-panel rounded-2xl p-6 space-y-4">
      <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
        <Send className="w-5 h-5 text-amber-400" />
        New Booking
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Full name *">
          <input
            type="text"
            value={form.full_name}
            onChange={(e) => setField('full_name', e.target.value)}
            className={inputCls}
            placeholder="Jane Doe"
          />
        </Field>
        <Field label="Email *">
          <input
            type="email"
            value={form.email}
            onChange={(e) => setField('email', e.target.value)}
            className={inputCls}
            placeholder="jane@example.com"
          />
        </Field>
        <Field label="Phone">
          <input
            type="tel"
            value={form.phone}
            onChange={(e) => setField('phone', e.target.value)}
            className={inputCls}
            placeholder="+1 555 000 1234"
          />
        </Field>
        <Field label="City">
          <input
            type="text"
            value={form.city}
            onChange={(e) => setField('city', e.target.value)}
            className={inputCls}
            placeholder="New York"
          />
        </Field>
        <Field label="Timezone (IANA)">
          <input
            type="text"
            value={form.timezone}
            onChange={(e) => setField('timezone', e.target.value)}
            className={inputCls}
            placeholder="America/New_York"
          />
        </Field>
        <Field label="Duration (minutes)">
          <select
            value={form.duration_minutes}
            onChange={(e) => setField('duration_minutes', e.target.value)}
            className={inputCls}
          >
            <option value={15}>15</option>
            <option value={30}>30</option>
            <option value={45}>45</option>
            <option value={60}>60</option>
          </select>
        </Field>
        <Field label="Requested time *">
          <input
            type="datetime-local"
            value={form.requested_at_local}
            onChange={(e) => setField('requested_at_local', e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label="Title">
          <input
            type="text"
            value={form.title}
            onChange={(e) => setField('title', e.target.value)}
            className={inputCls}
            placeholder="Discovery / preso call"
          />
        </Field>
      </div>

      <Field label="Notes">
        <textarea
          value={form.notes}
          onChange={(e) => setField('notes', e.target.value)}
          className={`${inputCls} resize-none`}
          rows={2}
          placeholder="Optional notes"
        />
      </Field>

      {error && (
        <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="flex items-center gap-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-60 text-white px-5 py-2.5 rounded-xl font-semibold shadow-lg shadow-amber-600/20 transition-all"
      >
        {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        Create Booking
      </button>
    </form>
  );
}

const inputCls =
  'w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/60 transition-all';

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-slate-400 mb-1.5">{label}</span>
      {children}
    </label>
  );
}

// Convert a "YYYY-MM-DDTHH:mm" datetime-local value into a tz-aware ISO-8601
// string interpreted in the given IANA timezone. We compute the wall-clock
// offset via Intl so the resulting instant is correct regardless of the
// browser's own tz.
function localToZoneAwareIso(localValue, timezone) {
  // Parse the wall-clock pieces directly (no Date auto-local-tz interpretation).
  const [datePart, timePart] = localValue.split('T');
  const [y, mo, d] = datePart.split('-').map(Number);
  const [h, mi] = (timePart || '00:00').split(':').map(Number);

  // Build a probe instant as-if-UTC from the wall-clock pieces, then read the
  // target tz's offset for that instant and back-correct so the stored instant
  // matches the wall clock in `timezone`.
  const probe = Date.UTC(y, mo - 1, d, h, mi);
  const utcOffsetMinutes = timeZoneOffsetMinutes(timezone, probe);
  const instant = probe - utcOffsetMinutes * 60 * 1000;
  return new Date(instant).toISOString();
}

function timeZoneOffsetMinutes(timeZone, epochMs) {
  // Returns the offset (minutes) of `timeZone` from UTC at the given epoch.
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  const parts = dtf.formatToParts(new Date(epochMs)).reduce((acc, p) => {
    if (p.type !== 'literal') acc[p.type] = parseInt(p.value, 10);
    return acc;
  }, {});
  const asUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
  return Math.round((asUtc - epochMs) / 60000);
}
