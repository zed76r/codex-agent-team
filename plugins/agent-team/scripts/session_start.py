"""Inject the installed skill entrypoint without copying its delegation rules."""

import json
from pathlib import Path
import sys


def main():
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        print("Agent Team: invalid hook input", file=sys.stderr)
        return 1
    if not isinstance(event, dict):
        print("Agent Team: expected a hook object", file=sys.stderr)
        return 1
    if (
        event.get("hook_event_name") != "SessionStart"
        or event.get("source") not in ("startup", "resume", "clear", "compact", "fork")
        or event.get("model") not in ("gpt-6-sol", "gpt-6.1-sol", "gpt-6-astra")
        or event.get("agent_id")
    ):
        return 0
    skill = Path(__file__).resolve().parents[1] / "skills/agent-team/SKILL.md"
    context = (
        "Agent Team entrypoint (primary agent only): before planning non-trivial work, "
        f"read and follow the installed $agent-team skill at {skill}. "
        "This skill requests bounded delegation when independent work would materially "
        "improve speed or quality; read it before deciding whether to delegate. "
        "The primary chooses the useful work packages and retains final acceptance. "
        "Handle trivial or tightly coupled work directly. Follow native session "
        "instructions; do not infer delegation permissions from reasoning effort. "
        "Delegation never expands user authorization; preserve local safety and "
        "sensitive-data constraints. If you are a delegated child, do not delegate again. "
        "If the skill or a required role is unavailable, report it and continue safely "
        "as primary without silently substituting models or installing roles."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": context,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
