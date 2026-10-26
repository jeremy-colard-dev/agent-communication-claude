#!/usr/bin/env python3
"""
Module central de configuration et d'utilitaires sans dépendances tierces.
Conçu pour fonctionner nativement dans les environnements éphémères (ex: Claude Code Web)
sans nécessiter de `pip install` pour l'authentification Cloud ou la lecture de secrets.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

# Neutralise le jeton expiré parfois injecté par défaut dans certaines VM cloud éphémères
os.environ.pop("CLOUDSDK_AUTH_ACCESS_TOKEN", None)

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
ORG_CONFIG_PATH = ROOT_DIR / "config" / "organization.json"
SERVICE_ACCOUNT_PATH = ROOT_DIR / "service_account.json"


def _load_dotenv(dotenv_path: Path) -> Dict[str, str]:
    """Charge un fichier .env standard sans dépendance externe (python-dotenv non requis)."""
    values: Dict[str, str] = {}
    if not dotenv_path.exists():
        return values

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and ((val[0] == val[-1] == '"') or (val[0] == val[-1] == "'")):
            val = val[1:-1]
        values[key] = val
    return values


def load_organization_config() -> Dict[str, Any]:
    """Charge le fichier déclaratif `config/organization.json`."""
    if not ORG_CONFIG_PATH.exists():
        return {
            "organization": {
                "name": "Mon Organisation",
                "short_name": "ORG",
                "email": "contact@exemple.org",
                "phone": "01 00 00 00 00",
                "website": "https://www.exemple.org",
            },
            "business_user": {
                "first_name": "Utilisateur",
                "full_name": "Utilisateur Métier",
                "role": "Responsable Communication",
                "email": "communication@exemple.org",
            },
            "tech_support": {
                "name": "Référent Technique",
                "role": "Administrateur",
                "email": "support@exemple.org",
            },
            "design_system": {
                "colors": {
                    "background_outer": "#f4f2eb",
                    "background_card": "#fbf8f0",
                    "text_primary": "#111111",
                    "accent_primary": "#1f5c4b",
                    "accent_highlight": "#c84b31",
                },
                "rules": {
                    "allow_emojis_in_emails": False,
                    "instagram_margin_hex": "#f4f2eb",
                },
            },
            "connectors": {},
        }
    return json.loads(ORG_CONFIG_PATH.read_text(encoding="utf-8"))


_DOTENV_CACHE = _load_dotenv(ENV_PATH)
ORG_CONFIG = load_organization_config()


def get_env(key: str, default: str = "") -> str:
    """Récupère une variable depuis l'environnement système ou le fichier `.env`."""
    return os.environ.get(key) or _DOTENV_CACHE.get(key, default)


def get_org_info() -> Dict[str, Any]:
    """Retourne les métadonnées de l'organisation."""
    return ORG_CONFIG.get("organization", {})


def get_business_user() -> Dict[str, Any]:
    """Retourne le profil de l'utilisateur métier non-technique."""
    return ORG_CONFIG.get("business_user", {})


def get_tech_support() -> Dict[str, str]:
    """Retourne les coordonnées du référent technique (surchargeables via .env)."""
    support = dict(ORG_CONFIG.get("tech_support", {}))
    if get_env("TECH_SUPPORT_NAME"):
        support["name"] = get_env("TECH_SUPPORT_NAME")
    if get_env("TECH_SUPPORT_EMAIL"):
        support["email"] = get_env("TECH_SUPPORT_EMAIL")
    return support


def get_design_rules() -> Dict[str, Any]:
    """Retourne les règles du design system définies dans `config/organization.json`."""
    return ORG_CONFIG.get("design_system", {})


# Plage Unicode couvrant les émojis et pictogrammes courants
_EMOJI_REGEX = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U00002600-\U000026FF"
    "\U0000FE0F"
    "]+",
    flags=re.UNICODE,
)


def strip_emojis_if_configured(text: str) -> str:
    """
    Supprime automatiquement les émojis si `allow_emojis_in_emails` vaut `false`
    dans `config/organization.json`. Garantit le respect de la charte éditoriale
    sans bloquer l'utilisateur métier.
    """
    if not text:
        return text
    rules = get_design_rules().get("rules", {})
    if rules.get("allow_emojis_in_emails", False):
        return text
    cleaned = _EMOJI_REGEX.sub("", text)
    cleaned = re.sub(r"  +", " ", cleaned)
    return cleaned.strip()


def load_gcp_service_account() -> Optional[Dict[str, Any]]:
    """
    Charge les identifiants du compte de service GCP (optionnel) :
    1. Depuis la variable d'environnement `GCP_SERVICE_ACCOUNT_JSON` (JSON brut ou Base64)
    2. Ou depuis le fichier local `service_account.json`
    """
    raw_env = get_env("GCP_SERVICE_ACCOUNT_JSON")
    if raw_env:
        try:
            if raw_env.strip().startswith("{"):
                return json.loads(raw_env)
            decoded = base64.b64decode(raw_env).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            pass

    if SERVICE_ACCOUNT_PATH.exists():
        try:
            return json.loads(SERVICE_ACCOUNT_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def get_gcp_access_token(
    scopes: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Génère un jeton OAuth2 Google Cloud en signant un JWT RS256 via `openssl`
    et la bibliothèque standard Python (aucune dépendance `google-auth` requise).
    """
    sa = load_gcp_service_account()
    if not sa or "private_key" not in sa or "client_email" not in sa:
        return None

    if scopes is None:
        scopes = [
            "https://www.googleapis.com/auth/devstorage.read_write",
            "https://www.googleapis.com/auth/datastore",
        ]

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": sa["client_email"],
        "scope": " ".join(scopes),
        "aud": sa.get("token_uri", "https://oauth2.googleapis.com/token"),
        "iat": now,
        "exp": now + 3600,
    }

    signing_input = (
        f"{_b64url_encode(json.dumps(header).encode('utf-8'))}."
        f"{_b64url_encode(json.dumps(payload).encode('utf-8'))}"
    )

    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False, encoding="utf-8") as key_file:
        key_file.write(sa["private_key"])
        key_path = key_file.name

    try:
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_path],
            input=signing_input.encode("ascii"),
            capture_output=True,
            check=True,
        )
        signature = _b64url_encode(proc.stdout)
    finally:
        try:
            os.remove(key_path)
        except OSError:
            pass

    assertion = f"{signing_input}.{signature}"
    body = urllib.parse.urlencode(
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        sa.get("token_uri", "https://oauth2.googleapis.com/token"),
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        token_data = json.loads(resp.read().decode("utf-8"))
        return token_data.get("access_token")


def _parse_firestore_value(val_obj: Dict[str, Any]) -> Any:
    """Convertit un champ typé de l'API REST Firestore en type Python natif."""
    if "stringValue" in val_obj:
        return val_obj["stringValue"]
    if "booleanValue" in val_obj:
        return bool(val_obj["booleanValue"])
    if "integerValue" in val_obj:
        return int(val_obj["integerValue"])
    if "doubleValue" in val_obj:
        return float(val_obj["doubleValue"])
    if "nullValue" in val_obj:
        return None
    if "arrayValue" in val_obj:
        values = val_obj["arrayValue"].get("values", [])
        return [_parse_firestore_value(v) for v in values]
    if "mapValue" in val_obj:
        fields = val_obj["mapValue"].get("fields", {})
        return {k: _parse_firestore_value(v) for k, v in fields.items()}
    return None


def fetch_firestore_collection(collection_name: str) -> List[Dict[str, Any]]:
    """
    Lit une collection Firestore via l'API REST HTTPS officielle sans aucun SDK externe.
    Retourne une liste vide si Firestore n'est pas configuré ou désactivé.
    """
    if not collection_name:
        return []
    token = get_gcp_access_token()
    sa = load_gcp_service_account() or {}
    project_id = get_env("GCP_PROJECT_ID") or sa.get("project_id", "")
    if not token or not project_id:
        return []

    results: List[Dict[str, Any]] = []
    page_token = ""
    base_url = (
        f"https://firestore.googleapis.com/v1/projects/{project_id}"
        f"/databases/(default)/documents/{collection_name}"
    )

    while True:
        url = f"{base_url}?pageSize=300"
        if page_token:
            url += f"&pageToken={urllib.parse.quote(page_token)}"

        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError:
            break

        for doc in data.get("documents", []):
            fields = doc.get("fields", {})
            parsed = {k: _parse_firestore_value(v) for k, v in fields.items()}
            parsed["_id"] = doc.get("name", "").rsplit("/", 1)[-1]
            results.append(parsed)

        page_token = data.get("nextPageToken", "")
        if not page_token:
            break

    return results


def print_status() -> None:
    """Affiche un diagnostic lisible de la configuration sans jamais exposer les secrets."""
    org = get_org_info()
    user = get_business_user()
    support = get_tech_support()

    checks = {
        "Brevo API (Newsletters & CRM)": bool(
            get_env("BREVO_API_KEY") and not get_env("BREVO_API_KEY").startswith("xkeysib-votre")
        ),
        "Meta Graph API (Facebook & Instagram)": bool(
            get_env("META_PAGE_ACCESS_TOKEN")
            and not get_env("META_PAGE_ACCESS_TOKEN").startswith("EAA...")
        ),
        "Google Apps Script (E-mails & Support)": bool(
            get_env("APPSCRIPT_WEBHOOK_URL")
            and "VOTRE_ID" not in get_env("APPSCRIPT_WEBHOOK_URL")
        ),
        "Google Cloud Service Account (GCS / Firestore)": load_gcp_service_account() is not None,
    }

    print("=" * 68)
    print(f"DIAGNOSTIC DE CONFIGURATION — {org.get('name', 'Organisation')}")
    print("=" * 68)
    print(f"Utilisateur métier  : {user.get('full_name')} ({user.get('role')})")
    print(f"Référent technique  : {support.get('name')} <{support.get('email')}>")
    print(f"Fichier .env local  : {'Présent' if ENV_PATH.exists() else 'Absent (mode variables env / dry-run)'}")
    print("-" * 68)
    print("État des connecteurs :")
    for label, configured in checks.items():
        badge = "[ACTIF]" if configured else "[NON CONFIGURÉ — Mode --dry-run disponible]"
        print(f"  - {label:<44} : {badge}")
    print("=" * 68)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vérification de la configuration de l'agent de communication."
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status"],
        help="Affiche l'état des connecteurs et des paramètres de l'organisation.",
    )
    parser.parse_args()
    print_status()


if __name__ == "__main__":
    main()
