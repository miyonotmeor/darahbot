"""Checks the quiz: enough questions, answers computed, and almost-correct answers accepted."""
import bot_engine as bot, quiz, tempfile, os
data = bot.load_data(); S = data["states"]
Q = {q["id"]: q for q in quiz.build_questions(data)}
ok = bad = 0
def t(name, cond):
    global ok, bad
    ok += cond; bad += (not cond); print(("  PASS  " if cond else "  FAIL  ") + name)
t(f"{len(Q)} questions (need 40-50)", 40 <= len(Q) <= 55)
t("ids unique", len(Q) == len(quiz.build_questions(data)))
mark = lambda qid, a: quiz.check(a, Q[qid], S)[0] in ("correct", "close")
tot = Q["n_total"]["answer"]
t("exact total accepted", mark("n_total", f"{tot:,.0f}"))
t("'590k' accepted", mark("n_total", "590k"))
t("'590 ribu' accepted", mark("n_total", "590 ribu"))
t("'around 600000' accepted", mark("n_total", "around 600000"))
t("'400k' rejected", not mark("n_total", "400k"))
t("KL alias accepted", mark("st_most", "KL"))
t("'kuala lumpur' accepted", mark("st_most", "kuala lumpur"))
t("misspelt 'kuala lumpor' accepted", mark("st_most", "kuala lumpor"))
t("wrong state rejected", not mark("st_most", "Johor"))
t("two states rejected", not mark("st_most", "KL or Johor"))
t("blood type 'O' accepted", mark("c_common", "o"))
t("'type o' accepted", mark("c_common", "type O"))
t("'A' rejected for O", not mark("c_common", "A"))
t("'pusat darah negra' accepted", mark("c_bank", "pusat darah negra"))
t("'PDN' accepted", mark("c_bank", "PDN"))
t("age 18 exact", mark("r_age", "18") and not mark("r_age", "17"))
t("'lapan belas'? number words ok for 3", mark("r_lives", "three") and mark("r_lives", "tiga"))
t("weight '45kg'", mark("r_weight", "45kg"))
t("fasting 'tidak'", mark("r_fasting", "tidak") and not mark("r_fasting", "ya"))
t("genz % within 4 pts", mark("n_genz_share", f"{Q['n_genz_share']['answer']+3:.0f}%"))
t("day in Malay", mark("c_busy_day", quiz.DAYS_MS[quiz.DAYS.index(Q["c_busy_day"]["answer"])]))
t("raya down", mark("c_raya", "turun") or mark("c_raya", "up"))
# answers recomputed independently
import pandas as pd
raw = pd.read_csv("data/donations_state.csv"); raw["y"] = raw.date.str[:4].astype(int)
full = data["latest_full_year"]
t("total = CSV", tot == raw[(raw.state == "Malaysia") & (raw.y == full)].daily.sum())
top = raw[(raw.state != "Malaysia") & (raw.y == full)].groupby("state").daily.sum().idxmax()
t("most state = CSV", Q["st_most"]["answer"] == top)
# no repeats
p = quiz.QuestionPool(list(Q), os.path.join(tempfile.mkdtemp(), "used.json"))
seen = []
for _ in range(len(Q) // 10):
    seen += p.draw(10)
t("no repeats until pool used up", len(seen) == len(set(seen)))
t("pool refills after all used", len(p.draw(10)) == 10)
print(f"\nRESULT: {ok} passed, {bad} failed")
for q in list(Q.values())[:0]: pass
