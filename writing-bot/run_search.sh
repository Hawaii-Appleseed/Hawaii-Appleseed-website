#!/bin/bash
# Launch the Hawaiʻi Appleseed Source Search UI locally.
# Forces LOCAL embeddings (unset OPENAI_API_KEY) so search always runs at $0 and
# stays consistent with the locally-built MiniLM index — regardless of shell env.
set -euo pipefail

cd "$(dirname "$0")"

unset OPENAI_API_KEY

# Disable the file-watcher: it walks torch/transformers submodules on every
# rerun (noisy tracebacks + overhead) and we restart manually anyway.
exec ./.venv/bin/streamlit run search.py --server.fileWatcherType none "$@"
