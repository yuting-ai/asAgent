#!/usr/bin/env bash

set -euo pipefail

uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv lock --check
git --no-pager diff --check