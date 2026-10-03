from __future__ import annotations

import json
from openai import AsyncOpenAI

from app.core.config import get_settings


SYSTEM_INSTRUCTIONS = """You are Fight IQ AI, a technical martial-arts analysis assistant.
Give concise, specific coaching that improves decision-making, positioning, defense,
tactical adaptation, energy management, and composure. Do not pretend to have seen
video that was not provided. Separate observations from recommendations. Favor safe,
supervised drills and avoid encouraging reckless training."""


async def generate_corner_advice(analysis: dict, context: str = "") -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    payload = {
        "analysis": analysis,
        "fighter_context": context[:4000],
    }
    response = await client.responses.create(
        model=settings.openai_model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=(
            "Turn this Fight IQ analysis into a practical corner-coaching response. "
            "Give: 1) the single highest priority correction, 2) a 3-step tactical adjustment, "
            "3) two drills, and 4) one short cue the fighter can remember under pressure.\n\n"
            + json.dumps(payload)
        ),
    )
    return response.output_text.strip()
