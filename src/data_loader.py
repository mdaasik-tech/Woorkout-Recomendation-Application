
"""
data_loader.py
Loads and validates the exercises.csv dataset.
"""
from __future__ import annotations

import pandas as pd
from pathlib import Path

EXERCISE_FILE = Path(__file__).parent.parent / "exercises.csv"

REQUIRED_COLUMNS = [
    "exercise_id",
    "exercise_name",
    "muscle_group",
    "primary_muscles",
    "equipment",
    "location",
    "level",
    "difficulty",
    "exercise_type",
    "instructions",
    "sets_min",
    "sets_max",
    "reps_min",
    "reps_max",
    "rest_seconds",
    "duration_minutes",
]

MULTI_VALUE_COLS = ["equipment", "location", "level", "secondary_muscles", "alternative_ids"]


def split_values(value: str) -> list[str]:
    """Split a semicolon-separated string into a cleaned list."""
    if pd.isna(value) or str(value).strip() == "":
        return []
    return [item.strip().lower() for item in str(value).split(";") if item.strip()]


def load_exercises(filepath: Path | str = EXERCISE_FILE) -> pd.DataFrame:
    """
    Load exercises from CSV, validate columns, and clean data.
    Returns a DataFrame with parsed multi-value columns as lists.
    Raises ValueError if required columns are missing.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Exercise file not found: {filepath}")

    df = pd.read_csv(filepath, dtype=str, encoding="utf-8")

    # Normalise column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Remove duplicates and rows without IDs or names
    df = df.drop_duplicates(subset=["exercise_id"])
    df = df.dropna(subset=["exercise_id", "exercise_name"])
    df = df.reset_index(drop=True)

    # Normalise text fields to lowercase
    for col in ["primary_muscles", "muscle_group", "movement_pattern",
                 "difficulty", "exercise_type", "muscle_emphasis"]:
        if col in df.columns:
            df[col] = df[col].str.strip().str.lower()

    # Parse numeric fields safely
    for col in ["sets_min", "sets_max", "reps_min", "reps_max",
                 "rest_seconds", "duration_minutes"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Parse multi-value columns into lists
    for col in MULTI_VALUE_COLS:
        if col in df.columns:
            df[col] = df[col].apply(split_values)

    # reviewed flag
    if "reviewed" in df.columns:
        df["reviewed"] = df["reviewed"].str.strip().str.lower().map(
            lambda v: v == "true"
        )
    else:
        df["reviewed"] = False

    return df
