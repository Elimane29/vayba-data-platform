# dbt — nettoyage, recommandations et qualité

## Résultat vérifié le 2 novembre 2026

Le lancement réussi de dbt Core 1.11.16 avec l'adaptateur Snowflake 1.11.6 a abouti à 12 modèles, 13 tests et une journalisation sans erreur. Un second lancement a produit exactement les mêmes playlists et métriques. Les preuves sont disponibles à `evidence/cloud_dbt_build.json`, `cloud_dbt_results.json` et `cloud_dbt_replay.json`.

La source reste `VAYBA.DEV_HUGO_BRONZE`. Les résultats validés de ce lancement sont disponibles à `VAYBA.DEV_HUGO_DBT_SILVER`, `DEV_HUGO_DBT_GOLD` et `DEV_HUGO_DBT_OPS`. Les fichiers ont été chargés manuellement dans Snowflake : le passage par GCS et le lancement Airflow restent à valider avec Yanis et Elimane. Les exécutions SQL manuelles précédentes dans `DEV_HUGO_*` sont conservées comme preuves distinctes.

## Exécution locale depuis la racine du dépôt

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install dbt-core==1.11.16 dbt-snowflake==1.11.6 -r dbt/requirements-local.txt
gzip -dc tests/fixtures/listens_raw.jsonl.gz > tests/fixtures/listens_raw.jsonl
gzip -dc tests/fixtures/mb_artists_raw.jsonl.gz > tests/fixtures/mb_artists_raw.jsonl
python dbt/tools/load_fixtures.py --fixtures tests/fixtures
dbt build --project-dir dbt --profiles-dir dbt --target local
python dbt/tools/check_pipeline.py --fixtures tests/fixtures
```

Le dossier doit contenir `listens_raw.jsonl` et `mb_artists_raw.jsonl`. Ne pas ajouter la copie identique du fichier d’écoutes. Les clés privées, fichiers `.env`, bases DuckDB et dossiers `target/` et `logs/` restent locaux.

## Exécution Snowflake

Chaque membre utilise une connexion autorisée et une clé privée conservée localement. Pour le compte technique configuré par Hugo, définir les variables suivantes, puis exécuter dbt. Ne jamais envoyer la clé privée dans GitHub ou un chat.

```bash
export SNOWFLAKE_ACCOUNT="<organisation-compte>"
export SNOWFLAKE_USER="VAYBA_DBT_HUGO"
export SNOWFLAKE_ROLE="VAYBA_DBT_HUGO_ROLE"
export SNOWFLAKE_WAREHOUSE="VAYBA_WH"
export SNOWFLAKE_PRIVATE_KEY_FILE="/chemin/local/cle.p8"
export VAYBA_DEV_SCHEMA="DEV_HUGO_DBT"
dbt build --project-dir dbt --profiles-dir dbt --target dev
```

Le préfixe de développement est configurable par `VAYBA_DEV_SCHEMA`; son défaut reste `DEV_HUGO`. La source bronze se configure avec la variable dbt `bronze_schema`, dont le défaut est `DEV_HUGO_BRONZE`. Le journal d’exécution est écrit dans le schéma OPS correspondant au préfixe. Les tables partagées `BRONZE`, `SILVER` et `GOLD` ne sont pas publiées par cette commande.

## Règles de transformation

L'utilisateur est lu dans `RAW:user_name`, ou à défaut dans le chemin `listenbrainz/week=YYYY-MM-DD/user=<nom>.json` produit par Yanis. Sans identifiant exploitable, l'écoute reste en quarantaine. Les utilisateurs et chemins sources sont pseudonymisés par SHA-256; cela ne garantit pas l'anonymat. La clé d'écoute repose sur utilisateur, secondes Unix et `recording_msid`. Le dédoublonnage est déterministe. La liste d'artistes est dépliée dans une table de liaison : compter les écoutes dans `silver_listens`, pas dans cette liaison. Une référence MusicBrainz inconnue fait échouer un test.

La co-écoute utilise la similarité de Jaccard entre ensembles d'artistes. Les candidats sont classés par somme des similarités, avec la popularité en secours. Les artistes déjà connus sont exclus. Un morceau représentatif et un artiste partagé expliquent chaque proposition. Les départages sont déterministes. Le calcul des voisins est quadratique : adapté au prototype, il devra être revu à grande échelle.

## Évaluation et limites

Les paramètres par défaut sont : historique du 21 septembre au 25 octobre 2026, recommandations pour la semaine du 26 octobre, validation jusqu’au 2 novembre exclu, 10 titres au maximum par profil. Toutes les bornes sont en UTC et paramétrées par le run. La taille se règle avec `playlist_size`; le choix de 10 ou 20 titres reste à confirmer avec Yanis.

Le hit rate S+1 mesure la proportion de profils éligibles ayant écouté au moins un artiste recommandé pendant la validation. La popularité utilise le même dénominateur et la même taille maximale, en excluant aussi les artistes connus. Le taux de découverte actuellement calculé mesure la part des artistes recommandés absents de l'historique observé; il vaut donc 100 % par construction et ne mesure pas la satisfaction. La définition finale de cette métrique reste à harmoniser avec Yanis.

Résultats : 6652 écoutes bronze, 915 artistes, 6125 écoutes silver, 527 écoutes en quarantaine, 6615 liens écoute-artiste et 40 recommandations. Sur quatre profils et une semaine, le hit rate vaut 0,75 contre 0,50 pour la popularité. Ces résultats ne prouvent pas une supériorité générale.

Les contrôles locaux couvrent le rejeu, les fichiers API sans utilisateur dans RAW, l'absence de fuite temporelle, un exemple calculé à la main et un échec volontaire de `no_unknown_artists`. Les genres et les profils manuels restent à intégrer. Le chargeur manuel Snowflake respecte les quatre colonnes bronze, mais sa commande cloud n'a pas été exécutée : le chargement réalisé utilisait Snowsight.
