import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getAgents } from '@/services/agentApi';
import type { PilotAgent } from '@/types/pilot.types';

export function AgentsPage() {
  const [agents, setAgents] = useState<PilotAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getAgents()
      .then(setAgents)
      .catch((err: Error) => setError(err.message || 'Failed to load agents'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-slate-500">Loading agents…</p>;
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Agents</h2>
          <p className="text-sm text-slate-500 mt-1">{agents.length} configured</p>
        </div>
        <Link
          to="/agents/new"
          className="rounded-md bg-pilot-600 px-4 py-2 text-sm font-medium text-white hover:bg-pilot-700"
        >
          New Agent
        </Link>
      </div>

      {agents.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
          No agents yet. Create your first agent to get started.
        </div>
      ) : (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {agents.map((agent) => (
            <li key={agent.name} className="flex items-center justify-between px-4 py-3">
              <div>
                <Link
                  to={`/agents/${encodeURIComponent(agent.name)}`}
                  className="font-medium text-slate-900 hover:text-pilot-700"
                >
                  {agent.agent_name || agent.name}
                </Link>
                {agent.description && (
                  <p className="text-sm text-slate-500 mt-0.5 line-clamp-1">{agent.description}</p>
                )}
                <p className="text-xs text-slate-400 mt-1">
                  {agent.model || 'No model'} · {agent.disabled ? 'Disabled' : 'Active'}
                </p>
              </div>
              <Link
                to={`/chat?agent=${encodeURIComponent(agent.name)}`}
                className="text-sm text-pilot-600 hover:text-pilot-700 font-medium"
              >
                Chat
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
