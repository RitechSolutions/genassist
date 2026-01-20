# ==========================================
# Stage 1: Builder (Compilers & Heavy Lifting)
# ==========================================
FROM python:3.12-slim-bookworm as builder

WORKDIR /src
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 1. Install Build Dependencies
COPY packages.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    && xargs -a packages.txt apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 2. Create Virtual Environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 3. Install Requirements (Aggressive Cleanup Mode)
COPY requirements-main.txt .
COPY requirements-rag.txt .
COPY requirements-app.txt .

RUN pip install --upgrade pip setuptools wheel && \
    # A. Install everything normally (might pull heavy GPU versions)
    pip install --no-cache-dir \
    -r requirements-main.txt \
    -r requirements-rag.txt \
    -r requirements-app.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu && \
    # B. Uninstall Torch and NVIDIA bloat
    pip uninstall -y torch torchvision torchaudio && \
    pip freeze | grep nvidia | cut -d= -f1 | xargs -r pip uninstall -y && \
    # C. Re-install strictly CPU-only versions
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# ==========================================
# Stage 2: Runtime (Minimal & Secure)
# ==========================================
FROM python:3.12-slim-bookworm as runtime

WORKDIR /src

# 1. Install Runtime Dependencies & Security Updates
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libmagic1 \
    antiword \
    curl \
    libpq5 \
    libxml2 \
    && rm -rf /var/lib/apt/lists/*

# 2. Configure Environment & User
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME="/home/genassist/.cache" \
    TRANSFORMERS_CACHE="/home/genassist/.cache"

RUN useradd -m -u 1000 genassist

# 3. Copy LEAN Virtual Environment from Builder
COPY --from=builder /opt/venv /opt/venv

# 4. Copy Application Code
COPY --chown=genassist:genassist ./run.py ./run_celery.py ./migrations.py ./alembic.ini /src/
COPY --chown=genassist:genassist ./app /src/app
COPY --chown=genassist:genassist ./alembic /src/alembic

RUN --chown -R genassist:genassist .cache

# Optional: Certs (Ensure no keys)
COPY --chown=genassist:genassist ./certs /src/certs

# 5. Set User and Entrypoint
USER genassist

EXPOSE 8000
CMD ["python", "/src/run.py"]