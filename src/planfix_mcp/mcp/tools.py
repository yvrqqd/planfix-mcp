from collections.abc import Awaitable
from inspect import Parameter, Signature
from typing import Any, Literal, Protocol

from mcp.server.fastmcp import FastMCP

from planfix_mcp.errors import PlanfixMcpError
from planfix_mcp.ids import load_id_glossary
from planfix_mcp.limit import Profile
from planfix_mcp.mcp.descriptions import block_description
from planfix_mcp.mcp.runtime import SESSION_ASPECTS
from planfix_mcp.routing.aliases import ALIASES
from planfix_mcp.routing.manifest import Manifest
from planfix_mcp.toon import encode

ProfileLit = Literal['schema', 'summary', 'detail', 'full']

BLOCK_ARGS: dict[str, tuple[str, ...]] = {
    'tasks': (
        'query',
        'filter',
        'search',
        'offset',
        'page_size',
        'last_action',
        'from_action',
        'task',
        'project',
        'object',
        'parent',
    ),
    'projects': ('query', 'filter', 'search', 'offset', 'page_size', 'group', 'client'),
    'contacts': ('query', 'filter', 'search', 'offset', 'page_size', 'user', 'is_company'),
    'employees': ('query', 'filter', 'search', 'offset', 'page_size', 'user', 'group', 'parent', 'project'),
    'handbooks': ('query', 'filter', 'search', 'offset', 'page_size', 'handbook', 'expand'),
    'documents': ('query', 'offset', 'page_size', 'folder_offset', 'first_group_offset'),
    'planners': ('offset', 'page_size', 'filter', 'object', 'parent'),
    'filters': ('offset', 'page_size', 'filter', 'parent'),
    'analytics': ('offset', 'page_size', 'task'),
    'reports': ('offset', 'page_size'),
    'automation': (
        'offset',
        'page_size',
        'object',
        'expand',
        'status_set',
        'trigger',
        'task',
        'contact',
        'date',
        'operator',
    ),
    'account_config': ('offset', 'page_size', 'object', 'expand'),
    'workspace': ('offset', 'page_size', 'object'),
    'audit': (
        'offset',
        'page_size',
        'user',
        'task',
        'period',
        'date',
        'data_from',
        'data_to',
        'search_type',
    ),
    'session': (),
}


def block_args(block: str) -> tuple[str, ...]:
    return BLOCK_ARGS.get(block, ('offset', 'page_size'))


def tool_aspects(manifest: Manifest, block: str) -> tuple[str, ...]:
    catalog = manifest.aspect_names(block)
    aliases = tuple(
        alias for (alias_block, alias), target in ALIASES.items() if alias_block == block and target in catalog
    )
    if block == 'session':
        return SESSION_ASPECTS + catalog + aliases
    return catalog + aliases


def _annotation(name: str) -> object:
    if name in {'offset', 'page_size', 'last_action', 'folder_offset', 'first_group_offset'}:
        return int
    if name == 'expand':
        return bool
    return str | None


def _default(name: str) -> object:
    if name in {'offset', 'last_action'}:
        return 0
    if name in {'folder_offset', 'first_group_offset'}:
        return -1
    if name == 'page_size':
        return 50
    if name == 'expand':
        return False
    return None


def _profile(value: str) -> Profile:
    if value not in {'schema', 'summary', 'detail', 'full'}:
        return 'summary'
    return value  # type: ignore[return-value]


def _signature(block: str, aspects: tuple[str, ...]) -> Signature:
    aspect_type = Literal[*aspects]
    parameters = [
        Parameter('aspect', Parameter.POSITIONAL_OR_KEYWORD, annotation=aspect_type),
    ]
    for name in block_args(block):
        parameters.append(
            Parameter(
                name,
                Parameter.POSITIONAL_OR_KEYWORD,
                default=_default(name),
                annotation=_annotation(name),
            ),
        )
    parameters.append(
        Parameter(
            'response_profile',
            Parameter.POSITIONAL_OR_KEYWORD,
            default='summary',
            annotation=ProfileLit,
        ),
    )
    return Signature(parameters, return_annotation=str)


class ToolRuntime(Protocol):
    manifest: Manifest

    async def call_block(
        self,
        block: str,
        *,
        aspect: str,
        args: dict[str, Any],
        response_profile: Profile,
    ) -> Any: ...

    async def call_ajax(
        self,
        command: str,
        *,
        params: dict[str, Any] | None,
        response_profile: Profile,
    ) -> Any: ...


AJAX_DESCRIPTION = (
    'Raw Planfix POST /ajax/ for reviewed reads. Prefer domain tools first. '
    'command must be an exact read command already present in the reviewed routing manifest; '
    'unknown commands and unreviewed parameter names are refused. '
    'params are allowlisted selector/paging form fields. Persist flags are pinned to 0. '
    'Pagination: lists use offset+pageSize (pageSize capped at 50). search:* ignores pageSize '
    '(step 20, handbook 40). Recognizable list payloads return items, has_more, and next_offset; '
    'do not use a raw Planfix Offset field. Task feed is lastAction, not offset; comment history is '
    'action:getTaskCardData with nextPage=1 when offset>0. '
    'response_profile: schema | summary (operational fields) | detail (analysis) | '
    'full (non-secret Planfix structure / debug). Result is TOON text. '
    'Prefer summary; full is for unknown keys.'
)


def register_tools(mcp: FastMCP, state: ToolRuntime) -> None:
    for block in state.manifest.block_order:
        _register_block(mcp, state, block)
    _register_ajax(mcp, state)
    _register_resources(mcp)


def _register_block(mcp: FastMCP, state: ToolRuntime, block: str) -> None:
    aspects = tool_aspects(state.manifest, block)
    description = block_description(block, aspects)

    async def _call(**kwargs: Any) -> str:
        aspect = str(kwargs.pop('aspect'))
        profile = _profile(str(kwargs.pop('response_profile', 'summary')))
        return await _toon(
            state.call_block(block, aspect=aspect, args=kwargs, response_profile=profile),
        )

    _call.__name__ = block
    _call.__signature__ = _signature(block, aspects)  # type: ignore[attr-defined]
    mcp.add_tool(_call, name=block, description=description, structured_output=False)


def _register_ajax(mcp: FastMCP, state: ToolRuntime) -> None:
    async def ajax(
        command: str,
        params: dict[str, Any] | None = None,
        response_profile: ProfileLit = 'summary',
    ) -> str:
        return await _toon(
            state.call_ajax(command, params=params, response_profile=_profile(response_profile)),
        )

    ajax.__doc__ = AJAX_DESCRIPTION
    mcp.tool(name='ajax', description=AJAX_DESCRIPTION, structured_output=False)(ajax)


def _register_resources(mcp: FastMCP) -> None:
    @mcp.resource(
        'planfix://ids',
        name='ids',
        description=(
            'Planfix id kinds for reads. Users see the task number (GeneralID); '
            'AJAX card/actions use internal TaskID. This server cannot write business records.'
        ),
        mime_type='application/json',
    )
    def ids() -> dict[str, Any]:
        return load_id_glossary()


async def _toon(operation: Awaitable[Any]) -> str:
    try:
        return encode(await operation)
    except PlanfixMcpError as exc:
        raise RuntimeError(exc.message) from None
