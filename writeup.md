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

On the old, messier corpus, section-aware chunking lost. On the current
directions, which have consistent chapter / lettered-section /
numbered-paragraph structure, it won clearly (these are the 28 questions on the
two-direction corpus; section 4 has the 14-direction numbers):

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
0.81 context precision and 0.89 context recall on all 28 questions. The
assistant also declined all three questions whose answers weren't in the
documents instead of guessing.

The free tier shaped the tooling too: one RAGAS run doesn't fit in a day's
tokens, so the eval caches answers, saves each question's scores as they
arrive, and resumes where it stopped.

## 4. Two documents was a toy; fourteen was a test

With only the two directions I started from, "did the right document come
back" was 100% by default, and most questions a visitor would ask (loans,
cards, recovery agents, digital lending) got "not covered". So I grew the
corpus to 14 Master Directions, about 830 pages: nine for commercial banks and
five for NBFCs.

Two things happened. On the original 28 questions the default setup kept its
82% hit rate but its MRR fell from 0.78 to 0.69: the right passage still made
the top 4, just behind look-alikes from other directions. And the corpus now
had near-duplicates. The bank and NBFC KYC directions both say high-risk
customers' KYC must be refreshed "at least once in every two years". Without
help, one in six retrieved chunks came from the wrong entity's directions.

The fix was boring and effective: tag every chunk with the entity it applies
to, let retrieval filter on it, and tell the model which entity each excerpt
covers. On 50 questions across all 14 directions:

| Setup | Chunk hit rate | MRR | Wrong-entity chunks |
|---|---|---|---|
| section + hybrid | 82% | 0.68 | 16% |
| section + hybrid + entity filter | 84% | 0.72 | 0% |

Growing the corpus also broke my eval in a useful way: two of my three
"out-of-corpus" questions (the digital lending cooling-off period and the DLG
cap) were now answerable, because digital lending moved into the banks'
Credit Facilities direction. Out-of-corpus tests need re-checking every time
the corpus changes.

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

- Live demo: https://regulatory-rag-assistant-g8pv5qvhhtguovlbk9ihd8.streamlit.app
- Code: https://github.com/yashviharia/regulatory-rag-assistant
