FROM python:3.12.16-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Pre-install DuckDB extensions so the lab works offline. Extensions are
# downloaded at image build time and stored outside the bind-mounted HOME.
RUN python - <<'PY'
import duckdb
con = duckdb.connect(config={"extension_directory": "/opt/duckdb-extensions"})
con.execute("INSTALL iceberg")
con.execute("INSTALL httpfs")
con.execute("INSTALL avro")
con.close()
PY
RUN chmod -R a+rX /opt/duckdb-extensions

WORKDIR /workspace

# The compose service runs as the host UID. Nothing in the image needs a
# writable home; HOME points at the mounted state directory.
CMD ["python", "--version"]
