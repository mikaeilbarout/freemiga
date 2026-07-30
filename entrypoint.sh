#!/usr/bin/env bash
set -e

# Schema setup runs once here, as a single process, before gunicorn spawns
# multiple workers — see scripts/init_db.py for why that ordering matters.
python -m scripts.init_db

exec gunicorn -c gunicorn_conf.py app.main:app
