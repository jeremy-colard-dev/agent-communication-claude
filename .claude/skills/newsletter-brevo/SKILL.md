---
name: newsletter-brevo
description: Création, prévisualisation web, test et envoi de campagnes de newsletters via Brevo. Toujours utiliser ce skill lorsqu'on demande de préparer ou d'envoyer une lettre d'information mensuelle.
---

# Gestion des Newsletters (Brevo)

## Flux de travail obligatoire en 4 étapes

### Étape 1 — Rédaction à partir du gabarit officiel
1. Lire les règles du skill `design-system` et copier la structure de `templates/template_newsletter.html`.
2. Enregistrer le fichier HTML dans `newsletters/newsletter_<mois>_<annee>.html`.

### Étape 2 — Génération de l'aperçu web pour l'utilisateur métier
Avant toute création de campagne dans Brevo, générer un lien d'aperçu visuel :
```bash
python tools/media_tool.py preview newsletters/newsletter_<mois>_<annee>.html --name apercu_newsletter
```
Présenter ce lien à l'utilisateur métier pour recueillir ses retours sur le texte et les photos.

### Étape 3 — Création du brouillon Brevo & envoi d'un e-mail de test
Une fois le visuel validé :
```bash
python tools/brevo_tool.py create \
  --name "Newsletter <Mois> <Année>" \
  --subject "Les Ateliers du Parc — Lettre de <Mois>" \
  --html-file newsletters/newsletter_<mois>_<annee>.html
```
Puis proposer d'envoyer un e-mail de test :
```bash
python tools/brevo_tool.py send-test --campaign-id <ID_CAMPAGNE> --to "<EMAIL_UTILISATEUR>"
```

### Étape 4 — Envoi définitif (uniquement sur accord explicite)
Ne **JAMAIS** exécuter la commande `send` sans que l'utilisateur ait explicitement confirmé : *« Oui, tu peux l'envoyer à tous les abonnés »*.
```bash
python tools/brevo_tool.py send --campaign-id <ID_CAMPAGNE>
```
