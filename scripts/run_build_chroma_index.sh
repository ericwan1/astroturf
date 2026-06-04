#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${REPO_DIR}/.venv/bin/python"
INDEXER="${REPO_DIR}/scripts/build_chroma_index.py"
LOG_DIR="${REPO_DIR}/logs"
LOG_FILE="${LOG_DIR}/chroma_indexing.log"

SUBREDDIT="${SUBREDDIT:-redscarepod}"
DB_PATH="${DB_PATH:-${REPO_DIR}/data/corpus.sqlite}"
CHROMA_DB_PATH="${CHROMA_DB_PATH:-${REPO_DIR}/chroma_db}"
REBUILD="${REBUILD:-0}"
BATCH_SIZE="${BATCH_SIZE:-100}"

mkdir -p "${LOG_DIR}" "${CHROMA_DB_PATH}"

{
  echo "------------------------------------------------------------"
  echo "CHROMA INDEX RUN START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "subreddit=${SUBREDDIT}"
  echo "db_path=${DB_PATH}"
  echo "chroma_db_path=${CHROMA_DB_PATH}"
  echo "rebuild=${REBUILD}"
  echo "batch_size=${BATCH_SIZE}"
  echo "------------------------------------------------------------"
} >> "${LOG_FILE}"

cd "${REPO_DIR}" || {
  echo "CHROMA INDEX RUN FAILED $(date -u +%Y-%m-%dT%H:%M:%SZ) could not cd to ${REPO_DIR}" >> "${LOG_FILE}"
  exit 1
}

INDEX_ARGS=(
  "${SUBREDDIT}"
  --db "${DB_PATH}"
  --chroma-db "${CHROMA_DB_PATH}"
  --batch-size "${BATCH_SIZE}"
)
if [ "${REBUILD}" = "1" ]; then
  INDEX_ARGS+=(--rebuild)
fi

"${PYTHON_BIN}" "${INDEXER}" "${INDEX_ARGS[@]}" >> "${LOG_FILE}" 2>&1

EXIT_CODE=$?

{
  echo "------------------------------------------------------------"
  echo "CHROMA INDEX RUN END $(date -u +%Y-%m-%dT%H:%M:%SZ) exit_code=${EXIT_CODE}"
  echo "------------------------------------------------------------"
  echo
} >> "${LOG_FILE}"

exit "${EXIT_CODE}"
