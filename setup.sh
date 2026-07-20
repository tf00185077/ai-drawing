#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CACHE_ROOT=${XDG_CACHE_HOME:-"$HOME/.cache"}
export UV_NO_MODIFY_PATH=1
export UV_UNMANAGED_INSTALL="$CACHE_ROOT/ai-drawing/uv/0.11.29"
UV_BIN="$UV_UNMANAGED_INSTALL/bin/uv"

if [ ! -x "$UV_BIN" ]; then
  UV_INSTALLER_URL="https://astral.sh/uv/0.11.29/install.sh"
  if ! command -v mktemp >/dev/null 2>&1; then
    printf '%s\n' "ERROR [BOOTSTRAP_TEMPFILE_UNAVAILABLE] 無法建立安全的暫存安裝檔。" >&2
    printf '%s\n' "Hint: 請安裝系統的 mktemp 工具後重試。" >&2
    exit 1
  fi
  UV_INSTALLER=$(mktemp "${TMPDIR:-/tmp}/ai-drawing-uv-install.XXXXXX")
  cleanup_installer() {
    rm -f "$UV_INSTALLER"
  }
  trap cleanup_installer EXIT HUP INT TERM

  if command -v curl >/dev/null 2>&1; then
    if ! curl -LsSf -o "$UV_INSTALLER" "$UV_INSTALLER_URL"; then
      printf '%s\n' "ERROR [BOOTSTRAP_DOWNLOAD_FAILED] uv 安裝程式下載失敗。" >&2
      printf '%s\n' "Hint: 請確認網路與 astral.sh 可連線後重試。" >&2
      exit 1
    fi
  elif command -v wget >/dev/null 2>&1; then
    if ! wget -qO "$UV_INSTALLER" "$UV_INSTALLER_URL"; then
      printf '%s\n' "ERROR [BOOTSTRAP_DOWNLOAD_FAILED] uv 安裝程式下載失敗。" >&2
      printf '%s\n' "Hint: 請確認網路與 astral.sh 可連線後重試。" >&2
      exit 1
    fi
  else
    printf '%s\n' "ERROR [BOOTSTRAP_DOWNLOADER_MISSING] 找不到 curl 或 wget。" >&2
    printf '%s\n' "Hint: 請先安裝 curl 或 wget，再重新執行 setup.sh。" >&2
    exit 127
  fi

  if ! sh "$UV_INSTALLER"; then
    printf '%s\n' "ERROR [BOOTSTRAP_INSTALL_FAILED] uv 安裝程式執行失敗。" >&2
    printf '%s\n' "Hint: 請查看上一段輸出並確認使用者 cache 可寫入。" >&2
    exit 1
  fi
  cleanup_installer
  trap - EXIT HUP INT TERM
fi

if [ ! -x "$UV_BIN" ]; then
  printf '%s\n' "ERROR [BOOTSTRAP_INSTALL_INCOMPLETE] 找不到安裝後的 uv。" >&2
  printf '%s\n' "Hint: 請確認 $UV_UNMANAGED_INSTALL 可寫入後重試。" >&2
  exit 1
fi

AI_DRAWING_UV_BIN=$(CDPATH= cd -- "$(dirname -- "$UV_BIN")" && pwd)/$(basename -- "$UV_BIN")
export AI_DRAWING_UV_BIN

cd "$PROJECT_ROOT"
exec "$UV_BIN" run --python 3.12 --no-project scripts/bootstrap.py "$@"
