#!/usr/bin/env bash
# One-time bootstrap for the first real Let's Encrypt certificate.
# Run this ONCE on the VPS, after `docker compose up -d db app` but before
# relying on HTTPS. Safe to re-run — it skips itself if a real cert already
# exists, so it won't burn Let's Encrypt's rate limit by accident.
#
# Why this exists: nginx's HTTPS server block refuses to start without a
# certificate file on disk, but Certbot needs nginx already serving port 80
# to complete the HTTP-01 challenge and issue that certificate. This script
# breaks the chicken-and-egg by placing a throwaway self-signed cert first,
# starting nginx, then swapping in the real one and reloading.
set -euo pipefail

DOMAINS=(freemiga.com www.freemiga.com)
EMAIL="${CERTBOT_EMAIL:-}"   # set CERTBOT_EMAIL=you@example.com before running
RSA_KEY_SIZE=4096
PRIMARY_DOMAIN="${DOMAINS[0]}"

if [ -z "$EMAIL" ]; then
  echo "Set CERTBOT_EMAIL=you@example.com before running this script (Let's Encrypt uses it for renewal/expiry notices)."
  exit 1
fi

if docker compose run --rm certbot certificates 2>/dev/null | grep -q "$PRIMARY_DOMAIN"; then
  echo "A certificate for $PRIMARY_DOMAIN already exists — nothing to do. Delete it via 'docker compose run --rm certbot delete' first if you really want to re-issue."
  exit 0
fi

domain_args=()
for d in "${DOMAINS[@]}"; do domain_args+=("-d" "$d"); done

echo "### Creating a temporary self-signed certificate so nginx can start ###"
docker compose run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:$RSA_KEY_SIZE -days 1 \
    -keyout '/etc/letsencrypt/live/$PRIMARY_DOMAIN/privkey.pem' \
    -out '/etc/letsencrypt/live/$PRIMARY_DOMAIN/fullchain.pem' \
    -subj '/CN=localhost'" certbot

echo "### Starting nginx ###"
docker compose up -d nginx

echo "### Deleting the temporary certificate ###"
docker compose run --rm --entrypoint "\
  rm -rf /etc/letsencrypt/live/$PRIMARY_DOMAIN \
         /etc/letsencrypt/archive/$PRIMARY_DOMAIN \
         /etc/letsencrypt/renewal/$PRIMARY_DOMAIN.conf" certbot

echo "### Requesting the real Let's Encrypt certificate ###"
docker compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    --email $EMAIL \
    ${domain_args[*]} \
    --rsa-key-size $RSA_KEY_SIZE \
    --agree-tos \
    --non-interactive" certbot

echo "### Reloading nginx with the real certificate ###"
docker compose exec nginx nginx -s reload

echo "Done. $PRIMARY_DOMAIN is now serving a real certificate. The 'certbot' service will keep it renewed automatically."
