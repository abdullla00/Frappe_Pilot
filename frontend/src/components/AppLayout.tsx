import { NavLink, Outlet } from 'react-router-dom';
import { PilotLogo } from '@/components/PilotLogo';
import { NavIcon } from '@/components/NavIcon';
import { navSections } from '@/lib/nav';
import { usePermissions } from '@/contexts/PermissionsContext';

function navLinkClass(isActive: boolean): string {
  return [
    'group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors border-l-2',
    isActive
      ? 'border-pilot-500 bg-pilot-50 text-pilot-700'
      : 'border-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  ].join(' ');
}

export function AppLayout() {
  const { fullName, user, isLoading } = usePermissions();
  const initial = (fullName || user || '?').charAt(0).toUpperCase();

  return (
    <div className="min-h-screen flex bg-gradient-to-br from-pilot-50 via-white to-slate-50">
      <aside className="w-60 shrink-0 border-r border-slate-200/80 bg-white/90 backdrop-blur flex flex-col">
        <div className="px-4 py-5 border-b border-pilot-100 pilot-sidebar-header">
          <PilotLogo variant="full" />
        </div>

        <nav className="flex-1 p-3 space-y-5 overflow-y-auto">
          {navSections.map((section) => (
            <div key={section.title}>
              <div className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                {section.title}
              </div>
              <div className="space-y-0.5">
                {section.items.map((item) =>
                  item.href ? (
                    <a key={item.label} href={item.href} className={navLinkClass(false)}>
                      <NavIcon name={item.icon} />
                      {item.label}
                    </a>
                  ) : (
                    <NavLink
                      key={item.label}
                      to={item.to!}
                      end={item.end}
                      className={({ isActive }) => navLinkClass(isActive)}
                    >
                      <NavIcon name={item.icon} />
                      {item.label}
                    </NavLink>
                  )
                )}
              </div>
            </div>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-200 flex items-center gap-3">
          <div className="h-9 w-9 rounded-full bg-pilot-100 text-pilot-700 flex items-center justify-center text-sm font-semibold">
            {initial}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium text-slate-800 truncate">
              {isLoading ? 'Loading…' : fullName || 'Guest'}
            </div>
            <div className="text-xs text-slate-500 truncate">{user || '—'}</div>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-slate-200/80 bg-white/70 backdrop-blur px-6 flex items-center justify-between">
          <span className="text-sm font-medium text-slate-600">Pilot console</span>
          <a
            href="/desk/pilot"
            className="text-xs font-medium text-pilot-600 hover:text-pilot-700 hover:underline"
          >
            Open desk workspace
          </a>
        </header>
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
