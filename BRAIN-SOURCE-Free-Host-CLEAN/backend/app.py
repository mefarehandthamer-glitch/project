"""BRAIN SOURCE optional persistent backend.
Run with: uvicorn app:app --host 0.0.0.0 --port 8000
Set BRAIN_SOURCE_ADMIN_PASSWORD and BRAIN_SOURCE_SECRET_KEY before starting.
"""
from __future__ import annotations
import csv, hashlib, hmac, io, json, os, secrets, sqlite3, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DATABASE_URL = os.environ.get("BRAIN_SOURCE_DATABASE_URL", "").strip()
DB_PATH = Path(os.environ.get("BRAIN_SOURCE_DB", str(ROOT / "data" / "brain_source.sqlite3")))
if not DATABASE_URL:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_KIND = "postgresql" if DATABASE_URL else "sqlite"
if os.environ.get("RENDER") and not DATABASE_URL:
    raise RuntimeError("Hosted Render deployments must set BRAIN_SOURCE_DATABASE_URL to a persistent PostgreSQL database. SQLite on the free filesystem can lose data.")
ADMIN_PASSWORD = os.environ.get("BRAIN_SOURCE_ADMIN_PASSWORD", "")
SECRET_KEY = os.environ.get("BRAIN_SOURCE_SECRET_KEY", "")
COOKIE_SECURE = os.environ.get("BRAIN_SOURCE_COOKIE_SECURE", "0") == "1"
SESSION_HOURS = int(os.environ.get("BRAIN_SOURCE_SESSION_HOURS", "12"))
APP_VERSION = "1.2.0"

app = FastAPI(title="BRAIN SOURCE API", version=APP_VERSION, docs_url="/api/docs" if os.environ.get("BRAIN_SOURCE_SHOW_API_DOCS") == "1" else None, redoc_url=None)


class DBConnection:
    """Small DB adapter so the same API works with SQLite locally or hosted PostgreSQL."""
    def __init__(self):
        self.kind = DB_KIND
        if DATABASE_URL:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            self.raw = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=10)
        else:
            self.raw = sqlite3.connect(DB_PATH, timeout=15)
            self.raw.row_factory = sqlite3.Row
            self.raw.execute("PRAGMA foreign_keys=ON")
            self.raw.execute("PRAGMA journal_mode=WAL")

    def execute(self, sql, params=()):
        if self.kind == "postgresql":
            cur = self.raw.cursor()
            cur.execute(sql.replace("?", "%s"), params)
            return cur
        return self.raw.execute(sql, params)

    def executescript(self, script):
        if self.kind == "postgresql":
            for statement in script.split(";"):
                if statement.strip():
                    self.execute(statement)
        else:
            self.raw.executescript(script)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.raw.commit()
            else:
                self.raw.rollback()
        finally:
            self.raw.close()
        return False


def connect() -> DBConnection:
    return DBConnection()


def init_db() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS app_data (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        payload TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        created_at BIGINT NOT NULL,
        expires_at BIGINT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS appointments (
        id TEXT PRIMARY KEY,
        participant TEXT NOT NULL,
        scheduled_at TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'planned',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS drafts (
        participant TEXT NOT NULL,
        draft_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (participant, draft_id)
    );
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT NOT NULL,
        created_at TEXT NOT NULL,
        details TEXT NOT NULL DEFAULT '{}'
    );
    """
    if DATABASE_URL:
        schema = schema.replace("id INTEGER PRIMARY KEY AUTOINCREMENT", "id BIGSERIAL PRIMARY KEY")
    with connect() as con:
        con.executescript(schema)

init_db()

class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=1024)

class DataBody(BaseModel):
    participants: list[str] = Field(min_length=1, max_length=100)
    attempts: list[dict[str, Any]] = Field(max_length=100000)

class AppointmentBody(BaseModel):
    participant: str = Field(min_length=1, max_length=80)
    scheduled_at: str = Field(min_length=10, max_length=80)
    note: str = Field(default="", max_length=500)
    status: str = Field(default="planned", pattern="^(planned|completed|cancelled)$")

class DraftBody(BaseModel):
    participant: str = Field(min_length=1, max_length=80)
    draft_id: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def log_event(event: str, details: dict[str, Any] | None = None) -> None:
    with connect() as con:
        con.execute("INSERT INTO audit_log(event, created_at, details) VALUES(?,?,?)", (event, now_iso(), json.dumps(details or {}, separators=(",", ":"))))

def token_hash(token: str) -> str:
    key = SECRET_KEY.encode() if SECRET_KEY else b"brain-source-local-session-key"
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()

def verify_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    # Same-origin only. Reverse proxies should preserve the public Host header.
    from urllib.parse import urlsplit
    parsed = urlsplit(origin)
    host = request.headers.get("host", "")
    if parsed.netloc.lower() != host.lower():
        raise HTTPException(status_code=403, detail="Cross-origin request rejected")

async def require_admin(request: Request) -> str:
    token = request.cookies.get("bs_admin")
    if not token:
        raise HTTPException(status_code=401, detail="Admin login required")
    th = token_hash(token)
    with connect() as con:
        row = con.execute("SELECT expires_at FROM sessions WHERE token_hash=?", (th,)).fetchone()
        if not row or row["expires_at"] < int(time.time()):
            if row:
                con.execute("DELETE FROM sessions WHERE token_hash=?", (th,))
            raise HTTPException(status_code=401, detail="Session expired")
    return th

# Minimal in-memory login throttling. Put a rate-limiting proxy in front for public deployments.
LOGIN_FAILS: dict[str, list[float]] = {}
def check_login_rate(ip: str) -> None:
    now = time.time()
    recent = [t for t in LOGIN_FAILS.get(ip, []) if now - t < 600]
    LOGIN_FAILS[ip] = recent
    if len(recent) >= 8:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in ten minutes.")

def record_login_failure(ip: str) -> None:
    LOGIN_FAILS.setdefault(ip, []).append(time.time())

@app.get("/api/health")
def health():
    try:
        with connect() as con:
            con.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return {"ok": db_ok, "version": APP_VERSION, "database": DB_KIND, "admin_configured": bool(ADMIN_PASSWORD and SECRET_KEY)}

@app.post("/api/login")
def login(body: LoginBody, request: Request, response: Response):
    verify_origin(request)
    ip = request.client.host if request.client else "unknown"
    check_login_rate(ip)
    if not ADMIN_PASSWORD or not SECRET_KEY:
        raise HTTPException(status_code=503, detail="Admin authentication is not configured. Set BRAIN_SOURCE_ADMIN_PASSWORD and BRAIN_SOURCE_SECRET_KEY.")
    if not hmac.compare_digest(body.password.encode(), ADMIN_PASSWORD.encode()):
        record_login_failure(ip)
        log_event("login_failed")
        raise HTTPException(status_code=401, detail="Incorrect password")
    LOGIN_FAILS.pop(ip, None)
    token = secrets.token_urlsafe(48)
    now = int(time.time())
    with connect() as con:
        con.execute("INSERT INTO sessions(token_hash, created_at, expires_at) VALUES(?,?,?)", (token_hash(token), now, now + SESSION_HOURS * 3600))
    response.set_cookie("bs_admin", token, httponly=True, secure=COOKIE_SECURE, samesite="strict", max_age=SESSION_HOURS * 3600, path="/")
    log_event("login_success")
    return {"ok": True, "expires_at": datetime.fromtimestamp(now + SESSION_HOURS*3600, timezone.utc).isoformat()}

@app.get("/api/me")
async def me(_: str = Depends(require_admin)):
    return {"authenticated": True}

@app.post("/api/logout")
async def logout(request: Request, response: Response):
    verify_origin(request)
    token = request.cookies.get("bs_admin")
    if token:
        with connect() as con:
            con.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))
    response.delete_cookie("bs_admin", path="/", httponly=True, secure=COOKIE_SECURE, samesite="strict")
    return {"ok": True}

@app.get("/api/data")
async def get_data(_: str = Depends(require_admin)):
    with connect() as con:
        row = con.execute("SELECT payload, updated_at FROM app_data WHERE id=1").fetchone()
    if not row:
        return {"participants": ["P1", "P2", "P3", "P4", "P5", "P6"], "attempts": [], "updated_at": None}
    return {**json.loads(row["payload"]), "updated_at": row["updated_at"]}

@app.put("/api/data")
async def put_data(body: DataBody, request: Request, _: str = Depends(require_admin)):
    verify_origin(request)
    if len(json.dumps(body.model_dump(), separators=(",", ":"))) > 25_000_000:
        raise HTTPException(status_code=413, detail="Dataset is too large")
    # Preserve the app's expected shape and reject malformed attempt records.
    for item in body.attempts:
        if not isinstance(item, dict) or not item.get("id") or not item.get("participant") or not item.get("activity"):
            raise HTTPException(status_code=422, detail="Each attempt must include id, participant, and activity")
    payload = json.dumps({"participants": body.participants, "attempts": body.attempts}, ensure_ascii=False, separators=(",", ":"))
    stamp = now_iso()
    with connect() as con:
        con.execute("INSERT INTO app_data(id,payload,updated_at) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", (payload, stamp))
    log_event("data_saved", {"participants": len(body.participants), "attempts": len(body.attempts)})
    return {"ok": True, "updated_at": stamp, "attempts": len(body.attempts)}

@app.get("/api/appointments")
async def get_appointments(_: str = Depends(require_admin)):
    with connect() as con:
        rows = con.execute("SELECT * FROM appointments ORDER BY scheduled_at").fetchall()
    return [dict(r) for r in rows]

@app.post("/api/appointments")
async def create_appointment(body: AppointmentBody, request: Request, _: str = Depends(require_admin)):
    verify_origin(request)
    try:
        datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail="scheduled_at must be an ISO date/time")
    aid = secrets.token_urlsafe(12)
    with connect() as con:
        con.execute("INSERT INTO appointments(id,participant,scheduled_at,note,status,created_at) VALUES(?,?,?,?,?,?)", (aid, body.participant, body.scheduled_at, body.note, body.status, now_iso()))
    log_event("appointment_created", {"participant": body.participant, "status": body.status})
    return {"id": aid, **body.model_dump(), "created_at": now_iso()}

@app.patch("/api/appointments/{appointment_id}")
async def update_appointment(appointment_id: str, body: AppointmentBody, request: Request, _: str = Depends(require_admin)):
    verify_origin(request)
    with connect() as con:
        cur = con.execute("UPDATE appointments SET participant=?, scheduled_at=?, note=?, status=? WHERE id=?", (body.participant, body.scheduled_at, body.note, body.status, appointment_id))
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="Appointment not found")
    return {"ok": True, "id": appointment_id, **body.model_dump()}

@app.delete("/api/appointments/{appointment_id}")
async def delete_appointment(appointment_id: str, request: Request, _: str = Depends(require_admin)):
    verify_origin(request)
    with connect() as con:
        cur = con.execute("DELETE FROM appointments WHERE id=?", (appointment_id,))
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="Appointment not found")
    return {"ok": True}

@app.put("/api/drafts")
async def save_draft(body: DraftBody, request: Request, _: str = Depends(require_admin)):
    verify_origin(request)
    payload = json.dumps(body.payload, ensure_ascii=False, separators=(",", ":"))
    if len(payload) > 2_000_000:
        raise HTTPException(status_code=413, detail="Draft too large")
    stamp = now_iso()
    with connect() as con:
        con.execute("INSERT INTO drafts(participant,draft_id,payload,updated_at) VALUES(?,?,?,?) ON CONFLICT(participant,draft_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", (body.participant, body.draft_id, payload, stamp))
    return {"ok": True, "updated_at": stamp}

@app.get("/api/drafts")
async def list_drafts(_: str = Depends(require_admin)):
    with connect() as con:
        rows = con.execute("SELECT participant,draft_id,payload,updated_at FROM drafts ORDER BY updated_at DESC LIMIT 100").fetchall()
    return [{"participant": r["participant"], "draft_id": r["draft_id"], "payload": json.loads(r["payload"]), "updated_at": r["updated_at"]} for r in rows]

@app.get("/api/drafts/{participant}/{draft_id}")
async def get_draft(participant: str, draft_id: str, _: str = Depends(require_admin)):
    with connect() as con:
        row = con.execute("SELECT payload,updated_at FROM drafts WHERE participant=? AND draft_id=?", (participant, draft_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"payload": json.loads(row["payload"]), "updated_at": row["updated_at"]}

@app.delete("/api/drafts/{participant}/{draft_id}")
async def delete_draft(participant: str, draft_id: str, request: Request, _: str = Depends(require_admin)):
    verify_origin(request)
    with connect() as con:
        con.execute("DELETE FROM drafts WHERE participant=? AND draft_id=?", (participant, draft_id))
    return {"ok": True}

@app.get("/api/export.csv")
async def export_csv(_: str = Depends(require_admin)):
    with connect() as con:
        row = con.execute("SELECT payload FROM app_data WHERE id=1").fetchone()
    payload = json.loads(row["payload"]) if row else {"participants": [], "attempts": []}
    fields = ["participant", "attempt_id", "activity", "mode", "status", "correct", "total", "normalized", "accuracy", "elapsedMs", "timestamp"]
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in payload.get("attempts", []):
        writer.writerow({"participant": item.get("participant"), "attempt_id": item.get("id"), "activity": item.get("activity"), "mode": item.get("mode"), "status": item.get("status"), "correct": item.get("correct"), "total": item.get("total"), "normalized": item.get("normalized"), "accuracy": item.get("accuracy"), "elapsedMs": item.get("elapsedMs"), "timestamp": item.get("timestamp")})
    return StreamingResponse(iter(["\ufeff" + out.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=brain-source-results.csv"})

@app.get("/api/admin/audit")
async def audit(_: str = Depends(require_admin)):
    with connect() as con:
        rows = con.execute("SELECT event,created_at,details FROM audit_log ORDER BY id DESC LIMIT 200").fetchall()
    return [{"event": r["event"], "created_at": r["created_at"], "details": json.loads(r["details"])} for r in rows]

@app.get("/")
def index():
    return FileResponse(ROOT / "index.html")

