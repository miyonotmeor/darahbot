# AI prompt log

Tool used: Claude (Anthropic). AI helped with planning, coding and debugging. All numbers were checked by running `test_bot.py` against the original CSV files.

> Fill in the "Our decision" column yourselves. It should reflect what your group actually accepted, changed or rejected.

| # | Date | Prompt (summary) | AI response (summary) | Our decision |
|---|---|---|---|---|
| 1 | 21 Oct 2026 | Explain the exhibition challenge guide in simple terms. | Explained datasets, pandas, Streamlit, rule-based intents, evidence and the 4 required question types. | Accepted |
| 2 | 21 Oct 2026 | Show a visual preview of what the chatbot could look like. | Interactive mock-up with example questions, evidence card, chart and honest refusal. | Accepted |
| 3 | 21 Oct 2026 | Use the blood donation data from our Data Storytelling video plus a related dataset. | Used KKM `donations_state.csv` and `newdonors_state.csv`; added KKM/DOSM 2020 population to calculate fair "per 1,000 adults" rates. | |
| 4 | 21 Oct 2026 | Build the chatbot functions (lookup, compare, highest/lowest, average) with pandas. | Wrote `bot_engine.py`: keyword intent detection, state/year/metric extraction, pandas query functions, evidence and charts. | |
| 5 | 21 Oct 2026 | Build a creative Streamlit interface. | Wrote `app.py`: chat with history and example buttons, tile map, animated time machine, Gen Z story, guess game, about-data tab. | |
| 6 | 21 Oct 2026 | Test and verify the answers. | Wrote `test_bot.py` (20 tests). One test failed: blood types A+B+O+AB did not equal total donations. | |
| 7 | 21 Oct 2026 | Debug the blood-type test failure. | Found ~0.005% of donations have no blood type recorded. Changed the test to allow this and the bot now says "donations with a recorded blood type". Documented as a limitation. | |
| 8 | 21 Oct 2026 | Improve the Gen Z chart (Melaka line was flat next to Malaysia). | Changed to an index chart (2019 = 100) so states of different size share one scale. | |
| 9 | 22 Oct 2026 | Make the chatbot more fun and "wow" for the exhibition; then make sent questions editable. | Added heartbeat header ("a donation every 53 seconds"), "Did you know?" facts computed from the data, typing effect, follow-up memory ("what about Johor?"), My blood type tab, Blood calendar heatmap, phone QR code, and edit-and-resend for questions. | |
| 10 | 22 Oct 2026 | Add all 11 extra ideas (BM mode, voice, hero card, hospitals, festive effect, exhibition mode, plus presentation materials). | Added bilingual answers, Chrome voice input, Donor Hero PNG card, hospital leaderboard (mapping verified by totals), festival and Ramadan comparison (dates verified against data), auto slideshow. Tests grew to 29. | |
| 11 | 28 Oct 2026 | Redesign DarahBot to match our survey website (dermadarah.jomana.my) and improve it; host it at dermadarahchatbox.jomana.my. | New blood-red theme (same colours/fonts as the survey), sidebar blood bag that fills as visitors ask, bilingual EN + grey BM text, one Plotly chart style, typing animation, phone layout with rising blood. New: "Can I donate?" (5 Pusat Darah Negara rules, shown as a hypothesis), live "Our survey" tab and survey questions in the chat (anonymised export only), public QR code. Hosting: kept Python/Streamlit because the guide requires Python; app runs on Streamlit Community Cloud and the subdomain points to it. Tests grew to 40. | Accepted |

## Rejected or limited AI ideas

- An LLM answering questions at runtime was **not** used, because it could invent statistics. Only pandas produces numbers.
- "Why" and "predict" questions are refused on purpose, since the data cannot support them.
- Rebuilding the chatbot as a plain HTML/JavaScript website (so it could run on Hostinger) was **rejected**: the challenge guide requires Python, so the app stays Python/Streamlit.
- The chatbot reads only the **anonymised** survey export (no names or emails), following the guide's rule about personal data.
