import React, { useCallback, useEffect, useState } from 'react';
import { Pencil, Save, Loader2, RotateCcw, User, Mail, Phone } from 'lucide-react';
import { apiGet, apiPut } from '../lib/api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';

/**
 * PersonaEditor — inline persona prompt editor backed by a Radix/shadcn Dialog.
 *
 * Used on the voice-demo pages (Home, Drive-Thru) so a persona can be tweaked
 * without bouncing into the Management dashboard. Behavior:
 *
 *   • On mount, GET /agents/<name>/persona. If the DB has a saved persona,
 *     that wins. If it returns `null` (agent not seeded / never saved), fall
 *     back to `defaultPersona` so the demo is always usable.
 *   • The compact preview shows the in-memory persona (truncated) with any
 *     {{name}} and {{email}} placeholders substituted from the name/email inputs.
 *   • The Edit button opens a Radix-ported Dialog with a large Textarea for
 *     editing the raw template — properly focus-trapped, ESC-to-close,
 *     outside-click-to-close.
 *   • Save PUTs the raw template to /agents/<name>/persona and closes the dialog.
 *   • Reset to Default restores the hardcoded `defaultPersona` locally — it
 *     does NOT wipe the saved copy in the DB until the user also hits Save.
 *
 * {{name}} and {{email}} are resolved client-side before the persona is passed
 * to onPersonaChange / the voice agent. The raw template (with placeholders) is
 * what gets saved to the DB so variable substitution works on every call.
 */

function resolvePersona(raw, name, email, phone) {
  if (!raw) return '';
  return raw
    .replaceAll('{{name}}', name || '')
    .replaceAll('{{email}}', email || '')
    .replaceAll('{{phone}}', phone || '');
}

export default function PersonaEditor({
  agentName,
  defaultPersona,
  onPersonaChange,
  defaultName = '',
  defaultEmail = '',
  defaultPhone = '',
  placeholder = 'Describe how the assistant should behave…',
}) {
  const [persona, setPersona] = useState(defaultPersona);
  const [source, setSource] = useState('default');
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const [name, setName] = useState(defaultName);
  const [email, setEmail] = useState(defaultEmail);
  const [phone, setPhone] = useState(defaultPhone);

  const loadPersona = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet(`/agents/${encodeURIComponent(agentName)}/persona`);
      if (typeof data.persona === 'string' && data.persona.length > 0) {
        setPersona(data.persona);
        setSource('db');
      } else {
        setPersona(defaultPersona);
        setSource('default');
      }
    } catch {
      setPersona(defaultPersona);
      setSource('default');
    } finally {
      setLoading(false);
    }
  }, [agentName, defaultPersona]);

  useEffect(() => { loadPersona(); }, [loadPersona]);

  // Notify parent whenever the resolved persona changes (raw + variables).
  const resolved = resolvePersona(persona, name, email, phone);
  useEffect(() => { onPersonaChange?.(resolved); }, [resolved]); // eslint-disable-line

  const openDialog = () => {
    setDraft(persona); // raw template in the editor
    setError(null);
    setOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const data = await apiPut(
        `/agents/${encodeURIComponent(agentName)}/persona`,
        { persona: draft },
      );
      const saved = typeof data.persona === 'string' && data.persona.length > 0
        ? data.persona
        : draft;
      setPersona(saved); // raw template (with placeholders) saved to state
      setSource('db');
      setOpen(false);
    } catch (err) {
      setError(err.message || 'Failed to save persona');
    } finally {
      setSaving(false);
    }
  };

  const previewText = loading
    ? 'Loading persona…'
    : resolved?.trim() || '— no persona set —';

  return (
    <div className="w-full max-w-lg text-left">
      {/* ── Variable inputs (name / email) ── */}
      <div className="mb-4 space-y-3">
        <div>
          <label className="block text-slate-300 font-medium text-sm mb-1" htmlFor={`name-${agentName}`}>
            <User className="w-3.5 h-3.5 inline mr-1.5 -mt-0.5 text-slate-400" />
            Your Name
          </label>
          <Input
            id={`name-${agentName}`}
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Jane Doe"
            className="bg-slate-800/50 border-slate-700 text-slate-200 placeholder:text-slate-500 focus-visible:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-slate-300 font-medium text-sm mb-1" htmlFor={`email-${agentName}`}>
            <Mail className="w-3.5 h-3.5 inline mr-1.5 -mt-0.5 text-slate-400" />
            Your Email
          </label>
          <Input
            id={`email-${agentName}`}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="e.g. jane@example.com"
            className="bg-slate-800/50 border-slate-700 text-slate-200 placeholder:text-slate-500 focus-visible:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-slate-300 font-medium text-sm mb-1" htmlFor={`phone-${agentName}`}>
            <Phone className="w-3.5 h-3.5 inline mr-1.5 -mt-0.5 text-slate-400" />
            Your Phone
          </label>
          <Input
            id={`phone-${agentName}`}
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="e.g. +1 555 000 1234"
            className="bg-slate-800/50 border-slate-700 text-slate-200 placeholder:text-slate-500 focus-visible:ring-blue-500"
          />
        </div>
        <p className="text-xs text-slate-500 italic">
          Use <code className="text-amber-400 bg-amber-400/10 px-1 rounded text-xs">{'{{name}}'}</code>,{' '}
          <code className="text-amber-400 bg-amber-400/10 px-1 rounded text-xs">{'{{email}}'}</code>, and{' '}
          <code className="text-amber-400 bg-amber-400/10 px-1 rounded text-xs">{'{{phone}}'}</code> in the
          persona below — they&apos;ll be filled in automatically.
        </p>
      </div>

      {/* ── Persona section ── */}
      <div className="flex items-center justify-between mb-2">
        <label className="block text-slate-300 font-medium" htmlFor={`persona-${agentName}`}>
          How should the assistant act?
        </label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={openDialog}
          className="bg-slate-800/70 border-slate-700 hover:bg-slate-700 hover:text-white text-slate-300"
          title="Edit persona in a larger window"
        >
          <Pencil className="w-3.5 h-3.5 mr-1.5" />
          Edit
        </Button>
      </div>

      <div
        id={`persona-${agentName}`}
        onClick={openDialog}
        className="w-full bg-slate-800/50 border border-slate-700 rounded-xl p-4 text-slate-200 transition-all cursor-pointer hover:bg-slate-800/70 hover:border-slate-600 min-h-[5.5rem]"
      >
        {loading ? (
          <span className="text-slate-400 italic">Loading persona…</span>
        ) : (
          <>
            <p className="text-slate-400 text-xs mb-1.5">
              {source === 'db'
                ? 'Saved persona (edit to change)'
                : 'Hardcoded default (click to customize and save)'}
            </p>
            <p className="text-slate-300 text-sm whitespace-pre-wrap line-clamp-4 break-words">
              {previewText}
            </p>
          </>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-3xl bg-slate-900/95 border-slate-700 backdrop-blur-md text-slate-100 [&>button]:text-slate-400 [&>button]:hover:text-white">
          <DialogHeader>
            <DialogTitle>Edit Persona</DialogTitle>
            <DialogDescription className="text-slate-400">
              Agent: <code className="text-slate-300">{agentName}</code> · saved to the database on Save.
              {' '}Variables <code className="text-amber-400">{'{{name}}'}</code>,{' '}
              <code className="text-amber-400">{'{{email}}'}</code>, and{' '}
              <code className="text-amber-400">{'{{phone}}'}</code> are resolved at runtime.
            </DialogDescription>
          </DialogHeader>

          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            autoFocus
            className="font-mono text-sm leading-relaxed bg-slate-950/70 border-slate-700 text-slate-200 min-h-[24rem] focus-visible:ring-blue-500"
            rows={20}
            placeholder={placeholder}
            spellCheck={false}
          />

          {error && (
            <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-md px-3 py-2">
              {error}
            </div>
          )}

          <DialogFooter className="gap-2 sm:justify-between flex-col-reverse sm:flex-row items-stretch sm:items-center">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setDraft(defaultPersona)}
              className="text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              title="Restore the hardcoded default persona (not saved until you press Save)"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset to default
            </Button>
            <div className="flex gap-2 justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setOpen(false)}
                className="bg-slate-800 hover:bg-slate-700 text-slate-200"
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleSave}
                disabled={saving || draft.trim().length === 0}
                className="bg-blue-600 hover:bg-blue-500 text-white"
              >
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                Save
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
