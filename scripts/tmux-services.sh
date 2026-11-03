#!/usr/bin/env bash
set -euo pipefail

TMUX_BIN="${TMUX_BIN:-/opt/homebrew/bin/tmux}"
TMUX_SOCKET="${TMUX_SOCKET:-ai-drawing}"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.11}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
RUN_USER="${USER:-$(id -un)}"
RUN_HOME="${HOME:-/Users/USER"
REPO_ROOT="${AI_DRAWING_ROOT:-$(dirname "$SCRIPT_DIR")}"
COMFYUI_ROOT="${COMFYUI_ROOT:-$RUN_HOME/comfyui}"
HERMES_SITE_PACKAGES="${HERMES_SITE_PACKAGES:-$RUN_HOME/.hermes/hermes-agent/venv/lib/python3.11/site-packages}"
HOMEBREW_SITE_PACKAGES="${HOMEBREW_SITE_PACKAGES:-/opt/homebrew/lib/python3.11/site-packages}"
PYTHONPATH_VALUE="${HERMES_SITE_PACKAGES}:${HOMEBREW_SITE_PACKAGES}"
RUN_TMPDIR="${TMPDIR:-/tmp}"
RUN_LANG="${LANG:-en_US.UTF-8}"
RUN_PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SESSION_COMFYUI="ai-drawing-comfyui"
SESSION_BACKEND="ai-drawing-backend"
SESSION_BOT="ai-drawing-discord-bot"

usage() {
  cat <<'EOF'
Usage: scripts/tmux-services.sh <command> [service]

Commands:
  start [all|comfyui|backend|bot]    Start detached tmux service session(s)
  stop [all|comfyui|backend|bot]     Gracefully stop service session(s)
  restart [all|comfyui|backend|bot]  Stop then start service session(s)
  status                             Show tmux and HTTP/socket status
  attach <comfyui|backend|bot>       Attach to one service session
  logs <comfyui|backend|bot>         Print the latest 200 pane lines

Detach from an attached session with Ctrl-b then d.
EOF
}

require_runtime() {
  [[ -x "$TMUX_BIN" ]] || { echo "tmux not executable: $TMUX_BIN" >&2; exit 1; }
  [[ -x "$PYTHON_BIN" ]] || { echo "Python not executable: $PYTHON_BIN" >&2; exit 1; }
  [[ -d "$REPO_ROOT" ]] || { echo "Repository missing: $REPO_ROOT" >&2; exit 1; }
  [[ -d "$COMFYUI_ROOT" ]] || { echo "ComfyUI missing: $COMFYUI_ROOT" >&2; exit 1; }
}

session_for() {
  case "$1" in
    comfyui) printf '%s\n' "$SESSION_COMFYUI" ;;
    backend) printf '%s\n' "$SESSION_BACKEND" ;;
    bot) printf '%s\n' "$SESSION_BOT" ;;
    *) echo "Unknown service: $1" >&2; exit 2 ;;
  esac
}

has_session() {
  "$TMUX_BIN" -L "$TMUX_SOCKET" has-session -t "$(session_for "$1")" 2>/dev/null
}

run_service() {
  case "$1" in
    comfyui)
      cd "$COMFYUI_ROOT"
      exec env -i \
        HOME="$RUN_HOME" USER="$RUN_USER" LOGNAME="$RUN_USER" \
        PATH="$RUN_PATH" TMPDIR="$RUN_TMPDIR" LANG="$RUN_LANG" \
        PYTHONUNBUFFERED=1 \
        "$PYTHON_BIN" main.py --listen 127.0.0.1 --port 8188
      ;;
    backend)
      cd "$REPO_ROOT/backend"
      exec env -i \
        HOME="$RUN_HOME" USER="$RUN_USER" LOGNAME="$RUN_USER" \
        PATH="$RUN_PATH" TMPDIR="$RUN_TMPDIR" LANG="$RUN_LANG" \
        PYTHONUNBUFFERED=1 PYTHONPATH="$PYTHONPATH_VALUE" \
        "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8001
      ;;
    bot)
      cd "$REPO_ROOT/discord-bot"
      exec env -i \
        HOME="$RUN_HOME" USER="$RUN_USER" LOGNAME="$RUN_USER" \
        PATH="$RUN_PATH" TMPDIR="$RUN_TMPDIR" LANG="$RUN_LANG" \
        PYTHONUNBUFFERED=1 PYTHONPATH="$PYTHONPATH_VALUE" \
        "$PYTHON_BIN" -m bot.main
      ;;
    *) echo "Unknown service: $1" >&2; exit 2 ;;
  esac
}

start_one() {
  local service="$1" session
  session="$(session_for "$service")"
  if has_session "$service"; then
    echo "$service: already running in tmux session $session"
    return
  fi
  "$TMUX_BIN" -L "$TMUX_SOCKET" new-session -d -s "$session" \
    "$0 __run '$service'"
  echo "$service: started in tmux session $session"
}

stop_one() {
  local service="$1" session i
  session="$(session_for "$service")"
  if ! has_session "$service"; then
    echo "$service: not running"
    return
  fi
  "$TMUX_BIN" -L "$TMUX_SOCKET" send-keys -t "$session" C-c
  for i in {1..40}; do
    if ! has_session "$service"; then
      echo "$service: stopped"
      return
    fi
    sleep 0.25
  done
  "$TMUX_BIN" -L "$TMUX_SOCKET" kill-session -t "$session"
  echo "$service: force-closed tmux session after graceful timeout"
}

for_selected() {
  local operation="$1" target="${2:-all}" service
  case "$target" in
    all)
      for service in comfyui backend bot; do "${operation}_one" "$service"; done
      ;;
    comfyui|backend|bot) "${operation}_one" "$target" ;;
    *) echo "Unknown service: $target" >&2; usage; exit 2 ;;
  esac
}

http_code() {
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "$1" 2>/dev/null || true)"
  printf '%s' "${code:-000}"
}

status() {
  local service session state
  for service in comfyui backend bot; do
    session="$(session_for "$service")"
    if has_session "$service"; then state="running ($session)"; else state="stopped"; fi
    printf '%-8s %s\n' "$service:" "$state"
  done
  printf '%-8s %s\n' 'ComfyUI HTTP:' "$(http_code http://127.0.0.1:8188/system_stats)"
  printf '%-8s %s\n' 'Backend HTTP:' "$(http_code http://127.0.0.1:8001/health)"
  if has_session bot; then
    local pane_pid
    pane_pid="$($TMUX_BIN -L "$TMUX_SOCKET" display-message -p -t "$SESSION_BOT" '#{pane_pid}')"
    if lsof -nP -a -p "$pane_pid" -iTCP -sTCP:ESTABLISHED 2>/dev/null | grep -q ':443'; then
      printf '%-8s %s\n' 'Bot TLS:' established
    else
      printf '%-8s %s\n' 'Bot TLS:' not-established
    fi
  fi
}

command="${1:-}"
case "$command" in
  __run)
    require_runtime
    run_service "${2:?service required}"
    ;;
  start)
    require_runtime
    for_selected start "${2:-all}"
    ;;
  stop)
    require_runtime
    for_selected stop "${2:-all}"
    ;;
  restart)
    require_runtime
    for_selected stop "${2:-all}"
    for_selected start "${2:-all}"
    ;;
  status)
    require_runtime
    status
    ;;
  attach)
    require_runtime
    service="${2:?service required}"
    exec "$TMUX_BIN" -L "$TMUX_SOCKET" attach-session -t "$(session_for "$service")"
    ;;
  logs)
    require_runtime
    service="${2:?service required}"
    "$TMUX_BIN" -L "$TMUX_SOCKET" capture-pane -p -S -200 -t "$(session_for "$service")"
    ;;
  *)
    usage
    exit 2
    ;;
esac
