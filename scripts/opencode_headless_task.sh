#!/usr/bin/env bash
set -euo pipefail

issue_key=""
agent="tradingagents-implementer"
model=""
variant=""
title=""
prompt_file=""
attach_url=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue)
      issue_key="${2:?missing issue value}"
      shift 2
      ;;
    --agent)
      agent="${2:?missing agent value}"
      shift 2
      ;;
    --model)
      model="${2:?missing model value}"
      shift 2
      ;;
    --variant)
      variant="${2:?missing variant value}"
      shift 2
      ;;
    --title)
      title="${2:?missing title value}"
      shift 2
      ;;
    --prompt-file)
      prompt_file="${2:?missing prompt file path}"
      shift 2
      ;;
    --attach)
      attach_url="${2:?missing attach url}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${issue_key}" ]]; then
  echo "--issue is required" >&2
  exit 1
fi

if [[ -z "${prompt_file}" ]]; then
  echo "--prompt-file is required" >&2
  exit 1
fi

if [[ ! -f "${prompt_file}" ]]; then
  echo "prompt file not found: ${prompt_file}" >&2
  exit 1
fi

worktree_root="$(git rev-parse --show-toplevel)"
resolved_prompt="$(cd "$(dirname "${prompt_file}")" && pwd -P)/$(basename "${prompt_file}")"
session_title="${title:-${issue_key} headless implementation}"
prompt_text="$(cat "${resolved_prompt}")"

cmd=(
  bash
  "${worktree_root}/scripts/opencode_env.sh"
  run
  --dir "${worktree_root}"
  --agent "${agent}"
  --format json
  --title "${session_title}"
  --dangerously-skip-permissions
)

if [[ -n "${model}" ]]; then
  cmd+=(--model "${model}")
fi

if [[ -n "${variant}" ]]; then
  cmd+=(--variant "${variant}")
fi

if [[ -n "${attach_url}" ]]; then
  cmd+=(--attach "${attach_url}")
fi

cmd+=("${prompt_text}")

exec "${cmd[@]}"
