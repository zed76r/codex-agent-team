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
        "Agent Team entrypoint (primary agent only): read and follow the installed "
        f"$agent-team skill at {skill} when coordinating suitable independent work. "
        "The skill owns role selection, handoff, verification and agent cleanup. "
        "Do not force delegation for trivial or tightly coupled work. "
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
