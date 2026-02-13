# Azure Pipelines

This folder contains the CI/CD pipeline definitions for GenAssist. All pipelines are **manually triggered** (`trigger: none`) and run on the **Ritech-AI-TR1** self-hosted agent pool.

## Pipelines

| Pipeline | File | Services |
|---|---|---|
| Backend Release | `release-backend.yml` | app, celery_worker, celery_beat, whisper, flower |
| Frontend Release | `release-frontend.yml` | ui |

Both pipelines share the same 3-stage promotion flow and accept boolean parameters to toggle each stage independently:

- **Deploy to DEV** (default: `true`)
- **Deploy to TEST** (default: `false`)
- **Deploy to PROD** (default: `false`)

The backend pipeline also has toggles for individual service groups:

- **Include infrastructure services** (`includeInfra`, default: `false`) — db, redis, chroma, qdrant
- **Include Celery services** (`includeCelery`, default: `true`) — celery_worker, celery_beat
- **Include Whisper service** (`includeWhisper`, default: `true`)
- **Include Flower service** (`includeFlower`, default: `true`)

The `app` service is always deployed. Other services can be toggled on/off per run.

## Stage Flow

```
DEV (deploy) ──► TEST (build + push + deploy) ──► PROD (promote, no rebuild)
```

Each stage can be skipped — if a stage is disabled, the next stage still runs (it doesn't require the previous one to succeed, only to not fail).

### 1. DEV

Deploys directly on the self-hosted agent using `docker compose`.

- Downloads the environment-specific secure file and copies it to the correct `.env` location:
  - Backend pipeline: `env.dev.backend` → `backend/.env`
  - Frontend pipeline: `env.dev.frontend` → `frontend/.env`
- Appends dynamic env vars if configured (e.g., `VITE_UI_VERSION` for the frontend)
- Pulls latest images, then starts services with `up -d --build --remove-orphans` (rolling update, no downtime)
- Uses compose files: `docker-compose.base.yml` + `docker-compose.yml`

**Backend** deploys: `app` (always) + optional `celery_worker celery_beat`, `whisper`, `flower`
**Frontend** deploys: `ui`

Infrastructure services (`db`, `redis`, `chroma`, `qdrant`) are **not** deployed by default — set `includeInfra` to `true` for first-time setup or when infrastructure services need to be restarted. Celery, Whisper, and Flower are included by default but can be toggled off if not needed for a particular deployment.

### 2. TEST

Builds Docker images, pushes them to **GitHub Container Registry (GHCR)**, and **deploys containers on the same build server**.

**Build & Push:**
- Logs in to GHCR using `GHCR_USER` and `GHCR_PAT` secret variables
- Builds via `docker compose` using `docker-compose.base.yml` + `docker-compose.build.yml`
- No environment variables are injected at build time (see [Environment Variables](#environment-variables) below)
- Tags with: `$(Build.BuildNumber)` and `latest`
- Pushes to: `ghcr.io/ritechsolutions/<image-name>`

| Service | Local Image | Registry Image |
|---|---|---|
| Backend | `genassist-app-image` | `genassist-backend` |
| Frontend | `genassist-ui` | `genassist-frontend` |

**Deploy:**
- Downloads the environment-specific secure file and copies it to the correct `.env` location:
  - Backend pipeline: `env.test.backend` → `backend/.env`
  - Frontend pipeline: `env.test.frontend` → `frontend/.env`
- Appends dynamic env vars if configured (e.g., `VITE_UI_VERSION` for the frontend)
- Starts services with `up -d --build --remove-orphans` (rolling update, no downtime)
- Env vars are injected at container runtime via docker-compose `env_file`

### 3. PROD

Promotes the **exact same image** from TEST to the PROD registry path — no rebuild.

- Logs in to GHCR using `GHCR_USER` and `GHCR_PAT` secret variables
- Pulls the TEST image by `$(Build.BuildNumber)` tag
- Retags with: `$(Build.BuildNumber)`, `latest`, and `prod`
- Pushes to: `ghcr.io/ritechsolutions/genassist/prod/<image-name>`

This guarantees that the image deployed to production is identical to what was tested.

## Templates

Reusable templates in the `templates/` folder:

| Template | Purpose | Parameters |
|---|---|---|
| `deploy.yml` | Docker compose deploy on self-hosted agent (used by DEV and TEST) | `services`, `envFile`, `envDest`, `extraEnv` (optional) |
| `build-push-test.yml` | Build image and push to GHCR | `composeService`, `localImageName`, `registryImageName` |
| `promote-to-prod.yml` | Retag tested image for PROD (no rebuild) | `registryImageName` |

The `extraEnv` parameter allows appending dynamic environment variables to the `.env` file after copying the secure file. Supports multi-line values for multiple variables:

```yaml
extraEnv: |
  VITE_UI_VERSION=$(Build.BuildNumber)
  ANOTHER_VAR=value
```

## Environment Variables

### Backend

The backend reads `.env` at **runtime** (container startup). No env vars are needed at Docker build time. The backend `.dockerignore` explicitly excludes `.env` and `.env.*` to prevent secrets from leaking into image layers.

### Frontend

The frontend uses **runtime placeholder substitution** to avoid baking secrets into images:

1. **Build time:** The Dockerfile copies `.env.docker` (committed to the repo with placeholder values like `__VITE_PUBLIC_API_URL__`) as `.env` before `npm run build`. Vite bakes these placeholders into the JS bundle.
2. **Runtime:** `container/entrypoint.sh` replaces each placeholder with the actual environment variable value passed to the container, then starts nginx.

This means a single frontend image works in any environment — the env vars are injected at container startup, not at build time.

**Managed placeholders** (defined in `frontend/.env.docker`):
- `VITE_UI_VERSION`
- `VITE_PUBLIC_API_URL`
- `VITE_WEBSOCKET_PUBLIC_URL`
- `VITE_GENASSIST_CHAT_APIKEY`
- `VITE_MULTI_TENANT_ENABLED`
- `VITE_WS`
- `VITE_ONBOARDING_API_URL`
- `VITE_ONBOARDING_CHAT_APIKEY`
- `VITE_ONBOARDING_USERNAME`
- `VITE_ONBOARDING_PASSWORD`
- `VITE_GENASSIST_CHAT_TENANT_ID`

When adding a new `VITE_` variable, update both `frontend/.env.docker` and `frontend/container/entrypoint.sh`.

**Dynamic variables:** `VITE_UI_VERSION` is set dynamically per build via the `extraEnv` parameter (value: `$(Build.BuildNumber)`), not from the secure file.

**Local development:** When running without Docker (`npm run dev`), Vite reads `frontend/.env` directly — the `.env.docker` and `entrypoint.sh` files are only used in the Docker flow.

## Environments

The pipelines use Azure DevOps environments for deployment tracking and approvals:

- `genassist-dev`
- `genassist-test`
- `genassist-production`

Approval gates can be configured per environment in Azure DevOps under **Pipelines > Environments > Approvals and checks**.

## Secure Files

Environment variables are stored as Azure DevOps **Secure Files** and downloaded at runtime. Backend and frontend have **separate** secure files:

| Secure File | Stage | Destination |
|---|---|---|
| `env.dev.backend` | DEV | `backend/.env` |
| `env.dev.frontend` | DEV | `frontend/.env` |
| `env.test.backend` | TEST | `backend/.env` |
| `env.test.frontend` | TEST | `frontend/.env` |

These are never checked into source control. The PROD stage does not require secure files — it promotes the already-built image without rebuilding.

## Secret Variables

The following must be set as **secret pipeline variables** in both pipeline settings UIs (not in YAML):

- `GHCR_USER` — GitHub Container Registry username
- `GHCR_PAT` — GitHub Container Registry personal access token

These are used by the `build-push-test.yml` and `promote-to-prod.yml` templates to authenticate with GHCR.
