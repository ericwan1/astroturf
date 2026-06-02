"""Extract subreddit culture features from the raw SQLite corpus."""

from __future__ import annotations

import json
import math
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DELETED_BODIES = {"[deleted]", "[removed]"}

STOPWORDS = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "but",
    "by", "can", "could", "did", "do", "does", "doing", "don", "down", "for",
    "from", "get", "go", "going", "got", "had", "has", "have", "he", "her",
    "here", "him", "his", "how", "i", "if", "in", "into", "is", "it", "its",
    "just", "like", "ll", "me", "more", "most", "my", "no", "not", "now", "of",
    "on", "one", "or", "our", "out", "re", "s", "she", "so", "some", "t", "than",
    "that", "the", "their", "them", "then", "there", "these", "they", "this",
    "to", "too", "up", "ve", "was", "we", "were", "what", "when", "where",
    "which", "who", "why", "will", "with", "would", "you", "your",
}

TOKEN_RE = re.compile(r"[a-z0-9']+")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
REDDIT_BOILERPLATE_RE = re.compile(
    r"\[(?:removed|deleted)\]|"
    r"(?:comment|post)\s+(?:removed|deleted)(?:\s+by\s+reddit)?",
    re.I,
)

NOISY_LANGUAGE_TERMS = {
    "reddit", "removed", "deleted", "http", "https", "www", "com", "org",
}

NOISY_PHRASES = {
    "removed reddit",
    "post history",
    "hidden post",
    "hidden post history",
    "comment removed",
    "post removed",
}


def clean_text_for_language(text: str) -> str:
    text = URL_RE.sub(" ", text)
    text = REDDIT_BOILERPLATE_RE.sub(" ", text)
    return " ".join(text.split())


def is_noisy_language_item(tokens: tuple[str, ...] | list[str]) -> bool:
    phrase = " ".join(tokens)
    if phrase in NOISY_PHRASES:
        return True
    if any(token in NOISY_LANGUAGE_TERMS for token in tokens):
        return True
    return False


POSTING_SUFFIX_RE = re.compile(r"\b([a-z0-9'-]{3,})(posting|maxxing|maxxed|maxx)\b", re.I)
QUOTED_RE = re.compile(
    r'"([^"]{2,80})"|\'([^\']{2,80})\'|\u201c([^\u201d]{2,80})\u201d'
)
CAPS_PHRASE_RE = re.compile(r"\b[A-Z]{2,}(?:[-'][A-Z0-9]+)*\b")
TITLE_TEMPLATE_PATTERNS = [
    ("question", re.compile(r"\?\s*$")),
    ("lowercase", re.compile(r"^[a-z0-9].*[a-z0-9]$")),
    ("single_word", re.compile(r"^\S+$")),
    ("starts_with_i", re.compile(r"^i\b", re.I)),
    ("ellipsis", re.compile(r"\.{3}|…")),
    ("meta_posting", re.compile(r"\b\w+(posting|maxxing|maxx)\b", re.I)),
]


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[lower])
    weight = rank - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def distribution_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "max": None,
            "mean": None,
        }
    return {
        "count": len(values),
        "min": float(min(values)),
        "p25": percentile(values, 0.25),
        "median": float(statistics.median(values)),
        "p75": percentile(values, 0.75),
        "max": float(max(values)),
        "mean": float(statistics.fmean(values)),
    }


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def content_tokens(text: str) -> list[str]:
    return [token for token in tokenize(text) if token not in STOPWORDS and len(token) > 1]


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if len(tokens) < n:
        return []
    return [tuple(tokens[index:index + n]) for index in range(len(tokens) - n + 1)]


def top_ngrams(texts: list[str], n: int, top_k: int = 25, min_count: int = 2) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, ...]] = Counter()
    for text in texts:
        grams = ngrams(content_tokens(clean_text_for_language(text)), n)
        counter.update({gram for gram in grams if not is_noisy_language_item(gram)})
    ranked = counter.most_common(top_k * 5)
    results = []
    for gram, count in ranked:
        if count < min_count:
            continue
        results.append({"phrase": " ".join(gram), "count": count})
        if len(results) >= top_k:
            break
    return results


def top_terms(texts: list[str], top_k: int = 40, min_count: int = 3) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for text in texts:
        tokens = {
            token
            for token in content_tokens(clean_text_for_language(text))
            if token not in NOISY_LANGUAGE_TERMS
        }
        counter.update(tokens)
    return [
        {"term": term, "doc_count": count}
        for term, count in counter.most_common(top_k * 3)
        if count >= min_count
    ][:top_k]


def extract_posting_patterns(texts: list[str], top_k: int = 20) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for text in texts:
        for match in POSTING_SUFFIX_RE.finditer(text.lower()):
            counter[match.group(0)] += 1
    return [{"pattern": pattern, "count": count} for pattern, count in counter.most_common(top_k)]


def extract_quoted_phrases(texts: list[str], top_k: int = 20) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for text in texts:
        for match in QUOTED_RE.finditer(text):
            phrase = next(group for group in match.groups() if group)
            normalized = " ".join(phrase.split())
            if len(normalized) >= 3:
                counter[normalized.lower()] += 1
    return [{"phrase": phrase, "count": count} for phrase, count in counter.most_common(top_k)]


def extract_caps_references(texts: list[str], top_k: int = 20) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for text in texts:
        for match in CAPS_PHRASE_RE.finditer(text):
            token = match.group(0)
            if token in {"I", "A", "TV", "AI", "US", "UK", "IDF", "NEET", "AGP", "RS"}:
                continue
            counter[token.lower()] += 1
    return [{"reference": ref, "count": count} for ref, count in counter.most_common(top_k)]


def classify_title(title: str) -> list[str]:
    labels = []
    for label, pattern in TITLE_TEMPLATE_PATTERNS:
        if pattern.search(title):
            labels.append(label)
    return labels


def latest_post_rows(conn: sqlite3.Connection, subreddit: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT p.*
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
        ORDER BY p.score DESC, p.created_utc DESC
        """,
        (subreddit, subreddit),
    ).fetchall()


def latest_comment_rows(conn: sqlite3.Connection, subreddit: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT c.*
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


def extract_trajectories(conn: sqlite3.Connection, subreddit: str, top_k: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT reddit_id, title, score, source_listings_json, scraped_at
        FROM raw_post_snapshots
        WHERE subreddit = ?
        ORDER BY scraped_at DESC, score DESC
        """,
        (subreddit,),
    ).fetchall()

    by_post: dict[str, dict[str, Any]] = {}
    for reddit_id, title, score, source_listings_json, scraped_at in rows:
        listings = {
            normalize_listing_label(item["listing"], item.get("time_filter"))
            for item in json.loads(source_listings_json)
        }
        record = by_post.setdefault(
            reddit_id,
            {
                "reddit_id": reddit_id,
                "title": title,
                "max_score": score,
                "listings_seen": set(),
                "runs_seen": set(),
            },
        )
        record["listings_seen"].update(listings)
        record["runs_seen"].add(scraped_at)
        record["max_score"] = max(record["max_score"], score)

    trajectories = []
    for record in by_post.values():
        listings = sorted(record["listings_seen"])
        if len(listings) < 2 and len(record["runs_seen"]) < 2:
            continue
        trajectories.append(
            {
                "reddit_id": record["reddit_id"],
                "title": record["title"],
                "max_score": record["max_score"],
                "listings_seen": listings,
                "run_count": len(record["runs_seen"]),
                "has_new_to_hot_or_top": (
                    "new" in record["listings_seen"]
                    and bool(record["listings_seen"] & {"hot", "rising", "top:day"})
                ),
            }
        )

    trajectories.sort(
        key=lambda item: (item["has_new_to_hot_or_top"], len(item["listings_seen"]), item["max_score"]),
        reverse=True,
    )
    return trajectories[:top_k]


def normalize_listing_label(listing: str, time_filter: str | None) -> str:
    if time_filter:
        return f"{listing}:{time_filter}"
    return listing


def comment_style_stats(comments: list[sqlite3.Row]) -> dict[str, Any]:
    lengths = [len(row["body"]) for row in comments]
    scores = [float(row["score"]) for row in comments]
    depths = [float(row["depth"]) for row in comments if row["depth"] is not None]

    lowercase_starts = sum(1 for row in comments if row["body"][:1].islower())
    one_liners = sum(1 for row in comments if len(row["body"]) <= 80)
    ends_with_punct = sum(1 for row in comments if row["body"].rstrip().endswith((".", "!", "?", "...")))

    by_depth: dict[int, list[int]] = defaultdict(list)
    for row in comments:
        depth = int(row["depth"] or 0)
        by_depth[depth].append(len(row["body"]))

    return {
        "length_chars": distribution_summary([float(value) for value in lengths]),
        "score": distribution_summary(scores),
        "depth": distribution_summary(depths),
        "lowercase_start_ratio": round(lowercase_starts / len(comments), 3) if comments else 0.0,
        "one_liner_ratio": round(one_liners / len(comments), 3) if comments else 0.0,
        "ends_with_punctuation_ratio": round(ends_with_punct / len(comments), 3) if comments else 0.0,
        "length_by_depth": {
            str(depth): distribution_summary([float(value) for value in values])
            for depth, values in sorted(by_depth.items())
        },
    }


def title_style_stats(posts: list[sqlite3.Row]) -> dict[str, Any]:
    titles = [row["title"] or "" for row in posts if row["title"]]
    lengths = [len(title) for title in titles]
    label_counts: Counter[str] = Counter()
    for title in titles:
        label_counts.update(classify_title(title))

    return {
        "length_chars": distribution_summary([float(value) for value in lengths]),
        "label_counts": dict(label_counts.most_common()),
        "sample_titles_by_label": sample_titles_by_label(posts),
    }


def sample_titles_by_label(posts: list[sqlite3.Row], per_label: int = 5) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = defaultdict(list)
    for row in posts:
        title = row["title"] or ""
        for label in classify_title(title):
            if len(buckets[label]) < per_label:
                buckets[label].append(title)
    return dict(buckets)


def comment_to_exemplar(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "reddit_id": row["reddit_id"],
        "post_reddit_id": row["post_reddit_id"],
        "score": row["score"],
        "depth": row["depth"],
        "body": row["body"],
    }


def select_exemplars(
    comments: list[sqlite3.Row],
    *,
    top_k: int = 10,
    high_min_score: int = 50,
    max_depth: int = 2,
) -> dict[str, list[dict[str, Any]]]:
    """
    Return two exemplar sets:
    - high: top-scored comments for peak subreddit humor
    - median: typical comments near the corpus median length/score band
    """
    if not comments:
        return {"high": [], "median": []}

    scores = [float(row["score"]) for row in comments]
    lengths = [float(len(row["body"])) for row in comments]
    score_p25 = percentile(scores, 0.25) or 1.0
    score_p75 = percentile(scores, 0.75) or 20.0
    score_median = percentile(scores, 0.5) or 5.0
    length_p25 = percentile(lengths, 0.25) or 40.0
    length_p75 = percentile(lengths, 0.75) or 185.0
    length_median = percentile(lengths, 0.5) or 84.0

    high_rows = [row for row in comments if row["score"] >= high_min_score]
    high_rows.sort(key=lambda row: row["score"], reverse=True)

    median_candidates = [
        row for row in comments
        if score_p25 <= row["score"] <= score_p75
        and (row["depth"] or 0) <= max_depth
        and length_p25 <= len(row["body"]) <= length_p75
    ]
    median_candidates.sort(
        key=lambda row: (
            abs(len(row["body"]) - length_median),
            abs(row["score"] - score_median),
        )
    )

    seen_posts: set[str] = set()
    median_rows: list[sqlite3.Row] = []
    for row in median_candidates:
        if row["post_reddit_id"] in seen_posts:
            continue
        seen_posts.add(row["post_reddit_id"])
        median_rows.append(row)
        if len(median_rows) >= top_k:
            break

    return {
        "high": [comment_to_exemplar(row) for row in high_rows[:top_k]],
        "median": [comment_to_exemplar(row) for row in median_rows],
    }


def median_poster_profile(comments: list[sqlite3.Row]) -> dict[str, Any]:
    """Summarize the typical commenter the agent should emulate."""
    if not comments:
        return {}

    target_length = percentile([float(len(row["body"])) for row in comments], 0.5) or 80.0
    target_depth = percentile([float(row["depth"] or 0) for row in comments], 0.5) or 1.0
    representative = min(
        comments,
        key=lambda row: (
            abs(len(row["body"]) - target_length),
            abs((row["depth"] or 0) - target_depth),
            -row["score"],
        ),
    )

    return {
        "target_length_chars": round(target_length),
        "target_depth": round(target_depth),
        "target_score_band": {
            "p25": percentile([float(row["score"]) for row in comments], 0.25),
            "median": percentile([float(row["score"]) for row in comments], 0.5),
            "p75": percentile([float(row["score"]) for row in comments], 0.75),
        },
        "style_hints": {
            "prefer_lowercase_start": True,
            "often_short": target_length <= 100,
            "typical_top_level_or_first_reply": target_depth <= 1,
        },
        "representative_comment": {
            "reddit_id": representative["reddit_id"],
            "score": representative["score"],
            "depth": representative["depth"],
            "body": representative["body"],
        },
    }


def mine_culture(
    db_path: str | Path,
    subreddit: str,
    *,
    top_k: int = 25,
    min_ngram_count: int = 2,
) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Database does not exist: {path}")

    conn = sqlite3.connect(path)
    posts = latest_post_rows(conn, subreddit)
    comments = latest_comment_rows(conn, subreddit)

    post_titles = [row["title"] or "" for row in posts if row["title"]]
    comment_bodies = [row["body"] for row in comments]
    all_text = post_titles + comment_bodies

    scrape_runs = conn.execute(
        """
        SELECT COUNT(DISTINCT scraped_at)
        FROM raw_post_snapshots
        WHERE subreddit = ?
        """,
        (subreddit,),
    ).fetchone()[0]

    features = {
        "subreddit": subreddit,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "db_path": str(path),
            "scrape_runs": scrape_runs,
            "unique_posts": len(posts),
            "unique_comments": len(comments),
        },
        "median_poster_profile": median_poster_profile(comments),
        "comment_style": comment_style_stats(comments),
        "title_style": title_style_stats(posts),
        "language": {
            "top_comment_terms": top_terms(comment_bodies, top_k=top_k, min_count=min_ngram_count),
            "top_title_terms": top_terms(post_titles, top_k=top_k, min_count=min_ngram_count),
            "comment_bigrams": top_ngrams(comment_bodies, 2, top_k=top_k, min_count=min_ngram_count),
            "comment_trigrams": top_ngrams(comment_bodies, 3, top_k=top_k, min_count=min_ngram_count),
            "title_bigrams": top_ngrams(post_titles, 2, top_k=top_k, min_count=min_ngram_count),
            "posting_patterns": extract_posting_patterns(all_text, top_k=top_k),
            "quoted_phrases": extract_quoted_phrases(all_text, top_k=top_k),
            "caps_references": extract_caps_references(all_text, top_k=top_k),
        },
        "comment_exemplars": select_exemplars(comments, top_k=min(10, top_k)),
        "post_trajectories": extract_trajectories(conn, subreddit, top_k=top_k),
        "top_posts": [
            {
                "reddit_id": row["reddit_id"],
                "score": row["score"],
                "num_comments": row["num_comments"],
                "title": row["title"],
            }
            for row in posts[:top_k]
        ],
    }
    conn.close()
    return features


def format_summary(features: dict[str, Any]) -> str:
    lines = [
        f"subreddit=r/{features['subreddit']}",
        f"generated_at={features['generated_at']}",
        f"unique_posts={features['source']['unique_posts']}",
        f"unique_comments={features['source']['unique_comments']}",
        "",
        "median_poster_profile",
        "-------------------",
    ]

    profile = features.get("median_poster_profile") or {}
    if profile:
        lines.extend(
            [
                f"target_length_chars={profile['target_length_chars']}",
                f"target_depth={profile['target_depth']}",
                f"score_band={profile['target_score_band']}",
                f"representative_comment={profile['representative_comment']['body'][:120]}",
            ]
        )

    lines.extend(["", "comment_style", "-------------"])
    comment_style = features["comment_style"]
    lines.append(f"length_median={comment_style['length_chars']['median']}")
    lines.append(f"score_median={comment_style['score']['median']}")
    lines.append(f"depth_median={comment_style['depth']['median']}")
    lines.append(f"one_liner_ratio={comment_style['one_liner_ratio']}")

    lines.extend(["", "top_comment_terms", "-----------------"])
    for item in features["language"]["top_comment_terms"][:10]:
        lines.append(f"{item['term']} ({item['doc_count']})")

    lines.extend(["", "comment_bigrams", "---------------"])
    for item in features["language"]["comment_bigrams"][:10]:
        lines.append(f"{item['phrase']} ({item['count']})")

    lines.extend(["", "posting_patterns", "----------------"])
    posting_patterns = features["language"]["posting_patterns"]
    if posting_patterns:
        for item in posting_patterns[:10]:
            lines.append(f"{item['pattern']} ({item['count']})")
    else:
        lines.append("(none)")

    lines.extend(["", "title_style_labels", "------------------"])
    for label, count in features["title_style"]["label_counts"].items():
        lines.append(f"{label}={count}")

    lines.extend(["", "median_exemplars", "----------------"])
    median_exemplars = features["comment_exemplars"].get("median", [])
    if median_exemplars:
        for item in median_exemplars[:5]:
            lines.append(
                f"score={item['score']} depth={item['depth']} "
                f"body={item['body'][:100]}"
            )
    else:
        lines.append("(none)")

    lines.extend(["", "post_trajectories", "-----------------"])
    trajectories = features["post_trajectories"]
    if trajectories:
        for item in trajectories[:5]:
            lines.append(
                f"{item['reddit_id']} listings={','.join(item['listings_seen'])} "
                f"score={item['max_score']} title={item['title'][:70]}"
            )
    else:
        lines.append("(none yet)")

    return "\n".join(lines)
