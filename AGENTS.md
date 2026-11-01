# Vayba: shared working agreement for the team and its agents

**Every agent reads this file before acting.** If a request conflicts with it, the agent tells its human before continuing.

**Graphify is mandatory on this project.** Agents must use it before searching or reading code, to save tokens. See section 9.

## 1. The project
- **Context:** oral defense for the Data Engineering & Cloud course, group 7. Vayba is a fictional music streaming company.
- **Promise:** helping people look for new vibes.
- **Product:** every week, one "New Vibes" playlist per user.
- **Deadlines:** submission on **Nov 4, 2026**, oral defense on **Nov 6 at 11:00**.
- **Priority:** a small pipeline that runs and can be proven beats a big architecture. No decorative components.

## 2. Shared decisions
These change only if all 3 members agree.

| Topic | Decision |
|---|---|
| Data | ListenBrainz, MusicBrainz (CC0 only), Wikipedia pageviews, Wikidata only to link artists to Wikipedia. **No Spotify data or API** |
| Storage | Private GCS bucket |
| Warehouse | Snowflake, database `VAYBA`, schemas `BRONZE`, `SILVER`, `GOLD`, on one shared account |
| Transformation | dbt 1.11 |
| Recommendation | Co-listening in SQL inside dbt, no ML model |
| Orchestration | Airflow + Docker, weekly batch, no streaming |
| IaC | Terraform, remote state in GCS |
| Visualisation | Dash, read-only on `GOLD` |

**Still open:** B2B (recommended) or B2C, and 4 or 5 sources, depending on the instructor's answer.

## 3. Ownership

### Part 1: Business and ingestion, owner Yanis
**Folders:** `ingestion/`, `docs/business.md`
- Revenue model, customers, size, stakeholders, numerical constraints, all stated as assumptions.
- Use case sheet: decision, user, metrics with grain, formula and exclusions, frequency, acceptance test.
- Extraction scripts to GCS, one per source, with timeout, retry and visible failure.
- `COPY INTO` loading to `BRONZE`.
- **Done when:** at least two real sources reach bronze, and rerunning the load creates no duplicates.
- **Rubric:** C1, C2, ingestion in C3.

### Part 2: dbt, quality and app, owner Hugo
**Folders:** `dbt/`, `dashboard/`
- Silver: typing, deduplication, quarantine with a reason, hashed usernames.
- Gold: co-listening, `PLAYLIST_HEBDO`, `METRICS_HEBDO`.
- Tests: key, business rule, freshness or completeness, with one demonstrated failure.
- Acceptance test on a small dataset calculated by hand.
- Next-week (S+1) evaluation against a popularity baseline.
- Seed of listening histories entered by hand by the 3 members, and a genre consistency check.
- Dash app with two views: playlist, metrics.
- **Done when:** `dbt build` passes and the app shows a playlist from `GOLD`.
- **Rubric:** transformations and verification in C3, tests in C6.

### Part 3: Automation, cloud and incidents, owner Elimane
**Folders:** `airflow/`, `terraform/`, `docker/`, `.github/`, `docs/runbook.md`
- Docker images for ingestion and dbt, pinned versions, no secrets.
- Weekly DAG: ingestion, `dbt build`, publication.
- Terraform: GCS bucket and remote state.
- Replay without double counting.
- Two incident scenarios, including the tested double load.
- Allowed and denied access, prototype cost and projection, budget alert, shutdown procedure.
- Architecture review: Elimane reads across all parts to be able to explain everything.
- **Done when:** a full Airflow run succeeds and the replay leaves the numbers unchanged.
- **Rubric:** container in C3, C4, C5, rest of C6, C7.

### Shared work (C8)
- **Slides:** each member writes the slides for their part, Yanis assembles them.
- **`README.md` and architecture diagram:** Elimane.
- **Video and run evidence:** Elimane, from one complete run.

## 4. Contracts between parts
These contracts allow parallel work. They change only through a PR approved by the other 2 members.

### Bronze (part 1 to part 2)
`VAYBA.BRONZE.LISTENS_RAW`, `MB_ARTISTS_RAW`, `WIKI_PAGEVIEWS_RAW`:

| Column | Type | Purpose |
|---|---|---|
| `RAW` | VARIANT | Untouched source document |
| `_SOURCE_FILE` | VARCHAR | Source file |
| `_BATCH_ID` | VARCHAR | Run identifier |
| `_LOADED_AT` | TIMESTAMP_TZ | Load time |

### Gold (part 2 to the app and part 3)
`VAYBA.GOLD.PLAYLIST_HEBDO`, one row per `WEEK_START`, `USER_KEY`, `POSITION`:
`WEEK_START` DATE, `USER_KEY` VARCHAR (hashed, or manual profile), `POSITION` INT, `RECORDING_MBID`, `TRACK_NAME`, `ARTIST_MBID`, `ARTIST_NAME`, `BECAUSE_ARTIST_NAME` VARCHAR, `SCORE` FLOAT.

`VAYBA.GOLD.METRICS_HEBDO`, one row per `WEEK_START`:
`WEEK_START` DATE, `USERS_EVALUATED` INT, `HIT_RATE_S1` FLOAT, `HIT_RATE_BASELINE_S1` FLOAT, `DISCOVERY_RATE` FLOAT, `LAST_LOADED_AT` TIMESTAMP_TZ.

### Commands (parts 1 and 2 to part 3)
- `python ingestion/run.py --source <name> --week <YYYY-MM-DD>`: idempotent, non-zero exit code on failure.
- `dbt build --project-dir dbt --profiles-dir dbt`.

### Environment
Variables live in `.env`, never committed, with the template in `.env.example`: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_FILE`, `VAYBA_RUNTIME`, plus whatever each part adds to the template.

## 5. Working without stepping on each other
- **Folders:** each member changes only their own. For a need elsewhere, open an issue or ask the owner.
- **Shared files:** `AGENTS.md`, `.gitignore`, `.graphifyignore`, `.env.example`, `requirements*.txt` and `README.md` change through a small dedicated PR.
- **Git:** never commit directly to `main`. Branches: `part1/<topic>`, `part2/<topic>`, `part3/<topic>`.
- **PRs:** small, stating what was run and the result. Reviewed by another member.
- **Snowflake:** each member develops in their own `DEV_<FIRSTNAME>_*` schemas. `BRONZE`, `SILVER` and `GOLD` receive validated runs only.
- **No waiting:** until upstream is ready, work on a small extract that respects the contract, in `tests/fixtures/`.

## 6. Rules for agents
1. Read this file and the README of the relevant folder before writing.
2. Stay within your human's scope, and never change a contract alone.
3. Never read, print or commit secrets, keys or `.env`.
4. Never run these without human approval: `terraform apply` or `destroy`, deleting a table or bucket, pushing to `main`, large downloads, permission changes.
5. Report a result only after running it, and quote the command and its output. Never invent a number, run or piece of evidence.
6. Flag anything untested, and any deviation from this agreement.
7. Write simple code the human can explain at the oral defense. No dependency or tool without a justified need.
8. Reuse the resource pack examples and the `red203-kiosk-data-quality`, `red401-airflow-terraform` and `redgrave-platform` repositories first, without importing their Redgrave names, the hardcoded local path or the deliberate `--crash-on-try` crash.
9. Make code replayable: same input, same result. Date comes from the run, storage in UTC.
10. Put evidence in `docs/evidence/`: date, run ID, versions, result, no sensitive data.

## 7. Being able to take over
| If absent or blocked | Backup | Must know how to |
|---|---|---|
| Yanis | Elimane | Rerun ingestion, defend the business case |
| Hugo | Yanis | Run `dbt build`, read a failing test, launch the app |
| Elimane | Hugo | Run the DAG, restart a run, execute the replay |

- **Trigger:** blocked for more than 2 hours or a missed checkpoint. Tell the group, then the backup takes over.
- **Shared code:** push at least every evening, even on a branch, so nothing lives on one laptop only.
- **Documentation:** every folder has a README with prerequisites, the launch command, how to verify the result and known failures.
- **Access:** all 3 members can access the repository, Snowflake and the GCP project. Secrets never go through the repository or a public chat.
- **Takeover test:** before submission, each member runs someone else's part at least once using only its README.
- **Oral defense:** each member presents their part and must be able to answer on the other two.

## 8. Checkpoints
| When | Expected |
|---|---|
| **Nov 1, evening** | Repository, access, `.env`, agreed contracts, test extracts |
| **Nov 2, evening** | Manual end-to-end: one source in bronze, `PLAYLIST_HEBDO` filled, app connected |
| **Nov 3, noon** | Additional sources, tests and S+1 metrics |
| **Nov 3, evening** | DAG, Terraform, replay, tested incident. **No new features after this** |
| **Nov 4** | Slides, README, architecture, video, takeover tested, **submission** |
| **Nov 5** | Timed rehearsal and jury questions |

**If time runs short, cut in this order:** Wikidata and pageviews, cloud deployment of the app, CI, genre check. Never cut: end-to-end pipeline, tests, replay, tested incident.

## 9. Mandatory: saving tokens with Graphify
AI quota can run out right before the defense, so **every agent must use Graphify**. If it is missing or fails, the agent says so and helps its human set it up before exploring the code.

**Setup, once per member:**
- `pip install "graphifyy[sql]"` (the `sql` extra is required to read the dbt models)
- From the repository root: `graphify update .`
- Claude Code users: `graphify claude install`. Codex users get these rules through `AGENTS.md`.

**Rules for agents:**
1. Before any search or file read, start with `graphify query "<question>" --budget 1500`, then `graphify path "A" "B"` or `graphify explain "X"`.
2. Read `graphify-out/GRAPH_REPORT.md` only for a broad architecture review, or if those commands are not enough.
3. Open only the files the graph points to. Never read the whole repository, data files, logs or `.venv/`.
4. After changing code, run `graphify update .`. It needs no LLM.
5. Quote only the failing lines of long outputs.
6. One task per session, and start a new session between tasks.

`graphify-out/` stays local and is not committed: everyone rebuilds it, which avoids merge conflicts.
