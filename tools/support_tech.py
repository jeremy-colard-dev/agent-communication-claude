#!/usr/bin/env python3
"""
Outil d'escalade et de support humain-dans-la-boucle (`support_tech.py`).
Permet à l'agent Claude Code de signaler au référent technique :
1. Un incident technique bloquant (`incident`)
2. Une demande d'évolution fonctionnelle pertinente exprimée par l'utilisateur métier (`evolution`)

GARDE-FOU OBLIGATOIRE : L'envoi nécessite toujours le flag `--confirm`, qui ne doit
être activé qu'après accord explicite de l'utilisateur métier dans la conversation.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.appscript_email import send_appscript_email
from tools.config import get_business_user, get_org_info, get_tech_support


def build_support_email_html(
    report_type: str,
    user_action: str,
    tool_name: str,
    details: str,
) -> tuple[str, str]:
    """Construit l'objet et le corps HTML du rapport destiné au référent technique."""
    org = get_org_info()
    user = get_business_user()
    support = get_tech_support()
    now_str = datetime.now().strftime("%d/%m/%Y à %H:%M:%S")

    org_name = org.get("name", "Organisation")
    user_name = user.get("full_name", "L'utilisateur métier")
    support_name = support.get("name", "Référent Technique")

    if report_type == "incident":
        subject = f"[INCIDENT] {org_name} - Blocage signalé par {user_name}"
        badge_color = "#c84b31"
        title = "Signalement d'incident bloquant"
        intro = (
            f"{html.escape(user_name)} a rencontré un blocage en utilisant l'assistant "
            f"de communication et a confirmé l'envoi de ce rapport."
        )
        details_label = "Détails techniques & trace complète"
    else:
        subject = f"[ÉVOLUTION] {org_name} - Besoin exprimé par {user_name}"
        badge_color = "#1f5c4b"
        title = "Demande d'évolution fonctionnelle"
        intro = (
            f"{html.escape(user_name)} a exprimé un besoin pertinent qui dépasse les "
            f"capacités actuelles de l'assistant et a souhaité vous en informer."
        )
        details_label = "Description du besoin & piste technique suggérée"

    html_body = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; background-color: #f4f2eb; padding: 24px; color: #111111;">
  <div style="max-width: 640px; margin: 0 auto; background: #fbf8f0; border: 1px solid #e2dec9; border-radius: 8px; padding: 28px;">
    <p style="margin: 0 0 8px 0; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: {badge_color}; font-weight: bold;">
      {html.escape(org_name)} — {html.escape(title)}
    </p>
    <p style="margin: 0 0 16px 0; font-size: 15px;">Bonjour {html.escape(support_name)},</p>
    <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.5;">{intro}</p>
    <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px;">
      <tr>
        <td style="padding: 8px 0; border-bottom: 1px solid #e2dec9; font-weight: bold; width: 35%;">Date</td>
        <td style="padding: 8px 0; border-bottom: 1px solid #e2dec9;">{now_str}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; border-bottom: 1px solid #e2dec9; font-weight: bold;">Demande de {html.escape(user.get('first_name', 'l’utilisateur'))}</td>
        <td style="padding: 8px 0; border-bottom: 1px solid #e2dec9;">{html.escape(user_action)}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; border-bottom: 1px solid #e2dec9; font-weight: bold;">Outil / Module concerné</td>
        <td style="padding: 8px 0; border-bottom: 1px solid #e2dec9;"><code>{html.escape(tool_name)}</code></td>
      </tr>
    </table>
    <p style="font-weight: bold; font-size: 14px; margin-bottom: 8px;">{details_label} :</p>
    <pre style="background: #111111; color: #f4f2eb; padding: 14px; border-radius: 6px; font-size: 12px; white-space: pre-wrap; word-break: break-word;">{html.escape(details)}</pre>
  </div>
</body>
</html>"""
    return subject, html_body


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Envoie un rapport d'incident ou une demande d'évolution au référent technique."
    )
    parser.add_argument(
        "type",
        choices=["incident", "evolution"],
        help="Type de ticket : 'incident' (erreur bloquante) ou 'evolution' (nouveau besoin métier)",
    )
    parser.add_argument(
        "--action",
        required=True,
        help="Action demandée en langage naturel par l'utilisateur métier",
    )
    parser.add_argument(
        "--tool",
        default="assistant-general",
        help="Script ou connecteur concerné (ex: tools/brevo_tool.py)",
    )
    parser.add_argument(
        "--details",
        required=True,
        help="Trace technique complète (pour un incident) ou spécification du besoin (pour une évolution)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirme que l'utilisateur métier a donné son accord explicite pour envoyer ce signalement",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule l'envoi du ticket sans appeler le webhook d'e-mail",
    )

    args = parser.parse_args()
    user = get_business_user()
    support = get_tech_support()

    if not args.confirm:
        print(
            json.dumps(
                {
                    "status": "confirmation_required",
                    "message": (
                        f"Halte : demandez d'abord l'accord de {user.get('first_name', 'l’utilisateur')} "
                        f"avant de prévenir {support.get('name', 'le référent technique')}, "
                        f"puis relancez la commande avec --confirm."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    subject, html_body = build_support_email_html(
        report_type=args.type,
        user_action=args.action,
        tool_name=args.tool,
        details=args.details,
    )

    recipient = support.get("email", "support@exemple.org")
    result = send_appscript_email(
        to_email=recipient,
        subject=subject,
        html_body=html_body,
        dry_run=args.dry_run,
    )
    result["ticket_type"] = args.type
    result["support_contact"] = support.get("name")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
