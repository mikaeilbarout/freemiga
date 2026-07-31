#!/usr/bin/env bash
# One command for "pull the latest code and redeploy" that can't forget the
# docker-compose.shared-nginx.yml overlay — a plain `docker compose up -d app`
# on a shared-nginx server (see README.md, "اگه سرور از قبل یه nginx دیگه
# داره") silently drops the app container's `web_shared` network attachment
# and its `freemiga_app` alias, taking the site offline until someone
# notices and manually reconnects it. Detecting the mode here instead of
# relying on whoever runs the deploy to remember the right `-f` flags is
# what actually prevents that class of outage from recurring.
set -euo pipefail
cd "$(dirname "$0")"

git pull origin main

if docker network inspect web_shared >/dev/null 2>&1; then
  echo "==> Shared-nginx mode detected (web_shared network exists)."
  echo "==> docker compose -f docker-compose.yml -f docker-compose.shared-nginx.yml ..."
  docker compose -f docker-compose.yml -f docker-compose.shared-nginx.yml build app
  docker compose -f docker-compose.yml -f docker-compose.shared-nginx.yml up -d db app
else
  echo "==> Standalone mode (this project's own nginx/certbot)."
  docker compose build app
  docker compose up -d
fi

docker compose ps
