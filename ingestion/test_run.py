"""Offline checks of run.py, no network: python ingestion/test_run.py"""
import datetime as dt

from run import artist_mbids, main, week_bounds

start, end = week_bounds("2026-10-26")
assert start == dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc) and end - start == dt.timedelta(days=7)
try:
    week_bounds("2026-10-27")  # a Tuesday
    raise AssertionError("a non-Monday week must be refused")
except ValueError:
    pass

mapped = {"track_metadata": {"mbid_mapping": {"artist_mbids": ["a74b1b7f-71a5-4011-9441-d0b5e4122711", "../etc"]}}}
assert artist_mbids(mapped) == ["a74b1b7f-71a5-4011-9441-d0b5e4122711"]  # only real UUIDs reach a file name
assert artist_mbids({"track_metadata": {}}) == []                       # unmapped listen
assert artist_mbids({"track_metadata": {"mbid_mapping": None}}) == []

assert main(["--source", "listenbrainz", "--week", "2026-10-27", "--no-load"]) == 1  # failure -> exit code 1
print("ok")
