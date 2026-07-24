import React, { useState } from 'react';
import { probeApiHealth } from '@/config/api';

const ServerDownPage: React.FC = () => {
  const [pending, setPending] = useState(false);
  return (
    <div className="min-h-screen w-full bg-muted flex flex-col">
      <div className="w-full bg-red-50 text-red-800 border-b border-red-200 dark:bg-red-500/15 dark:text-red-400 dark:border-red-500/30 px-4 py-2 text-sm">
        Server connection error
      </div>
      <div className="flex-1 flex items-start justify-center p-6">
        <div className="w-full max-w-3xl bg-card rounded-lg shadow-sm border border-border">
          <div className="px-6 py-5">
            <h1 className="text-2xl font-semibold mb-3">Server Connection Error</h1>
            <p className="text-muted-foreground mb-4">Unable to connect to the server. This may be because:</p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>The server is not running</li>
              <li>There is a network issue</li>
              <li>The server configuration is incorrect</li>
            </ul>
            <p className="text-muted-foreground mt-4">Please check your server configuration and try again.</p>
            <div className="mt-6 flex justify-end">
              <button
                onClick={async () => { setPending(true); await probeApiHealth(); setPending(false); }}
                disabled={pending}
                className="inline-flex items-center rounded-md bg-destructive px-4 py-2 text-destructive-foreground text-sm font-medium hover:bg-destructive/90 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-destructive"
              >
                {pending ? 'Checking…' : 'Retry'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ServerDownPage;

