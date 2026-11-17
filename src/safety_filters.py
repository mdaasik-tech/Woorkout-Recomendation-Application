
"""
safety_filters.py
Apply safety exclusions and health-related filters before ranking.
"""
from __future__ import annotations

import pandas as pd


def apply_safety_exclusions(
    df: pd.DataFrame,
    avoided_names: list[str],
    has_current_pain: bool,
    has_injury: bool,
    has_medical_restriction: bool,
    avoided_movements: list[str] | None = None,
) -> pd.DataFrame:
    """
    Remove exercises that the user has explicitly excluded or that are
    contraindicated given reported pain / injury / medical restrictions.

    Parameters
    ----------
    df : DataFrame of exercises (all columns).
    avoided_names : list of exercise names or IDs to exclude.
    has_current_pain : user reported current pain.
    has_injury : user reported a relevant past injury.
    has_medical_restriction : user reported a medical restriction.
    avoided_movements : optional list of movement_pattern strings to skip.

    Returns
    -------
    Filtered DataFrame.
    """
    result = df.copy()

    # Exclude exercises explicitly named or ID'd by the user
    if avoided_names:
        avoided_lower = [a.strip().lower() for a in avoided_names if a.strip()]
        name_mask = result["exercise_name"].str.lower().isin(avoided_lower)
        id_mask = result["exercise_id"].str.lower().isin(avoided_lower)
        result = result[~(name_mask | id_mask)]

    # Exclude avoided movement patterns
    if avoided_movements:
        avoided_mv_lower = [m.strip().lower() for m in avoided_movements if m.strip()]
        if avoided_mv_lower and "movement_pattern" in result.columns:
            mv_mask = result["movement_pattern"].str.lower().isin(avoided_mv_lower)
            result = result[~mv_mask]

    # If user reports current pain, injury, or medical restriction:
    # exclude exercises where the contraindication_notes mention caution keywords
    if has_current_pain or has_injury or has_medical_restriction:
        caution_keywords = [
            "avoid with current",
            "consult a professional",
            "not suitable if",
            "not suitable with",
        ]
        if "contraindication_notes" in result.columns:
            def is_high_risk(notes: str) -> bool:
                if pd.isna(notes) or str(notes).strip() == "":
                    return False
                notes_lower = str(notes).lower()
                return any(kw in notes_lower for kw in caution_keywords)

            result = result[~result["contraindication_notes"].apply(is_high_risk)]

    return result.reset_index(drop=True)
