#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CACHE_ROOT=${XDG_CACHE_HOME:-"$HOME/.cache"}
export UV_NO_MODIFY_PATH=1
export UV_UNMANAGED_INSTALL="$CACHE_ROOT/ai-drawing/uv/0.11.29"
UV_BIN="$UV_UNMANAGED_INSTALL/bin/uv"

if [ ! -x "$UV_BIN" ]; then
  curl -LsSf https://astral.sh/uv/0.11.29/install.sh | sh
fi

cd "$PROJECT_ROOT"
exec "$UV_BIN" run --python 3.12 --no-project scripts/bootstrap.py "$@"
