import os
import sys
import praw
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)

# Setup
subreddit_name = sys.argv[1]
load_dotenv()

try:
    reddit_client = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD")
    )
except praw.exceptions.PRAWException as e:
    logging.error(f"Reddit API error: {e}")
    sys.exit(1)
except Exception as e:
    logging.error(f"Unexpected error initializing Reddit client: {e}")
    sys.exit(1)

try:
    scraped_comments = []
    scraped_posts = []
    subreddit = reddit_client.subreddit(subreddit_name)
    scraped_comments = [comment.body for comment in subreddit.comments(limit=1000)]
    for post in subreddit.hot(limit=10):
        scraped_posts.append(post.title)
        scraped_posts.append(post.selftext)
except Exception as e:
    logging.error(f"Error scraping posts: {e}")
    scraped_posts = []

try:
    client = chromadb.PersistentClient(path="./chroma_db")
    col = client.get_or_create_collection(name=f"{subreddit_name}_comments_and_posts")
except Exception as e:
    logging.error(f"ChromaDB error: {e}")
    sys.exit(1)

try:
    if scraped_comments:
        col.add(documents=scraped_comments)
    if scraped_posts:
        col.add(documents=scraped_posts)
except Exception as e:
    logging.error(f"Error adding documents to ChromaDB: {e}")
    sys.exit(1)
