# Dagster does not publish a maintained 1.13 image, so the lab builds one.
# It starts from the tools image on purpose: module 3 assets call the same dlt,
# dbt and pyiceberg code the learner already uses, with the same pins.
FROM de-lab-tools:local

RUN pip install --no-cache-dir \
    dagster==1.13.27 \
    dagster-webserver==1.13.27 \
    dagster-postgres==0.29.27 \
    sqlalchemy==2.0.55

ENV DAGSTER_HOME=/opt/dagster/home \
    PYTHONPATH=/workspace:/workspace/generator:/opt/dagster/home

RUN mkdir -p /opt/dagster/home/compute_logs /workspace
COPY orchestration/dagster.yaml orchestration/workspace.yaml /opt/dagster/home/

WORKDIR /workspace
CMD ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000", "-w", "/opt/dagster/home/workspace.yaml"]
