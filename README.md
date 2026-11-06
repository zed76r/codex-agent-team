# Codex Agent Team

A standalone Codex plugin for a `gpt-6-sol`, `gpt-6.1-sol`, or `gpt-6-astra` primary working with bounded Terra, Luna, and Astra specialists.

## Responsibilities

| Role | Model / effort | Responsibility |
| --- | --- | --- |
| Primary | `gpt-6-sol`, `gpt-6.1-sol`, or `gpt-6-astra` | Requirements, architecture, overall plans, approach comparisons, scope, task decomposition, implementation order, integration, and final acceptance. |
| `worker` | `gpt-6.1-terra` / `high` | Bounded fact-finding, implementation, and defined checks; no independent review, plan drafting, or design recommendations. |
| `luna_monitor` | `gpt-6-luna` / `high` | Read-only, bounded monitoring of CI and authorized non-production rollouts; reports state changes and terminal evidence, without independent review, deployment, or remediation. |
| `uiux_designer` | `gpt-6-astra` / `medium` | Visual and interaction design, UI implementation, and rendered verification. |
| `astra_critic` | `gpt-6-astra` / `high` | Scoped independent, read-only review of code, plans, architecture, consequential tradeoffs, or disputed assumptions. |

The primary retains planning judgment and may review directly. Terra workers may execute defined checks, collect evidence, diagnose bugs, and self-check assigned implementation; they do not perform independent review or issue review findings, risk assessments, or approval verdicts. Delegation does not expand user authorization, and child agents must not delegate again.

For delegated independent code, plan, or architecture review, explicitly select `astra_critic`; keep UI/UX review with `uiux_designer`. Route by the required judgment, not the task name. Independent review remains optional, with at most one critic pass by default per task. If the review role is unavailable or unverified, the primary reviews directly instead of using a worker, monitor, or generic role.

## Install

Requires a Codex client supporting plugins and named TOML agents, access to the configured models, and Python 3.11+ on macOS/Linux for role management.

Clone this repository using a GitHub account with access:

```bash
gh repo clone zed76r/codex-agent-team
cd codex-agent-team
codex plugin marketplace add .
codex plugin add agent-team@agent-team-dev
codex plugin list
```

`agent-team-dev` is the existing marketplace identifier, retained for local installation compatibility. The plugin itself is named `agent-team`.

Use the installed plugin root printed by the CLI, not the repository root:

```bash
TEAM_PLUGIN_ROOT=/absolute/path/to/installed/agent-team
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" plan
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" install
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" status
```

Plugin installation and role registration are separate steps. Existing unmanaged roles or edited managed files can block installation; see the [setup guide](plugins/agent-team/skills/agent-team/references/setup.md) for ownership, adoption, recovery, and removal.

Review and trust the plugin's hook in Codex `/hooks` (desktop: **Settings > Hooks**), then start a new thread. The `SessionStart` hook injects a short `$agent-team` entrypoint for `gpt-6-sol`, `gpt-6.1-sol`, and `gpt-6-astra`, including after resume, clear, compaction, or fork. Delegation rules remain in the skill; no global `AGENTS.md` entry is required. The hook reads only its event input and emits context; it does not install roles, change permissions, or start agents. Other models, including Luna, receive no entrypoint. You can still invoke `$agent-team` explicitly when hooks are unavailable or disabled.

After launch, verify the actual child role and effective model/effort from runtime metadata; `task_name` alone is not proof. The plugin does not change the primary model or require delegation for every task. The separate Luna-primary `astra_advisor` workflow is outside this plugin; do not trigger it simultaneously with `$agent-team`.

## Repository contents

- `.agents/plugins/marketplace.json`: the portable local marketplace entry.
- `plugins/agent-team/skills/agent-team/`: delegation rules and setup documentation.
- `plugins/agent-team/hooks/hooks.json` and `scripts/session_start.py`: the model-scoped session entrypoint.
- `plugins/agent-team/roles/`: source templates for the four managed roles.
- `plugins/agent-team/scripts/manage_agents.py`: ownership-aware role installation and recovery.
- `plugins/agent-team/tests/`: isolated role-manager and hook tests.

Personal `AGENTS.md` files, machine-specific constraints, credentials, installed role copies, ownership state, backups, and plugin caches are not part of this repository. Maintain role templates here and synchronize installed copies with the manager; do not edit managed copies directly.

## Validation

Run the existing tests from the repository root using Python 3.11+:

```bash
python3 -B -m unittest discover -s plugins/agent-team/tests -v
```

Tests use temporary directories rather than the active Codex home. They cover role-manager behavior and the packaged hook command, including paths with spaces, model/source routing, child suppression, and malformed input. Passing tests does not establish hook trust, actual runtime injection, or model availability in a fresh Codex thread.
