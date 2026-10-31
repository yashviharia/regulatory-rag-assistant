"""
Retrieve relevant chunks for a question and get an answer from Groq.

Usage:
    python src/query.py "What is the cooling-off period for digital loans?"
"""

import os
import re
import sys
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config

# silence the HF tokenizers fork warning (Groq's HTTP client forks after the model loads)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


SYSTEM_PROMPT = """You are a compliance assistant that answers questions \
about regulatory circulars using ONLY the provided context excerpts. \
If the answer isn't in the context, say plainly that the RBI directions \
indexed here don't cover it, instead of guessing. \
Cite which source document (and paragraph number, when the excerpt shows \
one) each part of your answer comes from. Each excerpt says which type of \
entity it applies to (commercial banks or NBFCs); rules for one don't \
automatically apply to the other, so say which one your answer covers."""

# Reciprocal rank fusion constant; 60 is the value from the original RRF paper
RRF_K = 60


# Loading the embedding model takes seconds, so each process loads it once
# and reuses it across questions (API requests, eval loops, UI reruns).
@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(config.EMBEDDING_MODEL)


@lru_cache(maxsize=None)
def get_collection(collection_name: str):
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR),
                                       settings=Settings(anonymized_telemetry=False))
    return client.get_collection(collection_name)


@lru_cache(maxsize=1)
def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    from groq import Groq
    # free tier allows 8k tokens/min; a fixed_large prompt alone is ~6k, so
    # back off and retry on 429s (the SDK honours Groq's retry-after) instead
    # of failing after the default 2 attempts
    return Groq(api_key=api_key, max_retries=8)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


@lru_cache(maxsize=None)
def get_bm25_index(collection_name: str):
    """BM25 over every chunk in the collection, built once per process."""
    from rank_bm25 import BM25Okapi
    data = get_collection(collection_name).get(include=["documents", "metadatas"])
    return BM25Okapi([tokenize(d) for d in data["documents"]]), data


def dense_search(question: str, collection_name: str, n: int, entity: str = None) -> list:
    query_embedding = get_embedding_model().encode([question]).tolist()
    results = get_collection(collection_name).query(
        query_embeddings=query_embedding, n_results=n,
        where={"entity": entity} if entity else None)
    # MiniLM embeddings are unit length, so Chroma's squared L2 distance
    # d = 2 - 2*cos; report cosine similarity so higher always means better
    return [(chunk, meta, 1 - dist / 2) for chunk, meta, dist in
            zip(results["documents"][0], results["metadatas"][0], results["distances"][0])]


def retrieve(question: str, collection_name: str, k: int = config.TOP_K,
             mode: str = config.ACTIVE_RETRIEVAL_MODE, entity: str = None) -> list:
    """Returns the top-k (chunk, metadata, score) tuples, best first.
    score is cosine similarity in dense mode and the RRF score in hybrid mode.
    entity ("bank" / "nbfc") limits the search to that entity's directions."""
    if entity is not None and entity not in config.ENTITIES:
        raise ValueError(f"unknown entity {entity!r}; expected one of {list(config.ENTITIES)}")
    if mode == "dense":
        return dense_search(question, collection_name, k, entity)
    if mode != "hybrid":
        raise ValueError(f"unknown retrieval mode {mode!r}; expected one of {config.RETRIEVAL_MODES}")

    # fuse the two rankings over a wider candidate pool, then cut to k
    pool = max(k * 5, 20)
    dense = dense_search(question, collection_name, pool, entity)
    bm25, data = get_bm25_index(collection_name)
    bm25_scores = bm25.get_scores(tokenize(question))
    candidates = [i for i in range(len(bm25_scores))
                  if entity is None or data["metadatas"][i].get("entity") == entity]
    bm25_top = sorted(candidates, key=lambda i: -bm25_scores[i])[:pool]

    fused, items = {}, {}
    for rank, (chunk, meta, _score) in enumerate(dense):
        key = (meta["source"], meta["chunk_index"])
        fused[key] = fused.get(key, 0) + 1 / (RRF_K + rank + 1)
        items[key] = (chunk, meta)
    for rank, i in enumerate(bm25_top):
        if bm25_scores[i] <= 0:
            break  # no query term in this chunk or any after it
        meta = data["metadatas"][i]
        key = (meta["source"], meta["chunk_index"])
        fused[key] = fused.get(key, 0) + 1 / (RRF_K + rank + 1)
        items[key] = (data["documents"][i], meta)

    best = sorted(fused, key=lambda key: -fused[key])[:k]
    return [(*items[key], fused[key]) for key in best]


def build_context(retrieved: list) -> str:
    parts = []
    for i, (chunk, meta, _score) in enumerate(retrieved):
        applies_to = config.ENTITIES[meta.get("entity") or config.entity_of(meta["source"])]
        parts.append(f"[Excerpt {i+1} — source: {meta['source']} — applies to: {applies_to}]\n{chunk}")
    return "\n\n".join(parts)


def answer(question: str, collection_name: str = None, k: int = config.TOP_K,
           mode: str = config.ACTIVE_RETRIEVAL_MODE, entity: str = None) -> dict:
    collection_name = collection_name or f"{config.COLLECTION_NAME}_{config.ACTIVE_CHUNK_STRATEGY}"
    retrieved = retrieve(question, collection_name, k=k, mode=mode, entity=entity)
    context = build_context(retrieved)

    client = get_groq_client()
    if client is None:
        return {
            "question": question,
            "context": context,
            "retrieved": retrieved,
            "answer": "[No GROQ_API_KEY set — showing retrieved context only. "
                      "Get a free key at https://console.groq.com/keys and add it to .env]",
        }

    completion = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
        temperature=0.1,
    )
    return {
        "question": question,
        "context": context,
        "retrieved": retrieved,
        "answer": completion.choices[0].message.content,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python src/query.py "your question here"')
        sys.exit(1)
    q = " ".join(sys.argv[1:])
    result = answer(q)
    print("\n--- RETRIEVED CHUNKS ---")
    for chunk, meta, score in result["retrieved"]:
        print(f"[{meta['source']} chunk {meta['chunk_index']}] (score={score:.3f})")
        print(chunk[:200].replace("\n", " ") + "...\n")
    print("--- ANSWER ---")
    print(result["answer"])
