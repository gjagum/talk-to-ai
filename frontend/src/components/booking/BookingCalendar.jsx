import React, { useCallback, useMemo, useState } from 'react';
import { DayPicker } from 'react-day-picker';
import { format, parseISO, isSameDay } from 'date-fns';
import { Clock, Loader2, CalendarDays, CheckCircle2 } from 'lucide-react';
import { apiGet } from '../../lib/api';
import 'react-day-picker/dist/style.css';

/**
 * BookingCalendar — month calendar that shows existing bookings + open slots.
 *
 * - Dates that hold any (non-cancelled) booking get a dot marker.
 * - Clicking a day fetches `/api/booking/availability?date=YYYY-MM-DD` for the
 *   remaining free 30-min windows, and lists that day's existing bookings
 *   above them as "Booked" chips.
 * - Clicking a free time-slot's "Book" button fires onBook(slot, date).
 *
 * `bookings` is the full booking list (BookingRead[]) owned by the parent
 * BookingManager, so agent-made bookings appear here without an extra fetch.
 */
const STATUS_STYLES = {
  pending: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  confirmed: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  cancelled: 'bg-red-500/15 text-red-300 border-red-500/30',
  completed: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
};

export default function BookingCalendar({ onBook, bookings = [] }) {
  const [selected, setSelected] = useState(null);
  const [slots, setSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [error, setError] = useState(null);

  const fetchSlots = useCallback(async (date) => {
    setLoadingSlots(true);
    setError(null);
    setSlots([]);
    try {
      const dateStr = format(date, 'yyyy-MM-dd');
      const data = await apiGet(`/booking/availability?date=${dateStr}&timezone=Asia/Manila`);
      setSlots(data.slots || []);
    } catch (err) {
      setError(err.message || 'Failed to load availability');
    } finally {
      setLoadingSlots(false);
    }
  }, []);

  const handleDayClick = (day) => {
    setSelected(day);
    fetchSlots(day);
  };

  // Dates that hold at least one non-cancelled booking → highlighted with a dot.
  const bookedDates = useMemo(() => {
    const seen = new Set();
    const dates = [];
    for (const b of bookings) {
      if (b.status === 'cancelled') continue;
      let d;
      try {
        d = parseISO(b.requested_at);
      } catch {
        continue;
      }
      if (isNaN(d)) continue;
      const key = d.toDateString();
      if (seen.has(key)) continue;
      seen.add(key);
      dates.push(d);
    }
    return dates;
  }, [bookings]);

  // Existing bookings on the currently-selected day (any status), earliest last.
  const dayBookings = useMemo(() => {
    if (!selected) return [];
    return bookings
      .filter((b) => {
        try {
          return isSameDay(parseISO(b.requested_at), selected);
        } catch {
          return false;
        }
      })
      .sort((a, b) => new Date(a.requested_at) - new Date(b.requested_at));
  }, [bookings, selected]);

  // Disable past dates + Sundays
  const disabledDays = [
    { before: new Date(new Date().setHours(0, 0, 0, 0)) },
    { dayOfWeek: [0] }, // Sundays
  ];

  return (
    <div className="space-y-5">
      {/* Calendar card */}
      <div className="glass-panel rounded-2xl p-4 sm:p-6 flex justify-center">
        <DayPicker
          mode="single"
          selected={selected}
          onDayClick={handleDayClick}
          disabled={disabledDays}
          showOutsideDays={false}
          modifiers={{ hasBookings: bookedDates }}
          modifiersClassNames={{
            selected:
              '!bg-amber-500 !text-white !rounded-lg',
            today:
              '!text-amber-400 !font-bold',
            // Small sky-blue dot beneath the date number for booked days.
            hasBookings:
              '!relative !after:content-[""] !after:absolute !after:left-1/2 !after:-translate-x-1/2 !after:bottom-0.5 !after:h-1 !after:w-1 !after:rounded-full !after:bg-sky-400',
          }}
          styles={{
            root: { margin: 0 },
            caption: { color: '#e2e8f0' },
            caption_label: { color: '#e2e8f0', fontSize: '1rem' },
            head_cell: { color: '#94a3b8' },
            cell: { color: '#cbd5e1' },
            day: {
              color: '#cbd5e1',
              borderRadius: '0.5rem',
            },
            day_disabled: { color: '#475569' },
            day_outside: { color: '#475569' },
            nav_button: { color: '#94a3b8' },
          }}
        />
      </div>

      {/* Slots + bookings for selected day */}
      {selected && (
        <div className="glass-panel rounded-2xl p-4 sm:p-6 space-y-4">
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <CalendarDays className="w-5 h-5 text-amber-400" />
            {format(selected, 'EEEE, MMMM d, yyyy')}
          </h3>

          {/* Existing bookings on this day */}
          {dayBookings.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500 font-medium">
                Booked
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {dayBookings.map((b) => {
                  const start = format(parseISO(b.requested_at), 'h:mm a');
                  const end = format(
                    new Date(new Date(b.requested_at).getTime() + b.duration_minutes * 60000),
                    'h:mm a'
                  );
                  return (
                    <div
                      key={b.id}
                      className="flex items-center justify-between gap-3 rounded-xl border border-slate-700/60 bg-slate-800/40 p-3"
                    >
                      <div className="flex items-center gap-2 text-sm text-slate-300 min-w-0">
                        <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0" />
                        <span className="truncate">
                          {start} – {end}
                          {b.contact?.full_name ? ` · ${b.contact.full_name}` : ''}
                        </span>
                      </div>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full border font-medium capitalize shrink-0 ${STATUS_STYLES[b.status] || STATUS_STYLES.pending}`}
                      >
                        {b.status}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Free availability slots */}
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-slate-500 font-medium">
              Available
            </p>
            {loadingSlots && (
              <div className="flex items-center gap-2 text-slate-400 py-4">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading availability…
              </div>
            )}

            {error && (
              <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            {!loadingSlots && !error && slots.length === 0 && (
              <p className="text-slate-500 text-sm py-2">
                No available slots for this day.
              </p>
            )}

            {!loadingSlots && !error && slots.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {slots.map((slot, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between gap-3 rounded-xl border border-slate-700/60 bg-slate-800/40 p-3 hover:border-slate-600 transition-colors"
                  >
                    <div className="flex items-center gap-2 text-sm text-slate-200">
                      <Clock className="w-4 h-4 text-emerald-400" />
                      <span>
                        {format(parseISO(slot.start), 'h:mm a')} –{' '}
                        {format(parseISO(slot.end), 'h:mm a')}
                      </span>
                    </div>
                    <button
                      onClick={() =>
                        onBook({
                          date: selected,
                          slot: {
                            start: slot.start,
                            end: slot.end,
                          },
                        })
                      }
                      className="text-xs font-medium px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white transition-colors shrink-0"
                    >
                      Book
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
