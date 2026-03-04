#!/bin/bash

set -euo pipefail

echo "[SMOKE] vortex-x --version"
vortex-x --version

echo "[SMOKE] python imports"
python3 -c "import psutil, yaml"

echo "[SMOKE] nginx config test"
nginx -t

echo "[SMOKE] doctor"
vortex-x doctor --json

echo "[SMOKE] done"
