---
name: email-sender
description: Envoi d'e-mails directs (aux adhérents, partenaires, intervenants ou bénévoles) au nom de l'organisation via Google Apps Script, sans émojis et avec mise en page soignée.
---

# Envoi d'E-mails Transactionnels (`tools/appscript_email.py`)

## Bonnes pratiques
1. **Zéro émoji** : Ne jamais mettre d'émojis dans l'objet ni dans le corps du mail (le script les supprime automatiquement si la charte l'interdit).
2. **Validation préalable** : Toujours montrer à l'utilisateur métier le destinataire, l'objet et le texte de l'e-mail, et attendre sa confirmation avant l'envoi réel.

## Commande d'envoi
```bash
python tools/appscript_email.py \
  --to "partenaire@mairie-lyon.fr" \
  --subject "Les Ateliers du Parc — Invitation aux Portes Ouvertes du 14 novembre" \
  --html "<p>Bonjour,</p><p>Nous serions ravis de vous accueillir...</p><p>Bien cordialement,<br><strong>Claire Martin</strong><br>Présidente — Les Ateliers du Parc</p>"
```
