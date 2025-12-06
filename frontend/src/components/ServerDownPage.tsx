import React, { useState } from 'react';
import { probeApiHealth } from '@/config/api';

const ServerDownPage: React.FC = () => {
  const [pending, setPending] = useState(false);
  return (
    <div className="min-h-screen w-full bg-zinc-100 flex flex-col">
      <div className="w-full bg-red-50 text-red-800 border-b border-red-200 px-4 py-2 text-sm">
        Server connection error
      </div>
      <div className="flex-1 flex items-start justify-center p-6">
        <div className="w-full max-w-3xl bg-white rounded-lg shadow-sm border border-zinc-200">
          <div className="px-6 py-5">
            <h1 className="text-2xl font-semibold mb-3">Server Connection Error</h1>
            <p className="text-zinc-700 mb-4">Unable to connect to the server. This may be because:</p>
            <ul className="list-disc pl-6 space-y-1 text-zinc-700">
              <li>The server is not running</li>
              <li>There is a network issue</li>
              <li>The server configuration is incorrect</li>
            </ul>
            <p className="text-zinc-700 mt-4">Please check your server configuration and try again.</p>
            <div className="mt-6 flex justify-end">
              <button
                onClick={async () => { setPending(true); await probeApiHealth(); setPending(false); }}
                disabled={pending}
                className="inline-flex items-center rounded-md bg-red-600 px-4 py-2 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-red-500"
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

