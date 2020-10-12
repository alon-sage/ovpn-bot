FROM ubuntu:18.04 as base

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
RUN apt-get update && apt-get install -y \
    ca-certificates \
    python3.8 \
    && rm -rf /var/lib/apt/lists/*


FROM base as build

RUN apt-get update && apt-get install -y \
    python3-virtualenv \
    python3-setuptools \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN python3.8 -m easy_install pipenv
COPY Pipfile Pipfile.lock /app/
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install


FROM base as app

WORKDIR /app
COPY --from=build /app/.venv /app/.venv/
COPY ovpn_bot /app/ovpn_bot
CMD ["/app/.venv/bin/python", "-m", "ovpn_bot"]