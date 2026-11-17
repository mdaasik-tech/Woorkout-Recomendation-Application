"""
validators.py
Input validation for user preferences.
"""
from __future__ import annotations

VALID_GOALS = ["muscle_gain", "strength", "general_fitness", "fat_loss"]
VALID_LEVELS = ["beginner", "intermediate", "advanced"]
VALID_MUSCLE_GROUPS = ["chest", "back", "shoulders", "biceps", "triceps", "legs", "core"]
VALID_EQUIPMENT = [
    "bodyweight", "dumbbells", "barbell", "cable_machine",
    "resistance_bands", "machines", "pull_up_bar",
]
VALID_LOCATIONS = ["gym", "home"]
VALID_DURATIONS = [30, 45, 60, 75, 90]
VALID_INTENSITIES = ["low", "moderate", "high"]


class ValidationError(Exception):
    """Raised when user input fails validation."""


def validate_user_input(prefs: dict) -> list[str]:
    """
    Validate a user preferences dict.
    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    if prefs.get("goal") not in VALID_GOALS:
        errors.append(f"Invalid goal '{prefs.get('goal')}'. Choose from: {VALID_GOALS}")

    if prefs.get("level") not in VALID_LEVELS:
        errors.append(f"Invalid level '{prefs.get('level')}'. Choose from: {VALID_LEVELS}")

    if prefs.get("muscle_group") not in VALID_MUSCLE_GROUPS:
        errors.append(
            f"Invalid muscle group '{prefs.get('muscle_group')}'. "
            f"Choose from: {VALID_MUSCLE_GROUPS}"
        )

    equipment = prefs.get("equipment", [])
    if not isinstance(equipment, list) or len(equipment) == 0:
        errors.append("Please select at least one equipment option.")
    else:
        invalid_eq = [e for e in equipment if e not in VALID_EQUIPMENT]
        if invalid_eq:
            errors.append(f"Unknown equipment: {invalid_eq}")

    if prefs.get("location") not in VALID_LOCATIONS:
        errors.append(f"Invalid location '{prefs.get('location')}'. Choose from: {VALID_LOCATIONS}")

    if prefs.get("duration") not in VALID_DURATIONS:
        errors.append(f"Invalid duration. Choose from: {VALID_DURATIONS} minutes")

    if prefs.get("intensity") not in VALID_INTENSITIES:
        errors.append(f"Invalid intensity '{prefs.get('intensity')}'. Choose from: {VALID_INTENSITIES}")

    age = prefs.get("age")
    if age is not None:
        try:
            age_int = int(age)
            if not (10 <= age_int <= 120):
                errors.append("Age must be between 10 and 120.")
        except (ValueError, TypeError):
            errors.append("Age must be a whole number.")

    return errors

