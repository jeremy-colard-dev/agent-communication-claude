---
name: social-publisher
description: Publication sur la Page Facebook et le compte Instagram Professionnel de l'organisation via Meta Graph API, avec conversion automatique des visuels aux ratios Instagram.
---

# Publication Réseaux Sociaux (Facebook & Instagram)

## Règles de sécurité avant publication
1. **Toujours rédiger et présenter le texte de la publication** à l'utilisateur métier avant de publier.
2. **Vérifier le visuel** : Instagram exige obligatoirement une image. Le script `tools/meta_publisher.py` accepte `--image-file` (qu'il convertit et recadre automatiquement aux normes JPEG 4:5 d'Instagram) ou `--image-url`.
3. **Attendre le feu vert explicite** de l'utilisateur avant de lancer la commande sans `--dry-run`.

## Commandes (`tools/meta_publisher.py`)

### Publier simultanément sur Facebook et Instagram avec une image locale
```bash
python tools/meta_publisher.py \
  --platform both \
  --message "Retour en images sur notre atelier céramique de samedi dernier ! Merci à tous les participants." \
  --image-file visuel_atelier.png
```

### Publier sur Facebook uniquement (avec ou sans image)
```bash
python tools/meta_publisher.py \
  --platform facebook \
  --message "Rappel : notre Repair Café solidaire a lieu demain soir à 18h30 au 14 Allée des Cèdres."
```
