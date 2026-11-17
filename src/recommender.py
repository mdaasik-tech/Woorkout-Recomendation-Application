"""
recommender.py
Rule-based filtering and weighted ranking of exercises.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Goal → movement pattern preference mapping
# ---------------------------------------------------------------------------
GOAL_MOVEMENT_PREFS: dict[str, list[str]] = {
    "muscle_gain": [
        "horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull",
        "squat", "hip_hinge", "elbow_flexion", "elbow_extension",
        "shoulder_abduction", "hip_extension",
    ],
    "strength": [
        "horizontal_push", "vertical_push", "horizontal_pull", "squat",
        "hip_hinge",
    ],
    "general_fitness": [],  # all patterns welcome
    "fat_loss": [
        "squat", "hip_hinge", "horizontal_push", "horizontal_pull",
        "vertical_pull", "anti_extension",
    ],
}

# Goal → preferred exercise types
GOAL_TYPE_PREFS: dict[str, list[str]] = {
    "muscle_gain": ["compound", "isolation"],
    "strength": ["compound"],
    "general_fitness": ["compound", "isolation", "stability", "isometric"],
    "fat_loss": ["compound", "stability"],
}

# Experience level → allowed difficulty levels (cumulative)
LEVEL_DIFFICULTY_MAP: dict[str, list[str]] = {
    "beginner": ["low"],
    "intermediate": ["low", "moderate"],
    "advanced": ["low", "moderate", "high"],
}


def filter_exercises(df: pd.DataFrame, prefs: dict) -> pd.DataFrame:
    """
    Apply hard filters: muscle group, equipment, location, level.
    Returns a filtered DataFrame.
    """
    result = df.copy()
    muscle = prefs["muscle_group"].lower()
    equipment_list = [e.lower() for e in prefs["equipment"]]
    location = prefs["location"].lower()
    level = prefs["level"].lower()

    # 1. Muscle group match (primary column 'muscle_group' or 'primary_muscles')
    if "muscle_group" in result.columns:
        result = result[result["muscle_group"].str.lower() == muscle]
    else:
        result = result[result["primary_muscles"].str.lower() == muscle]

    if result.empty:
        return result

    # 2. Equipment: exercise's required equipment intersects user's available equipment
    result = result[result["equipment"].apply(
        lambda eq_list: bool(set(eq_list) & set(equipment_list))
    )]

    if result.empty:
        return result

    # 3. Location
    result = result[result["location"].apply(
        lambda loc_list: location in loc_list
    )]

    if result.empty:
        return result

    # 4. Experience level
    result = result[result["level"].apply(
        lambda lvl_list: level in lvl_list
    )]

    return result.reset_index(drop=True)


def _score_exercise(row: pd.Series, prefs: dict) -> float:
    """
    Compute a weighted relevance score for a single exercise.
    Components (sum = 1.0):
      muscle_match   0.35
      equipment      0.20
      level_match    0.20
      goal_match     0.15
      preference     0.10
    """
    muscle = prefs["muscle_group"].lower()
    equipment_list = [e.lower() for e in prefs["equipment"]]
    level = prefs["level"].lower()
    goal = prefs["goal"]

    # Muscle match (1 if exact primary muscle, 0.5 if secondary)
    primary_ok = str(row.get("primary_muscles", "")).lower() == muscle
    secondary_list = row.get("secondary_muscles", [])
    if isinstance(secondary_list, str):
        secondary_list = [s.strip().lower() for s in secondary_list.split(";")]
    secondary_ok = muscle in secondary_list
    muscle_score = 1.0 if primary_ok else (0.5 if secondary_ok else 0.0)

    # Equipment match (proportion of exercise equip that user has)
    ex_eq = row.get("equipment", [])
    if not isinstance(ex_eq, list):
        ex_eq = []
    if ex_eq:
        eq_score = len(set(ex_eq) & set(equipment_list)) / len(ex_eq)
    else:
        eq_score = 0.0

    # Level match
    ex_levels = row.get("level", [])
    if not isinstance(ex_levels, list):
        ex_levels = []
    level_score = 1.0 if level in ex_levels else 0.0

    # Goal / movement-pattern match
    preferred_mvs = GOAL_MOVEMENT_PREFS.get(goal, [])
    mv = str(row.get("movement_pattern", "")).lower()
    if not preferred_mvs:
        goal_score = 1.0
    else:
        goal_score = 1.0 if mv in preferred_mvs else 0.5

    # Preference: compound gets a small bonus for muscle_gain / strength / fat_loss
    ex_type = str(row.get("exercise_type", "")).lower()
    preferred_types = GOAL_TYPE_PREFS.get(goal, [])
    if preferred_types:
        pref_score = 1.0 if ex_type == preferred_types[0] else (0.5 if ex_type in preferred_types else 0.0)
    else:
        pref_score = 1.0

    score = (
        0.35 * muscle_score
        + 0.20 * eq_score
        + 0.20 * level_score
        + 0.15 * goal_score
        + 0.10 * pref_score
    )
    return round(score, 4)


def rank_exercises(df: pd.DataFrame, prefs: dict) -> pd.DataFrame:
    """Add a 'score' column and sort descending."""
    if df.empty:
        return df
    df = df.copy()
    df["score"] = df.apply(lambda row: _score_exercise(row, prefs), axis=1)
    return df.sort_values("score", ascending=False).reset_index(drop=True)


def find_alternatives(
    exercise_id: str,
    df_all: pd.DataFrame,
    prefs: dict,
    n: int = 3,
) -> pd.DataFrame:
    """
    Find alternative exercises for a given exercise_id.
    Prefers alternatives listed in alternative_ids, then falls back to
    same muscle group + same movement pattern + equipment filter.
    """
    # Fetch the target exercise
    target_rows = df_all[df_all["exercise_id"] == exercise_id]
    if target_rows.empty:
        return pd.DataFrame()

    target = target_rows.iloc[0]
    alt_ids: list[str] = target.get("alternative_ids", []) or []
    if not isinstance(alt_ids, list):
        alt_ids = []

    # Try preferred alternatives first
    if alt_ids:
        alt_df = df_all[df_all["exercise_id"].isin(alt_ids)].copy().reset_index(drop=True)
        if not alt_df.empty and "equipment" in alt_df.columns:
            alt_df = alt_df[alt_df["equipment"].apply(
                lambda eq_list: bool(set(eq_list) & set([e.lower() for e in prefs["equipment"]]))
            )]
        if not alt_df.empty and "location" in alt_df.columns:
            alt_df = alt_df[alt_df["location"].apply(
                lambda loc_list: prefs["location"].lower() in loc_list
            )]
        if not alt_df.empty and "level" in alt_df.columns:
            alt_df = alt_df[alt_df["level"].apply(
                lambda lvl_list: prefs["level"].lower() in lvl_list
            )]
        if len(alt_df) >= n:
            return rank_exercises(alt_df, prefs).head(n)

    # Fallback: same muscle group + movement pattern
    mv = str(target.get("movement_pattern", "")).lower()
    mg = str(target.get("muscle_group", "")).lower()
    fallback = df_all[
        (df_all["exercise_id"] != exercise_id)
        & (df_all["muscle_group"].str.lower() == mg)
    ].copy()
    if mv:
        mv_match = fallback[fallback["movement_pattern"].str.lower() == mv]
        if len(mv_match) >= n:
            fallback = mv_match

    fallback = fallback[fallback["equipment"].apply(
        lambda eq_list: bool(set(eq_list) & set([e.lower() for e in prefs["equipment"]]))
    )]
    fallback = fallback[fallback["location"].apply(
        lambda loc_list: prefs["location"].lower() in loc_list
    )]
    fallback = fallback[fallback["level"].apply(
        lambda lvl_list: prefs["level"].lower() in lvl_list
    )]
    return rank_exercises(fallback, prefs).head(n)

