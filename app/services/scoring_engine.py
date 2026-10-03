from __future__ import annotations

from typing import Any

PILLAR_WEIGHTS = {
    "distance_intelligence": 0.20,
    "threat_recognition": 0.20,
    "risk_management": 0.20,
    "tactical_adaptation": 0.15,
    "efficiency": 0.15,
    "composure": 0.10,
}

SEVERITY_PENALTY = {
    "minor": 4.0,
    "risky": 8.0,
    "critical": 14.0,
}

MISTAKES: dict[str, dict[str, Any]] = {
    "DIST_001": {
        "id": "DIST_001",
        "name": "Entering Without Setup",
        "pillar": "distance_intelligence",
        "danger_rating": 3,
        "coaching_cue": "Win the entry with a feint, jab, or angle before committing.",
        "drills": ["Feint-to-entry shadowboxing", "Jab-to-angle rounds"],
    },
    "DIST_002": {
        "id": "DIST_002",
        "name": "Backing Straight Up",
        "pillar": "distance_intelligence",
        "danger_rating": 4,
        "coaching_cue": "Exit on an angle instead of conceding the center in a straight line.",
        "drills": ["L-step exits", "Fence/cage angle escape drill"],
    },
    "THRT_001": {
        "id": "THRT_001",
        "name": "Hands Drop After Combination",
        "pillar": "threat_recognition",
        "danger_rating": 4,
        "coaching_cue": "Finish every combination in a defensible position.",
        "drills": ["Combo-cover-reset", "Partner return-fire drill"],
    },
    "RISK_001": {
        "id": "RISK_001",
        "name": "Chin Exposed During Exchange",
        "pillar": "risk_management",
        "danger_rating": 5,
        "coaching_cue": "Keep the chin hidden and shoulders active while exchanging.",
        "drills": ["Tennis-ball chin drill", "Mirror defense rounds"],
    },
    "ADAPT_001": {
        "id": "ADAPT_001",
        "name": "Repeating a Read Opponent Has Solved",
        "pillar": "tactical_adaptation",
        "danger_rating": 4,
        "coaching_cue": "Change the ending after the opponent gives the same defensive read twice.",
        "drills": ["Three-ending combination tree", "Read-and-branch sparring"],
    },
    "EFF_001": {
        "id": "EFF_001",
        "name": "Overcommitting Power",
        "pillar": "efficiency",
        "danger_rating": 3,
        "coaching_cue": "Use only the force needed to create the next opening.",
        "drills": ["50/70/90 percent power rounds", "Relaxed speed bag or shadowboxing"],
    },
    "COMP_001": {
        "id": "COMP_001",
        "name": "Rushing After Getting Hit",
        "pillar": "composure",
        "danger_rating": 5,
        "coaching_cue": "Reset stance and vision before trying to win the exchange back.",
        "drills": ["Hit-reset-return drill", "Breath reset between exchanges"],
    },
    "GRAP_001": {
        "id": "GRAP_001",
        "name": "Accepting Bottom Position Without Immediate Frame",
        "pillar": "risk_management",
        "danger_rating": 4,
        "coaching_cue": "Build frames immediately; do not wait for the top player to settle.",
        "drills": ["First-three-seconds escape rounds", "Frame-to-hip-escape chains"],
    },
}


def grade_for_score(score: float) -> str:
    if score >= 93:
        return "A"
    if score >= 85:
        return "B"
    if score >= 77:
        return "C"
    if score >= 70:
        return "D"
    return "F"


def analyze_mistakes(mistakes: list[dict[str, Any]]) -> dict[str, Any]:
    pillar_scores = {pillar: 100.0 for pillar in PILLAR_WEIGHTS}
    normalized: list[dict[str, Any]] = []

    for item in mistakes:
        mistake_id = str(item.get("mistake_id", "")).upper()
        severity = str(item.get("severity", "risky")).lower()
        round_no = int(item.get("round", 1))
        definition = MISTAKES.get(mistake_id)
        if not definition:
            continue

        severity = severity if severity in SEVERITY_PENALTY else "risky"
        penalty = SEVERITY_PENALTY[severity] * (1 + (definition["danger_rating"] - 3) * 0.10)
        pillar = definition["pillar"]
        pillar_scores[pillar] = max(0.0, pillar_scores[pillar] - penalty)

        normalized.append(
            {
                "mistake_id": mistake_id,
                "severity": severity,
                "round": round_no,
                **definition,
                "penalty": round(penalty, 2),
            }
        )

    overall = sum(pillar_scores[p] * w for p, w in PILLAR_WEIGHTS.items())
    priority = max(normalized, key=lambda x: (x["penalty"], x["danger_rating"]), default=None)

    return {
        "overall_score": round(overall, 1),
        "grade": grade_for_score(overall),
        "pillar_scores": {
            pillar: {
                "score": round(score, 1),
                "weight": PILLAR_WEIGHTS[pillar],
            }
            for pillar, score in pillar_scores.items()
        },
        "mistakes": normalized,
        "priority_fix": priority,
        "mistake_taxonomy": list(MISTAKES.values()),
    }
