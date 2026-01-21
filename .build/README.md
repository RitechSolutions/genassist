# Build and Deploy Guide

## Step 1: Clone the Repository

```bash
git clone https://github.com/RitechSolutions/genassist.git
cd genassist
```

## Step 2: Add Environment Files

Create `.env` files in the following directories:

1. **Backend** - Create `.env` file in `backend/` folder (copy from env.example)
2. **Frontend** - Create `.env` file in `frontend/` folder (copy from env.example)

Contact your team lead or check your secrets manager for the required environment variables.

## Step 3: Build and Push Docker Images

Run the `push-images.sh` script to build and push Docker images to GHCR.

### Prerequisites
- Docker installed and running

### Required Environment Variables

These variables are used by both `push-images.sh` and `docker-compose.build.yml`:

```bash
export OWNER="YOUR_ACCOUNT_ON_GITHUB"   # GitHub org/user (e.g., RitechSolutions)
export REPO="YOUR_GITHUB_REPO"          # Repository name (e.g., genassist)
export VERSION="1.0.0"                  # Version tag (e.g., 1.2.3)
export GHCR_TOKEN="your_github_token"   # GitHub Container Registry token
```

> **Note:** The `OWNER` and `REPO` variables are used to construct the image names in the format `ghcr.io/${OWNER}/${REPO}/<service>`

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REGISTRY` | `ghcr.io` | Container registry |
| `IMAGE_TAG` | `$VERSION` | Immutable release tag |
| `PROD_TAG` | `prod` | Production tag |
| `LATEST_TAG` | `latest` | Latest tag |
| `PUSH_UITESTS` | `false` | Set to `true` to also push UI tests image |

### Run the Script

```bash
./.build/push-images.sh
```

This will:
1. Log into GHCR
2. Build all services (app, ui, whisper)
3. Push versioned tags
4. Create and push `prod` and `latest` tags

## Step 4: Deploy to Cloud

For cloud deployment instructions, refer to the infrastructure repository:

**[genassist-internal-infra](https://github.com/RitechSolutions/genassist-internal-infra)**

Follow the README.md in that repository for detailed deployment steps.
