"""Disposable local official-SDK MCP server fixture for stdio, StreamableHTTP, and SSE tests."""
from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any

import anyio
from mcp.server import Server
from mcp.server.lowlevel.server import ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.stdio import stdio_server
import mcp_types as types


def build_stdio_server(mode: str) -> Server:
    pid_file = os.environ.get("FIXTURE_PID_FILE")
    if pid_file:
        Path(pid_file).write_text(str(os.getpid()), encoding="utf-8")

    state_counter = {"calls": 0}

    # Emit synthetic secret noise to stderr to verify parent discards stderr.
    sys.stderr.write(f"STDERR_NOISE secret={os.environ.get('SYNTHETIC_STDIO_SECRET', '')}\n")
    sys.stderr.flush()

    async def handle_list_tools(
        _ctx: ServerRequestContext[Any],
        params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        cursor = params.cursor if params else None
        if mode == "infinite_cursor":
            return types.ListToolsResult(
                tools=[
                    types.Tool(
                        name=f"page_tool_{cursor or '0'}",
                        description="Paginated tool",
                        input_schema={"type": "object", "properties": {}},
                    )
                ],
                next_cursor="1",
            )
        if mode == "external_ref":
            return types.ListToolsResult(
                tools=[
                    types.Tool(
                        name="bad_ref_tool",
                        description="Has external ref",
                        input_schema={
                            "type": "object",
                            "properties": {"x": {"$ref": "https://evil.invalid/schema.json"}},
                        },
                    )
                ]
            )
        if mode == "secret_in_schema":
            sec = os.environ.get("SYNTHETIC_STDIO_SECRET", "fallback-secret")
            return types.ListToolsResult(
                tools=[
                    types.Tool(
                        name="leaking_schema_tool",
                        description="Schema leaks secret in enum",
                        input_schema={
                            "type": "object",
                            "properties": {"token": {"type": "string", "enum": [sec, "public"]}},
                        },
                    )
                ]
            )
        if mode == "secret_in_name":
            sec = os.environ.get("SYNTHETIC_STDIO_SECRET", "fallback-secret")
            return types.ListToolsResult(
                tools=[
                    types.Tool(
                        name=f"tool_{sec}",
                        description="Name leaks secret",
                        input_schema={"type": "object", "properties": {}},
                    )
                ]
            )
        if mode == "duplicate_tools":
            return types.ListToolsResult(
                tools=[
                    types.Tool(name="dup", description="First", input_schema={"type": "object", "properties": {}}),
                    types.Tool(name="dup", description="Second", input_schema={"type": "object", "properties": {}}),
                ]
            )
        if mode == "runtime_stateful":
            return types.ListToolsResult(
                tools=[
                    types.Tool(
                        name="stateful_step",
                        title="Stateful Step",
                        description="Increments in-process counter and optionally writes side-effect log",
                        input_schema={
                            "type": "object",
                            "properties": {
                                "tag": {"type": "string"},
                                "delay": {"type": "number"},
                            },
                            "required": ["tag"],
                        },
                        annotations=types.ToolAnnotations(read_only_hint=True),
                    ),
                    types.Tool(
                        name="peer_info",
                        title="Peer Info",
                        description="Second tool on the same server sharing the live process",
                        input_schema={
                            "type": "object",
                            "properties": {"note": {"type": "string"}},
                        },
                    ),
                    types.Tool(
                        name="media_and_error",
                        description="Returns image or tool error",
                        input_schema={
                            "type": "object",
                            "properties": {
                                "fail": {"type": "boolean"},
                                "open_meta": {"type": "object"},
                                "$ref": {"type": "string"},
                            },
                        },
                    ),
                ],
                next_cursor=None,
            )
        if mode == "paginated":
            if cursor is None:
                return types.ListToolsResult(
                    tools=[
                        types.Tool(
                            name="echo_env",
                            title="Echo Env",
                            description=f"Echoes env (secret={os.environ.get('SYNTHETIC_STDIO_SECRET', '')})",
                            input_schema={
                                "type": "object",
                                "properties": {
                                    "message": {"type": "string"},
                                    "extra": {"type": "object"},
                                },
                                "required": ["message"],
                            },
                            annotations=types.ToolAnnotations(read_only_hint=True),
                        )
                    ],
                    next_cursor="page2",
                )
            return types.ListToolsResult(
                tools=[
                    types.Tool(
                        name="slow_op",
                        description="Sleeps when requested",
                        input_schema={
                            "type": "object",
                            "properties": {"delay": {"type": "number"}},
                        },
                    ),
                    types.Tool(
                        name="media_and_error",
                        description="Returns image or tool error",
                        input_schema={
                            "type": "object",
                            "properties": {"fail": {"type": "boolean"}},
                        },
                    ),
                ],
                next_cursor=None,
            )
        return types.ListToolsResult(tools=[])

    async def handle_call_tool(
        _ctx: ServerRequestContext[Any],
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        name = params.name
        args = dict(params.arguments or {})
        if name == "stateful_step":
            state_counter["calls"] += 1
            call_no = state_counter["calls"]
            log_file = os.environ.get("FIXTURE_CALL_LOG")
            if log_file:
                with Path(log_file).open("a", encoding="utf-8") as fh:
                    fh.write(f"{os.getpid()}:{call_no}:{args.get('tag', '')}\n")
            delay = float(args.get("delay", 0.0) or 0.0)
            if delay > 0:
                await anyio.sleep(delay)
            sec = os.environ.get("SYNTHETIC_STDIO_SECRET", "")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"pid={os.getpid()} call={call_no} tag={args.get('tag', '')} secret={sec}",
                    )
                ],
                structured_content={
                    "pid": os.getpid(),
                    "call_count": call_no,
                    "tag": args.get("tag", ""),
                    "secret_echo": sec,
                },
            )
        if name == "peer_info":
            state_counter["calls"] += 1
            call_no = state_counter["calls"]
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"peer pid={os.getpid()} call={call_no} note={args.get('note', '')}",
                    )
                ],
                structured_content={
                    "pid": os.getpid(),
                    "call_count": call_no,
                    "note": args.get("note", ""),
                },
            )
        if name == "echo_env":
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=(
                            f"msg={args.get('message', '')} "
                            f"secret={os.environ.get('SYNTHETIC_STDIO_SECRET', '')} "
                            f"ambient={os.environ.get('AMBIENT_APP_SENTINEL', 'ABSENT')}"
                        ),
                    )
                ],
                structured_content={
                    "message": args.get("message", ""),
                    "extra": args.get("extra"),
                    "ambient": os.environ.get("AMBIENT_APP_SENTINEL", "ABSENT"),
                    "leaked_secret": os.environ.get("SYNTHETIC_STDIO_SECRET", ""),
                },
            )
        if name == "slow_op":
            delay = float(args.get("delay", 5.0))
            await anyio.sleep(delay)
            return types.CallToolResult(content=[types.TextContent(type="text", text="done")])
        if name == "media_and_error":
            if args.get("fail"):
                return types.CallToolResult(
                    is_error=True,
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Tool failed with secret={os.environ.get('SYNTHETIC_STDIO_SECRET', '')}",
                        )
                    ],
                )
            b64_img = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            return types.CallToolResult(
                content=[
                    types.TextContent(type="text", text="Generated image"),
                    types.ImageContent(type="image", data=b64_img, mime_type="image/png"),
                    types.ResourceLink(type="resource_link", uri="https://remote.invalid/do-not-fetch.png", name="remote"),
                ]
            )
        return types.CallToolResult(
            is_error=True,
            content=[types.TextContent(type="text", text=f"Unknown tool {name}")],
        )

    return Server(
        "fixture-stdio-server",
        version="1.2.3",
        on_list_tools=handle_list_tools,
        on_call_tool=handle_call_tool,
    )


async def run_stdio(mode: str) -> None:
    if mode == "hang_init":
        pid_file = os.environ.get("FIXTURE_PID_FILE")
        if pid_file:
            Path(pid_file).write_text(str(os.getpid()), encoding="utf-8")
        await anyio.sleep(60)
        return
    srv = build_stdio_server(mode)
    async with stdio_server() as (read_stream, write_stream):
        await srv.run(read_stream, write_stream, srv.create_initialization_options())


def create_http_mcp_server() -> MCPServer:
    mcp = MCPServer("fixture-http-server", version="2.0.0")

    @mcp.tool(description="Add two integers and report status")
    def add_numbers(a: int, b: int) -> dict:
        return {"sum": a + b, "note": "secret-token-http-999"}

    @mcp.tool(description="Inspect open payload")
    def inspect_payload(payload: dict) -> str:
        return f"keys={sorted(payload.keys())}"

    return mcp


if __name__ == "__main__":
    mode_arg = sys.argv[1] if len(sys.argv) > 1 else "paginated"
    anyio.run(run_stdio, mode_arg)
