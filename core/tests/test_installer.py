from __future__ import annotations

import hashlib
import json
import os
import signal
import sqlite3
import stat
import subprocess
import sys
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from htc_core.codex_config import ConfigConflict, merge_agents, merge_hooks, merge_mcp_config
from htc_core.doctor import run_doctor
from htc_core.installer import (
    InstallPlan,
    InstallRequest,
    PlannedFile,
    PreimageChanged,
    RollbackConflict,
    UnsafeInstallTarget,
    apply_install_plan,
    build_install_plan,
    rollback_install,
)

CORE_ROOT = Path(__file__).parents[1]


def _request(tmp_path: Path) -> InstallRequest:
    return InstallRequest(
        source_root=CORE_ROOT,
        program_root=tmp_path / "localapp" / "HTC",
        data_root=tmp_path / "profile" / ".htc",
        codex_home=tmp_path / "profile" / ".codex",
        python_executable=Path(sys.executable),
        version="0.1.0-test",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_install_plan_is_dry_run_and_never_touches_session_files(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.codex_home.mkdir(parents=True)
    session_file = request.codex_home / "sessions" / "live-session.sqlite"
    session_file.parent.mkdir()
    session_file.write_bytes(b"session bytes must remain untouched")
    before = session_file.read_bytes()

    plan = build_install_plan(request)

    assert not request.program_root.exists()
    assert not request.data_root.exists()
    assert session_file.read_bytes() == before
    assert session_file not in {item.path for item in plan.files}
    assert all(item.path.name in {"hooks.json", "config.toml", "AGENTS.md"}
               or item.path == request.data_root / "identity.json"
               or item.path == request.data_root / "install-manifest.json"
               or item.path.parent == request.program_root / "bin"
               for item in plan.files)


def test_saved_install_plan_and_backup_are_private(tmp_path: Path) -> None:
    request = _request(tmp_path)
    plan = build_install_plan(request)
    plan_path = tmp_path / "install-plan.json"
    plan.write(plan_path)
    if os.name != "nt":
        assert plan_path.stat().st_mode & 0o077 == 0

    apply_install_plan(plan)
    backup_dir = Path(json.loads((request.data_root / "install-manifest.json").read_text())["backup_dir"])
    if os.name != "nt":
        assert backup_dir.stat().st_mode & 0o077 == 0
        assert (backup_dir / "files").stat().st_mode & 0o077 == 0
        assert (backup_dir / "index.json").stat().st_mode & 0o077 == 0
        assert all(path.stat().st_mode & 0o077 == 0 for path in (backup_dir / "files").iterdir())


def test_apply_install_is_independent_of_checkout_and_registers_absolute_launchers(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    request.codex_home.mkdir(parents=True)
    (request.codex_home / "config.toml").write_text(
        '[profiles.default]\nmodel = "gpt-test"\n', encoding="utf-8"
    )
    (request.codex_home / "AGENTS.md").write_text("# Personal rules\n", encoding="utf-8")

    plan = build_install_plan(request)
    apply_install_plan(plan)

    manifest = json.loads((request.data_root / "install-manifest.json").read_text())
    hook = Path(manifest["launchers"]["codex_hook"])
    mcp = Path(manifest["launchers"]["mcp"])
    assert hook.is_absolute()
    assert mcp.is_absolute()
    assert hook.exists()
    assert mcp.exists()
    assert str(request.source_root) not in hook.read_text(encoding="utf-8")
    assert str(request.source_root) not in mcp.read_text(encoding="utf-8")

    hooks = json.loads((request.codex_home / "hooks.json").read_text(encoding="utf-8"))
    commands = [
        hook_item["command"]
        for groups in hooks["hooks"].values()
        for group in groups
        for hook_item in group.get("hooks", [])
        if "command" in hook_item
    ]
    assert commands.count(str(hook)) == 2
    config = (request.codex_home / "config.toml").read_text(encoding="utf-8")
    assert tomllib.loads(config)["mcp_servers"]["htc"]["command"] == str(mcp)
    assert "model = \"gpt-test\"" in config
    assert "# Personal rules" in (request.codex_home / "AGENTS.md").read_text(encoding="utf-8")


def test_windows_launchers_encode_non_ascii_install_paths_as_utf8(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows launcher contract")
    base = _request(tmp_path)
    request = replace(
        base,
        program_root=tmp_path / "用户资料" / "HTC程序",
        data_root=tmp_path / "用户资料" / ".htc数据",
        codex_home=tmp_path / "用户资料" / ".codex配置",
    )

    apply_install_plan(build_install_plan(request))

    for launcher in request.bin_root.glob("*.cmd"):
        content = launcher.read_text(encoding="utf-8")
        assert content.startswith("\ufeff")
        assert "chcp 65001 >NUL" in content
        assert str(request.data_root) in content


def test_installed_hook_runs_from_unrelated_directory_without_checkout(tmp_path: Path) -> None:
    base = _request(tmp_path)
    request = InstallRequest(
        source_root=base.source_root,
        program_root=base.program_root,
        data_root=base.data_root,
        codex_home=base.codex_home,
        python_executable=base.python_executable,
        version=base.version,
        timezone="UTC",
    )
    apply_install_plan(build_install_plan(request))
    manifest = json.loads((request.data_root / "install-manifest.json").read_text())
    hook = Path(manifest["launchers"]["codex_hook"])
    unrelated = tmp_path / "unrelated" / "working-directory"
    unrelated.mkdir(parents=True)
    prompt = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "installed-session",
        "turn_id": "installed-turn",
        "prompt": "明天继续安装后的任务",
    }
    runtime_manifest = request.data_root / "runtime.json"
    try:
        result = subprocess.run(
            [str(hook)],
            cwd=unrelated,
            input=json.dumps(prompt, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert "systemMessage" not in result.stdout
        assert runtime_manifest.is_file()
        database = sqlite3.connect(request.data_root / "htc.sqlite3")
        try:
            assert database.execute("SELECT COUNT(*) FROM adapter_events").fetchone()[0] == 1
        finally:
            database.close()
    finally:
        if runtime_manifest.is_file():
            pid = json.loads(runtime_manifest.read_text(encoding="utf-8"))["pid"]
            os.kill(pid, signal.SIGTERM)


def test_repeated_install_is_idempotent(tmp_path: Path) -> None:
    request = _request(tmp_path)
    apply_install_plan(build_install_plan(request))
    tracked = [
        request.codex_home / "hooks.json",
        request.codex_home / "config.toml",
        request.codex_home / "AGENTS.md",
        request.data_root / "identity.json",
        request.data_root / "install-manifest.json",
    ]
    before = {path: _sha256(path) for path in tracked}

    second = build_install_plan(request)
    apply_install_plan(second)

    assert {path: _sha256(path) for path in tracked} == before
    hooks = json.loads((request.codex_home / "hooks.json").read_text(encoding="utf-8"))
    for event_groups in hooks["hooks"].values():
        htc_entries = [
            item
            for group in event_groups
            for item in group.get("hooks", [])
            if "htc-codex-hook" in item.get("command", "")
        ]
        assert len(htc_entries) == 1


def test_rollback_restores_exact_preimages_without_deleting_user_data(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.codex_home.mkdir(parents=True)
    hooks = request.codex_home / "hooks.json"
    config = request.codex_home / "config.toml"
    agents = request.codex_home / "AGENTS.md"
    hooks.write_text('{"hooks": {"Stop": []}}\n', encoding="utf-8")
    config.write_text('[profiles.default]\nmodel = "keep-me"\n', encoding="utf-8")
    agents.write_text("Keep this rule.\n", encoding="utf-8")
    originals = {path: path.read_bytes() for path in (hooks, config, agents)}

    apply_install_plan(build_install_plan(request))
    identity = request.data_root / "identity.json"
    assert identity.exists()

    rollback_install(request.data_root / "install-manifest.json")

    assert {path: path.read_bytes() for path in originals} == originals
    assert identity.exists()
    assert not (request.program_root / "bin").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits are not portable on Windows")
def test_rollback_restores_preimage_file_mode(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.codex_home.mkdir(parents=True)
    config = request.codex_home / "config.toml"
    config.write_text('[profiles.default]\nmodel = "keep-me"\n', encoding="utf-8")
    config.chmod(0o600)
    original_mode = stat.S_IMODE(config.stat().st_mode)

    apply_install_plan(build_install_plan(request))
    config.chmod(0o644)
    rollback_install(request.data_root / "install-manifest.json")

    assert stat.S_IMODE(config.stat().st_mode) == original_mode


def test_config_merges_preserve_unmanaged_content_and_block_conflicts() -> None:
    hooks = '{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "user-tool"}]}]}}\n'
    merged = merge_hooks(hooks, Path("C:/HTC/bin/htc-codex-hook.cmd"))
    decoded = json.loads(merged.content)
    assert any(
        item.get("command") == "user-tool"
        for group in decoded["hooks"]["Stop"]
        for item in group["hooks"]
    )

    toml = '[profiles.default]\nmodel = "keep-me"\n'
    merged_toml = merge_mcp_config(toml, Path("C:/HTC/bin/htc-mcp.cmd"))
    assert 'model = "keep-me"' in merged_toml.content
    assert tomllib.loads(merged_toml.content)["mcp_servers"]["htc"]["command"] == str(
        Path("C:/HTC/bin/htc-mcp.cmd")
    )
    assert "[mcp_servers.htc]" in merged_toml.content

    with pytest.raises(ConfigConflict):
        merge_mcp_config(
            '[mcp_servers.htc]\ncommand = "some-other-server"\n',
            Path("C:/HTC/bin/htc-mcp.cmd"),
        )


def test_config_migration_replaces_legacy_htc_hook_and_preserves_mcp_options() -> None:
    old_hook = r"C:\Old HTC\bin\htc-codex-hook.cmd"
    new_hook = r"C:\New HTC\bin\htc-codex-hook.cmd"
    hooks = json.dumps(
        {
            "hooks": {
                "UserPromptSubmit": [
                    {"hooks": [{"type": "command", "command": old_hook}]},
                    {"hooks": [{"type": "command", "command": "user-tool"}]},
                ],
                "Stop": [{"hooks": [{"type": "command", "command": old_hook}]}],
            }
        }
    )

    migrated_hooks = json.loads(
        merge_hooks(hooks, new_hook, managed_commands=(old_hook,)).content
    )
    for event_name in ("UserPromptSubmit", "Stop"):
        commands = [
            item["command"]
            for group in migrated_hooks["hooks"][event_name]
            for item in group["hooks"]
            if "command" in item
        ]
        assert commands.count(new_hook) == 1
        assert old_hook not in commands
    assert "user-tool" in commands or any(
        item.get("command") == "user-tool"
        for group in migrated_hooks["hooks"]["UserPromptSubmit"]
        for item in group["hooks"]
    )

    old_mcp = r"C:\Old HTC\bin\htc-mcp.cmd"
    config = (
        "[mcp_servers.htc]\n"
        f"command = {json.dumps(old_mcp)}\n"
        'args = ["--profile", "custom"]\n'
        'env = { HTC_TEST = "keep" }\n'
        "startup_timeout_sec = 42\n"
        "custom_flag = true\n"
    )
    migrated_config = tomllib.loads(
        merge_mcp_config(config, new_hook, managed_commands=(old_mcp,)).content
    )
    mcp = migrated_config["mcp_servers"]["htc"]
    assert mcp["command"] == new_hook
    assert mcp["args"] == ["--profile", "custom"]
    assert mcp["env"] == {"HTC_TEST": "keep"}
    assert mcp["startup_timeout_sec"] == 42
    assert mcp["custom_flag"] is True


def test_config_merge_does_not_replace_similarly_named_user_hook() -> None:
    user_hook = r"C:\Tools\my-htc-codex-hook-wrapper.cmd"
    new_hook = r"C:\HTC\bin\htc-codex-hook.cmd"
    hooks = json.dumps(
        {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": user_hook}]}]}}
    )

    merged = json.loads(merge_hooks(hooks, new_hook).content)
    commands = [
        item["command"]
        for group in merged["hooks"]["Stop"]
        for item in group["hooks"]
        if "command" in item
    ]

    assert user_hook in commands
    assert new_hook in commands


def test_config_merge_rejects_unknown_htc_hook_command() -> None:
    unknown_htc_hook = r"C:\Tools\htc-codex-hook.cmd"
    new_hook = r"C:\HTC\bin\htc-codex-hook.cmd"
    hooks = json.dumps(
        {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": unknown_htc_hook}]}]}}
    )

    with pytest.raises(ConfigConflict, match="ambiguous_htc_hook_registration:Stop"):
        merge_hooks(hooks, new_hook)


def test_config_merge_supports_inline_and_nested_dotted_mcp_keys() -> None:
    old_mcp = r"C:\Old HTC\bin\htc-mcp.cmd"
    new_mcp = r"C:\New HTC\bin\htc-mcp.cmd"

    inline = (
        "mcp_servers.htc = { "
        f"command = {json.dumps(old_mcp)}, "
        'args = ["--profile", "custom"], env = { HTC_TEST = "keep" } }\n'
    )
    inline_result = tomllib.loads(
        merge_mcp_config(inline, new_mcp, managed_commands=(old_mcp,)).content
    )["mcp_servers"]["htc"]
    assert inline_result["command"] == new_mcp
    assert inline_result["args"] == ["--profile", "custom"]
    assert inline_result["env"] == {"HTC_TEST": "keep"}
    assert inline_result["startup_timeout_sec"] == 10

    nested = (
        f"mcp_servers.htc.command = {json.dumps(old_mcp)}\n"
        'mcp_servers.htc.args = ["--profile", "custom"]\n'
        'mcp_servers.htc.env = { HTC_TEST = "keep" }\n'
    )
    nested_result = tomllib.loads(
        merge_mcp_config(nested, new_mcp, managed_commands=(old_mcp,)).content
    )["mcp_servers"]["htc"]
    assert nested_result["command"] == new_mcp
    assert nested_result["args"] == ["--profile", "custom"]
    assert nested_result["env"] == {"HTC_TEST": "keep"}
    assert nested_result["startup_timeout_sec"] == 10


def test_manifest_cannot_authorize_arbitrary_user_command_migration(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.data_root.mkdir(parents=True)
    user_hook = r"C:\Tools\my-wrapper.cmd"
    (request.codex_home / "hooks.json").parent.mkdir(parents=True)
    (request.codex_home / "hooks.json").write_text(
        json.dumps(
            {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": user_hook}]}]}}
        ),
        encoding="utf-8",
    )
    (request.data_root / "install-manifest.json").write_text(
        json.dumps(
            {
                "launchers": {"codex_hook": user_hook, "mcp": r"C:\Tools\my-mcp.cmd"},
                "program_root": r"C:\Tools",
                "bin_root": r"C:\Tools\bin",
            }
        ),
        encoding="utf-8",
    )

    plan = build_install_plan(request)
    planned_hooks = json.loads(
        next(item.content for item in plan.files if item.path.name == "hooks.json")
    )
    commands = [
        item["command"]
        for group in planned_hooks["hooks"]["Stop"]
        for item in group["hooks"]
        if "command" in item
    ]
    assert user_hook in commands


def test_install_refuses_reparse_point_inside_source_package(tmp_path: Path, monkeypatch) -> None:
    import htc_core.installer as installer

    source_root = tmp_path / "source"
    source_package = source_root / "src" / "htc_core"
    source_package.mkdir(parents=True)
    linked = source_package / "linked.py"
    linked.write_text("outside = True\n", encoding="utf-8")
    original_is_reparse_point = installer._is_reparse_point
    monkeypatch.setattr(
        installer,
        "_is_reparse_point",
        lambda path: Path(path) == linked or original_is_reparse_point(path),
    )

    request = replace(_request(tmp_path), source_root=source_root)
    with pytest.raises(UnsafeInstallTarget, match="source_package_reparse_point"):
        build_install_plan(request)


def test_install_refuses_reparse_point_inside_dependency_inventory(tmp_path: Path, monkeypatch) -> None:
    import importlib.metadata

    import htc_core.installer as installer

    dependency_root = tmp_path / "site-packages"
    dependency_root.mkdir()
    linked = dependency_root / "dependency.py"
    linked.write_text("outside = True\n", encoding="utf-8")

    class FakeDistribution:
        files = [Path("dependency.py")]
        requires: list[str] = []

        def locate_file(self, _name: str) -> Path:
            return dependency_root

    original_is_reparse_point = installer._is_reparse_point
    monkeypatch.setattr(
        importlib.metadata,
        "distribution",
        lambda _name: FakeDistribution(),
    )
    monkeypatch.setattr(
        installer,
        "_is_reparse_point",
        lambda path: Path(path) == linked or original_is_reparse_point(path),
    )

    with pytest.raises(UnsafeInstallTarget, match="dependency_reparse_point"):
        installer._dependency_inventory()


def test_rollback_rejects_manifest_binding_drift(tmp_path: Path) -> None:
    request = _request(tmp_path)
    apply_install_plan(build_install_plan(request))
    manifest_path = request.data_root / "install-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_digest"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    backup_dir = Path(manifest["backup_dir"])
    index_path = backup_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for entry in index["entries"]:
        if entry["path"] == str(manifest_path):
            entry["postimage_sha256"] = _sha256(manifest_path)
            break
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(RollbackConflict, match="rollback_installation_binding_mismatch"):
        rollback_install(manifest_path)


def test_rollback_reports_snapshot_cleanup_failure(tmp_path: Path, monkeypatch) -> None:
    import htc_core.installer as installer

    request = _request(tmp_path)
    apply_install_plan(build_install_plan(request))
    original_rmtree = installer.shutil.rmtree

    def fail_snapshot_cleanup(path, *args, **kwargs):
        candidate = Path(path)
        if candidate.parent == request.data_root and candidate.name.startswith(".rollback-current-"):
            raise OSError("simulated snapshot cleanup failure")
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(installer.shutil, "rmtree", fail_snapshot_cleanup)
    with pytest.raises(RollbackConflict, match="rollback_snapshot_cleanup_failed"):
        rollback_install(request.data_root / "install-manifest.json")
    assert list(request.data_root.glob(".rollback-current-*"))


def test_multiple_managed_blocks_are_not_guessed() -> None:
    block = "<!-- HTC:BEGIN -->\nold\n<!-- HTC:END -->\n"
    with pytest.raises(ConfigConflict):
        merge_agents(block + block, "new")


def test_doctor_is_read_only_and_reports_drift_and_pending_trust(tmp_path: Path) -> None:
    request = _request(tmp_path)
    apply_install_plan(build_install_plan(request))
    hook = request.codex_home / "hooks.json"
    before = hook.read_bytes()
    hook.write_text(hook.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = run_doctor(request.data_root / "install-manifest.json")

    assert result["ok"] is False
    assert "managed_file_drift" in {finding["code"] for finding in result["findings"]}
    assert "codex_hook_trust_pending" in {
        finding["code"] for finding in result["findings"]
    }
    assert hook.read_bytes() != before


def test_doctor_reports_corrupt_manifest_fields_without_raising(tmp_path: Path) -> None:
    manifest = tmp_path / "install-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "managed_files": [],
                "launchers": [],
                "codex": [],
            }
        ),
        encoding="utf-8",
    )

    result = run_doctor(manifest)

    codes = {finding["code"] for finding in result["findings"]}
    assert result["ok"] is False
    assert {"managed_files_invalid", "launchers_invalid", "codex_manifest_invalid"} <= codes


def test_rollback_rejects_drift_before_restoring_any_file(tmp_path: Path) -> None:
    request = _request(tmp_path)
    apply_install_plan(build_install_plan(request))
    hooks = request.codex_home / "hooks.json"
    hooks.write_text("drifted after install\n", encoding="utf-8")
    config = request.codex_home / "config.toml"
    current_config = config.read_bytes()

    with pytest.raises(RollbackConflict, match="rollback_target_drifted"):
        rollback_install(request.data_root / "install-manifest.json")

    assert config.read_bytes() == current_config
    assert hooks.read_text(encoding="utf-8") == "drifted after install\n"


def test_rollback_rejects_unknown_version_files_without_deleting_them(tmp_path: Path) -> None:
    request = _request(tmp_path)
    apply_install_plan(build_install_plan(request))
    unexpected = request.version_root / "unexpected.txt"
    unexpected.write_text("user-added\n", encoding="utf-8")
    hooks = request.codex_home / "hooks.json"
    installed_hooks = hooks.read_bytes()

    with pytest.raises(RollbackConflict, match="version_root_changed"):
        rollback_install(request.data_root / "install-manifest.json")

    assert unexpected.read_text(encoding="utf-8") == "user-added\n"
    assert hooks.read_bytes() == installed_hooks


def test_rollback_rejects_tampered_backup_before_restoring(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.codex_home.mkdir(parents=True)
    (request.codex_home / "config.toml").write_text(
        '[profiles.default]\nmodel = "before"\n', encoding="utf-8"
    )
    apply_install_plan(build_install_plan(request))
    manifest = json.loads((request.data_root / "install-manifest.json").read_text())
    backup_dir = Path(manifest["backup_dir"])
    backup_file = next((backup_dir / "files").iterdir())
    backup_file.write_bytes(b"tampered backup")
    hooks = request.codex_home / "hooks.json"
    current_hooks = hooks.read_bytes()

    with pytest.raises(RollbackConflict, match="rollback_backup_drifted"):
        rollback_install(request.data_root / "install-manifest.json")

    assert hooks.read_bytes() == current_hooks


def test_rollback_restores_current_state_when_restore_fails(tmp_path: Path, monkeypatch) -> None:
    import htc_core.installer as installer

    request = _request(tmp_path)
    apply_install_plan(build_install_plan(request))
    tracked = {
        path: path.read_bytes()
        for path in (
            request.codex_home / "hooks.json",
            request.codex_home / "config.toml",
            request.codex_home / "AGENTS.md",
        )
    }

    def fail_restore(index):
        raise OSError("simulated restore failure")

    monkeypatch.setattr(installer, "_restore_backup", fail_restore)
    with pytest.raises(OSError, match="simulated restore failure"):
        rollback_install(request.data_root / "install-manifest.json")

    assert {path: path.read_bytes() for path in tracked} == tracked
    assert request.version_root.is_dir()


def test_apply_refuses_preimage_drift(tmp_path: Path) -> None:
    request = _request(tmp_path)
    plan = build_install_plan(request)
    request.codex_home.mkdir(parents=True)
    (request.codex_home / "config.toml").write_text("changed before apply\n", encoding="utf-8")
    with pytest.raises(PreimageChanged):
        apply_install_plan(plan)


def test_apply_refuses_dependency_inventory_drift(tmp_path: Path) -> None:
    request = _request(tmp_path)
    plan = build_install_plan(request)
    drifted = replace(plan, dependency_digest="0" * 64)

    with pytest.raises(PreimageChanged, match="runtime_dependencies_changed"):
        apply_install_plan(drifted)

    assert not request.program_root.exists()
    assert not request.data_root.exists()


@pytest.mark.parametrize("target", ["program_root", "data_root", "codex_home"])
def test_install_refuses_targets_inside_source_tree(tmp_path: Path, target: str) -> None:
    request = _request(tmp_path)
    unsafe = request.source_root / "temporary-install-target"
    request = replace(request, **{target: unsafe})

    with pytest.raises(UnsafeInstallTarget, match="install_target_contains_source"):
        build_install_plan(request)


def test_install_refuses_overlapping_install_roots(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request = replace(request, codex_home=request.data_root / "codex")

    with pytest.raises(UnsafeInstallTarget, match="install_target_roots_overlap"):
        build_install_plan(request)


def test_saved_plan_is_loadable_and_cannot_escape_managed_scope(tmp_path: Path) -> None:
    request = _request(tmp_path)
    plan_path = tmp_path / "install-plan.json"
    plan = build_install_plan(request)
    plan.write(plan_path)
    loaded = InstallPlan.load(plan_path)
    apply_install_plan(loaded)

    session_file = request.codex_home / "sessions" / "must-not-change.sqlite"
    session_file.parent.mkdir(parents=True)
    session_file.write_bytes(b"untouched")
    escaped = replace(
        loaded,
        files=loaded.files
        + (
            PlannedFile(
                path=session_file,
                content="overwritten",
                preimage_exists=True,
                preimage_sha256=_sha256(session_file),
                postimage_sha256=_sha256(session_file),
            ),
        ),
    )
    with pytest.raises(UnsafeInstallTarget):
        apply_install_plan(escaped)
    assert session_file.read_bytes() == b"untouched"
