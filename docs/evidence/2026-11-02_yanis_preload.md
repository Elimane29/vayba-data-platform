# Préparation du chargement réel — 2026-11-02

Statut : extraction locale réussie ; chargement GCS/Snowflake non exécuté.

Dépôt : révision ee9cd82, synchronisée par `git pull --ff-only`.

Commandes exécutées et résultats :
- `python -m venv .venv` : code 0.
- `.venv\Scripts\python.exe -m pip install -r requirements.txt` : code 0.
- `.venv\Scripts\python.exe -m pip check` : `No broken requirements found.`
- `.venv\Scripts\python.exe ingestion/test_run.py` : `ok`, code 0. Le message FAILED sur 2026-10-27 fait partie du test de date invalide.
- `.venv\Scripts\python.exe ingestion/run.py --source listenbrainz --week 2026-10-26 --no-load` : `listenbrainz: 8003 listens, 25 users, week 2026-10-26`, code 0.

Versions demandées et installées : dbt-core 1.11.16 ; dbt-snowflake 1.11.6 ; snowflake-connector-python 4.8.0 ; google-cloud-storage 3.17.1.

Les données sont dans data/landing/ et ne sont pas committées. Le compte de 8001 était une mesure antérieure ; le présent run donne 8003. Aucun rejeu n'a été mesuré dans cette session.

Blocages observés :
- .env absent à la racine du dépôt ; variables Snowflake/GCS absentes de la session (présence seule vérifiée, aucune valeur lue).
- Fichier ADC Google absent à son emplacement Windows standard ; gcloud absent du PATH.
- Accès Chrome refusé par l'outil de contrôle : aucune session Snowflake vérifiée par navigateur.

Informations publiques du runbook : bucket vayba-elimane-2026-landing ; authentification GCP personnelle par ADC ; aucun compte de service à clé prévu.

Restent non exécutés : vérification RSA/session/stage/droits Snowflake, chargement GCS et bronze, deuxième source en bronze, contrôle des doublons et rejeu, dbt build et incidents. Graphify a produit un graphe local, mais les extensions SQL/HCL sont absentes : graphe incomplet pour ces formats.

## Contrôles réels dans Snowsight — 2026-11-02 vers 18:46–18:49 Europe/Paris

Session navigateur : YANIS_RAJHI / VAYBA_YANIS.

`SHOW STAGES IN SCHEMA VAYBA.DEV_YANIS_BRONZE;`, puis sélection de name, type, url, storage_integration depuis RESULT_SCAN :
- LANDING_GCS : INTERNAL ; URL vide ; storage_integration vide.

Comptes par requête SQL UNION ALL sur les trois tables :
- LISTENS_RAW : 0.
- MB_ARTISTS_RAW : 0.
- WIKI_PAGEVIEWS_RAW : 0.

`SHOW STORAGE INTEGRATIONS;` : 0 ligne visible pour le rôle courant. Cela ne démontre pas l'absence d'intégration au niveau du compte.

Console GCP après validation personnelle : compte scolaire de Yanis connecté, mais refus sur le bucket vayba-elimane-2026-landing. Message : « Additional permissions required to list objects in this bucket », permission manquante storage.objects.list. Aucun objet n'a été chargé.

Le connecteur Python avec authenticator=externalbrowser a échoué : DatabaseError, errno 390190. Aucun secret lu ni affiché par l'agent. La session Snowsight fonctionne et permet les vérifications SQL.

Mesures locales détaillées : 2026-11-02_listenbrainz_local.json. L'extraction MusicBrainz a été démarrée ; son résultat final reste à vérifier. Wikipedia non exécuté dans cette session.

Ajouts sur branche part1/real-data-validation : ingestion/verify_bronze.sql (préparé, non exécuté intégralement), mise à jour du statut dans ingestion/README.md. Aucun commit ni push.

## Vérification avec le compte Google personnel confirmé

Le compte rajhiyanis12@gmail.com a été sélectionné et son activation Google Cloud a été terminée par Yanis. Après actualisation du bucket vayba-elimane-2026-landing, l'accès aux objets reste refusé : storage.objects.list manque. L'onglet Autorisations indique également storage.buckets.get et storage.buckets.getIamPolicy manquants pour afficher les métadonnées et la politique IAM. Ces deux derniers droits concernent l'inspection administrative ; le besoin opérationnel principal reste l'accès aux objets.

Le refus n'est donc plus imputable au seul compte scolaire. Il faut faire vérifier l'invitation et les rôles du compte personnel par Elimane. Aucun changement IAM effectué.

## Chargement GCS réussi — 2026-11-02 vers 19:19 Europe/Paris

Compte Google : yrajhi@albertschool.com. Après mise à jour des droits, le bucket est accessible en lecture et en écriture.

Envoi via la console Google Cloud du dossier local data/landing/listenbrainz. Résultat affiché : « 25 files successfully uploaded ».
Destination : gs://vayba-elimane-2026-landing/listenbrainz/week=2026-10-26/.
Volume source local correspondant : 25 fichiers, 8 003 écoutes, 9 486 050 octets ; empreinte globale dans 2026-11-02_listenbrainz_local.json.

Diagnostic Snowflake exécuté : DESC INTEGRATION VAYBA_GCS_INT;
Résultat : « Insufficient privileges to operate on integration 'VAYBA_GCS_INT' ». Le message demande USAGE sur cette intégration pour VAYBA_YANIS. L'intégration existe donc ; son absence de SHOW STORAGE INTEGRATIONS reflète l'absence de visibilité du rôle.

Action administrateur restante : GRANT USAGE ON INTEGRATION VAYBA_GCS_INT TO ROLE VAYBA_YANIS;
Le stage DEV_YANIS_BRONZE.LANDING_GCS est encore interne au dernier contrôle. Aucun COPY INTO ni rejeu bronze exécuté.
