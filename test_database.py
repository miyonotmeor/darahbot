"""Questions about any part of the KKM database must get a real answer."""
import bot_engine as bot
data=bot.load_data()
QS=[("How many student donations in Selangor in 2024?","en"),("How many donations at mobile drives in Johor 2025?","en"),("regular donors in Penang 2023","en"),
("donations per 1000 adults in Melaka","en"),("new donors in Sabah 2022","en"),("Which state had the most new donors in 2024?","en"),
("Which hospital in Sarawak collects the most blood?","en"),("blood types in Kelantan 2025","en"),("what percentage of donations in Johor were type B","en"),
("which month had the most donations in Melaka in 2024","en"),("average donations per day in Kedah 2025","en"),("Compare Melaka, Johor and Selangor in 2025","en"),
("Gen Z share of new donors in Terengganu 2025","en"),("trend of student donations in Malaysia","en"),("how many donations in 2010","en"),
("Which year had the most blood donations?","en"),("busiest day ever","en"),("total donations 2015 to 2025","en"),("How did Perak donations change from 2020 to 2025","en"),
("Berapa derma pelajar di Selangor 2024?","bm"),("Negeri mana paling ramai penderma baru 2024?","bm"),("Purata derma sehari di Johor 2025","bm"),
("Jenis darah di Kelantan 2025","bm"),("Bandingkan Kedah dan Perlis 2025","bm"),("How many donations during COVID in 2020?","en"),("Did donations drop in 2020?","en"),
("Which state improved the most from 2019 to 2025?","en"),("lowest month in 2023","en"),("donations in KL in March 2025","en"),("How many blood banks in Johor?","en"),
("What % of donations were at mobile drives in 2025?","en"),("how many first time donors in 2025","en"),("percentage of Gen Z donors in Malaysia 2019","en")]
bad=0
for q,l in QS:
    r=bot.answer(q,data,None,l); bad+= r['kind']!='ok'
    print(f"{r['kind']:7} {q[:50]:50} -> {r['text'][:85]!r}")
print(f"\nRESULT: {len(QS)-bad} passed, {bad} not answered (Perlis is expected: not reported separately)")
