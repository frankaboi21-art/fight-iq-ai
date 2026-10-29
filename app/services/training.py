"""Private athlete accounts, an evidence journal and a practice/reassessment loop."""
from datetime import date, timedelta
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core import database
from app.core.config import get_settings
from app.core.security import consume_allowance, require_same_origin, require_session

router = APIRouter(prefix="/api/v1/training")
COOKIE = "fightiq_athlete"
DISCIPLINES = Literal["MMA", "Boxing", "Muay Thai", "Kickboxing", "Brazilian Jiu-Jitsu", "Wrestling", "Taekwondo"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Credentials(Strict):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, allow_inf_nan=False)
    handle: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=15, max_length=128)

    @field_validator("handle", mode="before")
    @classmethod
    def lowercase(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class Recovery(Credentials):
    recovery: str = Field(min_length=20, max_length=100)

    @field_validator("recovery", mode="before")
    @classmethod
    def clean_code(cls, value):
        return value.strip() if isinstance(value, str) else value


class Profile(Strict):
    display_name: str = Field(default="", max_length=60)
    discipline: DISCIPLINES = "MMA"
    experience: Literal["Beginner", "Intermediate", "Advanced"] = "Beginner"
    stance: Literal["Orthodox", "Southpaw", "Switch", "Not specified"] = "Not specified"
    goal: str = Field(default="", max_length=600)
    style: str = Field(default="", max_length=200)
    sessions_per_week: int = Field(default=3, ge=1, le=7)
    practice_minutes: int = Field(default=15, ge=5, le=60)
    coaching_policy: Literal["confirmed_advice", "coach_supported_only"] = "confirmed_advice"


class EntryInput(Strict):
    title: str = Field(min_length=1, max_length=100)
    discipline: DISCIPLINES
    purpose: Literal["self", "opponent", "style"] = "self"
    training_type: Literal["drilling", "sparring", "competition", "other"] = "drilling"
    performed_on: date
    minutes: int = Field(ge=1, le=240)
    notes: str = Field(default="", max_length=2000)
    source: str = Field(default="", max_length=300)
    kind: Literal["footage", "corner", "session", "note"]
    report: dict = Field(default_factory=dict)
    receipt: str = Field(default="", max_length=160)

    @field_validator("performed_on")
    @classmethod
    def past_date(cls, value):
        if value > date.today() + timedelta(days=1):
            raise ValueError("A saved review must describe a completed session")
        return value


class Feedback(Strict):
    verdict: Literal["unreviewed", "confirmed", "needs_correction"]
    correction: str = Field(default="", max_length=2000)


class TaskUpdate(Strict):
    status: Literal["planned", "practiced", "reassessed"]
    outcome: Literal["not_checked", "improving", "unchanged", "needs_work"] = "not_checked"
    notes: str = Field(default="", max_length=1000)
    reassessment_entry: str = Field(default="", max_length=40)
    planned_minutes: int | None = Field(default=None, ge=1, le=60)


class Comment(Strict):
    body: str = Field(min_length=1, max_length=2000)


class CoachGrant(Strict):
    handle: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")


class DeleteAccount(Strict):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, allow_inf_nan=False)
    password: str = Field(min_length=1, max_length=128)
    confirmation: Literal["DELETE"]


class Branch(Strict):
    reaction: str = Field(min_length=1, max_length=200)
    response: str = Field(min_length=1, max_length=400)
    exit: str = Field(min_length=1, max_length=300)


class TacticalSystem(Strict):
    title: str = Field(min_length=1, max_length=100)
    discipline: DISCIPLINES
    situation: str = Field(min_length=1, max_length=400)
    cue: str = Field(min_length=1, max_length=300)
    action: str = Field(min_length=1, max_length=400)
    prerequisite: str = Field(min_length=1, max_length=300)
    branches: list[Branch] = Field(min_length=2, max_length=4)
    practice: str = Field(min_length=1, max_length=500)
    success_check: str = Field(min_length=1, max_length=300)
    entry_id: str = Field(default="", max_length=40)


@router.get("/systems")
def systems(request: Request):
    with database.transaction() as db:
        owner = account(request, db)["id"]
        return {"systems": [json.loads(r[0]) for r in db.execute("SELECT data FROM tactical_systems WHERE athlete=? ORDER BY id", (owner,)).fetchall()]}


@router.post("/systems")
def save_system(payload: TacticalSystem, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        if payload.entry_id:
            owned_entry(db, owner, payload.entry_id)
        if db.execute("SELECT COUNT(*) FROM tactical_systems WHERE athlete=?", (owner,)).fetchone()[0] >= 100:
            raise HTTPException(409, "Your tactical library has reached 100 systems.")
        system = {**payload.model_dump(), "id": secrets.token_hex(16), "status": "athlete-authored; review with your coach"}
        db.execute("INSERT INTO tactical_systems VALUES (?,?,?)", (system["id"], owner, json.dumps(system)))
    return {"system": system}


@router.delete("/systems/{system_id}")
def delete_system(system_id: str, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.execute("DELETE FROM tactical_systems WHERE id=? AND athlete=?", (system_id, owner))
    return {"deleted": True}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(value, salt=None):
    salt = salt or secrets.token_hex(16)
    result = hashlib.scrypt(value.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64*1024*1024)
    return salt + ":" + result.hex()


def password_matches(value, encoded):
    return hmac.compare_digest(password_hash(value, encoded.split(":")[0]), encoded)


def canonical(value):
    # Browsers serialize 0.0 as 0. Normalize integral floats before signing.
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value


def receipt(kind, report, nonce=None):
    nonce = nonce or secrets.token_hex(16)
    body = json.dumps(canonical({"kind": kind, "report": report}), sort_keys=True, separators=(",", ":"), allow_nan=False)
    signature = hmac.new(get_settings().beta_access_code.encode(), ("training-report:" + nonce + ":" + body).encode(), hashlib.sha256).hexdigest()
    return nonce + "." + signature


def valid_receipt(kind, report, supplied):
    if not re.fullmatch(r"[0-9a-f]{32}\.[0-9a-f]{64}", supplied):
        return False
    try:
        return hmac.compare_digest(supplied, receipt(kind, report, supplied.split(".")[0]))
    except (ValueError, TypeError, RecursionError):
        return False


def account(request, db):
    token = request.cookies.get(COOKIE, "")
    if not 30 <= len(token) <= 100:
        raise HTTPException(401, "Sign in to your athlete account.")
    row = db.execute("SELECT a.id,a.handle,a.profile FROM athlete_sessions s JOIN athletes a ON s.athlete=a.id WHERE s.token=? AND s.expires>?", (digest(token), time.time())).fetchone()
    if not row:
        raise HTTPException(401, "Sign in to your athlete account.")
    return {"id": row[0], "handle": row[1], "profile": json.loads(row[2])}


def login_cookie(response, db, owner):
    token = secrets.token_urlsafe(32)
    db.execute("DELETE FROM athlete_sessions WHERE expires<?", (time.time(),))
    db.execute("INSERT INTO athlete_sessions VALUES (?,?,?)", (digest(token), owner, time.time()+7*86400))
    response.set_cookie(COOKIE, token, max_age=7*86400, secure=get_settings().environment == "production", httponly=True, samesite="strict", path="/")


def auth_limit(request, handle):
    address = request.client.host if request.client else "unknown"
    consume_allowance("login", digest("athlete-ip:" + address))
    consume_allowance("login", digest("athlete-handle:" + handle))


@router.get("/me")
def me(request: Request):
    if not database.available():
        return {"available": False, "athlete": None}
    with database.transaction() as db:
        try:
            athlete = account(request, db)
        except HTTPException as error:
            if error.status_code != 401:
                raise
            athlete = None
    return {"available": True, "athlete": athlete}


@router.post("/register")
def register(payload: Credentials, request: Request, response: Response):
    require_same_origin(request)
    require_session(request)
    auth_limit(request, payload.handle)
    encoded = password_hash(payload.password)
    recovery = secrets.token_urlsafe(32)
    with database.transaction() as db:
        if db.execute("SELECT id FROM athletes WHERE handle=?", (payload.handle,)).fetchone():
            raise HTTPException(409, "That username is unavailable. Choose another.")
        owner = secrets.token_hex(16)
        inserted = db.execute("INSERT INTO athletes VALUES (?,?,?,?,?,?) ON CONFLICT(handle) DO NOTHING", (owner, payload.handle, encoded, digest(recovery), Profile().model_dump_json(), time.time()))
        if inserted.rowcount != 1:
            raise HTTPException(409, "That username is unavailable. Choose another.")
        login_cookie(response, db, owner)
    return {"recovery_code": recovery, "message": "Save this recovery code in your password manager. It is shown only once."}


@router.post("/login")
def login(payload: Credentials, request: Request, response: Response):
    require_same_origin(request)
    auth_limit(request, payload.handle)
    with database.transaction() as db:
        row = db.execute("SELECT id,password FROM athletes WHERE handle=?", (payload.handle,)).fetchone()
        encoded = row[1] if row else "00"*16 + ":" + "00"*64
        if not password_matches(payload.password, encoded) or not row:
            raise HTTPException(401, "Username or password did not match.")
        login_cookie(response, db, row[0])
    return {"authenticated": True}


@router.post("/recover")
def recover(payload: Recovery, request: Request, response: Response):
    require_same_origin(request)
    auth_limit(request, payload.handle)
    encoded = password_hash(payload.password)
    recovery = secrets.token_urlsafe(32)
    with database.transaction() as db:
        row = db.execute("SELECT id,recovery FROM athletes WHERE handle=?", (payload.handle,)).fetchone()
        if not row or not hmac.compare_digest(row[1], digest(payload.recovery)):
            raise HTTPException(401, "Username or recovery code did not match.")
        db.lock_owner(row[0])
        # Recheck after the lock: a recovery code can only be redeemed once.
        current = db.execute("SELECT recovery FROM athletes WHERE id=?", (row[0],)).fetchone()
        if not current or not hmac.compare_digest(current[0], digest(payload.recovery)):
            raise HTTPException(401, "Username or recovery code did not match.")
        db.execute("UPDATE athletes SET password=?,recovery=? WHERE id=?", (encoded, digest(recovery), row[0]))
        db.execute("DELETE FROM athlete_sessions WHERE athlete=?", (row[0],))
        login_cookie(response, db, row[0])
    return {"recovery_code": recovery, "message": "Password changed. Save the replacement recovery code; the previous code no longer works."}


@router.post("/logout")
def logout(request: Request, response: Response):
    require_same_origin(request)
    with database.transaction() as db:
        db.execute("DELETE FROM athlete_sessions WHERE token=?", (digest(request.cookies.get(COOKIE, "")),))
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=get_settings().environment == "production", samesite="strict")
    return {"authenticated": False}


@router.post("/profile")
def profile(payload: Profile, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        athlete = account(request, db)
        db.execute("UPDATE athletes SET profile=? WHERE id=?", (payload.model_dump_json(), athlete["id"]))
    return {"profile": payload.model_dump()}


def load_entries(db, owner):
    return [json.loads(row[0]) for row in db.execute("SELECT data FROM training_entries WHERE athlete=? ORDER BY created DESC", (owner,)).fetchall()]


def owned_entry(db, owner, entry_id):
    row = db.execute("SELECT data FROM training_entries WHERE id=? AND athlete=?", (entry_id, owner)).fetchone()
    if not row:
        raise HTTPException(404, "Review not found.")
    return json.loads(row[0])


def write_entry(db, owner, entry):
    db.execute("UPDATE training_entries SET data=? WHERE id=? AND athlete=?", (json.dumps(entry), entry["id"], owner))


def tasks_for(payload):
    if payload.purpose != "self":
        return []
    report = payload.report
    if payload.kind == "footage":
        if report.get("visibility") == "unusable" or report.get("athlete_match") != "confirmed":
            return []
        blocks = report.get("practice", [])
    elif payload.kind == "corner":
        blocks = report.get("plan", {}).get("drills", [])
    else:
        blocks = []
    return [{"id": str(i), "name": p["name"], "instructions": p["instructions"],
             "minutes": p.get("minutes"), "duration": p.get("duration", ""),
             "success_check": p.get("success_check", "Agree a visible success check with your coach before practice."),
             "status": "planned", "outcome": "not_checked", "notes": "", "reassessment_entry": ""}
            for i, p in enumerate(blocks[:3])]


@router.post("/entries")
def save_entry(payload: EntryInput, request: Request):
    require_same_origin(request)
    if payload.kind == "note":
        if payload.report or payload.receipt:
            raise HTTPException(422, "Notes cannot include an AI report.")
    elif not get_settings().beta_access_code or not valid_receipt(payload.kind, payload.report, payload.receipt):
        raise HTTPException(422, "This report could not be verified. Generate a new review or save a written note.")
    with database.transaction() as db:
        athlete = account(request, db)
        db.lock_owner(athlete["id"])
        if db.execute("SELECT COUNT(*) FROM training_entries WHERE athlete=?", (athlete["id"],)).fetchone()[0] >= 1000:
            raise HTTPException(409, "Your journal has reached 1,000 entries. Export and remove older reviews first.")
        entries = load_entries(db, athlete["id"])
        if payload.kind != "note" and any(e.get("report_receipt") == payload.receipt for e in entries):
            raise HTTPException(409, "This review is already in your journal.")
        entry = payload.model_dump(mode="json", exclude={"receipt"})
        entry.update(id=secrets.token_hex(16), created=time.time(), report_receipt=payload.receipt,
                     feedback={"verdict": "unreviewed", "correction": ""}, tasks=tasks_for(payload))
        db.execute("INSERT INTO training_entries VALUES (?,?,?,?)", (entry["id"], athlete["id"], json.dumps(entry), entry["created"]))
    return {"entry": entry}


@router.get("/entries")
def entries(request: Request):
    with database.transaction() as db:
        athlete = account(request, db)
        result = load_entries(db, athlete["id"])
    return {"entries": result}


@router.post("/entries/{entry_id}/feedback")
def feedback(entry_id: str, payload: Feedback, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        entry = owned_entry(db, owner, entry_id)
        entry["feedback"] = payload.model_dump()
        write_entry(db, owner, entry)
        if payload.verdict != "confirmed":
            for previous in load_entries(db, owner):
                changed = False
                for task in previous["tasks"]:
                    if task["reassessment_entry"] == entry_id:
                        task.update(status="practiced", outcome="not_checked", reassessment_entry="")
                        changed = True
                if changed:
                    write_entry(db, owner, previous)
    return {"entry": entry}


@router.post("/entries/{entry_id}/tasks/{task_id}")
def update_task(entry_id: str, task_id: str, payload: TaskUpdate, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        entry = owned_entry(db, owner, entry_id)
        task = next((t for t in entry["tasks"] if t["id"] == task_id), None)
        if not task:
            raise HTTPException(404, "Practice task not found.")
        if entry["feedback"]["verdict"] != "confirmed":
            raise HTTPException(409, "Confirm the review before adding its drills to practice.")
        if payload.status == "reassessed":
            later = owned_entry(db, owner, payload.reassessment_entry)
            if (later["id"] == entry_id or later["performed_on"] < entry["performed_on"] or
                    later["created"] <= entry["created"] or later["purpose"] != "self" or later["discipline"] != entry["discipline"] or
                    later["training_type"] != entry["training_type"] or later["feedback"]["verdict"] != "confirmed" or payload.outcome == "not_checked"):
                raise HTTPException(422, "Choose a later confirmed review of yourself in the same discipline and training setting, and record an outcome.")
        elif payload.outcome != "not_checked" or payload.reassessment_entry:
            raise HTTPException(422, "Link a later review before recording improvement.")
        task.update(payload.model_dump(), updated=time.time())
        write_entry(db, owner, entry)
    return {"entry": entry}


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: str, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        owned_entry(db, owner, entry_id)
        db.execute("DELETE FROM training_entries WHERE id=? AND athlete=?", (entry_id, owner))
        for row in db.execute("SELECT data FROM research_reports WHERE athlete=?", (owner,)).fetchall():
            study = json.loads(row[0])
            if entry_id in study["sources"]:
                db.execute("DELETE FROM research_reports WHERE id=? AND athlete=?", (study["id"], owner))
        for entry in load_entries(db, owner):
            changed = False
            for task in entry["tasks"]:
                if task["reassessment_entry"] == entry_id:
                    task.update(status="practiced", outcome="not_checked", reassessment_entry="")
                    changed = True
            if changed:
                write_entry(db, owner, entry)
        for row in db.execute("SELECT data FROM tactical_systems WHERE athlete=?", (owner,)).fetchall():
            system = json.loads(row[0])
            if system["entry_id"] == entry_id:
                system["entry_id"] = ""
                db.execute("UPDATE tactical_systems SET data=? WHERE id=? AND athlete=?", (json.dumps(system), system["id"], owner))
        for row in db.execute("SELECT data FROM gym_plans WHERE recipient=?", (owner,)).fetchall():
            plan = json.loads(row[0])
            if plan.get("entry_id") == entry_id:
                plan["entry_id"] = ""
                db.execute("UPDATE gym_plans SET data=? WHERE id=?", (json.dumps(plan), plan["id"]))
    return {"deleted": True}


def development(profile, entries):
    from app.services.development import organize
    own = sorted([e for e in entries if e["purpose"] == "self" and e["discipline"] == profile["discipline"]],
                 key=lambda e: (e["performed_on"], e["created"]), reverse=True)
    confirmed = [e for e in own if e["feedback"]["verdict"] == "confirmed"]
    minutes = profile["practice_minutes"]
    all_tasks = [t for e in confirmed for t in e["tasks"]]
    return {"goal": profile["goal"], "discipline": profile["discipline"], **organize(profile, confirmed),
            "sessions_per_week": profile["sessions_per_week"], "practice_minutes": minutes,
            "reason": "The latest confirmed session for each drill governs the plan. Needs-work and unchanged reassessments come first, then practiced drills awaiting a check, then new practice. Improving drills leave the active plan. Within each group, newer sessions come first. Up to three full drills fit your time budget. This is a rules-based organizer of existing advice, not a new AI assessment or a severity ranking.",
            "metrics": {"saved_reviews": len(own), "confirmed_reviews": len(confirmed),
                        "practiced_tasks": sum(t["status"] != "planned" for t in all_tasks),
                        "reassessed_tasks": sum(t["status"] == "reassessed" for t in all_tasks),
                        "reported_improving": sum(t["status"] == "reassessed" and t["outcome"] == "improving" for t in all_tasks)},
            "coverage": [{"date": e["performed_on"], "title": e["title"], "kind": e["kind"], "setting": e["training_type"],
                          "minutes_logged": e["minutes"], "sampled_seconds": (e["report"].get("coverage", {}).get("end", 0)-e["report"].get("coverage", {}).get("start", 0)) if e["kind"] == "footage" else None,
                          "pillars_reviewed": (e["report"].get("assessment", e["report"])).get("reviewed_count") if e["kind"] in {"session", "corner"} else None} for e in own[:30]]}


@router.get("/development")
def plan(request: Request):
    from app.services.validation import archive, task_decision
    with database.transaction() as db:
        athlete = account(request, db)
        entries = load_entries(db, athlete["id"])
        human_reviews = archive(db,athlete['id'],entries)
        for entry in entries:
            reviews = human_reviews[entry['id']]
            for i, task in enumerate(entry['tasks']):
                task['coach_review'] = task_decision(reviews,i)
        return development(athlete["profile"], entries)


@router.get("/export")
def export(request: Request):
    from app.services.research import records as research_records
    from app.services.gyms import archive as gym_archive
    from app.services.validation import archive as human_archive
    with database.transaction() as db:
        athlete = account(request, db)
        comments = db.execute("SELECT c.entry,a.handle,c.body,c.created FROM coach_comments c JOIN training_entries e ON c.entry=e.id JOIN athletes a ON c.author=a.id WHERE e.athlete=?", (athlete["id"],)).fetchall()
        return {"format": "fightiq-training-v1", "exported": time.time(), "athlete": athlete,
                "entries": load_entries(db, athlete["id"]),
                "systems": [json.loads(r[0]) for r in db.execute("SELECT data FROM tactical_systems WHERE athlete=?", (athlete["id"],)).fetchall()],
                "temporary_round_reviews": [{k: v for k, v in json.loads(r[0]).items() if k != "lease"} for r in db.execute("SELECT data FROM round_jobs WHERE athlete=? AND created>?", (athlete["id"], time.time()-7*86400)).fetchall()],
                "research_studies": research_records(db, athlete["id"]),
                "gym_collaboration": gym_archive(db, athlete["id"]),
                "human_reviews": human_archive(db,athlete['id'],load_entries(db,athlete['id'])),
                "comments": [{"entry": c[0], "author": c[1], "body": c[2], "created": c[3]} for c in comments]}


@router.post("/delete-account")
def delete_account(payload: DeleteAccount, request: Request, response: Response):
    require_same_origin(request)
    with database.transaction() as db:
        athlete = account(request, db)
        auth_limit(request, athlete["handle"])
        encoded = db.execute("SELECT password FROM athletes WHERE id=?", (athlete["id"],)).fetchone()[0]
        if not password_matches(payload.password, encoded):
            raise HTTPException(401, "Password did not match.")
        # Remove owned gym trees before nulling this athlete in surviving audit
        # records/plans. Do not depend on mixed foreign-key trigger ordering.
        db.execute("DELETE FROM gyms WHERE owner=?", (athlete["id"],))
        db.execute("DELETE FROM athletes WHERE id=?", (athlete["id"],))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict", secure=get_settings().environment == "production")
    return {"deleted": True}


@router.get("/coaches")
def coaches(request: Request):
    with database.transaction() as db:
        owner = account(request, db)["id"]
        granted = db.execute("SELECT a.handle FROM coach_grants g JOIN athletes a ON g.coach=a.id WHERE g.owner=?", (owner,)).fetchall()
        athletes = db.execute("SELECT a.id,a.handle FROM coach_grants g JOIN athletes a ON g.owner=a.id WHERE g.coach=?", (owner,)).fetchall()
    return {"coaches": [c[0] for c in granted], "athletes": [{"id": a[0], "handle": a[1]} for a in athletes]}


@router.post("/coaches")
def grant(payload: CoachGrant, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        coach = db.execute("SELECT id FROM athletes WHERE handle=?", (payload.handle.lower(),)).fetchone()
        if not coach or coach[0] == owner:
            raise HTTPException(404, "Choose another existing athlete username.")
        if db.execute("SELECT COUNT(*) FROM coach_grants WHERE owner=?", (owner,)).fetchone()[0] >= 5:
            raise HTTPException(409, "Remove a coach before adding another (maximum five).")
        db.execute("INSERT INTO coach_grants VALUES (?,?) ON CONFLICT DO NOTHING", (owner, coach[0]))
    return {"granted": True}


@router.delete("/coaches/{handle}")
def revoke(handle: str, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        db.execute("DELETE FROM coach_grants WHERE owner=? AND coach IN (SELECT id FROM athletes WHERE handle=?)", (owner, handle.lower()))
    return {"revoked": True}


@router.get("/athletes/{owner}/entries")
def shared_entries(owner: str, request: Request):
    with database.transaction() as db:
        coach = account(request, db)["id"]
        if not db.execute("SELECT owner FROM coach_grants WHERE owner=? AND coach=?", (owner, coach)).fetchone():
            raise HTTPException(404, "Shared athlete not found.")
        # Scouting/style research and the private profile are not shared.
        return {"entries": [e for e in load_entries(db, owner) if e["purpose"] == "self"]}


def comment_access(request, db, entry_id):
    from app.services.gyms import gym_access, access_audit
    author = account(request, db)
    row = db.execute("SELECT athlete,data FROM training_entries WHERE id=?", (entry_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Review not found.")
    db.lock_owner(row[0])
    if row[0] != author["id"]:
        if json.loads(row[1])["purpose"] != "self":
            raise HTTPException(404, "Review not found.")
        direct = db.execute("SELECT owner FROM coach_grants WHERE owner=? AND coach=?", (row[0], author["id"])).fetchone()
        if not direct:
            if not gym_access(db, author["id"], row[0]):
                raise HTTPException(404, "Review not found.")
            access_audit(db, author["id"], row[0])
    return author


@router.get("/entries/{entry_id}/comments")
def comments(entry_id: str, request: Request):
    with database.transaction() as db:
        comment_access(request, db, entry_id)
        rows = db.execute("SELECT a.handle,c.body,c.created FROM coach_comments c JOIN athletes a ON c.author=a.id WHERE c.entry=? ORDER BY c.created", (entry_id,)).fetchall()
    return {"comments": [{"author": c[0], "body": c[1], "created": c[2]} for c in rows]}


@router.post("/entries/{entry_id}/comments")
def add_comment(entry_id: str, payload: Comment, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        author = comment_access(request, db, entry_id)
        if db.execute("SELECT COUNT(*) FROM coach_comments WHERE entry=?", (entry_id,)).fetchone()[0] >= 100:
            raise HTTPException(409, "This review has reached 100 comments.")
        db.execute("INSERT INTO coach_comments VALUES (?,?,?,?,?)", (secrets.token_hex(16), entry_id, author["id"], payload.body, time.time()))
    return {"saved": True}
