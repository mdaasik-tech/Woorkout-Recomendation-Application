"""AI Workout Recommendation System - Streamlit app.

Run locally with:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.constants import (
    DISCOMFORT_AREAS,
    DURATIONS,
    EXPERIENCE_LEVELS,
    GOALS,
    HOME_DEFAULT_EQUIPMENT,
    INTENSITIES,
    LOCATIONS,
    TARGET_MUSCLES,
    WARMUP_RESERVE_MIN,
    WEIGHT_LABELS,
    WEIGHTS,
    WorkoutPreferences,
)
from src.data_loader import DataLoadError, data_status, equipment_options, format_label, load_exercises
from src.safety_filters import (
    PROFESSIONAL_ADVICE,
    SAFETY_DISCLAIMER,
    detect_health_concern,
    parse_avoid_terms,
)
from src.ui_components import (
    CSS,
    badge,
    chips_html,
    developer_card_html,
    exercise_card_html,
    flatten,
    footer_html,
    hero_html,
    score_breakdown_html,
    stat_html,
    tile_html,
)
from src.validators import validate_preferences
from src.workout_builder import (
    alternatives_for,
    build_workout,
    prescribe_item,
    replace_exercise,
    summarize,
    to_csv_bytes,
)

st.set_page_config(
    page_title="AI Workout Recommendation System",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

NAV_ITEMS = ["Home", "Create Workout", "Workout Results", "Exercise Alternatives", "My Workout", "About & Safety"]
NAV_ICONS = {
    "Home": "🏠",
    "Create Workout": "🛠️",
    "Workout Results": "📋",
    "Exercise Alternatives": "🔄",
    "My Workout": "✅",
    "About & Safety": "🛡️",
}


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def get_data() -> pd.DataFrame:
    return load_exercises()


try:
    DF = get_data()
except DataLoadError as exc:
    st.error(f"Could not load the exercise dataset: {exc}")
    st.stop()

STATUS = data_status(DF)
EQUIPMENT_OPTIONS = equipment_options(DF)
NAME_TO_ID = dict(zip(DF["exercise_name"], DF["exercise_id"]))
ALL_NAMES = sorted(NAME_TO_ID)


def default_equipment(location: str) -> list:
    if location == "Home":
        return [e for e in HOME_DEFAULT_EQUIPMENT if e in EQUIPMENT_OPTIONS]
    return list(EQUIPMENT_OPTIONS)


FORM_DEFAULTS = {
    "pref_goal": "General Fitness",
    "pref_experience": "Beginner",
    "pref_targets": ["Chest"],
    "pref_location": "Gym",
    "pref_equipment": default_equipment("Gym"),
    "pref_duration": 60,
    "pref_intensity": "Moderate",
    "pref_avoid_names": [],
    "pref_avoid_text": "",
    "pref_areas": [],
    "pref_notes": "",
}
APP_DEFAULTS = {
    "nav": "Home",
    "workout": None,
    "original_workout": None,
    "prefs": None,
    "build_warnings": [],
    "funnel": [],
    "health_concern": False,
    "done_ids": set(),
    "flash": "",
    "form_error": [],
    "empty_result": None,
    "alt_target": None,
}


def init_state() -> None:
    ss = st.session_state
    for key, value in {**APP_DEFAULTS, **FORM_DEFAULTS}.items():
        if key not in ss:
            ss[key] = value if not isinstance(value, (list, set)) else type(value)(value)
    # Keep form answers when the user switches pages (Streamlit drops the state
    # of widgets that are not drawn on the current page).
    for key in list(FORM_DEFAULTS) + ["alt_target"]:
        ss[key] = ss[key]


# --------------------------------------------------------------------------- #
# Callbacks (run before the next render, so they may change navigation state)
# --------------------------------------------------------------------------- #
def go(page: str) -> None:
    st.session_state.nav = page


def on_location_change() -> None:
    st.session_state.pref_equipment = default_equipment(st.session_state.pref_location)


def reset_form() -> None:
    for key, value in FORM_DEFAULTS.items():
        st.session_state[key] = list(value) if isinstance(value, list) else value
    st.session_state.form_error = []
    st.session_state.empty_result = None


def collect_preferences() -> WorkoutPreferences:
    ss = st.session_state
    return WorkoutPreferences(
        goal=ss.pref_goal,
        experience=ss.pref_experience,
        targets=[TARGET_MUSCLES[t] for t in ss.pref_targets if t in TARGET_MUSCLES],
        location=ss.pref_location,
        equipment=list(ss.pref_equipment),
        duration=int(ss.pref_duration),
        intensity=ss.pref_intensity,
        excluded_ids=[NAME_TO_ID[n] for n in ss.pref_avoid_names if n in NAME_TO_ID],
        excluded_terms=parse_avoid_terms(ss.pref_avoid_text),
        discomfort_areas=list(ss.pref_areas),
    )


def generate_workout() -> None:
    ss = st.session_state
    prefs = collect_preferences()
    problems = validate_preferences(prefs, EQUIPMENT_OPTIONS)
    if problems:
        ss.form_error = problems
        return
    ss.form_error = []
    result = build_workout(DF, prefs)
    ss.prefs = prefs
    ss.funnel = result.funnel
    ss.build_warnings = result.warnings
    ss.health_concern = detect_health_concern(ss.pref_notes, ss.pref_avoid_text)
    ss.flash = ""
    if result.empty:
        # Do not force a workout when nothing suitable exists.
        ss.empty_result = result
        ss.workout = None
        ss.original_workout = None
        return
    ss.empty_result = None
    ss.workout = result.workout
    ss.original_workout = result.workout.copy()
    ss.done_ids = set()
    ss.alt_target = result.workout["exercise_id"].iloc[0]
    ss.nav = "Workout Results"


def open_alternatives(exercise_id: str) -> None:
    st.session_state.alt_target = exercise_id
    st.session_state.nav = "Exercise Alternatives"


def replace_cb(old_id: str, new_id: str) -> None:
    ss = st.session_state
    options = alternatives_for(DF, ss.prefs, ss.workout, old_id, limit=50)
    match = options[options["exercise_id"] == new_id]
    if match.empty:
        ss.flash = "That alternative is no longer available."
        return
    old_name = ss.workout.loc[ss.workout["exercise_id"] == old_id, "exercise_name"].iloc[0]
    ss.workout = replace_exercise(ss.workout, old_id, match.iloc[0], ss.prefs)
    ss.done_ids.discard(old_id)
    ss.alt_target = new_id
    ss.flash = f"Replaced {old_name} with {match.iloc[0]['exercise_name']}."


def restore_original() -> None:
    ss = st.session_state
    if ss.original_workout is not None:
        ss.workout = ss.original_workout.copy()
        ss.done_ids = set()
        ss.alt_target = ss.workout["exercise_id"].iloc[0]
        ss.flash = "Restored the originally generated workout."


def clear_workout() -> None:
    ss = st.session_state
    ss.workout = None
    ss.original_workout = None
    ss.done_ids = set()
    ss.flash = ""


def toggle_done(exercise_id: str) -> None:
    ss = st.session_state
    if ss.get(f"done_{exercise_id}"):
        ss.done_ids.add(exercise_id)
    else:
        ss.done_ids.discard(exercise_id)


# --------------------------------------------------------------------------- #
# Shared UI pieces
# --------------------------------------------------------------------------- #
def html(markup: str) -> None:
    st.markdown(flatten(markup), unsafe_allow_html=True)


def page_footer() -> None:
    html(footer_html())


def review_notice() -> None:
    """Always be explicit about the review status of the exercise data."""
    if STATUS["none_reviewed"]:
        st.info(
            f"**Exercise data not reviewed.** None of the {STATUS['total']} exercises in the "
            "dataset are marked as professionally reviewed (the `reviewed` column is False for every row). "
            "Treat all exercise details as unverified and have a qualified coach check them."
        )
    elif not STATUS["all_reviewed"]:
        st.info(
            f"**Partly reviewed data.** {STATUS['unreviewed']} of {STATUS['total']} exercises are "
            "not marked as reviewed in the dataset."
        )


def safety_notice() -> None:
    st.caption("⚠️ " + SAFETY_DISCLAIMER)


def no_workout_state() -> None:
    st.info("You have not created a workout yet. Choose your preferences to get started.")
    st.button("Create a workout", type="primary", on_click=go, args=("Create Workout",), key="empty_cta")


def download_button(key: str) -> None:
    st.download_button(
        "Download workout (CSV)",
        data=to_csv_bytes(st.session_state.workout),
        file_name="my_workout.csv",
        mime="text/csv",
        key=key,
    )


def flash_message() -> None:
    if st.session_state.flash:
        st.success(st.session_state.flash)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def render_sidebar() -> None:
    with st.sidebar:
        html('<div class="sb-brand">AI Workout <span>Recommender</span></div>'
             '<div class="sb-sub">Rule-based plans from your exercise dataset</div>')
        st.radio(
            "Navigation",
            NAV_ITEMS,
            key="nav",
            format_func=lambda p: f"{NAV_ICONS[p]}  {p}",
            label_visibility="collapsed",
        )
        st.divider()
        if st.session_state.workout is not None:
            s = summarize(st.session_state.workout, st.session_state.prefs.duration)
            st.caption(f"Current workout: {s['exercises']} exercises, about {s['minutes']:g} min")
        else:
            st.caption("No workout created yet")
        st.caption(
            f"Dataset: {STATUS['total']} exercises, "
            + ("not reviewed" if STATUS["none_reviewed"] else f"{STATUS['reviewed']} marked reviewed")
        )
        st.caption("General exercise ideas only. Not medical advice.")


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def page_home() -> None:
    html(hero_html(STATUS["total"]))
    st.button("Start workout", type="primary", on_click=go, args=("Create Workout",), key="home_start")
    st.write("")

    cols = st.columns(4)
    tiles = [
        ("🎯", "Matched to you", "Goal, experience, muscles, location and equipment all shape the result."),
        ("⚖️", "Transparent scoring", "Five visible weights rank every exercise. No black box."),
        ("⏱️", "Fits your time", "Exercises are chosen to fit the duration you pick, with a warm-up reserve."),
        ("🔄", "Easy to adjust", "Swap any exercise for an alternative from the dataset and download the plan."),
    ]
    for col, (icon, title, text) in zip(cols, tiles):
        with col:
            html(tile_html(icon, title, text))

    st.write("")
    st.markdown("### How it works")
    steps = st.columns(4)
    flow = [
        ("1. Tell us about you", "Pick your goal, experience, target muscles, location, equipment and time."),
        ("2. Filter and rank", "Unsuitable exercises are removed first, then the rest are scored."),
        ("3. Build a balanced plan", "Compound and isolation work are mixed and fitted to your minutes."),
        ("4. Review and download", "Swap exercises, tick them off during your session and export a CSV."),
    ]
    for col, (title, text) in zip(steps, flow):
        with col:
            html(tile_html("", title, text))

    st.write("")
    s1, s2, s3 = st.columns(3)
    s1.markdown(stat_html(STATUS["total"], "exercises in the dataset"), unsafe_allow_html=True)
    s2.markdown(stat_html(DF["muscle_group"].nunique(), "muscle groups"), unsafe_allow_html=True)
    s3.markdown(stat_html(DF["equipment"].nunique(), "equipment types"), unsafe_allow_html=True)
    st.write("")
    review_notice()
    safety_notice()
    page_footer()


def page_create() -> None:
    ss = st.session_state
    st.markdown("## Create your workout")
    st.caption("Answer a few questions. Exercises come only from the project's exercises.csv.")

    for problem in ss.form_error:
        st.error(problem)

    if ss.empty_result is not None:
        st.warning(" ".join(ss.build_warnings))
        funnel = pd.DataFrame(ss.funnel, columns=["Step", "Exercises left"])
        st.markdown("**Where the options ran out**")
        st.dataframe(funnel, hide_index=True, use_container_width=True)

    with st.container(border=True):
        st.markdown("#### Goal and experience")
        c1, c2 = st.columns(2)
        c1.selectbox("Fitness goal", GOALS, key="pref_goal")
        c2.selectbox("Experience level", EXPERIENCE_LEVELS, key="pref_experience")

    with st.container(border=True):
        st.markdown("#### Target muscles and place")
        st.multiselect("Target muscles", list(TARGET_MUSCLES), key="pref_targets",
                       help="Pick one or more. Time is shared between the muscles you choose.")
        st.radio("Workout location", LOCATIONS, key="pref_location", horizontal=True,
                 on_change=on_location_change)
        st.multiselect(
            "Available equipment",
            EQUIPMENT_OPTIONS,
            key="pref_equipment",
            format_func=format_label,
            help="Bodyweight exercises are always included.",
        )
        st.caption("Bodyweight exercises are always included. Changing the location resets the equipment suggestion.")

    with st.container(border=True):
        st.markdown("#### Time and intensity")
        c1, c2 = st.columns(2)
        with c1:
            st.select_slider("Workout duration", options=DURATIONS, key="pref_duration",
                             format_func=lambda m: f"{m} min")
            st.caption(f"{WARMUP_RESERVE_MIN} minutes are kept free for warm-up and transitions.")
        with c2:
            st.radio("Preferred intensity", INTENSITIES, key="pref_intensity", horizontal=True,
                     help="Sets how many sets are used and which difficulty ranks higher.")

    with st.container(border=True):
        st.markdown("#### Exclusions and safety")
        st.multiselect("Exercises to avoid", ALL_NAMES, key="pref_avoid_names",
                       help="These exercises will never be recommended.")
        st.text_input("Or avoid by keyword (comma separated)", key="pref_avoid_text",
                      placeholder="e.g. squat, lunge",
                      help="Removes every exercise whose name contains the keyword.")
        st.multiselect("Areas to work around (optional)", list(DISCOMFORT_AREAS), key="pref_areas",
                       help="Removes exercises whose dataset caution note mentions the area.")
        st.text_area("Anything else we should know? (optional)", key="pref_notes", height=80,
                     placeholder="e.g. current pain, an injury or a medical restriction")
        st.caption(
            "If you have pain, an injury or a medical restriction, speak to a qualified professional "
            "first. This app cannot diagnose or assess it."
        )

    b1, b2 = st.columns([3, 1])
    b1.button("Generate my workout", type="primary", use_container_width=True,
              on_click=generate_workout, key="generate_btn")
    b2.button("Reset selections", use_container_width=True, on_click=reset_form, key="reset_btn")
    page_footer()


def page_results() -> None:
    ss = st.session_state
    st.markdown("## Your workout")
    if ss.workout is None:
        no_workout_state()
        page_footer()
        return

    prefs: WorkoutPreferences = ss.prefs
    ws: pd.DataFrame = ss.workout
    s = summarize(ws, prefs.duration)
    available = max(prefs.duration - WARMUP_RESERVE_MIN, 1)

    st.caption(
        f"{prefs.goal} | {prefs.experience} | {prefs.location} | {prefs.intensity} intensity | "
        f"Target: {', '.join(format_label(t) for t in prefs.targets)}"
    )
    flash_message()
    if ss.health_concern:
        st.warning(PROFESSIONAL_ADVICE)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Exercises", s["exercises"])
    m2.metric("Total sets", s["total_sets"])
    m3.metric("Estimated time", f"{s['minutes']:g} min")
    m4.metric("Chosen duration", f"{prefs.duration} min")
    st.progress(min(s["minutes"] / available, 1.0),
                text=f"{s['minutes']:g} of {available} available minutes planned "
                     f"({WARMUP_RESERVE_MIN} min reserved for warm-up)")
    html(f'<div>{chips_html(s["groups"])}</div>')
    if s["minutes"] > available:
        st.warning("After swaps, the estimated time is above your chosen duration.")
    for w in ss.build_warnings:
        st.warning(w)
    review_notice()

    st.write("")
    download_button("download_results")

    for _, row in ws.iterrows():
        html(exercise_card_html(row, int(row["order"])))
        with st.expander("Why was this recommended?"):
            st.markdown(f"Overall match score: **{row['score']:.0f} / 100**")
            html(score_breakdown_html(row))
            st.caption("Scores are rule-based estimates from the dataset, not a measure of results.")
        st.button("Find alternatives", key=f"alt_btn_{row['exercise_id']}",
                  on_click=open_alternatives, args=(row["exercise_id"],))
    safety_notice()
    page_footer()


def page_alternatives() -> None:
    ss = st.session_state
    st.markdown("## Exercise alternatives")
    if ss.workout is None:
        no_workout_state()
        page_footer()
        return

    ws: pd.DataFrame = ss.workout
    prefs: WorkoutPreferences = ss.prefs
    ids = list(ws["exercise_id"])
    labels = {r["exercise_id"]: f"{int(r['order'])}. {r['exercise_name']} ({format_label(r['muscle_group'])})"
              for _, r in ws.iterrows()}
    if ss.alt_target not in ids:
        ss.alt_target = ids[0]

    st.caption("Alternatives respect your equipment, location, experience level, exclusions and safety filters.")
    flash_message()
    st.selectbox("Exercise to replace", ids, key="alt_target", format_func=lambda i: labels[i])

    current = ws[ws["exercise_id"] == ss.alt_target].iloc[0]
    st.markdown("**Current exercise**")
    html(exercise_card_html(current, int(current["order"])))

    alts = alternatives_for(DF, prefs, ws, ss.alt_target, limit=6)
    st.markdown("### Suitable alternatives")
    if alts.empty:
        st.warning(
            "No other suitable exercises were found in the dataset for this muscle group with your "
            "current filters, so nothing is suggested. Try changing equipment, location or exclusions."
        )
    else:
        for n, (_, row) in enumerate(alts.iterrows(), start=1):
            item = prescribe_item(row, prefs)
            src_badge = badge(row["alt_source"], "teal")
            html(exercise_card_html(item, n, alt=True, extra_badges=src_badge, reason=row["reason"]))
            st.button(f"Replace with {row['exercise_name']}", key=f"rep_{ss.alt_target}_{row['exercise_id']}",
                      type="primary", on_click=replace_cb, args=(ss.alt_target, row["exercise_id"]))

    st.write("")
    st.button("Restore original workout", on_click=restore_original, key="restore_btn",
              disabled=ss.original_workout is None)
    page_footer()


def page_my_workout() -> None:
    ss = st.session_state
    st.markdown("## My workout")
    if ss.workout is None:
        no_workout_state()
        page_footer()
        return

    ws: pd.DataFrame = ss.workout
    prefs: WorkoutPreferences = ss.prefs
    s = summarize(ws, prefs.duration)
    st.caption("Your workout lives in this browser session. Download the CSV to keep it.")
    flash_message()
    if ss.health_concern:
        st.warning(PROFESSIONAL_ADVICE)

    done = len([i for i in ws["exercise_id"] if i in ss.done_ids])
    st.progress(done / s["exercises"], text=f"{done} of {s['exercises']} exercises completed")

    table = pd.DataFrame({
        "#": ws["order"],
        "Exercise": ws["exercise_name"],
        "Muscle": ws["muscle_group"].map(format_label),
        "Equipment": ws["equipment"].map(format_label),
        "Sets x reps": ws["sets"].astype(str) + " x " + ws["reps"],
        "Rest": ws["rest_seconds"].astype(str) + " s",
        "Est. minutes": ws["est_minutes"],
    })
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.caption(f"Total estimated time: {s['minutes']:g} min (chosen duration: {prefs.duration} min).")

    st.markdown("#### Session checklist")
    for _, row in ws.iterrows():
        label = f"{int(row['order'])}. {row['exercise_name']}: {row['sets']} x {row['reps']}, rest {row['rest_seconds']} s"
        st.checkbox(label, value=row["exercise_id"] in ss.done_ids, key=f"done_{row['exercise_id']}",
                    on_change=toggle_done, args=(row["exercise_id"],))

    review_notice()
    c1, c2, c3 = st.columns(3)
    with c1:
        download_button("download_my")
    c2.button("Create a new workout", on_click=go, args=("Create Workout",), key="new_btn")
    c3.button("Clear workout", on_click=clear_workout, key="clear_btn")
    safety_notice()
    page_footer()


def page_about() -> None:
    st.markdown("## About and safety")

    st.markdown("### How the recommendations work")
    st.markdown(
        "The app uses plain Python and Pandas rules. No machine learning is involved. "
        "Every step is visible and repeatable:"
    )
    st.markdown(
        "1. **Filter first.** Exercises are removed if they do not match the target muscle, location, "
        "available equipment or experience level, or if you asked to avoid them or to work around an area.\n"
        "2. **Score the rest.** Each remaining exercise gets a 0 to 100 score from the weights below.\n"
        "3. **Build a balanced plan.** Time is shared between your target muscles. The builder mixes compound "
        "and isolation exercises, avoids repeating the same movement where possible and fits the exercises "
        "to your duration.\n"
        "4. **Never force a result.** If nothing suitable exists, the app says so instead of filling the plan."
    )
    weights = pd.DataFrame({
        "Factor": [WEIGHT_LABELS[k] for k in WEIGHTS],
        "Weight": [f"{w * 100:.0f}%" for w in WEIGHTS.values()],
    })
    st.table(weights)
    st.markdown(
        "- **Muscle match:** the exercise must be for a selected muscle group. The score also rewards exercises that involve more secondary muscles.\n"
        "- **Equipment match:** equipment you selected scores highest. Bodyweight is always assumed available and scores slightly lower unless it is all you have.\n"
        "- **Experience suitability:** how specifically the exercise is listed for your level, and how well its difficulty fits that level.\n"
        "- **Fitness goal relevance:** rule-based fit between the exercise type, rep range and rest time and your goal.\n"
        "- **User preference:** how closely the exercise difficulty matches your preferred intensity."
    )
    st.markdown(
        "**Sets, reps, rest and time** come from the dataset. Sets and reps are chosen inside each exercise's "
        "listed range using your goal, experience and intensity. Rest time is the dataset value. Estimated time scales the "
        "dataset's `duration_minutes` by the number of sets used. "
        f"A {WARMUP_RESERVE_MIN}-minute reserve for warm-up is an assumption of this app."
    )

    st.markdown("### Exercise data")
    if STATUS["none_reviewed"]:
        st.warning(
            f"All {STATUS['total']} exercises are marked `reviewed = False`. The information has **not** been "
            "professionally verified. Instructions, common mistakes, set and rep ranges and caution notes "
            "need review by a qualified coach or physiotherapist before public use."
        )
    elif STATUS["all_reviewed"]:
        st.info("The CSV marks every exercise as reviewed, but this app cannot confirm who reviewed it or how.")
    else:
        st.warning(f"{STATUS['unreviewed']} of {STATUS['total']} exercises are not marked as reviewed.")
    for src in STATUS["sources"]:
        st.caption(f"Dataset source note: {src}")

    st.markdown("### Safety and disclaimer")
    st.warning(SAFETY_DISCLAIMER)
    st.markdown(
        "- The app does not diagnose injuries or medical conditions.\n"
        "- If you report pain, an injury or a medical restriction, consult a qualified professional first.\n"
        "- Exercises you choose to avoid are always excluded.\n"
        "- Caution notes come from the dataset and may be incomplete. Stop any exercise that causes pain.\n"
        "- Estimates and scores describe how well an exercise matches your inputs, not how well it will work for you."
    )

    st.markdown("### Developer")
    html(developer_card_html())
    page_footer()


PAGES = {
    "Home": page_home,
    "Create Workout": page_create,
    "Workout Results": page_results,
    "Exercise Alternatives": page_alternatives,
    "My Workout": page_my_workout,
    "About & Safety": page_about,
}


def main() -> None:
    init_state()
    st.markdown(f"<style>{flatten(CSS)}</style>", unsafe_allow_html=True)
    render_sidebar()
    PAGES[st.session_state.nav]()


main()
