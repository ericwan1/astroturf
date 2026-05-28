#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${REPO_DIR}/.venv/bin/python"
MINER="${REPO_DIR}/scripts/mine_culture.py"
LOG_DIR="${REPO_DIR}/logs"
LOG_FILE="${LOG_DIR}/culture_mining.log"

SUBREDDIT="${SUBREDDIT:-redscarepod}"
DB_PATH="${DB_PATH:-${REPO_DIR}/data/corpus.sqlite}"
OUTPUT_PATH="${OUTPUT_PATH:-${REPO_DIR}/data/culture/${SUBREDDIT}_features.json}"
TOP_K="${TOP_K:-25}"
MIN_NGRAM_COUNT="${MIN_NGRAM_COUNT:-2}"

mkdir -p "${LOG_DIR}" "$(dirname "${OUTPUT_PATH}")"

{
  echo "------------------------------------------------------------"
  echo "CULTURE MINING RUN START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "subreddit=${SUBREDDIT}"
  echo "db_path=${DB_PATH}"
  echo "output_path=${OUTPUT_PATH}"
  echo "top_k=${TOP_K}"
  echo "min_ngram_count=${MIN_NGRAM_COUNT}"
  echo "------------------------------------------------------------"
} >> "${LOG_FILE}"

cd "${REPO_DIR}" || {
  echo "CULTURE MINING RUN FAILED $(date -u +%Y-%m-%dT%H:%M:%SZ) could not cd to ${REPO_DIR}" >> "${LOG_FILE}"
  exit 1
}

"${PYTHON_BIN}" "${MINER}" "${SUBREDDIT}" \
  --db "${DB_PATH}" \
  --output "${OUTPUT_PATH}" \
  --top-k "${TOP_K}" \
  --min-ngram-count "${MIN_NGRAM_COUNT}" >> "${LOG_FILE}" 2>&1

EXIT_CODE=$?

{
  echo "------------------------------------------------------------"
  echo "CULTURE MINING RUN END $(date -u +%Y-%m-%dT%H:%M:%SZ) exit_code=${EXIT_CODE}"
  echo "------------------------------------------------------------"
  echo
} >> "${LOG_FILE}"

exit "${EXIT_CODE}"
