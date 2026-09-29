#!/bin/bash
# Put the corpus snapshot where a colleague's clone lives (~/HawaiiAppleseed),
# inside the eval sandbox's private HOME, so the skill finds it the normal way.
set -euo pipefail
case_dir="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/HawaiiAppleseed"
cp -R "$case_dir/../../corpus/." "$HOME/HawaiiAppleseed/"
