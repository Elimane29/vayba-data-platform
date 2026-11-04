# Démo courte et muette — Yanis

Fichier : `Vayba_Yanis_demo_pipeline_muette_2026-11-04.mp4`.
Durée : environ 38,5 secondes. Aucune piste audio. Aucune slide.

La vidéo est constituée de captures successives des interfaces réelles pendant la navigation du 4 novembre,
avec leur chronologie conservée. Ce n'est pas le montage des anciennes captures de preuves du 3 novembre.

| Temps approximatif | Écran visité |
|---|---|
| 0–5 s | Bucket GCS et dossiers des trois sources |
| 5–11 s | Deux semaines ListenBrainz disponibles |
| 11–19 s | Fichiers NDJSON de la semaine du 26 octobre |
| 19–25 s | Stage GCS dans Snowflake et comptes de fichiers |
| 25–38,5 s | Exécution du SELECT de contrôle et résultats bronze |

Résultat observé : 16 447 écoutes / 50 fichiers, 2 478 artistes / fichiers, 1 234 documents Wikipédia / fichiers,
zéro doublon pour chaque source. Le contrôle des écoutes reconstitue l'utilisateur depuis le fichier source
lorsqu'il est absent du JSON. La requête est conservée dans `ingestion/sql/verify_bronze_demo.sql`.

La séquence ne relance pas la chaîne de production : LIST et SELECT sont des lectures. Airflow et Dash ne
sont pas inclus ; aucun lien accessible n'a été trouvé dans les messages Vayba consultés. La vidéo d'ensemble
doit associer ce passage ingestion aux séquences des autres membres si le rendu demande toute la chaîne.

L'ancien support commenté de trois minutes est remplacé par cette version dans les livrables actifs.
