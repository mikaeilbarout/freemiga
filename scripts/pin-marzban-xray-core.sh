#!/usr/bin/env bash
# One-time (idempotent) fix: pin Marzban's Xray-core to a newer release than
# the one baked into the gozargah/marzban:latest image, via a host bind mount
# — so it survives `docker compose pull` / image rebuilds instead of getting
# silently reverted, which is what happens if you just `docker cp` a new
# binary into the running container's writable layer.
#
# Why this was needed: the panel image (as of writing) ships Xray 24.12.31.
# Modern clients (e.g. current v2rayNG builds) bundle a much newer Xray-core,
# and a large version gap breaks VLESS+REALITY's handshake — the client logs
# "REALITY: received real certificate (potential MITM or redirection)" and
# the server never even logs the attempt (REALITY silently proxies
# unauthenticated-looking connections to `dest` by design, so it looks like
# nothing happened server-side). Plain VLESS+WS+TLS is unaffected by this,
# which is why only REALITY looked broken.
#
# Also required: Marzban's own config parser tries to auto-derive each
# REALITY inbound's public key by shelling out to `xray x25519 -i
# <privateKey>` and scraping its stdout. Newer Xray-core builds changed that
# command's output slightly, which crashes Marzban on startup (KeyError /
# TypeError in app/xray/config.py, crash-looping the whole panel — not just
# REALITY, everything, since it's the same container). The fix is to make
# every REALITY inbound's realitySettings carry an explicit "publicKey"
# field alongside "privateKey", so Marzban never needs to shell out at all.
# This script does NOT edit xray_config.json for you (that's Marzban's own
# state, normally only touched via its panel UI) — it just prints a
# reminder if it finds a REALITY inbound missing "publicKey".
#
# Run this ON THE SERVER, as root.
set -euo pipefail

XRAY_VERSION="${XRAY_VERSION:-v26.7.28}"
MARZBAN_DIR="${MARZBAN_DIR:-}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
warn() { printf '\n\033[1;33m!!! %s\033[0m\n' "$1"; }
die() { printf '\n\033[1;31mXXX %s\033[0m\n' "$1" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "Run as root (writes under /opt, restarts the Marzban container)."

# --- 1. Locate the Marzban install (same detection logic as switch-marzban-domain.sh) ---
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

mz_container="$(docker ps --format '{{.Names}}' -f "label=com.docker.compose.project.working_dir=$MARZBAN_DIR" | grep -vi marzban-node | grep -vi marzban-guard | head -1 || true)"
[ -n "$mz_container" ] || mz_container="marzban-marzban-1"

# --- 2. Warn if any REALITY inbound is missing the explicit publicKey Marzban needs ---
if docker exec "$mz_container" test -f /var/lib/marzban/xray_config.json 2>/dev/null; then
  missing_pbk="$(docker exec "$mz_container" python3 -c '
import json
try:
    cfg = json.load(open("/var/lib/marzban/xray_config.json"))
except Exception:
    raise SystemExit(0)
bad = 0
for inbound in cfg.get("inbounds", []):
    rs = (inbound.get("streamSettings") or {}).get("realitySettings")
    if rs and "privateKey" in rs and "publicKey" not in rs:
        bad += 1
print(bad)
' 2>/dev/null || echo 0)"
  if [ "${missing_pbk:-0}" != "0" ]; then
    warn "Found $missing_pbk REALITY inbound(s) in xray_config.json without an explicit \"publicKey\" field. Add one (Marzban panel -> Core Settings -> next to that inbound's \"privateKey\", derive it with: docker exec $mz_container xray x25519 -i <privateKey>) BEFORE proceeding, or the version bump below will crash-loop the panel."
    read -rp "Continue anyway? [y/N] " ans
    [ "${ans:-}" = "y" ] || exit 1
  fi
fi

# --- 3. Download the pinned Xray-core release to a permanent host path ---
BIN_DIR="$MARZBAN_DIR/xray-bin"
mkdir -p "$BIN_DIR"
log "Downloading Xray-core $XRAY_VERSION"
tmp_zip="$(mktemp)"
curl -fsSL "https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-64.zip" -o "$tmp_zip" \
  || die "Download failed — check XRAY_VERSION=$XRAY_VERSION is a real release tag."
tmp_dir="$(mktemp -d)"
unzip -oq "$tmp_zip" -d "$tmp_dir"
install -m 755 "$tmp_dir/xray" "$BIN_DIR/xray"
rm -rf "$tmp_zip" "$tmp_dir"
log "Installed to $BIN_DIR/xray"

# --- 4. Make sure docker-compose.yml bind-mounts it over the image's own binary ---
compose_file="$MARZBAN_DIR/docker-compose.yml"
mount_line="      - $BIN_DIR/xray:/usr/local/bin/xray:ro"
if grep -qF "$BIN_DIR/xray:/usr/local/bin/xray" "$compose_file"; then
  log "docker-compose.yml already mounts $BIN_DIR/xray — leaving it as-is."
else
  log "Adding bind mount to $compose_file"
  cp "$compose_file" "$compose_file.bak.$(date +%s)"
  # Insert right after the existing /var/lib/marzban volume line.
  if grep -q '/var/lib/marzban:/var/lib/marzban' "$compose_file"; then
    sed -i "\#/var/lib/marzban:/var/lib/marzban#a\\$mount_line" "$compose_file"
  else
    die "Couldn't find the expected /var/lib/marzban volume line in $compose_file to anchor the insert. Add this line under the service's 'volumes:' by hand: $mount_line"
  fi
fi

# --- 5. Recreate the container so it picks up the bind mount, and verify ---
log "Recreating the Marzban container"
(cd "$MARZBAN_DIR" && docker compose up -d --force-recreate)

sleep 5
if ! docker ps --format '{{.Names}} {{.Status}}' | grep -q "$mz_container.*Up"; then
  die "$mz_container isn't up after recreate — check: docker logs $mz_container --tail 100. Your compose backup is at $compose_file.bak.*"
fi

installed_version="$(docker exec "$mz_container" xray version | head -1)"
echo
echo "Done. $installed_version"
echo "This binary is now bind-mounted from $BIN_DIR/xray, so it survives 'docker compose pull' and image rebuilds."
echo "To bump the pinned version later: XRAY_VERSION=vX.Y.Z $0"
