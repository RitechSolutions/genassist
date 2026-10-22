# Architecture Diagrams

This document contains the system architecture and communication diagrams for GenAssist, rendered using [Mermaid](https://mermaid.js.org/).

---

## 🛠 System Interaction Diagram

This diagram illustrates the high-level communication between major system components.

```mermaid
graph TD
    Client["User Browser (Frontend)"] -- "REST API (HTTP/JSON, SSE for chat turns)" --> API["FastAPI (Backend)"]
    Client -- "WebSocket (JSON)" --> WS["WebSocket Service"]

    API -- "CRUD Operations" --> DB["PostgreSQL"]
    API -- "Cache/Queue" --> Redis["Redis"]
    API -- "Vector Search" --> Chroma["ChromaDB"]
    API -- "Graph Queries" --> Neo4j["Neo4j"]

    WS -- "Pub/Sub (websocket:*, ws_upstream:*)" --> Redis

    API -- "Chat turns (inside the request)" --> LangGraph["LangGraph / LLMs"]

    CeleryWorker["Celery Worker"] -- "Process Tasks" --> Redis
    CeleryWorker -- "Scheduled workflows, analyses" --> LangGraph
    CeleryWorker -- "Transcribe" --> Whisper["Whisper Service"]

    API -- "Enqueues Tasks" --> Redis

    subgraph "External Services"
        OpenAI["OpenAI / Anthropic"]
        Azure["Azure Services"]
    end

    LangGraph --> OpenAI
    CeleryWorker --> Azure
```

---

## 🔄 Data Flow: Chat Interaction

This sequence diagram shows one chat turn. The turn runs inside the update request; Celery handles background work (transcription, scheduled workflows, analysis backfills), not chat replies.

```mermaid
sequenceDiagram
    participant User as User (UI)
    participant API as FastAPI Backend
    participant WS as WebSocket Service
    participant Redis as Redis PubSub
    participant LLM as LLM (OpenAI/Anthropic)
    participant DB as PostgreSQL / Vector DB

    User->>API: Start conversation
    API-->>User: conversation_id + guest token

    opt WebSocket enabled (USE_WS)
        User->>WS: Open WebSocket (conversation_id, topics)
        WS->>API: Verify token (internal /api/internal/ws/verify-token)
        API-->>WS: Authenticated user + tenant
    end

    User->>API: PATCH /api/conversations/in-progress/update/{conversation_id}
    API->>API: Authenticate, rate limit, reCAPTCHA
    API->>DB: Retrieve context (RAG)
    API->>LLM: Generate response with context
    LLM-->>API: AI response
    API->>DB: Store messages, response log, stats

    opt WebSocket enabled (USE_WS)
        API->>Redis: Publish event (websocket:{tenant_id}:{conversation_id})
        Redis-->>WS: Event
        WS-->>User: Message over WebSocket
    end

    alt Accept: text/event-stream
        API-->>User: SSE activity frames while it works, then done with the updated conversation
    else
        API-->>User: Updated conversation (JSON)
    end
```
