#!/usr/bin/env bash
# Creates the separate databases used by Lakekeeper, Dagster and MLflow.
# Runs once, on an empty Postgres data volume, from the official image init.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<-SQL
CREATE ROLE ${LAKEKEEPER_DB_USER:-lakekeeper} LOGIN PASSWORD '${LAKEKEEPER_DB_PASSWORD:-lakekeeper}';
CREATE DATABASE ${LAKEKEEPER_DB:-lakekeeper} OWNER ${LAKEKEEPER_DB_USER:-lakekeeper};

CREATE ROLE ${DAGSTER_DB_USER:-dagster} LOGIN PASSWORD '${DAGSTER_DB_PASSWORD:-dagster}';
CREATE DATABASE ${DAGSTER_DB:-dagster} OWNER ${DAGSTER_DB_USER:-dagster};

CREATE ROLE ${MLFLOW_DB_USER:-mlflow} LOGIN PASSWORD '${MLFLOW_DB_PASSWORD:-mlflow}';
CREATE DATABASE ${MLFLOW_DB:-mlflow} OWNER ${MLFLOW_DB_USER:-mlflow};
SQL
