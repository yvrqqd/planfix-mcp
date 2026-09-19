from collections.abc import Callable, Set
from datetime import datetime
from typing import Any

from planfix_mcp.errors import RouteError
from planfix_mcp.routing.manifest import AspectRoute
from planfix_mcp.routing.safety import assert_allowlisted_read_command

MAX_PAGE_SIZE = 50

PERSIST_KEYS = frozenset(
    {
        'saveFilter',
        'setFilter',
        'setSort',
        'saveMode',
        'changeSortType',
        'forceSortType',
        'sortTypes',
        'changed',
    }
)
_PERSIST_KEYS_CASEFOLD = frozenset(key.casefold() for key in PERSIST_KEYS)
_AJAX_READ_PARAM_KEYS = frozenset(
    {
        'client',
        'contact',
        'datafrom',
        'datato',
        'date',
        'filter',
        'firstgroupoffset',
        'folderoffset',
        'fromaction',
        'group',
        'handbook',
        'id',
        'lastaction',
        'loginid',
        'object',
        'offset',
        'operator',
        'page_size',
        'pagesize',
        'parent',
        'period',
        'project',
        'query',
        'search',
        'searchtype',
        'starred',
        'statussetid',
        'task',
        'taskid',
        'trigger',
        'user',
        'userid',
    }
)

ARG_TO_PARAM: dict[str, str] = {
    'filter': 'filter',
    'query': 'query',
    'search': 'search',
    'offset': 'offset',
    'page_size': 'pageSize',
    'last_action': 'lastAction',
    'from_action': 'fromaction',
    'folder_offset': 'folderOffset',
    'first_group_offset': 'firstGroupOffset',
    'task': 'task',
    'user': 'user',
    'project': 'project',
    'object': 'object',
    'group': 'group',
    'parent': 'parent',
    'handbook': 'handbook',
    'client': 'client',
    'period': 'period',
    'date': 'date',
    'data_from': 'dataFrom',
    'data_to': 'dataTo',
    'status_set': 'StatusSetID',
    'starred': 'starred',
    'mode': 'mode',
    'is_company': 'is_company',
    'stat_times': 'statTimes',
}

# Planfix search ignores pageSize; the UI only sends offset. Step is 20, or 40 for handbook search.
DEFAULT_SEARCH_PAGE_SIZE = 20
SEARCH_PAGE_SIZES: dict[tuple[str, str], int] = {
    ('handbooks', 'global_search'): 40,
    ('handbooks', 'data_search'): 40,
}
_SEARCH_COMMAND_PAGE_SIZES = {
    'search:handbook': 40,
    'search:handbookdata': 40,
}
_PAGING_ARGS = frozenset(
    {
        'offset',
        'page_size',
        'last_action',
        'from_action',
        'folder_offset',
        'first_group_offset',
    }
)
ENTITY_LOG_FROM = '01.01.2000 00:00:00'
_FEED_VIEW = {
    'card': '1',
    'actions': '0',
}

REQUIRED: dict[tuple[str, str], tuple[str, ...]] = {
    ('tasks', 'global_search'): ('query',),
    ('tasks', 'search_actions'): ('query',),
    ('tasks', 'tech_log'): ('task',),
    ('tasks', 'card'): ('task',),
    ('tasks', 'actions'): ('task',),
    ('tasks', 'card_data'): ('task',),
    ('tasks', 'checklist'): ('task',),
    ('tasks', 'dependencies'): ('task',),
    ('tasks', 'reminders'): ('task',),
    ('tasks', 'workers'): ('task',),
    ('tasks', 'task_contacts'): ('task',),
    ('tasks', 'subtask_count'): ('task',),
    ('tasks', 'access_logins'): ('task',),
    ('tasks', 'task_data'): ('task',),
    ('tasks', 'fields'): ('task',),
    ('projects', 'global_search'): ('query',),
    ('contacts', 'by_login'): ('user',),
    ('contacts', 'client_search'): ('query',),
    ('contacts', 'global_search'): ('query',),
    ('employees', 'global_search'): ('query',),
    ('employees', 'is_admin'): ('user',),
    ('employees', 'get'): ('user',),
    ('handbooks', 'data'): ('handbook',),
    ('handbooks', 'logs'): ('handbook',),
    ('handbooks', 'global_search'): ('query',),
    ('handbooks', 'data_search'): ('query',),
    ('documents', 'global_search'): ('query',),
    ('filters', 'get'): ('filter',),
    ('filters', 'access'): ('filter',),
    ('analytics', 'from_task'): ('task',),
    ('workspace', 'get'): ('object',),
    ('audit', 'user_log'): ('user',),
    ('audit', 'work_summary'): ('user',),
    ('automation', 'triggers'): ('status_set',),
    ('automation', 'macros'): ('status_set',),
    ('automation', 'trigger_logs'): ('status_set',),
}

LIST_DEFAULTS: dict[str, dict[str, str]] = {
    'tasks': {
        'filter': ':all',
        'filterData': 'null',
        'parent': '0',
        'project': '-1',
        'object': '0',
        'search': '',
        'starred': '0',
        'groupby': '-1',
        'mode': 'list',
        'isPageOfSubtasks': 'false',
        'isPageOfCrmtasks': 'false',
        'generalIdOfContact': '0',
        'mysubfilter': '0',
    },
    'projects': {
        'filter': ':projectsall',
        'filterData': 'null',
        'group': '0',
        'client': '0',
        'search': '',
        'starred': '0',
        'groupby': '0',
    },
    'contacts': {
        'filter': ':contact',
        'filterData': 'null',
        'search': '',
        'starred': '0',
    },
    'employees': {
        'filter': ':users',
        'filterData': 'null',
        'group': '-1',
        'active': '-1',
        'delete': '-1',
        'robots': '-1',
        'workHours': '0',
        'parent': '0',
        'project': '-1',
        'search': '',
        'starred': '0',
        'statTimes': '0',
    },
}

SEARCH_DEFAULTS: dict[tuple[str, str], dict[str, str]] = {
    ('tasks', 'global_search'): {'sortBy': 'date', 'searchByNumber': 'true', 'ignoreCompleted': '0'},
    ('tasks', 'search_actions'): {'sortBy': 'date', 'ignoreCompleted': '0'},
    ('projects', 'global_search'): {'sortBy': 'date'},
    ('contacts', 'global_search'): {'sortBy': 'date', 'searchByNumber': 'true'},
    ('contacts', 'client_search'): {'sortBy': 'date'},
    ('employees', 'global_search'): {'sortBy': 'date'},
    ('handbooks', 'global_search'): {'sortBy': 'relevance'},
    ('handbooks', 'data_search'): {'sortBy': 'relevance'},
    ('documents', 'global_search'): {'sortBy': 'date', 'view': 'preview'},
}

type ParamBuilder = Callable[[AspectRoute, dict[str, Any]], dict[str, str]]
type DetailBuilder = Callable[[str, dict[str, Any]], dict[str, str]]

PARAM_REMAPS: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {
    ('tasks', 'task_data'): (('task', 'taskId'),),
    ('contacts', 'by_login'): (('user', 'loginId'),),
    ('contacts', 'templates'): (('is_company', 'iscompany'),),
    ('employees', 'is_admin'): (('user', 'loginID'),),
    ('filters', 'get'): (('filter', 'id'),),
    ('filters', 'access'): (('filter', 'id'),),
    ('analytics', 'from_task'): (('task', 'taskId'),),
    ('audit', 'user_log'): (('user', 'userId'),),
}

READ_DEFAULTS: dict[tuple[str, str], dict[str, str]] = {
    ('filters', 'get'): {'plannerType': '8', 'isCreate': 'false'},
    ('automation', 'triggers'): {'searchData[]': ''},
}


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def _as_int(raw: Any, default: int) -> int:
    try:
        return int(raw)
    except TypeError, ValueError:
        return default


def _page_size(args: dict[str, Any]) -> str:
    size = _as_int(args.get('page_size', 50), 50)
    if size < 1:
        size = 1
    if size > MAX_PAGE_SIZE:
        size = MAX_PAGE_SIZE
    return str(size)


def _offset(args: dict[str, Any]) -> str:
    offset = _as_int(args.get('offset', 0), 0)
    if offset < 0:
        offset = 0
    return str(offset)


def _cursor(args: dict[str, Any], name: str, default: int = 0) -> str:
    value = _as_int(args.get(name, default), default)
    if value < 0:
        value = 0
    return str(value)


def _folder_offset(args: dict[str, Any], name: str) -> str:
    return str(_as_int(args.get(name, -1), -1))


def search_page_size(block: str, aspect: str) -> int:
    return SEARCH_PAGE_SIZES.get((block, aspect), DEFAULT_SEARCH_PAGE_SIZE)


def search_page_size_for_command(command: str) -> int:
    return _SEARCH_COMMAND_PAGE_SIZES.get(command, DEFAULT_SEARCH_PAGE_SIZE)


def page_window(block: str, route: AspectRoute, args: dict[str, Any]) -> tuple[int, int]:
    offset = int(_offset(args))
    if route.kind == 'search':
        return offset, search_page_size(block, route.aspect)
    return offset, int(_page_size(args))


def ajax_page_window(command: str, extra: dict[str, Any] | None) -> tuple[int, int]:
    args = {str(key).casefold(): value for key, value in (extra or {}).items()}
    offset = int(_offset({'offset': args.get('offset')}))
    if command.startswith('search:'):
        return offset, search_page_size_for_command(command)
    if 'page_size' in args or 'pagesize' in args:
        return offset, int(_page_size({'page_size': args.get('page_size', args.get('pagesize'))}))
    return offset, MAX_PAGE_SIZE


def _copy_args(args: dict[str, Any], params: dict[str, str]) -> None:
    for arg_name, param_name in ARG_TO_PARAM.items():
        if arg_name not in args or args[arg_name] is None:
            continue
        if arg_name in _PAGING_ARGS:
            continue
        params[param_name] = _stringify(args[arg_name])


def _pin_list(params: dict[str, str]) -> None:
    params['saveFilter'] = '0'
    params['setFilter'] = '0'
    params['setSort'] = '0'
    params['changed'] = '0'
    for key in ('saveMode', 'changeSortType', 'forceSortType', 'sortTypes'):
        params.pop(key, None)


def _pin_search(params: dict[str, str]) -> None:
    params['setFilter'] = '0'
    params['setSort'] = '0'


def build_raw_params(
    command: str,
    extra: dict[str, Any] | None,
    *,
    allowed_commands: Set[str],
) -> dict[str, str]:
    cleaned = assert_allowlisted_read_command(command, allowed_commands)
    params: dict[str, str] = {'command': cleaned}
    for key, value in (extra or {}).items():
        normalized_key = str(key)
        folded_key = normalized_key.casefold()
        if value is None or folded_key == 'command' or folded_key in _PERSIST_KEYS_CASEFOLD:
            continue
        if folded_key not in _AJAX_READ_PARAM_KEYS:
            raise RouteError(f'Parameter "{normalized_key}" is not in the reviewed ajax allowlist')
        if folded_key in {'page_size', 'pagesize'}:
            params['pageSize'] = _page_size({'page_size': value})
            continue
        if folded_key == 'offset':
            params['offset'] = _offset({'offset': value})
            continue
        params[normalized_key] = _stringify(value)
    if cleaned.startswith('search:'):
        params.pop('pageSize', None)
        params.setdefault('offset', '0')
    _pin_list(params)
    return params


def _feed_params(route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    return {
        'command': 'action:getNewActions',
        'task': _stringify(args['task']),
        'lastAction': _cursor(args, 'last_action'),
        'istaskview': _FEED_VIEW[route.aspect],
        'notAllActions': '0',
    }


def _card_data_params(_route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    offset = _offset(args)
    params: dict[str, str] = {
        'command': 'action:getTaskCardData',
        'task': _stringify(args['task']),
        'offset': offset,
        'pageSize': _page_size(args),
        'sort': 'desc',
        'gid': '0',
        'taskType': 'task',
        'taskcard': '1',
    }
    if int(offset) > 0:
        params['nextPage'] = '1'
        params['taskstate'] = 'comments'
    from_action = args.get('from_action')
    if from_action:
        params['fromaction'] = _stringify(from_action)
    return params


def _docs_items_params(_route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    params: dict[str, str] = {
        'command': 'docs:getItems',
        'offset': _offset(args),
        'pageSize': _page_size(args),
        'folderOffset': _folder_offset(args, 'folder_offset'),
        'firstGroupOffset': _folder_offset(args, 'first_group_offset'),
    }
    _copy_args(args, params)
    for persist_key in PERSIST_KEYS:
        params.pop(persist_key, None)
    return params


def _ajax_command(route: AspectRoute) -> str:
    command = route.command
    if command is None:
        raise RouteError(f'aspect {route.aspect} uses a path route')
    return command


def _entity_log_params(route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    # Planfix returns Logs: [] unless both dataFrom and dataTo are set.
    data_from = args.get('data_from')
    data_to = args.get('data_to')
    params: dict[str, str] = {
        'command': _ajax_command(route),
        'offset': _offset(args),
        'pageSize': _page_size(args),
        'dataFrom': _stringify(data_from) if data_from else ENTITY_LOG_FROM,
        'dataTo': _stringify(data_to) if data_to else datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
    }
    search_type = args.get('search_type')
    if search_type:
        params['searchData[2]'] = _stringify(search_type)
    return params


def _workspace_get_params(route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    return {
        'command': _ajax_command(route),
        'id': _stringify(args['object']),
        'needsAccessData': 'true',
    }


def _automation_macros_params(route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    return {
        'command': _ajax_command(route),
        'statusSetId': _stringify(args['status_set']),
        'objType': _stringify(args.get('object') or '0'),
        'groupID': '0',
        'afterChange': '0',
    }


def _automation_trigger_logs_params(route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    return {
        'command': _ajax_command(route),
        'statusSetId': _stringify(args['status_set']),
        'filterTrigger': _stringify(args.get('trigger') or '0'),
        'filterTask': _stringify(args.get('task') or '0'),
        'filterContact': _stringify(args.get('contact') or '0'),
        'filterDate': _stringify(args.get('date') or '0'),
        'operator': _stringify(args.get('operator') or ''),
        'offset': _offset(args),
        'pageSize': _page_size(args),
    }


SPECIAL_BUILDERS: dict[tuple[str, str], ParamBuilder] = {
    ('tasks', 'card'): _feed_params,
    ('tasks', 'actions'): _feed_params,
    ('tasks', 'card_data'): _card_data_params,
    ('documents', 'items'): _docs_items_params,
    ('audit', 'entity_log'): _entity_log_params,
    ('workspace', 'get'): _workspace_get_params,
    ('automation', 'macros'): _automation_macros_params,
    ('automation', 'trigger_logs'): _automation_trigger_logs_params,
}

INCOMING_WEBHOOK_SEARCH = '{"columnId":0,"value":""}'


def _incoming_webhooks_params(_route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    return {
        'currentOffset': _offset(args),
        'pageSize': _page_size(args),
        'sort': '0',
        'searchData': INCOMING_WEBHOOK_SEARCH,
    }


PATH_BUILDERS: dict[tuple[str, str], ParamBuilder] = {
    ('account_config', 'incoming_webhooks'): _incoming_webhooks_params,
}


def build_path_params(block: str, route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    if route.path is None:
        raise RouteError(f'aspect {route.aspect} is not a path route')
    missing = [name for name in REQUIRED.get((block, route.aspect), ()) if not args.get(name)]
    if missing:
        raise RouteError(f'Required for aspect {route.aspect}: {", ".join(missing)}')
    builder = PATH_BUILDERS.get((block, route.aspect))
    if builder is None:
        raise RouteError(f'path params are not configured for aspect {route.aspect}')
    return builder(route, args)


def _require_expand_arg(args: dict[str, Any], aspect: str, name: str) -> str:
    value = args.get(name)
    if not value:
        raise RouteError(f'Required for expand on aspect {aspect}: {name}')
    return _stringify(value)


def _handbook_detail(command: str, args: dict[str, Any]) -> dict[str, str]:
    handbook = _require_expand_arg(args, 'list', 'handbook')
    return {'command': command, 'handbook': handbook, 'extra': '1'}


def _template_detail(command: str, args: dict[str, Any]) -> dict[str, str]:
    object_id = _require_expand_arg(args, 'task_templates', 'object')
    return {'command': command, 'object': object_id}


def _status_set_detail(command: str, args: dict[str, Any]) -> dict[str, str]:
    status_set = _require_expand_arg(args, 'status_sets', 'status_set')
    return {'command': command, 'StatusSetID': status_set}


def _trigger_detail(command: str, args: dict[str, Any]) -> dict[str, str]:
    trigger = _require_expand_arg(args, 'triggers', 'trigger')
    return {'command': command, 'id': trigger}


DETAIL_BUILDERS: dict[tuple[str, str], DetailBuilder] = {
    ('handbooks', 'list'): _handbook_detail,
    ('account_config', 'task_templates'): _template_detail,
    ('automation', 'status_sets'): _status_set_detail,
    ('automation', 'triggers'): _trigger_detail,
}


def build_detail_params(block: str, route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    command = route.detail_command
    if command is None:
        raise RouteError(f'expand is not supported for aspect {route.aspect}')
    builder = DETAIL_BUILDERS.get((block, route.aspect))
    if builder is None:
        raise RouteError(f'expand is not configured for aspect {route.aspect}')
    return builder(command, args)


def _apply_remaps(block: str, aspect: str, params: dict[str, str]) -> None:
    for source, dest in PARAM_REMAPS.get((block, aspect), ()):
        if source in params:
            params[dest] = params.pop(source)
    for key, value in READ_DEFAULTS.get((block, aspect), {}).items():
        params.setdefault(key, value)


def build_params(block: str, route: AspectRoute, args: dict[str, Any]) -> dict[str, str]:
    command = route.command
    if route.path is not None or command is None:
        raise RouteError(f'aspect {route.aspect} uses a path route')
    missing = [name for name in REQUIRED.get((block, route.aspect), ()) if not args.get(name)]
    if missing:
        raise RouteError(f'Required for aspect {route.aspect}: {", ".join(missing)}')

    params: dict[str, str] = {'command': command}
    if route.kind == 'list':
        params.update(LIST_DEFAULTS.get(block, {}))
        params['offset'] = _offset(args)
        params['pageSize'] = _page_size(args)
        _copy_args(args, params)
        if block == 'tasks':
            params['mode'] = 'list'
        _pin_list(params)
        return params

    if route.kind == 'search':
        params['offset'] = _offset(args)
        params['query'] = _stringify(args['query'])
        params['favorite'] = 'false'
        params['usePrefix'] = '0'
        params.update(SEARCH_DEFAULTS.get((block, route.aspect), {'sortBy': 'date'}))
        _copy_args(args, params)
        _pin_search(params)
        return params

    special = SPECIAL_BUILDERS.get((block, route.aspect))
    if special is not None:
        return special(route, args)

    params['offset'] = _offset(args)
    params['pageSize'] = _page_size(args)
    _copy_args(args, params)
    for persist_key in PERSIST_KEYS:
        params.pop(persist_key, None)
    _apply_remaps(block, route.aspect, params)
    return params
