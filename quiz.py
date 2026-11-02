"""
quiz.py  -  DarahBot Blood Quiz
================================
* build_questions(data) makes ~48 questions. Every data answer is COMPUTED from the
  KKM CSV files with pandas (nothing typed in by hand), so the quiz is always correct.
* check(answer, question) marks a typed answer and accepts "almost correct" answers:
    - numbers: within a tolerance (e.g. 589,866 -> "590k", "590 ribu", "around 600,000")
    - states: aliases and spelling mistakes ("KL", "melak", "penang")
    - words: small spelling mistakes ("pusat darah negra", "typ O")
* QuestionPool hands out questions so the SAME question is not given again to the
  next person, until every question has been used once.
"""

import difflib
import json
import random
import re
import threading
from pathlib import Path

import pandas as pd

import bot_engine as bot

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAYS_MS = ["Isnin", "Selasa", "Rabu", "Khamis", "Jumaat", "Sabtu", "Ahad"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
MONTHS_MS = ["Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September",
             "Oktober", "November", "Disember"]
YES = ["yes", "ya", "y", "true", "yup", "yep", "yeah", "ye", "yea", "yess", "yas", "iya", "iye", "betol", "ok", "okay", "correct", "right", "sure", "betul", "benar", "up", "naik", "increase", "increased", "bertambah", "more", "lebih"]
NO = ["no", "tidak", "tak", "nope", "nah", "nop", "noo", "tk", "tidk", "tdk", "x", "bukan", "takde", "tiada", "never", "not", "cannot", "cant", "wrong", "incorrect", "x", "false", "salah", "down", "turun", "decrease", "decreased", "berkurang", "less", "kurang", "fell", "drop"]


def _fmt(v):
    if float(v).is_integer() and 1900 <= v <= 2100:
        return f"{v:.0f}"                      # years: 2006, not 2,006
    return f"{v:,.0f}" if abs(v) >= 100 else (f"{v:.1f}".rstrip("0").rstrip(".") if v % 1 else f"{v:.0f}")


# ---------------------------------------------------------------------------
# 1. QUESTIONS (computed from the data)
# ---------------------------------------------------------------------------
def build_questions(data):
    full = data["latest_full_year"]
    prev = full - 1
    Q = []
    SKIP = {"st_new", "st_student", "st_mobile", "st_genz_lo", "cmp_new_pk", "n_sgr", "n_prk", "n_pct_b", "n_best_day"}

    def add(qid, en, ms, kind, answer, show, accept=None, tol=0.10, unit="", hint="", hint_ms="", source=bot.SOURCE_DONATIONS):
        if qid in SKIP:          # kept out to avoid near-duplicate questions
            return
        Q.append(dict(id=qid, en=en, ms=ms, kind=kind, answer=answer, show=show, accept=accept or [],
                      tol=tol, unit=unit, hint=hint, hint_ms=hint_ms, source=source))

    # ---- which state ... (answer = a state) ------------------------------------
    def top_state(metric, year, lowest=False):
        return bot.rank(data, metric, year, lowest=lowest).iloc[0]["state"]

    add("st_most", f"Which state had the MOST blood donations in {full}?", f"Negeri mana paling banyak derma darah pada {full}?",
        "state", top_state("donations", full), top_state("donations", full), hint="It has the National Blood Centre.",
        hint_ms="Pusat Darah Negara terletak di sini.")
    add("st_least", f"Which state had the FEWEST blood donations in {full}?", f"Negeri mana paling sedikit derma darah pada {full}?",
        "state", top_state("donations", full, True), top_state("donations", full, True))
    add("st_new", f"Which state had the most NEW donors in {full}?", f"Negeri mana paling ramai penderma baru pada {full}?",
        "state", top_state("new_donors", full), top_state("new_donors", full), source=bot.SOURCE_NEWDONORS)
    add("st_genz", f"Which state had the most Gen Z (17–24) new donors in {full}?", f"Negeri mana paling ramai penderma baru Gen Z (17–24) pada {full}?",
        "state", top_state("genz", full), top_state("genz", full), source=bot.SOURCE_NEWDONORS)
    add("st_pc_hi", "Which state had the HIGHEST donations per 1,000 adults in 2020?", "Negeri mana paling tinggi derma bagi setiap 1,000 dewasa pada 2020?",
        "state", top_state("per_capita", 2020), top_state("per_capita", 2020))
    add("st_pc_lo", "Which state had the LOWEST donations per 1,000 adults in 2020?", "Negeri mana paling rendah derma bagi setiap 1,000 dewasa pada 2020?",
        "state", top_state("per_capita", 2020, True), top_state("per_capita", 2020, True))
    add("st_student", f"Which state had the most donations by STUDENTS in {full}?", f"Negeri mana paling banyak derma oleh pelajar pada {full}?",
        "state", top_state("students", full), top_state("students", full))
    add("st_mobile", f"Which state had the most donations at MOBILE drives in {full}?", f"Negeri mana paling banyak derma di kempen bergerak pada {full}?",
        "state", top_state("mobile", full), top_state("mobile", full))
    add("st_2nd", f"Which state came SECOND for blood donations in {full}?", f"Negeri mana di tempat KEDUA bagi derma darah pada {full}?",
        "state", bot.rank(data, "donations", full).iloc[1]["state"], bot.rank(data, "donations", full).iloc[1]["state"])
    add("st_genz_lo", f"Which state had the FEWEST Gen Z new donors in {full}?", f"Negeri mana paling sedikit penderma baru Gen Z pada {full}?",
        "state", top_state("genz", full, True), top_state("genz", full, True), source=bot.SOURCE_NEWDONORS)

    # ---- comparisons (answer = one of two states) ------------------------------
    for qid, a, b_, metric, en_m, ms_m, src in [
        ("cmp_genz_mj", "Melaka", "Johor", "genz", "Gen Z new donors", "penderma baru Gen Z", bot.SOURCE_NEWDONORS),
        ("cmp_don_sp", "Selangor", "Perak", "donations", "blood donations", "derma darah", bot.SOURCE_DONATIONS),
        ("cmp_don_ks", "Kedah", "Sarawak", "donations", "blood donations", "derma darah", bot.SOURCE_DONATIONS),
        ("cmp_new_pk", "Pulau Pinang", "Kelantan", "new_donors", "new donors", "penderma baru", bot.SOURCE_NEWDONORS),
    ]:
        c = bot.compare(data, metric, a, b_, full)
        win = a if c["a"] >= c["b"] else b_
        add(qid, f"Who had more {en_m} in {full}: {a} or {b_}?", f"Siapa lebih banyak {ms_m} pada {full}: {a} atau {b_}?",
            "state", win, f"{win} ({_fmt(max(c['a'], c['b']))} vs {_fmt(min(c['a'], c['b']))})", source=src)

    # ---- numbers ---------------------------------------------------------------
    def num(qid, en, ms, value, unit="", tol=0.10, hint="", hint_ms="", source=bot.SOURCE_DONATIONS):
        add(qid, en, ms, "num", float(value), f"{_fmt(value)}{(' ' + unit) if unit else ''}", tol=tol, unit=unit,
            hint=hint, hint_ms=hint_ms, source=source)

    look = lambda m, s, y: bot.lookup(data, m, s, y)
    num("n_total", f"About how many blood donations were there in Malaysia in {full}?",
        f"Lebih kurang berapa derma darah di Malaysia pada {full}?", look("donations", "Malaysia", full), "donations",
        hint="Between 500,000 and 700,000.", hint_ms="Antara 500,000 dan 700,000.")
    num("n_total_prev", f"About how many blood donations were there in Malaysia in {prev}?",
        f"Lebih kurang berapa derma darah di Malaysia pada {prev}?", look("donations", "Malaysia", prev), "donations")
    num("n_new", f"About how many NEW (first-time) donors were there in Malaysia in {full}?",
        f"Lebih kurang berapa penderma BARU di Malaysia pada {full}?", look("new_donors", "Malaysia", full), "people",
        source=bot.SOURCE_NEWDONORS)
    num("n_genz", f"About how many Gen Z (17–24) new donors were there in Malaysia in {full}?",
        f"Lebih kurang berapa penderma baru Gen Z di Malaysia pada {full}?", look("genz", "Malaysia", full), "people",
        source=bot.SOURCE_NEWDONORS)
    num("n_genz19", "About how many Gen Z (17–24) new donors were there in Malaysia in 2019?",
        "Lebih kurang berapa penderma baru Gen Z di Malaysia pada 2019?", look("genz", "Malaysia", 2019), "people",
        source=bot.SOURCE_NEWDONORS)
    num("n_genz_share", f"What percentage of new donors were Gen Z (17–24) in {full}?",
        f"Berapa peratus penderma baru ialah Gen Z (17–24) pada {full}?", look("genz_share", "Malaysia", full), "%",
        tol=4, source=bot.SOURCE_NEWDONORS)
    for st, qid in [("Melaka", "n_mlk"), ("Johor", "n_jhr"), ("Selangor", "n_sgr"), ("Perak", "n_prk"),
                    ("W.P. Kuala Lumpur", "n_kl")]:
        nm = "Kuala Lumpur" if st.startswith("W.P.") else st
        num(qid, f"About how many blood donations were there in {nm} in {full}?",
            f"Lebih kurang berapa derma darah di {nm} pada {full}?", look("donations", st, full), "donations", tol=0.15)
    num("n_mlk_genz", f"About how many Gen Z new donors were there in Melaka in {full}?",
        f"Lebih kurang berapa penderma baru Gen Z di Melaka pada {full}?", look("genz", "Melaka", full), "people",
        tol=0.15, source=bot.SOURCE_NEWDONORS)
    g19, gf = look("genz", "Malaysia", 2019), look("genz", "Malaysia", full)
    num("n_genz_drop", f"By about what percent did Gen Z new donors in Malaysia FALL from 2019 to {full}?",
        f"Lebih kurang berapa peratus penderma baru Gen Z di Malaysia TURUN dari 2019 ke {full}?",
        abs((gf - g19) / g19 * 100), "%", tol=6, source=bot.SOURCE_NEWDONORS)
    secs, _ = bot.seconds_per_donation(data)
    num("n_secs", f"In {full}, someone in Malaysia donated blood every how many SECONDS (on average)?",
        f"Pada {full}, seseorang di Malaysia menderma darah setiap berapa SAAT (purata)?", secs, "seconds", tol=0.15)
    prof = {bt: bot.blood_type_profile(data, bt, full) for bt in ["A", "B", "O", "AB"]}
    pct = {bt: float(p[p.state == "Malaysia"]["percent"].iloc[0]) for bt, p in prof.items()}
    for bt in ["O", "A", "B", "AB"]:
        num(f"n_pct_{bt.lower()}", f"About what percentage of donations in {full} were blood type {bt}?",
            f"Lebih kurang berapa peratus derma pada {full} ialah jenis darah {bt}?", pct[bt], "%", tol=4)
    num("n_states", "How many states does this dataset report separately?",
        "Berapa banyak negeri dilaporkan secara berasingan dalam set data ini?", len(data["states"]), "states", tol=0,
        hint="Perlis, Putrajaya and Labuan are grouped with nearby states.", hint_ms="Perlis, Putrajaya dan Labuan digabungkan.")
    num("n_first_year", "The KKM blood donation data starts in which year?",
        "Data derma darah KKM bermula pada tahun berapa?", bot.FIRST_YEAR, "", tol=0)
    num("n_banks", "How many government blood banks (hospitals) are in this dataset?",
        "Berapa banyak bank darah kerajaan (hospital) dalam set data ini?", data["facility"]["hospital"].nunique(), "blood banks", tol=1)
    d = data["donations"]
    nat = d[(d.state == "Malaysia") & (d.year == full)]
    num("n_best_day", f"What was the HIGHEST number of donations in Malaysia on a single day in {full}?",
        f"Berapakah bilangan derma TERTINGGI di Malaysia dalam satu hari pada {full}?", nat["daily"].max(), "donations", tol=0.15)
    num("n_avg_day", f"On average, about how many blood donations happened PER DAY in Malaysia in {full}?",
        f"Secara purata, lebih kurang berapa derma darah SETIAP HARI di Malaysia pada {full}?", nat["daily"].mean(), "donations", tol=0.12)

    # ---- choices / words ---------------------------------------------------------
    common = max(pct, key=pct.get)
    rare = min(pct, key=pct.get)
    add("c_common", f"Which blood type was donated the MOST in Malaysia in {full}?", f"Jenis darah mana paling banyak didermakan pada {full}?",
        "word", common, f"Type {common}", accept=[common, f"type {common}", f"jenis {common}", f"{common}+", f"{common} positive"])
    add("c_rare", f"Which blood type was donated the LEAST in Malaysia in {full}?", f"Jenis darah mana paling sedikit didermakan pada {full}?",
        "word", rare, f"Type {rare}", accept=[rare, f"type {rare}", f"jenis {rare}", f"{rare}+"])
    hr = bot.hospital_ranking(data, full)
    top_h = hr.iloc[0]["hospital"]
    add("c_bank", f"Which blood bank collected the most blood in {full}?", f"Bank darah mana paling banyak mengumpul darah pada {full}?",
        "word", top_h, top_h, accept=[top_h, "pdn", "national blood centre", "national blood center", "pusat darah"],
        source=bot.SOURCE_FACILITY)
    mlk = bot.hospital_ranking(data, full, state="Melaka").iloc[0]["hospital"]
    add("c_bank_mlk", f"Which hospital collected the most blood in Melaka in {full}?", f"Hospital mana paling banyak mengumpul darah di Melaka pada {full}?",
        "word", mlk, mlk, accept=[mlk, mlk.replace("Hospital ", ""), "melaka hospital", "hospital melaka"], source=bot.SOURCE_FACILITY)
    wk = nat.assign(wd=nat["date"].dt.weekday).groupby("wd")["daily"].mean()
    bd, qd = int(wk.idxmax()), int(wk.idxmin())
    add("c_busy_day", f"On which DAY of the week were donations highest on average in {full}?",
        f"Pada HARI apa derma paling tinggi secara purata pada {full}?", "day", bd, f"{DAYS[bd]} ({DAYS_MS[bd]})")
    add("c_quiet_day", f"On which DAY of the week were donations lowest on average in {full}?",
        f"Pada HARI apa derma paling rendah secara purata pada {full}?", "day", qd, f"{DAYS[qd]} ({DAYS_MS[qd]})")
    mo = nat.assign(m=nat["date"].dt.month).groupby("m")["daily"].sum()
    bm, qm = int(mo.idxmax()) - 1, int(mo.idxmin()) - 1
    add("c_busy_month", f"Which MONTH had the most blood donations in Malaysia in {full}?",
        f"BULAN mana paling banyak derma darah di Malaysia pada {full}?", "month", bm, f"{MONTHS[bm]} ({MONTHS_MS[bm]}) · month {bm + 1}")
    add("c_quiet_month", f"Which MONTH had the fewest blood donations in Malaysia in {full}?",
        f"BULAN mana paling sedikit derma darah di Malaysia pada {full}?", "month", qm, f"{MONTHS[qm]} ({MONTHS_MS[qm]}) · month {qm + 1}",
        hint="Think about Ramadan and Hari Raya.", hint_ms="Fikirkan tentang Ramadan dan Hari Raya.")
    fe = bot.festive_effect(data, "Hari Raya Aidilfitri")
    add("c_raya", "On the first day of Hari Raya Aidilfitri, do blood donations go UP or DOWN?",
        "Pada hari pertama Hari Raya Aidilfitri, adakah derma darah NAIK atau TURUN?", "bool",
        bool(fe["change %"].median() > 0), "Down (turun): almost no donations that day" if fe["change %"].median() < 0 else "Up (naik)")

    # ---- yes / no about the data --------------------------------------------------
    up = look("donations", "Malaysia", full) > look("donations", "Malaysia", prev)
    add("b_total_up", f"Did total blood donations in Malaysia go UP from {prev} to {full}? (yes / no)",
        f"Adakah jumlah derma darah di Malaysia NAIK dari {prev} ke {full}? (ya / tidak)", "bool", up, "Yes (ya)" if up else "No (tidak)")
    genz_up = gf > g19
    add("b_genz_up", f"Did Gen Z new donors in Malaysia go UP from 2019 to {full}? (yes / no)",
        f"Adakah penderma baru Gen Z di Malaysia NAIK dari 2019 ke {full}? (ya / tidak)", "bool", genz_up,
        "No (tidak): they fell" if not genz_up else "Yes (ya)", source=bot.SOURCE_NEWDONORS)
    kl_more = look("donations", "W.P. Kuala Lumpur", full) > look("donations", "Selangor", full)
    add("b_kl_sgr", f"Did Kuala Lumpur collect more blood donations than Selangor in {full}? (yes / no)",
        f"Adakah Kuala Lumpur mengumpul lebih banyak derma daripada Selangor pada {full}? (ya / tidak)", "bool", kl_more,
        "Yes (ya)" if kl_more else "No (tidak)")
    o_half = pct["O"] > 50
    add("b_o_half", f"Were MORE than half of all donations in {full} blood type O? (yes / no)",
        f"Adakah LEBIH separuh daripada semua derma pada {full} jenis darah O? (ya / tidak)", "bool", o_half,
        f"{'Yes' if o_half else 'No'}: type O was {pct['O']:.1f}%")

    # ---- donor rules (Pusat Darah Negara guidelines, not the KKM dataset) ---------
    R = bot.SOURCE_RULES if hasattr(bot, "SOURCE_RULES") else "Pusat Darah Negara donor rules"
    num("r_age", "What is the MINIMUM age to donate blood in Malaysia (without parent consent)?",
        "Berapakah umur MINIMUM untuk menderma darah di Malaysia (tanpa kebenaran ibu bapa)?", 18, "years", tol=0, source=R)
    num("r_weight", "What is the minimum body WEIGHT to donate blood?", "Berapakah BERAT badan minimum untuk menderma darah?",
        45, "kg", tol=0, source=R)
    num("r_sleep", "At least how many HOURS of sleep do you need the night before donating?",
        "Sekurang-kurangnya berapa JAM tidur diperlukan pada malam sebelum menderma?", 5, "hours", tol=0, source=R)
    num("r_tattoo", "How many MONTHS must you wait after a tattoo or piercing before donating?",
        "Berapa BULAN perlu menunggu selepas tatu atau tindik sebelum menderma?", 12, "months", tol=0, source=R)
    num("r_lives", "One blood donation can help save up to how many LIVES?", "Satu derma darah boleh membantu menyelamatkan sehingga berapa NYAWA?",
        3, "lives", tol=0, source=R)
    num("r_maxage", "What is the MAXIMUM age for a FIRST-time blood donor?", "Berapakah umur MAKSIMUM bagi penderma KALI PERTAMA?",
        60, "years", tol=0, source=R)
    add("r_fasting", "Can you donate blood while you are FASTING? (yes / no)", "Bolehkah anda menderma darah semasa BERPUASA? (ya / tidak)",
        "bool", False, "No (tidak): eat first and drink plenty of water", source=R)
    return Q


# ---------------------------------------------------------------------------
# 2. MARKING (accepts almost-correct answers)
# ---------------------------------------------------------------------------
def _norm(s):
    return re.sub(r"[^a-z0-9+ ]", " ", str(s).lower()).split()


def parse_number(text):
    """'590k', '590 ribu', '5.9 juta', '589,866', 'around 600000', '43%' -> float (or None)."""
    t = str(text).lower().replace(",", "").replace("rm", "")
    m = re.search(r"(-?\d+(?:\.\d+)?)(?:\s*(k|thousand|ribu|rb|m|mil|million|juta|j)\b)?", t)
    if not m:
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                 "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6, "tujuh": 7, "lapan": 8, "sembilan": 9, "sepuluh": 10,
                 "twelve": 12, "dua belas": 12, "sebelas": 11, "eleven": 11, "eighteen": 18, "lapan belas": 18, "forty five": 45, "sixty": 60}
        for w, v in sorted(words.items(), key=lambda x: -len(x[0])):
            if re.search(r"\b" + w + r"\b", t):
                return float(v)
        return None
    v = float(m.group(1))
    mult = m.group(2)
    if mult in ("k", "thousand", "ribu", "rb"):
        v *= 1_000
    elif mult in ("m", "mil", "million", "juta", "j"):
        v *= 1_000_000
    return v


# every way people write a month or a day (English, Malay, short forms, slang)
MONTH_WORDS = {}
for _i, (_en, _ms) in enumerate(zip(MONTHS, MONTHS_MS)):
    for _w in {_en.lower(), _ms.lower(), _en[:3].lower(), _ms[:3].lower(), _en[:4].lower()}:
        MONTH_WORDS[_w] = _i
MONTH_WORDS.update({"sept": 8, "okt": 9, "dis": 11, "ogo": 7, "mac": 2, "mei": 4, "julai": 6, "jul": 6, "jun": 5,
                    "febuari": 1, "febuary": 1, "feburary": 1, "agust": 7, "ogs": 7})
DAY_WORDS = {}
for _i, (_en, _ms) in enumerate(zip(DAYS, DAYS_MS)):
    for _w in {_en.lower(), _ms.lower(), _en[:3].lower(), _ms[:3].lower(), _en[:4].lower()}:
        DAY_WORDS[_w] = _i
DAY_WORDS.update({"tues": 1, "weds": 2, "thur": 3, "thurs": 3, "jumat": 4, "jummat": 4, "minggu": 6, "ahd": 6,
                  "isnen": 0, "slasa": 1, "kamis": 3, "sabtu": 5})
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
             "ten": 10, "eleven": 11, "twelve": 12, "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6,
             "tujuh": 7, "lapan": 8, "sembilan": 9, "sepuluh": 10, "sebelas": 11, "first": 1, "second": 2, "third": 3,
             "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
             "twelfth": 12, "pertama": 1, "kedua": 2, "ketiga": 3, "keempat": 4, "kelima": 5, "keenam": 6,
             "ketujuh": 7, "kelapan": 8, "kesembilan": 9, "kesepuluh": 10, "kesebelas": 11, "kedua belas": 12,
             "dua belas": 12}


def parse_choice(text, words, n):
    """Find which month (n=12) or day (n=7) someone meant: names, Malay, short forms, typos, or a number
    (1 = January / Monday). Returns a 0-based index, or None if unclear or more than one was given."""
    t = str(text).lower()
    found = set()
    toks = re.findall(r"[a-z]+|\d+", t)
    for tok in toks:
        if tok.isdigit():
            v = int(tok)
            if 1 <= v <= n and len(tok) <= 2:     # ignore years like 2025
                found.add(v - 1)
            continue
        if tok in words:
            found.add(words[tok])
            continue
        if len(tok) >= 4:                          # spelling mistakes: "febuary", "agoust", "wensday"
            best = difflib.get_close_matches(tok, [w for w in words if len(w) >= 4], n=1, cutoff=0.72)
            if best:
                found.add(words[best[0]])
    if not found:
        for w, v in sorted(NUM_WORDS.items(), key=lambda x: -len(x[0])):
            if v <= n and re.search(r"\b" + w + r"\b", t):
                found.add(v - 1)
                break
    return found.pop() if len(found) == 1 else None


def check(answer, q, states=None):
    """Return (result, message): result is 'correct', 'close' (counted correct) or 'wrong'."""
    a = str(answer or "").strip()
    if not a:
        return "wrong", "No answer"
    kind = q["kind"]
    if kind in ("month", "day"):
        got = parse_choice(a, MONTH_WORDS if kind == "month" else DAY_WORDS, 12 if kind == "month" else 7)
        if got is None:
            return "wrong", ""
        return ("correct", "") if got == q["answer"] else ("wrong", "")
    if kind == "num":
        v = parse_number(a)
        low = a.lower()
        if v is None and re.search(r"\b(a|one|se|satu)\s*(year|tahun)\b|setahun", low):
            v = 1.0
        # "1 year" for a question in months, "2 years" etc.
        if v is not None and q["unit"] in ("months", "month") and re.search(r"year|tahun", low):
            v *= 12
        if v is None:
            return "wrong", "That isn't a number"
        target = q["answer"]
        if v == target or abs(v - target) < 1e-9:
            return "correct", ""
        tol = q["tol"]
        diff = abs(v - target)
        if q["unit"] == "%":
            ok = diff <= tol                        # percentage points
        elif tol == 0:
            ok = diff < 0.5                         # rules and counts must be exact
        elif tol >= 1:
            ok = diff <= tol                        # small absolute tolerance
        else:
            ok = diff <= abs(target) * tol          # big numbers: within tol (e.g. 10%)
        if ok:
            return "close", "Close enough!"
        return "wrong", ""
    if kind == "state":
        found, _ = bot.find_states(a, states or [])
        found = [f for f in found if f != "Malaysia"]
        if q["answer"] in found and len(found) == 1:
            return "correct", ""
        # last try: one misspelt word against the right state ("selanor", "terenganu", "kualalumpur")
        target = q["answer"].lower().replace("w.p. ", "")
        squash = lambda x: re.sub(r"[^a-z]", "", x.lower())
        if not found and difflib.SequenceMatcher(None, squash(a), squash(target)).ratio() >= 0.75:
            return "close", "Close enough!"
        return "wrong", ""
    if kind == "bool":
        w = set(_norm(a))
        said_yes = bool(w & set(YES))
        said_no = bool(w & set(NO))
        if said_yes and said_no and w & {"not", "tak", "tidak", "never", "x", "bukan", "tk", "tdk", "tidk"}:
            said_yes = False                        # "not increase", "tak naik" mean no
        if said_yes == said_no:
            return "wrong", "Answer yes or no"
        return ("correct", "") if said_yes == bool(q["answer"]) else ("wrong", "")
    # free word answer: allow small spelling mistakes
    guess = " ".join(_norm(a))
    for acc in q["accept"]:
        target = " ".join(_norm(acc))
        if not target:
            continue
        if guess == target:
            return "correct", ""
        # short answers like blood types must match as a whole word
        if len(target) <= 3:
            if target in guess.split() or target.replace("+", "") in [g.replace("+", "") for g in guess.split()]:
                return "correct", ""
            continue
        if guess.replace(" ", "") == target.replace(" ", ""):
            return "correct", ""
        if target in guess or (len(guess) >= 4 and guess in target):
            return "close", "Close enough!"
        if difflib.SequenceMatcher(None, guess, target).ratio() >= 0.78:
            return "close", "Close enough!"
    return "wrong", ""


# ---------------------------------------------------------------------------
# 3. NO-REPEAT POOL (shared by everyone using the app)
# ---------------------------------------------------------------------------
class QuestionPool:
    """Gives out questions so the next person does not get the same ones, until all have been used."""

    def __init__(self, ids, path):
        self.ids = list(ids)
        self.path = Path(path)
        self.lock = threading.Lock()
        try:
            self.used = set(json.loads(self.path.read_text())) & set(self.ids)
        except Exception:
            self.used = set()

    def draw(self, n):
        with self.lock:
            free = [i for i in self.ids if i not in self.used]
            if len(free) < n:                       # everything has been used: start a fresh round
                keep = random.sample(free, len(free))
                self.used = set()
                rest = [i for i in self.ids if i not in keep]
                pick = keep + random.sample(rest, n - len(keep))
            else:
                pick = random.sample(free, n)
            self.used.update(pick)
            try:
                self.path.write_text(json.dumps(sorted(self.used)))
            except Exception:
                pass
            return pick

    def remaining(self):
        return len([i for i in self.ids if i not in self.used])
