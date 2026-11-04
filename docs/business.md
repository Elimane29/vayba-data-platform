# Vayba: business case and use case sheet

Vayba is a fictional music streaming company. **Promise:** helping people look for new vibes.
**Product:** every Monday, one "New Vibes" playlist per user, with 10 distinct artists absent from their
observed training history and one representative recording per artist, picked through co-listening.

Every number below is either **measured** on our real data (with its source) or an **assumption** (H1, H2…)
that we state as such. Nothing here is a real company figure.

## 1. Business model

**Selected model: B2C.** Vayba serves listeners directly through a free tier and a premium subscription.
The audience, conversion and price below form a fictional scenario, not measured commercial performance.

| Item | B2C scenario | Status |
|---|---|---|
| Customer | Listeners using Vayba directly | Selected target |
| Offer | Free tier plus a premium subscription, with weekly discovery playlists | Product scenario |
| Premium price | €9.99 per month | H1: assumed price |
| Audience | 100,000 listeners | H2: assumed monthly audience |
| Premium conversion | 5%, or 5,000 paying subscribers | H3: assumed conversion |
| Monthly revenue | 100,000 × 5% × €9.99 = **approximately €49,950 per month** | Scenario arithmetic; not profit or proven revenue |

Acquisition by a large group is a **possible exit hypothesis**, contingent on interest from a buyer and
the development of the business. It is not an operating plan, a promised transaction or an assumed valuation.

## 2. Stakeholders and constraints

| Stakeholder | Interest | What they receive |
|---|---|---|
| Listener | Discover artists they like | Their playlist (Dash, view "playlist") |
| Head of product | Decide whether co-listening is worth it compared with a simple popularity list | `METRICS_HEBDO` (Dash, view "metrics") |
| Premium subscriber (B2C) | A service worth renewing each month | A weekly discovery playlist, ready by Monday 08:00 |
| Data team | A pipeline that can be rerun and explained | Yanis: ingestion · Hugo: dbt, tests, app · Elimane: Airflow, Terraform, incidents |
| DPO | Listening history is personal data (GDPR) | User names hashed from silver onwards, only `GOLD` exposed |

| Constraint | Value | Source |
|---|---|---|
| Listens per user per week | about 320 | **measured**: 8,001 listens for 25 users, week 2026-10-26 |
| Raw size of one listen | about 1.2 KB | **measured**: 1,183 bytes on average, same week |
| Bronze growth at launch | 100,000 × 320 × 1.2 KB ≈ **38 GB per week** | computed from H2 and the two lines above |
| Listens without a MusicBrainz id | about 12 % | **measured**: 964 of 8,001, same week |
| Freshness | Playlist ready Monday 08:00 Europe/Paris, built from listens up to Sunday 23:59:59 UTC | Product service target, not yet a measured SLA |
| Playlist size | 10 distinct artists, one representative recording per artist | Agreed prototype convention; `playlist_size=10` |
| MusicBrainz API | 1 request per second | MusicBrainz rate-limiting rules |
| Latency needed | one week: a **weekly batch**, no streaming | product definition |

## 3. Use case sheet: weekly "New Vibes" playlist

| Item | Content |
|---|---|
| Decision | **Automatic, every Monday:** rank 10 artists for each user's playlist for week W through co-listening. **Human, every week:** the head of product reviews the comparison with popularity and decides the next product action |
| Decision rule | Accept co-listening's business value only if `HIT_RATE_S1 ≥ HIT_RATE_BASELINE_S1` on the evaluated weeks. Failure requires a human decision; automatic switching to the popularity baseline is not implemented |
| Users | Listener (playlist), head of product (metrics) |
| Inputs | `BRONZE.LISTENS_RAW` (who listened to what, when), `MB_ARTISTS_RAW` (artist identity, Wikidata link), `WIKI_PAGEVIEWS_RAW` (retrospective English Wikipedia attention proxy, with coverage reported) |
| Outputs | `GOLD.PLAYLIST_HEBDO`, `GOLD.METRICS_HEBDO` (contracts in AGENTS.md) |
| Frequency | Weekly. Week W = Monday 00:00 UTC to the next Monday 00:00 UTC |

### Metrics (`GOLD.METRICS_HEBDO`, grain: one row per `WEEK_START`)

The playlist of week W is built only from listens **before** W, and judged on listens **during** W (the "S+1" week
relative to the data used). The following definitions align with Hugo's Wikipedia and discovery work,
integrated in main through PR11 (`f80d0f6`). These are agreed conventions, rather than claims of causality.

| Column | Formula | Exclusions |
|---|---|---|
| `USERS_EVALUATED` | Users with a playlist for W **and** at least one mapped listen during W | Users without listens during W; manual profiles |
| `HIT_RATE_S1` | Evaluated users who listened during W to at least one artist of their playlist ÷ `USERS_EVALUATED` | Listens without a MusicBrainz artist id |
| `HIT_RATE_BASELINE_S1` | Same formula and evaluated users, with up to 10 artists ranked by distinct listeners before W, excluding artists already known to each user | Same |
| `DISCOVERY_RATE` | Distinct mapped listens during W by evaluated users for which **all** mapped artists are absent from that user's history before W ÷ all their distinct mapped listens during W | Unmapped listens; each multi-artist listen counts once |
| `LESSER_KNOWN_RATE` | Distinct recommended artists with fewer than 1,000 English Wikipedia pageviews during W ÷ distinct recommended artists with seven observed days during W | Missing or partial Wikipedia weeks; NULL if none are covered |
| `WIKI_COVERAGE_RATE` | Distinct recommended artists with seven observed Wikipedia days during W ÷ all distinct recommended artists for W | An artist appearing in several users' playlists counts once |
| `LESSER_KNOWN_PAGEVIEWS_THRESHOLD` | Configurable exploratory threshold; default 1,000 via `lesser_known_pageviews_threshold` | Strictly fewer than the threshold qualifies |
| `LAST_LOADED_AT` | `MAX(_LOADED_AT)` of the bronze listens at build time, as currently implemented | A load timestamp, not a guarantee that every source is complete |

An artist hit (not a track hit): with about 320 listens a week, the exact recording is too rare to measure anything.

### Multi-artist listens and Wikipedia conventions

An artist association is expanded for co-listening, but an individual listen is identified by `listen_key`
and counted once for `DISCOVERY_RATE`. A listen featuring a known artist and an unknown artist is **not**
classified as a new discovery. A hit may match any mapped artist on the listen. Discovery describes observed
listening; it does not show that the playlist caused the listener to discover an artist.

Wikipedia days are deduplicated by artist and UTC date, then summed by artist and Monday-based UTC week.
Only valid non-negative daily values are included. Seven observed days are required for the notoriety
denominator; missing or partial observations do not become zero views. The threshold of 1,000 weekly views
is an exploratory English-language attention proxy, not a universal definition of an unknown artist.
The metric uses week W retrospectively and does not alter recommendation scores or ranking.

Always publish `LESSER_KNOWN_RATE` with `WIKI_COVERAGE_RATE`: low coverage can bias the subset being measured.
With no covered recommended artist, lesser-known rate is NULL and coverage is zero when recommendations exist.
If there are no recommended artists, the denominator is empty and a NULL coverage must not be reported as zero.

### Acceptance tests

| # | Test | Pass when |
|---|---|---|
| A1 | Rerun ingestion of a week | Bronze row counts per file unchanged, 0 duplicate listen (`ingestion/README.md`) |
| A2 | Freshness | `LAST_LOADED_AT` less than 24 h before the Monday run |
| A3 | Playlist shape | Each eligible user has positions 1 to 10, 10 distinct artists and no duplicate recording, with no artist from their observed history before W; a shorter playlist must be reported as incomplete |
| A4 | Value | On the evaluated weeks, `HIT_RATE_S1 ≥ HIT_RATE_BASELINE_S1`; otherwise value is not demonstrated and the head of product must decide the next action. No automatic baseline switch is implemented |

## 4. Prototype evidence (2026-11-03)

The manual GCS-to-Snowflake load and replay were executed on `VAYBA.BRONZE`, with
`YANIS_RAJHI` / `VAYBA_YANIS`. For week 2026-10-26, both runs returned:

| Source | Rows | Files | Duplicates after replay |
|---|---:|---:|---:|
| ListenBrainz | 8,003 | 25 | 0 |
| MusicBrainz | 1,580 | 1,580 | 0 |
| Wikipedia pageviews | 1,234 | 1,234 | 0 |

Counts and `HASH_AGG(RAW, _SOURCE_FILE)` stayed unchanged. This validates A1 for these frozen files,
not the Airflow replay or a fresh extraction from a changing API. Full query IDs and screenshots are in
`docs/evidence/2026-11-03_three_sources_replay.json` and the corresponding images.

On this local extract, 965 of 8,003 listens have no artist mapping (12.06%). Among 1,278 artists with a
Wikidata link, 1,234 have pageviews for each of the seven days (96.56%). This extraction coverage uses artists
with a Wikidata link as its denominator; it is distinct from recommendation-level `WIKI_COVERAGE_RATE`.
These are sample measurements,
not population estimates. An artist absent from the observed history is not necessarily an artist the user
has never heard in their lifetime.

A2-A4 were not established by this first single-week ingestion proof. A valid S+1 evaluation needs training
data before the target week and a complete evaluation week; the later measurements are described below.
The commercial model is B2C. The implemented prototype uses the three public APIs, as described below.
Hashing user names from silver
pseudonymizes identifiers; it does not by itself guarantee anonymity.

### Two-week extension and measured local S+1 result

The final frozen input now includes the complete weeks of October 19 and October 26:
16,447 listens and 2,478 artists, plus the same 1,234 Wikipedia documents for October 26.
Both manual Snowflake runs produced identical business content hashes and zero duplicates.
The earlier table remains the first, single-week snapshot.

Hugo PR4 (`cd28e33`) was built locally on these real extracts with training starting October 19,
target week October 26, and evaluation ending November 2: 12 models, 13 tests and the hook passed.
For 25 evaluated users, hit rate was **48% versus 56% for popularity**. A4 is therefore **not met on this
sample**: no superiority or recommendation gain is demonstrated. The ranking remains co-listening;
automatic switching to the popularity baseline is not implemented. This local result is not a production dbt result.

The build produced 250 playlist rows (10 per user), consistent with the agreed size. Its historical
discovery rate of 100% measured recommended artists absent from history, which holds by construction.
That number is superseded by the listening-based definition above and must not be used for the new metric.
The dated evidence files are preserved as historical records of that version.

### Updated discovery and Wikipedia evidence from Hugo

Hugo's `part2/wiki-discovery` revision `c002a7e` consumes Wikipedia in dbt and reports, for the same 25 users
and 250 recommendations: discovery **38.1643%**, lesser-known rate **1.1364%** (1 of 88 distinct recommended
artists), and Wikipedia coverage **100%** (88 of 88 artists with seven observed days). The threshold is
1,000 weekly English Wikipedia pageviews. Hit rate remains **48% versus 56%** for popularity.

Sources on that revision:
[Wikipedia metrics](https://github.com/Elimane29/vayba-data-platform/blob/c002a7e/dbt/evidence/wiki_cloud_metrics.json)
and [final cloud checks](https://github.com/Elimane29/vayba-data-platform/blob/c002a7e/dbt/evidence/final_cloud_checks.json).
The latter distinguishes a successful development dbt build from publication of two compiled models in
shared GOLD; that publication is not a new complete production dbt/Airflow run. Its incident proof concerns
isolated `DEV_HUGO_INCIDENT_*` schemas. The separate full Airflow run and replay are documented below.
These are Hugo's recorded executions, reviewed for this document; they were not rerun by Yanis.

### Production run and replay evidence reviewed on November 4

Elimane's `docs/evidence/2026-11-03_airflow_run.md` and `docs/runbook.md` now document a successful production
run and replay: 16,447 listens, zero duplicates, `PASS=26`, 14,472 silver listens and 250 playlist rows.
The run is `scheduled__2026-11-02T05:00:00+00:00`; its replay is
`manual__2026-11-03T19:57:29.316849+00:00`. The three ingestion tasks and dbt completed successfully.
Denied-access checks are separately recorded in `dbt/evidence/final_cloud_checks.json` and
`dashboard/evidence/checks.json`.

These records certify their dated runs and model versions. The newer Wikipedia metrics and explanation
changes have their own development/publication evidence; `PASS=26` must not be relabelled as a full Airflow
run of the newer 28-result development version. The earlier 100% discovery value in the original run is
historical, and is superseded by the listening-based 38.1643% definition above.

### Source choice for the implemented prototype

The prototype uses ListenBrainz's API for a fixed sample of 25 public profiles and two completed UTC weeks,
MusicBrainz's API for artist metadata, and the Wikimedia APIs for article resolution and daily pageviews.
API responses are preserved as NDJSON in GCS for loading and replay. This supports a small, inspectable
weekly prototype without downloading a complete listening corpus.

Incremental dumps remain an alternative for larger historical backfills. No dump ingestion benchmark was
executed in this prototype, and API data should not be presented as a dump extract. The sample is small and
not representative; API rate limits, transient failures, late listens, missing artist mappings and incomplete
Wikipedia coverage constrain the results. Subscription price and conversion are assumptions, since these
sources contain no premium-conversion data.
