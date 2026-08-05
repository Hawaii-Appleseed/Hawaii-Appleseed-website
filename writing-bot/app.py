"""
Hawaiʻi Appleseed Writing Bot — Streamlit UI.

Local-only for now. Run from the repo root:
    .venv/bin/streamlit run app.py
or:
    ./run_ui.sh

The file is structured to be migration-compatible: imports are limited to
project modules (bot, retrieval) so the same file can later be dropped into
hawaii-appleseed-dashboard/pages/writing_bot.py without changes.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import streamlit as st

# Project-root import (only matters when app.py lives at repo root).
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bot  # noqa: E402

st.set_page_config(page_title="Appleseed Writing Bot", page_icon="🌺", layout="wide")


# ---------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Opening index…")
def get_collection():
    return bot.index_documents(force=False)


@st.cache_resource(show_spinner=False)
def get_anthropic_client():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=key)


@st.cache_data(show_spinner=False)
def get_positions_text():
    return bot.load_positions()


@st.cache_data(show_spinner=False)
def list_topics():
    testimony_dir = ROOT / "testimony"
    if not testimony_dir.exists():
        return []
    return sorted(p.name for p in testimony_dir.iterdir() if p.is_dir())


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.title("🌺 Hawaiʻi Appleseed Writing Bot")
st.caption("RAG-grounded drafting. Sources are retrieved from HA's testimony, blog posts, publications, and reference docs; output follows `positions.md`.")

with st.sidebar:
    st.header("Draft")
    prompt = st.text_area(
        "What do you want written?",
        value=st.session_state.get("prompt", ""),
        height=120,
        placeholder="e.g. Draft testimony in support of HB2049, the conveyance tax modernization bill.",
    )
    mode = st.selectbox("Mode", ["testimony", "blog", "op-ed"], index=st.session_state.get("mode_idx", 0))
    topics = [""] + list_topics()
    topic = st.selectbox("Topic filter (testimony folders only)", topics, index=st.session_state.get("topic_idx", 0))
    year_min = st.number_input("Year ≥", min_value=2016, max_value=2030, value=st.session_state.get("year_min", 2024), step=1)
    n_results = st.slider("Number of chunks to retrieve", 4, 16, value=st.session_state.get("n_results", bot.DEFAULT_N_RESULTS))

    st.markdown("---")
    st.caption("Retrieval engine")
    use_bm25 = st.checkbox("BM25 keyword retrieval", value=True)
    use_rerank = st.checkbox("Cross-encoder rerank", value=True)
    use_memory = st.checkbox(
        "Include coalition/relationship context (internal)",
        value=False,
        help="Folds in internal coalition, meeting, and people notes as background to "
             "inform framing and targeting. Never quoted or cited in the published draft.",
    )

    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.error(
            "`ANTHROPIC_API_KEY` not set in this shell. Add it to "
            "`~/.openclaw/secrets.env` and relaunch with `./run_ui.sh`. "
            "Retrieval-only mode is still available below."
        )

    run_clicked = st.button("Run", type="primary", use_container_width=True)
    retrieval_only = st.checkbox("Retrieval only (skip generation)", value=not bool(os.environ.get("ANTHROPIC_API_KEY")))


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------

if run_clicked and prompt.strip():
    st.session_state["prompt"] = prompt
    st.session_state["mode_idx"] = ["testimony", "blog", "op-ed"].index(mode)
    st.session_state["topic_idx"] = topics.index(topic)
    st.session_state["year_min"] = int(year_min)
    st.session_state["n_results"] = int(n_results)

    collection = get_collection()
    where = bot.build_where_filter(
        doc_type=None,
        topic=topic or None,
        year_min=int(year_min),
    )
    with st.spinner("Retrieving…"):
        hits = bot.retrieve(collection, prompt, int(n_results), where,
                            use_bm25=use_bm25, use_rerank=use_rerank)

    memory_hits = None
    if use_memory:
        with st.spinner("Retrieving relationship context…"):
            memory_hits = bot.retrieve_memory(collection, prompt, bot.DEFAULT_MEMORY_N,
                                              use_bm25=use_bm25, use_rerank=use_rerank)

    st.session_state["hits"] = hits
    st.session_state["memory_hits"] = memory_hits

    if not retrieval_only:
        client = get_anthropic_client()
        if client is None:
            st.error("ANTHROPIC_API_KEY missing — falling back to retrieval-only.")
            st.session_state["draft"] = None
            st.session_state["usage"] = None
        else:
            with st.spinner(f"Generating with {bot.GENERATION_MODEL}…"):
                draft, usage = bot.generate(prompt, hits, mode=mode, client=client,
                                            memory_hits=memory_hits)
            st.session_state["draft"] = draft
            st.session_state["usage"] = usage
    else:
        st.session_state["draft"] = None
        st.session_state["usage"] = None


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

hits = st.session_state.get("hits")
draft = st.session_state.get("draft")
usage = st.session_state.get("usage")

if hits is None:
    st.info("Fill in the sidebar and click **Run** to generate a draft.")
else:
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.subheader("Draft")
        if draft:
            # Surface [N] markers visibly so users can match them to the sources panel.
            # Anchored linking across Streamlit columns is unreliable in iframes;
            # numbering is preserved so the eye-match is one-step.
            rendered = re.sub(r"\[(\d+)\]", r"**[\1]**", draft)
            st.markdown(rendered)
        else:
            st.caption("_(retrieval-only mode — no draft generated)_")

    with right:
        st.subheader(f"Sources ({len(hits)})")
        for i, (text, meta) in enumerate(hits, start=1):
            src = meta.get("source", "?")
            badges = []
            for k in ("doc_type", "year", "topic", "bill", "position"):
                if meta.get(k):
                    badges.append(f"`{k}={meta[k]}`")
            with st.expander(f"**[{i}]** {src}", expanded=(i <= 3)):
                if badges:
                    st.markdown(" ".join(badges))
                st.markdown(text)

    if usage:
        st.markdown("---")
        st.caption(
            f"Tokens — input: {usage['input_tokens']:,} · output: {usage['output_tokens']:,} · "
            f"cache create: {usage['cache_creation_input_tokens']:,} · "
            f"cache read: {usage['cache_read_input_tokens']:,}"
        )

    with st.expander("positions.md (loaded into every prompt)", expanded=False):
        st.markdown(get_positions_text())
