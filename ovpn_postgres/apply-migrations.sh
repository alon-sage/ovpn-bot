#!/usr/bin/env bash

cd /app || exit 1
/app/.venv/bin/alembic upgrade head
