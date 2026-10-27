#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec .venv/bin/python start_workbench.py "$@"
