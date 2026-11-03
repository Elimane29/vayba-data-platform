import argparse
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from check_pipeline import ROOT, build, snapshot


def check(database):
    before = snapshot(database)
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / 'duplicate.duckdb'
        shutil.copyfile(database, copy)
        with duckdb.connect(str(copy)) as connection:
            raw_before = connection.execute('SELECT COUNT(*) FROM DEV_HUGO_BRONZE.LISTENS_RAW').fetchone()[0]
            silver_before = connection.execute('SELECT COUNT(*) FROM DEV_HUGO_SILVER.SILVER_LISTENS').fetchone()[0]
            # New technical batch, same business event: bypass the loader's exact-replay guard.
            connection.execute("""INSERT INTO DEV_HUGO_BRONZE.LISTENS_RAW
                SELECT RAW, _SOURCE_FILE, _BATCH_ID || ':incident_duplicate', _LOADED_AT,
                       sha256('incident_duplicate:' || _ROW_HASH)
                FROM DEV_HUGO_BRONZE.LISTENS_RAW
                WHERE json_array_length(json_extract(RAW, '$.track_metadata.mbid_mapping.artist_mbids')) > 0
                ORDER BY _ROW_HASH LIMIT 1""")
            raw_after = connection.execute('SELECT COUNT(*) FROM DEV_HUGO_BRONZE.LISTENS_RAW').fetchone()[0]
            assert raw_after == raw_before + 1
        log = build(copy)
        with duckdb.connect(str(copy), read_only=True) as connection:
            silver_after, distinct_keys = connection.execute('SELECT COUNT(*), COUNT(DISTINCT listen_key) FROM DEV_HUGO_SILVER.SILVER_LISTENS').fetchone()
        assert silver_after == silver_before == distinct_keys
        assert snapshot(copy) == before
        assert 'unique_silver_listens_listen_key' in log
    assert snapshot(database) == before
    return {'executed_at_utc': datetime.now(timezone.utc).isoformat(),
            'execution_target': 'local DuckDB; disposable copy; original database unchanged',
            'bronze_before': raw_before, 'bronze_after_injection': raw_after,
            'silver_before': silver_before, 'silver_after': silver_after,
            'silver_distinct_keys_after': distinct_keys,
            'dbt_build': 'PASS', 'gold_unchanged': True,
            'silver_unique_test': 'PASS; the duplicate was removed upstream',
            'expected_quality_failure': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, default=ROOT / 'vayba_local.duckdb')
    parser.add_argument('--output', type=Path, default=ROOT / 'dbt/evidence/duplicate_recovery.json')
    args = parser.parse_args()
    result = check(args.database.resolve())
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
