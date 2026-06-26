import { useEffect } from 'react';

export function SettingsRedirect() {
  useEffect(() => {
    window.location.href = '/app/pilot-settings';
  }, []);

  return (
    <div className="text-slate-500">
      Redirecting to Pilot Settings…
    </div>
  );
}
