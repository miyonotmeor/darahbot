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
    ("per_capita", [r"per ?capita", r"per (1,?000|thousand|person|people|orang)", r"\brate\b", r"\bkadar\b", r"\bfair\b"]),
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
    if re.search(r"\b(eligible|eligibility|layak|kelayakan|can i donate|am i allowed|boleh saya derma|bolehkah saya|boleh ke saya)\b", t):
        return "eligible"
    if re.search(r"\b(predict|forecast|will be|next year|future|ramal|akan datang|tahun depan)\b", t):
        return "predict"
    if re.search(r"\b(blood types|jenis darah|types of blood|breakdown|composition|pecahan)\b", t):
        return "breakdown"
    if re.search(r"\b(compare|comparison|vs\.?|versus|banding|bandingkan|beza|difference)\b", t):
        return "compare"
    if re.search(r"\b(trend|over the years|over time|changed?|berubah|sejak|since|growth|increase|decrease|naik|turun)\b", t):
        return "trend"
    if re.search(r"\b(highest|most|top|lowest|least|fewest|rank|ranking|paling|tertinggi|terendah|terbanyak|tersedikit|best|worst)\b", t):
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

    intent = detect_intent(q)
    states, corrections = find_states(q, data["states"])
    years = find_years(q)
    metric = find_metric(q)
    hospital_q = bool(re.search(r"\b(hospitals?|blood banks?|pusat darah|facilit(y|ies))\b", q.lower()))

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
    if intent == "eligible":
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

    if intent == "trend":
        place = states or ["Malaysia"]
        if len(years) >= 2:
            y1, y2 = min(years), max(years)
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
