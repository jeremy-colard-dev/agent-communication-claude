#!/usr/bin/env python3
"""
Synchronisation Git sécurisée (`git_sync.py`).
Garantit que les fichiers sensibles (`.env`, `service_account.json`) ne sont JAMAIS
indexés ni poussés par erreur lorsque l'agent sauvegarde les créations de l'utilisateur métier.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FORBIDDEN_FILES = [".env", "service_account.json"]


def _run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=check,
    )


def safe_sync(message: str, dry_run: bool = False) -> dict[str, object]:
    """Ajoute les créations, désindexe proactivement tout fichier secret et pousse sur la branche active."""
    branch_proc = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    current_branch = branch_proc.stdout.strip() or "main"

    if dry_run:
        return {
            "status": "dry_run",
            "branch": current_branch,
            "commit_message": message,
            "protected_files": FORBIDDEN_FILES,
        }

    _run_git(["add", "-A"], check=False)
    for secret_file in FORBIDDEN_FILES:
        _run_git(["reset", "HEAD", secret_file], check=False)

    status_proc = _run_git(["status", "--porcelain"], check=False)
    if not status_proc.stdout.strip():
        return {"status": "clean", "branch": current_branch, "message": "Aucune modification à sauvegarder."}

    _run_git(["commit", "-m", message], check=True)
    push_proc = _run_git(["push", "-u", "origin", current_branch], check=False)
    return {
        "status": "pushed" if push_proc.returncode == 0 else "committed_locally",
        "branch": current_branch,
        "commit_message": message,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sauvegarde Git sécurisée sans fuite de secrets.")
    parser.add_argument(
        "--message",
        "-m",
        default="chore: sauvegarde automatique des créations de communication",
        help="Message de commit",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    res = safe_sync(args.message, dry_run=args.dry_run)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
