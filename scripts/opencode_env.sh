#!/usr/bin/env bash
set -euo pipefail

worktree_root="$(git rev-parse --show-toplevel)"
common_git_dir="$(git rev-parse --git-common-dir)"
common_repo_root="$(cd "$(dirname "$common_git_dir")" && pwd -P)"

export XDG_DATA_HOME="${worktree_root}/.local-state/opencode/data"
export XDG_CONFIG_HOME="${worktree_root}/.local-state/opencode/config"
export XDG_CACHE_HOME="${worktree_root}/.local-state/opencode/cache"
export XDG_STATE_HOME="${worktree_root}/.local-state/opencode/state"

mkdir -p \
  "${XDG_DATA_HOME}" \
  "${XDG_CONFIG_HOME}" \
  "${XDG_CACHE_HOME}" \
  "${XDG_STATE_HOME}"

if [[ -f "${common_repo_root}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${common_repo_root}/.env"
  set +a
fi

if [[ -f "${common_repo_root}/.env.enterprise" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${common_repo_root}/.env.enterprise"
  set +a
fi

exec opencode "$@"
