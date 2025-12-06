export type ServerStatus = { down: boolean };

let status: ServerStatus = { down: false };

const emit = () => {
  try {
    window.dispatchEvent(new CustomEvent<ServerStatus>('server:status', { detail: { ...status } }));
  } catch {}
};

export const getServerStatus = (): ServerStatus => ({ ...status });
export const isServerDown = (): boolean => status.down;
export const setServerDown = () => { status = { down: true }; emit(); };
export const setServerUp = () => { status = { down: false }; emit(); };

export const subscribeServerStatus = (cb: (s: ServerStatus) => void) => {
  const handler = (e: Event) => cb((e as CustomEvent<ServerStatus>).detail);
  window.addEventListener('server:status', handler as EventListener);
  return () => window.removeEventListener('server:status', handler as EventListener);
};

