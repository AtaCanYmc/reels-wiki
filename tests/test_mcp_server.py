from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from reels_wiki.config import Config
from reels_wiki.mcp_server import create_mcp_server


def _call_tool_json(server, name: str, args: dict) -> dict:
    res = asyncio.run(server.call_tool(name, args))
    contents = res.content if hasattr(res, "content") else (res[0] if isinstance(res, tuple) else res)
    return json.loads(contents[0].text)


def test_mcp_server_registers_expected_tools(tmp_path: Path) -> None:
    server = create_mcp_server(Config(vault_path=tmp_path))
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}

    assert names == {"enqueue_reel", "import_ig_export", "process_reels_queue", "get_queue_stats"}
    for tool in tools:
        schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
        assert schema["type"] == "object"


def test_mcp_tools_delegate_and_return_json(tmp_path: Path) -> None:
    server = create_mcp_server(Config(vault_path=tmp_path))

    with patch("reels_wiki.mcp_server.enqueue", return_value={"enqueued": True, "shortcode": "ABC12345678"}):
        enq = _call_tool_json(server, "enqueue_reel", {"url": "https://www.instagram.com/reel/ABC12345678/"})
    assert enq["enqueued"] is True

    with patch(
        "reels_wiki.mcp_server._import_ig_export",
        return_value={"found": 2, "enqueued": 2, "duplicates": 0, "ignored": 0},
    ) as mock_imp:
        imp = _call_tool_json(server, "import_ig_export", {"export_path": str(tmp_path / "saved_posts.json")})
    mock_imp.assert_called_once()
    assert imp["enqueued"] == 2

    with patch(
        "reels_wiki.mcp_server.process_queue",
        return_value={"selected": 1, "processed": 1, "skipped": 0, "failed": 0},
    ) as mock_proc:
        proc = _call_tool_json(server, "process_reels_queue", {"limit": 1, "force": True})
    mock_proc.assert_called_once()
    assert mock_proc.call_args.kwargs["re_extract"] is True
    assert proc["processed"] == 1

    with patch("reels_wiki.mcp_server.queue_stats", return_value={"total_indexed": 5}):
        stats = _call_tool_json(server, "get_queue_stats", {})
    assert stats["total_indexed"] == 5
