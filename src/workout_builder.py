
"""
workout_builder.py
Compose a balanced workout session from ranked exercises,
respecting duration, movement-pattern variety, and volume limits.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Volume / duration tables
# ---------------------------------------------------------------------------

# Target number of exercises per session duration
DURATION_EXERCISE_COUNT: dict[int, tuple[int, int]] = {
    30: (3, 4),
    45: (4, 5),
    60: (5, 6),
    75: (6, 7),
    90: (7, 8),
}

# Sets to use depending on intensity and goal
INTENSITY_SET_BIAS: dict[str, dict[str, int]] = {
    "low":      {"muscle_gain": 2, "strength": 3, "general_fitness": 2, "fat_loss": 2},
    "moderate": {"muscle_gain": 3, "strength": 3, "general_fitness": 3, "fat_loss": 3},
    "high":     {"muscle_gain": 4, "strength": 5, "general_fitness": 4, "fat_loss": 4},
}

# Approximate time (seconds) per set including reps
SET_DURATION_SECONDS = 40  # active set time
TRANSITION_SECONDS = 30    # time to move to next exercise


def _pick_set_count(row: pd.Series, intensity: str, goal: str) -> int:
    bias = INTENSITY_SET_BIAS.get(intensity, {}).get(goal, 3)
    sets_min = int(row["sets_min"])
    sets_max = int(row["sets_max"])
    chosen = max(sets_min, min(sets_max, bias))
    return chosen


def _estimate_exercise_time(row: pd.Series, sets: int) -> float:
    """Return approximate exercise time in minutes."""
    rest = int(row["rest_seconds"])
    active = sets * SET_DURATION_SECONDS
    rest_total = (sets - 1) * rest
    total_seconds = active + rest_total + TRANSITION_SECONDS
    return round(total_seconds / 60, 1)


def build_workout(ranked_df: pd.DataFrame, prefs: dict) -> list[dict]:
    """
    Select and configure exercises for the session.

    Returns a list of exercise dicts with resolved sets, reps, rest, duration.
    Returns empty list if no exercises are available.
    """
    if ranked_df.empty:
        return []

    duration = int(prefs["duration"])
    intensity = prefs["intensity"]
    goal = prefs["goal"]

    min_ex, max_ex = DURATION_EXERCISE_COUNT.get(duration, (4, 5))
    target_count = max_ex

    selected: list[dict] = []
    used_patterns: list[str] = []
    total_minutes = 5.0  # warm-up buffer

    for _, row in ranked_df.iterrows():
        if len(selected) >= target_count:
            break
        if total_minutes >= duration:
            break

        # Avoid too many same movement patterns (allow at most 2 per pattern)
        mv = str(row.get("movement_pattern", "")).lower()
        if used_patterns.count(mv) >= 2:
            continue

        sets = _pick_set_count(row, intensity, goal)
        ex_time = _estimate_exercise_time(row, sets)

        if total_minutes + ex_time > duration + 5:  # small overflow allowed
            # Try with fewer sets
            sets = max(int(row["sets_min"]), sets - 1)
            ex_time = _estimate_exercise_time(row, sets)
            if total_minutes + ex_time > duration + 5:
                continue

        # Rep range: use middle or goal-biased value
        reps_min = int(row["reps_min"])
        reps_max = int(row["reps_max"])
        rep_unit = str(row.get("rep_unit", "reps")).lower()

        if goal == "strength":
            reps = reps_min
        elif goal == "fat_loss":
            reps = reps_max
        else:
            reps = (reps_min + reps_max) // 2

        reps = max(reps_min, min(reps_max, reps))

        selected.append({
            "exercise_id": row["exercise_id"],
            "exercise_name": row["exercise_name"],
            "primary_muscles": row.get("primary_muscles", ""),
            "secondary_muscles": row.get("secondary_muscles", []),
            "muscle_group": row.get("muscle_group", ""),
            "movement_pattern": mv,
            "equipment": row.get("equipment", []),
            "difficulty": row.get("difficulty", ""),
            "exercise_type": row.get("exercise_type", ""),
            "instructions": row.get("instructions", ""),
            "common_mistakes": row.get("common_mistakes", ""),
            "contraindication_notes": row.get("contraindication_notes", ""),
            "alternative_ids": row.get("alternative_ids", []),
            "sets": sets,
            "reps": reps,
            "rep_unit": rep_unit,
            "rest_seconds": int(row["rest_seconds"]),
            "estimated_minutes": ex_time,
            "score": float(row.get("score", 0.0)),
        })

        used_patterns.append(mv)
        total_minutes += ex_time

    return selected


def estimate_total_duration(exercises: list[dict]) -> float:
    """Return estimated total session duration in minutes including warm-up."""
    warmup = 5.0
    cooldown = 3.0
    ex_time = sum(e["estimated_minutes"] for e in exercises)
    return round(warmup + ex_time + cooldown, 1)
