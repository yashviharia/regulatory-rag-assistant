These files are placeholder dev fixtures I wrote myself (not copied from
any real circular) so the ingestion/retrieval pipeline could be built and
tested without needing network access. They are deliberately short and
simplified.

Before running the real project, replace this folder's role entirely:
run `scripts/download_sources.py` to pull real RBI/SEBI PDFs into
`data/raw/`, and point `src/config.py` at `data/raw/` instead of here.
Your actual eval numbers should come from the real documents, not these
fixtures.
