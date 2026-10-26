#!/usr/bin/env python3
"""
Gestionnaire de médias et d'aperçus web (`media_tool.py`).
Fonctionnalités :
- `preview` : Génère un lien d'aperçu web (sur Google Cloud Storage si configuré, sinon en local dans `output/previews/`)
- `upload` : Héberge une image ou un PDF sur Google Cloud Storage via l'API REST (zéro dépendance `google-cloud-storage`)
- `social-jpg` : Convertit une affiche HTML ou une image WebP/PNG en JPG conforme aux ratios stricts d'Instagram (4:5 à 1.91:1)
- `gallery` : Liste les dernières photos publiées dans un bucket Firebase Storage (si activé)
"""

from __future__ import annotations

import argparse
import datetime
import json
import mimetypes
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.config import (
    ROOT_DIR,
    get_design_rules,
    get_env,
    get_gcp_access_token,
)

OUTPUT_DIR = ROOT_DIR / "output"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (244, 242, 235)


def upload_to_gcs_or_local(
    local_path: Path,
    destination_blob: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Téléverse un fichier vers Google Cloud Storage via l'API JSON/REST officielle.
    Si GCS n'est pas configuré ou si `--dry-run` est actif, sauvegarde le fichier dans `output/`
    pour que tout développeur puisse tester l'outil localement sans compte GCP.
    """
    if not local_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {local_path}")

    bucket = get_env("GCS_MEDIA_BUCKET")
    token = None if dry_run else get_gcp_access_token()

    if dry_run or not bucket or not token:
        target = OUTPUT_DIR / destination_blob
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, target)
        return {
            "status": "local_preview",
            "mode": "dry_run_or_local_fallback",
            "local_path": str(target),
            "url": target.as_uri(),
            "message": "GCS non configuré ou --dry-run actif : fichier généré localement.",
        }

    content_type, _ = mimetypes.guess_type(str(local_path))
    if not content_type:
        content_type = "application/octet-stream"
    if local_path.suffix.lower() == ".html":
        content_type = "text/html; charset=utf-8"

    encoded_name = urllib.parse.quote(destination_blob, safe="")
    upload_url = (
        f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o"
        f"?uploadType=media&name={encoded_name}"
    )

    data = local_path.read_bytes()
    req = urllib.request.Request(
        upload_url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        _ = resp.read()

    public_url = f"https://storage.googleapis.com/{bucket}/{destination_blob}"
    return {
        "status": "uploaded",
        "bucket": bucket,
        "blob": destination_blob,
        "url": public_url,
    }


def prepare_social_image(
    source_path: Path,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Convertit une image (PNG, WebP, JPG) aux normes strictes d'Instagram Graph API :
    - Format JPEG (.jpg)
    - Ratio largeur/hauteur compris entre 0.8 (4:5 portrait) et 1.91 (paysage)
    - Ajout automatique de marges à la couleur du fond de la charte (`instagram_margin_hex`)
      si l'image est trop verticale (ex: affiche A4 1:1.414).
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "La bibliothèque Pillow est requise pour normaliser les images sociales (`pip install Pillow`)."
        ) from exc

    rules = get_design_rules().get("rules", {})
    bg_hex = rules.get("instagram_margin_hex", "#f4f2eb")
    bg_rgb = _hex_to_rgb(bg_hex)

    img = Image.open(source_path).convert("RGB")
    w, h = img.size
    ratio = w / float(h)

    min_ratio = 0.80  # 4:5 portrait max Instagram
    max_ratio = 1.91  # Paysage max Instagram

    if ratio < min_ratio:
        new_w = int(round(h * min_ratio))
        canvas = Image.new("RGB", (new_w, h), bg_rgb)
        canvas.paste(img, ((new_w - w) // 2, 0))
        img = canvas
    elif ratio > max_ratio:
        new_h = int(round(w / max_ratio))
        canvas = Image.new("RGB", (w, new_h), bg_rgb)
        canvas.paste(img, (0, (new_h - h) // 2))
        img = canvas

    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / "social" / f"{source_path.stem}_instagram.jpg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="JPEG", quality=92, optimize=True)
    return output_path


def list_firebase_gallery(prefix: str = "galerie/", dry_run: bool = False) -> List[Dict[str, str]]:
    """
    Liste les images publiques d'un bucket Firebase Storage via l'endpoint REST v0.
    Si non configuré ou `--dry-run`, renvoie une galerie d'exemple prête à l'emploi.
    """
    bucket = get_env("FIREBASE_STORAGE_BUCKET")
    if dry_run or not bucket or bucket.startswith("mon-projet-gcp"):
        return [
            {
                "name": "atelier_poterie_automne.jpg",
                "url": "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "jardin_partage_recolte.jpg",
                "url": "https://images.unsplash.com/photo-1466692476868-aef1dfb1e735?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "concert_acoustique_parc.jpg",
                "url": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=900&q=80",
            },
        ]

    url = (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o"
        f"?prefix={urllib.parse.quote(prefix)}"
    )
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    items: List[Dict[str, str]] = []
    for obj in data.get("items", []):
        name = obj.get("name", "")
        if name.endswith("/"):
            continue
        encoded = urllib.parse.quote(name, safe="")
        public_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{encoded}?alt=media"
        items.append({"name": name, "url": public_url})
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Outil de gestion des médias et aperçus HTML.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_preview = subparsers.add_parser("preview", help="Publier un aperçu HTML (GCS ou local)")
    p_preview.add_argument("html_file", help="Chemin du fichier HTML à prévisualiser")
    p_preview.add_argument("--name", default="apercu", help="Préfixe du fichier d'aperçu")
    p_preview.add_argument("--dry-run", action="store_true")

    p_upload = subparsers.add_parser("upload", help="Héberger un média sur GCS (ou local en fallback)")
    p_upload.add_argument("file_path", help="Chemin du fichier à téléverser")
    p_upload.add_argument("--folder", default="assets", help="Dossier cible dans le bucket")
    p_upload.add_argument("--dry-run", action="store_true")

    p_social = subparsers.add_parser(
        "social-jpg",
        help="Convertir et cadrer une image aux ratios Instagram (4:5 à 1.91:1)",
    )
    p_social.add_argument("source", help="Chemin de l'image source (PNG, WebP, JPG)")
    p_social.add_argument("--dry-run", action="store_true")

    p_gallery = subparsers.add_parser("gallery", help="Lister les photos récentes de la galerie")
    p_gallery.add_argument("--prefix", default="galerie/", help="Préfixe du dossier Storage")
    p_gallery.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "preview":
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        blob_name = f"previews/{args.name}_{ts}.html"
        res = upload_to_gcs_or_local(Path(args.html_file), blob_name, dry_run=args.dry_run)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.command == "upload":
        src = Path(args.file_path)
        blob_name = f"{args.folder.strip('/')}/{src.name}"
        res = upload_to_gcs_or_local(src, blob_name, dry_run=args.dry_run)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.command == "social-jpg":
        out = prepare_social_image(Path(args.source))
        res = upload_to_gcs_or_local(out, f"social/{out.name}", dry_run=args.dry_run)
        res["local_jpg"] = str(out)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.command == "gallery":
        photos = list_firebase_gallery(prefix=args.prefix, dry_run=args.dry_run)
        print(json.dumps({"count": len(photos), "photos": photos}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
