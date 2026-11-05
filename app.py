"""ApplyPilot: evidence-grounded job search analysis with human approval gates."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator



ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
DB = os.getenv("APPLYPILOT_DB", str(ROOT / "applypilot.db"))
DEFAULT_PROFILE = {
    "headline": "",
    "skills": ["Python", "FastAPI", "SQL", "React", "JavaScript", "LLM applications"],
    "target_roles": ["AI Engineer", "AI Builder", "Software Engineer", "Backend Engineer", "Full Stack Engineer"],
    "years_experience": 1,
    "advanced_spanish": False,
    "requires_us_sponsorship": True,
    "projects": [],
}

app = FastAPI(title="ApplyPilot", version="1.0.0", description="Evidence-grounded job search agent with human approval")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connection() -> sqlite3.Connection:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("""CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL, title TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE, description TEXT NOT NULL, score INTEGER NOT NULL,
        decision TEXT NOT NULL, reasons TEXT NOT NULL, draft TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'awaiting_review', analysis TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY AUTOINCREMENT, application_id INTEGER, event TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(application_id) REFERENCES applications(id))")
    db.commit()
    return db


def load_profile(db: sqlite3.Connection | None = None) -> dict[str, Any]:
    owned = db is None
    db = db or connection()
    row = db.execute("SELECT value FROM settings WHERE key='profile'").fetchone()
    profile = {**DEFAULT_PROFILE, **(json.loads(row[0]) if row else {})}
    if owned:
        db.close()
    return profile


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    db = connection()
    db.execute("INSERT INTO settings(key,value) VALUES('profile',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(profile),))
    db.commit()
    db.close()
    return profile


class Job(BaseModel):
    company: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=160)
    url: str = Field(min_length=8, max_length=1200)
    description: str = Field(min_length=30, max_length=40000)

    @field_validator("url")
    @classmethod
    def valid_public_url(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("Use an http or https listing URL")
        return value


class ProfileInput(BaseModel):
    headline: str = Field(default="", max_length=300)
    skills: list[str] = Field(default_factory=list, max_length=60)
    target_roles: list[str] = Field(default_factory=list, max_length=30)
    years_experience: int = Field(default=0, ge=0, le=60)
    advanced_spanish: bool = False
    requires_us_sponsorship: bool = False
    projects: list[dict[str, str]] = Field(default_factory=list, max_length=30)


class Review(BaseModel):
    approved: bool


class ReviewDraft(BaseModel):
    draft: str = Field(min_length=1, max_length=12000)


def evaluate(job: Job, profile: dict[str, Any]) -> dict[str, Any]:
    text = f"{job.title} {job.description}".lower()
    blockers: list[str] = []
    notes: list[str] = []
    if re.search(r"(fluent|native|advanced|c1|c2)\s+(in\s+)?spanish|spanish\s+(fluency|c1|c2|required)", text) and not profile.get("advanced_spanish"):
        blockers.append("Advanced Spanish appears required")
    us_role = bool(re.search(r"\b(us|usa|united states|san francisco|new york|seattle|california)\b", text))
    if us_role and profile.get("requires_us_sponsorship") and re.search(r"no visa sponsorship|cannot sponsor|unable to sponsor|must have (unrestricted|existing) work authorization|without sponsorship", text):
        blockers.append("The listing appears to require existing US work authorization")
    years = [int(n) for n in re.findall(r"\b(\d{1,2})\s*\+?\s*years?\b", text)]
    max_years = max(years, default=0)
    experience_gap = max_years > int(profile.get("years_experience", 0)) + 1
    if experience_gap:
        notes.append(f"Experience requirement may be above your profile ({max_years} years mentioned)")
    skills = profile.get("skills", [])
    matched = [s for s in skills if s.strip() and re.search(r"\b" + re.escape(s.strip().lower()) + r"\b", text)]
    title = job.title.lower()
    targets = [r.lower().strip() for r in profile.get("target_roles", []) if r.strip()]
    role_match = any(r in title for r in targets)
    score = max(0, min(100, (30 if role_match else 8) + min(50, len(matched) * 10) - (15 if experience_gap else 0)))
    if matched:
        notes.append("Matching profile skills: " + ", ".join(matched))
    else:
        notes.append("No configured skills matched explicitly")
    notes.append("Target role match" if role_match else "Role title is outside configured targets")
    if blockers:
        notes.extend(blockers)
    decision = "blocked" if blockers else "strong_match" if score >= 65 else "review" if score >= 35 else "low_match"
    return {"score": score, "decision": decision, "reasons": notes, "blockers": blockers, "matched_skills": matched, "experience_gap": experience_gap}


def starter_draft(job: Job, profile: dict[str, Any], reasons: list[str]) -> str:
    projects = profile.get("projects") or []
    project_line = ""
    if projects:
        p = projects[0]
        project_line = f"\n\nA relevant project is {p.get('name', 'a project')}" + (f" ({p.get('url')})" if p.get("url") else "") + "."
    return (f"Subject: {job.title} — {job.company}\n\nHello {job.company} team,\n\n"
            f"I’m applying for the {job.title} role. {profile.get('headline') or 'My background includes building software and applied AI projects.'}"
            f"{project_line}\n\nI’d welcome the opportunity to discuss how I could contribute.\n\nBest,\n[Your name]\n\n"
            "— Review before sending: confirm every claim, add a specific reason for this company, and attach the right resume.")


def record_activity(db: sqlite3.Connection, app_id: int, event: str, detail: str) -> None:
    db.execute("INSERT INTO activity(application_id,event,detail,created_at) VALUES(?,?,?,?)", (app_id, event, detail, now()))


async def run_agent(job: Job, profile: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any] | None:
    provider = os.getenv("APPLYPILOT_PROVIDER", "rules")
    if provider == "openai":
        from paid_agent import analyze
    elif provider == "ollama":
        from local_agent import analyze
    else:
        return None
    return await analyze(job.model_dump(), profile, baseline)


def row_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for key in ("reasons", "analysis"):
        d[key] = json.loads(d[key]) if d.get(key) else [] if key == "reasons" else {}
    return d


@app.get("/")
def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/health")
def health() -> dict[str, Any]:
    from paid_agent import configured
    provider = os.getenv("APPLYPILOT_PROVIDER", "rules")
    ready = configured() if provider == "openai" else bool(os.getenv("APPLYPILOT_LOCAL_MODEL")) if provider == "ollama" else False
    return {"ok": True, "agent_configured": ready, "provider": provider, "model": os.getenv("APPLYPILOT_MODEL", "gpt-4.1-mini") if provider == "openai" else os.getenv("APPLYPILOT_LOCAL_MODEL", ""), "paid_enabled": configured(), "version": "1.1.0"}


@app.get("/api/profile")
def get_profile() -> dict[str, Any]:
    return load_profile()


@app.put("/api/profile")
def put_profile(profile: ProfileInput) -> dict[str, Any]:
    return save_profile(profile.model_dump())


@app.get("/api/applications")
def applications() -> list[dict[str, Any]]:
    db = connection()
    rows = [row_dict(r) for r in db.execute("SELECT * FROM applications ORDER BY updated_at DESC, id DESC")]
    db.close()
    return rows


@app.get("/api/applications/{application_id}")
def application(application_id: int) -> dict[str, Any]:
    db = connection()
    row = db.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Application not found")
    return row_dict(row)


@app.get("/api/activity")
def activity() -> list[dict[str, Any]]:
    db = connection()
    rows = [dict(r) for r in db.execute("SELECT * FROM activity ORDER BY id DESC LIMIT 100")]
    db.close()
    return rows


@app.post("/api/jobs/analyze")
async def analyze_job(job: Job) -> dict[str, Any]:
    profile = load_profile()
    baseline = evaluate(job, profile)
    llm = await run_agent(job, profile, baseline)
    agent_used = bool(llm and not llm.get("agent_error"))
    draft = llm.get("outreach_draft") if agent_used else starter_draft(job, profile, baseline["reasons"])
    analysis = llm if agent_used else {"summary": "Rule-based result. AI was not used for this analysis. Check your connection settings or the recorded error.", "strengths": baseline["matched_skills"], "risks": baseline["blockers"] or (baseline["reasons"] if baseline["experience_gap"] else []), "next_steps": ["Review the listing and confirm work authorization requirements", "Verify all profile evidence before using the draft"], "agent_error": llm.get("agent_error") if llm else None}
    status = "blocked" if baseline["decision"] == "blocked" else "awaiting_review"
    db = connection()
    db.execute("""INSERT INTO applications(company,title,url,description,score,decision,reasons,draft,status,analysis,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET company=excluded.company,title=excluded.title,description=excluded.description,
        score=excluded.score,decision=excluded.decision,reasons=excluded.reasons,draft=excluded.draft,status=excluded.status,analysis=excluded.analysis,updated_at=excluded.updated_at""",
        (job.company, job.title, job.url, job.description, baseline["score"], baseline["decision"], json.dumps(baseline["reasons"]), draft, status, json.dumps(analysis), now(), now()))
    row = db.execute("SELECT * FROM applications WHERE url=?", (job.url,)).fetchone()
    record_activity(db, row["id"], "analyzed", f"{'Agent' if agent_used else 'Rules'} analysis · score {baseline['score']}")
    db.commit()
    result = row_dict(db.execute("SELECT * FROM applications WHERE id=?", (row["id"],)).fetchone())
    db.close()
    result["agent_used"] = agent_used
    return result


@app.patch("/api/applications/{application_id}/draft")
def update_draft(application_id: int, body: ReviewDraft) -> dict[str, Any]:
    db = connection()
    row = db.execute("SELECT id FROM applications WHERE id=?", (application_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Application not found")
    db.execute("UPDATE applications SET draft=?,updated_at=? WHERE id=?", (body.draft, now(), application_id))
    record_activity(db, application_id, "draft_edited", "User edited the outreach draft")
    db.commit(); db.close()
    return {"saved": True}


@app.post("/api/applications/{application_id}/review")
def review(application_id: int, body: Review) -> dict[str, Any]:
    db = connection()
    row = db.execute("SELECT decision,status FROM applications WHERE id=?", (application_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Application not found")
    if body.approved and row["decision"] == "blocked":
        db.close()
        raise HTTPException(409, "This job has a hard eligibility blocker. Recheck the profile or listing first.")
    status = "approved_draft" if body.approved else "dismissed"
    db.execute("UPDATE applications SET status=?,updated_at=? WHERE id=?", (status, now(), application_id))
    record_activity(db, application_id, "draft_approved" if body.approved else "dismissed", "Draft marked ready for the user's next step" if body.approved else "Application dismissed")
    db.commit(); db.close()
    return {"status": status, "sent": False, "note": "ApplyPilot never sends emails or submits applications."}


@app.delete("/api/applications/{application_id}")
def delete_application(application_id: int) -> dict[str, bool]:
    db = connection()
    row = db.execute("SELECT id FROM applications WHERE id=?", (application_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Application not found")
    db.execute("DELETE FROM activity WHERE application_id=?", (application_id,))
    db.execute("DELETE FROM applications WHERE id=?", (application_id,))
    db.commit(); db.close()
    return {"deleted": True}


class AutopilotAnswers(BaseModel):
    full_name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=250)
    phone: str = Field(default="", max_length=80)
    linkedin: str = Field(default="", max_length=500)
    github: str = Field(default="", max_length=500)
    location: str = Field(default="", max_length=200)
    relocation: str = Field(default="", max_length=500)
    notice_period: str = Field(default="", max_length=500)
    work_authorization: str = Field(default="", max_length=1000)
    interests_and_constraints: str = Field(default="", max_length=4000)
    saved_answers: str = Field(default="", max_length=15000)
    auto_submit: bool = False


class ApplicationLink(BaseModel):
    url: str = Field(min_length=10, max_length=1500)


def private_json(name, default):
    from automation import DATA
    path = DATA / name
    return json.loads(path.read_text()) if path.exists() else default


@app.get('/api/autopilot/settings')
def autopilot_settings():
    return private_json('answers.json', AutopilotAnswers().model_dump())


@app.put('/api/autopilot/settings')
def update_autopilot_settings(body: AutopilotAnswers):
    from automation import DATA
    DATA.mkdir(exist_ok=True, mode=0o700)
    path = DATA / 'answers.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(body.model_dump()))
    temporary.replace(path)
    return {'saved': True}


@app.get('/api/documents')
def documents():
    return [{k:v for k,v in document.items() if k not in ('path', 'text')} for document in private_json('documents.json', [])]


@app.post('/api/documents')
async def upload_document(file: UploadFile = File(...), kind: str = Form(...), description: str = Form('')):
    import uuid
    from automation import DATA, LOCK
    if kind not in ('resume', 'cover_letter') or len(description) > 1000:
        raise HTTPException(422, 'Choose resume or cover letter and a description under 1000 characters.')
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ('.pdf', '.docx', '.txt'):
        raise HTTPException(422, 'Use PDF, DOCX, or TXT files.')
    content = await file.read(10 * 1024 * 1024 + 1)
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, 'Upload a nonempty document under 10 MB.')
    try:
        import io
        if suffix == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            extracted = '\n'.join(page.extract_text() or '' for page in reader.pages[:12])
        elif suffix == '.docx':
            import zipfile
            from xml.etree import ElementTree
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                metadata = archive.getinfo('word/document.xml')
                if metadata.file_size > 2 * 1024 * 1024:
                    raise ValueError('Document text is too large')
                tree = ElementTree.fromstring(archive.read('word/document.xml'))
                extracted = ' '.join(tree.itertext())
        else:
            extracted = content.decode('utf-8')
    except Exception as exc:
        raise HTTPException(422, 'Could not read document text. Use a text PDF, DOCX, or UTF-8 TXT.') from exc
    if not extracted.strip():
        raise HTTPException(422, 'No readable text was found. Use a text-based document instead of a scanned image.')
    DATA.mkdir(exist_ok=True, mode=0o700)
    identifier = str(uuid.uuid4())
    path = DATA / (identifier + suffix)
    path.write_bytes(content)
    path.chmod(0o600)
    document = {'id': identifier, 'name': Path(file.filename).name, 'kind': kind, 'description': description, 'text': extracted[:12000], 'path': str(path)}
    with LOCK:
        saved = private_json('documents.json', [])
        saved.append(document)
        temporary = DATA / 'documents.tmp'
        temporary.write_text(json.dumps(saved))
        temporary.replace(DATA / 'documents.json')
    return {k:v for k,v in document.items() if k not in ('path', 'text')}


@app.post('/api/autopilot')
def launch_autopilot(body: ApplicationLink):
    from automation import start
    settings = autopilot_settings()
    if not settings['full_name'] or not settings['email']:
        raise HTTPException(422, 'Save your full name and email in Autopilot setup first.')
    saved_documents = private_json('documents.json', [])
    if not any(document['kind'] == 'resume' for document in saved_documents):
        raise HTTPException(422, 'Upload at least one resume before starting.')
    try:
        return start(body.url, load_profile(), settings, saved_documents)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/api/autopilot/{run_id}')
def autopilot_run(run_id: str):
    from automation import get_run
    try:
        return get_run(run_id)
    except (ValueError, KeyError):
        raise HTTPException(404, 'Run not found')


@app.post('/api/autopilot/{run_id}/continue')
def continue_autopilot(run_id: str):
    from automation import WAKE, get_run
    run = get_run(run_id)
    if run.get('state') != 'paused' or run_id not in WAKE:
        raise HTTPException(409, 'This browser run is not waiting for input.')
    WAKE[run_id].set()
    return {'continuing': True}
