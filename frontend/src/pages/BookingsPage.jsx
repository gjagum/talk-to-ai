import React from 'react';
import BookingManager from '../components/booking/BookingManager';

/**
 * BookingsPage — the existing BookingManager component on its own route.
 */
export default function BookingsPage() {
  return (
    <div className="w-full max-w-3xl">
      <BookingManager />
    </div>
  );
}
