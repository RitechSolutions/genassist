FROM python:3.12-slim-bookworm
WORKDIR /src

COPY packages.txt /src/packages.txt

RUN sed -i 's/\r$//' /src/packages.txt

RUN apt-get update && apt-get clean && apt-get install -y build-essential && \
    xargs -a /src/packages.txt apt-get install -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY ./requirements-main.txt /src/requirements-main.txt
RUN pip install --no-cache-dir -r /src/requirements-main.txt

# COPY ./requirements-whisper.txt /src/requirements-whisper.txt
COPY ./requirements-rag.txt /src/requirements-rag.txt
COPY ./requirements-app.txt /src/requirements-app.txt

# RUN pip install --no-cache-dir -r /src/requirements-whisper.txt && \
RUN pip install --no-cache-dir -r /src/requirements-rag.txt && \
    pip install --no-cache-dir -r /src/requirements-app.txt

# RUN playwright install to donwload the browser of the library
RUN playwright install chromium

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