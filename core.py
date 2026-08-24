"""
CRM Multi-Agent System — Core
Shared database, agent registry, logging, and orchestration primitives.
DB: agent_crm.db  (SQLite, WAL mode)
"""
import sqlite3
import time
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path.home() / ".crm_agents" / "agent_crm.db"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def ensure_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def get_db() -> sqlite3.Connection:
    ensure_dir()
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domain TEXT,
            website TEXT,
            country TEXT,
            city TEXT,
            industry TEXT,
            description TEXT,
            est_size TEXT,
            founded_year TEXT,
            revenue_range TEXT,
            employees_min INTEGER,
            employees_max INTEGER,
            tags TEXT,
            decision_maker TEXT,
            dm_title TEXT,
            dm_email TEXT,
            dm_phone TEXT,
            email TEXT,
            email_source TEXT,
            phone TEXT,
            phone_source TEXT,
            whatsapp TEXT,
            instagram TEXT,
            tiktok TEXT,
            facebook TEXT,
            linkedin TEXT,
            twitter TEXT,
            youtube TEXT,
            other_social TEXT,
            primary_contact TEXT,
            contact_confidence REAL,
            source TEXT,
            source_url TEXT,
            scrape_html_len INTEGER,
            scored INTEGER DEFAULT 0,
            opportunity_score INTEGER,
            best_service TEXT,
            notes TEXT,
            export_ready INTEGER DEFAULT 0,
            duplicate_of INTEGER,
            status TEXT DEFAULT 'new',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            value TEXT NOT NULL,
            source TEXT,
            confidence REAL,
            verified INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT,
            detail TEXT,
            result TEXT,
            duration_ms INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL,
            problem TEXT NOT NULL,
            cause TEXT,
            correction TEXT,
            confidence REAL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observation TEXT NOT NULL,
            old_weight REAL,
            new_weight REAL,
            change_for_next_run TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS good_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            company_id INTEGER,
            message TEXT NOT NULL,
            seen INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS companies_fts USING fts5(
            name, domain, website, country, city, industry, description,
            tags, decision_maker, dm_title, source, notes,
            content='companies', content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS companies_ai AFTER INSERT ON companies BEGIN
            INSERT INTO companies_fts(rowid, name, domain, website, country, city, industry, description, tags, decision_maker, dm_title, source, notes)
            VALUES (new.id, new.name, new.domain, new.website, new.country, new.city, new.industry, new.description, new.tags, new.decision_maker, new.dm_title, new.source, new.notes);
        END;
        CREATE TRIGGER IF NOT EXISTS companies_ad AFTER DELETE ON companies BEGIN
            INSERT INTO companies_fts(companies_fts, rowid, name, domain, website, country, city, industry, description, tags, decision_maker, dm_title, source, notes)
            VALUES ('delete', old.id, old.name, old.domain, old.website, old.country, old.city, old.industry, old.description, old.tags, old.decision_maker, old.dm_title, old.source, old.notes);
        END;
        CREATE TRIGGER IF NOT EXISTS companies_au AFTER UPDATE ON companies BEGIN
            INSERT INTO companies_fts(companies_fts, rowid, name, domain, website, country, city, industry, description, tags, decision_maker, dm_title, source, notes)
            VALUES ('delete', old.id, old.name, old.domain, old.website, old.country, old.city, old.industry, old.description, old.tags, old.decision_maker, old.dm_title, old.source, old.notes);
            INSERT INTO companies_fts(rowid, name, domain, website, country, city, industry, description, tags, decision_maker, dm_title, source, notes)
            VALUES (new.id, new.name, new.domain, new.website, new.country, new.city, new.industry, new.description, new.tags, new.decision_maker, new.dm_title, new.source, new.notes);
        END;
    """)
    conn.commit()
    conn.close()

class Agent:
    def __init__(self, name: str):
        self.name = name

    def run(self, action, target="", detail="", fn=None, *args, **kwargs):
        start = time.time()
        try:
            result = fn(*args, **kwargs) if fn else None
            duration_ms = int((time.time() - start) * 1000)
            if result is not None:
                try:
                    detail_json = json.dumps(result, default=str)
                except Exception:
                    detail_json = str(result)
            else:
                detail_json = None
            log_run(self.name, action, target, detail, detail_json, duration_ms)
            return result
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            log_error(self.name, str(exc), "", "", 0.0)
            raise

    def log(self, action, target="", detail="", result=None, duration_ms=None):
        if duration_ms is None:
            duration_ms = 0
        if result is not None:
            try:
                result = json.dumps(result, default=str)
            except Exception:
                result = str(result)
        log_run(self.name, action, target, detail, result, duration_ms)

def log_run(agent, action, target, detail, result, duration_ms):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO agent_runs(agent, action, target, detail, result, duration_ms, created_at) VALUES (?,?,?,?,?,?,?)",
            (agent, action, target, detail, result, duration_ms, _now())
        )
        conn.commit()
    finally:
        conn.close()

def log_error(agent, problem, cause, correction, confidence):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO agent_errors(agent, problem, cause, correction, confidence, created_at) VALUES (?,?,?,?,?,?)",
            (agent, problem, cause, correction, confidence, _now())
        )
        conn.commit()
    finally:
        conn.close()

def log_lesson(observation, old_weight, new_weight, change):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO agent_lessons(observation, old_weight, new_weight, change_for_next_run, created_at) VALUES (?,?,?,?,?)",
            (observation, old_weight, new_weight, change, _now())
        )
        conn.commit()
    finally:
        conn.close()

def log_good_news(kind, company_id, message):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO good_news(kind, company_id, message, created_at) VALUES (?,?,?,?)",
            (kind, company_id, message, _now())
        )
        conn.commit()
    finally:
        conn.close()

def _now():
    return datetime.now(timezone.utc).isoformat()

def upsert_company(**fields):
    now = _now()
    defaults = {
        "tags": "[]",
        "other_social": "{}",
        "scored": 0,
        "opportunity_score": 0,
        "export_ready": 0,
        "status": "new",
    }
    for k, v in defaults.items():
        fields.setdefault(k, v)
    fields["updated_at"] = now
    fields["created_at"] = fields.get("created_at", now)

    conn = get_db()
    try:
        cols = [k for k in fields if k not in ("id",)]
        placeholders = ",".join("?" for _ in cols)
        col_str = ",".join(cols)
        values = [fields[c] for c in cols]
        conn.execute(
            f"INSERT INTO companies ({col_str}) VALUES ({placeholders})",
            values
        )
        conn.commit()
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return cid
    except sqlite3.IntegrityError:
        if "domain" in fields and fields["domain"]:
            conn.execute(
                "UPDATE companies SET name=?, website=?, country=?, city=?, industry=?, description=?, "
                "est_size=?, founded_year=?, revenue_range=?, employees_min=?, employees_max=?, "
                "tags=?, decision_maker=?, dm_title=?, dm_email=?, dm_phone=?, email=?, email_source=?, "
                "phone=?, phone_source=?, whatsapp=?, instagram=?, tiktok=?, facebook=?, linkedin=?, "
                "twitter=?, youtube=?, other_social=?, primary_contact=?, contact_confidence=?, "
                "source=?, source_url=?, scrape_html_len=?, scored=?, opportunity_score=?, best_service=?, "
                "notes=?, export_ready=?, status=?, updated_at=? WHERE domain=?",
                [fields.get(c) for c in [
                    "name","website","country","city","industry","description","est_size","founded_year",
                    "revenue_range","employees_min","employees_max","tags","decision_maker","dm_title",
                    "dm_email","dm_phone","email","email_source","phone","phone_source","whatsapp","instagram",
                    "tiktok","facebook","linkedin","twitter","youtube","other_social","primary_contact",
                    "contact_confidence","source","source_url","scrape_html_len","scored","opportunity_score",
                    "best_service","notes","export_ready","status","updated_at","domain"
                ]]
            )
            conn.commit()
            row = conn.execute("SELECT id FROM companies WHERE domain=?", (fields["domain"],)).fetchone()
            cid = row["id"] if row else None
        else:
            cid = None
        return cid
    finally:
        conn.close()

def get_company(cid):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
        return row
    finally:
        conn.close()

def search_companies(query, limit=50, offset=0, filters=None):
    conn = get_db()
    try:
        base = "SELECT c.* FROM companies c JOIN companies_fts fts ON c.id = fts.rowid WHERE companies_fts MATCH ?"
        params = [query]
        if filters:
            if filters.get("country"):
                base += " AND c.country = ?"
                params.append(filters["country"])
            if filters.get("industry"):
                base += " AND c.industry = ?"
                params.append(filters["industry"])
            if filters.get("status"):
                base += " AND c.status = ?"
                params.append(filters["status"])
            if filters.get("min_score"):
                base += " AND c.opportunity_score >= ?"
                params.append(filters["min_score"])
            if filters.get("has_email"):
                base += " AND c.email != ''"
            if filters.get("has_phone"):
                base += " AND c.phone != ''"
            if filters.get("has_social"):
                base += " AND (c.instagram != '' OR c.tiktok != '' OR c.facebook != '' OR c.linkedin != '')"
        base += " ORDER BY c.opportunity_score DESC, c.updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(base, params).fetchall()
        return rows
    finally:
        conn.close()

def set_company_field(cid, **fields):
    conn = get_db()
    try:
        now = _now()
        fields["updated_at"] = now
        cols = [k for k in fields if k not in ("id", "created_at")]
        if not cols:
            return False
        set_clause = ", ".join(f"{c} = ?" for c in cols)
        values = [fields[c] for c in cols] + [cid]
        conn.execute(f"UPDATE companies SET {set_clause} WHERE id=?", values)
        conn.commit()
        return True
    finally:
        conn.close()

def add_contact(company_id, type_, value, source="", confidence=0.5):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO contacts(company_id, type, value, source, confidence, created_at) VALUES (?,?,?,?,?,?)",
            (company_id, type_, value, source, confidence, _now())
        )
        conn.commit()
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        type_rank = {"email": 5, "whatsapp": 4, "phone": 3, "instagram": 2, "tiktok": 2,
                     "facebook": 1, "linkedin": 1, "twitter": 1, "youtube": 1, "other": 0}
        rank = type_rank.get(type_, 0)
        cur = conn.execute("SELECT primary_contact, contact_confidence FROM companies WHERE id=?", (company_id,)).fetchone()
        if cur:
            old_rank = type_rank.get(cur["primary_contact"], -1) if cur["primary_contact"] else -1
            if rank > old_rank or (rank == old_rank and confidence > (cur["contact_confidence"] or 0)):
                conn.execute(
                    "UPDATE companies SET primary_contact=?, contact_confidence=?, updated_at=? WHERE id=?",
                    (type_, confidence, _now(), company_id)
                )
                conn.commit()
        return cid
    finally:
        conn.close()

def get_contacts(company_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM contacts WHERE company_id=? ORDER BY CASE type WHEN 'email' THEN 1 WHEN 'whatsapp' THEN 2 WHEN 'phone' THEN 3 ELSE 4 END",
            (company_id,)
        ).fetchall()
    finally:
        conn.close()

def get_recent_agent_runs(limit=100):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()

def get_good_news(unseen=True):
    conn = get_db()
    try:
        if unseen:
            rows = conn.execute(
                "SELECT * FROM good_news WHERE seen=0 ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            for r in rows:
                conn.execute("UPDATE good_news SET seen=1 WHERE id=?", (r["id"],))
                conn.commit()
            return rows
        return conn.execute("SELECT * FROM good_news ORDER BY created_at DESC LIMIT 50").fetchall()
    finally:
        conn.close()

def mark_company_exported(cid):
    conn = get_db()
    try:
        conn.execute("UPDATE companies SET export_ready=1, updated_at=? WHERE id=?", (_now(), cid))
        conn.commit()
    finally:
        conn.close()

def get_stats():
    conn = get_db()
    try:
        s = {}
        s["total_companies"] = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        s["with_email"] = conn.execute("SELECT COUNT(*) FROM companies WHERE email != ''").fetchone()[0]
        s["with_phone"] = conn.execute("SELECT COUNT(*) FROM companies WHERE phone != ''").fetchone()[0]
        s["with_whatsapp"] = conn.execute("SELECT COUNT(*) FROM companies WHERE whatsapp != ''").fetchone()[0]
        s["with_instagram"] = conn.execute("SELECT COUNT(*) FROM companies WHERE instagram != ''").fetchone()[0]
        s["with_tiktok"] = conn.execute("SELECT COUNT(*) FROM companies WHERE tiktok != ''").fetchone()[0]
        s["with_facebook"] = conn.execute("SELECT COUNT(*) FROM companies WHERE facebook != ''").fetchone()[0]
        s["with_linkedin"] = conn.execute("SELECT COUNT(*) FROM companies WHERE linkedin != ''").fetchone()[0]
        s["contacted"] = conn.execute("SELECT COUNT(*) FROM companies WHERE status='contacted'").fetchone()[0]
        s["qualified"] = conn.execute("SELECT COUNT(*) FROM companies WHERE status='qualified'").fetchone()[0]
        s["converted"] = conn.execute("SELECT COUNT(*) FROM companies WHERE status='converted'").fetchone()[0]
        s["high_opp"] = conn.execute("SELECT COUNT(*) FROM companies WHERE opportunity_score >= 70").fetchone()[0]
        s["total_contacts"] = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        return s
    finally:
        conn.close()

def get_setting(key, default=""):
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()

def set_setting(key, value):
    conn = get_db()
    try:
        conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)", (key, value))
        conn.commit()
    finally:
        conn.close()

init_db()
print("CRM DB initialized at", DB_PATH)
