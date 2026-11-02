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
  `SNOWFLAKE_PRIVATE_KEY_FILE`, `GCS_BUCKET`, `GOOGLE_APPLICATION_CREDENTIALS`
- Once: `ingestion/sql/setup_bronze.sql` (storage integration with ACCOUNTADMIN, stage, 3 tables)

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

Loading into GCS and Snowflake not run yet: the bucket and the shared Snowflake account do not exist yet (2026-11-02).

## Known failures

| Symptom | Cause | What happens |
|---|---|---|
| Exit code 1, `FAILED <source> <week>: ...` on stderr | any error | nothing in bronze changes (one transaction); the week's GCS files are replaced only after every API call succeeded |
| `no listens landed for week ...` | `musicbrainz` or `wikipedia` run before `listenbrainz` | run `listenbrainz` first |
| `ListenBrainz user X not found` | user renamed or deleted | fix `listenbrainz_users.txt` |
| MusicBrainz 503 "busy" | its 1 request/s limit, or overload | 5 tries with a growing delay, then failure |
| First `musicbrainz` run takes 30–45 min | about 1,000 new artists for 25 users, at 1 request/s | run it before any demo; later weeks fetch only new artists |
| ListenBrainz answers an HTML page "Verifying your browser" with status 200 | its anti-bot check, seen on 2026-11-02 after ~100 fast calls | treated as a temporary error: retried with a growing delay; 1 s pause between calls |
| ~12 % of listens have no `mbid_mapping` | ListenBrainz could not match the track | kept in bronze; silver quarantines them |
