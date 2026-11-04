"""
bot_engine.py  -  the "brain" of DarahBot
=========================================
This file has NO user interface. It only:
  1. loads the 3 CSV files with pandas
  2. reads a visitor's question and detects what they want (the "intent")
  3. runs a pandas query to compute the answer
  4. returns the answer + evidence + a chart

Every number the bot says comes from a pandas calculation in this file.
Nothing is typed in by hand and no AI model is used when the app runs.

app.py (the Streamlit chat screen) imports this file.
test_bot.py tests this file without opening the app.
"""

import re
import difflib
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

DATA_DIR = Path(__file__).parent / "data"

SOURCE_DONATIONS = "KKM / National Blood Centre (PDN), data-darah-public: donations_state.csv"
SOURCE_NEWDONORS = "KKM / National Blood Centre (PDN), data-darah-public: newdonors_state.csv"
SOURCE_FACILITY = "KKM / National Blood Centre (PDN), data-darah-public: donations_facility.csv"
SOURCE_POP = "KKM covid19-public static/population.csv (DOSM 2020 estimates)"

FIRST_YEAR = 2006

# Colours: the same blood-red theme as our survey website (dermadarah.jomana.my)
RED = "#B0122A"        # main blood red
RED2 = "#D81F3B"       # brighter red
WINE = "#5C0714"       # dark wine
PINK = "#EE8E9C"       # soft pink
BLUSH = "#F7CDD3"      # very light pink
GREY = "#E6D7D4"       # warm grey for "other" bars
INK = "#2B0F13"        # text
MUTED = "#8D7476"      # grey text (Malay lines)
OK_GREEN = "#1D8A5A"
AMBER = "#C0620F"
SERIES = [RED, WINE, PINK, "#D9A441", "#6B7A8F", "#E35D6A"]

# One Plotly style ("template") used by every chart in the app
pio.templates["darah"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, system-ui, sans-serif", size=13, color=INK),
    title=dict(font=dict(family="Bricolage Grotesque, Inter, sans-serif", size=18, color=INK), x=0, xanchor="left"),
    colorway=SERIES,
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(gridcolor="#F1E4E1", zerolinecolor="#EADAD6", linecolor="#EADAD6", tickfont=dict(color=MUTED)),
    yaxis=dict(gridcolor="#F1E4E1", zerolinecolor="#EADAD6", linecolor="#EADAD6", tickfont=dict(color=MUTED)),
    hoverlabel=dict(bgcolor="white", bordercolor=RED, font=dict(family="Inter, sans-serif", color=INK)),
    legend=dict(orientation="h", yanchor="top", y=-0.2, x=0, title_text=""),
    colorscale=dict(sequential=[[0, "#FBEFF0"], [0.5, RED2], [1, WINE]]),
))
pio.templates.default = "plotly_white+darah"


# ---------------------------------------------------------------------------
# 1. LOAD DATA
# ---------------------------------------------------------------------------
def load_data(data_dir=DATA_DIR):
    """Read the 3 CSV files and add a 'year' column. Returns a dictionary."""
    donations = pd.read_csv(Path(data_dir) / "donations_state.csv", parse_dates=["date"])
    newdonors = pd.read_csv(Path(data_dir) / "newdonors_state.csv", parse_dates=["date"])
    population = pd.read_csv(Path(data_dir) / "population.csv")
    facility = pd.read_csv(Path(data_dir) / "donations_facility.csv", parse_dates=["date"])
    hospital_state = pd.read_csv(Path(data_dir) / "hospital_state.csv")
    facility = facility.merge(hospital_state, on="hospital", how="left")
    facility["year"] = facility["date"].dt.year

    donations["year"] = donations["date"].dt.year
    newdonors["year"] = newdonors["date"].dt.year

    # Drop duplicate rows if any (robustness)
    donations = donations.drop_duplicates(subset=["date", "state"])
    newdonors = newdonors.drop_duplicates(subset=["date", "state"])

    last_date = donations["date"].max()
    states = sorted(s for s in donations["state"].unique() if s != "Malaysia")

    return {
        "donations": donations,
        "newdonors": newdonors,
        "population": population,
        "facility": facility,
        "last_date": last_date,
        "latest_year": int(last_date.year),
        # the latest year that is complete (has 31 December)
        "latest_full_year": int(last_date.year) if (last_date.month == 12 and last_date.day == 31) else int(last_date.year) - 1,
        "states": states,
    }


# ---------------------------------------------------------------------------
# 2. WHAT CAN BE MEASURED  (metric = one column in a dataset)
# ---------------------------------------------------------------------------
# key: (dataset, column, label, unit, source)
METRICS = {
    "donations":  ("donations", "daily", "blood donations", "donations", SOURCE_DONATIONS),
    "new_donors": ("newdonors", "total", "new donors", "people", SOURCE_NEWDONORS),
    "genz":       ("newdonors", "17-24", "Gen Z new donors (age 17-24)", "people", SOURCE_NEWDONORS),
    "blood_a":    ("donations", "blood_a", "type A donations", "donations", SOURCE_DONATIONS),
    "blood_b":    ("donations", "blood_b", "type B donations", "donations", SOURCE_DONATIONS),
    "blood_o":    ("donations", "blood_o", "type O donations", "donations", SOURCE_DONATIONS),
    "blood_ab":   ("donations", "blood_ab", "type AB donations", "donations", SOURCE_DONATIONS),
    "students":   ("donations", "social_student", "donations by students", "donations", SOURCE_DONATIONS),
    "mobile":     ("donations", "location_mobile", "donations at mobile drives", "donations", SOURCE_DONATIONS),
    "regular":    ("donations", "donations_regular", "donations by regular donors", "donations", SOURCE_DONATIONS),
    # computed metrics (not a single column)
    "per_capita": ("computed", None, "donations per 1,000 adults", "per 1,000 adults", SOURCE_DONATIONS + " + " + SOURCE_POP),
    "genz_share": ("computed", None, "share of new donors who are Gen Z (17-24)", "%", SOURCE_NEWDONORS),
}

# Words a visitor might type (English + Bahasa Melayu) -> metric key.
# Checked in this order, so more specific words come first.
METRIC_KEYWORDS = [
    ("genz_share", [r"\b(percent|percentage|share|peratus|%|proportion|bahagian)\b.*\b(gen ?z|young|muda|youth|belia|17-24)\b",
                    r"\b(gen ?z|young|muda|youth|belia|17-24)\b.*\b(percent|percentage|share|peratus|%|proportion)\b"]),
    ("genz",       [r"\bgen ?z\b", r"\byoung\b", r"\byouth\b", r"\bmuda\b", r"\bbelia\b", r"17-24", r"\bremaja\b"]),
    ("per_capita", [r"per ?capita", r"per (1,?000|thousand|person|people|orang)", r"(bagi )?setiap (1,?000|seribu)", r"per seribu", r"\brate\b", r"\bkadar\b", r"\bfair\b"]),
    ("new_donors", [r"new donor", r"first[- ]time", r"penderma baru", r"\bbaru\b", r"\bnew\b"]),
    ("blood_ab",   [r"\b(type|jenis|group|kumpulan)\s*ab\b", r"\bab\s*(blood|darah|\+|-)", r"\bab\b"]),
    ("blood_a",    [r"\b(type|jenis|group|kumpulan)\s*a\b", r"\ba\+", r"\bblood a\b", r"\bdarah a\b"]),
    ("blood_b",    [r"\b(type|jenis|group|kumpulan)\s*b\b", r"\bb\+", r"\bblood b\b", r"\bdarah b\b"]),
    ("blood_o",    [r"\b(type|jenis|group|kumpulan)\s*o\b", r"\bo\+", r"\bblood o\b", r"\bdarah o\b"]),
    ("students",   [r"student", r"pelajar", r"universit", r"\buni\b"]),
    ("mobile",     [r"mobile", r"bergerak", r"\bdrive\b", r"\bcampaign\b", r"kempen"]),
    ("regular",    [r"regular", r"\btetap\b", r"repeat"]),
    ("donations",  [r"donation", r"\bderma", r"sumbangan", r"\bbags?\b", r"\bbeg\b"]),
]

# Different ways people write state names -> official name in the dataset
STATE_ALIASES = {
    "kl": "W.P. Kuala Lumpur", "kuala lumpur": "W.P. Kuala Lumpur", "wp kuala lumpur": "W.P. Kuala Lumpur",
    "penang": "Pulau Pinang", "pulau pinang": "Pulau Pinang", "pinang": "Pulau Pinang",
    "n9": "Negeri Sembilan", "ns": "Negeri Sembilan", "negeri sembilan": "Negeri Sembilan", "nogori": "Negeri Sembilan",
    "malacca": "Melaka", "jb": "Johor", "johore": "Johor",
    "malaysia": "Malaysia", "nationwide": "Malaysia", "national": "Malaysia", "seluruh negara": "Malaysia",
}
# States that exist in Malaysia but are NOT reported separately in this dataset
NOT_IN_DATA = {"perlis": "Perlis", "putrajaya": "Putrajaya", "labuan": "Labuan"}


# ---------------------------------------------------------------------------
# 3. UNDERSTAND THE QUESTION
# ---------------------------------------------------------------------------
def find_states(text, states):
    """
    Return (list of official state names found, list of fuzzy corrections made).
    Handles aliases (KL, Penang) and spelling mistakes (Melak -> Melaka).
    """
    text = text.lower()
    found, corrections = [], []

    def add(name, pos):
        if name not in [f[0] for f in found]:
            found.append((name, pos))

    # 1) exact names and aliases
    for name in states + ["Malaysia"]:
        short = name.lower().replace("w.p. ", "")
        m = re.search(r"\b" + re.escape(short) + r"\b", text)
        if m:
            add(name, m.start())
    for alias, name in STATE_ALIASES.items():
        m = re.search(r"\b" + re.escape(alias) + r"\b", text)
        if m:
            add(name, m.start())

    # 2) fuzzy match each word / pair of words that was not already matched
    words = re.findall(r"[a-z]+", text)
    candidates = {n.lower().replace("w.p. ", ""): n for n in states}
    candidates.update({a: n for a, n in STATE_ALIASES.items() if len(a) > 3})
    stop = {"compare", "between", "donor", "donors", "blood", "which", "state", "states", "highest", "lowest",
            "average", "students", "student", "regular", "mobile", "malay", "males", "darah", "negeri", "about",
            "trend", "years", "type", "share", "change", "people"}
    chunks = words + [" ".join(p) for p in zip(words, words[1:])]
    already = " ".join(n.lower() for n, _ in found)
    for chunk in chunks:
        if len(chunk) < 4 or chunk in stop or chunk in already:
            continue
        match = difflib.get_close_matches(chunk, candidates.keys(), n=1, cutoff=0.8)
        if match:
            name = candidates[match[0]]
            if name not in [f[0] for f in found]:
                add(name, text.find(chunk))
                corrections.append((chunk, name))

    found.sort(key=lambda x: x[1])  # keep the order the visitor typed them
    return [f[0] for f in found], corrections


def find_years(text):
    """Return every 4-digit year in the question (as integers)."""
    return [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2}|21\d{2})\b", text)]


def find_metric(text):
    """Return the metric key the visitor asked about, or None if not stated."""
    t = text.lower()
    for key, patterns in METRIC_KEYWORDS:
        if any(re.search(p, t) for p in patterns):
            return key
    return None


def detect_intent(text):
    """Decide WHAT KIND of question this is, using keywords (rule-based)."""
    t = text.lower()
    if re.search(r"\b(why|kenapa|mengapa|sebab|cause|caused|reason|punca)\b", t):
        return "cause"
    if re.search(r"\b(survey|tinjauan|respondents?|responden|questionnaire|soal selidik|borang)\b", t):
        return "survey"
    if re.search(r"\b(eligible|eligibility|layak|kelayakan|can i donate|can i give blood|am i allowed|boleh saya derma|bolehkah saya|boleh ke saya|"
                 r"saya boleh (derma|menderma)|boleh tak saya|boleh ke derma|who can (donate|give)|siapa (yang )?boleh (derma|menderma)|"
                 r"syarat|requirements?|criteria|kriteria|qualif\w*)\b", t):
        return "eligible"
    if re.search(r"\b(predict|forecast|will be|next year|future|ramal|akan datang|tahun depan)\b", t):
        return "predict"
    if re.search(r"\b(blood types?|jenis darah|types of blood|blood groups?|kumpulan darah|breakdown|composition|pecahan)\b", t) \
            or re.search(r"\b(type|jenis)\s*(a|b|o|ab)\b", t):
        return "breakdown"
    if re.search(r"\b(compare|comparison|vs\.?|versus|banding|bandingkan|beza|difference)\b", t):
        return "compare"
    if re.search(r"\b(trend|over the years|over time|changed?|berubah|sejak|since|growth|increase|increased|decrease|decreased|naik|turun|go(es)? up|went up|go(es)? down|went down|rise|rose|fall|fell|drop(ped)?|meningkat|menurun)\b", t) \
            or (len(set(re.findall(r"\b(?:19|20)\d{2}\b", t))) >= 2 and re.search(r"\b(from|dari|daripada|to|hingga|ke)\b", t)):
        return "trend"
    if re.search(r"\b(highest|most|top|lowest|least|fewest|rank|ranking|paling|tertinggi|terendah|terbanyak|tersedikit|best|worst|second|2nd|third|3rd|kedua|ketiga|tempat|came)\b", t):
        return "rank"
    if re.search(r"\b(average|mean|purata|summary|ringkasan|overall|total)\b", t):
        return "summary"
    if re.search(r"^\s*(hi|hello|hai|helo|assalamualaikum|salam|help|tolong)\b", t):
        return "greet"
    return "lookup"


# ---------------------------------------------------------------------------
# 4. QUERY FUNCTIONS  (pandas does the maths here)
# ---------------------------------------------------------------------------
def yearly_values(data, metric, states=None):
    """
    Core query: returns a table with columns [state, year, value]
    for one metric, summed per year. Works for normal and computed metrics.
    """
    dataset, column, *_ = METRICS[metric]

    if metric == "per_capita":
        d = data["donations"].groupby(["state", "year"], as_index=False)["daily"].sum()
        pop = data["population"][["state", "pop_18"]]
        d = d.merge(pop, on="state", how="left")
        d["value"] = d["daily"] / d["pop_18"] * 1000
        d = d.dropna(subset=["value"])
    elif metric == "genz_share":
        d = data["newdonors"].groupby(["state", "year"], as_index=False)[["17-24", "total"]].sum()
        d["value"] = d["17-24"] / d["total"] * 100
        d = d.replace([float("inf")], pd.NA).dropna(subset=["value"])
    else:
        d = data[dataset].groupby(["state", "year"], as_index=False)[column].sum()
        d = d.rename(columns={column: "value"})

    if states:
        d = d[d["state"].isin(states)]
    return d[["state", "year", "value"]]


def cap(text):
    return text[0].upper() + text[1:]


def fmt(value, metric):
    unit = METRICS[metric][3]
    if unit == "%":
        return f"{value:.1f}%"
    if unit == "per 1,000 adults":
        return f"{value:.1f}"
    return f"{value:,.0f}"


def year_note(data, year, lang="en"):
    if year == data["latest_year"] and year != data["latest_full_year"]:
        if lang == "bm":
            return f" (tahun separa: data hanya sehingga {data['last_date']:%d %b %Y})"
        return f" (partial year: data only up to {data['last_date']:%d %b %Y})"
    return ""


def lookup(data, metric, state, year):
    """LOOKUP: value of one metric for one state in one year."""
    d = yearly_values(data, metric, [state])
    row = d[d["year"] == year]
    if row.empty:
        return None
    return float(row["value"].iloc[0])


def compare(data, metric, state_a, state_b, year):
    """COMPARISON: two states, same metric, same year."""
    a = lookup(data, metric, state_a, year)
    b = lookup(data, metric, state_b, year)
    if a is None or b is None:
        return None
    return {"a": a, "b": b, "diff": a - b, "ratio": (a / b) if b else None}


def rank(data, metric, year, lowest=False):
    """HIGHEST / LOWEST: all states (excluding the Malaysia total), sorted."""
    d = yearly_values(data, metric)
    d = d[(d["year"] == year) & (d["state"] != "Malaysia")]
    return d.sort_values("value", ascending=lowest).reset_index(drop=True)


def summary(data, metric, year):
    """AVERAGE / SUMMARY across states for one year."""
    d = rank(data, metric, year)
    if d.empty:
        return None
    return {"mean": d["value"].mean(), "total": d["value"].sum(), "n": len(d),
            "max": d.iloc[0], "min": d.iloc[-1], "table": d}


def hospital_ranking(data, year, column="daily", state=None):
    """HOSPITAL LEADERBOARD: donations per blood bank for one year (optionally one state)."""
    f = data["facility"]
    f = f[f["year"] == year]
    if state:
        f = f[f["state"] == state]
    g = f.groupby(["hospital", "state"], as_index=False)[column].sum().rename(columns={column: "value"})
    return g.sort_values("value", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 5. CHARTS  (always drawn from the same filtered table used for the answer)
# ---------------------------------------------------------------------------
def bar_chart(df, highlight, title, metric):
    df = df.copy()
    df["colour"] = df["state"].apply(lambda s: "selected" if s in highlight else "other")
    fig = px.bar(df, x="value", y="state", orientation="h", color="colour",
                 color_discrete_map={"selected": RED, "other": GREY},
                 text=df["value"].apply(lambda v: fmt(v, metric)), title=title)
    fig.update_layout(showlegend=False, yaxis={"categoryorder": "total ascending", "title": ""},
                      xaxis_title=METRICS[metric][3], height=max(260, 34 * len(df)), margin=dict(l=10, r=10, t=50, b=10))
    fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
    return fig


def line_chart(df, title, metric):
    fig = px.line(df, x="year", y="value", color="state", markers=True, title=title,
                  color_discrete_sequence=SERIES)
    fig.update_layout(yaxis_title=METRICS[metric][3], xaxis_title="", height=360, margin=dict(l=10, r=10, t=60, b=10))
    fig.update_traces(line_width=3, marker_size=7)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.12, x=0), legend_title_text="")
    return fig


# ---------------------------------------------------------------------------
# 5b. DONOR RULES + OUR OWN SURVEY  (new in the October 2026 update)
# ---------------------------------------------------------------------------
SOURCE_RULES = ("Pusat Darah Negara donor rules (as summarised by SAYS, 2025 and Malaysia4u). "
                "These are guideline rules, not part of the KKM dataset.")
SOURCE_SURVEY = "Our CSC649 survey, dermadarah.jomana.my (live, anonymised: no names or emails)"


def check_eligibility(age, weight_kg, sleep_hours, tattoo_12m, meds_days):
    """
    The same 5 basic rules our survey uses for first-time donors.
    Returns a list of (passed, rule in English, rule in Malay).
    This is a HYPOTHESIS only: the blood bank staff make the real check.
    """
    return [
        (18 <= age <= 60, "Age 18 to 60", "Umur 18 hingga 60"),
        (weight_kg >= 45, "Weight 45 kg or more", "Berat 45 kg ke atas"),
        (sleep_hours >= 5, "At least 5 hours of sleep", "Tidur sekurang-kurangnya 5 jam"),
        (not tattoo_12m, "No tattoo, piercing or acupuncture in 12 months", "Tiada tatu, tindik atau akupunktur dalam 12 bulan"),
        (meds_days == 0, "No long-term medicine", "Tiada ubat jangka panjang"),
    ]


def load_survey(url, timeout=8):
    """
    Read our survey answers from the website's anonymised CSV export.
    Returns a DataFrame, or None if the link is missing or the website can't be reached.
    """
    if not url:
        return None
    try:
        df = pd.read_csv(url, storage_options={"User-Agent": "DarahBot"}) if url.startswith("http") else pd.read_csv(url)
    except Exception:
        return None
    if "ever_donated" not in df.columns:      # e.g. "no responses yet"
        return df.iloc[0:0].assign(ever_donated=pd.Series(dtype=str))
    for c in ("name", "email"):               # never keep personal details, even if the link had them
        if c in df.columns:
            df = df.drop(columns=c)
    for c in ("age", "weight_kg", "sleep_hours", "meds_days_per_month", "willingness", "times_donated", "months_since_last"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def survey_summary(df):
    """Counts used by the chat answer and the 'Our survey' tab."""
    donors = df[df["ever_donated"] == "Yes"]
    never = df[df["ever_donated"] == "No"]
    if len(never):
        ok = never.apply(lambda r: all(p for p, *_ in check_eligibility(
            r["age"], r["weight_kg"], r["sleep_hours"], r["tattoo_12m"] == "Yes", r["meds_days_per_month"])), axis=1)
        likely = int(ok.sum())
    else:
        likely = 0
    return {
        "n": len(df), "donors": len(donors), "never": len(never),
        "accepted": int((donors.get("last_result") == "Accepted").sum()) if len(donors) else 0,
        "deferred": int((donors.get("last_result") == "Deferred").sum()) if len(donors) else 0,
        "likely": likely, "not_yet": len(never) - likely,
        "avg_willing": float(df["willingness"].mean()) if len(df) else None,
    }


# ---------------------------------------------------------------------------
# 6. THE MAIN FUNCTION: question in -> answer out
# ---------------------------------------------------------------------------
FOLLOWUP = re.compile(r"^\s*(what about|how about|and|then|same for|bagaimana dengan|macam mana dengan|kalau|apa pula)\b|\bpula\b", re.I)

# Bahasa Melayu names for labels and units (used when the visitor picks BM)
BM_LABELS = {
    "blood donations": "derma darah", "new donors": "penderma baru",
    "Gen Z new donors (age 17-24)": "penderma baru Gen Z (umur 17-24)",
    "type A donations": "derma darah jenis A", "type B donations": "derma darah jenis B",
    "type O donations": "derma darah jenis O", "type AB donations": "derma darah jenis AB",
    "donations by students": "derma oleh pelajar", "donations at mobile drives": "derma di kempen bergerak",
    "donations by regular donors": "derma oleh penderma tetap",
    "donations per 1,000 adults": "derma bagi setiap 1,000 orang dewasa",
    "share of new donors who are Gen Z (17-24)": "peratus penderma baru yang Gen Z (17-24)",
}
BM_UNITS = {"donations": "derma", "people": "orang", "per 1,000 adults": "bagi setiap 1,000 dewasa", "%": "%"}


def is_followup(question, intent, understood_something):
    """A 'what about...' question, or a short one that mentions a state/year/measure, continues the previous one."""
    if not understood_something:
        return False
    return bool(FOLLOWUP.search(question)) or (intent == "lookup" and len(question.split()) <= 3)


# ---------------------------------------------------------------------------
# DONOR RULES (basic questions: age, weight, sleep, tattoo, fasting, how often, lives)
# The same rules as our survey and quiz (Pusat Darah Negara guidelines). Not from the KKM dataset.
# ---------------------------------------------------------------------------
_DONATE_WORDS = r"(derma|donat|donor|penderma|darah|blood)"


def _num_near(t, units):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:" + units + r")\b", t)
    return float(m.group(1)) if m else None


def rule_answer(question, lang="en"):
    """Answer a basic donor-rule question, or return None if it is not one."""
    t = question.lower()
    bm = lang == "bm"
    T = (lambda en, ms: ms if bm else en)
    about_donating = re.search(_DONATE_WORDS, t)
    lines, rules = [], []

    # age: "umur 17 boleh derma?", "can a 16 year old donate", "minimum age", "how old"
    age = None
    m = re.search(r"(?:umur|age|aged|berumur)\s*(\d{1,3})\b|(\d{1,3})\s*(?:years?|yrs?)[\s-]*old\b|(\d{1,3})\s*y/?o\b"
                  r"|(?:saya|aku|i am|i'm|im|anak saya|my (?:son|daughter|child|kid) is)\s+(\d{1,2})\b", t)
    if m:
        age = int(m.group(1) or m.group(2) or m.group(3) or m.group(4))
        if m.group(4) and re.search(r"(berat|weight|weigh|tidur|sleep)\s*(badan\s*)?(saya|aku|i am|i'm)\s*\d", t):
            age = None                 # "berat saya 50" is a weight, not an age
    age_group_q = re.search(r"\b(group|groups|kumpulan|gen ?z|generation|bracket|17\s*[-–]\s*24)\b", t)
    if not age_group_q and (age is not None or re.search(r"\b(umur|how old|berapa umur|old enough|minimum age|maximum age|age limit|had umur)\b", t)):
        rules.append("age")
        if age is None:
            lines.append(T("**Age:** 18 to 60 years old. At **17** you can donate with your parent's or guardian's written consent. "
                           "Regular donors who are healthy can continue up to 65.",
                           "**Umur:** 18 hingga 60 tahun. Pada umur **17** anda boleh menderma dengan kebenaran bertulis ibu bapa atau penjaga. "
                           "Penderma tetap yang sihat boleh terus menderma sehingga 65 tahun."))
        elif age < 17:
            lines.append(T(f"**At {age}: not yet.** The minimum age is 17 (with parent's consent) and 18 on your own. "
                           "Thank you for wanting to help: you can still bring your family and friends!",
                           f"**Umur {age}: belum lagi.** Umur minimum ialah 17 tahun (dengan kebenaran ibu bapa) dan 18 tahun tanpa kebenaran. "
                           "Terima kasih kerana mahu membantu: anda masih boleh ajak keluarga dan rakan!"))
        elif age == 17:
            lines.append(T("**At 17: yes, with your parent's or guardian's written consent.** From 18 you can donate on your own "
                           "(you also need to weigh at least 45 kg and be healthy).",
                           "**Umur 17: boleh, dengan kebenaran bertulis ibu bapa atau penjaga.** Mulai 18 tahun anda boleh menderma sendiri "
                           "(berat sekurang-kurangnya 45 kg dan sihat)."))
        elif age <= 60:
            lines.append(T(f"**At {age}: yes, your age is fine** (18 to 60). You also need to weigh at least 45 kg and be healthy on the day.",
                           f"**Umur {age}: boleh, umur anda sesuai** (18 hingga 60). Anda juga perlu berat sekurang-kurangnya 45 kg dan sihat pada hari itu."))
        elif age <= 65:
            lines.append(T(f"**At {age}: only if you are already a regular donor** and healthy. First-time donors must be 60 or younger.",
                           f"**Umur {age}: hanya jika anda penderma tetap** dan sihat. Penderma kali pertama mesti 60 tahun ke bawah."))
        else:
            lines.append(T(f"**At {age}: usually not.** The upper limit is 60 for first-time donors and 65 for regular donors.",
                           f"**Umur {age}: biasanya tidak.** Had umur ialah 60 tahun untuk penderma kali pertama dan 65 tahun untuk penderma tetap."))

    w = _num_near(t, r"kg|kilo|kilogram")
    if w is None:                      # "berat 40", "weight is 40", "berat saya 40"
        mw = re.search(r"\b(?:berat|weight|weigh|weighs)\s*(?:badan\s*)?(?:saya\s*|is\s*|:\s*|only\s*|hanya\s*)?(\d{2,3}(?:\.\d+)?)\b", t)
        w = float(mw.group(1)) if mw else None
    if w is not None or re.search(r"\b(berat|weight|weigh|kurus|thin)\b", t):
        rules.append("weight")
        if w is None:
            lines.append(T("**Weight:** at least **45 kg**.", "**Berat:** sekurang-kurangnya **45 kg**."))
        else:
            ok = w >= 45
            lines.append(T(f"**{w:g} kg: {'yes, that is fine' if ok else 'not yet'}.** You need at least 45 kg.",
                           f"**{w:g} kg: {'boleh, sesuai' if ok else 'belum lagi'}.** Berat minimum ialah 45 kg."))

    h = _num_near(t, r"jam|hours?|hrs?|h")
    if re.search(r"\b(tidur|sleep|slept|rest|rehat)\b", t):
        rules.append("sleep")
        if h is None:
            lines.append(T("**Sleep:** at least **5 hours** the night before.", "**Tidur:** sekurang-kurangnya **5 jam** pada malam sebelumnya."))
        else:
            ok = h >= 5
            lines.append(T(f"**{h:g} hours of sleep: {'fine' if ok else 'not enough'}.** You need at least 5 hours the night before.",
                           f"**Tidur {h:g} jam: {'cukup' if ok else 'tidak cukup'}.** Perlu sekurang-kurangnya 5 jam pada malam sebelumnya."))

    if re.search(r"\b(tattoo|tatu|piercing|pierce|tindik|acupuncture|akupunktur)", t):
        rules.append("tattoo")
        lines.append(T("**Tattoo, piercing or acupuncture:** wait **12 months** before donating.",
                       "**Tatu, tindik atau akupunktur:** tunggu **12 bulan** sebelum menderma."))

    if re.search(r"(puasa|\bfasting\b|\bfast\b|ramadan|ramadhan|\blapar\b|empty stomach|\bmakan\b|\beat\b)", t) and about_donating:
        rules.append("fasting")
        lines.append(T("**No, not on an empty stomach.** **Fasting / empty stomach:** don't donate on an empty stomach. Eat a proper meal and drink plenty of water first "
                       "(during Ramadan, donate after breaking your fast).",
                       "**Tidak, jangan dengan perut kosong.** **Puasa / perut kosong:** jangan menderma dengan perut kosong. Makan dengan baik dan minum banyak air dahulu "
                       "(pada bulan Ramadan, derma selepas berbuka)."))

    if re.search(r"\b(how often|berapa kerap|how many times can|selang|interval)\b", t) and about_donating:
        rules.append("interval")
        lines.append(T("**How often:** wait about **3 months** between whole blood donations.",
                       "**Berapa kerap:** tunggu kira-kira **3 bulan** antara derma darah penuh."))

    if re.search(r"\b(lives|nyawa|save lives?|selamatkan)\b", t) and about_donating:
        rules.append("lives")
        lines.append(T("**One donation can help save up to 3 lives**, because it is split into red cells, plasma and platelets.",
                       "**Satu derma boleh membantu menyelamatkan sehingga 3 nyawa**, kerana darah dipecahkan kepada sel darah merah, plasma dan platelet."))

    if not lines or not (about_donating or rules):
        return None
    if rules == ["sleep"] and not about_donating:
        return None
    text = "\n".join(f"- {x}" for x in lines) if len(lines) > 1 else lines[0]
    text += T("\n\nFor the full check, open **✅ Can I donate?**. The blood bank staff make the final decision on the day.",
              "\n\nUntuk semakan penuh, buka **✅ Can I donate?**. Kakitangan bank darah membuat keputusan akhir pada hari itu.")
    return {"text": text, "kind": "ok", "chart": None, "rows": None, "notes": [], "context": None,
            "goto": ["elig"], "evidence": {"value": ", ".join(rules), "field": "donor rules", "filters": "none", "unit": "rule", "source": SOURCE_RULES}}


# ---------------------------------------------------------------------------
# EVERYDAY QUESTIONS (general facts + a few extra data questions)
# ---------------------------------------------------------------------------
SOURCE_GENERAL = ("General blood donation guidance (Pusat Darah Negara / WHO). Not part of the KKM dataset; "
                  "the blood bank staff give the final advice.")
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MONTHS_MS = ["Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September", "Oktober", "November", "Disember"]
DAYS_MS = {"Monday": "Isnin", "Tuesday": "Selasa", "Wednesday": "Rabu", "Thursday": "Khamis", "Friday": "Jumaat", "Saturday": "Sabtu", "Sunday": "Ahad"}


def _reply(text, source=SOURCE_GENERAL, value="", field="general guidance", goto=None, chart=None, rows=None):
    return {"text": text, "kind": "ok", "chart": chart, "rows": rows, "notes": [], "context": None, "goto": goto or [],
            "evidence": {"value": value or "-", "field": field, "filters": "none", "unit": "-", "source": source}}


def faq_answer(question, data, lang="en"):
    """Answers the common questions visitors ask that are not a number lookup. Returns None if not one."""
    t = question.lower()
    bm = lang == "bm"
    T = (lambda en, ms: ms if bm else en)
    donate = re.search(_DONATE_WORDS, t)
    full = data["latest_full_year"]

    # small talk and about the project
    if re.fullmatch(r"\s*(thanks?|thank you|thx|tq|terima ?kasih|tenkiu|ok(ay)?|nice|cool|best|great|mantap|bagus)[\s!.]*", t):
        return _reply(T("You're welcome! Ask me anything else about blood donation, or try the **🏆 Quiz** to win a prize.",
                        "Sama-sama! Tanya apa-apa lagi tentang derma darah, atau cuba **🏆 Kuiz** untuk menang hadiah."), goto=["quiz"])
    if re.search(r"\b(what is darahbot|apa itu darahbot|who (made|built|created) (you|this|darahbot)|siapa (buat|cipta|bina)|about (you|darahbot)|what are you|siapa kamu|siapa awak)\b", t):
        return _reply(T("I'm **DarahBot**, a blood donation chatbot made by **Muhammad Amirrul Mukminin** and **Nur Ayuni Athirah** for the "
                        "CSC649 Data Science Exhibition. I answer from official KKM blood donation data and always show my evidence.",
                        "Saya **DarahBot**, chatbot derma darah yang dibina oleh **Muhammad Amirrul Mukminin** dan **Nur Ayuni Athirah** untuk "
                        "Pameran Sains Data CSC649. Saya menjawab daripada data rasmi KKM dan sentiasa menunjukkan bukti."),
                      source=SOURCE_DONATIONS, field="about DarahBot", goto=["about"])
    if re.search(r"\b(where.*data|data.*(from|source)|sumber data|data (dari|daripada) mana|accurate|tepat|betul ke data|reliable|boleh percaya)\b", t):
        return _reply(T(f"All my numbers come from the official **KKM / National Blood Centre (PDN)** open data on GitHub "
                        f"(*data-darah-public*), updated daily, from {FIRST_YEAR} to {data['last_date']:%d %b %Y}. "
                        "Every answer shows the exact field and filters I used, so you can check it yourself.",
                        f"Semua nombor saya daripada data terbuka rasmi **KKM / Pusat Darah Negara (PDN)** di GitHub "
                        f"(*data-darah-public*), dikemas kini setiap hari, dari {FIRST_YEAR} hingga {data['last_date']:%d %b %Y}. "
                        "Setiap jawapan menunjukkan medan dan penapis tepat yang saya guna, jadi anda boleh semak sendiri."),
                      source=SOURCE_DONATIONS, field="data source")

    # what to expect when donating
    if donate and re.search(r"\b(safe|selamat ke|bahaya|danger|risk|risiko|jangkit|infection)\b", t):
        return _reply(T("**Yes, donating blood is safe.** Every donor gets a new, sterile, single-use needle, so you cannot catch an infection from donating. "
                        "A nurse checks your blood pressure and haemoglobin first. Some people feel a little dizzy, so rest and drink water afterwards.",
                        "**Ya, menderma darah adalah selamat.** Setiap penderma guna jarum baru yang steril dan sekali guna, jadi anda tidak boleh dijangkiti kerana menderma. "
                        "Jururawat akan periksa tekanan darah dan hemoglobin dahulu. Ada yang rasa sedikit pening, jadi berehat dan minum air selepasnya."), goto=["elig"])
    if donate and re.search(r"\b(hurt|pain|painful|sakit|takut|scared|afraid|ngeri)\b", t):
        return _reply(T("**Only a quick pinch** when the needle goes in, like a normal blood test. After that most people feel nothing while the bag fills.",
                        "**Hanya rasa cucuk sekejap** semasa jarum dimasukkan, sama seperti ujian darah biasa. Selepas itu kebanyakan orang tidak rasa apa-apa semasa beg diisi."))
    if donate and re.search(r"\b(how long|berapa lama|lama ke|take long|duration|tempoh|minutes|minit)\b", t):
        return _reply(T("**The blood draw takes about 8 to 10 minutes.** With registration, the health check and rest with a drink after, plan for about **30 to 45 minutes**.",
                        "**Pengambilan darah mengambil kira-kira 8 hingga 10 minit.** Termasuk pendaftaran, pemeriksaan kesihatan dan rehat selepasnya, sediakan masa kira-kira **30 hingga 45 minit**."))
    if re.search(r"\b(happens? to (my|the) blood|where does (my|the) blood go|blood (go|used)|darah (saya )?(pergi|digunakan|dibuat apa)|apa jadi)\b", t):
        return _reply(T("Your **450 ml** is tested for safety, then split into **red cells, plasma and platelets**. "
                        "That is why one donation can help **up to 3 patients**, such as accident victims, mothers giving birth, and cancer or thalassaemia patients.",
                        "Darah **450 ml** anda diuji keselamatannya, kemudian dipecahkan kepada **sel darah merah, plasma dan platelet**. "
                        "Sebab itu satu derma boleh membantu **sehingga 3 pesakit**, seperti mangsa kemalangan, ibu bersalin, dan pesakit kanser atau talasemia."))
    if re.search(r"\b(benefits?|kebaikan|faedah|manfaat|why (should|donate)|kenapa (perlu|patut) derma|good for)\b", t) and (donate or "benefit" in t):
        return _reply(T("- **You help save lives:** one donation can help up to 3 patients.\n- **A free mini health check:** blood pressure and haemoglobin are checked.\n"
                        "- **Your body makes new blood:** plasma is replaced in about a day and red cells within a few weeks.\n- **A good feeling** of helping your community.",
                        "- **Anda membantu menyelamatkan nyawa:** satu derma boleh membantu sehingga 3 pesakit.\n- **Pemeriksaan kesihatan mini percuma:** tekanan darah dan hemoglobin diperiksa.\n"
                        "- **Badan anda menghasilkan darah baru:** plasma diganti dalam kira-kira sehari dan sel darah merah dalam beberapa minggu.\n- **Rasa gembira** kerana membantu masyarakat."),
                      goto=["elig"])
    if re.search(r"\b(universal (donor|recipient|receiver)|penderma universal|penerima universal|receive from (anyone|all)|give to (anyone|everyone|all)|boleh terima semua|boleh beri semua)\b", t):
        return _reply(T("**O negative (O-)** is the *universal donor*: red cells from O- can be given to anyone in an emergency. "
                        "**AB positive (AB+)** is the *universal recipient*: they can receive red cells from all types.",
                        "**O negatif (O-)** ialah *penderma universal*: sel darah merah O- boleh diberikan kepada sesiapa dalam kecemasan. "
                        "**AB positif (AB+)** ialah *penerima universal*: mereka boleh menerima sel darah merah daripada semua jenis."), goto=["type"])
    if re.search(r"\b(what is my blood type|apa jenis darah saya|my blood (type|group)|jenis darah saya|how (do i|to) know my blood)\b", t):
        return _reply(T("I can't know your blood type from the data, but **you get it for free when you donate**: the blood bank tests it and it is printed on your donor card. "
                        "Already know it? Open **🩸 My blood type** to see how common it is in Malaysia.",
                        "Saya tidak dapat tahu jenis darah anda daripada data, tetapi **anda dapat tahu secara percuma apabila menderma**: bank darah akan mengujinya dan ia dicetak pada kad penderma anda. "
                        "Sudah tahu? Buka **🩸 My blood type** untuk lihat betapa biasa jenis darah anda di Malaysia."), goto=["type"])
    if donate and re.search(r"\b(women|woman|female|girls?|perempuan|wanita|haid|period|menstruat|pregnan|mengandung|hamil|breastfeed|menyusu)\b", t):
        return _reply(T("**Yes, women can donate.** During your period it is usually fine if you feel well and your haemoglobin is normal (the nurse checks it). "
                        "If you are **pregnant or breastfeeding**, wait until after that time, and ask the blood bank staff.",
                        "**Ya, wanita boleh menderma.** Semasa haid biasanya boleh jika anda sihat dan hemoglobin normal (jururawat akan periksa). "
                        "Jika anda **mengandung atau menyusukan bayi**, tunggu sehingga selepas tempoh itu, dan tanya kakitangan bank darah."), goto=["elig"])
    personal = re.search(r"\b(i|i'm|im|my|me|saya|aku|kalau|if|boleh|can|bolehkah|someone|seseorang|orang yang)\b", t)
    if donate and personal and re.search(r"\b(diabet|kencing manis|darah tinggi|high blood pressure|hypertension|tekanan darah|sick|demam|fever|flu|selsema|batuk|cough|ubat|medicine|medication|antibiotic|asthma|asma|jantung|heart|anaemia|anemia|kurang darah|surgery|pembedahan|covid|operation|disease|penyakit)", t):
        return _reply(T("**It depends, so please ask the doctor at the blood bank.** Some conditions are fine when they are well controlled (for example blood pressure or diabetes managed without insulin), "
                        "while others need you to wait (fever, flu, antibiotics, recent surgery). DarahBot can't judge your health, but you can check the basic rules in **✅ Can I donate?**.",
                        "**Bergantung, jadi sila tanya doktor di bank darah.** Sesetengah keadaan dibenarkan jika terkawal (contohnya tekanan darah atau kencing manis yang dikawal tanpa insulin), "
                        "manakala yang lain perlu tunggu (demam, selsema, antibiotik, pembedahan baru-baru ini). DarahBot tidak boleh menilai kesihatan anda, tetapi anda boleh semak syarat asas di **✅ Can I donate?**."),
                      goto=["elig"])

    # facts about the dataset itself
    if re.search(r"\b(how many states|berapa (banyak )?negeri|number of states|bilangan negeri)\b", t):
        st_ = data["states"]
        return _reply(T(f"The dataset reports **{len(st_)} states** separately: {', '.join(st_)}. "
                        "Perlis, Labuan and Putrajaya are grouped with a nearby state by the National Blood Centre.",
                        f"Set data ini melaporkan **{len(st_)} negeri** secara berasingan: {', '.join(st_)}. "
                        "Perlis, Labuan dan Putrajaya digabungkan dengan negeri berdekatan oleh Pusat Darah Negara."),
                      source=SOURCE_DONATIONS, value=f"{len(st_)} states", field="state (excluding Malaysia)")
    if re.search(r"\b(start|starts|started|begin|begins|first year|bermula|mula|since when|sejak bila|tahun pertama)\b", t) and re.search(r"\b(data|dataset|set data|record|rekod)\b", t):
        return _reply(T(f"The KKM data starts in **{FIRST_YEAR}** and runs to **{data['last_date']:%d %b %Y}** (updated daily).",
                        f"Data KKM bermula pada tahun **{FIRST_YEAR}** hingga **{data['last_date']:%d %b %Y}** (dikemas kini setiap hari)."),
                      source=SOURCE_DONATIONS, value=str(FIRST_YEAR), field="min(date)")
    if re.search(r"\b(how many|berapa (banyak|buah)?|number of|bilangan)\b", t) and re.search(r"\b(blood banks?|bank darah|hospitals?|facilit)", t) \
            and not re.search(r"\b(donations?|derma|kumpul|collect)", t):
        sts2, _ = find_states(question, data["states"])
        fac = data["facility"]
        if sts2 and sts2[0] != "Malaysia":
            hs = sorted(fac[fac["state"] == sts2[0]]["hospital"].unique())
            return _reply(T(f"**{sts2[0]}** has **{len(hs)}** government blood bank{'s' if len(hs) != 1 else ''} in the dataset: " + ", ".join(hs) + ".",
                            f"**{sts2[0]}** ada **{len(hs)}** bank darah kerajaan dalam set data: " + ", ".join(hs) + "."),
                          source=SOURCE_FACILITY, value=f"{len(hs)} blood banks", field=f"unique hospital, state = {sts2[0]}")
        h = fac["hospital"].nunique()
        return _reply(T(f"The dataset has **{h} government blood banks** (hospitals and the National Blood Centre).",
                        f"Set data ini ada **{h} bank darah kerajaan** (hospital dan Pusat Darah Negara)."),
                      source=SOURCE_FACILITY, value=f"{h} blood banks", field="unique hospital")
    if re.search(r"\b(seconds|saat)\b", t) and donate:
        y = find_years(question)
        secs, total = seconds_per_donation(data, y[0] if y else full)
        return _reply(T(f"In **{y[0] if y else full}**, someone in Malaysia donated blood about **every {secs:.1f} seconds** ({total:,} donations in the year).",
                        f"Pada **{y[0] if y else full}**, seseorang di Malaysia menderma darah kira-kira **setiap {secs:.1f} saat** ({total:,} derma setahun)."),
                      source=SOURCE_DONATIONS, value=f"{secs:.1f} s", field="seconds in year ÷ total donations")
    if re.search(r"\b(per day|a day|each day|daily average|average daily|setiap hari|sehari|sehari-hari|purata harian)\b", t) and donate:
        y = find_years(question)
        year = y[0] if y else full
        sts, _ = find_states(question, data["states"])
        place = sts[0] if sts else "Malaysia"
        d_ = data["donations"]
        rows_ = d_[(d_["state"] == place) & (d_["year"] == year)]
        avg = rows_["daily"].mean()
        return _reply(T(f"In **{year}**, **{place}** had about **{avg:,.0f}** blood donations **per day** on average ({rows_['daily'].sum():,} in the year).",
                        f"Pada **{year}**, **{place}** mencatat purata kira-kira **{avg:,.0f}** derma darah **sehari** ({rows_['daily'].sum():,} setahun)."),
                      source=SOURCE_DONATIONS, value=f"{avg:,.0f} per day", field=f"mean of daily, state = {place}, year = {year}")
    fest = None
    if re.search(r"(raya|aidilfitri|lebaran|eid)", t):
        fest = "Hari Raya Aidilfitri"
    elif re.search(r"(chinese new year|\bcny\b|tahun baru cina|imlek)", t):
        fest = "Chinese New Year"
    elif re.search(r"(deepavali|diwali)", t):
        fest = "Deepavali"
    if fest and (donate or re.search(r"\b(up|down|naik|turun)\b", t)):
        fe = festive_effect(data, fest)
        if len(fe):
            avg = fe["change %"].mean()
            down = avg < 0
            yesno = ""
            if re.search(r"\b(up or down|naik atau turun|go up|go down|naik|turun)\b", t):
                yesno = T("**Down.** " if down else "**Up.** ", "**Turun.** " if down else "**Naik.** ")
            return _reply(yesno + T(f"On the first day of **{fest}**, blood donations go **{'down' if down else 'up'}**: on average **{abs(avg):.0f}% {'lower' if down else 'higher'}** "
                                    f"than a normal day ({fe['year'].min()}–{fe['year'].max()}). Blood banks need donors before and after the holiday!",
                                    f"Pada hari pertama **{fest}**, derma darah **{'turun' if down else 'naik'}**: secara purata **{abs(avg):.0f}% {'lebih rendah' if down else 'lebih tinggi'}** "
                                    f"daripada hari biasa ({fe['year'].min()}–{fe['year'].max()}). Bank darah perlukan penderma sebelum dan selepas cuti!"),
                          source=SOURCE_DONATIONS, value=f"{avg:+.0f}% on the day", field="festival day vs median of 2 weeks around it",
                          rows=fe.drop(columns=["date"]).round(1))

    # data questions in everyday words
    nat = data["donations"][data["donations"]["state"] == "Malaysia"]
    if re.search(r"\b(today|hari ini|yesterday|semalam|latest|terkini|this week|minggu ini|recent|baru-baru ini)\b", t) and (donate or "how many" in t or "berapa" in t):
        last = nat.loc[nat["date"].idxmax()]
        return _reply(T(f"The latest day in the data is **{last['date']:%d %b %Y}**: **{last['daily']:,}** blood donations across Malaysia. "
                        "The KKM data is updated daily, so today's number appears tomorrow.",
                        f"Hari terkini dalam data ialah **{last['date']:%d %b %Y}**: **{last['daily']:,}** derma darah di seluruh Malaysia. "
                        "Data KKM dikemas kini setiap hari, jadi nombor hari ini akan muncul esok."),
                      source=SOURCE_DONATIONS, value=f"{last['daily']:,}", field="daily (latest date), state = Malaysia")
    sts, _ = find_states(re.sub(r"\b(kedua|ketiga)\b", " ", question, flags=re.I), data["states"])
    place = sts[0] if sts else "Malaysia"
    pl = data["donations"][data["donations"]["state"] == place]
    # a specific month: "donations in KL in March 2025"
    mon = None
    for i_, (en_, ms_) in enumerate(zip(MONTHS_EN, MONTHS_MS)):
        e_, m_ = en_.lower(), ms_.lower()
        if e_ in ("may",) or m_ in ("mei", "mac", "jun"):
            hit = re.search(r"\b(in|bulan|pada|during|month of)\s+(" + e_ + "|" + m_ + r")\b", t) or re.search(r"\b(" + e_ + "|" + m_ + r")\s+(19|20)\d{2}\b", t)
        else:
            hit = re.search(r"\b(" + e_ + "|" + m_ + r")\b", t)
        if hit:
            mon = i_ + 1
    if mon and re.search(r"\b(how many|berapa|donations?|derma|total|jumlah)\b", t) and not re.search(r"\b(which|mana|most|least|paling)\b", t):
        y = find_years(question)
        year = y[0] if y else full
        v_ = pl[(pl["year"] == year) & (pl["date"].dt.month == mon)]["daily"].sum()
        if v_:
            nm = MONTHS_MS[mon - 1] if bm else MONTHS_EN[mon - 1]
            return _reply(T(f"**{place}** recorded **{v_:,}** blood donations in **{nm} {year}**.",
                            f"**{place}** mencatat **{v_:,}** derma darah pada **{nm} {year}**."),
                          source=SOURCE_DONATIONS, value=f"{v_:,}", field=f"sum of daily, state = {place}, {MONTHS_EN[mon - 1]} {year}")
    # which YEAR had the most / least
    if re.search(r"\b(which year|what year|tahun (mana|apa|bila)|record year|best year|worst year|tahun rekod)\b", t):
        yr = pl[pl["year"] <= full].groupby("year")["daily"].sum()
        low = re.search(r"\b(least|fewest|lowest|worst|paling (sedikit|rendah|kurang)|terendah)\b", t)
        k_ = int(yr.idxmin() if low else yr.idxmax())
        tbl = yr.rename("value").reset_index().rename(columns={"year": "state"}); tbl["state"] = tbl["state"].astype(str)
        return _reply(T(f"For **{place}**, the year with the **{'fewest' if low else 'most'}** blood donations was **{k_}** ({yr[k_]:,} donations, {FIRST_YEAR}–{full}).",
                        f"Bagi **{place}**, tahun dengan derma darah **{'paling sedikit' if low else 'paling banyak'}** ialah **{k_}** ({yr[k_]:,} derma, {FIRST_YEAR}–{full})."),
                      source=SOURCE_DONATIONS, value=f"{k_}: {yr[k_]:,}", field=f"sum of daily per year, state = {place}",
                      chart=bar_chart(tbl, [str(k_)], T(f"Blood donations per year, {place}", f"Derma darah setiap tahun, {place}"), "donations"), rows=tbl)
    # the single busiest day ever
    if re.search(r"\b(ever|pernah|of all time|sepanjang masa|record)\b", t) and re.search(r"\b(day|hari)\b", t):
        best = pl.loc[pl["daily"].idxmax()]
        return _reply(T(f"The busiest single day ever for **{place}** was **{best['date']:%d %B %Y}**, with **{best['daily']:,}** donations in one day.",
                        f"Hari paling sibuk pernah direkodkan bagi **{place}** ialah **{best['date']:%d/%m/%Y}**, dengan **{best['daily']:,}** derma dalam sehari."),
                      source=SOURCE_DONATIONS, value=f"{best['daily']:,}", field=f"max of daily, state = {place}")
    if re.search(r"\b(month|bulan)\b", t) and re.search(r"\b(most|busiest|highest|paling|banyak|tertinggi|least|fewest|lowest|quiet|sunyi|sedikit|rendah|terendah)\b", t):
        y = find_years(question)
        year = y[0] if y else full
        m = pl[pl["year"] == year].assign(m=lambda x: x["date"].dt.month).groupby("m")["daily"].sum()
        if len(m):
            low = re.search(r"\b(least|fewest|lowest|quiet|sunyi|sedikit|rendah|terendah)\b", t)
            k = int(m.idxmin() if low else m.idxmax())
            name = MONTHS_MS[k - 1] if bm else MONTHS_EN[k - 1]
            tbl = pd.DataFrame({"state": [MONTHS_EN[i - 1][:3] for i in m.index], "value": m.values})
            return _reply(T(f"In **{year}**, the month with the **{'fewest' if low else 'most'}** blood donations in {place} was **{name}** ({m[k]:,} donations).",
                            f"Pada **{year}**, bulan dengan derma darah **{'paling sedikit' if low else 'paling banyak'}** di {place} ialah **{name}** ({m[k]:,} derma)."),
                          source=SOURCE_DONATIONS, value=f"{name}: {m[k]:,}", field=f"sum of daily per month, year = {year}",
                          chart=bar_chart(tbl, [MONTHS_EN[k - 1][:3]], T(f"Blood donations by month, {year}", f"Derma darah mengikut bulan, {year}"), "donations"), rows=tbl)
    if re.search(r"\b(day of the week|which day|busiest day|hari apa|hari mana|best day|quietest day|weekday|weekend|hujung minggu)\b", t) or re.search(r"\bhari\b.*\b(paling|tertinggi|terendah)\b", t):
        y = find_years(question)
        year = y[0] if y else full
        n = nat[nat["year"] == year].assign(w=lambda x: x["date"].dt.day_name())
        wk = n.groupby("w")["daily"].mean().sort_values()
        hi, lo = wk.index[-1], wk.index[0]
        hn, ln = (DAYS_MS[hi], DAYS_MS[lo]) if bm else (hi, lo)
        tbl = wk.rename("value").reset_index().rename(columns={"w": "state"})
        if re.search(r"\b(lowest|least|fewest|quiet|quietest|sunyi|rendah|terendah|sedikit|kurang)\b", t):
            return _reply(T(f"In **{year}**, **{ln}** was the quietest day of the week (about **{wk[lo]:,.0f}** donations on average); **{hn}** was the busiest (about **{wk[hi]:,.0f}**).",
                            f"Pada **{year}**, hari **{ln}** paling sunyi (purata kira-kira **{wk[lo]:,.0f}** derma); hari **{hn}** paling sibuk (kira-kira **{wk[hi]:,.0f}**)."),
                          source=SOURCE_DONATIONS, value=f"{lo}: {wk[lo]:,.0f} per day", field=f"mean of daily by weekday, year = {year}",
                          chart=bar_chart(tbl, [lo], T(f"Average donations by day of the week, {year}", f"Purata derma mengikut hari, {year}"), "donations"), rows=tbl)
        return _reply(T(f"In **{year}**, **{hn}** was the busiest day to donate (about **{wk[hi]:,.0f}** donations on average) and **{ln}** the quietest (about **{wk[lo]:,.0f}**). "
                        f"Want a short queue? Go on a {ln}.",
                        f"Pada **{year}**, hari **{hn}** paling sibuk (purata kira-kira **{wk[hi]:,.0f}** derma) dan hari **{ln}** paling sunyi (kira-kira **{wk[lo]:,.0f}**). "
                        f"Mahu barisan pendek? Pergi pada hari {ln}."),
                      source=SOURCE_DONATIONS, value=f"{hi}: {wk[hi]:,.0f} per day", field=f"mean of daily by weekday, year = {year}",
                      chart=bar_chart(tbl, [hi], T(f"Average donations by day of the week, {year}", f"Purata derma mengikut hari, {year}"), "donations"), rows=tbl)
    if re.search(r"\b(rarest|rare|jarang|least common|paling (sikit|kurang)|uncommon)\b", t) and re.search(r"\b(blood|darah|type|jenis)\b", t):
        y = find_years(question)
        year = y[0] if y else full
        rows = nat[nat["year"] == year]
        cols = {"A": "blood_a", "B": "blood_b", "O": "blood_o", "AB": "blood_ab"}
        tot = pd.DataFrame({"state": [f"Type {k}" for k in cols], "value": [rows[c].sum() for c in cols.values()]})
        tot["percent"] = tot["value"] / tot["value"].sum() * 100
        lo = tot.sort_values("value").iloc[0]
        return _reply(T(f"In **{year}**, the rarest blood type donated in Malaysia was **{lo['state']}**: only **{lo['percent']:.1f}%** of donations. "
                        "If you are type AB, your donation is extra special!",
                        f"Pada **{year}**, jenis darah paling jarang didermakan di Malaysia ialah **{lo['state'].replace('Type', 'jenis')}**: hanya **{lo['percent']:.1f}%** daripada derma. "
                        "Jika anda jenis AB, derma anda sangat istimewa!"),
                      source=SOURCE_DONATIONS, value=f"{lo['state']}: {lo['percent']:.1f}%", field=f"blood_a/b/o/ab, year = {year}",
                      chart=bar_chart(tot[["state", "value"]], [lo["state"]], T(f"Donations by blood type, {year}", f"Derma mengikut jenis darah, {year}"), "donations"),
                      rows=tot, goto=["type"])
    return None


# ---------------------------------------------------------------------------
# QUIZ: general info only. Never reveal which questions are asked or their answers.
# ---------------------------------------------------------------------------
QUIZ_N, QUIZ_PRIZE_AT = 6, 5


def quiz_answer(question, lang="en"):
    t = question.lower()
    if not re.search(r"\b(quiz|kuiz|prize|hadiah|present)\b", t):
        return None
    T = (lambda en, ms: ms if lang == "bm" else en)
    asks_content = re.search(r"\b(what (are|is) the (quiz )?(questions?|answers?)|which questions|list (of )?(the )?questions|"
                             r"answers? (to|for|of)|the answers?|jawapan|soalan (apa|mana)|apa soalan|senarai soalan|bagi soalan|"
                             r"tell me the questions?|show me the questions?|question \d|soalan (no\.? ?)?\d|bocor|leak|cheat|tipu|spoiler|hint)\b", t)
    if asks_content:
        return {"text": T("Nice try! 😄 I can't tell you the quiz questions or their answers, that would spoil the game for everyone. "
                          "But you can still ask me anything about blood donation in Malaysia to warm up. Good luck!",
                          "Cubaan yang bagus! 😄 Saya tidak boleh beritahu soalan kuiz atau jawapannya, nanti tak adil untuk semua. "
                          "Tetapi anda masih boleh tanya apa-apa tentang derma darah di Malaysia sebagai latihan. Semoga berjaya!"),
                "kind": "ok", "chart": None, "rows": None, "notes": [], "context": None, "goto": ["quiz"],
                "evidence": {"value": "-", "field": "quiz rules", "filters": "none", "unit": "-", "source": "DarahBot quiz rules"}}
    return {"text": T(f"**About the DarahBot quiz:**\n- **{QUIZ_N} questions** per round, picked at random from a bank of **48**, so everyone gets a different set.\n"
                      f"- Get **{QUIZ_PRIZE_AT} or more** right to **win a prize** (while prizes last). Close answers count, e.g. 590k for 589,866.\n"
                      "- **No time limit**: take your time. Each question must be answered before the next one.\n"
                      "- First **register with your email**: if you answered our survey before you go straight in; if not, answer the 2-minute survey.\n"
                      "- After the quiz, take a **memory photo** (winners take 2: a framed photo and a photo booth strip) and download it with a QR code.",
                      f"**Tentang kuiz DarahBot:**\n- **{QUIZ_N} soalan** setiap pusingan, dipilih secara rawak daripada **48** soalan, jadi setiap orang dapat set berbeza.\n"
                      f"- Betul **{QUIZ_PRIZE_AT} atau lebih** untuk **menang hadiah** (selagi ada). Jawapan hampir betul dikira, contohnya 590k untuk 589,866.\n"
                      "- **Tiada had masa**: jawab dengan tenang. Setiap soalan perlu dijawab sebelum ke soalan seterusnya.\n"
                      "- **Daftar dengan e-mel** dahulu: jika pernah menjawab tinjauan kami, terus masuk; jika belum, jawab tinjauan 2 minit.\n"
                      "- Selepas kuiz, ambil **gambar kenangan** (pemenang ambil 2: gambar berbingkai dan jalur photo booth) dan muat turun dengan kod QR."),
            "kind": "ok", "chart": None, "rows": None, "notes": [], "context": None, "goto": ["quiz"],
            "evidence": {"value": f"{QUIZ_N} questions, {QUIZ_PRIZE_AT} to win", "field": "quiz rules", "filters": "none", "unit": "-",
                         "source": "DarahBot quiz rules"}}


def answer(question, data, context=None, lang="en", survey=None):
    """
    Returns a dictionary:
      text      - the reply shown in the chat
      kind      - "ok", "refuse" (cannot answer) or "clarify" (needs more info)
      evidence  - dict with value, field, filters, unit, source (or None)
      chart     - a Plotly figure (or None)
      rows      - the pandas rows used (or None), for the "How I got this" panel
      notes     - small explanations (defaults used, spelling fixed, ...)
      context   - what was understood, so the next question can follow on
    lang = "en" (English) or "bm" (Bahasa Melayu). Numbers are identical in both.
    survey = our survey answers (DataFrame from load_survey) or None if not connected.
    """
    bm = lang == "bm"

    def t(en, ms):  # pick the English or Malay sentence
        return ms if bm else en

    q = (question or "").strip()
    out = {"text": "", "kind": "ok", "evidence": None, "chart": None, "rows": None, "notes": [], "context": None}

    if not q:
        out.update(kind="clarify", text=t("Type a question about blood donations, for example: *Which state had the most donations in 2025?*",
                                          "Taip soalan tentang derma darah, contohnya: *Negeri mana paling banyak derma darah pada 2025?*"))
        return out

    r = quiz_answer(q, lang) or rule_answer(q, lang) or faq_answer(q, data, lang)   # donor rules + everyday questions first
    if r:
        return r
    intent = detect_intent(q)
    q_for_states = re.sub(r"\b(kedua|ketiga|keempat|kelima|keenam)\b", " ", q, flags=re.I)   # "kedua" is not Kedah
    states, corrections = find_states(q_for_states, data["states"])
    years = find_years(q)
    metric = find_metric(q)
    hospital_q = bool(re.search(r"\b(hospitals?|blood banks?|bank darah|pusat darah|facilit(y|ies))\b", q.lower()))
    where_q = bool(re.search(r"\b(where|di ?mana|mana (nak|boleh|untuk|tempat|satu)|tempat (derma|menderma|untuk derma)|lokasi|location|nearest|terdekat|nak derma|pergi derma)\b|^mana\b", q.lower())) and \
        bool(re.search(_DONATE_WORDS, q.lower())) and intent not in ("compare", "trend")
    if where_q:
        hospital_q = True

    # --- Follow-up memory: "what about Johor?" reuses the last question's details
    if context and intent not in ("cause", "predict", "greet") and is_followup(q, intent, bool(states or years or metric or hospital_q)):
        if not states:
            states = list(context["states"])
        elif context["intent"] == "compare" and len(states) == 1 and context["states"]:
            states = [context["states"][0], states[0]]
        metric = metric or context["metric"]
        years = years or list(context["years"])
        hospital_q = hospital_q or context.get("hospital", False)
        if intent == "lookup":
            intent = context["intent"]
        out["notes"].append(t("Following on from your last question.", "Menyambung soalan anda sebelum ini."))
    out["context"] = {"intent": intent, "states": states, "years": years, "metric": metric, "hospital": hospital_q}

    for typed, fixed in corrections:
        out["notes"].append(t(f"I read **{typed}** as **{fixed}**.", f"Saya baca **{typed}** sebagai **{fixed}**."))

    last = f"{data['last_date']:%d %b %Y}"

    # --- Honest refusals ---------------------------------------------------
    if intent == "greet":
        out["text"] = t("Hi! I'm **DarahBot**. I answer questions about blood donations in Malaysia "
                        "using official KKM data, and I always show my evidence. Try one of the example questions.",
                        "Hai! Saya **DarahBot**. Saya menjawab soalan tentang derma darah di Malaysia "
                        "menggunakan data rasmi KKM, dan saya sentiasa tunjukkan bukti. Cuba salah satu contoh soalan.")
        return out
    if intent == "eligible" and not where_q:
        rules = check_eligibility(0, 0, 0, False, 0)
        out["text"] = t(
            "I can't see your health from the KKM dataset, but I can check the **5 basic donor rules** with you. "
            "Open the **✅ Can I donate?** tab, answer 5 quick questions, and I'll give you an early hypothesis "
            "(LAYAK or BELUM LAYAK). The basic rules are:\n"
            + "\n".join(f"- {en}" for _, en, _ in rules)
            + "\n\nOnly the blood bank staff can give you the real answer.",
            "Saya tidak dapat melihat kesihatan anda daripada set data KKM, tetapi saya boleh semak **5 syarat asas penderma** bersama anda. "
            "Buka tab **✅ Can I donate?**, jawab 5 soalan ringkas, dan saya akan beri hipotesis awal "
            "(LAYAK atau BELUM LAYAK). Syarat asasnya:\n"
            + "\n".join(f"- {ms}" for _, _, ms in rules)
            + "\n\nHanya kakitangan bank darah boleh memberi jawapan sebenar.")
        out["evidence"] = {"value": "5 rules", "field": "age, weight, sleep, tattoo/piercing, long-term medicine",
                           "filters": "none", "unit": "rule", "source": SOURCE_RULES}
        out["context"] = None
        return out
    if intent == "survey":
        out["context"] = None
        if survey is None:
            out.update(kind="refuse", text=t(
                "I cannot reach our survey data right now, so I won't guess. You can still take the survey at **dermadarah.jomana.my**.",
                "Saya tidak dapat mencapai data tinjauan kami sekarang, jadi saya tidak akan meneka. Anda masih boleh menjawab tinjauan di **dermadarah.jomana.my**."))
            return out
        sv = survey
        where = ""
        if states and states[0] != "Malaysia" and "state" in sv.columns:
            sv = sv[sv["state"] == states[0]]
            where = states[0]
        s = survey_summary(sv)
        if s["n"] == 0:
            out["text"] = t(f"No one{' from ' + where if where else ''} has answered our survey yet. Be the first at **dermadarah.jomana.my**!",
                            f"Belum ada sesiapa{' dari ' + where if where else ''} menjawab tinjauan kami. Jadilah yang pertama di **dermadarah.jomana.my**!")
            return out
        place_en = f" from **{where}**" if where else ""
        place_ms = f" dari **{where}**" if where else ""
        out["text"] = t(
            f"So far, **{s['n']}** people{place_en} have answered our survey: **{s['donors']}** have donated before "
            f"(they are our database) and **{s['never']}** have never donated."
            + (f" Of the donors, **{s['accepted']}** were accepted and **{s['deferred']}** were deferred on their last try." if s["donors"] else "")
            + (f" Of the first-timers, our early hypothesis says **{s['likely']}** can probably donate." if s["never"] else ""),
            f"Setakat ini, **{s['n']}** orang{place_ms} telah menjawab tinjauan kami: **{s['donors']}** pernah menderma "
            f"(mereka ialah pangkalan data kami) dan **{s['never']}** belum pernah menderma."
            + (f" Daripada penderma, **{s['accepted']}** diterima dan **{s['deferred']}** ditangguhkan pada cubaan terakhir." if s["donors"] else "")
            + (f" Daripada mereka yang belum pernah, hipotesis awal kami ialah **{s['likely']}** berkemungkinan layak." if s["never"] else ""))
        bars = pd.DataFrame({
            "group": [t("Donated: accepted", "Penderma: diterima"), t("Donated: deferred", "Penderma: ditangguhkan"),
                      t("Never: probably eligible", "Belum: berkemungkinan layak"), t("Never: not yet", "Belum: belum layak")],
            "people": [s["accepted"], s["deferred"], s["likely"], s["not_yet"]]})
        fig = px.bar(bars, x="people", y="group", orientation="h", text="people",
                     title=t("Our survey so far", "Tinjauan kami setakat ini") + (f" · {where}" if where else ""))
        fig.update_traces(marker_color=[OK_GREEN, AMBER, OK_GREEN, AMBER], textposition="outside", cliponaxis=False)
        fig.update_layout(yaxis={"categoryorder": "array", "categoryarray": list(bars["group"])[::-1], "title": ""},
                          xaxis_title=t("people", "orang"), height=280, margin=dict(l=10, r=10, t=60, b=10))
        out.update(chart=fig, rows=bars, evidence={
            "value": f"{s['n']} answers", "field": "ever_donated, last_result, age, weight_kg, sleep_hours, tattoo_12m, meds_days_per_month",
            "filters": f"state = {where}" if where else "all answers", "unit": "people", "source": SOURCE_SURVEY})
        return out
    if intent == "cause":
        out.update(kind="refuse", text=t(
            "I cannot answer *why* from this dataset. It records **how many** people donated, "
            "but not their reasons. I can show you **how it changed** instead, for example: "
            "*How did Gen Z donors in Melaka change from 2019 to 2025?*",
            "Saya tidak boleh jawab *kenapa* daripada set data ini. Data ini merekod **berapa ramai** yang menderma, "
            "tetapi bukan sebabnya. Saya boleh tunjukkan **bagaimana ia berubah**, contohnya: "
            "*Bagaimana penderma muda di Melaka berubah dari 2019 hingga 2025?*"))
        return out
    if intent == "predict":
        out.update(kind="refuse", text=t(
            f"I cannot predict the future. This dataset only contains real records from {FIRST_YEAR} to {last}, and I don't guess numbers.",
            f"Saya tidak boleh meramal masa depan. Set data ini hanya ada rekod sebenar dari {FIRST_YEAR} hingga {last}, dan saya tidak meneka nombor."))
        return out
    missing = [NOT_IN_DATA[w] for w in NOT_IN_DATA if re.search(r"\b" + w + r"\b", q.lower())]
    if missing:
        out.update(kind="refuse", text=t(
            f"I cannot answer for **{', '.join(missing)}**. This dataset does not report it as a separate state "
            f"(the National Blood Centre groups it with a nearby state). States I can answer for: {', '.join(data['states'])}.",
            f"Saya tidak boleh jawab untuk **{', '.join(missing)}**. Set data ini tidak melaporkannya sebagai negeri berasingan "
            f"(Pusat Darah Negara menggabungkannya dengan negeri berdekatan). Negeri yang saya boleh jawab: {', '.join(data['states'])}."))
        return out
    bad_years = [y for y in years if y < FIRST_YEAR or y > data["latest_year"]]
    if bad_years:
        out.update(kind="refuse", text=t(
            f"I cannot answer for **{bad_years[0]}**. This dataset covers {FIRST_YEAR} to {last} only.",
            f"Saya tidak boleh jawab untuk **{bad_years[0]}**. Set data ini hanya meliputi {FIRST_YEAR} hingga {last}."))
        return out

    # --- Defaults (and say so, so the visitor knows) -------------------------
    if metric is None:
        metric = "donations"
        if intent not in ("breakdown",) and not hospital_q:
            out["notes"].append(t("You didn't say what to measure, so I used **total blood donations**.",
                                  "Anda tidak nyatakan apa yang hendak diukur, jadi saya guna **jumlah derma darah**."))
    if metric == "per_capita" and years and years[0] != 2020:
        out["notes"].append(t("Population figures are DOSM 2020 estimates, so per-capita rates for other years are approximate.",
                              "Angka penduduk ialah anggaran DOSM 2020, jadi kadar per kapita untuk tahun lain adalah anggaran."))
    if not years and re.search(r"\b(last year|tahun lepas|tahun lalu|previous year)\b", q.lower()):
        years = [data["latest_full_year"]]
    year = years[0] if years else data["latest_full_year"]
    if not years and intent not in ("trend",):
        out["notes"].append(t(f"No year given, so I used **{year}** (the latest complete year).",
                              f"Tiada tahun diberi, jadi saya guna **{year}** (tahun lengkap terkini)."))
    label, unit, source = METRICS[metric][2], METRICS[metric][3], METRICS[metric][4]
    lab = BM_LABELS.get(label, label) if bm else label        # label in the chosen language
    un = BM_UNITS.get(unit, unit) if bm else unit             # unit in the chosen language
    yn = year_note(data, year, lang)

    # --- Hospital leaderboard -------------------------------------------------
    if hospital_q:
        col = METRICS[metric][1] if METRICS[metric][0] == "donations" else "daily"
        if col == "daily" and metric != "donations":
            out["notes"].append(t("Hospital data only has donation counts, so I used **total blood donations**.",
                                  "Data hospital hanya ada bilangan derma, jadi saya guna **jumlah derma darah**."))
            metric, label, lab, unit, un = "donations", "blood donations", t("blood donations", "derma darah"), "donations", t("donations", "derma")
        df = hospital_ranking(data, year, col, states[0] if states and states[0] != "Malaysia" else None)
        where = states[0] if states and states[0] != "Malaysia" else "Malaysia"
        if df.empty:
            out.update(kind="refuse", text=t(f"No hospital data for {where} in {year}.", f"Tiada data hospital untuk {where} pada {year}."))
            return out
        top = df.iloc[0]
        if where_q:
            names = ", ".join(f"**{h}**" for h in df["hospital"].head(5))
            out["text"] = t(f"You can donate at these blood banks in **{where}** (busiest first, {year}): {names}. "
                            "Mobile blood drives also visit malls, campuses and mosques, so watch for them near you.",
                            f"Anda boleh menderma di bank darah ini di **{where}** (paling sibuk dahulu, {year}): {names}. "
                            "Kempen derma darah bergerak juga datang ke pusat beli-belah, kampus dan masjid, jadi perhatikan berdekatan anda.")
            chart_df = df[["hospital", "value"]].rename(columns={"hospital": "state"})
            out.update(chart=bar_chart(chart_df, [top["hospital"]], t(f"Blood banks in {where}, {year}", f"Bank darah di {where}, {year}"), metric),
                       rows=df, evidence={"value": f"{len(df)} blood banks", "field": col, "filters": f"year = {year}" + (f", state = {where}" if where != "Malaysia" else ""),
                                          "unit": unit, "source": SOURCE_FACILITY})
            return out
        out["text"] = t(f"In **{year}**{yn}, the blood bank that collected the most {label} in **{where}** was "
                        f"**{top['hospital']}** ({top['state']}): **{top['value']:,.0f}** {unit}.",
                        f"Pada **{year}**{yn}, bank darah yang mengumpul paling banyak {lab} di **{where}** ialah "
                        f"**{top['hospital']}** ({top['state']}): **{top['value']:,.0f}** {un}.")
        chart_df = df[["hospital", "value"]].rename(columns={"hospital": "state"})
        out.update(chart=bar_chart(chart_df, [top["hospital"]], f"{cap(lab)} by hospital, {year}" if not bm else f"{cap(lab)} mengikut hospital, {year}", metric),
                   rows=df, evidence={"value": f"{top['hospital']}: {top['value']:,.0f}", "field": col,
                                      "filters": f"year = {year}" + (f", state = {where}" if where != "Malaysia" else ""),
                                      "unit": unit, "source": SOURCE_FACILITY})
        return out

    # --- Answer by intent ----------------------------------------------------
    if intent == "breakdown":
        place = states[0] if states else "Malaysia"
        cols = {"A": "blood_a", "B": "blood_b", "O": "blood_o", "AB": "blood_ab"}
        rows = data["donations"][(data["donations"]["state"] == place) & (data["donations"]["year"] == year)]
        totals = pd.DataFrame({"blood type": list(cols), "donations": [rows[c].sum() for c in cols.values()]})
        totals["percent"] = totals["donations"] / totals["donations"].sum() * 100
        top = totals.sort_values("donations", ascending=False).iloc[0]
        n = f"{totals['donations'].sum():,.0f}"
        ql = q.lower()
        all_pct = ", ".join(f"{r_['blood type']} **{r_['percent']:.1f}%**" for _, r_ in totals.iterrows())
        asked = {"blood_a": "A", "blood_b": "B", "blood_o": "O", "blood_ab": "AB"}.get(metric)
        least = re.search(r"\b(least|lowest|fewest|rarest|rare|paling (sedikit|kurang|jarang)|terendah|tersedikit|jarang)\b", ql)
        if asked or least:
            row_ = totals[totals["blood type"] == asked].iloc[0] if asked else totals.sort_values("donations").iloc[0]
            pre = ""
            if asked and re.search(r"\b(more than half|over half|majority|lebih (dari|daripada)? ?separuh|melebihi separuh)\b", ql):
                pre = t("**Yes.** " if row_["percent"] > 50 else "**No.** ", "**Ya.** " if row_["percent"] > 50 else "**Tidak.** ")
            out["text"] = pre + t(f"In **{place}** in **{year}**{yn}, **type {row_['blood type']}** made up **{row_['percent']:.1f}%** of donations "
                                  f"({row_['donations']:,.0f} of {n})" + (" — the least of all types." if least and not asked else ".") + f" All types: {all_pct}.",
                                  f"Di **{place}** pada **{year}**{yn}, **jenis {row_['blood type']}** ialah **{row_['percent']:.1f}%** daripada derma "
                                  f"({row_['donations']:,.0f} daripada {n})" + (", paling sedikit antara semua jenis." if least and not asked else ".") + f" Semua jenis: {all_pct}.")
            fig = px.pie(totals, names="blood type", values="donations", hole=0.55,
                         title=t(f"Blood types donated, {place} {year}", f"Jenis darah yang didermakan, {place} {year}"),
                         color_discrete_sequence=[RED, PINK, WINE, BLUSH])
            fig.update_traces(textinfo="label+percent")
            out.update(chart=fig, rows=totals.round(1), evidence={
                "value": f"{row_['percent']:.1f}% type {row_['blood type']}", "field": "blood_a, blood_b, blood_o, blood_ab",
                "filters": f"state = {place}, year = {year}", "unit": "donations", "source": SOURCE_DONATIONS})
            return out
        out["text"] = t(f"In **{place}** in **{year}**{yn}, the most common blood type donated was **type {top['blood type']}** "
                        f"({top['percent']:.1f}% of {n} donations with a recorded blood type).",
                        f"Di **{place}** pada **{year}**{yn}, jenis darah yang paling banyak didermakan ialah **jenis {top['blood type']}** "
                        f"({top['percent']:.1f}% daripada {n} derma yang mempunyai rekod jenis darah).")
        fig = px.pie(totals, names="blood type", values="donations", hole=0.55,
                     title=t(f"Blood types donated, {place} {year}", f"Jenis darah yang didermakan, {place} {year}"),
                     color_discrete_sequence=[RED, PINK, WINE, BLUSH])
        fig.update_traces(textinfo="label+percent")
        fig.update_layout(legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"))
        out.update(chart=fig, rows=totals.round(1), evidence={
            "value": f"{top['percent']:.1f}% type {top['blood type']}", "field": "blood_a, blood_b, blood_o, blood_ab",
            "filters": f"state = {place}, year = {year}", "unit": "donations", "source": SOURCE_DONATIONS})
        return out

    if intent == "compare" or len(states) >= 2:
        if len(states) < 2:
            out.update(kind="clarify", text=t("Which **two** states should I compare? For example: *Compare Melaka and Johor in 2025*.",
                                              "Dua negeri **mana** yang hendak saya bandingkan? Contohnya: *Bandingkan Melaka dan Johor 2025*."))
            return out
        a, b = states[0], states[1]
        c = compare(data, metric, a, b, year)
        if c is None:
            out.update(kind="refuse", text=t(f"I couldn't find {label} for both {a} and {b} in {year}.",
                                             f"Saya tidak jumpa {lab} untuk {a} dan {b} pada {year}."))
            return out
        bigger = a if c["diff"] >= 0 else b
        diff = fmt(abs(c["diff"]), metric).rstrip("%")
        ratio_v = max(c["a"], c["b"]) / min(c["a"], c["b"]) if min(c["a"], c["b"]) > 0 and unit != "%" else None
        if unit == "%":
            diff_unit = t("percentage points", "mata peratusan")
        else:
            diff_unit = un
        out["text"] = t(f"For **{label}** in **{year}**{yn}: **{a}** recorded **{fmt(c['a'], metric)}** and "
                        f"**{b}** recorded **{fmt(c['b'], metric)}**. {bigger} is higher by **{diff}** {diff_unit}."
                        + (f" That's **{ratio_v:.1f}×** as much." if ratio_v else ""),
                        f"Untuk **{lab}** pada **{year}**{yn}: **{a}** mencatat **{fmt(c['a'], metric)}** dan "
                        f"**{b}** mencatat **{fmt(c['b'], metric)}**. {bigger} lebih tinggi sebanyak **{diff}** {diff_unit}."
                        + (f" Iaitu **{ratio_v:.1f}×** ganda." if ratio_v else ""))
        df = yearly_values(data, metric, [a, b])
        rows = df[df["year"] == year]
        out.update(chart=bar_chart(rows, [a, b], f"{cap(lab)}, {year}", metric), rows=rows,
                   evidence={"value": f"{fmt(c['a'], metric)} vs {fmt(c['b'], metric)}", "field": METRICS[metric][1] or "computed",
                             "filters": f"state in [{a}, {b}], year = {year}", "unit": unit, "source": source})
        return out

    if intent in ("trend", "rank") and re.search(r"\b(improved|grew|increased|rose|dropped|fell|decreased|declined|meningkat|naik|turun|menurun|merosot)\b.*\b(most|paling)\b|\b(most|paling)\b.*\b(improved|grew|increase|rise|drop|fall|decline|meningkat|naik|turun|menurun|merosot)\b", q.lower()) and not states:
        y1, y2 = (min(years), max(years)) if len(years) >= 2 else ((years[0], data["latest_full_year"]) if years else (2019, data["latest_full_year"]))
        df = yearly_values(data, metric, data["states"])
        a_ = df[df.year == y1].set_index("state")["value"]; b_ = df[df.year == y2].set_index("state")["value"]
        ch = ((b_ - a_) / a_ * 100).dropna().sort_values()
        dropq = re.search(r"\b(dropped|fell|decreased|declined|turun|menurun|merosot|drop|fall|decline)\b", q.lower())
        st_ = ch.index[0] if dropq else ch.index[-1]
        tbl = ch.rename("value").reset_index()
        out["text"] = t(f"From **{y1}** to **{y2}**, **{st_}** {'fell' if ch[st_] < 0 else 'grew'} the {'most' if True else ''} for {label}: **{ch[st_]:+.1f}%** "
                        f"({fmt(a_[st_], metric)} → {fmt(b_[st_], metric)}).",
                        f"Dari **{y1}** hingga **{y2}**, **{st_}** paling {'turun' if ch[st_] < 0 else 'meningkat'} bagi {lab}: **{ch[st_]:+.1f}%** "
                        f"({fmt(a_[st_], metric)} → {fmt(b_[st_], metric)}).")
        out.update(chart=bar_chart(tbl, [st_], t(f"Change in {label}, {y1} to {y2} (%)", f"Perubahan {lab}, {y1} hingga {y2} (%)"), "genz_share"),
                   rows=tbl.round(1), evidence={"value": f"{st_}: {ch[st_]:+.1f}%", "field": METRICS[metric][1] or "computed",
                                                "filters": f"{y1} vs {y2}, all states", "unit": "% change", "source": source})
        return out
    if intent == "trend":
        place = states or ["Malaysia"]
        if len(years) >= 2:
            y1, y2 = min(years), max(years)
        elif years and re.match(r"\s*(did|do|does|was|were|adakah)\b", q.lower()):
            y1, y2 = years[0] - 1, years[0]           # "did donations drop in 2020?" -> 2019 vs 2020
        elif years and years[0] < data["latest_full_year"]:
            y1, y2 = years[0], data["latest_full_year"]
        else:
            y2 = years[0] if years else data["latest_full_year"]
            y1 = 2015 if not years else y2
        if y1 == y2:
            y1 = max(FIRST_YEAR, y2 - 6)
        df = yearly_values(data, metric, place)
        df = df[(df["year"] >= y1) & (df["year"] <= y2)]
        lines, plain = [], []
        for s in place:
            v1 = df[(df.state == s) & (df.year == y1)]["value"]
            v2 = df[(df.state == s) & (df.year == y2)]["value"]
            if v1.empty or v2.empty:
                continue
            v1, v2 = float(v1.iloc[0]), float(v2.iloc[0])
            change = (v2 - v1) / v1 * 100 if v1 else 0
            up = v2 > v1
            lines.append(t(f"**{s}**: {label} {'rose' if up else 'fell'} from **{fmt(v1, metric)}** in {y1} to **{fmt(v2, metric)}** in {y2} ({change:+.1f}%).",
                           f"**{s}**: {lab} {'naik' if up else 'turun'} daripada **{fmt(v1, metric)}** pada {y1} kepada **{fmt(v2, metric)}** pada {y2} ({change:+.1f}%)."))
            plain.append(f"{s}: {fmt(v1, metric)} ({y1}) -> {fmt(v2, metric)} ({y2}), {change:+.1f}%")
        if not lines:
            out.update(kind="refuse", text=t(f"I don't have {label} for {', '.join(place)} between {y1} and {y2}.",
                                             f"Saya tiada {lab} untuk {', '.join(place)} antara {y1} dan {y2}."))
            return out
        out["text"] = "\n\n".join(lines) + year_note(data, y2, lang)
        asked_up = re.search(r"\b(up|naik|increase|increased|rise|rose|grow|grew|more|meningkat|bertambah)\b", q.lower())
        asked_down = re.search(r"\b(down|turun|decrease|decreased|fall|fell|drop|dropped|less|fewer|menurun|berkurang)\b", q.lower())
        if re.match(r"\s*(did|do|does|is|was|were|has|have|adakah|adakan|betul ke|ke)\b", q.lower()) and (asked_up or asked_down) and len(place) == 1:
            went_up = "rose" in lines[0] or "naik" in lines[0]
            yes = went_up if asked_up else not went_up
            out["text"] = t("**Yes.** " if yes else "**No.** ", "**Ya.** " if yes else "**Tidak.** ") + out["text"]
        out.update(chart=line_chart(df, f"{cap(lab)}, {y1}–{y2}", metric), rows=df,
                   evidence={"value": "; ".join(plain), "field": METRICS[metric][1] or "computed",
                             "filters": f"state in {place}, {y1} ≤ year ≤ {y2}", "unit": unit, "source": source})
        return out

    if intent == "rank":
        lowest = bool(re.search(r"\b(lowest|least|fewest|terendah|tersedikit|worst|paling sedikit|paling rendah|paling kurang)\b", q.lower()))
        df = rank(data, metric, year, lowest=lowest)
        if df.empty:
            out.update(kind="refuse", text=t(f"No {label} recorded for {year}.", f"Tiada {lab} direkodkan untuk {year}."))
            return out
        nth = {"second": 2, "2nd": 2, "kedua": 2, "ke-2": 2, "third": 3, "3rd": 3, "ketiga": 3, "ke-3": 3,
               "fourth": 4, "4th": 4, "keempat": 4, "fifth": 5, "5th": 5, "kelima": 5}
        k = next((v for w, v in nth.items() if re.search(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", q.lower())), 1)
        if k > 1 and len(df) >= k:
            top = df.iloc[k - 1]
            pos_en = {2: "second", 3: "third", 4: "fourth", 5: "fifth"}[k]
            out["text"] = t(f"In **{year}**{yn}, **{top['state']}** came **{pos_en} {'lowest' if lowest else 'highest'}** for {label}: "
                            f"**{fmt(top['value'], metric)}** {unit}, after {', '.join(df['state'].head(k - 1))}.",
                            f"Pada **{year}**{yn}, **{top['state']}** di tempat **ke-{k}** ({'terendah' if lowest else 'tertinggi'}) bagi {lab}: "
                            f"**{fmt(top['value'], metric)}** {un}, selepas {', '.join(df['state'].head(k - 1))}.")
            out.update(chart=bar_chart(df, [top["state"]], t(f"{cap(label)} by state, {year}", f"{cap(lab)} mengikut negeri, {year}"), metric), rows=df,
                       evidence={"value": f"#{k} {top['state']}: {fmt(top['value'], metric)}", "field": METRICS[metric][1] or "computed",
                                 "filters": f"year = {year}, ranked {len(df)} states", "unit": unit, "source": source})
            return out
        top = df.iloc[0]
        out["text"] = t(f"In **{year}**{yn}, **{top['state']}** had the **{'lowest' if lowest else 'highest'}** {label}: "
                        f"**{fmt(top['value'], metric)}** {unit}. Here is the full ranking.",
                        f"Pada **{year}**{yn}, **{top['state']}** mencatat {lab} **{'paling rendah' if lowest else 'paling tinggi'}**: "
                        f"**{fmt(top['value'], metric)}** {un}. Ini kedudukan penuh.")
        out.update(chart=bar_chart(df, [top["state"]], t(f"{cap(label)} by state, {year}", f"{cap(lab)} mengikut negeri, {year}"), metric), rows=df,
                   evidence={"value": f"{top['state']}: {fmt(top['value'], metric)}", "field": METRICS[metric][1] or "computed",
                             "filters": f"year = {year}, all {len(df)} states (Malaysia total excluded)", "unit": unit, "source": source})
        return out

    if intent == "summary" and not states:
        s = summary(data, metric, year)
        if s is None:
            out.update(kind="refuse", text=t(f"No {label} recorded for {year}.", f"Tiada {lab} direkodkan untuk {year}."))
            return out
        show_total = unit not in ("%", "per 1,000 adults")
        mx, mn = s["max"], s["min"]
        out["text"] = t(f"In **{year}**{yn}, the average {label} per state was **{fmt(s['mean'], metric)}** {unit} across {s['n']} states."
                        + (f" Total across all states: **{fmt(s['total'], metric)}**." if show_total else "")
                        + f" Highest: **{mx['state']}** ({fmt(mx['value'], metric)}), lowest: **{mn['state']}** ({fmt(mn['value'], metric)}).",
                        f"Pada **{year}**{yn}, purata {lab} setiap negeri ialah **{fmt(s['mean'], metric)}** {un} bagi {s['n']} negeri."
                        + (f" Jumlah semua negeri: **{fmt(s['total'], metric)}**." if show_total else "")
                        + f" Tertinggi: **{mx['state']}** ({fmt(mx['value'], metric)}), terendah: **{mn['state']}** ({fmt(mn['value'], metric)}).")
        fig = bar_chart(s["table"], [], t(f"{cap(label)} by state, {year}", f"{cap(lab)} mengikut negeri, {year}"), metric)
        fig.add_vline(x=s["mean"], line_dash="dash", line_color=RED, annotation_text=t("average", "purata"))
        out.update(chart=fig, rows=s["table"], evidence={
            "value": f"mean = {fmt(s['mean'], metric)}", "field": METRICS[metric][1] or "computed",
            "filters": f"year = {year}, {s['n']} states", "unit": unit, "source": source})
        return out

    # --- LOOKUP (default) -----------------------------------------------------
    place = states[0] if states else None
    if place is None and (years or re.search(r"\b(how many|berapa|ramai|jumlah|total|number|bilangan|count|donations?|derma)\b", q.lower())):
        place = "Malaysia"                     # "donations in 2025", "berapa ramai derma tahun lepas" -> whole country
    if place is None:
        out.update(kind="refuse", text=t(
            "I'm not sure how to answer that from this dataset. I can answer questions like:\n"
            "- *How many blood donations in Melaka in 2025?* (lookup)\n"
            "- *Compare Johor and Selangor Gen Z donors* (comparison)\n"
            "- *Which state had the lowest donations per 1,000 adults?* (highest/lowest)\n"
            "- *Average new donors per state in 2024* (summary)\n"
            "- *How did Gen Z donors in Melaka change from 2019 to 2025?* (trend)\n"
            "- *Which hospital in Perak collects the most blood?* (hospital)",
            "Saya tidak pasti cara menjawabnya daripada set data ini. Saya boleh jawab soalan seperti:\n"
            "- *Berapa derma darah di Melaka pada 2025?* (carian)\n"
            "- *Bandingkan penderma muda Johor dan Selangor* (perbandingan)\n"
            "- *Negeri mana paling rendah derma setiap 1000 dewasa?* (tertinggi/terendah)\n"
            "- *Purata penderma baru setiap negeri 2024* (purata)\n"
            "- *Bagaimana penderma muda di Melaka berubah dari 2019 hingga 2025?* (trend)\n"
            "- *Hospital mana di Perak paling banyak kumpul darah?* (hospital)"))
        return out
    v = lookup(data, metric, place, year)
    if v is None:
        out.update(kind="refuse", text=t(f"I couldn't find {label} for {place} in {year}.", f"Saya tidak jumpa {lab} untuk {place} pada {year}."))
        return out
    nat = lookup(data, metric, "Malaysia", year) if place != "Malaysia" else None
    pct = f"{v / nat * 100:.1f}%" if nat and unit not in ("%", "per 1,000 adults") else None
    if metric in ("mobile", "students", "regular") and re.search(r"(%|\bpercent|\bpercentage|\bperatus|\bshare\b|\bproportion|\bbahagian)", q.lower()):
        tot_ = lookup(data, "donations", place, year)
        if tot_:
            sh_ = v / tot_ * 100
            out["text"] = t(f"In **{year}**{yn}, **{sh_:.1f}%** of blood donations in **{place}** were {label} ({fmt(v, metric)} of {tot_:,.0f}).",
                            f"Pada **{year}**{yn}, **{sh_:.1f}%** derma darah di **{place}** ialah {lab} ({fmt(v, metric)} daripada {tot_:,.0f}).")
            out["evidence"] = {"value": f"{sh_:.1f}%", "field": f"{METRICS[metric][1]} ÷ daily", "filters": f"state = {place}, year = {year}",
                               "unit": "%", "source": source}
            return out
    out["text"] = t(f"**{place}** recorded **{fmt(v, metric)}** {label} in **{year}**{yn}." + (f" That's **{pct}** of Malaysia's total." if pct else ""),
                    f"**{place}** mencatat **{fmt(v, metric)}** {lab} pada **{year}**{yn}." + (f" Iaitu **{pct}** daripada jumlah Malaysia." if pct else ""))
    df = yearly_values(data, metric, [place])
    df = df[(df["year"] >= year - 6) & (df["year"] <= year)]
    fig = px.bar(df, x="year", y="value", title=t(f"{cap(label)} in {place}", f"{cap(lab)} di {place}"),
                 text=df["value"].apply(lambda x: fmt(x, metric)))
    fig.update_traces(marker_color=[RED if y == year else GREY for y in df["year"]], textposition="outside", cliponaxis=False)
    fig.update_layout(yaxis_title=un, xaxis_title="", height=330, margin=dict(l=10, r=10, t=50, b=10))
    out.update(chart=fig, rows=df, evidence={
        "value": f"{fmt(v, metric)} {unit}", "field": METRICS[metric][1] or "computed",
        "filters": f"state = {place}, year = {year}", "unit": unit, "source": source})
    return out


# ---------------------------------------------------------------------------
# 7. FUN EXTRAS for the exhibition (still 100% computed from the data)
# ---------------------------------------------------------------------------
def seconds_per_donation(data, year=None):
    """How often, on average, someone in Malaysia donated blood in a year."""
    year = year or data["latest_full_year"]
    total = lookup(data, "donations", "Malaysia", year)
    days = 366 if pd.Timestamp(year=year, month=12, day=31).dayofyear == 366 else 365
    return days * 24 * 3600 / total, total


def fun_facts(data, lang="en"):
    """A list of (fact, evidence) pairs, every number calculated here."""
    def t(en, ms):
        return ms if lang == "bm" else en
    BM_DAYS = {"Monday": "Isnin", "Tuesday": "Selasa", "Wednesday": "Rabu", "Thursday": "Khamis",
               "Friday": "Jumaat", "Saturday": "Sabtu", "Sunday": "Ahad"}
    d = data["donations"]
    full = data["latest_full_year"]
    nat = d[d["state"] == "Malaysia"].copy()
    facts = []

    best_day = nat.loc[nat["daily"].idxmax()]
    facts.append((t(f"The busiest single day ever was **{best_day['date']:%d %B %Y}**, with **{best_day['daily']:,}** donations in one day.",
                    f"Hari paling sibuk pernah direkodkan ialah **{best_day['date']:%d/%m/%Y}**, dengan **{best_day['daily']:,}** derma dalam sehari."),
                  "max of daily, state = Malaysia"))

    yearly = nat[nat["year"] <= full].groupby("year")["daily"].sum()
    facts.append((t(f"The record year was **{yearly.idxmax()}**, with **{yearly.max():,}** donations.",
                    f"Tahun rekod ialah **{yearly.idxmax()}**, dengan **{yearly.max():,}** derma."),
                  f"sum of daily per year, {FIRST_YEAR}–{full}"))

    nat["weekday"] = nat["date"].dt.day_name()
    wk = nat[nat["year"] == full].groupby("weekday")["daily"].mean().sort_values()
    hi, lo = wk.index[-1], wk.index[0]
    facts.append((t(f"In {full}, **{hi}** was the busiest day of the week (about **{wk.iloc[-1]:,.0f}** donations), "
                    f"and **{lo}** the quietest (about **{wk.iloc[0]:,.0f}**).",
                    f"Pada {full}, hari **{BM_DAYS[hi]}** paling sibuk (kira-kira **{wk.iloc[-1]:,.0f}** derma), "
                    f"dan hari **{BM_DAYS[lo]}** paling sunyi (kira-kira **{wk.iloc[0]:,.0f}**)."),
                  f"average daily by weekday, {full}"))

    y = nat[nat["year"] == full]
    types = {k: y[f"blood_{k.lower()}"].sum() for k in ["A", "B", "O", "AB"]}
    tot = sum(types.values())
    o, ab = types["O"] / tot * 100, types["AB"] / tot * 100
    facts.append((t(f"**{o:.0f}%** of donations in {full} were **type O**, while type AB was only **{ab:.0f}%**.",
                    f"**{o:.0f}%** derma pada {full} ialah **jenis O**, manakala jenis AB hanya **{ab:.0f}%**."),
                  f"blood_o and blood_ab ÷ all typed donations, {full}"))

    mob = y["location_mobile"].sum() / y["daily"].sum() * 100
    facts.append((t(f"**{mob:.0f}%** of donations in {full} happened at **mobile drives**, not at a blood bank.",
                    f"**{mob:.0f}%** derma pada {full} berlaku di **kempen bergerak**, bukan di bank darah."),
                  f"location_mobile ÷ daily, {full}"))

    kl = d[(d["state"] == "W.P. Kuala Lumpur") & (d["year"] == full)]["daily"].sum() / y["daily"].sum() * 100
    facts.append((t(f"Blood banks in **Kuala Lumpur** collected **{kl:.0f}%** of all of Malaysia's donations in {full}.",
                    f"Bank darah di **Kuala Lumpur** mengumpul **{kl:.0f}%** daripada semua derma Malaysia pada {full}."),
                  f"KL daily ÷ Malaysia daily, {full}"))

    n = data["newdonors"]
    g19 = n[(n["state"] == "Malaysia") & (n["year"] == 2019)]["17-24"].sum()
    gf = n[(n["state"] == "Malaysia") & (n["year"] == full)]["17-24"].sum()
    drop = (g19 - gf) / g19 * 100
    facts.append((t(f"Gen Z first-time donors dropped from **{g19:,}** in 2019 to **{gf:,}** in {full}, a fall of **{drop:.0f}%**.",
                    f"Penderma kali pertama Gen Z turun daripada **{g19:,}** pada 2019 kepada **{gf:,}** pada {full}, jatuh **{drop:.0f}%**."),
                  "newdonors_state 17-24, Malaysia"))

    secs, total = seconds_per_donation(data)
    facts.append((t(f"In {full}, someone in Malaysia donated blood about **every {secs:.0f} seconds**.",
                    f"Pada {full}, seseorang di Malaysia menderma darah kira-kira **setiap {secs:.0f} saat**."),
                  f"seconds in {full} ÷ {total:,.0f} donations"))

    fe = festive_effect(data, "Hari Raya Aidilfitri")
    facts.append((t(f"On the first day of **Hari Raya Aidilfitri**, donations usually drop by about **{-fe['change %'].median():.0f}%**.",
                    f"Pada hari pertama **Hari Raya Aidilfitri**, derma biasanya jatuh kira-kira **{-fe['change %'].median():.0f}%**."),
                  "festival day vs median of 2 weeks around it, 2015–2025"))
    return facts


def blood_type_profile(data, blood_type, year=None):
    """Share of donations of one blood type in every state (for 'My blood type')."""
    year = year or data["latest_full_year"]
    col = f"blood_{blood_type.lower()}"
    d = data["donations"][data["donations"]["year"] == year]
    g = d.groupby("state")[["blood_a", "blood_b", "blood_o", "blood_ab"]].sum()
    out = pd.DataFrame({"state": g.index, "donations": g[col].values,
                        "percent": (g[col] / g.sum(axis=1) * 100).values})
    return out.sort_values("percent", ascending=False).reset_index(drop=True)


def daily_calendar(data, state, year):
    """Daily donations for one state and year (for the calendar heatmap)."""
    d = data["donations"]
    d = d[(d["state"] == state) & (d["year"] == year)][["date", "daily"]].copy()
    d["week"] = d["date"].dt.isocalendar().week.astype(int)
    d.loc[(d["date"].dt.month == 1) & (d["week"] > 50), "week"] = 0
    d.loc[(d["date"].dt.month == 12) & (d["week"] == 1), "week"] = 53
    d["weekday"] = d["date"].dt.weekday
    return d


# ---------------------------------------------------------------------------
# 8. FESTIVE EFFECT
# ---------------------------------------------------------------------------
# First day of each festival (Malaysian public holiday calendar).
# The Aidilfitri dates were checked against the data: each one is the
# lowest-donation day in the 4 weeks around it.
FESTIVALS = {
    "Hari Raya Aidilfitri": ["2015-07-17", "2016-07-06", "2017-06-25", "2018-06-15", "2019-06-05", "2020-05-24",
                             "2021-05-13", "2022-05-02", "2023-04-22", "2024-04-10", "2025-03-31"],
    "Chinese New Year": ["2015-02-19", "2016-02-08", "2017-01-28", "2018-02-16", "2019-02-05", "2020-01-25",
                         "2021-02-12", "2022-02-01", "2023-01-22", "2024-02-10", "2025-01-29"],
    "Deepavali": ["2015-11-10", "2016-10-29", "2017-10-18", "2018-11-06", "2019-10-27", "2020-11-14",
                  "2021-11-04", "2022-10-24", "2023-11-12", "2024-10-31", "2025-10-20"],
}


def festive_effect(data, festival, state="Malaysia"):
    """Donations on the festival day vs a normal day (median of the 2 weeks before and after)."""
    d = data["donations"]
    s = d[d["state"] == state].set_index("date")["daily"]
    rows = []
    for x in FESTIVALS[festival]:
        day = pd.Timestamp(x)
        around = pd.concat([s[day - pd.Timedelta(days=14): day - pd.Timedelta(days=1)],
                            s[day + pd.Timedelta(days=1): day + pd.Timedelta(days=14)]])
        if day in s.index and len(around):
            normal = around.median()
            rows.append({"year": day.year, "date": day, "on the day": int(s[day]), "normal day": float(normal),
                         "change %": (s[day] - normal) / normal * 100})
    return pd.DataFrame(rows)


def ramadan_effect(data, state="Malaysia"):
    """Average daily donations in the 29 days before Aidilfitri (Ramadan) vs the 29 days before that."""
    d = data["donations"]
    s = d[d["state"] == state].set_index("date")["daily"]
    rows = []
    for x in FESTIVALS["Hari Raya Aidilfitri"]:
        raya = pd.Timestamp(x)
        ramadan = s[raya - pd.Timedelta(days=29): raya - pd.Timedelta(days=1)]
        before = s[raya - pd.Timedelta(days=58): raya - pd.Timedelta(days=30)]
        rows.append({"year": raya.year, "Ramadan (avg/day)": ramadan.mean(), "month before (avg/day)": before.mean(),
                     "change %": (ramadan.mean() - before.mean()) / before.mean() * 100})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 9. DONOR HERO CARD (a fun picture; not an official certificate)
# ---------------------------------------------------------------------------
def make_hero_card(data, name, blood_type, state):
    """Draw a shareable PNG card with real facts about the visitor's blood type. Returns PNG bytes."""
    import io
    from PIL import Image, ImageDraw, ImageFont

    full = data["latest_full_year"]
    prof = blood_type_profile(data, blood_type, full)
    nat = prof[prof["state"] == "Malaysia"].iloc[0]
    mine = prof[prof["state"] == state].iloc[0]
    every_min = (365 * 24 * 60) / mine["donations"] if mine["donations"] else None

    fonts = Path(__file__).parent / "assets" / "fonts"

    def font(size, weight="regular"):
        file = {"regular": "Inter-Regular.otf", "semi": "Inter-SemiBold.otf", "black": "InterDisplay-ExtraBold.otf"}[weight]
        try:
            return ImageFont.truetype(str(fonts / file), size)
        except Exception:
            try:
                return ImageFont.load_default(size=size)
            except TypeError:  # very old Pillow
                return ImageFont.load_default()

    W, H = 1200, 675
    img = Image.new("RGB", (W, H), "#FBF6F4")
    draw = ImageDraw.Draw(img)
    # left red panel with a soft gradient
    for x in range(430):
        k = x / 430
        r, g, b = int(163 - 70 * k), int(18 - 10 * k), int(42 - 20 * k)
        draw.line([(x, 0), (x, H)], fill=(r, g, b))
    for yy in range(18, H, 34):                 # dotted pattern like the website
        for xx in range(18, 430, 34):
            draw.ellipse([xx - 2, yy - 2, xx + 2, yy + 2], fill=(255, 255, 255, 40) if False else (176, 60, 75))
    # blood drop with the blood type
    import math
    cx, cy, rad = 215, 360, 120
    # tear-drop outline: x = sin(t)·sin(t/2), y = cos(t)  (point at the top, round at the bottom)
    pts = []
    for i in range(361):
        a = math.radians(i)
        pts.append((cx + 1.45 * rad * math.sin(a) * math.sin(a / 2), cy + 30 - 1.55 * rad * math.cos(a)))
    draw.polygon(pts, fill="white")
    f_type = font(150 if len(blood_type) == 1 else 120, "black")
    tw = draw.textlength(blood_type, font=f_type)
    draw.text((cx - tw / 2, cy - 82), blood_type, fill=RED, font=f_type)
    draw.text((40, 40), "DarahBot", fill="white", font=font(34, "black"))
    draw.text((40, 84), "Donor Hero Card", fill=(255, 205, 212), font=font(22, "semi"))
    draw.text((40, H - 60), "@amirrulmukminin · CSC649", fill=(255, 205, 212), font=font(18, "semi"))

    x0 = 480
    draw.text((x0, 60), "THIS CARD BELONGS TO", fill=RED, font=font(20, "semi"))
    draw.text((x0, 92), (name.strip() or "A future donor")[:24], fill=INK, font=font(64, "black"))
    draw.text((x0, 172), "Kad ini milik wira penderma darah", fill=MUTED, font=font(20))
    draw.text((x0, 240), f"{nat['percent']:.1f}%", fill=RED, font=font(70, "black"))
    draw.text((x0, 322), f"of donations in Malaysia were type {blood_type} ({full})", fill=INK, font=font(24, "semi"))
    draw.text((x0, 354), f"daripada derma di Malaysia ialah jenis {blood_type}", fill=MUTED, font=font(19))
    y = 420
    lines = [(f"In {state}: {mine['donations']:,.0f} type {blood_type} bags in {full}", f"Di {state}: {mine['donations']:,.0f} beg jenis {blood_type}")]
    if every_min:
        lines.append((f"That's about one every {every_min:.0f} minutes", f"Kira-kira satu setiap {every_min:.0f} minit"))
    lines.append(("Your blood type can help someone today.", "Jenis darah anda boleh membantu seseorang hari ini."))
    for en, ms in lines:
        draw.text((x0, y), en, fill=INK, font=font(23, "semi"))
        draw.text((x0, y + 30), ms, fill=MUTED, font=font(18))
        y += 70
    draw.text((x0, H - 52), "Source: KKM data-darah-public, computed by DarahBot. A fun card, not an official certificate.",
              fill=MUTED, font=font(15))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
