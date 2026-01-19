# ==========================================
# Stage 1: Builder
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

# 3. Install Requirements (Let pip do its thing first)

COPY requirements-main.txt .
COPY requirements-rag.txt .
COPY requirements-app.txt .

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements-main.txt && \
    pip install --no-cache-dir -r requirements-rag.txt && \
    pip install --no-cache-dir -r requirements-app.txt

# 4. Force Replace PyTorch with CPU Version
RUN pip uninstall -y torch torchvision torchaudio && \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# ==========================================
# Stage 2: Runtime
# ==========================================
FROM python:3.12-slim-bookworm as runtime

WORKDIR /src

# 1. Install Runtime System Dependencies ONLY
# We keep the 500MB of runtime libs (ffmpeg, tesseract) because the app needs them
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

# 3. Create Non-Root User
RUN useradd -m -u 1000 genassist

# 4. Copy Lean Virtual Environment from Builder
COPY --from=builder /opt/venv /opt/venv

# 5. Copy Application Code
COPY --chown=genassist:genassist ./run.py ./run_celery.py ./migrations.py ./alembic.ini /src/
COPY --chown=genassist:genassist ./app /src/app
COPY --chown=genassist:genassist ./alembic /src/alembic

# Optional: Certs
COPY --chown=genassist:genassist ./certs /src/certs

# 6. Set User and Entrypoint
USER genassist

EXPOSE 8000
CMD ["python", "/src/run.py"]