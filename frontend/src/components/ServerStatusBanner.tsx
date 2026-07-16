import React, { useState } from 'react';
import { useServerStatus } from '@/context/ServerStatusContext';
import { Alert, AlertDescription } from '@/components/alert';
import { probeApiHealth } from '@/config/api';

const ServerStatusBanner: React.FC = () => {
  const { status, isOffline } = useServerStatus();
  const [pending, setPending] = useState(false);
  const show = isOffline || status.down;
  if (!show) return null;

  return (
    <div className="sticky top-0 z-50">
      <Alert className="rounded-none border-0 text-red-900 bg-red-50">
        <AlertDescription className="flex items-center justify-between">
          <span className="font-medium">Server connection error.</span>
          <button
            onClick={async () => { setPending(true); await probeApiHealth(); setPending(false); }}
            disabled={pending}
            className="ml-4 inline-flex items-center rounded-md bg-destructive px-3 py-1 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-60"
          >
            {pending ? 'Checking…' : 'Retry'}
          </button>
        </AlertDescription>
      </Alert>
    </div>
  );
};

export default ServerStatusBanner;

