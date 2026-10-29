"""
Answer-quality evaluation with RAGAS, run on top of the retrieval eval.

For every answerable question in qa_set.json it runs the full pipeline
(retrieve -> Groq answer) for a chunking strategy, then scores:
  - faithfulness:      is every claim in the answer supported by the
                       retrieved excerpts? (catches hallucination)
  - context_precision: are the relevant excerpts ranked near the top?
  - context_recall:    do the excerpts contain what the reference answer needs?

Questions with expected_source = null (answer not in the corpus) can't be
scored this way; their answers are printed so you can check by eye that
the assistant says it can't find the answer instead of guessing.

Groq's free tier caps tokens per day per model, so a full run may not fit
in one day. Everything is resumable: answers are cached in
eval/ragas_cache/, each question's scores are saved as soon as they're in,
and re-running the same command only does what's missing (including
retrying questions whose scores failed).

Needs GROQ_API_KEY. The judge (config.RAGAS_JUDGE_MODEL) is a different
model from the one that writes the answers, so the model isn't grading itself.

Usage:
    python eval/run_ragas.py                          # default strategy
    python eval/run_ragas.py --strategy fixed_small
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.query import answer

EVAL_DIR = Path(__file__).resolve().parent
QA_PATH = EVAL_DIR / "qa_set.json"
OUT_PATH = EVAL_DIR / "ragas_results.json"
CACHE_DIR = EVAL_DIR / "ragas_cache"
METRIC_NAMES = ["faithfulness", "llm_context_precision_with_reference", "context_recall"]


def build_judge():
    from langchain_groq import ChatGroq
    from ragas.llms import LangchainLLMWrapper
    return LangchainLLMWrapper(ChatGroq(model=config.RAGAS_JUDGE_MODEL, temperature=0,
                                        model_kwargs=config.RAGAS_JUDGE_KWARGS))


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def get_answers(strategy_name: str, mode: str, qa_set: list) -> dict:
    """question -> {answer, contexts}, generating only what isn't cached."""
    cache_path = CACHE_DIR / f"answers_{strategy_name}_{mode}.json"
    cache = load_json(cache_path, {})
    collection_name = f"{config.COLLECTION_NAME}_{strategy_name}"
    todo = [item for item in qa_set if item["question"] not in cache]
    for i, item in enumerate(todo, 1):
        print(f"  answering {i}/{len(todo)}: {item['question'][:60]}")
        result = answer(item["question"], collection_name, mode=mode)
        cache[item["question"]] = {"answer": result["answer"],
                                   "contexts": [chunk for chunk, _m, _s in result["retrieved"]]}
        CACHE_DIR.mkdir(exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    return cache


def score_one(item: dict, cached: dict, judge) -> dict:
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference, LLMContextRecall
    from ragas.run_config import RunConfig

    sample = SingleTurnSample(user_input=item["question"], retrieved_contexts=cached["contexts"],
                              response=cached["answer"], reference=item["reference_answer"])
    # Groq's free tier rate-limits hard: one request at a time, retry on 429s
    scores = evaluate(
        EvaluationDataset(samples=[sample]),
        metrics=[Faithfulness(), LLMContextPrecisionWithReference(), LLMContextRecall()],
        llm=judge,
        run_config=RunConfig(max_workers=1, max_retries=4, max_wait=60, timeout=180),
        raise_exceptions=False,
        show_progress=False,
    )
    row = scores.to_pandas().to_dict(orient="records")[0]
    return {"question": item["question"], "answer": cached["answer"],
            **{name: (None if math.isnan(row[name]) else row[name]) for name in METRIC_NAMES}}


def summarize(strategy_name: str, mode: str, rows: dict, n_answerable: int, out_of_corpus: list) -> dict:
    means = {}
    for name in METRIC_NAMES:
        values = [r[name] for r in rows.values() if r[name] is not None]
        means[name] = sum(values) / len(values) if values else None
    complete = sum(all(r[n] is not None for n in METRIC_NAMES) for r in rows.values())
    return {"strategy": strategy_name, "mode": mode, "judge": config.RAGAS_JUDGE_MODEL,
            "n_answerable": n_answerable, "n_fully_scored": complete,
            "means": means, "details": list(rows.values()), "out_of_corpus_answers": out_of_corpus}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=list(config.CHUNK_STRATEGIES.keys()),
                        default=config.ACTIVE_CHUNK_STRATEGY)
    parser.add_argument("--mode", choices=config.RETRIEVAL_MODES, default=config.ACTIVE_RETRIEVAL_MODE)
    args = parser.parse_args()

    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY is not set. RAGAS needs an LLM to judge answers; "
              "add your key to .env (free at https://console.groq.com/keys).")
        sys.exit(1)

    qa_set = json.loads(QA_PATH.read_text())
    answerable = [q for q in qa_set if q["expected_source"] is not None]
    print(f"Strategy {args.strategy}/{args.mode}, judge {config.RAGAS_JUDGE_MODEL}")
    answers = get_answers(args.strategy, args.mode, qa_set)
    out_of_corpus = [{"question": q["question"], "answer": answers[q["question"]]["answer"]}
                     for q in qa_set if q["expected_source"] is None]

    # results from earlier runs: other strategies are kept as they are, and
    # this strategy's fully scored questions are skipped
    saved = {(r["strategy"], r.get("mode")): r for r in load_json(OUT_PATH, [])}
    key = (args.strategy, args.mode)
    rows = {}
    if key in saved and saved[key].get("judge") == config.RAGAS_JUDGE_MODEL:
        rows = {r["question"]: r for r in saved[key]["details"]}
    judge = build_judge()

    todo = [q for q in answerable
            if q["question"] not in rows or any(rows[q["question"]][n] is None for n in METRIC_NAMES)]
    print(f"{len(answerable) - len(todo)} of {len(answerable)} already scored; scoring {len(todo)}")
    for i, item in enumerate(todo, 1):
        row = score_one(item, answers[item["question"]], judge)
        rows[item["question"]] = row
        cells = "  ".join(f"{n[:12]}={'fail' if row[n] is None else f'{row[n]:.2f}'}" for n in METRIC_NAMES)
        print(f"  [{i}/{len(todo)}] {cells}  {item['question'][:50]}")
        saved[key] = summarize(args.strategy, args.mode, rows, len(answerable), out_of_corpus)
        OUT_PATH.write_text(json.dumps(list(saved.values()), indent=2, ensure_ascii=False, default=str))
        if all(row[n] is None for n in METRIC_NAMES):
            print("Every metric failed for this question; probably the judge's daily token cap. "
                  "Re-run the same command later to continue.")
            break

    saved[key] = summarize(args.strategy, args.mode, rows, len(answerable), out_of_corpus)
    OUT_PATH.write_text(json.dumps(list(saved.values()), indent=2, ensure_ascii=False, default=str))
    print(f"\nResults written to {OUT_PATH}")

    print("\n--- SUMMARY (paste this into your README) ---")
    print("| Strategy | Retrieval | Faithfulness | Context precision | Context recall | Questions scored |")
    print("|---|---|---|---|---|---|")
    for r in saved.values():
        m = r["means"]
        cells = " | ".join("n/a" if m[n] is None else f"{m[n]:.2f}" for n in METRIC_NAMES)
        print(f"| {r['strategy']} | {r.get('mode', '')} | {cells} | {r.get('n_fully_scored')} of {r.get('n_answerable')} |")

    print("\n--- OUT-OF-CORPUS ANSWERS (should say the answer isn't in the context) ---")
    for item in out_of_corpus:
        print(f"Q: {item['question']}\n  A: {item['answer'][:300]}\n")


if __name__ == "__main__":
    main()
