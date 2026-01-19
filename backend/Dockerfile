# ==========================================
# Stage 1: Builder (Compilers & Headers)
# ==========================================
FROM python:3.12-slim-bookworm as builder

WORKDIR /src
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# 1. Install Build Dependencies
COPY packages.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && xargs -a packages.txt apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 2. Create Virtual Environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 3. Upgrade Pip & Install PyTorch (CPU Optimized)
# CRITICAL: We explicitly install the CPU version of torch. 
RUN pip install --upgrade pip==24.0 && \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 4. Install Application Requirements
COPY requirements-main.txt .
COPY requirements-rag.txt .
COPY requirements-app.txt .

RUN pip install --no-cache-dir -r requirements-main.txt && \
    pip install --no-cache-dir -r requirements-rag.txt && \
    pip install --no-cache-dir -r requirements-app.txt

# ==========================================
# Stage 2: Runtime (Binaries Only)
# ==========================================
FROM python:3.12-slim-bookworm as runtime

WORKDIR /src

# 1. Install Runtime System Dependencies ONLY
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# 3. Copy Virtual Environment from Builder
COPY --from=builder /opt/venv /opt/venv

# 4. Copy Application Code
# We rely on .dockerignore to exclude local secrets/heavy files
COPY --chown=genassist:genassist ./run.py ./run_celery.py ./migrations.py ./alembic.ini /src/
COPY --chown=genassist:genassist ./app /src/app
COPY --chown=genassist:genassist ./alembic /src/alembic

# --- OPTIONAL: CERTIFICATES ---
# Ensure no private keys are in here
COPY --chown=genassist:genassist ./certs /src/certs

# 5. Set User and Entrypoint
USER genassist

EXPOSE 8000
CMD ["python", "/src/run.py"]