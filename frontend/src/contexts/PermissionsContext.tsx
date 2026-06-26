import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { getMe } from '@/services/agentApi';
import type { MeResponse } from '@/types/pilot.types';

interface PermissionsContextType {
  pilotRole: string | null;
  capabilities: string[];
  fullName: string;
  user: string;
  isLoading: boolean;
  hasCapability: (capability: string) => boolean;
  refresh: () => Promise<void>;
}

const PermissionsContext = createContext<PermissionsContextType | undefined>(undefined);

interface PermissionsProviderProps {
  children: ReactNode;
}

export function PermissionsProvider({ children }: PermissionsProviderProps) {
  const [data, setData] = useState<MeResponse>({
    user: '',
    full_name: '',
    pilot_role: null,
    capabilities: [],
  });
  const [isLoading, setIsLoading] = useState(true);

  const load = async () => {
    setIsLoading(true);
    try {
      const me = await getMe();
      setData(me);
    } catch {
      const bootUser = window.frappe?.boot?.user;
      const userName =
        typeof bootUser === 'object' && bootUser !== null ? bootUser.name || '' : '';
      const fullName =
        typeof bootUser === 'object' && bootUser !== null ? bootUser.full_name || '' : '';
      setData({
        user: userName,
        full_name: fullName,
        pilot_role: null,
        capabilities: [],
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const hasCapability = (capability: string): boolean => {
    return data.capabilities.includes(capability);
  };

  return (
    <PermissionsContext.Provider
      value={{
        pilotRole: data.pilot_role,
        capabilities: data.capabilities,
        fullName: data.full_name,
        user: data.user,
        isLoading,
        hasCapability,
        refresh: load,
      }}
    >
      {children}
    </PermissionsContext.Provider>
  );
}

export function usePermissions(): PermissionsContextType {
  const ctx = useContext(PermissionsContext);
  if (!ctx) {
    throw new Error('usePermissions must be used inside <PermissionsProvider>');
  }
  return ctx;
}
