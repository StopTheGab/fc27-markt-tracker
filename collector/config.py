"""Paths and settings. Secrets come only from .env (gitignored)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
EXPORT_DIR = ROOT / "export"
PUBLISH_DIR = DATA_DIR / "publish"
DB_PATH = DATA_DIR / "fc27.sqlite"
PID_FILE = DATA_DIR / "collector.pid"
STOP_FILE = DATA_DIR / "STOP"
HEARTBEAT_FILE = DATA_DIR / "heartbeat.txt"
WATCHLIST_PATH = ROOT / "watchlist.json"
CALENDAR_PATH = ROOT / "market_calendar.json"
ENV_PATH = ROOT / ".env"

VERSION = "1.0.0"
TZ_LOCAL = "Europe/Berlin"


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    """Minimal .env parser (KEY=VALUE, # comments). Process env overrides file."""
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            env[key.strip()] = value
    for key, value in os.environ.items():
        if key.startswith(("FC27_", "MAIL_", "SMTP_", "RESEND_", "FUTDB_", "DATA_", "DASHBOARD_")):
            env[key] = value
    return env


def flag(env: dict[str, str], key: str, default: bool) -> bool:
    value = env.get(key)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "ja", "on")


class Settings:
    def __init__(self, env: dict[str, str] | None = None):
        self.env = env if env is not None else load_env()
        e = self.env
        self.interval_minutes = int(e.get("FC27_INTERVAL_MINUTES", "15"))
        self.repo_url = e.get("DATA_REPO_URL", "https://github.com/StopTheGab/fc27-markt-tracker.git")
        self.data_branch = e.get("DATA_BRANCH", "data")
        self.publish_enabled = flag(e, "DATA_PUBLISH_ENABLED", True)
        self.dashboard_url = e.get("DASHBOARD_URL", "https://fc27-markt-tracker.vercel.app")
        # Mail
        self.mail_provider = e.get("MAIL_PROVIDER", "none").strip().lower()  # resend | smtp | none
        self.mail_to = e.get("MAIL_TO", "gabriel.anter123@outlook.com")
        self.mail_from = e.get("MAIL_FROM", "FC27 Tracker <onboarding@resend.dev>")
        self.mail_signals_enabled = flag(e, "MAIL_SIGNALS_ENABLED", True)
        self.mail_hourly_enabled = flag(e, "MAIL_HOURLY_ENABLED", True)
        self.mail_daily_cap = int(e.get("MAIL_DAILY_CAP", "90"))
        self.resend_api_key = e.get("RESEND_API_KEY", "")
        self.smtp_host = e.get("SMTP_HOST", "")
        self.smtp_port = int(e.get("SMTP_PORT", "587") or 587)
        self.smtp_user = e.get("SMTP_USER", "")
        self.smtp_password = e.get("SMTP_PASSWORD", "")
        self.smtp_starttls = flag(e, "SMTP_STARTTLS", True)
        # History import per run (spreads load on the source)
        self.history_imports_per_run = int(e.get("FC27_HISTORY_IMPORTS_PER_RUN", "15"))

    @property
    def dashboard_link(self) -> str:
        """Dashboard URL incl. decryption key in the fragment (never sent to a server)."""
        key = self.env.get("DATA_KEY", "")
        return f"{self.dashboard_url.rstrip('/')}/#k={key}" if key else self.dashboard_url


def ensure_dirs() -> None:
    for d in (DATA_DIR, LOG_DIR, EXPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)
