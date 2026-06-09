# Astroturf

Astroturf is an experimental Reddit corpus and agent project. The long-term goal is to build an agent that can understand a specific subreddit's language, recurring references, posting formats, and meta-discourse well enough to generate subreddit-native comments and eventually post/reply autonomously in a controlled, evaluated setting.

The current target subreddit is **r/redscarepod**.

## Project status

| Milestone | Status |
|---|---|
| 1. Corpus collection + validation | Done — cron scraper + inspection running |
| 2. Culture mining | Done — features JSON from SQLite corpus |
| 3. Chroma retrieval index | Done — posts/comments indexed from SQLite |
| 4. Generation + evaluation loop | In progress — dry-run generator wired to culture + Chroma + Ollama |
| 5. Autonomous monitoring/posting agent | Not started — scaffold exists in `reddit_agentic_ai.py` |

Latest corpus snapshot (local): ~750 unique posts, ~14.5k unique comments, 18 scrape runs.

## Current files

### Data collection

- `subreddit_scraper.py` — scrapes post/comment snapshots into SQLite via PRAW
- `scripts/run_scraper.sh` — cron wrapper → `logs/subreddit_scraper.log`
- `scripts/inspect_corpus.py` — corpus health checks
- `scripts/run_inspection.sh` — cron wrapper → `logs/corpus_inspection.log`

### Culture + retrieval

- `culture_miner.py` — extracts median-poster profile, n-grams, exemplars, trajectories
- `scripts/mine_culture.py` — CLI → `data/culture/{subreddit}_features.json`
- `scripts/run_mine_culture.sh` — cron wrapper → `logs/culture_mining.log`
- `corpus_indexer.py` — builds Chroma index from deduped SQLite corpus
- `scripts/build_chroma_index.py` — CLI → `chroma_db/`
- `scripts/run_build_chroma_index.sh` — cron wrapper → `logs/chroma_indexing.log`
- `chroma_utils.py` — semantic retrieval helpers over Chroma collections

### Generation + agent

- `llm.py` — unified chat wrapper over pluggable providers
- `llm_providers.py` — `ollama` (local) and `gemini` (Google API) backends
- `comment_generator.py` — builds prompts from culture features + Chroma retrieval, calls `llm.py`
- `comment_evaluator.py` — scores generated comments against mined style constraints
- `scripts/dry_run_generate.py` — generates comments for corpus posts locally (**no Reddit posting**)
- `reddit_agentic_ai.py` — early live-agent scaffold (monitor → retrieve → generate → post). Uses `comment_generator.py`; posting should only happen after dry-run eval looks good.

LLM provider env vars:

```bash
# Local Ollama (default)
export LLM_PROVIDER=ollama
export OLLAMA_MODEL=deepseek-r1:1.5b

# Google Gemini
export LLM_PROVIDER=gemini
export GEMINI_API_KEY=your-key
export GEMINI_MODEL=gemini-2.5-flash-lite
```

### Other

- `requirements.txt` — Python dependencies
- `.env` — Reddit credentials (not committed)

## Typical pipeline

After scraper runs, refresh derived artifacts:

```bash
scripts/run_mine_culture.sh
scripts/run_build_chroma_index.sh
```

Dry-run comment generation (requires a configured LLM provider):

```bash
# Local Ollama
.venv/bin/python scripts/dry_run_generate.py redscarepod \
  --provider ollama \
  --model deepseek-r1:1.5b \
  --limit 2

# Google Gemini
export GEMINI_API_KEY=your-key
.venv/bin/python scripts/dry_run_generate.py redscarepod \
  --provider gemini \
  --model gemini-2.5-flash-lite \
  --limit 2
```

## Architecture

```
SQLite corpus (source of truth)
    ├── culture_miner → data/culture/*_features.json
    └── corpus_indexer → chroma_db/

dry_run_generate / reddit_agentic_ai
    ├── load culture features
    ├── query Chroma for similar comments
    ├── llm.py (Ollama) → candidate comment
    └── comment_evaluator → style score
```

## Next steps

1. **Improve dry-run eval** — compare generated comments to real thread comments; tune prompts/model.
2. **Monitoring loop** — watch `new`/`rising` for r/redscarepod without posting.
3. **Safety gates** — rate limits, score thresholds, human review before live comments.
4. **Live posting** — only after dry-run quality is acceptable.

## Runtime data (gitignored)

- `data/corpus.sqlite`
- `data/culture/`
- `chroma_db/`
- `logs/`
