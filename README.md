# Astroturf

Astroturf is an experimental Reddit corpus and agent project. The long-term goal is to build an agent that can understand a specific subreddit's language, recurring references, posting formats, and meta-discourse well enough to generate subreddit-native comments and eventually post/reply autonomously in a controlled, evaluated setting.

The current target subreddit is **r/redscarepod** (`config.DEFAULT_SUBREDDIT`). Override with the `SUBREDDIT` env var or a CLI/subreddit argument when targeting another community later.

## Project status

| Milestone | Status |
|---|---|
| 1. Corpus collection + validation | Done — cron scraper + inspection running |
| 2. Culture mining | Done — features JSON from SQLite corpus |
| 3. Chroma retrieval index | Done — posts/comments indexed from SQLite |
| 4. Generation + evaluation loop | v1 done — dry-run wired to culture + Chroma + LLM; quality tuning ongoing |
| 5. Autonomous monitoring/posting agent | Not started — scaffold in `reddit_agentic_ai.py` (`dry_run=True` by default) |

Corpus size changes over time; run `scripts/inspect_corpus.py` for current counts.

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
- `reddit_agentic_ai.py` — early live-agent scaffold. Uses `comment_generator.py` for retrieval + generation. **`dry_run=True` by default** — will not post to Reddit unless explicitly disabled. Pass `subreddit=` (or set `SUBREDDIT`) to target a community; defaults to r/redscarepod.

LLM provider env vars (`LLMConfig.from_env()` is used by dry-run and the agent):

```bash
# Target subreddit (optional; default redscarepod — also used by run_*.sh cron wrappers)
export SUBREDDIT=redscarepod

# Local Ollama (default)
export LLM_PROVIDER=ollama
export OLLAMA_MODEL=deepseek-r1:1.5b

# Google Gemini
export LLM_PROVIDER=gemini
export GEMINI_API_KEY=your-key
export GEMINI_MODEL=gemini-2.5-flash-lite
```

### Other

- `config.py` — default subreddit (`redscarepod`), `SUBREDDIT` env override, culture path helpers
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
    ├── comment_generator
    │     ├── load culture features
    │     └── query Chroma for similar comments
    ├── llm.py (Ollama or Gemini) → candidate comment
    └── comment_evaluator → style score

reddit_agentic_ai defaults to dry_run=True and skips Reddit posting.
```

## Next steps

1. **Improve dry-run eval** — compare generated comments to real thread comments; tune prompts/model.
2. **Monitoring loop** — watch `new`/`rising` for r/redscarepod without posting.
3. **Safety gates** — rate limits, score thresholds, human review before live comments (`dry_run=False`).
4. **Live posting** — only after dry-run quality is acceptable.

## Runtime data (gitignored)

- `data/corpus.sqlite`
- `data/culture/`
- `chroma_db/`
- `logs/`
