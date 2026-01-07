# Architecture Diagrams

This document contains the system architecture and communication diagrams for GenAssist, rendered using [Mermaid](https://mermaid.js.org/).

---

## 🛠 System Interaction Diagram

This diagram illustrates the high-level communication between major system components.

```mermaid
graph TD
    Client["User Browser (Frontend)"] -- "REST API (HTTP/JSON)" --> API["FastAPI (Backend)"]
    API -- "CRUD Operations" --> DB["PostgreSQL"]
    API -- "Cache/Queue" --> Redis["Redis"]
    API -- "Vector Search" --> Chroma["ChromaDB"]
    API -- "Graph Queries" --> Neo4j["Neo4j"]
    
    CeleryWorker["Celery Worker"] -- "Process Tasks" --> Redis
    CeleryWorker -- "AI Orchestration" --> LangGraph["LangGraph / LLMs"]
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

This sequence diagram shows the flow of a typical chat request, highlighting the asynchronous task processing.

```mermaid
sequenceDiagram
    participant User as User (UI)
    participant API as FastAPI Backend
    participant Redis as Redis Queue
    participant Worker as Celery Worker
    participant LLM as LLM (OpenAI/Anthropic)
    participant DB as Vector/Graph DB
    
    User->>API: Send Message
    API->>API: Authenticate & Validate
    API->>Redis: Enqueue Processing Task
    API-->>User: Acknowledge (Task ID)
    
    Worker->>Redis: Fetch Task
    Worker->>DB: Retrieve Context (RAG)
    Worker->>LLM: Generate Response with Context
    LLM-->>Worker: Provide AI Response
    Worker->>DB: Store Conversation History
    Worker->>Redis: Mark Task Complete
    
    User->>API: Poll Status / WebSocket
    API-->>User: Deliver AI Response
```
