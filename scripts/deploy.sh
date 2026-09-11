#!/usr/bin/env bash
# Freemiga production deploy/update script. Run this ON THE SERVER (not from
# a dev machine), as a user that can run docker (root, or a member of the
# `docker` group). Idempotent — safe to re-run for updates.
#
# What it does NOT do: touch an nginx/certbot setup that already exists for
# other sites on this host. It detects that case and prints the manual steps
# from README.md instead of guessing at someone else's container names.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/freemiga}"
REPO_URL="${REPO_URL:-git@github.com:mikaeilbarout/freemiga.git}"
DOMAIN="${DOMAIN:-shop.persepolisconstruction.co.uk}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
warn() { printf '\n\033[1;33m!!! %s\033[0m\n' "$1"; }
gen_hex() { python3 -c "import secrets; print(secrets.token_hex(32))"; }
gen_urlsafe() { python3 -c "import secrets; print(secrets.token_urlsafe(24))"; }

# --- 1. Docker ---
if ! command -v docker >/dev/null 2>&1; then
  log "Docker not found — installing via get.docker.com"
  curl -fsSL https://get.docker.com | sh
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "The 'docker compose' plugin is missing. Install docker-compose-plugin and re-run." >&2
  exit 1
fi

# --- 2. Clone or update the repo ---
if [ -d "$REPO_DIR/.git" ]; then
  log "Repo already present at $REPO_DIR — pulling latest"
  git -C "$REPO_DIR" fetch origin
  git -C "$REPO_DIR" pull --ff-only origin "$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD)"
else
  log "Cloning $REPO_URL to $REPO_DIR"
  mkdir -p "$(dirname "$REPO_DIR")"
  git clone "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"

# --- 3. .env ---
if [ ! -f .env ]; then
  log "Creating .env from .env.example with generated secrets"
  cp .env.example .env
  sed -i "s#^SESSION_SECRET=.*#SESSION_SECRET=$(gen_hex)#" .env
  sed -i "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=$(gen_urlsafe)#" .env
  sed -i "s#^SITE_BASE_URL=.*#SITE_BASE_URL=https://$DOMAIN#" .env
  warn "Everything else in .env (Marzban admin creds, admin panel password, payment
    keys, Telegram token, Resend key) is still a placeholder. Edit
    $REPO_DIR/.env before real customers use the site — see README.md for
    what each variable is and where to get it."
else
  log ".env already exists — leaving it untouched"
fi

# --- 4. dev override file must not run in prod ---
if [ -f docker-compose.override.yml ]; then
  warn "docker-compose.override.yml exists — that's dev-only (exposes the app
    directly on :8002 with no nginx/TLS, and trusts forwarded-for headers
    from anyone). Remove it before continuing in production."
  read -rp "Remove it now? [y/N] " ans
  if [ "${ans:-}" = "y" ] || [ "${ans:-}" = "Y" ]; then
    rm docker-compose.override.yml
  else
    echo "Leaving it in place — re-run this script after removing it." >&2
    exit 1
  fi
fi

# --- 5. Bring up db + app (no nginx yet) ---
log "Starting db + app"
docker compose up -d db app
sleep 2
docker compose logs --tail 30 app

# --- 6. Detect whether this host already has an nginx on 80/443 ---
ports_taken=""
if command -v ss >/dev/null 2>&1; then
  ss -ltn 2>/dev/null | grep -qE ':80\s' && ports_taken="80"
  ss -ltn 2>/dev/null | grep -qE ':443\s' && ports_taken="${ports_taken:+$ports_taken,}443"
fi
# A container of ours already binding those ports doesn't count as "someone else's nginx".
if docker compose ps nginx 2>/dev/null | grep -q "Up"; then
  ports_taken=""
fi

if [ -n "$ports_taken" ]; then
  warn "Port(s) $ports_taken already in use by something else on this host —
    this matches the README's documented 'shared nginx' scenario (this
    server already fronts persepolisconstruction.co.uk). This script will NOT
    touch that existing nginx/certbot setup — it can't safely guess the other
    site's container name or config layout.

    App + Postgres are up and listening internally on :8001 as service
    'app' on the compose network 'freemiga_default'. To finish, follow
    README.md -> 'If the server already runs a different nginx':
      1. docker network create web_shared        # once, if it doesn't exist
      2. docker network connect web_shared \$(docker compose ps -q app)
      3. docker network connect web_shared <existing-nginx-container-name>
      4. add a server block to that nginx's conf.d — copy nginx/conf.d/freemiga.conf
         from this repo as a starting point, set server_name $DOMAIN, and
         proxy_pass http://\$(docker compose ps -q app):8001;
         (the container ID is stable across restarts as long as you don't
         recreate it; for a friendlier name add 'container_name: freemiga_app'
         under the app service in docker-compose.yml and use that instead)
      5. issue a cert on the existing certbot for $DOMAIN, then reload that nginx
      6. if port 443 is actually taken by Xray/Marzban rather than nginx, put
         $DOMAIN behind Cloudflare and use an Origin Rule to route 443 to
         whatever port nginx really listens on (README covers this case too)

    docker compose ps:"
  docker compose ps
  exit 0
fi

log "Ports 80/443 are free — bringing up this project's own nginx + Let's Encrypt"
if [ -z "$CERTBOT_EMAIL" ]; then
  read -rp "Email for Let's Encrypt renewal notices (CERTBOT_EMAIL): " CERTBOT_EMAIL
fi
sed -i "s/server_name .*/server_name $DOMAIN;/" nginx/conf.d/freemiga.conf
sed -i "s#/etc/letsencrypt/live/[^/]*/#/etc/letsencrypt/live/$DOMAIN/#g" nginx/conf.d/freemiga.conf
sed -i "s/^DOMAINS=.*/DOMAINS=($DOMAIN)/" scripts/init-letsencrypt.sh

CERTBOT_EMAIL="$CERTBOT_EMAIL" ./scripts/init-letsencrypt.sh
docker compose up -d

log "Done. docker compose ps:"
docker compose ps
echo
echo "https://$DOMAIN should now be live. Admin panel: https://$DOMAIN/admin"
