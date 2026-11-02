# Hugo — bronze de développement, silver et recommandations

## Statut

Les modèles et les tests ont été exécutés sur les deux extraits réels de Yanis avec dbt Core 1.11 et DuckDB. Le 2 novembre 2026, les 12 modèles SQL ont également été exécutés manuellement dans Snowsight sur VAYBA_WH. Les sept contrôles SQL cloud et les quatre comparaisons de rejeu ont tous retourné zéro anomalie. Le lancement de dbt Core contre Snowflake n'a pas encore été exécuté; le passage par GCS reste à intégrer. Le chargeur Snowflake utilise un stage interne pour ces extraits : il ne remplace pas l'ingestion GCS de Yanis.

Le défaut est `local`. La cible Snowflake `dev` écrit dans `VAYBA.DEV_HUGO_SILVER`, `DEV_HUGO_GOLD` et `DEV_HUGO_OPS`, sans toucher aux schémas partagés. La source bronze est `DEV_HUGO_BRONZE`; pour utiliser le bronze validé de Yanis, passer `--vars '{"bronze_schema":"BRONZE"}'`.

## Installer et exécuter depuis la racine du dépôt

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r dbt/requirements-local.txt
.venv/bin/python dbt/tools/load_fixtures.py --fixtures /chemin/vers/les/fichiers
DBT_SEND_ANONYMOUS_USAGE_STATS=false .venv/bin/dbt build --project-dir dbt --profiles-dir dbt --target local
.venv/bin/python dbt/tools/check_pipeline.py --fixtures /chemin/vers/les/fichiers
```

Le dossier des fichiers doit contenir `listens_raw.jsonl` et `mb_artists_raw.jsonl`. Le second fichier d'écoutes téléchargé est une copie identique : ne pas l'ajouter. Les données brutes, la base `.duckdb`, les clés, `.env`, `target/` et `logs/` restent locaux. Aucun téléchargement n'est effectué par les scripts.

## Modèle et règles

- `listens_checked` : utilisateur lu dans `RAW:user_name`, ou à défaut dans le chemin `listenbrainz/week=YYYY-MM-DD/user=<nom>.json` produit par Yanis. Un nom absent des deux emplacements reste en quarantaine. Clé SHA-256 sur utilisateur + secondes Unix + recording_msid; tri de dédoublonnage déterministe. Pseudonymisation SHA-256 de l'utilisateur et du chemin source. Il s'agit de pseudonymisation, pas d'anonymisation garantie.
- `listens_quarantine` : données invalides avec motif. Les écoutes sans identifiant d'artiste sont rejetées; pas de rapprochement approximatif sur les noms.
- `silver_listens` : une ligne par écoute. Conversion des secondes Unix explicitement en UTC.
- `listen_artists` : une ligne par écoute et artiste, après dépliage de la liste. Compter les écoutes dans `silver_listens`, pas dans cette table de liaison.
- `silver_artists` : une ligne par identifiant MusicBrainz. Les références inconnues provoquent un échec de qualité.
- `train_listens`, `user_artists` : historique antérieur à la date de recommandation.
- `neighbors` : Jaccard sur les ensembles d'artistes des utilisateurs, sans utiliser la période de validation.
- `ranked_artists` : somme des similarités des voisins écoutant un artiste; exclusion des artistes connus. Classement populaire en secours, après les candidats par co-écoute. Départages déterministes par identifiant.
- `PLAYLIST_HEBDO` : jusqu'à 10 artistes; un morceau représentatif issu uniquement de l'historique de construction par artiste. L'explication cite un artiste partagé avec un voisin contributeur.
- `evaluation_users`, `METRICS_HEBDO` : évaluation historique sur la période suivante.

## Évaluation

Valeurs par défaut : construction `[2026-09-21 00:00 UTC, 2026-10-26 00:00 UTC)`, validation `[2026-10-26 00:00 UTC, 2026-11-02 00:00 UTC)`, taille 10. Ces dates sont des paramètres de run, jamais la date de la machine. Exemple : `--vars '{"week_start":"2026-10-26","history_start":"2026-09-21","test_end":"2026-11-02","playlist_size":10}'`.

`HIT_RATE_S1` = proportion des utilisateurs éligibles qui ont écouté au moins un artiste recommandé durant la semaine de validation. Éligibles : historique exploitable ET au moins une écoute exploitable durant la validation; les profils sans activité future sont exclus du dénominateur. Une écoute est un signal implicite, pas une preuve que le morceau a plu.

`HIT_RATE_BASELINE_S1` applique le même calcul au top des artistes par nombre d'auditeurs dans l'historique, puis nombre d'écoutes et identifiant. Même exclusion des artistes déjà connus et même taille maximale.

`DISCOVERY_RATE` = part des artistes recommandés absents de l'historique observé de leur destinataire. Ce taux est imposé par les exclusions; il ne mesure pas la satisfaction. Nouveauté signifie « absent de ces cinq semaines », pas « jamais écouté de sa vie ».

La comparaison concerne seulement quatre utilisateurs : aucune conclusion de supériorité générale. Il n'y a pas de réglage automatique des paramètres sur la semaine de validation. Les genres et les profils manuels ne sont pas disponibles dans ces deux fichiers.

## Vérifications et limites

`check_pipeline.py` vérifie aussi que les 6 652 écoutes sans `RAW:user_name`, identifiées par leur chemin GCS, produisent exactement les mêmes playlists et métriques. Il vérifie les comptes observés des extraits, recharge le même lot puis compare les sorties, retire les écoutes futures d'une copie et vérifie que les playlists ne changent pas, et exécute le même SQL dbt sur un jeu calculé à la main : A={X,Y}, B={X,Y,Z}, C={X,W}; Z doit être premier pour A, avec un score de 2/3. Une écoute invalide est mise en quarantaine. Une dimension manquante est ensuite injectée dans cette base jetable et doit faire échouer `no_unknown_artists`.

Le contrôle de complétude exige un historique non vide et des écoutes près de la fin de la fenêtre; il ne prouve pas l'exhaustivité de l'API pour chaque utilisateur. Le graphe de voisinage est quadratique en nombre d'utilisateurs : adapté à cet extrait, à remplacer par une sélection de voisins à grande échelle. Les tables gold sont des sorties de développement : la publication atomique en production reste à intégrer avec Elimane après validation de tous les tests.

## Snowflake — connexion au compte commun

Faire relire `tools/bootstrap_dev.sql` avant exécution. Configurer localement `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`. SSO via navigateur par défaut; pour une clé déjà configurée, `SNOWFLAKE_PRIVATE_KEY_FILE` désigne son chemin local. Ne jamais copier la clé ou un mot de passe dans le dépôt.

```bash
.venv/bin/python dbt/tools/load_fixtures.py --fixtures /chemin/vers/les/fichiers --target snowflake
DBT_SEND_ANONYMOUS_USAGE_STATS=false .venv/bin/dbt build --project-dir dbt --profiles-dir dbt --target dev
```

Les résultats d'exécution restent dans `DEV_HUGO_OPS.DBT_RESULTS`. Conserver également les query IDs, `run_results.json`, les comptes et les métriques comme preuves cloud. Les preuves locales sont dans `evidence/checks.json`; `snowflake_syntax.json` est uniquement une vérification de syntaxe, pas une exécution Snowflake.

## Preuves cloud du 2 novembre 2026

`evidence/cloud_results.csv` est exporté directement depuis Snowflake : 6 652 écoutes et 915 artistes en bronze, 6 125 écoutes en silver, 527 en quarantaine, 6 615 liens écoute-artiste, 40 recommandations pour quatre utilisateurs. Hit rate S+1 : 0,75, contre 0,50 pour la popularité, sur la seule semaine du 26 octobre. Les comptes construction/validation sont 4 858/1 267.

`tools/run_models_snowsight.sql` contient le SQL effectivement utilisé, y compris les deux COPY INTO depuis le stage interne. `tools/replay_snowsight.sql` conserve les résultats précédents dans DEV_HUGO_OPS puis rejoue et compare dans les deux sens. `tools/cloud_evidence.sql` produit le tableau de vérification exporté. Les contrôles cloud sont des requêtes de vérification; la commande dbt build complète a été exécutée uniquement sur la cible locale.

L'environnement de développement a été créé manuellement avec accord d'Hugo. Cette création manuelle ne constitue pas une preuve Terraform; Elimane doit déclarer au moins une ressource utile en IaC et documenter les étapes manuelles. Les comptes personnels de Yanis et d'Elimane et leurs rôles Vayba sont créés; leur activation reste manuelle. GCS, Airflow/Docker, la publication atomique et Dash restent à intégrer. Aucun fichier n'a été poussé sur GitHub par cette opération.

## Raccordement ingestion du 2 novembre

Les nouveaux fichiers API identifient les utilisateurs par leur chemin GCS. Le test de compatibilité reproduit ce format sur toutes les écoutes réelles et exige des sorties gold identiques. Le chargeur manuel respecte les quatre colonnes bronze, y compris sur les tables déjà créées dans Snowflake; sa commande cloud reste non exécutée.

La connexion `externalbrowser` a été essayée : le compte retourne une erreur SAML 390190. Une authentification par clé est à activer pour lancer `dbt build --target dev`. Ne pas confondre ce blocage avec les modèles SQL déjà exécutés dans Snowsight. Le choix 10/20 titres et la définition finale du taux de découverte restent à confirmer avec Yanis.
