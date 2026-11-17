"""Validation of the exercise dataset and of user preferences."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

import pandas as pd

from .constants import (
    DURATIONS,
    EXPERIENCE_LEVELS,
    GOALS,
    INTENSITIES,
    LOCATIONS,
    TARGET_MUSCLES,
    WEIGHTS,
    WorkoutPreferences,
)

REQUIRED_COLUMNS = [
    "exercise_id", "exercise_name", "muscle_group", "primary_muscles",
    "equipment", "location", "level", "difficulty", "exercise_type",
    "instructions", "common_mistakes", "sets_min", "sets_max",
    "reps_min", "reps_max", "rep_unit", "rest_seconds", "duration_minutes",
]
# Optional columns: missing columns or missing values are handled safely.
OPTIONAL_COLUMNS = [
    "secondary_muscles", "muscle_emphasis", "movement_pattern",
    "contraindication_notes", "alternative_ids", "source", "reviewed",
]
NUMERIC_COLUMNS = [
    "sets_min", "sets_max", "reps_min", "reps_max",
    "rest_seconds", "duration_minutes",
]
# Required columns that must never be blank
NON_EMPTY_COLUMNS = [
    "exercise_id", "exercise_name", "muscle_group", "primary_muscles",
    "equipment", "location", "level", "difficulty",
]
VALID_LEVELS = {"beginner", "intermediate", "advanced"}
VALID_LOCATIONS = {"gym", "home"}
VALID_DIFFICULTIES = {"low", "moderate", "high"}


@dataclass
class ValidationReport:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _tokens(value) -> List[str]:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return []
    return [t.strip().lower() for t in str(value).split(";") if t.strip()]


def validate_dataframe(df: pd.DataFrame) -> ValidationReport:
    """Validate the raw CSV frame. Missing *optional* data is never an error."""
    report = ValidationReport()

    if df is None or df.empty:
        report.errors.append("The exercise file contains no rows.")
        return report

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        report.errors.append(
            "Missing required column(s): " + ", ".join(missing) + "."
        )
        return report  # nothing else can be checked reliably

    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            report.warnings.append(
                f"Optional column '{col}' is missing; default values are used."
            )

    # Blank required values
    for col in NON_EMPTY_COLUMNS:
        blanks = df[col].isna() | (df[col].astype(str).str.strip() == "")
        if blanks.any():
            ids = df.loc[blanks, "exercise_id"].astype(str).tolist()[:5]
            report.errors.append(
                f"Column '{col}' has {int(blanks.sum())} blank value(s) "
                f"(e.g. rows {ids})."
            )

    # Duplicate IDs
    dupes = df["exercise_id"].astype(str).str.strip().duplicated()
    if dupes.any():
        report.errors.append(
            "Duplicate exercise_id values: "
            + ", ".join(df.loc[dupes, "exercise_id"].astype(str).head(5)) + "."
        )

    # Numeric columns
    numeric = {}
    numeric_ok = True
    for col in NUMERIC_COLUMNS:
        numeric[col] = pd.to_numeric(df[col], errors="coerce")
        bad = numeric[col].isna() | (numeric[col] <= 0)
        if bad.any():
            numeric_ok = False
            report.errors.append(
                f"Column '{col}' has {int(bad.sum())} missing, non-numeric "
                "or non-positive value(s)."
            )
    if numeric_ok:
        if (numeric["sets_min"] > numeric["sets_max"]).any():
            report.errors.append("Some rows have sets_min greater than sets_max.")
        if (numeric["reps_min"] > numeric["reps_max"]).any():
            report.errors.append("Some rows have reps_min greater than reps_max.")

    # Allowed categorical values
    for col, valid in (("difficulty", VALID_DIFFICULTIES),):
        bad = ~df[col].astype(str).str.strip().str.lower().isin(valid)
        if bad.any():
            report.errors.append(f"Column '{col}' contains unexpected values.")
    for col, valid in (("level", VALID_LEVELS), ("location", VALID_LOCATIONS)):
        bad_rows = df[col].apply(lambda v: not set(_tokens(v)) <= valid or not _tokens(v))
        if bad_rows.any():
            report.errors.append(f"Column '{col}' contains unexpected values.")

    # Unknown muscle groups are a warning (rows simply can't be targeted)
    known = set(TARGET_MUSCLES.values())
    unknown = set(df["muscle_group"].astype(str).str.strip().str.lower()) - known
    if unknown:
        report.warnings.append(
            "Muscle groups not offered in the app: " + ", ".join(sorted(unknown)) + "."
        )

    # Alternative IDs should point at real exercises
    if "alternative_ids" in df.columns:
        ids = set(df["exercise_id"].astype(str).str.strip())
        dangling = {a for v in df["alternative_ids"] for a in _tokens_keep_case(v)} - ids
        if dangling:
            report.warnings.append(
                f"{len(dangling)} alternative id(s) do not match any exercise_id "
                "and are ignored."
            )

    # Review status is informational, never silently assumed
    if "reviewed" in df.columns:
        reviewed = df["reviewed"].astype(str).str.strip().str.lower().isin(
            {"true", "1", "yes", "y"}
        )
        if not reviewed.all():
            report.warnings.append(
                f"{int((~reviewed).sum())} of {len(df)} exercises are marked as "
                "not reviewed."
            )
    return report


def _tokens_keep_case(value) -> List[str]:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return []
    return [t.strip() for t in str(value).split(";") if t.strip()]


def validate_weights() -> bool:
    """Scoring weights must sum to exactly 100 %."""
    return abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def validate_preferences(prefs: WorkoutPreferences, equipment_options: Iterable[str] = ()) -> List[str]:
    """Return a list of human-readable problems (empty list = valid)."""
    problems: List[str] = []
    if prefs.goal not in GOALS:
        problems.append("Please choose a fitness goal.")
    if prefs.experience not in EXPERIENCE_LEVELS:
        problems.append("Please choose your experience level.")
    if not prefs.targets:
        problems.append("Please select at least one target muscle.")
    elif not set(prefs.targets) <= set(TARGET_MUSCLES.values()):
        problems.append("One or more target muscles are not recognised.")
    if prefs.location not in LOCATIONS:
        problems.append("Please choose a workout location.")
    if prefs.duration not in DURATIONS:
        problems.append("Please choose a workout duration.")
    if prefs.intensity not in INTENSITIES:
        problems.append("Please choose a preferred intensity.")
    options = set(equipment_options)
    if options and not set(prefs.equipment) <= options:
        problems.append("One or more equipment choices are not recognised.")
    return problems
