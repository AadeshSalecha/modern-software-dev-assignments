#!/usr/bin/env bash
# The gate, under a stable name. See kit/check.py for what it checks.
cd "$(dirname "$0")/.." && exec python3 kit/check.py "$@"
