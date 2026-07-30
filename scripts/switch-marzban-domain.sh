#!/usr/bin/env bash
# One-time migration: move the Marzban panel to a new domain
# (panel.freemiga.com by default) and issue it a real Let's Encrypt cert.
# Run this ON THE SERVER, as root (it stops/starts services and edits
# Marzban's own config).
#
# Existing customers' already-issued subscription links keep pointing at the
# OLD domain (e.g. panel.persepolisconstruction.co.uk) — this script does not
# touch that domain's DNS/cert, so old links keep working. Only NEW/renewed
# orders after this runs will use the new domain (via app/config.py's
# MARZBAN_BASE_URL default, or the .env override this script also updates).
#
# This is intentionally cautious: it asks before stopping anything it didn't
# create itself, because it can't see what's actually running on this host's
# port 80 ahead of time.
set -euo pipefail

NEW_DOMAIN="${NEW_DOMAIN:-panel.freemiga.com}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
FREEMIGA_DIR="${FREEMIGA_DIR:-/opt/freemiga}"
MARZBAN_DIR="${MARZBAN_DIR:-}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
warn() { printf '\n\033[1;33m!!! %s\033[0m\n' "$1"; }
die() { printf '\n\033[1;31mXXX %s\033[0m\n' "$1" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "Run as root (needs to stop port 80, write to /etc/letsencrypt, edit Marzban's .env)."

# --- 0. Sanity: does the domain actually resolve here? ---
log "Checking DNS for $NEW_DOMAIN"
resolved_ip="$(getent hosts "$NEW_DOMAIN" | awk '{print $1}' | head -1 || true)"
this_ip="$(curl -fsS --max-time 5 https://ifconfig.me || curl -fsS --max-time 5 https://api.ipify.org || true)"
if [ -z "$resolved_ip" ]; then
  die "$NEW_DOMAIN doesn't resolve at all yet. Point its A record at this server's IP and wait for propagation before re-running."
fi
if [ -n "$this_ip" ] && [ "$resolved_ip" != "$this_ip" ]; then
  warn "$NEW_DOMAIN resolves to $resolved_ip but this host's public IP looks like $this_ip. If that's wrong (e.g. behind Cloudflare proxy — DNS-only/grey-cloud is required for the HTTP-01 challenge below), fix it first."
  read -rp "Continue anyway? [y/N] " ans
  [ "${ans:-}" = "y" ] || exit 1
fi

# --- 1. Locate the Marzban install ---
if [ -z "$MARZBAN_DIR" ]; then
  for candidate in /opt/marzban /root/Marzban /root/marzban; do
    [ -f "$candidate/.env" ] && [ -f "$candidate/docker-compose.yml" ] && MARZBAN_DIR="$candidate" && break
  done
fi
if [ -z "$MARZBAN_DIR" ]; then
  mz_container="$(docker ps --format '{{.Names}}' | grep -i marzban | grep -vi marzban-node | grep -vi marzban-guard | head -1 || true)"
  if [ -n "$mz_container" ]; then
    mz_workdir="$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' "$mz_container" 2>/dev/null || true)"
    [ -n "$mz_workdir" ] && [ -f "$mz_workdir/.env" ] && MARZBAN_DIR="$mz_workdir"
  fi
fi
[ -n "$MARZBAN_DIR" ] || die "Couldn't find Marzban's install directory automatically. Re-run with MARZBAN_DIR=/path/to/marzban $0"
log "Found Marzban at $MARZBAN_DIR"

grep -q '^UVICORN_SSL_CERTFILE' "$MARZBAN_DIR/.env" 2>/dev/null || \
  warn "Didn't find UVICORN_SSL_CERTFILE in $MARZBAN_DIR/.env — this script assumes the standard Marzban TLS-on-uvicorn setup. Double check $MARZBAN_DIR/.env by hand if the panel doesn't come back up HTTPS at the end."

echo "Current relevant lines in $MARZBAN_DIR/.env:"
grep -E '^UVICORN_SSL_(CERT|KEY)FILE' "$MARZBAN_DIR/.env" 2>/dev/null || echo "  (none found)"
read -rp "Proceed with migrating Marzban's panel domain to $NEW_DOMAIN? [y/N] " ans
[ "${ans:-}" = "y" ] || exit 1

# --- 2. Figure out what currently owns port 80, so we can free it for the HTTP-01 challenge ---
stop_cmd=""
start_cmd=""
if [ -f "$FREEMIGA_DIR/docker-compose.yml" ] && docker compose -f "$FREEMIGA_DIR/docker-compose.yml" ps nginx 2>/dev/null | grep -q "Up"; then
  log "Port 80 is held by Freemiga's own nginx container ($FREEMIGA_DIR) — will stop/start that automatically."
  stop_cmd="docker compose -f $FREEMIGA_DIR/docker-compose.yml stop nginx"
  start_cmd="docker compose -f $FREEMIGA_DIR/docker-compose.yml start nginx"
elif command -v ss >/dev/null 2>&1 && ss -ltnp 2>/dev/null | grep -q ':80 '; then
  owner_line="$(ss -ltnp 2>/dev/null | grep ':80 ' | head -1)"
  warn "Something else is listening on port 80 (this is likely the shared nginx that already fronts persepolisconstruction.co.uk):
    $owner_line
  This script does not know how to safely stop/start it for you."
  echo "Enter the exact command to STOP it (e.g. 'systemctl stop nginx', or 'docker stop <container>'), or leave blank to abort:"
  read -rp "stop command: " stop_cmd
  [ -n "$stop_cmd" ] || die "No stop command given — aborting rather than guessing."
  echo "Enter the exact command to START it again afterward:"
  read -rp "start command: " start_cmd
  [ -n "$start_cmd" ] || die "No start command given — aborting rather than guessing."
else
  log "Port 80 looks free already — no need to stop anything."
fi

# --- 3. certbot on the host (separate from any dockerized certbot — independent cert store) ---
if ! command -v certbot >/dev/null 2>&1; then
  log "Installing certbot on the host"
  (command -v apt-get >/dev/null 2>&1 && apt-get update -qq && apt-get install -y -qq certbot) || die "certbot install failed — install it manually and re-run."
fi

if [ -z "$CERTBOT_EMAIL" ]; then
  read -rp "Email for Let's Encrypt renewal notices (CERTBOT_EMAIL): " CERTBOT_EMAIL
fi

if [ -d "/etc/letsencrypt/live/$NEW_DOMAIN" ]; then
  log "A certificate for $NEW_DOMAIN already exists on this host — skipping issuance."
else
  log "Issuing certificate for $NEW_DOMAIN"
  [ -n "$stop_cmd" ] && { log "Stopping: $stop_cmd"; eval "$stop_cmd"; }
  trap '[ -n "$start_cmd" ] && { log "Restarting: $start_cmd"; eval "$start_cmd"; }' EXIT
  certbot certonly --standalone --preferred-challenges http --http-01-port 80 \
    -d "$NEW_DOMAIN" --email "$CERTBOT_EMAIL" --agree-tos --non-interactive
  [ -n "$start_cmd" ] && { log "Restarting: $start_cmd"; eval "$start_cmd"; }
  trap - EXIT
fi

# --- 4. Point Marzban at the new cert ---
log "Updating $MARZBAN_DIR/.env"
cp "$MARZBAN_DIR/.env" "$MARZBAN_DIR/.env.bak.$(date +%s)"
if grep -q '^UVICORN_SSL_CERTFILE' "$MARZBAN_DIR/.env"; then
  sed -i "s#^UVICORN_SSL_CERTFILE.*#UVICORN_SSL_CERTFILE = \"/etc/letsencrypt/live/$NEW_DOMAIN/fullchain.pem\"#" "$MARZBAN_DIR/.env"
else
  echo "UVICORN_SSL_CERTFILE = \"/etc/letsencrypt/live/$NEW_DOMAIN/fullchain.pem\"" >> "$MARZBAN_DIR/.env"
fi
if grep -q '^UVICORN_SSL_KEYFILE' "$MARZBAN_DIR/.env"; then
  sed -i "s#^UVICORN_SSL_KEYFILE.*#UVICORN_SSL_KEYFILE = \"/etc/letsencrypt/live/$NEW_DOMAIN/privkey.pem\"#" "$MARZBAN_DIR/.env"
else
  echo "UVICORN_SSL_KEYFILE = \"/etc/letsencrypt/live/$NEW_DOMAIN/privkey.pem\"" >> "$MARZBAN_DIR/.env"
fi

log "Restarting Marzban"
if command -v marzban >/dev/null 2>&1; then
  marzban restart
else
  (cd "$MARZBAN_DIR" && docker compose restart)
fi

sleep 3
log "Verifying HTTPS on the new domain"
if curl -fsSk --max-time 10 "https://$NEW_DOMAIN:8000/docs" >/dev/null 2>&1 || curl -fsSk --max-time 10 "https://127.0.0.1:8000/docs" --resolve "$NEW_DOMAIN:8000:127.0.0.1" >/dev/null 2>&1; then
  echo "OK — https://$NEW_DOMAIN:8000 is responding."
else
  warn "Couldn't confirm the panel is responding on the new domain/cert. Check: docker logs on the Marzban container, and the .env values written above. Your backup is at $MARZBAN_DIR/.env.bak.*"
fi

# --- 5. Update Freemiga's own MARZBAN_BASE_URL and restart the shop app ---
if [ -f "$FREEMIGA_DIR/.env" ]; then
  log "Updating $FREEMIGA_DIR/.env MARZBAN_BASE_URL"
  sed -i "s#^MARZBAN_BASE_URL=.*#MARZBAN_BASE_URL=https://$NEW_DOMAIN:8000#" "$FREEMIGA_DIR/.env"
  (cd "$FREEMIGA_DIR" && docker compose up -d app)
else
  warn "$FREEMIGA_DIR/.env not found — set MARZBAN_BASE_URL=https://$NEW_DOMAIN:8000 there by hand and restart the app."
fi

# --- 6. Auto-renewal, including restarting Marzban after each renewal ---
cron_file=/etc/cron.d/marzban-panel-cert-renew
if [ ! -f "$cron_file" ]; then
  log "Installing renewal cron at $cron_file"
  {
    echo "# Renews the $NEW_DOMAIN cert and restarts Marzban to pick it up (Marzban doesn't hot-reload certs)."
    if [ -n "$stop_cmd" ]; then
      echo "0 3 * * * root bash -c '$stop_cmd; certbot renew --quiet --deploy-hook \"cd $MARZBAN_DIR && docker compose restart\"; $start_cmd'"
    else
      echo "0 3 * * * root certbot renew --quiet --deploy-hook \"cd $MARZBAN_DIR && docker compose restart\""
    fi
  } > "$cron_file"
  chmod 644 "$cron_file"
else
  log "Renewal cron already exists at $cron_file — leaving it as-is."
fi

echo
echo "Done. New panel: https://$NEW_DOMAIN:8000"
echo "Old domain/cert (panel.persepolisconstruction.co.uk) was left untouched — existing customers' subscription links keep working."
