# Transmission Yanis — 3 novembre 2026

## Partie ingestion exécutée

Les vraies données API sont dans le bucket `vayba-elimane-2026-landing`, puis dans `VAYBA.BRONZE`.
Deux chargements manuels Snowsight sont validés avec `VAYBA_YANIS` : mêmes comptes et mêmes
`HASH_AGG(RAW, _SOURCE_FILE)`, aucun doublon. Les métadonnées de chargement sont exclues du hash.

| Source | Lignes | Fichiers | Périmètre |
|---|---:|---:|---|
| ListenBrainz | 16 447 | 50 | 19–25 et 26 oct.–1 nov. |
| MusicBrainz | 2 478 | 2 478 | Union des artistes des deux semaines |
| Wikipedia | 1 234 | 1 234 | 26 oct.–1 nov., 7 jours par document |

Requêtes de chargement : `01c8296b-040c-c63d-0034-1e6b0018611e` puis
`01c8296c-040c-c63f-0034-1e6b00185172`. Les scripts et preuves sont dans `ingestion/sql/` et `docs/evidence/`.
Il s'agit du rejeu manuel des fichiers figés ; une nouvelle extraction API peut légitimement changer les volumes.

## Reprise de la partie Hugo

PR4 `cd28e33` testée dans un worktree isolé, sans modifier son code : build dbt local réussi sur ses fixtures,
contrôles de rejeu/fuite temporelle/incident de référence manquante réussis. Build supplémentaire sur nos vraies
données réussi : 12 modèles, 13 tests et un hook, aucune erreur. Ces preuves locales ne certifient pas la production.

Le contrôle `check_targets.py` échoue sous Windows car il cherche `/gold/` dans des chemins avec antislash.
Le correctif proposé utilise `'gold' in Path(node['original_file_path']).parts` ; la copie diagnostique passe les
contrôles prod/dev/local sans se connecter à Snowflake. Le patch est fourni séparément, la PR Hugo reste inchangée.

Mesure locale S+1 : 25 utilisateurs, hit rate 48 %, référence popularité 56 %, découverte 100 %.
**Aucun gain démontré : A4 non satisfait sur cet échantillon.** Appliquer la règle de repli popularité ou revoir
le choix avec l'équipe. 250 recommandations produites, soit 10 par utilisateur ; le document métier en prévoit 20.
1 975 écoutes sont en quarantaine locale. Wikipedia est disponible en bronze, sans modèle dbt consommateur actuel.

## Suite à faire avec Hugo et Elimane

1. Relire puis fusionner leurs changements et la branche Yanis `part1/real-data-validation`.
2. Reconstruire l'image et utiliser exactement les dates suivantes pour ces données :

```json
{"history_start":"2026-10-19","week_start":"2026-10-26","test_end":"2026-11-02"}
```

3. Lancer dbt en production avec le rôle prévu, puis Airflow, son rejeu et un incident contrôlé ; conserver les
   identifiants et sorties. Aucun de ces builds/rejeux prod n'a été lancé par cette session.
4. Aligner la taille de playlist, décider le repli popularité et confirmer le choix commercial et API/dumps.
5. Intégrer les cinq slides Yanis au support commun, puis répéter l'oral.

Le PowerPoint fourni décrit explicitement le premier instantané validé (8 003 écoutes / 1 580 artistes, semaine du
26 octobre). Les volumes finaux ci-dessus incluent une semaine historique ajoutée pour permettre le test S+1.
Ne pas présenter les mesures locales comme des mesures Snowflake de production.
