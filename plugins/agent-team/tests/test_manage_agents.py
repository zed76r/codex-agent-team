from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

PLUGIN = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("manage_agents", PLUGIN / "scripts/manage_agents.py")
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


class AgentManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "codex"
        self.plugin = self.base / "plugin"
        shutil.copytree(PLUGIN / "roles", self.plugin / "roles")
        (self.plugin / ".codex-plugin").mkdir()
        shutil.copyfile(PLUGIN / ".codex-plugin/plugin.json", self.plugin / ".codex-plugin/plugin.json")

    def run_action(self, action, adopt=None):
        return manager.execute(action, self.root, adopt, self.plugin)

    def target(self, name="worker"):
        return self.root / "agents" / f"{name}.toml"

    def existing(self, name="worker", data=b"original local role\n"):
        path = self.target(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data

    def test_plan_does_not_create_home(self):
        self.assertEqual(self.run_action("plan")["status"], "changes_required")
        self.assertFalse(self.root.exists())

    def test_install_idempotence_and_status(self):
        self.assertEqual(self.run_action("install")["status"], "installed")
        snapshot = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(self.run_action("install")["status"], "current")
        self.assertEqual(self.run_action("status")["status"], "current")
        self.assertEqual(snapshot, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_managed_update(self):
        self.run_action("install")
        source = self.plugin / "roles/worker.toml"
        source.write_text(source.read_text() + "\n# new revision\n")
        self.assertEqual(self.run_action("status")["status"], "changes_required")
        self.run_action("install")
        self.assertEqual(self.target().read_bytes(), source.read_bytes())

    def test_upgrade_adds_monitor_to_existing_three_role_state(self):
        self.run_action("install")
        state_path = self.root / manager.STATE
        state = json.loads(state_path.read_text())
        state["roles"].pop("luna_monitor")
        state_path.write_bytes(manager.json_bytes(state))
        self.target("luna_monitor").unlink()

        self.assertEqual(self.run_action("status")["status"], "changes_required")
        self.assertEqual(self.run_action("install")["status"], "installed")
        self.assertEqual(self.target("luna_monitor").read_bytes(),
                         (self.plugin / "roles/luna_monitor.toml").read_bytes())
        self.assertEqual(self.run_action("status")["status"], "current")

    def install_legacy_worker(self, original=None):
        source = self.plugin / "roles/worker.toml"
        legacy = self.plugin / "roles/luna_worker.toml"
        legacy.write_text(source.read_text().replace('name = "worker"', 'name = "luna_worker"'))
        adopt = None
        if original is not None:
            self.existing("luna_worker", original)
            adopt = {"luna_worker": manager.digest(original)}
        roles = ("luna_worker", *manager.ROLES[1:])
        with mock.patch.object(manager, "ROLES", roles):
            self.run_action("install", adopt)
        legacy.unlink()

    def test_worker_model_contract(self):
        role = manager.tomllib.loads((self.plugin / "roles/worker.toml").read_text())
        self.assertEqual(role["name"], "worker")
        self.assertEqual(role["model"], "gpt-6.1-terra")
        self.assertEqual(role["model_reasoning_effort"], "high")

    def test_upgrade_retires_legacy_worker_and_preserves_original(self):
        original = b"original legacy role\n"
        self.install_legacy_worker(original)
        snapshot = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(self.run_action("plan")["status"], "changes_required")
        self.assertEqual(snapshot, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.run_action("install")
        self.assertFalse(self.target("luna_worker").exists())
        self.assertEqual(self.target().read_bytes(), (self.plugin / "roles/worker.toml").read_bytes())
        state = json.loads((self.root / manager.STATE).read_text())
        self.assertIsNone(state["roles"]["luna_worker"]["installed_sha256"])
        self.assertEqual(self.run_action("status")["status"], "current")
        self.assertEqual(self.run_action("install")["status"], "current")
        self.run_action("uninstall")
        self.assertEqual(self.target("luna_worker").read_bytes(), original)
        self.assertFalse(self.target().exists())

    def test_upgrade_refuses_unmanaged_worker(self):
        self.install_legacy_worker()
        self.existing(data=b"unrelated worker")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(manager.Conflict, "unmanaged same-name"):
            self.run_action("install")
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_legacy_worker_drift_blocks_upgrade_and_retired_recreation(self):
        self.install_legacy_worker()
        legacy = self.target("luna_worker")
        installed = legacy.read_bytes()
        legacy.write_bytes(b"manual change")
        with self.assertRaisesRegex(manager.Conflict, "managed role drift"):
            self.run_action("install")
        self.assertFalse(self.target().exists())
        legacy.write_bytes(installed)
        self.run_action("install")
        legacy.write_bytes(b"new unrelated role")
        for action in ("install", "uninstall"):
            with self.subTest(action=action), self.assertRaisesRegex(manager.Conflict, "managed role drift"):
                self.run_action(action)
        self.assertEqual(legacy.read_bytes(), b"new unrelated role")

    def test_worker_migration_rolls_back_on_failure(self):
        self.install_legacy_worker()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        original = manager.atomic_change

        def injected(path, old, new):
            if path == self.target("luna_worker") and new is None:
                raise OSError("injected retirement failure")
            return original(path, old, new)

        with mock.patch.object(manager, "atomic_change", side_effect=injected):
            with self.assertRaisesRegex(manager.Conflict, "rolled back"):
                self.run_action("install")
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_unknown_conflict_prevents_all_writes(self):
        original = self.existing("uiux_designer")
        with self.assertRaises(manager.Conflict):
            self.run_action("install")
        self.assertFalse(self.target().exists())
        self.assertFalse((self.root / "agent-team").exists())
        self.assertEqual(self.target("uiux_designer").read_bytes(), original)

    def test_adopt_then_update_and_uninstall_restores_original(self):
        original = self.existing()
        self.run_action("install", {"worker": manager.digest(original)})
        source = self.plugin / "roles/worker.toml"
        source.write_text(source.read_text() + "\n# update\n")
        self.run_action("install")
        unrelated = self.target("unrelated")
        unrelated.write_text("preserve")
        self.run_action("uninstall")
        self.assertEqual(self.target().read_bytes(), original)
        self.assertEqual(unrelated.read_text(), "preserve")
        self.assertFalse(self.target("astra_critic").exists())
        self.assertFalse(self.target("uiux_designer").exists())

    def test_stale_adoption_hash_refused(self):
        self.existing()
        with self.assertRaises(manager.Conflict):
            self.run_action("install", {"worker": "0" * 64})

    def test_hand_edited_managed_role_blocks_update_and_uninstall(self):
        self.run_action("install")
        self.target().write_text("manual edit")
        for action in ("install", "uninstall"):
            with self.subTest(action=action), self.assertRaises(manager.Conflict):
                self.run_action(action)
        with self.assertRaises(manager.Conflict):
            self.run_action("install", {"worker": manager.digest(b"manual edit")})
        self.assertEqual(self.target().read_text(), "manual edit")

    def test_symlink_role_and_parent_refused(self):
        self.root.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        (self.root / "agents").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(manager.Conflict):
            self.run_action("install")
        self.assertEqual(list(outside.iterdir()), [])
        (self.root / "agents").unlink()
        self.target().parent.mkdir()
        (outside / "role").write_text("preserve")
        self.target().symlink_to(outside / "role")
        with self.assertRaises(manager.Conflict):
            self.run_action("install")
        self.assertEqual((outside / "role").read_text(), "preserve")

    def test_failure_rolls_back_partial_install(self):
        original = manager.atomic_change
        failed = False

        def injected(path, before, after):
            nonlocal failed
            if path == self.target("astra_critic") and not failed:
                failed = True
                raise OSError("injected write failure")
            return original(path, before, after)

        with mock.patch.object(manager, "atomic_change", side_effect=injected):
            with self.assertRaisesRegex(manager.Conflict, "rolled back"):
                self.run_action("install")
        self.assertFalse(self.target().exists())
        self.assertFalse((self.root / manager.STATE).exists())
        self.assertFalse((self.root / manager.PENDING).exists())

    def test_interrupted_transaction_recovery(self):
        original = manager.atomic_change

        def killed(path, before, after):
            if path == self.target("astra_critic"):
                raise KeyboardInterrupt()
            return original(path, before, after)

        with mock.patch.object(manager, "atomic_change", side_effect=killed):
            with self.assertRaises(KeyboardInterrupt):
                self.run_action("install")
        self.assertTrue(self.target().exists())
        with self.assertRaisesRegex(manager.Conflict, "pending transaction"):
            self.run_action("install")
        with mock.patch.object(manager.os, "kill", side_effect=ProcessLookupError):
            self.assertEqual(self.run_action("recover")["status"], "restored")
        self.assertFalse(self.target().exists())

    def test_recovery_does_not_overwrite_concurrent_edits(self):
        self.root.mkdir()
        self.existing(data=b"concurrent")
        pending = self.root / manager.PENDING
        pending.parent.mkdir()
        pending.write_bytes(manager.json_bytes({"schema": 1, "owner_pid": manager.os.getpid(), "changes": {
            "agents/worker.toml": {"before": None, "after": manager.encode(b"installed")}
        }}))
        with mock.patch.object(manager.os, "kill", side_effect=ProcessLookupError):
            with self.assertRaisesRegex(manager.Conflict, "concurrent"):
                self.run_action("recover")
        self.assertEqual(self.target().read_bytes(), b"concurrent")
        self.assertTrue(pending.exists())

    def test_invalid_state_and_transaction_paths_refused(self):
        self.run_action("install")
        path = self.root / manager.STATE
        state = json.loads(path.read_text())
        state["roles"]["worker"]["original"] = {"path": "../../outside", "sha256": "0" * 64}
        path.write_text(json.dumps(state))
        with self.assertRaises(manager.Conflict):
            self.run_action("uninstall")
        pending = self.root / manager.PENDING
        pending.write_bytes(manager.json_bytes({"schema": 1, "owner_pid": manager.os.getpid(), "changes": {
            "../outside": {"before": None, "after": manager.encode(b"bad")}
        }}))
        with self.assertRaises(manager.Conflict):
            self.run_action("recover")

    def test_original_backup_drift_blocks_uninstall(self):
        original = self.existing()
        self.run_action("install", {"worker": manager.digest(original)})
        state = json.loads((self.root / manager.STATE).read_text())
        backup = self.root / "agent-team" / state["roles"]["worker"]["original"]["path"]
        backup.write_text("changed")
        with self.assertRaises(manager.Conflict):
            self.run_action("uninstall")

    def test_journal_flush_failure_leaves_no_pending_record(self):
        with mock.patch.object(manager.os, "fsync", side_effect=OSError("journal I/O failure")):
            with self.assertRaises(OSError):
                self.run_action("install")
        self.assertFalse((self.root / manager.PENDING).exists())
        self.assertFalse(self.target().exists())
        self.assertEqual(self.run_action("install")["status"], "installed")

    def test_change_before_journal_claim_is_not_rolled_back(self):
        original = manager.os.link

        def concurrent(source, destination):
            self.existing(data=b"other writer")
            return original(source, destination)

        with mock.patch.object(manager.os, "link", side_effect=concurrent):
            with self.assertRaisesRegex(manager.Conflict, "after transaction claim"):
                self.run_action("install")
        self.assertEqual(self.target().read_bytes(), b"other writer")
        self.assertFalse((self.root / manager.PENDING).exists())

    def test_deletion_rechecks_content(self):
        self.existing(data=b"before")
        original = manager.read
        calls = 0

        def concurrent(path):
            nonlocal calls
            if path == self.target():
                calls += 1
                if calls == 2:
                    path.write_bytes(b"other writer")
            return original(path)

        with mock.patch.object(manager, "read", side_effect=concurrent):
            with self.assertRaises(manager.Conflict):
                manager.atomic_change(self.target(), b"before", None)
        self.assertEqual(self.target().read_bytes(), b"other writer")

    def test_recovery_refuses_live_transaction_owner(self):
        pending = self.root / manager.PENDING
        pending.parent.mkdir(parents=True)
        pending.write_bytes(manager.json_bytes({"schema": 1, "owner_pid": manager.os.getpid(), "changes": {
            "agents/worker.toml": {"before": None, "after": manager.encode(b"installed")}
        }}))
        with self.assertRaisesRegex(manager.Conflict, "still be running"):
            self.run_action("recover")
        self.assertTrue(pending.exists())


if __name__ == "__main__":
    unittest.main()
