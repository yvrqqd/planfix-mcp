import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from mcp.server.fastmcp import FastMCP

from planfix_mcp.config import SETTINGS
from planfix_mcp.errors import PlanfixMcpError
from planfix_mcp.logs import configure_logging
from planfix_mcp.mcp.instructions import INSTRUCTIONS
from planfix_mcp.mcp.runtime import PlanfixRuntime
from planfix_mcp.mcp.tools import register_tools

logger = logging.getLogger(__name__)


def build_server(runtime: PlanfixRuntime | None = None) -> FastMCP:
    configure_logging(SETTINGS.log_level)
    state = runtime or PlanfixRuntime()

    @asynccontextmanager
    async def lifespan(_mcp: FastMCP) -> AsyncIterator[dict[str, object]]:
        task = asyncio.create_task(_warmup(state), name='planfix-warmup')
        try:
            yield {}
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await state.close()

    mcp = FastMCP(
        name='planfix-mcp',
        instructions=INSTRUCTIONS,
        lifespan=lifespan,
    )
    register_tools(mcp, state)
    return mcp


async def _warmup(state: PlanfixRuntime) -> None:
    try:
        await state.warmup()
    except PlanfixMcpError as exc:
        logger.warning('Planfix background login failed: %s', exc.message)
    except Exception as exc:
        logger.warning('Planfix background login failed: unexpected %s', type(exc).__name__)


def main() -> None:
    server = build_server()
    server.run(transport='stdio')
