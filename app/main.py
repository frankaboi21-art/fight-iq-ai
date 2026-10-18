from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import get_settings
from app.core.security import (COOKIE_NAME, access_ready, consume_allowance, make_session,
                               require_same_origin, require_session, session_id)
from app.services.ai_coach import generate_corner_advice
from app.services.video_coach import VideoRequest, generate_footage_review, validate_images
from app.services.scoring_engine import MISTAKES, PILLAR_WEIGHTS, analyze_mistakes

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.3.0", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                   allow_credentials=True, allow_methods=["GET", "POST", "DELETE"],
                   allow_headers=["Content-Type", "X-FightIQ-Client"])


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        video_request = scope["path"] == "/api/v1/video/review"
        if video_request:
            # Reject anonymous image uploads before buffering or decoding them.
            try:
                request = Request(scope)
                require_same_origin(request)
                require_session(request)
            except HTTPException as error:
                return await JSONResponse({"detail": error.detail}, error.status_code)(scope, receive, send)
        limit = 6100000 if video_request else 32768
        messages, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > limit:
                return await JSONResponse({"detail": "Please shorten this request."}, 413)(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break
        async def replay():
            return messages.pop(0) if messages else await receive()
        await self.app(scope, replay, send)


app.add_middleware(BodyLimitMiddleware)


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Never echo submitted access codes or context in validation responses.
    return JSONResponse({"detail": "Check the session fields and try again."}, status_code=422)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MistakeInput(StrictModel):
    mistake_id: str = Field(max_length=24)
    severity: Literal["minor", "risky", "critical"] = "risky"
    round: int = Field(default=1, ge=1, le=12)
    count: int = Field(default=1, ge=1, le=20)

    @field_validator("mistake_id")
    @classmethod
    def known_mistake(cls, value):
        if value not in MISTAKES:
            raise ValueError("Unknown mistake")
        return value


class AnalysisRequest(StrictModel):
    mistakes: list[MistakeInput] = Field(default_factory=list, max_length=100)
    reviewed_pillars: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("reviewed_pillars")
    @classmethod
    def known_pillars(cls, values):
        if any(value not in PILLAR_WEIGHTS for value in values):
            raise ValueError("Unknown pillar")
        return list(dict.fromkeys(values))


class CoachRequest(AnalysisRequest):
    context: str = Field(default="", max_length=2000)


class LoginRequest(StrictModel):
    code: str = Field(min_length=1, max_length=256)


def calculate(payload: AnalysisRequest):
    return analyze_mistakes([item.model_dump() for item in payload.mistakes], payload.reviewed_pillars)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "version": app.version,
            "environment": settings.environment,
            "openai_configured": bool(settings.openai_api_key),
            "coach_available": access_ready() and bool(settings.openai_api_key)}


@app.get("/api/v1/session")
async def session(request: Request):
    return {"authenticated": bool(session_id(request)), "access_available": access_ready(),
            "session_limit": 3, "window_minutes": 15}


@app.post("/api/v1/session")
async def unlock(payload: LoginRequest, request: Request, response: Response):
    require_same_origin(request)
    if not access_ready():
        raise HTTPException(503, "Beta access is being set up. Scoring is available now.")
    address = request.client.host if request.client else "unknown"
    consume_allowance("login", hashlib.sha256(address.encode()).hexdigest())
    actual = hashlib.sha256(payload.code.encode()).digest()
    expected = hashlib.sha256(settings.beta_access_code.encode()).digest()
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(401, "That access code didn't match. Please try again.")
    response.set_cookie(COOKIE_NAME, make_session(), max_age=settings.session_hours * 3600,
                        httponly=True, secure=settings.environment == "production", samesite="strict", path="/")
    return {"authenticated": True, "session_limit": 3, "window_minutes": 15}


@app.delete("/api/v1/session")
async def lock(request: Request, response: Response):
    require_same_origin(request)
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.environment == "production",
                           httponly=True, samesite="strict")
    return {"authenticated": False}


@app.get("/api/v1/mistakes")
async def mistakes():
    return {"mistakes": list(MISTAKES.values()), "pillars": list(PILLAR_WEIGHTS)}


@app.post("/api/v1/analysis")
async def analysis(payload: AnalysisRequest):
    return calculate(payload)


DEMO_MISTAKES = [
    {"mistake_id": "DIST_002", "severity": "risky", "round": 1, "count": 2},
    {"mistake_id": "RISK_001", "severity": "critical", "round": 2, "count": 1},
    {"mistake_id": "COMP_001", "severity": "risky", "round": 2, "count": 1},
]


@app.get("/api/v1/analysis/demo")
async def demo_analysis():
    return {**analyze_mistakes(DEMO_MISTAKES, list(PILLAR_WEIGHTS)), "is_demo": True}


coach_slots = asyncio.Semaphore(2)
video_slots = asyncio.Semaphore(1)


@app.post("/api/v1/video/review")
async def video_review(payload: VideoRequest, request: Request):
    require_same_origin(request)
    identity = require_session(request)
    if not settings.openai_api_key:
        raise HTTPException(503, "Footage review is temporarily unavailable.")
    if video_slots.locked():
        raise HTTPException(429, "Another footage review is in progress. Please try shortly.",
                            headers={"Retry-After": "30"})
    async with video_slots:
        try:
            await asyncio.to_thread(validate_images, payload)
        except ValueError:
            raise HTTPException(422, "A video frame could not be read. Please select the section again.") from None
        consume_allowance("video", identity)
        try:
            review = await asyncio.wait_for(generate_footage_review(payload), timeout=85)
            return {"review": review, "model": settings.openai_model}
        except (APITimeoutError, asyncio.TimeoutError):
            raise HTTPException(504, "The footage review took too long. Try a shorter section.") from None
        except APIConnectionError:
            raise HTTPException(503, "The video coach couldn't connect. Please try again later.") from None
        except APIStatusError as error:
            if error.status_code == 429:
                raise HTTPException(503, "The AI provider allowance is unavailable. Please try later.") from None
            raise HTTPException(502, "The video coach is temporarily unavailable.") from None
        except Exception:
            raise HTTPException(502, "A grounded review couldn't be completed. Try a clearer section.") from None


@app.post("/api/v1/ai/coach")
async def ai_coach(payload: CoachRequest, request: Request):
    require_same_origin(request)
    identity = require_session(request)
    report = calculate(payload)  # Never accept client-supplied scores or coaching instructions.
    if not report["reviewed_count"]:
        raise HTTPException(422, "Log an observation or review a pillar before asking your corner.")
    if not settings.openai_api_key:
        raise HTTPException(503, "AI Corner is temporarily unavailable. Your assessment is still available.")
    if coach_slots.locked():
        raise HTTPException(429, "Your corner is busy. Please try again in a moment.", headers={"Retry-After": "15"})
    async with coach_slots:
        consume_allowance("coach", identity)
        try:
            plan = await asyncio.wait_for(generate_corner_advice(report, payload.context), timeout=55)
            return {"plan": plan, "model": settings.openai_model}
        except (APITimeoutError, asyncio.TimeoutError):
            raise HTTPException(504, "Your coaching request took too long. You can try again.") from None
        except APIConnectionError:
            raise HTTPException(503, "Your corner couldn't connect. Please try again shortly.") from None
        except APIStatusError as exc:
            if exc.status_code == 429:
                raise HTTPException(503, "AI Corner has reached its provider allowance. Please try again later.") from None
            raise HTTPException(502, "Your corner is temporarily unavailable. Please try again later.") from None
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from None
        except Exception:
            raise HTTPException(502, "A complete plan couldn't be generated. Please try again.") from None


@app.websocket("/ws/live/{session_id}")
async def live_session(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logged: list[dict] = []
    await websocket.send_json({"type": "connected", "session_id": session_id[:100]})
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw) > 32768:
                await websocket.close(code=1009)
                return
            try:
                event = json.loads(raw)
                if not isinstance(event, dict):
                    raise ValueError("Invalid event")
                if event.get("type") == "mistake":
                    if len(logged) >= 100:
                        await websocket.send_json({"type": "error", "message": "Session limit reached. Reset to start again."})
                        continue
                    item = MistakeInput.model_validate({key: value for key, value in event.items() if key != "type"})
                    logged.append(item.model_dump())
                    await websocket.send_json({"type": "analysis", "data": analyze_mistakes(logged)})
                elif event.get("type") == "reset":
                    logged.clear()
                    await websocket.send_json({"type": "analysis", "data": analyze_mistakes([])})
                else:
                    await websocket.send_json({"type": "pong"})
            except (ValueError, ValidationError):
                await websocket.send_json({"type": "error", "message": "Check the observation and try again."})
    except WebSocketDisconnect:
        return


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})
