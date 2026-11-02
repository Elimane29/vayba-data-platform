# Containerised ingestion, 2026-11-02

Image `vayba-pipeline:1.0.0`, built from `docker/pipeline/Dockerfile`.

    docker run --rm vayba-pipeline:1.0.0 python ingestion/run.py --source listenbrainz --week 2026-10-26 --no-load
    listenbrainz: 8003 listens, 25 users, week 2026-10-26
    exit code: 0

The ingestion README reported 8,001 listens for the same week earlier the same day:
late listens reached ListenBrainz in between.
