"""
Downloads the RBI Master Direction PDFs into data/raw/.

The corpus is the current consolidated directions the RBI issued on
28 Nov 2025 (which withdrew the older circulars; those live in
data/withdrawn/ for reference). Each entry is a direct rbidocs PDF link.

rbidocs.rbi.org.in often drops scripted requests. If that happens, open
the links in your browser, save the PDFs (keep RBI's filenames), and run:
    python scripts/download_sources.py --from-dir ~/Downloads
which finds each file there, checks it's a real PDF, and copies it into
data/raw/ under its slug. Nothing is written unless the bytes start with %PDF.
"""

import argparse
import shutil
import sys
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# (direct PDF link, short slug for the filename)
SOURCES = [
    ("https://rbidocs.rbi.org.in/rdocs/notification/PDFs/169MD.pdf",
     "kyc_directions_commercial_banks_2025"),
    ("https://rbidocs.rbi.org.in/rdocs/notification/PDFs/339MD7166A79E96D64572B378949D3972DBD1.PDF",
     "nbfc_sbr_directions_2025"),
    # Add more (link, slug) pairs as you expand the corpus; the RBI lists the
    # Master Directions per type of regulated entity on its website.
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; student-research-project)"}


class DownloadError(Exception):
    pass


def fetch_pdf(url: str) -> bytes:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    print(f"  {resp.status_code}  Content-Type: {resp.headers.get('Content-Type')}")
    if not resp.content.startswith(b"%PDF"):
        raise DownloadError(f"not a PDF (body starts with {resp.content[:20]!r})")
    return resp.content


def import_from_dir(url: str, from_dir: Path) -> Path:
    """Locate the browser-saved PDF for this link in from_dir."""
    name = url.rsplit("/", 1)[-1].lower()
    matches = [p for p in from_dir.iterdir() if p.name.lower() == name]
    if not matches:
        raise DownloadError(f"{name} not found in {from_dir}; open {url} and save it there")
    if matches[0].read_bytes()[:4] != b"%PDF":
        raise DownloadError(f"{matches[0]} is not a valid PDF")
    return matches[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-dir", type=Path, default=None,
                        help="Copy browser-saved PDFs from this folder instead of downloading")
    args = parser.parse_args()

    failed = []
    for url, slug in SOURCES:
        out_path = RAW_DIR / f"{slug}.pdf"
        if out_path.exists():
            print(f"skip (exists): {out_path.name}")
            continue
        print(slug)
        try:
            if args.from_dir:
                src = import_from_dir(url, args.from_dir.expanduser())
                shutil.copyfile(src, out_path)
                print(f"  copied {src.name} -> {out_path.name}")
                continue
            content = fetch_pdf(url)
        except Exception as e:
            print(f"  FAILED: {e}")
            failed.append(slug)
            continue
        out_path.write_bytes(content)
        print(f"  saved {out_path.name} ({len(content):,} bytes)")

    if failed:
        print(f"\n{len(failed)} download(s) failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
