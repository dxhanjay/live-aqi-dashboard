#!/usr/bin/env bash
# One-command end-to-end run: extract -> transform -> load -> dashboard
#   ./run_pipeline.sh                                  # 25 Oct 2026 -> today
#   ./run_pipeline.sh --start 2026-11-01 --end 2026-11-12   (extract args pass through)
set -e
cd "$(dirname "$0")"
python3 extract.py "$@"
python3 transform.py
python3 load.py
python3 build_dashboard.py
echo "Pipeline complete. Dashboard: site/index.html"
