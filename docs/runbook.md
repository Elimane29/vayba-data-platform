# Vayba runbook (part 3, owner Elimane)

How to run the pipeline, prove it is reliable, and shut it down. Every command is meant to be copied as is.
Sections marked **TO RUN** still need a real run on the shared Snowflake account; fill in the result and the date.

## 1. Architecture in one line

Public APIs → `ingestion/run.py` (container) → GCS bucket `iconic-ruler-513415-p0-landing` → `COPY INTO`
Snowflake `VAYBA.BRONZE` → dbt (`SILVER`, `GOLD`) → Dash. Airflow runs it every Monday at 06:00 Europe/Paris.

## 2. Prerequisites

| What | Where | Manual step? |
|---|---|---|
| GCP project `iconic-ruler-513415-p0`, budget alert | GCP console | Yes, once |
| Terraform state bucket `iconic-ruler-513415-p0-tfstate` (versioned) | `gcloud`, see `terraform/` | Yes, once |
| Landing bucket, its access, Snowflake read role | `terraform/main.tf` | No: `terraform apply` |
| Storage integration, stage, bronze tables | `ingestion/sql/setup_bronze.sql` | Yes, once (ACCOUNTADMIN) |
| Snowflake user with an RSA public key | Snowflake account owner | Yes, once per member |
| `.env` (root) and `airflow/.env` | from the `.env.example` files | Yes, never committed |

Each member signs in to GCP with their own account (`gcloud auth application-default login`). No service account key exists.

## 3. Launch

```bash
docker build -f docker/pipeline/Dockerfile -t vayba-pipeline:1.0.0 .
cd airflow && docker compose up --build
```

Open http://localhost:8080, unpause `vayba_weekly`, then **Trigger** with the parameter `week` set to a Monday
(e.g. `2026-10-26`). An empty `week` processes the previous week.

Order: `ingest_listenbrainz` → `ingest_musicbrainz` → `ingest_wikipedia` → `dbt_build`.
The first `ingest_musicbrainz` takes 30 to 45 minutes (1 request/s): run it once before any demo.

## 4. Verify a run

```sql
-- rows per source for the week, and the Airflow run that loaded them
SELECT 'listens' AS source, _BATCH_ID, COUNT(*) FROM VAYBA.BRONZE.LISTENS_RAW
WHERE _SOURCE_FILE LIKE 'listenbrainz/week=2026-10-26/%' GROUP BY 1, 2;

-- no duplicate listen: must return 0
SELECT COUNT(*) - COUNT(DISTINCT RAW:user_name, RAW:listened_at, RAW:recording_msid) FROM VAYBA.BRONZE.LISTENS_RAW;

-- the output exists
SELECT WEEK_START, COUNT(*) FROM VAYBA.GOLD.PLAYLIST_HEBDO GROUP BY 1 ORDER BY 1;
```

`_BATCH_ID` must hold the Airflow run id (e.g. `manual__2026-11-03T...`), not the text `{{ run_id }}`.

## 5. Replay without double counting (C6) — TO RUN

1. Run the DAG for week `2026-10-26`, then run the three queries above and note the counts.
2. Trigger the DAG again with the same `week`.
3. Run the queries again: counts must be identical, duplicates must stay at 0.

Why it holds: for a given week, `run.py` replaces the week's GCS files and deletes then reloads the week's bronze
rows in one transaction; `COPY INTO` skips files it already loaded; silver deduplicates listens.

| Run | Listens in bronze | Duplicates | Playlist rows | Date |
|---|---|---|---|---|
| 1 | | | | |
| 2 (replay) | | | | |

Note: counts can legitimately grow between two runs hours apart, because late listens reach ListenBrainz
(8,001 then 8,003 listens for the same week on 2026-11-02). Replay right after the first run to compare.

## 6. Incident 1, tested: a file loaded twice — TO RUN

**Scenario:** someone reloads a week by hand with `FORCE = TRUE`, bypassing the pipeline. Every task stays green,
but listens are counted twice.

**Trigger it** (on a `DEV_*_BRONZE` schema, never on shared `BRONZE`):

```sql
COPY INTO DEV_ELIMANE_BRONZE.LISTENS_RAW (RAW, _SOURCE_FILE, _BATCH_ID, _LOADED_AT)
FROM (SELECT $1, METADATA$FILENAME, 'incident-double-load', CURRENT_TIMESTAMP()
      FROM @DEV_ELIMANE_BRONZE.LANDING_GCS/listenbrainz/week=2026-10-26/)
FORCE = TRUE;
```

**Detect it:** the duplicate check above returns more than 0, and the dbt tests on the listens fail, so
`dbt build` skips gold: the wrong numbers never reach the playlists.

**Recover:** rerun the week through the pipeline (`python ingestion/run.py --source listenbrainz --week 2026-10-26`,
or the DAG with `week`). It deletes the week's rows and reloads each file once. The check returns 0 again.

**Prevent:** loads only go through `run.py`; shared `BRONZE` is written by the pipeline only.

| Step | Result | Date |
|---|---|---|
| Duplicates before | | |
| Duplicates after the forced load | | |
| `dbt build` result | | |
| Duplicates after recovery | | |

## 7. Incident 2, documented: a public API is down

**Scenario:** MusicBrainz answers 503, or ListenBrainz returns its anti-bot page, during the Monday run.

**What happens:** `run.py` retries 5 times with a growing delay; if it still fails it exits with code 1 and
**nothing changes in bronze** (one transaction, GCS files replaced only after every call succeeded). Airflow then
retries the task twice, 5 minutes apart, then calls the failure alert. Downstream tasks do not run, so gold keeps
last week's playlists.

**Recover:** once the API answers again, clear the failed task in Airflow, or trigger the DAG with the same `week`.

**Who and when:** the part owner, then the backup in `AGENTS.md` section 7. The batch is weekly, so a fix the same
day is enough: no night on-call.

## 8. Access: allowed and denied (C7) — TO RUN

| Test | Expected | Result |
|---|---|---|
| Elimane uploads to the landing bucket | Allowed | |
| Hugo (reader) uploads to the landing bucket | **Denied** (403) | |
| Snowflake lists the stage | Allowed | |
| Dash read-only role reads `BRONZE` | **Denied** | |

```bash
echo '{"test": true}' > test.json
gcloud storage cp test.json gs://iconic-ruler-513415-p0-landing/test/test.json
```

Secrets: Snowflake private keys and GCP credentials stay outside the repository and are mounted read-only into
containers at run time. Personal data: ListenBrainz usernames are visible in bronze and in GCS, hashed from silver on.

## 9. Costs (C7)

Prototype: to be measured, not estimated.

```sql
-- Snowflake credits per warehouse since the start of the project
SELECT WAREHOUSE_NAME, SUM(CREDITS_USED) AS CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE START_TIME >= '2026-11-01' GROUP BY 1;
```

GCP: Billing → Reports, filtered on the project.

| Item | Driver | Prototype (measured) | Assumption for the projection |
|---|---|---|---|
| Snowflake compute | XSMALL warehouse, 1 credit per running hour, auto-suspend 60 s | | weekly run length × 52 |
| Snowflake storage | bronze + silver + gold size | | grows with listens kept |
| GCS storage | files kept 30 days (lifecycle rule) | | weekly volume × 4 |
| GCS to Snowflake transfer | Snowflake runs on AWS, the bucket on GCP | | weekly volume read once |

Fill the projection with real numbers from one weekly run; state every assumption on the slide.

## 10. Budget alert and shutdown (C7)

**Alerts:** GCP budget alert on the project (warns, does not cap). On Snowflake, the account owner adds a monitor
that stops the warehouse:

```sql
USE ROLE ACCOUNTADMIN;
CREATE RESOURCE MONITOR IF NOT EXISTS VAYBA_MONITOR WITH CREDIT_QUOTA = 10
  TRIGGERS ON 80 PERCENT DO NOTIFY ON 100 PERCENT DO SUSPEND;
ALTER WAREHOUSE VAYBA_WH SET RESOURCE_MONITOR = VAYBA_MONITOR;
```

**Pause** (between demos): pause `vayba_weekly` in Airflow, then

```bash
cd airflow && docker compose down
```

```sql
ALTER WAREHOUSE VAYBA_WH SUSPEND;
```

**Full cleanup** (after grading only, never before the defense):
1. Empty the landing bucket: `gcloud storage rm "gs://iconic-ruler-513415-p0-landing/**"`
2. `cd terraform && terraform destroy` (the bucket refuses deletion while it holds files).
3. In Snowflake: `DROP DATABASE VAYBA;`, `DROP WAREHOUSE VAYBA_WH;`, `DROP INTEGRATION VAYBA_GCS_INT;`
4. Delete the state bucket, then shut the GCP project down from the console.
