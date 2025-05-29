FROM python:3.10-slim
WORKDIR /src

COPY packages.txt /src/packages.txt

RUN apt-get update && \
    xargs -a /src/packages.txt apt-get install -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /src/requirements.txt
RUN pip install -r /src/requirements.txt

COPY ./run.py /src/run.py
COPY ./certs /src/certs
COPY ./app /src/app

COPY ./.env.example /src/.env

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