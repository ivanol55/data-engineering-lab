#!/usr/bin/env bash
# Host-side sanity check for the lab. Loud, fast, and dependency-light.
set -uo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

FAILURES=0
WARNINGS=0

pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
warn() { printf '  \033[33mwarn\033[0m %s\n' "$1"; WARNINGS=$((WARNINGS + 1)); }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

section() { printf '\n%s\n' "$1"; }

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-de-lab}"
LAB_MIN_FREE_GB="${LAB_MIN_FREE_GB:-4}"

section "Host"
if command -v docker >/dev/null 2>&1; then
  pass "docker: $(docker --version)"
else
  fail "docker is not installed"
fi

if docker info >/dev/null 2>&1; then
  pass "docker daemon is reachable"
else
  fail "docker daemon is not reachable (is it running? are you in the docker group?)"
fi

if docker compose version >/dev/null 2>&1; then
  pass "compose: $(docker compose version --short 2>/dev/null || docker compose version)"
else
  fail "docker compose plugin is not available"
fi

if [[ -f .env ]]; then
  pass ".env exists"
else
  fail ".env is missing; run: cp .env.example .env"
fi

section "Memory"
if command -v free >/dev/null 2>&1; then
  AVAILABLE_GB=$(free -g | awk '/^Mem:/ {print $7}')
  if [[ -z "${AVAILABLE_GB:-}" ]]; then
    AVAILABLE_GB=$(free -m | awk '/^Mem:/ {printf "%d", $7/1024}')
  fi
  if (( AVAILABLE_GB >= LAB_MIN_FREE_GB )); then
    pass "${AVAILABLE_GB} GiB available (need ${LAB_MIN_FREE_GB} GiB)"
  else
    fail "only ${AVAILABLE_GB} GiB available; stop other stacks or lower LAB_MIN_FREE_GB"
  fi
else
  warn "free(1) not found; cannot check RAM"
fi

section "Ports"
port_belongs_to_lab() {
  local port="$1"
  docker ps \
    --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" \
    --format '{{.Ports}}' 2>/dev/null | grep -qE ":${port}->"
}

port_is_listening() {
  (exec 3<>"/dev/tcp/127.0.0.1/${1}") >/dev/null 2>&1
}

check_port() {
  local name="$1" port="$2" required="$3"
  if [[ -z "$port" ]]; then
    return
  fi
  if ! port_is_listening "$port"; then
    pass "$name :$port is free"
  elif port_belongs_to_lab "$port"; then
    pass "$name :$port is used by this lab"
  elif [[ "$required" == "yes" ]]; then
    fail "$name :$port is already in use by another process"
  else
    warn "$name :$port is already in use (change it in .env before using that profile)"
  fi
}

check_port "postgres" "${POSTGRES_PORT:-5432}" yes
check_port "seaweedfs-s3" "${SEAWEEDFS_S3_PORT:-8333}" yes
check_port "seaweedfs-master" "${SEAWEEDFS_MASTER_PORT:-9333}" yes
check_port "lakekeeper" "${LAKEKEEPER_PORT:-8181}" yes
check_port "trino" "${TRINO_PORT:-8085}" yes
check_port "kafka" "${KAFKA_HOST_PORT:-29092}" no
check_port "kafka-connect" "${KAFKA_CONNECT_PORT:-8083}" no
check_port "apicurio" "${APICURIO_PORT:-8086}" no
check_port "flink" "${FLINK_PORT:-8082}" no
check_port "dagster" "${DAGSTER_PORT:-3002}" no
check_port "valkey" "${VALKEY_PORT:-6379}" no
check_port "api" "${API_PORT:-8001}" no
check_port "grafana" "${GRAFANA_PORT:-3001}" no
check_port "prometheus" "${PROMETHEUS_PORT:-9090}" no
check_port "mlflow" "${MLFLOW_PORT:-5001}" no

section "Images and fixtures"
if docker image inspect de-lab-tools:local >/dev/null 2>&1; then
  pass "de-lab-tools:local exists"
else
  fail "de-lab-tools:local is missing; run: make build-tools"
fi

EVENT_FILES=$(find fixtures/events -name '*.jsonl' 2>/dev/null | wc -l)
if [[ "$EVENT_FILES" -eq 7 ]]; then
  pass "7 daily event fixtures"
elif [[ "$EVENT_FILES" -eq 0 ]]; then
  fail "no event fixtures; run: make fixtures"
else
  warn "found ${EVENT_FILES} event fixture files (expected 7)"
fi

section "Core services"
if docker ps --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" --format '{{.Label "com.docker.compose.service"}}' 2>/dev/null | grep -qx postgres; then
  if docker compose --env-file .env exec -T postgres pg_isready -U "${POSTGRES_USER:-app}" -d "${POSTGRES_DB:-app}" >/dev/null 2>&1; then
    USERS=$(docker compose --env-file .env exec -T postgres \
      psql -U "${POSTGRES_USER:-app}" -d "${POSTGRES_DB:-app}" -tAc 'SELECT count(*) FROM users' 2>/dev/null | tr -d '[:space:]')
    if [[ "$USERS" == "2000" ]]; then
      pass "postgres: 2000 seeded users"
    else
      warn "postgres is up but users=${USERS:-unknown}; run make reset if the seed is incomplete"
    fi
  else
    fail "postgres is running but not accepting connections"
  fi
else
  warn "core profile is not running (expected before make up P=core)"
fi

if docker ps --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" --format '{{.Label "com.docker.compose.service"}}' 2>/dev/null | grep -qx trino; then
  if curl -fsS "http://127.0.0.1:${TRINO_PORT:-8085}/v1/info" >/dev/null 2>&1; then
    pass "trino responds on :${TRINO_PORT:-8085}"
  else
    fail "trino is running but /v1/info does not respond"
  fi
  if curl -fsS "http://127.0.0.1:${LAKEKEEPER_PORT:-8181}/health" >/dev/null 2>&1; then
    pass "lakekeeper responds on :${LAKEKEEPER_PORT:-8181}"
  else
    fail "lakekeeper is running but /health does not respond"
  fi
fi

section "Optional profiles"
running_service() {
  docker ps --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" \
    --format '{{.Label "com.docker.compose.service"}}' 2>/dev/null | grep -qx "$1"
}

check_http() {
  local service="$1" name="$2" url="$3"
  if running_service "$service"; then
    if curl -fsS "$url" >/dev/null 2>&1; then
      pass "$name responds"
    else
      fail "$name is running but does not respond at $url"
    fi
  fi
}

check_http kafka-connect "kafka-connect" "http://127.0.0.1:${KAFKA_CONNECT_PORT:-8083}/connectors"
check_http apicurio "apicurio" "http://127.0.0.1:${APICURIO_PORT:-8086}/apis/registry/v3/system/info"
check_http kafbat "kafbat" "http://127.0.0.1:${KAFBAT_PORT:-8081}/"
check_http flink-jobmanager "flink" "http://127.0.0.1:${FLINK_PORT:-8082}/overview"
check_http dagster-webserver "dagster" "http://127.0.0.1:${DAGSTER_PORT:-3002}/server_info"
check_http api "decision api" "http://127.0.0.1:${API_PORT:-8001}/health"
check_http prometheus "prometheus" "http://127.0.0.1:${PROMETHEUS_PORT:-9090}/-/healthy"
check_http grafana "grafana" "http://127.0.0.1:${GRAFANA_PORT:-3001}/api/health"
check_http mlflow "mlflow" "http://127.0.0.1:${MLFLOW_PORT:-5001}/health"

printf '\n'
if (( FAILURES > 0 )); then
  printf '\033[31m%d check(s) failed\033[0m' "$FAILURES"
  (( WARNINGS > 0 )) && printf ', %d warning(s)' "$WARNINGS"
  printf '\n'
  exit 1
fi
printf '\033[32mall checks passed\033[0m'
(( WARNINGS > 0 )) && printf ' (%d warning(s))' "$WARNINGS"
printf '\n'
