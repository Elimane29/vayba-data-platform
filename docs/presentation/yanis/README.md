# Livraison Yanis — 4 novembre 2026

Ce dossier contient la partie business et ingestion prête à intégrer au support commun.

- `Vayba_Yanis_partie1_final_2026-11-04.pptx` : cinq slides éditables, notes orales et références incluses.
- `Vayba_Yanis_partie1_final_2026-11-04.pdf` : copie de consultation des cinq slides, exportée depuis les rendus.
- `oral.md` : texte de répétition, cible d'environ 4 min 30, et réponses aux questions.
- `Vayba_Yanis_support_video_2026-11-04.mp4` : support commenté d'environ trois minutes, avec voix de synthèse.
- `video.md` et `narration_video.json` : déroulé de la séquence et commentaire du support vidéo.
- `profil_validation.json` : vérification du format et des comptes du CSV musical déjà fourni.

Dans le deck commun, utiliser les slides 2 à 5 si une couverture de groupe existe déjà. La durée indiquée
est une cible de répétition, pas une durée de parole mesurée avec Yanis. Le support global et les séquences
de Hugo/Elimane restent à assembler dans le fichier commun lorsqu'il est disponible.

La version finale remplace le B2B et les anciens volumes par :
- B2C : 9,99 €/mois, 100 000 auditeurs et 5 % de conversion, soit 49 950 € de CA hypothétique.
- Dix artistes par playlist, avec un morceau représentatif chacun.
- 16 447 écoutes, 2 478 artistes et 1 234 documents Wikipédia, avec les périmètres temporels indiqués.
- Rejeu manuel avec empreintes identiques et zéro doublon ; exécution Airflow d'équipe documentée séparément.
- 48 % contre 56 % pour la popularité : pas de gain démontré ni de basculement automatique implémenté.

La source métier est [docs/business.md](../../business.md). Les preuves sont dans
[docs/evidence](../../evidence/), [dbt/evidence](../../../dbt/evidence/) et le
[runbook](../../runbook.md). Les preuves anciennes restent datées et ne sont pas réécrites.

## Profil musical

Le CSV validé est [docs/team_profile_yanis.csv](../../team_profile_yanis.csv). Ses comptes déclarés ne sont
pas des événements d'écoute horodatés. Sa validation ne prouve pas son intégration à dbt ou Dash.
Le contrôle trouve 23 artistes distincts et 83 écoutes déclarées ; 14 artistes sont présents dans l'instantané
local des 2 478 artistes, et 9 en sont absents. Cela ne constitue pas une vérification actuelle du cloud.
Elimane a indiqué prendre cette intégration en charge ; il faut une preuve de sortie avant une démonstration
personnalisée. Les 25 profils et les métriques S+1 existants ne sont pas modifiés par cette livraison.

## Vidéo

Le support vidéo fourni dans ce dossier utilise une voix de synthèse française, les slides et les captures datées
du chargement manuel. Ce n'est pas un nouveau run enregistré ni la voix de Yanis. Il peut servir de répétition
ou de séquence commentée, à assembler avec la démonstration réelle d'Airflow et Dash des autres membres.
