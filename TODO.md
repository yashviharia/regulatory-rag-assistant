# Build plan (5 weeks)

- [x] Week 0: repo scaffolding
- [x] Week 1: corpus — switched to the current RBI Master Directions (KYC for commercial banks; NBFC registration + SBR), since all six original circulars were withdrawn by the 28 Nov 2025 consolidation (archived in data/withdrawn/)
- [x] Week 2: ingestion pipeline (clean -> chunk -> embed -> ChromaDB) + query end to end
- [x] Week 3: eval
  - [x] 28 answerable + 3 out-of-corpus questions with verbatim evidence quotes
  - [x] chunk-level retrieval eval: 3 chunking strategies x dense/hybrid retrieval
  - [x] section-aware chunking + hybrid BM25 retrieval (now the defaults)
  - [x] RAGAS on the default config, judged by a different model
  - [x] all 28 scored on the 2-direction corpus (0.91 / 0.81 / 0.89)
- [x] Week 4: FastAPI + Streamlit UI; deploy
  - [x] API: strategy/mode/top_k params, scores + sections in sources, /sources, CORS, 422/502/503 errors
  - [x] Streamlit UI: chat history, example questions, source cards, settings, auto index build
  - [x] scripts/deploy_hf_space.py (Hugging Face Spaces)
  - [x] deployed on Streamlit Community Cloud: https://regulatory-rag-assistant-g8pv5qvhhtguovlbk9ihd8.streamlit.app
- [x] Week 5: README with real numbers, write-up post (writeup.md)
  - [ ] demo GIF

## Ideas beyond the plan
- [ ] cross-encoder reranker over the top 20 (remaining misses are paraphrase gaps)
- [ ] per-chunk document status (issued / withdrawn) and a warning when an answer relies on a superseded rule
- [ ] RAGAS for the non-default strategies (Groq's daily token cap allows about one per day)
- [x] more Master Directions: 14 now (9 bank, 5 NBFC), with a bank/NBFC entity filter
- [ ] RAGAS on the 14-direction corpus and all 50 questions (about 3 days of Groq's judge quota)
