FROM python:3.12.16-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir \
    mlflow==3.17.2 \
    boto3==1.43.117 \
    botocore==1.43.117 \
    psycopg[binary]==3.3.6 \
    pyiceberg==0.12.0 \
    pyarrow==25.0.0 \
    pandas==3.1.0 \
    scikit-learn==1.9.1 \
    requests==2.34.2 \
    pytest==9.2.0

EXPOSE 5000
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000"]
