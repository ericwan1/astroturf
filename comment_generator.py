"""Build prompts and generate subreddit-native comments from culture + retrieval context."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from chroma_utils import ChromaQueryManager
from comment_evaluator import evaluate_comment
from llm import ChatMessage, LLMWrapper

_THINK_OPEN = "<" + "think>"
_THINK_CLOSE = "</" + "think>"
THINK_BLOCK_RE = re.compile(
    re.escape(_THINK_OPEN) + r".*?" + re.escape(_THINK_CLOSE),
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class GenerationResult:
    comment: str
    evaluation: dict[str, Any]
    retrieved_comments: list[dict[str, Any]]
    post_title: str
    post_body: str


def load_culture_features(path: str | Path) -> dict[str, Any]:
    features_path = Path(path)
    if not features_path.exists():
        raise FileNotFoundError(f"Culture features not found: {features_path}")
    return json.loads(features_path.read_text())


def _format_retrieved(results: list[dict[str, Any]], limit: int = 4) -> str:
    lines = []
    for index, item in enumerate(results[:limit], start=1):
        metadata = item.get("metadata") or {}
        body = item.get("document") or ""
        if body.startswith("Post:"):
            body = body.split("\n\n", 1)[-1]
        score = metadata.get("score", "?")
        lines.append(f"{index}. (score={score}) {body[:220]}")
    return "\n".join(lines) if lines else "(none)"


def build_system_prompt(culture_features: dict[str, Any]) -> str:
    profile = culture_features.get("median_poster_profile") or {}
    style = culture_features.get("comment_style") or {}
    posting_patterns = culture_features.get("language", {}).get("posting_patterns") or []
    exemplars = culture_features.get("comment_exemplars", {}).get("median") or []

    pattern_text = ", ".join(
        item["pattern"] for item in posting_patterns[:8]
    ) or "none noted"

    exemplar_lines = []
    for item in exemplars[:4]:
        exemplar_lines.append(f'- "{item["body"][:180]}"')

    return "\n".join(
        [
            f"You are emulating a typical r/{culture_features.get('subreddit', 'redscarepod')} commenter.",
            "Write one comment only. No preamble, no quotes around the comment, no explanation.",
            "",
            "Style constraints:",
            f"- Aim for about {profile.get('target_length_chars', 90)} characters.",
            f"- Typical score band: {profile.get('target_score_band', {})}. Do not try to be the funniest/top comment.",
            f"- Median depth: {profile.get('target_depth', 1)}. Sound like a normal participant, not a stand-up bit.",
            f"- One-liner ratio in corpus: {style.get('one_liner_ratio', 0.5):.2f}. Short and direct is fine.",
            f"- Known meta suffixes/patterns: {pattern_text}.",
            "",
            "Examples of median comments from this subreddit:",
            *exemplar_lines,
        ]
    )


def build_post_user_prompt(
    post_title: str,
    post_body: str,
    retrieved_comments: list[dict[str, Any]],
) -> str:
    body = (post_body or "").strip()
    post_section = f"Title: {post_title.strip()}"
    if body:
        post_section += f"\nBody: {body[:1200]}"

    return "\n".join(
        [
            "Write a single Reddit comment responding to this post.",
            "",
            post_section,
            "",
            "Similar comments from this subreddit for tone reference:",
            _format_retrieved(retrieved_comments),
        ]
    )


def build_reply_user_prompt(
    post_title: str,
    parent_comment: str,
    thread_context: list[str],
    retrieved_comments: list[dict[str, Any]],
) -> str:
    context_lines = []
    for index, comment in enumerate(thread_context[-4:], start=1):
        context_lines.append(f"{index}. {comment[:220]}")

    return "\n".join(
        [
            "Write a single Reddit reply to the parent comment below.",
            "",
            f"Post title: {post_title.strip()}",
            "",
            "Thread context:",
            *(context_lines or ["(none)"]),
            "",
            f"Parent comment: {parent_comment.strip()[:800]}",
            "",
            "Similar comments from this subreddit for tone reference:",
            _format_retrieved(retrieved_comments),
        ]
    )


class CommentGenerator:
    """Generate evaluated comments using culture features, Chroma retrieval, and a local LLM."""

    def __init__(
        self,
        culture_features: dict[str, Any],
        llm: LLMWrapper,
        chroma_db_path: str = "chroma_db",
    ):
        self.culture_features = culture_features
        self.llm = llm
        self.subreddit = culture_features.get("subreddit", "redscarepod")
        self.chroma = ChromaQueryManager(chroma_db_path=chroma_db_path)

    def retrieve_similar_comments(
        self,
        query_text: str,
        *,
        n_results: int = 4,
    ) -> list[dict[str, Any]]:
        return self.chroma.query_similar_content(
            self.subreddit,
            query_text,
            n_results=n_results,
            filter_metadata={"type": "comment"},
        )

    def generate_for_post(
        self,
        post_title: str,
        post_body: str = "",
        *,
        n_results: int = 4,
    ) -> GenerationResult:
        query = f"{post_title}\n{post_body}".strip()
        retrieved = self.retrieve_similar_comments(query, n_results=n_results)
        messages: list[ChatMessage] = [
            {"role": "system", "content": build_system_prompt(self.culture_features)},
            {
                "role": "user",
                "content": build_post_user_prompt(post_title, post_body, retrieved),
            },
        ]
        comment = self._clean_model_output(self.llm.chat(messages))
        return GenerationResult(
            comment=comment,
            evaluation=evaluate_comment(comment, self.culture_features),
            retrieved_comments=retrieved,
            post_title=post_title,
            post_body=post_body,
        )

    def generate_for_reply(
        self,
        post_title: str,
        parent_comment: str,
        thread_context: Optional[list[str]] = None,
        *,
        n_results: int = 4,
    ) -> GenerationResult:
        thread_context = thread_context or []
        query = f"{post_title}\n{parent_comment}\n" + "\n".join(thread_context)
        retrieved = self.retrieve_similar_comments(query, n_results=n_results)
        messages: list[ChatMessage] = [
            {"role": "system", "content": build_system_prompt(self.culture_features)},
            {
                "role": "user",
                "content": build_reply_user_prompt(
                    post_title,
                    parent_comment,
                    thread_context,
                    retrieved,
                ),
            },
        ]
        comment = self._clean_model_output(self.llm.chat(messages))
        return GenerationResult(
            comment=comment,
            evaluation=evaluate_comment(comment, self.culture_features),
            retrieved_comments=retrieved,
            post_title=post_title,
            post_body=parent_comment,
        )

    @staticmethod
    def _clean_model_output(text: str) -> str:
        cleaned = THINK_BLOCK_RE.sub("", text).strip()
        if cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1].strip()
        return cleaned
