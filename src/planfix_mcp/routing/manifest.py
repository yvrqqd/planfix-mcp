import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from planfix_mcp.errors import RouteError
from planfix_mcp.routing.aliases import ALIASES
from planfix_mcp.routing.safety import assert_j_path, assert_read_command, assert_referer

Kind = Literal['read', 'list', 'search', 'overview']

OVERVIEW_COMMAND = '__overview__'
_PINNED_LIST_COMMANDS = frozenset(
    {
        'task:changeFilter',
        'project:changeFilter',
        'crm:changeFilter',
        'user:changeFilter',
    }
)
_REVIEWED_READ_EXCEPTIONS = frozenset({'log:changeSummaryDate'})
_ROUTE_KEYS = frozenset({'aspect', 'command', 'detail_command', 'path', 'detail_path', 'referer'})


@dataclass(frozen=True, slots=True)
class AspectRoute:
    aspect: str
    command: str | None
    detail_command: str | None
    kind: Kind
    path: str | None = None
    detail_path: str | None = None
    referer: str | None = None


@dataclass(frozen=True, slots=True)
class OverviewSection:
    section: str
    command: str


@dataclass(frozen=True, slots=True)
class Manifest:
    block_order: tuple[str, ...]
    aspects: dict[str, dict[str, AspectRoute]]
    overview_sections: tuple[OverviewSection, ...]
    ajax_commands: frozenset[str]
    j_paths: frozenset[str]

    def aspect(self, block: str, name: str) -> AspectRoute:
        try:
            return self.aspects[block][name]
        except KeyError as exc:
            raise KeyError(f'unknown aspect "{name}" for {block}') from exc

    def aspect_names(self, block: str) -> tuple[str, ...]:
        return tuple(self.aspects.get(block, {}))


def classify_command(command: str) -> Kind:
    if command == OVERVIEW_COMMAND:
        return 'overview'
    if command.startswith('search:'):
        return 'search'
    _namespace, sep, action = command.partition(':')
    if sep and action == 'changeFilter':
        return 'list'
    return 'read'


_DEFAULT_ROUTING = Path(__file__).resolve().parent.parent / 'data' / 'routing.json'


def _invalid(message: str) -> None:
    raise ValueError(f'invalid routing manifest: {message}')


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        _invalid(f'{label} must be a non-empty string')
    return value


def _validate_read_command(command: str, *, allow_overview: bool = False) -> None:
    if allow_overview and command == OVERVIEW_COMMAND:
        return
    if command in _PINNED_LIST_COMMANDS or command in _REVIEWED_READ_EXCEPTIONS:
        return
    try:
        assert_read_command(command)
    except RouteError as exc:
        _invalid(exc.message)


def _is_ajax_read_command(command: str) -> bool:
    try:
        assert_read_command(command)
    except RouteError:
        return False
    return True


def _optional_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _validate_j_path(path: str) -> str:
    try:
        return assert_j_path(path)
    except RouteError as exc:
        raise ValueError(f'invalid routing manifest: {exc.message}') from exc


def _validate_referer(referer: str) -> str:
    try:
        return assert_referer(referer)
    except RouteError as exc:
        raise ValueError(f'invalid routing manifest: {exc.message}') from exc


def _parse_route(block: str, item: dict[str, Any]) -> AspectRoute:
    unknown = set(item) - _ROUTE_KEYS
    if unknown:
        _invalid(f'unknown keys for {block}: {", ".join(sorted(unknown))}')
    aspect = _text(item.get('aspect'), f'aspect for {block}')
    command = _optional_text(item.get('command'), f'command for {block}/{aspect}')
    path = _optional_text(item.get('path'), f'path for {block}/{aspect}')
    if (command is None) == (path is None):
        _invalid(f'route {block}/{aspect} must have exactly one of command or path')
    detail_command = _optional_text(item.get('detail_command'), f'detail command for {block}/{aspect}')
    detail_path = _optional_text(item.get('detail_path'), f'detail path for {block}/{aspect}')
    referer = _optional_text(item.get('referer'), f'referer for {block}/{aspect}')
    if path is not None:
        if detail_command is not None:
            _invalid(f'detail_command requires command for {block}/{aspect}')
        if referer is None:
            _invalid(f'path route {block}/{aspect} requires referer')
        path = _validate_j_path(path)
        referer = _validate_referer(referer)
        if detail_path is not None:
            detail_path = _validate_j_path(detail_path)
        return AspectRoute(
            aspect=aspect,
            command=None,
            detail_command=None,
            kind='read',
            path=path,
            detail_path=detail_path,
            referer=referer,
        )
    if detail_path is not None:
        _invalid(f'detail_path requires path for {block}/{aspect}')
    if referer is not None:
        _invalid(f'referer is only valid with path for {block}/{aspect}')
    assert command is not None
    _validate_read_command(command, allow_overview=True)
    if detail_command is not None:
        _validate_read_command(detail_command)
    return AspectRoute(
        aspect=aspect,
        command=command,
        detail_command=detail_command,
        kind=classify_command(command),
    )


def load_manifest(path: Path | None = None) -> Manifest:
    decoded = json.loads((path or _DEFAULT_ROUTING).read_text(encoding='utf-8'))
    if not isinstance(decoded, dict):
        _invalid('root must be an object')
    payload: dict[str, Any] = decoded
    raw_order = payload.get('block_order')
    raw_routes = payload.get('aspect_routes')
    if not isinstance(raw_order, list) or not isinstance(raw_routes, dict):
        _invalid('block_order must be a list and aspect_routes must be an object')
    block_order = tuple(_text(block, 'block') for block in raw_order)
    if len(block_order) != len(set(block_order)):
        _invalid('block_order contains duplicates')
    if set(block_order) != set(raw_routes):
        _invalid('block_order and aspect_routes must contain the same blocks')

    aspects: dict[str, dict[str, AspectRoute]] = {}
    for block in block_order:
        routes = raw_routes[block]
        if not isinstance(routes, list) or not routes:
            _invalid(f'routes for {block} must be a non-empty list')
        mapped: dict[str, AspectRoute] = {}
        for item in routes:
            if not isinstance(item, dict):
                _invalid(f'route for {block} must be an object')
            aspect = _text(item.get('aspect'), f'aspect for {block}')
            if aspect in mapped:
                _invalid(f'duplicate aspect "{aspect}" for {block}')
            mapped[aspect] = _parse_route(block, item)
        aspects[block] = mapped

    raw_overview = payload.get('overview_sections', [])
    if not isinstance(raw_overview, list):
        _invalid('overview_sections must be a list')
    overview_rows: list[OverviewSection] = []
    overview_names: set[str] = set()
    for item in raw_overview:
        if not isinstance(item, dict):
            _invalid('overview section must be an object')
        section = _text(item.get('section'), 'overview section')
        command = _text(item.get('command'), f'overview command for {section}')
        if section in overview_names:
            _invalid(f'duplicate overview section "{section}"')
        _validate_read_command(command)
        overview_names.add(section)
        overview_rows.append(OverviewSection(section=section, command=command))

    for (block, alias), target in ALIASES.items():
        if block not in aspects or target not in aspects[block] or alias in aspects[block]:
            _invalid(f'invalid alias "{alias}" for {block}/{target}')

    commands = {
        command
        for routes in aspects.values()
        for route in routes.values()
        for command in (route.command, route.detail_command)
        if command is not None and _is_ajax_read_command(command)
    }
    commands.update(row.command for row in overview_rows if _is_ajax_read_command(row.command))
    j_paths = {
        path
        for routes in aspects.values()
        for route in routes.values()
        for path in (route.path, route.detail_path)
        if path is not None
    }

    return Manifest(
        block_order=block_order,
        aspects=aspects,
        overview_sections=tuple(overview_rows),
        ajax_commands=frozenset(commands),
        j_paths=frozenset(j_paths),
    )
