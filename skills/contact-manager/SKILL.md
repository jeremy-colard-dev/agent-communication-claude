---
name: contact-manager
description: Recherche de coordonnées (e-mail, téléphone, rôle), ajout unitaire, import en masse et retrait de contacts dans le CRM Brevo (avec enrichissement Firestore optionnel).
---

# Gestionnaire de Contacts CRM

## Commandes disponibles (`tools/contact_tool.py`)

### 1. Rechercher un contact (nom, prénom, e-mail ou rôle)
```bash
python tools/contact_tool.py search "Dupont"
```
> Retourne l'e-mail, le prénom, le nom, le numéro de téléphone et le rôle de toutes les fiches correspondantes.

### 2. Ajouter ou mettre à jour un contact unique
```bash
python tools/contact_tool.py add \
  --email "marie.curie@exemple.org" \
  --prenom "Marie" \
  --nom "Curie" \
  --telephone "06 11 22 33 44" \
  --role "Partenaire culturel"
```

### 3. Importer une liste de plusieurs contacts en 1 seul appel (`bulk-add`)
Dès qu'il y a plus de 3 contacts à ajouter (ex: liste issue d'un e-mail ou d'un tableau), utiliser **obligatoirement** `bulk-add` pour éviter les boucles d'appels unitaires :
```bash
python tools/contact_tool.py bulk-add --json '[{"email":"a@exemple.org","prenom":"Alice","nom":"Martin","role":"Bénévole"}]'
```

### 4. Retirer un contact d'une liste de diffusion
```bash
python tools/contact_tool.py remove --email "ancien.contact@exemple.org"
```

### 5. Consulter les listes de diffusion
```bash
python tools/contact_tool.py lists
```
