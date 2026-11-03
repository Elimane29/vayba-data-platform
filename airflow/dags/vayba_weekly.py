"""Vayba · weekly pipeline.

listenbrainz -> musicbrainz -> wikipedia -> dbt_build

Every task runs in the vayba-pipeline image: Airflow only decides WHEN and IN WHAT ORDER
they run, retries them and alerts on failure. Secrets are mounted read-only at run time.
"""
import os

import pendulum
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import DAG, Param
from docker.types import Mount

IMAGE = "vayba-pipeline:1.0.0"

# The week to process: the Monday before the run, or the "week" parameter of a manual run.
WEEK_EXPR = "params.week or data_interval_start.start_of('week').to_date_string()"
WEEK = "{{ " + WEEK_EXPR + " }}"

# dbt dates (part 2): recommend from the previous week's history, evaluate on the processed week.
DBT_VARS = (
    '{"history_start": "{{ macros.ds_add(' + WEEK_EXPR + ', -7) }}", '
    '"week_start": "' + WEEK + '", '
    '"test_end": "{{ macros.ds_add(' + WEEK_EXPR + ', 7) }}"}'
)

ENV = {
    "SNOWFLAKE_ACCOUNT": os.environ["SNOWFLAKE_ACCOUNT"],
    "SNOWFLAKE_USER": os.environ["SNOWFLAKE_USER"],
    "SNOWFLAKE_ROLE": os.environ["SNOWFLAKE_ROLE"],  # personal role: members do not have SYSADMIN
    "SNOWFLAKE_WAREHOUSE": os.environ["SNOWFLAKE_WAREHOUSE"],
    "SNOWFLAKE_PRIVATE_KEY_FILE": "/secrets/snowflake/rsa_key.p8",
    "GCS_BUCKET": os.environ["GCS_BUCKET"],
    "GOOGLE_CLOUD_PROJECT": os.environ["GCP_PROJECT"],
    "GOOGLE_APPLICATION_CREDENTIALS": "/secrets/gcloud/application_default_credentials.json",
    "VAYBA_RUNTIME": "airflow",
    "VAYBA_BATCH_ID": "{{ run_id }}",  # written into _BATCH_ID in bronze: links each row to its run
}

# Keys never enter an image: they are mounted read-only for the duration of the task.
SECRETS = [
    Mount(source=os.environ["VAYBA_KEYS_DIR"], target="/secrets/snowflake", type="bind", read_only=True),
    Mount(source=os.environ["GCLOUD_CONFIG_DIR"], target="/secrets/gcloud", type="bind", read_only=True),
]


def alert_on_failure(context):
    """After the last retry. Here: a loud log line. Real life: a Slack / Teams / e-mail webhook."""
    ti = context["task_instance"]
    print(f"ALERT >>> {ti.dag_id}.{ti.task_id} FAILED (attempt {ti.try_number}). Log: {ti.log_url}")


def pipeline_task(task_id, command, **kwargs):
    return DockerOperator(
        task_id=task_id,
        image=IMAGE,
        command=command,
        environment=ENV,
        mounts=SECRETS,
        mount_tmp_dir=False,
        auto_remove="success",  # keep a failed container for debugging
        **kwargs,
    )


with DAG(
    dag_id="vayba_weekly",
    # Monday 06:00 Paris: the previous week (Monday 00:00 to Monday 00:00 UTC) is complete
    schedule="0 6 * * 1",
    start_date=pendulum.datetime(2026, 10, 26, tz="Europe/Paris"),
    catchup=False,
    max_active_runs=1,  # one week at a time: no two runs write the same tables in parallel
    params={"week": Param("", type="string", description="Monday YYYY-MM-DD to (re)process; empty = previous week")},
    default_args={
        "retries": 2,  # public APIs fail transiently (503, anti-bot page)
        "retry_delay": pendulum.duration(minutes=5),
        "on_failure_callback": alert_on_failure,
    },
    tags=["vayba"],
) as dag:

    listenbrainz = pipeline_task("ingest_listenbrainz", f"python ingestion/run.py --source listenbrainz --week {WEEK}")

    # The first run fetches ~1,000 new artists at 1 request/s (30-45 min); later weeks only new ones
    musicbrainz = pipeline_task(
        "ingest_musicbrainz",
        f"python ingestion/run.py --source musicbrainz --week {WEEK}",
        execution_timeout=pendulum.duration(minutes=90),
    )

    wikipedia = pipeline_task("ingest_wikipedia", f"python ingestion/run.py --source wikipedia --week {WEEK}")

    # Needs the "prod" target in dbt/profiles.yml (part 2), writing to SILVER and GOLD
    dbt_build = pipeline_task(
        "dbt_build",
        "dbt build --project-dir dbt --profiles-dir dbt --target prod --vars '" + DBT_VARS + "'",
    )
    
    listenbrainz >> musicbrainz >> wikipedia >> dbt_build
