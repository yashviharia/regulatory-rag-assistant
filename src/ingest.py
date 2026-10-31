"""
Loads documents from SOURCE_DIR, chunks them, embeds the chunks, and
stores everything in a local ChromaDB collection.

Usage:
    python src/ingest.py                      # uses ACTIVE_CHUNK_STRATEGY
    python src/ingest.py --strategy fixed_large
    python src/ingest.py --strategy all       # every strategy, for the eval
"""

import argparse
import re
import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config

# Page furniture pypdf extracts from RBI PDFs: the "Withdrawn" watermark,
# page numbers ("13", "-12-") and table-of-contents lines ("10. Cooling-off ..... 10").
WATERMARK_RE = re.compile(r"^\s*Withdrawn\s*$")
PAGE_NUMBER_RE = re.compile(r"^\s*-?\s*\d{1,3}\s*-?\s*$")
TOC_LINE_RE = re.compile(r"\.{5,}\s*\d+\s*$")

# A chapter or annex title: "Chapter III: Conduct ...", "Chapter-II – Framework ...",
# "Annex – I". Cross-references ("Chapter IX of the Directions, ...") don't match.
CHAPTER_RE = re.compile(r"^\s*((?:Chapter[\s-]+[IVXLC]+\b|Annex(?:ure)?(?:[\s–-]+[IVXLC\d]+)?)"
                        r"(?:\s*[–:.-]?\s*[A-Z(].{0,100})?)\s*$")
# A lettered heading under a chapter: "A. Short Title and Commencement" (not "I." / "V."
# / "X.", which are roman-numeral list items)
LETTER_HEADING_RE = re.compile(r"^\s*([A-HJ-UWYZ])\.\s+([A-Z][^.]{2,90}?)[.:]?\s*$")
# A numbered heading: "10. Cooling-off period" — short, no full stop at the end
HEADING_RE = re.compile(r"^\s*(\d{1,3})\.\s+([A-Z][^.]{2,90})$")
# A paragraph start: any of the above, or "5.1.14 “Infrastructure ...". Sub-clauses like
# "i." or "(a)" stay inside their paragraph.
NUMBERED_PARA_RE = re.compile(r"^\s*\d{1,3}(?:\.\d{1,3}){0,3}\.?\s+\S")


PROSE_OPENERS = {"The", "For", "Any", "In", "If", "An", "A", "All", "Once", "Such", "These", "This", "Where"}


def is_numbered_heading(m: re.Match) -> bool:
    # numbered prose ("2. The Reserve Bank has observed ...", "10. The Base Layer
    # shall comprise of:") isn't a heading
    title = m.group(2).strip()
    return (len(title.split()) <= 10 and " shall " not in f" {title} "
            and title[-1] not in ":,;" and title.split()[0] not in PROSE_OPENERS)


def clean_text(text: str) -> str:
    """Strips page furniture and repairs the commonest pypdf splits."""
    lines = []
    for line in text.splitlines():
        if WATERMARK_RE.match(line) or PAGE_NUMBER_RE.match(line) or TOC_LINE_RE.search(line):
            continue
        # Hindi letterheads extract as mojibake; drop lines that are mostly non-ASCII
        if line.strip() and sum(c.isascii() for c in line) / len(line) < 0.5:
            continue
        lines.append(line.rstrip())
    text = "\n".join(lines)
    # a heading's first letter or two split onto its own line: "R\neserve Bank", "RB\nI/2025"
    text = re.sub(r"^([A-Z][A-Za-z]?)\n(?=\S)", r"\1", text, flags=re.MULTILINE)
    # stray spaces and line wraps around hyphens: "mis -selling", "Cooling- off", "cooling-\noff"
    text = re.sub(r"(\w) -(\w)", r"\1-\2", text)
    text = re.sub(r"(\w)-[ \t]*\n?[ \t]*(\w)", r"\1-\2", text)
    # a capital split off its word: "C ertain", "D igital" (not "A" or "I", which are words)
    text = re.sub(r"\b([B-HJ-Z]) ([a-z]{2,})", r"\1\2", text)
    return text


def load_documents(source_dir: Path) -> list[dict]:
    """Returns a list of {source, text} dicts from .txt and .pdf files."""
    docs = []
    for path in sorted(source_dir.glob("*")):
        if path.suffix.lower() == ".txt":
            text = path.read_text(encoding="utf-8")
        elif path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            continue
        text = clean_text(text)
        if text.strip():
            docs.append({"source": path.name, "text": text})
    return docs


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Simple word-based sliding-window chunker; the baseline strategy."""
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(chunk_size - chunk_overlap, 1)
    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break
    return chunks


def split_sections(text: str) -> list[dict]:
    """Splits text into numbered paragraphs, each tagged with the chapter
    and top-level heading it falls under."""
    paras, current = [], []
    chapter, heading = "", ""

    def flush():
        if current:
            paras.append({"chapter": chapter, "heading": heading, "text": " ".join(current)})

    for line in text.splitlines():
        if not line.strip():
            continue
        chapter_m = CHAPTER_RE.match(line)
        letter_m = LETTER_HEADING_RE.match(line)
        if chapter_m or letter_m or NUMBERED_PARA_RE.match(line):
            flush()
            current = []
            if chapter_m:
                chapter, heading = chapter_m.group(1).strip(), ""
            elif letter_m:
                heading = f"{letter_m.group(1)}. {letter_m.group(2).strip()}"
            elif (m := HEADING_RE.match(line)) and is_numbered_heading(m):
                heading = f"{m.group(1)}. {m.group(2).strip()}"
        current.append(line.strip())
    flush()
    return paras


def chunk_sections(text: str, chunk_size: int, chunk_overlap: int) -> list[dict]:
    """Packs whole paragraphs into chunks of at most chunk_size words without
    crossing a heading, so a chunk never mixes two rules. Each chunk starts
    with its chapter/heading so the embedding knows where it sits; a single
    paragraph longer than chunk_size falls back to the word window."""
    chunks = []
    buf, buf_words, buf_key = [], 0, None

    def emit(key, body):
        chapter, heading = key
        label = " > ".join(p for p in (chapter, heading) if p)
        chunks.append({"section": label, "text": f"[{label}]\n{body}" if label else body})

    def flush():
        nonlocal buf, buf_words
        if buf:
            emit(buf_key, " ".join(buf))
        buf, buf_words = [], 0

    for para in split_sections(text):
        key = (para["chapter"], para["heading"])
        n = len(para["text"].split())
        # a bare chapter title joins its first section instead of standing alone
        joins_chapter = bool(buf_key) and not buf_key[1] and buf_key[0] == key[0]
        if (key != buf_key and not joins_chapter) or buf_words + n > chunk_size:
            flush()
        buf_key = key
        if n > chunk_size:
            for piece in chunk_text(para["text"], chunk_size, chunk_overlap):
                emit(key, piece)
            continue
        buf.append(para["text"])
        buf_words += n
    flush()
    return chunks


def make_chunks(text: str, strategy: dict) -> list[dict]:
    if strategy["chunker"] == "section":
        return chunk_sections(text, strategy["chunk_size"], strategy["chunk_overlap"])
    return [{"section": "", "text": c}
            for c in chunk_text(text, strategy["chunk_size"], strategy["chunk_overlap"])]


def ingest(strategy_name: str, docs: list[dict], model: SentenceTransformer,
           collection_name: str = None):
    strategy = config.CHUNK_STRATEGIES[strategy_name]
    collection_name = collection_name or f"{config.COLLECTION_NAME}_{strategy_name}"

    print(f"Chunking with strategy '{strategy_name}' ({strategy}) ...")
    all_chunks, all_ids, all_metadatas = [], [], []
    for doc in docs:
        for i, chunk in enumerate(make_chunks(doc["text"], strategy)):
            all_chunks.append(chunk["text"])
            all_ids.append(f"{doc['source']}::chunk{i}")
            all_metadatas.append({"source": doc["source"], "chunk_index": i,
                                  "section": chunk["section"],
                                  "entity": config.entity_of(doc["source"])})
    print(f"Produced {len(all_chunks)} chunks total.")

    print("Embedding chunks ...")
    embeddings = model.encode(all_chunks, show_progress_bar=True).tolist()

    print(f"Writing to ChromaDB collection '{collection_name}' ...")
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR),
                                       settings=Settings(anonymized_telemetry=False))
    # fresh start each run so re-ingesting doesn't duplicate chunks
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(collection_name)

    batch = 100
    for i in tqdm(range(0, len(all_chunks), batch), desc="writing"):
        collection.add(
            ids=all_ids[i : i + batch],
            documents=all_chunks[i : i + batch],
            embeddings=embeddings[i : i + batch],
            metadatas=all_metadatas[i : i + batch],
        )

    print(f"Done. {collection.count()} chunks stored in '{collection_name}'.\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default=config.ACTIVE_CHUNK_STRATEGY,
                         choices=list(config.CHUNK_STRATEGIES.keys()) + ["all"])
    parser.add_argument("--collection", default=None,
                         help="Override collection name (single strategy only)")
    args = parser.parse_args()
    if args.strategy == "all" and args.collection:
        parser.error("--collection can't be combined with --strategy all")

    print(f"Loading documents from {config.SOURCE_DIR} ...")
    docs = load_documents(config.SOURCE_DIR)
    if not docs:
        print(f"No .txt/.pdf files found in {config.SOURCE_DIR}. "
              f"Run scripts/download_sources.py first, or check config.SOURCE_DIR.")
        return
    print(f"Loaded {len(docs)} source documents.")

    print(f"Loading embedding model '{config.EMBEDDING_MODEL}' ...")
    model = SentenceTransformer(config.EMBEDDING_MODEL)

    strategies = list(config.CHUNK_STRATEGIES) if args.strategy == "all" else [args.strategy]
    for name in strategies:
        ingest(name, docs, model, args.collection)


if __name__ == "__main__":
    main()
