import os
import sys
import praw
import chromadb
from dotenv import load_dotenv
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)


def setup_reddit_client():
    """Initialize Reddit client with credentials from environment variables."""
    try:
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


def setup_chromadb_client(subreddit_name):
    """Initialize ChromaDB client and get/create collection."""
    try:
        client = chromadb.PersistentClient(path="./chroma_db")
        collection = client.get_or_create_collection(
            name=f"{subreddit_name}_comments_and_posts"
        )
        logging.info(
            f"ChromaDB collection '{subreddit_name}_comments_and_posts' ready"
            )
        return collection
    except Exception as e:
        logging.error(f"ChromaDB error: {e}")
        sys.exit(1)


def scrape_subreddit_data(reddit_client, subreddit_name):
    """Scrape comments and posts from the specified subreddit."""
    try:
        subreddit = reddit_client.subreddit(subreddit_name)

        # Scrape comments
        logging.info("Scraping comments...")
        comments_data = []
        comment_count = 0

        for comment in subreddit.comments(limit=1000):
            # Filter out deleted and negatively upvoted comments
            if (comment.body and len(comment.body.strip()) > 10 and
                    comment.score > 1):
                comments_data.append({
                    'id': f"comment_{comment.id}",
                    'document': comment.body,
                    'metadata': {
                        'type': 'comment',
                        'author': (str(comment.author)
                                   if comment.author else '[deleted]'),
                        'score': comment.score,
                        'created_utc': comment.created_utc,
                        'subreddit': subreddit_name,
                        'parent_id': comment.parent_id,
                        'scraped_at': datetime.now().isoformat()
                    }
                })
                comment_count += 1

                if comment_count % 100 == 0:
                    logging.info(f"Processed {comment_count} comments...")

        # Scrape posts
        logging.info("Scraping posts...")
        posts_data = []
        post_count = 0

        for post in subreddit.hot(limit=10):
            # Add post title
            if post.title and len(post.title.strip()) > 5:
                posts_data.append({
                    'id': f"post_title_{post.id}",
                    'document': post.title,
                    'metadata': {
                        'type': 'post_title',
                        'author': (str(post.author)
                                   if post.author else '[deleted]'),
                        'score': post.score,
                        'created_utc': post.created_utc,
                        'subreddit': subreddit_name,
                        'post_id': post.id,
                        'scraped_at': datetime.now().isoformat()
                    }
                })
                post_count += 1

            # Add post content (selftext)
            if post.selftext and len(post.selftext.strip()) > 10:
                posts_data.append({
                    'id': f"post_content_{post.id}",
                    'document': post.selftext,
                    'metadata': {
                        'type': 'post_content',
                        'author': (str(post.author)
                                   if post.author else '[deleted]'),
                        'score': post.score,
                        'created_utc': post.created_utc,
                        'subreddit': subreddit_name,
                        'post_id': post.id,
                        'scraped_at': datetime.now().isoformat()
                    }
                })
                post_count += 1

        logging.info(
            f"Scraped {comment_count} comments and {post_count} post items"
            )
        return comments_data, posts_data

    except Exception as e:
        logging.error(f"Error scraping data: {e}")
        sys.exit(1)


def store_data_in_chromadb(collection, comments_data, posts_data):
    """Store scraped data in ChromaDB collection."""
    try:
        # Add comments to ChromaDB
        if comments_data:
            logging.info("Adding comments to ChromaDB...")
            collection.add(
                ids=[item['id'] for item in comments_data],
                documents=[item['document'] for item in comments_data],
                metadatas=[item['metadata'] for item in comments_data]
            )
            logging.info(f"Added {len(comments_data)} comments to ChromaDB")

        # Add posts to ChromaDB
        if posts_data:
            logging.info("Adding posts to ChromaDB...")
            collection.add(
                ids=[item['id'] for item in posts_data],
                documents=[item['document'] for item in posts_data],
                metadatas=[item['metadata'] for item in posts_data]
            )
            logging.info(f"Added {len(posts_data)} post items to ChromaDB")

        # Get collection info
        collection_info = collection.count()
        logging.info(f"Total documents in collection: {collection_info}")

    except Exception as e:
        logging.error(f"Error adding documents to ChromaDB: {e}")
        sys.exit(1)


def main():
    """Main execution function."""
    # Setup
    if len(sys.argv) != 2:
        print("Usage: python subreddit_scraper.py <subreddit_name>")
        sys.exit(1)

    subreddit_name = sys.argv[1]
    load_dotenv()

    # Step 1: Setup Reddit client
    reddit_client = setup_reddit_client()

    # Step 2: Setup ChromaDB client
    collection = setup_chromadb_client(subreddit_name)

    # Step 3: Scrape subreddit data
    comments_data, posts_data = scrape_subreddit_data(
        reddit_client,
        subreddit_name
        )

    # Step 4: Store data in ChromaDB
    store_data_in_chromadb(collection, comments_data, posts_data)

    logging.info("Scraping completed successfully!")


if __name__ == "__main__":
    main()
