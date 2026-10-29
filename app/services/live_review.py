"""Bounded near-live sampled windows, with no image/result persistence."""
import asyncio
import json
import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, model_validator

from app.core import database
from app.core.config import get_settings
from app.core.security import consume_allowance, require_same_origin, require_session
from app.services.training import Strict, account, receipt
from app.services.video_coach import DISCIPLINES, VideoRequest, VideoFrame, generate_footage_review, validate_images
from typing import Literal

router = APIRouter(prefix="/api/v1/live")
slots = asyncio.Semaphore(1)


class LiveStart(Strict):
    discipline: DISCIPLINES
    experience: Literal["Beginner", "Intermediate", "Advanced"]
    athlete: str = Field(min_length=3, max_length=200)
    goal: str = Field(default="", max_length=600)
    consent: Literal[True]


class LiveWindow(VideoRequest):
    frames: list[VideoFrame] = Field(min_length=10, max_length=25)

    @model_validator(mode="after")
    def valid_sequence(self):
        if not 2 <= self.end-self.start <= 5.5 or self.end > 181:
            raise ValueError("Live windows must span two to five seconds within a three-minute session")
        times = [frame.timestamp for frame in self.frames]
        if abs(times[0]-self.start) > .05 or not 0 <= self.end-times[-1] <= .6:
            raise ValueError("Live coverage must match actual frame timestamps")
        if any(not .1 <= b-a <= .6 for a,b in zip(times,times[1:])):
            raise ValueError("Live sampling was interrupted; capture a fresh window")
        return self


def session(db, actor, session_id):
    row = db.execute("SELECT data,created,active,busy_until,calls,lease FROM live_sessions WHERE id=? AND athlete=?", (session_id,actor)).fetchone()
    if not row:
        raise HTTPException(404,"Live session not found.")
    return row


@router.post("/start")
def start(payload: LiveStart, request: Request):
    require_same_origin(request);require_session(request)
    with database.transaction() as db:
        actor=account(request,db)["id"];db.lock_owner(actor)
        now=time.time()
        db.execute("DELETE FROM live_sessions WHERE created<?",(now-600,))
        if db.execute("SELECT id FROM live_sessions WHERE athlete=? AND created>? AND active=1",(actor,now-180)).fetchone():
            raise HTTPException(409,"Stop the existing live session first, or wait for its three-minute limit.")
        if db.execute("SELECT COUNT(*) FROM live_sessions WHERE athlete=?",(actor,)).fetchone()[0]>=20:
            raise HTTPException(429,"Too many live session starts. Wait ten minutes before trying again.")
        sid=secrets.token_hex(16)
        db.execute("INSERT INTO live_sessions VALUES (?,?,?,?,?,?,?,?)",(sid,actor,json.dumps({'context':payload.model_dump(),'last_end':-1}),now,1,0,0,""))
    return {"id":sid,"max_windows":6,"session_seconds":180,"window_seconds":4}


@router.post("/{session_id}/stop")
def stop(session_id: str, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db)["id"];db.lock_owner(actor);session(db,actor,session_id)
        # Retain the lease until in-flight work settles, but clear submitted context.
        db.execute("UPDATE live_sessions SET active=0,data='{}' WHERE id=?",(session_id,))
    return {"stopped":True}


@router.post("/{session_id}/window")
async def window(session_id: str,payload: LiveWindow,request: Request):
    require_same_origin(request);identity=require_session(request)
    if not get_settings().openai_api_key:
        raise HTTPException(503,"Live review is temporarily unavailable.")
    with database.transaction() as db:
        actor=account(request,db)["id"]
        row=session(db,actor,session_id)
    if not row[2] or time.time()-row[1]>180:
        raise HTTPException(409,"This live session has stopped or expired. Start a new session explicitly.")
    context=payload.model_dump(exclude={"frames","start","end"})
    if json.loads(row[0])['context'] != context:
        raise HTTPException(422,"Live context changed. Stop and start again with the new details.")
    if payload.end > time.time()-row[1]+2:
        raise HTTPException(422,"Frame times are ahead of the live session clock.")
    if time.time()-row[1]-payload.end>15:
        raise HTTPException(422,"This live window is stale. Capture a fresh window.")
    if slots.locked():
        raise HTTPException(429,"A live review is already processing. No window was queued.")
    async with slots:
        try:
            await asyncio.to_thread(validate_images,payload)
        except ValueError:
            raise HTTPException(422,"A live frame could not be read. Start a fresh capture.") from None
        consume_allowance("live",identity)
        lease=secrets.token_hex(16)
        with database.transaction() as db:
            if account(request,db)["id"]!=actor:
                raise HTTPException(401,"Sign in again.")
            db.lock_owner(actor)
            if db.postgres: db.execute("SELECT pg_advisory_xact_lock(481095)")
            row=session(db,actor,session_id)
            if not row[2] or time.time()-row[1]>180 or row[4]>=6:
                raise HTTPException(409,"Live session stopped, expired or reached six windows.")
            if time.time()-row[1]-payload.end>15:
                raise HTTPException(422,"This live window is stale. Capture a fresh window.")
            stored=json.loads(row[0])
            if payload.start<stored['last_end']:
                raise HTTPException(409,"This window overlaps a submitted window. Capture fresh frames; no replay is allowed.")
            if db.execute("SELECT id FROM live_sessions WHERE busy_until>?",(time.time(),)).fetchone():
                raise HTTPException(429,"A live window is processing. No window was queued.")
            stored['last_end']=payload.end
            db.execute("UPDATE live_sessions SET busy_until=?,calls=calls+1,lease=?,data=? WHERE id=?",(time.time()+100,lease,json.dumps(stored),session_id))
        began=time.monotonic()
        try:
            review=await asyncio.wait_for(generate_footage_review(payload),timeout=85)
            elapsed=round(time.monotonic()-began,2)
            with database.transaction() as db:
                if account(request,db)["id"]!=actor: raise HTTPException(401,"Sign in again.")
                current=session(db,actor,session_id)
                if not current[2] or current[5]!=lease or time.time()-current[1]>180:
                    raise HTTPException(409,"The session ended. Late feedback was discarded.")
            return {"review":review,"receipt":receipt("footage",review),"processing_seconds":elapsed,
                    "captured_end":payload.end,"windows_used":row[4]+1,"model":get_settings().openai_model}
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502,"Live review could not finish. Capture has stopped; no automatic retry was made.") from None
        finally:
            payload.frames.clear()
            with database.transaction() as db:
                db.execute("UPDATE live_sessions SET busy_until=0,lease='' WHERE id=? AND lease=?",(session_id,lease))


def cleanup(db):
    db.execute("DELETE FROM live_sessions WHERE created<?",(time.time()-600,))


async def cleanup_loop():
    while True:
        try:
            if database.available():
                with database.transaction() as db: cleanup(db)
        except HTTPException:
            pass
        await asyncio.sleep(60)
