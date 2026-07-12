#!/bin/sh
set -eu

API_BASE_URL="${VITE_API_BASE_URL:-${AGENT_OS_PUBLIC_API_BASE_URL:-http://127.0.0.1:18010}}"

mkdir -p /app/dist

cat > /app/dist/runtime-config.json <<EOF
{
  "apiBaseUrl": "${API_BASE_URL}"
}
EOF

exec "$@"
