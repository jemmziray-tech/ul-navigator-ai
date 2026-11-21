"""Admin authentication, rate limiting keys and upload validation."""
from __future__ import annotations

import csv
import getpass
import io
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter

from .config import get_settings

_bearer = HTTPBearer(auto_error=False)

ALLOWED_UPLOADS = {".pdf": "pdf", ".csv": "csv", ".rtf": "rtf", ".txt": "txt", ".md": "md"}


# ----------------------------------------------------------------- rate limiting
def client_ip(request: Request) -> str:
    if get_settings().trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip, default_limits=[get_settings().rate_limit_default],
                  headers_enabled=False)


# ----------------------------------------------------------------- passwords/JWT
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def admin_configured() -> bool:
    s = get_settings()
    return bool(s.admin_password_hash and s.jwt_secret
                and len(s.jwt_secret.get_secret_value()) >= 32)


def authenticate(username: str, password: str) -> bool:
    s = get_settings()
    if not admin_configured():
        return False
    ok_user = username == s.admin_username
    ok_pw = verify_password(password, s.admin_password_hash.get_secret_value())
    return ok_user and ok_pw


def create_token(username: str) -> tuple[str, datetime]:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expiry_minutes)
    token = jwt.encode({"sub": username, "exp": exp, "role": "admin"},
                       s.jwt_secret.get_secret_value(), algorithm="HS256")
    return token, exp


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if not admin_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Admin access is not configured on this server.")
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret.get_secret_value(),
                             algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"}) from None
    if payload.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return payload["sub"]


# ----------------------------------------------------------------- uploads
def safe_filename(name: str) -> str:
    base = Path(name or "upload").name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "upload"
    return base[:120]


def validate_upload(filename: str, data: bytes) -> str:
    """Returns the file kind or raises ValueError with a user-safe message."""
    s = get_settings()
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_UPLOADS:
        raise ValueError(f"File type {ext or '(none)'} is not allowed. "
                         f"Allowed: {', '.join(sorted(ALLOWED_UPLOADS))}")
    if not data:
        raise ValueError("The file is empty.")
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise ValueError(f"File exceeds the {s.max_upload_mb} MB limit.")
    kind = ALLOWED_UPLOADS[ext]
    if kind == "pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("File content is not a valid PDF.")
        if b"/JavaScript" in data or b"/JS " in data or b"/Launch" in data:
            raise ValueError("PDFs containing embedded scripts or launch actions are rejected.")
        return kind
    if kind == "rtf" and not data.lstrip().startswith(b"{\\rtf"):
        raise ValueError("File content is not valid RTF.")
    if b"\x00" in data[:8192]:
        raise ValueError("Binary content is not allowed for text-based uploads.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Text files must be UTF-8 encoded.") from None
    if kind == "csv":
        try:
            header = next(csv.reader(io.StringIO(text[:20000])))
        except (StopIteration, csv.Error):
            raise ValueError("CSV file could not be parsed.") from None
        if len([h for h in header if h.strip()]) < 1:
            raise ValueError("CSV needs a header row.")
    return kind


if __name__ == "__main__":  # python -m app.security hash-password
    if len(sys.argv) > 1 and sys.argv[1] == "hash-password":
        pw = getpass.getpass("Admin password: ")
        if len(pw) < 12:
            sys.exit("Use at least 12 characters.")
        print(hash_password(pw))
    elif len(sys.argv) > 1 and sys.argv[1] == "jwt-secret":
        import secrets
        print(secrets.token_urlsafe(48))
    else:
        print("usage: python -m app.security [hash-password|jwt-secret]")
