# dbt — nettoyage, recommandations et qualité

Mise à jour du 3 novembre 2026 : Wikipédia est consommé par dbt depuis BRONZE.WIKI_PAGEVIEWS_RAW. Le modèle silver_wiki_pageviews extrait l'identifiant MusicBrainz du chemin source, déplie les jours, conserve une valeur par artiste et jour après dédoublonnage déterministe, puis totalise les pages vues par artiste et semaine UTC. observed_days distingue les semaines complètes des données partielles.

DISCOVERY_RATE suit désormais le document métier : parmi les écoutes mappées de la semaine des utilisateurs évalués, part des écoutes dont tous les artistes sont absents de l'historique avant cette semaine. Une écoute multi-artistes compte une seule fois ; si un artiste est déjà connu, elle n'est pas nouvelle. Les utilisateurs évalués doivent avoir une playlist et des écoutes pendant la semaine. Ce taux décrit les écoutes observées, sans attribuer leur découverte à la recommandation.

LESSER_KNOWN_RATE mesure la part d'artistes recommandés distincts ayant moins de 1 000 pages vues sur Wikipédia en anglais pendant la semaine évaluée. Ce seuil exploratoire est configurable par lesser_known_pageviews_threshold. Seuls les artistes avec sept jours observés entrent dans ce dénominateur. WIKI_COVERAGE_RATE rapporte ce dénominateur à tous les artistes recommandés distincts. Les données absentes ne valent jamais zéro. Sans couverture, le premier taux reste NULL. Cette mesure rétrospective ne modifie pas le classement des recommandations.

La validation réelle utilise l'historique du 19 au 25 octobre, la semaine cible du 26 octobre et une fin de validation au 2 novembre exclu, avec 10 artistes par playlist. Le build Snowflake dans DEV_HUGO_FINAL produit 28 résultats sans erreur. Sur 25 utilisateurs : 250 recommandations, hit rate de 48 % contre 56 % pour la popularité, découverte de 38,1643 %, faible notoriété de 1,1364 % et couverture Wikipédia de 100 %. La faible notoriété correspond à un artiste sur 88 artistes distincts recommandés. Le seuil ne constitue pas une définition universelle d'un artiste peu connu.

Les tests calculés à la main vérifient le dédoublonnage Wikipédia, les écoutes multi-artistes, la couverture partielle et les valeurs manquantes. Dans des copies Snowflake DEV_HUGO_INCIDENT, no_unknown_artists passe, échoue après suppression d'une référence artiste, puis repasse après restauration. La production n'est pas modifiée par cet incident.

Dash lit VAYBA.GOLD avec VAYBA_GOLD_SCHEMA=GOLD, le rôle VAYBA_DASH_READ et les rôles secondaires désactivés. Le compte technique du prototype possède un autre rôle pour dbt ; un déploiement autonome doit avoir un utilisateur dédié à l'application. Le rôle Dash n'a accès ni au Bronze ni à l'écriture Gold.

À transmettre à Yanis : aligner docs/business.md sur les playlists de 10 artistes, conserver la nouvelle définition de DISCOVERY_RATE et ajouter les conventions sur les écoutes multi-artistes, le seuil Wikipédia et sa couverture. Le résultat 48 % contre 56 % ne satisfait pas la règle métier de supériorité sur la popularité. Le classement reste celui de la co-écoute : le basculement automatique vers la popularité n'est pas implémenté et ne doit pas être présenté comme réalisé.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install dbt-core==1.11.16 dbt-snowflake==1.11.6 -r dbt/requirements-local.txt
gzip -dc tests/fixtures/listens_raw.jsonl.gz > tests/fixtures/listens_raw.jsonl
gzip -dc tests/fixtures/mb_artists_raw.jsonl.gz > tests/fixtures/mb_artists_raw.jsonl
python dbt/tools/load_fixtures.py --fixtures tests/fixtures
dbt build --project-dir dbt --profiles-dir dbt --target local
python dbt/tools/check_pipeline.py --fixtures tests/fixtures

python dbt/tools/check_wiki_metrics.py
export SNOWFLAKE_ACCOUNT="<organisation-compte>"
export SNOWFLAKE_USER="VAYBA_DBT_HUGO"
export SNOWFLAKE_ROLE="VAYBA_DBT_HUGO_ROLE"
export SNOWFLAKE_WAREHOUSE="VAYBA_WH"
export SNOWFLAKE_PRIVATE_KEY_FILE="/chemin/local/cle.p8"
export VAYBA_DEV_SCHEMA="DEV_HUGO_DBT"
dbt build --project-dir dbt --profiles-dir dbt --target dev

python dbt/tools/check_targets.py
export SNOWFLAKE_USER=ELIMANE_DIALLO
export SNOWFLAKE_PRIVATE_KEY_FILE="/chemin/local/cle-elimane.p8"
export SNOWFLAKE_ROLE=VAYBA_ELIMANE
export SNOWFLAKE_WAREHOUSE=VAYBA_WH
dbt build --project-dir dbt --profiles-dir dbt --target prod --vars '{"history_start":"2026-10-19","week_start":"2026-10-26","test_end":"2026-11-02"}'
```


Révision du 4 novembre 2026 : neighbors choisit comme raison l'artiste commun le plus écouté par l'auditeur dans son historique avant la semaine cible. En cas d'égalité, les écoutes du voisin puis l'identifiant MusicBrainz départagent les candidats de façon stable. La similarité de Jaccard et le classement des recommandations restent inchangés.

Le test calculé à la main couvre le choix de l'artiste, le sens de la relation entre auditeurs et les égalités. Le build Snowflake dans DEV_HUGO_REASONS passe avec 28 résultats sans erreur. La comparaison avec la version validée de PR #11 confirme 250 recommandations identiques pour les artistes, morceaux, positions et scores ; seules 153 raisons changent. Toutes les métriques sont inchangées. Une même raison peut encore apparaître plusieurs fois lorsqu'un artiste domine l'historique commun. Le correctif ne force pas la diversité des explications. Aucun nouveau run de production Airflow n'est revendiqué pour cette correction.
