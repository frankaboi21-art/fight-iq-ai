"""Local-only browser fixture. Run explicitly; never used by production startup.

python -m uvicorn tests.preview_app:app --host 127.0.0.1 --port 8007
Uses disposable local records and deterministic synthetic responses, no provider calls.
"""
import os
from pathlib import Path

fixture_dir = Path(__file__).resolve().parents[1] / ".data" / "browser-preview"
fixture_dir.mkdir(parents=True, exist_ok=True)
os.environ.update(
    ENVIRONMENT="development", DATABASE_URL="", OPENAI_API_KEY="synthetic-preview-only",
    BETA_ACCESS_CODE="synthetic-browser-test-code", PUBLIC_ORIGIN="http://127.0.0.1:8007",
    RENDER_EXTERNAL_URL="", TRAINING_DB_PATH=str(fixture_dir / "training.db"),
    USAGE_DB_PATH=str(fixture_dir / "usage.db"),
)

import app.main as main
from app.services.video_coach import FootageReview, attach_evidence


async def synthetic_review(payload):
    return attach_evidence(FootageReview(
        visibility="unusable", athlete_match="uncertain",
        summary="Synthetic browser test: this pattern contains no martial artist.",
        limitations=["Fixture response for interface testing; no AI provider was called."],
        moments=[], priority="Use permissioned training footage.", additions=[], practice=[],
        next_session_check="Keep the athlete visible.",
    ), payload)


async def synthetic_corner(analysis, context):
    return {
        "observations": ["Synthetic interface fixture based on the submitted observation log."],
        "priority": {"title": "Preview practice priority", "explanation": "This is a deterministic test result.", "action": "Review with a coach."},
        "tactics": ["Observe the starting position.", "Practice slowly.", "Review the outcome."],
        "drills": [{"name": "Preview rehearsal", "duration": "5 minutes", "instructions": "Synthetic drill for testing the saved practice flow."},
                   {"name": "Preview reset", "duration": "3 minutes", "instructions": "Synthetic second drill."}],
        "cue": "Synthetic preview, not coaching advice.",
    }


main.generate_footage_review = synthetic_review
main.generate_corner_advice = synthetic_corner
from app.services import round_review
round_review.generate_footage_review = synthetic_review
from app.services import research


async def synthetic_study(payload, sources):
    finding = research.Finding(title="Synthetic evidence link", observation="Test-only observation from the selected fixture.",
        interpretation="This checks citation rendering, not fighting technique.", uncertainty="No real athlete was analyzed.",
        training_option="No real coaching recommendation.", prerequisite="Qualified review is required for real advice.",
        success_check="The citation opens the selected saved review.",
        citations=[research.Citation(entry_id=sources[0]["entry_id"], moment_index=0)])
    return research.ResearchReport(summary="Synthetic research preview; no provider was called.", findings=[finding],
        limitations=["Interface fixture only; not an evaluated scouting report."], next_evidence="Use permissioned footage with qualified coach review.")


research.generate = synthetic_study
app = main.app
