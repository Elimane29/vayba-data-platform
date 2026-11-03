# Ingestion (part 1, owner Yanis)

One command per source and week: public API → NDJSON file in GCS → `COPY INTO` Snowflake `VAYBA.BRONZE`.

| Source | Command | GCS file | Bronze table | Rerun |
|---|---|---|---|---|
| ListenBrainz listens | `--source listenbrainz` | `listenbrainz/week=<monday>/user=<name>.json` | `LISTENS_RAW` | the week's files and rows are replaced |
| MusicBrainz artists | `--source musicbrainz` | `musicbrainz/artist=<mbid>.json` | `MB_ARTISTS_RAW` | only new artists are fetched; Snowflake skips files already loaded |
| Wikipedia pageviews | `--source wikipedia` | `wikipedia/week=<monday>/artist=<mbid>.json` | `WIKI_PAGEVIEWS_RAW` | the week's files and rows are replaced |

Order inside a week: `listenbrainz` → `musicbrainz` → `wikipedia` (each reads the previous one's files).
Wikidata is only used inside `wikipedia` to turn an artist's Wikidata id into its English article title.

Every bronze row: `RAW` (untouched source document), `_SOURCE_FILE` (path in the bucket), `_BATCH_ID`
(`VAYBA_BATCH_ID`, e.g. the Airflow run id, otherwise `<source>-<week>-<UTC time>`), `_LOADED_AT`.

## Prerequisites

- Python 3.10+, `pip install -r requirements.txt`
- `.env` at the repository root (template `.env.example`): `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
  `SNOWFLAKE_PRIVATE_KEY_FILE`, `GCS_BUCKET`, `GOOGLE_APPLICATION_CREDENTIALS`.
  Optional, defaults in brackets: `SNOWFLAKE_ROLE` (`SYSADMIN`), `SNOWFLAKE_WAREHOUSE` (`VAYBA_WH`),
  `VAYBA_BRONZE_SCHEMA` (`BRONZE`; set `DEV_<FIRSTNAME>_BRONZE` to test without touching shared bronze)
- Once: `ingestion/sql/setup_bronze.sql`. Part 1 is for the Snowflake account owner (storage integration,
  ACCOUNTADMIN); part 2 creates the stage and the 3 tables, once for `BRONZE` and once per `DEV_*_BRONZE` schema

## Run

```bash
python ingestion/run.py --source listenbrainz --week 2026-10-26
python ingestion/run.py --source musicbrainz  --week 2026-10-26
python ingestion/run.py --source wikipedia    --week 2026-10-26
```

`--week` is the Monday of the week, in UTC (listens from Monday 00:00 to the next Monday 00:00).
`--no-load` only writes `data/landing/` (git-ignored): no GCS, no Snowflake, no credentials needed.
Users to ingest: `ingestion/listenbrainz_users.txt`. Offline checks: `python ingestion/test_run.py`.

## Verify

```sql
-- rows per file of the week: run the command twice, the numbers must not move
SELECT _SOURCE_FILE, COUNT(*) FROM VAYBA.BRONZE.LISTENS_RAW
WHERE _SOURCE_FILE LIKE 'listenbrainz/week=2026-10-26/%' GROUP BY 1 ORDER BY 1;

-- no duplicate listen: must return 0
SELECT COUNT(*) - COUNT(DISTINCT RAW:user_name, RAW:listened_at, RAW:recording_msid) FROM VAYBA.BRONZE.LISTENS_RAW;
```

Reference runs, `--no-load`, 2026-11-02, week 2026-10-26:
- listenbrainz, 25 users: 8,001 listens in 40 s, 1,580 distinct artists, 12 % of listens without a MusicBrainz id.
- listenbrainz, first 4 users only: 1,411 listens (Mergzo 232, frankpanduh 440, jwheel 333, zzzach 406), second run
  byte-identical.
- wikipedia, same 4 users: 379 artists with pageviews out of 388 with a Wikidata link, in 2 min.

Additional local run, 2026-11-02, week 2026-10-26: 8,003 listens for 25 users,
with 0 duplicates on `(user file, listened_at, recording_msid)`. The earlier 8,001 count is a previous
measurement, not a fixed expected count: late listens can change the API response.

Production validation, 2026-11-03, week 2026-10-26:
- `VAYBA.BRONZE.LISTENS_RAW`: 8,003 rows from 25 files, 0 duplicates.
- `VAYBA.BRONZE.MB_ARTISTS_RAW`: 1,580 rows from 1,580 files, 0 duplicate artist ids.
- Both were loaded from the GCS stage with `VAYBA_YANIS`, then replayed from the **same files**.
  Counts and `HASH_AGG(RAW, _SOURCE_FILE)` stayed identical.
- This is a manual Snowsight `COPY INTO` validation. The Airflow replay and dbt production build are separate,
  not yet executed by this session. Evidence: `docs/evidence/2026-11-03_bronze_replay.json`.
- `VAYBA.BRONZE.WIKI_PAGEVIEWS_RAW`: 1,234 rows from 1,234 files. The three-source replay also passed, with 0 duplicates and identical content hashes.
  Evidence: `docs/evidence/2026-11-03_three_sources_replay.json`.

After loading, run `ingestion/sql/verify_prod.sql` in Snowsight twice, once before and once after replay.
Keep the same landed files during this test: compare row counts and content hashes, excluding the batch ID
and load timestamp. A second extraction from the live API is a separate freshness test and can legitimately
produce additional listens. Save both outputs and run IDs in `docs/evidence/`.

## Known failures

Final two-week extension, 2026-11-03:
- Frozen ListenBrainz weeks 2026-10-19 and 2026-10-26: 16,447 rows / 50 files.
- MusicBrainz cache: 2,478 artists / files; Wikipedia week 2026-10-26: 1,234 rows / files.
- `ingestion/sql/load_two_weeks.sql` and `verify_two_weeks.sql` were executed twice in Snowsight.
  Counts and content hashes matched, with zero duplicates for all three sources.
- Evidence: `docs/evidence/2026-11-03_two_weeks_replay.json` and screenshots.
- Hugo PR4 was also built locally on these actual API extracts: 12 models + 13 tests + hook passed.
  This does not certify Snowflake SQL execution or Airflow. Use explicit dbt vars
  `history_start: 2026-10-19`, `week_start: 2026-10-26`, `test_end: 2026-11-02`.
- Local S+1 results: 25 users, hit rate 0.48 versus popularity 0.56; no uplift demonstrated.
  See `docs/evidence/2026-11-03_real_data_dbt_local.json` and the handoff for remaining decisions.

| Symptom | Cause | What happens |
|---|---|---|
| Exit code 1, `FAILED <source> <week>: ...` on stderr | any error | nothing in bronze changes (one transaction); the week's GCS files are replaced only after every API call succeeded |
| `no listens landed for week ...` | `musicbrainz` or `wikipedia` run before `listenbrainz` | run `listenbrainz` first |
| `ListenBrainz user X not found` | user renamed or deleted | fix `listenbrainz_users.txt` |
| MusicBrainz 503 "busy" | its 1 request/s limit, or overload | 5 tries with a growing delay, then failure |
| First `musicbrainz` run takes 30–45 min | about 1,000 new artists for 25 users, at 1 request/s | run it before any demo; later weeks fetch only new artists |
| ListenBrainz answers an HTML page "Verifying your browser" with status 200 | its anti-bot check, seen on 2026-11-02 after ~100 fast calls | treated as a temporary error: retried with a growing delay; 1 s pause between calls |
| ~12 % of listens have no `mbid_mapping` | ListenBrainz could not match the track | kept in bronze; silver quarantines them |
