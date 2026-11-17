"""Builds a balanced, time-boxed workout from ranked candidates."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from .constants import (
    GROUP_ORDER,
    MAX_PER_GROUP,
    MAX_TOTAL_EXERCISES,
    WARMUP_RESERVE_MIN,
    WorkoutPreferences,
)
from .data_loader import format_list
from .recommender import SCORE_COLUMNS, find_alternatives, get_candidates

# Target share of compound lifts per goal (rest = isolation / core work)
COMPOUND_SHARE = {"Strength": 0.75, "Fat Loss": 0.70, "Muscle Gain": 0.50, "General Fitness": 0.50}

WORKOUT_COLUMNS = [
    "order", "exercise_id", "exercise_name", "muscle_group", "primary_muscles",
    "secondary_muscles", "equipment", "difficulty", "exercise_type",
    "movement_pattern", "muscle_emphasis", "sets", "reps", "rest_seconds",
    "est_minutes", "instructions", "common_mistakes", "caution_note",
    "alternative_ids", "reviewed", "score",
] + SCORE_COLUMNS

EXPORT_COLUMNS = {
    "order": "Order",
    "exercise_name": "Exercise",
    "muscle_group": "Muscle group",
    "primary_muscles": "Primary muscles",
    "secondary_muscles": "Secondary muscles",
    "equipment": "Equipment",
    "difficulty": "Difficulty",
    "sets": "Sets",
    "reps": "Reps",
    "rest_seconds": "Rest (seconds)",
    "est_minutes": "Estimated minutes",
    "instructions": "Instructions",
    "common_mistakes": "Common mistakes",
    "caution_note": "Caution note",
    "reviewed": "Dataset reviewed",
    "exercise_id": "Exercise ID",
}


@dataclass
class WorkoutResult:
    """Outcome of one build, including honest notes about anything missing."""
    workout: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=WORKOUT_COLUMNS))
    funnel: List = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    target_minutes: int = 0
    available_minutes: int = 0

    @property
    def empty(self) -> bool:
        return self.workout.empty

    @property
    def total_minutes(self) -> float:
        return round(float(self.workout["est_minutes"].sum()), 1) if not self.empty else 0.0


# --------------------------------------------------------------------------- #
# Prescription: sets, reps, rest and time - all derived from CSV values
# --------------------------------------------------------------------------- #
def prescribe_sets(row: pd.Series, prefs: WorkoutPreferences) -> int:
    lo, hi = int(row["sets_min"]), int(row["sets_max"])
    if prefs.intensity == "Low":
        sets = lo
    elif prefs.intensity == "High":
        sets = hi
    else:
        sets = math.ceil((lo + hi) / 2)
    if prefs.experience == "Beginner":
        sets = min(sets, 3)  # keep beginners at a manageable volume
    return int(min(max(sets, lo), hi))


def prescribe_reps(row: pd.Series, goal: str) -> str:
    """Pick a window inside the CSV rep range according to the goal."""
    lo, hi = int(row["reps_min"]), int(row["reps_max"])
    span = hi - lo
    third = round(span / 3)
    if goal == "Strength":
        start, end = lo, lo + third
    elif goal == "Muscle Gain":
        start, end = lo, lo + round(2 * span / 3)
    elif goal == "Fat Loss":
        start, end = lo + third, hi
    else:  # General Fitness
        start, end = lo, hi
    if end - start < 2 and span >= 2:  # avoid awkward ranges such as "8-9"
        if goal == "Fat Loss":
            start = max(lo, end - 2)
        else:
            end = min(hi, start + 2)
    unit = " sec" if row["rep_unit"] == "seconds" else ""
    return f"{start}{unit}" if start == end else f"{start}-{end}{unit}"


def estimate_minutes(row: pd.Series, sets: int) -> float:
    """Scale the CSV duration_minutes by chosen sets vs. the mid-range set count."""
    mid_sets = (int(row["sets_min"]) + int(row["sets_max"])) / 2
    return round(float(row["duration_minutes"]) * sets / mid_sets, 1)


def _to_item(row: pd.Series, prefs: WorkoutPreferences) -> Dict:
    sets = prescribe_sets(row, prefs)
    return {
        "exercise_id": row["exercise_id"],
        "exercise_name": row["exercise_name"],
        "muscle_group": row["muscle_group"],
        "primary_muscles": format_list(row["primary_list"]),
        "secondary_muscles": format_list(row["secondary_list"], empty="None listed"),
        "equipment": row["equipment"],
        "difficulty": row["difficulty"],
        "exercise_type": row["exercise_type"],
        "movement_pattern": row["movement_pattern"],
        "muscle_emphasis": row["muscle_emphasis"],
        "sets": sets,
        "reps": prescribe_reps(row, prefs.goal),
        "rest_seconds": int(row["rest_seconds"]),
        "est_minutes": estimate_minutes(row, sets),
        "instructions": row["instructions"],
        "common_mistakes": row["common_mistakes"],
        "caution_note": row["contraindication_notes"],
        "alternative_ids": row["alternative_ids"],
        "reviewed": bool(row["reviewed"]),
        "score": float(row["score"]),
        **{c: float(row[c]) for c in SCORE_COLUMNS},
    }


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #
def _pick_for_group(group_df: pd.DataFrame, prefs: WorkoutPreferences, budget: float,
                    cap: int) -> List[Dict]:
    """Greedy, diversity-aware pick that steers toward the goal's compound share."""
    target_share = COMPOUND_SHARE[prefs.goal]
    chosen: List[Dict] = []
    used_ids, patterns, emphases = set(), set(), set()
    remaining = budget

    def fits(item: Dict) -> bool:
        return item["est_minutes"] <= remaining + 1e-9

    for strict in (True, False):
        while len(chosen) < cap:
            items = [_to_item(r, prefs) for _, r in group_df.iterrows() if r["exercise_id"] not in used_ids]
            items = [i for i in items if fits(i)]
            if strict:
                items = [i for i in items if i["movement_pattern"] not in patterns
                         and i["muscle_emphasis"] not in emphases]
            if not items:
                break
            n_comp = sum(1 for c in chosen if c["exercise_type"] == "compound")
            want_compound = not chosen or (n_comp / len(chosen)) < target_share
            preferred = [i for i in items if (i["exercise_type"] == "compound") == want_compound]
            pick = (preferred or items)[0]  # group_df is already ranked by score
            chosen.append(pick)
            used_ids.add(pick["exercise_id"])
            patterns.add(pick["movement_pattern"])
            emphases.add(pick["muscle_emphasis"])
            remaining -= pick["est_minutes"]
    return chosen


def _sort_workout(items: List[Dict]) -> pd.DataFrame:
    def key(i: Dict):
        g = GROUP_ORDER.index(i["muscle_group"]) if i["muscle_group"] in GROUP_ORDER else 99
        return (g, 0 if i["exercise_type"] == "compound" else 1, -i["score"])
    ordered = sorted(items, key=key)
    for n, item in enumerate(ordered, start=1):
        item["order"] = n
    return pd.DataFrame(ordered, columns=WORKOUT_COLUMNS)


def build_workout(df: pd.DataFrame, prefs: WorkoutPreferences) -> WorkoutResult:
    """Create a workout from the CSV. Never pads with unsuitable exercises."""
    available = max(prefs.duration - WARMUP_RESERVE_MIN, 0)
    result = WorkoutResult(target_minutes=prefs.duration, available_minutes=available)

    ranked, funnel = get_candidates(df, prefs)
    result.funnel = funnel
    if ranked.empty:
        result.warnings.append(
            "No suitable exercises match your selections. Try another location, "
            "add equipment, choose different muscles, or remove some exclusions."
        )
        return result

    groups = [g for g in GROUP_ORDER if g in prefs.targets and g in set(ranked["muscle_group"])]
    missing = [g for g in prefs.targets if g not in groups]
    for g in missing:
        result.warnings.append(
            f"No suitable {g} exercises were found for your equipment, location, "
            "experience level and exclusions, so none were added."
        )

    per_group_budget = available / len(groups)
    cap = min(MAX_PER_GROUP, MAX_TOTAL_EXERCISES)
    items: List[Dict] = []
    for g in groups:
        items += _pick_for_group(ranked[ranked["muscle_group"] == g], prefs, per_group_budget, cap)

    # Spend leftover minutes on the best remaining exercises, rotating across groups
    used = sum(i["est_minutes"] for i in items)
    chosen_ids = {i["exercise_id"] for i in items}
    while len(items) < MAX_TOTAL_EXERCISES:
        counts = {g: sum(1 for i in items if i["muscle_group"] == g) for g in groups}
        options = []
        for g in sorted(groups, key=lambda x: counts[x]):
            if counts[g] >= MAX_PER_GROUP:
                continue
            for _, r in ranked[ranked["muscle_group"] == g].iterrows():
                if r["exercise_id"] in chosen_ids:
                    continue
                item = _to_item(r, prefs)
                if used + item["est_minutes"] <= available + 1e-9:
                    options.append(item)
                    break
            if options:
                break
        if not options:
            break
        items.append(options[0])
        chosen_ids.add(options[0]["exercise_id"])
        used += options[0]["est_minutes"]

    if not items:
        result.warnings.append("The time available is too short for any matching exercise.")
        return result

    result.workout = _sort_workout(items)
    planned = result.total_minutes
    if available and planned < 0.8 * available:
        result.warnings.append(
            f"Only {planned:g} of {available} available minutes could be filled with suitable "
            "exercises. Adding more muscle groups or equipment would give more options."
        )
    return result


# --------------------------------------------------------------------------- #
# Replacement and export
# --------------------------------------------------------------------------- #
def replace_exercise(workout: pd.DataFrame, old_id: str, new_row: pd.Series,
                     prefs: WorkoutPreferences) -> pd.DataFrame:
    """Swap one exercise for an alternative, keeping its position in the plan."""
    if old_id not in set(workout["exercise_id"]):
        return workout
    if new_row["exercise_id"] in set(workout["exercise_id"]):
        return workout  # already in the workout
    item = _to_item(new_row, prefs)
    out = workout.copy().reset_index(drop=True)
    idx = out.index[out["exercise_id"] == old_id][0]
    item["order"] = int(out.at[idx, "order"])
    for col, val in item.items():
        out.at[idx, col] = val
    return out[WORKOUT_COLUMNS]


def alternatives_for(df: pd.DataFrame, prefs: WorkoutPreferences, workout: pd.DataFrame,
                     exercise_id: str, limit: int = 6) -> pd.DataFrame:
    return find_alternatives(df, prefs, exercise_id, list(workout["exercise_id"]), limit)


def summarize(workout: pd.DataFrame, target_minutes: int) -> Dict:
    if workout.empty:
        return {"exercises": 0, "minutes": 0.0, "target": target_minutes, "groups": {}}
    groups = workout["muscle_group"].value_counts().to_dict()
    return {
        "exercises": int(len(workout)),
        "minutes": round(float(workout["est_minutes"].sum()), 1),
        "target": target_minutes,
        "groups": groups,
        "total_sets": int(workout["sets"].sum()),
    }


def to_csv_bytes(workout: pd.DataFrame) -> bytes:
    """CSV export for download. Keeps the dataset 'reviewed' flag visible."""
    out = workout[list(EXPORT_COLUMNS)].rename(columns=EXPORT_COLUMNS).copy()
    out["Equipment"] = out["Equipment"].str.replace("_", " ").str.capitalize()
    out["Muscle group"] = out["Muscle group"].str.capitalize()
    out["Difficulty"] = out["Difficulty"].str.capitalize()
    return out.to_csv(index=False).encode("utf-8")


def prescribe_item(row: pd.Series, prefs: WorkoutPreferences) -> Dict:
    """Public helper: sets/reps/rest/time and display fields for one ranked row."""
    return _to_item(row, prefs)
