---
name: agent-team
description: Coordinate bounded parallel work under a gpt-6-sol, gpt-6.1-sol, or gpt-6-astra primary using Terra workers, an Astra UI/UX designer, and an optional Astra critic. Use for multi-agent task allocation, independent decision review, or delegating visual and interaction design execution. Includes setup and verification of the named Codex roles. Other primary models do not automatically adopt this team.
---

# Agent Team

The `gpt-6-sol`, `gpt-6.1-sol`, or `gpt-6-astra` primary owns requirements, architecture, authorization, integration, and final acceptance. This skill governs delegation; it does not change the primary model or require every task to use subagents. It is Codex-specific.

For installation, upgrade, drift, or removal, read [setup](references/setup.md). TOMLs in the plugin's [roles directory](../../roles) are the source of truth. Plugin installation alone does not register them. If a role is unavailable, report that limitation and continue work the primary can safely complete; do not silently substitute a model or install roles during an unrelated task.

## Respect the session scheduling mode

Follow the current session's native delegation instructions first. Determine Ultra from an explicit current-session mode or effort setting supplied by the runtime or user; do not infer it from the model name or the global config. The SessionStart event does not expose a documented effort field. If the mode is unavailable, follow native instructions and apply team defaults only where permitted.

In Ultra, the primary chooses whether and when to delegate, the number of agents, and general-agent model/effort settings where the client permits. General work may use the `default` agent with native selection or inheritance; `worker` and `luna_monitor` are optional specialists. The dispatch requirements and corrective-follow-up/critic-pass counts below are defaults for other levels, including xhigh, and do not constrain Ultra's native scheduling. Named-role duties and fixed model/effort settings, delegated review and UI/UX specialization, authorization boundaries, verification, and final acceptance still apply in both modes.

At other levels, use the team routing and delegation defaults below within the session's permission to delegate. This skill never overrides a runtime restriction on proactive delegation. Select the named `worker` for the Terra/high implementation path rather than relying on a global subagent default.

## Route by judgment required

| Role | Model / effort | Assign |
| --- | --- | --- |
| `worker` | `gpt-6.1-terra` / `high` | Bounded fact-finding, implementation, and defined checks; no independent review, plan drafting, or design recommendations. |
| `luna_monitor` | `gpt-6-luna` / `high` | Read-only, bounded CI and authorized non-production deployment monitoring; reports transitions and terminal evidence, not review or approval verdicts. |
| `uiux_designer` | `gpt-6-astra` / `medium` | Visual direction, layout, typography, interaction design, responsive states, implementation, and visual verification. |
| `astra_critic` | `gpt-6-astra` / `high` | Scoped independent, read-only code, plan, or architecture review; consequential tradeoffs, disputed assumptions, or conflicting evidence. |

The primary may review directly. When delegating independent code, plan, or architecture review, select `agent_type = "astra_critic"`; never use a worker, monitor, or generic role. Keep UI/UX review with `uiux_designer`. Route by the required judgment, not the task name: collecting CI status or running defined checks may go to the worker or monitor, but assessing correctness, risks, or plan gaps as an independent reviewer may not. The worker may still diagnose bugs and self-check assigned implementation. If the review role is unavailable, the primary reviews directly; do not downgrade it to the worker or monitor.

An interface can be small in code yet require design judgment: route it to `uiux_designer`. The worker may own separate API/data plumbing or mechanical changes within an already accepted design system. Decisions affecting visual hierarchy or interaction behavior stay with the designer. The designer is an executor and may edit its assigned UI files.

Once the primary understands the question and can define independent work, delegate a suitable package while continuing useful independent work. Do not complete the same exploration first or fragment a trivial edit to create a delegation. Use multiple workers only when ownership does not overlap and coordination has a clear benefit. Tightly coupled decisions and changes remain with the primary.

For a long-running CI or non-production rollout, route bounded status observation to `luna_monitor` when it can proceed independently. Give the exact pipeline or deployment target, expected ref, polling interval, deadline, and terminal conditions. For a single CI pipeline, a background `pipeline-wait` may be simpler. The monitor reports evidence and changes in state; the primary decides whether to proceed, investigate, or accept the result. Actual deployment and remediation stay with the primary under the user's authorization.

The `gpt-6-sol`, `gpt-6.1-sol`, or `gpt-6-astra` primary must formulate the overall plan, compare approaches, set scope, decompose tasks, and order implementation. During planning, the worker may investigate explicit factual questions and return evidence and unknowns only; do not delegate plan drafting or design recommendations, even as a draft for primary review. If the work needs planning judgment, keep it with the primary rather than relabeling it as exploration. Independent review by the critic does not replace this ownership.

The named roles fix their own model and effort; spawn overrides do not change those settings. Confirm the role is exposed before dispatch; after launch, verify its actual role and effective model/effort from runtime metadata, not `task_name`. If these cannot be verified, do not rely on that child for independent review. Only the primary schedules agents. Children must not spawn further agents. The separate Luna-primary `astra_advisor` workflow is outside this team and should not be triggered simultaneously with this workflow.

## Give an executable assignment

Specify the objective, allowed reads/changes, prohibited actions, relevant contracts, and concrete acceptance evidence. Include the unique absolute working directory and baseline ref/SHA for Git work; the child must stop on a mismatch. Tell every executor that it shares the workspace and must preserve other work.

Pass only necessary safe context and applicable authorization limits. Use a fresh or narrow context when sufficient; never forward secrets, PII, raw production logs, production operations, or destructive operations. Delegation does not expand authorization. Include visual references and existing design constraints for UI work.

Check that the child actually starts. Reuse its thread for a related correction when useful. Allow at most one corrective follow-up for a package; if it still needs a different direction, the primary diagnoses and redesigns or takes over. A missing dependency or ordinary test failure does not automatically require a critic.

## Use independent review selectively

Give `astra_critic` the original question, constraints, competing options, and safe evidence. Label a proposed answer as a hypothesis. Ask for concrete counterexamples or missing evidence, rather than endorsement of the primary's conclusion.

Use at most one critic pass by default per task. Use it for requested or useful independent review, including before execution when a disputed assumption determines the approach or during acceptance when new evidence raises a consequential question. A later pass needs a new substantive question or evidence identified by the primary. Not every implementation needs a critic.

The critic advises; the primary decides. No opinion replaces tests, browser acceptance, user design feedback, or current runtime readback.

For disputed designs or rules, use ablation experiments (消融实验) when needed to test necessity. Reuse the existing team; do not add a role. The primary handles straightforward cases; the critic can assess what to keep, simplify, or defer, with evidence, what would be lost, and the smallest useful check. Keeping the current design is valid; fewer lines alone are not success.

When review cannot resolve the benefit, the primary defines a baseline, acceptance criteria, and experiment bounds, then routes isolated, authorized variants through the existing roles. Change only the disputed element and repeat comparisons when variability matters. Distinguish measured results from judgment and report inconclusive evidence without forcing a change.

## Integrate and finish

Each child reports its result, files, verification actually performed, failures/retries, and unverified items. The primary independently checks critical changes and evidence, resolves contradictions, and verifies the integrated result. For UI work, obtain rendered/browser evidence where available; compilation alone does not establish visual quality. State when rendering is unavailable.

Complete or interrupt all children before the final answer. Report local changes, installation, commit/push, deployment, and runtime acceptance separately. Internal review does not authorize external writes or deployment.
