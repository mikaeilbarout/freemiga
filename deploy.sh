#!/usr/bin/env bash
# One command for "pull the latest code and redeploy" that can't forget the
# docker-compose.shared-nginx.yml overlay — a plain `docker compose up -d app`
# on a shared-nginx server (see README.md, "If the server already runs a
# different nginx") silently drops the app container's `web_shared` network attachment
# and its `freemiga_app` alias, taking the site offline until someone
# notices and manually reconnects it. Detecting the mode here instead of
# relying on whoever runs the deploy to remember the right `-f` flags is
# what actually prevents that class of outage from recurring.
# Only the docker calls are elevated (via sudo below) — `git pull` runs as
# whichever user invoked this script, so it keeps using *their* SSH key/agent
# for GitHub. Run this script plain (`./deploy.sh`), not with a leading
# `sudo` — `sudo ./deploy.sh` would run git as root too, which has no access
# to your GitHub key and fails with "Permission denied (publickey)".
#
# --force-recreate on `app` below isn't optional: `docker compose up -d` can
# decide nothing meaningful changed and just start the *existing* container
# instead of building a new one from the current compose config — seen
# firsthand on this project, where that left app running without its
# web_shared attachment even on a correctly-flagged `up -d` command. Forcing
# recreation makes that decision moot.
set -euo pipefail
cd "$(dirname "$0")"

git pull origin main

DC=(sudo docker compose)
SHARED_NGINX=false

if sudo docker network inspect web_shared >/dev/null 2>&1; then
  SHARED_NGINX=true
  echo "==> Shared-nginx mode detected (web_shared network exists)."
  echo "==> docker compose -f docker-compose.yml -f docker-compose.shared-nginx.yml ..."
  "${DC[@]}" -f docker-compose.yml -f docker-compose.shared-nginx.yml build app
  "${DC[@]}" -f docker-compose.yml -f docker-compose.shared-nginx.yml up -d --force-recreate db app
else
  echo "==> Standalone mode (this project's own nginx/certbot)."
  "${DC[@]}" build app
  "${DC[@]}" up -d --force-recreate
fi

"${DC[@]}" ps

if [ "$SHARED_NGINX" = true ]; then
  # Belt-and-suspenders: confirm the alias the external nginx's proxy_pass
  # depends on actually made it onto the new container before declaring
  # success, instead of finding out from a site-down report.
  if sudo docker inspect freemiga-app-1 --format '{{json .NetworkSettings.Networks.web_shared.Aliases}}' 2>/dev/null | grep -q freemiga_app; then
    echo "==> OK: freemiga_app alias confirmed on web_shared."
  else
    echo "!! WARNING: freemiga_app alias NOT found on web_shared — the site is likely down." >&2
    echo "!! Run: sudo docker network connect --alias freemiga_app web_shared freemiga-app-1" >&2
    exit 1
  fi
fi
