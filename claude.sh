# Sourced from ~/.bashrc or ~/.zshrc by the nonoclaude installer.
unalias claude 2>/dev/null || true
claude() {
  if [[ "${1-}" == "--no-sandbox" ]]; then
    shift
    command claude "$@"
    return
  fi
  case "${1-}" in
    agents|attach|auth|auto-mode|doctor|gateway|import|install|logs|mcp|plugin|plugins|purge|respawn|rm|setup-token|stop|kill|ultrareview|update|upgrade|-h|--help|-v|--version)
      command claude "$@"
      return
      ;;
  esac
  if [[ "$PWD" == "$HOME" || "$PWD" == /tmp ]]; then
    if (( $# == 0 )) && [[ "$PWD" == "$HOME" ]]; then
      (cd /tmp && command claude)
    else
      command claude "$@"
    fi
  else
    nonoclaude "$@"
  fi
}
