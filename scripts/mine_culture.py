#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from culture_miner import format_summary, mine_culture
from config import CULTURE_FEATURES_TEMPLATE, DEFAULT_SUBREDDIT, resolve_subreddit


def parse_args():
    parser = argparse.ArgumentParser(
        description="Mine subreddit culture features from the raw SQLite corpus."
    )
    parser.add_argument(
        "subreddit",
        nargs="?",
        default=None,
        help=f"Subreddit name without r/ (default: SUBREDDIT env or {DEFAULT_SUBREDDIT})",
    )
    parser.add_argument(
        "--db",
        default="data/corpus.sqlite",
        help="SQLite corpus database path"
    )
    parser.add_argument(
        "--output",
        default=CULTURE_FEATURES_TEMPLATE,
        help="Output JSON path; {subreddit} is substituted when present"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=25,
        help="Number of ranked items to keep for n-grams, exemplars, etc."
    )
    parser.add_argument(
        "--min-ngram-count",
        type=int,
        default=2,
        help="Minimum frequency for n-gram and term features"
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print the human-readable summary without writing JSON"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    subreddit = resolve_subreddit(args.subreddit)
    features = mine_culture(
        args.db,
        subreddit,
        top_k=args.top_k,
        min_ngram_count=args.min_ngram_count,
    )
    print(format_summary(features))

    if args.summary_only:
        return

    output_path = Path(args.output.format(subreddit=subreddit))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(features, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote_features={output_path}")


if __name__ == "__main__":
    main()
