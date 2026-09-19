from typing import Any

from planfix_mcp.limit import Profile, cap_payload, list_cap
from planfix_mcp.shape.compact import as_maps, compact, is_scalar, pick, skip_key
from planfix_mcp.shape.fields import GENERIC, ITEM_FIELDS
from planfix_mcp.shape.logs import LOG_ASPECTS, normalize_log_item

_NESTED_LISTS = ('Tasks', 'Projects', 'Contacts', 'Users', 'Handbooks')
_TOP_LISTS = (
    'Items',
    'UserList',
    'Reports',
    'filters',
    'planners',
    'Actions',
    'OnlineList',
    'Logs',
    'StatusSets',
    'Templates',
    'Triggers',
    'macrosList',
    'AnaliticList',
    'Handbooks',
    'Groups',
    'Fields',
)
_SIDECARS = (
    ('FilterID', 'filter_id'),
    ('FilterName', 'filter_name'),
    ('FolderOffset', 'folder_offset'),
    ('StatusSet', 'status_set'),
    ('Groups', 'groups'),
    ('FieldTypes', 'field_types'),
    ('AnaliticFieldTypeList', 'field_types'),
    ('complexWebhooksVersion', 'complex_webhooks_version'),
)


def looks_like_list(payload: dict[str, Any], items: list[dict[str, Any]] | None) -> bool:
    return (
        items is not None
        or 'FilterID' in payload
        or 'FolderOffset' in payload
        or any(key in payload for key in _NESTED_LISTS)
    )


def extract_items(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    for wrapper in _NESTED_LISTS:
        nested = payload.get(wrapper)
        if isinstance(nested, dict) and isinstance(nested.get('Items'), list):
            return as_maps(nested['Items'])
    for key in _TOP_LISTS:
        if isinstance(payload.get(key), list):
            return as_maps(payload[key])
    return None


def shape_list(
    payload: dict[str, Any],
    *,
    block: str,
    aspect: str,
    profile: Profile,
    offset: int,
    page_size: int,
    items: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    rows_src = items or []
    if (block, aspect) in LOG_ASPECTS:
        rows_src = [normalize_log_item(item) for item in rows_src]
    sample = rows_src[0] if rows_src else {}
    fields = _fields(block, aspect, profile, sample)
    cap = min(list_cap(profile), max(page_size, 1))
    rows = [pick(item, fields, profile) for item in rows_src[:cap]]
    body: dict[str, Any] = {
        'result': payload.get('Result'),
        'items_count': len(rows_src),
        'items': rows,
    }
    body.update(paging(offset, page_size, len(rows_src), len(rows)))
    if len(rows_src) > cap:
        body['truncated'] = True
    for src, dest in _SIDECARS:
        if src in payload:
            body[dest] = compact(payload[src], profile, depth=1)
    return cap_payload(body, profile)


def paging(offset: int, page_size: int, raw_count: int, emitted_count: int) -> dict[str, Any]:
    size = page_size if page_size > 0 else 50
    has_more = raw_count > emitted_count or raw_count >= size
    body: dict[str, Any] = {'offset': offset, 'has_more': has_more}
    if has_more:
        body['next_offset'] = offset + emitted_count
    return body


def _fields(block: str, aspect: str, profile: Profile, sample: dict[str, Any]) -> tuple[str, ...]:
    configured = ITEM_FIELDS.get((block, aspect), {}).get(profile)
    if configured:
        return tuple(name for name in configured if not skip_key(name))
    wanted = GENERIC[profile]
    present = tuple(name for name in wanted if name in sample and not skip_key(name))
    if present:
        return present
    scalar = tuple(key for key, value in sample.items() if is_scalar(value) and not skip_key(key))
    limit = 3 if profile == 'schema' else 8 if profile == 'summary' else 12
    return scalar[:limit]
