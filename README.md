<img width="2880" height="2048" alt="GenAssist Infographics" src="https://github.com/user-attachments/assets/4ba0ac3e-7453-4110-8038-02ec6a9becb1" />

# GenAssist

GenAssist is an AI-powered platform for building, managing and deploying AI agents, with conversation management, analytics and knowledge bases built in.

- **Product documentation:** [docs.genassist.ai](https://docs.genassist.ai/docs/introduction/)
- **How-to videos:** [GenAssist Workflows](https://docs.genassist.ai/docs/workflows/)
- **Internal technical docs:** [Architecture diagrams](./docs/architecture_diagrams.md) · [Tech stack](./docs/tech_stack.md)

---

## Features and architecture

### Key features

- **User management:** authentication, role-based access control and API key management
- **AI agents:** configure and manage agents with various LLM providers and tools
- **Knowledge base:** document management with RAG (retrieval-augmented generation)
- **Analytics:** performance metrics, conversation analysis and KPI tracking
- **Conversation management:** transcripts, conversation and sentiment analysis
- **Audit logging:** system activity tracking and change history

### Architecture

- **Frontend:** React, TypeScript, Vite, Tailwind CSS and shadcn-ui
- **Backend:** Python with FastAPI, SQLAlchemy ORM and PostgreSQL, using a layered architecture with dependency injection
- **Supporting services:** Redis, Celery workers, Chroma and Qdrant vector databases, Whisper transcription and a WebSocket relay

## Contents

1. [Quick start (Docker)](#quick-start-docker): run everything on your laptop
2. [Everyday commands](#everyday-commands)
3. [Where everything runs](#where-everything-runs)
4. [Troubleshooting](#troubleshooting)
5. [Optional extras](#optional-extras): observability stack, prebuilt images
6. [Local development (without Docker)](#local-development-without-docker)
7. [Integrations](#integrations)
8. [Testing](#testing)
9. [Features and architecture](#features-and-architecture)

---

## Quick start (Docker)

This is the recommended way to run GenAssist locally. Everything runs in Docker, so you don't need Python or Node.js installed.

> [!WARNING]
> **This setup is for local development and demos only. Never run it on a server or anywhere reachable from the internet.**
>
> - **Default passwords and keys are public.** The database password, the dashboard logins and the test API keys created on first start are visible in this public repository, so anyone can look them up.
> - **Services are reachable from your network.** Docker publishes the ports to every device on the same network as your computer, including the database, Redis, the API and the dashboards, not just to you.
> - **Stop GenAssist when you're not using it** (see [Everyday commands](#everyday-commands)), and avoid running it on public or shared Wi-Fi.
> - **Keep your `.env` files private.** Don't commit them or reuse them for any shared, staging or production environment. Those environments need their own unique passwords and keys.

### What you need

| Requirement | Notes |
|---|---|
| **Git** | macOS: run `xcode-select --install` in Terminal. Windows/Linux: [git-scm.com](https://git-scm.com/) |
| **Docker Desktop** | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/). It must be **open and running** whenever you use GenAssist. |
| **Memory** | Give Docker at least **8 GB** (Docker Desktop → Settings → Resources → Memory). The stack runs about 15 services. |
| **Time** | The first build downloads and builds several large images: expect **15–30 minutes**. Later starts take seconds. |
| **AI provider key** *(optional)* | GenAssist starts without one, but agents won't answer until you add one (for example an OpenAI key). |

### Step 1: Download the code

```bash
git clone https://github.com/RitechSolutions/genassist
cd genassist
```

> All the commands below are run from inside this `genassist` folder.

### Step 2: Create the three settings files

The stack reads three `.env` files. Create them from the provided examples:

```bash
cp frontend/.env.template frontend/.env
cp backend/.env.example   backend/.env
cp websocket/.env.example websocket/.env
```

### Step 3: Fill in the required settings

Open `backend/.env` in any text editor and set these values:

| Setting | What to put | Why |
|---|---|---|
| `SEED_ADMIN_PASSWORD` | A password of your choice | Your login password for the `admin` user. It is only applied on the **first** start; see [Reset everything](#everyday-commands). |
| `FERNET_KEY` | A generated key (see below) | Encryption key. The backend **will not start** with the placeholder value. |
| `DB_PASS` | `postgres` | Must match the database password in `docker-compose.dev.yml`. |
| `OPENAI_API_KEY` | Your OpenAI key *(optional)* | Needed for agents to respond. |

To generate a `FERNET_KEY`, run this and paste the output after `FERNET_KEY=`:

```bash
openssl rand -base64 32 | tr '+/' '-_'
```

Then open `websocket/.env` and set `WS_INTERNAL_SECRET` to the **same value** as `WS_INTERNAL_SECRET` in `backend/.env`.

### Step 4: Build and start

```bash
docker compose -f docker-compose.dev.yml -p genassist_dev up --build -d
```

Wait until the command finishes and every line shows **Started**, **Running** or **Healthy**. On the very first start the backend also creates and fills the database, which can take up to **3–5 minutes** before it reports healthy.

### Step 5: Open GenAssist

Open **http://localhost:8080** in your browser and log in:

- **Username:** `admin`
- **Password:** the `SEED_ADMIN_PASSWORD` you set in step 3

That's it. 🎉

---

## Everyday commands

Run these from the `genassist` folder. Docker Desktop must be open.

| To… | Run |
|---|---|
| **Start** GenAssist | `docker compose -f docker-compose.dev.yml -p genassist_dev up -d` |
| **Stop** GenAssist (keeps your data) | `docker compose -f docker-compose.dev.yml -p genassist_dev down` |
| **Rebuild** after pulling new code | `docker compose -f docker-compose.dev.yml -p genassist_dev up -d --build` |
| **Apply changed `.env` settings** | `docker compose -f docker-compose.dev.yml -p genassist_dev up -d --force-recreate` |
| **See what's running** | `docker ps --format "table {{.Names}}\t{{.Status}}"` |
| **Read the backend log** | `docker logs genassist-app-dev --tail 100` |
| **Reset everything** ⚠️ deletes all data | `docker compose -f docker-compose.dev.yml -p genassist_dev down -v` |

> **Tip:** to see only errors in the backend log, run
> `docker logs genassist-app-dev 2>&1 | grep -E "ERROR|Traceback|Error:" | tail -n 40`

---

## Where everything runs

| Service | URL | Login |
|---|---|---|
| **GenAssist app** | http://localhost:8080 | `admin` / your `SEED_ADMIN_PASSWORD` |
| Backend API | http://localhost:8000/api | n/a |
| API documentation (Swagger) | http://localhost:8000/docs | n/a |
| Backend health check | http://localhost:8000/api/playground/health | n/a |
| Celery jobs dashboard (Flower) | http://localhost:5555 | `user1` / `password1` |
| Metabase (analytics) | http://localhost:3000 | Set up on first visit |

Other users created on first start (passwords are set in `backend/.env`): `supervisor1`, `operator1`, `apiuser1`, `transcribeoperator1`.

---

## Troubleshooting

| What you see | Cause | Fix |
|---|---|---|
| `env file …/frontend/.env not found` (or `websocket/.env`) | A settings file is missing | Repeat [step 2](#step-2-create-the-three-settings-files). |
| `container genassist-app-dev is unhealthy` | The backend failed to start | Read the log (see [Everyday commands](#everyday-commands)) and match the error below. |
| Log: `Fernet key must be 32 url-safe base64-encoded bytes` | `FERNET_KEY` is still the placeholder | Generate a key ([step 3](#step-3-fill-in-the-required-settings)), then run the *Apply changed `.env` settings* command. |
| Log: `password authentication failed` | `DB_PASS` doesn't match the database | Set `DB_PASS=postgres`, then run *Apply changed `.env` settings*. |
| Browser: **ERR_CONNECTION_RESET** on `http://localhost` | The app is served on port 8080 | Use **http://localhost:8080**. |
| Login fails right after starting | The backend is still starting | Wait 1–2 minutes. The health check URL should return `200`. |
| Login fails with the password you set | The admin user was created on an earlier start with a different password | Reset everything (`down -v`) and start again. |
| Containers keep stopping or restarting | Docker is out of memory | Increase Docker's memory to 8 GB or more. |
| Agents don't reply | No AI provider key | Add `OPENAI_API_KEY` (or another provider key) to `backend/.env`, then run *Apply changed `.env` settings*. |
| Many `change detected` DEBUG lines in the log | Normal in development mode | Safe to ignore. Use the error-only log command above. |

---

## Optional extras

### Observability stack (Grafana + Prometheus + OpenTelemetry Collector)

GenAssist can export workflow metrics via OpenTelemetry and display them in Grafana. This stack is optional and lives in [`docker-compose.otel.yml`](./docker-compose.otel.yml).

```bash
docker compose -f docker-compose.dev.yml -f docker-compose.otel.yml -p genassist_dev up -d
```

| Service | URL |
|---|---|
| Grafana (Dashboards → folder `OTEL`) | http://localhost:3010 |
| Prometheus | http://localhost:9090 |
| Collector zpages | http://localhost:55679/debug/tracez |
| Collector exported metrics | http://localhost:8889/metrics |

For details and PromQL examples, see [`observability/README.md`](./observability/README.md).

### Run prebuilt images instead of building from source

Uses the published images from the container registry, which is faster because nothing is built locally. You still need the `.env` files from steps 2 and 3.

```bash
# Start
docker compose -f docker-compose.yml -p genassist_local_01 up -d
# Stop
docker compose -f docker-compose.yml -p genassist_local_01 down
```

---

## Local development (without Docker)

For developers working on the code directly. Requires **Node.js + npm** (frontend) and **Python 3.12+** (backend).

| Part | Setup |
|---|---|
| **Frontend** | `cd frontend`, create `.env` from `.env.template`, then follow [frontend/README.md](./frontend/README.md) |
| **Backend** | `cd backend`, create `.env` from `.env.example`, then follow [backend/README.md](./backend/README.md) |

The backend API is then available at http://localhost:8000/api and its docs at http://localhost:8000/docs.

---

## Integrations

### React plugin

```bash
cd plugins/react
npm run build

# Run the chat plugin example
cd example-app
npm run dev
```

### JavaScript widget (standalone)

A self-contained widget that can be embedded in any website (help centres, landing pages) without a framework. It bundles React, styles and fonts into a single JS + CSS pair.

```bash
cd plugins/plugin-js
cp src/config/config.example.js src/config/config.js
npm install
npm run build
```

See the [plugin-js README](./plugins/plugin-js/README.md) for configuration options and [BUILD.md](./plugins/plugin-js/BUILD.md) for generating `widget.iife.js` and `widget.css`.

### iOS plugin

The iOS plugin lives in [`plugins/ios`](./plugins/ios). *(Build steps to be added.)*

---

## Testing

### UI tests (Playwright)

```bash
cd ui_tests
npx playwright install
npx playwright test
```

### Backend tests

```bash
cd backend
python -m pytest tests/

# With coverage
coverage run --source=app -m pytest -v tests && coverage report -m

# HTML coverage report
python -m pytest tests/ -v --cov=app --cov-report=html
```
See the [architecture diagrams](./docs/architecture_diagrams.md) for details.
