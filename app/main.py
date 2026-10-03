from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.ai_coach import generate_corner_advice
from app.services.scoring_engine import MISTAKES, analyze_mistakes

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MistakeInput(BaseModel):
    mistake_id: str
    severity: Literal["minor", "risky", "critical"] = "risky"
    round: int = Field(default=1, ge=1, le=12)


class AnalysisRequest(BaseModel):
    mistakes: list[MistakeInput] = Field(default_factory=list)


class CoachRequest(BaseModel):
    analysis: dict
    context: str = Field(default="", max_length=4000)


@app.get("/api/v1/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "openai_configured": bool(settings.openai_api_key),
    }


@app.get("/api/v1/mistakes")
async def mistakes() -> dict:
    return {"mistakes": list(MISTAKES.values())}


@app.post("/api/v1/analysis")
async def analysis(payload: AnalysisRequest) -> dict:
    return analyze_mistakes([item.model_dump() for item in payload.mistakes])


@app.get("/api/v1/analysis/demo")
async def demo_analysis() -> dict:
    return analyze_mistakes(
        [
            {"mistake_id": "DIST_002", "severity": "risky", "round": 1},
            {"mistake_id": "RISK_001", "severity": "critical", "round": 2},
            {"mistake_id": "COMP_001", "severity": "risky", "round": 2},
        ]
    )


@app.post("/api/v1/ai/coach")
async def ai_coach(payload: CoachRequest) -> dict:
    try:
        advice = await generate_corner_advice(payload.analysis, payload.context)
        return {"advice": advice, "model": settings.openai_model}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI coaching request failed") from exc


@app.websocket("/ws/live/{session_id}")
async def live_session(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    logged: list[dict] = []
    await websocket.send_json({"type": "connected", "session_id": session_id})
    try:
        while True:
            event = await websocket.receive_json()
            if event.get("type") == "mistake":
                logged.append(
                    {
                        "mistake_id": event.get("mistake_id"),
                        "severity": event.get("severity", "risky"),
                        "round": event.get("round", 1),
                    }
                )
                await websocket.send_json(
                    {"type": "analysis", "data": analyze_mistakes(logged)}
                )
            elif event.get("type") == "reset":
                logged.clear()
                await websocket.send_json({"type": "analysis", "data": analyze_mistakes([])})
            else:
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        return


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def home():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"name": settings.app_name, "docs": "/docs"}
