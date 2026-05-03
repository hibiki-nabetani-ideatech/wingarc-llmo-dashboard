#!/usr/bin/env bash
# manual_update.sh — WingArc LLMO manual update orchestration (in-repo layout).
#
# Layout: this script lives at <repo>/_pipeline/manual_update.sh.
# It builds <repo>/index.html (the GitHub Pages site).
#
# This is a static manual-refresh fork. Run this script after dropping new
# CSV / Brand Radar JSON files into the appropriate raw/ folders.
#
# Steps:
#   1) snapshot _pipeline/data_v3.json → _pipeline/data_v3_prev.json
#   2) merge Brand Radar responses into _pipeline/data_v3.json (if present)
#   3) fetch ⑤ AI Topics (skipped silently if ANTHROPIC_API_KEY unset)
#   4) compute the diff
#   5) build the HTML dashboard → ../index.html (repo root)
#
# Optional env vars:
#   BR_DIR               — directory containing br_<llm>.json (default /tmp/br)
#   DASHBOARD_URL        — public URL (default GitHub Pages link)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"             # <repo>/_pipeline
SITE_DIR="$(cd "$ROOT/.." && pwd)"                # <repo>
cd "$ROOT"

BR_DIR="${BR_DIR:-/tmp/br}"
ASOF="$(date '+%Y-%m-%d %H:%M JST')"

echo "=== manual_update @ $ASOF ==="
echo "    ROOT=$ROOT"
echo "    SITE_DIR=$SITE_DIR"

# 1) Snapshot
if [[ -f data_v3.json ]]; then
  cp data_v3.json data_v3_prev.json
  echo "[1/5] snapshot: data_v3.json → data_v3_prev.json"
else
  echo "ERR: data_v3.json missing in $ROOT" >&2
  exit 1
fi

# 2) Merge Brand Radar (skip if no input dir / no files)
if [[ -d "$BR_DIR" ]] && ls "$BR_DIR"/*.json >/dev/null 2>&1; then
  echo "[2/5] merging Brand Radar from $BR_DIR …"
  python3 merge_brand_radar.py --in-dir "$BR_DIR"
else
  echo "[2/5] WARN: no Brand Radar files in $BR_DIR — skipping merge"
fi

# 3) Fetch ⑤ AI Topics (skip silently if ANTHROPIC_API_KEY unset; keeps prior entries on any error)
echo "[3/5] fetching AI Topics …"
python3 fetch_ai_topics.py || echo "[3/5] WARN: fetch_ai_topics.py exited non-zero; continuing"

# 4) Diff
echo "[4/5] computing diff …"
python3 compute_diff.py

# 5) Build HTML directly into repo root
echo "[5/5] building HTML …"
python3 build_html_v3.py --out "$SITE_DIR/index.html"

echo "=== done ==="
echo "Review changes with 'git status' / 'git diff' before committing."
