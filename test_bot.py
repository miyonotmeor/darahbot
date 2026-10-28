"""
test_bot.py  -  checks DarahBot's answers (Activity 7: test, debug and verify)
=============================================================================
Run with:   python test_bot.py

Part A recomputes answers DIRECTLY from the CSV files (simple pandas, without
using bot_engine) and checks the bot gives the same numbers.
Part B checks the tricky cases: misspelling, unknown state, missing year,
unsupported and "why" questions.
"""

import pandas as pd
import bot_engine as bot

data = bot.load_data()
raw_d = pd.read_csv("data/donations_state.csv")
raw_n = pd.read_csv("data/newdonors_state.csv")
raw_d["year"] = raw_d["date"].str[:4].astype(int)
raw_n["year"] = raw_n["date"].str[:4].astype(int)

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


print("\nPART A - numbers recomputed straight from the CSV")

# 1 lookup
direct = raw_d[(raw_d.state == "Melaka") & (raw_d.year == 2025)]["daily"].sum()
check("Melaka donations 2025", bot.lookup(data, "donations", "Melaka", 2025) == direct, direct)

# 2 comparison
m = raw_n[(raw_n.state == "Melaka") & (raw_n.year == 2025)]["17-24"].sum()
j = raw_n[(raw_n.state == "Johor") & (raw_n.year == 2025)]["17-24"].sum()
c = bot.compare(data, "genz", "Melaka", "Johor", 2025)
check("Compare Melaka vs Johor Gen Z 2025", (c["a"], c["b"]) == (m, j), (m, j))

# 3 highest
by_state = raw_d[(raw_d.year == 2025) & (raw_d.state != "Malaysia")].groupby("state")["daily"].sum()
check("Highest donations 2025", bot.rank(data, "donations", 2025).iloc[0]["state"] == by_state.idxmax(), by_state.idxmax())

# 4 lowest
check("Lowest donations 2025", bot.rank(data, "donations", 2025, lowest=True).iloc[0]["state"] == by_state.idxmin())

# 5 average
avg = raw_n[(raw_n.year == 2024) & (raw_n.state != "Malaysia")].groupby("state")["total"].sum().mean()
check("Average new donors per state 2024", abs(bot.summary(data, "new_donors", 2024)["mean"] - avg) < 1e-6, avg)

# 6 state totals add up to the Malaysia row
nat = raw_d[(raw_d.state == "Malaysia") & (raw_d.year == 2025)]["daily"].sum()
check("States add up to Malaysia total (2025)", by_state.sum() == nat, (by_state.sum(), nat))

# 7 Gen Z share
row = raw_n[(raw_n.state == "Melaka") & (raw_n.year == 2019)][["17-24", "total"]].sum()
check("Gen Z share Melaka 2019", abs(bot.lookup(data, "genz_share", "Melaka", 2019) - row["17-24"] / row["total"] * 100) < 1e-9)

# 8 blood types sum to total donations
t = raw_d[(raw_d.state == "Selangor") & (raw_d.year == 2025)]
# Finding: a handful of donations have no blood type recorded, so A+B+O+AB is a
# tiny bit lower than the total (about 0.005%). We check it is within 0.01%.
types, total = t[["blood_a", "blood_b", "blood_o", "blood_ab"]].sum().sum(), t["daily"].sum()
check(f"Blood types vs total (Selangor 2025): {total - types} donations without a type", abs(total - types) / total < 0.0001)

print("\nPART B - robustness")
cases = [
    ("Misspelling: 'melak'", "How many donors in melak 2024?", "ok", "Melaka"),
    ("Alias: 'KL' and 'Penang'", "Compare KL vs Penang 2025", "ok", "Kuala Lumpur"),
    ("State not in data", "Perlis donations 2024", "refuse", "Perlis"),
    ("Year not in data", "Melaka donations 2035", "refuse", "2035"),
    ("Year before data", "Johor donations 1999", "refuse", "1999"),
    ("Why question", "Why did donations drop?", "refuse", "cannot answer"),
    ("Prediction", "Predict Johor donations next year", "refuse", "cannot predict"),
    ("Unsupported question", "Who is the prime minister?", "refuse", "not sure"),
    ("Ambiguous compare", "Compare Melaka", "clarify", "two"),
    ("Empty message", "   ", "clarify", "Type a question"),
    ("Bahasa Melayu", "Negeri mana paling tinggi penderma muda 2025?", "ok", "highest"),
    ("Partial year flagged", "Melaka donations 2026", "ok", "partial year"),
]
for name, q, kind, must_contain in cases:
    r = bot.answer(q, data)
    check(name, r["kind"] == kind and must_contain.lower() in (r["text"] + " ".join(r["notes"])).lower(),
          f"-> {r['kind']}: {r['text'][:90]}")

# Follow-up memory: "what about Johor?" continues the previous comparison
first = bot.answer("Compare Melaka and Kedah Gen Z donors in 2025", data)
follow = bot.answer("what about Johor?", data, first["context"])
check("Follow-up memory ('what about Johor?')", "Melaka" in follow["text"] and "Johor" in follow["text"] and "2,397" in follow["text"],
      follow["text"][:90])

# Fun fact recomputed directly
secs, total = bot.seconds_per_donation(data, 2025)
check("'Every N seconds' fact (2025)", abs(secs - 365 * 86400 / nat) < 1e-9, secs)

print("\nPART C - new features")
# Hospital totals add up exactly to each state's total (proves the hospital->state mapping)
fac = pd.read_csv("data/donations_facility.csv").merge(pd.read_csv("data/hospital_state.csv"), on="hospital")
diff = (fac.groupby("state")["daily"].sum() - raw_d[raw_d.state != "Malaysia"].groupby("state")["daily"].sum()).abs().sum()
check("Hospital totals = state totals (all years)", diff == 0, diff)

fac["year"] = fac["date"].str[:4].astype(int)
top = fac[fac.year == 2025].groupby("hospital")["daily"].sum().idxmax()
check("Top hospital 2025 matches CSV", bot.hospital_ranking(data, 2025).iloc[0]["hospital"] == top, top)

# Bahasa Melayu answers give the same numbers as English
en = bot.answer("Compare Melaka and Johor Gen Z donors in 2025", data)
ms = bot.answer("Bandingkan Melaka dan Johor penderma muda 2025", data, lang="bm")
check("BM answer has same numbers as English", "2,211" in ms["text"] and "2,397" in ms["text"] and "mencatat" in ms["text"])
check("BM refusal for 'kenapa'", bot.answer("kenapa makin kurang", data, lang="bm")["kind"] == "refuse")

# Off-topic short question is NOT treated as a follow-up
check("Off-topic short question not a follow-up", bot.answer("siapa perdana menteri", data, first["context"], "bm")["kind"] == "refuse")

# Festive effect recomputed by hand for Raya 2025 (31 Mar 2025)
s = raw_d[raw_d.state == "Malaysia"].set_index("date")["daily"]
check("Raya 2025 donations on the day = CSV", int(bot.festive_effect(data, "Hari Raya Aidilfitri").set_index("year").loc[2025, "on the day"]) == s["2025-03-31"])

# Hero card is a real PNG
png = bot.make_hero_card(data, "Test", "AB", "Melaka")
check("Hero card makes a PNG image", png[:8] == b"\x89PNG\r\n\x1a\n")

print("\nPART D - October 2026 update: survey + 'Can I donate?'")
# Eligibility rules (same 5 rules as the survey website)
ok = bot.check_eligibility(22, 55, 7, False, 0)
check("Eligible person passes all 5 rules", all(p for p, *_ in ok))
no = bot.check_eligibility(17, 42, 4, True, 3)
check("Not-eligible person fails all 5 rules", not any(p for p, *_ in no))
check("'Can I donate?' is understood", bot.answer("Can I donate blood?", data)["evidence"]["source"] == bot.SOURCE_RULES)
check("'Bolehkah saya derma?' is understood (BM)", bot.detect_intent("bolehkah saya derma darah") == "eligible")

# Survey answers: recompute by hand from a small made-up table
fake = pd.DataFrame([
    dict(ever_donated="Yes", age=22, weight_kg=55, sleep_hours=7, tattoo_12m="No", meds_days_per_month=0, willingness=8, last_result="Accepted", state="Melaka", name="X", email="x@y.com"),
    dict(ever_donated="Yes", age=30, weight_kg=70, sleep_hours=6, tattoo_12m="No", meds_days_per_month=0, willingness=9, last_result="Deferred", state="Johor", name="Y", email="y@y.com"),
    dict(ever_donated="No", age=20, weight_kg=50, sleep_hours=6, tattoo_12m="No", meds_days_per_month=0, willingness=7, last_result=None, state="Melaka", name="Z", email="z@y.com"),
    dict(ever_donated="No", age=17, weight_kg=40, sleep_hours=6, tattoo_12m="No", meds_days_per_month=0, willingness=5, last_result=None, state="Kedah", name="W", email="w@y.com"),
])
fake.to_csv("_test_survey.csv", index=False)
sv = bot.load_survey("_test_survey.csv")
import os; os.remove("_test_survey.csv")
check("Survey loader drops names and emails", "name" not in sv.columns and "email" not in sv.columns)
sm = bot.survey_summary(sv)
check("Survey counts: 4 answers, 2 donors, 2 never", (sm["n"], sm["donors"], sm["never"]) == (4, 2, 2), sm)
check("Survey: 1 accepted, 1 deferred", (sm["accepted"], sm["deferred"]) == (1, 1), sm)
check("Survey: 1 first-timer probably eligible", (sm["likely"], sm["not_yet"]) == (1, 1), sm)
r = bot.answer("How many people answered the survey from Melaka?", data, survey=sv)
check("Survey question filtered by state (Melaka = 2)", "**2** people" in r["text"], r["text"][:80])
check("No survey connected -> honest refusal", bot.answer("how many survey respondents", data, survey=None)["kind"] == "refuse")
check("Missing survey link -> None (no crash)", bot.load_survey("") is None and bot.load_survey("https://invalid.invalid/x.csv") is None)

print(f"\nRESULT: {passed} passed, {failed} failed\n")
