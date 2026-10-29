# Flink with PyFlink and the Kafka SQL connector.
#
# The official Flink image has no Python. Module 6 uses the Table API from
# Python, so both the JobManager and TaskManager need the same interpreter and
# connector JAR. The connector is downloaded at build time; runtime is offline.
FROM flink:2.3.0

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv curl \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/local/bin/python \
    && python3 -m pip install --break-system-packages --no-cache-dir \
    apache-flink==2.3.0 \
    confluent-kafka==2.16.1 \
    requests==2.34.2 \
    pytest==9.2.0

# Built for Flink 2.2; the 2.x Table API is compatible with 2.3.0 in the lab.
RUN curl -fsSL -o /opt/flink/lib/flink-sql-connector-kafka-5.0.0-2.2.jar \
    https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/5.0.0-2.2/flink-sql-connector-kafka-5.0.0-2.2.jar

RUN mkdir -p /opt/flink/checkpoints && chown -R flink:flink /opt/flink/checkpoints

USER flink
