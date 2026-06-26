export type NavIconName =
  | 'home'
  | 'agents'
  | 'chat'
  | 'executions'
  | 'knowledge'
  | 'flows'
  | 'mcp'
  | 'roles'
  | 'settings'
  | 'external';

const paths: Record<NavIconName, JSX.Element> = {
  home: (
    <>
      <path d="M3 10.5L12 3l9 7.5V20a1.5 1.5 0 01-1.5 1.5H15v-6H9v6H4.5A1.5 1.5 0 013 20v-9.5z" />
    </>
  ),
  agents: (
    <>
      <rect x="4" y="8" width="16" height="12" rx="2" />
      <path d="M9 8V6a3 3 0 016 0v2" />
      <circle cx="12" cy="14" r="1.5" />
    </>
  ),
  chat: (
    <>
      <path d="M4 5h16v10H8l-4 4V5z" />
    </>
  ),
  executions: (
    <>
      <path d="M5 5h14v14H5z" />
      <path d="M9 12h6M9 9h4M9 15h5" />
    </>
  ),
  knowledge: (
    <>
      <path d="M5 4h10a2 2 0 012 2v14l-7-4-7 4V6a2 2 0 012-2z" />
    </>
  ),
  flows: (
    <>
      <circle cx="6" cy="6" r="2" />
      <circle cx="18" cy="12" r="2" />
      <circle cx="8" cy="18" r="2" />
      <path d="M8 6h8M16 8v2M10 16h6" />
    </>
  ),
  mcp: (
    <>
      <rect x="3" y="4" width="18" height="6" rx="1" />
      <rect x="3" y="14" width="18" height="6" rx="1" />
      <path d="M7 7h.01M7 17h.01" />
    </>
  ),
  roles: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 19c0-3 2.5-5 6-5s6 2 6 5" />
      <path d="M16 8h5M18.5 6v4" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
    </>
  ),
  external: (
    <>
      <path d="M14 3h7v7" />
      <path d="M10 14L21 3" />
      <path d="M18 14v5H3V6h5" />
    </>
  ),
};

type NavIconProps = {
  name: NavIconName;
  className?: string;
};

export function NavIcon({ name, className = '' }: NavIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-4 w-4 shrink-0 ${className}`}
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
