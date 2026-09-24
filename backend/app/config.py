import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = Path(os.environ.get("BUREAU_DATA_DIR", BACKEND_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "bureau.db"
AUTH_PATH = DATA_DIR / "auth.json"

# The CV that leads get matched against. Under data/, so it's gitignored
# and never leaves this machine — but it IS on disk, unlike Sabha itself
# which holds a CV in memory only. See app/sabha.py for that tradeoff.
CV_PATH = DATA_DIR / "cv.txt"

# Signs the session cookie. Set BUREAU_SECRET_KEY yourself in production;
# a random one is generated on first run otherwise (invalidates sessions
# on every restart, which is fine for a single-user local tool).
SECRET_KEY = os.environ.get("BUREAU_SECRET_KEY")
if not SECRET_KEY:
    _secret_path = DATA_DIR / ".secret_key"
    if _secret_path.exists():
        SECRET_KEY = _secret_path.read_text().strip()
    else:
        SECRET_KEY = os.urandom(32).hex()
        _secret_path.write_text(SECRET_KEY)

SESSION_COOKIE_NAME = "bureau_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY")

# Sabha (the local hiring-council service) and the Ollama it runs on. Both
# are local-only by nature; nothing here reaches the internet.
SABHA_URL = os.environ.get("BUREAU_SABHA_URL", "http://127.0.0.1:8700")
OLLAMA_URL = os.environ.get("BUREAU_OLLAMA_URL", "http://127.0.0.1:11434")
# The screen runs once per lead, so smaller is tempting — but llama3.2:3b
# was measured scoring a German inbound-call-centre role 80/100 against a
# backend engineer's CV, and a React role 0. Every 8B+ model tested got
# both right. qwen2.5:14b discriminated best and is already resident for
# Sabha's council, so it costs no extra GPU memory: ~5s/lead.
SCREEN_MODEL = os.environ.get("BUREAU_SCREEN_MODEL", "qwen2.5:14b")

# How often the background ingestion loop refreshes each source, in seconds.
INGEST_INTERVAL_SECONDS = int(os.environ.get("BUREAU_INGEST_INTERVAL_SECONDS", 60 * 60 * 6))
