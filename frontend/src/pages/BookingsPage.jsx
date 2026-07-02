import React, { useState } from 'react';
import { Headphones } from 'lucide-react';
import TalkAgent from '../components/TalkAgent';
import PersonaEditor from '../components/PersonaEditor';
import BookingManager from '../components/booking/BookingManager';
import { DEFAULT_PERSONA } from '../lib/personas';

/**
 * BookingsPage — the booking calendar + voice assistant.
 *
 * Ryan the AI receptionist can take calls and book appointments directly
 * into the schedule. The calendar + booking list sit below the agent.
 */
export default function BookingsPage() {
  const [persona, setPersona] = useState(DEFAULT_PERSONA);

  return (
    <>
      <div className="glass-panel rounded-3xl p-6 w-full flex flex-col items-center text-center">
        <h2 className="text-lg font-bold text-slate-100 mb-1 flex items-center gap-2">
          <Headphones className="w-5 h-5 text-amber-400" />
          Booking Assistant (voice)
        </h2>
        <p className="text-slate-400 text-sm mb-4 max-w-md">
          Ryan answers calls, checks availability, and books discovery calls right into the calendar below.
        </p>

        <PersonaEditor
          agentName="receptionist"
          defaultPersona={DEFAULT_PERSONA}
          onPersonaChange={setPersona}
        />

        <div className="mt-4">
          <TalkAgent persona={persona} />
        </div>
      </div>
      <BookingManager />
    </>
  );
}
