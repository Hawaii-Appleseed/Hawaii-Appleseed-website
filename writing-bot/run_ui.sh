#!/bin/bash
# Launch the Hawaiʻi Appleseed Writing Bot Streamlit UI locally.
set -euo pipefail

cd "$(dirname "$0")"

if [ -f "$HOME/.openclaw/secrets.env" ]; then
  set -a; source "$HOME/.openclaw/secrets.env"; set +a
fi

exec ./.venv/bin/streamlit run app.py "$@"
