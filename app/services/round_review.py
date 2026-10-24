"""Resumable round reviews. Only text results persist; frames exist during one request.

The browser supplies one bounded section at a time. Work runs after acknowledgement,
with an expiring database lease. Interrupted work never retries a provider call itself.
"""
import asyncio
import json
import math
import secrets
import time
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import Field, model_validator

from app.core import database
from app.core.config import get_settings
from app.core.security import consume_allowance, require_same_origin, require_session
from app.services.training import Strict, account, receipt
from app.services.video_coach import DISCIPLINES, VideoRequest, generate_footage_review, validate_images

router = APIRouter(prefix="/api/v1/rounds")
RETENTION = 7 * 86400


def purge_expired():
    if database.available():
        with database.transaction() as db:
            db.execute("DELETE FROM round_jobs WHERE created<?", (time.time()-RETENTION,))


async def cleanup_loop():
    while True:
        try:
            await asyncio.to_thread(purge_expired)
        except HTTPException:
            # A temporarily unavailable database is retried at the next maintenance pass.
            pass
        await asyncio.sleep(3600)


class RoundInput(Strict):
    discipline: DISCIPLINES
    experience: Literal["Beginner", "Intermediate", "Advanced"]
    athlete: str = Field(min_length=3, max_length=200)
    goal: str = Field(default="", max_length=600)
    source_name: str = Field(min_length=1, max_length=160)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    start: float = Field(ge=0, le=14399)
    end: float = Field(gt=0, le=14400)
    consent: Literal[True]

    @model_validator(mode="after")
    def duration(self):
        if not 1 <= self.end - self.start <= 300:
            raise ValueError("Select one second to five minutes")
        return self


class SectionInput(VideoRequest):
    retry: bool = False


def windows(start, end):
    count = math.ceil((end-start)/10)
    # Equal sections avoid an unsupported sub-second final section.
    points = [round(start+(end-start)*i/count, 3) for i in range(count+1)]
    return [{"start": points[i], "end": points[i+1]} for i in range(count)]


def write(db, job):
    job["updated"] = time.time()
    db.execute("UPDATE round_jobs SET data=?,updated=?,status=? WHERE id=?", (json.dumps(job), job["updated"], job["status"], job["id"]))


def owned(db, owner, job_id):
    row = db.execute("SELECT data FROM round_jobs WHERE id=? AND athlete=?", (job_id, owner)).fetchone()
    if not row:
        raise HTTPException(404, "Round review not found.")
    job = json.loads(row[0])
    if time.time()-job["created"] > RETENTION:
        db.execute("DELETE FROM round_jobs WHERE id=?", (job_id,))
        raise HTTPException(410, "This temporary review expired. Saved journal entries are unchanged.")
    if job["status"] == "running" and time.time()-job["updated"] > 100:
        job.update(status="interrupted", error="Processing was interrupted. Review the allowance before explicitly retrying this section.")
        write(db, job)
    return job


def public(job):
    return {**{k: v for k, v in job.items() if k != "lease"}, "completed_sections": len(job["sections"])}


def clean_text(value, length=400):
    return str(value)[:length]


def summary(job):
    """A bounded evidence index, not a second model's invented whole-round judgment."""
    usable = [r for r in job["sections"] if r["visibility"] != "unusable" and r["athlete_match"] == "confirmed"]
    moments = []
    for index, report in enumerate(job["sections"]):
        if report not in usable:
            continue
        for moment in report["moments"]:
            copy = {k: clean_text(v) if isinstance(v, str) else v for k, v in moment.items()}
            copy["section_number"] = index+1
            moments.append(copy)
    first = usable[0] if usable else None
    start, end = job["context"]["start"], job["context"]["end"]
    return {
        "visibility": "limited" if usable else "unusable",
        "athlete_match": "confirmed" if usable else "uncertain",
        "summary": f"{len(usable)} of {len(job['sections'])} sections supported an athlete review. This index collects section findings; inspect each section before drawing whole-round conclusions.",
        "limitations": ["Still frames sampled at 5 fps can miss fast actions; this is not every source frame.",
                        "The index includes up to 8 cited moments and practice suggestions from the first usable section. Read all section reports for complete coverage.",
                        "No cross-section identity tracking or overall fighting ability score is inferred."],
        "moments": sorted(moments, key=lambda m: m["timestamp"])[:8],
        "priority": clean_text(first["priority"]) if first else "Use clearer footage and a specific athlete description.",
        "additions": [{k: clean_text(v, 250) for k, v in a.items()} for a in first["additions"][:3]] if first else [],
        "practice": [{k: clean_text(v, 350) if isinstance(v, str) else v for k, v in p.items()} for p in first["practice"][:3]] if first else [],
        "next_session_check": clean_text(first["next_session_check"]) if first else "Keep the selected athlete visible.",
        "coverage": {"start": start, "end": end, "frames": sum(r["coverage"]["frames"] for r in job["sections"]), "sample_fps": 5,
                     "sections": len(job["sections"]), "usable_sections": len(usable)},
    }


@router.post("")
def create(payload: RoundInput, request: Request):
    require_same_origin(request)
    require_session(request)
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        db.execute("DELETE FROM round_jobs WHERE created<?", (time.time()-RETENTION,))
        if db.execute("SELECT COUNT(*) FROM round_jobs WHERE athlete=?", (owner,)).fetchone()[0] >= 20:
            raise HTTPException(409, "Remove an old temporary review before starting another (maximum 20).")
        if db.execute("SELECT id FROM round_jobs WHERE athlete=? AND status IN ('ready','running','failed','interrupted')", (owner,)).fetchone():
            raise HTTPException(409, "Finish or cancel your existing round review first.")
        now = time.time()
        job = {"id": secrets.token_hex(16), "created": now, "updated": now, "status": "ready",
               "context": payload.model_dump(exclude={"consent"}), "windows": windows(payload.start, payload.end),
               "sections": [], "attempts": 0, "error": "", "lease": "", "expires": now+RETENTION}
        db.execute("INSERT INTO round_jobs VALUES (?,?,?,?,?,?)", (job["id"], owner, json.dumps(job), now, now, job["status"]))
    return public(job)


@router.get("")
def listing(request: Request):
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        db.execute("DELETE FROM round_jobs WHERE athlete=? AND created<?", (owner, time.time()-RETENTION))
        rows = db.execute("SELECT id FROM round_jobs WHERE athlete=? ORDER BY created DESC", (owner,)).fetchall()
        return {"jobs": [{k: v for k, v in public(owned(db, owner, row[0])).items() if k not in {"sections", "report", "receipt"}} for row in rows]}


@router.get("/{job_id}")
def get(job_id: str, request: Request):
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        return public(owned(db, owner, job_id))


@router.post("/{job_id}/cancel")
def cancel(job_id: str, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        job = owned(db, owner, job_id)
        if job["status"] != "complete":
            job.update(status="cancelled", error="Cancelled. A provider call already started may still consume an allowance.")
            write(db, job)
        return public(job)


@router.delete("/{job_id}")
def delete(job_id: str, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        owner = account(request, db)["id"]
        db.lock_owner(owner)
        db.execute("DELETE FROM round_jobs WHERE id=? AND athlete=?", (job_id, owner))
    return {"deleted": True}


async def process(job_id, owner, lease, payload):
    result, error = None, ""
    try:
        result = await asyncio.wait_for(generate_footage_review(payload), timeout=85)
    except asyncio.CancelledError:
        # A process shutdown leaves a lease that becomes interrupted, never retried.
        raise
    except Exception:
        error = "This section could not be reviewed. Completed sections are preserved. Retry explicitly when ready; another provider request may be charged."
    finally:
        # Release image strings promptly; never serialize them into a job.
        payload.frames.clear()
    with database.transaction() as db:
        if not db.lock_owner(owner):
            return
        row = db.execute("SELECT data FROM round_jobs WHERE id=? AND athlete=?", (job_id, owner)).fetchone()
        if not row:
            return
        job = json.loads(row[0])
        if job["status"] != "running" or job["lease"] != lease:
            return
        if error:
            job.update(status="failed", error=error)
        else:
            job["sections"].append(result)
            job.update(status="ready", error="")
            if len(job["sections"]) == len(job["windows"]):
                job["status"] = "complete"
                job["report"] = summary(job)
                job["receipt"] = receipt("footage", job["report"])
        write(db, job)


@router.post("/{job_id}/sections/{index}", status_code=202)
async def submit(job_id: str, index: int, payload: SectionInput, request: Request, background: BackgroundTasks):
    require_same_origin(request)
    require_session(request)
    if not get_settings().openai_api_key:
        raise HTTPException(503, "Footage review is temporarily unavailable.")
    try:
        await asyncio.to_thread(validate_images, payload)
    except ValueError:
        raise HTTPException(422, "A sampled frame could not be decoded.") from None
    # Never nest an allowance transaction inside a training transaction (SQLite lock).
    # First check ownership; quota is reserved before the atomic claim below.
    with database.transaction() as db:
        owner = account(request, db)["id"]
        job = owned(db, owner, job_id)
        validate_submission(job, index, payload)
    consume_allowance("round", owner)
    with database.transaction() as db:
        if db.postgres:
            db.execute("SELECT pg_advisory_xact_lock(481094)")
        db.lock_owner(owner)
        job = owned(db, owner, job_id)
        validate_submission(job, index, payload)
        if db.execute("SELECT id FROM round_jobs WHERE status='running' AND updated>?", (time.time()-100,)).fetchone():
            raise HTTPException(429, "Another round section is processing. Wait, then continue.", headers={"Retry-After": "30"})
        job.update(status="running", error="", attempts=job["attempts"]+1, lease=secrets.token_hex(16))
        write(db, job)
    data = payload.model_dump(exclude={"retry"})
    background.add_task(process, job_id, owner, job["lease"], VideoRequest.model_validate(data))
    return public(job)


def validate_submission(job, index, payload):
    if job["status"] not in {"ready", "failed", "interrupted"} or index != len(job["sections"]):
        raise HTTPException(409, "This section is already processing, completed or cancelled. Refresh the round review.")
    if job["attempts"] >= len(job["windows"])+3:
        raise HTTPException(429, "This round has used its section and retry budget. Completed results remain available.")
    if job["status"] in {"failed", "interrupted"} and not payload.retry:
        raise HTTPException(409, "An explicit retry is required after a failed or interrupted section.")
    window = job["windows"][index]
    if any(getattr(payload, k) != v for k, v in window.items()):
        raise HTTPException(422, "The submitted section does not match this round.")
    if any(getattr(payload, k) != job["context"][k] for k in ("discipline", "experience", "athlete", "goal")):
        raise HTTPException(422, "The athlete and coaching context must stay consistent within a round review.")
