SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose --env-file .env
ALL_PROFILES := core tools stream flink orchestration serving observability ml
TOOLS_IMAGE ?= de-lab-tools:local

M ?=
P ?=
Q ?=
ARGS ?=

.PHONY: help env build build-tools build-orchestration build-api build-mlflow up down reset doctor \
	check check-all load load-users load-threat-intel load-events fixtures generator \
	psql query duckdb ps logs seed test-generator

help:
	@echo "Data Engineering Lab"
	@echo
	@echo "  make up P=core              start profiles (comma separated)"
	@echo "  make down                   stop containers, keep volumes"
	@echo "  make reset                  stop and delete volumes + lab state"
	@echo "  make doctor                 check Docker, RAM, ports and health"
	@echo "  make check M=1              run module 1 behavioural checks"
	@echo "  make load                   module 1: load all three sources"
	@echo "  make query Q='SELECT 1'     run SQL in Trino"
	@echo "  make duckdb Q='SELECT 1'    run SQL in DuckDB over Iceberg"
	@echo "  make fixtures               regenerate deterministic fixtures"
	@echo "  make psql                   open the application database"
	@echo
	@echo "Profiles: $(ALL_PROFILES)"

.env:
	@cp .env.example .env
	@echo "Created .env from .env.example (local-only defaults)."

env: .env

build: build-tools build-orchestration build-api build-mlflow

build-tools: .env
	docker build -t $(TOOLS_IMAGE) -f images/tools/Dockerfile images/tools

build-orchestration: build-tools
	docker build -t de-lab-orchestration:local -f images/orchestration/Dockerfile .

build-api: .env
	docker build -t de-lab-api:local -f images/api/Dockerfile images/api

build-mlflow: .env
	docker build -t de-lab-mlflow:local -f images/mlflow/Dockerfile images/mlflow

up: .env
	@test -n "$(P)" || (echo "P is required, e.g. make up P=core"; exit 2)
	@profiles="$(P)"; \
	if [ "$$profiles" = "all" ]; then profiles="$(ALL_PROFILES)"; fi; \
	case ",$$profiles," in \
	  *,orchestration,*|*,ml,*|*,serving,*) \
	    case ",$$profiles," in *,core,*) ;; *) profiles="core,$$profiles" ;; esac ;; \
	esac; \
	for p in $${profiles//,/ }; do \
	  case $$p in \
	    core|tools) $(MAKE) --no-print-directory build-tools ;; \
	    orchestration) $(MAKE) --no-print-directory build-orchestration ;; \
	    serving) $(MAKE) --no-print-directory build-api ;; \
	    ml) $(MAKE) --no-print-directory build-mlflow ;; \
	  esac; \
	done; \
	args=""; \
	for p in $${profiles//,/ }; do args="$$args --profile $$p"; done; \
	echo "Starting: $$profiles"; \
	$(COMPOSE) $$args up -d --wait --wait-timeout 300

down: .env
	$(COMPOSE) $(foreach p,$(ALL_PROFILES),--profile $(p)) down --remove-orphans

reset: .env
	$(COMPOSE) $(foreach p,$(ALL_PROFILES),--profile $(p)) down -v --remove-orphans
	@rm -rf state/*
	@mkdir -p state
	@touch state/.gitkeep
	@echo "Lab volumes and state deleted. The next 'make up' reseeds Postgres."

doctor: .env
	@bash scripts/doctor.sh

check: .env
	@test -n "$(M)" || (echo "M is required, e.g. make check M=1"; exit 2)
	@$(MAKE) --no-print-directory up P=core
	@$(COMPOSE) --profile tools run --rm tools \
		pytest -q checks/module_$(shell printf '%02d' $(M))

check-all: .env
	@set -e; for m in 0 1; do echo "=== module $$m ==="; $(MAKE) --no-print-directory check M=$$m; done

core-up: .env
	@$(MAKE) --no-print-directory up P=core

load: core-up
	@$(COMPOSE) --profile tools run --rm tools \
		python modules/01-batch-ingestion/exercises/run.py all

load-users: core-up
	@$(COMPOSE) --profile tools run --rm tools \
		python modules/01-batch-ingestion/exercises/run.py users

load-threat-intel: core-up
	@$(COMPOSE) --profile tools run --rm tools \
		python modules/01-batch-ingestion/exercises/run.py threat-intel

load-events: core-up
	@$(COMPOSE) --profile tools run --rm tools \
		python modules/01-batch-ingestion/exercises/run.py events

fixtures: .env
	@$(MAKE) --no-print-directory build-tools
	@$(COMPOSE) --profile tools run --rm tools \
		python scripts/make_fixtures.py

generator: .env
	@$(MAKE) --no-print-directory build-tools
	@$(COMPOSE) --profile tools run --rm tools \
		python -m de_lab_generator $(ARGS)

psql: .env
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-app} -d $${POSTGRES_DB:-app}

query: .env
	@test -n "$(Q)" || (echo "Q is required, e.g. make query Q='SELECT 1'"; exit 2)
	$(COMPOSE) exec -T trino trino --catalog iceberg --schema raw --execute "$(Q)"

duckdb: .env
	@test -n "$(Q)" || (echo "Q is required, e.g. make duckdb Q='SELECT 1'"; exit 2)
	@$(COMPOSE) --profile tools run --rm tools \
		python modules/01-batch-ingestion/exercises/duckdb_query.py "$(Q)"

ps: .env
	$(COMPOSE) ps

logs: .env
	$(COMPOSE) logs --tail=100 -f

seed: .env
	@$(COMPOSE) --profile tools run --rm tools python scripts/seed_app_db.py

test-generator: .env
	@$(COMPOSE) --profile tools run --rm tools pytest -q checks/test_generator.py
