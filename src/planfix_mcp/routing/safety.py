import re
from collections.abc import Set
from urllib.parse import urlsplit

from planfix_mcp.errors import RouteError

_J_PATH = re.compile(r'^/j/[A-Za-z][A-Za-z0-9]*/[A-Za-z][A-Za-z0-9]*$')

WRITE_ACTION_PREFIXES = (
    'create',
    'add',
    'set',
    'save',
    'update',
    'delete',
    'remove',
    'change',
    'toggle',
    'del',
    'close',
    'apply',
    'attach',
    'copy',
    'move',
    'restore',
    'enable',
    'disable',
    'rename',
    'lock',
    'unlock',
    'import',
    'invite',
    'archive',
    'publish',
    'send',
    'assign',
    'transfer',
    'accept',
    'reject',
    'stop',
    'start',
    'clear',
    'reset',
    'freeze',
    'hide',
    'generate',
    'complete',
    'reopen',
    'edit',
    'execute',
    'mark',
)
FORBIDDEN_COMMANDS = frozenset({'logon:auth'})


def assert_read_command(command: str) -> str:
    cleaned = command.strip()
    namespace, sep, action = cleaned.partition(':')
    if (
        not sep
        or not namespace
        or not action
        or ':' in action
        or namespace != namespace.strip()
        or action != action.strip()
    ):
        raise RouteError('command must be namespace:action')
    if cleaned.lower() in FORBIDDEN_COMMANDS:
        raise RouteError(f'Command "{cleaned}" is not allowed')
    lowered = action.lower()
    if any(lowered.startswith(prefix) for prefix in WRITE_ACTION_PREFIXES):
        raise RouteError(f'Write command "{cleaned}" is not allowed')
    return cleaned


def assert_allowlisted_read_command(command: str, allowed_commands: Set[str]) -> str:
    cleaned = assert_read_command(command)
    if cleaned not in allowed_commands:
        raise RouteError(f'Command "{cleaned}" is not in the reviewed read allowlist')
    return cleaned


def assert_j_path(path: str) -> str:
    cleaned = path.strip()
    if not _J_PATH.fullmatch(cleaned) or '..' in cleaned or '?' in cleaned or '#' in cleaned:
        raise RouteError('path must be /j/resource/action')
    action = cleaned.rsplit('/', 1)[-1]
    lowered = action.lower()
    if any(lowered.startswith(prefix) for prefix in WRITE_ACTION_PREFIXES):
        raise RouteError(f'Write path "{cleaned}" is not allowed')
    return cleaned


def assert_referer(referer: str) -> str:
    cleaned = referer.strip()
    parsed = urlsplit(cleaned)
    if (
        not cleaned.startswith('/')
        or cleaned.startswith('//')
        or '\\' in cleaned
        or '..' in cleaned
        or '#' in cleaned
        or parsed.scheme
        or parsed.netloc
        or parsed.fragment
    ):
        raise RouteError('referer must be a relative same-origin path')
    return cleaned
