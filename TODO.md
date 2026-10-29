# Build plan (5 weeks)

- [x] Week 0: repo scaffolding
- [x] Week 1: corpus — switched to the current RBI Master Directions (KYC for commercial banks; NBFC registration + SBR), since all six original circulars were withdrawn by the 28 Nov 2025 consolidation (archived in data/withdrawn/)
- [x] Week 2: ingestion pipeline (clean -> chunk -> embed -> ChromaDB) + query end to end
- [x] Week 3: eval
  - [x] 28 answerable + 3 out-of-corpus questions with verbatim evidence quotes
  - [x] chunk-level retrieval eval: 3 chunking strategies x dense/hybrid retrieval
  - [x] section-aware chunking + hybrid BM25 retrieval (now the defaults)
  - [x] RAGAS on the default config, judged by a different model: 17 of 28 scored
  - [ ] score the other 11: re-run `python eval/run_ragas.py` once Groq's daily cap resets (it resumes)
- [x] Week 4: FastAPI + Streamlit UI; deploy
  - [x] API: strategy/mode/top_k params, scores + sections in sources, /sources, CORS, 422/502/503 errors
  - [x] Streamlit UI: chat history, example questions, source cards, settings, auto index build
  - [x] scripts/deploy_hf_space.py (Hugging Face Spaces)
  - [ ] deploy: `huggingface-cli login`, then `python scripts/deploy_hf_space.py`; add the link to README + writeup.md
- [x] Week 5: README with real numbers, write-up post (writeup.md)
  - [ ] demo GIF

## Ideas beyond the plan
- [ ] cross-encoder reranker over the top 20 (remaining misses are paraphrase gaps)
- [ ] per-chunk document status (issued / withdrawn) and a warning when an answer relies on a superseded rule
- [ ] RAGAS for the non-default strategies (Groq's daily token cap allows about one per day)
- [ ] more Master Directions (digital lending lives in the new entity-specific directions)
