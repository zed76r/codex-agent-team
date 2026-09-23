#!/usr/bin/env python3
"""Manage Agent Team roles on macOS/Linux. Requires Python 3.11+."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
if sys.version_info < (3, 11):
    raise SystemExit("Agent Team role management requires Python 3.11 or newer.")
import tomllib
import uuid

ROLES = ("luna_worker", "luna_monitor", "astra_critic", "uiux_designer")
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STATE = "agent-team/state.json"
PENDING = "agent-team/pending.json"
TARGETS = {STATE, *(f"agents/{name}.toml" for name in ROLES)}


class Conflict(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(path: Path) -> Path:
    path = path.absolute()
    for part in (*reversed(path.parents), path):
        if part.is_symlink():
            raise Conflict(f"symlink path refused: {part}")
    if path.exists() and not path.is_file() and not path.is_dir():
        raise Conflict(f"non-regular path refused: {path}")
    return path


def read(path: Path) -> bytes | None:
    safe_path(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise Conflict(f"expected regular file: {path}")
    return path.read_bytes()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def parse_json(raw: bytes, label: str) -> dict:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise Conflict(f"invalid {label}") from exc
    if not isinstance(data, dict):
        raise Conflict(f"invalid {label}")
    return data


def atomic_change(path: Path, before: bytes | None, after: bytes | None) -> None:
    if read(path) != before:
        raise Conflict(f"concurrent change: {path}")
    if before == after:
        return
    safe_path(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    if after is None:
        if read(path) != before:
            raise Conflict(f"concurrent change: {path}")
        path.unlink()
        return
    fd, temporary = tempfile.mkstemp(prefix=".agent-team-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
        if read(path) != before:
            raise Conflict(f"concurrent change: {path}")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_sources(plugin: Path) -> tuple[str, dict[str, bytes]]:
    manifest = parse_json(read(plugin / ".codex-plugin/plugin.json") or b"", "plugin manifest")
    if manifest.get("name") != "agent-team" or not isinstance(manifest.get("version"), str):
        raise Conflict("unexpected plugin identity/version")
    files = {}
    for name in ROLES:
        data = read(plugin / "roles" / f"{name}.toml")
        if data is None:
            raise Conflict(f"missing source role: {name}")
        try:
            role = tomllib.loads(data.decode())
        except (ValueError, UnicodeError) as exc:
            raise Conflict(f"invalid source role: {name}") from exc
        if role.get("name") != name or any(
            not isinstance(role.get(key), str) or not role[key].strip()
            for key in ("model", "model_reasoning_effort", "developer_instructions", "description")
        ):
            raise Conflict(f"invalid role contract: {name}")
        files[name] = data
    return manifest["version"], files


def load_state(root: Path) -> tuple[bytes | None, dict]:
    raw = read(root / STATE)
    if raw is None:
        return None, {"schema": 1, "version": None, "roles": {}}
    state = parse_json(raw, "ownership state")
    if (set(state) != {"schema", "version", "roles"} or state["schema"] != 1
            or not isinstance(state["version"], str)
            or not isinstance(state["roles"], dict)
            or not state["roles"] or not set(state["roles"]) <= set(ROLES)):
        raise Conflict("invalid ownership state")
    for name, record in state["roles"].items():
        if (not isinstance(record, dict) or set(record) != {"installed_sha256", "original"}
                or not re.fullmatch(r"[0-9a-f]{64}", str(record["installed_sha256"]))):
            raise Conflict(f"invalid ownership record: {name}")
        original = record["original"]
        if original is not None:
            if (not isinstance(original, dict) or set(original) != {"path", "sha256"}
                    or not re.fullmatch(rf"backups/[0-9a-f]{{32}}-{name}\.toml", str(original["path"]))
                    or not re.fullmatch(r"[0-9a-f]{64}", str(original["sha256"]))):
                raise Conflict(f"invalid original backup record: {name}")
            data = read(root / "agent-team" / original["path"])
            if data is None or digest(data) != original["sha256"]:
                raise Conflict(f"missing or changed original backup: {name}")
    return raw, state


def parse_adoptions(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        name, sep, sha = value.partition("=")
        if name not in ROLES or not sep or not re.fullmatch(r"[0-9a-f]{64}", sha) or name in result:
            raise Conflict("--adopt requires a unique known-role=SHA256")
        result[name] = sha
    return result


def encode(data: bytes | None) -> str | None:
    return None if data is None else base64.b64encode(data).decode()


def decode(data: object) -> bytes | None:
    if data is None:
        return None
    if not isinstance(data, str):
        raise Conflict("invalid transaction content")
    try:
        return base64.b64decode(data, validate=True)
    except ValueError as exc:
        raise Conflict("invalid transaction content") from exc


def recover(root: Path, *, own_transaction: bool = False) -> dict:
    raw = read(root / PENDING)
    if raw is None:
        return {"action": "recover", "status": "no_pending_transaction"}
    journal = parse_json(raw, "transaction journal")
    if (set(journal) != {"schema", "owner_pid", "changes"} or journal["schema"] != 1
            or type(journal["owner_pid"]) is not int or not 0 < journal["owner_pid"] <= 2**31 - 1
            or not isinstance(journal["changes"], dict)):
        raise Conflict("invalid transaction journal")
    if not journal["changes"] or not set(journal["changes"]) <= TARGETS:
        raise Conflict("invalid transaction target")
    if own_transaction:
        if journal["owner_pid"] != os.getpid():
            raise Conflict("transaction owner changed")
    else:
        try:
            os.kill(journal["owner_pid"], 0)
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            raise Conflict("transaction owner may still be running") from exc
        else:
            raise Conflict("transaction owner may still be running")
    changes = {}
    for rel, entry in journal["changes"].items():
        if not isinstance(entry, dict) or set(entry) != {"before", "after"}:
            raise Conflict("invalid transaction entry")
        before, after = decode(entry["before"]), decode(entry["after"])
        current = read(root / rel)
        if current not in (before, after):
            raise Conflict(f"recovery blocked by concurrent changes: {rel}")
        changes[rel] = (current, before)
    for rel, (current, before) in changes.items():
        atomic_change(root / rel, current, before)
    atomic_change(root / PENDING, raw, None)
    return {"action": "recover", "status": "restored", "files": sorted(changes)}


def transact(root: Path, changes: dict[str, tuple[bytes | None, bytes | None]], backups: dict[str, bytes]) -> None:
    # The exclusive journal also serializes invocations of this manager.
    for rel, (before, _) in changes.items():
        if read(root / rel) != before:
            raise Conflict(f"concurrent change: {rel}")
    pending = safe_path(root / PENDING)
    pending.parent.mkdir(parents=True, exist_ok=True)
    journal = json_bytes({"schema": 1, "owner_pid": os.getpid(), "changes": {
        rel: {"before": encode(before), "after": encode(after)}
        for rel, (before, after) in changes.items()
    }})
    # Publish only a complete, flushed journal. link() claims the destination
    # exclusively; a failed write cannot leave a truncated pending record.
    fd, temporary = tempfile.mkstemp(prefix=".agent-team-journal-", dir=pending.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(journal)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, pending)
        except FileExistsError as exc:
            raise Conflict("pending transaction exists; inspect and run recover") from exc
    finally:
        os.unlink(temporary)
    # Another invocation could have completed between planning and our claim.
    # No target has been changed yet: release only our journal on stale input.
    try:
        for rel, (before, _) in changes.items():
            if read(root / rel) != before:
                raise Conflict(f"concurrent change after transaction claim: {rel}")
    except Exception:
        atomic_change(pending, journal, None)
        raise
    try:
        for rel, data in backups.items():
            atomic_change(root / "agent-team" / rel, None, data)
        for rel, (before, after) in changes.items():
            atomic_change(root / rel, before, after)
        atomic_change(pending, journal, None)
    except Exception as exc:
        try:
            recover(root, own_transaction=True)
        except Exception as recovery_error:
            raise Conflict(f"transaction interrupted; recovery evidence retained: {recovery_error}") from exc
        raise Conflict(f"transaction failed and was rolled back: {type(exc).__name__}") from exc


def execute(action: str, root: Path, adopt: dict[str, str] | None = None, plugin: Path = PLUGIN_ROOT) -> dict:
    if os.name != "posix":
        raise Conflict("role management currently supports macOS/Linux only")
    root = safe_path(root.expanduser().absolute())
    adopt = adopt or {}
    if adopt and action not in ("plan", "install"):
        raise Conflict("--adopt is only valid with plan/install")
    if action == "recover":
        return recover(root)
    if read(root / PENDING) is not None:
        raise Conflict("pending transaction exists; inspect and run recover")
    before_state, state = load_state(root)
    version, sources = load_sources(plugin) if action != "uninstall" else (state["version"], {})
    changes, backups, records, report = {}, {}, {}, []
    for name in ROLES:
        rel = f"agents/{name}.toml"
        current = read(root / rel)
        record = state["roles"].get(name)
        if record:
            if name in adopt:
                raise Conflict(f"managed role cannot be re-adopted: {name}")
            if current is None or digest(current) != record["installed_sha256"]:
                raise Conflict(f"managed role drift: {name}")
        if action == "uninstall":
            if not record:
                continue
            original = record["original"]
            after = read(root / "agent-team" / original["path"]) if original else None
            changes[rel] = current, after
            report.append({"role": name, "operation": "restore" if original else "remove"})
            continue
        after = sources[name]
        original = record["original"] if record else None
        if record:
            operation = "unchanged" if current == after else "update"
        elif current is None:
            if name in adopt:
                raise Conflict(f"adoption target missing: {name}")
            operation = "install"
        else:
            if adopt.get(name) != digest(current):
                raise Conflict(f"unmanaged same-name role: {name}; review and explicitly adopt its current SHA256")
            operation = "adopt"
            backup = f"backups/{uuid.uuid4().hex}-{name}.toml"
            backups[backup] = current
            original = {"path": backup, "sha256": digest(current)}
        records[name] = {"installed_sha256": digest(after), "original": original}
        changes[rel] = current, after
        report.append({"role": name, "operation": operation})
    if action == "uninstall":
        changes[STATE] = before_state, None
    else:
        changes[STATE] = before_state, json_bytes({"schema": 1, "version": version, "roles": records})
    changes = {rel: pair for rel, pair in changes.items() if pair[0] != pair[1]}
    status = "current" if not changes else "changes_required"
    if action in ("install", "uninstall") and changes:
        transact(root, changes, backups)
        status = "installed" if action == "install" else "uninstalled"
    return {"action": action, "status": status, "codex_home": str(root), "version": version, "roles": report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "status", "install", "uninstall", "recover"))
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
    parser.add_argument("--adopt", action="append", default=[], metavar="ROLE=SHA256")
    args = parser.parse_args()
    try:
        result = execute(args.action, args.codex_home, parse_adoptions(args.adopt))
        print(json.dumps(result, indent=2))
        return 1 if args.action == "status" and result["status"] != "current" else 0
    except (Conflict, OSError) as exc:
        print(json.dumps({"action": args.action, "status": "blocked", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
