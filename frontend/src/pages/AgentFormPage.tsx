import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { createAgent, getAgent, updateAgent } from '@/services/agentApi';

export function AgentFormPage() {
  const { name } = useParams<{ name: string }>();
  const isNew = name === 'new' || !name;
  const navigate = useNavigate();

  const [agentName, setAgentName] = useState('');
  const [description, setDescription] = useState('');
  const [instructions, setInstructions] = useState('');
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isNew || !name) return;

    getAgent(name)
      .then((agent) => {
        setAgentName(agent.agent_name || '');
        setDescription(agent.description || '');
        setInstructions(agent.instructions || '');
      })
      .catch((err: Error) => setError(err.message || 'Failed to load agent'))
      .finally(() => setLoading(false));
  }, [isNew, name]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError('');

    const payload = {
      agent_name: agentName,
      description,
      instructions,
    };

    try {
      if (isNew) {
        const created = await createAgent(payload);
        navigate(`/agents/${encodeURIComponent(created.name)}`);
      } else if (name) {
        await updateAgent(name, payload);
        navigate('/agents');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save agent');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="text-slate-500">Loading agent…</p>;
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <Link to="/agents" className="text-sm text-pilot-600 hover:text-pilot-700">
          ← Back to agents
        </Link>
        <h2 className="text-xl font-semibold text-slate-900 mt-2">
          {isNew ? 'New Agent' : 'Edit Agent'}
        </h2>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-slate-200 bg-white p-6">
        <div>
          <label htmlFor="agent_name" className="block text-sm font-medium text-slate-700">
            Agent Name
          </label>
          <input
            id="agent_name"
            required
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-pilot-500 focus:outline-none focus:ring-1 focus:ring-pilot-500"
          />
        </div>
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-slate-700">
            Description
          </label>
          <input
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-pilot-500 focus:outline-none focus:ring-1 focus:ring-pilot-500"
          />
        </div>
        <div>
          <label htmlFor="instructions" className="block text-sm font-medium text-slate-700">
            Instructions
          </label>
          <textarea
            id="instructions"
            rows={6}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-pilot-500 focus:outline-none focus:ring-1 focus:ring-pilot-500"
          />
        </div>
        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-pilot-600 px-4 py-2 text-sm font-medium text-white hover:bg-pilot-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
          <Link
            to="/agents"
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
