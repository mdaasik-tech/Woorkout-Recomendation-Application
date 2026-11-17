"""Rule-based recommender: filtering, transparent weighted scoring, alternatives."""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .constants import BODYWEIGHT, WEIGHTS, WorkoutPreferences
from .safety_filters import apply_safety_filters

SCORE_COLUMNS = list(WEIGHTS.keys())

# --- Rule tables (kept in one place so they stay transparent) ---------------- #
# Fitness-goal relevance: how well the exercise type serves each goal (0-1)
GOAL_TYPE_SCORE = {
    "Muscle Gain":     {"compound": 1.0, "isolation": 0.9, "isometric": 0.3, "stability": 0.3},
    "Strength":        {"compound": 1.0, "isolation": 0.4, "isometric": 0.3, "stability": 0.4},
    "General Fitness": {"compound": 1.0, "isolation": 0.6, "isometric": 0.8, "stability": 0.9},
    "Fat Loss":        {"compound": 1.0, "isolation": 0.4, "isometric": 0.6, "stability": 0.7},
}
GOAL_REP_WINDOW = {"Muscle Gain": (6, 15), "General Fitness": (8, 15)}
LOADABLE_EQUIPMENT = {"barbell", "dumbbells", "machines", "cable_machine"}

# Experience: how well the exercise's difficulty suits the user (0-1)
EXPERIENCE_DIFFICULTY_SCORE = {
    "Beginner":     {"low": 1.0, "moderate": 0.6, "high": 0.2},
    "Intermediate": {"low": 0.6, "moderate": 1.0, "high": 0.7},
    "Advanced":     {"low": 0.4, "moderate": 0.8, "high": 1.0},
}
INTENSITY_RANK = {"low": 0, "moderate": 1, "high": 2}


# --------------------------------------------------------------------------- #
# Step 1 - hard filters
# --------------------------------------------------------------------------- #
def filter_candidates(df: pd.DataFrame, prefs: WorkoutPreferences) -> Tuple[pd.DataFrame, List[Tuple[str, int]]]:
    """Muscle, location, equipment, experience, then exclusion/safety filters.

    Returns the surviving rows plus a 'funnel' (label, rows remaining) that
    explains where options disappeared.
    """
    funnel: List[Tuple[str, int]] = [("All exercises in dataset", len(df))]

    out = df[df["muscle_group"].isin(prefs.targets)]
    funnel.append(("Target muscle group", len(out)))

    loc = prefs.location.lower()
    out = out[out["location_list"].apply(lambda locs: loc in locs)]
    funnel.append((f"Location: {prefs.location}", len(out)))

    allowed_equipment = set(prefs.equipment) | {BODYWEIGHT}
    out = out[out["equipment"].isin(allowed_equipment)]
    funnel.append(("Available equipment", len(out)))

    level = prefs.experience.lower()
    out = out[out["level_list"].apply(lambda levels: level in levels)]
    funnel.append((f"Suitable for {prefs.experience.lower()}", len(out)))

    out, _removed = apply_safety_filters(out, prefs)
    funnel.append(("After exclusions and safety filters", len(out)))
    return out.copy(), funnel


# --------------------------------------------------------------------------- #
# Step 2 - weighted scoring (each component 0-1, total 0-100)
# --------------------------------------------------------------------------- #
def _range_overlap(lo: int, hi: int, win_lo: int, win_hi: int) -> float:
    """Share of the exercise's rep range that sits inside a preferred window."""
    if hi <= lo:
        return 1.0 if win_lo <= lo <= win_hi else 0.0
    overlap = max(0, min(hi, win_hi) - max(lo, win_lo))
    return overlap / (hi - lo)


def _goal_score(row: pd.Series, goal: str) -> float:
    type_score = GOAL_TYPE_SCORE[goal].get(row["exercise_type"], 0.5)
    if row["rep_unit"] != "reps":
        param = 0.5  # timed holds: neutral on rep-range rules
    elif goal == "Strength":
        reps_min = row["reps_min"]
        rep_part = 1.0 if reps_min <= 8 else 0.7 if reps_min <= 10 else 0.4
        load_part = 1.0 if row["equipment"] in LOADABLE_EQUIPMENT else 0.5
        param = 0.7 * rep_part + 0.3 * load_part
    elif goal == "Fat Loss":
        rest = row["rest_seconds"]
        param = 1.0 if rest <= 60 else 0.8 if rest <= 75 else 0.6 if rest <= 90 else 0.4
    else:
        win_lo, win_hi = GOAL_REP_WINDOW[goal]
        param = _range_overlap(row["reps_min"], row["reps_max"], win_lo, win_hi)
    return 0.5 * type_score + 0.5 * param


def _experience_score(row: pd.Series, experience: str) -> float:
    n_levels = max(len(row["level_list"]), 1)
    level_fit = {1: 1.0, 2: 0.85}.get(n_levels, 0.7)  # more specific listing = better fit
    diff_fit = EXPERIENCE_DIFFICULTY_SCORE[experience].get(row["difficulty"], 0.5)
    return 0.5 * level_fit + 0.5 * diff_fit


def _preference_score(difficulty: str, intensity: str) -> float:
    gap = abs(INTENSITY_RANK.get(difficulty, 1) - INTENSITY_RANK[intensity.lower()])
    return {0: 1.0, 1: 0.5}.get(gap, 0.0)


def score_exercises(candidates: pd.DataFrame, prefs: WorkoutPreferences) -> pd.DataFrame:
    """Add the five weighted components and `score` (0-100) to the candidates."""
    df = candidates.copy()
    if df.empty:
        for col in SCORE_COLUMNS + ["score"]:
            df[col] = pd.Series(dtype=float)
        return df

    # Muscle match: 70 % target-group match (always 1 after filtering)
    # + 30 % muscle engagement (secondary muscles worked, capped at 3).
    engagement = np.minimum(df["secondary_list"].apply(len) / 3.0, 1.0)
    df["muscle_match"] = 0.7 * 1.0 + 0.3 * engagement

    # Equipment match: equipment the user explicitly selected = 1.0;
    # bodyweight (always assumed) = 0.8 unless it is all they have.
    explicit = set(prefs.equipment)
    if explicit:
        df["equipment_match"] = np.where(df["equipment"].isin(explicit), 1.0, 0.8)
    else:
        df["equipment_match"] = 1.0

    df["experience_suitability"] = df.apply(_experience_score, axis=1, experience=prefs.experience)
    df["goal_relevance"] = df.apply(_goal_score, axis=1, goal=prefs.goal)
    df["user_preference"] = df["difficulty"].apply(_preference_score, intensity=prefs.intensity)

    df["score"] = 100.0 * sum(df[c] * w for c, w in WEIGHTS.items())
    df["score"] = df["score"].round(1)
    return df.sort_values(["score", "exercise_name"], ascending=[False, True]).reset_index(drop=True)


def get_candidates(df: pd.DataFrame, prefs: WorkoutPreferences) -> Tuple[pd.DataFrame, List[Tuple[str, int]]]:
    """Full pipeline: filters first, then ranking. Empty result is never padded."""
    filtered, funnel = filter_candidates(df, prefs)
    return score_exercises(filtered, prefs), funnel


# --------------------------------------------------------------------------- #
# Step 3 - alternatives
# --------------------------------------------------------------------------- #
def find_alternatives(df: pd.DataFrame, prefs: WorkoutPreferences, exercise_id: str,
                      exclude_ids: List[str], limit: int = 6) -> pd.DataFrame:
    """Suitable replacements for one exercise, taken only from the CSV.

    Candidates must pass every user filter (equipment, location, level,
    exclusions, safety) and share the exercise's muscle group. Exercises listed
    in the CSV's `alternative_ids` come first, then similar movements.
    """
    match = df[df["exercise_id"] == exercise_id]
    if match.empty:
        return pd.DataFrame()
    current = match.iloc[0]

    scoped = prefs.copy_with(targets=[current["muscle_group"]])
    pool, _ = get_candidates(df, scoped)
    pool = pool[~pool["exercise_id"].isin(set(exclude_ids) | {exercise_id})].copy()
    if pool.empty:
        return pool

    listed = {a: i for i, a in enumerate(current["alt_list"])}
    pool["listed_rank"] = pool["exercise_id"].map(listed)
    pool["same_pattern"] = pool["movement_pattern"].eq(current["movement_pattern"]) & (current["movement_pattern"] != "")
    pool["same_emphasis"] = pool["muscle_emphasis"].eq(current["muscle_emphasis"]) & (current["muscle_emphasis"] != "")
    pool["same_type"] = pool["exercise_type"].eq(current["exercise_type"])

    def reason(r: pd.Series) -> str:
        parts = []
        if not pd.isna(r["listed_rank"]):
            parts.append("Listed as an alternative in the dataset")
        if r["same_pattern"]:
            parts.append("same movement pattern")
        if r["same_emphasis"]:
            parts.append("same muscle emphasis")
        if not parts:
            parts.append(f"also trains {current['muscle_group']}")
        text = ", ".join(parts)
        return text[0].upper() + text[1:]

    pool["reason"] = pool.apply(reason, axis=1)
    pool["alt_source"] = np.where(pool["listed_rank"].notna(), "Dataset alternative", "Similar exercise")
    pool["similarity"] = (pool["same_pattern"].astype(int) * 2 + pool["same_emphasis"].astype(int)
                          + pool["same_type"].astype(int))
    pool["_rank"] = pool["listed_rank"].fillna(999)
    pool = pool.sort_values(["_rank", "similarity", "score"], ascending=[True, False, False])
    return pool.drop(columns=["_rank"]).head(limit).reset_index(drop=True)
