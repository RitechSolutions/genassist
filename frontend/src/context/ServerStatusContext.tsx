import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { getServerStatus, subscribeServerStatus, type ServerStatus } from '@/config/serverStatus';

type Ctx = { status: ServerStatus; isOffline: boolean };

const C = createContext<Ctx | undefined>(undefined);

export const ServerStatusProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<ServerStatus>(() => getServerStatus());
  const [isOffline, setIsOffline] = useState<boolean>(typeof navigator !== 'undefined' ? !navigator.onLine : false);

  useEffect(() => {
    const unsub = subscribeServerStatus(setStatus);
    const onOnline = () => setIsOffline(false);
    const onOffline = () => setIsOffline(true);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    return () => { unsub(); window.removeEventListener('online', onOnline); window.removeEventListener('offline', onOffline); };
  }, []);

  const value = useMemo(() => ({ status, isOffline }), [status, isOffline]);

  return <C.Provider value={value}>{children}</C.Provider>;
};

export const useServerStatus = (): Ctx => {
  const ctx = useContext(C);
  if (!ctx) throw new Error('useServerStatus must be used inside ServerStatusProvider');
  return ctx;
};

