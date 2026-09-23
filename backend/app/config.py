import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = Path(os.environ.get("SCOUT_DATA_DIR", BACKEND_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "scout.db"
AUTH_PATH = DATA_DIR / "auth.json"

# Signs the session cookie. Set SCOUT_SECRET_KEY yourself in production;
# a random one is generated on first run otherwise (invalidates sessions
# on every restart, which is fine for a single-user local tool).
SECRET_KEY = os.environ.get("SCOUT_SECRET_KEY")
if not SECRET_KEY:
    _secret_path = DATA_DIR / ".secret_key"
    if _secret_path.exists():
        SECRET_KEY = _secret_path.read_text().strip()
    else:
        SECRET_KEY = os.urandom(32).hex()
        _secret_path.write_text(SECRET_KEY)

SESSION_COOKIE_NAME = "scout_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY")

# How often the background ingestion loop refreshes each source, in seconds.
INGEST_INTERVAL_SECONDS = int(os.environ.get("SCOUT_INGEST_INTERVAL_SECONDS", 60 * 60 * 6))
