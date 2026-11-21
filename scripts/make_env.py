"""Creates .env from .env.example with freshly generated admin secrets (runs locally)."""
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
env_path = ROOT / ".env"
if env_path.exists():
    print(".env already exists - left unchanged")
    sys.exit(0)
from app.security import hash_password  # noqa: E402

pw = "ULNav-" + secrets.token_urlsafe(12)
env = (ROOT / ".env.example").read_text(encoding="utf-8")
env = env.replace("GEMINI_API_KEY=your-gemini-api-key-here", "GEMINI_API_KEY=")
env = env.replace("ADMIN_PASSWORD_HASH=\n", f"ADMIN_PASSWORD_HASH={hash_password(pw)}\n")
env = env.replace("JWT_SECRET=\n", f"JWT_SECRET={secrets.token_urlsafe(48)}\n")
env = env.replace("contact: your-email@example.com",
                  "by John Elifuraha Mziray, University of Limerick student")
env_path.write_text(env, encoding="utf-8")
(ROOT / "data").mkdir(exist_ok=True)
(ROOT / "data" / "ADMIN_PASSWORD.txt").write_text(
    f"Admin username: admin\nAdmin password: {pw}\n(Change it with: python -m app.security hash-password)\n",
    encoding="utf-8")
print(".env created; admin password saved to data\\ADMIN_PASSWORD.txt")
