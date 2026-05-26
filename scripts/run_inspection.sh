#!/usr/bin/env bash
set -u

REPO_DIR="/Users/ericwan/Desktop/astroturf"
PYTHON_BIN="${REPO_DIR}/.venv/bin/python"
INSPECTOR="${REPO_DIR}/scripts/inspect_corpus.py"
LOG_DIR="${REPO_DIR}/logs"
LOG_FILE="${LOG_DIR}/corpus_inspection.log"

DB_PATH="${DB_PATH:-${REPO_DIR}/data/corpus.sqlite}"
RECENT_RUNS="${RECENT_RUNS:-10}"

mkdir -p "${LOG_DIR}"

{
  echo "------------------------------------------------------------"
  echo "INSPECTION RUN START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "db_path=${DB_PATH}"
  echo "recent_runs=${RECENT_RUNS}"
  echo "------------------------------------------------------------"
} >> "${LOG_FILE}"

cd "${REPO_DIR}" || {
  echo "INSPECTION RUN FAILED $(date -u +%Y-%m-%dT%H:%M:%SZ) could not cd to ${REPO_DIR}" >> "${LOG_FILE}"
  exit 1
}

"${PYTHON_BIN}" "${INSPECTOR}" \
  --db "${DB_PATH}" \
  --recent-runs "${RECENT_RUNS}" >> "${LOG_FILE}" 2>&1

EXIT_CODE=$?

{
  echo "------------------------------------------------------------"
  echo "INSPECTION RUN END $(date -u +%Y-%m-%dT%H:%M:%SZ) exit_code=${EXIT_CODE}"
  echo "------------------------------------------------------------"
  echo
} >> "${LOG_FILE}"

exit "${EXIT_CODE}"
