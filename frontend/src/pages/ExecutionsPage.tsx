import { useEffect, useState } from 'react';
import { getExecutions } from '@/services/agentApi';
import type { PilotAgentRun } from '@/types/pilot.types';

export function ExecutionsPage() {
  const [runs, setRuns] = useState<PilotAgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getExecutions()
      .then(setRuns)
      .catch((err: Error) => setError(err.message || 'Failed to load executions'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-slate-500">Loading executions…</p>;
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
      <h2 className="text-xl font-semibold text-slate-900 mb-4">Executions</h2>
      {runs.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
          No agent runs recorded yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="px-4 py-3 font-medium">Run</th>
                <th className="px-4 py-3 font-medium">Agent</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Started</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {runs.map((run) => (
                <tr key={run.name}>
                  <td className="px-4 py-3 font-medium text-slate-900">{run.name}</td>
                  <td className="px-4 py-3 text-slate-600">{run.agent || '—'}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                      {run.status || 'Unknown'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {run.start_time ? new Date(run.start_time).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
