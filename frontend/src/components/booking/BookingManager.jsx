import React, { useEffect, useState, useCallback } from 'react';
import { CalendarDays, RefreshCw, Loader2 } from 'lucide-react';
import BookingCalendar from './BookingCalendar';
import BookingModal from './BookingModal';
import BookingList from './BookingList';
import { apiGet, apiPatch } from '../../lib/api';

/**
 * BookingManager — container for the Bookings tab.
 *
 * Shows a month calendar for picking available slots, with the booking form
 * in a modal that opens when a time slot is selected. The scheduled bookings
 * list is shown below the calendar.
 */
export default function BookingManager() {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedBooking, setSelectedBooking] = useState(null);

  const fetchBookings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet('/booking/');
      setBookings(data);
    } catch (err) {
      setError(err.message || 'Failed to load bookings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBookings();
  }, [fetchBookings]);

  const handleCreated = useCallback(
    (created) => {
      setBookings((prev) =>
        [...prev, created].sort(
          (a, b) => new Date(b.requested_at) - new Date(a.requested_at)
        )
      );
    },
    []
  );

  const handleAdvance = useCallback(async (bookingId, nextStatus) => {
    try {
      const updated = await apiPatch(`/booking/${bookingId}/status`, {
        status: nextStatus,
      });
      setBookings((prev) =>
        prev
          .map((b) => (b.id === bookingId ? updated : b))
          .sort((a, b) => new Date(b.requested_at) - new Date(a.requested_at))
      );
    } catch (err) {
      setError(err.message || 'Failed to update booking');
    }
  }, []);

  const handleBook = useCallback((booking) => {
    setSelectedBooking(booking);
    setModalOpen(true);
  }, []);

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <CalendarDays className="w-6 h-6 text-amber-400" />
          Booking Schedule
        </h2>
        <button
          onClick={fetchBookings}
          disabled={loading}
          className="flex items-center gap-2 text-sm text-slate-300 hover:text-white bg-slate-800/60 hover:bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 transition-colors"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Refresh
        </button>
      </div>

      {/* Calendar with slot picker */}
      <BookingCalendar onBook={handleBook} />

      {/* Modal for creating the booking */}
      <BookingModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        booking={selectedBooking}
        onCreated={handleCreated}
      />

      {error && (
        <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <BookingList
        bookings={bookings}
        loading={loading}
        onAdvance={handleAdvance}
      />

      <p className="text-xs text-slate-500 text-center pt-2">
        Times shown in each contact's own timezone. Consultant working hours are
        Asia/Manila 09:00–17:00; slot availability is validated server-side.
      </p>
    </div>
  );
}
