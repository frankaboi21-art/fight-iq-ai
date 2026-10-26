"""Explainable practice scheduling from existing, athlete-confirmed advice.

This organizer does not infer technique, invent drills, or raise training intensity.
"""
from datetime import date, timedelta
import re


def duration(task):
    """Use explicit minutes only; do not guess at rounds, repetitions or ranges."""
    override = task.get("planned_minutes")
    if override is not None:
        return override, "Time chosen by you"
    if isinstance(task.get("minutes"), int) and 1 <= task["minutes"] <= 60:
        return task["minutes"], "Time from the saved review"
    match = re.fullmatch(r"([1-9]\d?)\s*(?:minutes?|mins?)", task.get("duration", "").strip(), re.I)
    if match and int(match[1]) <= 60:
        return int(match[1]), "Time from the saved review"
    return None, "Choose a practice time with your coach in the source review."


def organize(profile, confirmed):
    candidates, completed, seen = [], [], set()
    for entry in confirmed:  # Caller orders by performed date, then creation time.
        for task in entry["tasks"]:
            key = " ".join(task["name"].casefold().split())
            if key in seen:
                continue
            seen.add(key)
            item = {**task, "entry_id": entry["id"], "source_title": entry["title"],
                    "performed_on": entry["performed_on"], "training_type": entry["training_type"],
                    "source_correction": entry["feedback"].get("correction", ""),
                    "revisit": task["status"] == "reassessed"}
            if task["status"] == "reassessed" and task["outcome"] == "improving":
                completed.append(item)
                continue
            if task["status"] == "reassessed":
                priority = 0 if task["outcome"] == "needs_work" else 1
                reason = "Your later review still needs work." if priority == 0 else "Your later review recorded no change."
                next_step = "Review the drill and your reassessment notes with your coach, then adjust and practice again."
            elif task["status"] == "practiced":
                priority, reason = 2, "You recorded practice; a comparable reassessment is still missing."
                next_step = "Use the success check in a later review of the same discipline and training setting."
            else:
                priority, reason = 3, "This is an unfinished drill from a confirmed review."
                next_step = "Practice the agreed correction, then compare it with a later review."
            minutes, time_basis = duration(task)
            candidates.append({**item, "priority": priority, "priority_reason": reason,
                               "next_step": next_step, "allocated_minutes": minutes, "time_basis": time_basis})
    # Stable sorting preserves recency within a priority. Priority is not a severity score.
    candidates.sort(key=lambda t: t["priority"])
    selected, deferred, used = [], [], 0
    for task in candidates:
        minutes = task["allocated_minutes"]
        if minutes is None:
            why = "The saved duration is not an exact number of minutes. Choose a time in the source review."
        elif minutes > profile["practice_minutes"]:
            why = "The full drill exceeds your session budget. Review its timing or update your availability."
        elif len(selected) >= 3:
            why = "Three priorities are already selected. Keep the current practice focused before adding more."
        elif used + minutes > profile["practice_minutes"]:
            why = "The remaining session time cannot fit the full drill. No instructions or duration were shortened."
        else:
            selected.append(task)
            used += minutes
            continue
        deferred.append({**task, "deferred_reason": why})
    count = profile["sessions_per_week"]
    sessions = []
    for index in range(count if selected else 0):
        final = index == count - 1
        sessions.append({"number": index + 1, "minutes": used,
                         "focus": "Practice and collect a comparable review" if final else "Practice the selected corrections",
                         "task_refs": [{"entry_id": t["entry_id"], "task_id": t["id"]} for t in selected],
                         "check": "After practice, compare each success check with a later confirmed review in the same training setting. Record improving, unchanged, or needs work; do not assume progress." if final else
                                  "Note what you observed against each success check. Record actual practice in the source review."})
    return {"tasks": selected, "deferred_tasks": deferred, "improving_tasks": completed,
            "weekly_plan": {"generated_on": date.today().isoformat(),
                            "suggested_review_on": (date.today() + timedelta(days=7)).isoformat(),
                            "sessions": sessions, "minutes_per_session": used,
                            "total_minutes": used * len(sessions),
                            "note": "A flexible outline for your chosen availability, not a prescription to train every day. Keep the original drill instructions and intensity. Session slots do not mark practice complete."}}
