import React, { useState } from 'react';
import { Zap, FileAudio, Headphones } from 'lucide-react';
import RealtimeAgent from '../components/RealtimeAgent';
import WhisperAgent from '../components/WhisperAgent';
import TalkAgent from '../components/TalkAgent';
import PersonaEditor from '../components/PersonaEditor';
import { DEFAULT_PERSONA } from '../lib/personas';

/**
 * HomePage — the public voice playground.
 *
 * Preserves the original single-page mode switcher (Talk / Realtime / Whisper)
 * on the index route. Drive-Thru moved to its own `/drive-thru` route and
 * Bookings to `/bookings`, so this page is purely the persona-driven voice
 * demos.
 */
export default function HomePage() {
  const [persona, setPersona] = useState(DEFAULT_PERSONA);
  const [mode, setMode] = useState('talk');

  return (
    <div className="w-full max-w-3xl flex flex-col gap-6">
      <div className="glass-panel rounded-3xl p-8 flex flex-col items-center justify-center relative overflow-hidden gap-6">
        <div className="flex bg-slate-800/80 p-1 rounded-2xl shadow-inner border border-slate-700/50 flex-wrap justify-center">
          <button
            onClick={() => setMode('talk')}
            className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all ${
              mode === 'talk' ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/25' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Headphones className="w-5 h-5" />
            Talk
          </button>
          <button
            onClick={() => setMode('realtime')}
            className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all ${
              mode === 'realtime' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Zap className="w-5 h-5" />
            Realtime API
          </button>
          <button
            onClick={() => setMode('whisper')}
            className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all ${
              mode === 'whisper' ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/25' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileAudio className="w-5 h-5" />
            Whisper REST
          </button>
        </div>

        <PersonaEditor
          agentName="receptionist"
          defaultPersona={DEFAULT_PERSONA}
          onPersonaChange={setPersona}
        />
      </div>

      {mode === 'realtime' ? (
        <RealtimeAgent persona={persona} />
      ) : mode === 'talk' ? (
        <TalkAgent persona={persona} />
      ) : (
        <WhisperAgent persona={persona} />
      )}
    </div>
  );
}
