import React, { useCallback, useEffect, useState } from 'react';
import { DayPicker } from 'react-day-picker';
import { format, parseISO, isSameDay } from 'date-fns';
import { Clock, Loader2, CalendarDays } from 'lucide-react';
import { apiGet } from '../../lib/api';
import 'react-day-picker/dist/style.css';

/**
 * BookingCalendar — month calendar that shows available appointment slots.
 *
 * Fetches /api/booking/availability?date=YYYY-MM-DD to get open 30-min windows
 * for the selected day. Dates that already have bookings get highlighted.
 * Clicking a time-slot "Book" button fires onBook(slot, date).
 */
export default function BookingCalendar({ onBook }) {
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
          modifiersClassNames={{
            selected:
              '!bg-amber-500 !text-white !rounded-lg',
            today:
              '!text-amber-400 !font-bold',
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

      {/* Slots for selected day */}
      {selected && (
        <div className="glass-panel rounded-2xl p-4 sm:p-6 space-y-4">
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <CalendarDays className="w-5 h-5 text-amber-400" />
            {format(selected, 'EEEE, MMMM d, yyyy')}
          </h3>

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
      )}
    </div>
  );
}
