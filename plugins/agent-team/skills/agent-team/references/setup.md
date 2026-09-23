# Install and maintain Agent Team

This plugin is for local Codex clients with custom TOML agents. The role manager currently supports macOS/Linux, requires Python 3.11 or newer, and uses only the standard library. Choose a Python executable meeting that requirement for the commands below. The source roles are `luna_worker` (`gpt-6-luna` / `max`), `luna_monitor` (`gpt-6-luna` / `high`), `astra_critic` (`gpt-6-astra` / `high`), and `uiux_designer` (`gpt-6-astra` / `medium`). Their fixed model/effort settings are not changed by spawn arguments.

## Install the plugin and roles

Clone the private repository with an authorized GitHub account and register its local marketplace:

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

`plan` is read-only. `install` deploys or updates only the four named roles under `$CODEX_HOME/agents/`, or `~/.codex/agents/` when `CODEX_HOME` is unset. `--codex-home /absolute/path` selects another Codex home, including an isolated test directory. The tool records ownership under that home's `agent-team/` directory. It does not edit `config.toml`, `AGENTS.md`, other agents, skills, credentials, or plugin registries. Existing three-role ownership state is accepted so `install` can add `luna_monitor` without adopting or replacing unrelated files.

Installation is an explicit local configuration action. A role missing during ordinary task execution does not authorize installing it. Preserve the user's current primary model, permission settings, and unrelated plugin configuration.

## Existing files and drift

An unmanaged same-name role is a conflict by default. Review its difference from the corresponding source TOML before choosing to adopt it. Compute the SHA-256 of the reviewed local file, then pass the exact expected value:

```bash
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" plan --adopt "luna_worker=<reviewed-sha256>"
python3 "$TEAM_PLUGIN_ROOT/scripts/manage_agents.py" install --adopt "luna_worker=<reviewed-sha256>"
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

Start a new Codex thread after role installation or update. Confirm all four named roles are exposed, then run small, safe assignments through each role and check the actual child results. TOML parsing, plugin validation, and matching version labels do not establish runtime discovery or model execution.

For automatic routing under a `gpt-6-sol` or `gpt-6-astra` primary, a user or project `AGENTS.md` may contain a short `$agent-team` entrypoint. Keep authorization, production access, credentials, tunnels, and machine-specific constraints in their existing local guidance. Do not copy those settings into the shared plugin.

When a `gpt-6-sol` primary needs Astra judgment on a key tradeoff, route it to `astra_critic`; when a `gpt-6-astra` primary only needs an independent opinion, use the critic. Do not trigger duplicate analysis by default.

The separate `astra_advisor` and `astra_advisor_xhigh` roles for a Luna primary are not owned by this plugin and should not be triggered simultaneously with this plugin's workflow. UI/UX work can use installed design/browser skills, but the plugin does not install or vendor third-party skills.

The critic has a read-only default and an explicit no-write instruction. Runtime permission inheritance can override a default; verify effective permissions when isolation matters. All role assignments must still preserve the parent task's read/write authorization.
