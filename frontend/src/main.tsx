import "ace-builds/src-noconflict/ace";
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError } from 'axios'
import App from './App.tsx'
import './index.css'

// Network error codes that indicate server is unreachable
const NETWORK_ERROR_CODES = new Set([
  "ERR_NETWORK",
  "ECONNABORTED",
  "ERR_CONNECTION_REFUSED",
  "ERR_CONNECTION_RESET",
  "ERR_SOCKET_NOT_CONNECTED",
  "ENOTFOUND",
]);

// Custom retry function that limits retries on server/network errors
const shouldRetry = (failureCount: number, error: unknown): boolean => {
  const maxRetries = 2;

  if (failureCount >= maxRetries) {
    return false;
  }

  if (error instanceof AxiosError) {
    const status = error.response?.status;
    const code = error.code;

    // Don't retry on server errors (5xx)
    if (status && status >= 500) {
      return false;
    }

    // Don't retry on network errors (server unreachable)
    if (NETWORK_ERROR_CODES.has(code ?? "")) {
      return false;
    }
  }

  return true;
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: shouldRetry,
    },
  },
})

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);
