"""
Deploys the Streamlit app to a Hugging Face Space.

The Space builds the ChromaDB index on first start (frontend/app.py), so
only code and the source PDFs are uploaded. GROQ_API_KEY from .env is
stored as a Space secret, never as a file.

One-time setup:  venv/bin/huggingface-cli login   (token with write access)
Usage:           python scripts/deploy_hf_space.py [--space user/name]
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent

# Hugging Face reads the Space config from the README's front matter; it's
# written only into the Space copy so the GitHub README stays clean.
SPACE_README = """---
title: RBI Regulation Assistant
emoji: 🏦
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.41.1
python_version: "3.12"
app_file: frontend/app.py
pinned: false
short_description: RAG over current RBI KYC and NBFC Master Directions
---

"""

UPLOAD_PATTERNS = ["src/*.py", "frontend/*.py", ".streamlit/config.toml", "data/raw/*.pdf", "requirements.txt"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--space", default=None,
                        help="Space id, e.g. yashviharia/rbi-regulation-assistant "
                             "(default: <your HF username>/rbi-regulation-assistant)")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    api = HfApi()
    try:
        user = api.whoami()["name"]
    except Exception:
        sys.exit("Not logged in to Hugging Face. Run: venv/bin/huggingface-cli login")
    space = args.space or f"{user}/rbi-regulation-assistant"

    api.create_repo(space, repo_type="space", space_sdk="streamlit", exist_ok=True)
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key and groq_key != "your_key_here":
        api.add_space_secret(space, "GROQ_API_KEY", groq_key)
    else:
        print("WARNING: no GROQ_API_KEY in .env; the Space will show excerpts only.")

    with tempfile.TemporaryDirectory() as tmp:
        readme = Path(tmp) / "README.md"
        readme.write_text(SPACE_README + (ROOT / "README.md").read_text())
        api.upload_file(path_or_fileobj=str(readme), path_in_repo="README.md",
                        repo_id=space, repo_type="space")
    api.upload_folder(folder_path=str(ROOT), repo_id=space, repo_type="space",
                      allow_patterns=UPLOAD_PATTERNS,
                      commit_message="Deploy from scripts/deploy_hf_space.py")
    print(f"Deployed: https://huggingface.co/spaces/{space}")


if __name__ == "__main__":
    main()
