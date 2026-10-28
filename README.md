# 🩸 DarahBot: Malaysia Blood Donation Chatbot

Python Data Science Exhibition Challenge (CSC649). A Streamlit chatbot that answers visitor questions about blood donations in Malaysia **only from official KKM data**, shows its evidence, and says *"I cannot answer from this dataset"* instead of guessing.

## How to run on your Mac (Anaconda)

1. Open **Terminal** and go to this folder:
   ```
   cd ~/CSC\ Lab/DarahBot
   ```
2. Activate your environment and install the libraries (first time only):
   ```
   conda activate lab1
   pip install -r requirements.txt
   ```
3. (Optional) connect the live survey: copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
   and put your survey's **anonymised** export link in it (the one ending with `&anon=1`).
4. Start the app:
   ```
   streamlit run app.py
   ```
   It opens at http://localhost:8501. Stop it with **Ctrl + C**.
5. Check the answers are correct:
   ```
   python test_bot.py
   ```

## Put it online: dermadarahchatbox.jomana.my

Hostinger can't run Python apps, so the app runs free on **Streamlit Community Cloud** and the subdomain opens it.

1. **GitHub:** make a free account, create a new repository called `darahbot`, and upload everything in this folder
   **except** `.streamlit/secrets.toml` (never upload that). Create `.streamlit/config.toml` with *Add file → Create new file* if the
   hidden folder didn't upload.
2. **Streamlit Cloud:** go to share.streamlit.io, sign in with GitHub, *Create app* → repository `darahbot`, branch `main`,
   main file `app.py`, app URL e.g. `darahbot`. Under *Advanced settings* pick Python 3.12 and paste the lines from
   `secrets.toml.example` (with your real key) into *Secrets*. Press *Deploy*.
3. **Hostinger:** create the subdomain `dermadarahchatbox`, then upload `hostinger/index.html` into its folder
   (edit the one link inside it if your Streamlit app URL is different). The subdomain now shows DarahBot.

## Files

| File | What it is |
|---|---|
| `app.py` | The chat screen and exhibition tabs (Streamlit), in the same blood-red design as our survey |
| `bot_engine.py` | The "brain": reads the question, runs pandas, builds answer + evidence + chart |
| `test_bot.py` | 40 tests: re-calculates answers straight from the CSV, tests tricky questions, the survey and "Can I donate?" |
| `data/` | The 4 original KKM CSV files + `hospital_state.csv` (hospital → state, verified) |
| `data_dictionary.md` | Every column explained (meaning, type, example, unit) |
| `sample_questions.md` | 11 verified questions with the bot's answers |
| `prompt_log.md` | AI prompt log (required for submission) |
| `requirements.txt` | Libraries needed |
| `assets/` | Chat avatars and the Inter font for the Donor Hero card |
| `.streamlit/` | `config.toml` (colours) and `secrets.toml.example` (survey link template) |
| `hostinger/index.html` | The page for dermadarahchatbox.jomana.my that opens the online app |

## How it works

```
visitor message → detect_intent() → find_states() / find_years() / find_metric()
               → pandas query (lookup / compare / rank / summary / trend)
               → answer text + evidence card + Plotly chart + exact rows used
```

No AI model runs inside the app. Every number comes from a pandas calculation.

## New in the October 2026 update

- 🎨 **Same design as our survey** (dermadarah.jomana.my): blood-red panel, English with smaller grey Malay underneath, one chart style
- 🩸 **The blood bag fills up** as a visitor asks questions (6 questions = 450 ml); on phones, blood rises behind the page
- ✅ **Can I donate?** tab: 5 quick questions, LAYAK / BELUM LAYAK early hypothesis (Pusat Darah Negara rules)
- 📋 **Our survey (live)** tab and chat answers about our own survey (anonymised, refreshes every minute)
- 📱 **QR code** points to the public link when online, or to the Mac's Wi-Fi address at the exhibition
- Made by **@amirrulmukminin**

## Main features

- 🇬🇧/🇲🇾 **English or Bahasa Melayu** answers (switch in the sidebar). The numbers are identical in both
- 🎤 **Voice questions** (Google Chrome; speech is turned into text by Chrome)
- ✏️ **Edit and resend** any question
- 🧠 **Follow-up memory**: "Compare Melaka and Kedah" → "what about Johor?"
- 💡 **"Did you know?" facts**, all calculated from the data

## App tabs (for the exhibition)

- **💬 Ask DarahBot:** the chatbot, with example question buttons, evidence cards, charts and a "How I got this" panel
- **✅ Can I donate?:** the 5-rule early hypothesis, same as the survey
- **📋 Our survey:** live numbers and charts from dermadarah.jomana.my
- **🩸 My blood type:** 100-drop picture of how common your type is, plus a downloadable **Donor Hero card**
- **🗺️ State map:** Malaysia tile map, coloured by any measure and year
- **🏥 Hospitals:** leaderboard of the 22 government blood banks
- **📅 Calendar & festivals:** every day of the year as a square, plus the Hari Raya / CNY / Deepavali / Ramadan effect
- **⏳ Time machine:** animated bar race of 20 years of donations
- **📉 Gen Z story:** "Darah Muda, Semakin Kurang?", the Gen Z trend from our storytelling video
- **🎯 Guess the number:** visitors guess a number, then the data reveals the truth
- **📺 Exhibition mode:** auto slideshow of facts and charts every 8 seconds, for when nobody is typing
- **📄 About the data:** sources and limitations

## Suggested 3-5 minute demo (Activity 8)

1. **Introduce the data (30s):** KKM blood donation records, daily, by state, 2006 to today.
2. **Easy question (30s):** click *"Which state had the most blood donations in 2025?"* and point at the evidence card.
3. **Comparison (45s):** *"Compare Melaka and Johor Gen Z donors in 2025"*.
4. **Chart and story (60s):** open **Gen Z story**: Gen Z new donors in Melaka fell about 48% from 2019 to 2025.
5. **Show a limitation (30s):** ask *"Why are fewer young people donating?"*. The bot refuses honestly.
6. **Explain two functions (60s):** `detect_intent()` (keywords → question type) and `rank()` (pandas groupby + sort).
7. **Invite the visitor** to play **Guess the number**.
