#!/bin/sh
# Самоподписанный сертификат. Для админки по IP лучше пользоваться HTTP :80.
# Телефонам нужен HTTPS с именем из PUBLIC_BASE_URL.
set -e
DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../nginx/ssl" && pwd)"
mkdir -p "$DIR"
HOST="${1:-ncdc.example.com}"
if [ -f "$DIR/ncdc.crt" ] && [ -f "$DIR/ncdc.key" ]; then
  echo "Certificates already exist in $DIR"
  exit 0
fi
SAN="DNS:${HOST},DNS:localhost,IP:127.0.0.1"
shift || true
for extra in "$@"; do
  case "$extra" in
    *[a-zA-Z]*) SAN="${SAN},DNS:${extra}" ;;
    *) SAN="${SAN},IP:${extra}" ;;
  esac
done
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout "$DIR/ncdc.key" \
  -out "$DIR/ncdc.crt" \
  -subj "/CN=$HOST" \
  -addext "subjectAltName=${SAN}"
chmod 600 "$DIR/ncdc.key"
echo "Wrote $DIR/ncdc.crt and $DIR/ncdc.key for $HOST ($SAN)"
