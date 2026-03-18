## WebSocket Standalone Service – Change Summary & Impact

This document explains what changed with the standalone WebSocket service, how it differs from the previous (backward‑compatible) mode, and what the impact is for different teams.

---

## 1. Overview

Your system now supports **two WebSocket deployment modes**:

- **Standalone WebSocket service (new / recommended)**
- **Backward‑compatibility mode (legacy, WebSockets co‑hosted with the HTTP API)**

The client code (frontend app and React SDK) automatically switches between these modes based on configuration.

---

## 2. Configuration & Modes

### 2.1 Frontend application

**Relevant env vars (e.g. `frontend/.env`):**

- **`VITE_WEBSOCKET_PUBLIC_URL`**
  Base URL of the WebSocket service (e.g. `wss://ws.example.com`).

- **`VITE_WEBSOCKET_VERSION`**
  `1` → legacy / embedded mode.
  `2` → new standalone WebSocket routes.

- **`VITE_WS`**
  `"true"` → WebSockets enabled.
  `"false"` → WebSockets disabled; use HTTP polling instead.

**Behavior in code (from `frontend/src/config/api.ts` and `frontend/src/views/ActiveConversations/hooks/useWebsocket.ts`):**

- `isWsEnabled` is computed from `VITE_WS` and controls if WebSockets are used at all.
- `getWsUrl()` returns `VITE_WEBSOCKET_PUBLIC_URL` (or rejects if WS is disabled).
- `getWsVersion()` uses `VITE_WEBSOCKET_VERSION` when set; otherwise defaults to `2` when `VITE_WEBSOCKET_PUBLIC_URL` is set (standalone), or `1` when falling back to API URL (backend-hosted).

Inside `useWebSocketTranscript`:

- When **`wsVersion === 1`** (legacy):

  ```ts
  wsUrl = `${wsBaseUrl}/conversations/ws/${conversationId}?access_token=${token}${langParam}&${queryString}${tenantParam}`;
  ```

- When **`wsVersion === 2`** (standalone):

  ```ts
  wsUrl = `${wsBaseUrl}/ws/conversations/${conversationId}?access_token=${token}${langParam}&${queryString}${tenantParam}`;
  ```

The **only difference is the route shape and (optionally) the host**; topics and payloads remain the same.

---

### 2.2 React SDK / external integrators

The React SDK (`plugins/react/src/services/chatService.ts`) also supports both modes.

**Constructor:**

```ts
constructor(
  baseUrl: string,
  websocketUrl: string | undefined,
  apiKey: string,
  metadata?: Record<string, any>,
  tenant?: string,
  language?: string,
  useWs: boolean = true,
  usePoll: boolean = false
) {
  this.baseUrl = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;

  if (websocketUrl && websocketUrl !== "") {
    // New websocket service
    this.wsVersion = 2;
    this.websocketUrl = websocketUrl.endsWith("/") ? websocketUrl.slice(0, -1) : websocketUrl;
  } else {
    // Backward-compat mode
    this.wsVersion = 1;
    this.websocketUrl = `${this.baseUrl.replace("http", "ws")}/api`;
  }

  // ...
}
```

**WebSocket connection URL:**

```ts
const topics = ["message", "takeover", "finalize"];
const topicsQuery = topics.map((t) => `topics=${t}`).join("&");

// Use guest_token if available, otherwise fall back to api_key
const authParam = this.guestToken
  ? `access_token=${encodeURIComponent(this.guestToken)}`
  : `api_key=${encodeURIComponent(this.apiKey)}`;

// Determine route based on version
const wsRoute = this.wsVersion === 1 ? `conversations/ws` : `ws/conversations`;

let wsUrl = `${this.websocketUrl}/${wsRoute}/${this.conversationId}?${authParam}&lang=en&${topicsQuery}`;

// Optional tenant
if (this.tenant) {
  wsUrl += `&x-tenant-id=${encodeURIComponent(this.tenant)}`;
}
```

**Modes:**

- **Backward‑compat (no `websocketUrl`):**

  ```ts
  new ChatService("https://api.example.com", undefined, "API_KEY");
  ```

  - `wsVersion = 1`
  - `websocketUrl = "ws://api.example.com/api"`
  - Final WS URL example:
    - `ws://api.example.com/api/conversations/ws/:conversationId?...`

- **Standalone WebSocket service (recommended):**

  ```ts
  new ChatService(
    "https://api.example.com",      // HTTP API
    "wss://ws.example.com",        // WS service
    "API_KEY"
  );
  ```

  - `wsVersion = 2`
  - `websocketUrl = "wss://ws.example.com"`
  - Final WS URL example:
    - `wss://ws.example.com/ws/conversations/:conversationId?...`

---

## 2.3 Backwards-compatible mode: GenAgentChat ↔ Backend communication

When using **backwards-compat mode** (no standalone WS service), GenAgentChat talks directly to the backend. The flow:

```
┌─────────────────┐                    ┌─────────────────────────────────────────┐
│   GenAgentChat   │                    │              Backend (FastAPI)           │
│   (React SDK)    │                    │                                         │
└────────┬────────┘                    └─────────────────────┬───────────────────┘
         │                                                    │
         │  1. POST /api/conversations/in-progress/start      │
         │     (api_key header or recaptcha)                  │
         │ ─────────────────────────────────────────────────>│
         │     ← conversation_id, guest_token                 │
         │                                                    │
         │  2. WebSocket connect (wsVersion=1)               │
         │     ws://host/api/conversations/ws/:convId         │
         │     ?api_key=... or ?access_token=...&topics=...   │
         │ ─────────────────────────────────────────────────>│
         │     SocketConnectionManager.connect()               │
         │     (subscribes to Redis websocket:* for this room)│
         │                                                    │
         │  3. PATCH /api/conversations/in-progress/update/:id│
         │     (send user message)                             │
         │ ─────────────────────────────────────────────────>│
         │                                                    │
         │     Backend: process_conversation_update_with_agent │
         │     → run_query_agent_logic()                       │
         │     → socket_connection_manager.broadcast(         │
         │         msg_type="message", payload={...}          │
         │       ) → Redis publish(websocket:tenant:convId)     │
         │                                                    │
         │  4. Redis subscriber (in SocketConnectionManager)  │
         │     receives message, forwards to WebSocket        │
         │     <─────────────────────────────────────────────│
         │     { type: "message", payload: { agent response }}│
         │                                                    │
         │  5. takeover / finalize: same broadcast pattern    │
         │                                                    │
└────────┴────────┘                    └─────────────────────┴───────────────────┘
```

**Important for backwards-compat:** Do **not** pass `websocketUrl` when using the backend-hosted WS. If you pass `websocketUrl` (e.g. `ws://localhost:8000/api`), the SDK uses wsVersion 2 and connects to `/api/ws/conversations/:id`, which the backend does **not** expose. The backend only exposes `/api/conversations/ws/:id`.

| Config | wsVersion | WebSocket path | Backend has it? |
|--------|-----------|----------------|-----------------|
| `websocketUrl` = undefined | 1 | `/api/conversations/ws/:id` | ✓ Yes |
| `websocketUrl` = `ws://host/api` | 2 | `/api/ws/conversations/:id` | ✗ No (standalone WS only) |

**Example-app for backwards-compat:**

```env
VITE_GENASSIST_CHAT_APIURL=http://localhost:8000
# Omit or leave empty for backend-hosted WS:
# VITE_GENASSIST_CHAT_WEBSOCKET_URL=
```

In code: `websocketUrl: undefined` or `websocketUrl: ""` so the SDK derives `ws://localhost:8000/api` and uses route `conversations/ws`.

**Frontend alignment:** When the frontend uses backend-hosted WS (`VITE_WEBSOCKET_VERSION=1`), it must pass `websocketUrl=undefined` to GenAgentChat so the SDK uses the same path as the dashboard/transcript hooks (`/api/conversations/ws/:id`). `GlobalChat` and `ChatAsCustomer` do this by checking `getWsVersion()` and only passing the URL when `wsVersion === 2`.

**Guest token auth:** The backend's conversation websocket (`/api/conversations/ws/:id`) supports guest tokens (from `start` response) via `socket_auth_conversation`. Guest tokens now include `read:in_progress_conversation` so GenAgentChat can connect with `access_token=guest_token`.

---

## 3. What Actually Changed?

### 3.1. URL / route structure

**Old / backward‑compat (embedded WS):**

- WS is assumed to live alongside the HTTP API.
- URL pattern:

  - Frontend hook:
    `wsBaseUrl + "/conversations/ws/:conversation_id?..."`
  - SDK:
    `ws://<API_HOST>/api/conversations/ws/:conversation_id?...`

**New standalone WS service:**

- WS can live on a separate host (e.g. `ws.example.com`) or separate service.
- URL pattern:

  - Frontend hook:
    `wsBaseUrl + "/ws/conversations/:conversation_id?..."`
  - SDK:
    `wss://<WS_HOST>/ws/conversations/:conversation_id?...`

**Important:** The **message format, topics (`message`, `statistics`, `finalize`, `takeover`, etc.), and auth query parameters** are intended to be the same across both modes. The main change is **where** and **under what path** the WebSocket endpoint is hosted.

---

## 4. Rationale for Standalone WebSocket Service

### 4.1. Scalability & performance

- WebSockets are long‑lived connections.
- Moving them into a dedicated service avoids tying up HTTP workers or API instances.
- You can scale WS instances independently from REST API instances.

### 4.2. Operational isolation

- Failures or overloads in the WS layer won’t directly bring down the core HTTP API.
- You can configure:
  - Different timeouts.
  - Different load‑balancer settings.
  - Different autoscaling rules.

### 4.3. Cleaner separation of concerns

- **WS service**: real‑time streaming, live transcripts, status topics.
- **HTTP API**: request/response patterns (start conversation, update, poll, configuration).

### 4.4. Backward compatibility preserved

- Environments that still host WS under the API do not have to change immediately.
- They can keep using:
  - `VITE_WEBSOCKET_VERSION=1`
  - Or omit `websocketUrl` in the SDK.

---

## 5. Impact by Role

### 5.1. Backend / DevOps

**What you need to do for standalone WS:**

- **Deploy a separate WebSocket service** exposing at least:

  - `GET /ws/conversations/:conversation_id` (WebSocket upgrade).

- **Configure routing and TLS:**

  - DNS entry for the WS host (e.g. `ws.example.com`).
  - Ingress / load balancer rules for `wss://ws.example.com`.
  - Proper TLS certificates for `wss://` connections.

- **Ensure auth & multi‑tenancy still work:**

  - Validate `access_token` (guest JWT) or `api_key` passed as query parameter.
  - Respect `x-tenant-id` as query parameter if present.

- **Capacity planning:**

  - Size the WS service for concurrent connections and throughput.
  - Introduce appropriate monitoring for connection count, errors, and backpressure.

**Fallback / compatibility:**

- You can continue to host WS on the API server for environments that haven’t migrated yet.
- In that case:
  - Use `VITE_WEBSOCKET_VERSION=1`.
  - Omit the `websocketUrl` parameter from SDK usage.

---

### 5.2. Frontend team

**New mode (standalone WS):**

- Set these env vars for environments that have the WS service deployed:

  ```env
  VITE_WEBSOCKET_PUBLIC_URL=wss://ws.example.com
  VITE_WEBSOCKET_VERSION=2
  VITE_WS=true
  ```

- No code changes are required; the hook already understands both versions.

**Legacy / backward‑compat mode:**

- Either keep using the old values, or explicitly set:

  ```env
  VITE_WEBSOCKET_VERSION=1
  VITE_WS=true
  ```

- WebSockets will continue to connect to the old route:
  - `/conversations/ws/:conversation_id` on the API host.

**Disabling WS entirely (for debugging or constrained environments):**

- Set:

  ```env
  VITE_WS=false
  ```

- The UI will then rely on **HTTP polling** (via `isPollEnabled` and `pollInProgressConversation`), not WebSockets.

---

### 5.3. SDK consumers / external integrators

**If they do nothing (current behavior):**

- Code like:

  ```ts
  new ChatService("https://api.example.com", undefined, "API_KEY");
  ```

  remains valid:

  - Uses backward‑compat mode.
  - Connects to `ws://api.example.com/api/conversations/ws/:conversation_id?...`.

**To opt into the standalone WS service:**

- Update initialization to pass the WS URL:

  ```ts
  const chatService = new ChatService(
    "https://api.example.com",
    "wss://ws.example.com",
    "API_KEY",
    metadata,
    tenant,
  );
  ```

- No other interface changes are needed.

---

## 6. Diagnostics & Troubleshooting

### 6.1. Diagnostic logs in the SDK

The SDK uses `createWebSocketDiagnostic` (`plugins/react/src/utils/websocket.ts`) to generate detailed error messages:

- Shows the (redacted) WS URL.
- Logs close codes, reasons, and ready state.

This helps you identify:

- Misconfigured host or route (e.g. incorrect `/ws/conversations` path).
- TLS or network issues.
- Invalid tokens (`access_token` / `api_key`).

### 6.2. Common failure modes when switching to standalone

- **404 / 400 on WS upgrade**
  WS service not exposing `/ws/conversations/:id` correctly.

- **403 / unauthorized**
  WS service not validating `access_token`/`api_key` in the same way as the API.

- **CORS / origin issues**
  LB or WS server not allowing your frontend origin for WebSockets.

- **Connection refused / timeout**
  DNS, LB, or firewall misconfiguration for the new WS host.

In all of these cases, you can temporarily:

- Switch `VITE_WEBSOCKET_VERSION` back to `1`, or
- Remove `websocketUrl` from SDK usage, or
- Set `VITE_WS=false` and rely on HTTP polling while debugging.

---

## 7. Migration Checklist

**To move an environment from embedded WS to standalone WS:**

1. **Deploy the standalone WebSocket service**
   - Implement `/ws/conversations/:conversation_id` with the existing protocol and topics.

2. **Configure infrastructure**
   - DNS: `ws.example.com`.
   - TLS: valid certificate for `wss://ws.example.com`.
   - LB / ingress route rules to the WS service.

3. **Configure frontend env**
   - `VITE_WEBSOCKET_PUBLIC_URL=wss://ws.example.com`
   - `VITE_WEBSOCKET_VERSION=2`
   - `VITE_WS=true`

4. **Update SDK integrators (optional, if they want to use standalone WS)**
   - Pass `websocketUrl="wss://ws.example.com"` into `ChatService`.

5. **Test end‑to‑end**
   - Start a conversation.
   - Verify:
     - WebSocket connects to the new endpoint.
     - Messages, takeover, and finalize events are received as expected.

6. **Fallback plan**
   - If issues appear, temporarily:
     - Set `VITE_WEBSOCKET_VERSION=1`, or
     - Remove `websocketUrl` from SDK initialization, or
     - Set `VITE_WS=false` to force HTTP polling.

