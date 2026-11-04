# Airflow run, week 2026-10-26 (2026-11-03)

Run: `scheduled__2026-11-02T05:00:00+00:00`, DAG `vayba_weekly`, image `vayba-pipeline:1.0.0`.
The DAG processed the completed week 2026-10-26 (fix: Airflow 3 data interval starts at run time).

## Incident: Snowflake key rejected (tested, recovered)

- Attempt 1 of `ingest_listenbrainz`: extraction OK (`listenbrainz: 8003 listens, 25 users, week 2026-10-26`),
  then `FAILED listenbrainz 2026-10-26: DatabaseError: 390144 (28000): ... JWT token is invalid.`
- Airflow set the task to `up_for_retry`; bronze was not changed (one transaction).
- Cause: the public key registered on the Snowflake user did not match the private key.
- Fix: the account owner registered the right public key (fingerprint checked on both sides).
- Retry: `ingest_listenbrainz` success, 2026-11-03 19:18:53 → 19:20:41 UTC (1 min 48 s).

## Tasks

| Task | State | Start (UTC) | End (UTC) | Duration | Output |
|---|---|---|---|---|---|
| ingest_listenbrainz | success | 19:18:53 | 19:20:41 | 1 min 48 s | 8,003 listens, 25 users |
| ingest_musicbrainz | success | 19:20:42 | 19:21:20 | 38 s | 0 new artists to fetch |
| ingest_wikipedia | success | 19:21:21 | 19:47:33 | 26 min 12 s | 1,234 artists with pageviews out of 1,278 linked to Wikidata |
| dbt_build | success | 19:47:34 | 19:48:30 | 56 s | dbt 1.11.16: `PASS=26 WARN=0 ERROR=0 SKIP=0` (12 models, 13 tests, 1 operation) |

## Snowflake after the run (read with `VAYBA_ELIMANE`, 2026-11-03)

| Check | Result |
|---|---|
| Bronze listens, week 2026-10-19 (batch `yanis-20261103-history-run2`) | 8,444 |
| Bronze listens, week 2026-10-26 (batch `scheduled__2026-11-02T05:00:00+00:00`) | 8,003 |
| Bronze total | 16,447, same as the part 1 load: the week was replaced, not added |
| Bronze duplicate listens | 0 |
| Bronze artists / Wikipedia documents | 2,478 / 1,234 |
| Silver listens | 14,472 |
| Gold `PLAYLIST_HEBDO`, week 2026-10-26 | 25 users, 250 rows (10 per user) |
| Gold `METRICS_HEBDO`, week 2026-10-26 | hit rate S+1 0.48, popularity baseline 0.56, discovery rate 1.00 |
| `OPS.DBT_RESULTS`, runtime `airflow` | 12 `success`, 13 `pass` |
