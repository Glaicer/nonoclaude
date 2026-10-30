#!/usr/bin/env bash
# nonoclaude installer: Claude Code in a nono sandbox (https://github.com/Glaicer/nonoclaude)
# Usage: curl -fsSL https://raw.githubusercontent.com/Glaicer/nonoclaude/main/install.sh | bash
set -euo pipefail

REPO="${NONOCLAUDE_REPO:-https://raw.githubusercontent.com/Glaicer/nonoclaude/main}"
BIN="$HOME/.local/bin"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}/nonoclaude"
SETTINGS="${XDG_CONFIG_HOME:-$HOME/.config}/nono/claude-dev.json"

say() { printf 'nonoclaude: %s\n' "$*"; }
die() { printf 'nonoclaude: ERROR: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
confirm() {
  local answer
  [ "$2" = no ] && return 1
  [ "$interactive" = true ] || return 0
  printf '%s [Y/n] ' "$1" >&2
  IFS= read -r answer <&3 || die "input ended; installation cancelled"
  case "$answer" in ''|y|Y|yes|Yes|YES) return 0 ;; *) return 1 ;; esac
}

[ "$(id -u)" -ne 0 ] || die "run as a regular user, not root"
case "$(uname -s)" in
  Linux) platform=linux nono_hint="https://docs.nono.sh/cli/getting_started/installation" ;;
  Darwin) platform=macos nono_hint="brew install nono" ;;
  *) die "supported platforms: Linux, WSL2, macOS" ;;
esac
python3 -c '' 2>/dev/null || die "python3 is required"
have nono || die "nono is required: $nono_hint"
have claude || die "Claude Code is required: https://code.claude.com/docs/en/setup"
if [ "$platform" = linux ] && [ -r /sys/kernel/security/lsm ] && ! grep -qw landlock /sys/kernel/security/lsm; then
  die "Landlock is not enabled in this kernel; nono cannot enforce the sandbox"
fi
profile="profile.$platform.json"

interactive=true known_hosts=ask shell_integration=ask
for arg in "$@"; do
  case "$arg" in
    --yes) interactive=false ;;
    --no-known-hosts) known_hosts=no ;;
    --no-shell-integration) shell_integration=no ;;
    *) die "usage: bash install.sh [--yes] [--no-known-hosts] [--no-shell-integration]" ;;
  esac
done
if [ "$interactive" = true ] && ! { exec 3</dev/tty; } 2>/dev/null; then
  interactive=false
fi

if [ -f nonoclaude ] && [ -f claude.sh ] && [ -f "$profile" ]; then
  src=$PWD
else
  src=$(mktemp -d)
  trap 'rm -rf "$src"' EXIT
  for file in nonoclaude claude.sh "$profile"; do
    curl -fsSL "$REPO/$file" -o "$src/$file" || die "failed to download $REPO/$file"
  done
fi

mkdir -p "$BIN" "$SHARE" "$(dirname "$SETTINGS")"
install -m 755 "$src/nonoclaude" "$BIN/nonoclaude"
install -m 644 "$src/claude.sh" "$SHARE/claude.sh"
say "installed $BIN/nonoclaude"

if [ -f "$SETTINGS" ]; then
  say "$SETTINGS exists; left untouched"
else
  install -m 644 "$src/$profile" "$SETTINGS"
  say "created $SETTINGS"
  say "Git over SSH needs ~/.ssh/known_hosts to verify servers. Keys stay blocked."
  if confirm "Let the agent read ~/.ssh/known_hosts?" "$known_hosts"; then
    python3 - "$SETTINGS" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
settings = json.loads(path.read_text())
settings["read_exceptions"] = ["$HOME/.ssh/known_hosts"]
path.write_text(json.dumps(settings, indent=2) + "\n")
PY
  fi
fi

case "${SHELL:-}" in
  */zsh) rc="${ZDOTDIR:-$HOME}/.zshrc" ;;
  *) rc="$HOME/.bashrc" ;;
esac
line="[ -f \"$SHARE/claude.sh\" ] && . \"$SHARE/claude.sh\"  # nonoclaude"
if grep -qF '# nonoclaude' "$rc" 2>/dev/null; then
  say "shell integration already in $rc"
else
  say "Shell integration makes 'claude' sandboxed inside projects; ~ and /tmp stay unsandboxed."
  if confirm "Add it to $rc?" "$shell_integration"; then
    printf '\n%s\n' "$line" >> "$rc"
    say "added to $rc; open a new shell to use it"
  fi
fi

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) say "add $BIN to PATH" ;;
esac

say "verifying nono + claude"
check=$(mktemp -d)
(cd "$check" && "$BIN/nonoclaude" --version) || die "verification failed"
rmdir "$check"
say "done. cd into a project and run: nonoclaude"
