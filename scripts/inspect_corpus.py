#!/usr/bin/env python
import argparse
import json
import sqlite3
from pathlib import Path


def scalar(conn, query, params=()):
    return conn.execute(query, params).fetchone()[0]


def print_rows(title, rows):
    print(f"\n{title}")
    print("-" * len(title))
    if not rows:
        print("(none)")
        return

    for row in rows:
        print(row)


def source_count(source_listings_json):
    return len(json.loads(source_listings_json))


def inspect_corpus(db_path, recent_runs):
    path = Path(db_path)
    if not path.exists():
        raise SystemExit(f"Database does not exist: {path}")

    conn = sqlite3.connect(path)
    conn.create_function("source_count", 1, source_count)

    post_count = scalar(conn, "SELECT COUNT(*) FROM raw_post_snapshots")
    comment_count = scalar(conn, "SELECT COUNT(*) FROM raw_comment_snapshots")
    run_count = scalar(
        conn,
        "SELECT COUNT(DISTINCT scraped_at) FROM raw_post_snapshots"
    )
    latest_scraped_at = scalar(
        conn,
        "SELECT COALESCE(MAX(scraped_at), '(none)') FROM raw_post_snapshots"
    )

    print(f"db_path={path}")
    print(f"post_snapshots={post_count}")
    print(f"comment_snapshots={comment_count}")
    print(f"post_snapshot_runs={run_count}")
    print(f"latest_scraped_at={latest_scraped_at}")

    if latest_scraped_at == "(none)":
        return

    latest_post_count = scalar(
        conn,
        "SELECT COUNT(*) FROM raw_post_snapshots WHERE scraped_at = ?",
        (latest_scraped_at,)
    )
    latest_comment_count = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM raw_comment_snapshots
        WHERE post_snapshot_id IN (
            SELECT id FROM raw_post_snapshots WHERE scraped_at = ?
        )
        """,
        (latest_scraped_at,)
    )
    latest_multi_source = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM raw_post_snapshots
        WHERE scraped_at = ? AND source_count(source_listings_json) > 1
        """,
        (latest_scraped_at,)
    )

    print(f"latest_post_snapshots={latest_post_count}")
    print(f"latest_comment_snapshots={latest_comment_count}")
    print(f"latest_multi_source_posts={latest_multi_source}")

    recent = conn.execute(
        """
        SELECT scraped_at, COUNT(*) AS post_count
        FROM raw_post_snapshots
        GROUP BY scraped_at
        ORDER BY scraped_at DESC
        LIMIT ?
        """,
        (recent_runs,)
    ).fetchall()
    print_rows("recent_post_snapshot_runs", recent)

    by_subreddit = conn.execute(
        """
        SELECT subreddit, COUNT(*) AS post_count
        FROM raw_post_snapshots
        GROUP BY subreddit
        ORDER BY post_count DESC
        """
    ).fetchall()
    print_rows("post_snapshots_by_subreddit", by_subreddit)

    top_latest_posts = conn.execute(
        """
        SELECT reddit_id, score, num_comments, title
        FROM raw_post_snapshots
        WHERE scraped_at = ?
        ORDER BY score DESC
        LIMIT 10
        """,
        (latest_scraped_at,)
    ).fetchall()
    print_rows("top_latest_posts_by_score", top_latest_posts)

    comment_counts = conn.execute(
        """
        SELECT p.reddit_id, COUNT(c.id) AS comment_snapshots, p.title
        FROM raw_post_snapshots p
        LEFT JOIN raw_comment_snapshots c ON c.post_snapshot_id = p.id
        WHERE p.scraped_at = ?
        GROUP BY p.id
        ORDER BY comment_snapshots DESC, p.score DESC
        LIMIT 10
        """,
        (latest_scraped_at,)
    ).fetchall()
    print_rows("latest_comment_snapshots_by_post", comment_counts)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Inspect raw Reddit corpus SQLite health."
    )
    parser.add_argument(
        "--db",
        default="data/corpus.sqlite",
        help="SQLite corpus database path"
    )
    parser.add_argument(
        "--recent-runs",
        type=int,
        default=10,
        help="Number of recent scraped_at groups to print"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    inspect_corpus(args.db, args.recent_runs)


if __name__ == "__main__":
    main()
