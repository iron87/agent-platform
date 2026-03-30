from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import gettempdir
from time import perf_counter
from typing import Any


DEFAULT_FILE_OPS_ROOT_DIR = Path(gettempdir()) / "2brain_file_ops"
DEFAULT_FILE_OPS_MAX_READ_BYTES = 65536

ALLOWED_ACTIONS = {
    "read_file",
    "write_file",
    "append_file",
    "list_dir",
    "make_dir",
    "delete_path",
}


class FileOpsToolError(RuntimeError):
    """Raised when a sandboxed file operation fails."""


@dataclass(frozen=True)
class FileOpsResponse:
    action: str
    path: str
    success: bool
    message: str
    content: str | None
    entries: list[str] | None
    bytes_read: int | None
    took_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FileOpsTool:
    name = "file_ops"
    description = "Perform sandboxed file operations in an isolated workspace directory."
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": sorted(ALLOWED_ACTIONS),
                "description": "File operation to execute.",
            },
            "path": {
                "type": "string",
                "minLength": 1,
                "description": "Relative path inside the sandbox root.",
            },
            "content": {
                "type": "string",
                "description": "File content for write/append actions.",
            },
            "recursive": {
                "type": "boolean",
                "description": "If true, delete_path can remove non-empty directories.",
            },
        },
        "required": ["action", "path"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        root_dir: Path | str = DEFAULT_FILE_OPS_ROOT_DIR,
        max_read_bytes: int = DEFAULT_FILE_OPS_MAX_READ_BYTES,
    ) -> None:
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.max_read_bytes = max_read_bytes
        self.root_dir.mkdir(parents=True, exist_ok=True)

    @property
    def tool_definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    async def arun(
        self,
        *,
        action: str,
        path: str,
        content: str | None = None,
        recursive: bool = False,
    ) -> dict[str, Any]:
        result = await self.execute(action=action, path=path, content=content, recursive=recursive)
        return result.to_dict()

    async def execute(
        self,
        *,
        action: str,
        path: str,
        content: str | None = None,
        recursive: bool = False,
    ) -> FileOpsResponse:
        normalized_action = action.strip().lower()
        if normalized_action not in ALLOWED_ACTIONS:
            raise FileOpsToolError(f"unsupported action '{action}'. Allowed actions: {sorted(ALLOWED_ACTIONS)}")

        target = self._resolve_sandbox_path(path)
        started = perf_counter()

        if normalized_action == "read_file":
            result = self._read_file(target)
        elif normalized_action == "write_file":
            result = self._write_file(target, content or "", append=False)
        elif normalized_action == "append_file":
            result = self._write_file(target, content or "", append=True)
        elif normalized_action == "list_dir":
            result = self._list_dir(target)
        elif normalized_action == "make_dir":
            result = self._make_dir(target)
        elif normalized_action == "delete_path":
            result = self._delete_path(target, recursive=recursive)
        else:
            raise FileOpsToolError(f"unhandled action '{action}'")

        took_ms = int((perf_counter() - started) * 1000)
        return FileOpsResponse(
            action=normalized_action,
            path=str(target.relative_to(self.root_dir)),
            success=True,
            message=result.get("message", "ok"),
            content=result.get("content"),
            entries=result.get("entries"),
            bytes_read=result.get("bytes_read"),
            took_ms=took_ms,
        )

    async def aclose(self) -> None:
        return None

    def _resolve_sandbox_path(self, raw_path: str) -> Path:
        normalized = raw_path.strip()
        if not normalized:
            raise FileOpsToolError("path must not be blank")

        candidate = (self.root_dir / normalized).resolve()
        try:
            candidate.relative_to(self.root_dir)
        except ValueError as exc:
            raise FileOpsToolError("path escapes sandbox root") from exc
        return candidate

    def _read_file(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileOpsToolError(f"file not found: {path.name}")
        if not path.is_file():
            raise FileOpsToolError("read_file requires a regular file path")

        data = path.read_bytes()
        truncated = data[: self.max_read_bytes]
        text = truncated.decode("utf-8", errors="ignore")
        message = "ok"
        if len(data) > self.max_read_bytes:
            message = f"content truncated to {self.max_read_bytes} bytes"

        return {
            "message": message,
            "content": text,
            "bytes_read": len(truncated),
        }

    def _write_file(self, path: Path, content: str, *, append: bool) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with path.open(mode, encoding="utf-8") as fh:
            fh.write(content)

        return {
            "message": "appended" if append else "written",
        }

    def _list_dir(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileOpsToolError(f"directory not found: {path.name}")
        if not path.is_dir():
            raise FileOpsToolError("list_dir requires a directory path")

        entries = []
        for child in sorted(path.iterdir(), key=lambda p: p.name):
            rel = child.relative_to(self.root_dir)
            suffix = "/" if child.is_dir() else ""
            entries.append(f"{rel}{suffix}")

        return {
            "message": f"{len(entries)} entries",
            "entries": entries,
        }

    def _make_dir(self, path: Path) -> dict[str, Any]:
        path.mkdir(parents=True, exist_ok=True)
        return {"message": "directory ready"}

    def _delete_path(self, path: Path, *, recursive: bool) -> dict[str, Any]:
        if not path.exists():
            raise FileOpsToolError(f"path not found: {path.name}")

        if path.is_file():
            path.unlink()
            return {"message": "file deleted"}

        if path.is_dir():
            if recursive:
                for child in sorted(path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                    if child.is_file():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                path.rmdir()
                return {"message": "directory deleted recursively"}

            path.rmdir()
            return {"message": "directory deleted"}

        raise FileOpsToolError("unsupported filesystem object")


def build_file_ops_tool(
    *,
    root_dir: Path | str = DEFAULT_FILE_OPS_ROOT_DIR,
    max_read_bytes: int = DEFAULT_FILE_OPS_MAX_READ_BYTES,
) -> FileOpsTool:
    return FileOpsTool(root_dir=root_dir, max_read_bytes=max_read_bytes)


def format_file_ops_response(response: FileOpsResponse) -> str:
    lines = [
        f"Action: {response.action}",
        f"Path: {response.path}",
        f"Result: {'success' if response.success else 'failed'} in {response.took_ms}ms",
        f"Message: {response.message}",
    ]
    if response.entries is not None:
        lines.append("\n=== Entries ===")
        lines.extend(response.entries)
    if response.content is not None:
        lines.append("\n=== Content ===")
        lines.append(response.content)
    return "\n".join(lines)
