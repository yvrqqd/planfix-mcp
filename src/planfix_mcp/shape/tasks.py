from collections.abc import Callable
from typing import Any

from planfix_mcp.limit import Profile, list_cap
from planfix_mcp.shape.compact import as_maps, pick
from planfix_mcp.shape.fields import ACTION, CARD

type TaskShaper = Callable[[dict[str, Any], Profile, int, int], dict[str, Any]]


def shape_counts(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get('Counts')
    rows: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, dict):
                rows.append({'id': key, 'count': value.get('Count')})
            else:
                rows.append({'id': key, 'count': value})
    return {'result': payload.get('Result'), 'counts': rows}


def shape_task(payload: dict[str, Any], profile: Profile, offset: int, page_size: int) -> dict[str, Any]:
    del offset, page_size
    task = payload.get('Task')
    if not isinstance(task, dict):
        task = _task_from_actions(payload)
    return {'result': payload.get('Result'), 'task': pick(task, CARD[profile], profile)}


def shape_actions(payload: dict[str, Any], profile: Profile, offset: int, page_size: int) -> dict[str, Any]:
    del offset, page_size
    raw = as_maps(payload.get('Actions'))
    selected = raw[: list_cap(profile)]
    rows = []
    for item in selected:
        row = pick(item, ACTION[profile], profile)
        type_obj = item.get('Type')
        if isinstance(type_obj, dict) and 'Type' in ACTION[profile]:
            row['Type'] = type_obj.get('Acr', type_obj.get('Name'))
        rows.append(row)
    body: dict[str, Any] = {
        'result': payload.get('Result'),
        'items_count': len(raw),
        'items': rows,
    }
    if len(raw) > len(selected):
        body['truncated'] = True
    cursor = _action_cursor(selected)
    if cursor is not None:
        body['last_action'] = cursor
    return body


def shape_card_data(payload: dict[str, Any], profile: Profile, offset: int, page_size: int) -> dict[str, Any]:
    raw = as_maps(payload.get('Actions'))
    cap = min(list_cap(profile), max(page_size, 1))
    selected = raw[:cap]
    exists = payload.get('isExistsOtherActions')
    has_more = _truthy(exists) or len(raw) > len(selected) or len(raw) >= page_size
    body: dict[str, Any] = {
        'result': payload.get('Result'),
        'items_count': len(raw),
        'items': [pick(item, ACTION[profile], profile) for item in selected],
        'offset': offset,
        'has_more': has_more,
        'is_exists_other_actions': _truthy(exists),
        'actions_skipped': payload.get('ActionsSkipped'),
    }
    if len(raw) > len(selected):
        body['truncated'] = True
    if has_more:
        step = len(selected) if len(raw) > len(selected) else page_size
        body['next_offset'] = offset + step
    created = payload.get('TaskCreatedAction')
    if isinstance(created, dict):
        body['created'] = pick(created, ACTION[profile], profile)
    task = payload.get('Task')
    if isinstance(task, dict):
        body['task'] = pick(task, CARD[profile], profile)
    last_id = payload.get('LastActionID')
    if last_id is not None:
        body['last_action'] = last_id
    return body


TASK_SHAPERS: dict[str, TaskShaper] = {
    'card': shape_task,
    'actions': shape_actions,
    'card_data': shape_card_data,
}


def _task_from_actions(payload: dict[str, Any]) -> dict[str, Any]:
    for item in as_maps(payload.get('Actions')):
        nested = item.get('Task')
        if isinstance(nested, dict) and nested:
            return nested
    return {}


def _action_cursor(items: list[dict[str, Any]]) -> int | None:
    ids: list[int] = []
    for item in items:
        try:
            ids.append(int(item['ID']))
        except KeyError, TypeError, ValueError:
            continue
    return max(ids) if ids else None


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, int | float):
        return value != 0
    return isinstance(value, str) and value.strip().lower() in {'1', 'true', 'yes'}
