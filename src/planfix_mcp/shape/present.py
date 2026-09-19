from typing import Any

from planfix_mcp.limit import Profile, cap_payload, limit_payload
from planfix_mcp.shape.compact import compact
from planfix_mcp.shape.fields import ITEM_FIELDS
from planfix_mcp.shape.lists import extract_items, looks_like_list, shape_list
from planfix_mcp.shape.tasks import TASK_SHAPERS, shape_counts
from planfix_mcp.shape.webhooks import prepare_webhooks


def present_payload(
    payload: Any,
    *,
    block: str,
    aspect: str,
    kind: str,
    profile: Profile,
    offset: int = 0,
    page_size: int = 50,
) -> Any:
    if not isinstance(payload, dict):
        return limit_payload(payload, profile)
    if block == 'account_config' and aspect == 'incoming_webhooks':
        prepared = prepare_webhooks(payload)
        return shape_list(
            prepared,
            block=block,
            aspect=aspect,
            profile=profile,
            offset=offset,
            page_size=page_size,
            items=extract_items(prepared),
        )
    if profile == 'full':
        return cap_payload(compact(payload, profile, depth=0), profile)
    if aspect == 'counts' or isinstance(payload.get('Counts'), dict):
        return cap_payload(shape_counts(payload), profile)
    task_shaper = TASK_SHAPERS.get(aspect) if block == 'tasks' else None
    if task_shaper is not None:
        return cap_payload(task_shaper(payload, profile, offset, page_size), profile)
    items = extract_items(payload)
    if (kind in {'list', 'search'} or (block, aspect) in ITEM_FIELDS or block == 'ajax') and looks_like_list(
        payload,
        items,
    ):
        return shape_list(
            payload,
            block=block,
            aspect=aspect,
            profile=profile,
            offset=offset,
            page_size=page_size,
            items=items,
        )
    compacted = compact(payload, profile, depth=0)
    if profile == 'schema':
        return limit_payload(compacted, profile)
    return cap_payload(compacted, profile)
