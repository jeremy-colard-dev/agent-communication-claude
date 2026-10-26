---
name: media-manager
description: Hébergement d'images/PDF sur Google Cloud Storage (ou dossier local en fallback), création de liens d'aperçu web HTML, consultation de la galerie photo et conversion automatique aux formats Instagram.
---

# Gestion des Médias & Aperçus Web (`tools/media_tool.py`)

## 1. Générer un lien d'aperçu pour une newsletter ou une affiche HTML
```bash
python tools/media_tool.py preview newsletters/exemple_newsletter_octobre.html --name newsletter_octobre
```

## 2. Lister les photos récentes de la galerie de l'organisation
```bash
python tools/media_tool.py gallery
```

## 3. Héberger une image ou un document PDF pour obtenir une URL publique
```bash
python tools/media_tool.py upload chemin/vers/fichier.jpg --folder newsletters
```

## 4. Convertir une image ou affiche au format JPEG compatible Instagram (ratios 4:5 à 1.91:1)
Instagram Graph API rejette les fichiers WebP/PNG ainsi que les formats A4 trop verticaux (`1:1.414`). Cette commande convertit l'image en `.jpg` et ajoute automatiquement des marges latérales à la couleur du fond de la charte (`#f4f2eb`) :
```bash
python tools/media_tool.py social-jpg chemin/vers/visuel.png
```
