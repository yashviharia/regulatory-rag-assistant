"""Central config so every script agrees on paths/models/params."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Real circulars pulled by scripts/download_sources.py. The dev fixtures
# in data/sample_dev are kept only for offline smoke tests.
SOURCE_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
CHROMA_DIR = ROOT / "data" / "chroma_db"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # small, fast, good enough for this scale

# Chunking strategies compared by eval/run_eval.py. "fixed" is a word
# window; "section" splits on RBI paragraph numbers and packs whole
# paragraphs into chunks of at most chunk_size words.
CHUNK_STRATEGIES = {
    "fixed_small": {"chunker": "fixed", "chunk_size": 300, "chunk_overlap": 50},
    "fixed_large": {"chunker": "fixed", "chunk_size": 800, "chunk_overlap": 100},
    "section": {"chunker": "section", "chunk_size": 300, "chunk_overlap": 50},
}
ACTIVE_CHUNK_STRATEGY = "section"  # best chunk hit rate + MRR in eval/run_eval.py

# "dense" = embeddings only; "hybrid" = embeddings + BM25 keyword search,
# merged with reciprocal rank fusion (helps with exact terms like "DLG")
RETRIEVAL_MODES = ["dense", "hybrid"]
ACTIVE_RETRIEVAL_MODE = "hybrid"  # beat dense on chunk MRR for every strategy (eval/run_eval.py)

COLLECTION_NAME = "regulatory_circulars"

# Since the Nov 2025 consolidation the RBI issues a separate direction per type
# of regulated entity, and bank and NBFC versions often share wording (both have
# KYC, IRACP and conduct directions). Each chunk is tagged so retrieval can be
# limited to one entity type.
ENTITIES = {"bank": "Commercial banks", "nbfc": "NBFCs"}


def entity_of(source: str) -> str:
    return "nbfc" if source.lower().startswith("nbfc") else "bank"

GROQ_MODEL = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile was retired; see console.groq.com/docs/models
# eval/run_ragas.py judge: a different model from GROQ_MODEL so the model doesn't
# grade itself. qwen/qwen3.8-27b (a different family) is the better choice but
# ran out of its 200k tokens/day after 16 questions; gpt-oss-20b on low
# reasoning effort fits a full run.
RAGAS_JUDGE_MODEL = "openai/gpt-oss-20b"
RAGAS_JUDGE_KWARGS = {"extra_body": {"reasoning_effort": "low"}}
TOP_K = 4
