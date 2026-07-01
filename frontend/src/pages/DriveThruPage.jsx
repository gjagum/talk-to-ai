import React, { useState } from 'react';
import { UtensilsCrossed } from 'lucide-react';
import TalkAgent from '../components/TalkAgent';
import MenuManager from '../components/menu/MenuManager';
import { DEFAULT_PERSONA, DEFAULT_DRIVE_THRU_PERSONA } from '../lib/personas';

/**
 * DriveThruPage — the Drive-Thru cashier demo + order dashboard.
 *
 * Splits the original in-line JSX from App.jsx into its own route. Kept the
 * same persona defaulting (the drive-thru persona is used unless the user
 * edits the textarea) and the TalkAgent + MenuManager pairing.
 */
export default function DriveThruPage() {
  const [persona, setPersona] = useState(DEFAULT_DRIVE_THRU_PERSONA);

  return (
    <div className="w-full max-w-3xl flex flex-col gap-6">
      <div className="glass-panel rounded-3xl p-6">
        <h2 className="text-lg font-bold text-slate-100 mb-1 flex items-center gap-2">
          <UtensilsCrossed className="w-5 h-5 text-orange-400" />
          Drive-Thru Cashier (voice)
        </h2>
        <p className="text-slate-400 text-sm mb-4">
          Riley takes the order over the phone and builds a draft in the dashboard below.
        </p>

        <div className="text-left mb-4">
          <label className="block text-slate-300 font-medium mb-2" htmlFor="dt-persona">
            Persona
          </label>
          <textarea
            id="dt-persona"
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            className="w-full bg-slate-800/50 border border-slate-700 rounded-xl p-4 text-slate-200 focus:outline-none focus:ring-2 focus:ring-orange-500 transition-all resize-none"
            rows="4"
          />
        </div>

        <TalkAgent persona={persona} mode="drive_thru" />
      </div>
      <MenuManager />
    </div>
  );
}
