"""
python/lib/cleanup.py — Temp directory cleanup utility.

Removes /tmp/science_narrator/<run_id>/ and all contents.
Used by the n8n error node to clean up after pipeline failures.

Usage:
    python python/lib/cleanup.py --run-id <uuid>
"""

import argparse
import os
import shutil
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove temp files for a pipeline run")
    parser.add_argument("--run-id", required=True, help="Pipeline run UUID")
    args = parser.parse_args()

    run_dir = f"/tmp/science_narrator/{args.run_id}"

    if not os.path.exists(run_dir):
        print(f"INFO: Temp directory does not exist, nothing to clean: {run_dir}", file=sys.stderr)
        sys.exit(0)

    try:
        shutil.rmtree(run_dir)
        print(f"INFO: Cleaned up temp directory: {run_dir}", file=sys.stderr)
    except Exception as exc:
        print(f"ERROR: Failed to remove {run_dir}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
