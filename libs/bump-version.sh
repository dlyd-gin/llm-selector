#!/usr/bin/env bash
set -euo pipefail
uv --directory "$(dirname "$0")/llm-selector" version --bump patch
