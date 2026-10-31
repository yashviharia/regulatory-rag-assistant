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
from frontend.theme import ICONS, apply_theme, label

st.set_page_config(page_title="RBI Regulation Assistant", page_icon="🏦", layout="wide")

# Display names for the PDFs in data/raw/; unknown files fall back to their filename
DOC_TITLES = {
    "kyc_directions_commercial_banks_2025.pdf":
        "RBI (Commercial Banks – Know Your Customer) Directions, 2025",
    "cb_responsible_business_conduct_2025.pdf":
        "RBI (Commercial Banks – Responsible Business Conduct) Directions, 2025",
    "cb_interest_rates_on_advances_2025.pdf":
        "RBI (Commercial Banks – Interest Rates on Advances) Directions, 2025",
    "cb_credit_debit_cards_2025.pdf":
        "RBI (Commercial Banks – Credit Cards and Debit Cards: Issuance and Conduct) Directions, 2025",
    "cb_credit_facilities_2025.pdf":
        "RBI (Commercial Banks – Credit Facilities) Directions, 2025",
    "cb_interest_rate_on_deposits_2025.pdf":
        "RBI (Commercial Banks – Interest Rate on Deposits) Directions, 2025",
    "cb_wilful_defaulters_2025.pdf":
        "RBI (Commercial Banks – Treatment of Wilful Defaulters and Large Defaulters) Directions, 2025",
    "cb_iracp_2025.pdf":
        "RBI (Commercial Banks – Income Recognition, Asset Classification and Provisioning) Directions, 2025",
    "cb_outsourcing_2025.pdf":
        "RBI (Commercial Banks – Managing Risks in Outsourcing) Directions, 2025",
    "nbfc_sbr_directions_2025.pdf":
        "RBI (NBFCs – Registration, Exemptions and Scale Based Regulation) Directions, 2025",
    "nbfc_responsible_business_conduct_2025.pdf":
        "RBI (NBFCs – Responsible Business Conduct) Directions, 2025",
    "nbfc_kyc_2025.pdf":
        "RBI (NBFCs – Know Your Customer) Directions, 2025",
    "nbfc_iracp_2025.pdf":
        "RBI (NBFCs – Income Recognition, Asset Classification and Provisioning) Directions, 2025",
    "nbfc_microfinance_2025.pdf":
        "RBI (NBFCs – Microfinance Institution) Directions, 2025",
}

EXAMPLES = [
    "What is the minimum cooling-off period on a digital loan?",
    "What does a bank owe for delay in returning property documents?",
    "What penalty does a bank pay for delaying a credit card closure?",
    "How often must a bank update KYC for a high-risk customer?",
    "What asset size puts an NBFC in the Upper Layer?",
]

STRATEGY_LABELS = {
    "section": "Section-aware",
    "fixed_small": "Fixed, 300 words",
    "fixed_large": "Fixed, 800 words",
}
MODE_LABELS = {"hybrid": "Hybrid (BM25 + embeddings)", "dense": "Embeddings only"}
ENTITY_OPTIONS = [None, *config.ENTITIES]  # None = search every direction



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


USER_AVATAR, ASSISTANT_AVATAR = ":material/person:", ":material/account_balance:"


def render_sources(retrieved: list):
    st.markdown(f'<div class="drawer-head">{ICONS["seal"]}{len(retrieved)} excerpts cited from the directions</div>',
                unsafe_allow_html=True)
    for i, (chunk, meta, score) in enumerate(retrieved, 1):
        section = meta.get("section") or f"chunk {meta['chunk_index']}"
        # <details> rather than st.expander: Streamlit can't nest expanders
        st.markdown(
            f'<div class="cite"><div class="seal">{i}</div><div class="cite-body">'
            f'<div class="cite-title">{html.escape(doc_title(meta["source"]))}</div>'
            f'<div class="cite-meta"><span>{html.escape(section)}</span><span class="rel">relevance {score:.3f}</span></div>'
            f'<details><summary>Read excerpt</summary><div class="excerpt">{html.escape(chunk)}</div></details>'
            f'</div></div>',
            unsafe_allow_html=True)


def card():
    """A bordered sidebar section; the anchor lets theme.py style it as a ledger card."""
    box = st.container(border=True)
    box.markdown('<span class="card-anchor"></span>', unsafe_allow_html=True)
    return box


groq_client = load_pipeline()

with st.sidebar:
    st.markdown(f'<div class="side-brand">{ICONS["bank"]}<span>₹</span>Ledger</div>'
                '<div class="side-sub">Retrieval settings and sources</div>', unsafe_allow_html=True)
    dark = st.toggle("Dark mode", key="dark")

    with card():
        st.markdown(label("layers", "Chunking strategy"), unsafe_allow_html=True)
        strategies = available_strategies() or [config.ACTIVE_CHUNK_STRATEGY]
        strategy = st.selectbox("Chunking strategy", strategies,
                                index=strategies.index(config.ACTIVE_CHUNK_STRATEGY)
                                if config.ACTIVE_CHUNK_STRATEGY in strategies else 0,
                                format_func=lambda s: STRATEGY_LABELS.get(s, s),
                                label_visibility="collapsed")

    with card():
        st.markdown(label("search", "Retrieval"), unsafe_allow_html=True)
        mode = st.radio("Retrieval", config.RETRIEVAL_MODES,
                        index=config.RETRIEVAL_MODES.index(config.ACTIVE_RETRIEVAL_MODE),
                        format_func=lambda m: MODE_LABELS.get(m, m), label_visibility="collapsed")
        top_k = st.slider("Excerpts to retrieve", 2, 8, config.TOP_K)
        entity = st.selectbox("Regulated entity", ENTITY_OPTIONS,
                              format_func=lambda e: config.ENTITIES.get(e, "All entities"),
                              help="Bank and NBFC directions often share wording; "
                                   "pick one to search only its rules.")

    with card():
        st.markdown(label("doc", "Documents"), unsafe_allow_html=True)
        docs = corpus(strategy)
        for key, name in config.ENTITIES.items():
            group = sorted((s, n) for s, n in docs.items() if config.entity_of(s) == key)
            if not group:
                continue
            with st.expander(f"{name} ({len(group)})"):
                st.markdown("".join(
                    f'<div class="doc-item">{ICONS["doc"]}<div><div class="doc-title">'
                    f'{html.escape(doc_title(source))}</div>'
                    f'<div class="doc-meta">{n} chunks indexed</div></div></div>'
                    for source, n in group), unsafe_allow_html=True)
        st.caption("Current RBI Master Directions issued 28 Nov 2025 (as updated in 2026). "
                   "Answers come only from these documents.")

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.history = []

apply_theme(dark)

st.markdown(f"""
<div class="hero">
  <div class="hero-kicker">{ICONS["bank"]}Reserve Bank of India · Master Directions</div>
  <h1><span class="rupee">₹</span>RBI Regulation Assistant</h1>
  <p>Ask about <b>KYC, lending conduct, digital lending, loan pricing, cards, deposits,
  defaulters and provisioning</b> for commercial banks and NBFCs. Every answer is grounded in retrieved excerpts, cited by document and
  paragraph, and says so when the directions don't cover the question.</p>
  <div class="thread"></div>
  <div class="disclaimer">A portfolio project, not legal advice. Check the cited paragraph before relying on an answer.</div>
</div>""", unsafe_allow_html=True)

if groq_client is None:
    st.warning("No GROQ_API_KEY set: showing retrieved excerpts only, no generated answer.")

if "history" not in st.session_state:
    st.session_state.history = []

question = st.chat_input("Ask a question about the directions...")
question = question or st.session_state.pop("pending", None)

if not st.session_state.history and not question:
    st.markdown(label("seal", "Try one of these"), unsafe_allow_html=True)
    cols = st.columns(len(EXAMPLES))
    for col, example in zip(cols, EXAMPLES):
        if col.button(example, use_container_width=True):
            st.session_state.pending = example
            st.rerun()

for turn in st.session_state.history:
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown('<span class="user-marker"></span>', unsafe_allow_html=True)
        st.write(turn["question"])
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        st.markdown(turn["answer"])
        with st.expander("Sources", icon=":material/menu_book:"):
            render_sources(turn["retrieved"])

if question:
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown('<span class="user-marker"></span>', unsafe_allow_html=True)
        st.write(question)
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.spinner("Searching the directions and drafting an answer..."):
            try:
                result = answer(question, collection_name(strategy), k=top_k, mode=mode,
                                entity=entity)
            except Exception as e:
                st.error(f"Couldn't generate an answer ({type(e).__name__}). "
                         "Groq's free tier may be rate-limited; try again in a minute.")
                st.stop()
        st.markdown(result["answer"])
        with st.expander("Sources", expanded=True, icon=":material/menu_book:"):
            render_sources(result["retrieved"])
    st.session_state.history.append({"question": question, "answer": result["answer"],
                                     "retrieved": result["retrieved"]})
