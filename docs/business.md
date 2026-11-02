# Vayba: business case and use case sheet

Vayba is a fictional music streaming company. **Promise:** helping people look for new vibes.
**Product:** every Monday, one "New Vibes" playlist per user, made of artists they have never listened to,
picked from what people with a similar taste listen to (co-listening).

Every number below is either **measured** on our real data (with its source) or an **assumption** (H1, H2…)
that we state as such. Nothing here is a real company figure.

## 1. Business model

**Open decision (AGENTS.md):** B2B, recommended, or B2C. Both are written down so the team can choose; the use case
sheet in section 3 is the same in both cases.

| | B2B (recommended) | B2C |
|---|---|---|
| Customer | Small music apps and web radios that have listeners but no recommendation team | Listeners |
| Offer | White-label "New Vibes" playlist for each of their users, delivered weekly | Free tier + premium subscription |
| Revenue (assumption) | H1: €0.05 per monthly active user per month | H1': premium €9.99 per month, 5 % of users convert |
| Size at launch (assumption) | H2: 10 partner apps × 10,000 users = 100,000 users | H2': 100,000 users |
| Monthly revenue | 100,000 × €0.05 = **€5,000** | 100,000 × 5 % × €9.99 = **€49,950** |
| Why | Fewer customers, no consumer marketing, the data product *is* what is sold | Bigger revenue, but a consumer app to build and market |

## 2. Stakeholders and constraints

| Stakeholder | Interest | What they receive |
|---|---|---|
| Listener | Discover artists they like | Their playlist (Dash, view "playlist") |
| Head of product | Decide whether co-listening is worth it compared with a simple popularity list | `METRICS_HEBDO` (Dash, view "metrics") |
| Partner app (B2B) | Engagement of its users, a weekly delivery it can rely on | Playlists by Monday 08:00 |
| Data team | A pipeline that can be rerun and explained | Yanis: ingestion · Hugo: dbt, tests, app · Elimane: Airflow, Terraform, incidents |
| DPO | Listening history is personal data (GDPR) | User names hashed from silver onwards, only `GOLD` exposed |

| Constraint | Value | Source |
|---|---|---|
| Listens per user per week | about 350 | **measured**: 1,411 listens for 4 users, week 2026-10-26 |
| Raw size of one listen | about 1.4 KB | **measured**: 9.2 MB for 6,652 listens (extract of 2026-11-02) |
| Bronze growth at launch | 100,000 × 350 × 1.4 KB ≈ **49 GB per week** | computed from H2 and the two lines above |
| Listens without a MusicBrainz id | about 8 % | **measured**: 527 of 6,652 |
| Freshness | Playlist ready Monday 08:00 Europe/Paris, built from listens up to Sunday 23:59:59 UTC | H3 |
| Playlist size | 20 tracks | H4 |
| MusicBrainz API | 1 request per second | MusicBrainz rate-limiting rules |
| Latency needed | one week: a **weekly batch**, no streaming | product definition |

## 3. Use case sheet: weekly "New Vibes" playlist

| Item | Content |
|---|---|
| Decision | **Automatic, every Monday:** which 20 tracks go into each user's playlist for week W. **Human, every week:** the head of product keeps co-listening or falls back to the popularity list |
| Decision rule | Keep co-listening while `HIT_RATE_S1 ≥ HIT_RATE_BASELINE_S1` on the evaluated weeks |
| Users | Listener (playlist), head of product (metrics) |
| Inputs | `BRONZE.LISTENS_RAW` (who listened to what, when), `MB_ARTISTS_RAW` (artist identity, Wikidata link), `WIKI_PAGEVIEWS_RAW` (how mainstream an artist is) |
| Outputs | `GOLD.PLAYLIST_HEBDO`, `GOLD.METRICS_HEBDO` (contracts in AGENTS.md) |
| Frequency | Weekly. Week W = Monday 00:00 UTC to the next Monday 00:00 UTC |

### Metrics (`GOLD.METRICS_HEBDO`, grain: one row per `WEEK_START`)

The playlist of week W is built only from listens **before** W, and judged on listens **during** W (the "S+1" week
relative to the data used). Definitions to confirm with Hugo before he implements them.

| Column | Formula | Exclusions |
|---|---|---|
| `USERS_EVALUATED` | Users with a playlist for W **and** at least one mapped listen during W | Users without listens during W; manual profiles |
| `HIT_RATE_S1` | Evaluated users who listened during W to at least one artist of their playlist ÷ `USERS_EVALUATED` | Listens without a MusicBrainz artist id |
| `HIT_RATE_BASELINE_S1` | Same formula, with the baseline playlist instead: the 20 artists with the most distinct listeners before W, minus artists the user already knows | Same |
| `DISCOVERY_RATE` | Listens during W by evaluated users of artists absent from their history before W ÷ all their mapped listens during W | Same |
| `LAST_LOADED_AT` | `MAX(_LOADED_AT)` of the listens used for W | — |

An artist hit (not a track hit): with about 350 listens a week, the exact recording is too rare to measure anything.

### Acceptance tests

| # | Test | Pass when |
|---|---|---|
| A1 | Rerun ingestion of a week | Bronze row counts per file unchanged, 0 duplicate listen (`ingestion/README.md`) |
| A2 | Freshness | `LAST_LOADED_AT` less than 24 h before the Monday run |
| A3 | Playlist shape | Each user of the week has positions 1 to 20, no duplicate recording, no artist from their history before W |
| A4 | Value | On the evaluated weeks, `HIT_RATE_S1 ≥ HIT_RATE_BASELINE_S1`; otherwise the decision rule says: fall back to popularity |
