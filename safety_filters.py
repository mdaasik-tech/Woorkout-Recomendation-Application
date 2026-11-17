"""Safety and exclusion filters. These run BEFORE any ranking.

Nothing here diagnoses an injury or a medical condition. The filters only
(a) remove exercises the user asked to avoid and (b) remove exercises whose
dataset caution note mentions a body area the user wants to work around.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

import pandas as pd

from .constants import DISCOMFORT_AREAS, WorkoutPreferences

SAFETY_DISCLAIMER = (
    "This app gives general exercise ideas only. It is not medical advice and "
    "does not diagnose, treat or prevent any injury or condition. Stop if you feel "
    "pain, dizziness or unusual discomfort, and speak to a qualified doctor, "
    "physiotherapist or certified trainer before starting if you have an injury, "
    "a medical condition or any doubts. No result, injury-prevention or "
    "muscle-growth outcome is guaranteed."
)

PROFESSIONAL_ADVICE = (
    "You mentioned pain, an injury or a medical restriction. Please consult a "
    "qualified professional (doctor, physiotherapist or certified trainer) before "
    "following any workout. This app cannot assess or diagnose your situation. "
    "The areas you select under 'Areas to work around' only remove exercises whose "
    "dataset caution note mentions that area, which does not make a workout safe."
)

# Words suggesting pain / injury / medical restriction in free text
_CONCERN_PATTERN = re.compile(
    r"\b(pain|painful|ache|aching|hurt|hurts|hurting|injur\w*|strain\w*|sprain\w*|"
    r"tear|torn|fracture\w*|surgery|surgical|operation|hernia|slipped disc|disc|"
    r"sciatica|arthritis|tendon\w*|dislocat\w*|concussion|dizz\w*|faint\w*|"
    r"pregnan\w*|blood pressure|hypertension|heart|asthma|diabet\w*|"
    r"medical|doctor|physio\w*|condition|chronic|rehab\w*)\b",
    re.IGNORECASE,
)
_NO_CAUTION = "no specific caution"


def detect_health_concern(*texts: str) -> bool:
    """True if any free-text field mentions pain, injury or a medical restriction."""
    return any(t and _CONCERN_PATTERN.search(t) for t in texts)


def parse_avoid_terms(text: str) -> List[str]:
    """'squat, lunge' -> ['squat', 'lunge'] (lower-cased, blanks removed)."""
    return [t.strip().lower() for t in re.split(r"[,;\n]", text or "") if t.strip()]


def exclusion_mask(df: pd.DataFrame, excluded_ids: List[str], terms: List[str]) -> pd.Series:
    """Rows the user explicitly wants to avoid (by id/name or by name keyword)."""
    mask = df["exercise_id"].isin(excluded_ids)
    names = df["exercise_name"].str.lower()
    for term in terms:
        mask |= names.str.contains(re.escape(term.lower()), regex=True, na=False)
    return mask


def caution_mask(df: pd.DataFrame, areas: List[str]) -> pd.Series:
    """Rows whose caution note mentions any selected body area."""
    notes = df["contraindication_notes"].str.lower()
    mask = pd.Series(False, index=df.index)
    for area in areas:
        for keyword in DISCOMFORT_AREAS.get(area, [area.lower()]):
            mask |= notes.str.contains(re.escape(keyword), regex=True, na=False)
    # A note saying "no specific caution" never counts as a mention
    return mask & ~notes.str.startswith(_NO_CAUTION)


def apply_safety_filters(df: pd.DataFrame, prefs: WorkoutPreferences) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Remove excluded and caution-flagged exercises.

    Returns the filtered frame and a dict with how many rows each rule removed.
    """
    removed = {"excluded_by_user": 0, "caution_note_match": 0}
    excl = exclusion_mask(df, prefs.excluded_ids, prefs.excluded_terms)
    removed["excluded_by_user"] = int(excl.sum())
    df = df[~excl]
    if prefs.discomfort_areas:
        caution = caution_mask(df, prefs.discomfort_areas)
        removed["caution_note_match"] = int(caution.sum())
        df = df[~caution]
    return df, removed
