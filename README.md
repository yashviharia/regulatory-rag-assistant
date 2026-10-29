# RBI Regulation Assistant (RAG)

Question answering over current Reserve Bank of India Master Directions, with
every answer grounded in retrieved excerpts and cited by document and
paragraph. Built to show the parts of RAG that usually get skipped: measuring
retrieval at the passage level, comparing chunking and retrieval strategies
with numbers, and noticing when the corpus itself goes out of date.

**Write-up:** [writeup.md](writeup.md)

![Screenshot: a question about politically exposed persons answered with a paragraph citation and four source excerpts](docs/screenshot.png)

## Corpus
| Document | Issued | Pages |
|---|---|---|
| RBI (Commercial Banks – Know Your Customer) Directions, 2025 | 28 Nov 2025, updated 1 Oct 2026 | 101 |
| RBI (NBFCs – Registration, Exemptions and Framework for Scale Based Regulation) Directions, 2025 | 28 Nov 2025, updated 1 Jul 2026 | 31 |

The first version used six 2021–2025 circulars. Every page of them turned out to
be stamped *Withdrawn*: the RBI's 28 Nov 2025 consolidation replaced 9,445
circulars with 244 Master Directions. They're kept in `data/withdrawn/` (with
their old eval set and results) but no longer ingested.

## How it works
```
data/raw/*.pdf ─► src/ingest.py ─► clean text ─► chunk ─► embed (MiniLM) ─► ChromaDB
                                                                              │
question ─► src/query.py ─► dense search + BM25 ─► reciprocal rank fusion ─► top 4
                                                                              │
                         Groq (gpt-oss-120b) ◄─ excerpts + "answer only from these, cite them"
                                │
                 src/api.py (FastAPI)  ·  frontend/app.py (Streamlit)
```
- **Text cleanup:** drops watermarks, page numbers, table-of-contents lines and
  garbled Hindi letterheads; repairs pypdf's split words and line-wrap hyphens.
- **Section-aware chunking** (default): splits on chapter / lettered section /
  numbered paragraph boundaries, packs whole paragraphs into chunks of at most
  300 words without crossing a heading, and prefixes each chunk with its
  location, e.g. `[Chapter VI – Customer Due Diligence > 42. Updation / Periodic Updation of KYC]`.
- **Hybrid retrieval** (default): embeddings plus BM25 keyword search, merged
  with reciprocal rank fusion, which helps with exact terms like "NBFC-ICC" or "V-CIP".

## Results

### Retrieval (`eval/run_eval.py`, no API key needed)
28 answerable questions written from the two directions, each with a verbatim
evidence quote from its answering passage, plus 3 questions whose answers aren't
in the corpus. A retrieved chunk counts as a hit only if it contains the quote.

| Strategy | Retrieval | Chunk hit rate (top 4) | Chunk MRR |
|---|---|---|---|
| fixed_small (300 words) | dense | 61% | 0.46 |
| fixed_small (300 words) | hybrid | 75% | 0.59 |
| fixed_large (800 words) | dense | 54% | 0.42 |
| fixed_large (800 words) | hybrid | 68% | 0.55 |
| section | dense | 79% | 0.72 |
| **section** | **hybrid** | **82%** | **0.78** |

Document-level hit rate is 100% for every configuration, which with two
documents says nothing; that's why the eval scores passages.

### Answer quality (`eval/run_ragas.py`, RAGAS 0.2.9)
Default configuration (section chunking, hybrid retrieval). Answers by
`gpt-oss-120b`, judged by `gpt-oss-20b` so the model doesn't grade itself.

| Faithfulness | Context precision | Context recall | Questions scored |
|---|---|---|---|
| 0.91 | 0.83 | 0.94 | 17 of 28 (the KYC questions) |

All 3 out-of-corpus questions (digital lending cooling-off period, DLG cap,
small finance bank capital) were answered with "the excerpts don't cover
this" rather than a guess. The remaining 11 questions are waiting on Groq's
daily token cap; re-running the same command scores only what's missing.

### What the numbers say
- **Passage-level scoring changes the picture.** On the old corpus, document hit
  rate was 100% while the answering passage was in the top 4 only 57% of the time.
- **Section-aware chunking wins on well-structured documents.** On the old,
  messier circulars it lost to 300-word windows; on the consolidated directions,
  with consistent chapter → section → paragraph numbering, it leads on both hit
  rate and rank.
- **Hybrid beats dense for every chunker.** Regulatory questions hinge on exact
  terms that BM25 catches and a small embedding model blurs.
- **Remaining misses are paraphrase gaps,** e.g. "shareholding" vs "controlling
  ownership interest", or "what test decides the Upper Layer" vs a one-line
  asset-size rule. Acronym-only phrasing is weaker too: "What NOF does an
  infrastructure finance company need?" misses the paragraph that "minimum net
  owned fund" ranks first. A reranker and acronym expansion are the next steps.

### Caveats
- I wrote the questions after reading the documents, which flatters retrieval.
- 28 questions: differences of a few points are noise.
- Citations can be off by a sub-clause (e.g. 45(1)(iv) for a rule in 45(1)(iii)):
  check the excerpt, which the UI shows under every answer.
- Groq's free tier (8k tokens/min, 200k tokens/day per model) limits how much
  RAGAS can run per day.

## Run it
Needs Python 3.12 (the pinned torch/chromadb/pandas don't support 3.14 yet).
```bash
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # add a free Groq key: https://console.groq.com/keys

python src/ingest.py --strategy all  # build every strategy's index
streamlit run frontend/app.py        # UI (builds the default index itself if missing)
uvicorn src.api:app --reload         # API: localhost:8000/docs
python src/query.py "How often must a bank update KYC for a high-risk customer?"

python eval/run_eval.py              # retrieval, every strategy x retrieval mode
python eval/run_ragas.py --strategy section   # answer quality (needs GROQ_API_KEY)
```

### API
`POST /ask` with `{"question": "...", "strategy": "section", "mode": "hybrid", "top_k": 4}`
(all but `question` optional) returns the answer plus each source's document,
section, score and text. `GET /sources` lists the indexed documents. Bad input
returns 422, a missing index 503, an LLM failure 502. Set `CORS_ORIGINS` to
restrict which sites can call it.

### Adding documents
Add `(pdf_link, slug)` pairs to `scripts/download_sources.py` and run it. RBI's
server often drops scripted requests; if so, save the PDFs from a browser and
run `python scripts/download_sources.py --from-dir ~/Downloads`. Then add
questions with evidence quotes to `eval/qa_set.json`; `run_eval.py` warns about
any quote it can't find in the corpus.

## Deploy
- **Hugging Face Spaces** (used for the demo): `huggingface-cli login`, then
  `python scripts/deploy_hf_space.py`. It uploads the code and PDFs, stores
  `GROQ_API_KEY` as a Space secret, and the app builds its index on first start.
- **Render:** `render.yaml` builds the index during the build and serves the API.

## Stack
sentence-transformers (`all-MiniLM-L6-v2`), ChromaDB, rank-bm25, Groq
(`openai/gpt-oss-120b` answers, `qwen/qwen3.8-27b` as the RAGAS judge so the
model doesn't grade itself), RAGAS 0.2.9, FastAPI, Streamlit.
