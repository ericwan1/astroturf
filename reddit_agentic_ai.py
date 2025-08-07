import praw
from typing import List
from dataclasses import dataclass

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

    def __init__(self, reddit_config: RedditConfig, llm_api_key: str):
        """
        Initialize the RedditAgenticAI instance.

        Args:
            reddit_config: Configuration for Reddit API access
            llm_api_key: API key for the LLM
        """
        self.reddit_config = reddit_config
        self.llm_api_key = llm_api_key

        # Initialize Reddit client
        self.reddit = praw.Reddit(
            client_id=reddit_config.client_id,
            client_secret=reddit_config.client_secret,
            user_agent=reddit_config.user_agent,
            username=reddit_config.username,
            password=reddit_config.password
        )
        
    def generate_comment_to_post(self):
        """
        Generates a comment after:
            1. Analyzing the parent post
            2. Pull subreddit slang from ChromaDB
            3. Generate a comment
            4. Submit comment
        """
        
    def generate_reply(self):
        """
        Generates a reply after:
            1. Analyzing the parent comments (checking the full thread)
            2. Analyzing the parent commentor's engaged subreddits
            3. Pull subreddit slang from ChromaDB
            4. Generate a response
            5. Submit response
        """

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