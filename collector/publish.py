"""Force-push export/ as a single orphan commit to the `data` branch.

A fresh one-commit branch each time keeps the remote small (no ever-growing history).
The branch contains dashboard/vercel.json with deploymentEnabled=false, so Vercel never
builds it (plus the main-branch vercel.json and the project's ignored-build-step setting).
Credentials: the local git credential manager (no token in this code or the repo).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import stat
import subprocess

from . import crypto
from .config import EXPORT_DIR, PUBLISH_DIR, Settings

log = logging.getLogger("publish")

README = """# FC27 Markt-Tracker – Daten

Automatisch erzeugt vom lokalen Collector (alle 15 Minuten, force-push, immer nur ein Commit).
Preisdaten sind AES-256-GCM-verschlüsselt (Lizenz der Preisquelle erlaubt keine öffentliche Spiegelung);
nur `status.json` ist Klartext.
Format: siehe `docs/DATA_CONTRACT.md` im Branch `main`. Nicht von Hand bearbeiten.
"""


def _git(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=PUBLISH_DIR, capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def publish(settings: Settings, message: str) -> tuple[bool, str]:
    if not settings.publish_enabled:
        return True, "Publish deaktiviert (DATA_PUBLISH_ENABLED=false)"
    try:
        if PUBLISH_DIR.exists():
            shutil.rmtree(PUBLISH_DIR, onexc=_force_remove)  # git objects are read-only on Windows
        PUBLISH_DIR.mkdir(parents=True)
        # Everything except status.json is encrypted (source licence: no public mirroring)
        key = crypto.ensure_key(settings.env)
        for src in EXPORT_DIR.rglob("*.json"):
            rel = src.relative_to(EXPORT_DIR)
            dst = PUBLISH_DIR / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if rel.as_posix() == "status.json":
                shutil.copyfile(src, dst)
            else:
                dst.write_text(crypto.encrypt_file_json(key, src.read_bytes()), encoding="utf-8")
        (PUBLISH_DIR / "README.md").write_text(README, encoding="utf-8")
        (PUBLISH_DIR / "dashboard").mkdir(exist_ok=True)
        (PUBLISH_DIR / "dashboard" / "vercel.json").write_text(
            json.dumps({"git": {"deploymentEnabled": False}}), encoding="utf-8")
        (PUBLISH_DIR / "vercel.json").write_text(
            json.dumps({"git": {"deploymentEnabled": False}}), encoding="utf-8")
        steps = [
            ["init", "-q", "-b", settings.data_branch],
            ["config", "user.name", "fc27-collector"],
            ["config", "user.email", "fc27-collector@users.noreply.github.com"],
            ["config", "core.autocrlf", "false"],
            ["add", "-A"],
            ["commit", "-q", "-m", message],
        ]
        for s in steps:
            r = _git(s)
            if r.returncode != 0:
                return False, f"git {s[0]} fehlgeschlagen: {r.stderr.strip()[:300]}"
        r = _git(["push", "-q", "--force", settings.repo_url, f"HEAD:refs/heads/{settings.data_branch}"], timeout=180)
        if r.returncode != 0:
            return False, f"git push fehlgeschlagen: {r.stderr.strip()[:300]}"
        return True, "ok"
    except Exception as e:  # never crash the collector
        log.exception("publish failed")
        return False, f"publish Fehler: {e}"
