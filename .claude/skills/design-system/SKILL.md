---
name: design-system
description: Charte graphique, éditoriale et accessibilité de l'organisation (Les Ateliers du Parc par défaut, personnalisable dans config/organization.json). À consulter systématiquement avant de générer une newsletter, une affiche A4 ou un e-mail HTML.
---

# Charte Graphique & Éditoriale

## 1. Philosophie visuelle
Le style visuel privilégie une esthétique **éditoriale chaleureuse, lisible et accessible** :
- Pas de fond blanc clinique (`#ffffff`) en plein écran : utiliser le fond **Papier (`#f4f2eb`)** à l'extérieur et **Crème (`#fbf8f0`)** pour les cartes de contenu.
- Contraste maximal pour la lecture : texte principal en **Noir Encre (`#111111`)** et texte secondaire en **Gris Ardoise (`#4a4842`)**.
- Deux couleurs d'accentuation complémentaires définies dans `config/organization.json` :
  - **Vert Forêt (`#1f5c4b`)** : surtitres, badges de dates, étiquettes de rubriques.
  - **Terracotta (`#c84b31`)** : boutons d'action principaux (CTA) et **un seul mot-clé mis en valeur** dans le grand titre (`<em>` en italique souligné).

## 2. Typographies
- **Titres (`h1`, `h2`, `h3`)** : `Playfair Display`, Georgia, serif.
- **Corps de texte & boutons** : `Manrope`, Arial, sans-serif (taille minimale `15px` sur e-mail, interlignage généreux `1.6` à `1.7`).

## 3. Règles éditoriales strictes
1. **Zéro émoji dans les e-mails et newsletters** : Ne jamais insérer d'émojis dans les objets ou le corps des e-mails. Les scripts `brevo_tool.py` et `appscript_email.py` nettoient d'ailleurs automatiquement tout émoji résiduel si `allow_emojis_in_emails` vaut `false`.
2. **Utilisation obligatoire des gabarits** :
   - Pour une newsletter : toujours partir de `templates/template_newsletter.html`.
   - Pour une affiche imprimable ou sociale : toujours partir de `templates/template_affiche_a4.html`.
3. **Pied de page complet** : Toujours conserver le bloc de pied de page sombre (`#111111`) contenant l'adresse postale, le téléphone et l'adresse e-mail cliquable de l'organisation.
