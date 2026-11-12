#!/usr/bin/env bash
# Kerberos demo setup for the bind-mount layout in compose.yaml.
#   ./setup.sh           keep the existing KDC database, (re)create bob's principal and keytab
#   ./setup.sh --reset   also wipe ./kdc/data and the keytab first (fresh KDC database)
set -euo pipefail

REALM="PROJECT.TEST"
BOB_PRINC="bob/localhost@${REALM}"
HOST_KEYTAB="./bob/keytabs/bob.keytab"
KDC_TMP="/tmp/bob.keytab"
BOB_KT="/etc/bob/bob.keytab"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }
kadm() { docker compose exec -T kdc kadmin.local -q "$1"; }

[ -f compose.yaml ] || [ -f docker-compose.yml ] || fail "Run this from the folder containing compose.yaml"
[ -f .env ] || fail "Missing .env - compose needs KDC_MASTER_PASSWORD=... in it"
grep -q '^KDC_MASTER_PASSWORD=' .env || fail "KDC_MASTER_PASSWORD is not set in .env"

# ------------------------------------------------------------ 1. optional reset
step "1/8 Preparing host files"
docker compose down --remove-orphans
if [ "${1:-}" = "--reset" ]; then
  echo "Resetting: wiping ./kdc/data and the keytab (may ask for sudo, files are root-owned)"
  sudo rm -rf ./kdc/data/* "$HOST_KEYTAB"
fi

# The keytab is a single-file bind mount. If it does not exist when the container
# starts, Docker creates a DIRECTORY with that name and everything breaks.
mkdir -p "$(dirname "$HOST_KEYTAB")"
if [ -d "$HOST_KEYTAB" ]; then
  echo "$HOST_KEYTAB is a directory (Docker created it); removing"
  sudo rm -rf "$HOST_KEYTAB"
fi
[ -e "$HOST_KEYTAB" ] || : > "$HOST_KEYTAB"

# ------------------------------------------------------------ 2. start
step "2/8 Building and starting containers"
docker compose up -d --build

# ------------------------------------------------------------ 3. wait for KDC
step "3/8 Waiting for the KDC"
for i in $(seq 1 60); do
  kadm "listprincs" >/dev/null 2>&1 && { echo "KDC ready after ${i}s"; break; }
  [ "$i" -eq 60 ] && { docker compose logs kdc | tail -30; fail "KDC not ready after 60s"; }
  sleep 1
done

# ------------------------------------------------------------ 4. alice
step "4/8 Checking alice"
kadm "listprincs" | grep -q "^alice@${REALM}" \
  || { kadm "listprincs"; fail "alice@${REALM} missing - your KDC entrypoint should create it"; }
echo "alice found"

# ------------------------------------------------------------ 5. bob principal
step "5/8 Ensuring ${BOB_PRINC} exists"
if kadm "listprincs" | grep -q "^${BOB_PRINC}"; then
  echo "already exists (keeping it, so the key version does not change)"
else
  kadm "addprinc -randkey ${BOB_PRINC}"
fi

# ------------------------------------------------------------ 6. keytab on host
step "6/8 Exporting keytab to ${HOST_KEYTAB}"
docker compose exec -T kdc rm -f "$KDC_TMP"
kadm "ktadd -norandkey -k ${KDC_TMP} ${BOB_PRINC}"
# '>' truncates the existing file in place, so the bind mount keeps pointing at it.
docker compose exec -T kdc cat "$KDC_TMP" > "$HOST_KEYTAB"
chmod 644 "$HOST_KEYTAB" 2>/dev/null || true   # world-readable: uid mapping on /mnt/c is unreliable
[ -s "$HOST_KEYTAB" ] || fail "Exported keytab is empty"

# ------------------------------------------------------------ 7. verify
step "7/8 Verifying bob sees exactly the keytab the KDC exported"
KDC_SUM="$(docker compose exec -T kdc sha256sum "$KDC_TMP" | awk '{print $1}')"
docker compose restart bob >/dev/null
sleep 3
BOB_SUM="$(docker compose exec -T bob sha256sum "$BOB_KT" | awk '{print $1}')"
echo "kdc export : $KDC_SUM"
echo "bob mounted: $BOB_SUM"
[ "$KDC_SUM" = "$BOB_SUM" ] || fail "bob's keytab differs from the exported one (check the bind mount path in compose.yaml)"
echo "keytabs identical: OK"
echo "KDC key version:"; kadm "getprinc ${BOB_PRINC}" | grep -i "key version" || true
docker compose exec -T bob klist -ke "$BOB_KT" 2>/dev/null || echo "(klist not available in bob, checksum match is enough)"

# ------------------------------------------------------------ 8. test
step "8/8 Testing authentication"
docker compose logs --tail 3 bob
echo
echo "Getting a fresh ticket for alice (enter alice's password):"
docker compose exec alice kdestroy -A 2>/dev/null || true
docker compose exec alice kinit alice
docker compose exec alice klist
echo
docker compose exec alice python3 src/client.py
echo
echo "Done. If the client authenticated successfully, everything is set up correctly."
