# My RAG eval said 100%. It was answering from withdrawn regulations.

I built a question-answering assistant over Reserve Bank of India regulations:
local embeddings, ChromaDB, an LLM on Groq, FastAPI and Streamlit. The
interesting part wasn't the pipeline. It was the three times the numbers told
me something I didn't expect.

## 1. "Right document" is not "right answer"

My first retrieval metric checked whether the expected *document* appeared in
the top 4 results. My smallest chunking strategy scored 100%.

Then I ran RAGAS, which uses an LLM judge to check whether the retrieved text
actually contains what the reference answer needs. Context recall was 0.50:
half the time, the right document came back but the passage that answers the
question didn't.

So I rewrote the retrieval eval. Each question now carries a short verbatim
quote from the answering passage, and a retrieved chunk only counts if it
contains that quote (compared on letters and digits only, so PDF extraction
quirks like `Percent age` still match). That single change turned a 100% into a
57%, and made every later comparison honest.

## 2. The corpus had quietly gone stale

While writing a section-aware chunker I looked at the raw PDF text and noticed
every page of every document ended with the word *Withdrawn*. On 28 November
2025 the RBI withdrew 9,445 circulars and consolidated them into 244 Master
Directions per type of regulated entity. All six of my source documents were
among them.

Nothing in the pipeline or the eval could catch that: the answers were
grounded, cited and faithful, just to rules that no longer applied. I swapped
in the current directions (KYC for commercial banks, and NBFC registration and
scale-based regulation, as updated in 2026) and rewrote the eval set against
them. At least one rule had materially changed: the Upper Layer for NBFCs is
now a flat ₹1,00,000 crore asset-size test instead of a scoring methodology.

## 3. The best chunking strategy depends on the documents

I compared three chunkers (300- and 800-word sliding windows, and a
section-aware splitter that breaks on RBI paragraph numbers and prefixes every
chunk with its chapter and heading), each with dense-only and hybrid
(BM25 + embeddings, reciprocal rank fusion) retrieval.

On the old, messier corpus, section-aware chunking lost. On the new one,
which has consistent chapter / lettered-section / numbered-paragraph
structure, it won clearly:

| Strategy | Retrieval | Chunk hit rate (top 4) | Chunk MRR |
|---|---|---|---|
| fixed 300 words | dense | 61% | 0.46 |
| fixed 300 words | hybrid | 75% | 0.59 |
| fixed 800 words | dense | 54% | 0.42 |
| fixed 800 words | hybrid | 68% | 0.55 |
| section-aware | dense | 79% | 0.72 |
| **section-aware** | **hybrid** | **82%** | **0.78** |

28 answerable questions written from the current directions, plus 3 whose
answers aren't in the corpus. Hybrid retrieval beat dense for every chunker:
regulatory questions lean on exact terms ("NBFC-ICC", "V-CIP", "PEP") that
keyword search catches and small embedding models blur.

On answer quality (RAGAS, answers by `gpt-oss-120b`, judged by a different
model, `gpt-oss-20b`), the default configuration scored 0.91 faithfulness,
0.83 context precision and 0.94 context recall on the 17 questions the free
tier's daily token cap allowed. The assistant also declined all three
questions whose answers aren't in the documents instead of guessing.

The free tier shaped the tooling too: one RAGAS run doesn't fit in a day's
tokens, so the eval caches answers, saves each question's scores as they
arrive, and resumes where it stopped.

## What I'd do next

- **Rerank.** The remaining misses are paraphrase gaps ("shareholding" vs
  "controlling ownership interest"); a cross-encoder reranker over the top 20
  is the obvious next step.
- **Track document status.** Store issue date and withdrawn/current status per
  chunk, and warn when an answer leans on a superseded rule. Most RAG demos
  assume documents never change; regulation is the opposite.
- **A bigger eval set, written by someone else.** I wrote the questions after
  reading the documents, which flatters retrieval a little.

## Try it

- Code: https://github.com/yashviharia/regulatory-rag-assistant
