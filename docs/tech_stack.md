# Technology Stack & System Architecture

This document provides a comprehensive overview of the technology stack and system architecture for GenAssist.

## 🚀 Overview

GenAssist is a powerful AI-driven assistance platform built with a modern, scalable architecture. It leverages cutting-edge technologies in frontend development, backend orchestration, and AI/ML processing to deliver a seamless user experience.

---

## 💻 Tech Stack

### Frontend
- **Framework**: [React](https://reactjs.org/) (v18)
- **Build Tool**: [Vite](https://vitejs.dev/)
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/), [Shadcn/UI](https://ui.shadcn.com/)
- **State Management/Data Fetching**: [TanStack Query](https://tanstack.com/query/latest) (React Query)
- **UI Components**: [Radix UI](https://www.radix-ui.com/), [Lucide React](https://lucide.dev/), [Ant Design](https://ant.design/)
- **Form Management**: [React Hook Form](https://react-hook-form.com/) & [Zod](https://zod.dev/)

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Task Queue**: [Celery](https://docs.celeryq.dev/)
- **Dependency Injection**: [FastAPI-Injector](https://github.com/alantriz/fastapi-injector)
- **Asynchronous Processing**: [Uvicorn](https://www.uvicorn.org/) (ASGI server)
- **ORM/Database Toolkit**: [SQLAlchemy](https://www.sqlalchemy.org/) & [Alembic](https://alembic.sqlalchemy.org/)

### AI & ML Operations
- **Orchestration**: [LangChain](https://www.langchain.com/), [LangGraph](https://langchain-ai.github.io/langgraph/)
- **LLM Integrations**: OpenAI, Anthropic, Ollama
- **Audio Processing**: [OpenAI Whisper](https://github.com/openai/whisper) (hosted as a separate service)
- **Embedding/Vector Search**: [ChromaDB](https://www.trychroma.com/)
- **Graph Database**: [Neo4j](https://neo4j.com/) (for RAG Graph)

### Infrastructure & DevOps
- **Containerization**: [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- **Caching & Messaging**: [Redis](https://redis.io/)
- **CI/CD**: Azure Pipelines
- **Observability**: [OpenTelemetry](https://opentelemetry.io/), [Flower](https://flower.readthedocs.io/) (Celery Monitoring)
- **Analytics**: [Metabase](https://www.metabase.com/)

---

## 🛠 System Architecture & Communication

The system's architecture and communication flows are detailed in a separate document to ensure clarity and maintainability.

> [!TIP]
> **View Diagrams**: Check out the [Architecture Diagrams](file:///Users/a/Code/ritech/genassist/docs/architecture_diagrams.md) for a visual representation of system interactions and data flows.

### 🔍 Tools for Viewing Diagrams

To view and edit the Mermaid diagrams in this project, you can use the following tools:

1.  **VS Code Extension**: [Mermaid Editor](https://marketplace.visualstudio.com/items?itemName=tomoyukim.vscode-mermaid-editor) or [Markdown Preview Mermaid Support](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid).
2.  **Online Editor**: [Mermaid Live Editor](https://mermaid.live/) - Copy and paste the Mermaid code block into this tool for a live preview.
3.  **GitHub/GitLab**: Most modern Git hosting platforms render Mermaid diagrams natively in the browser when viewing markdown files.
4.  **Browser Extensions**: Various extensions are available for Chrome and Firefox (e.g., [Mermaid Diagram Renderer](https://chromewebstore.google.com/detail/mermaid-diagram-renderer/lbaogofofidjabbdclmmanneidpcpneb)) that automatically render these diagrams.

---

## 📂 Project Structure

- `frontend/`: React components, services, and hooks.
- `backend/`: FastAPI application, models, tasks, and core logic.
- `docs/`: Technical documentation and guides.
- `plugins/`: Custom extensions and integrations.
- `ui_tests/`: End-to-end testing suite.
