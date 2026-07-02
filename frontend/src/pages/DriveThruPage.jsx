import React, { useState } from 'react';
import { UtensilsCrossed } from 'lucide-react';
import TalkAgent from '../components/TalkAgent';
import PersonaEditor from '../components/PersonaEditor';
import MenuManager from '../components/menu/MenuManager';
import { DEFAULT_PERSONA, DEFAULT_DRIVE_THRU_PERSONA } from '../lib/personas';

/**
 * DriveThruPage — the Drive-Thru cashier demo + order dashboard.
 *
 * Persona is loaded from the DB via PersonaEditor; if no saved persona exists,
 * the hardcoded DEFAULT_DRIVE_THRU_PERSONA is used and shown as the default.
 */
export default function DriveThruPage() {
  const [persona, setPersona] = useState(DEFAULT_DRIVE_THRU_PERSONA);

  return (
    <>
      <div className="glass-panel rounded-3xl p-6 w-full flex flex-col items-center text-center">
        <h2 className="text-lg font-bold text-slate-100 mb-1 flex items-center gap-2">
          <UtensilsCrossed className="w-5 h-5 text-orange-400" />
          Drive-Thru Cashier (voice)
        </h2>
        <p className="text-slate-400 text-sm mb-4 max-w-md">
          Riley takes the order over the phone and builds a draft in the dashboard below.
        </p>

        <PersonaEditor
          agentName="drive_thru"
          defaultPersona={DEFAULT_DRIVE_THRU_PERSONA}
          onPersonaChange={setPersona}
        />

        <div className="mt-4">
          <TalkAgent persona={persona} mode="drive_thru" />
        </div>
      </div>
      <MenuManager />
    </>
  );
}
