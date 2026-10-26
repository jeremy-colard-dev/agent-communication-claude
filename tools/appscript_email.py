#!/usr/bin/env python3
"""
Envoi d'e-mails transactionnels via un webhook Google Apps Script.
Respecte automatiquement la politique éditoriale de `config/organization.json`
(ex: nettoyage automatique des émojis si `allow_emojis_in_emails` est désactivé)
et supporte le mode `--dry-run`.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.config import get_env, get_org_info, strip_emojis_if_configured


def send_appscript_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Envoie un e-mail via le webhook Google Apps Script configuré."""
    clean_subject = strip_emojis_if_configured(subject)
    clean_html = strip_emojis_if_configured(html_body)
    clean_text = strip_emojis_if_configured(text_body or "")

    org = get_org_info()
    payload: Dict[str, Any] = {
        "to": to_email,
        "subject": clean_subject,
        "htmlBody": clean_html,
        "senderName": get_env("BREVO_SENDER_NAME", org.get("name", "Communication")),
    }
    if clean_text:
        payload["body"] = clean_text
    if cc:
        payload["cc"] = cc
    if bcc:
        payload["bcc"] = bcc

    secret = get_env("APPSCRIPT_SECRET_TOKEN")
    if secret and secret != "votre_jeton_secret_appscript":
        payload["token"] = secret

    webhook_url = get_env("APPSCRIPT_WEBHOOK_URL")
    if dry_run or not webhook_url or "VOTRE_ID" in webhook_url:
        return {
            "status": "dry_run",
            "to": to_email,
            "subject": clean_subject,
            "html_length": len(clean_html),
            "message": "Simulation réussie (--dry-run ou APPSCRIPT_WEBHOOK_URL non configuré).",
        }

    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"raw_response": raw}
            return {
                "status": "sent",
                "to": to_email,
                "subject": clean_subject,
                "response": data,
            }
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Erreur HTTP Apps Script ({exc.code}) : {err_body}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Envoi d'e-mails via Google Apps Script avec respect de la charte éditoriale."
    )
    parser.add_argument("--to", required=True, help="Destinataire principal (ou liste séparée par des virgules)")
    parser.add_argument("--subject", required=True, help="Objet de l'e-mail")
    parser.add_argument("--html", help="Corps de l'e-mail en HTML (texte direct)")
    parser.add_argument("--html-file", help="Chemin vers un fichier HTML à envoyer")
    parser.add_argument("--cc", help="Destinataires en copie (CC)")
    parser.add_argument("--bcc", help="Destinataires en copie cachée (CCI)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule l'envoi sans appeler le webhook Google Apps Script",
    )

    args = parser.parse_args()
    if args.html_file:
        html_content = Path(args.html_file).read_text(encoding="utf-8")
    elif args.html:
        html_content = args.html
    else:
        parser.error("Vous devez fournir --html ou --html-file.")
        return

    result = send_appscript_email(
        to_email=args.to,
        subject=args.subject,
        html_body=html_content,
        cc=args.cc,
        bcc=args.bcc,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
