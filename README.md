# 📰 AP Style Editor

A simple Streamlit web app that rewrites any text in AP (Associated Press) style, with a side-by-side diff and citations to specific AP rules so edits are trustworthy and reviewable.

- **LLM**: Google Gemini (`gemini-1.5-flash`) — has a generous free tier.
- **Hosting**: Streamlit Community Cloud — free.
- **Citation trust**: Every change cites a rule ID from the bundled [`ap_rules.md`](ap_rules.md) cheat sheet. The app verifies every cited ID exists and flags any the model fabricated.

> Unofficial assistant. Not a substitute for the official AP Stylebook. Always have a human editor verify.

---

## Run locally

```bash
cd ap_style_editor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Option A: put the key in Streamlit secrets
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml and paste your Gemini API key

# Option B: skip secrets and paste the key in the sidebar at runtime

streamlit run app.py
```

Get a free Gemini API key at https://aistudio.google.com/app/apikey.

---

## Deploy free on Streamlit Community Cloud

1. Push this folder to a public GitHub repo (or to a subfolder of one).
2. Go to https://share.streamlit.io → **New app**.
3. Point it at the repo, branch, and `ap_style_editor/app.py`.
4. In **App settings → Secrets**, paste:

   ```toml
   GEMINI_API_KEY = "your-real-key-here"
   APP_PASSWORD = "pick-a-shared-password"   # optional but recommended
   ```

5. Deploy. Share the public URL.

Setting `APP_PASSWORD` gates the app behind a single shared password so randoms can't burn through your free API quota.

---

## How the trust mechanism works

The Gemini prompt embeds the entire [`ap_rules.md`](ap_rules.md) cheat sheet and instructs the model to cite a rule **ID** (e.g., `NUM-003`) for every change. After Gemini responds, the app:

1. Parses Gemini's JSON output.
2. Extracts every `ap_rule_id` from the response.
3. Checks each ID against the IDs present in `ap_rules.md`.
4. Any ID not found is flagged with a ⚠️ in the UI — those are likely hallucinations and need human review.

This means citations are grounded in a known, paraphrased rule set you control. To add or refine rules, just edit `ap_rules.md` — no code change needed.

---

## Files

- `app.py` — the Streamlit app.
- `ap_rules.md` — paraphrased AP style cheat sheet, used both as model context and as the citation source of truth.
- `requirements.txt` — `streamlit` + `google-generativeai`.
- `.streamlit/secrets.toml.example` — template for secrets.

---

## Legal note

`ap_rules.md` contains paraphrased summaries of widely known AP conventions written in our own words. It does **not** reproduce verbatim text from the AP Stylebook. The app is positioned as an unofficial assistant, not a substitute for the official Stylebook.
