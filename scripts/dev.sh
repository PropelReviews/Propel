#!/usr/bin/env bash
# Print dev stack status on attach (devcontainer postAttachCommand).
# Runs inside the dev container, so it reaches sibling services by their
# compose service names over the shared network.
set -uo pipefail

# Docker-outside-of-docker: WSL2 / Docker Desktop often bind-mounts the host
# socket as root:root, so the vscode user (in group docker) cannot connect.
if [ -S /var/run/docker.sock ] && ! docker info &>/dev/null; then
  sudo chgrp docker /var/run/docker.sock 2>/dev/null || true
  sudo chmod 660 /var/run/docker.sock 2>/dev/null || true
fi

echo
echo "Propel dev stack (separate containers, hot reload via bind mounts)"
echo
echo "Services:"

http_check() {
  local name="$1" url="$2"
  if curl -fsS -o /dev/null --max-time 2 "$url"; then
    echo "  ok  $name — $url"
  else
    echo "  --  $name — not reachable yet at $url"
  fi
}

tcp_check() {
  local name="$1" host="$2" port="$3"
  if (exec 3<>"/dev/tcp/$host/$port") 2>/dev/null; then
    exec 3<&- 3>&-
    echo "  ok  $name — $host:$port"
  else
    echo "  --  $name — not reachable yet at $host:$port"
  fi
}

http_check "Backend"  "http://backend:8000/health"
http_check "Frontend" "http://frontend:5173/"
tcp_check  "Postgres" "postgres" "5432"

echo
echo "Host URLs:  backend http://localhost:8000  |  frontend http://localhost:5173"
echo "           (published by docker-compose — do not auto-forward these ports in the devcontainer)"
echo
echo "Backend deps: edit in dev (uv add), then:  docker compose restart backend"
echo
