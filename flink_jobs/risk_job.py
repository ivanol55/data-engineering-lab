"""Event-time risk windows written to the risk.signals topic.

Submit with:
    flink run -m flink-jobmanager:8081 -d -py /workspace/flink_jobs/risk_job.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/workspace")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyflink.table import EnvironmentSettings, TableEnvironment  # noqa: E402

from flink_jobs import config  # noqa: E402


def build_environment() -> TableEnvironment:
    settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
    table_env = TableEnvironment.create(settings)
    table_env.get_config().set("pipeline.name", config.JOB_NAME)
    table_env.get_config().set("parallelism.default", "2")
    table_env.get_config().set("pipeline.jars",
                               "file:///opt/flink/lib/flink-sql-connector-kafka-5.0.0-2.2.jar")

    if config.STATE_TTL_HOURS > 0:
        table_env.get_config().set(
            "table.exec.state.ttl", f"{config.STATE_TTL_HOURS} h"
        )
    if config.ALLOWED_LATENESS_SECONDS > 0:
        table_env.get_config().set(
            "table.exec.window.allowed-lateness",
            f"{config.ALLOWED_LATENESS_SECONDS} s",
        )
    if config.CHECKPOINTING:
        table_env.get_config().set(
            "execution.checkpointing.interval",
            str(config.CHECKPOINT_INTERVAL_MS),
        )
        table_env.get_config().set(
            "execution.checkpointing.mode", "EXACTLY_ONCE"
        )
        table_env.get_config().set(
            "state.checkpoints.dir", config.CHECKPOINT_DIR
        )
    return table_env


def source_sql() -> str:
    if config.TIME_CHARACTERISTIC == "event":
        schema = f"""
            event_id STRING,
            event_time TIMESTAMP(3),
            user_id STRING,
            outcome STRING,
            source_ip STRING,
            risk_score BIGINT,
            is_attack BOOLEAN,
            WATERMARK FOR event_time AS event_time - INTERVAL '{config.WATERMARK_SECONDS}' SECOND
        """
    else:
        schema = """
            event_id STRING,
            event_time TIMESTAMP(3),
            user_id STRING,
            outcome STRING,
            source_ip STRING,
            risk_score BIGINT,
            is_attack BOOLEAN,
            proc_time AS PROCTIME()
        """
    return f"""
        CREATE TABLE login_events (
            {schema}
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{config.INPUT_TOPIC}',
            'properties.bootstrap.servers' = '{config.BOOTSTRAP}',
            'properties.group.id' = 'risk-signals',
            'scan.startup.mode' = 'earliest-offset',
            'format' = 'json',
            'json.ignore-parse-errors' = 'true',
            'json.timestamp-format.standard' = 'SQL'
        )
    """


def sink_sql() -> str:
    return f"""
        CREATE TABLE risk_signals (
            window_start TIMESTAMP(3),
            window_end TIMESTAMP(3),
            event_count BIGINT,
            failure_count BIGINT,
            distinct_users BIGINT,
            max_risk BIGINT
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{config.OUTPUT_TOPIC}',
            'properties.bootstrap.servers' = '{config.BOOTSTRAP}',
            'format' = 'json',
            'json.timestamp-format.standard' = 'ISO-8601'
        )
    """


def insert_sql() -> str:
    time_column = (
        "event_time"
        if config.TIME_CHARACTERISTIC == "event"
        else "proc_time"
    )
    return f"""
        INSERT INTO risk_signals
        SELECT
            window_start,
            window_end,
            count(*) AS event_count,
            sum(case when outcome <> 'allow' then 1 else 0 end) AS failure_count,
            count(distinct user_id) AS distinct_users,
            max(risk_score) AS max_risk
        FROM TABLE(
            TUMBLE(
                TABLE login_events,
                DESCRIPTOR({time_column}),
                INTERVAL '{config.WINDOW_MINUTES}' MINUTES
            )
        )
        GROUP BY window_start, window_end
    """


def main() -> None:
    table_env = build_environment()
    table_env.execute_sql(source_sql())
    table_env.execute_sql(sink_sql())
    table_env.execute_sql(insert_sql()).wait()


if __name__ == "__main__":
    main()
