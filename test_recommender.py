"""Tests for CSV loading, filtering, scoring, building and alternatives.

Run with:  python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.constants import WEIGHTS, WorkoutPreferences  # noqa: E402
from src.data_loader import DataLoadError, data_status, load_exercises  # noqa: E402
from src.recommender import filter_candidates, find_alternatives, get_candidates  # noqa: E402
from src.safety_filters import detect_health_concern, parse_avoid_terms  # noqa: E402
from src.validators import validate_dataframe, validate_preferences, validate_weights  # noqa: E402
from src.workout_builder import build_workout, replace_exercise, to_csv_bytes  # noqa: E402

ALL_EQUIPMENT = ["barbell", "cable_machine", "dumbbells", "machines", "pull_up_bar", "resistance_bands"]


def prefs(**kw):
    base = dict(goal="Muscle Gain", experience="Intermediate", targets=["chest", "back", "legs"],
                location="Gym", equipment=ALL_EQUIPMENT, duration=60, intensity="Moderate")
    base.update(kw)
    return WorkoutPreferences(**base)


class TestDataLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_exercises()

    def test_loads_all_rows(self):
        self.assertEqual(len(self.df), 122)
        self.assertTrue(self.df["exercise_id"].is_unique)

    def test_missing_secondary_muscles_are_not_errors(self):
        empty = self.df["secondary_list"].apply(len) == 0
        self.assertEqual(int(empty.sum()), 13)
        self.assertTrue((self.df.loc[empty, "secondary_muscles"] == "").all())

    def test_reviewed_flag_preserved_and_reported(self):
        status = data_status(self.df)
        self.assertEqual(status["reviewed"], 0)
        self.assertTrue(status["none_reviewed"])
        self.assertFalse(self.df["reviewed"].any())

    def test_missing_file_raises_readable_error(self):
        with self.assertRaises(DataLoadError):
            load_exercises(ROOT / "does_not_exist.csv")

    def test_missing_required_column_is_rejected(self):
        raw = pd.read_csv(ROOT / "exercises.csv").drop(columns=["equipment"])
        self.assertFalse(validate_dataframe(raw).ok)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            raw.to_csv(path, index=False)
            with self.assertRaises(DataLoadError):
                load_exercises(path)

    def test_bad_values_are_rejected(self):
        raw = pd.read_csv(ROOT / "exercises.csv")
        raw.loc[0, "sets_min"] = 9  # greater than sets_max
        raw.loc[1, "exercise_id"] = raw.loc[2, "exercise_id"]  # duplicate id
        report = validate_dataframe(raw)
        self.assertFalse(report.ok)
        self.assertGreaterEqual(len(report.errors), 2)

    def test_alternative_ids_all_point_to_real_exercises(self):
        ids = set(self.df["exercise_id"])
        for alts in self.df["alt_list"]:
            self.assertTrue(set(alts) <= ids)


class TestScoringAndFilters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_exercises()

    def test_weights(self):
        self.assertTrue(validate_weights())
        self.assertEqual(WEIGHTS["muscle_match"], 0.35)
        self.assertEqual(WEIGHTS["equipment_match"], 0.20)
        self.assertEqual(WEIGHTS["experience_suitability"], 0.20)
        self.assertEqual(WEIGHTS["goal_relevance"], 0.15)
        self.assertEqual(WEIGHTS["user_preference"], 0.10)

    def test_scores_are_bounded_and_sorted(self):
        ranked, _ = get_candidates(self.df, prefs())
        self.assertFalse(ranked.empty)
        self.assertTrue(ranked["score"].between(0, 100).all())
        self.assertTrue(ranked["score"].is_monotonic_decreasing)

    def test_home_with_no_equipment_excludes_gym_only_and_gear(self):
        cand, _ = filter_candidates(self.df, prefs(location="Home", equipment=[]))
        self.assertFalse(cand.empty)
        self.assertTrue(cand["equipment"].eq("bodyweight").all())
        self.assertTrue(cand["location_list"].apply(lambda l: "home" in l).all())

    def test_equipment_filter(self):
        cand, _ = filter_candidates(self.df, prefs(equipment=["dumbbells"]))
        self.assertTrue(cand["equipment"].isin({"dumbbells", "bodyweight"}).all())

    def test_experience_filter(self):
        cand, _ = filter_candidates(self.df, prefs(experience="Beginner", targets=list(set(self.df.muscle_group))))
        self.assertTrue(cand["level_list"].apply(lambda l: "beginner" in l).all())

    def test_excluded_by_id_and_keyword(self):
        base, _ = filter_candidates(self.df, prefs(targets=["legs"]))
        some_id = base["exercise_id"].iloc[0]
        cand, _ = filter_candidates(self.df, prefs(targets=["legs"], excluded_ids=[some_id]))
        self.assertNotIn(some_id, set(cand["exercise_id"]))
        cand, _ = filter_candidates(self.df, prefs(targets=["legs"], excluded_terms=parse_avoid_terms("squat, LUNGE")))
        names = cand["exercise_name"].str.lower()
        self.assertFalse(names.str.contains("squat").any() or names.str.contains("lunge").any())

    def test_discomfort_area_removes_matching_caution_notes(self):
        cand, _ = filter_candidates(self.df, prefs(targets=["chest", "shoulders"], discomfort_areas=["Shoulder"]))
        self.assertFalse(cand["contraindication_notes"].str.lower().str.contains("shoulder").any())

    def test_health_concern_detection(self):
        self.assertTrue(detect_health_concern("I have knee pain"))
        self.assertTrue(detect_health_concern("", "recovering from surgery"))
        self.assertFalse(detect_health_concern("I like leg day"))

    def test_preference_validation(self):
        self.assertEqual(validate_preferences(prefs(), ALL_EQUIPMENT), [])
        self.assertTrue(validate_preferences(prefs(targets=[]), ALL_EQUIPMENT))
        self.assertTrue(validate_preferences(prefs(duration=50), ALL_EQUIPMENT))


class TestWorkoutBuilder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_exercises()

    def test_workout_fits_time_and_is_balanced(self):
        for duration in (30, 45, 60, 75, 90):
            p = prefs(duration=duration)
            result = build_workout(self.df, p)
            self.assertFalse(result.empty)
            self.assertLessEqual(result.total_minutes, duration - 5 + 1e-6)
            self.assertTrue(result.workout["exercise_id"].is_unique)
            self.assertEqual(set(result.workout["muscle_group"]), {"chest", "back", "legs"})

    def test_only_csv_exercises_and_ranges_respected(self):
        result = build_workout(self.df, prefs())
        merged = result.workout.merge(self.df, on="exercise_id", suffixes=("", "_csv"))
        self.assertEqual(len(merged), len(result.workout))
        self.assertTrue((merged["exercise_name"] == merged["exercise_name_csv"]).all())
        self.assertTrue(merged["sets"].between(merged["sets_min"], merged["sets_max"]).all())
        self.assertTrue((merged["rest_seconds"] == merged["rest_seconds_csv"]).all())

    def test_beginner_sets_are_capped(self):
        result = build_workout(self.df, prefs(experience="Beginner", intensity="High"))
        self.assertTrue((result.workout["sets"] <= 3).all())

    def test_no_forced_recommendations(self):
        every_id = list(self.df["exercise_id"])
        result = build_workout(self.df, prefs(excluded_ids=every_id))
        self.assertTrue(result.empty)
        self.assertTrue(result.warnings)

    def test_missing_group_is_reported_not_filled(self):
        # Home + no equipment has no bodyweight biceps exercise for a beginner after exclusion
        p = prefs(location="Home", equipment=[], targets=["chest", "biceps"], excluded_terms=["curl"])
        result = build_workout(self.df, p)
        self.assertFalse(result.empty)
        self.assertNotIn("biceps", set(result.workout["muscle_group"]))
        self.assertTrue(any("biceps" in w for w in result.warnings))

    def test_alternatives_are_suitable_and_replace_works(self):
        p = prefs()
        result = build_workout(self.df, p)
        wk = result.workout
        target = wk["exercise_id"].iloc[0]
        alts = find_alternatives(self.df, p, target, list(wk["exercise_id"]))
        self.assertFalse(alts.empty)
        group = self.df.loc[self.df.exercise_id == target, "muscle_group"].iloc[0]
        self.assertTrue((alts["muscle_group"] == group).all())
        self.assertNotIn(target, set(alts["exercise_id"]))
        self.assertTrue(alts["equipment"].isin(set(ALL_EQUIPMENT) | {"bodyweight"}).all())
        self.assertFalse(set(alts["exercise_id"]) & set(wk["exercise_id"]))
        # dataset-listed alternatives come first
        listed = set(self.df.loc[self.df.exercise_id == target, "alt_list"].iloc[0])
        sources = list(alts["alt_source"])
        if "Similar exercise" in sources and "Dataset alternative" in sources:
            self.assertLess(sources.index("Dataset alternative"), sources.index("Similar exercise"))
        new = alts.iloc[0]
        updated = replace_exercise(wk, target, new, p)
        self.assertNotIn(target, set(updated["exercise_id"]))
        self.assertIn(new["exercise_id"], set(updated["exercise_id"]))
        self.assertEqual(len(updated), len(wk))

    def test_csv_export(self):
        result = build_workout(self.df, prefs())
        text = to_csv_bytes(result.workout).decode("utf-8")
        frame = pd.read_csv(pd.io.common.StringIO(text))
        self.assertEqual(len(frame), len(result.workout))
        self.assertIn("Dataset reviewed", frame.columns)
        self.assertFalse(frame["Dataset reviewed"].any())
        for col in ("Exercise", "Sets", "Reps", "Rest (seconds)", "Instructions", "Common mistakes"):
            self.assertIn(col, frame.columns)


if __name__ == "__main__":
    unittest.main()
