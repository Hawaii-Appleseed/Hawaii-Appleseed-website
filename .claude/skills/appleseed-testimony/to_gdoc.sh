#!/usr/bin/env bash
# Put rendered testimony HTML on the macOS clipboard as HTML flavor, ready to
# paste into a blank Google Doc. This is the `backend: chrome` route documented
# in ~/.claude/drive-routes.yml — the Drive API routes are blocked by Workspace
# policy (service account refused by the shared drive; gcloud OAuth not
# allowlisted), so paste is the working path.
#
# Usage:  ./to_gdoc.sh out/HB1884.html
set -euo pipefail

f="${1:-}"
[ -n "$f" ] || { echo "usage: $0 <rendered.html>" >&2; exit 1; }
[ -f "$f" ] || { echo "error: $f not found" >&2; exit 1; }

bytes=$(wc -c < "$f" | tr -d ' ')
if [ "$bytes" -gt 400000 ]; then
  echo "error: $f is ${bytes} bytes; too large to pass through osascript safely." >&2
  echo "       Re-render with --html-only after shrinking the embedded logo." >&2
  exit 1
fi

hex=$(xxd -p "$f" | tr -d '\n')
osascript -e "set the clipboard to «data HTML${hex}»"

cat <<EOF
HTML on the clipboard (${bytes} bytes).

Next, in Chrome signed in as devin@hibudget.org:
  1. Open the target Drive folder (see the 'testimony' route in ~/.claude/drive-routes.yml).
  2. New ▸ Google Docs ▸ Blank document.
  3. Cmd+V.
  4. Rename the doc to the testimony title.
  5. Confirm the logo came through — a base64 data: URI does not always survive
     the paste. If it is missing, Insert ▸ Image ▸ Upload using
     assets/appleseed-horizontal-green.png.
  6. Add the new Doc to the "Google Docs in progress" memory list.
EOF
