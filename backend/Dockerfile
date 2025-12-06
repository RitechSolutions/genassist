FROM python:3.10-slim-bookworm AS builder
WORKDIR /src

COPY packages.txt /src/packages.txt

RUN sed -i 's/\r$//' /src/packages.txt

RUN apt-get update && \
    xargs -a /src/packages.txt apt-get install -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip==24.0

COPY ./requirements-main.txt /src/requirements-main.txt
RUN pip install --no-cache-dir -r /src/requirements-main.txt

FROM python:3.10-slim-bookworm
WORKDIR /src

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY packages.txt /src/packages.txt
RUN apt-get update && \
    xargs -a /src/packages.txt apt-get install -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# COPY ./requirements-whisper.txt /src/requirements-whisper.txt
COPY ./requirements-rag.txt /src/requirements-rag.txt
COPY ./requirements-app.txt /src/requirements-app.txt

# RUN pip install --no-cache-dir -r /src/requirements-whisper.txt && \
RUN pip install --no-cache-dir -r /src/requirements-rag.txt && \
    pip install --no-cache-dir -r /src/requirements-app.txt

COPY ./run.py /src/run.py
COPY ./run_celery.py /src/run_celery.py
COPY ./certs /src/certs
COPY ./app /src/app
COPY ./.pylintrc /src/.pylintrc
COPY ./tests /src/tests
COPY ./pytest.ini /src/pytest.ini
COPY ./alembic /src/alembic
COPY ./alembic.ini /src/alembic.ini
COPY ./migrations.py /src/migrations.py
COPY ./models /root/.cache

RUN ls /root/.cache



EXPOSE 8000

CMD ["python", "/src/run.py"]