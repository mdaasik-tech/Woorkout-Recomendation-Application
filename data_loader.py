"""CSV loading with validation, normalisation and safe handling of optional data."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from .constants import BODYWEIGHT, DEFAULT_EQUIPMENT_OPTIONS
from .validators import (
    NUMERIC_COLUMNS,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    validate_dataframe,
)

DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "exercises.csv"

_TEXT_DEFAULTS = {
    "secondary_muscles": "",
    "muscle_emphasis": "",
    "movement_pattern": "",
    "contraindication_notes": "",
    "alternative_ids": "",
    "source": "",
}


class DataLoadError(Exception):
    """Raised when the exercise CSV is missing, unreadable or invalid."""


def split_list(value) -> List[str]:
    """Split a ';'-separated cell into a clean list. Missing values -> []."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return []
    return [t.strip() for t in str(value).split(";") if t.strip()]


def format_label(text: str) -> str:
    """'front_delts' -> 'Front delts'."""
    text = str(text).replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else text


def format_list(items: List[str], empty: str = "None listed") -> str:
    return ", ".join(format_label(i) for i in items) if items else empty


def _parse_reviewed(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def load_exercises(path=DEFAULT_CSV_PATH) -> pd.DataFrame:
    """Load, validate and normalise the exercise dataset.

    Validation warnings (e.g. 'not reviewed') are kept in ``df.attrs['warnings']``.
    Raises DataLoadError with a readable message for any blocking problem.
    """
    path = Path(path)
    if not path.exists():
        raise DataLoadError(
            f"Exercise file not found: {path.name}. Place exercises.csv next to app.py."
        )
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        raise DataLoadError("The exercise file is empty.")
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DataLoadError(f"The exercise file could not be read: {exc}")

    report = validate_dataframe(raw)
    if not report.ok:
        raise DataLoadError(" ".join(report.errors))

    df = raw.copy()

    # Optional columns -> safe defaults (missing secondary muscles are NOT errors)
    for col, default in _TEXT_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].fillna(default).astype(str).str.strip()
    if "reviewed" not in df.columns:
        df["reviewed"] = False
    df["reviewed"] = _parse_reviewed(df["reviewed"])

    # Required text columns
    for col in ("exercise_id", "exercise_name", "instructions", "common_mistakes", "rep_unit"):
        df[col] = df[col].fillna("").astype(str).str.strip()
    for col in ("muscle_group", "equipment", "difficulty", "exercise_type"):
        df[col] = df[col].astype(str).str.strip().str.lower()
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col]).astype(int)
    df["rep_unit"] = df["rep_unit"].str.lower().replace("", "reps")

    # Parsed list columns
    df["primary_list"] = df["primary_muscles"].apply(split_list)
    df["secondary_list"] = df["secondary_muscles"].apply(split_list)
    df["level_list"] = df["level"].apply(lambda v: [t.lower() for t in split_list(v)])
    df["location_list"] = df["location"].apply(lambda v: [t.lower() for t in split_list(v)])
    df["alt_list"] = df["alternative_ids"].apply(split_list)

    df = df.reset_index(drop=True)
    df.attrs["warnings"] = report.warnings
    return df


def data_status(df: pd.DataFrame) -> Dict[str, object]:
    """Review status of the dataset, used to keep the UI honest."""
    total = int(len(df))
    reviewed = int(df["reviewed"].sum()) if total else 0
    return {
        "total": total,
        "reviewed": reviewed,
        "unreviewed": total - reviewed,
        "none_reviewed": reviewed == 0,
        "all_reviewed": total > 0 and reviewed == total,
        "sources": sorted({s for s in df["source"] if s}),
    }


def equipment_options(df: pd.DataFrame) -> List[str]:
    """Selectable equipment (bodyweight is always available, so it is excluded)."""
    found = sorted(set(df["equipment"]) - {BODYWEIGHT})
    return found or list(DEFAULT_EQUIPMENT_OPTIONS)
