import { useEffect, useState } from 'react';
import { getRoles } from '@/services/agentApi';
import type { PilotRole } from '@/types/pilot.types';

export function RolesPage() {
  const [roles, setRoles] = useState<PilotRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getRoles()
      .then(setRoles)
      .catch((err: Error) => setError(err.message || 'Failed to load roles'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-slate-500">Loading roles…</p>;
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
      <h2 className="text-xl font-semibold text-slate-900 mb-4">Roles</h2>
      {roles.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
          No pilot roles configured.
        </div>
      ) : (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {roles.map((role) => (
            <li key={role.role_name} className="px-4 py-3">
              <p className="font-medium text-slate-900">{role.role_name}</p>
              {role.description && (
                <p className="text-sm text-slate-500 mt-0.5">{role.description}</p>
              )}
              {role.capabilities && role.capabilities.length > 0 && (
                <p className="text-xs text-slate-400 mt-2">
                  {role.capabilities.length} capabilities
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
