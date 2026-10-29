"""
Streamlit UI for the Regulatory Circular Assistant.

Run: streamlit run frontend/app.py
"""

import html
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.query import answer, get_collection, get_embedding_model, get_groq_client

st.set_page_config(page_title="RBI Regulation Assistant", page_icon="🏦", layout="wide")

# Display names for the PDFs in data/raw/; unknown files fall back to their filename
DOC_TITLES = {
    "kyc_directions_commercial_banks_2025.pdf":
        "RBI (Commercial Banks – Know Your Customer) Directions, 2025",
    "nbfc_sbr_directions_2025.pdf":
        "RBI (NBFCs – Registration, Exemptions and Scale Based Regulation) Directions, 2025",
}

EXAMPLES = [
    "How often must a bank update KYC for a high-risk customer?",
    "What is the maximum balance allowed in a small account?",
    "Who has to approve an account for a politically exposed person?",
    "What asset size puts an NBFC in the Upper Layer?",
    "What net owned fund does an NBFC-ICC need?",
]

STRATEGY_LABELS = {
    "section": "Section-aware",
    "fixed_small": "Fixed, 300 words",
    "fixed_large": "Fixed, 800 words",
}
MODE_LABELS = {"hybrid": "Hybrid (BM25 + embeddings)", "dense": "Embeddings only"}

st.markdown("""
<style>
.block-container {max-width: 1100px; padding-top: 2rem;}
.source-card {border: 1px solid rgba(128,128,128,.25); border-radius: 10px;
              padding: .7rem .9rem; margin-bottom: .5rem;}
.source-title {font-weight: 600; font-size: .92rem;}
.source-meta {opacity: .7; font-size: .8rem;}
.source-card summary {cursor: pointer; font-size: .82rem; margin-top: .3rem;}
.excerpt {white-space: pre-wrap; font-size: .82rem; margin-top: .4rem; max-height: 320px; overflow-y: auto;}
</style>
""", unsafe_allow_html=True)


def doc_title(source: str) -> str:
    return DOC_TITLES.get(source, source)


def collection_name(strategy: str) -> str:
    return f"{config.COLLECTION_NAME}_{strategy}"


# Load the heavy pieces once per server process, not on every widget
# interaction (Streamlit reruns this whole script on each one). A fresh
# deploy has no index yet, so build the default one on first start.
@st.cache_resource(show_spinner="Loading the embedding model and index (first start takes a minute)...")
def load_pipeline():
    model = get_embedding_model()
    try:
        get_collection(collection_name(config.ACTIVE_CHUNK_STRATEGY))
    except Exception:
        from src.ingest import ingest, load_documents
        ingest(config.ACTIVE_CHUNK_STRATEGY, load_documents(config.SOURCE_DIR), model)
        get_collection.cache_clear()
    return get_groq_client()


@st.cache_data
def available_strategies() -> list[str]:
    built = []
    for name in config.CHUNK_STRATEGIES:
        try:
            get_collection(collection_name(name))
            built.append(name)
        except Exception:
            pass
    return built


@st.cache_data
def corpus(strategy: str) -> dict[str, int]:
    counts = {}
    for meta in get_collection(collection_name(strategy)).get(include=["metadatas"])["metadatas"]:
        counts[meta["source"]] = counts.get(meta["source"], 0) + 1
    return counts


def render_sources(retrieved: list):
    st.caption(f"{len(retrieved)} excerpts retrieved")
    for i, (chunk, meta, score) in enumerate(retrieved, 1):
        section = meta.get("section") or f"chunk {meta['chunk_index']}"
        # <details> rather than st.expander: Streamlit can't nest expanders
        st.markdown(
            f'<div class="source-card"><div class="source-title">[{i}] {html.escape(doc_title(meta["source"]))}</div>'
            f'<div class="source-meta">{html.escape(section)} · relevance {score:.3f}</div>'
            f'<details><summary>Show excerpt</summary><div class="excerpt">{html.escape(chunk)}</div></details></div>',
            unsafe_allow_html=True)


groq_client = load_pipeline()

with st.sidebar:
    st.header("Settings")
    strategies = available_strategies() or [config.ACTIVE_CHUNK_STRATEGY]
    strategy = st.selectbox("Chunking strategy", strategies,
                            index=strategies.index(config.ACTIVE_CHUNK_STRATEGY)
                            if config.ACTIVE_CHUNK_STRATEGY in strategies else 0,
                            format_func=lambda s: STRATEGY_LABELS.get(s, s))
    mode = st.radio("Retrieval", config.RETRIEVAL_MODES,
                    index=config.RETRIEVAL_MODES.index(config.ACTIVE_RETRIEVAL_MODE),
                    format_func=lambda m: MODE_LABELS.get(m, m))
    top_k = st.slider("Excerpts to retrieve", 2, 8, config.TOP_K)
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.history = []

    st.header("Documents")
    for source, n in sorted(corpus(strategy).items()):
        st.markdown(f"**{doc_title(source)}**  \n<span style='opacity:.7'>{n} chunks</span>",
                    unsafe_allow_html=True)
    st.caption("Current RBI Master Directions issued 28 Nov 2025 (as updated in 2026). "
               "Answers come only from these documents.")

st.title("🏦 RBI Regulation Assistant")
st.markdown("Ask about **KYC rules for commercial banks** or the **NBFC scale-based regulation "
            "framework**. Every answer is grounded in retrieved excerpts, cited by document "
            "and paragraph, and says so when the documents don't cover the question.")
st.caption("A portfolio project, not legal advice. Check the source paragraph before relying on an answer.")

if groq_client is None:
    st.warning("No GROQ_API_KEY set: showing retrieved excerpts only, no generated answer.")

if "history" not in st.session_state:
    st.session_state.history = []

question = st.chat_input("Ask a question about the directions...")
question = question or st.session_state.pop("pending", None)

if not st.session_state.history and not question:
    st.markdown("##### Try one of these")
    cols = st.columns(len(EXAMPLES))
    for col, example in zip(cols, EXAMPLES):
        if col.button(example, use_container_width=True):
            st.session_state.pending = example
            st.rerun()

for turn in st.session_state.history:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.markdown(turn["answer"])
        with st.expander("Sources"):
            render_sources(turn["retrieved"])

if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Searching the directions and drafting an answer..."):
            try:
                result = answer(question, collection_name(strategy), k=top_k, mode=mode)
            except Exception as e:
                st.error(f"Couldn't generate an answer ({type(e).__name__}). "
                         "Groq's free tier may be rate-limited; try again in a minute.")
                st.stop()
        st.markdown(result["answer"])
        with st.expander("Sources", expanded=True):
            render_sources(result["retrieved"])
    st.session_state.history.append({"question": question, "answer": result["answer"],
                                     "retrieved": result["retrieved"]})
