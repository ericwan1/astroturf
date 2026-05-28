# Astroturf

Astroturf is an experimental Reddit corpus and agent project. The long-term goal is to build an agent that can understand a specific subreddit’s language, recurring references, posting formats, and meta-discourse well enough to generate subreddit-native comments in a controlled/evaluated setting.

The project is currently focused on the first milestone: collecting raw subreddit data over time. The current scraper stores timestamped post and comment snapshots so later systems can analyze how posts move across `new`, `hot`, `rising`, and `top`, and how community language evolves around them.

## Current Files

`subreddit_scraper.py` is the main corpus collection script. It uses PRAW to scrape a subreddit’s configured listings, deduplicates posts within a scrape run, stores raw post/comment snapshots in SQLite, and links comments back to the post snapshot they came from.

`scripts/run_scraper.sh` is the cron-friendly wrapper for the scraper. It sets conservative default scrape limits, writes run delimiters to `logs/subreddit_scraper.log`, and derives the repo path from the script location so it can run from any clone path.

`scripts/inspect_corpus.py` inspects the SQLite corpus database. It reports high-level health metrics such as post/comment snapshot counts, recent scrape runs, latest run volume, multi-source posts, and top posts by score.

`scripts/run_inspection.sh` is the cron-friendly wrapper for corpus inspection. It writes timestamped inspection output to `logs/corpus_inspection.log` so scheduled scraper runs can be checked against scheduled validation runs.

`chroma_utils.py` contains helpers for querying ChromaDB collections. This was part of the earlier vector-search prototype and will likely become useful again when we rebuild Chroma indexes from the SQLite corpus.

`llm.py` contains a thin Ollama API wrapper. It is the starting point for local generation, but it is not yet wired into a full evaluated comment-generation loop.

`reddit_agentic_ai.py` is an early scaffold for an agent that analyzes posts, retrieves subreddit context, generates comments, and posts replies. It is not currently the active path; the corpus builder needs to mature before this layer becomes useful.

`requirements.txt` lists the Python dependencies used by the current scripts. The main runtime dependency for data collection is PRAW, with `python-dotenv` used to load local Reddit credentials from `.env`.

## Next Steps

1. **Corpus builder validation:** Let the scheduled scraper and inspection jobs run for several cycles, then check that `data/corpus.sqlite` and the logs are growing as expected. Watch for auth errors, rate-limit behavior, duplicate volume, and whether the default scrape size is sufficient.

2. **Culture miner:** Build scripts that read from SQLite and extract subreddit-specific signals: common phrases, recurring n-grams, `-posting` patterns, high-score comment exemplars, post title formats, repeated references, and post trajectories from `new` into `hot` or `top`.

3. **Derived retrieval index:** Rebuild ChromaDB from the SQLite corpus rather than scraping directly into Chroma. This should index posts/comments with useful metadata while keeping SQLite as the raw source of truth.

4. **Generation and evaluation loop:** Create a dry-run agent that retrieves relevant context, uses mined culture features, generates candidate comments, and scores them before any live posting is considered.

5. **Automated tracking agent:** After culture mining and evaluation work, implement an agent that monitors posts/comments over time, tracks emerging references, and uses the corpus to reason about when and how subreddit-specific language changes.
