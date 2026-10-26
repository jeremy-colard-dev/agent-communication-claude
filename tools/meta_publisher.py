#!/usr/bin/env python3
"""
Outil de publication sur Facebook et Instagram via Meta Graph API (`meta_publisher.py`).
Fonctionnalités :
- Publication sur la Page Facebook (texte seul ou texte + image)
- Publication sur le compte Instagram Professionnel (image obligatoire, normalisée automatiquement en JPG au ratio 4:5..1.91:1)
- Publication simultanée sur les deux réseaux (`--platform both`)
- Mode `--dry-run` intégré pour simuler la publication sans jeton Meta
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.config import get_env
from tools.media_tool import prepare_social_image, upload_to_gcs_or_local

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def _is_meta_configured() -> bool:
    token = get_env("META_PAGE_ACCESS_TOKEN")
    return bool(token and not token.startswith("EAA..."))


def _graph_post(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{GRAPH_API_BASE}/{endpoint.lstrip('/')}"
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Erreur Meta Graph API ({exc.code}) : {err_body}") from exc


def _graph_get(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{GRAPH_API_BASE}/{endpoint.lstrip('/')}?{query}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def publish_facebook(
    message: str,
    image_url: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Publie un post sur la Page Facebook."""
    page_id = get_env("META_PAGE_ID", "123456789012345")
    page_token = get_env("META_PAGE_ACCESS_TOKEN")

    if dry_run or not _is_meta_configured():
        return {
            "platform": "facebook",
            "status": "dry_run",
            "page_id": page_id,
            "message_preview": message[:120],
            "image_url": image_url,
        }

    if image_url:
        resp = _graph_post(
            f"{page_id}/photos",
            {
                "url": image_url,
                "caption": message,
                "access_token": page_token,
            },
        )
    else:
        resp = _graph_post(
            f"{page_id}/feed",
            {
                "message": message,
                "access_token": page_token,
            },
        )
    return {"platform": "facebook", "status": "published", "response": resp}


def publish_instagram(
    caption: str,
    image_url: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Publie une photo sur le compte Instagram Professionnel associé."""
    ig_id = get_env("META_INSTAGRAM_ACCOUNT_ID", "17841400000000000")
    page_token = get_env("META_PAGE_ACCESS_TOKEN")

    if dry_run or not _is_meta_configured():
        return {
            "platform": "instagram",
            "status": "dry_run",
            "instagram_account_id": ig_id,
            "caption_preview": caption[:120],
            "image_url": image_url,
        }

    container = _graph_post(
        f"{ig_id}/media",
        {
            "image_url": image_url,
            "caption": caption,
            "access_token": page_token,
        },
    )
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError(f"Échec de création du conteneur Instagram : {container}")

    # Attente active de la validation du conteneur par Meta
    for _ in range(12):
        status_data = _graph_get(
            str(creation_id),
            {"fields": "status_code", "access_token": page_token},
        )
        code = status_data.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"Erreur de traitement média Instagram : {status_data}")
        time.sleep(2.5)

    published = _graph_post(
        f"{ig_id}/media_publish",
        {
            "creation_id": creation_id,
            "access_token": page_token,
        },
    )
    return {"platform": "instagram", "status": "published", "response": published}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publication Facebook & Instagram avec normalisation automatique des images."
    )
    parser.add_argument(
        "--platform",
        choices=["facebook", "instagram", "both"],
        default="both",
        help="Réseau social cible (facebook, instagram ou both)",
    )
    parser.add_argument("--message", required=True, help="Texte / légende de la publication")
    parser.add_argument("--image-url", help="URL publique d'une image déjà hébergée")
    parser.add_argument(
        "--image-file",
        help="Fichier image local à convertir aux normes Instagram et héberger automatiquement",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simule la publication sans appeler Meta")

    args = parser.parse_args()
    final_image_url = args.image_url

    if args.image_file:
        local_src = Path(args.image_file)
        normalized_jpg = prepare_social_image(local_src)
        upload_res = upload_to_gcs_or_local(
            normalized_jpg,
            f"social/{normalized_jpg.name}",
            dry_run=args.dry_run,
        )
        final_image_url = upload_res.get("url")

    results = []
    if args.platform in ("facebook", "both"):
        results.append(
            publish_facebook(
                message=args.message,
                image_url=final_image_url,
                dry_run=args.dry_run,
            )
        )

    if args.platform in ("instagram", "both"):
        if not final_image_url:
            raise RuntimeError("Instagram exige obligatoirement une image (--image-url ou --image-file).")
        results.append(
            publish_instagram(
                caption=args.message,
                image_url=final_image_url,
                dry_run=args.dry_run,
            )
        )

    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
