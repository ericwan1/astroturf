#!/usr/bin/env python
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from comment_generator import CommentGenerator, load_culture_features
from config import CULTURE_FEATURES_TEMPLATE, DEFAULT_SUBREDDIT, resolve_subreddit
from llm import LLMConfig, LLMWrapper


def sample_posts(conn: sqlite3.Connection, subreddit: str, limit: int) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT p.reddit_id, p.title, p.selftext, p.score
        FROM raw_post_snapshots p
        INNER JOIN (
            SELECT reddit_id, MAX(scraped_at) AS latest_scraped_at
            FROM raw_post_snapshots
            WHERE subreddit = ?
            GROUP BY reddit_id
        ) latest
            ON p.reddit_id = latest.reddit_id
           AND p.scraped_at = latest.latest_scraped_at
        WHERE p.subreddit = ?
          AND p.title IS NOT NULL
          AND TRIM(p.title) != ''
        ORDER BY p.score DESC, p.created_utc DESC
        LIMIT ?
        """,
        (subreddit, subreddit, limit),
    ).fetchall()


def sample_real_comments(
    conn: sqlite3.Connection,
    post_reddit_id: str,
    limit: int = 3,
) -> list[str]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT c.body, c.score
        FROM raw_comment_snapshots c
        INNER JOIN raw_post_snapshots p ON p.id = c.post_snapshot_id
        WHERE p.reddit_id = ?
          AND c.body NOT IN ('[deleted]', '[removed]')
        ORDER BY c.score DESC, LENGTH(c.body) ASC
        LIMIT ?
        """,
        (post_reddit_id, limit),
    ).fetchall()
    return [f"[score={row['score']}] {row['body'][:180]}" for row in rows]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Dry-run comment generation against corpus posts (no Reddit posting)."
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
        help="SQLite corpus database path",
    )
    parser.add_argument(
        "--culture",
        default=CULTURE_FEATURES_TEMPLATE,
        help="Culture features JSON path",
    )
    parser.add_argument(
        "--chroma-db",
        default="chroma_db",
        help="ChromaDB path",
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "gemini"],
        default=os.getenv("LLM_PROVIDER", "ollama"),
        help="LLM provider backend",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name for the selected provider",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=2,
        help="Number of corpus posts to generate against",
    )
    return parser.parse_args()


def build_llm_config(args) -> LLMConfig:
    config = LLMConfig.from_env(args.provider)
    if args.model:
        config.model = args.model
    if args.provider == "ollama":
        config.think = False
    return config


def main():
    args = parse_args()
    subreddit = resolve_subreddit(args.subreddit)
    culture_path = args.culture.format(subreddit=subreddit)
    features = load_culture_features(culture_path)
    llm_config = build_llm_config(args)
    llm = LLMWrapper(llm_config)
    generator = CommentGenerator(features, llm, chroma_db_path=args.chroma_db)

    conn = sqlite3.connect(args.db)
    posts = sample_posts(conn, subreddit, args.limit)
    if not posts:
        raise SystemExit(f"No posts found for r/{subreddit} in {args.db}")

    print(f"subreddit=r/{subreddit}")
    print(f"provider={llm_config.provider}")
    print(f"model={llm_config.model}")
    print(f"posts={len(posts)}")
    print()

    for index, post in enumerate(posts, start=1):
        print("=" * 72)
        print(f"POST {index}/{len(posts)} id={post['reddit_id']} score={post['score']}")
        print(f"title={post['title'][:120]}")
        if post["selftext"]:
            print(f"body={post['selftext'][:200]}")

        result = generator.generate_for_post(post["title"], post["selftext"] or "")
        evaluation = result.evaluation

        print("\nGENERATED")
        print(result.comment)
        print(
            f"\nEVAL length={evaluation['length']} band={evaluation['length_band']} "
            f"acceptable={evaluation['acceptable']} "
            f"checks={evaluation['checks_passed']}/{evaluation['checks_total']}"
        )

        real_comments = sample_real_comments(conn, post["reddit_id"])
        print("\nREAL COMMENTS FROM CORPUS")
        if real_comments:
            for comment in real_comments:
                print(f"- {comment}")
        else:
            print("(none)")
        print()

    conn.close()


if __name__ == "__main__":
    main()
