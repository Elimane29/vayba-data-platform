# Dash — playlists et métriques Vayba

L’application présente deux vues : la playlist par semaine et profil, puis les métriques de validation S+1 comparées à la popularité. Elle lit les vraies tables Snowflake `PLAYLIST_HEBDO` et `METRICS_HEBDO` du gold ; aucune donnée de remplacement n'est affichée. Le bouton de mise à jour relit les tables. Les identifiants des profils sont pseudonymisés.

## Installer et lancer

À partir de la racine du dépôt, avec Python 3.10 ou supérieur :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r dashboard/requirements.txt
export SNOWFLAKE_ACCOUNT="<organisation-compte>"
export SNOWFLAKE_USER="<utilisateur-autorise>"
export SNOWFLAKE_PRIVATE_KEY_FILE="/chemin/local/cle.p8"
export SNOWFLAKE_WAREHOUSE="VAYBA_WH"
export VAYBA_GOLD_SCHEMA="DEV_HUGO_DBT_GOLD"
python dashboard/app.py
```

Ouvrir `http://127.0.0.1:8050`. Le serveur écoute uniquement sur le Mac qui le lance. Aucune clé privée n'est envoyée au navigateur ou au dépôt. L'application échoue explicitement si sa connexion initiale à Snowflake ne fonctionne pas; elle ne bascule pas sur des résultats fictifs.

## Accès et vérification

Le rôle de session est fixé à `VAYBA_DASH_READ`, avec les rôles secondaires désactivés. La préparation de ce rôle est décrite dans `setup_read_role.sql`, à exécuter par un administrateur autorisé. Ce rôle lit le gold et utilise le petit warehouse, sans droit de lecture du bronze ni droit d’insertion dans les tables gold. Le prototype utilise l'utilisateur technique de Hugo, qui possède aussi un rôle distinct pour dbt; un déploiement autonome devra employer un utilisateur propre à l'application.

```bash
python dashboard/check_app.py
```

Ce contrôle utilise le vrai Snowflake : 40 recommandations, quatre profils, une playlist de 10 titres et la vue métriques à 75 % contre 50 %. Il vérifie aussi le refus de lecture du bronze et le refus d’une insertion sans ligne dans le gold. Les résultats et query IDs sont enregistrés dans `evidence/checks.json`. Les tables temporaires ont un régime différent dans Snowflake et ne constituent pas un test fiable de refus d’écriture persistante.

## Limites et reprise

Le serveur recharge les données au démarrage et sur demande. La lecture est limitée à 10000 lignes par table pour ce prototype; il faudra paginer pour un déploiement plus grand. Le taux de nouveauté décrit l'absence d'un artiste dans l'historique utilisé, pas sa nouveauté dans toute la vie de l'utilisateur. Les résultats sur quatre profils et une semaine sont exploratoires. Le choix de 10 ou 20 titres et la définition finale de la découverte restent à valider avec Yanis. GCS, Airflow et la publication dans les schémas partagés restent des étapes distinctes à valider en équipe.
