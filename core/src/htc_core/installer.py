from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import stat
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .codex_config import HTC_AGENTS_BLOCK, merge_agents, merge_hooks, merge_mcp_config


class InstallError(RuntimeError):
    pass


class PreimageChanged(InstallError):
    pass


class RollbackConflict(InstallError):
    pass


class UnsafeInstallTarget(InstallError):
    pass


_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")


@dataclass(frozen=True)
class InstallRequest:
    source_root: Path
    program_root: Path
    data_root: Path
    codex_home: Path
    python_executable: Path = Path(sys.executable)
    version: str = "0.1.0"
    timezone: str = "Asia/Shanghai"

    @property
    def source_package(self) -> Path:
        return self.source_root / "src" / "htc_core"

    @property
    def version_root(self) -> Path:
        return self.program_root / "versions" / self.version

    @property
    def bin_root(self) -> Path:
        return self.program_root / "bin"

    @property
    def manifest_path(self) -> Path:
        return self.data_root / "install-manifest.json"

    @property
    def identity_path(self) -> Path:
        return self.data_root / "identity.json"


@dataclass(frozen=True)
class PlannedFile:
    path: Path
    content: str
    preimage_exists: bool
    preimage_sha256: str | None
    postimage_sha256: str
    preserve_on_rollback: bool = False


@dataclass(frozen=True)
class PackageFile:
    relative_path: str
    sha256: str


@dataclass(frozen=True)
class InstallPlan:
    request: InstallRequest
    operation_id: str
    created_at: str
    source_digest: str
    dependency_digest: str
    dependency_source_root: Path
    package_files: tuple[PackageFile, ...]
    dependency_files: tuple[PackageFile, ...]
    files: tuple[PlannedFile, ...]
    user_id: str
    backup_dir: Path
    created_version: bool

    @property
    def changed(self) -> bool:
        return self.created_version or any(
            not item.preimage_exists or item.preimage_sha256 != item.postimage_sha256
            for item in self.files
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "operation_id": self.operation_id,
            "created_at": self.created_at,
            "source_digest": self.source_digest,
            "dependency_digest": self.dependency_digest,
            "dependency_source_root": str(self.dependency_source_root),
            "user_id": self.user_id,
            "backup_dir": str(self.backup_dir),
            "created_version": self.created_version,
            "request": {
                "source_root": str(self.request.source_root),
                "program_root": str(self.request.program_root),
                "data_root": str(self.request.data_root),
                "codex_home": str(self.request.codex_home),
                "python_executable": str(self.request.python_executable),
                "version": self.request.version,
                "timezone": self.request.timezone,
            },
            "package_files": [
                {"relative_path": item.relative_path, "sha256": item.sha256}
                for item in self.package_files
            ],
            "dependency_files": [
                {"relative_path": item.relative_path, "sha256": item.sha256}
                for item in self.dependency_files
            ],
            "files": [
                {
                    "path": str(item.path),
                    "content": item.content,
                    "preimage_exists": item.preimage_exists,
                    "preimage_sha256": item.preimage_sha256,
                    "postimage_sha256": item.postimage_sha256,
                    "preserve_on_rollback": item.preserve_on_rollback,
                }
                for item in self.files
            ],
        }

    def write(self, path: Path) -> None:
        _atomic_write(
            path,
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            mode=0o600,
        )

    @classmethod
    def load(cls, path: Path) -> InstallPlan:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InstallError("invalid_install_plan") from exc
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise InstallError("unsupported_install_plan")
        raw_request = value.get("request")
        if not isinstance(raw_request, dict):
            raise InstallError("install_plan_request_missing")
        request = InstallRequest(
            source_root=Path(str(raw_request["source_root"])),
            program_root=Path(str(raw_request["program_root"])),
            data_root=Path(str(raw_request["data_root"])),
            codex_home=Path(str(raw_request["codex_home"])),
            python_executable=Path(str(raw_request["python_executable"])),
            version=str(raw_request["version"]),
            timezone=str(raw_request["timezone"]),
        )
        raw_files = value.get("files")
        raw_package_files = value.get("package_files")
        raw_dependency_files = value.get("dependency_files")
        if not isinstance(raw_files, list) or not isinstance(raw_package_files, list):
            raise InstallError("install_plan_files_missing")
        dependency_files = raw_dependency_files if isinstance(raw_dependency_files, list) else []
        files = tuple(
            PlannedFile(
                path=Path(str(item["path"])),
                content=str(item["content"]),
                preimage_exists=bool(item["preimage_exists"]),
                preimage_sha256=item.get("preimage_sha256"),
                postimage_sha256=str(item["postimage_sha256"]),
                preserve_on_rollback=bool(item.get("preserve_on_rollback", False)),
            )
            for item in raw_files
        )
        package_files = tuple(
            PackageFile(relative_path=str(item["relative_path"]), sha256=str(item["sha256"]))
            for item in raw_package_files
        )
        parsed_dependency_files = tuple(
            PackageFile(relative_path=str(item["relative_path"]), sha256=str(item["sha256"]))
            for item in dependency_files
        )
        return cls(
            request=request,
            operation_id=str(value["operation_id"]),
            created_at=str(value["created_at"]),
            source_digest=str(value["source_digest"]),
            dependency_digest=str(value.get("dependency_digest", "")),
            dependency_source_root=Path(str(value["dependency_source_root"])),
            package_files=package_files,
            dependency_files=parsed_dependency_files,
            files=files,
            user_id=str(value["user_id"]),
            backup_dir=Path(str(value["backup_dir"])),
            created_version=bool(value["created_version"]),
        )


def _absolute(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _path_exists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _reject_reparse_components(path: Path, *, label: str) -> None:
    lexical = Path(os.path.abspath(os.path.expanduser(str(path))))
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current /= part
        try:
            if _is_reparse_point(current):
                raise UnsafeInstallTarget(f"{label}_reparse_point:{current}")
        except OSError as exc:
            raise UnsafeInstallTarget(f"{label}_path_unreadable:{current}") from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_text(path: Path) -> str:
    if not _path_exists(path):
        return ""
    if _is_reparse_point(path) or not path.is_file():
        raise UnsafeInstallTarget(f"target_is_not_regular_file:{path}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InstallError(f"target_is_not_utf8:{path}") from exc


def _preimage(path: Path) -> tuple[bool, str | None]:
    if not _path_exists(path):
        return False, None
    if _is_reparse_point(path) or not path.is_file():
        raise UnsafeInstallTarget(f"target_is_not_regular_file:{path}")
    return True, _sha256_file(path)


def _atomic_write(path: Path, content: str | bytes, *, mode: int | None = None) -> None:
    _reject_reparse_components(path.parent, label="write_parent")
    path.parent.mkdir(parents=True, exist_ok=True)
    if _path_exists(path) and (_is_reparse_point(path) or not path.is_file()):
        raise UnsafeInstallTarget(f"target_is_not_regular_file:{path}")
    data = content.encode("utf-8") if isinstance(content, str) else content
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(data)
    if mode is not None:
        temporary.chmod(mode)
    elif path.exists():
        temporary.chmod(stat.S_IMODE(path.stat().st_mode))
    elif path.name in {"identity.json", "install-manifest.json"}:
        temporary.chmod(0o600)
    else:
        temporary.chmod(0o644)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _validate_request(request: InstallRequest) -> InstallRequest:
    for raw_path, label in (
        (request.source_root, "source"),
        (request.program_root, "program_root"),
        (request.data_root, "data_root"),
        (request.codex_home, "codex_home"),
    ):
        _reject_reparse_components(raw_path, label=label)
    requested_python = _absolute(request.python_executable)
    resolved = InstallRequest(
        source_root=_absolute(request.source_root),
        program_root=_absolute(request.program_root),
        data_root=_absolute(request.data_root),
        codex_home=_absolute(request.codex_home),
        python_executable=requested_python,
        version=request.version,
        timezone=request.timezone,
    )
    if not _VERSION_RE.fullmatch(resolved.version):
        raise InstallError("invalid_install_version")
    if not resolved.source_package.is_dir():
        raise InstallError("source_package_not_found")
    if resolved.python_executable.is_relative_to(resolved.source_root):
        candidates = [
            Path(sys.base_prefix) / ("python.exe" if os.name == "nt" else "bin/python"),
            Path(sys.executable),
        ]
        for candidate in candidates:
            candidate = _absolute(candidate)
            if candidate.is_file() and not candidate.is_relative_to(resolved.source_root):
                resolved = InstallRequest(
                    source_root=resolved.source_root,
                    program_root=resolved.program_root,
                    data_root=resolved.data_root,
                    codex_home=resolved.codex_home,
                    python_executable=candidate,
                    version=resolved.version,
                    timezone=resolved.timezone,
                )
                break
        else:
            raise InstallError("python_executable_is_inside_source_tree")
    elif not resolved.python_executable.is_file():
        raise InstallError("python_executable_not_found")
    for target in (resolved.program_root, resolved.data_root, resolved.codex_home):
        if _paths_overlap(target, resolved.source_root):
            raise UnsafeInstallTarget(f"install_target_contains_source:{target}")
    targets = (
        (resolved.program_root, "program_root"),
        (resolved.data_root, "data_root"),
        (resolved.codex_home, "codex_home"),
    )
    for index, (left, left_label) in enumerate(targets):
        for right, right_label in targets[index + 1 :]:
            if _paths_overlap(left, right):
                raise UnsafeInstallTarget(f"install_target_roots_overlap:{left_label}:{right_label}")
    for target, label in (
        (resolved.program_root / "versions", "version_parent"),
        (resolved.bin_root, "bin_parent"),
    ):
        _reject_reparse_components(target, label=label)
    return resolved


def _inventory_files(root: Path, *, label: str) -> tuple[Path, ...]:
    root = _lexical_absolute(root)
    try:
        if _is_reparse_point(root):
            raise UnsafeInstallTarget(f"{label}_reparse_point:{root}")
        if not root.is_dir():
            raise InstallError(f"{label}_not_directory:{root}")
    except OSError as exc:
        raise InstallError(f"{label}_unreadable:{root}") from exc

    pending = [root]
    files: list[Path] = []
    while pending:
        current = pending.pop()
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise InstallError(f"{label}_unreadable:{current}") from exc
        for path in children:
            try:
                if _is_reparse_point(path):
                    raise UnsafeInstallTarget(f"{label}_reparse_point:{path}")
                if path.is_dir():
                    pending.append(path)
                elif path.is_file():
                    relative = path.relative_to(root)
                    if "__pycache__" not in relative.parts and path.suffix != ".pyc":
                        files.append(path)
                else:
                    raise InstallError(f"{label}_non_regular_entry:{path}")
            except OSError as exc:
                raise InstallError(f"{label}_unreadable:{path}") from exc
    return tuple(sorted(files, key=lambda item: item.relative_to(root).as_posix()))


def _package_inventory(source_package: Path) -> tuple[str, tuple[PackageFile, ...]]:
    digest = hashlib.sha256()
    entries: list[PackageFile] = []
    for path in _inventory_files(source_package, label="source_package"):
        relative = path.relative_to(source_package).as_posix()
        data = path.read_bytes()
        file_hash = _sha256_bytes(data)
        entries.append(PackageFile(relative_path=relative, sha256=file_hash))
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
    if not entries:
        raise InstallError("source_package_empty")
    return digest.hexdigest(), tuple(entries)


def _requirement_name_and_active(raw: str) -> tuple[str, bool]:
    requirement, _, marker = raw.partition(";")
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    if not match:
        return "", False
    marker = marker.strip().lower()
    if not marker:
        return match.group(1), True
    if " or " in marker:
        return match.group(1), any(
            _requirement_marker_clause_active(clause) for clause in marker.split(" or ")
        )
    return match.group(1), all(
        _requirement_marker_clause_active(clause) for clause in marker.split(" and ")
    )


def _requirement_marker_clause_active(clause: str) -> bool:
    clause = clause.strip().strip("()")
    if "extra" in clause:
        return False
    platform_match = re.search(r"sys_platform\s*([=!]+)\s*['\"]([^'\"]+)", clause)
    if platform_match:
        actual = "win32" if os.name == "nt" else sys.platform
        expected = platform_match.group(2)
        return actual == expected if platform_match.group(1) in {"=", "=="} else actual != expected
    version_match = re.search(r"python_version\s*([<>=!]+)\s*['\"]([0-9.]+)", clause)
    if version_match:
        current = (sys.version_info.major, sys.version_info.minor)
        wanted = tuple(int(part) for part in version_match.group(2).split("."))
        operator = version_match.group(1)
        comparisons = {
            "<": current < wanted,
            "<=": current <= wanted,
            ">": current > wanted,
            ">=": current >= wanted,
            "==": current == wanted,
            "!=": current != wanted,
        }
        return comparisons.get(operator, False)
    if "platform_python_implementation" in clause:
        return "cpython" in clause
    return "emscripten" not in clause


def _dependency_inventory() -> tuple[str, Path, tuple[PackageFile, ...]]:
    pending = ["mcp", "tzdata"]
    seen: set[str] = set()
    source_root: Path | None = None
    files: dict[str, tuple[str, Path]] = {}
    while pending:
        name = pending.pop()
        key = name.lower().replace("-", "_")
        if key in seen:
            continue
        seen.add(key)
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise InstallError(f"dependency_not_available:{name}") from exc
        raw_root = Path(distribution.locate_file(""))
        _reject_reparse_components(raw_root, label="dependency_root")
        root = _absolute(raw_root)
        if _is_reparse_point(root):
            raise UnsafeInstallTarget(f"dependency_root_reparse_point:{root}")
        source_root = source_root or root
        if root != source_root:
            raise InstallError("dependencies_span_multiple_python_environments")
        for raw_file in distribution.files or ():
            relative = Path(str(raw_file))
            if relative.is_absolute() or "." in relative.parts or ".." in relative.parts:
                continue
            source = root / relative
            _reject_reparse_components(source.parent, label="dependency_parent")
            if _is_reparse_point(source):
                raise UnsafeInstallTarget(f"dependency_reparse_point:{source}")
            if not source.is_file():
                continue
            relative_text = relative.as_posix()
            digest = _sha256_file(source)
            previous = files.get(relative_text)
            if previous is not None and previous[0] != digest:
                raise InstallError(f"dependency_file_collision:{relative_text}")
            files[relative_text] = (digest, source)
        for raw_requirement in distribution.requires or ():
            dependency, active = _requirement_name_and_active(raw_requirement)
            if active and dependency:
                pending.append(dependency)
    if source_root is None or not files:
        raise InstallError("runtime_dependencies_empty")
    digest = hashlib.sha256()
    entries: list[PackageFile] = []
    for relative_text in sorted(files):
        file_digest, _ = files[relative_text]
        entries.append(PackageFile(relative_path=relative_text, sha256=file_digest))
        digest.update(relative_text.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_digest))
    return digest.hexdigest(), source_root, tuple(entries)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not _path_exists(path):
        return None
    if _is_reparse_point(path) or not path.is_file():
        raise UnsafeInstallTarget(f"target_is_not_regular_file:{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallError(f"invalid_json:{path}") from exc
    if not isinstance(value, dict):
        raise InstallError(f"json_root_must_be_object:{path}")
    return value


def _identity(data_root: Path) -> tuple[str, str]:
    path = data_root / "identity.json"
    existing = _load_json(path)
    if existing is not None:
        user_id = existing.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            raise InstallError("identity_missing_user_id")
        return user_id, _read_text(path)
    user_id = f"user-{uuid.uuid4().hex}"
    content = json.dumps(
        {
            "schema_version": 1,
            "user_id": user_id,
            "installation_id": uuid.uuid4().hex,
            "created_at": _utc_now(),
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    return user_id, content


def _host_command(path: Path) -> str:
    value = str(path)
    return f'"{value}"' if any(char.isspace() for char in value) else value


def _cmd_value(value: str) -> str:
    return value.replace("%", "%%").replace('"', '""')


def _cmd_launcher(
    python_executable: Path,
    version_root: Path,
    data_root: Path,
    user_id: str,
    timezone_name: str,
    module: str,
    arguments: tuple[str, ...] = (),
    *,
    auto_start: bool,
) -> str:
    import os as _os

    values = {
        "PYTHONUTF8": "1",
        "PYTHONPATH": str(version_root) + _os.pathsep + str(version_root / "site-packages"),
        "HTC_DATA_HOME": str(data_root),
        "HTC_DB": str(data_root / "htc.sqlite3"),
        "HTC_RUNTIME_DIR": str(data_root),
        "HTC_USER_ID": user_id,
        "HTC_TIMEZONE": timezone_name,
        "HTC_AUTO_START": "1" if auto_start else "0",
    }
    lines = ["\ufeff@echo off", "chcp 65001 >NUL", "setlocal"]
    lines.extend(f'set "{key}={_cmd_value(value)}"' for key, value in values.items())
    command = " ".join([f'"{_cmd_value(str(python_executable))}"', "-m", module, *arguments, "%*"])
    lines.extend([command, "exit /b %ERRORLEVEL%", ""])
    return "\r\n".join(lines)


def _shell_launcher(
    python_executable: Path,
    version_root: Path,
    data_root: Path,
    user_id: str,
    timezone_name: str,
    module: str,
    arguments: tuple[str, ...] = (),
    *,
    auto_start: bool,
) -> str:
    import shlex

    values = {
        "PYTHONUTF8": "1",
        "PYTHONPATH": str(version_root) + os.pathsep + str(version_root / "site-packages"),
        "HTC_DATA_HOME": str(data_root),
        "HTC_DB": str(data_root / "htc.sqlite3"),
        "HTC_RUNTIME_DIR": str(data_root),
        "HTC_USER_ID": user_id,
        "HTC_TIMEZONE": timezone_name,
        "HTC_AUTO_START": "1" if auto_start else "0",
    }
    lines = ["#!/bin/sh", "set -eu"]
    lines.extend(f"export {key}={shlex.quote(value)}" for key, value in values.items())
    command = " ".join(
        [shlex.quote(str(python_executable)), "-m", module, *(shlex.quote(item) for item in arguments), '"$@"']
    )
    lines.extend([f"exec {command}", ""])
    return "\n".join(lines)


def _launcher_contents(request: InstallRequest, user_id: str) -> dict[str, str]:
    extension = ".cmd" if os.name == "nt" else ".sh"
    make = _cmd_launcher if extension == ".cmd" else _shell_launcher
    common = {
        "codex_hook": request.bin_root / f"htc-codex-hook{extension}",
        "mcp": request.bin_root / f"htc-mcp{extension}",
        "daemon": request.bin_root / f"htcd{extension}",
        "cli": request.bin_root / f"htc{extension}",
    }
    rendered = {
        str(common["codex_hook"]): make(
            request.python_executable,
            request.version_root,
            request.data_root,
            user_id,
            request.timezone,
            "htc_core.codex_adapter",
            (),
            auto_start=True,
        ),
        str(common["mcp"]): make(
            request.python_executable,
            request.version_root,
            request.data_root,
            user_id,
            request.timezone,
            "htc_core.mcp_server",
            (),
            auto_start=True,
        ),
        str(common["daemon"]): make(
            request.python_executable,
            request.version_root,
            request.data_root,
            user_id,
            request.timezone,
            "htc_core.daemon",
            (),
            auto_start=False,
        ),
        str(common["cli"]): make(
            request.python_executable,
            request.version_root,
            request.data_root,
            user_id,
            request.timezone,
            "htc_core.cli",
            (),
            auto_start=False,
        ),
    }
    return rendered


def _existing_managed_commands(manifest: dict[str, Any] | None) -> tuple[str, ...]:
    if not manifest:
        return ()
    launchers = manifest.get("launchers", {})
    program_root = manifest.get("program_root")
    bin_root = manifest.get("bin_root")
    if (
        not isinstance(launchers, dict)
        or not isinstance(program_root, str)
        or not isinstance(bin_root, str)
    ):
        return ()
    expected_bin_root = _lexical_absolute(Path(program_root)) / "bin"
    if _lexical_absolute(Path(bin_root)) != expected_bin_root:
        return ()
    allowed_names = {
        "codex_hook": {"htc-codex-hook.cmd", "htc-codex-hook.sh"},
        "mcp": {"htc-mcp.cmd", "htc-mcp.sh"},
    }
    values: list[str] = []
    for key, names in allowed_names.items():
        value = launchers.get(key)
        if not isinstance(value, str):
            continue
        target = _lexical_absolute(Path(value))
        if target.parent == expected_bin_root and target.name in names:
            values.append(str(target))
    return tuple(values)


def _inventory_map(items: tuple[PackageFile, ...]) -> dict[str, str]:
    return {item.relative_path: item.sha256 for item in items}


def _installation_binding(plan: InstallPlan) -> dict[str, Any]:
    request = plan.request
    return {
        "operation_id": plan.operation_id,
        "program_root": str(_lexical_absolute(request.program_root)),
        "data_root": str(_lexical_absolute(request.data_root)),
        "codex_home": str(_lexical_absolute(request.codex_home)),
        "bin_root": str(_lexical_absolute(request.bin_root)),
        "version_root": str(_lexical_absolute(request.version_root)),
        "backup_dir": str(_lexical_absolute(plan.backup_dir)),
        "active_version": request.version,
        "created_version": plan.created_version,
        "source_digest": plan.source_digest,
        "dependency_digest": plan.dependency_digest,
        "dependency_source_root": str(_lexical_absolute(plan.dependency_source_root)),
        "package_files": _inventory_map(plan.package_files),
        "dependency_files": _inventory_map(plan.dependency_files),
    }


def _canonical_inventory(raw: Any, *, label: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise RollbackConflict(f"{label}_invalid")
    result: dict[str, str] = {}
    for raw_relative, raw_digest in raw.items():
        if not isinstance(raw_relative, str) or not raw_relative:
            raise RollbackConflict(f"{label}_path_invalid")
        relative = Path(raw_relative)
        if (
            relative.is_absolute()
            or not relative.parts
            or "." in relative.parts
            or ".." in relative.parts
        ):
            raise RollbackConflict(f"{label}_path_invalid:{raw_relative}")
        normalized = relative.as_posix()
        if normalized in result:
            raise RollbackConflict(f"{label}_duplicate:{normalized}")
        if not isinstance(raw_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", raw_digest):
            raise RollbackConflict(f"{label}_digest_invalid:{normalized}")
        result[normalized] = raw_digest
    return dict(sorted(result.items()))


def _canonical_binding(raw: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RollbackConflict(f"{label}_invalid")
    path_values: dict[str, str] = {}
    for key in (
        "program_root",
        "data_root",
        "codex_home",
        "bin_root",
        "version_root",
        "backup_dir",
        "dependency_source_root",
    ):
        value = raw.get(key)
        if not isinstance(value, str) or not value:
            raise RollbackConflict(f"{label}_{key}_invalid")
        path_values[key] = str(_lexical_absolute(Path(value)))
    operation_id = raw.get("operation_id")
    if not isinstance(operation_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}", operation_id
    ):
        raise RollbackConflict(f"{label}_operation_id_invalid")
    active_version = raw.get("active_version")
    if not isinstance(active_version, str) or not _VERSION_RE.fullmatch(active_version):
        raise RollbackConflict(f"{label}_active_version_invalid")
    created_version = raw.get("created_version")
    if type(created_version) is not bool:
        raise RollbackConflict(f"{label}_created_version_invalid")
    source_digest = raw.get("source_digest")
    dependency_digest = raw.get("dependency_digest")
    for key, value in (("source_digest", source_digest), ("dependency_digest", dependency_digest)):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise RollbackConflict(f"{label}_{key}_invalid")
    return {
        **path_values,
        "operation_id": operation_id,
        "active_version": active_version,
        "created_version": created_version,
        "source_digest": source_digest,
        "dependency_digest": dependency_digest,
        "package_files": _canonical_inventory(
            raw.get("package_files"), label=f"{label}_package_files"
        ),
        "dependency_files": _canonical_inventory(
            raw.get("dependency_files"), label=f"{label}_dependency_files"
        ),
    }


def _manifest_binding(manifest: dict[str, Any]) -> dict[str, Any]:
    return _canonical_binding(
        {
            "operation_id": manifest.get("operation_id"),
            "program_root": manifest.get("program_root"),
            "data_root": manifest.get("data_root"),
            "codex_home": manifest.get("codex_home"),
            "bin_root": manifest.get("bin_root"),
            "version_root": manifest.get("version_root"),
            "backup_dir": manifest.get("backup_dir"),
            "active_version": manifest.get("active_version"),
            "created_version": manifest.get("created_version"),
            "source_digest": manifest.get("source_digest"),
            "dependency_digest": manifest.get("dependency_digest"),
            "dependency_source_root": manifest.get("dependency_source_root"),
            "package_files": manifest.get("package_files"),
            "dependency_files": manifest.get("dependency_files"),
        },
        label="rollback_manifest_binding",
    )


def _same_install(
    existing: dict[str, Any] | None,
    request: InstallRequest,
    source_digest: str,
    dependency_digest: str,
    dependency_source_root: Path,
    package_files: tuple[PackageFile, ...],
    dependency_files: tuple[PackageFile, ...],
) -> bool:
    return bool(
        existing
        and existing.get("active_version") == request.version
        and existing.get("source_digest") == source_digest
        and existing.get("dependency_digest") == dependency_digest
        and existing.get("program_root") == str(request.program_root)
        and existing.get("version_root") == str(request.version_root)
        and existing.get("bin_root") == str(request.bin_root)
        and existing.get("data_root") == str(request.data_root)
        and existing.get("codex_home") == str(request.codex_home)
        and existing.get("dependency_source_root") == str(dependency_source_root)
        and existing.get("package_files") == _inventory_map(package_files)
        and existing.get("dependency_files") == _inventory_map(dependency_files)
        and type(existing.get("created_version")) is bool
        and isinstance(existing.get("operation_id"), str)
        and _lexical_absolute(Path(str(existing.get("backup_dir", ""))))
        == request.data_root / "backups" / str(existing.get("operation_id"))
    )


def _plan_file(path: Path, content: str, *, preserve_on_rollback: bool = False) -> PlannedFile:
    exists, digest = _preimage(path)
    return PlannedFile(
        path=path,
        content=content,
        preimage_exists=exists,
        preimage_sha256=digest,
        postimage_sha256=_sha256_bytes(content.encode("utf-8")),
        preserve_on_rollback=preserve_on_rollback,
    )


def _existing_backup_is_intact(manifest_path: Path, manifest: dict[str, Any]) -> bool:
    try:
        manifest_binding = _manifest_binding(manifest)
        backup_dir = _lexical_absolute(Path(str(manifest["backup_dir"])))
        index = _load_json(backup_dir / "index.json")
        if (
            index is None
            or index.get("schema_version") != 1
            or index.get("operation_id") != manifest.get("operation_id")
            or _canonical_binding(index.get("installation_binding"), label="install_index_binding")
            != manifest_binding
        ):
            return False
        entries = index.get("entries")
        if not isinstance(entries, list):
            return False
        manifest_entries = [
            entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("path") == str(manifest_path)
        ]
        if len(manifest_entries) != 1 or not manifest_path.is_file():
            return False
        expected = manifest_entries[0].get("postimage_sha256")
        return isinstance(expected, str) and _sha256_file(manifest_path) == expected
    except (OSError, InstallError, RollbackConflict, ValueError):
        return False


def build_install_plan(request: InstallRequest) -> InstallPlan:
    request = _validate_request(request)
    source_digest, package_files = _package_inventory(request.source_package)
    dependency_digest, dependency_source_root, dependency_files = _dependency_inventory()
    existing_manifest = _load_json(request.manifest_path)
    user_id, identity_content = _identity(request.data_root)
    launcher_contents = _launcher_contents(request, user_id)
    launchers = {key: path for key, path in {
        "codex_hook": request.bin_root / ("htc-codex-hook.cmd" if os.name == "nt" else "htc-codex-hook.sh"),
        "mcp": request.bin_root / ("htc-mcp.cmd" if os.name == "nt" else "htc-mcp.sh"),
        "daemon": request.bin_root / ("htcd.cmd" if os.name == "nt" else "htcd.sh"),
        "cli": request.bin_root / ("htc.cmd" if os.name == "nt" else "htc.sh"),
    }.items()}
    managed_commands = _existing_managed_commands(existing_manifest)

    hooks_path = request.codex_home / "hooks.json"
    config_path = request.codex_home / "config.toml"
    agents_path = request.codex_home / "AGENTS.md"
    hooks = merge_hooks(
        _read_text(hooks_path),
        _host_command(launchers["codex_hook"]),
        managed_commands=managed_commands,
    ).content
    config = merge_mcp_config(
        _read_text(config_path),
        launchers["mcp"],
        managed_commands=managed_commands,
    ).content
    agents = merge_agents(_read_text(agents_path), HTC_AGENTS_BLOCK).content

    same_install = _same_install(
        existing_manifest,
        request,
        source_digest,
        dependency_digest,
        dependency_source_root,
        package_files,
        dependency_files,
    )
    version_root = request.version_root
    created_version = not _path_exists(version_root)
    if _path_exists(version_root) and _is_reparse_point(version_root):
        raise UnsafeInstallTarget(f"version_root_is_symlink:{version_root}")

    generated: dict[Path, tuple[str, bool]] = {
        request.identity_path: (identity_content, True),
        hooks_path: (hooks, False),
        config_path: (config, False),
        agents_path: (agents, False),
    }
    generated.update((Path(path), (content, False)) for path, content in launcher_contents.items())

    unchanged_files = bool(
        same_install
        and all(
            _path_exists(path) and _sha256_bytes(content.encode("utf-8")) == _sha256_file(path)
            for path, (content, _) in generated.items()
        )
        and _path_exists(version_root)
        and _package_matches_inventory(version_root / "htc_core", package_files)
        and _package_matches_inventory(version_root / "site-packages", dependency_files)
        and existing_manifest is not None
        and _existing_backup_is_intact(request.manifest_path, existing_manifest)
    )
    operation_id = (
        str(existing_manifest.get("operation_id"))
        if unchanged_files and isinstance(existing_manifest.get("operation_id"), str)
        else f"install-{uuid.uuid4().hex}"
    )
    created_at = (
        str(existing_manifest.get("installed_at"))
        if unchanged_files and isinstance(existing_manifest.get("installed_at"), str)
        else _utc_now()
    )
    backup_dir = request.data_root / "backups" / operation_id

    # The manifest is deliberately written last and contains no runtime token,
    # prompt text, or database contents.
    managed_hashes = {
        str(path): _sha256_bytes(content.encode("utf-8"))
        for path, (content, _) in generated.items()
        if path != request.identity_path
    }
    preimages = {
        str(path): {
            "exists": exists,
            "sha256": digest,
        }
        for path in generated
        for exists, digest in [_preimage(path)]
        if path != request.identity_path
    }
    manifest = {
        "schema_version": 1,
        "operation_id": operation_id,
        "installed_at": created_at,
        "active_version": request.version,
        "source_digest": source_digest,
        "dependency_digest": dependency_digest,
        "dependency_source_root": str(dependency_source_root),
        "program_root": str(request.program_root),
        "version_root": str(version_root),
        "bin_root": str(request.bin_root),
        "data_root": str(request.data_root),
        "codex_home": str(request.codex_home),
        "backup_dir": str(backup_dir),
        "created_version": created_version,
        "user_id": user_id,
        "identity_path": str(request.identity_path),
        "launchers": {key: str(path) for key, path in launchers.items()},
        "managed_files": managed_hashes,
        "preimages": preimages,
        "codex": {
            "hooks_path": str(hooks_path),
            "config_path": str(config_path),
            "agents_path": str(agents_path),
            "trust": "pending",
        },
        "package_files": {
            item.relative_path: item.sha256 for item in package_files
        },
        "dependency_files": {
            item.relative_path: item.sha256 for item in dependency_files
        },
    }
    if unchanged_files and request.manifest_path.is_file():
        manifest_content = _read_text(request.manifest_path)
    else:
        manifest_content = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    generated[request.manifest_path] = (manifest_content, False)
    files = tuple(
        _plan_file(path, content, preserve_on_rollback=preserve)
        for path, (content, preserve) in generated.items()
    )
    return InstallPlan(
        request=request,
        operation_id=operation_id,
        created_at=created_at,
        source_digest=source_digest,
        dependency_digest=dependency_digest,
        dependency_source_root=dependency_source_root,
        package_files=package_files,
        dependency_files=dependency_files,
        files=files,
        user_id=user_id,
        backup_dir=backup_dir,
        created_version=created_version,
    )


def _verify_preimages(plan: InstallPlan) -> None:
    for item in plan.files:
        exists, digest = _preimage(item.path)
        if exists != item.preimage_exists or digest != item.preimage_sha256:
            raise PreimageChanged(f"preimage_changed:{item.path}")


def _validate_plan_scope(plan: InstallPlan) -> None:
    request = plan.request
    extension = ".cmd" if os.name == "nt" else ".sh"
    expected = {
        request.identity_path,
        request.manifest_path,
        request.codex_home / "hooks.json",
        request.codex_home / "config.toml",
        request.codex_home / "AGENTS.md",
        request.bin_root / f"htc-codex-hook{extension}",
        request.bin_root / f"htc-mcp{extension}",
        request.bin_root / f"htcd{extension}",
        request.bin_root / f"htc{extension}",
    }
    actual = {item.path.resolve(strict=False) for item in plan.files}
    if actual != {path.resolve(strict=False) for path in expected}:
        raise UnsafeInstallTarget("install_plan_scope_invalid")
    if not plan.backup_dir.resolve(strict=False).is_relative_to(
        request.data_root.resolve(strict=False) / "backups"
    ):
        raise UnsafeInstallTarget("install_plan_backup_scope_invalid")
    _reject_reparse_components(plan.backup_dir.parent, label="install_plan_backup_parent")
    for item in plan.package_files:
        relative = Path(item.relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise UnsafeInstallTarget("install_plan_package_path_invalid")
    for item in plan.dependency_files:
        relative = Path(item.relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise UnsafeInstallTarget("install_plan_dependency_path_invalid")


def _verify_source(plan: InstallPlan) -> None:
    digest, package_files = _package_inventory(plan.request.source_package)
    if digest != plan.source_digest or package_files != plan.package_files:
        raise PreimageChanged("source_package_changed")


def _verify_dependencies(plan: InstallPlan) -> None:
    digest, source_root, dependency_files = _dependency_inventory()
    if (
        digest != plan.dependency_digest
        or source_root.resolve() != plan.dependency_source_root.resolve()
        or dependency_files != plan.dependency_files
    ):
        raise PreimageChanged("runtime_dependencies_changed")


def _backup_files(plan: InstallPlan) -> dict[str, Any]:
    backup_dir = plan.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_dir.chmod(0o700)
    files_dir = backup_dir / "files"
    files_dir.mkdir()
    files_dir.chmod(0o700)
    entries: list[dict[str, Any]] = []
    for index, item in enumerate(plan.files):
        if item.preserve_on_rollback:
            continue
        target = item.path
        exists, digest = _preimage(target)
        entry = {
            "path": str(target),
            "exists": exists,
            "sha256": digest,
            "mode": stat.S_IMODE(target.stat().st_mode) if exists else None,
            "postimage_exists": True,
            "postimage_sha256": item.postimage_sha256,
            "backup_file": None,
            "preserve_on_rollback": item.preserve_on_rollback,
        }
        if exists:
            backup_file = files_dir / f"{index:04d}.bin"
            shutil.copyfile(target, backup_file)
            backup_file.chmod(0o600)
            entry["backup_file"] = str(backup_file)
        entries.append(entry)
    index = {
        "schema_version": 1,
        "operation_id": plan.operation_id,
        "installation_binding": _installation_binding(plan),
        "entries": entries,
    }
    _atomic_write(
        backup_dir / "index.json",
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        mode=0o600,
    )
    return index


def _package_matches(plan: InstallPlan) -> bool:
    root = plan.request.version_root / "htc_core"
    dependency_root = plan.request.version_root / "site-packages"
    return _package_matches_inventory(root, plan.package_files) and _package_matches_inventory(
        dependency_root, plan.dependency_files
    )


def _package_matches_inventory(root: Path, package_files: tuple[PackageFile, ...]) -> bool:
    if not root.is_dir() or _is_reparse_point(root):
        return False
    for item in package_files:
        relative = Path(item.relative_path)
        if relative.is_absolute() or "." in relative.parts or ".." in relative.parts:
            return False
        path = root / relative
        try:
            _reject_reparse_components(path.parent, label="installed_package_parent")
        except (OSError, UnsafeInstallTarget):
            return False
        if not path.is_file() or _is_reparse_point(path) or _sha256_file(path) != item.sha256:
            return False
    expected = {Path(item.relative_path) for item in package_files}
    try:
        actual = {path.relative_to(root) for path in _inventory_files(root, label="installed_package")}
    except (OSError, InstallError, UnsafeInstallTarget):
        return False
    return actual == expected


def _copy_inventory_file(
    source_root: Path,
    target_root: Path,
    item: PackageFile,
    *,
    label: str,
) -> None:
    relative = Path(item.relative_path)
    if relative.is_absolute() or "." in relative.parts or ".." in relative.parts:
        raise UnsafeInstallTarget(f"{label}_path_invalid:{relative}")
    source = source_root / relative
    target = target_root / relative
    _reject_reparse_components(source.parent, label=f"{label}_source_parent")
    if _is_reparse_point(source) or not source.is_file():
        raise PreimageChanged(f"{label}_source_changed:{source}")
    data = source.read_bytes()
    if _sha256_bytes(data) != item.sha256:
        raise PreimageChanged(f"{label}_source_changed:{source}")
    _reject_reparse_components(target.parent, label=f"{label}_target_parent")
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_reparse_components(target.parent, label=f"{label}_target_parent")
    if _path_exists(target):
        raise InstallError(f"{label}_stage_target_exists:{target}")
    _atomic_write(target, data, mode=0o644)


def _stage_package(plan: InstallPlan) -> bool:
    version_root = plan.request.version_root
    if _path_exists(version_root):
        if _is_reparse_point(version_root):
            raise UnsafeInstallTarget(f"version_root_is_symlink:{version_root}")
        if _package_matches(plan):
            return False
        raise InstallError(f"version_directory_conflict:{version_root}")
    _reject_reparse_components(version_root.parent, label="version_parent")
    stage_root = plan.request.program_root / f".stage-{plan.operation_id}" / "versions" / plan.request.version
    stage_parent = plan.request.program_root / f".stage-{plan.operation_id}"
    if _path_exists(stage_parent):
        raise InstallError(f"stage_directory_conflict:{stage_parent}")
    _reject_reparse_components(stage_root.parent, label="stage_parent")
    stage_root.mkdir(parents=True, exist_ok=False)
    try:
        package_target = stage_root / "htc_core"
        for item in plan.package_files:
            _copy_inventory_file(
                plan.request.source_package,
                package_target,
                item,
                label="source_package",
            )
        dependency_target = stage_root / "site-packages"
        for item in plan.dependency_files:
            _copy_inventory_file(
                plan.dependency_source_root,
                dependency_target,
                item,
                label="dependency",
            )
        version_root.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage_root, version_root)
        shutil.rmtree(stage_parent)
        return True
    except Exception:
        if _path_exists(stage_parent):
            shutil.rmtree(stage_parent)
        raise


def _restore_backup(index: dict[str, Any]) -> None:
    for entry in reversed(index.get("entries", [])):
        path = Path(entry["path"])
        if entry.get("exists"):
            backup_file = Path(entry["backup_file"])
            mode = entry.get("mode")
            if mode is not None and (not isinstance(mode, int) or mode < 0 or mode > 0o777):
                raise RollbackConflict(f"rollback_mode_invalid:{path}")
            _atomic_write(path, backup_file.read_bytes(), mode=mode)
        else:
            if _path_exists(path):
                if _is_reparse_point(path):
                    raise RollbackConflict(f"rollback_target_reparse_point:{path}")
                path.unlink()


def _remove_empty_parent(path: Path, stop: Path) -> None:
    current = path
    while current != stop and current.exists() and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def apply_install_plan(plan: InstallPlan) -> dict[str, Any]:
    plan = InstallPlan(
        request=_validate_request(plan.request),
        operation_id=plan.operation_id,
        created_at=plan.created_at,
        source_digest=plan.source_digest,
        dependency_digest=plan.dependency_digest,
        dependency_source_root=plan.dependency_source_root,
        package_files=plan.package_files,
        dependency_files=plan.dependency_files,
        files=plan.files,
        user_id=plan.user_id,
        backup_dir=plan.backup_dir,
        created_version=plan.created_version,
    )
    _validate_plan_scope(plan)
    _verify_source(plan)
    _verify_dependencies(plan)
    _verify_preimages(plan)
    if not plan.changed and plan.request.manifest_path.exists():
        value = _load_json(plan.request.manifest_path)
        if value is not None:
            return value

    plan.request.data_root.mkdir(parents=True, exist_ok=True)
    backup_index = _backup_files(plan)
    version_created = False
    try:
        version_created = _stage_package(plan)
        for item in plan.files:
            if item.path == plan.request.manifest_path:
                continue
            _atomic_write(item.path, item.content)
        manifest_item = next(item for item in plan.files if item.path == plan.request.manifest_path)
        _atomic_write(manifest_item.path, manifest_item.content)
        for item in plan.files:
            if not item.path.exists() or _sha256_file(item.path) != item.postimage_sha256:
                raise InstallError(f"postimage_verification_failed:{item.path}")
        return _load_json(plan.request.manifest_path) or {}
    except Exception:
        try:
            _restore_backup(backup_index)
        finally:
            if version_created and plan.request.version_root.exists():
                shutil.rmtree(plan.request.version_root)
            if plan.request.bin_root.exists():
                _remove_empty_parent(plan.request.bin_root, plan.request.program_root)
        raise


def _load_manifest(path: Path) -> dict[str, Any]:
    value = _load_json(path)
    if value is None:
        raise InstallError("install_manifest_not_found")
    if value.get("schema_version") != 1:
        raise InstallError("unsupported_install_manifest")
    return value


def _check_postimages(manifest: dict[str, Any], index: dict[str, Any]) -> None:
    managed = manifest.get("managed_files", {})
    if not isinstance(managed, dict):
        raise RollbackConflict("manifest_managed_files_invalid")
    entries = index.get("entries")
    if not isinstance(entries, list):
        raise RollbackConflict("rollback_backup_invalid")
    entry_by_path = {str(entry.get("path")): entry for entry in entries if isinstance(entry, dict)}
    for raw_path, expected in managed.items():
        path = _rollback_path(raw_path, label="rollback_target")
        entry = entry_by_path.get(str(raw_path))
        if entry is None or entry.get("postimage_sha256") != expected:
            raise RollbackConflict(f"rollback_manifest_postimage_mismatch:{path}")
    for entry in entries:
        if not isinstance(entry, dict):
            raise RollbackConflict("rollback_backup_entry_invalid")
        path = _rollback_path(entry.get("path"), label="rollback_target")
        expected = entry.get("postimage_sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise RollbackConflict(f"rollback_postimage_invalid:{path}")
        if not path.is_file() or _is_reparse_point(path) or _sha256_file(path) != expected:
            raise RollbackConflict(f"rollback_target_drifted:{path}")


def _rollback_path(raw_path: Any, *, label: str, root: Path | None = None) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise RollbackConflict(f"{label}_missing")
    path = _lexical_absolute(Path(raw_path))
    if root is not None and not path.is_relative_to(_lexical_absolute(root)):
        raise RollbackConflict(f"{label}_scope_invalid:{path}")
    try:
        _reject_reparse_components(path.parent, label=f"{label}_parent")
        if _is_reparse_point(path):
            raise RollbackConflict(f"{label}_reparse_point:{path}")
    except OSError as exc:
        raise RollbackConflict(f"{label}_path_unreadable:{path}") from exc
    return path


def _validate_rollback_scope(manifest: dict[str, Any], manifest_path: Path) -> None:
    manifest_binding = _manifest_binding(manifest)
    data_root = _rollback_path(manifest.get("data_root"), label="rollback_data_root")
    program_root = _rollback_path(manifest.get("program_root"), label="rollback_program_root")
    codex_home = _rollback_path(manifest.get("codex_home"), label="rollback_codex_home")
    bin_root = _rollback_path(manifest.get("bin_root"), label="rollback_bin_root", root=program_root)
    if bin_root != program_root / "bin":
        raise RollbackConflict("rollback_bin_scope_invalid")
    roots = (data_root, program_root, codex_home)
    if any(left == right or left.is_relative_to(right) or right.is_relative_to(left) for index, left in enumerate(roots) for right in roots[index + 1 :]):
        raise RollbackConflict("rollback_roots_overlap")
    expected_manifest = data_root / "install-manifest.json"
    if manifest_path != expected_manifest:
        raise RollbackConflict("rollback_manifest_path_mismatch")
    _rollback_path(str(manifest_path), label="rollback_manifest", root=data_root)
    backup_dir = _rollback_path(manifest.get("backup_dir"), label="rollback_backup", root=data_root / "backups")
    expected_backup_dir = data_root / "backups" / manifest_binding["operation_id"]
    if backup_dir != expected_backup_dir:
        raise RollbackConflict("rollback_backup_scope_invalid")
    version_root = _rollback_path(
        manifest.get("version_root"), label="rollback_version", root=program_root / "versions"
    )
    expected_version_root = program_root / "versions" / manifest_binding["active_version"]
    if version_root != expected_version_root:
        raise RollbackConflict("rollback_version_scope_invalid")
    active_version = manifest.get("active_version")
    if not isinstance(active_version, str) or not _VERSION_RE.fullmatch(active_version):
        raise RollbackConflict("rollback_active_version_invalid")
    if version_root.name != active_version:
        raise RollbackConflict("rollback_version_name_mismatch")
    launchers = manifest.get("launchers")
    if not isinstance(launchers, dict) or set(launchers) != {"codex_hook", "mcp", "daemon", "cli"}:
        raise RollbackConflict("rollback_launchers_invalid")
    launcher_stems = {
        "codex_hook": {"htc-codex-hook.cmd", "htc-codex-hook.sh"},
        "mcp": {"htc-mcp.cmd", "htc-mcp.sh"},
        "daemon": {"htcd.cmd", "htcd.sh"},
        "cli": {"htc.cmd", "htc.sh"},
    }
    expected_launcher_paths: set[Path] = set()
    for key, allowed_names in launcher_stems.items():
        target = _rollback_path(launchers[key], label=f"rollback_launcher_{key}", root=bin_root)
        if target.parent != bin_root or target.name not in allowed_names:
            raise RollbackConflict(f"rollback_launcher_scope_invalid:{target}")
        expected_launcher_paths.add(target)
    codex = manifest.get("codex")
    if not isinstance(codex, dict) or set(codex) - {"hooks_path", "config_path", "agents_path", "trust"}:
        raise RollbackConflict("rollback_codex_manifest_invalid")
    expected_codex_paths = {
        "hooks_path": codex_home / "hooks.json",
        "config_path": codex_home / "config.toml",
        "agents_path": codex_home / "AGENTS.md",
    }
    expected_managed = set(expected_codex_paths.values()) | expected_launcher_paths
    for key, expected_path in expected_codex_paths.items():
        target = _rollback_path(codex.get(key), label=f"rollback_codex_{key}", root=codex_home)
        if target != expected_path:
            raise RollbackConflict(f"rollback_codex_scope_invalid:{target}")
    managed = manifest.get("managed_files", {})
    if not isinstance(managed, dict):
        raise RollbackConflict("manifest_managed_files_invalid")
    managed_paths = {_rollback_path(raw_path, label="rollback_target") for raw_path in managed}
    if managed_paths != expected_managed:
        raise RollbackConflict("rollback_managed_targets_mismatch")
    allowed: set[Path] = set()
    allowed.update(managed_paths)
    allowed.add(manifest_path)
    index = _load_json(backup_dir / "index.json")
    if index is None or index.get("schema_version") != 1 or not isinstance(index.get("entries"), list):
        raise RollbackConflict("rollback_backup_invalid")
    if index.get("operation_id") != manifest.get("operation_id"):
        raise RollbackConflict("rollback_operation_mismatch")
    index_binding = _canonical_binding(
        index.get("installation_binding"), label="rollback_index_binding"
    )
    if index_binding != manifest_binding:
        raise RollbackConflict("rollback_installation_binding_mismatch")
    seen: set[Path] = set()
    for entry in index["entries"]:
        if not isinstance(entry, dict):
            raise RollbackConflict("rollback_backup_entry_invalid")
        target = _rollback_path(entry.get("path"), label="rollback_target")
        if target not in allowed:
            raise RollbackConflict(f"rollback_target_scope_invalid:{target}")
        if target in seen:
            raise RollbackConflict(f"rollback_duplicate_target:{target}")
        seen.add(target)
        if entry.get("exists") not in {True, False}:
            raise RollbackConflict(f"rollback_preimage_invalid:{target}")
        mode = entry.get("mode")
        if mode is not None and (not isinstance(mode, int) or mode < 0 or mode > 0o777):
            raise RollbackConflict(f"rollback_mode_invalid:{target}")
        backup_file = entry.get("backup_file")
        if backup_file is not None:
            backup_path = _rollback_path(backup_file, label="rollback_backup_file", root=backup_dir / "files")
            if not backup_path.is_relative_to(backup_dir / "files") or not backup_path.is_file():
                raise RollbackConflict("rollback_backup_file_scope_invalid")
            expected_preimage = entry.get("sha256")
            if not isinstance(expected_preimage, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_preimage):
                raise RollbackConflict("rollback_preimage_hash_invalid")
            if _sha256_file(backup_path) != expected_preimage:
                raise RollbackConflict("rollback_backup_drifted")
        elif entry.get("exists"):
            raise RollbackConflict("rollback_backup_file_missing")
        elif entry.get("sha256") is not None:
            raise RollbackConflict("rollback_preimage_invalid")
    if seen != allowed:
        raise RollbackConflict("rollback_backup_targets_mismatch")
    if not manifest_path.is_file():
        raise RollbackConflict("rollback_manifest_missing")


def _package_matches_manifest(manifest: dict[str, Any]) -> bool:
    version_root = _lexical_absolute(Path(str(manifest.get("version_root", ""))))
    package_root = version_root / "htc_core"
    dependency_root = version_root / "site-packages"
    package_files = manifest.get("package_files", {})
    dependency_files = manifest.get("dependency_files", {})
    if not version_root.is_dir() or _is_reparse_point(version_root):
        return False
    try:
        top_level = {path.name for path in version_root.iterdir()}
    except OSError:
        return False
    if top_level != {"htc_core", "site-packages"}:
        return False
    if (
        not package_root.is_dir()
        or _is_reparse_point(package_root)
        or not dependency_root.is_dir()
        or _is_reparse_point(dependency_root)
        or not isinstance(package_files, dict)
        or not isinstance(dependency_files, dict)
    ):
        return False
    def matches(root: Path, files: dict[str, Any]) -> bool:
        expected = set()
        for relative, digest in files.items():
            relative_path = Path(str(relative))
            if (
                relative_path.is_absolute()
                or not relative_path.parts
                or "." in relative_path.parts
                or ".." in relative_path.parts
            ):
                return False
            path = root / relative_path
            try:
                _reject_reparse_components(path.parent, label="rollback_package_parent")
                if _is_reparse_point(path) or not path.is_file() or _sha256_file(path) != digest:
                    return False
            except OSError:
                return False
            expected.add(relative_path)
        try:
            actual = {path.relative_to(root) for path in _inventory_files(root, label="rollback_package")}
        except (OSError, InstallError, UnsafeInstallTarget):
            return False
        return actual == expected

    return matches(package_root, package_files) and matches(dependency_root, dependency_files)


def rollback_install(manifest_path: Path, *, apply: bool = True) -> dict[str, Any]:
    manifest_path = _lexical_absolute(manifest_path)
    manifest = _load_manifest(manifest_path)
    _validate_rollback_scope(manifest, manifest_path)
    backup_dir = _lexical_absolute(Path(str(manifest["backup_dir"])))
    index_path = backup_dir / "index.json"
    index = _load_json(index_path)
    if index is None:
        raise RollbackConflict("rollback_backup_missing")
    _check_postimages(manifest, index)
    version_root = _lexical_absolute(Path(str(manifest["version_root"])))
    program_root = _lexical_absolute(Path(str(manifest["program_root"])))
    if manifest.get("created_version") and not _package_matches_manifest(manifest):
        raise RollbackConflict("version_root_changed")
    report = {
        "operation_id": manifest.get("operation_id"),
        "targets": [entry.get("path") for entry in index.get("entries", [])],
        "apply": apply,
    }
    if not apply:
        return report

    snapshot_root = manifest_path.parent / f".rollback-current-{uuid.uuid4().hex}"
    snapshot_files = snapshot_root / "files"
    snapshot_entries: list[dict[str, Any]] = []
    version_snapshot: Path | None = None
    operation_error: BaseException | None = None
    try:
        _reject_reparse_components(snapshot_root.parent, label="rollback_snapshot_parent")
        snapshot_root.mkdir(parents=True, exist_ok=False)
        snapshot_root.chmod(0o700)
        snapshot_files.mkdir(parents=True, exist_ok=False)
        snapshot_files.chmod(0o700)
        for index_number, entry in enumerate(index["entries"]):
            path = _rollback_path(entry.get("path"), label="rollback_snapshot_target")
            snapshot_file = snapshot_files / f"{index_number:04d}.bin"
            _atomic_write(snapshot_file, path.read_bytes(), mode=0o600)
            snapshot_entries.append(
                {
                    "path": str(path),
                    "snapshot_file": str(snapshot_file),
                    "mode": stat.S_IMODE(path.stat().st_mode),
                }
            )
        if manifest.get("created_version"):
            version_snapshot = version_root.parent / f".{version_root.name}.rollback-{uuid.uuid4().hex}"
            _reject_reparse_components(version_snapshot.parent, label="rollback_version_parent")
            os.replace(version_root, version_snapshot)
        try:
            _restore_backup(index)
            if version_snapshot is not None:
                shutil.rmtree(version_snapshot)
        except Exception:
            try:
                for entry in reversed(snapshot_entries):
                    _atomic_write(
                        Path(entry["path"]),
                        Path(entry["snapshot_file"]).read_bytes(),
                        mode=entry["mode"],
                    )
                if version_snapshot is not None and version_snapshot.exists() and not version_root.exists():
                    os.replace(version_snapshot, version_root)
            except Exception as recovery_error:
                raise RollbackConflict("rollback_recovery_failed") from recovery_error
            raise
    except BaseException as exc:
        operation_error = exc
        raise
    finally:
        if _path_exists(snapshot_root):
            try:
                if _is_reparse_point(snapshot_root):
                    raise RollbackConflict("rollback_snapshot_reparse_point")
                shutil.rmtree(snapshot_root)
            except Exception as cleanup_error:
                if operation_error is None:
                    raise RollbackConflict("rollback_snapshot_cleanup_failed") from cleanup_error
                operation_error.add_note(f"rollback_snapshot_cleanup_failed:{cleanup_error}")
    if manifest.get("created_version"):
        _remove_empty_parent(version_root.parent, program_root)
    bin_root = _lexical_absolute(Path(str(manifest["bin_root"])))
    _remove_empty_parent(bin_root, program_root)
    return report
