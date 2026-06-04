#!/usr/bin/env python
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from corpus_indexer import build_chroma_index, format_index_summary


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a ChromaDB retrieval index from the SQLite corpus."
    )
    parser.add_argument(
        "subreddit",
        nargs="?",
        default="redscarepod",
        help="Subreddit name without r/",
    )
    parser.add_argument(
        "--db",
        default="data/corpus.sqlite",
        help="SQLite corpus database path",
    )
    parser.add_argument(
        "--chroma-db",
        default="chroma_db",
        help="ChromaDB persistent storage path",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete and recreate the subreddit collection before indexing",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records to upsert per batch",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    stats = build_chroma_index(
        args.db,
        args.subreddit,
        chroma_db_path=args.chroma_db,
        rebuild=args.rebuild,
        batch_size=args.batch_size,
    )
    print(format_index_summary(stats))


if __name__ == "__main__":
    main()
