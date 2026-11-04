"""Small typos and short forms (BM and English) must still be understood."""
import bot_engine as bot
data = bot.load_data()
QS = ["saya bleh dermah darah ke?", "brp derma darah kt melaka 2024", "hosptal mana paling bnyak kumpul darah", "can i donnate blod",
      "umor 17 bleh derma x", "whch state had the moust donations", "kalo berat 40 layak x derma drah", "tatoo boleh derma?",
      "selangr 2024 derma", "berpa ramai pnderma baru 2025", "Berapa derma di melak 2024?", "johor vs selangor gen z"]
bad = 0
for q in QS:
    r = bot.answer(q, data, None, "bm")
    ok = r["kind"] == "ok"
    bad += not ok
    print(("PASS " if ok else "FAIL ") + q)
r = bot.answer("Who is the prime minister?", data, None, "en")
bad += r["kind"] != "refuse"
print(("PASS " if r["kind"] == "refuse" else "FAIL ") + "unrelated question still refused")
print(f"\nRESULT: {len(QS) + 1 - bad} passed, {bad} failed")
