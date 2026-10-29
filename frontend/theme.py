"""
Visual theme for the Streamlit app: a warm "central bank ledger" look —
parchment surfaces, gold accents, serif headings, a guilloché background
and a slowly turning ₹ coin behind the chat. Pure presentation; app.py
calls apply_theme() once per run and the widgets keep working as before.
"""

import math
from urllib.parse import quote

import streamlit as st

PALETTES = {
    "light": {
        "bg": "#FBF6EC", "surface": "#F5EDDC", "surface-2": "#EFE3C8",
        "gold": "#B8860B", "gold-bright": "#C9972B", "gold-soft": "rgba(201,151,43,.16)",
        "ink": "#2B2114", "ink-soft": "#6B5A40", "line": "rgba(184,134,11,.32)",
        "card": "#FFFCF5", "shadow": "rgba(92,64,18,.10)", "pattern": "#B8860B",
        "pattern-opacity": ".16", "coin-opacity": ".14",
    },
    "dark": {
        "bg": "#17120B", "surface": "#211A10", "surface-2": "#2C2316",
        "gold": "#D4A73C", "gold-bright": "#E6BC5C", "gold-soft": "rgba(212,167,60,.14)",
        "ink": "#F3E9D2", "ink-soft": "#B9A782", "line": "rgba(212,167,60,.30)",
        "card": "#1D170E", "shadow": "rgba(0,0,0,.45)", "pattern": "#D4A73C",
        "pattern-opacity": ".10", "coin-opacity": ".11",
    },
}


def guilloche_svg(color: str, opacity: float) -> str:
    """A tile of phase-shifted sine waves spanning its full height, which
    weave into the fine mesh engraved on banknotes."""
    w, h = 180, 90
    paths = []
    for k in range(9):
        phase = 2 * math.pi * k / 9
        pts = " ".join(f"{x},{h / 2 + (h / 2 - 3) * math.sin(2 * math.pi * x / w + phase):.1f}"
                       for x in range(0, w + 1, 3))
        paths.append(f'<polyline points="{pts}" fill="none" stroke="{color}" '
                     f'stroke-opacity="{opacity}" stroke-width=".7"/>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">{"".join(paths)}</svg>'
    return f"url(\"data:image/svg+xml,{quote(svg)}\")"


# Back face of the coin: a pillared bank-front emblem
EMBLEM_SVG = """<svg viewBox="0 0 64 64" width="46%" fill="none" stroke="currentColor" stroke-width="2.2"
 stroke-linejoin="round"><path d="M8 24 32 10l24 14z"/><path d="M10 26h44M12 50h40M8 55h48"/>
<path d="M17 30v17M27 30v17M37 30v17M47 30v17"/></svg>"""

COIN_HTML = f"""
<div class="coin-stage" aria-hidden="true"><div class="coin">
  {''.join(f'<div class="coin-edge" style="transform: translateZ({z}px)"></div>' for z in range(-7, 7))}
  <div class="coin-face coin-front"><span class="coin-ring"></span><span class="coin-glyph">₹</span>
    </div>
  <div class="coin-face coin-back"><span class="coin-ring"></span>{EMBLEM_SVG}</div>
</div></div>
"""


def css(p: dict) -> str:
    v = "\n".join(f"  --{k}: {val};" for k, val in p.items())
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
:root, .stApp {{
{v}
  --serif: 'EB Garamond', Georgia, 'Times New Roman', serif;
  --sans: 'Inter', system-ui, -apple-system, sans-serif;
  --thread: repeating-linear-gradient(90deg, var(--gold) 0 14px, transparent 14px 20px);
}}

/* ---------- canvas: parchment, guilloché, ledger lines ---------- */
.stApp {{
  isolation: isolate;
  background-color: var(--bg);
  background-image:
    repeating-linear-gradient(0deg, transparent 0 31px, var(--gold-soft) 31px 32px),
    {guilloche_svg(p['pattern'], float(p['pattern-opacity']))};
  background-blend-mode: normal;
  color: var(--ink);
  font-family: var(--sans);
}}
.stApp::before {{   /* soften the engraving behind the reading column */
  content: ""; position: fixed; inset: 0; z-index: -2; pointer-events: none;
  background: radial-gradient(ellipse 60% 70% at 50% 45%, var(--bg) 0%, transparent 80%);
  opacity: .75;
}}
[data-testid="stHeader"], [data-testid="stBottom"] > div {{ background: transparent; }}
[data-testid="stBottom"] {{ background: linear-gradient(to top, var(--bg) 60%, transparent); }}
[data-testid="stDecoration"] {{ background: var(--thread); height: 3px; opacity: .8; }}
.block-container {{ max-width: 1080px; padding-top: 2.2rem; padding-bottom: 7rem; }}

/* ---------- type ---------- */
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button {{
  font-family: var(--sans); color: var(--ink);
}}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {{
  font-family: var(--serif); color: var(--ink); letter-spacing: .01em;
}}
.stApp [data-testid="stCaptionContainer"], .stApp small {{ color: var(--ink-soft); }}
.stApp a {{ color: var(--gold); }}
.stApp strong {{ color: var(--ink); }}
::selection {{ background: var(--gold-soft); }}

/* ---------- hero ---------- */
.hero {{ position: relative; padding: .2rem 0 1.1rem; margin-bottom: 1.2rem; }}
.hero-kicker {{ font: 600 .72rem var(--sans); letter-spacing: .22em; text-transform: uppercase;
  color: var(--gold); display: flex; align-items: center; gap: .55rem; }}
.hero-kicker svg {{ width: 18px; height: 18px; }}
.hero h1 {{ font: 700 2.9rem/1.05 var(--serif); margin: .35rem 0 .55rem; padding: 0; }}
.hero h1 .rupee {{ color: var(--gold); font-weight: 600; margin-right: .18em; }}
.hero p {{ font-size: 1.02rem; line-height: 1.6; color: var(--ink-soft); max-width: 46rem; margin: 0; }}
.hero p b {{ color: var(--ink); font-weight: 600; }}
.thread {{ height: 4px; margin: 1.1rem 0 .55rem; border-radius: 2px;
  background: var(--thread), linear-gradient(90deg, var(--gold-soft), var(--gold-soft));
  background-size: 100% 2px, 100% 4px; background-repeat: no-repeat; background-position: center; }}
.disclaimer {{ font-size: .78rem; color: var(--ink-soft); }}

/* ---------- section labels with icons ---------- */
.label {{ display: flex; align-items: center; gap: .5rem; margin: 0 0 .55rem;
  font: 600 1.12rem var(--serif); color: var(--ink); }}
.label svg {{ width: 17px; height: 17px; color: var(--gold); flex: none; }}

/* ---------- buttons: example chips and sidebar ---------- */
.stApp [data-testid="stBaseButton-secondary"] {{
  background: var(--card); color: var(--ink); border: 1px solid var(--line);
  border-radius: 12px; box-shadow: 0 1px 0 var(--shadow);
  transition: border-color .2s, box-shadow .2s, transform .2s;
}}
.stApp [data-testid="stBaseButton-secondary"]:hover {{
  border-color: var(--gold-bright); color: var(--ink); transform: translateY(-1px);
  box-shadow: 0 0 0 3px var(--gold-soft), 0 6px 18px var(--shadow);
}}
.stApp [data-testid="stBaseButton-secondary"]:focus:not(:active) {{ border-color: var(--gold); color: var(--ink); }}
.stApp [data-testid="stBaseButton-secondary"] p {{ font-size: .88rem; line-height: 1.4; }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{ background: var(--surface); border-right: 1px solid var(--line); }}
[data-testid="stSidebar"]::after {{ content: ""; position: absolute; top: 0; right: 0; bottom: 0;
  width: 2px; background: repeating-linear-gradient(180deg, var(--gold) 0 14px, transparent 14px 20px); opacity: .55; }}
.side-brand {{ font: 700 1.35rem var(--serif); display: flex; align-items: center; gap: .5rem; margin-bottom: .2rem; }}
.side-brand span {{ color: var(--gold); }}
.side-brand svg {{ width: 24px; height: 24px; color: var(--gold); flex: none; }}
.side-sub {{ font-size: .78rem; color: var(--ink-soft); margin-bottom: .4rem; }}
.doc-item {{ display: flex; gap: .6rem; padding: .55rem 0; border-top: 1px dashed var(--line); }}
.doc-item:first-of-type {{ border-top: 0; padding-top: .1rem; }}
.doc-item svg {{ width: 18px; height: 18px; color: var(--gold); flex: none; margin-top: .15rem; }}
.doc-title {{ font: 600 .95rem/1.3 var(--serif); color: var(--ink); }}
.doc-meta {{ font-size: .75rem; color: var(--ink-soft); margin-top: .15rem; }}

/* bordered containers become ledger cards */
.stApp [data-testid="stElementContainer"]:has(.card-anchor),
.stApp [data-testid="stElementContainer"]:has(.user-marker) {{ display: none; }}
.stApp [data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] .card-anchor) {{
  background: var(--card); border: 1px solid var(--line) !important; border-radius: 14px;
  box-shadow: 0 1px 0 var(--shadow), inset 0 0 0 3px var(--bg), inset 0 0 0 4px var(--gold-soft);
  padding: .35rem .3rem;
}}

/* widgets */
.stApp [data-baseweb="select"] > div {{ background: var(--card); border-color: var(--line); border-radius: 10px; }}
.stApp [data-baseweb="select"] > div:hover {{ border-color: var(--gold-bright); }}
.stApp [data-baseweb="select"] * {{ color: var(--ink); }}
[data-baseweb="popover"] ul {{ background: var(--card); }}
[data-baseweb="popover"] li {{ color: var(--ink); }}
.stApp [data-testid="stWidgetLabel"] p {{ font-size: .8rem; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; color: var(--ink-soft); }}
.stApp [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stCheckbox"] p {{ text-transform: none; letter-spacing: 0; font-size: .88rem; }}
.stApp [data-testid="stSlider"] [role="slider"] {{ background: var(--gold); box-shadow: 0 0 0 4px var(--gold-soft); }}
.stApp [data-testid="stSliderThumbValue"] {{ color: var(--gold); font-weight: 600; }}
.stApp [data-testid="stSliderTickBarMin"], .stApp [data-testid="stSliderTickBarMax"] {{ color: var(--ink-soft); }}

/* ---------- chat ---------- */
[data-testid="stChatMessage"] {{
  background: var(--card); border: 1px solid var(--line); border-radius: 16px;
  padding: 1rem 1.15rem; margin-bottom: 1.1rem; box-shadow: 0 2px 12px var(--shadow);
  animation: rise .45s ease-out both;
}}
[data-testid="stChatMessage"]:has(.user-marker) {{ background: var(--surface-2); box-shadow: none; }}
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {{ font-size: .98rem; line-height: 1.65; }}
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"],
[data-testid="stChatMessage"] [data-testid^="stChatMessageAvatar"] {{
  background: var(--gold); color: var(--bg); border-radius: 50%;
}}
@keyframes rise {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: none; }} }}

[data-testid="stChatInput"] {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  box-shadow: 0 6px 24px var(--shadow); }}
[data-testid="stChatInput"]:focus-within {{ border-color: var(--gold); box-shadow: 0 0 0 3px var(--gold-soft), 0 6px 24px var(--shadow); }}
[data-testid="stChatInputTextArea"] {{ color: var(--ink); background: transparent; }}
[data-testid="stChatInputTextArea"]::placeholder {{ color: var(--ink-soft); }}
[data-testid="stChatInputSubmitButton"] {{ color: var(--gold); }}

/* ---------- sources drawer and certificate cards ---------- */
[data-testid="stExpander"] details {{
  background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
  border-left: 4px solid var(--gold);
}}
[data-testid="stExpander"] summary {{ font: 600 1rem var(--serif); color: var(--ink); }}
[data-testid="stExpander"] summary:hover {{ color: var(--gold); }}
[data-testid="stExpander"] summary svg {{ color: var(--gold); }}
.drawer-head {{ display: flex; align-items: center; gap: .5rem; font-size: .78rem; letter-spacing: .14em;
  text-transform: uppercase; color: var(--ink-soft); margin: .1rem 0 .8rem; }}
.drawer-head svg {{ width: 15px; height: 15px; color: var(--gold); }}
.cite {{
  position: relative; display: flex; gap: .9rem; align-items: flex-start;
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: .85rem 1rem .8rem; margin-bottom: .7rem;
  box-shadow: inset 0 0 0 4px var(--card), inset 0 0 0 5px var(--gold-soft);
  animation: rise .5s ease-out both; transition: border-color .2s, box-shadow .2s;
}}
.cite:hover {{ border-color: var(--gold-bright);
  box-shadow: inset 0 0 0 4px var(--card), inset 0 0 0 5px var(--line), 0 6px 18px var(--shadow); }}
.seal {{
  flex: none; width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center;
  font: 700 1rem var(--serif); color: var(--gold);
  background: radial-gradient(circle, var(--gold-soft) 55%, transparent 56%);
  border: 1.5px dashed var(--gold); box-shadow: 0 0 0 3px var(--card), 0 0 0 4px var(--line);
}}
.cite-body {{ min-width: 0; flex: 1; }}
.cite-title {{ font: 600 1rem/1.3 var(--serif); color: var(--ink); }}
.cite-meta {{ font-size: .78rem; color: var(--ink-soft); margin-top: .2rem; display: flex; flex-wrap: wrap; gap: .35rem .8rem; }}
.cite-meta .rel {{ color: var(--gold); font-weight: 600; }}
.stApp .cite details {{ border: 0; background: none; padding: 0; margin: 0; border-radius: 0; }}
.stApp .cite details summary {{ padding: 0; background: none; border: 0; display: inline-block; }}
.cite summary::-webkit-details-marker {{ display: none; }}
.cite summary::marker {{ content: ""; }}
.cite details summary {{ cursor: pointer; font-size: .8rem; color: var(--gold); margin-top: .45rem; list-style: none; }}
.cite details summary::before {{ content: "▸ "; }}
.cite details[open] summary::before {{ content: "▾ "; }}
.cite details summary:hover {{ text-decoration: underline; text-underline-offset: 3px; }}
.excerpt {{ white-space: pre-wrap; font-size: .84rem; line-height: 1.6; color: var(--ink);
  margin-top: .5rem; padding: .7rem .8rem; max-height: 320px; overflow-y: auto;
  background: var(--surface); border-radius: 8px; border-left: 2px solid var(--gold-soft); }}

/* ---------- alerts ---------- */
.stApp [data-testid="stAlert"] > div {{ background: var(--surface-2); color: var(--ink); border-radius: 12px; }}

/* ---------- the coin ---------- */
.coin-stage {{ position: fixed; z-index: -1; pointer-events: none; top: 9vh; right: 4vw;
  width: min(34vw, 380px); aspect-ratio: 1; perspective: 1100px; opacity: var(--coin-opacity); }}
.coin {{ position: relative; width: 100%; height: 100%; transform-style: preserve-3d;
  animation: spin 10s linear infinite; filter: drop-shadow(0 30px 30px rgba(60,40,5,.45)); }}
.coin-face, .coin-edge {{ position: absolute; inset: 0; border-radius: 50%; }}
.coin-face {{ display: grid; place-items: center; backface-visibility: hidden; color: #5A3E08;
  background:
    radial-gradient(circle at 32% 28%, rgba(255,246,214,.95), transparent 42%),
    radial-gradient(circle, #E9C25F 0%, #C9972B 58%, #9A6E12 100%);
  box-shadow: inset 0 0 0 6px rgba(120,84,10,.55), inset 0 0 0 10px rgba(255,236,180,.35); }}
.coin-front {{ transform: translateZ(7px); }}
.coin-back {{ transform: rotateY(180deg) translateZ(7px); }}
.coin-edge {{ background: linear-gradient(90deg, #8A6210, #C9972B, #7A560C); }}
.coin-ring {{ position: absolute; inset: 13%; border-radius: 50%; border: 2px dotted rgba(90,62,8,.55); }}
.coin-glyph {{ font: 700 clamp(4rem, 12vw, 9rem)/1 var(--serif); text-shadow: 0 2px 0 rgba(255,240,200,.5); }}
@keyframes spin {{ from {{ transform: rotateY(0deg); }} to {{ transform: rotateY(360deg); }} }}
@media (prefers-reduced-motion: reduce) {{
  .coin {{ animation: none; transform: rotateY(-28deg) rotateX(8deg); }}
  [data-testid="stChatMessage"], .cite {{ animation: none; }}
}}
@media (max-width: 760px) {{ .coin-stage {{ top: auto; bottom: 14vh; right: -12vw; width: 70vw; }} }}
</style>
"""


ICONS = {
    "bank": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M3 9.5 12 4l9 5.5z"/><path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20.5h18"/></svg>',
    "doc": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/></svg>',
    "search": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>',
    "layers": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/></svg>',
    "sliders": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/></svg>',
    "seal": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="10" r="6"/><path d="m8.5 15-1.5 6 5-2.5 5 2.5-1.5-6"/></svg>',
}


def label(icon: str, text: str) -> str:
    return f'<div class="label">{ICONS[icon]}<span>{text}</span></div>'


def apply_theme(dark: bool = False):
    st.markdown(css(PALETTES["dark" if dark else "light"]) + COIN_HTML, unsafe_allow_html=True)
