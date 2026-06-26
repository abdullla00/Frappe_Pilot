import type { NavIconName } from '@/components/NavIcon';

export type NavItem = {
  to?: string;
  href?: string;
  label: string;
  icon: NavIconName;
  end?: boolean;
};

export type NavSection = {
  title: string;
  items: NavItem[];
};

export const navSections: NavSection[] = [
  {
    title: 'Console',
    items: [
      { to: '/', label: 'Home', icon: 'home', end: true },
      { to: '/chat', label: 'Chat', icon: 'chat' },
      { to: '/executions', label: 'Executions', icon: 'executions' },
    ],
  },
  {
    title: 'Build',
    items: [
      { to: '/agents', label: 'Agents', icon: 'agents' },
      { to: '/knowledge', label: 'Knowledge', icon: 'knowledge' },
      { to: '/flows', label: 'Flows', icon: 'flows' },
      { to: '/mcp', label: 'MCP', icon: 'mcp' },
    ],
  },
  {
    title: 'Admin',
    items: [
      { to: '/roles', label: 'Roles', icon: 'roles' },
      { href: '/app/pilot-settings', label: 'Pilot Settings', icon: 'settings' },
    ],
  },
];

export type FeatureCard = {
  to?: string;
  href?: string;
  title: string;
  description: string;
  icon: NavIconName;
};

export const featureCards: FeatureCard[] = [
  { to: '/agents', title: 'Agents', description: 'Configure and manage AI agents.', icon: 'agents' },
  { to: '/chat', title: 'Chat', description: 'Talk to an agent in real time.', icon: 'chat' },
  { to: '/executions', title: 'Executions', description: 'Review recent agent runs.', icon: 'executions' },
  { to: '/knowledge', title: 'Knowledge', description: 'Manage knowledge sources.', icon: 'knowledge' },
  { to: '/flows', title: 'Flows', description: 'Design automation flows.', icon: 'flows' },
  { to: '/mcp', title: 'MCP', description: 'Connect MCP tool servers.', icon: 'mcp' },
  { to: '/roles', title: 'Roles', description: 'Control pilot access roles.', icon: 'roles' },
  { href: '/app/pilot-settings', title: 'Settings', description: 'Providers, languages, and access.', icon: 'settings' },
];
