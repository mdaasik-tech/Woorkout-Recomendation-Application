"""Shared constants and the user-preferences data class."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# --------------------------------------------------------------------------- #
# Developer profile (URLs must stay exactly as given)
# --------------------------------------------------------------------------- #
DEVELOPER_NAME = "Mohammed Aasik"
GITHUB_URL = "https://github.com/mdaasik-tech"
LINKEDIN_URL = "https://www.linkedin.com/in/mohammed-aasik-257787433/"

# --------------------------------------------------------------------------- #
# Option lists used by the form, the validators and the recommender
# --------------------------------------------------------------------------- #
GOALS = ["Muscle Gain", "Strength", "General Fitness", "Fat Loss"]
EXPERIENCE_LEVELS = ["Beginner", "Intermediate", "Advanced"]
INTENSITIES = ["Low", "Moderate", "High"]
DURATIONS = [30, 45, 60, 75, 90]
LOCATIONS = ["Gym", "Home"]

# Display label -> value used in the CSV `muscle_group` column
TARGET_MUSCLES = {
    "Chest": "chest",
    "Back": "back",
    "Shoulders": "shoulders",
    "Biceps": "biceps",
    "Triceps": "triceps",
    "Legs": "legs",
    "Core": "core",
}
# Sensible training order (large muscle groups first, core last)
GROUP_ORDER = ["legs", "back", "chest", "shoulders", "biceps", "triceps", "core"]

# Equipment: bodyweight is always available; everything else is user-selected.
BODYWEIGHT = "bodyweight"
DEFAULT_EQUIPMENT_OPTIONS = [
    "barbell",
    "cable_machine",
    "dumbbells",
    "machines",
    "pull_up_bar",
    "resistance_bands",
]
HOME_DEFAULT_EQUIPMENT = ["dumbbells", "resistance_bands", "pull_up_bar"]

# Areas a user can ask the app to work around. Keywords are matched against the
# CSV `contraindication_notes` column. This is NOT a diagnosis.
DISCOMFORT_AREAS = {
    "Shoulder": ["shoulder"],
    "Elbow": ["elbow"],
    "Wrist": ["wrist"],
    "Neck": ["neck"],
    "Lower back": ["lower back", "spinal", "hinging"],
    "Hip": ["hip"],
    "Knee": ["knee"],
}

# --------------------------------------------------------------------------- #
# Scoring weights (transparent, must sum to 1.0)
# --------------------------------------------------------------------------- #
WEIGHTS = {
    "muscle_match": 0.35,
    "equipment_match": 0.20,
    "experience_suitability": 0.20,
    "goal_relevance": 0.15,
    "user_preference": 0.10,
}
WEIGHT_LABELS = {
    "muscle_match": "Muscle match",
    "equipment_match": "Equipment match",
    "experience_suitability": "Experience suitability",
    "goal_relevance": "Fitness goal relevance",
    "user_preference": "User preference (intensity)",
}

# --------------------------------------------------------------------------- #
# Workout-builder settings
# --------------------------------------------------------------------------- #
WARMUP_RESERVE_MIN = 5      # minutes kept free for warm-up / transitions
MAX_PER_GROUP = 8           # max exercises per target muscle group
MAX_TOTAL_EXERCISES = 14    # max exercises in one workout


@dataclass
class WorkoutPreferences:
    """Everything the recommender needs to know about the user."""

    goal: str = "General Fitness"
    experience: str = "Beginner"
    targets: List[str] = field(default_factory=lambda: ["chest"])  # CSV values
    location: str = "Gym"
    equipment: List[str] = field(default_factory=list)  # excluding bodyweight
    duration: int = 60
    intensity: str = "Moderate"
    excluded_ids: List[str] = field(default_factory=list)
    excluded_terms: List[str] = field(default_factory=list)
    discomfort_areas: List[str] = field(default_factory=list)

    def copy_with(self, **changes) -> "WorkoutPreferences":
        data = {**self.__dict__, **changes}
        return WorkoutPreferences(**data)
