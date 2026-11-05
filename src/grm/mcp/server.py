"""MCP server entry point, built with FastMCP.

Run it on its own port for the voice team:

    uvicorn grm.mcp.server:app --host 0.0.0.0 --port 8100

The same MCP server is mounted inside the main application at /mcp, so one port
can serve both the web demo and the voice stack if that is simpler on one VM.

Transport notes, because they matter to the caller:

* Streamable HTTP, mounted at /mcp.
* `json_response=True`: replies are plain JSON, not SSE frames. A deterministic
  client should not have to parse an event stream to read one string.
* `stateless_http=True`: no Mcp-Session-Id handshake. Their service keeps its
  own call identifier; there is no protocol session to lose on a restart.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastmcp.server.http import StarletteWithLifespan

from grm.config import get_settings
from grm.mcp.constants import MCP_PREFIX, SERVER_NAME, SERVER_VERSION
from grm.mcp.tools import mcp
from grm.observability.logging import configure_logging, get_logger


def build_mcp_asgi() -> StarletteWithLifespan:
    """MCP transport as a mountable ASGI app.

    The transport owns the /mcp path itself. Mounting it at the application root
    avoids Starlette's /mcp -> /mcp/ redirect, so clients can use the canonical
    URL directly.
    """
    return mcp.http_app(path=MCP_PREFIX, json_response=True, stateless_http=True)


def create_mcp_app() -> FastAPI:
    """Standalone MCP application for the voice team's port."""
    configure_logging()
    if get_settings().demo_auto_verify:
        get_logger().warning(
            "DEMO_AUTO_VERIFY is on: identity verification bypassed",
            stage="startup",
        )
    transport = build_mcp_asgi()
    app = FastAPI(
        title="GRM MCP",
        version=SERVER_VERSION,
        description="OpenG2P Beneficiary Conversational Agent, exposed over MCP.",
        lifespan=transport.lifespan,
    )

    # Health must be declared before the root mount, or the MCP app shadows it.
    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            {"status": "ok", "service": SERVER_NAME, "transport": "mcp", "version": SERVER_VERSION}
        )

    app.mount("/", transport)

    return app


app = create_mcp_app()
