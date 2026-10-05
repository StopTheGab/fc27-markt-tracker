"""AES-256-GCM envelope for the public `data` branch.

The price source's licence (FUTNext: personal, non-commercial use, no mirroring) does not allow
republishing its prices openly, so everything except status.json is encrypted. The key lives only in
.env (DATA_KEY) and in the dashboard link fragment (#k=…), which browsers never send to a server.
"""
from __future__ import annotations

import base64
import json
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import ENV_PATH


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def ensure_key(env: dict[str, str]) -> str:
    """Return DATA_KEY; generate and append it to .env on first use."""
    key = env.get("DATA_KEY", "").strip()
    if key:
        return key
    key = b64url(secrets.token_bytes(32))
    with open(ENV_PATH, "a", encoding="utf-8") as f:
        f.write("\n# Schlüssel für die verschlüsselten Dashboard-Daten (automatisch erzeugt, nicht teilen)\n"
                f"DATA_KEY={key}\n")
    env["DATA_KEY"] = key
    return key


def encrypt_bytes(key_b64: str, plaintext: bytes) -> dict:
    iv = os.urandom(12)
    ct = AESGCM(b64url_decode(key_b64)).encrypt(iv, plaintext, None)
    return {"v": 1, "alg": "AES-256-GCM", "iv": base64.b64encode(iv).decode(), "ct": base64.b64encode(ct).decode()}


def decrypt_envelope(key_b64: str, env: dict) -> bytes:
    return AESGCM(b64url_decode(key_b64)).decrypt(base64.b64decode(env["iv"]), base64.b64decode(env["ct"]), None)


def encrypt_file_json(key_b64: str, plaintext: bytes) -> str:
    return json.dumps(encrypt_bytes(key_b64, plaintext), separators=(",", ":"))
