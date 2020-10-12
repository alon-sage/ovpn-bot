FROM postgres as base

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
RUN apt-get update && apt-get install -y \
    ca-certificates \
    python3.7 \
    && rm -rf /var/lib/apt/lists/*


FROM base as build

RUN apt-get update && apt-get install -y \
    python3-virtualenv \
    python3-setuptools \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN python3.7 -m easy_install pipenv
COPY Pipfile Pipfile.lock /app/
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install


FROM base as app

COPY --from=build /app/.venv /app/.venv/
COPY alembic.ini env.py /app/
COPY versions /app/versions/
COPY apply-migrations.sh /docker-entrypoint-initdb.d/apply-migrations.sh