"""Everyday visitor questions (EN + BM) must all get a real answer, not 'I'm not sure'."""
import bot_engine as bot
data = bot.load_data()
QS=["saya boleh derma darah ke?","boleh tak saya derma darah","layak ke saya derma darah?","can i give blood","am i eligible to donate","who can donate blood","siapa boleh derma darah","apa syarat derma darah","what are the requirements to donate blood",
"where can i donate blood in melaka","mana nak derma darah di johor","is donating blood safe","does it hurt to donate blood","sakit tak derma darah","how long does donating blood take","berapa lama derma darah",
"what blood type is the rarest","jenis darah paling jarang","what is my blood type","which blood type is most common","what blood type can receive from anyone","universal donor",
"how many people donate blood in malaysia","berapa ramai derma darah tahun lepas","donations in 2025","kl vs selangor","which state donates the least","trend of donations",
"how many donations today","berapa derma darah semalam","which month has most donations","when is the busiest day to donate","what happens to my blood after donating",
"benefits of donating blood","kebaikan derma darah","can i donate if i have diabetes","boleh derma kalau ada darah tinggi","can i donate during my period","can women donate blood",
"what is darahbot","who made you","siapa buat chatbot ni","thank you","terima kasih","how accurate is this data","where is the data from"]
bad = 0
for q in QS:
    lang = "bm" if any(w in q for w in ["saya", "boleh", "apa", "siapa", "mana", "berapa", "jenis", "sakit", "kebaikan", "terima", "layak"]) else "en"
    r = bot.answer(q, data, None, lang)
    ok = r["kind"] == "ok"
    bad += not ok
    print(("PASS " if ok else "FAIL ") + q)
print(f"\nRESULT: {len(QS) - bad} passed, {bad} failed")
