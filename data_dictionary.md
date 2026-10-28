# Data dictionary

## Sources

| File | Publisher | Link | Accessed |
|---|---|---|---|
| `donations_state.csv` | Ministry of Health (KKM), National Blood Centre (PDN) | https://github.com/MoH-Malaysia/data-darah-public | 21 Oct 2026 |
| `newdonors_state.csv` | Ministry of Health (KKM), National Blood Centre (PDN) | https://github.com/MoH-Malaysia/data-darah-public | 21 Oct 2026 |
| `donations_facility.csv` | Ministry of Health (KKM), National Blood Centre (PDN) | https://github.com/MoH-Malaysia/data-darah-public | 21 Oct 2026 |
| `hospital_state.csv` | Made by our group: which state each of the 22 hospitals is in | Checked: hospital totals add up exactly to each state's total in `donations_state.csv` | 22 Oct 2026 |
| `population.csv` | KKM, based on DOSM 2020 population estimates | https://github.com/MoH-Malaysia/covid19-public (static/population.csv) | 21 Oct 2026 |

Coverage: 1 Jan 2006 to 20 Oct 2026, daily. 13 states + a "Malaysia" total row. No missing values were found.
Not reported separately: Perlis, Putrajaya, Labuan.

## 1. donations_state.csv (one row = one state on one day)

| Column | Meaning | Type | Example | Unit |
|---|---|---|---|---|
| date | Day of donation | date | 2025-03-14 | YYYY-MM-DD |
| state | State of the blood bank (or "Malaysia" for the total) | text | Melaka | - |
| daily | Total donations that day | integer | 84 | donations |
| blood_a / blood_b / blood_o / blood_ab | Donations by blood group | integer | 36 | donations |
| location_centre | Donations at a blood bank/centre | integer | 40 | donations |
| location_mobile | Donations at mobile drives | integer | 44 | donations |
| type_wholeblood | Whole-blood donations | integer | 80 | donations |
| type_apheresis_platelet | Platelet donations by apheresis | integer | 3 | donations |
| type_apheresis_plasma | Plasma donations by apheresis | integer | 1 | donations |
| type_other | Other donation types | integer | 0 | donations |
| social_civilian / social_student / social_policearmy | Donations by social group | integer | 12 | donations |
| donations_new | Donations from first-time donors | integer | 10 | donations |
| donations_regular | Donations from regular donors | integer | 60 | donations |
| donations_irregular | Donations from irregular donors | integer | 14 | donations |

## 2. newdonors_state.csv (one row = one state on one day)

| Column | Meaning | Type | Example | Unit |
|---|---|---|---|---|
| date | Day | date | 2025-03-14 | YYYY-MM-DD |
| state | State (or "Malaysia") | text | Melaka | - |
| 17-24, 25-29, … 60-64 | First-time donors in that age group. **17-24 = "Gen Z" in this project** | integer | 5 | people |
| other | First-time donors outside the listed ages | integer | 0 | people |
| total | All first-time donors that day | integer | 13 | people |

## 2b. donations_facility.csv (one row = one hospital blood bank on one day)

Same columns as `donations_state.csv`, but `hospital` instead of `state`. 22 hospitals.

## 2c. hospital_state.csv

| Column | Meaning | Type | Example |
|---|---|---|---|
| hospital | Hospital name exactly as in donations_facility.csv | text | Hospital Melaka |
| state | State the hospital is in | text | Melaka |

## 3. population.csv (one row = one state)

| Column | Meaning | Type | Example | Unit |
|---|---|---|---|---|
| state | State name | text | Melaka | - |
| idxs | Sort order | integer | 4 | - |
| pop | Total population (2020) | integer | 937800 | people |
| pop_18 | Population aged 18+ | integer | 683700 | people |
| pop_60 | Population aged 60+ | integer | 123200 | people |
| pop_12 / pop_5 | Population in younger groups (as published) | integer | 85600 | people |

## Calculated measures (made by the bot)

| Measure | Formula |
|---|---|
| Donations per 1,000 adults | yearly `daily` ÷ `pop_18` × 1000 |
| Gen Z share of new donors | yearly `17-24` ÷ yearly `total` × 100 |

## Festival dates

Hari Raya Aidilfitri, Chinese New Year and Deepavali dates (2015–2025) come from the Malaysian public holiday calendar and are written in `bot_engine.py` (`FESTIVALS`). Each Aidilfitri date is the lowest-donation day in the 4 weeks around it, which confirms the dates.

## Known limitations

- Donations are counted at the **blood bank's** state, not where the donor lives, so W.P. Kuala Lumpur looks very high and Selangor low.
- 2026 is a **partial year** (to 20 Oct 2026).
- About 0.005% of donations have no blood type recorded, so A + B + O + AB is slightly below `daily`.
- Population is a 2020 snapshot, so per-1,000 rates for other years are approximate.
- The data records **how many**, never **why**.

## Eight questions this dataset can genuinely answer

1. How many blood donations were there in Melaka in 2025?
2. Compare Gen Z (17-24) new donors in Melaka and Johor in 2025.
3. Which state had the most donations in 2025?
4. Which state had the lowest donations per 1,000 adults in 2020?
5. What was the average number of new donors per state in 2024?
6. How did Gen Z new donors in Melaka change from 2019 to 2025?
7. Which blood type was donated most in Melaka in 2025?
8. How many donations came from students in Sabah in 2025?
