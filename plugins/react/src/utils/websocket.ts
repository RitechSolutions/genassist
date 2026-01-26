/**
 * This factory ensures the library uses the native browser WebSocket API
 * and does not require Node.js-specific WebSocket packages or shims.
 */

export function createWebSocket(
  url: string,
  protocols?: string | string[]
): WebSocket {
  // Use native browser WebSocket and polyfilled by bundlers when needed
  if (typeof globalThis !== 'undefined' && globalThis.WebSocket) {
    return new globalThis.WebSocket(url, protocols);
  }
  
  // Fallback for environments where globalThis might not be available
  if (typeof window !== 'undefined' && window.WebSocket) {
    return new window.WebSocket(url, protocols);
  }
  
  // Last resort - should not happen in browser environments
  if (typeof WebSocket !== 'undefined') {
    return new WebSocket(url, protocols);
  }
  
  throw new Error(
    'WebSocket is not available in this environment. ' +
    'This library requires a browser environment with native WebSocket support.'
  );
}

export function redactUrl(url: string): string {
  try {
    const urlObj = new URL(url);
    // Redact api_key, access_token, and access_token query params
    if (urlObj.searchParams.has('api_key')) {
      urlObj.searchParams.set('api_key', '[REDACTED]');
    }
    if (urlObj.searchParams.has('access_token')) {
      urlObj.searchParams.set('access_token', '[REDACTED]');
    }
    if (urlObj.searchParams.has('guest_token')) {
      urlObj.searchParams.set('guest_token', '[REDACTED]');
    }
    return urlObj.toString();
  } catch {
    // If URL parsing fails, return a safe redacted version
    return url.replace(/[?&](api_key|access_token|guest_token)=[^&]*/g, (match) => {
      const param = match.split('=')[0];
      return `${param}=[REDACTED]`;
    });
  }
}

export function createWebSocketDiagnostic(
  event: CloseEvent | Event,
  url: string
): string {
  const redactedUrl = redactUrl(url);
  const parts: string[] = [];
  
  parts.push(`WebSocket connection issue`);
  parts.push(`URL: ${redactedUrl}`);
  
  if (event instanceof CloseEvent) {
    parts.push(`Close code: ${event.code}`);
    if (event.reason) {
      parts.push(`Reason: ${event.reason}`);
    }
    parts.push(`Was clean: ${event.wasClean}`);
  }
  
  if ('readyState' in event && typeof (event as any).readyState === 'number') {
    const states = ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'];
    const state = states[(event as any).readyState] || 'UNKNOWN';
    parts.push(`Ready state: ${state} (${(event as any).readyState})`);
  }
  
  return parts.join(' | ');
}

