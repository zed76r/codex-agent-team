import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]


class SessionStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent team ")
        self.addCleanup(self.temp.cleanup)
        self.plugin = Path(self.temp.name) / "installed plugin"
        shutil.copytree(PLUGIN, self.plugin)
        manifest = json.loads((self.plugin / ".codex-plugin/plugin.json").read_text())
        hooks = json.loads((self.plugin / manifest["hooks"]).read_text())["hooks"]
        self.assertEqual(list(hooks), ["SessionStart"])
        self.group, = hooks["SessionStart"]
        self.handler, = self.group["hooks"]

    def run_hook(self, payload):
        return subprocess.run(
            self.handler["command"], shell=True,
            input=payload, text=True, capture_output=True,
            cwd=self.temp.name,
            env={**os.environ, "PLUGIN_ROOT": str(self.plugin)},
            timeout=self.handler["timeout"],
        )

    def event(self, **overrides):
        return {"hook_event_name": "SessionStart", "source": "startup",
                "model": "gpt-6.1-sol", **overrides}

    def test_supported_models_and_lifecycle_sources(self):
        for model in ["gpt-6-sol", "gpt-6.1-sol", "gpt-6-astra"]:
            for source in ["startup", "resume", "clear", "compact", "fork"]:
                with self.subTest(model=model, source=source):
                    self.assertIsNotNone(re.fullmatch(self.group["matcher"], source))
                    result = self.run_hook(json.dumps(self.event(model=model, source=source)))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    output = json.loads(result.stdout)["hookSpecificOutput"]
                    self.assertEqual(output["hookEventName"], "SessionStart")
                    context = output["additionalContext"]
                    self.assertIn(str(self.plugin / "skills/agent-team/SKILL.md"), context)
                    self.assertIn("$agent-team", context)
                    self.assertIn("never expands user authorization", context)
                    self.assertNotIn("astra-advisor", context)
                    self.assertLess(len(context), 1500)

    def test_unsupported_models_events_and_children_are_silent(self):
        for override in [{"model": "gpt-6-luna"}, {"model": "gpt-6.1-terra"},
                         {"model": "unknown"}, {"model": None}, {"model": []},
                         {"hook_event_name": "SubagentStart"},
                         {"source": "unknown"}, {"source": {}}, {"agent_id": "child"}]:
            with self.subTest(override=override):
                result = self.run_hook(json.dumps(self.event(**override)))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
        result = self.run_hook("{}")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_malformed_input_is_reported_without_echoing_payload(self):
        for payload in ['{"private-marker":', '[]', 'null']:
            result = self.run_hook(payload)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("Agent Team:", result.stderr)
            self.assertNotIn("private-marker", result.stderr)


if __name__ == "__main__":
    unittest.main()
