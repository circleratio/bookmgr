import math
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# server/app/config.py -> repo root is two levels up, server/ is one level up.
REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = str(REPO_ROOT / "db" / "bookmgr.db")
DEFAULT_MIGRATIONS_DIR = str(REPO_ROOT / "db" / "migrations")
DEFAULT_TEMPLATES_DIR = str(SERVER_DIR / "templates")
DEFAULT_STATIC_DIR = str(SERVER_DIR / "static")

# The API key is the sole credential for both the REST API and the web
# screens, so require enough length to make online guessing infeasible.
MIN_API_KEY_LENGTH = 32
# Floor for the character-frequency entropy estimate (see
# estimate_entropy_bits). It only rejects keys built from very few distinct
# characters: genuinely random keys score well above it (secrets.token_hex(16),
# the weakest common 32-character format, measured >= 91 bits over 200k samples).
MIN_API_KEY_ENTROPY_BITS = 80


def estimate_entropy_bits(value: str) -> float:
    """Estimates entropy as length x Shannon entropy of the character
    frequencies. A crude upper bound: it cannot recognize dictionary words."""
    n = len(value)
    return -n * sum(c / n * math.log2(c / n) for c in Counter(value).values())


def is_repeated_pattern(value: str) -> bool:
    """True if value is a shorter string repeated, e.g. "password" * 4."""
    return len(value) > 1 and value in (value + value)[1:-1]


def api_key_weakness(api_key: str) -> str | None:
    """Returns why api_key is too weak to use, or None if it is acceptable."""
    if len(api_key) < MIN_API_KEY_LENGTH:
        return f"API_KEY must be at least {MIN_API_KEY_LENGTH} characters"
    if is_repeated_pattern(api_key):
        return "API_KEY must not be a repeated pattern"
    if estimate_entropy_bits(api_key) < MIN_API_KEY_ENTROPY_BITS:
        return "API_KEY uses too few distinct characters to be a random key"
    return None


@dataclass
class Settings:
    api_key: str
    # Loopback by default so a forgotten HOST never exposes plain HTTP
    # publicly; set HOST=0.0.0.0 explicitly to accept remote connections.
    host: str = "127.0.0.1"
    port: int = 8080
    db_path: str = DEFAULT_DB_PATH
    migrations_dir: str = DEFAULT_MIGRATIONS_DIR
    templates_dir: str = DEFAULT_TEMPLATES_DIR
    static_dir: str = DEFAULT_STATIC_DIR
    google_books_api_key: str = ""
    # Mark the session cookie Secure (HTTPS-only). Leave false for plain-HTTP
    # local development; set true when served over HTTPS (e.g. behind Caddy),
    # since browsers silently drop Secure cookies set over plain HTTP.
    cookie_secure: bool = False
    # uvicorn access log. Request lines include query strings (search terms,
    # ISBNs), so it can be turned off with ACCESS_LOG=false for privacy.
    access_log: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = os.environ.get("API_KEY")
        if not api_key:
            raise RuntimeError("API_KEY environment variable is required")
        weakness = api_key_weakness(api_key)
        if weakness:
            raise RuntimeError(
                f"{weakness} "
                "(e.g. generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
            )
        return cls(
            api_key=api_key,
            host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "8080")),
            db_path=os.environ.get("DB_PATH", DEFAULT_DB_PATH),
            google_books_api_key=os.environ.get("GOOGLE_BOOKS_API_KEY", ""),
            cookie_secure=os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes"),
            access_log=os.environ.get("ACCESS_LOG", "true").lower() not in ("0", "false", "no"),
        )
