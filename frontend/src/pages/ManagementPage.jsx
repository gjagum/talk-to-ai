import React, { useCallback, useEffect, useState } from 'react';
import {
  Bot,
  Wrench,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  RefreshCw,
  Save,
  X,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost, apiPut } from '../lib/api';

/**
 * ManagementPage — admin dashboard for the data-driven Agent + Tool store.
 *
 * Backed by `/api/admin/agents` and `/api/admin/tools` (JWT-gated). Two
 * tabbed panels:
 *   • Agents: list/create/edit/delete canonical agents + tool assignment.
 *   • Tools:  list/create/edit/delete the Deepgram function tools.
 *
 * The persona/greeting/pipeline model fields are large blobs, so each row
 * expands to an inline editor form rather than a table of inputs. Tool
 * assignment is a multi-select checkbox list of all tools.
 *
 * All write calls reuse the same optimistic pattern: collect the form, POST/
 * PUT/DELETE, then refetch the relevant list (cheap, and avoids drift).
 */

const DEFAULT_AGENT = {
  name: '',
  description: '',
  persona: '',
  greeting: '',
  stt_provider: 'deepgram',
  stt_model: 'nova-3',
  tts_provider: 'deepgram',
  tts_model: 'aura-asteria-en',
  llm_provider: 'open_ai',
  llm_model: 'gpt-4o-mini',
  llm_temperature: 0.7,
  is_active: true,
  tool_ids: [],
};

const EMPTY_TOOL = {
  name: '',
  description: '',
  parameters: {},
  handler_key: '',
  is_active: true,
};

export default function ManagementPage() {
  const [tab, setTab] = useState('agents');

  return (
    <div className="w-full max-w-5xl flex flex-col gap-6">
      <div className="flex items-center gap-2">
        <TabButton active={tab === 'agents'} onClick={() => setTab('agents')} icon={Bot} label="Agents" />
        <TabButton active={tab === 'tools'} onClick={() => setTab('tools')} icon={Wrench} label="Tools" />
      </div>

      {tab === 'agents' ? <AgentsPanel /> : <ToolsPanel />}
    </div>
  );
}

function TabButton({ active, onClick, icon: Icon, label }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all ${
        active ? 'bg-slate-700/70 text-white shadow-inner' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Agents panel
// ---------------------------------------------------------------------------
function AgentsPanel() {
  const [agents, setAgents] = useState([]);
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null); // agent object being edited, or 'new', or null

  const fetchAgents = useCallback(async () => {
    setError(null);
    try {
      const [a, t] = await Promise.all([
        apiGet('/admin/agents', { auth: true }),
        apiGet('/admin/tools', { auth: true }),
      ]);
      setAgents(a);
      setTools(t);
    } catch (err) {
      setError(err.message || 'Failed to load agents');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchAgents();
  }, [fetchAgents]);

  const onDelete = async (agent) => {
    if (!confirm(`Delete agent "${agent.name}"? This cannot be undone.`)) return;
    try {
      await apiDelete(`/admin/agents/${agent.id}`, { auth: true });
      await fetchAgents();
    } catch (err) {
      setError(err.message || 'Delete failed');
    }
  };

  return (
    <Panel
      title="Agents"
      icon={Bot}
      loading={loading}
      error={error}
      onRefresh={() => {
        setLoading(true);
        fetchAgents();
      }}
      actionLabel="New agent"
      onAction={() => setEditing('new')}
    >
      {agents.length === 0 ? (
        <EmptyState what="agents" />
      ) : (
        <ul className="space-y-3">
          {agents.map((a) => (
            <li key={a.id} className="glass-panel rounded-2xl p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-slate-100 font-bold">{a.name}</h3>
                    {!a.is_active && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700/60 text-slate-300">
                        inactive
                      </span>
                    )}
                  </div>
                  {a.description && (
                    <p className="text-slate-400 text-sm mt-0.5">{a.description}</p>
                  )}
                  <div className="text-slate-500 text-xs mt-1">
                    {a.stt_provider}/{a.stt_model} · {a.llm_provider}/{a.llm_model} · {a.tts_model}
                  </div>
                  {a.tools?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {a.tools.map((t) => (
                        <span
                          key={t.id}
                          className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-200 border border-blue-500/20"
                        >
                          {t.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <IconBtn onClick={() => setEditing(a)} icon={Pencil} label="Edit" />
                  <IconBtn onClick={() => onDelete(a)} icon={Trash2} label="Delete" danger />
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <AgentEditor
          agent={editing === 'new' ? null : editing}
          tools={tools}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            fetchAgents();
          }}
        />
      )}
    </Panel>
  );
}

function AgentEditor({ agent, tools, onClose, onSaved }) {
  const [form, setForm] = useState(
    agent
      ? {
          ...agent,
          tool_ids: (agent.tools || []).map((t) => t.id),
        }
      : { ...DEFAULT_AGENT }
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const toggleTool = (id) =>
    setForm((f) => ({
      ...f,
      tool_ids: f.tool_ids.includes(id)
        ? f.tool_ids.filter((t) => t !== id)
        : [...f.tool_ids, id],
    }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description,
        persona: form.persona,
        greeting: form.greeting,
        stt_provider: form.stt_provider,
        stt_model: form.stt_model,
        tts_provider: form.tts_provider,
        tts_model: form.tts_model,
        llm_provider: form.llm_provider,
        llm_model: form.llm_model,
        llm_temperature: Number(form.llm_temperature),
        is_active: form.is_active,
        tool_ids: form.tool_ids,
      };
      if (agent) {
        await apiPut(`/admin/agents/${agent.id}`, payload, { auth: true });
      } else {
        await apiPost('/admin/agents', payload, { auth: true });
      }
      onSaved();
    } catch (err) {
      setError(err.message || 'Save failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal onClose={onClose} title={agent ? `Edit ${agent.name}` : 'New agent'}>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Name" required>
          <input
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            required
            className={inputCls}
            placeholder="receptionist"
          />
        </Field>

        <Field label="Description">
          <input
            value={form.description || ''}
            onChange={(e) => set('description', e.target.value)}
            className={inputCls}
            placeholder="AI receptionist for…"
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="STT provider">
            <input value={form.stt_provider} onChange={(e) => set('stt_provider', e.target.value)} className={inputCls} />
          </Field>
          <Field label="STT model">
            <input value={form.stt_model} onChange={(e) => set('stt_model', e.target.value)} className={inputCls} />
          </Field>
          <Field label="LLM provider">
            <input value={form.llm_provider} onChange={(e) => set('llm_provider', e.target.value)} className={inputCls} />
          </Field>
          <Field label="LLM model">
            <input value={form.llm_model} onChange={(e) => set('llm_model', e.target.value)} className={inputCls} />
          </Field>
          <Field label="TTS provider">
            <input value={form.tts_provider} onChange={(e) => set('tts_provider', e.target.value)} className={inputCls} />
          </Field>
          <Field label="TTS model">
            <input value={form.tts_model} onChange={(e) => set('tts_model', e.target.value)} className={inputCls} />
          </Field>
          <Field label="LLM temperature">
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={form.llm_temperature}
              onChange={(e) => set('llm_temperature', e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Active">
            <label className="flex items-center gap-2 h-[42px]">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => set('is_active', e.target.checked)}
                className="w-4 h-4"
              />
              <span className="text-sm text-slate-300">enabled</span>
            </label>
          </Field>
        </div>

        <Field label="Greeting">
          <textarea
            value={form.greeting}
            onChange={(e) => set('greeting', e.target.value)}
            rows={2}
            className={`${inputCls} resize-none`}
            placeholder="Hi! This is Ryan…"
          />
        </Field>

        <Field label="Persona (system prompt)">
          <textarea
            value={form.persona}
            onChange={(e) => set('persona', e.target.value)}
            rows={8}
            className={`${inputCls} resize-none font-mono text-xs`}
            placeholder="You are…"
          />
        </Field>

        <Field label="Tools">
          {tools.length === 0 ? (
            <p className="text-slate-500 text-sm">No tools defined. Create some in the Tools tab.</p>
          ) : (
            <div className="grid grid-cols-2 gap-1.5 max-h-40 overflow-y-auto p-2 rounded-xl border border-slate-700 bg-slate-900/40">
              {tools.map((t) => (
                <label key={t.id} className="flex items-center gap-2 text-sm text-slate-300">
                  <input
                    type="checkbox"
                    checked={form.tool_ids.includes(t.id)}
                    onChange={() => toggleTool(t.id)}
                    className="w-4 h-4"
                  />
                  <span className="truncate">{t.name}</span>
                </label>
              ))}
            </div>
          )}
        </Field>

        {error && <ErrorBox text={error} />}

        <FormActions busy={busy} onCancel={onClose} />
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Tools panel
// ---------------------------------------------------------------------------
function ToolsPanel() {
  const [tools, setTools] = useState([]);
  const [handlerKeys, setHandlerKeys] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null);

  const fetchTools = useCallback(async () => {
    setError(null);
    try {
      const [t, h] = await Promise.all([
        apiGet('/admin/tools', { auth: true }),
        apiGet('/admin/tools/handler-keys', { auth: true }),
      ]);
      setTools(t);
      setHandlerKeys(h);
    } catch (err) {
      setError(err.message || 'Failed to load tools');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchTools();
  }, [fetchTools]);

  const onDelete = async (tool) => {
    if (!confirm(`Delete tool "${tool.name}"? Agents using it will lose access.`)) return;
    try {
      await apiDelete(`/admin/tools/${tool.id}`, { auth: true });
      await fetchTools();
    } catch (err) {
      setError(err.message || 'Delete failed');
    }
  };

  return (
    <Panel
      title="Tools"
      icon={Wrench}
      loading={loading}
      error={error}
      onRefresh={() => {
        setLoading(true);
        fetchTools();
      }}
      actionLabel="New tool"
      onAction={() => setEditing('new')}
    >
      {tools.length === 0 ? (
        <EmptyState what="tools" />
      ) : (
        <ul className="space-y-3">
          {tools.map((t) => (
            <li key={t.id} className="glass-panel rounded-2xl p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-slate-100 font-bold font-mono">{t.name}</h3>
                    {!t.is_active && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700/60 text-slate-300">
                        inactive
                      </span>
                    )}
                  </div>
                  <p className="text-slate-400 text-sm mt-0.5 line-clamp-2">{t.description}</p>
                  <div className="text-slate-500 text-xs mt-1 font-mono">
                    handler: <span className="text-amber-300">{t.handler_key}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <IconBtn onClick={() => setEditing(t)} icon={Pencil} label="Edit" />
                  <IconBtn onClick={() => onDelete(t)} icon={Trash2} label="Delete" danger />
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <ToolEditor
          tool={editing === 'new' ? null : editing}
          handlerKeys={handlerKeys}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            fetchTools();
          }}
        />
      )}
    </Panel>
  );
}

function ToolEditor({ tool, handlerKeys, onClose, onSaved }) {
  const [form, setForm] = useState(
    tool
      ? { ...tool, parameters: tool.parameters || {} }
      : { ...EMPTY_TOOL }
  );
  const [paramsText, setParamsText] = useState(
    JSON.stringify(tool?.parameters || {}, null, 2)
  );
  const [paramsError, setParamsError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setParamsError(null);

    // Validate the parameters JSON before sending.
    let parameters = {};
    try {
      parameters = paramsText.trim() ? JSON.parse(paramsText) : {};
      if (typeof parameters !== 'object' || Array.isArray(parameters)) {
        throw new Error('parameters must be a JSON object');
      }
    } catch (err) {
      setParamsError(`Invalid JSON: ${err.message}`);
      setBusy(false);
      return;
    }

    try {
      const payload = {
        name: form.name.trim(),
        description: form.description,
        parameters,
        handler_key: form.handler_key,
        is_active: form.is_active,
      };
      if (tool) {
        await apiPut(`/admin/tools/${tool.id}`, payload, { auth: true });
      } else {
        await apiPost('/admin/tools', payload, { auth: true });
      }
      onSaved();
    } catch (err) {
      setError(err.message || 'Save failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal onClose={onClose} title={tool ? `Edit ${tool.name}` : 'New tool'}>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Name (Deepgram function name)" required>
          <input
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            required
            className={`${inputCls} font-mono`}
            placeholder="gja_get_menu"
          />
        </Field>

        <Field label="Description">
          <textarea
            value={form.description}
            onChange={(e) => set('description', e.target.value)}
            rows={3}
            className={`${inputCls} resize-none`}
            placeholder="What this tool does, shown to the LLM…"
          />
        </Field>

        <Field label="Handler key" required>
          {handlerKeys.length === 0 ? (
            <input
              value={form.handler_key}
              onChange={(e) => set('handler_key', e.target.value)}
              required
              className={`${inputCls} font-mono`}
              placeholder="menu.list"
            />
          ) : (
            <select
              value={form.handler_key}
              onChange={(e) => set('handler_key', e.target.value)}
              required
              className={`${inputCls} font-mono`}
            >
              <option value="">Select a handler…</option>
              {handlerKeys.map((h) => (
                <option key={h.key} value={h.key}>
                  {h.key} — {h.label}
                </option>
              ))}
            </select>
          )}
        </Field>

        <Field label="Parameters (JSON schema fragment)">
          <textarea
            value={paramsText}
            onChange={(e) => setParamsText(e.target.value)}
            rows={8}
            className={`${inputCls} resize-none font-mono text-xs`}
            placeholder={`{"type":"object","properties":{},"required":[]}`}
          />
          {paramsError && <p className="text-red-300 text-xs mt-1">{paramsError}</p>}
        </Field>

        <Field label="Active">
          <label className="flex items-center gap-2 h-[42px]">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => set('is_active', e.target.checked)}
              className="w-4 h-4"
            />
            <span className="text-sm text-slate-300">enabled</span>
          </label>
        </Field>

        {error && <ErrorBox text={error} />}

        <FormActions busy={busy} onCancel={onClose} />
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Shared layout primitives
// ---------------------------------------------------------------------------
const inputCls =
  'w-full bg-slate-800/50 border border-slate-700 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all';

function Panel({ title, icon: Icon, loading, error, onRefresh, actionLabel, onAction, children }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <Icon className="w-6 h-6 text-amber-400" />
          {title}
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            disabled={loading}
            className="flex items-center gap-2 text-sm text-slate-300 hover:text-white bg-slate-800/60 hover:bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 transition-colors"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Refresh
          </button>
          <button
            onClick={onAction}
            className="flex items-center gap-2 text-sm text-white bg-blue-600 hover:bg-blue-500 rounded-lg px-3 py-2 transition-colors"
          >
            <Plus className="w-4 h-4" />
            {actionLabel}
          </button>
        </div>
      </div>

      {error && <ErrorBox text={error} className="mb-4" />}

      {loading && children?.props ? null : children}
    </div>
  );
}

function EmptyState({ what }) {
  return (
    <div className="glass-panel rounded-2xl p-8 text-center text-slate-500">
      No {what} yet. Click the button above to create one.
    </div>
  );
}

function Field({ label, required, children }) {
  return (
    <div>
      <label className="block text-slate-300 font-medium mb-2 text-sm">
        {label}
        {required && <span className="text-red-400"> *</span>}
      </label>
      {children}
    </div>
  );
}

function IconBtn({ onClick, icon: Icon, label, danger }) {
  return (
    <button
      onClick={onClick}
      title={label}
      className={`flex items-center justify-center w-9 h-9 rounded-lg border transition-colors ${
        danger
          ? 'text-red-300 border-transparent hover:text-red-200 hover:border-red-500/30'
          : 'text-slate-300 border-slate-700 hover:bg-slate-700/60 hover:text-white'
      }`}
    >
      <Icon className="w-4 h-4" />
    </button>
  );
}

function ErrorBox({ text, className = '' }) {
  return (
    <div
      className={`rounded-xl border border-red-500/30 bg-red-500/10 text-red-200 px-4 py-3 text-sm ${className}`}
    >
      {text}
    </div>
  );
}

function FormActions({ busy, onCancel }) {
  return (
    <div className="flex items-center justify-end gap-2 pt-2">
      <button
        type="button"
        onClick={onCancel}
        className="flex items-center gap-1 text-sm text-slate-300 hover:text-white border border-slate-700 rounded-lg px-3 py-2 transition-colors"
      >
        <X className="w-4 h-4" />
        Cancel
      </button>
      <button
        type="submit"
        disabled={busy}
        className="flex items-center gap-2 text-sm text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-60 rounded-lg px-3 py-2 transition-colors"
      >
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
        Save
      </button>
    </div>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto glass-panel rounded-3xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-100">{title}</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-2 rounded-lg hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
