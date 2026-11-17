
"""
data_loader.py
Loads and validates the exercises.csv dataset.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


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

MULTI_VALUE_COLS = [
    "equipment",
    "location",
    "level",
    "secondary_muscles",
    "alternative_ids",
]


class DataLoadError(Exception):
    """Raised when the exercise dataset cannot be loaded."""


def split_values(value) -> list[str]:
    """Split semicolon-separated values into a cleaned list."""
    if pd.isna(value) or str(value).strip() == "":
        return []

    return [
        item.strip().lower()
        for item in str(value).split(";")
        if item.strip()
    ]


def format_label(value: str) -> str:
    """Convert a dataset value into a readable label."""
    if not isinstance(value, str):
        return str(value)

    return value.replace("_", " ").strip().title()


def load_exercises(
    filepath: Path | str = EXERCISE_FILE
) -> pd.DataFrame:
    """Load, validate and clean the exercise dataset."""

    filepath = Path(filepath)

    try:
        if not filepath.exists():
            raise DataLoadError(
                f"Exercise file not found: {filepath}"
            )

        df = pd.read_csv(
            filepath,
            dtype=str,
            encoding="utf-8"
        )

        df.columns = [
            c.strip().lower().replace(" ", "_")
            for c in df.columns
        ]

        missing = [
            col for col in REQUIRED_COLUMNS
            if col not in df.columns
        ]

        if missing:
            raise DataLoadError(
                f"Missing required columns: {missing}"
            )

        df = df.drop_duplicates(subset=["exercise_id"])
        df = df.dropna(
            subset=["exercise_id", "exercise_name"]
        )
        df = df.reset_index(drop=True)

        text_columns = [
            "primary_muscles",
            "muscle_group",
            "movement_pattern",
            "difficulty",
            "exercise_type",
            "muscle_emphasis",
        ]

        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].fillna("").str.strip().str.lower()

        numeric_columns = [
            "sets_min",
            "sets_max",
            "reps_min",
            "reps_max",
            "rest_seconds",
            "duration_minutes",
        ]

        for col in numeric_columns:
            df[col] = (
                pd.to_numeric(df[col], errors="coerce")
                .fillna(0)
                .astype(int)
            )

        for col in MULTI_VALUE_COLS:
            if col in df.columns:
                df[col] = df[col].apply(split_values)

        if "reviewed" in df.columns:
            df["reviewed"] = (
                df["reviewed"]
                .fillna("")
                .str.strip()
                .str.lower()
                .eq("true")
            )
        else:
            df["reviewed"] = False

        return df

    except DataLoadError:
        raise

    except Exception as exc:
        raise DataLoadError(
            f"Unable to load exercise dataset: {exc}"
        ) from exc


def data_status(df: pd.DataFrame) -> dict:
    """Return dataset statistics and review information."""

    total = len(df)

    reviewed_count = (
        int(df["reviewed"].sum())
        if "reviewed" in df.columns
        else 0
    )

    sources = []

    if "source" in df.columns:
        sources = sorted({
            str(value).strip()
            for value in df["source"].dropna()
            if str(value).strip()
        })

    return {
        "total": total,
        "reviewed": reviewed_count,
        "unreviewed": total - reviewed_count,
        "none_reviewed": reviewed_count == 0,
        "all_reviewed": total > 0 and reviewed_count == total,
        "sources": sources,
    }


def equipment_options(df: pd.DataFrame) -> list[str]:
    """Return unique equipment options from the dataset."""

    equipment_set = set()

    if "equipment" not in df.columns:
        return []

    for items in df["equipment"]:
        if isinstance(items, list):
            equipment_set.update(items)
        elif isinstance(items, str):
            equipment_set.update(split_values(items))

    return sorted(equipment_set)
