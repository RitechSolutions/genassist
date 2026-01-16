FROM python:3.12-slim
WORKDIR /src

RUN apt-get update
RUN apt-get install -y software-properties-common
RUN apt-get install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm git \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev ffmpeg

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

COPY ./models /root/.cache
RUN ls /root/.cache

CMD ["python", "/src/run.py"]