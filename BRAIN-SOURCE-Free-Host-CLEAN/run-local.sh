#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo 'Python 3 is required.' >&2; exit 1; }
if [[ ! -d .venv ]]; then python3 -m venv .venv; fi
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
if [[ -z "${BRAIN_SOURCE_ADMIN_PASSWORD:-}" ]]; then
  read -r -s -p 'Choose an administrator password for this local server: ' BRAIN_SOURCE_ADMIN_PASSWORD
  echo
  export BRAIN_SOURCE_ADMIN_PASSWORD
fi
if [[ -z "${BRAIN_SOURCE_SECRET_KEY:-}" ]]; then
  export BRAIN_SOURCE_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
fi
export BRAIN_SOURCE_DB="${BRAIN_SOURCE_DB:-$PWD/data/brain_source.sqlite3}"
export BRAIN_SOURCE_COOKIE_SECURE="${BRAIN_SOURCE_COOKIE_SECURE:-0}"
mkdir -p "$(dirname "$BRAIN_SOURCE_DB")"
echo 'Starting BRAIN SOURCE at http://127.0.0.1:8000'
echo 'Keep this terminal open. Press Ctrl+C to stop the server.'
uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000
