"""Vayba ingestion (part 1): one source, one week -> GCS landing -> Snowflake BRONZE.

    python ingestion/run.py --source listenbrainz --week 2026-10-26
    python ingestion/run.py --source musicbrainz  --week 2026-10-26   # needs that week's listens
    python ingestion/run.py --source wikipedia    --week 2026-10-26   # needs that week's artists
    add --no-load to only write data/landing/ (no GCS, no Snowflake)

Rerunning gives the same bronze rows: weekly sources replace their week, artists are immutable files.
Any failure ends with a non-zero exit code.
"""
import argparse
import datetime as dt
import functools
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LANDING = ROOT.parent / "data" / "landing"
UA = "VaybaStudentProject/0.1 ( https://github.com/Elimane29/vayba-data-platform )"
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
TABLES = {"listenbrainz": "LISTENS_RAW", "musicbrainz": "MB_ARTISTS_RAW", "wikipedia": "WIKI_PAGEVIEWS_RAW"}


# ---------- helpers ----------

def load_dotenv(path=ROOT.parent / ".env"):
    """Read KEY=VALUE lines from .env without overriding variables already set (Airflow, Docker)."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"'))


def week_bounds(week):
    """--week must be a Monday. Returns [start, end) in UTC."""
    start = dt.datetime.strptime(week, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    if start.weekday() != 0:
        raise ValueError(f"--week {week} is not a Monday")
    return start, start + dt.timedelta(days=7)


def get_json(url, pause=0.0, tries=5):
    """GET with a timeout, retries on 429 / 5xx / network errors / non-JSON answers with a growing delay,
    loud failure. 404 -> None."""
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=30) as response:
                time.sleep(pause)
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise
        # ValueError: an HTML page with status 200, e.g. ListenBrainz's "Verifying your browser" anti-bot check
        except (urllib.error.URLError, TimeoutError, ValueError):
            if attempt == tries - 1:
                raise
        time.sleep(2 ** attempt)


def artist_mbids(listen):
    """Artist ids ListenBrainz mapped to MusicBrainz; empty when the listen is not mapped."""
    ids = (listen["track_metadata"].get("mbid_mapping") or {}).get("artist_mbids") or []
    return [a for a in ids if re.fullmatch(UUID, a)]


@functools.lru_cache(maxsize=None)
def bucket():
    from google.cloud import storage  # imported here so --no-load runs with the standard library only
    return storage.Client().bucket(os.environ["GCS_BUCKET"])


def landed(prefix, upload):
    """Names of the files already landed under prefix (GCS, or data/landing/ with --no-load)."""
    if upload:
        return {b.name for b in bucket().list_blobs(prefix=prefix)}
    return {p.relative_to(LANDING).as_posix() for p in (LANDING / prefix).rglob("*.json")}


def read_lines(name, upload):
    text = bucket().blob(name).download_as_text() if upload else (LANDING / name).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def write(name, docs, upload):
    """One untouched source document per line (NDJSON). Local copy always, GCS copy unless --no-load."""
    path = LANDING / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs), encoding="utf-8")
    if upload:
        bucket().blob(name).upload_from_filename(str(path), content_type="application/x-ndjson")


def reset(prefix, upload):
    """Remove a week's landed files, so a rerun cannot keep a stale file."""
    shutil.rmtree(LANDING / prefix, ignore_errors=True)
    if upload:
        for blob in bucket().list_blobs(prefix=prefix):
            blob.delete()


def week_artists(week, upload):
    names = landed(f"listenbrainz/week={week}/", upload)
    if not names:
        raise RuntimeError(f"no listens landed for week {week}: run --source listenbrainz first")
    return sorted({a for name in names for listen in read_lines(name, upload) for a in artist_mbids(listen)})


# ---------- sources: each writes its files and returns (prefix to load, replace the prefix in bronze?) ----------

def ingest_listenbrainz(week, start, end, upload):
    prefix = f"listenbrainz/week={week}/"
    users = [u.strip() for u in (ROOT / "listenbrainz_users.txt").read_text(encoding="utf-8").splitlines()
             if u.strip() and not u.startswith("#")]
    if not users:
        raise RuntimeError("ingestion/listenbrainz_users.txt is empty")
    files = {}
    for user in users:
        listens, max_ts = [], int(end.timestamp())
        while True:
            page = get_json(f"https://api.listenbrainz.org/1/user/{urllib.parse.quote(user)}/listens"
                            f"?count=1000&max_ts={max_ts}", pause=1.0)  # polite: fewer anti-bot checks
            if page is None:
                raise RuntimeError(f"ListenBrainz user {user} not found")
            batch = page["payload"]["listens"]  # newest first
            listens += [l for l in batch if l["listened_at"] >= start.timestamp()]
            if not batch or batch[-1]["listened_at"] < start.timestamp():
                break
            # shortcut: max_ts is exclusive, so listens sharing the page-boundary second can be missed;
            # negligible at a few listens per minute, switch to min_ts paging if users get much heavier
            max_ts = batch[-1]["listened_at"]
        files[f"{prefix}user={user}.json"] = listens
    reset(prefix, upload)  # only after every API call succeeded: a failed run keeps last week's good files
    for name, docs in files.items():
        write(name, docs, upload)
    print(f"listenbrainz: {sum(map(len, files.values()))} listens, {len(files)} users, week {week}")
    return prefix, True


def ingest_musicbrainz(week, start, end, upload):
    prefix = "musicbrainz/"
    have = landed(prefix, upload)
    todo = [a for a in week_artists(week, upload) if f"{prefix}artist={a}.json" not in have]
    print(f"musicbrainz: {len(todo)} new artists to fetch at 1 request/s")
    for a in todo:
        doc = get_json(f"https://musicbrainz.org/ws/2/artist/{a}?fmt=json&inc=url-rels", pause=1.0)
        if doc is not None:  # 404: id merged or deleted in MusicBrainz, silver will quarantine those listens
            write(f"{prefix}artist={a}.json", [doc], upload)
    return prefix, False  # artist files never change once landed: Snowflake's load history skips them


def ingest_wikipedia(week, start, end, upload):
    prefix = f"wikipedia/week={week}/"
    have = landed("musicbrainz/", upload)
    qids = {}
    for a in week_artists(week, upload):
        if f"musicbrainz/artist={a}.json" in have:
            for rel in read_lines(f"musicbrainz/artist={a}.json", upload)[0].get("relations", []):
                if rel.get("type") == "wikidata":
                    qids[a] = rel["url"]["resource"].rsplit("/", 1)[-1]
    titles, ids = {}, sorted(set(qids.values()))
    for i in range(0, len(ids), 50):  # Wikidata: 50 ids per call, used only to find the English article
        answer = get_json("https://www.wikidata.org/w/api.php?action=wbgetentities&props=sitelinks"
                          "&sitefilter=enwiki&format=json&ids=" + urllib.parse.quote("|".join(ids[i:i + 50])))
        titles.update({q: e["sitelinks"]["enwiki"]["title"] for q, e in answer["entities"].items()
                       if "enwiki" in e.get("sitelinks", {})})
    days = f"{start:%Y%m%d}/{end - dt.timedelta(days=1):%Y%m%d}"
    files = {}
    for a, q in qids.items():
        if q in titles:
            article = urllib.parse.quote(titles[q].replace(" ", "_"), safe="")
            doc = get_json("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
                           f"all-access/user/{article}/daily/{days}", pause=0.05)
            if doc:  # the artist MBID lives in the file name: the source document has only the article title
                files[f"{prefix}artist={a}.json"] = [doc]
    reset(prefix, upload)
    for name, docs in files.items():
        write(name, docs, upload)
    print(f"wikipedia: {len(files)} artists with pageviews out of {len(qids)} with a Wikidata link")
    return prefix, True


SOURCES = {"listenbrainz": ingest_listenbrainz, "musicbrainz": ingest_musicbrainz, "wikipedia": ingest_wikipedia}


# ---------- Snowflake ----------

def load(table, prefix, batch_id, replace):
    """COPY INTO bronze. replace=True: delete the week's rows, then reload its files, in one transaction."""
    import snowflake.connector

    copy = (f"COPY INTO {table} (RAW, _SOURCE_FILE, _BATCH_ID, _LOADED_AT) "
            f"FROM (SELECT $1, METADATA$FILENAME, '{batch_id}', CURRENT_TIMESTAMP() FROM @LANDING_GCS/{prefix}) "
            "FILE_FORMAT = (FORMAT_NAME = 'JSONL') ON_ERROR = ABORT_STATEMENT" + (" FORCE = TRUE" if replace else ""))
    con = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"],
        role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "VAYBA_WH"),
        database="VAYBA",
        schema=os.environ.get("VAYBA_BRONZE_SCHEMA", "BRONZE"))  # DEV_<FIRSTNAME>_BRONZE to test (AGENTS.md §5)
    try:
        cur = con.cursor()
        cur.execute("BEGIN")
        if replace:
            cur.execute(f"DELETE FROM {table} WHERE _SOURCE_FILE LIKE %s", (prefix + "%",))
        cur.execute(copy)
        cur.execute("COMMIT")
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE _SOURCE_FILE LIKE %s", (prefix + "%",))
        print(f"{table}: {cur.fetchone()[0]} rows under {prefix}")
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, choices=SOURCES)
    parser.add_argument("--week", required=True, help="Monday of the week, YYYY-MM-DD, in UTC")
    parser.add_argument("--no-load", action="store_true", help="only write data/landing/: no GCS, no Snowflake")
    args = parser.parse_args(argv)
    try:
        load_dotenv()
        start, end = week_bounds(args.week)
        upload = not args.no_load
        batch_id = os.environ.get("VAYBA_BATCH_ID") or \
            f"{args.source}-{args.week}-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}"
        if not re.fullmatch(r"[\w.:+-]+", batch_id):  # it is written into the COPY statement
            raise ValueError(f"invalid VAYBA_BATCH_ID {batch_id!r}")
        prefix, replace = SOURCES[args.source](args.week, start, end, upload)
        if upload:
            load(TABLES[args.source], prefix, batch_id, replace)
    except Exception as e:
        print(f"FAILED {args.source} {args.week}: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
