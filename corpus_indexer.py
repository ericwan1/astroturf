"""Build and maintain ChromaDB indexes from the raw SQLite corpus."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb

from culture_miner import latest_post_rows


DELETED_BODIES = {"[deleted]", "[removed]"}


@dataclass
class IndexRecord:
    chroma_id: str
    document: str
    metadata: dict[str, str | int | float | bool]


@dataclass
class IndexStats:
    subreddit: str
    collection_name: str
    posts_indexed: int
    comments_indexed: int
    total_indexed: int
    collection_count: int
    rebuild: bool


def collection_name_for_subreddit(subreddit: str) -> str:
    return f"{subreddit}_comments_and_posts"


def latest_comment_rows_with_context(
    conn: sqlite3.Connection,
    subreddit: str,
) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT
            c.reddit_id,
            c.post_reddit_id,
            c.body,
            c.score,
            c.depth,
            c.created_utc,
            c.scraped_at,
            p.title AS post_title,
            p.selftext AS post_selftext
        FROM raw_comment_snapshots c
        INNER JOIN raw_post_snapshots p ON p.id = c.post_snapshot_id
        INNER JOIN (
            SELECT reddit_id, MAX(scraped_at) AS latest_scraped_at
            FROM raw_comment_snapshots
            GROUP BY reddit_id
        ) latest
            ON c.reddit_id = latest.reddit_id
           AND c.scraped_at = latest.latest_scraped_at
        WHERE p.subreddit = ?
          AND c.body NOT IN ('[deleted]', '[removed]')
        ORDER BY c.score DESC, c.created_utc DESC
        """,
        (subreddit,),
    ).fetchall()


def build_post_document(title: str | None, selftext: str | None) -> str:
    title = (title or "").strip()
    selftext = (selftext or "").strip()
    if selftext:
        return f"{title}\n\n{selftext}".strip()
    return title


def build_comment_document(post_title: str | None, body: str) -> str:
    post_title = (post_title or "").strip()
    body = body.strip()
    if post_title:
        return f"Post: {post_title}\n\n{body}"
    return body


def post_record(row: sqlite3.Row) -> IndexRecord | None:
    document = build_post_document(row["title"], row["selftext"])
    if not document:
        return None

    return IndexRecord(
        chroma_id=f"post:{row['reddit_id']}",
        document=document,
        metadata={
            "type": "post",
            "subreddit": row["subreddit"],
            "reddit_id": row["reddit_id"],
            "post_reddit_id": row["reddit_id"],
            "title": row["title"] or "",
            "score": int(row["score"] or 0),
            "depth": -1,
            "num_comments": int(row["num_comments"] or 0),
            "created_utc": float(row["created_utc"] or 0),
            "scraped_at": row["scraped_at"],
        },
    )


def comment_record(row: sqlite3.Row) -> IndexRecord | None:
    body = (row["body"] or "").strip()
    if not body or body in DELETED_BODIES:
        return None

    return IndexRecord(
        chroma_id=f"comment:{row['reddit_id']}",
        document=build_comment_document(row["post_title"], body),
        metadata={
            "type": "comment",
            "subreddit": "",
            "reddit_id": row["reddit_id"],
            "post_reddit_id": row["post_reddit_id"],
            "title": row["post_title"] or "",
            "score": int(row["score"] or 0),
            "depth": int(row["depth"] or 0),
            "num_comments": 0,
            "created_utc": float(row["created_utc"] or 0),
            "scraped_at": row["scraped_at"],
        },
    )


def collect_index_records(conn: sqlite3.Connection, subreddit: str) -> list[IndexRecord]:
    records: list[IndexRecord] = []

    for row in latest_post_rows(conn, subreddit):
        record = post_record(row)
        if record is not None:
            records.append(record)

    comment_rows = latest_comment_rows_with_context(conn, subreddit)
    for row in comment_rows:
        record = comment_record(row)
        if record is not None:
            record.metadata["subreddit"] = subreddit
            records.append(record)

    return records


def upsert_records(collection, records: list[IndexRecord], batch_size: int = 100) -> None:
    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        collection.upsert(
            ids=[record.chroma_id for record in batch],
            documents=[record.document for record in batch],
            metadatas=[record.metadata for record in batch],
        )


def get_or_reset_collection(
    client: chromadb.ClientAPI,
    subreddit: str,
    *,
    rebuild: bool,
):
    name = collection_name_for_subreddit(subreddit)
    if rebuild:
        try:
            client.delete_collection(name)
        except Exception:
            pass
    return client.get_or_create_collection(name=name)


def build_chroma_index(
    db_path: str | Path,
    subreddit: str,
    *,
    chroma_db_path: str | Path = "chroma_db",
    rebuild: bool = False,
    batch_size: int = 100,
) -> IndexStats:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Database does not exist: {path}")

    conn = sqlite3.connect(path)
    records = collect_index_records(conn, subreddit)
    conn.close()

    posts_indexed = sum(1 for record in records if record.metadata["type"] == "post")
    comments_indexed = sum(1 for record in records if record.metadata["type"] == "comment")

    client = chromadb.PersistentClient(path=str(chroma_db_path))
    collection = get_or_reset_collection(client, subreddit, rebuild=rebuild)
    upsert_records(collection, records, batch_size=batch_size)

    return IndexStats(
        subreddit=subreddit,
        collection_name=collection_name_for_subreddit(subreddit),
        posts_indexed=posts_indexed,
        comments_indexed=comments_indexed,
        total_indexed=len(records),
        collection_count=collection.count(),
        rebuild=rebuild,
    )


def format_index_summary(stats: IndexStats) -> str:
    mode = "rebuild" if stats.rebuild else "upsert"
    return "\n".join(
        [
            f"subreddit=r/{stats.subreddit}",
            f"collection={stats.collection_name}",
            f"mode={mode}",
            f"posts_indexed={stats.posts_indexed}",
            f"comments_indexed={stats.comments_indexed}",
            f"total_indexed={stats.total_indexed}",
            f"collection_count={stats.collection_count}",
        ]
    )
