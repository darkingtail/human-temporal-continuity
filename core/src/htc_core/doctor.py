from __future__ import annotations

import hashlib
import json
import os
import tomllib
from pathlib import Path
from typing import Any

from .codex_config import HTC_AGENTS_BEGIN, HTC_AGENTS_END


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finding(code: str, message: str, *, path: Path | None = None, severity: str = "error") -> dict[str, Any]:
    value: dict[str, Any] = {"code": code, "message": message, "severity": severity}
    if path is not None:
        value["path"] = str(path)
    return value


def _load_manifest(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    if not path.is_file():
        findings.append(_finding("install_manifest_missing", "Install manifest does not exist", path=path))
        return None, findings
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        findings.append(_finding("install_manifest_invalid", "Install manifest is not valid UTF-8 JSON", path=path))
        return None, findings
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        findings.append(_finding("install_manifest_unsupported", "Unsupported install manifest", path=path))
        return None, findings
    return value, findings


def _command_executable(command: Any) -> str:
    if not isinstance(command, str):
        return ""
    value = command.strip()
    if value.startswith('"'):
        end = value.find('"', 1)
        if end > 0:
            value = value[1:end]
    else:
        value = value.split(None, 1)[0] if value else ""
    return os.path.normcase(os.path.normpath(value))


def _hook_event_command_count(value: Any, event_name: str, expected: str) -> int:
    if not isinstance(value, dict):
        return 0
    events = value.get("hooks", {})
    if not isinstance(events, dict):
        return 0
    groups = events.get(event_name, [])
    if not isinstance(groups, list):
        return 0
    count = 0
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            continue
        count += sum(
            1
            for hook in group["hooks"]
            if isinstance(hook, dict) and _command_executable(hook.get("command")) == _command_executable(expected)
        )
    return count


def run_doctor(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve(strict=False)
    manifest, findings = _load_manifest(manifest_path)
    if manifest is None:
        return {"ok": False, "findings": findings}

    managed = manifest.get("managed_files", {})
    if not isinstance(managed, dict):
        findings.append(_finding("managed_files_invalid", "Managed file map is invalid", path=manifest_path))
        managed = {}
    for raw_path, expected in managed.items():
        path = Path(str(raw_path))
        if not path.is_file() or _sha256(path) != expected:
            findings.append(_finding("managed_file_drift", "Managed file is missing or changed", path=path))

    identity_path = Path(str(manifest.get("identity_path", "")))
    if not identity_path.is_file():
        findings.append(_finding("identity_missing", "Stable HTC identity is missing", path=identity_path))
    else:
        try:
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            if not isinstance(identity, dict) or identity.get("user_id") != manifest.get("user_id"):
                findings.append(_finding("identity_mismatch", "Identity does not match install manifest", path=identity_path))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            findings.append(_finding("identity_invalid", "Identity is not valid UTF-8 JSON", path=identity_path))

    launchers = manifest.get("launchers", {})
    if not isinstance(launchers, dict):
        findings.append(_finding("launchers_invalid", "Launcher map is invalid", path=manifest_path))
        launchers = {}

    codex = manifest.get("codex", {})
    if not isinstance(codex, dict):
        findings.append(_finding("codex_manifest_invalid", "Codex registration map is invalid", path=manifest_path))
        codex = {}
    hooks_path = Path(str(codex.get("hooks_path", "")))
    expected_hook = launchers.get("codex_hook", "")
    try:
        hooks_value = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        hooks_value = None
        findings.append(_finding("codex_hooks_invalid", "Codex hooks file is missing or invalid", path=hooks_path))
    if hooks_value is not None:
        event_counts = {
            event_name: _hook_event_command_count(hooks_value, event_name, str(expected_hook))
            for event_name in ("UserPromptSubmit", "Stop")
        }
        if any(count != 1 for count in event_counts.values()):
            findings.append(
                _finding(
                    "codex_hook_registration_count",
                    "Expected exactly one HTC hook for each of UserPromptSubmit and Stop",
                    path=hooks_path,
                )
            )

    config_path = Path(str(codex.get("config_path", "")))
    try:
        config_value = tomllib.loads(config_path.read_text(encoding="utf-8"))
        mcp_servers = config_value.get("mcp_servers", {})
        mcp_value = mcp_servers.get("htc") if isinstance(mcp_servers, dict) else None
        expected_mcp = launchers.get("mcp", "")
        if not isinstance(mcp_value, dict) or mcp_value.get("command") != expected_mcp:
            findings.append(_finding("codex_mcp_registration_invalid", "HTC MCP registration is missing or changed", path=config_path))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, AttributeError):
        findings.append(_finding("codex_config_invalid", "Codex config is missing or invalid TOML", path=config_path))

    agents_path = Path(str(codex.get("agents_path", "")))
    try:
        agents_text = agents_path.read_text(encoding="utf-8")
        if agents_text.count(HTC_AGENTS_BEGIN) != 1 or agents_text.count(HTC_AGENTS_END) != 1:
            findings.append(_finding("codex_agents_block_invalid", "HTC AGENTS managed block is missing or duplicated", path=agents_path))
    except (OSError, UnicodeDecodeError):
        findings.append(_finding("codex_agents_missing", "User-level AGENTS.md is missing or unreadable", path=agents_path))

    if codex.get("trust") != "trusted":
        findings.append(
            _finding(
                "codex_hook_trust_pending",
                "Codex must trust the user-level Hook before silent delivery is active",
                severity="warning",
            )
        )

    version_root = Path(str(manifest.get("version_root", "")))
    if not version_root.is_dir():
        findings.append(_finding("installed_version_missing", "Installed HTC version directory is missing", path=version_root))
    for raw_path in launchers.values():
        path = Path(str(raw_path))
        if not path.is_file():
            findings.append(_finding("launcher_missing", "Generated launcher is missing", path=path))

    return {
        "ok": not findings,
        "findings": findings,
        "active_version": manifest.get("active_version"),
        "user_id": manifest.get("user_id"),
    }
