#!/usr/bin/env python
"""Clone/refresh Lenny's Podcast transcripts and (re)build the retrieval index.

Usage:
    python scripts/ingest_transcripts.py
    python scripts/ingest_transcripts.py --skip-clone   # index files already on disk
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.services.retrieval.retriever import build_index


def clone_or_pull(repo_url: str, target_dir: Path):
    if (target_dir / ".git").exists():
        print(f"[ingest] Updating existing checkout at {target_dir} ...")
        subprocess.run(["git", "-C", str(target_dir), "pull", "--ff-only"], check=True)
    else:
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        print(f"[ingest] Cloning {repo_url} into {target_dir} ...")
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(target_dir)], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-clone", action="store_true", help="Skip git clone/pull, just index what's on disk.")
    args = parser.parse_args()

    settings = get_settings()
    transcripts_dir = Path(settings.transcripts_dir)

    if not args.skip_clone:
        clone_or_pull(settings.transcripts_repo_url, transcripts_dir)
    elif not transcripts_dir.exists():
        print(f"[ingest] ERROR: {transcripts_dir} does not exist and --skip-clone was passed.", file=sys.stderr)
        sys.exit(1)

    print(f"[ingest] Building index at {settings.index_db_path} ...")
    stats = build_index(
        transcripts_dir=str(transcripts_dir),
        index_db_path=settings.index_db_path,
        chunk_target_chars=settings.chunk_target_chars,
    )
    print(f"[ingest] Done. {stats}")


if __name__ == "__main__":
    main()
