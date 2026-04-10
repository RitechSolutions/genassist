FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    curl -LsSf https://astral.sh/uv/0.7.12/install.sh | sh && \
    cp /root/.local/bin/uv /usr/local/bin/uv && \
    cp /root/.local/bin/uvx /usr/local/bin/uvx

COPY requirements.txt .
RUN uv pip install --system --no-cache-dir -r requirements.txt

COPY src/ /app/

USER nobody

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]
