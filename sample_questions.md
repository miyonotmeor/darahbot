# Verified sample questions

Every answer below was produced by `bot_engine.py` and the numbers in rows 1-8 are re-checked directly against the CSV by `test_bot.py`.

Data up to 20 Oct 2026.

| # | Type | Visitor asks | DarahBot answers |
|---|---|---|---|
| 1 | Lookup | How many blood donations in Melaka in 2025? | **Melaka** recorded **28,845** blood donations in **2025**. That's **4.9%** of Malaysia's total. |
| 2 | Comparison | Compare Melaka and Johor Gen Z donors in 2025 | For **Gen Z new donors (age 17-24)** in **2025**: **Melaka** recorded **2,211** and **Johor** recorded **2,397**. Johor is higher by **186** people. That's **1.1×** as much. |
| 3 | Highest | Which state had the most blood donations in 2025? | In **2025**, **W.P. Kuala Lumpur** had the **highest** blood donations: **207,084** donations. Here is the full ranking. |
| 4 | Lowest | Which state has the lowest donations per 1000 adults in 2020? | In **2020**, **Selangor** had the **lowest** donations per 1,000 adults: **6.1** per 1,000 adults. Here is the full ranking. |
| 5 | Average / summary | Average new donors per state in 2024 | In **2024**, the average new donors per state was **8,747** people across 13 states. Total across all states: **113,705**. Highest: **W.P. Kuala Lumpur** (35,567), lowest: **Negeri Sembilan** (3,642). |
| 6 | Trend | How did Gen Z donors in Melaka change from 2019 to 2025? | **Melaka**: Gen Z new donors (age 17-24) fell from **4,220** in 2019 to **2,211** in 2025 (-47.6%). |
| 7 | Breakdown | What blood types were donated in Melaka 2025? | In **Melaka** in **2025**, the most common blood type donated was **type O** (42.1% of 28,845 donations with a recorded blood type). |
| 8 | Misspelling | How many donors in melak 2024? | **Melaka** recorded **29,387** blood donations in **2024**. That's **5.0%** of Malaysia's total. |
| 9 | Not in dataset | Perlis donations 2024 | I cannot answer for **Perlis**. This dataset does not report it as a separate state (the National Blood Centre groups it with a nearby state). States I can answer for: Johor, Kedah, Kelantan, Melaka, Negeri Sembilan, Pahang, Perak, Pulau Pinang, Sabah, Sarawak, Selangor, Terengganu, W.P. Kuala Lumpur. |
| 10 | Cause (honest refusal) | Why are fewer young people donating? | I cannot answer *why* from this dataset. It records **how many** people donated, but not their reasons. I can show you **how it changed** instead, for example: *How did Gen Z donors in Melaka change from 2019 to 2025?* |
| 11 | Year not covered | Melaka donations 2035 | I cannot answer for **2035**. This dataset covers 2006 to 20 Oct 2026 only. |
| 12 | Eligibility (rules, not dataset) | Can I donate blood? | Explains the 5 basic Pusat Darah Negara rules and points to the **Can I donate?** tab. Source shown: Pusat Darah Negara rules, *not* the KKM dataset. |
| 13 | Our survey (live) | How many people answered our survey? | Counts answers from dermadarah.jomana.my: donors (database) vs never donated (hypothesis), accepted vs deferred. If the survey cannot be reached, it refuses instead of guessing. |
