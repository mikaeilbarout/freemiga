# Freemiga

A VPN plan sales site with full account management: a customer signs up, picks
a plan, sends USDT (Tron or Polygon network), the system automatically
verifies the payment, and once confirmed provisions a dedicated Marzban user
for that specific order.

## Features

- **Customer signup/login** — the site username is separate from VPN
  usernames: each order gets its own Marzban username
  (`{username}_{order_id}`), because every plan a customer buys needs to be
  fully independent of their other plans, not merged together
- **Customer dashboard**: full order history; every purchased plan (new or
  repeat) has its own independent Marzban account and is shown separately in
  the dashboard, with its own live status (active/inactive/expired)
- **Account suspension**: an admin can suspend an account with a specific
  reason — VPN access (via Marzban) is cut off, and the customer immediately
  sees the reason message in their dashboard
- **Support**: customers open tickets from their dashboard, admins reply from
  the admin panel
- **Admin panel** (`/admin`): manage customers (suspend/unsuspend), view all
  orders + manually confirm payment (for when the payment-detection bot
  misses a transaction), and reply to support tickets

## How payment detection works

At checkout, the customer picks between **card** and **crypto**:

- **Card** via Stripe — a hosted checkout page, confirmed automatically via
  webhook.
- **Crypto (USDT)** — self-hosted, not a third-party gateway. The customer
  picks one of two networks: **Tron (TRC20)** or **Polygon** — since fees on
  these two networks vary a lot depending on the wallet/app the customer
  uses, offering both lets them pick the cheaper one. Each crypto order gets
  its own exact amount — the plan price plus a small unique offset (e.g.
  5.037 USDT for a $5 plan). The customer sends exactly that amount to our
  wallet address on that network, then pastes their transaction hash on the
  payment page. The server automatically checks the transaction on-chain
  (via TronGrid for Tron, or the Etherscan API for Polygon) — confirming the
  destination is our address, the amount is exactly this order's amount,
  it succeeded, and it was made after the order was created — and if
  everything checks out, automatically confirms the order and provisions
  the VPN account. The unique amount is what ties a payment to one order:
  our wallet address is public, so without it anyone could submit the hash
  of someone else's payment. A transaction hash can also never be used
  twice.

  Why this instead of a third-party gateway (like NowPayments)? Because
  gateways impose a minimum of roughly $11-15 for USDT on any network (even
  the cheapest), which doesn't work at all for cheap plans (e.g. $5). With
  this self-hosted approach there's no minimum, since the customer only pays
  the real network fee (a few cents), not an added service fee.

  **Security note:** we only store the wallets' **public addresses**, never
  their private keys — since we're only checking incoming transactions, not
  spending. Private keys should stay somewhere safe (a personal, offline
  wallet).

### Setting up crypto payments

Both networks are optional — if you only configure one, only that one is
shown to customers. To disable crypto entirely, configure neither.

**Tron (TRC20):**
1. In `.env`, set `TRON_USDT_WALLET_ADDRESS` to your USDT-TRC20 wallet's
   public address (address only, never the private key)
2. Create a free account at [trongrid.io](https://www.trongrid.io) and get an
   API key, put it in `TRONGRID_API_KEY`

**Polygon:**
1. In `.env`, set `POLYGON_USDT_WALLET_ADDRESS` to your USDT-Polygon wallet's
   public address (address only, never the private key)
2. Create a free account at [etherscan.io](https://etherscan.io) and get an
   API key (the same key works for Polygon since Etherscan's API is
   unified), put it in `POLYGONSCAN_API_KEY`

Restart the service after configuring either one.

## Server (VPS) install — with Docker

Full stack: **FastAPI (Gunicorn+Uvicorn) + PostgreSQL + Nginx + Certbot**, all
in Docker Compose.

### Prerequisites
- Docker + Docker Compose installed on the server
- A domain/subdomain (e.g. `freemiga.com`) with an A record pointing at the
  server's IP
- Ports 80 and 443 open on the server

### 1. Clone the project and set up `.env`

Code is kept on GitHub: [github.com/mikaeilbarout/freemiga](https://github.com/mikaeilbarout/freemiga)
(private repo). On the server, instead of manually uploading files, clone
directly:

```bash
git clone git@github.com:mikaeilbarout/freemiga.git /opt/freemiga
cd /opt/freemiga
```

Since the repo is private, the server needs a **Deploy Key** (a read-only SSH
key scoped to this repo — not a personal password or access token):
```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N "" -C "your-server-deploy"
cat ~/.ssh/github_deploy.pub   # add this under GitHub → Settings → Deploy keys → Add deploy key (Read-only)
```
Then add this to `~/.ssh/config` so git uses this key automatically:
```
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/github_deploy
  IdentitiesOnly yes
```

Then create `.env`:
```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # -> SESSION_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # -> POSTGRES_PASSWORD
nano .env
```
Also replace `server_name` in `nginx/conf.d/freemiga.conf` with your actual
domain (if it isn't `freemiga.com`).

**Important:** `docker-compose.override.yml` is for local development only
(exposes the app directly, without nginx/TLS, on port 8002) — make sure to
remove it before running on a production server, otherwise anyone can
connect directly to the app and spoof the `X-Forwarded-For`/`X-Real-IP`
headers.

**If the server already runs a different nginx** (e.g. another site owned by
the same server operator sitting on port 80/443 — exactly this server's
current situation, where `shop.persepolisconstruction.co.uk` is hosted
alongside `persepolisconstruction.co.uk` itself and the Marzban panel): don't
run the steps above (this project's own nginx/certbot). Instead, use the
ready-made overlay `docker-compose.shared-nginx.yml` (read its comments —
the `freemiga_app` alias defined in it must exactly match the existing
nginx's `proxy_pass`):
1. Once: `docker network create web_shared` (if it doesn't already exist)
2. `docker compose -f docker-compose.yml -f docker-compose.shared-nginx.yml up -d db app`
   — this replaces the "bring up the app and database" step below; don't
   bring up this project's own nginx/certbot
3. Connect the existing nginx to the same network too (once):
   `docker network connect web_shared <nginx-container>`
4. Copy a new config file (like this project's own
   `nginx/conf.d/freemiga.conf`) into that existing nginx's conf.d folder,
   with `proxy_pass http://freemiga_app:8001`
5. Use the existing certbot for the SSL certificate:
   `docker compose run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot -d shop.persepolisconstruction.co.uk`
6. Since another service (e.g. Xray/Marzban) usually already owns the real
   port 443, route the domain through Cloudflare and use an Origin Rule to
   redirect port 443 traffic to whatever port the existing nginx actually
   listens on (e.g. 8444).

**Important note:** since the network alias is only defined when using both
compose files together (`-f docker-compose.yml -f
docker-compose.shared-nginx.yml`), every subsequent update (`docker compose
build/up -d app`) must also be run with both `-f` flags — otherwise
recreating the container loses its connection to `web_shared` and the site
goes offline until you manually reconnect it.

### 2. Bring up the app and database (without nginx yet)
```bash
docker compose up -d db app
docker compose logs -f app   # you should see "Database schema ready." followed by gunicorn workers
```

### 3. Get a real HTTPS certificate (first time only)
```bash
CERTBOT_EMAIL=you@example.com ./scripts/init-letsencrypt.sh
```
This script creates a temporary certificate so nginx can start, then fetches
the real certificate from Let's Encrypt and reloads nginx. Only needed once.

### 4. Full run
```bash
docker compose up -d
docker compose ps
```
`https://freemiga.com` should now be up. The `certbot` service checks every
12 hours and renews the certificate before it expires — no manual work
needed.

### Updating after a code change
```bash
./deploy.sh
```
This script runs `git pull` and automatically detects whether the server is
using the "shared nginx" scenario (by checking whether the `web_shared`
network exists), and applies the right `-f` flags accordingly — no need to
remember it manually. If docker access needs sudo: `sudo ./deploy.sh`.

**Why this matters:** in the "shared nginx" scenario, if `docker compose up
-d app` is run without `-f docker-compose.yml -f
docker-compose.shared-nginx.yml`, the container gets recreated and loses the
`freemiga_app` alias on the `web_shared` network — the site goes offline
until you manually reconnect it with `docker network connect --alias
freemiga_app web_shared <container>`. `deploy.sh` exists specifically to
prevent this mistake.

### Viewing logs
```bash
docker compose logs -f app
```

## Site pages

| Path | What it is |
|---|---|
| `/` | Customer login |
| `/signup` | Customer signup |
| `/dashboard` | Customer dashboard (buy/renew, history, support) |
| `/pay/{order_id}` | Payment page for a specific order |
| `/admin` | Admin panel (username/password from `.env`) |

## Editing plans

```bash
sqlite3 /opt/freemiga/freemiga.db
UPDATE plans SET price_usdt=7 WHERE name='Basic';
```

## Setting up the Telegram bot (optional but recommended)

So customers automatically get messages (service delivery, suspension
notice, password reset code):

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Run `/newbot`, pick a name and username (must end in `bot`) — our bot is
   `@FreemigaBot`
3. BotFather gives you a **token** (something like `123456:ABC-DEF...`), put
   it in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
   TELEGRAM_BOT_USERNAME=FreemigaBot
   ```
4. Restart the service — from now on, a "Connect to Telegram bot" button
   appears in the customer dashboard

### Getting your own notifications (new orders/tickets)

If you want to be notified on Telegram about new orders and tickets
yourself:
1. Send any message (even `/start`) to your bot (`@FreemigaBot`) on Telegram
2. Open this URL in your browser (replace `<TOKEN>` with the bot's actual
   token):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. In the JSON output, look for `"chat":{"id":123456789` — put that number in
   `.env`:
   ```
   ADMIN_TELEGRAM_CHAT_ID=123456789
   ```
4. Restart the service

If you leave these two variables empty, the site works completely normally —
only Telegram notifications and password recovery via this route are
disabled (a locked-out customer can still get help via the "contact support"
form on the login page).

## Automatic backups

`backup.sh` backs up everything needed to rebuild the server into one file,
`backups/backup_<timestamp>.tar.gz`:

- this site's database, uploaded files, and `.env`
- Marzban (`/var/lib/marzban` + `/opt/marzban` — users, Xray config,
  REALITY keys), with a consistent snapshot of its live SQLite database
- marzban-guard's database

Marzban/marzban-guard are skipped with a warning if their containers aren't
running. Backups older than 14 days are deleted. It must run as root (it
reads `/var/lib/marzban`). Test it once:
```bash
sudo ./backup.sh
```
Then run it every night at 3am from root's crontab (use your real path to
the repo):
```bash
(sudo crontab -l 2>/dev/null; echo "0 3 * * * $PWD/backup.sh >> /var/log/freemiga-backup.log 2>&1") | sudo crontab -
```
Optional overrides (environment variables): `BACKUP_DIR`, `KEEP_DAYS`,
`MARZBAN_CONTAINER` (default `marzban-marzban-1`), `GUARD_DB_CONTAINER`
(default `marzban-guard-postgres-1`).

**Copy backups off the server regularly** — a backup that only lives on the
server is lost with it. From your own computer:
```bash
scp user@SERVER_IP:/path/to/freemiga/backups/backup_<timestamp>.tar.gz .
```
Each file contains every password and key (`.env`, Marzban's keys) — keep
it private.

To restore, unpack it (`tar xzf backup_<timestamp>.tar.gz`), then:
```bash
# Site database
gunzip -c <timestamp>/db.sql.gz | docker compose exec -T db psql -U freemiga freemiga
# Marzban (then restart it)
sudo tar xzf <timestamp>/marzban.tar.gz -C /
```

## Site language (Persian/English)

The site is fully bilingual (Persian/English, with automatic RTL for
Persian). Each new visitor's default language is determined like this:

1. If they already have a language cookie (from a previous manual switch),
   that's shown
2. Otherwise, their IP is checked against an offline GeoIP database — if
   their country is in `PERSIAN_COUNTRIES` (default: Iran and Afghanistan),
   Persian is shown
3. Otherwise English (`DEFAULT_LANGUAGE`)

Customers can always switch manually from the language button in the site's
top bar — after that, GeoIP is no longer used and their choice is stored in
a cookie. The admin panel (`/admin`) is always in English, regardless of the
visitor's language.

### Setting up GeoIP (optional, but recommended)

Without this file, the site works completely normally — new visitors just
always see English (instead of automatic detection based on their country).

1. Create a free account at [maxmind.com/en/geolite2/signup](https://www.maxmind.com/en/geolite2/signup)
2. Get a **License Key** from your account panel
3. Download the `GeoLite2-Country.mmdb` database (the "GeoIP2 Binary (.mmdb)"
   format)
4. Place the file at `app/data/GeoLite2-Country.mmdb` in the project
5. Run `docker compose build app && docker compose up -d app`

### Related variables in `.env`

```
GEOIP_DB_PATH=app/data/GeoLite2-Country.mmdb
DEFAULT_LANGUAGE=en
PERSIAN_COUNTRIES=IR,AF
```

## Production hardening

- **Guaranteed single-process**: payment checking and Telegram polling use a
  file lock, so even if you accidentally bring up multiple workers, only one
  actually runs
- **Secure cookies**: `SESSION_COOKIE_SECURE=true` in production only sends
  the login cookie over HTTPS
- **Duplicate-transaction prevention**: a blockchain transaction is never
  accepted twice for two different orders (both a software check and a
  unique database constraint)
- **Login rate limiting**: login/signup/password-recovery are limited to a
  few attempts per minute (prevents password guessing)
- **Automatic recovery**: if a Marzban username for an order (which includes
  the order id, so collisions are effectively impossible) already exists,
  it's renewed instead of erroring out
- **Admin action log**: every ban/unban/manual confirmation/ticket reply is
  logged in the admin panel's "Action Log" tab
- **Crypto payments are tied to one order**: each crypto order gets its own
  exact amount (e.g. 5.037 USDT instead of 5), and a transaction is only
  accepted if it pays exactly that amount and was made after the order was
  created — so nobody can claim someone else's payment to the public wallet.
  A payment for a different amount is rejected; confirm it by hand from the
  admin panel after checking it.
- **Late payments aren't lost**: a card/crypto/Stars payment that arrives
  after its order expired or was cancelled is still credited (you get a
  Telegram notice). A payment from a suspended or deleted account is held
  as "paid" without provisioning, for you to refund or confirm manually.
- **Database migrations run automatically** on every container start
  (`scripts/init_db.py`) — no manual step after `./deploy.sh`.
- **Cloudflare**: if the domain goes through Cloudflare's proxy and the
  server accepts traffic only from Cloudflare, set `TRUST_CLOUDFLARE_IP=true`
  in `.env` so rate limits and Persian auto-detection see visitors' real IPs.
- **`SESSION_SECRET` is required**: with `SESSION_COOKIE_SECURE=true` the app
  refuses to start without a real random value.

## Important security notes

- The `.env` file contains the Marzban admin password and this site's admin
  panel password — run `chmod 600 .env` and never share it anywhere
- After any change to `.env`: `sudo systemctl restart freemiga`
- Service logs: `journalctl -u freemiga -f`
- If you suspend/unsuspend a customer who doesn't have a Marzban account yet
  (hasn't made their first purchase), only this site's database is updated;
  as soon as they pay for the first time and their account is created, the
  suspension status is also applied in Marzban.
