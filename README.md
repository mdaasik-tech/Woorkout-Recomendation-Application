# AI Workout Recommendation System

A rule-based workout recommender built with **Python, Streamlit, Pandas and NumPy**.
It reads `exercises.csv` (122 exercises), filters and ranks them with transparent weights,
and builds a balanced workout that fits the user's time, equipment and goal.

> **Important - data review status:** the `reviewed` column in `exercises.csv` is `False` for every
> row. The exercise information has **not** been professionally verified. The app shows this clearly
> and keeps the flag in downloaded workouts. Have a qualified coach or physiotherapist review the data
> before any public or commercial use.

> **Safety:** this app gives general exercise ideas only. It does not diagnose injuries or medical
> conditions and makes no injury-prevention or muscle-growth guarantees. Consult a qualified
> professional if you have pain, an injury or a medical restriction.

## Features

- **Home** - landing page with a *Start workout* button
- **Create Workout** - goal, experience, target muscles, location, equipment, duration, intensity, exercises to avoid, areas to work around
- **Workout Results** - cards with muscles, equipment, difficulty, sets x reps, rest, estimated time, instructions, common mistakes and a score breakdown
- **Exercise Alternatives** - replace any exercise with a suitable alternative from the CSV
- **My Workout** - session checklist, progress bar and CSV download
- **About & Safety** - how scoring works, data review status, disclaimer and developer profile

## Install and run

Requires Python 3.9 or newer.

```bash
git clone <your-repo-url>
cd ai-workout-recommendation
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501.

## Run the tests

```bash
python -m unittest discover -s tests -v
```

The tests cover CSV loading and validation, every filter, scoring weights, workout building,
time limits, alternatives, replacements and CSV export.

## Project structure

```
ai-workout-recommendation/
├── app.py                  # Streamlit UI, navigation and session state
├── exercises.csv           # Single source of exercise data
├── requirements.txt
├── README.md
├── .streamlit/config.toml  # Dark theme
├── src/
│   ├── constants.py        # Options, weights, settings, WorkoutPreferences
│   ├── data_loader.py      # CSV loading, normalisation, review status
│   ├── validators.py       # Dataset and preference validation
│   ├── safety_filters.py   # Exclusions, caution-note filter, health-concern detection
│   ├── recommender.py      # Hard filters, weighted scoring, alternatives
│   ├── workout_builder.py  # Balanced, time-boxed workout, replacement, CSV export
│   └── ui_components.py    # CSS and HTML snippets
└── tests/test_recommender.py
```

## How recommendations work

1. **Filter** by target muscle, location, available equipment (bodyweight is always included) and experience level.
2. **Safety filters** remove exercises you chose to avoid (by name or keyword) and exercises whose dataset
   caution note mentions an area you want to work around. These run before ranking.
3. **Score** each remaining exercise from 0 to 100:

| Factor | Weight |
|---|---|
| Muscle match | 35% |
| Equipment match | 20% |
| Experience suitability | 20% |
| Fitness goal relevance | 15% |
| User preference (intensity) | 10% |

4. **Build** a balanced workout: time is shared between target muscles, compound and isolation work are
   mixed according to the goal, repeated movement patterns are avoided where possible, and the plan fits your
   duration minus a 5-minute warm-up reserve.
5. **No forced results:** if nothing suitable exists, or a muscle group has no suitable exercise, the app says so.

Sets, reps and rest come from the CSV ranges. Estimated time scales the CSV `duration_minutes` by the sets used.
The 5-minute warm-up reserve is an assumption of this app.

## Deploy on Streamlit Community Cloud

1. Push this folder to a public GitHub repository (keep `exercises.csv` in the repository root).
2. Go to https://share.streamlit.io and choose **New app**.
3. Select the repository and branch, and set the main file path to `app.py`.
4. Click **Deploy**. Dependencies are installed from `requirements.txt`.

## Developer

**Mohammed Aasik**

- GitHub: https://github.com/mdaasik-tech
- LinkedIn: https://www.linkedin.com/in/mohammed-aasik-257787433/
