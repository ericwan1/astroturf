import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import praw

from comment_generator import CommentGenerator, GenerationResult, load_culture_features
from llm import LLMConfig, LLMWrapper


@dataclass
class RedditConfig:
    """Reddit API access configuration."""

    client_id: str
    client_secret: str
    user_agent: str
    username: str
    password: str


@dataclass
class SubredditConfig:
    """Subreddit monitoring configuration."""

    subreddit_name: str
    keywords: List[str]
    min_score: int = 10
    max_posts_per_hour: int = 5
    max_comments_per_hour: int = 5
    response_delay_min: int = 5
    response_delay_max: int = 720


class RedditAgenticAI:
    """Agent scaffold for monitoring and commenting on specific subreddits."""

    def __init__(
        self,
        reddit_config: RedditConfig,
        llm_config: Optional[LLMConfig] = None,
        chroma_db_path: str = "./chroma_db",
        culture_features_path: Optional[str] = None,
        *,
        dry_run: bool = True,
    ):
        self.reddit_config = reddit_config
        self.chroma_db_path = chroma_db_path
        self.dry_run = dry_run

        self.reddit = praw.Reddit(
            client_id=reddit_config.client_id,
            client_secret=reddit_config.client_secret,
            user_agent=reddit_config.user_agent,
            username=reddit_config.username,
            password=reddit_config.password,
        )

        self.llm = LLMWrapper(llm_config or LLMConfig.from_env())
        self.comment_generator = self._build_comment_generator(culture_features_path)

    def _build_comment_generator(
        self,
        culture_features_path: Optional[str],
    ) -> CommentGenerator:
        if culture_features_path:
            path = Path(culture_features_path)
        else:
            subreddit = "redscarepod"
            path = Path(f"data/culture/{subreddit}_features.json")

        if not path.exists():
            logging.warning("Culture features not found at %s; using minimal defaults", path)
            culture_features = {
                "subreddit": "redscarepod",
                "median_poster_profile": {},
                "comment_style": {},
                "language": {},
                "comment_exemplars": {},
            }
        else:
            culture_features = load_culture_features(path)

        return CommentGenerator(
            culture_features,
            self.llm,
            chroma_db_path=self.chroma_db_path,
        )

    def get_relevant_context(self, post, subreddit_name: Optional[str] = None):
        subreddit = subreddit_name or self.comment_generator.subreddit
        return self.comment_generator.chroma.query_similar_content(
            subreddit,
            f"{post.title} {post.selftext}",
            n_results=5,
        )

    def analyze_post_content(self, post) -> dict:
        return {
            "title": post.title,
            "content": post.selftext,
            "score": post.score,
            "num_comments": post.num_comments,
            "subreddit": post.subreddit.display_name,
            "author": str(post.author) if post.author else "[deleted]",
            "created_utc": post.created_utc,
            "url": post.url,
        }

    def generate_comment(self, post_analysis: dict) -> GenerationResult:
        return self.comment_generator.generate_for_post(
            post_analysis["title"],
            post_analysis.get("content") or "",
        )

    def submit_comment(self, comment: str, post_id: str):
        if self.dry_run:
            logging.warning("Refusing to submit comment while dry_run=True")
            return False

        try:
            self.reddit.submission(id=post_id).reply(comment)
            return True
        except Exception as e:
            logging.error(f"Error submitting comment: {e}")
            return False

    def generate_comment_to_post(self, post) -> Optional[GenerationResult]:
        try:
            post_analysis = self.analyze_post_content(post)
            result = self.generate_comment(post_analysis)

            if self.dry_run:
                logging.info("dry_run generated comment for post %s: %s", post.id, result.comment)
                return result

            if self.submit_comment(result.comment, post.id):
                return result
            return None
        except Exception as e:
            logging.error(f"Error generating comment to post: {e}")
            return None

    def generate_reply(
        self,
        post_title: str,
        parent_comment: str,
        thread_context: List[str],
        subreddit_name: str,
    ) -> str:
        try:
            result = self.comment_generator.generate_for_reply(
                post_title,
                parent_comment,
                thread_context,
            )
            return result.comment
        except Exception as e:
            logging.error(f"Error generating reply: {e}")
            return ""

    def monitor_subreddits(self):
        pass

    def start_monitoring(self):
        pass

    def stop_monitoring(self):
        pass

    def get_activity_stats(self):
        pass
