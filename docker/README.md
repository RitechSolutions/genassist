# GenAssist Docker Configuration

This directory contains Docker Compose configurations for running GenAssist in different environments.

## Directory Structure

```
docker/
├── docker-compose.base.yml     # Base configuration (shared across all environments)
├── docker-compose.yml          # Production overrides (pre-built images from GHCR)
├── docker-compose.dev.yml      # Development overrides (build from source)
├── docker-compose.ci.yml       # CI/CD overrides (isolated ports)
├── .env.example                # Environment variables template
└── README.md                   # This file
```

## Architecture

GenAssist uses a **base + override** pattern for Docker Compose:

- `docker-compose.base.yml` - Contains common service definitions, healthchecks, profiles, and dependencies
- Environment-specific files only contain overrides (ports, volumes, images, container names)

This reduces duplication and ensures consistency across environments.

## Quick Start

### Setup (One-time)

```bash
# Copy environment template
cp .env.example .env
```

The `.env` file sets `COMPOSE_FILE` automatically, enabling simpler commands from the `docker/` directory.

### Option A: Full Stack (All Services in Docker)

Use this when you want to run everything in Docker containers.

```bash
cd docker
docker compose --profile full up -d --build   # Start all services
docker compose --profile full down            # Stop all services
```

### Option B: Infrastructure Only (For Local IDE Development)

Use this when you're developing backend/frontend locally in your IDE and only need databases and supporting services in Docker.

```bash
cd docker
docker compose up -d db redis chroma qdrant whisper   # Start infrastructure
docker compose down                                    # Stop infrastructure
```

### Option C: Using Make (From Repository Root)

```bash
make quickstart    # Setup env files + start infrastructure
make dev           # Start full development stack
make services      # Start infrastructure only
make dev-down      # Stop everything
```

### Option D: Explicit File Paths (From Any Directory)

```bash
# Full stack
docker compose -f docker/docker-compose.base.yml -f docker/docker-compose.dev.yml --profile full up -d --build

# Infrastructure only
docker compose -f docker/docker-compose.base.yml -f docker/docker-compose.dev.yml up -d db redis chroma qdrant whisper
```

## Environment Configurations

| Environment | Override File | Use Case |
|-------------|---------------|----------|
| **Development** | `docker-compose.dev.yml` | Builds from source, local development |
| **Production** | `docker-compose.yml` | Pre-built images from GHCR |
| **CI/CD** | `docker-compose.ci.yml` | Isolated ports (9xxx), automated testing |

### Switching Environments

Edit `docker/.env` and change the `COMPOSE_FILE` setting:

```bash
# Development (default)
COMPOSE_FILE=docker-compose.base.yml:docker-compose.dev.yml

# Production
COMPOSE_FILE=docker-compose.base.yml:docker-compose.yml

# CI/CD
COMPOSE_FILE=docker-compose.base.yml:docker-compose.ci.yml
```

Or specify files explicitly:

```bash
# Production
docker compose -f docker/docker-compose.base.yml -f docker/docker-compose.yml --profile full up -d

# CI/CD
docker compose -f docker/docker-compose.base.yml -f docker/docker-compose.ci.yml --profile full up -d --build
```

## Docker Compose Profiles

Services are organized into profiles for selective startup:

| Profile | Services Included |
|---------|-------------------|
| `core` | db, redis |
| `vectordb` | chroma, qdrant |
| `backend` | app, celery_worker, celery_beat, + core + vectordb + ml |
| `frontend` | ui |
| `monitoring` | flower, metabase |
| `ml` | whisper |
| `workers` | celery_worker, celery_beat |
| `testing` | uitests |
| `services` | db, redis, chroma, qdrant, whisper (infrastructure only) |
| `full` | All services |

### Using Profiles

From the `docker/` directory (with `.env` configured):

```bash
docker compose --profile core up -d                          # db + redis
docker compose --profile backend up -d                       # backend services
docker compose --profile backend --profile monitoring up -d  # backend + monitoring
docker compose --profile full up -d                          # everything
```

## Services Overview

### Core Infrastructure
| Service | Port | Description |
|---------|------|-------------|
| db | 5432 | PostgreSQL 17 with pgvector extension |
| redis | 6379 | Redis 7 for caching and Celery broker |

### Vector Databases
| Service | Port | Description |
|---------|------|-------------|
| chroma | 8005 | ChromaDB vector database |
| qdrant | 6333, 6334 | Qdrant vector database (REST + gRPC) |

### Application Services
| Service | Port | Description |
|---------|------|-------------|
| app | 8000 | Backend FastAPI application |
| ui | 80, 8080 | Frontend React application |
| celery_worker | - | Background task worker |
| celery_beat | - | Periodic task scheduler |

### ML Services
| Service | Port | Description |
|---------|------|-------------|
| whisper | 8001 | OpenAI Whisper transcription service |

### Monitoring
| Service | Port | Description |
|---------|------|-------------|
| flower | 5555 | Celery task monitoring (user1/password1) |
| metabase | 3000 | Analytics dashboard |

## Port Mappings by Environment

| Service | Production | Development | CI |
|---------|-----------|-------------|-----|
| db | 5432 | 5432 | 5433 |
| redis | 6379 | 6379 | 7379 |
| chroma | 8005 | 8005 | 9005 |
| qdrant | 6333/6334 | 6333/6334 | 9333/9334 |
| app | 8000 | 8000 | 9000 |
| ui | 80/8080 | 80/8080 | 9080/9081 |
| flower | 5555 | 5555 | 9555 |
| metabase | 3000 | 3000 | 9003 |
| whisper | 8001 | 8001 | 9002 |

## Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp docker/.env.example docker/.env
```

Key variables:

```bash
# Container images (production)
APP_IMAGE=ghcr.io/ritechsolutions/genassist-backend:latest
UI_IMAGE=ghcr.io/ritechsolutions/genassist-frontend:latest

# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=core_db

# Redis (optional password)
REDIS_PASSWORD=

# Whisper model size
WHISPER_MODEL=base  # tiny, small, medium, large, large-v2

# Flower monitoring
FLOWER_USER=user1
FLOWER_PASSWORD=password1
```

## Common Commands

### Using Make (Recommended)

Run `make help` from the repository root to see all commands.

| Command | Description |
|---------|-------------|
| `make dev` | Start full dev stack |
| `make services` | Start infrastructure only |
| `make dev-down` | Stop dev stack |
| `make logs-app` | View app logs |
| `make shell-app` | Shell into app container |
| `make shell-db` | PostgreSQL shell |
| `make clean` | Remove all containers |

### Using Docker Compose (from docker/ directory)

```bash
docker compose ps                        # View running containers
docker compose logs -f app               # View app logs
docker compose logs -f --tail=100        # View recent logs
docker compose exec app bash             # Shell into app
docker compose exec db psql -U postgres  # PostgreSQL shell
docker compose build app                 # Rebuild app image
docker compose up -d --build app         # Rebuild and restart app
docker compose up -d --scale celery_worker=3  # Scale workers
```

## GPU Support for Whisper

To enable GPU acceleration for the Whisper service, add the GPU configuration to the whisper service in `docker-compose.dev.yml`:

```yaml
whisper:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

Requires NVIDIA Container Toolkit. See `backend/whisper_ext/README-nvidia-docker.txt`.

## Troubleshooting

All commands below assume you're in the `docker/` directory with `.env` configured.

### Container won't start
```bash
docker compose logs app      # Check app logs
lsof -i :8000                # Check if port is in use
lsof -i :5432                # Check if db port is in use
```

### Database connection issues
```bash
docker compose ps db         # Verify db is healthy
docker compose logs db       # Check db logs
docker compose down -v       # Reset (removes data!)
docker compose up -d db      # Restart db
```

### Permission issues with volumes
```bash
docker compose up volume-init
```

### Clean slate restart
```bash
# From repository root
make clean && make clean-volumes && make dev
```

## Base + Override Pattern Explained

The Docker Compose configuration uses layering:

1. **Base file** (`docker-compose.base.yml`):
   - Service definitions with profiles
   - Health checks
   - Dependencies (depends_on)
   - Common environment variables
   - Restart policies

2. **Override files** (dev/ci/prod):
   - Container names
   - Port mappings
   - Volume mounts
   - Network definitions
   - Build configurations (dev/ci) or image references (prod)
   - Environment-specific settings

When you run `docker compose -f base.yml -f override.yml`, Docker merges the configurations:
- Maps (environment, labels) are merged recursively
- Lists (ports, volumes) are replaced
- Scalars are replaced

This means override files only need to specify what's different from the base.
