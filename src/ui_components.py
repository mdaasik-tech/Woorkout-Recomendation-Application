"""Presentation helpers: CSS and HTML snippets. Pure functions, no Streamlit calls."""
from __future__ import annotations

import html
from typing import Dict

from .constants import (
    DEVELOPER_NAME,
    GITHUB_URL,
    LINKEDIN_URL,
    WEIGHT_LABELS,
    WEIGHTS,
)
from .data_loader import format_label

GITHUB_SVG = (
    '<svg viewBox="0 0 16 16" width="18" height="18" fill="currentColor" aria-hidden="true">'
    '<path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49'
    '-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82'
    '.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15'
    '-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82'
    '.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2'
    ' 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>'
)
LINKEDIN_SVG = (
    '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">'
    '<rect width="24" height="24" rx="4" fill="currentColor"/>'
    '<path fill="#0C1118" d="M6.94 9.5H4.2V19h2.74V9.5zM5.57 5a1.6 1.6 0 100 3.2 1.6 1.6 0 000-3.2zM19.8 13.7c0-2.5-1.33-4.4-3.55-4.4-1.2 0-2 .64-2.33 1.25V9.5h-2.64V19h2.74v-5.1c0-1.35.66-2.15 1.74-2.15 1.04 0 1.6.78 1.6 2.15V19h2.44v-5.3z"/>'
    "</svg>"
)

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@600;700&display=swap');
:root{
  --bg:#0C1118; --surface:#141C27; --surface2:#1B2533; --border:#263244;
  --text:#E6EBF2; --muted:#93A1B5; --accent:#F59E3F; --accent2:#3DD6C4;
  --warn:#F2C14E; --danger:#F26D6D;
}
html, body, [class*="css"], .stApp{font-family:'Barlow','Segoe UI',system-ui,sans-serif;}
h1,h2,h3,h4{font-family:'Barlow Condensed','Segoe UI',system-ui,sans-serif !important; letter-spacing:.2px;}
.block-container{padding-top:2rem; padding-bottom:3rem; max-width:1120px;}
[data-testid="stSidebar"]{background:var(--surface); border-right:1px solid var(--border);}
[data-testid="stSidebar"] .block-container{padding-top:1.5rem;}
.sb-brand{font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:1.5rem; line-height:1.1; color:var(--text);}
.sb-brand span{color:var(--accent);}
.sb-sub{color:var(--muted); font-size:.85rem; margin:.2rem 0 1rem;}

/* Buttons */
.stButton > button, .stDownloadButton > button{border-radius:10px; border:1px solid var(--border); font-weight:600;}
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"],
.stDownloadButton > button[kind="primary"]{background:var(--accent); color:#1A1205; border-color:var(--accent);}
.stButton > button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover{filter:brightness(1.08); color:#1A1205;}

/* Hero */
.hero{background:linear-gradient(135deg,#17212F 0%,#101823 60%,#1B2A2A 100%); border:1px solid var(--border);
  border-radius:18px; padding:2.6rem 2.4rem; margin-bottom:1.2rem;}
.hero h1{font-size:3.1rem; line-height:1.02; margin:0 0 .6rem; color:var(--text); font-weight:700;}
.hero p{color:var(--muted); font-size:1.1rem; max-width:640px; margin:0;}
.hero .tag{display:inline-block; color:var(--accent2); font-weight:600; margin-bottom:.8rem; font-size:.95rem;}

/* Feature / stat tiles */
.tile{background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.2rem; height:100%;}
.tile h4{margin:0 0 .35rem; font-size:1.25rem; color:var(--text);}
.tile p{margin:0; color:var(--muted); font-size:.95rem; line-height:1.45;}
.tile .ico{font-size:1.4rem; margin-bottom:.35rem;}
.stat{background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:.9rem 1.1rem;}
.stat b{display:block; font-family:'Barlow Condensed',sans-serif; font-size:2rem; color:var(--accent); line-height:1.1;}
.stat span{color:var(--muted); font-size:.9rem;}

/* Workout cards */
.wk-card{background:var(--surface); border:1px solid var(--border); border-left:4px solid var(--accent);
  border-radius:14px; padding:1.1rem 1.25rem; margin:.9rem 0 .35rem;}
.wk-card.alt{border-left-color:var(--accent2);}
.wk-head{display:flex; align-items:flex-start; gap:.85rem; flex-wrap:wrap;}
.wk-num{background:var(--surface2); color:var(--accent); font-family:'Barlow Condensed',sans-serif; font-weight:700;
  font-size:1.35rem; min-width:2.2rem; height:2.2rem; border-radius:10px; display:flex; align-items:center; justify-content:center;}
.wk-title{font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:1.55rem; color:var(--text); line-height:1.15;}
.wk-grow{flex:1 1 220px; min-width:0;}
.wk-score{text-align:right; color:var(--muted); font-size:.85rem; white-space:nowrap;}
.wk-score b{display:block; color:var(--accent2); font-family:'Barlow Condensed',sans-serif; font-size:1.5rem; line-height:1;}
.badge{display:inline-block; padding:.12rem .6rem; border-radius:999px; font-size:.78rem; font-weight:600;
  border:1px solid var(--border); background:var(--surface2); color:var(--text); margin:.3rem .3rem 0 0;}
.badge.low{color:#7BE0A4; border-color:#2B5B43;} .badge.moderate{color:var(--warn); border-color:#5C4D1E;}
.badge.high{color:var(--danger); border-color:#5E2B2B;} .badge.warn{color:var(--warn); border-color:#5C4D1E;}
.badge.teal{color:var(--accent2); border-color:#1F5A54;}
.wk-stats{display:grid; grid-template-columns:repeat(auto-fit,minmax(110px,1fr)); gap:.6rem; margin:.9rem 0;}
.wk-stats div{background:var(--surface2); border-radius:10px; padding:.55rem .8rem;}
.wk-stats b{display:block; font-family:'Barlow Condensed',sans-serif; font-size:1.35rem; color:var(--text);}
.wk-stats span{color:var(--muted); font-size:.82rem;}
.wk-meta{color:var(--muted); font-size:.92rem; margin-bottom:.7rem; line-height:1.5;}
.wk-meta b{color:var(--text); font-weight:600;}
.wk-cols{display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:1rem;}
.wk-cols h5{margin:0 0 .25rem; font-size:.95rem; color:var(--accent); font-weight:600;}
.wk-cols p{margin:0; color:var(--text); font-size:.95rem; line-height:1.5;}
.wk-note{margin-top:.8rem; padding:.55rem .8rem; border-radius:10px; background:#1E1B12; border:1px solid #4A3F1A;
  color:#E8D9A8; font-size:.88rem;}
.bars{display:grid; gap:.35rem; margin-top:.2rem;}
.bar-row{display:grid; grid-template-columns:210px 1fr 90px; gap:.6rem; align-items:center; font-size:.88rem; color:var(--muted);}
.bar{height:8px; border-radius:6px; background:var(--surface2); overflow:hidden;}
.bar i{display:block; height:100%; background:var(--accent2);}
.chip{display:inline-block; background:var(--surface2); border:1px solid var(--border); border-radius:999px;
  padding:.2rem .8rem; margin:.15rem .4rem .15rem 0; font-size:.9rem;}
.chip b{color:var(--accent);}

/* Footer and developer card */
.footer{margin-top:3rem; padding-top:1.1rem; border-top:1px solid var(--border); color:var(--muted);
  font-size:.88rem; display:flex; justify-content:space-between; flex-wrap:wrap; gap:.8rem; align-items:center;}
.footer .small{max-width:560px; line-height:1.45;}
.links{display:flex; gap:.6rem; flex-wrap:wrap;}
.links a{display:inline-flex; align-items:center; gap:.45rem; padding:.4rem .85rem; border-radius:10px;
  border:1px solid var(--border); background:var(--surface2); color:var(--text) !important; text-decoration:none !important;
  font-weight:600; font-size:.92rem;}
.links a:hover{border-color:var(--accent); color:var(--accent) !important;}
.dev{background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.3rem 1.4rem;}
.dev h3{margin:0 0 .15rem;}
.dev p{color:var(--muted); margin:.2rem 0 .9rem;}

@media (max-width: 700px){
  .hero{padding:1.6rem 1.2rem;} .hero h1{font-size:2.3rem;}
  .bar-row{grid-template-columns:1fr 70px;} .bar-row .bar{display:none;}
  .wk-score{text-align:left;}
}
"""


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def flatten(markup: str) -> str:
    """Remove indentation and blank lines so Markdown never treats HTML as code."""
    return "\n".join(line.strip() for line in markup.splitlines() if line.strip())


def badge(text: str, kind: str = "") -> str:
    return f'<span class="badge {kind}">{esc(text)}</span>'


def social_links_html() -> str:
    return flatten(f"""
    <div class="links">
      <a href="{GITHUB_URL}" target="_blank" rel="noopener noreferrer" aria-label="GitHub profile of {esc(DEVELOPER_NAME)}">{GITHUB_SVG} GitHub</a>
      <a href="{LINKEDIN_URL}" target="_blank" rel="noopener noreferrer" aria-label="LinkedIn profile of {esc(DEVELOPER_NAME)}">{LINKEDIN_SVG} LinkedIn</a>
    </div>
    """)


def footer_html() -> str:
    return flatten(f"""
    <div class="footer">
      <div class="small"><b>Built by {esc(DEVELOPER_NAME)}.</b> General exercise ideas only, not medical advice.
      The exercise dataset's review status is shown on the About page.</div>
      {social_links_html()}
    </div>
    """)


def developer_card_html() -> str:
    return flatten(f"""
    <div class="dev">
      <h3>{esc(DEVELOPER_NAME)}</h3>
      <p>Developer of the AI Workout Recommendation System, a rule-based fitness
      recommender built with Python, Pandas, NumPy and Streamlit.</p>
      {social_links_html()}
    </div>
    """)


def hero_html(n_exercises: int) -> str:
    return flatten(f"""
    <div class="hero">
      <div class="tag">Rule-based, transparent and built on {n_exercises} dataset exercises</div>
      <h1>Train with a plan that fits your goal, gear and time.</h1>
      <p>Tell us your goal, experience, equipment and available minutes. The app filters the
      exercise dataset, scores each option with visible weights and builds a balanced workout you can adjust and download.</p>
    </div>
    """)


def tile_html(icon: str, title: str, text: str) -> str:
    return flatten(f"""
    <div class="tile"><div class="ico">{icon}</div><h4>{esc(title)}</h4><p>{esc(text)}</p></div>
    """)


def stat_html(value, label: str) -> str:
    return f'<div class="stat"><b>{esc(value)}</b><span>{esc(label)}</span></div>'


def chips_html(counts: Dict[str, int]) -> str:
    return "".join(f'<span class="chip">{esc(format_label(g))} <b>{n}</b></span>' for g, n in counts.items())


def score_breakdown_html(item) -> str:
    rows = []
    for key, weight in WEIGHTS.items():
        value = float(item[key])
        rows.append(
            f'<div class="bar-row"><span>{esc(WEIGHT_LABELS[key])} (weight {weight * 100:.0f}%)</span>'
            f'<div class="bar"><i style="width:{value * 100:.0f}%"></i></div><span>{value * 100:.0f}% match</span></div>'
        )
    return '<div class="bars">' + "".join(rows) + "</div>"


def exercise_card_html(item, position: int, alt: bool = False, extra_badges: str = "", reason: str = "") -> str:
    """One exercise as a card. `item` is a prescription dict/row from workout_builder."""
    rest = f"{int(item['rest_seconds'])} s"
    reviewed_badge = "" if bool(item["reviewed"]) else badge("Dataset not reviewed", "warn")
    caution = str(item["caution_note"]).strip()
    note = f'<div class="wk-note"><b>Caution from dataset:</b> {esc(caution)}</div>' if caution else ""
    reason_html = f'<div class="wk-meta"><b>Why suggested:</b> {esc(reason)}</div>' if reason else ""
    return flatten(f"""
    <div class="wk-card{' alt' if alt else ''}">
      <div class="wk-head">
        <div class="wk-num">{position}</div>
        <div class="wk-grow">
          <div class="wk-title">{esc(item['exercise_name'])}</div>
          <div>
            {badge(format_label(item['muscle_group']), 'teal')}
            {badge(format_label(item['equipment']))}
            {badge('Difficulty: ' + format_label(item['difficulty']), str(item['difficulty']))}
            {badge(format_label(item['exercise_type']))}
            {extra_badges}{reviewed_badge}
          </div>
        </div>
        <div class="wk-score"><b>{float(item['score']):.0f}</b>match score</div>
      </div>
      <div class="wk-stats">
        <div><b>{int(item['sets'])} x {esc(item['reps'])}</b><span>Sets x reps</span></div>
        <div><b>{rest}</b><span>Rest between sets</span></div>
        <div><b>{float(item['est_minutes']):g} min</b><span>Estimated time</span></div>
      </div>
      <div class="wk-meta"><b>Primary muscles:</b> {esc(item['primary_muscles'])}<br>
      <b>Secondary muscles:</b> {esc(item['secondary_muscles'])}</div>
      {reason_html}
      <div class="wk-cols">
        <div><h5>Instructions</h5><p>{esc(item['instructions'])}</p></div>
        <div><h5>Common mistakes</h5><p>{esc(item['common_mistakes'])}</p></div>
      </div>
      {note}
    </div>
    """)
