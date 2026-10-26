#!/usr/bin/env python3
"""
Gestionnaire de campagnes de newsletters Brevo (`brevo_tool.py`).
Fonctionnalités :
- Création de brouillon (`create`) avec nettoyage automatique des émojis selon la charte
- Synchronisation préalable optionnelle depuis Firestore (si activée dans `config/organization.json`)
- Envoi d'un e-mail de test (`send-test`)
- Envoi définitif ou programmation (`send`) uniquement après validation de l'utilisateur métier
- Mode `--dry-run` pour tester tout le flux sans clé API Brevo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.config import (
    ORG_CONFIG,
    fetch_firestore_collection,
    get_env,
    get_org_info,
    strip_emojis_if_configured,
)
from tools.contact_tool import _brevo_request, _is_brevo_configured, bulk_add_contacts


def sync_optional_firestore_subscribers(
    list_id: int,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Synchronise optionnellement les inscrits depuis Firestore vers la liste Brevo
    avant la création d'une campagne. Si Firestore n'est pas activé, retourne immédiatement.
    """
    connectors = ORG_CONFIG.get("connectors", {})
    newsletters_col = get_env("FIRESTORE_NEWSLETTERS_COLLECTION")
    contacts_col = get_env("FIRESTORE_CONTACTS_COLLECTION")

    if not connectors.get("firestore_sync_enabled") and not newsletters_col and not contacts_col:
        return {"synced": False, "reason": "Synchronisation Firestore non activée (mode Brevo autonome)"}

    collected: Dict[str, Dict[str, str]] = {}
    for col_name in filter(None, [contacts_col, newsletters_col]):
        for doc in fetch_firestore_collection(col_name):
            email = str(doc.get("email") or doc.get("mail") or "").strip().lower()
            if email and "@" in email:
                collected[email] = {
                    "email": email,
                    "prenom": str(doc.get("firstName") or doc.get("prenom") or ""),
                    "nom": str(doc.get("lastName") or doc.get("nom") or ""),
                }

    if not collected:
        return {"synced": True, "imported_count": 0}

    import_res = bulk_add_contacts(list(collected.values()), list_id=list_id, dry_run=dry_run)
    return {"synced": True, "imported_count": len(collected), "details": import_res}


def create_campaign_draft(
    name: str,
    subject: str,
    html_file: Path,
    list_ids: Optional[List[int]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Crée un brouillon de campagne e-mail dans Brevo."""
    if not html_file.exists():
        raise FileNotFoundError(f"Fichier HTML introuvable : {html_file}")

    org = get_org_info()
    target_lists = list_ids or [int(get_env("BREVO_DEFAULT_LIST_ID", "2"))]

    sync_report = sync_optional_firestore_subscribers(list_id=target_lists[0], dry_run=dry_run)

    clean_name = strip_emojis_if_configured(name)
    clean_subject = strip_emojis_if_configured(subject)
    clean_html = strip_emojis_if_configured(html_file.read_text(encoding="utf-8"))

    sender_name = get_env("BREVO_SENDER_NAME", org.get("name", "Les Ateliers du Parc"))
    sender_email = get_env("BREVO_SENDER_EMAIL", org.get("email", "contact@ateliersduparc.org"))

    payload = {
        "name": clean_name,
        "subject": clean_subject,
        "sender": {"name": sender_name, "email": sender_email},
        "type": "classic",
        "htmlContent": clean_html,
        "recipients": {"listIds": target_lists},
    }

    if dry_run or not _is_brevo_configured():
        return {
            "status": "dry_run",
            "campaign_id": 99901,
            "name": clean_name,
            "subject": clean_subject,
            "sender": payload["sender"],
            "list_ids": target_lists,
            "firestore_sync": sync_report,
            "message": "Brouillon simulé avec succès (--dry-run ou BREVO_API_KEY non configurée).",
        }

    resp = _brevo_request("POST", "/emailCampaigns", payload)
    return {
        "status": "draft_created",
        "campaign_id": resp.get("id"),
        "name": clean_name,
        "subject": clean_subject,
        "list_ids": target_lists,
        "firestore_sync": sync_report,
    }


def send_test_email(
    campaign_id: int,
    emails: List[str],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Envoie un e-mail de test d'un brouillon Brevo existant."""
    if dry_run or not _is_brevo_configured():
        return {
            "status": "dry_run",
            "campaign_id": campaign_id,
            "test_recipients": emails,
        }

    _brevo_request("POST", f"/emailCampaigns/{campaign_id}/sendTest", {"emailTo": emails})
    return {"status": "test_sent", "campaign_id": campaign_id, "test_recipients": emails}


def send_campaign_now(campaign_id: int, dry_run: bool = False) -> Dict[str, Any]:
    """Déclenche l'envoi définitif d'une campagne Brevo."""
    if dry_run or not _is_brevo_configured():
        return {"status": "dry_run", "campaign_id": campaign_id, "action": "sendNow"}

    _brevo_request("POST", f"/emailCampaigns/{campaign_id}/sendNow")
    return {"status": "sent", "campaign_id": campaign_id}


def main() -> None:
    parser = argparse.ArgumentParser(description="Gestion des campagnes de newsletters Brevo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_create = subparsers.add_parser("create", help="Créer un brouillon de campagne Brevo")
    p_create.add_argument("--name", required=True, help="Nom interne de la campagne")
    p_create.add_argument("--subject", required=True, help="Objet de l'e-mail reçu par les abonnés")
    p_create.add_argument("--html-file", required=True, help="Chemin du fichier HTML de la newsletter")
    p_create.add_argument("--list-id", type=int, default=None, help="ID de la liste Brevo cible")
    p_create.add_argument("--dry-run", action="store_true")

    p_test = subparsers.add_parser("send-test", help="Envoyer un tir de test")
    p_test.add_argument("--campaign-id", type=int, required=True)
    p_test.add_argument("--to", required=True, help="Adresse(s) e-mail séparées par des virgules")
    p_test.add_argument("--dry-run", action="store_true")

    p_send = subparsers.add_parser("send", help="Envoyer définitivement la campagne aux abonnés")
    p_send.add_argument("--campaign-id", type=int, required=True)
    p_send.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "create":
        lists = [args.list_id] if args.list_id else None
        res = create_campaign_draft(
            name=args.name,
            subject=args.subject,
            html_file=Path(args.html_file),
            list_ids=lists,
            dry_run=args.dry_run,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.command == "send-test":
        recipients = [e.strip() for e in args.to.split(",") if e.strip()]
        res = send_test_email(args.campaign_id, recipients, dry_run=args.dry_run)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.command == "send":
        res = send_campaign_now(args.campaign_id, dry_run=args.dry_run)
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
