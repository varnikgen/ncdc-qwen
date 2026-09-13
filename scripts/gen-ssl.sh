#!/bin/sh
# Generate a self-signed certificate for lab / first boot.
# Replace with a real cert (Let's Encrypt, internal CA) before production.
set -e
DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../nginx/ssl" && pwd)"
mkdir -p "$DIR"
HOST="${1:-ncdc.example.com}"
if [ -f "$DIR/ncdc.crt" ] && [ -f "$DIR/ncdc.key" ]; then
  echo "Certificates already exist in $DIR"
  exit 0
fi
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout "$DIR/ncdc.key" \
  -out "$DIR/ncdc.crt" \
  -subj "/CN=$HOST" \
  -addext "subjectAltName=DNS:$HOST,DNS:localhost,IP:127.0.0.1"
chmod 600 "$DIR/ncdc.key"
echo "Wrote $DIR/ncdc.crt and $DIR/ncdc.key for $HOST"
