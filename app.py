"""
AP Style Editor — paste text, get an AP-style rewrite with rule citations.

Single-file Streamlit app. Uses Google Gemini (free tier) for the rewrite,
and a bundled `ap_rules.md` cheat sheet as the citation source-of-truth.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Optional

import google.generativeai as genai
import streamlit as st

# ---------- Config ----------

APP_DIR = Path(__file__).parent
RULES_PATH = APP_DIR / "ap_rules.md"
MODEL_NAME = "gemini-2.5-flash"  # free-tier friendly

st.set_page_config(page_title="AP Style Editor", page_icon="📰", layout="wide")


# ---------- Rule loading ----------

@st.cache_data
def load_rules_text() -> str:
    return RULES_PATH.read_text(encoding="utf-8")


@st.cache_data
def extract_rule_ids(rules_text: str) -> set[str]:
    """Pull every `id: XXX-###` token out of the cheat sheet."""
    return set(re.findall(r"id:\s*([A-Z]+-\d+)", rules_text))


# ---------- Prompt ----------

SYSTEM_PROMPT_TEMPLATE = """You are an expert copy editor specializing in The Associated Press (AP) Stylebook.

Your job: take the user's text and rewrite it to conform to AP style, then explain every change.

CITATION RULES (CRITICAL):
- For each change you make, cite an `ap_rule_id` that matches EXACTLY one of the IDs in the cheat sheet below.
- If a change does not map to any rule in the cheat sheet, set `ap_rule_id` to "NONE" and explain why in `rationale`.
- Do NOT invent rule IDs. Do NOT cite the AP Stylebook by page number or section number.

REWRITE RULES:
- Preserve the author's meaning, voice, and factual content. Only fix style.
- Do not add new facts, opinions, or content the author did not include.
- Keep paragraph breaks.
- If the input is already AP-compliant, return it unchanged with an empty `changes` array.

AP STYLE CHEAT SHEET:
---
{rules}
---

OUTPUT FORMAT (strict JSON, no markdown, no commentary):
{{
  "rewritten_text": "<the full rewritten text>",
  "changes": [
    {{
      "original": "<exact original phrase>",
      "replacement": "<replacement phrase>",
      "ap_rule_id": "<rule ID from cheat sheet or 'NONE'>",
      "rationale": "<one-sentence explanation>"
    }}
  ]
}}
"""


def build_prompt(user_text: str) -> tuple[str, str]:
    system = SYSTEM_PROMPT_TEMPLATE.format(rules=load_rules_text())
    user = f"Rewrite the following text in AP style:\n\n---\n{user_text}\n---"
    return system, user


# ---------- Gemini call ----------

def rewrite_with_gemini(text: str, api_key: str) -> dict:
    genai.configure(api_key=api_key)
    system, user = build_prompt(text)
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    )
    response = model.generate_content(user)
    raw = response.text or ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # try to salvage by extracting the largest {...} block
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise RuntimeError(f"Model did not return valid JSON: {e}\n\nRaw output:\n{raw}")


# ---------- Diff rendering ----------

def render_word_diff(original: str, rewritten: str) -> str:
    """Produce HTML with word-level additions (green) and deletions (red strikethrough)."""
    orig_tokens = re.findall(r"\S+|\s+", original)
    new_tokens = re.findall(r"\S+|\s+", rewritten)
    sm = difflib.SequenceMatcher(a=orig_tokens, b=new_tokens, autojunk=False)
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            parts.append(_esc("".join(orig_tokens[i1:i2])))
        elif tag == "delete":
            parts.append(_del("".join(orig_tokens[i1:i2])))
        elif tag == "insert":
            parts.append(_ins("".join(new_tokens[j1:j2])))
        elif tag == "replace":
            parts.append(_del("".join(orig_tokens[i1:i2])))
            parts.append(_ins("".join(new_tokens[j1:j2])))
    body = "".join(parts).replace("\n", "<br>")
    return (
        '<div style="font-family: Georgia, serif; line-height: 1.7; '
        'padding: 1rem; border: 1px solid #ddd; border-radius: 6px; '
        'background: #fafafa; white-space: pre-wrap;">'
        f"{body}</div>"
    )


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _ins(s: str) -> str:
    if not s.strip():
        return _esc(s)
    return f'<span style="background:#d4f4dd;color:#1a6e2e;border-radius:2px;padding:0 2px;">{_esc(s)}</span>'


def _del(s: str) -> str:
    if not s.strip():
        return _esc(s)
    return f'<span style="background:#fadbd8;color:#a83232;text-decoration:line-through;border-radius:2px;padding:0 2px;">{_esc(s)}</span>'


# ---------- Auth helpers ----------

def get_secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)  # type: ignore[attr-defined]
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):  # type: ignore[attr-defined]
        return default
    except Exception:
        return default


def password_gate() -> bool:
    expected = get_secret("APP_PASSWORD", "")
    if not expected:
        return True  # no gate configured
    if st.session_state.get("authed"):
        return True
    st.title("📰 AP Style Editor")
    pw = st.text_input("Enter access password", type="password")
    if st.button("Unlock"):
        if pw == expected:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


def resolve_api_key() -> Optional[str]:
    """Prefer secret; otherwise let user paste a key in the sidebar."""
    secret_key = get_secret("GEMINI_API_KEY", "")
    if secret_key:
        return secret_key
    return st.session_state.get("user_api_key") or None


# ---------- UI ----------

def sidebar() -> None:
    with st.sidebar:
        st.header("Settings")
        if not get_secret("GEMINI_API_KEY", ""):
            st.markdown(
                "Get a free Gemini API key at "
                "[Google AI Studio](https://aistudio.google.com/app/apikey)."
            )
            st.text_input(
                "Gemini API key",
                type="password",
                key="user_api_key",
                help="Stored only in this browser session.",
            )
        else:
            st.success("Gemini API key loaded from secrets.")

        st.divider()
        st.caption(f"Model: `{MODEL_NAME}`")
        with st.expander("📖 Bundled AP rule cheat sheet"):
            st.markdown(load_rules_text())

        st.divider()
        st.caption(
            "Unofficial assistant. Not a substitute for the AP Stylebook. "
            "Always have a human editor verify."
        )


def render_results(result: dict, original: str) -> None:
    rewritten = result.get("rewritten_text", "")
    changes = result.get("changes", []) or []
    known_ids = extract_rule_ids(load_rules_text())

    # Citation-grounding guard: flag fabricated rule IDs
    flagged: list[int] = []
    for i, ch in enumerate(changes):
        rid = (ch.get("ap_rule_id") or "").strip()
        if rid and rid != "NONE" and rid not in known_ids:
            flagged.append(i)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Changes proposed", len(changes))
    col_b.metric(
        "Cited rules",
        sum(1 for c in changes if c.get("ap_rule_id") not in (None, "", "NONE")),
    )
    col_c.metric("⚠️ Unverified citations", len(flagged))

    if flagged:
        st.warning(
            f"{len(flagged)} change(s) cite a rule ID that is NOT in the bundled cheat sheet. "
            "Review these carefully — the model may have fabricated them."
        )

    tab_diff, tab_changes, tab_clean = st.tabs(
        ["🔀 Side-by-side diff", "📋 Changes table", "✨ Clean rewrite"]
    )

    with tab_diff:
        left, right = st.columns(2)
        with left:
            st.subheader("Original")
            st.markdown(
                f'<div style="font-family: Georgia, serif; line-height: 1.7; '
                f'padding: 1rem; border: 1px solid #ddd; border-radius: 6px; '
                f'background: #fff; white-space: pre-wrap;">{_esc(original)}</div>',
                unsafe_allow_html=True,
            )
        with right:
            st.subheader("AP-style rewrite (diff)")
            st.markdown(render_word_diff(original, rewritten), unsafe_allow_html=True)

    with tab_changes:
        if not changes:
            st.info("No changes proposed — your text is already AP-compliant. 🎉")
        else:
            rows = []
            for i, ch in enumerate(changes):
                rid = ch.get("ap_rule_id", "")
                is_flagged = i in flagged
                rows.append(
                    {
                        "Original": ch.get("original", ""),
                        "Replacement": ch.get("replacement", ""),
                        "AP Rule": ("⚠️ " + rid) if is_flagged else rid,
                        "Why": ch.get("rationale", ""),
                    }
                )
            st.dataframe(rows, use_container_width=True, hide_index=True)

    with tab_clean:
        st.subheader("Rewritten text")
        st.text_area(
            "Copy from here:",
            value=rewritten,
            height=400,
            label_visibility="collapsed",
        )
        st.download_button(
            "Download as .txt",
            data=rewritten,
            file_name="ap_style_rewrite.txt",
            mime="text/plain",
        )


def _start_over() -> None:
    """Clear the input and any prior result so the user can edit new text."""
    st.session_state["input_text"] = ""
    st.session_state.pop("last_result", None)
    st.session_state.pop("last_input", None)


def main() -> None:
    if not password_gate():
        return

    st.title("📰 AP Style Editor")
    st.caption(
        "Paste any text. Get an AP-style rewrite with a side-by-side diff and "
        "citations to specific rules from the bundled AP cheat sheet."
    )

    sidebar()

    user_text = st.text_area(
        "Your text",
        height=260,
        placeholder=(
            "Paste your article, paragraph, or headline here…\n\n"
            "Example: The U.S. president said 5 percent of the 25 states "
            "will use the Oxford comma, on January 5th, 2026."
        ),
        key="input_text",
    )

    col1, col2, col3 = st.columns([2, 2, 4])
    go = col1.button("Rewrite in AP style", type="primary", use_container_width=True)
    col2.button(
        "Start over",
        on_click=_start_over,
        use_container_width=True,
        help="Clear the input and previous result.",
    )
    word_count = len(user_text.split()) if user_text else 0
    col3.caption(f"{word_count} words")

    if go:
        if not user_text.strip():
            st.warning("Please paste some text first.")
            return

        api_key = resolve_api_key()
        if not api_key:
            st.error("No Gemini API key configured. Add one in the sidebar.")
            return

        with st.spinner("Editing…"):
            try:
                result = rewrite_with_gemini(user_text, api_key)
            except Exception as e:
                st.error(f"Something went wrong: {e}")
                return

        st.session_state["last_result"] = result
        st.session_state["last_input"] = user_text

    # Render the most recent result (if any) so it survives reruns
    # caused by widget interactions inside the result tabs.
    if "last_result" in st.session_state and "last_input" in st.session_state:
        render_results(st.session_state["last_result"], st.session_state["last_input"])


if __name__ == "__main__":
    main()
