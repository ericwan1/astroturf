import praw
import chromadb
import logging
import sys
from typing import List, Optional
from dataclasses import dataclass
from chroma_utils import ChromaQueryManager
from llm import LLMWrapper, LLMConfig


@dataclass
class RedditConfig:
    """Reddit API access configuration"""
    client_id: str
    client_secret: str
    user_agent: str
    username: str
    password: str


@dataclass
class SubredditConfig:
    """Subreddit monitoring configuration"""
    subreddit_name: str
    keywords: List[str]
    min_score: int = 10
    max_posts_per_hour: int = 5
    max_comments_per_hour: int = 5
    response_delay_min: int = 5
    response_delay_max: int = 720


class RedditAgenticAI:
    """
    Agentic AI system for monitoring and commenting on specific subreddits.
    """

    def __init__(self, reddit_config: RedditConfig, llm_config: Optional[LLMConfig] = None, chroma_db_path: str = "./chroma_db"):
        """
        Initialize the RedditAgenticAI instance.

        Args:
            reddit_config: Configuration for Reddit API access
            llm_config: Configuration for the LLM wrapper (optional)
            chroma_db_path: Path to ChromaDB storage
        """
        self.reddit_config = reddit_config
        self.chroma_db_path = chroma_db_path

        # Initialize LLM wrapper
        self.llm = LLMWrapper(llm_config)

        # Initialize Reddit client
        self.reddit = praw.Reddit(
            client_id=reddit_config.client_id,
            client_secret=reddit_config.client_secret,
            user_agent=reddit_config.user_agent,
            username=reddit_config.username,
            password=reddit_config.password
        )

        # ChromaDB Query Client
        self.chroma_query_manager = ChromaQueryManager()

        try:
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_db_path)
            logging.info(f"ChromaDB client initialized at {self.chroma_db_path}")
        except Exception as e:
            logging.error(f"Error initializing ChromaDB client: {e}")
            sys.exit(1)

    def get_relevant_context(self, post, subreddit_name: str):
        return self.chroma_query_manager.query_similar_content(
            subreddit_name,
            f"{post.title} {post.selftext}",
            n_results=5
        )

    def get_subreddit_slang(self, subreddit_name: str) -> List[str]:
        """
        Gets the slang for a subreddit from ChromaDB.

        Args:
            subreddit_name: The name of the subreddit to get slang for

        Returns:
            A list of slang words
        """
        try:
            collection = self.chroma_client.get_or_create_collection(name=f"{subreddit_name}_comments_and_posts")
            results = collection.query(query_texts=[subreddit_name], n_results=10)
            return results["documents"][0]
        except Exception as e:
            logging.error(f"Error getting slang for {subreddit_name}: {e}")
            return []

    def analyze_post_content(self, post) -> dict:
        """
        Helper function that extracts relevant information from a Reddit post.

        Args:
            post: PRAW submission object

        Returns:
            Dictionary containing post analysis
        """
        return {
            'title': post.title,
            'content': post.selftext,
            'score': post.score,
            'num_comments': post.num_comments,
            'subreddit': post.subreddit.display_name,
            'author': str(post.author) if post.author else '[deleted]',
            'created_utc': post.created_utc,
            'url': post.url
        }

    def generate_comment(self, post_analysis: dict, subreddit_slang: List[str]) -> str:
        """
        Generates a comment based on the post analysis and subreddit slang.
        """
        try:
            return self.llm.generate_response(post_analysis)
        except Exception as e:
            logging.error(f"Error generating comment: {e}")
            return ""

    def submit_comment(self, comment: str):
        """
        Submits a comment to a post.
        """
        pass

    def generate_comment_to_post(self, post):
        """
        Generates a comment after:
            1. Analyzing the parent post
            2. Pull subreddit slang from ChromaDB
            3. Generate a comment
            4. Submit comment
        """
        try:
            # Step 1: Analyze the parent post
            post_analysis = self.analyze_post_content(post)

            # Step 2: Pull subreddit slang from ChromaDB
            subreddit_slang = self.get_subreddit_slang(post_analysis["subreddit"])

            # Step 3: Generate a comment
            comment = self.generate_comment(post_analysis, subreddit_slang)

            # Step 4: Submit comment
            self.submit_comment(comment)
        except Exception as e:
            logging.error(f"Error generating comment to post: {e}")
            return None

    def generate_reply(self, parent_comment, thread_context: List[str], subreddit_name: str):
        """
        Generates a reply after:
            1. Analyzing the parent comments (checking the full thread)
            2. Analyzing the parent commentor's engaged subreddits
            3. Pull subreddit slang from ChromaDB
            4. Generate a response
            5. Submit response
        """
        try:
            # Get subreddit slang
            subreddit_slang = self.get_subreddit_slang(subreddit_name)

            # Generate reply using LLM wrapper
            reply = self.llm.generate_reply(parent_comment, thread_context, subreddit_slang, subreddit_name)

            return reply
        except Exception as e:
            logging.error(f"Error generating reply: {e}")
            return ""

    def monitor_subreddits(self):
        """
        Monitors subreddits for new posts and comments.
        """
        pass

    def start_monitoring(self):
        """
        Starts the monitoring process.
        """

    def stop_monitoring(self):
        """
        Stops the monitoring process.
        """

    def get_activity_stats(self):
        """
        Gets the activity statistics of the monitoring process.
        """
        pass
