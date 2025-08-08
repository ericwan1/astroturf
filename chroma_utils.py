import chromadb
import logging
from typing import List, Dict, Optional


class ChromaQueryManager:
    """Utility class for querying ChromaDB collections."""

    def __init__(self, chroma_db_path: str = "./chroma_db"):
        self.chroma_db_path = chroma_db_path
        try:
            self.client = chromadb.PersistentClient(path=chroma_db_path)
            logging.info("ChromaDB client initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize ChromaDB client: {e}")
            self.client = None

    def query_similar_content(self, subreddit_name: str, query_text: str, n_results: int = 5, filter_metadata: Optional[Dict] = None) -> List[Dict]:
        """
        Query ChromaDB for similar content based on semantic similarity.

        Args:
            subreddit_name: Name of the subreddit collection
            query_text: Text to find similar content for
            n_results: Number of similar results to return
            filter_metadata: Optional metadata filter (e.g., {'type': 'comment'})

        Returns:
            List of similar documents with metadata
        """
        if not self.client:
            logging.error("ChromaDB client not initialized")
            return []

        try:
            collection = self.client.get_collection(f"{subreddit_name}_comments_and_posts")

            results = collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=filter_metadata
            )

            # Format results for easier use
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        'document': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] and results['metadatas'][0] else {},
                        'distance': results['distances'][0][i] if results['distances'] and results['distances'][0] else None,
                        'id': results['ids'][0][i] if results['ids'] and results['ids'][0] else None
                    })

            return formatted_results

        except Exception as e:
            logging.error(f"Error querying ChromaDB: {e}")
            return []

    def get_high_engagement_content(self, subreddit_name: str, min_score: int = 10, n_results: int = 5) -> List[Dict]:
        """Get high-engagement content from a subreddit."""
        return self.query_similar_content(
            subreddit_name,
            "",  # Empty query to get any content
            n_results=n_results,
            filter_metadata={'score': {'$gte': min_score}}
        )

    def get_recent_content(self, subreddit_name: str, n_results: int = 5) -> List[Dict]:
        """Get recent content from a subreddit."""
        # This would require additional logic for timestamp filtering
        return self.query_similar_content(subreddit_name, "", n_results=n_results)


# Example usage function
def test_query_functionality():
    """Test the query functionality."""
    query_manager = ChromaQueryManager()

    # Test query
    test_query = "rabbit named peanut"
    similar_content = query_manager.query_similar_content("python", test_query, n_results=3)

    logging.info(f"Found {len(similar_content)} similar documents for query: '{test_query}'")
    for i, result in enumerate(similar_content):
        logging.info(f"Result {i+1}: {result['document'][:100]}... (Score: {result['distance']:.3f})")


if __name__ == "__main__":
    test_query_functionality()
