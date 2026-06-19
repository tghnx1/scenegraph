#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CERT_DIR=${CERT_DIR:-"$PROJECT_ROOT/nginx/certs"}
CERT_DAYS=${CERT_DAYS:-365}
KEY_FILE=${KEY_FILE:-"$CERT_DIR/privkey.pem"}
CERT_FILE=${CERT_FILE:-"$CERT_DIR/fullchain.pem"}

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/gen_cert.sh
  ./scripts/gen_cert.sh scenegraph.local
  ./scripts/gen_cert.sh 192.168.1.20
  ./scripts/gen_cert.sh scenegraph.local 192.168.1.20 localhost 127.0.0.1

Generates a self-signed certificate for nginx:
  nginx/certs/privkey.pem
  nginx/certs/fullchain.pem

Arguments are certificate names/IPs to include in subjectAltName.
Use the exact hostname or IP address that browsers will use.

Defaults:
  scenegraph localhost 127.0.0.1 ::1

Environment:
  CERT_CN       Common Name. Defaults to the first name/IP argument.
  CERT_DAYS     Certificate lifetime in days. Default: 365.
  CERT_DIR      Output directory. Default: nginx/certs.
  KEY_FILE      Key output path. Default: nginx/certs/privkey.pem.
  CERT_FILE     Certificate output path. Default: nginx/certs/fullchain.pem.

After generating, restart nginx:
  docker compose restart nginx or make upd (or make upd-build maybe)
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

is_ip_address() {
  case "$1" in
    *:*)
      return 0
      ;;
  esac

  printf "%s" "$1" | grep -Eq '^[0-9]+(\.[0-9]+){3}$'
}

if [ "$#" -eq 0 ]; then
  set -- scenegraph localhost 127.0.0.1 ::1
fi

#CN=${CERT_CN:-"$1"}
CN="scenegraph"
SAN=

for name in "$@"; do
  if is_ip_address "$name"; then
    san_entry="IP:$name"
  else
    san_entry="DNS:$name"
  fi

  if [ -z "$SAN" ]; then
    SAN=$san_entry
  else
    SAN="$SAN,$san_entry"
  fi
done

mkdir -p "$CERT_DIR"
umask 077

openssl req -x509 -nodes -days "$CERT_DAYS" -newkey rsa:2048 \
  -keyout "$KEY_FILE" \
  -out "$CERT_FILE" \
  -subj "/CN=$CN" \
  -addext "subjectAltName=$SAN"

echo "Generated self-signed certificate:"
echo "  Key:  $KEY_FILE"
echo "  Cert: $CERT_FILE"
echo "  CN:   $CN"
echo "  SAN:  $SAN"
echo ""
echo "Restart nginx to use it:"
echo "  docker compose restart nginx"
