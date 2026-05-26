import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO)


DEFAULT_LISTINGS = ["new", "hot", "rising", "top:day"]
DEFAULT_COMMENT_LISTINGS = {"hot", "rising", "top:day"}


def setup_reddit_client():
    """Initialize Reddit client with credentials from environment variables."""
    try:
        import praw

        reddit_client = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT"),
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD")
        )
        logging.info("Reddit client initialized successfully")
        return reddit_client
    except Exception as e:
        logging.error(f"Error initializing Reddit client: {e}")
        sys.exit(1)


def snapshot_key(*parts):
    """Create a deterministic key for a raw snapshot row."""
    value = "|".join(str(part) for part in parts)
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def parse_listing_spec(spec):
    """Parse listing specs like 'hot' or 'top:week'."""
    if ":" not in spec:
        return spec, None

    listing, time_filter = spec.split(":", 1)
    return listing, time_filter or None


def normalize_listing_spec(listing, time_filter=None):
    """Return the canonical source listing label stored in snapshots."""
    if time_filter:
        return f"{listing}:{time_filter}"
    return listing


def parse_reddit_fullname(fullname):
    """
    Split a Reddit fullname like t1_abc123 or t3_def456 into kind and id.

    PRAW comment parent IDs are fullnames, where t1 means comment and t3 means
    submission. Keeping both pieces makes future thread reconstruction explicit.
    """
    if not fullname or "_" not in fullname:
        return None, fullname

    kind, reddit_id = fullname.split("_", 1)
    return kind, reddit_id


def ensure_column(conn, table_name, column_name, column_definition):
    """Add a column to an existing SQLite table if it is missing."""
    columns = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN "
            f"{column_name} {column_definition}"
        )


def setup_sqlite_db(db_path):
    """Create raw corpus tables if they do not already exist."""
    path = Path(db_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_post_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_key TEXT NOT NULL UNIQUE,
            reddit_id TEXT NOT NULL,
            subreddit TEXT NOT NULL,
            title TEXT,
            selftext TEXT,
            author TEXT,
            created_utc REAL,
            permalink TEXT,
            url TEXT,
            score INTEGER,
            num_comments INTEGER,
            upvote_ratio REAL,
            scraped_at TEXT NOT NULL,
            source_listings_json TEXT NOT NULL,
            raw_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_comment_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_key TEXT NOT NULL UNIQUE,
            post_snapshot_id INTEGER NOT NULL,
            reddit_id TEXT NOT NULL,
            post_reddit_id TEXT NOT NULL,
            parent_fullname TEXT,
            parent_kind TEXT,
            parent_id TEXT,
            author TEXT,
            body TEXT,
            created_utc REAL,
            score INTEGER,
            permalink TEXT,
            depth INTEGER,
            scraped_at TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            FOREIGN KEY(post_snapshot_id) REFERENCES raw_post_snapshots(id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_posts_reddit_id
        ON raw_post_snapshots(reddit_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_posts_scraped_at
        ON raw_post_snapshots(scraped_at)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_comments_post_snapshot_id
        ON raw_comment_snapshots(post_snapshot_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_comments_reddit_id
        ON raw_comment_snapshots(reddit_id)
    """)
    ensure_column(conn, "raw_comment_snapshots", "parent_fullname", "TEXT")
    ensure_column(conn, "raw_comment_snapshots", "parent_kind", "TEXT")
    ensure_column(conn, "raw_comment_snapshots", "parent_id", "TEXT")
    conn.commit()
    return conn


def iter_listing(subreddit, listing, time_filter, limit):
    """Yield submissions for a configured subreddit listing."""
    if listing == "new":
        return subreddit.new(limit=limit)
    if listing == "hot":
        return subreddit.hot(limit=limit)
    if listing == "rising":
        return subreddit.rising(limit=limit)
    if listing == "top":
        return subreddit.top(time_filter=time_filter or "day", limit=limit)

    raise ValueError(f"Unsupported listing: {listing}")


def submission_raw_json(submission):
    """Capture source fields from PRAW without storing the whole object."""
    return {
        "id": submission.id,
        "name": getattr(submission, "name", None),
        "subreddit": submission.subreddit.display_name,
        "title": submission.title,
        "selftext": submission.selftext,
        "author": str(submission.author) if submission.author else None,
        "created_utc": submission.created_utc,
        "permalink": submission.permalink,
        "url": submission.url,
        "score": submission.score,
        "num_comments": submission.num_comments,
        "upvote_ratio": getattr(submission, "upvote_ratio", None),
        "link_flair_text": getattr(submission, "link_flair_text", None),
        "is_self": getattr(submission, "is_self", None),
        "over_18": getattr(submission, "over_18", None),
        "spoiler": getattr(submission, "spoiler", None),
        "stickied": getattr(submission, "stickied", None)
    }


def comment_raw_json(comment, post_reddit_id):
    """Capture source fields from a PRAW comment."""
    return {
        "id": comment.id,
        "name": getattr(comment, "name", None),
        "post_reddit_id": post_reddit_id,
        "parent_id": comment.parent_id,
        "author": str(comment.author) if comment.author else None,
        "body": comment.body,
        "created_utc": comment.created_utc,
        "score": comment.score,
        "permalink": comment.permalink,
        "depth": getattr(comment, "depth", None),
        "is_submitter": getattr(comment, "is_submitter", None),
        "distinguished": getattr(comment, "distinguished", None),
        "stickied": getattr(comment, "stickied", None)
    }


def scrape_post_snapshots(reddit_client, subreddit_name, listing_specs, limit):
    """
    Scrape configured post listings and aggregate duplicate posts seen in the
    same scrape window into one raw snapshot with multiple source listings.
    """
    subreddit = reddit_client.subreddit(subreddit_name)
    posts_by_id = {}
    completed = True

    for spec in listing_specs:
        listing, time_filter = parse_listing_spec(spec)
        source_label = normalize_listing_spec(listing, time_filter)
        logging.info(f"Scraping r/{subreddit_name} {source_label}...")

        try:
            for rank, submission in enumerate(
                iter_listing(subreddit, listing, time_filter, limit),
                start=1
            ):
                if submission.id not in posts_by_id:
                    posts_by_id[submission.id] = {
                        "submission": submission,
                        "source_listings": []
                    }

                posts_by_id[submission.id]["source_listings"].append({
                    "listing": listing,
                    "time_filter": time_filter,
                    "rank": rank
                })
        except Exception as e:
            completed = False
            logging.error(
                f"Stopping post listing scrape after error in "
                f"{source_label}: {e}"
            )
            break

    return list(posts_by_id.values()), completed


def upsert_post_snapshot(conn, post_record, scraped_at):
    """Store a raw post snapshot and return its internal row id."""
    submission = post_record["submission"]
    source_listings = post_record["source_listings"]
    key = snapshot_key(submission.id, scraped_at)
    raw = submission_raw_json(submission)

    conn.execute(
        """
        INSERT INTO raw_post_snapshots (
            snapshot_key,
            reddit_id,
            subreddit,
            title,
            selftext,
            author,
            created_utc,
            permalink,
            url,
            score,
            num_comments,
            upvote_ratio,
            scraped_at,
            source_listings_json,
            raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_key) DO UPDATE SET
            title = excluded.title,
            selftext = excluded.selftext,
            author = excluded.author,
            score = excluded.score,
            num_comments = excluded.num_comments,
            upvote_ratio = excluded.upvote_ratio,
            source_listings_json = excluded.source_listings_json,
            raw_json = excluded.raw_json
        """,
        (
            key,
            submission.id,
            submission.subreddit.display_name,
            submission.title,
            submission.selftext,
            str(submission.author) if submission.author else None,
            submission.created_utc,
            submission.permalink,
            submission.url,
            submission.score,
            submission.num_comments,
            getattr(submission, "upvote_ratio", None),
            scraped_at,
            json.dumps(source_listings, sort_keys=True),
            json.dumps(raw, sort_keys=True)
        )
    )
    row = conn.execute(
        "SELECT id FROM raw_post_snapshots WHERE snapshot_key = ?",
        (key,)
    ).fetchone()
    return row[0], key


def should_scrape_comments(post_record, comment_listing_specs):
    source_labels = {
        normalize_listing_spec(item["listing"], item["time_filter"])
        for item in post_record["source_listings"]
    }
    return bool(source_labels & comment_listing_specs)


def upsert_comment_snapshot(conn, comment, post_snapshot_id, post_reddit_id, scraped_at):
    """Store one raw comment snapshot linked to its post snapshot."""
    key = snapshot_key(comment.id, post_reddit_id, scraped_at)
    raw = comment_raw_json(comment, post_reddit_id)
    parent_kind, parent_id = parse_reddit_fullname(comment.parent_id)

    conn.execute(
        """
        INSERT INTO raw_comment_snapshots (
            snapshot_key,
            post_snapshot_id,
            reddit_id,
            post_reddit_id,
            parent_fullname,
            parent_kind,
            parent_id,
            author,
            body,
            created_utc,
            score,
            permalink,
            depth,
            scraped_at,
            raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_key) DO UPDATE SET
            body = excluded.body,
            score = excluded.score,
            raw_json = excluded.raw_json
        """,
        (
            key,
            post_snapshot_id,
            comment.id,
            post_reddit_id,
            comment.parent_id,
            parent_kind,
            parent_id,
            str(comment.author) if comment.author else None,
            comment.body,
            comment.created_utc,
            comment.score,
            comment.permalink,
            getattr(comment, "depth", None),
            scraped_at,
            json.dumps(raw, sort_keys=True)
        )
    )


def scrape_comments_for_post(conn, submission, post_snapshot_id, scraped_at, replace_more_limit):
    """Fetch and store comments for one post snapshot."""
    submission.comments.replace_more(limit=replace_more_limit)
    comments = submission.comments.list()

    for comment in comments:
        if not getattr(comment, "body", None):
            continue
        upsert_comment_snapshot(
            conn,
            comment,
            post_snapshot_id,
            submission.id,
            scraped_at
        )

    return len(comments)


def store_corpus_snapshot(
    conn,
    reddit_client,
    subreddit_name,
    listing_specs,
    post_limit,
    comment_listing_specs,
    max_comment_posts,
    replace_more_limit
):
    """Scrape post snapshots and selected comment trees into SQLite."""
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    post_records, post_scrape_completed = scrape_post_snapshots(
        reddit_client,
        subreddit_name,
        listing_specs,
        post_limit
    )

    post_rows = []
    for record in post_records:
        post_snapshot_id, _ = upsert_post_snapshot(conn, record, scraped_at)
        post_rows.append((record, post_snapshot_id))
    conn.commit()

    logging.info(
        f"Stored {len(post_rows)} post snapshots for {scraped_at}"
    )

    if not post_scrape_completed:
        logging.warning(
            "Post listing scrape ended early; saved valid post snapshots and "
            "skipped comment scraping for this run"
        )
        return

    comment_count = 0
    comment_posts = [
        (record, post_snapshot_id)
        for record, post_snapshot_id in post_rows
        if should_scrape_comments(record, comment_listing_specs)
    ][:max_comment_posts]

    for index, (record, post_snapshot_id) in enumerate(comment_posts, start=1):
        submission = record["submission"]
        logging.info(
            f"Scraping comments for post {index}/{len(comment_posts)}: "
            f"{submission.id}"
        )
        try:
            post_comment_count = scrape_comments_for_post(
                conn,
                submission,
                post_snapshot_id,
                scraped_at,
                replace_more_limit
            )
            conn.commit()
            comment_count += post_comment_count
        except Exception as e:
            conn.rollback()
            logging.error(
                f"Stopping comment scrape after error on post "
                f"{submission.id}: {e}"
            )
            break

    logging.info(
        f"Stored {len(post_rows)} post snapshots and "
        f"{comment_count} comment snapshots for {scraped_at}"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape raw Reddit corpus snapshots into SQLite."
    )
    parser.add_argument("subreddit_name", help="Subreddit name without r/")
    parser.add_argument(
        "--db",
        default="data/corpus.sqlite",
        help="SQLite database path"
    )
    parser.add_argument(
        "--listings",
        default=",".join(DEFAULT_LISTINGS),
        help="Comma-separated listings, e.g. new,hot,rising,top:day"
    )
    parser.add_argument(
        "--post-limit",
        type=int,
        default=100,
        help="Post limit per listing"
    )
    parser.add_argument(
        "--comment-listings",
        default=",".join(sorted(DEFAULT_COMMENT_LISTINGS)),
        help=(
            "Comma-separated source listings whose posts should have comment "
            "trees scraped; matches --listings labels exactly, e.g. "
            "hot,rising,top:day"
        )
    )
    parser.add_argument(
        "--max-comment-posts",
        type=int,
        default=50,
        help="Maximum number of posts to fetch comments for"
    )
    parser.add_argument(
        "--replace-more-limit",
        type=int,
        default=16,
        help="PRAW replace_more limit for each comment tree"
    )
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_args()
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        logging.warning("python-dotenv is not installed; skipping .env loading")

    reddit_client = setup_reddit_client()
    conn = setup_sqlite_db(args.db)
    listing_specs = [
        item.strip()
        for item in args.listings.split(",")
        if item.strip()
    ]
    comment_listing_specs = {
        item.strip()
        for item in args.comment_listings.split(",")
        if item.strip()
    }

    store_corpus_snapshot(
        conn,
        reddit_client,
        args.subreddit_name,
        listing_specs,
        args.post_limit,
        comment_listing_specs,
        args.max_comment_posts,
        args.replace_more_limit
    )

    logging.info("Scraping completed successfully!")


if __name__ == "__main__":
    main()
