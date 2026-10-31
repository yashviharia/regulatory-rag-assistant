"""
Runs the hand-written Q&A set against every chunking strategy in
config.CHUNK_STRATEGIES and every retrieval mode in config.RETRIEVAL_MODES,
and reports, over the top-k retrieved chunks:
  - doc hit rate:   did the expected source document appear at all?
  - chunk hit rate: did a chunk containing the answer appear? A chunk
                    counts if it contains one of the question's "evidence"
                    phrases (short verbatim quotes from the answering
                    passage). This is the stricter, more honest number:
                    the right document can still be the wrong passage.
  - chunk MRR:      mean of 1/rank of the first answering chunk (0 if none).
  - wrong entity:   share of retrieved chunks from the other entity type's
                    directions (bank vs NBFC), which often share wording.
The default config is also run with the entity filter set to the question's
entity, as the UI's "Regulated entity" selector does.
For answer quality (RAGAS faithfulness etc.), see eval/run_ragas.py.

Usage:
    python src/ingest.py --strategy all   # build every collection first
    python eval/run_eval.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.query import get_collection, retrieve

QA_PATH = Path(__file__).resolve().parent / "qa_set.json"
OUT_PATH = Path(__file__).resolve().parent / "eval_results.json"


def normalize(text: str) -> str:
    """Lowercase letters and digits only, so pypdf's stray spaces and
    line-break hyphens ("Percent age", "cooling-\\noff") still match."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def contains_evidence(chunk: str, evidence: list[str]) -> bool:
    chunk = normalize(chunk)
    return any(normalize(e) in chunk for e in evidence)


def check_evidence(qa_set: list, collection_name: str) -> list[str]:
    """Evidence phrases that appear in no chunk at all are typos or quotes
    from a document that isn't ingested; they'd silently count as misses."""
    corpus = [normalize(d) for d in get_collection(collection_name).get()["documents"]]
    missing = []
    for item in qa_set:
        for phrase in item.get("evidence") or []:
            if not any(normalize(phrase) in chunk for chunk in corpus):
                missing.append(f"{item['question'][:60]!r}: {phrase!r}")
    return missing


def evaluate(strategy_name: str, mode: str, qa_set: list, entity_filter: bool = False) -> dict:
    collection_name = f"{config.COLLECTION_NAME}_{strategy_name}"
    details = []
    out_of_corpus = 0

    for item in qa_set:
        # expected_source may be one filename, a list (answer appears in
        # several documents), or null (answer isn't in the corpus at all)
        expected = item["expected_source"]
        if expected is None:
            out_of_corpus += 1
            continue
        expected = [expected] if isinstance(expected, str) else expected
        entity = config.entity_of(expected[0])
        retrieved = retrieve(item["question"], collection_name, k=config.TOP_K, mode=mode,
                             entity=entity if entity_filter else None)

        sources = [meta["source"] for _chunk, meta, _score in retrieved]
        doc_ranks = [i + 1 for i, s in enumerate(sources) if s in expected]
        chunk_ranks = [i + 1 for i, (chunk, meta, _score) in enumerate(retrieved)
                       if meta["source"] in expected and contains_evidence(chunk, item["evidence"])]
        details.append({
            "question": item["question"],
            "expected_source": item["expected_source"],
            "retrieved": [f"{m['source']}::chunk{m['chunk_index']}" for _c, m, _s in retrieved],
            "doc_rank": doc_ranks[0] if doc_ranks else None,
            "chunk_rank": chunk_ranks[0] if chunk_ranks else None,
            "wrong_entity": sum(config.entity_of(s) != entity for s in sources) / len(sources),
        })

    n = len(details)
    return {
        "strategy": strategy_name,
        "mode": mode,
        "entity_filter": entity_filter,
        "doc_hit_rate": sum(d["doc_rank"] is not None for d in details) / n if n else 0,
        "chunk_hit_rate": sum(d["chunk_rank"] is not None for d in details) / n if n else 0,
        "chunk_mrr": sum(1 / d["chunk_rank"] for d in details if d["chunk_rank"]) / n if n else 0,
        "wrong_entity": sum(d["wrong_entity"] for d in details) / n if n else 0,
        "n_questions": n,
        "n_out_of_corpus": out_of_corpus,
        "details": details,
    }


def main():
    qa_set = json.loads(QA_PATH.read_text())
    no_evidence = [q["question"] for q in qa_set if q["expected_source"] and not q.get("evidence")]
    if no_evidence:
        sys.exit("These answerable questions have no 'evidence' phrases:\n  " + "\n  ".join(no_evidence))
    print(f"Loaded {len(qa_set)} eval questions, top_k={config.TOP_K}.\n")

    # strategies differ only in chunking, so one collection is enough to check the quotes
    missing = check_evidence(qa_set, f"{config.COLLECTION_NAME}_{next(iter(config.CHUNK_STRATEGIES))}")
    if missing:
        print("WARNING: evidence not found anywhere in the corpus (fix qa_set.json):")
        for m in missing:
            print(f"  {m}")
        print()

    all_results = []
    for strategy_name in config.CHUNK_STRATEGIES:
        for mode in config.RETRIEVAL_MODES:
            try:
                result = evaluate(strategy_name, mode, qa_set)
            except Exception as e:
                print(f"{strategy_name}/{mode}: skipped ({e}); "
                      f"run python src/ingest.py --strategy {strategy_name}")
                continue
            all_results.append(result)
    try:
        all_results.append(evaluate(config.ACTIVE_CHUNK_STRATEGY, config.ACTIVE_RETRIEVAL_MODE,
                                    qa_set, entity_filter=True))
    except Exception as e:
        print(f"entity-filtered run skipped ({e})")

    OUT_PATH.write_text(json.dumps(all_results, indent=2))
    print(f"Full results written to {OUT_PATH}")

    print("\n--- SUMMARY (paste this into your README) ---")
    print("| Strategy | Retrieval | Doc hit rate | Chunk hit rate | Chunk MRR | Wrong-entity chunks |")
    print("|---|---|---|---|---|---|")
    for r in all_results:
        mode = r["mode"] + (" + entity filter" if r["entity_filter"] else "")
        print(f"| {r['strategy']} | {mode} | {r['doc_hit_rate']:.0%} | "
              f"{r['chunk_hit_rate']:.0%} | {r['chunk_mrr']:.2f} | {r['wrong_entity']:.0%} |")
    if all_results:
        print(f"\nn = {all_results[0]['n_questions']} answerable questions "
              f"(+{all_results[0]['n_out_of_corpus']} out-of-corpus, not scored here)")


if __name__ == "__main__":
    main()
