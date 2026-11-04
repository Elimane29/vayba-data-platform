# Oral Yanis — business et ingestion

Objectif : environ 4 minutes 30, à mesurer pendant la répétition des 15 minutes du groupe.
Les cinq slides sont dans ce dossier. La couverture peut être retirée lors de l'assemblage du support commun.

## Slide 1 — 20 secondes

Vayba est notre entreprise fictive de streaming musical. Avec New Vibes, on propose chaque lundi dix artistes
absents de l'historique observé de l'auditeur, avec un morceau par artiste. On utilise la co-écoute : des personnes
qui écoutent des artistes en commun peuvent nous aider à proposer d'autres artistes. Ma partie couvre le cas
métier, les sources et leur chargement dans Snowflake.

## Slide 2 — 50 secondes

Nous avons choisi une offre B2C, destinée directement aux auditeurs, avec une version gratuite et un abonnement
premium à 9,99 euros par mois. Notre scénario suppose cent mille auditeurs et cinq pour cent d'abonnés payants.
Cela fait cinq mille abonnés, soit environ 49 950 euros de chiffre d'affaires mensuel. Ce sont des hypothèses :
les données d'écoute ne prouvent ni la conversion ni la rentabilité. Un rachat par un grand groupe reste une
hypothèse de sortie, sans transaction prévue. La question métier est de savoir si la co-écoute aide davantage
à découvrir des artistes qu'une simple liste de popularité.

## Slide 3 — 50 secondes

Nous avons trois sources. ListenBrainz apporte les historiques d'écoute de vingt-cinq profils publics. Nous
avons chargé deux semaines complètes, du 19 octobre au 1er novembre 2026 : 16 447 écoutes. MusicBrainz fournit
l'identité et les métadonnées de 2 478 artistes. Enfin, Wikidata nous aide à trouver leurs pages Wikipédia,
dont nous récupérons les vues quotidiennes en anglais. Nous avons 1 234 documents pour la semaine du
26 octobre. Ce nombre correspond aux documents, pas au total de vues. Les API conviennent à ce petit
prototype, mais elles imposent des limites de fréquence et peuvent échouer. Notre échantillon n'est pas
représentatif de tous les auditeurs.

## Slide 4 — 70 secondes

Le flux commence par la récupération des réponses des API. Les scripts prévoient un délai maximal et de
nouvelles tentatives pour les erreurs temporaires. Les réponses sont conservées en fichiers JSON dans GCS.
On garde ainsi une copie des données sources pour les recharger. Snowflake les reçoit dans le bronze avec
COPY INTO. Chaque ligne conserve le document brut, son fichier source, son identifiant de lot et sa date
de chargement. Pour les sources hebdomadaires, on remplace uniquement la semaine traitée. La suppression
et le chargement sont dans une transaction : en cas d'erreur, elle est annulée. MusicBrainz fonctionne par
fichier d'artiste et charge les nouveaux fichiers. Pour vérifier un rejeu, il faut garder les mêmes fichiers ;
une nouvelle extraction peut récupérer des écoutes tardives et changer les volumes.

## Slide 5 — 60 secondes

J'ai chargé les fichiers des deux semaines puis rejoué ce chargement. Les trois volumes restent identiques,
les empreintes de contenu sont les mêmes et les contrôles donnent zéro doublon. Les métadonnées de lot
et d'heure peuvent changer : elles sont donc exclues de l'empreinte. Elimane a ensuite validé le run Airflow
complet et son rejeu, avec vingt-six résultats sans erreur sur la version de ce run. Les versions suivantes
de Hugo ont leurs propres preuves. Sur vingt-cinq utilisateurs, le taux de succès atteint quarante-huit
pour cent, contre cinquante-six pour cent pour la popularité. La règle métier n'est donc pas satisfaite sur
cet échantillon. On conserve le classement par co-écoute : aucun basculement automatique vers la popularité
n'est implémenté. Hugo présente maintenant les transformations, les métriques et leur affichage dans Dash.

## Réponses courtes à préparer

- Pourquoi dix artistes ? C'est la taille retenue pour le prototype, identique pour la comparaison à la popularité.
- Pourquoi des API ? Un échantillon limité et inspectable, sans téléchargement d'un corpus entier ; les dumps
  restent une alternative pour de grands historiques, sans benchmark exécuté ici.
- Pourquoi GCS et Snowflake ? GCS conserve les fichiers sources ; Snowflake stocke et transforme les tables.
- Que garantit le rejeu ? Les mêmes fichiers ne créent pas de doublons et conservent leur contenu métier.
- Découverte ? Une écoute compte une fois ; tous ses artistes mappés doivent être absents de l'historique
  de l'utilisateur. La mesure actuelle est 38,1643 %, sans preuve de causalité de la recommandation.
- Wikipédia ? Moins de 1 000 vues hebdomadaires en anglais, seuil exploratoire, sur sept jours complets.
  Couverture des artistes recommandés : 100 % dans la mesure validée, soit 88 sur 88.
- Pourquoi 100 % figurait dans une ancienne preuve ? L'ancienne formule mesurait les recommandations
  absentes de l'historique. La nouvelle formule mesure les écoutes observées ; ne pas confondre les versions.
- Protection des données ? Les noms restent dans le bronze ; le silver pseudonymise par hash. Ce n'est
  pas une garantie d'anonymat.
- Profil manuel ? Le CSV est fourni. Sa présence dans Git ne prouve pas son intégration au calcul ; ne
  pas l'inclure artificiellement dans l'évaluation S+1 des vingt-cinq profils publics.

Sources : `docs/business.md`, `docs/evidence/2026-11-03_two_weeks_replay.json`,
`docs/evidence/2026-11-03_airflow_run.md`, `docs/runbook.md`, `dbt/evidence/final_cloud_checks.json`.
