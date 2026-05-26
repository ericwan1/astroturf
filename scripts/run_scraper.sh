#!/usr/bin/env bash
set -u

REPO_DIR="/Users/ericwan/Desktop/astroturf"
PYTHON_BIN="${REPO_DIR}/.venv/bin/python"
SCRAPER="${REPO_DIR}/subreddit_scraper.py"
LOG_DIR="${REPO_DIR}/logs"
LOG_FILE="${LOG_DIR}/subreddit_scraper.log"

SUBREDDIT="${SUBREDDIT:-redscarepod}"
DB_PATH="${DB_PATH:-${REPO_DIR}/data/corpus.sqlite}"
LISTINGS="${LISTINGS:-new,hot,rising,top:day}"
POST_LIMIT="${POST_LIMIT:-25}"
COMMENT_LISTINGS="${COMMENT_LISTINGS:-hot,rising,top:day}"
MAX_COMMENT_POSTS="${MAX_COMMENT_POSTS:-25}"
REPLACE_MORE_LIMIT="${REPLACE_MORE_LIMIT:-8}"

mkdir -p "${LOG_DIR}" "$(dirname "${DB_PATH}")"

{
  echo "------------------------------------------------------------"
  echo "SCRAPER RUN START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "subreddit=${SUBREDDIT}"
  echo "db_path=${DB_PATH}"
  echo "listings=${LISTINGS}"
  echo "post_limit=${POST_LIMIT}"
  echo "comment_listings=${COMMENT_LISTINGS}"
  echo "max_comment_posts=${MAX_COMMENT_POSTS}"
  echo "replace_more_limit=${REPLACE_MORE_LIMIT}"
  echo "------------------------------------------------------------"
} >> "${LOG_FILE}"

cd "${REPO_DIR}" || {
  echo "SCRAPER RUN FAILED $(date -u +%Y-%m-%dT%H:%M:%SZ) could not cd to ${REPO_DIR}" >> "${LOG_FILE}"
  exit 1
}

"${PYTHON_BIN}" "${SCRAPER}" "${SUBREDDIT}" \
  --db "${DB_PATH}" \
  --listings "${LISTINGS}" \
  --post-limit "${POST_LIMIT}" \
  --comment-listings "${COMMENT_LISTINGS}" \
  --max-comment-posts "${MAX_COMMENT_POSTS}" \
  --replace-more-limit "${REPLACE_MORE_LIMIT}" >> "${LOG_FILE}" 2>&1

EXIT_CODE=$?

{
  echo "------------------------------------------------------------"
  echo "SCRAPER RUN END $(date -u +%Y-%m-%dT%H:%M:%SZ) exit_code=${EXIT_CODE}"
  echo "------------------------------------------------------------"
  echo
} >> "${LOG_FILE}"

exit "${EXIT_CODE}"
