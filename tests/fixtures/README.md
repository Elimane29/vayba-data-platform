# Extrait réel ListenBrainz + MusicBrainz (fixture pour dbt)

Extrait le 2026-11-02, batch `fixture-2026-11-02`. Données réelles, API publiques, aucune clé.

| Fichier | Lignes | Table bronze visée |
|---|---|---|
| `listens_raw.jsonl.gz` | 6 652 écoutes | `VAYBA.BRONZE.LISTENS_RAW` |
| `mb_artists_raw.jsonl.gz` | 915 artistes | `VAYBA.BRONZE.MB_ARTISTS_RAW` |

Une ligne = une ligne bronze du contrat : `RAW` (document source intact), `_SOURCE_FILE`, `_BATCH_ID`, `_LOADED_AT`.
`_SOURCE_FILE` reprend le chemin prévu dans GCS (`listenbrainz/week=<lundi>/user=<nom>.json`, `musicbrainz/artist/<mbid>.json`).
Dans le vrai pipeline il viendra de `METADATA$FILENAME`.

## Périmètre

4 utilisateurs ListenBrainz, 6 semaines complètes en UTC, du lundi 2026-09-21 au dimanche 2026-11-01.

| Utilisateur | 09-21 | 09-28 | 10-05 | 10-12 | 10-19 | 10-26 |
|---|---|---|---|---|---|---|
| Mergzo | 240 | 316 | 236 | 244 | 152 | 232 |
| frankpanduh | 1 | 2 | 83 | 50 | 351 | 440 |
| jwheel | 178 | 266 | 276 | 445 | 500 | 333 |
| zzzach | 408 | 436 | 420 | 280 | 357 | 406 |

Artistes en commun (paires) : 8 à 34. Proposition : semaines 09-21 → 10-19 pour construire, **semaine 10-26 = S+1** pour évaluer.
frankpanduh n'écoute presque rien les 2 premières semaines : bon cas d'utilisateur « froid ».

## Où sont les champs (syntaxe Snowflake)

| Besoin | Champ |
|---|---|
| Utilisateur | `RAW:user_name` (pseudo public ListenBrainz, à hasher en silver) |
| Date d'écoute | `RAW:listened_at`, secondes Unix UTC → `TO_TIMESTAMP_TZ(RAW:listened_at::NUMBER)` |
| Morceau (nom) | `RAW:track_metadata.track_name` |
| Morceau (ID) | `RAW:track_metadata.mbid_mapping.recording_mbid` (6 134 écoutes sur 6 652) |
| Artiste (nom affiché) | `RAW:track_metadata.artist_name` |
| Artiste (IDs, **clé de jointure**) | `RAW:track_metadata.mbid_mapping.artist_mbids` : **tableau**, 405 écoutes ont plusieurs artistes → `LATERAL FLATTEN` |
| Clé unique d'une écoute | `user_name` + `listened_at` + `recording_msid` (0 doublon dans l'extrait) |
| Artiste MusicBrainz | `RAW:id` (= le MBID), `RAW:name`, `RAW:type`, `RAW:country` |
| Lien Wikidata | `RAW:relations[]` où `type = 'wikidata'` → `url.resource` (788 artistes sur 915) |

**Jointure** : `mbid_mapping.artist_mbids[i] = MB_ARTISTS_RAW.RAW:id`. Toutes les écoutes qui ont un `mbid_mapping` trouvent leurs artistes (6 125).

## Ce qui est sale exprès (c'est réel)

- 527 écoutes (7,9 %) sans `mbid_mapping` : pas d'ID d'artiste ni de morceau → quarantaine « non reliée ».
- `additional_info` dépend du lecteur de musique de l'utilisateur : ne pas s'y fier, utiliser `mbid_mapping`.
- Les genres MusicBrainz ne sont **pas** inclus (licence non CC0, cf. AGENTS.md).

## Charger dans Snowflake (non testé)

```sql
CREATE FILE FORMAT IF NOT EXISTS FF_JSONL TYPE = JSON;
CREATE STAGE IF NOT EXISTS FIXTURE_STAGE FILE_FORMAT = FF_JSONL;
-- depuis SnowSQL : PUT file://listens_raw.jsonl.gz @FIXTURE_STAGE AUTO_COMPRESS = FALSE;
CREATE TABLE IF NOT EXISTS LISTENS_RAW (RAW VARIANT, _SOURCE_FILE VARCHAR, _BATCH_ID VARCHAR, _LOADED_AT TIMESTAMP_TZ);
COPY INTO LISTENS_RAW
FROM (SELECT $1:RAW, $1:_SOURCE_FILE::VARCHAR, $1:_BATCH_ID::VARCHAR, $1:_LOADED_AT::TIMESTAMP_TZ
      FROM @FIXTURE_STAGE/listens_raw.jsonl.gz);
-- idem pour MB_ARTISTS_RAW avec mb_artists_raw.jsonl.gz
```

## Refaire l'extrait

Avec l'ingestion de la partie 1, semaine par semaine du 2026-09-21 au 2026-10-26 :
`python ingestion/run.py --source listenbrainz --week 2026-09-21 --no-load`, puis `--source musicbrainz`.
Les documents `RAW` sont les mêmes ; les fichiers arrivent dans `data/landing/`.
