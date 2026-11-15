# OpenCode Headless Workflow

This repo now supports a repo-local OpenCode lane that uses the existing `TradingAgents/.env` OpenRouter key while keeping OpenCode state inside `.local-state/`.

## What this is for

- Codex acts as adviser / engineering manager.
- OpenCode acts as the outsourced implementation lane.
- OpenCode works on one bounded task at a time in an isolated worktree.
- Codex reviews the diff, runs verification, then commits and merges.

## Repo-local setup

- `opencode.json` configures OpenRouter as the default provider path.
- `.opencode/agents/tradingagents-implementer.md` is the write-capable delivery agent.
- `.opencode/agents/tradingagents-reviewer.md` is the read-only review agent.
- `scripts/opencode_env.sh` sources the primary repo `.env` and `.env.enterprise` and pins OpenCode state to `.local-state/opencode/`.
- `scripts/opencode_headless_task.sh` runs one headless task session with JSON output.

## Why the wrapper exists

Linked worktrees do not receive ignored files like `.env`. The wrapper resolves the common git directory, sources credentials from the primary repo checkout, and then launches OpenCode from the worktree with repo-local XDG paths.

## Smoke commands

From the isolated worktree:

```bash
bash ./scripts/opencode_env.sh --version
bash ./scripts/opencode_env.sh models openrouter | rg 'deepseek|kimi|moonshot'
bash ./scripts/opencode_env.sh run \
  --dir "$PWD" \
  --model openrouter/deepseek/deepseek-chat-v3.1 \
  --format json \
  --dangerously-skip-permissions \
  "Reply with exactly the word OK."
bash ./scripts/opencode_env.sh run \
  --dir "$PWD" \
  --model openrouter/moonshotai/kimi-k2 \
  --format json \
  --dangerously-skip-permissions \
  "Reply with exactly the word OK."
```

## Backlog-clearing loop

1. Codex reads a Linear issue and rewrites it into a tight implementation brief.
2. Codex creates or selects an isolated feature worktree for that issue.
3. Codex fills a prompt file from `.opencode/prompts/tradingagents-backlog-template.md`.
4. Codex launches OpenCode headlessly:

```bash
bash ./scripts/opencode_headless_task.sh \
  --issue DIO-32 \
  --agent tradingagents-implementer \
  --model openrouter/moonshotai/kimi-k2.5 \
  --prompt-file /absolute/path/to/filled-brief.md
```

5. If needed, Codex runs a second pass with:

```bash
bash ./scripts/opencode_headless_task.sh \
  --issue DIO-32-review \
  --agent tradingagents-reviewer \
  --model openrouter/deepseek/deepseek-v4-pro \
  --prompt-file /absolute/path/to/review-brief.md
```

6. Codex inspects the diff, runs tests, requests fixes if needed, and performs the final commit and merge.

## First backlog target

Start with the TradingAgents integration lane under:

- `DIO-29` — `Epic: Adopt TradingAgents as a research-debate engine`
- `DIO-32` — `Story: Add optional TradingAgents adapter flow`

Prefer agent-ready child tasks instead of sending a whole story into one session. Keep the brief aligned with the current Linear acceptance criteria: additive-by-default integration, exact failure messaging for missing dependency or credentials, fixture-friendly behavior, repo-local cache/memory paths, and no execution or broker semantics.

## Budget note

OpenCode exposes `stats` and `export` for usage and cost visibility, but the current CLI/docs do not expose a documented hard per-session dollar cap for self-managed OpenRouter usage. Treat the `~$2` target as a soft cap:

- one issue per session
- constrained prompt
- explicit model choice
- inspect `bash ./scripts/opencode_env.sh stats --project \"\" --models 10` after each run
