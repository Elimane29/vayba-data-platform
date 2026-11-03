# Dash — playlists et métriques Vayba

Dash lit VAYBA.GOLD avec VAYBA_GOLD_SCHEMA=GOLD, le rôle VAYBA_DASH_READ et les rôles secondaires désactivés. Le compte technique du prototype possède un autre rôle pour dbt ; un déploiement autonome doit avoir un utilisateur dédié à l'application. Le rôle Dash n'a accès ni au Bronze ni à l'écriture Gold.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r dashboard/requirements.txt
export SNOWFLAKE_ACCOUNT="<organisation-compte>"
export SNOWFLAKE_USER="<utilisateur-autorise>"
export SNOWFLAKE_PRIVATE_KEY_FILE="/chemin/local/cle.p8"
export SNOWFLAKE_WAREHOUSE="VAYBA_WH"
export VAYBA_GOLD_SCHEMA="GOLD"
python dashboard/app.py

python dashboard/check_app.py
```
