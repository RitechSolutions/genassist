# Migrating from pip to uv

## Why Replace pip with uv?

### Performance

uv is written in Rust and is **10-100x faster** than pip for dependency resolution and installation. In a project like GenAssist with 4 Dockerfiles and multiple requirements files, this translates to significantly faster Docker builds and shorter CI/CD pipelines.

| Operation | pip | uv |
|-----------|-----|-----|
| Install from requirements.txt | ~45-90s | ~2-5s |
| Resolve dependencies | ~30-60s | ~1-3s |
| Docker layer rebuild (deps) | ~2-5 min | ~10-30s |

### Reproducibility

pip does not generate lockfiles natively. GenAssist currently pins versions in `requirements-*.txt` files, but transitive dependencies are not locked. uv provides a built-in `uv.lock` file that captures the entire dependency tree, eliminating "works on my machine" issues.

### Unified Tooling

uv replaces multiple tools in one binary:

| Current tool | uv equivalent |
|-------------|---------------|
| pip install | uv pip install |
| pip freeze | uv pip freeze |
| pip-compile (pip-tools) | uv pip compile |
| virtualenv / venv | uv venv |
| pyenv (Python version mgmt) | uv python install |

### Docker Image Benefits

- **Faster builds**: Dependency installation is the slowest layer in the backend Dockerfile. uv cuts this from minutes to seconds.
- **Better caching**: uv has smarter caching that works well with Docker layer caching.
- **Smaller attack surface**: Single static binary copied into the image vs. pip + setuptools + wheel.

---

## Current State

### Files Using pip

| File | Usage |
|------|-------|
| `backend/Dockerfile` | Install deps, uninstall torch/nvidia, reinstall CPU torch |
| `backend/app/Dockerfile` | Install deps from requirements.txt |
| `websocket/Dockerfile` | Install deps from requirements.txt |
| `backend/whisper_ext/Dockerfile.whisper` | Install deps across 6 separate pip calls |
| `backend/scripts/export_pip_requirements.sh` | Freeze installed packages |

### Requirements Files

| File | Purpose |
|------|---------|
| `backend/requirements-main.txt` | Core framework dependencies |
| `backend/requirements-app.txt` | Application-specific dependencies |
| `backend/requirements-rag.txt` | RAG/vector search dependencies |
| `backend/requirements-dev.txt` | Development and testing dependencies |
| `websocket/requirements.txt` | WebSocket service dependencies |

---

## Migration Plan

### Phase 1: Drop-in Replacement (Low Risk)

Replace `pip` commands with `uv pip` commands in all Dockerfiles. No changes to requirements files or project structure needed.

**Changes per Dockerfile:**

1. Add uv installation at the top:
   ```dockerfile
   COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
   ```

2. Replace all pip commands:
   ```dockerfile
   # Before
   RUN pip install --no-cache-dir -r requirements.txt

   # After
   RUN uv pip install --system --no-cache-dir -r requirements.txt
   ```

**Effort**: Small — find-and-replace across 4 Dockerfiles and 1 shell script.

**Win**: Immediate build speed improvement with zero risk to dependency resolution.

### Phase 2: Consolidate Requirements into pyproject.toml (Medium Risk)

Move dependency declarations from multiple `requirements-*.txt` files into `pyproject.toml` using dependency groups.

**Before:**
```
backend/requirements-main.txt
backend/requirements-app.txt
backend/requirements-rag.txt
backend/requirements-dev.txt
```

**After** (single `pyproject.toml`):
```toml
[project]
dependencies = [
    # contents of requirements-main.txt + requirements-app.txt
]

[project.optional-dependencies]
rag = [
    # contents of requirements-rag.txt
]
dev = [
    # contents of requirements-dev.txt
]
```

**Effort**: Medium — consolidate files, update Dockerfiles and CI to reference groups instead of files.

**Win**: Single source of truth for dependencies, easier to manage and review.

### Phase 3: Adopt uv Lockfile (Medium Risk)

Generate a `uv.lock` file that pins the entire dependency tree including transitive dependencies.

```bash
uv lock
```

Update Dockerfiles to use:
```dockerfile
RUN uv sync --frozen --no-dev
```

**Effort**: Small once Phase 2 is done — run `uv lock` and update Dockerfile commands.

**Win**: Fully reproducible builds. Every developer and CI run installs the exact same versions of every package, including transitive dependencies.

### Phase 4: Use uv for Python Version Management (Optional)

Replace any system Python setup with uv-managed Python:

```dockerfile
RUN uv python install 3.12
```

**Effort**: Small.

**Win**: Consistent Python version across all environments without relying on base image versions.

---

## Impact Summary

| Improvement | Phase | Impact |
|-------------|-------|--------|
| Docker build speed (10-100x faster installs) | 1 | High |
| CI/CD pipeline speed | 1 | High |
| Local development setup speed | 1 | Medium |
| Reproducible builds (lockfile) | 3 | High |
| Single dependency file (pyproject.toml) | 2 | Medium |
| Reduced tooling complexity | 2 | Low |
| Python version consistency | 4 | Low |

---

## Risks and Considerations

- **uv is relatively new**: Backed by Astral (creators of Ruff, already used in this project). Actively maintained and widely adopted.
- **PyTorch custom index URL**: uv supports `--index-url` and `--extra-index-url` flags, so the CPU-only torch install in `backend/Dockerfile` works without changes.
- **pip-specific flags**: Most pip flags have uv equivalents. The `--system` flag is needed in Docker contexts where there is no virtual environment.
- **Team familiarity**: uv's `pip` interface is intentionally compatible with pip's CLI, so the learning curve is minimal.
