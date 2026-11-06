# Install and maintain Agent Team

This plugin is for local Codex clients with custom TOML agents. The role manager currently supports macOS/Linux, requires Python 3.11 or newer, and uses only the standard library. Choose a Python executable meeting that requirement for the commands below. The source roles are `worker` (`gpt-6.1-terra` / `high`), `luna_monitor` (`gpt-6-luna` / `high`), `astra_critic` (`gpt-6-astra` / `high`), and `uiux_designer` (`gpt-6-astra` / `medium`). Their fixed model/effort settings are not changed by spawn arguments.

## Install the plugin and roles

Clone the repository with an authorized GitHub account and register its local marketplace:

```bash
gh repo clone zed76r/codex-agent-team
cd codex-agent-team
codex plugin marketplace add .
codex plugin add agent-team@agent-team-dev
codex plugin list
```

Find the actual installed plugin root from the list output. Use that installed root for role management; do not guess a cache version directory. Set a task-specific variable to that absolute path:

```bash
TEAM_PLUGIN_ROOT=/absolute/path/to/installed/agent-team
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" plan
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" install
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" status
```

`plan` is read-only. `install` deploys or updates only the four named roles under `$CODEX_HOME/agents/`, or `~/.codex/agents/` when `CODEX_HOME` is unset. `--codex-home /absolute/path` selects another Codex home, including an isolated test directory. The tool records ownership under that home's `agent-team/` directory. It does not edit `config.toml`, `AGENTS.md`, other agents, skills, credentials, or plugin registries. Existing ownership state is accepted. On upgrade, `install` retires a managed `luna_worker` and installs `worker`; it preserves the old ownership record and original backup for uninstall, and refuses drift or an unmanaged `worker`. A custom `worker` takes precedence over the built-in worker role.

Installation is an explicit local configuration action. A role missing during ordinary task execution does not authorize installing it. Preserve the user's current primary model, permission settings, and unrelated plugin configuration.

## Existing files and drift

An unmanaged same-name role is a conflict by default. Review its difference from the corresponding source TOML before choosing to adopt it. Compute the SHA-256 of the reviewed local file, then pass the exact expected value:

```bash
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" plan --adopt "worker=<reviewed-sha256>"
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" install --adopt "worker=<reviewed-sha256>"
```

Replace the placeholder before running the command. Adoption is explicit and conditional on that exact content. The tool saves the original role so uninstall can restore it. Do not take over an unrelated role merely because its name matches.

For a managed role, local edits block update or uninstall. Inspect and reconcile those edits with the repository source; adoption must not bypass managed-file drift. If a transaction is incomplete, inspect `agent-team/pending.json` and run `python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" recover` to restore its before-state after the recorded owner process has stopped. Recovery refuses a live owner or files changed outside the recorded transaction. A reused process ID can conservatively block recovery; inspect it rather than deleting the record. Do not remove ownership records or backups to suppress a conflict. Original backups are retained after uninstall for inspection.

Commands emit JSON operation metadata without file contents. Exit 0 means the requested operation succeeded (or a plan is safe to apply); `status` exits 1 when installation/update is needed; exit 2 indicates a conflict or I/O error. An ordinary write failure attempts rollback. An interrupted or blocked rollback retains the journal for explicit recovery.

## Update and remove

Update the plugin through the repository's normal version/cachebuster and reinstall flow, then run the role manager's `plan`, `install`, and `status` again from the new installed root. The installed TOMLs are managed copies; edit the repository's `roles/` files for durable changes.

To remove roles, first check status and then run:

```bash
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" uninstall
```

Uninstall restores adopted originals and removes roles created by this installation only when their current contents still match the recorded installed contents. Remove the plugin through `codex plugin remove agent-team@agent-team-dev` afterward. Plugin removal alone does not unregister copied role TOMLs. If using another marketplace, substitute the actual selector.

## Activate and verify

Start a new Codex thread after role installation or update. Confirm all four named roles are exposed, then run small, safe assignments and verify the actual child role and effective model/effort in runtime metadata. `task_name`, TOML parsing, plugin validation, and matching version labels do not establish runtime discovery or model execution. If the review role is unavailable or unverified, the primary reviews directly; never downgrade independent review to the worker, monitor, or a generic role.

For automatic routing, review and trust the bundled `SessionStart` hook in `/hooks` (desktop: **Settings > Hooks**). It injects only this skill's entrypoint for `gpt-6-sol`, `gpt-6.1-sol`, and `gpt-6-astra`, on startup, resume, clear, compact, and fork. Other models and identified child agents receive no entrypoint. It does not install roles or activate the separate Luna-primary advisor. Keep authorization, production access, credentials, tunnels, and machine-specific constraints in their existing local guidance.

No global `AGENTS.md` entry is needed once hook injection is verified. When migrating an existing installation, first review the new hook and observe its injected context in a fresh thread, then remove redundant global delegation instructions and their local guide. Hook installation, trust, injection, and actual child execution are separate checks. Updated scripts may require renewed trust; do not edit trust records or bypass review. If hooks are disabled or untrusted, invoke `$agent-team` explicitly. Restart with the desired primary model after switching models so the model-scoped entrypoint is reevaluated.

Explicitly select `astra_critic` for delegated independent code, plan, or architecture review and consequential tradeoffs; keep UI/UX review with `uiux_designer`. The primary may review directly. Do not trigger duplicate analysis by default.

The separate `astra_advisor` and `astra_advisor_xhigh` roles for a Luna primary are not owned by this plugin and should not be triggered simultaneously with this plugin's workflow. UI/UX work can use installed design/browser skills, but the plugin does not install or vendor third-party skills.

The critic has a read-only default and an explicit no-write instruction. Runtime permission inheritance can override a default; verify effective permissions when isolation matters. All role assignments must still preserve the parent task's read/write authorization.
