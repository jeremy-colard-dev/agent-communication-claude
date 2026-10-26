---
name: support-tech
description: Signalement d'incidents techniques bloquants et envoi de demandes d'évolution fonctionnelle au référent technique défini dans config/organization.json, sous réserve d'accord de l'utilisateur métier.
---

# Support Technique & Demandes d'Évolution (`tools/support_tech.py`)

## Quand utiliser ce skill ?

### Cas 1 — Incident technique bloquant (`incident`)
Si un outil Python renvoie une erreur bloquante (clé API expirée, restriction d'IP, service tiers indisponible) que tu ne peux pas résoudre de manière transparente :
1. **Ne montre jamais la trace d'erreur brute (stack trace)** à l'utilisateur métier.
2. Explique calmement la situation en une phrase simple et demande-lui :
   > *« Je rencontre un blocage technique sur ce service. Souhaitez-vous que j'envoie automatiquement un rapport détaillé au référent technique pour qu'il le débloque ? »*
3. Dès que l'utilisateur répond **Oui**, exécute :
```bash
python tools/support_tech.py incident \
  --action "Description claire de ce que l'utilisateur souhaitait faire" \
  --tool "tools/nom_du_script.py" \
  --details "Trace technique complète, code HTTP et diagnostic précis pour le développeur" \
  --confirm
```

### Cas 2 — Demande d'évolution pertinente (`evolution`)
Si l'utilisateur métier demande une fonctionnalité pertinente pour la communication de l'organisation mais qui n'est pas encore connectée (ex: publier sur LinkedIn, gérer une billetterie HelloAsso, envoyer des SMS) :
1. Explique-lui que cette capacité n'est pas encore branchée.
2. Propose-lui spontanément :
   > *« Cette fonctionnalité serait très utile mais n'est pas encore installée. Voulez-vous que j'envoie une proposition d'évolution au référent technique pour qu'il puisse l'ajouter ? »*
3. Dès que l'utilisateur répond **Oui**, exécute :
```bash
python tools/support_tech.py evolution \
  --action "Besoin exprimé par l'utilisateur métier" \
  --tool "nouvelle-brique" \
  --details "Spécification fonctionnelle et piste d'API suggérée" \
  --confirm
```
