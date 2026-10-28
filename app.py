"""
app.py  -  DarahBot exhibition app (Streamlit)
==============================================
Run with:   streamlit run app.py

This file only draws the screen. All calculations happen in bot_engine.py.
Design: the same blood-red theme as our survey website (dermadarah.jomana.my).
Made by @amirrulmukminin for the CSC649 Python Data Science Exhibition.
"""

import html
import io
import os
import random
import re
import socket
import time

import pandas as pd
import plotly.express as px
import streamlit as st

import bot_engine as bot

st.set_page_config(page_title="DarahBot · Malaysia Blood Donation Chatbot", page_icon="assets/bot.png",
                   layout="wide", initial_sidebar_state="auto")


# ---------------------------------------------------------------- settings
def setting(name, default=""):
    """Read a setting from .streamlit/secrets.toml (or an environment variable)."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


SURVEY_URL = setting("SURVEY_URL", "https://dermadarah.jomana.my")
SURVEY_CSV_URL = setting("SURVEY_CSV_URL", "")          # the anonymised export link (keep it secret)
APP_URL = setting("APP_URL", "https://dermadarahchatbox.jomana.my")
CREDIT = "@amirrulmukminin"


def B(en, ms):
    """English line + smaller grey Malay line underneath (same style as the survey)."""
    return f'{en}<span class="ms">{ms}</span>'


def heading(en, ms, sub_en="", sub_ms=""):
    sub = f'<p class="sub">{B(sub_en, sub_ms)}</p>' if sub_en else ""
    st.markdown(f'<div class="sec-head"><div class="h2">{B(en, ms)}</div>{sub}</div>', unsafe_allow_html=True)


def md_bold(text):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


# ---------------------------------------------------------------- style
CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root { --paper:#FBF6F4; --card:#FFFFFF; --ink:#2B0F13; --ink2:#5A3A3E; --muted:#8D7476; --line:#ECDCD8; --line2:#DCC3BF;
        --blood:#B0122A; --blood2:#D81F3B; --wine:#5C0714; --pink:#FFF0F1; --ok:#1D8A5A; --warn:#C0620F;
        --display:'Bricolage Grotesque', Inter, system-ui, sans-serif; --body:Inter, system-ui, -apple-system, sans-serif; }
html, body, .stApp { background: var(--paper) !important; }
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp div { font-family: var(--body); }
.stApp { color: var(--ink); }
h1, h2, h3, h4 { font-family: var(--display) !important; letter-spacing: -.015em; color: var(--ink); }
.ms { display:block; color: var(--muted); font-size:.8em; font-weight:400; letter-spacing:0; text-transform:none; margin-top:2px; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbarActions"], [data-testid="stMainMenu"], .stDeployButton, [data-testid="stAppDeployButton"] { display:none !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 2.2rem; max-width: 1180px; }

/* ---------- sidebar = the red panel ---------- */
[data-testid="stSidebar"] {
  background: radial-gradient(500px 400px at 10% 0%, rgba(255,90,110,.35), transparent 60%),
              linear-gradient(165deg, #A3122A 0%, #7A0A1B 55%, #4D0511 100%) !important;
}
[data-testid="stSidebar"]::before { content:""; position:absolute; inset:0; opacity:.07; pointer-events:none;
  background-image: radial-gradient(circle at 50% 60%, #fff 0 2.5px, transparent 3.5px); background-size: 30px 30px; }
[data-testid="stSidebar"] * { color: #fff; }
[data-testid="stSidebar"] .ms { color: rgba(255,255,255,.65); }
[data-testid="stSidebar"] .stButton button {
  background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.22); color:#fff; border-radius: 12px;
  text-align:left; justify-content:flex-start; font-weight:500; font-size:13.5px; transition: background .15s, transform .15s; }
[data-testid="stSidebar"] .stButton button:hover { background: rgba(255,255,255,.2); border-color: rgba(255,255,255,.45); transform: translateX(2px); color:#fff; }
[data-testid="stSidebar"] [data-baseweb="radio"] div { border-color: rgba(255,255,255,.7) !important; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"], [data-testid="stSidebar"] small { color: rgba(255,255,255,.75) !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.2); }
[data-testid="stSidebar"] [data-testid="stImage"] img { border-radius: 14px; border: 6px solid #fff; }
.brand { display:flex; align-items:center; gap:12px; margin: 4px 0 18px; }
.brand b { display:block; font: 800 22px/1.05 var(--display); }
.brand span { font-size: 12.5px; opacity:.8; }
.brand-drop { width:36px; height:36px; flex:none; background:#fff; border-radius:50% 50% 50% 0; transform:rotate(-45deg); position:relative; box-shadow:0 6px 18px rgba(0,0,0,.25); }
.brand-drop::after { content:""; position:absolute; inset:9px; border-radius:50%; background: var(--blood2); }
.bagbox { display:flex; align-items:center; gap:18px; padding: 10px 0 6px; }
.bagbox svg { width: 92px; flex:none; filter: drop-shadow(0 12px 22px rgba(0,0,0,.3)); }
.bagbox b { display:block; font: 800 40px/1 var(--display); letter-spacing:-.03em; }
.bagbox small { display:block; font-size:12.5px; opacity:.9; margin-top:6px; line-height:1.3; }
.wave { animation: wave 3.2s linear infinite; }
@keyframes wave { to { transform: translateX(-80px); } }
.side-label { font: 700 11px var(--body); letter-spacing:.14em; text-transform:uppercase; opacity:.75; margin: 16px 0 6px; }
.credit { font-size: 12px; opacity:.75; margin-top: 10px; }
.credit b { opacity: 1; }

/* ---------- hero ---------- */
.hero-tag { display:inline-flex; align-items:center; gap:8px; padding:7px 12px; border-radius:999px; background:var(--pink);
  color:var(--blood); font-size:13px; font-weight:600; margin-bottom:14px; }
.hero-tag i { width:8px; height:8px; border-radius:50%; background:var(--blood2); animation: beat 1.2s infinite; }
@keyframes beat { 0%,100% { transform:scale(1);} 15% { transform:scale(1.5);} 30% { transform:scale(1);} 45% { transform:scale(1.35);} }
.hero .h1 { font: 800 clamp(34px, 4.2vw, 56px)/1.02 var(--display); letter-spacing:-.035em; color: var(--ink); }
.hero .h1 em { font-style:normal; color: var(--blood); }
.hero .h1 .ms { font: 500 clamp(16px,1.4vw,20px)/1.3 var(--body); margin-top:10px; letter-spacing:0; }
.hero p.lead { font-size:16px; color: var(--ink2); margin: 14px 0 0; max-width: 760px; }
.hero p.lead .ms { font-size: 13.5px; }
.kpis { display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin: 22px 0 14px; }
.kpi { background:#fff; border:1px solid var(--line); border-radius:16px; padding:14px 16px; }
.kpi b { display:block; font: 800 30px/1.05 var(--display); color: var(--blood); letter-spacing:-.02em; }
.kpi span { font-size:13px; font-weight:600; color: var(--ink2); }
.kpi .ms, .kpi span .ms { font-size:11.5px; color: var(--muted); font-weight:500; }
.kpi em { display:inline-block; margin-top:6px; font-style:normal; font-size:12px; font-weight:700; padding:2px 8px; border-radius:999px; background:#E6F5EE; color:var(--ok); }
.kpi em.down { background:#FDF0E4; color: var(--warn); }
.fact { display:flex; gap:14px; align-items:flex-start; background: linear-gradient(135deg,#fff, var(--pink)); border:1.5px dashed #ECB0B8;
  border-radius:16px; padding:14px 18px; font-size:15.5px; }
.fact .ico { flex:none; width:36px; height:36px; border-radius:10px; background: var(--blood); color:#fff; display:grid; place-items:center; font-size:18px; }
.fact small { display:block; color: var(--muted); margin-top:4px; font-size:12px; }

/* ---------- tabs ---------- */
.stTabs [role="tablist"] { gap: 8px; flex-wrap: wrap; border-bottom: 0 !important; overflow: visible !important; }
.stTabs [data-testid="stTab"] { background:#fff; border:1.5px solid var(--line); border-radius: 999px; padding: 7px 14px;
  margin: 0 !important; transition: border-color .15s, transform .15s, background .15s; }
.stTabs [data-testid="stTab"]:hover { border-color:#E7A8B0; transform: translateY(-1px); }
.stTabs [data-testid="stTab"] p { font-weight:600; font-size: 14px; color: var(--ink); }
.stTabs [data-testid="stTab"][aria-selected="true"] { background: var(--blood); border-color: var(--blood); }
.stTabs [data-testid="stTab"][aria-selected="true"] p { color:#fff !important; }
.stTabs [data-testid="stTab"]::after, .stTabs [data-testid="stTab"]::before, .stTabs [role="tablist"]::after, .stTabs [role="tablist"]::before { display:none !important; content:none !important; }
.stTabs > div:has(> [role="tablist"]) { border:0 !important; box-shadow:none !important; background:none !important; }
.stTabs > div:has(> [role="tablist"])::after, .stTabs > div:has(> [role="tablist"])::before { display:none !important; }
[data-testid="stTabPanel"] { padding-top: 14px; }
/* ---------- section headings ---------- */
.sec-head { margin: 10px 0 14px; }
.sec-head .h2 { font: 700 clamp(22px,2vw,28px)/1.15 var(--display); color: var(--ink); letter-spacing:-.015em; }
.sec-head .h2 .ms { font: 400 14.5px var(--body); margin-top:4px; }
.sec-head p.sub { margin:6px 0 0; color: var(--ink2); font-size:14.5px; }
.sec-head p.sub .ms { font-size: 12.5px; }

/* ---------- buttons (main area) ---------- */
.stMainBlockContainer .stButton button, [data-testid="stMain"] .stButton button {
  border-radius: 14px; border: 1.5px solid var(--line); background:#fff; color: var(--ink); font-weight:600;
  transition: transform .15s, border-color .15s, box-shadow .15s; }
[data-testid="stMain"] .stButton button:hover { border-color:#E7A8B0; color: var(--blood); transform: translateY(-2px);
  box-shadow: 0 10px 24px -14px rgba(176,18,42,.5); }
[data-testid="stMain"] .stButton button[kind="primary"], [data-testid="stMain"] .stDownloadButton button[kind="primary"],
[data-testid="stMain"] [data-testid="stBaseButton-primary"] {
  background: linear-gradient(180deg, var(--blood2), var(--blood)); color:#fff; border:0;
  box-shadow: 0 12px 24px -12px rgba(176,18,42,.8); }
[data-testid="stMain"] [data-testid="stBaseButton-primary"]:hover { color:#fff; filter: brightness(1.06); }

/* ---------- chat ---------- */
[data-testid="stChatMessage"] { background:#fff; border:1px solid var(--line); border-radius: 18px; padding: 14px 16px; margin-bottom: 10px;
  animation: pop .45s cubic-bezier(.2,.8,.2,1) both; }
@keyframes pop { from { opacity:0; transform: translateY(12px); } to { opacity:1; transform:none; } }
[data-testid="stChatMessage"]:has(.umsg) { background: var(--pink); border-color:#F6CFD4; margin-left: 12%; }
.umsg { font-weight: 600; font-size: 15.5px; color: var(--ink); }
[data-testid="stChatInput"] { border-radius: 16px !important; border: 2px solid var(--line2) !important; background:#fff !important; }
[data-testid="stChatInput"]:focus-within { border-color: var(--blood) !important; box-shadow: 0 0 0 4px rgba(176,18,42,.12); }
[data-testid="stChatInputSubmitButton"] { background: var(--blood) !important; border-radius: 12px !important; }
[data-testid="stChatInputSubmitButton"] svg { fill:#fff !important; color:#fff !important; }
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: transparent !important; }
.evidence { background: #FBF6F4; border: 1px solid var(--line); border-left: 4px solid var(--blood); padding: 10px 14px;
  border-radius: 0 12px 12px 0; font-size: 13px; color: var(--ink2); margin-top: 8px; line-height:1.55; }
.evidence b { color: var(--ink); }
.evidence code { background:#fff; color: var(--blood); border:1px solid var(--line); border-radius:6px; padding:1px 5px; }
.refuse { background:#FDF4EA; border:1px solid #F1D2B6; border-left: 4px solid var(--warn); padding: 10px 14px; border-radius: 0 12px 12px 0; }
.typing { display:inline-flex; align-items:center; gap:6px; color: var(--muted); font-size: 13.5px; }
.typing i { width:10px; height:10px; border-radius:50% 50% 50% 0; transform: rotate(-45deg); background: var(--blood2); animation: hop 1s infinite ease-in-out; }
.typing i:nth-child(2) { animation-delay:.15s; } .typing i:nth-child(3) { animation-delay:.3s; }
@keyframes hop { 0%,100% { transform: rotate(-45deg) translateY(0); opacity:.5; } 40% { transform: rotate(-45deg) translate(4px,-4px); opacity:1; } }
.hello { background:#fff; border:1px solid var(--line); border-radius:18px; padding:18px 20px; margin-bottom:12px; }
.hello b { font: 700 19px var(--display); }
.chips-label { font: 700 11.5px var(--body); letter-spacing:.12em; text-transform:uppercase; color: var(--blood); margin: 10px 0 6px; }

/* ---------- cards used in tabs ---------- */
.card { background:#fff; border:1px solid var(--line); border-radius:18px; padding:18px 20px; margin-bottom:12px; }
.card .h3, .h3 { margin:0 0 4px; font: 700 19px/1.25 var(--display); color: var(--ink); }
.h3 .ms { font: 400 13px var(--body); }
.big-num { font: 800 clamp(40px,5vw,64px)/1 var(--display); color: var(--blood); letter-spacing:-.03em; }
.waffle { display:grid; grid-template-columns: repeat(20, 1fr); gap:5px; max-width: 560px; margin: 10px 0 6px; }
.waffle span { aspect-ratio: 1; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); background: var(--blood2);
  animation: pop .4s both; }
.waffle span.off { background: #F1E4E1; }
.split { display:flex; height:16px; border-radius:10px; overflow:hidden; background:#F1E4E1; margin-top:8px; }
.split i { display:block; height:100%; }
.legend { display:flex; flex-wrap:wrap; gap:14px; margin-top:8px; font-size:13.5px; color: var(--ink2); }
.legend em { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px; }
.meter { width:120px; height:120px; border-radius:50%; display:grid; place-content:center; text-align:center; position:relative;
  background: conic-gradient(var(--c) calc(var(--p) * 360deg), #F1E4E1 0); flex:none; }
.meter::before { content:""; position:absolute; inset:11px; border-radius:50%; background:#fff; }
.meter > * { position:relative; }
.meter b { font: 800 28px/1 var(--display); color: var(--c); }
.meter span { font-size:11px; color: var(--ink2); }
.result { display:flex; gap:20px; align-items:center; }
.result .lbl { font: 700 22px/1.2 var(--display); color: var(--c); }
.result .lbl .ms { font: 600 14px var(--body); color: var(--c); opacity:.8; }
.rules { list-style:none; padding:0; margin:14px 0 0; display:grid; grid-template-columns: 1fr 1fr; gap: 8px 18px; }
.rules li { display:flex; gap:10px; font-size:14.5px; }
.rules li i { flex:none; width:22px; height:22px; border-radius:50%; display:grid; place-items:center; font-style:normal; font-weight:800; color:#fff; font-size:12px; }
.rules li.pass i { background: var(--ok); } .rules li.fail i { background: var(--warn); }
.note { font-size: 12.5px; color: var(--muted); margin-top: 12px; }
.cta { display:flex; gap:16px; align-items:center; background: linear-gradient(135deg, var(--blood2), var(--wine)); color:#fff;
  border-radius:18px; padding:16px 20px; margin-top:12px; }
.cta a { color:#fff !important; font-weight:700; }
.cta .ms { color: rgba(255,255,255,.72); }

/* ---------- widgets ---------- */
[data-testid="stExpander"] { border:1px solid var(--line) !important; border-radius:14px !important; background:#fff; }
[data-baseweb="select"] > div, [data-baseweb="input"] > div, .stNumberInput input, .stTextInput input { border-radius: 12px !important; }
.stSlider [role="slider"] { background: #fff !important; border: 3px solid var(--blood) !important; }
[data-testid="stAlert"] { border-radius: 14px; }

/* ---------- phone: blood slowly rises behind everything ---------- */
.mblood { display:none; }
@media (max-width: 760px) {
  .block-container, [data-testid="stMainBlockContainer"] { padding-top: 3.2rem; padding-left: 1rem; padding-right: 1rem; }
  .kpis { grid-template-columns: 1fr 1fr; }
  .rules { grid-template-columns: 1fr; }
  .result { flex-direction: column; align-items: flex-start; }
  .mblood { display:block; position: fixed; left:0; right:0; bottom:0; z-index:0; pointer-events:none;
    background: linear-gradient(180deg, rgba(232,48,74,.14), rgba(176,18,42,.28)); transition: height 1.2s; }
  .mblood svg { position:absolute; left:0; bottom:100%; width:200%; height:24px; fill: rgba(232,48,74,.14); animation: mwave 6s linear infinite; }
  @keyframes mwave { to { transform: translateX(-50%); } }
  [data-testid="stMain"] { position: relative; z-index: 1; }
  [data-testid="stChatMessage"], .card, .kpi, .fact, .hello { background-color: rgba(255,255,255,.94); }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
</style>
"""
# (blank lines would break the <style> block inside st.markdown, so they are removed first)
st.markdown(re.sub(r"\n\s*\n", "\n", CSS), unsafe_allow_html=True)


# ---------------------------------------------------------------- data
@st.cache_data
def get_data():
    return bot.load_data()


@st.cache_data(ttl=60, show_spinner=False)
def get_survey(url):
    return bot.load_survey(url)


@st.cache_data
def qr_png(url):
    import qrcode
    qr = qrcode.QRCode(border=1, box_size=8, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    img = qr.make_image(fill_color="#5C0714", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


data = get_data()
survey = get_survey(SURVEY_CSV_URL) if SURVEY_CSV_URL else None
FULL = data["latest_full_year"]

if "lang" not in st.session_state:
    st.session_state.lang = "en"
BM = st.session_state.lang == "bm"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "context" not in st.session_state:
    st.session_state.context = None


def T(en, ms):
    """For the chatbot's answers and buttons: English or Malay, depending on the switch."""
    return ms if BM else en


EXAMPLES = [
    (f"Which state had the most blood donations in {FULL}?", f"Negeri mana paling banyak derma darah pada {FULL}?"),
    (f"Compare Melaka and Johor Gen Z donors in {FULL}", f"Bandingkan penderma muda Melaka dan Johor {FULL}"),
    ("How did Gen Z donors in Melaka change from 2019 to 2025?", "Bagaimana penderma muda di Melaka berubah dari 2019 hingga 2025?"),
    (f"Average new donors per state in {FULL}", f"Purata penderma baru setiap negeri {FULL}"),
    (f"Which hospital in Perak collects the most blood in {FULL}?", f"Hospital mana di Perak paling banyak kumpul darah {FULL}?"),
    (f"What blood types were donated in Melaka {FULL}?", f"Jenis darah yang didermakan di Melaka {FULL}"),
    ("How many people answered our survey?", "Berapa ramai yang menjawab tinjauan kami?"),
    ("Can I donate blood?", "Bolehkah saya derma darah?"),
    ("How many donors in melak 2024?", "Berapa derma di melak 2024?"),
    ("Why are fewer young people donating?", "Kenapa makin kurang orang muda menderma?"),
]
EX = [bm if BM else en for en, bm in EXAMPLES]

# ---------------------------------------------------------------- the blood bag (fills as you ask)
asked = sum(1 for m in st.session_state.messages if m["role"] == "user")
BAG_GOAL = 6
fill = min(asked / BAG_GOAL, 1.0)
prev = st.session_state.get("prev_fill", 0.0)
st.session_state.prev_fill = fill
ml = round(fill * 450)


def bag_svg(level, start):
    h = 168
    y_to = 176 if level == 0 else h * (1 - level) + 2
    y_from = 176 if start == 0 else h * (1 - start) + 2
    name = f"bagfill{int(level * 1000)}"
    return f"""
<svg viewBox="0 0 160 230" aria-hidden="true">
  <defs><clipPath id="bc"><rect x="22" y="42" width="116" height="168" rx="28"/></clipPath>
  <linearGradient id="lq" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff5468"/><stop offset="1" stop-color="#c3102c"/></linearGradient></defs>
  <style>@keyframes {name} {{ from {{ transform: translateY({y_from}px); }} to {{ transform: translateY({y_to}px); }} }}
  .lq{{ animation: {name} 1.2s cubic-bezier(.2,.8,.2,1) both; }}</style>
  <rect x="62" y="6" width="36" height="40" rx="8" fill="rgba(255,255,255,.18)" stroke="rgba(255,255,255,.85)" stroke-width="3"/>
  <circle cx="80" cy="20" r="6" fill="#7a0a1b" stroke="rgba(255,255,255,.85)" stroke-width="2"/>
  <rect x="22" y="42" width="116" height="168" rx="28" fill="rgba(255,255,255,.10)"/>
  <g clip-path="url(#bc)"><g class="lq"><path class="wave" fill="url(#lq)" d="M0 42 Q20 34 40 42 T80 42 T120 42 T160 42 T200 42 T240 42 T280 42 T320 42 V240 H0Z"/></g></g>
  <g stroke="rgba(255,255,255,.55)" stroke-width="2"><line x1="118" x2="132" y1="84" y2="84"/><line x1="118" x2="132" y1="126" y2="126"/><line x1="118" x2="132" y1="168" y2="168"/></g>
  <rect x="22" y="42" width="116" height="168" rx="28" fill="none" stroke="rgba(255,255,255,.85)" stroke-width="3"/>
  <path d="M80 210 V226" stroke="rgba(255,255,255,.85)" stroke-width="6" stroke-linecap="round"/>
</svg>"""


# phone: blood rising behind the page
st.markdown(f'<div class="mblood" style="height:{8 + fill * 62:.0f}vh"><svg viewBox="0 0 1200 60" preserveAspectRatio="none">'
            f'<path d="M0 30 Q150 60 300 30 T600 30 T900 30 T1200 30 V60 H0Z"/></svg></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(f'<div class="brand"><span class="brand-drop"></span><div><b>DarahBot</b>'
                f'<span>Blood Donation Chatbot</span></div></div>', unsafe_allow_html=True)
    note = (B("The bag is full. Thank you for asking!", "Beg sudah penuh. Terima kasih kerana bertanya!") if fill >= 1
            else B(f"Ask {BAG_GOAL - asked} more question{'s' if BAG_GOAL - asked != 1 else ''} to fill the bag",
                   f"Tanya {BAG_GOAL - asked} soalan lagi untuk mengisi beg"))
    st.markdown(f'<div class="bagbox">{bag_svg(fill, prev)}<div><b>{ml}</b><span>/ 450 ml</span><small>{note}</small></div></div>',
                unsafe_allow_html=True)

    st.markdown(f'<div class="side-label">{B("Answer language", "Bahasa jawapan")}</div>', unsafe_allow_html=True)
    choice_lang = st.radio("Answer language", ["English", "Bahasa Melayu"], horizontal=True, index=1 if BM else 0,
                           label_visibility="collapsed")
    new_lang = "bm" if choice_lang.endswith("Melayu") else "en"
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()
    if st.button(T("🗑️  Clear chat", "🗑️  Padam perbualan"), width="stretch"):
        st.session_state.messages = []
        st.session_state.context = None
        st.session_state.editing = None
        st.rerun()

    st.markdown(f'<div class="side-label">{B("Try asking", "Cuba tanya")}</div>', unsafe_allow_html=True)
    for q in EX:
        if st.button(q, key="side_" + q, width="stretch"):
            st.session_state.pending = q

    # QR code: on the exhibition Mac it points to this Wi-Fi; online it points to the public link
    try:
        host = st.context.url or ""
    except Exception:
        host = ""
    local = any(h in host for h in ("localhost", "127.0.0.1", "0.0.0.0")) or host == ""
    phone_url = APP_URL
    if local:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            phone_url = f"http://{sock.getsockname()[0]}:8501"
            sock.close()
        except Exception:
            phone_url = APP_URL
    st.markdown(f'<div class="side-label">{B("Try it on your phone", "Cuba di telefon anda")}</div>', unsafe_allow_html=True)
    st.image(qr_png(phone_url), width=150)
    st.caption(phone_url.replace("https://", "") + (" · same Wi-Fi / Wi-Fi sama" if local else ""))

    st.markdown(f'<div class="side-label">{B("Data sources", "Sumber data")}</div>', unsafe_allow_html=True)
    st.caption(f"• {bot.SOURCE_DONATIONS}\n\n• {bot.SOURCE_NEWDONORS}\n\n• {bot.SOURCE_FACILITY}\n\n• {bot.SOURCE_POP}\n\n"
               f"• {bot.SOURCE_SURVEY}")
    st.caption(f"KKM data: {bot.FIRST_YEAR} to {data['last_date']:%d %b %Y} · {len(data['states'])} states")
    st.markdown(f'<div class="credit">Made by <b>{CREDIT}</b></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- hero
nat = bot.yearly_values(data, "donations", ["Malaysia"])
genz = bot.yearly_values(data, "genz_share", ["Malaysia"])
nat_full = nat[nat.year == FULL]["value"].iloc[0]
nat_prev = nat[nat.year == FULL - 1]["value"].iloc[0]
gz_full = genz[genz.year == FULL]["value"].iloc[0]
gz_2019 = genz[genz.year == 2019]["value"].iloc[0]
SECS, _ = bot.seconds_per_donation(data)
ch = (nat_full - nat_prev) / nat_prev * 100
gz_ch = gz_full - gz_2019

st.markdown(f"""
<section class="hero">
  <span class="hero-tag"><i></i>In {FULL}, someone in Malaysia donated blood every {SECS:.0f} seconds</span>
  <div class="h1">Ask DarahBot.<br><em>Every answer shows its proof.</em>
    <span class="ms">Tanya DarahBot. Setiap jawapan disertakan bukti.</span></div>
  <p class="lead">Ask anything about blood donations in Malaysia. Every number comes from official KKM data, with the evidence shown underneath.
    <span class="ms">Tanya apa sahaja tentang derma darah di Malaysia. Setiap nombor datang daripada data rasmi KKM, dengan bukti di bawahnya.</span></p>
  <div class="kpis">
    <div class="kpi"><b>{nat_full:,.0f}</b><span>{B(f"Donations in {FULL}", f"Derma pada {FULL}")}</span><em class="{'' if ch >= 0 else 'down'}">{ch:+.1f}% vs {FULL - 1}</em></div>
    <div class="kpi"><b>{gz_full:.1f}%</b><span>{B("Gen Z share of new donors", "Peratus Gen Z dalam penderma baru")}</span><em class="{'' if gz_ch >= 0 else 'down'}">{gz_ch:+.1f} pts vs 2019</em></div>
    <div class="kpi"><b>{FULL - bot.FIRST_YEAR + 1}+</b><span>{B("Years of records", "Tahun rekod")}</span></div>
    <div class="kpi"><b>{len(data['donations']):,}</b><span>{B("Daily rows in the dataset", "Baris data harian")}</span></div>
  </div>
</section>""", unsafe_allow_html=True)

FACTS = bot.fun_facts(data, st.session_state.lang)
if "fact" not in st.session_state:
    st.session_state.fact = random.randrange(len(FACTS))
fc, fb = st.columns([6, 1], vertical_alignment="center")
fact, fact_ev = FACTS[st.session_state.fact]
fc.markdown(f'<div class="fact"><span class="ico">💡</span><div><b>{T("Did you know?", "Tahukah anda?")}</b> {md_bold(fact)}'
            f'<small>🔎 {fact_ev}</small></div></div>', unsafe_allow_html=True)
if fb.button(T("🔀 Another fact", "🔀 Fakta lain"), width="stretch"):
    st.session_state.fact = (st.session_state.fact + random.randrange(1, len(FACTS))) % len(FACTS)
    st.rerun()
st.write("")

(tab_chat, tab_elig, tab_survey, tab_type, tab_map, tab_hosp, tab_cal, tab_time, tab_story, tab_game, tab_show,
 tab_about) = st.tabs(["💬 Ask DarahBot", "✅ Can I donate?", "📋 Our survey", "🩸 My blood type", "🗺️ State map",
                       "🏥 Hospitals", "📅 Calendar", "⏳ Time machine", "📉 Gen Z story", "🎯 Guess", "📺 Exhibition",
                       "📄 About"])

# ================================================================ CHAT
with tab_chat:
    def typing(text):
        for word in text.split(" "):
            yield word + " "
            time.sleep(0.022)

    def show_reply(r, idx, animate=False):
        if animate:  # three hopping blood drops while DarahBot "thinks"
            ph = st.empty()
            ph.markdown(f'<div class="typing"><i></i><i></i><i></i>&nbsp;{T("DarahBot is checking the data…", "DarahBot sedang menyemak data…")}</div>',
                        unsafe_allow_html=True)
            time.sleep(0.8)
            ph.empty()
        if r["kind"] == "refuse":
            html = md_bold(r["text"])
            html = re.sub(r"\*(.+?)\*", r"<i>\1</i>", html).replace("\n- ", "<br>• ").replace("\n", "<br>")
            st.markdown(f'<div class="refuse">🙅 {html}</div>', unsafe_allow_html=True)
        elif animate:
            st.write_stream(typing(r["text"]))
        else:
            st.markdown(r["text"])
        if r["kind"] == "ok":
            for n in r["notes"]:
                st.caption("ℹ️ " + n)
        if r["evidence"]:
            e = r["evidence"]
            st.markdown(f'<div class="evidence">🔎 <b>{T("Evidence", "Bukti")}</b> · value: <b>{e["value"]}</b> · field: <code>{e["field"]}</code>'
                        f' · filter: {e["filters"]} · unit: {e["unit"]}<br>source: {e["source"]}</div>', unsafe_allow_html=True)
        if r["chart"] is not None:
            st.plotly_chart(r["chart"], width="stretch", key=f"chart_{idx}", config={"displayModeBar": False}, theme=None)
        if r["rows"] is not None:
            with st.expander(T("🧾 How I got this (the exact rows I used)", "🧾 Bagaimana saya dapat ini (baris data tepat)")):
                st.dataframe(r["rows"], width="stretch", hide_index=True)

    if not st.session_state.messages:
        st.markdown(f'<div class="hello"><b>{B("👋 Hi! I am DarahBot.", "Hai! Saya DarahBot.")}</b>'
                    f'<p style="margin:6px 0 0;color:var(--ink2)">{B("Pick a question below, type your own, or press 🎤 and speak. I answer in the language chosen on the left.", "Pilih soalan di bawah, taip sendiri, atau tekan 🎤 dan bercakap. Saya menjawab dalam bahasa yang dipilih di sebelah kiri.")}</p></div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="chips-label">{T("Try one of these", "Cuba salah satu")}</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, q in enumerate(EX[:8]):
            if cols[i % 2].button(q, key="main_" + q, width="stretch"):
                st.session_state.pending = q

    for i, m in enumerate(st.session_state.messages):
        with st.chat_message(m["role"], avatar="assets/user.png" if m["role"] == "user" else "assets/bot.png"):
            if m["role"] == "user":
                if st.session_state.get("editing") == i:
                    new_q = st.text_input(T("Edit your question", "Ubah soalan anda"), value=m["content"], key=f"edit_box_{i}")
                    b1, b2, _ = st.columns([1, 1, 4])
                    if b1.button(T("↩️ Resend", "↩️ Hantar semula"), key=f"resend_{i}", type="primary", width="stretch"):
                        if new_q.strip():
                            earlier = st.session_state.messages[:i]
                            st.session_state.messages = earlier
                            ok_replies = [x["content"] for x in earlier if x["role"] == "assistant" and x["content"]["kind"] == "ok"]
                            st.session_state.context = ok_replies[-1]["context"] if ok_replies else None
                            st.session_state.editing = None
                            st.session_state.pending = new_q.strip()
                            st.rerun()
                        else:
                            st.caption(":red[Type a question first.]")
                    if b2.button(T("Cancel", "Batal"), key=f"cancel_{i}", width="stretch"):
                        st.session_state.editing = None
                        st.rerun()
                else:
                    q_col, e_col = st.columns([12, 1], vertical_alignment="center")
                    q_col.markdown(f'<div class="umsg">{html.escape(m["content"])}</div>', unsafe_allow_html=True)
                    if e_col.button("✏️", key=f"edit_{i}", help=T("Edit and resend this question", "Ubah dan hantar semula soalan ini")):
                        st.session_state.editing = i
                        st.rerun()
            else:
                show_reply(m["content"], i, animate=(i == st.session_state.get("animate")))
    st.session_state.animate = None

    # quick follow-up buttons under the last answer (shows the bot remembers)
    ctx = st.session_state.context
    if st.session_state.messages and ctx:
        other = next(s for s in ["Johor", "Selangor", "Pulau Pinang"] if s not in (ctx["states"] or []))
        chips = [T(f"What about {other}?", f"Bagaimana dengan {other}?"), T("And in 2019?", "Kalau 2019?")]
        if ctx["intent"] != "trend":
            chips.append(T("Show the trend since 2015", "Tunjuk trend sejak 2015"))
        st.markdown(f'<div class="chips-label">{T("Ask a follow-up", "Tanya soalan susulan")}</div>', unsafe_allow_html=True)
        for col, chip in zip(st.columns(len(chips)), chips):
            if col.button(chip, key=f"chip_{chip}_{len(st.session_state.messages)}", width="stretch"):
                st.session_state.pending = chip
                st.rerun()

    # 🎤 Voice question: Chrome turns speech into text, then it is typed into the chat box for you
    st.iframe(f"""
    <div style="font-family:Inter,system-ui,sans-serif;display:flex;align-items:center;gap:10px">
      <button id="mic" style="background:linear-gradient(180deg,#D81F3B,#B0122A);color:white;border:none;border-radius:999px;
        padding:9px 18px;font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 10px 20px -10px rgba(176,18,42,.8)">
        🎤 {T("Speak your question", "Cakap soalan anda")}</button>
      <span id="st" style="color:#8D7476;font-size:13px"></span>
    </div>
    <script>
    const btn = document.getElementById("mic"), st = document.getElementById("st");
    const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
    btn.onclick = () => {{
      if (!Rec) {{ st.textContent = "{T("Voice works in Google Chrome only.", "Suara hanya berfungsi di Google Chrome.")}"; return; }}
      const r = new Rec(); r.lang = "{T("en-MY", "ms-MY")}"; r.interimResults = false;
      st.textContent = "{T("Listening…", "Sedang mendengar…")}"; btn.disabled = true;
      r.onresult = (e) => {{
        const text = e.results[0][0].transcript;
        st.textContent = "“" + text + "”";
        const doc = window.parent.document;
        const box = doc.querySelector('textarea[data-testid="stChatInputTextArea"]');
        const setter = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, "value").set;
        setter.call(box, text);
        box.dispatchEvent(new Event("input", {{ bubbles: true }}));
        setTimeout(() => doc.querySelector('[data-testid="stChatInputSubmitButton"]').click(), 300);
      }};
      r.onerror = (e) => {{ st.textContent = "{T("Couldn't hear you. Try again.", "Tidak dapat dengar. Cuba lagi.")}"; }};
      r.onend = () => {{ btn.disabled = false; }};
      r.start();
    }};
    </script>""", height=52)

    typed = st.chat_input(T("Ask about blood donations by state, year, age group or blood type…",
                            "Tanya tentang derma darah mengikut negeri, tahun, umur atau jenis darah…"))
    question = typed or st.session_state.pop("pending", None)
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        reply = bot.answer(question, data, st.session_state.context, st.session_state.lang, survey=survey)
        if reply["kind"] == "ok" and reply["context"]:
            st.session_state.context = reply["context"]
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.animate = len(st.session_state.messages) - 1
        st.rerun()


# ================================================================ CAN I DONATE?
def rules_html(rules):
    return '<ul class="rules">' + "".join(
        f'<li class="{"pass" if ok else "fail"}"><i>{"✓" if ok else "!"}</i><span>{B(en, ms)}</span></li>' for ok, en, ms in rules) + "</ul>"


with tab_elig:
    heading("Can I donate blood?", "Bolehkah saya menderma darah?",
            "Answer 5 quick questions to get an early hypothesis, the same check our survey uses.",
            "Jawab 5 soalan ringkas untuk mendapat hipotesis awal, sama seperti semakan dalam tinjauan kami.")
    a, b = st.columns(2)
    e_age = a.number_input("Age · Umur (years / tahun)", min_value=10, max_value=100, value=20, step=1)
    e_wt = b.number_input("Weight · Berat (kg)", min_value=20.0, max_value=250.0, value=55.0, step=0.5)
    e_sleep = a.slider("Usual sleep per night · Tidur biasa setiap malam (hours / jam)", 0.0, 16.0, 7.0, 0.5)
    e_meds = b.slider("Days a month on long-term medicine · Hari sebulan mengambil ubat jangka panjang", 0, 31, 0)
    e_tat = st.radio("Tattoo, piercing or acupuncture in the last 12 months? · Tatu, tindik atau akupunktur dalam 12 bulan lepas?",
                     ["No · Tidak", "Yes · Ya"], horizontal=True)
    if st.button("Check my result · Semak keputusan saya", type="primary"):
        st.session_state.elig = bot.check_eligibility(e_age, e_wt, e_sleep, e_tat.startswith("Yes"), e_meds)
    if st.session_state.get("elig"):
        rules = st.session_state.elig
        passed = sum(1 for ok, *_ in rules if ok)
        good = passed == len(rules)
        colour = "var(--ok)" if good else "var(--warn)"
        label = B("You can probably donate blood", "Anda berkemungkinan LAYAK menderma darah") if good else \
            B("You probably cannot donate yet", "Anda berkemungkinan BELUM LAYAK menderma darah")
        st.markdown(f"""
<div class="card" style="--c:{colour}">
  <div class="h3">{B("Our early hypothesis for you", "Hipotesis awal kami untuk anda")}</div>
  <div class="result" style="margin-top:12px">
    <div class="meter" style="--p:{passed / len(rules)}"><b>{passed}/{len(rules)}</b><span>rules met</span></div>
    <div><div class="lbl">{label}</div>
      <p style="margin:6px 0 0;color:var(--ink2)">{B("Based on the 5 basic Pusat Darah Negara rules.", "Berdasarkan 5 syarat asas Pusat Darah Negara.")}</p></div>
  </div>
  {rules_html(rules)}
  <p class="note">{B("This is only a hypothesis, not a medical decision. The blood bank staff will do the real check.",
                     "Ini hanya hipotesis, bukan keputusan perubatan. Kakitangan bank darah akan membuat semakan sebenar.")}</p>
</div>
<div class="cta"><span style="font-size:28px">📋</span><div>{B(f'Help us build the real model: take our 2-minute survey at <a href="{SURVEY_URL}" target="_blank">{SURVEY_URL.replace("https://", "")}</a>',
     "Bantu kami membina model sebenar: jawab tinjauan 2 minit kami")}</div></div>
""", unsafe_allow_html=True)
    st.caption("🔎 " + bot.SOURCE_RULES)

# ================================================================ OUR SURVEY (live)
with tab_survey:
    heading("Our survey, live", "Tinjauan kami, secara langsung",
            "Answers from dermadarah.jomana.my. Donors become our database; first-timers get a hypothesis. No names or emails are shown.",
            "Jawapan daripada dermadarah.jomana.my. Penderma menjadi pangkalan data kami; yang belum pernah mendapat hipotesis. Tiada nama atau e-mel ditunjukkan.")
    if survey is None:
        msg = B("The survey data is not connected right now, so I will not show any numbers.",
                "Data tinjauan tidak disambungkan sekarang, jadi saya tidak akan menunjukkan sebarang nombor.")
        st.markdown('<div class="card">' + msg + '<p class="note">Setup: add <code>SURVEY_CSV_URL</code> to '
                    '<code>.streamlit/secrets.toml</code> (see README).</p></div>', unsafe_allow_html=True)
    else:
        s = bot.survey_summary(survey)
        st.markdown(f"""
<div class="kpis">
  <div class="kpi"><b>{s['n']}</b><span>{B("Total answers", "Jumlah jawapan")}</span></div>
  <div class="kpi"><b>{s['donors']}</b><span>{B("Have donated (database)", "Pernah menderma (pangkalan data)")}</span></div>
  <div class="kpi"><b>{s['never']}</b><span>{B("Never donated (hypothesis)", "Belum pernah (hipotesis)")}</span></div>
  <div class="kpi"><b>{(f"{s['avg_willing']:.1f}" if s['avg_willing'] is not None and s['n'] else "–")}</b><span>{B("Average willingness /10", "Purata kesanggupan /10")}</span></div>
</div>""", unsafe_allow_html=True)

        def split(a, b_, la, lb):
            tot = max(1, a + b_)
            pa = a / tot * 100
            bars = (f'<i style="width:{pa}%;background:var(--ok)"></i><i style="width:{100 - pa}%;background:var(--warn)"></i>'
                    if a + b_ else "")
            return (f'<div class="split">{bars}</div><div class="legend"><span><em style="background:var(--ok)"></em>{la} <b>{a}</b></span>'
                    f'<span><em style="background:var(--warn)"></em>{lb} <b>{b_}</b></span></div>')

        c1, c2 = st.columns(2)
        c1.markdown(f'<div class="card"><div class="h3">{B("Donors: last result", "Penderma: keputusan terakhir")}</div>'
                    f'{split(s["accepted"], s["deferred"], "Accepted · Diterima", "Deferred · Ditangguhkan")}</div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="card"><div class="h3">{B("Never donated: our hypothesis", "Belum pernah: hipotesis kami")}</div>'
                    f'{split(s["likely"], s["not_yet"], "Probably eligible · Layak", "Not yet · Belum layak")}</div>', unsafe_allow_html=True)
        if s["n"]:
            sv = survey.copy()
            g1, g2 = st.columns(2)
            by_state = sv["state"].value_counts().rename_axis("state").reset_index(name="value")
            g1.plotly_chart(bot.bar_chart(by_state, [by_state.iloc[0]["state"]], "Answers by state · Jawapan mengikut negeri", "new_donors")
                            .update_layout(xaxis_title="people"), width="stretch", config={"displayModeBar": False}, theme=None)
            bt = sv["blood_type"].value_counts().rename_axis("blood type").reset_index(name="people")
            fig = px.pie(bt, names="blood type", values="people", hole=.55, title="Blood type · Jenis darah",
                         color_discrete_sequence=[bot.RED, bot.PINK, bot.WINE, bot.BLUSH, bot.GREY])
            fig.update_traces(textinfo="label+percent")
            fig.update_layout(legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"))
            g2.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)
            g3, g4 = st.columns(2)
            ages = pd.cut(sv["age"], [0, 17, 24, 34, 44, 60, 200], labels=["17", "18–24", "25–34", "35–44", "45–60", "61+"])
            ag = ages.value_counts().reindex(["17", "18–24", "25–34", "35–44", "45–60", "61+"], fill_value=0).rename_axis("age").reset_index(name="people")
            fig = px.bar(ag, x="age", y="people", text="people", title="Age group · Kumpulan umur")
            fig.update_traces(marker_color=bot.RED, textposition="outside", cliponaxis=False)
            g3.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)
            w = sv["willingness"].value_counts().reindex(range(1, 11), fill_value=0).rename_axis("score").reset_index(name="people")
            fig = px.bar(w, x="score", y="people", text="people", title="Willingness to donate (1–10) · Kesanggupan menderma")
            fig.update_traces(marker_color=[bot.BLUSH] * 5 + [bot.PINK] * 3 + [bot.RED] * 2, textposition="outside", cliponaxis=False)
            fig.update_xaxes(dtick=1)
            g4.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)
        st.caption("🔎 " + bot.SOURCE_SURVEY + " · refreshes every minute / dikemas kini setiap minit")
    q1, q2 = st.columns([1, 4], vertical_alignment="center")
    q1.image(qr_png(SURVEY_URL), width=140)
    short_url = SURVEY_URL.replace("https://", "")
    link = '<a href="' + SURVEY_URL + '" target="_blank">' + short_url + '</a>'
    cta = B("Not answered yet? Scan the code or open " + link + ". It takes about 2 minutes.",
            "Belum menjawab? Imbas kod atau buka " + link + ". Hanya kira-kira 2 minit.")
    q2.markdown('<div class="cta"><div>' + cta + '</div></div>', unsafe_allow_html=True)

# ================================================================ MY BLOOD TYPE
with tab_type:
    heading("What's your blood type?", "Apakah jenis darah anda?",
            "Pick yours and see how common it is among donations in Malaysia.",
            "Pilih jenis anda dan lihat betapa biasanya ia dalam derma darah di Malaysia.")
    a, b = st.columns(2)
    bt = a.radio("My blood type · Jenis darah saya", ["A", "B", "O", "AB"], horizontal=True, index=2)
    home = b.selectbox("My state · Negeri saya", data["states"], index=data["states"].index("Melaka"))
    prof = bot.blood_type_profile(data, bt)
    nat_row = prof[prof.state == "Malaysia"].iloc[0]
    states_only = prof[prof.state != "Malaysia"].reset_index(drop=True)
    mine = states_only[states_only.state == home].iloc[0]
    rank_no = int(states_only.index[states_only.state == home][0]) + 1
    pct = round(nat_row["percent"])
    word = ("rare", "jarang") if nat_row["percent"] < 10 else (("common", "biasa") if nat_row["percent"] > 30 else ("fairly common", "agak biasa"))
    waffle = "".join(f'<span class="{"" if i < pct else "off"}" style="animation-delay:{i * 8}ms"></span>' for i in range(100))
    st.markdown(f"""
<div class="card">
  <div class="big-num">{nat_row['percent']:.1f}%</div>
  <div class="h3" style="margin-top:6px !important">{B(f"of donations in Malaysia were type {bt} ({FULL})", f"daripada derma di Malaysia ialah jenis {bt} ({FULL})")}</div>
  <p style="margin:10px 0 0;color:var(--ink2)">{B(f"That's about <b>{pct} out of every 100</b> bags of blood:", f"Iaitu kira-kira <b>{pct} daripada setiap 100</b> beg darah:")}</p>
  <div class="waffle">{waffle}</div>
  <p style="margin:12px 0 0">{B(f"Type {bt} is <b>{word[0]}</b>. In <b>{home}</b>, type {bt} was <b>{mine['percent']:.1f}%</b> of donations ({mine['donations']:,.0f} bags), ranking <b>#{rank_no} of {len(states_only)}</b> states.",
                                f"Jenis {bt} adalah <b>{word[1]}</b>. Di <b>{home}</b>, jenis {bt} ialah <b>{mine['percent']:.1f}%</b> daripada derma ({mine['donations']:,.0f} beg), kedudukan <b>#{rank_no} daripada {len(states_only)}</b> negeri.")}</p>
</div>""", unsafe_allow_html=True)
    fig = bot.bar_chart(states_only.rename(columns={"percent": "value"}), [home], f"Share of donations that are type {bt}, {FULL}", "genz_share")
    fig.update_layout(xaxis_title="% of donations")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)
    st.caption(f"🔎 Evidence: blood_{bt.lower()} ÷ (blood_a + blood_b + blood_o + blood_ab), year = {FULL} · {bot.SOURCE_DONATIONS}. "
               "The data has no Rh (+/−) information. · Data tidak mempunyai maklumat Rh (+/−).")

    heading("Get your Donor Hero card", "Dapatkan kad Wira Penderma anda",
            "Type your name and download a card with real facts about your blood type. A fun souvenir, not an official certificate.",
            "Taip nama anda dan muat turun kad dengan fakta sebenar tentang jenis darah anda. Cenderahati, bukan sijil rasmi.")
    hero_name = st.text_input("Your name · Nama anda", max_chars=24, placeholder="Amirrul")
    if hero_name.strip():
        card = bot.make_hero_card(data, hero_name, bt, home)
        st.image(card, width=640)
        st.download_button("⬇️ Download my card · Muat turun kad saya", card,
                           file_name=f"DarahBot_{hero_name.strip().replace(' ', '_')}_{bt}.png", mime="image/png", type="primary")

# ================================================================ TILE MAP
TILES = {"Kedah": (1, 0), "Kelantan": (2, 0), "Pulau Pinang": (0, 1), "Perak": (1, 1), "Terengganu": (2, 1),
         "Selangor": (0, 2), "W.P. Kuala Lumpur": (1, 2), "Pahang": (2, 2), "Negeri Sembilan": (1, 3),
         "Melaka": (1, 4), "Johor": (2, 4), "Sarawak": (4.6, 3), "Sabah": (5.8, 2)}
SHORT = {"Pulau Pinang": "P.Pinang", "W.P. Kuala Lumpur": "KL", "Negeri Sembilan": "N.Sembilan", "Terengganu": "T'ganu"}
METRIC_CHOICES = {"Total donations": "donations", "Donations per 1,000 adults": "per_capita", "New donors": "new_donors",
                  "Gen Z new donors": "genz", "Gen Z share of new donors (%)": "genz_share", "Student donations": "students"}

with tab_map:
    heading("Which states give the most blood?", "Negeri mana paling banyak menderma darah?",
            "Each square is a state, placed roughly where it sits on the map. Darker red = higher value.",
            "Setiap petak ialah negeri, diletakkan lebih kurang seperti di peta. Merah lebih gelap = nilai lebih tinggi.")
    a, b = st.columns([2, 1])
    choice = a.selectbox("Measure · Ukuran", list(METRIC_CHOICES), index=1)
    yr = b.slider("Year · Tahun", bot.FIRST_YEAR, data["latest_year"], FULL, key="map_year")
    m = METRIC_CHOICES[choice]
    df = bot.rank(data, m, yr)
    df["x"] = df.state.map(lambda s: TILES[s][0])
    df["y"] = df.state.map(lambda s: TILES[s][1])
    df["label"] = df.apply(lambda r: f"{SHORT.get(r.state, r.state)}<br><b>{bot.fmt(r.value, m)}</b>", axis=1)
    fig = px.scatter(df, x="x", y="y", color="value", text="label", hover_name="state",
                     color_continuous_scale=["#FBEFF0", "#EE8E9C", "#D81F3B", "#5C0714"], labels={"value": choice})
    dark = df["value"] > df["value"].min() + 0.45 * (df["value"].max() - df["value"].min())
    fig.update_traces(marker=dict(symbol="square", size=86, line=dict(width=3, color="#FBF6F4")),
                      textfont=dict(color=["white" if d else "#2B0F13" for d in dark], family="Inter"))
    fig.update_xaxes(visible=False, range=[-0.7, 6.5])
    fig.update_yaxes(visible=False, autorange="reversed", range=[-0.7, 4.7])
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0))
    fig.add_annotation(x=1, y=-0.6, text="Peninsular Malaysia", showarrow=False, font_color="#8D7476")
    fig.add_annotation(x=5.2, y=1.3, text="Borneo", showarrow=False, font_color="#8D7476")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)
    top, low = df.iloc[0], df.iloc[-1]
    st.markdown(f'<div class="card">🏆 <b>{top.state}</b> is highest ({bot.fmt(top.value, m)}), <b>{low.state}</b> is lowest ({bot.fmt(low.value, m)}).'
                f'{bot.year_note(data, yr)}<span class="ms">{top.state} paling tinggi, {low.state} paling rendah.</span></div>', unsafe_allow_html=True)
    if m == "per_capita":
        st.caption("Per 1,000 adults uses DOSM 2020 population. KL scores very high partly because people from Selangor donate at KL hospitals.")

# ================================================================ HOSPITALS
with tab_hosp:
    heading("Which blood bank collects the most?", "Bank darah mana paling banyak kumpul?",
            "22 government blood banks. Each hospital is matched to its state, and the hospital totals add up exactly to each state's total.",
            "22 bank darah kerajaan. Setiap hospital dipadankan dengan negerinya, dan jumlahnya sama tepat dengan jumlah negeri.")
    a, b, c = st.columns(3)
    hs = a.selectbox("State · Negeri", ["All of Malaysia"] + data["states"], key="h_state")
    hy = b.slider("Year · Tahun", bot.FIRST_YEAR, data["latest_year"], FULL, key="h_year")
    hm_choices = {"Total donations": "daily", "Student donations": "social_student",
                  "Mobile drives": "location_mobile", "New donors' donations": "donations_new"}
    hm = c.selectbox("Measure · Ukuran", list(hm_choices), key="h_metric")
    hr = bot.hospital_ranking(data, hy, hm_choices[hm], None if hs == "All of Malaysia" else hs)
    if hr.empty:
        st.warning("No hospital data for this choice. · Tiada data hospital untuk pilihan ini.")
    else:
        top = hr.iloc[0]
        st.markdown(f'<div class="card">🏆 <b>{top["hospital"]}</b> ({top["state"]}): <b>{top["value"]:,.0f}</b>{bot.year_note(data, hy)}</div>',
                    unsafe_allow_html=True)
        hr2 = hr.copy()
        hr2["colour"] = ["top" if i == 0 else "other" for i in range(len(hr2))]
        fig = px.bar(hr2, x="value", y="hospital", orientation="h", color="colour", text=hr2["value"].map("{:,.0f}".format),
                     color_discrete_map={"top": bot.RED, "other": bot.PINK}, hover_data=["state"],
                     labels={"value": hm, "hospital": ""}, height=max(300, 32 * len(hr2)))
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        fig.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)
        st.caption(f"🔎 Evidence: {hm_choices[hm]}, year = {hy} · {bot.SOURCE_FACILITY}. "
                   "Pusat Darah Negara is in Kuala Lumpur, which is why KL's total is so high. · Pusat Darah Negara terletak di KL, sebab itu jumlah KL sangat tinggi.")

# ================================================================ CALENDAR
with tab_cal:
    heading("Blood calendar", "Kalendar darah",
            "Every square is one day. Darker = more donations. Spot the busy weekends and the quiet holidays!",
            "Setiap petak ialah satu hari. Lebih gelap = lebih banyak derma. Cari hujung minggu yang sibuk dan cuti yang sunyi!")
    a, b = st.columns(2)
    cs = a.selectbox("State · Negeri", ["Malaysia"] + data["states"], key="cal_state")
    cy = b.selectbox("Year · Tahun", list(range(FULL, bot.FIRST_YEAR - 1, -1)), key="cal_year")
    cal = bot.daily_calendar(data, cs, cy)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    grid = cal.pivot_table(index="weekday", columns="week", values="daily", aggfunc="sum")
    dates = cal.pivot_table(index="weekday", columns="week", values="date", aggfunc="first")
    fig = px.imshow(grid.values, x=grid.columns, y=[days[i] for i in grid.index], aspect="auto",
                    color_continuous_scale=["#FBEFF0", "#EE8E9C", "#D81F3B", "#5C0714"], labels={"color": "donations"})
    fig.update_traces(customdata=dates.reindex_like(grid).map(lambda v: f"{v:%d %b %Y}" if pd.notna(v) else "").values,
                      hovertemplate="%{customdata}<br>%{z:,} donations<extra></extra>", xgap=3, ygap=3)
    fig.update_layout(height=290, xaxis_title="week of the year · minggu", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)
    top3 = cal.nlargest(3, "daily")
    low3 = cal.nsmallest(3, "daily")
    l, r = st.columns(2)
    l.markdown(f'<div class="card"><div class="h3">{B("🔥 Busiest days", "Hari paling sibuk")}</div>' +
               "".join(f"<div>{d:%a %d %b}: <b>{v:,}</b></div>" for d, v in zip(top3.date, top3.daily)) + "</div>", unsafe_allow_html=True)
    r.markdown(f'<div class="card"><div class="h3">{B("🧊 Quietest days", "Hari paling sunyi")}</div>' +
               "".join(f"<div>{d:%a %d %b}: <b>{v:,}</b></div>" for d, v in zip(low3.date, low3.daily)) + "</div>", unsafe_allow_html=True)
    st.caption(f"🔎 Evidence: daily, state = {cs}, year = {cy} · {bot.SOURCE_DONATIONS}")

    heading("What happens on festival days?", "Apa berlaku pada hari perayaan?",
            "Donations on the first day of each festival, compared with a normal day (median of the 2 weeks before and after).",
            "Derma pada hari pertama setiap perayaan, berbanding hari biasa (median 2 minggu sebelum dan selepas).")
    fest = st.radio("Festival · Perayaan", list(bot.FESTIVALS), horizontal=True)
    fe = bot.festive_effect(data, fest, cs)
    fig = px.bar(fe, x="year", y=["normal day", "on the day"], barmode="group",
                 color_discrete_map={"normal day": bot.GREY, "on the day": bot.RED},
                 labels={"value": "donations · derma", "variable": ""}, title=f"{fest}: {cs}")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)
    med = fe["change %"].median()
    st.markdown(f'<div class="card">{B(f"Typical change on <b>{fest}</b>: <b>{med:+.0f}%</b> compared with a normal day ({len(fe)} years, 2015–2025).", f"Perubahan biasa pada <b>{fest}</b>: <b>{med:+.0f}%</b> berbanding hari biasa ({len(fe)} tahun, 2015–2025).")}</div>',
                unsafe_allow_html=True)
    if fest == "Hari Raya Aidilfitri":
        ra = bot.ramadan_effect(data, cs)
        rmed = ra["change %"].median()
        rtxt = B(f"During <b>Ramadan</b> (the 29 days before Raya), average daily donations were <b>{rmed:+.0f}%</b> compared with the month before (median 2015–2025).",
                 f"Semasa <b>Ramadan</b> (29 hari sebelum Raya), purata derma harian ialah <b>{rmed:+.0f}%</b> berbanding bulan sebelumnya (median 2015–2025).")
        st.markdown('<div class="card">🌙 ' + rtxt + '</div>', unsafe_allow_html=True)
        with st.expander("Ramadan numbers by year · Angka Ramadan mengikut tahun"):
            st.dataframe(ra.round(1), width="stretch", hide_index=True)
    st.caption("Festival dates come from the Malaysian public holiday calendar. The data shows the pattern, not the reason. · "
               "Tarikh perayaan daripada kalendar cuti umum Malaysia. Data menunjukkan corak, bukan sebabnya.")
    with st.expander("🧾 Exact numbers · Angka tepat"):
        st.dataframe(fe.assign(date=fe["date"].dt.date).round(1), width="stretch", hide_index=True)

# ================================================================ TIME MACHINE
with tab_time:
    heading("Press play and watch 20 years of donations", "Tekan main dan lihat 20 tahun derma",
            "Each bar is a state. The partial latest year is left out so the comparison is fair.",
            "Setiap bar ialah negeri. Tahun terkini yang belum lengkap tidak dimasukkan supaya perbandingan adil.")
    choice_t = st.selectbox("Measure · Ukuran", list(METRIC_CHOICES), index=0, key="time_metric")
    mt = METRIC_CHOICES[choice_t]
    dt = bot.yearly_values(data, mt)
    dt = dt[(dt.state != "Malaysia") & (dt.year <= FULL)]
    fig = px.bar(dt, x="value", y="state", animation_frame="year", orientation="h", color="value",
                 color_continuous_scale=["#F7CDD3", "#D81F3B", "#5C0714"], range_x=[0, dt.value.max() * 1.1],
                 labels={"value": choice_t, "state": ""})
    fig.update_layout(height=540, yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)

# ================================================================ GEN Z STORY
with tab_story:
    heading("Darah Muda, Semakin Kurang?", "Is the young generation stepping back from blood donation?",
            "Gen Z here means first-time donors aged 17–24.", "Gen Z di sini bermaksud penderma kali pertama berumur 17–24.")
    states_pick = st.multiselect("Compare · Bandingkan", ["Malaysia"] + data["states"], default=["Malaysia", "Melaka"])
    gz = bot.yearly_values(data, "genz", states_pick)
    gz = gz[gz.year <= FULL]
    share = bot.yearly_values(data, "genz_share", states_pick)
    share = share[share.year <= FULL]
    l, r = st.columns(2)
    base = gz[gz.year == 2019].set_index("state")["value"]
    idx = gz.copy()
    idx["value"] = idx["value"] / idx["state"].map(base) * 100
    fig_idx = bot.line_chart(idx, "Gen Z new donors, indexed (2019 = 100)", "genz")
    fig_idx.update_layout(yaxis_title="2019 = 100")
    fig_idx.add_hline(y=100, line_dash="dot", line_color="#8D7476")
    l.plotly_chart(fig_idx, width="stretch", config={"displayModeBar": False}, theme=None)
    l.caption("Indexing lets a small state and the whole country share one scale: 50 means half of the 2019 level.")
    r.plotly_chart(bot.line_chart(share, "Gen Z as % of all new donors", "genz_share"), width="stretch", config={"displayModeBar": False}, theme=None)
    rows_html = ""
    for s_ in states_pick:
        v19 = gz[(gz.state == s_) & (gz.year == 2019)]["value"]
        vf = gz[(gz.state == s_) & (gz.year == FULL)]["value"]
        if not v19.empty and not vf.empty:
            chg = (vf.iloc[0] - v19.iloc[0]) / v19.iloc[0] * 100
            rows_html += f"<div><b>{s_}:</b> {v19.iloc[0]:,.0f} Gen Z new donors in 2019 → <b>{vf.iloc[0]:,.0f}</b> in {FULL} (<b>{chg:+.1f}%</b>)</div>"
    if rows_html:
        st.markdown(f'<div class="card">{rows_html}</div>', unsafe_allow_html=True)
    st.caption("The data shows what changed. It cannot tell us why (e.g. COVID-19, campus campaigns). · Data menunjukkan apa yang berubah, bukan sebabnya.")

# ================================================================ GAME
with tab_game:
    heading("Guess the number", "Teka nombor", "Guess first, then let the data reveal the truth!", "Teka dulu, kemudian biar data dedahkan jawapan!")
    if "game" not in st.session_state or st.button("🎲 New question · Soalan baru"):
        s_ = random.choice(data["states"])
        y_ = random.randint(2012, FULL)
        gm = random.choice(["donations", "new_donors", "genz"])
        st.session_state.game = {"state": s_, "year": y_, "metric": gm, "answer": bot.lookup(data, gm, s_, y_), "revealed": False}
    g = st.session_state.game
    label = bot.METRICS[g["metric"]][2]
    st.markdown(f'<div class="card"><div class="h3">How many <span style="color:var(--blood)">{label}</span> were there in <b>{g["state"]}</b> in <b>{g["year"]}</b>?</div>'
                f'<span class="ms">Berapa {bot.BM_LABELS.get(label, label)} di {g["state"]} pada {g["year"]}?</span></div>', unsafe_allow_html=True)
    guess = st.number_input("Your guess · Tekaan anda", min_value=0, step=500, value=0)
    if st.button("Reveal the answer · Dedahkan jawapan", type="primary"):
        g["revealed"] = True
    if g["revealed"]:
        ans = g["answer"]
        off = abs(guess - ans) / ans * 100 if ans else 0
        st.markdown(f'<div class="card"><div class="big-num">{ans:,.0f}</div>{B(f"Real answer · your guess was {off:.0f}% off", f"Jawapan sebenar · tekaan anda tersasar {off:.0f}%")}</div>',
                    unsafe_allow_html=True)
        if off <= 10:
            st.balloons()
            st.success("Amazing! Within 10%. You're a data expert 🩸 · Hebat! Dalam lingkungan 10%.")
        elif off <= 30:
            st.info("Not bad! Within 30%. · Boleh tahan! Dalam lingkungan 30%.")
        else:
            st.warning("Quite far! That's why we check the data instead of guessing. · Jauh lagi! Sebab itu kita semak data, bukan meneka.")
        st.caption(f"Evidence: {bot.METRICS[g['metric']][1]} · state = {g['state']} · year = {g['year']} · {bot.METRICS[g['metric']][4]}")

# ================================================================ EXHIBITION MODE
with tab_show:
    heading("Exhibition mode", "Mod pameran",
            "Turn this on when nobody is typing. It shows a new fact or chart every 8 seconds. Tip: hide the sidebar and go full screen.",
            "Hidupkan bila tiada pelawat menaip. Fakta atau carta baru setiap 8 saat. Tip: sembunyikan sidebar dan guna skrin penuh.")
    if st.toggle("▶ Start the slideshow · Mula tayangan", key="show_on"):

        @st.fragment(run_every=8)
        def slideshow():
            slides = [("fact", f) for f in FACTS] + [("chart", k) for k in ("rank", "genz", "types", "festive", "survey")]
            kind, item = slides[int(time.time() // 8) % len(slides)]
            if kind == "fact":
                txt = re.sub(r"\*\*(.+?)\*\*", r"<span style='color:#B0122A'>\1</span>", item[0])
                st.markdown(f"<div class='card' style='padding:3rem 2rem;text-align:center;font:700 2.3rem/1.35 var(--display)'>"
                            f"💡<br>{txt}<br><span style='font:400 1rem var(--body);color:#8D7476'>🔎 {item[1]}</span></div>",
                            unsafe_allow_html=True)
            elif item == "rank":
                df_ = bot.rank(data, "per_capita", FULL)
                st.plotly_chart(bot.bar_chart(df_, [df_.iloc[0]["state"]], f"Donations per 1,000 adults, {FULL}", "per_capita"),
                                width="stretch", key="show_rank", config={"displayModeBar": False}, theme=None)
            elif item == "genz":
                g_ = bot.yearly_values(data, "genz", ["Malaysia"])
                g_ = g_[g_.year <= FULL]
                st.plotly_chart(bot.line_chart(g_, "Gen Z first-time donors in Malaysia", "genz"), width="stretch", key="show_genz",
                                config={"displayModeBar": False}, theme=None)
            elif item == "types":
                r_ = bot.answer(f"blood types Malaysia {FULL}", data, lang=st.session_state.lang)
                st.plotly_chart(r_["chart"], width="stretch", key="show_types", config={"displayModeBar": False}, theme=None)
            elif item == "survey":
                if survey is not None and len(survey):
                    s2 = bot.survey_summary(survey)
                    st.markdown(f"<div class='card' style='padding:3rem 2rem;text-align:center'><div class='big-num'>{s2['n']}</div>"
                                f"<div class='h3'>{B('people have answered our survey so far', 'orang telah menjawab tinjauan kami setakat ini')}</div>"
                                f"<p style='margin-top:10px'>{SURVEY_URL.replace('https://', '')}</p></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='card' style='padding:3rem 2rem;text-align:center;font:700 2rem var(--display)'>📋 "
                                f"{B('Take our 2-minute survey', 'Jawab tinjauan 2 minit kami')}<p style='font:500 1.1rem var(--body)'>"
                                f"{SURVEY_URL.replace('https://', '')}</p></div>", unsafe_allow_html=True)
            else:
                fe2 = bot.festive_effect(data, "Hari Raya Aidilfitri")
                fig2 = px.bar(fe2, x="year", y=["normal day", "on the day"], barmode="group",
                              color_discrete_map={"normal day": bot.GREY, "on the day": bot.RED},
                              title="Hari Raya Aidilfitri: donations almost stop for a day")
                st.plotly_chart(fig2, width="stretch", key="show_fest", config={"displayModeBar": False}, theme=None)
            st.progress((int(time.time() // 8) % len(slides) + 1) / len(slides))
            st.markdown(f"<div style='text-align:center;font-size:1.2rem'>🩸 {B('Ask me anything in the Ask DarahBot tab!', 'Tanya saya apa sahaja di tab Ask DarahBot!')}</div>",
                        unsafe_allow_html=True)

        slideshow()

# ================================================================ ABOUT
with tab_about:
    heading("About the data", "Tentang data")
    st.markdown(f"""
<div class="card">
<b>Dataset 1, donations_state.csv:</b> daily blood donations per state, split by blood type, location, donor type and social group.<br>
<b>Dataset 2, newdonors_state.csv:</b> daily number of first-time donors per state, split by age group.<br>
<b>Dataset 3, donations_facility.csv:</b> daily donations at each of the 22 government blood banks.<br>
<b>Dataset 4, population.csv:</b> state population (DOSM 2020 estimates), used for fair "per 1,000 adults" rates.<br>
<b>Our survey:</b> answers from dermadarah.jomana.my (anonymised: no names or emails are read).
<p class="note">Coverage: <b>{bot.FIRST_YEAR}</b> to <b>{data['last_date']:%d %B %Y}</b> · States: {', '.join(data['states'])}</p>
</div>
<div class="card"><div class="h3">{B("Limitations: what this bot cannot do", "Had: apa yang bot ini tidak boleh lakukan")}</div>
<ul>
<li>Perlis, Putrajaya and Labuan are not reported separately.</li>
<li>Donations are counted where the hospital/blood centre is, not where the donor lives (that's why KL is so high).</li>
<li>{data['latest_year']} is a partial year.</li>
<li>The data shows <i>how many</i>, never <i>why</i>. The bot refuses cause questions instead of guessing.</li>
<li>Population is a 2020 snapshot, so per-capita rates for other years are approximate.</li>
<li>"Can I donate?" uses 5 basic Pusat Darah Negara rules. It is a hypothesis, not a medical decision.</li>
</ul></div>
<p class="note">Made by <b>{CREDIT}</b> for the CSC649 Python Data Science Exhibition.</p>
""", unsafe_allow_html=True)
    st.markdown("**Preview of the raw data · Pratonton data mentah**")
    st.dataframe(data["donations"].tail(20), width="stretch", hide_index=True)
