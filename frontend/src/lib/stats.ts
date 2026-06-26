import { call } from '@/lib/frappe-sdk';

export type PilotStats = {
  total_runs: number;
  success_count: number;
  success_rate: number;
  total_cost: number;
  currency: string;
};

export async function fetchPilotStats(): Promise<PilotStats> {
  const result = await call.get('frappe_pilot.api.workspace.get_pilot_stats');
  return (result as { message: PilotStats }).message;
}

export function formatCost(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}
