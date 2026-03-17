# GenAssist WebSocket Service

A standalone WebSocket relay service for real-time communication in GenAssist. It manages client WebSocket connections and relays messages between the frontend, backend API, and Redis pub/sub.

## Overview

The WebSocket service is a **separate process** from the main backend API. It:

- Accepts WebSocket connections from clients (frontend, Twilio, etc.)
- Verifies authentication via the backend API
- Subscribes to Redis pub/sub channels to receive broadcast messages from the backend
- Delivers messages to connected clients in real time
- Publishes client-sent messages upstream to Redis for backend processing

This architecture allows the backend to remain stateless while the WebSocket service holds long-lived connections and scales independently.

## Architecture

```
┌─────────────┐     WebSocket      ┌──────────────────┐     HTTP (verify-token)     ┌─────────┐
│   Frontend  │ ◄────────────────► │  WebSocket Svc   │ ◄──────────────────────────►│ Backend │
└─────────────┘   ws://:8002/ws    └────────┬─────────┘     x-internal-secret       └────┬────┘
                                            │                                              │
                                            │ Redis Pub/Sub                                │ Redis publish
                                            │                                              │
                                            ▼                                              ▼
                                    ┌───────────────────────────────────────────────────────────────┐
                                    │                        Redis                                  │
                                    │  Backend → WS: websocket:{tenant_id}:{room_id} (pattern:      │
                                    │               websocket:*)                                     │
                                    │  WS → Backend:  ws_upstream:{tenant_id}:{room_id}             │
                                    └───────────────────────────────────────────────────────────────┘
```

## Communication with Other Services

### Backend API

The WebSocket service communicates with the backend over HTTP:

| Direction | Endpoint | Purpose |
|-----------|----------|---------|
| WebSocket → Backend | `POST /api/internal/ws/verify-token` | Verify access token or API key on connection. Returns `user_id`, `permissions`, `tenant_id`. Protected by `x-internal-secret` header. |
| WebSocket → Backend | `GET /api/internal/agents/{agent_id}/config` | Fetch agent configuration for Twilio/media-stream endpoints. |
| WebSocket → Backend | `POST /api/internal/agents/execute` | Execute agent with transcribed text (Twilio media stream). |

All internal calls use the `x-internal-secret` header for service-to-service authentication.

### Redis

Redis is the message bus between the backend and the WebSocket service:

| Channel pattern | Direction | Description |
|-----------------|-----------|-------------|
| `websocket:{tenant_id}:{room_id}` | Backend → WebSocket | Backend publishes broadcast messages as JSON. The WebSocket service subscribes via the `websocket:*` pattern and delivers to connected clients in the room. |
| `ws_upstream:{tenant_id}:{room_id}` | WebSocket → Backend | Client-sent messages. WebSocket publishes; backend (or other consumers) can subscribe to process them. |

**Downstream message format** (Backend → WebSocket service via Redis):

```json
{
  "type": "message",
  "payload": { ... },
  "required_topic": "message",
  "room_id": "conv-123",
  "tenant_id": "master"
}
```

When the WebSocket service delivers this to connected clients, it sends a simplified payload:

```json
{
  "type": "message",
  "payload": { ... }
}
```

**Upstream message format** (WebSocket → Backend via Redis):

```json
{
  "user_id": "user-uuid",
  "tenant_id": "master",
  "room_id": "conv-123",
  "data": "{raw client payload}"
}
```

### OpenAI (optional)

- **TTS endpoint** (`/ws/audio/tts`): Uses `OPENAI_API_KEY` to stream text-to-speech.
- **Twilio media stream** (`/ws/media-stream/{agent_id}`): Uses OpenAI Realtime API for transcription and TTS for voice responses.

## Client Connection Parameters

For authenticated endpoints, clients connect with query parameters:

- `access_token` **or** `api_key` (required): Credentials used by the WebSocket service to call the backend `/api/internal/ws/verify-token` endpoint.
- `x-tenant-id` (optional, default `master`): Tenant context passed to the backend for authorization and used for room isolation.
- `topics` (optional, repeatable): Limits which categories of events the client receives (e.g. `topics=message&topics=statistics`). The backend can set `required_topic` on Redis messages to target only connections subscribed to those topics.
- `lang` (optional, default `en`): Language hint for downstream processing.

## WebSocket Endpoints

| Path | Auth | Description |
|------|------|-------------|
| `/ws/conversations/{conversation_id}` | Token or API key | Conversation room. Receives real-time messages; client messages published upstream. Supports topic filters via the `topics` query parameter. |
| `/ws/dashboard/list` | Token or API key | Dashboard room for global/system updates. |
| `/ws/audio/tts` | Token or API key | Text-to-speech streaming (OpenAI TTS). |
| `/ws/media-stream/{agent_id}` | None (Twilio) | Twilio Media Stream bridge: Twilio ↔ OpenAI Realtime ↔ Backend agent. |
| `/ws/test` | None | Simple test endpoint (health checks). |

### Heartbeats

The service runs an application-level heartbeat loop:

- Periodically sends `{"type": "ping"}` messages to all active connections.
- Tracks the last time any message was received from each client.
- Closes connections that have not responded within `HEARTBEAT_INTERVAL + HEARTBEAT_TIMEOUT` seconds.

Clients should either:

- Rely on protocol-level WebSocket ping/pong (handled by the browser/ASGI stack), or
- Explicitly respond with `{"type": "pong"}` to application-level pings.

## Configuration

Environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://localhost:8000` | Backend API base URL |
| `WS_INTERNAL_SECRET` | — | Shared secret for internal API calls (must match backend) |
| `WS_PORT` | `8002` | Port for WebSocket server |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database index |
| `REDIS_PASSWORD` | _empty_ | Redis password (optional) |
| `REDIS_SSL` | `false` | Use TLS for Redis connection |
| `HEARTBEAT_INTERVAL` | `30` | Seconds between ping frames |
| `HEARTBEAT_TIMEOUT` | `10` | Seconds to wait for pong before disconnecting |
| `AUTH_CACHE_MAX_SIZE` | `10000` | LRU cache size for verified tokens |
| `OPENAI_API_KEY` | — | Required for TTS and Twilio media stream |

## Running Locally

```bash
cd websocket
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your settings
python run.py
# Or: uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

With Docker:

```bash
docker build -t genassist-websocket .
docker run -p 8002:8002 --env-file .env genassist-websocket
```

## Health Checks

- `GET /health` — Liveness check.
- `GET /ready` — Readiness check with connection stats (`total_connections`, `rooms_count`, `connections_by_tenant`).

## Multi-Tenancy

Rooms are tenant-scoped: `{tenant_id}:{room_id}`. Connections are isolated per tenant. Use the `x-tenant-id` query parameter (default: `master`) when connecting.
