"""Environment-backed application settings."""

from dataclasses import dataclass
import os
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    """Load simple KEY=VALUE entries without overriding the process environment."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    database_path: Path
    ai_provider: str
    ai_api_key: str | None
    ai_model: str | None


def get_settings() -> Settings:
    _load_dotenv()
    raw_database_path = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "shyam_manual.db"))
    return Settings(
        database_path=Path(raw_database_path).expanduser(),
        ai_provider=os.getenv("AI_PROVIDER", "mock").strip().lower() or "mock",
        ai_api_key=os.getenv("AI_API_KEY") or None,
        ai_model=os.getenv("AI_MODEL") or None,
    )
