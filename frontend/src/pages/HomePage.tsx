import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PilotLogo } from '@/components/PilotLogo';
import { NavIcon } from '@/components/NavIcon';
import { featureCards } from '@/lib/nav';
import { fetchPilotStats, formatCost, type PilotStats } from '@/lib/stats';

const emptyStats: PilotStats = {
  total_runs: 0,
  success_count: 0,
  success_rate: 0,
  total_cost: 0,
  currency: 'USD',
};

export function HomePage() {
  const [stats, setStats] = useState<PilotStats>(emptyStats);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState(false);

  useEffect(() => {
    let active = true;
    fetchPilotStats()
      .then((data) => {
        if (active) setStats(data);
      })
      .catch(() => {
        if (active) setStatsError(true);
      })
      .finally(() => {
        if (active) setStatsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="max-w-5xl space-y-8">
      <section className="pilot-gradient-hero rounded-2xl border border-pilot-100 p-8 shadow-sm">
        <PilotLogo variant="full" className="mb-4" />
        <h2 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome to Frappe Pilot</h2>
        <p className="mt-2 max-w-2xl text-slate-600">
          Manage AI agents, run conversations, connect knowledge and MCP tools, and monitor executions from one
          console.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            to="/chat"
            className="inline-flex items-center rounded-lg bg-pilot-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-pilot-700 transition"
          >
            Start Chat
          </Link>
          <Link
            to="/agents"
            className="inline-flex items-center rounded-lg border border-pilot-200 bg-white px-4 py-2.5 text-sm font-semibold text-pilot-700 hover:bg-pilot-50 transition"
          >
            Manage Agents
          </Link>
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">Live metrics</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <StatTile
            label="Total Agent Runs"
            value={statsLoading ? '…' : String(stats.total_runs)}
            tone="blue"
          />
          <StatTile
            label="Success Rate"
            value={statsLoading ? '…' : `${stats.success_rate}%`}
            tone="green"
            hint={statsError ? 'Unable to load' : undefined}
          />
          <StatTile
            label="Total Cost"
            value={statsLoading ? '…' : formatCost(stats.total_cost, stats.currency)}
            tone="amber"
          />
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">Explore</h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {featureCards.map((card) => {
            const inner = (
              <>
                <div className="flex items-center gap-2 text-pilot-600">
                  <NavIcon name={card.icon} />
                  <h3 className="font-semibold text-slate-900">{card.title}</h3>
                </div>
                <p className="mt-2 text-sm text-slate-500">{card.description}</p>
              </>
            );
            const className = 'pilot-card-hover rounded-xl border border-slate-200 bg-white p-5 shadow-sm block';

            if (card.href) {
              return (
                <a key={card.title} href={card.href} className={className}>
                  {inner}
                </a>
              );
            }
            return (
              <Link key={card.title} to={card.to!} className={className}>
                {inner}
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}

type StatTileProps = {
  label: string;
  value: string;
  tone: 'blue' | 'green' | 'amber';
  hint?: string;
};

function StatTile({ label, value, tone, hint }: StatTileProps) {
  const toneClass =
    tone === 'green' ? 'text-emerald-600' : tone === 'amber' ? 'text-amber-600' : 'text-blue-600';

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${toneClass}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-red-500">{hint}</div>}
    </div>
  );
}
