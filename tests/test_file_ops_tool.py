from __future__ import annotations

from pathlib import Path

import pytest

from agent.tools.file_ops import FileOpsTool, FileOpsToolError, format_file_ops_response


@pytest.mark.asyncio
async def test_file_ops_write_and_read(tmp_path: Path) -> None:
    tool = FileOpsTool(root_dir=tmp_path)

    await tool.execute(action="write_file", path="notes/hello.txt", content="ciao")
    result = await tool.execute(action="read_file", path="notes/hello.txt")

    assert result.success is True
    assert result.content == "ciao"
    assert result.bytes_read == 4

    await tool.aclose()


@pytest.mark.asyncio
async def test_file_ops_append_file(tmp_path: Path) -> None:
    tool = FileOpsTool(root_dir=tmp_path)

    await tool.execute(action="write_file", path="a.txt", content="hello")
    await tool.execute(action="append_file", path="a.txt", content=" world")
    result = await tool.execute(action="read_file", path="a.txt")

    assert result.content == "hello world"

    await tool.aclose()


@pytest.mark.asyncio
async def test_file_ops_make_and_list_dir(tmp_path: Path) -> None:
    tool = FileOpsTool(root_dir=tmp_path)

    await tool.execute(action="make_dir", path="docs")
    await tool.execute(action="write_file", path="docs/a.txt", content="A")
    await tool.execute(action="write_file", path="docs/b.txt", content="B")
    result = await tool.execute(action="list_dir", path="docs")

    assert result.entries is not None
    assert "docs/a.txt" in result.entries
    assert "docs/b.txt" in result.entries
    assert "entries" in result.message

    await tool.aclose()


@pytest.mark.asyncio
async def test_file_ops_delete_file(tmp_path: Path) -> None:
    tool = FileOpsTool(root_dir=tmp_path)

    await tool.execute(action="write_file", path="tmp.txt", content="x")
    await tool.execute(action="delete_path", path="tmp.txt")

    with pytest.raises(FileOpsToolError, match="not found"):
        await tool.execute(action="read_file", path="tmp.txt")

    await tool.aclose()


@pytest.mark.asyncio
async def test_file_ops_delete_dir_recursive(tmp_path: Path) -> None:
    tool = FileOpsTool(root_dir=tmp_path)

    await tool.execute(action="write_file", path="dir/sub/file.txt", content="x")
    result = await tool.execute(action="delete_path", path="dir", recursive=True)

    assert "recursively" in result.message

    await tool.aclose()


@pytest.mark.asyncio
async def test_file_ops_rejects_path_escape(tmp_path: Path) -> None:
    tool = FileOpsTool(root_dir=tmp_path)

    with pytest.raises(FileOpsToolError, match="escapes sandbox"):
        await tool.execute(action="read_file", path="../../etc/passwd")

    await tool.aclose()


@pytest.mark.asyncio
async def test_file_ops_rejects_unsupported_action(tmp_path: Path) -> None:
    tool = FileOpsTool(root_dir=tmp_path)

    with pytest.raises(FileOpsToolError, match="unsupported action"):
        await tool.execute(action="rename", path="a.txt")

    await tool.aclose()


@pytest.mark.asyncio
async def test_file_ops_read_is_truncated(tmp_path: Path) -> None:
    tool = FileOpsTool(root_dir=tmp_path, max_read_bytes=5)

    await tool.execute(action="write_file", path="big.txt", content="abcdefghijk")
    result = await tool.execute(action="read_file", path="big.txt")

    assert result.content == "abcde"
    assert result.bytes_read == 5
    assert "truncated" in result.message

    await tool.aclose()


@pytest.mark.asyncio
async def test_file_ops_arun_returns_dict(tmp_path: Path) -> None:
    tool = FileOpsTool(root_dir=tmp_path)

    payload = await tool.arun(action="write_file", path="hello.txt", content="ok")

    assert isinstance(payload, dict)
    assert payload["success"] is True
    assert payload["action"] == "write_file"
    assert "message" in payload

    await tool.aclose()


@pytest.mark.asyncio
async def test_format_file_ops_response_includes_key_sections(tmp_path: Path) -> None:
    tool = FileOpsTool(root_dir=tmp_path)

    await tool.execute(action="write_file", path="x.txt", content="hello")
    result = await tool.execute(action="read_file", path="x.txt")
    formatted = format_file_ops_response(result)

    assert "Action:" in formatted
    assert "Message:" in formatted
    assert "=== Content ===" in formatted

    await tool.aclose()
