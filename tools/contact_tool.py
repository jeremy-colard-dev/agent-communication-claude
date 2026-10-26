#!/usr/bin/env python3
"""
Gestionnaire de contacts CRM (Brevo + enrichissement optionnel Firestore).
Fonctionnalités :
- Recherche multi-critères (`search`) avec pagination complète Brevo et fusion Firestore optionnelle
- Ajout unitaire (`add`) et import en masse en 1 seul appel API (`bulk-add --json`)
- Suppression d'une liste (`remove`) et consultation des listes (`lists`)
- Mode `--dry-run` intégré pour tester sans clé API Brevo
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.config import (
    ORG_CONFIG,
    fetch_firestore_collection,
    get_env,
)

BREVO_API_BASE = "https://api.brevo.com/v3"


def _is_brevo_configured() -> bool:
    key = get_env("BREVO_API_KEY")
    return bool(key and not key.startswith("xkeysib-votre"))


def _brevo_request(
    method: str,
    endpoint: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Any:
    api_key = get_env("BREVO_API_KEY")
    if not _is_brevo_configured():
        raise RuntimeError(
            "Clé BREVO_API_KEY absente ou non configurée dans .env (utilisez --dry-run pour simuler)."
        )

    url = f"{BREVO_API_BASE}{endpoint}"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Erreur API Brevo ({exc.code}) : {err_body}") from exc


def fetch_all_brevo_contacts(list_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Récupère l'intégralité des contacts Brevo avec pagination automatique (limit=500)."""
    contacts: List[Dict[str, Any]] = []
    limit = 500
    offset = 0

    while True:
        if list_id:
            endpoint = f"/contacts/lists/{list_id}/contacts?limit={limit}&offset={offset}"
        else:
            endpoint = f"/contacts?limit={limit}&offset={offset}"

        data = _brevo_request("GET", endpoint)
        batch = data.get("contacts", [])
        contacts.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    return contacts


def _load_optional_firestore_contacts() -> Dict[str, Dict[str, Any]]:
    """
    Si `firestore_sync_enabled` est actif dans `config/organization.json` ou si
    `FIRESTORE_CONTACTS_COLLECTION` est renseigné, enrichit les contacts avec Firestore
    (ex: numéro de téléphone mobile, rôle, adhésion).
    """
    connectors = ORG_CONFIG.get("connectors", {})
    collection = get_env("FIRESTORE_CONTACTS_COLLECTION")
    if not connectors.get("firestore_sync_enabled") and not collection:
        return {}

    collection_name = collection or "User_sensitive"
    docs = fetch_firestore_collection(collection_name)
    by_email: Dict[str, Dict[str, Any]] = {}
    for doc in docs:
        email = str(doc.get("email") or doc.get("mail") or "").strip().lower()
        if email:
            by_email[email] = doc
    return by_email


def search_contacts(query: str, dry_run: bool = False) -> List[Dict[str, Any]]:
    """Recherche un contact par nom, prénom, e-mail, rôle ou téléphone."""
    if dry_run or not _is_brevo_configured():
        sample = [
            {
                "email": "claire.martin@ateliersduparc.org",
                "prenom": "Claire",
                "nom": "Martin",
                "telephone": "06 12 34 56 78",
                "role": "Présidente",
                "source": "dry-run",
            },
            {
                "email": "marc.dupont@ateliersduparc.org",
                "prenom": "Marc",
                "nom": "Dupont",
                "telephone": "06 98 76 54 32",
                "role": "Trésorier & Bénévole",
                "source": "dry-run",
            },
        ]
        q = query.strip().lower()
        return [
            c
            for c in sample
            if not q or any(q in str(v).lower() for v in c.values())
        ]

    brevo_contacts = fetch_all_brevo_contacts()
    firestore_by_email = _load_optional_firestore_contacts()
    merged: Dict[str, Dict[str, Any]] = {}

    for c in brevo_contacts:
        email = str(c.get("email", "")).strip().lower()
        attrs = c.get("attributes", {}) or {}
        fs = firestore_by_email.get(email, {})
        merged[email] = {
            "email": c.get("email", ""),
            "prenom": attrs.get("PRENOM") or attrs.get("FIRSTNAME") or fs.get("firstName") or fs.get("prenom") or "",
            "nom": attrs.get("NOM") or attrs.get("LASTNAME") or fs.get("lastName") or fs.get("nom") or "",
            "telephone": (
                attrs.get("SMS")
                or attrs.get("TELEPHONE")
                or fs.get("phone")
                or fs.get("telephone")
                or ""
            ),
            "role": attrs.get("ROLE") or fs.get("role") or "",
            "listIds": c.get("listIds", []),
        }

    for email, fs in firestore_by_email.items():
        if email not in merged:
            merged[email] = {
                "email": email,
                "prenom": fs.get("firstName") or fs.get("prenom") or "",
                "nom": fs.get("lastName") or fs.get("nom") or "",
                "telephone": fs.get("phone") or fs.get("telephone") or "",
                "role": fs.get("role") or "",
                "listIds": [],
            }

    q = query.strip().lower()
    return [
        item
        for item in merged.values()
        if not q or any(q in str(val).lower() for val in item.values())
    ]


def add_contact(
    email: str,
    prenom: str = "",
    nom: str = "",
    telephone: str = "",
    role: str = "",
    list_id: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Ajoute ou met à jour un contact dans Brevo."""
    target_list = list_id or int(get_env("BREVO_DEFAULT_LIST_ID", "2"))
    attributes: Dict[str, str] = {}
    if prenom:
        attributes["PRENOM"] = prenom
        attributes["FIRSTNAME"] = prenom
    if nom:
        attributes["NOM"] = nom
        attributes["LASTNAME"] = nom
    if telephone:
        attributes["TELEPHONE"] = telephone
    if role:
        attributes["ROLE"] = role

    payload = {
        "email": email.strip(),
        "attributes": attributes,
        "listIds": [target_list],
        "updateEnabled": True,
    }

    if dry_run or not _is_brevo_configured():
        return {"status": "dry_run", "action": "add_contact", "payload": payload}

    resp = _brevo_request("POST", "/contacts", payload)
    return {"status": "added_or_updated", "email": email, "list_id": target_list, "response": resp}


def bulk_add_contacts(
    contacts_list: List[Dict[str, Any]],
    list_id: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Importe une liste de contacts en un seul appel API Brevo `/contacts/import`."""
    target_list = list_id or int(get_env("BREVO_DEFAULT_LIST_ID", "2"))
    json_body: List[Dict[str, Any]] = []

    for item in contacts_list:
        email = str(item.get("email", "")).strip()
        if not email:
            continue
        attrs: Dict[str, str] = {}
        if item.get("prenom"):
            attrs["PRENOM"] = str(item["prenom"])
        if item.get("nom"):
            attrs["NOM"] = str(item["nom"])
        if item.get("role"):
            attrs["ROLE"] = str(item["role"])
        if item.get("telephone"):
            attrs["TELEPHONE"] = str(item["telephone"])
        json_body.append({"email": email, "attributes": attrs})

    payload = {
        "jsonBody": json_body,
        "listIds": [target_list],
        "updateExistingContacts": True,
    }

    if dry_run or not _is_brevo_configured():
        return {
            "status": "dry_run",
            "action": "bulk_add_contacts",
            "count": len(json_body),
            "list_id": target_list,
        }

    resp = _brevo_request("POST", "/contacts/import", payload)
    return {
        "status": "imported",
        "count": len(json_body),
        "list_id": target_list,
        "response": resp,
    }


def remove_contact(
    email: str,
    list_id: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Retire un contact d'une liste Brevo."""
    target_list = list_id or int(get_env("BREVO_DEFAULT_LIST_ID", "2"))
    if dry_run or not _is_brevo_configured():
        return {"status": "dry_run", "action": "remove_contact", "email": email, "list_id": target_list}

    resp = _brevo_request(
        "POST",
        f"/contacts/lists/{target_list}/contacts/remove",
        {"emails": [email.strip()]},
    )
    return {"status": "removed_from_list", "email": email, "list_id": target_list, "response": resp}


def main() -> None:
    parser = argparse.ArgumentParser(description="Gestionnaire CRM de contacts Brevo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_search = subparsers.add_parser("search", help="Rechercher un contact")
    p_search.add_argument("query", nargs="?", default="", help="Nom, prénom, e-mail ou rôle")
    p_search.add_argument("--dry-run", action="store_true")

    p_add = subparsers.add_parser("add", help="Ajouter ou mettre à jour un contact")
    p_add.add_argument("--email", required=True)
    p_add.add_argument("--prenom", default="")
    p_add.add_argument("--nom", default="")
    p_add.add_argument("--telephone", default="")
    p_add.add_argument("--role", default="")
    p_add.add_argument("--list-id", type=int, default=None)
    p_add.add_argument("--dry-run", action="store_true")

    p_bulk = subparsers.add_parser("bulk-add", help="Importer plusieurs contacts en un seul appel")
    p_bulk.add_argument(
        "--json",
        required=True,
        help="Tableau JSON de contacts ou chemin vers un fichier .json",
    )
    p_bulk.add_argument("--list-id", type=int, default=None)
    p_bulk.add_argument("--dry-run", action="store_true")

    p_remove = subparsers.add_parser("remove", help="Retirer un contact d'une liste")
    p_remove.add_argument("--email", required=True)
    p_remove.add_argument("--list-id", type=int, default=None)
    p_remove.add_argument("--dry-run", action="store_true")

    p_lists = subparsers.add_parser("lists", help="Afficher les listes de diffusion Brevo")
    p_lists.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "search":
        results = search_contacts(args.query, dry_run=args.dry_run)
        print(json.dumps({"count": len(results), "contacts": results}, ensure_ascii=False, indent=2))
    elif args.command == "add":
        res = add_contact(
            email=args.email,
            prenom=args.prenom,
            nom=args.nom,
            telephone=args.telephone,
            role=args.role,
            list_id=args.list_id,
            dry_run=args.dry_run,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.command == "bulk-add":
        json_arg = Path(args.json)
        if json_arg.exists():
            items = json.loads(json_arg.read_text(encoding="utf-8"))
        else:
            items = json.loads(args.json)
        res = bulk_add_contacts(items, list_id=args.list_id, dry_run=args.dry_run)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.command == "remove":
        res = remove_contact(args.email, list_id=args.list_id, dry_run=args.dry_run)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.command == "lists":
        if args.dry_run or not _is_brevo_configured():
            print(
                json.dumps(
                    {
                        "status": "dry_run",
                        "lists": [
                            {"id": 2, "name": "Adhérents & Abonnés Newsletter", "totalSubscribers": 184}
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(json.dumps(_brevo_request("GET", "/contacts/lists?limit=50"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
